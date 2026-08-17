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

// ---------- SWR-135 (p11/T-0010): Kompaktkacheln des Dashboards ----------

test("⚠ echte_null wird als 0 gezeigt, NICHT als 'keine Daten'", () => {
  // Widget-Vertrag woertlich: "0 offene Briefe ist ein Ergebnis, kein Loch."
  assert.strictEqual(R.feldText({ wert: 0, zustand: "echte_null" }), "0");
  assert.strictEqual(R.feldText({ wert: "", zustand: "echte_null" }), "0");
});

test("⚠ GEGENPROBE: nicht_geliefert wird als 'keine Daten' gezeigt, NIE als 0", () => {
  // Die teure Verwechslung: `team: null` (fuehrt keine Digests) und `briefe_offen: 0`
  // (keine offenen Briefe) kommen aus derselben Antwort. Ohne diese Trennung sehen sie
  // gleich aus — dieselbe Gleichheit, die in SWR-128 fuenf Sprints "null JS-Tests" verbarg.
  assert.strictEqual(R.feldText({ wert: null, zustand: "nicht_geliefert" }), R.KEINE_DATEN);
  assert.notStrictEqual(R.feldText({ wert: null, zustand: "nicht_geliefert" }), "0");
  assert.notStrictEqual(R.feldText({ wert: 0, zustand: "echte_null" }), R.KEINE_DATEN);
});

test("feldText liest den ZUSTAND, nicht den Wert", () => {
  // Gegenprobe gegen die naheliegende Regel `if (!wert) return "keine Daten"` — die waere
  // fuer eine echte 0 falsch. Der Zustand ist ein Fakt aus dem Backend (SWR-108), der Wert
  // allein waere eine Annahme.
  assert.strictEqual(R.feldText({ wert: 0, zustand: "echte_null" }), "0");
  assert.strictEqual(R.feldText({ wert: 7, zustand: "wert" }), "7");
});

test("⚠ ein Feld ohne bekannten Zustand zeigt 'keine Daten', nicht 'undefined'", () => {
  // Der erste Entwurf fiel hier bis `String(feld.wert)` durch und haette bei einem
  // unvollstaendigen Payload die Zeichenkette "undefined" angezeigt — eine Anzeige, die
  // aussieht wie ein Inhalt und keiner ist. Gefunden, weil der Test dazu zuerst so
  // geschrieben war, dass er BEIDES durchgelassen haette: die Gegenprobe fehlte.
  assert.strictEqual(R.feldText({}), R.KEINE_DATEN);
  assert.strictEqual(R.feldText({ wert: 5 }), R.KEINE_DATEN);
  assert.strictEqual(R.feldText({ wert: 5, zustand: "quatsch" }), R.KEINE_DATEN);
  assert.strictEqual(R.feldText(null), R.KEINE_DATEN);
});

test("team ist ein Objekt und wird nicht als [object Object] gezeigt", () => {
  assert.strictEqual(R.feldText({ wert: { letzter_digest: "2026-08-16" }, zustand: "wert" }),
                     "2026-08-16");
  // Fuehrt Digests, hat aber noch keinen: echte Null im INNEREN Feld (SWR-108).
  assert.strictEqual(R.feldText({ wert: { letzter_digest: "" }, zustand: "wert" }), "0");
  assert.strictEqual(R.feldText({ wert: { letzter_digest: null }, zustand: "wert" }),
                     R.KEINE_DATEN);
});

test("kachelFelder folgt der Reihenfolge des Backends und erfindet keine Felder", () => {
  const kachel = { felder: { aufgaben_offen: { wert: 3, zustand: "wert" },
                             briefe_offen: { wert: 0, zustand: "echte_null" },
                             team: { wert: null, zustand: "nicht_geliefert" } } };
  const f = R.kachelFelder(kachel);
  assert.deepStrictEqual(f.map(x => x.name), ["aufgaben_offen", "briefe_offen", "team"]);
  assert.deepStrictEqual(f.map(x => x.text), ["3", "0", R.KEINE_DATEN]);
  // Jedes Feld traegt eine Beschriftung — `name` als Rueckfall, nie leer.
  f.forEach(x => assert.ok(x.titel && x.titel.length));
});

test("kachelFelder ohne Felder liefert eine leere Liste, keinen Fehler", () => {
  assert.deepStrictEqual(R.kachelFelder({}), []);
  assert.deepStrictEqual(R.kachelFelder(null), []);
});

test("dashboardGruppen haelt die Cockpit-Reihenfolge, nicht die alphabetische", () => {
  // "Feste Teams" vor "Projekt-Teams" vor "Aktive Projekte" — die Ordnung aus SWR-067.
  // Alphabetisch waere es "abgeschlossen, aktiv, festes-team, projekt-team".
  const g = R.dashboardGruppen([
    { projekt: "a", gruppe: "aktiv" }, { projekt: "b", gruppe: "festes-team" },
    { projekt: "c", gruppe: "abgeschlossen" }, { projekt: "d", gruppe: "projekt-team" },
  ]);
  assert.deepStrictEqual(g.map(x => x.gruppe),
    ["festes-team", "projekt-team", "aktiv", "abgeschlossen"]);
});

test("leere Gruppen fallen weg", () => {
  const g = R.dashboardGruppen([{ projekt: "a", gruppe: "aktiv" }]);
  assert.deepStrictEqual(g.map(x => x.gruppe), ["aktiv"]);
});

test("⚠ GEGENPROBE: eine UNBEKANNTE Gruppe verschwindet nicht (SWR-096)", () => {
  // Ohne diesen Fall verliert ein neuer Gruppenname stillschweigend Projekte — und
  // niemand merkt es, weil die Summe nirgends gegen die Kachelzahl gehalten wird.
  const g = R.dashboardGruppen([
    { projekt: "a", gruppe: "aktiv" }, { projekt: "x", gruppe: "brandneu" },
    { projekt: "y", gruppe: "" },
  ]);
  const flach = g.reduce((s, x) => s.concat(x.kacheln.map(k => k.projekt)), []);
  assert.strictEqual(flach.length, 3);
  assert.ok(flach.includes("x") && flach.includes("y"));
  assert.strictEqual(g[g.length - 1].gruppe, "sonstige");
});

test("jede Kachel erscheint in genau EINER Gruppe", () => {
  const kacheln = [{ projekt: "a", gruppe: "aktiv" }, { projekt: "b", gruppe: "aktiv" },
                   { projekt: "c", gruppe: "festes-team" }];
  const flach = R.dashboardGruppen(kacheln)
    .reduce((s, x) => s.concat(x.kacheln.map(k => k.projekt)), []);
  assert.strictEqual(flach.length, 3);
  assert.strictEqual(new Set(flach).size, 3);
});
