// Der EINE Ladeweg fuer `app.js` in der JS-Teststrecke (p12/T-0006).
//
// ⚠⚠ **Warum das eine eigene Datei ist und keine Kopie in jeder Testdatei.** P12 ist eine
// Zusammenfuehrung; mit zwei Wegen zu enden ist das Ziel, das sie verfehlen kann. Das gilt
// fuer den Renderer **und fuer seine Pruefstrecke**: zwei Harnische, die `app.js` in zwei
// leicht verschiedene Mini-DOMs laden, sind zwei Aussagen darueber, was der Renderer
// vorfindet — und sie waeren an dem Tag verschieden, an dem es darauf ankommt.
//
// ⚠ Die Datei heisst NICHT `*.test.cjs` und wird deshalb von `js_tests.py` nicht als
// Testdatei eingesammelt (Muster: `.*\.test\.(c|m)?js$`). Sie ist Werkzeug, kein Nachweis.
//
// ⚠ Der DOM-Ersatz ist bewusst arm. Koennte er mehr als `createElement`,
// `createTextNode`, `appendChild`, `className`, `setAttribute` und `textContent`, waere
// er eine zweite Annahme darueber, was der Renderer tut.
"use strict";
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const WURZEL = path.resolve(__dirname, "..", "..", "..");
const APP = path.join(WURZEL, "platform", "backend", "static", "app.js");
// ⚠ SWR-098 (p12/T-0006): der Inline-Pass fragt `Regeln` nach dem Ticketziel, seit
// die Erkennung dort sitzt. `index.html` laedt `regeln.js` VOR `app.js` (Zeile 167/168)
// — der Nachweis tut dasselbe und baut kein Ersatz-`Regeln`: eine nachgebaute
// Ticketaufloesung waere eine zweite Antwort auf die Frage, gegen die SWR-150 gebaut ist.
const REGELN = path.join(WURZEL, "platform", "backend", "static", "regeln.js");

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

/** Die ECHTE app.js (mit regeln.js davor) in einem Kontext mit Mini-DOM. */
function ladeKontext() {
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
    vm.runInContext(fs.readFileSync(REGELN, "utf8"), kontext, { filename: "regeln.js" });
    vm.runInContext(quelle, kontext, { filename: "app.js" });
  } catch (e) {
    throw new Error("app.js liess sich nicht laden: " + e.message);
  }
  assert.strictEqual(typeof kontext.mdRender, "function",
                     "mdRender nicht gefunden — der Nachweis prueft sonst nichts");
  assert.strictEqual(typeof kontext.Regeln, "object",
                     "Regeln nicht im Kontext — der Inline-Pass faende kein Ticketziel");
  return kontext;
}

/** Nur der Renderer — der haeufigste Fall, damit die Aufrufer nichts auspacken. */
function ladeRenderer() { return ladeKontext().mdRender; }


module.exports = { knoten, ladeRenderer, ladeKontext, WURZEL, APP, REGELN };
