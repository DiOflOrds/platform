// SWR-223 (platform/T-0074): dieselbe Bauform wie `bestandswaechter.py`, in JS.
//
// **Der Befund.** Die CI von `platform` checkt `platform`, `process` und
// `produkt-datakonv` aus — sonst nichts. `renderer_vollstaendigkeit.test.cjs` misst aber
// am **echten Bestand**: es liest die Briefkästen von `pm`, `platform`, `team-dashboard`,
// `team-mail`, `promt-team` und `p0`. In der CI ist davon genau einer da, und die
// Zusicherung „Der Bestand ist nicht leer" wird rot — als **einziger** roter JS-Test von
// 116, gemessen im nachgestellten CI-Checkout.
//
// ⚠ **Was hier NICHT passiert: die Zusicherung entschärfen.** Die Schwelle „mindestens 20
// Briefe" bleibt, wo der Bestand da ist. Sie ist der Grund, warum der Nachweis darunter
// überhaupt etwas sagt (SWR-128-Familie). Geändert wird nur, WORAN der Lauf erkennt, dass
// er messen kann — und das wird **benannt**, nicht geraten.
//
// ⚠ `node:test` zählt einen `skip` als `ok`. Damit das kein stilles Grün wird, nennt der
// Grund die fehlende Eingabe beim Namen, und die Gegenprobe wohnt auf der Python-Seite:
// `test_bestandswaechter.AmVollenBestandUeberspringtNichts` ist rot, sobald eine
// deklarierte Eingabe auch dort fehlt, wo alles da sein muss.
"use strict";
const fs = require("node:fs");
const path = require("node:path");

const WURZEL = path.resolve(__dirname, "..", "..", "..");

/** Welche der benannten Eingaben fehlt? — Namen, in Deklarationsreihenfolge. */
function fehlende(...eingaben) {
  return eingaben.filter((e) => !fs.existsSync(path.join(WURZEL, ...e.split("/"))));
}

/** Der Grund für einen Skip — oder `undefined`, wenn nichts fehlt.
 *
 * Rückgabewert ist direkt als `{ skip: grund(...) }` verwendbar: `undefined` heißt bei
 * `node:test` „nicht überspringen".
 */
function grund(...eingaben) {
  const fehlt = fehlende(...eingaben);
  if (!fehlt.length) return undefined;
  return "Eingabe fehlt: " + fehlt.join(", ")
    + " — diese Zusicherung misst den echten Bestand der Organisation und hat hier "
    + "nichts zu lesen (SWR-223). Sie ist NICHT abgeschaltet: am vollständigen Bestand "
    + "läuft sie, und SWR-222 misst, dass sie das kann.";
}

module.exports = { WURZEL, fehlende, grund };
