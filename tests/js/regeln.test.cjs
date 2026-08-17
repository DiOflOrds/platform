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

// ---------- SWR-132 (pm/T-0064, Briefe pm/N-0038 + pm/N-0042): Aufgabenliste ----------

const AUFGABEN = [
  { projekt: "pm", id: "T-0064", ref: "pm/T-0064", rolle: "pl", verantwortlich: "team" },
  { projekt: "platform", id: "T-0013", ref: "platform/T-0013", rolle: "cm", verantwortlich: "team" },
  { projekt: "pm", id: "T-0001", ref: "pm/T-0001", rolle: "pl", verantwortlich: "team" },
  { projekt: "promt-team", id: "T-0002", ref: "promt-team/T-0002", rolle: "test", verantwortlich: "team" },
];

test("sortiereAufgaben ordnet nach Projekt, dann Kennung — ohne die Eingabe zu aendern", () => {
  const vorher = AUFGABEN.map(a => a.ref);
  const sortiert = R.sortiereAufgaben(AUFGABEN);
  assert.deepStrictEqual(sortiert.map(a => a.ref),
    ["platform/T-0013", "pm/T-0001", "pm/T-0064", "promt-team/T-0002"]);
  // Gegenprobe gegen ein blankes `sort()`: die API-Liste wird von mehreren Ansichten
  // gelesen, `sort` arbeitet in-place. Dieselbe Falle wie bei `sortiereBriefe`.
  assert.deepStrictEqual(AUFGABEN.map(a => a.ref), vorher);
});

test("GEGENPROBE: NICHT nach Prioritaet oder Frist sortiert — der Mensch priorisiert selbst", () => {
  // pm/N-0038 verlangt die Liste, DAMIT er priorisieren kann. Eine Vorsortierung nach
  // Dringlichkeit waere eine stille erste Priorisierung neben seiner — genau der Grund,
  // aus dem die Liste auch nicht gekuerzt wird.
  const mitPrio = [
    { projekt: "pm", id: "T-0002", ref: "pm/T-0002", prio: "niedrig", frist: "2026-08-18" },
    { projekt: "pm", id: "T-0001", ref: "pm/T-0001", prio: "hoch", frist: "2026-12-31" },
  ];
  assert.deepStrictEqual(R.sortiereAufgaben(mitPrio).map(a => a.ref),
    ["pm/T-0001", "pm/T-0002"]);
});

test("aufgabenNachRolle gruppiert, Rollen alphabetisch", () => {
  const gruppen = R.aufgabenNachRolle(AUFGABEN);
  assert.deepStrictEqual(gruppen.map(g => g.rolle), ["cm", "pl", "test"]);
  assert.deepStrictEqual(gruppen[1].aufgaben.map(a => a.ref), ["pm/T-0001", "pm/T-0064"]);
});

test("⚠ jede Aufgabe erscheint in GENAU EINER Gruppe", () => {
  // Die Zusicherung, an der eine Gruppierung scheitert: doppelt heisst doppelt gezaehlt,
  // fehlend heisst verschwunden. Beides pruefen, nicht nur eines.
  const gruppen = R.aufgabenNachRolle(AUFGABEN);
  const flach = gruppen.reduce((s, g) => s.concat(g.aufgaben.map(a => a.ref)), []);
  assert.strictEqual(flach.length, AUFGABEN.length);
  assert.strictEqual(new Set(flach).size, AUFGABEN.length);
  AUFGABEN.forEach(a => assert.ok(flach.includes(a.ref), `${a.ref} fehlt in jeder Gruppe`));
});

test("⚠ eine Aufgabe ohne Rolle bekommt eine BENANNTE Gruppe statt zu fehlen (SWR-096)", () => {
  const gruppen = R.aufgabenNachRolle([
    { projekt: "pm", id: "T-0001", ref: "pm/T-0001", rolle: "pl" },
    { projekt: "pm", id: "T-0002", ref: "pm/T-0002" },
    { projekt: "pm", id: "T-0003", ref: "pm/T-0003", rolle: "   " },
  ]);
  assert.deepStrictEqual(gruppen.map(g => g.rolle), ["pl", R.OHNE_ROLLE]);
  // Leerstring und Leerzeichen landen in derselben Gruppe — ohne den `trim()` waere
  // "   " eine eigene, unsichtbar benannte Rolle.
  assert.deepStrictEqual(gruppen[1].aufgaben.map(a => a.ref), ["pm/T-0002", "pm/T-0003"]);
});

test("⚠ 'ohne Rolle' steht ZULETZT und nicht alphabetisch zwischen den Rollen", () => {
  // Zwischen `cm` und `pl` einsortiert saehe das Fehlen einer Rolle wie eine Rolle aus.
  const gruppen = R.aufgabenNachRolle([
    { projekt: "pm", id: "T-0001", ref: "pm/T-0001" },
    { projekt: "pm", id: "T-0002", ref: "pm/T-0002", rolle: "test" },
    { projekt: "pm", id: "T-0003", ref: "pm/T-0003", rolle: "cm" },
  ]);
  assert.deepStrictEqual(gruppen.map(g => g.rolle), ["cm", "test", R.OHNE_ROLLE]);
});

test("gruppenTitel nennt IMMER die Zahl — kein Eintrag verschwindet ohne Zaehler", () => {
  assert.strictEqual(R.gruppenTitel({ rolle: "pl", aufgaben: [1, 2, 3, 4] }), "pl (4)");
  assert.strictEqual(R.gruppenTitel({ rolle: "cm", aufgaben: [] }), "cm (0)");
  assert.strictEqual(R.gruppenTitel(null), R.OHNE_ROLLE + " (0)");
});

test("GEGENPROBE: verantwortlich gruppiert NICHT — es bleibt Feld an der Zeile", () => {
  // `rolle` und `verantwortlich` sind zwei Fragen; ihre Verschmelzung war der Befund
  // hinter SWR-116, wo `rolle: mensch` eine zweite Bedeutung trug.
  const gruppen = R.aufgabenNachRolle([
    { projekt: "pm", id: "T-0001", ref: "pm/T-0001", rolle: "pl", verantwortlich: "mensch" },
    { projekt: "pm", id: "T-0002", ref: "pm/T-0002", rolle: "pl", verantwortlich: "team" },
  ]);
  assert.strictEqual(gruppen.length, 1);
  assert.strictEqual(gruppen[0].rolle, "pl");
});

test("leere und fehlende Liste liefern eine leere Gruppierung, keinen Fehler", () => {
  assert.deepStrictEqual(R.aufgabenNachRolle([]), []);
  assert.deepStrictEqual(R.aufgabenNachRolle(null), []);
  assert.deepStrictEqual(R.sortiereAufgaben(undefined), []);
});

// ---------- SWR-133 (pm/T-0067 aus pm/T-0066, Brief pm/N-0042): falten ----------

test("istGruppeOffen: nie angefasst -> Standard der Gruppe", () => {
  assert.strictEqual(R.istGruppeOffen({}, "aktiv", true), true);
  assert.strictEqual(R.istGruppeOffen({}, "abgeschlossen", false), false);
});

test("⚠ GEGENPROBE: 'nie angefasst' ist NICHT 'zugeklappt' (SWR-108)", () => {
  // Wuerde `undefined` als `false` gelesen, waere beim ersten Aufruf jede Gruppe zu —
  // der Auftraggeber saehe WENIGER als vorher, das Gegenteil beider Briefe.
  assert.strictEqual(R.istGruppeOffen(undefined, "aktiv", true), true);
  assert.strictEqual(R.istGruppeOffen(null, "aktiv", true), true);
  assert.notStrictEqual(R.istGruppeOffen({}, "aktiv", true),
                        R.istGruppeOffen({ aktiv: false }, "aktiv", true));
});

test("ein zugeklappter Zustand gewinnt ueber den Standard und ueberlebt", () => {
  const zustand = { aktiv: false, "festes-team": true };
  assert.strictEqual(R.istGruppeOffen(zustand, "aktiv", true), false);
  assert.strictEqual(R.istGruppeOffen(zustand, "festes-team", false), true);
});

test("gruppenTitel traegt die Zahl auch fuer die Cockpit-Gruppen — nichts ohne Zaehler", () => {
  // Dieselbe Funktion wie in der Aufgabenliste: eine Faltregel, ein Titelformat (B033).
  assert.strictEqual(R.gruppenTitel({ rolle: "Aktive Projekte", aufgaben: [1, 2] }),
                     "Aktive Projekte (2)");
});
