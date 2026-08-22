// SWR-224/SWR-225 (team-dashboard/T-0007, Brief p0/N-0002 des Auftraggebers).
//
// > *„das ist viel zu groß und hat noch alte inhalte mit darstellungsfehlern, das muss in
// > einen normalen kleinen widget reinpassen."*
//
// **Der Befund, gemessen am laufenden Renderweg und nicht am Screenshot:** `widgetKarte`
// lief über `w.eintraege` und zeichnete JEDEN Eintrag. Bei `team-mail` sind das drei
// versprochene Takte (`tag`, `woche`, `monat`) mit je vier Kacheln — **12 Kacheln** in
// einem Raster, das der Vertrag für EINE Zeitreihe vorsieht.
//
// ⚠⚠ **Und Ursache 2 (überlappende Spalten) steht im Code, nicht im Bild:** `.widget dl`
// ist ein Grid mit `grid-template-columns: auto 1fr`. Der Renderer hängte je Eintrag DREI
// Kinder hinein (`dt`, `dd`, `dd`-mit-Raster) — das dritte landet damit in der **schmalen
// ersten Spalte der nächsten Zeile**. Genau das zeigt der Screenshot: die Überschrift
// „Woche" oben rechts, ihre Karten weit darunter, Monat-Text in Fingerbreite.
//
// > **Ein Vertrag, der eine Obergrenze nennt, und ein Renderer, der sie nicht liest, sind
// > zwei Aussagen über dieselbe Kachel — und sichtbar ist die des Renderers.**
//
// ⚠ Diese Datei misst die STRUKTUR, nicht die Pixel. Sie kann nicht sagen, wie hoch die
// Kachel im Browser wird; sie kann sagen, wie viele Kacheln und wie viele Rasterzeilen
// entstehen — und genau das war die Ursache. Was ein Browser zeigen muss, steht im Ticket
// als offener Punkt und nicht hier als Behauptung.
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const { ladeKontext, WURZEL } = require("./_app_laden.cjs");

const INDEX = path.join(WURZEL, "platform", "backend", "static", "index.html");
const APP = path.join(WURZEL, "platform", "backend", "static", "app.js");

const SPAM_GRUND = "Rubrik 'Braucht Blick oder Reaktion' fehlt in diesem Digest";

function kacheln(takt, grund) {
  return [
    { schluessel: "in", beschriftung: "IN", wert: 165, zustand: "wert", grund: "" },
    { schluessel: "reaktion", beschriftung: "Reaktion", wert: 4, zustand: "wert", grund: "" },
    { schluessel: "rechnung", beschriftung: "Rechnung", wert: 0, zustand: "echte_null", grund: "" },
    { schluessel: "spam", beschriftung: "SPAM", wert: null, zustand: "nicht_geliefert",
      grund: grund || SPAM_GRUND },
  ];
}

/** Der Payload, wie ihn `team-mail` heute liefert: drei versprochene Takte. */
function postWidget(sicht) {
  return {
    id: "team-mail-post", titel: "Post", auftrag: "Zeigt, was in der Post liegt.",
    ziel: "#/team/team-mail", sicht_takt: sicht || "tag", digests_ohne_takt: 0,
    eintraege: [
      { takt: "tag", zustand: "wert", datum: "2026-08-20", mails: 26, reaktion: 1,
        zusammenfassung_verfuegbar: true, kacheln: kacheln("tag") },
      { takt: "woche", zustand: "wert", datum: "2026-08-16", mails: 165, reaktion: 4,
        zusammenfassung_verfuegbar: true, kacheln: kacheln("woche") },
      { takt: "monat", zustand: "nicht_geliefert", grund: "noch keiner erstellt",
        datum: null, mails: null, reaktion: null, reaktion_zustand: "nicht_geliefert",
        zusammenfassung_verfuegbar: false, kacheln: kacheln("monat") },
    ],
  };
}

/** Alle Knoten eines Baums mit dieser Klasse — der Mini-DOM kennt kein querySelectorAll. */
function mitKlasse(knoten, klasse) {
  const raus = [];
  (function lauf(k) {
    if (!k || typeof k !== "object") return;
    if (String(k.className || "").split(" ").indexOf(klasse) >= 0) raus.push(k);
    (k.kinder || []).forEach(lauf);
  })(knoten);
  return raus;
}

function karte(w) {
  const kontext = ladeKontext();
  assert.strictEqual(typeof kontext.widgetKarte, "function",
                     "widgetKarte nicht im Kontext — der Nachweis prueft sonst nichts");
  return kontext.widgetKarte(w);
}

test("SWR-224: von drei versprochenen Takten wird GENAU EINER gezeichnet", () => {
  const k = karte(postWidget("tag"));
  const dl = (k.kinder || []).find((x) => x.tagName === "dl");
  assert.ok(dl, "kein <dl> in der Karte");
  const titel = (dl.kinder || []).filter((x) => x.tagName === "dt");
  assert.strictEqual(titel.length, 1,
    "gezeichnete Zeitraeume: " + titel.length + " — der Vertrag v2.9 laesst EINEN zu");
});

test("SWR-224: vier Kacheln statt zwoelf — die gemessene Ursache von p0/N-0002", () => {
  const k = karte(postWidget("tag"));
  assert.strictEqual(mitKlasse(k, "wkachel").length, 4,
    "die Kachelzahl ist wieder groesser als ein Raster — genau der Befund des Auftraggebers");
  assert.strictEqual(mitKlasse(k, "widget-raster").length, 1, "mehr als EIN Raster");
});

test("GEGENPROBE: der alte Zustand WAERE rot — drei Eintraege sind drei Raster", () => {
  // ⚠ Ohne diese Probe belegt der Test oben nur, dass er gruen ist. Gezaehlt wird hier
  // direkt am Payload, was der alte Renderer gezeichnet haette.
  const w = postWidget("tag");
  const alteKachelzahl = w.eintraege.reduce((n, e) => n + e.kacheln.length, 0);
  assert.strictEqual(alteKachelzahl, 12,
    "die Vorlage traegt nicht mehr 12 Kacheln — dann misst der Vergleich nichts");
  assert.ok(alteKachelzahl > 4, "der Unterschied, um den es geht, ist verschwunden");
});

test("SWR-224: gezeigt wird der Takt aus sicht_takt und nicht der erste der Liste", () => {
  // ⚠⚠ Die schaerfere Haelfte. Ein Renderer, der IMMER den ersten Eintrag nimmt, bestuende
  // beide Tests darueber — die Reihenfolge der Liste ist aber keine Zusage des Vertrags.
  const k = karte(postWidget("woche"));
  const dl = (k.kinder || []).find((x) => x.tagName === "dl");
  const dt = (dl.kinder || []).filter((x) => x.tagName === "dt");
  assert.strictEqual(dt.length, 1);
  assert.strictEqual(dt[0].textContent, "Woche",
    "gezeigt wird '" + dt[0].textContent + "' statt des in sicht_takt genannten Takts");
});

test("SWR-224: ein sicht_takt ohne Eintrag zeigt NICHTS statt irgendetwas", () => {
  // Eine Kachel, die bei kaputter Eingabe den falschen Zeitraum zeigt, ist schlimmer als
  // eine leere: die eine faellt auf, die andere nicht.
  const w = postWidget("quartal");
  const k = karte(w);
  const dl = (k.kinder || []).find((x) => x.tagName === "dl");
  assert.strictEqual((dl.kinder || []).filter((x) => x.tagName === "dt").length, 0);
});

test("SWR-224: die uebrigen Zeitraeume werden GENANNT, nicht verschwiegen", () => {
  const k = karte(postWidget("tag"));
  const hinweis = mitKlasse(k, "weitere-takte");
  assert.strictEqual(hinweis.length, 1, "kein Hinweis auf die uebrigen Zeitraeume");
  assert.ok(hinweis[0].textContent.includes("Woche")
            && hinweis[0].textContent.includes("Monat"),
            "der Hinweis nennt die uebrigen Takte nicht beim Namen");
});

test("SWR-225: ein Grund, den mehrere Kacheln tragen, steht EINMAL", () => {
  const kontext = ladeKontext();
  const e = postWidget("tag").eintraege[0];
  // Zwei Kacheln mit demselben Grund — der Fall aus dem Screenshot (3x wortgleich).
  e.kacheln[2].grund = SPAM_GRUND;
  assert.strictEqual(kontext.Regeln.widgetGemeinsamerGrund(e), SPAM_GRUND);
  const k = kontext.widgetKarte(Object.assign(postWidget("tag"), { eintraege: [e] }));
  const wie_oft = k.textContent.split(SPAM_GRUND).length - 1;
  assert.strictEqual(wie_oft, 1,
    "der Grund steht " + wie_oft + "x — ein Satz, der sich je Kachel wiederholt, macht "
    + "aus einer Begruendung eine Tapete");
});

test("SWR-225: ein Grund, der GENAU EINER Kachel gehoert, bleibt AN ihr", () => {
  // ⚠ Die Gegenrichtung, und sie ist die wichtigere: wuerde jeder Grund gehoben, wuesste
  // niemand mehr, welche Kachel er erklaert.
  const kontext = ladeKontext();
  const e = postWidget("tag").eintraege[0];
  assert.strictEqual(kontext.Regeln.widgetGemeinsamerGrund(e), "",
    "ein einzelner Grund wird faelschlich als gemeinsam behandelt");
  const zellen = mitKlasse(kontext.widgetKarte(
    Object.assign(postWidget("tag"), { eintraege: [e] })), "wkachel")
    .filter((z) => String(z.className).includes("leer"));
  assert.ok(zellen.length >= 1, "keine leere Kachel im Nachweis");
  assert.ok(zellen.some((z) => z.textContent.includes(SPAM_GRUND)),
            "der Grund ist von seiner Kachel weggewandert");
});

test("SWR-108-GEGENPROBE: die Kachel wird nicht dadurch klein, dass sie Information verliert", () => {
  // ⚠⚠ Die Auflage aus der DoD von T-0007. „Klein" darf nicht heissen „weniger wahr":
  // `keine Daten` (nicht erhoben) und `0` (nichts vorgefallen) muessen BEIDE sichtbar
  // bleiben — sonst waere die Reparatur ein Informationsverlust mit gutem Aussehen.
  const k = karte(postWidget("tag"));
  const text = k.textContent;
  assert.ok(text.includes("keine Daten"), "der Zustand 'nicht erhoben' ist verschwunden");
  assert.ok(text.includes("0"), "die echte Null ist verschwunden");
  assert.ok(text.includes(SPAM_GRUND), "der Grund der leeren Kachel ist verschwunden");
});

test("URSACHE 2: das Raster spannt beide Spalten des dl-Grids", () => {
  // ⚠⚠ Der Kern des Darstellungsfehlers: `.widget dl` hat `grid-template-columns: auto 1fr`.
  // Ein drittes Kind ohne Spannweite faellt in die SCHMALE erste Spalte der naechsten Zeile.
  const k = karte(postWidget("tag"));
  const dl = (k.kinder || []).find((x) => x.tagName === "dl");
  const raster_dd = (dl.kinder || []).filter(
    (x) => x.tagName === "dd" && String(x.className).includes("raster-zeile"));
  assert.strictEqual(raster_dd.length, 1,
    "das Raster haengt ohne Spannklasse im dl-Grid — genau die ueberlappenden Spalten");
  const css = fs.readFileSync(INDEX, "utf8");
  assert.ok(/\.widget\s+dd\.raster-zeile\s*\{[^}]*grid-column\s*:\s*1\s*\/\s*-1/.test(css),
    "die Regel `.widget dd.raster-zeile { grid-column: 1 / -1 }` fehlt in index.html — "
    + "die Klasse allein spannt nichts");
});

test("der Renderer faellt KEINE eigene Entscheidung ueber den sichtbaren Takt", () => {
  // ⚠ Dieselbe Familie wie in widget_raster.test.cjs: die Auswahl gehoert in `Regeln`.
  // Ein `sicht_takt`-Vergleich im Renderer waere die zweite Stelle, die den Vertrag liest.
  const quelle = fs.readFileSync(APP, "utf8");
  const start = quelle.indexOf("function widgetKarte(");
  const block = quelle.slice(start, quelle.indexOf("\n}", start));
  assert.ok(block.includes("Regeln.widgetSichtEintrag"),
            "der Renderer benutzt die Auswahl aus Regeln nicht");
  assert.ok(!/e\.takt\s*===\s*w\.sicht_takt/.test(block),
            "der Renderer vergleicht den Takt selbst — zweite Antwort auf dieselbe Frage");
});
