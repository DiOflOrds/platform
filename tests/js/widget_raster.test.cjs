// Das 2x2-Raster im Renderer (SWR-210, team-dashboard/T-0005, Brief N-0004).
//
// ⚠⚠ **Die Uebersetzung Zustand -> Text liegt in `Regeln` und nicht im Renderer.** Diese
// Datei haelt genau das fest: `app.js` fragt `Regeln.widgetRaster` und faellt keine
// eigene Entscheidung darueber, wie „nicht erhoben" aussieht. Eine zweite Stelle, die
// `nicht_geliefert` in Worte fasst, ist die Familie, die dieses Haus zwoelfmal gefunden
// hat — und sie faengt immer als eine Zeile im Renderer an.
"use strict";
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const WURZEL = path.resolve(__dirname, "..", "..", "..");
const REGELN = path.join(WURZEL, "platform", "backend", "static", "regeln.js");
const APP = path.join(WURZEL, "platform", "backend", "static", "app.js");

const kontext = { window: {}, document: { addEventListener() {} }, console };
kontext.globalThis = kontext;
vm.createContext(kontext);
vm.runInContext(fs.readFileSync(REGELN, "utf8"), kontext, { filename: "regeln.js" });
const Regeln = kontext.Regeln || kontext.window.Regeln;

let bestanden = 0;
function pruefe(name, fn) {
  fn();
  bestanden += 1;
  console.log("ok - " + name);
}

const EINTRAG = {
  takt: "tag", zustand: "wert", datum: "2026-08-20", mails: 42, reaktion: 3,
  zusammenfassung_verfuegbar: true,
  kacheln: [
    { schluessel: "in", beschriftung: "IN", wert: 42, zustand: "wert", grund: "" },
    { schluessel: "reaktion", beschriftung: "Reaktion", wert: 3, zustand: "wert", grund: "" },
    { schluessel: "rechnung", beschriftung: "Rechnung", wert: 0, zustand: "echte_null", grund: "" },
    { schluessel: "spam", beschriftung: "SPAM", wert: null, zustand: "nicht_geliefert",
      grund: "keine Quelle: der Digest fuehrt keine SPAM-Rubrik (CR an team-mail, team-mail/T-0007)" }
  ]
};

pruefe("vier Kacheln in der Reihenfolge der Vorlage", () => {
  const r = Regeln.widgetRaster(EINTRAG);
  assert.deepStrictEqual(r.map(k => k.schluessel), ["in", "reaktion", "rechnung", "spam"]);
});

pruefe("echte Null wird als 0 gezeigt und NICHT als 'keine Daten'", () => {
  const r = Regeln.widgetRaster(EINTRAG);
  const rechnung = r.find(k => k.schluessel === "rechnung");
  assert.strictEqual(rechnung.text, "0");
  assert.strictEqual(rechnung.unbekannt, false);
});

pruefe("nicht_geliefert wird als 'keine Daten' gezeigt und NICHT als 0", () => {
  const r = Regeln.widgetRaster(EINTRAG);
  const spam = r.find(k => k.schluessel === "spam");
  assert.strictEqual(spam.unbekannt, true);
  assert.notStrictEqual(spam.text, "0");
  assert.ok(spam.grund.length > 0, "die Kachel sagt nicht, warum sie nichts weiss");
});

pruefe("nur die Reaktions-Kachel ist klappbar", () => {
  const r = Regeln.widgetRaster(EINTRAG);
  assert.deepStrictEqual(r.filter(k => k.klappbar).map(k => k.schluessel), ["reaktion"]);
});

pruefe("ohne verfuegbare Zusammenfassung klappt auch Reaktion nicht", () => {
  // ⚠ Die Gegenrichtung: sonst verspraeche die Kachel ein Aufklappen, hinter dem nichts
  // liegt — und der Mensch tippt gegen eine Wand.
  const ohne = Object.assign({}, EINTRAG, { zusammenfassung_verfuegbar: false });
  assert.strictEqual(Regeln.widgetRaster(ohne).filter(k => k.klappbar).length, 0);
});

pruefe("ein Eintrag ohne kacheln ergibt ein leeres Raster und keinen Absturz", () => {
  // ⚠ Laenge statt deepStrictEqual: das leere Raster entsteht IM VM-Kontext und ist
  // deshalb nicht referenzgleich mit einem Array des Testprozesses. Ein Vergleich, der
  // an der Kontextgrenze scheitert, misst die Grenze und nicht die Sache.
  assert.strictEqual(Regeln.widgetRaster({}).length, 0);
  assert.strictEqual(Regeln.widgetRaster(null).length, 0);
});

pruefe("der Renderer faellt KEINE eigene Zustandsentscheidung", () => {
  // ⚠⚠ Der eigentliche Gegenstand dieser Datei. `app.js` darf das Wort
  // `nicht_geliefert` im Raster-Block nicht selbst auswerten.
  const quelle = fs.readFileSync(APP, "utf8");
  const start = quelle.indexOf("var raster = Regeln.widgetRaster(e);");
  assert.ok(start > 0, "der Raster-Block fehlt im Renderer");
  const block = quelle.slice(start, quelle.indexOf("karte.appendChild(dl);", start));
  assert.ok(!block.includes("nicht_geliefert"),
    "der Renderer uebersetzt Zustaende selbst — zweite Antwort auf dieselbe Frage");
  assert.ok(block.includes("k.unbekannt") && block.includes("k.grund"),
    "der Renderer benutzt die Marken aus Regeln nicht");
});

console.log("\n" + bestanden + " Zusicherung(en) gruen (widget_raster).");
