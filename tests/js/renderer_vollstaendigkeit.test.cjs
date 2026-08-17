// Vollständigkeitsnachweis des Renderers (SWR-099, projects/p12/T-0008 (Teil a von T-0005)).
//
// **Die Frage, die dieser Test beantwortet:** schluckt `mdRender` aus `app.js` Text, den
// es nicht versteht? SWR-099 verlangt den Nachweis **gegen den Bestand** und **vor** der
// Umstellung — ein Renderer, der Text verliert, fällt sonst erst an dem Brief auf, bei dem
// es darauf ankam.
//
// ⚠ **Warum der Renderer hier aus `app.js` geladen und nicht nachgebaut wird.** Ein
// zweiter Renderer im Test wäre ein zweiter Renderpfad — und P12 ist eine
// **Zusammenführung**: mit zwei Wegen zu enden ist genau das Ziel, das sie verfehlen kann.
// Deshalb wird die Datei gelesen, in einem eigenen Kontext ausgeführt und mit einem
// **winzigen** DOM versehen, das nur kann, was der Renderer aufruft.
//
// ⚠ Der DOM-Ersatz ist bewusst arm. Könnte er mehr als `createElement`,
// `createTextNode`, `appendChild`, `className`, `setAttribute` und `textContent`, wäre
// er eine zweite Annahme darüber, was der Renderer tut.
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const WURZEL = path.resolve(__dirname, "..", "..", "..");
const APP = path.join(WURZEL, "platform", "backend", "static", "app.js");

/** Ein Knoten, der genau so viel kann, wie der Renderer verlangt. */
function knoten(tag) {
  return {
    tagName: tag, kinder: [], className: "", attrs: {},
    appendChild(k) { this.kinder.push(k); return k; },
    addEventListener() {},
    setAttribute(k, v) { this.attrs[k] = v; },
    get textContent() {
      return this.kinder.map((k) => (k.text !== undefined ? k.text : k.textContent))
        .join("");
    },
  };
}

/** `mdRender` aus der ECHTEN app.js, in einem Kontext mit Mini-DOM. */
function ladeRenderer() {
  const quelle = fs.readFileSync(APP, "utf8");
  const dokument = {
    createElement: (t) => knoten(t),
    createTextNode: (t) => ({ text: String(t), textContent: String(t) }),
    // ⚠ `getElementById` liefert einen Knoten und nicht `null`: app.js haengt beim Start
    // Ereignisse an feste Elemente. Mit `null` stirbt der Ladevorgang, und der Nachweis
    // waere still uebersprungen — die Lage aus SWR-114.
    getElementById: () => knoten("div"),
    querySelector: () => knoten("div"),
    addEventListener() {},
    querySelectorAll: () => [],
    body: knoten("body"),
  };
  // ⚠ `location` steht als eigener Name im Kontext und nicht nur unter `window`: app.js
  // liest beides. Ohne ihn wirft der Startlauf ASYNCHRON, nachdem der Test schon gruen
  // gemeldet hat — Node meldet das als `unhandledRejection`, und der Testlauf ist rot,
  // waehrend jede einzelne Zusicherung gruen dasteht. Das ist die unangenehmste
  // Fehlerform, die diese Bauart hergibt.
  const kontext = {
    document: dokument, location: { hash: "", search: "" },
    window: { location: { hash: "", search: "" }, addEventListener() {} },
    console, setTimeout, clearTimeout, setInterval: () => 0, clearInterval: () => {},
    // ⚠ Ein `fetch`, das NIE aufloest — und das ist eine Entscheidung, keine Bequemlichkeit.
    // Der Startlauf von app.js haengt an `fetch`; loest es auf, laeuft danach die ganze
    // Oberflaeche in einem Mini-DOM weiter und wirft ASYNCHRON, nachdem der Test schon
    // gruen gemeldet hat. Node meldet das als `unhandledRejection`: jede Zusicherung gruen,
    // der Lauf rot. Statt dem DOM-Ersatz eine API nach der anderen nachzuruesten — was ihn
    // in einen zweiten Browser verwandelte — wird der Start hier SAUBER ANGEHALTEN. Geladen
    // wird die Datei fuer ihre Funktionsdeklarationen; ihre Oberflaeche prueft dieser Test
    // ausdruecklich nicht.
    fetch: () => new Promise(() => {}),
    URLSearchParams, encodeURIComponent, decodeURIComponent, Promise, Date, JSON, Math,
    localStorage: { getItem: () => null, setItem() {} },
  };
  vm.createContext(kontext);
  // ⚠ Der Modulaufbau von app.js ist eine Folge von Funktionsdeklarationen ohne
  // Seiteneffekt beim Laden bis auf den Start am Ende — der laeuft ins Leere, weil das
  // Mini-DOM nichts findet. Ein Fehler dabei ist KEIN Grund, den Nachweis ausfallen zu
  // lassen: er wuerde ihn still ueberspringen, und das ist die Lage aus SWR-114.
  try {
    vm.runInContext(quelle, kontext, { filename: "app.js" });
  } catch (e) {
    throw new Error("app.js liess sich nicht laden: " + e.message);
  }
  assert.strictEqual(typeof kontext.mdRender, "function",
                     "mdRender nicht gefunden — der Nachweis prueft sonst nichts");
  return kontext.mdRender;
}

/** Die Zeichen, die SWR-099 als **Markup** ausnimmt — und sonst keine. */
const MARKUP = /[#*`|\-\[\]()>_\s]/g;

// ⚠⚠ **Der erste rote Lauf dieses Nachweises war ein Fehler der MESSUNG, nicht des
// Renderers.** Er meldete an sieben Briefen fehlende Ziffern und Punkte — `1.`, `2.`,
// `3.`, `4.`. Das sind die **Marken einer Nummernliste**: die Quelle schreibt sie, das
// `<ol>` erzeugt sie, und der Renderer wirft daher nichts weg. Die obige Zeichenklasse
// kennt `-` und `*` als Listenmarke und Ziffern nicht.
//
// > **Was als „Markup" gilt, ist eine Entscheidung der Messung — und eine unsaubere
// > macht einen richtigen Renderer rot.**
//
// Ein solcher Dauerbefund waere schlimmer als kein Nachweis: er trainiert das Wegsehen an
// (die Falle aus SWR-131), und zwar an genau der Pruefung, die spaeter einen echten
// Verlust zeigen soll. Die Struktur wird deshalb **zeilenweise** entfernt, bevor die
// Zeichen gezaehlt werden: die fuehrende Marke einer Zeile ist Markup, eine Ziffer
// mitten im Satz nicht.
const ZEILEN_MARKE = /^\s*(?:#{1,4}\s+|(?:\d+\.|[-*])\s+|>\s?)/;

/** Der Textbestand: Sprintberichte und Briefe der Organisation. */
function bestand() {
  const dateien = [];
  const orte = [
    path.join(WURZEL, "pm", "management", "briefkasten"),
    path.join(WURZEL, "platform", "management", "briefkasten"),
    path.join(WURZEL, "team-dashboard", "management", "briefkasten"),
    path.join(WURZEL, "team-mail", "management", "briefkasten"),
    path.join(WURZEL, "promt-team", "management", "briefkasten"),
    path.join(WURZEL, "p0", "management", "briefkasten"),
  ];
  orte.forEach((ort) => {
    if (!fs.existsSync(ort)) return;
    fs.readdirSync(ort).filter((n) => n.endsWith(".md"))
      .forEach((n) => dateien.push(path.join(ort, n)));
  });
  return dateien;
}

/** Nicht-Whitespace ohne Markup — die Menge, die SWR-099 erhalten wissen will.
 *
 * `quelle=true` entfernt zusaetzlich die **zeilenfuehrende Struktur**. Sie wird nur auf
 * der Quellseite entfernt, weil nur dort welche steht: im Ergebnis ist die Liste ein
 * `<ol>` und die Ueberschrift ein `<h2>`.
 */
function nutztext(s, quelle) {
  let text = String(s);
  if (quelle) {
    text = text.split("\n").map((z) => z.replace(ZEILEN_MARKE, "")).join("\n");
  }
  return text.replace(MARKUP, "");
}

test("Der Bestand ist nicht leer — sonst prueft der Nachweis nichts", () => {
  assert.ok(bestand().length >= 20,
            "weniger als 20 Briefe gefunden: " + bestand().length);
});

test("SWR-099: der Renderer verliert im Bestand kein Nutzzeichen", () => {
  const mdRender = ladeRenderer();
  const verluste = [];
  bestand().forEach((datei) => {
    const quelle = fs.readFileSync(datei, "utf8");
    const gerendert = mdRender(quelle).textContent;
    const soll = nutztext(quelle, true);
    const ist = nutztext(gerendert);
    // Zeichenweise Bilanz: welche Zeichen kommen in der Quelle oefter vor als im
    // Ergebnis? ⚠ Eine reine Laengenpruefung wuerde einen Verlust uebersehen, den ein
    // anderer Zuwachs ausgleicht — und genau so ein Fall waere der unangenehmste.
    const zaehle = (s) => {
      const m = new Map();
      for (const c of s) m.set(c, (m.get(c) || 0) + 1);
      return m;
    };
    const a = zaehle(soll), b = zaehle(ist);
    const fehlt = [];
    for (const [c, n] of a) {
      const m = b.get(c) || 0;
      if (m < n) fehlt.push(c + "×" + (n - m));
    }
    if (fehlt.length) {
      verluste.push(path.basename(datei) + ": " + fehlt.slice(0, 8).join(" "));
    }
  });
  assert.deepStrictEqual(
    verluste, [],
    "SWR-099 verletzt — der Renderer schluckt Text:\n  " + verluste.join("\n  "));
});

test("GEGENPROBE: der Nachweis wuerde einen Verlust BEMERKEN", () => {
  // ⚠ Ohne diese Zusicherung belegt der Test oben nur, dass er gruen ist. Ein Renderer,
  // der alles wegwirft, muss ihn rot machen — sonst misst er nichts.
  const wegwerfer = () => ({ textContent: "" });
  const quelle = "Ein Satz mit Inhalt.";
  const soll = nutztext(quelle, true);
  const ist = nutztext(wegwerfer(quelle).textContent);
  assert.ok(soll.length > 0 && ist.length === 0,
            "die Bilanz erkennt einen Totalverlust nicht");
});

test("GEGENPROBE: eine Ziffer MITTEN IM SATZ bleibt Nutztext", () => {
  // ⚠ Die Gegenrichtung der Korrektur oben, und die wichtigere: die Strukturregel darf
  // nicht so weit gefasst sein, dass sie echte Zahlen verschluckt. Ginge sie zu weit,
  // waere der Nachweis blind fuer den Verlust jeder Jahreszahl und jedes Betrags.
  const soll = nutztext("Wir haben 7 Laeufe und 138 Anforderungen.", true);
  assert.ok(soll.includes("7"), "die Strukturregel frisst Ziffern im Satz");
  assert.ok(soll.includes("138"), "die Strukturregel frisst Zahlen im Satz");
});

test("GEGENPROBE: eine Listenmarke am Zeilenanfang gilt als Markup", () => {
  const soll = nutztext("1. Erster Punkt\n2. Zweiter Punkt", true);
  assert.ok(!soll.includes("1"), "die Listenmarke wird als Nutztext gezaehlt");
  assert.ok(soll.includes("ErsterPunkt"), "der Inhalt hinter der Marke fehlt");
});

test("Codebloecke: der belegte Einzelfall aus platform/N-0002", () => {
  // ⚠ Der Renderer kennt heute KEINE Zaeune (```). Dieser Test misst, was daraus folgt,
  // statt es zu behaupten — und er nennt die Datei, damit der Befund pruefbar ist.
  const mdRender = ladeRenderer();
  const quelle = "Text davor.\n\n```\nvar x = 1;\n```\n\nText danach.";
  const ist = mdRender(quelle).textContent;
  assert.ok(ist.includes("Text davor"), "Text vor dem Zaun fehlt");
  assert.ok(ist.includes("Text danach"), "Text nach dem Zaun fehlt");
  assert.ok(ist.includes("var x = 1;"),
            "SWR-099: der Inhalt eines Codeblocks faellt heraus");
});
