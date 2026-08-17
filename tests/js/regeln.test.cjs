// Teststrecke fuer die Renderregeln des Briefverlaufs (SWR-128; ADR-008).
//
// Laeuft mit dem **eingebauten** Testrunner von Node (`node --test`) — kein npm, kein
// package.json, keine Abhaengigkeit. Das ist die Bedingung, unter der ADR-008 diesen Weg
// gewaehlt hat; ein Testlauf, der erst etwas herunterlaedt, waere eine andere Entscheidung
// gewesen (und Klasse A).
//
// ⚠ Die Gegenproben sind hier kein Beiwerk. Sprint 11 hat fuenf Alttests gefunden, die
// **die Provokation** ersetzt hatten statt der Erwartung — ein Test, der nur den guten Fall
// zeigt, belegt eine Nachsicht und nennt sie eine Steuerung. Jede Zusicherung hier hat
// deshalb einen Fall, der gegen die **naive** Regel rot wird.
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const R = require("../../backend/static/regeln.js");

const NUTZER = ["E. John", "Team-Assistenz"];

// Ein Bestandsbrief, wie ihn `briefkasten.liste` heute liefert (gemessen an pm/N-0041).
function altbrief(status) {
  return {
    id: "N-0041", von: "E. John", zeit: "2026-08-17T07:41:29+00:00",
    status: status || "beantwortet",
    beitraege: [
      { absender: "E. John", zeit: "2026-08-17T07:41:29+00:00", text: "es gibt immer noch fristen als datum!", ist_erstbeitrag: true },
      { absender: "Antwort des Teams", zeit: "2026-08-17", text: "Du hattest recht.", ist_erstbeitrag: false }
    ]
  };
}

test("Erstbeitrag ist immer vom Menschen — auch ohne Registry", () => {
  const b = altbrief();
  assert.strictEqual(R.urheber(b.beitraege[0], NUTZER), "mensch");
  assert.strictEqual(R.urheber(b.beitraege[0], []), "mensch");
});

test("Team-Antwort im Bestand wird als Team erkannt", () => {
  assert.strictEqual(R.urheber(altbrief().beitraege[1], NUTZER), "team");
});

test("GEGENPROBE: ein zweiter Beitrag des Menschen unter ANDEREM Namen ist Mensch, nicht Team", () => {
  // Genau der Fall, an dem die naive Regel "Absender == brief.von" scheitert: der Mensch
  // waehlt beim Senden einen anderen registrierten Nutzer. Der Brief kaeme sonst als
  // Team-Antwort auf den Schirm — und `istWiederOffen` wuerde ihn falsch markieren.
  const b = altbrief("offen");
  b.beitraege.push({ absender: "Team-Assistenz", zeit: "2026-08-17 12:00", text: "Nachfrage.", ist_erstbeitrag: false });
  assert.strictEqual(R.urheber(b.beitraege[2], NUTZER), "mensch");
  assert.notStrictEqual(b.beitraege[2].absender, b.von);  // die naive Regel saehe hier "team"
});

test("GEGENPROBE: 'Vollzug (Team, 2026-08-16, Routine-Session)' ist Team, obwohl es nicht mit 'Antwort' beginnt", () => {
  // Der eine gemessene Sonderfall im Bestand (pm/N-0015). Gegen den reinen B054-Einstieg
  // waere er Mensch — die Registry entscheidet ihn richtig.
  const beitrag = { absender: "Vollzug", zeit: "2026-08-16", text: "…", ist_erstbeitrag: false };
  assert.strictEqual(R.urheber(beitrag, NUTZER), "team");
});

test("ohne Registry faellt die Regel auf den B054-Einstieg zurueck und erfindet nichts", () => {
  const beitrag = { absender: "Antwort des Teams", zeit: "2026-08-17", text: "…", ist_erstbeitrag: false };
  assert.strictEqual(R.urheber(beitrag, []), "team");
  assert.strictEqual(R.urheber(beitrag, null), "team");
});

test("istWiederOffen: offen MIT Team-Antwort ist die Nachfrage des Menschen", () => {
  assert.strictEqual(R.istWiederOffen(altbrief("offen"), NUTZER), true);
});

test("GEGENPROBE: ein frischer Brief ist offen und NICHT wieder-offen", () => {
  // Ohne diese Gegenprobe waere die Kennzeichnung ein Dauerschild an jedem offenen Brief
  // — und traefe genau die Aussage nicht mehr, fuer die sie da ist.
  const frisch = { id: "N-0042", von: "E. John", zeit: "2026-08-17 12:00", status: "offen",
                   beitraege: [{ absender: "E. John", zeit: "2026-08-17 12:00", text: "neu", ist_erstbeitrag: true }] };
  assert.strictEqual(R.istWiederOffen(frisch, NUTZER), false);
});

test("GEGENPROBE: ein beantworteter Brief ist nicht wieder-offen", () => {
  assert.strictEqual(R.istWiederOffen(altbrief("beantwortet"), NUTZER), false);
});

test("beitragKopf holt Absender und Zeit des Erstbeitrags aus dem Brief, wenn sie fehlen", () => {
  const brief = { von: "E. John", zeit: "2026-08-17T07:41:29+00:00", status: "offen",
                  beitraege: [{ absender: "", zeit: "", text: "x", ist_erstbeitrag: true }] };
  const k = R.beitragKopf(brief.beitraege[0], brief, NUTZER);
  assert.strictEqual(k.absender, "E. John");
  assert.strictEqual(k.zeit, "2026-08-17T07:41:29+00:00");
});

test("beitragKopf erfindet nichts, wenn auch der Brief nichts hergibt (B038)", () => {
  const k = R.beitragKopf({ absender: "", zeit: "", text: "x", ist_erstbeitrag: true }, {}, NUTZER);
  assert.strictEqual(k.absender, "");
  assert.strictEqual(k.zeit, "");
});

test("verlauf bleibt lesbar, wenn die Antwort kein beitraege-Feld hat", () => {
  // Der Ausfallfall: eine aeltere Backend-Fassung oder ein halb ausgerolltes System.
  // Eine leere Ansicht waere die schlechteste Anzeige — sie behauptet, es stuende nichts da.
  const alt = { id: "N-0001", von: "E. John", zeit: "2026-08-16", status: "beantwortet",
                nachricht: "Frage?", antwort: "Antwort.", antwort_datum: "2026-08-16" };
  const v = R.verlauf(alt, NUTZER);
  assert.strictEqual(v.length, 2);
  assert.strictEqual(v[0].urheber, "mensch");
  assert.strictEqual(v[1].urheber, "team");
  assert.strictEqual(v[1].text, "Antwort.");
});

test("verlauf eines leeren Briefs ist leer und wirft nicht", () => {
  assert.deepStrictEqual(R.verlauf({}, NUTZER), []);
  assert.deepStrictEqual(R.verlauf(null, NUTZER), []);
});

test("GEGENPROBE: sortiereBriefe dreht die Anzeige um und laesst die Eingabe unangetastet", () => {
  // SWR-083 verlangt neueste zuerst; `reverse()` allein arbeitet in-place und veraendert
  // die Liste, aus der andere Ansichten lesen. Diese Gegenprobe wird gegen ein blankes
  // `briefe.reverse()` rot.
  const briefe = [{ id: "N-0001" }, { id: "N-0002" }, { id: "N-0003" }];
  const anzeige = R.sortiereBriefe(briefe);
  assert.deepStrictEqual(anzeige.map(b => b.id), ["N-0003", "N-0002", "N-0001"]);
  assert.deepStrictEqual(briefe.map(b => b.id), ["N-0001", "N-0002", "N-0003"]);
});

// ---------- SWR-130 (pm/T-0058): gespeichert vs. gescheitert ----------

test("briefIdAusFehler liest die Kennung aus der SWR-121-Meldung", () => {
  const meldung = "GESPEICHERT als N-0042 — NICHT erneut senden. Ursache: Git-Commit fehlgeschlagen";
  assert.strictEqual(R.briefIdAusFehler(meldung), "N-0042");
});

test("GEGENPROBE: ohne Kennung wird keine erfunden — dann ist es ein echter Fehler (B038)", () => {
  // Ohne diese Gegenprobe wuerde jeder Fehler als "gespeichert" durchgehen, auch einer,
  // bei dem gar nichts geschrieben wurde (leerer Text, zu lang, unbekanntes Projekt).
  assert.strictEqual(R.briefIdAusFehler("Nachricht darf nicht leer sein"), "");
  assert.strictEqual(R.briefIdAusFehler(""), "");
  assert.strictEqual(R.briefIdAusFehler(null), "");
});

test("GEGENPROBE: eine Ticket-Kennung ist keine Brief-Kennung", () => {
  assert.strictEqual(R.briefIdAusFehler("T-0058 ist kein offener Decision Request"), "");
});
