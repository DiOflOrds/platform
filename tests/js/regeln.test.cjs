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

// --------------------------------------------------------------- SWR-138 (pm/T-0052)
// „Für dich" hat ZWEI Abschnitte. Der Grund ist B033: an der Entscheidungsliste hängen
// die Knöpfe (SWR-042), und eine Liste, in der manche Einträge Knöpfe haben und manche
// nicht, ist eine Fläche mit zwei Bedeutungen.

test("fuerDichAbschnitte gibt genau zwei Abschnitte in fester Reihenfolge (SWR-138)", () => {
  const a = R.fuerDichAbschnitte([], []);
  assert.strictEqual(a.length, 2);
  assert.deepStrictEqual(a.map(x => x.schluessel), ["entscheidungen", "handlungen"]);
});

test("nur der Entscheidungsabschnitt traegt Knoepfe (SWR-138)", () => {
  // ⚠ Die Zusicherung, aus der der eigene Abschnitt ueberhaupt folgt. Ein Knopf ohne
  // Optionen waere entweder wirkungslos oder eine zweite Bedeutung derselben Flaeche.
  const a = R.fuerDichAbschnitte([{ id: "T-0001" }], [{ id: "T-0002" }]);
  assert.strictEqual(a[0].knoepfe, true);
  assert.strictEqual(a[1].knoepfe, false);
  assert.notStrictEqual(a[0].knoepfe, a[1].knoepfe);
});

test("⚠ beide Abschnitte erscheinen AUCH LEER, mit eigenem Leertext (SWR-138)", () => {
  // DoD 4. Ein Abschnitt, der bei 0 verschwindet, ist von einem nicht gebauten nicht zu
  // unterscheiden — dieselbe Begruendung wie die Nullzeilen des Preflights (SWR-114/122).
  const a = R.fuerDichAbschnitte([], []);
  assert.strictEqual(a[0].eintraege.length, 0);
  assert.strictEqual(a[1].eintraege.length, 0);
  assert.strictEqual(a[0].leer, R.FUER_DICH_LEER_ENTSCHEIDUNGEN);
  assert.strictEqual(a[1].leer, R.FUER_DICH_LEER_HANDLUNGEN);
  assert.notStrictEqual(a[0].leer, a[1].leer);  // zwei Aussagen, zwei Texte
});

test("⚠ GEGENPROBE: fehlende Listen werden zu leeren, nicht zu undefined (SWR-138)", () => {
  // Ohne diesen Fall wuerde ein Aussetzer einer der vier API-Aufrufe die ganze Ansicht
  // mit `undefined.length` abwerfen — und der Auftraggeber saehe eine leere Seite statt
  // eines leeren Abschnitts.
  const a = R.fuerDichAbschnitte(undefined, null);
  assert.deepStrictEqual(a[0].eintraege, []);
  assert.deepStrictEqual(a[1].eintraege, []);
});

test("die Eintraege werden unveraendert durchgereicht (SWR-138)", () => {
  // Die Reihenfolge kommt vom Server; eine stille Sortierung hier waere eine zweite
  // Priorisierung neben der des Auftraggebers (dieselbe Ueberlegung wie SWR-132).
  const handlungen = [{ ref: "p0/T-0002" }, { ref: "pm/T-0001" }];
  const a = R.fuerDichAbschnitte([], handlungen);
  assert.deepStrictEqual(a[1].eintraege.map(x => x.ref), ["p0/T-0002", "pm/T-0001"]);
});

// --------------------------------------------------------------------------
// SWR-144 (pm/T-0065): die Beschriftung des Terminierungsknopfs.
//
// ⚠ Geprueft wird die **Beschriftung** und nicht die Wirkung — die Wirkung liegt im
// Server (`test_terminieren.py`) und muss dort liegen: eine Regel, die in JavaScript
// entscheidet, OB geschrieben wird, waere eine zweite Antwort neben der des Servers.
// --------------------------------------------------------------------------

test("der Knopf nennt die Nummer aus dem Payload und rechnet nichts (SWR-144)", () => {
  const b = R.terminierKnopf({ geplant_sprint: "17" }, 18);
  assert.strictEqual(b.text, "→ Sprint 18");
  assert.strictEqual(b.wirkungslos, false);
});

test("⚠ die Nummer wird NICHT aus sprint_nr abgeleitet (SWR-144, B033)", () => {
  // Die Gegenprobe zur Bequemlichkeit: `sprint_nr + 1` in der Ansicht waere genau dann
  // falsch, wenn zwischen Laden und Klick ein Sprint gewechselt hat. Hier wird eine
  // Nummer uebergeben, die zu KEINER Ableitung aus `geplant_sprint` passt — kaeme sie
  // aus einer Rechnung, stuende hier etwas anderes.
  const b = R.terminierKnopf({ geplant_sprint: "3" }, 99);
  assert.strictEqual(b.text, "→ Sprint 99");
});

test("⚠ steht die Aufgabe schon auf dem naechsten Sprint, verspricht der Knopf nichts (SWR-144)", () => {
  // DoD 4 in der Ansicht. Ein Knopf, der bei jedem Klick dasselbe verspricht, sagt nicht
  // mehr, ob er gebraucht wird.
  const b = R.terminierKnopf({ geplant_sprint: "18" }, 18);
  assert.strictEqual(b.wirkungslos, true);
  assert.match(b.text, /steht auf 18/);
  assert.match(b.titel, /aendert nichts/);
});

test("⚠ wirkungslos SPERRT nicht — die Zahl im Payload kann alt sein (SWR-144)", () => {
  // Der Unterschied, der hier zaehlt: `wirkungslos` ist eine Beschriftung, keine Sperre.
  // Ein deaktivierter Knopf auf einer veralteten Zahl waere eine Sperre auf einer
  // Vermutung — und die Wahrheit hat der Server.
  const b = R.terminierKnopf({ geplant_sprint: "18" }, 18);
  assert.strictEqual("deaktiviert" in b, false);
  assert.strictEqual("disabled" in b, false);
});

test("eine Zahl als String zaehlt wie eine Zahl (SWR-144)", () => {
  // `geplant_sprint` kommt als String aus dem Frontmatter, `naechster_sprint` als Zahl
  // aus dem Register. Ein Vergleich ohne Normierung waere hier still falsch.
  assert.strictEqual(R.terminierKnopf({ geplant_sprint: 18 }, "18").wirkungslos, true);
});

test("⚠ ohne Nummer wird NICHT geraten (SWR-144)", () => {
  // Dieselbe Bauart wie `nicht_geliefert` im Widget-Vertrag: ein fehlender Wert bekommt
  // einen eigenen Text und nicht die 1 aus `0 + 1`.
  [undefined, null, 0, "", "keine"].forEach(function (n) {
    const b = R.terminierKnopf({ geplant_sprint: "5" }, n);
    assert.strictEqual(b.wirkungslos, true, "bei " + JSON.stringify(n));
    assert.match(b.text, /unbekannt/);
  });
});

test("eine Aufgabe ohne geplant_sprint bekommt einen wirksamen Knopf (SWR-144)", () => {
  // Der haeufigste Fall im Bestand — ein Ticket ganz ohne Termin. Er darf nicht als
  // „steht schon dort" gelesen werden, nur weil beide Werte leer aussehen.
  const b = R.terminierKnopf({}, 18);
  assert.strictEqual(b.wirkungslos, false);
});

// --------------------------------------------------------------------------
// SWR-146 (platform/T-0016 DoD 2/3): die EINE Stelle fuer den Text eines Cockpit-Feldes.
//
// ⚠ DoD 3 verlangt die Migration **ohne Verhaltensaenderung**. Die neun Wortlaute unten
// sind deshalb Zeichen fuer Zeichen die von Sprint 3 bis 16 — abgelesen am Stand VOR der
// Migration, nicht neu formuliert. Eine Vereinheitlichung waere eine Verhaltensaenderung
// mit gutem Gewissen.
// --------------------------------------------------------------------------

test("letzte_baseline: die drei Zustaende, Wortlaute unveraendert (SWR-146)", () => {
  assert.strictEqual(R.cockpitFeldText("letzte_baseline", "nicht_geliefert"), "keine Daten");
  assert.strictEqual(R.cockpitFeldText("letzte_baseline", "echte_null"), "noch keine");
  assert.strictEqual(R.cockpitFeldText("letzte_baseline", "wert", "p0-v1.0"), "p0-v1.0");
});

test("team.letzter_digest: die drei Zustaende, Wortlaute unveraendert (SWR-146)", () => {
  assert.strictEqual(R.cockpitFeldText("team.letzter_digest", "nicht_geliefert"),
                     "Digest: keine Daten");
  assert.strictEqual(R.cockpitFeldText("team.letzter_digest", "echte_null"),
                     "noch kein Digest");
  assert.strictEqual(R.cockpitFeldText("team.letzter_digest", "wert", "Digest 2026-08-17"),
                     "Digest 2026-08-17");
});

test("kpi: der Fehlfall, Wortlaut unveraendert (SWR-146)", () => {
  assert.strictEqual(R.cockpitFeldText("kpi", "nicht_geliefert"), "KPI: keine Daten");
});

test("⚠ ein FEHLENDER Zustand gilt als nicht_geliefert, nicht als Wert (SWR-146)", () => {
  // Dieselbe Entscheidung wie in `feldText`, und aus demselben Grund: bei einem
  // unvollstaendigen Payload (alte Serverversion ohne `zustaende`) stuende sonst
  // "undefined" auf dem Schirm — eine Anzeige, die wie ein Inhalt aussieht und keiner ist.
  [undefined, null, "", "quatsch"].forEach(function (z) {
    assert.strictEqual(R.cockpitFeldText("letzte_baseline", z), "keine Daten",
                       "bei " + JSON.stringify(z));
  });
});

test("⚠ ein unbekanntes Feld wird nicht geraten (SWR-146)", () => {
  assert.strictEqual(R.cockpitFeldText("gibt_es_nicht", "wert", "X"), "keine Daten");
});

test("⚠ 'keine Daten' steht EINMAL da und wird zusammengesetzt (SWR-146, B033)", () => {
  // Der Kern der Anforderung als Zaehltest: die Marke selbst darf nicht dreimal als
  // Literal in der Tabelle stehen, sonst ist die Migration eine Umzugsaktion und keine
  // Zusammenfuehrung. Gemessen daran, dass beide Praefix-Faelle die Marke ENTHALTEN und
  // mit ihr enden.
  assert.match(R.COCKPIT_TEXTE["team.letzter_digest"].nicht_geliefert,
               new RegExp(R.KEINE_DATEN + "$"));
  assert.match(R.COCKPIT_TEXTE["kpi"].nicht_geliefert,
               new RegExp(R.KEINE_DATEN + "$"));
  assert.strictEqual(R.COCKPIT_TEXTE["letzte_baseline"].nicht_geliefert, R.KEINE_DATEN);
});

test("alle drei migrierten Felder stehen in der Tabelle (SWR-146, DoD 4)", () => {
  // Die Gegenprobe zum Zaehltest in `test_dashboard_endpunkt.py`: der Altbestand ist dort
  // auf 0 gezogen, weil die Regel HIER steht. Verschwindet sie hier, ist die 0 dort eine
  // Luecke und kein Erfolg.
  assert.deepStrictEqual(Object.keys(R.COCKPIT_TEXTE).sort(),
                         ["kpi", "letzte_baseline", "team.letzter_digest"]);
});

// ---------- SWR-148 (team-mail/T-0004): Widgets ----------

test("widgetZeile: Datum, Mailzahl und Reaktionspunkte in einer Zeile", () => {
  const z = R.widgetZeile({ takt: "tag", zustand: "wert", datum: "2026-08-16",
                            mails: 89, reaktion: 4, reaktion_zustand: "wert" });
  assert.strictEqual(z.titel, "Tag");
  assert.ok(z.text.includes("2026-08-16"));
  assert.ok(z.text.includes("89 Mails"));
  assert.ok(z.text.includes("4× Blick oder Reaktion"));
});

test("⚠ nicht_geliefert nennt den GRUND — sonst sind zwei Handlungen dasselbe Nichts", () => {
  // „nicht eingerichtet" kann der Mensch aendern, „noch keiner erstellt" muss er abwarten.
  const a = R.widgetZeile({ takt: "monat", zustand: "nicht_geliefert",
                            grund: "nicht eingerichtet — Takt fehlt in konfiguration.yaml" });
  const b = R.widgetZeile({ takt: "monat", zustand: "nicht_geliefert",
                            grund: "noch keiner erstellt" });
  assert.strictEqual(a.text, R.KEINE_DATEN);
  assert.strictEqual(b.text, R.KEINE_DATEN);
  assert.notStrictEqual(a.grund, b.grund);
  assert.ok(a.grund.length && b.grund.length);
});

test("⚠ GEGENPROBE: eine fehlende Rubrik ist nicht 0 Reaktionspunkte", () => {
  // Ein Digest ohne die Rubrik sagt NICHTS ueber offene Punkte. „0" zu melden hiesse
  // „nichts zu tun" behaupten — die teuerste Verwechslung dieser Anzeige.
  const ohne = R.widgetZeile({ takt: "tag", zustand: "wert", datum: "2026-08-16",
                               mails: 89, reaktion: null,
                               reaktion_zustand: "nicht_geliefert" });
  const null_ = R.widgetZeile({ takt: "tag", zustand: "wert", datum: "2026-08-16",
                                mails: 89, reaktion: 0, reaktion_zustand: "echte_null" });
  assert.ok(ohne.text.includes("Reaktion: " + R.KEINE_DATEN));
  assert.ok(null_.text.includes("0× Blick oder Reaktion"));
  assert.notStrictEqual(ohne.text, null_.text);
});

test("eine fehlende Mailzahl wird nicht als 0 erfunden (B038)", () => {
  const z = R.widgetZeile({ takt: "woche", zustand: "wert", datum: "2026-08-16",
                            mails: null, reaktion: 4, reaktion_zustand: "wert" });
  assert.ok(!z.text.includes("0 Mails"));
  assert.ok(z.text.includes("2026-08-16"));
});

test("⚠ auftrag ist PFLICHT — ein Widget ohne Auftrag wird nicht angezeigt", () => {
  // Der Wunsch lautete „jedes widget soll eine beschreibung als Auftrag erhalten". Ohne
  // Pflichtpruefung waere die Regel nach zwei Teams wieder weg (SWR-125).
  const gut = { id: "a", titel: "T", auftrag: "was es zeigt", ziel: "#/x" };
  assert.strictEqual(R.widgetVollstaendig(gut), true);
  assert.strictEqual(R.widgetVollstaendig({ ...gut, auftrag: "" }), false);
  assert.strictEqual(R.widgetVollstaendig({ ...gut, auftrag: "   " }), false);
  assert.strictEqual(R.widgetVollstaendig({ ...gut, ziel: "" }), false);
  assert.strictEqual(R.widgetVollstaendig({ ...gut, id: "" }), false);
  assert.strictEqual(R.widgetVollstaendig(null), false);
});

test("widgetMaengel NENNT das fehlende Feld statt nur 'unvollstaendig' (B038)", () => {
  assert.deepStrictEqual(R.widgetMaengel({ id: "a", titel: "T", auftrag: " ", ziel: "" }),
                         ["auftrag", "ziel"]);
  assert.deepStrictEqual(R.widgetMaengel({ id: "a", titel: "T", auftrag: "x", ziel: "#/x" }),
                         []);
});

test("die Touch-Mindesthoehe ist eine Zahl an EINER Stelle, nicht eine Behauptung", () => {
  // „Touchscreen geeignet" ohne pruefbare Zahl waere eine Zusage ohne Pruefung (SWR-125).
  assert.strictEqual(typeof R.TOUCH_MIN_PX, "number");
  assert.ok(R.TOUCH_MIN_PX >= 44, "unter 44 px ist keine Fingerflaeche");
});

test("ein unbekannter Takt wird durchgereicht statt verschluckt", () => {
  const z = R.widgetZeile({ takt: "quartal", zustand: "nicht_geliefert", grund: "x" });
  assert.strictEqual(z.titel, "quartal");
});
