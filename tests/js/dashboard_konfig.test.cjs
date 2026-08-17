// Dashboard-Konfiguration mit Persistenz (SWR-151, projects/p11/T-0011).
//
// ⚠ Geprueft werden die **Regeln** aus `regeln.js` — ohne DOM, ohne Browser (ADR-008).
// Die Ansicht zeichnet nur; was sie zeichnet, wird hier entschieden.
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const R = require("../../backend/static/regeln.js");

const W = (projekt, titel) => ({ projekt, titel: titel || ("Widget " + projekt) });
const namen = (liste) => liste.map((w) => w.projekt);

// ---------------------------------------------------------------- DoD 3: ohne Konfiguration

test("SWR-151/DoD3: OHNE Konfiguration ist das Dashboard VOLLSTAENDIG", () => {
  // ⚠ Der Erstbesuch ist der Fall, den man beim Bauen nie sieht und der Mensch immer
  // zuerst. Ein leeres Dashboard beim ersten Aufruf saehe aus wie ein Ladefehler.
  const alle = [W("p11"), W("p12"), W("team-mail")];
  const g = R.widgetsOrdnen(alle, R.konfigLesen(null));
  assert.deepStrictEqual(namen(g.sichtbar), ["p11", "p12", "team-mail"]);
  assert.deepStrictEqual(g.versteckt, []);
});

test("SWR-151: kaputter Speicherinhalt ergibt den STANDARD und keinen Fehler", () => {
  // ⚠ Eine Ansicht, die an ihrer eigenen Voreinstellung stirbt, ist schlimmer als eine
  // ohne Voreinstellung. Der Speicher liegt ausserhalb unserer Reichweite.
  ["{kaputt", "null", "[]", '"text"', "", "17"].forEach((roh) => {
    const k = R.konfigLesen(roh);
    assert.deepStrictEqual(k, R.konfigLeer(), "kaputt: " + JSON.stringify(roh));
  });
});

test("SWR-151: ein `versteckt`, das keine Liste ist, wird NICHT durchgereicht", () => {
  // ⚠ Waere es eine Zeichenkette, faende `indexOf` Teiltreffer: `p1` waere versteckt,
  // weil `p11` im Text steht. Feldweise pruefen statt „ist es ein Objekt".
  const k = R.konfigLesen(JSON.stringify({ versteckt: "p11", reihenfolge: 3 }));
  assert.deepStrictEqual(k, R.konfigLeer());
});

// ---------------------------------------------------------------- DoD 1: Auswahl + Reihenfolge

test("SWR-151/DoD1: ein ausgeblendetes Widget steht in `versteckt` und nicht in `sichtbar`", () => {
  const alle = [W("p11"), W("p12"), W("team-mail")];
  const k = R.konfigUmschalten(R.konfigLeer(), "p12");
  const g = R.widgetsOrdnen(alle, k);
  assert.deepStrictEqual(namen(g.sichtbar), ["p11", "team-mail"]);
  assert.deepStrictEqual(namen(g.versteckt), ["p12"]);
});

test("SWR-151/DoD1: Umschalten ist umkehrbar und aendert die Vorlage NICHT", () => {
  // ⚠ Eine Konfigurationsfunktion, die ihr Argument aendert, macht aus „was waere wenn"
  // ein „ist jetzt so" — und der Aufrufer merkt es erst, wenn er zurueck will.
  const vorher = R.konfigLeer();
  const aus = R.konfigUmschalten(vorher, "p12");
  assert.deepStrictEqual(vorher.versteckt, [], "die Vorlage wurde veraendert");
  const ein = R.konfigUmschalten(aus, "p12");
  assert.deepStrictEqual(ein.versteckt, []);
});

test("SWR-151/DoD1: die Reihenfolge des Menschen gewinnt gegen die des Servers", () => {
  const alle = [W("p11"), W("p12"), W("team-mail")];
  const k = R.konfigLesen(JSON.stringify({ versteckt: [], reihenfolge: ["team-mail", "p12"] }));
  const g = R.widgetsOrdnen(alle, k);
  assert.deepStrictEqual(namen(g.sichtbar), ["team-mail", "p12", "p11"]);
});

test("SWR-151: Verschieben schreibt die Reihenfolge aus der SICHTBAREN Liste neu", () => {
  // ⚠ Wuerde sie in der gespeicherten fortgeschrieben, spraenge ein Schritt „hoch" ueber
  // ein Loch, das ein laengst verschwundenes Projekt hinterlassen hat.
  const alle = [W("p11"), W("p12"), W("team-mail")];
  const start = R.konfigLesen(JSON.stringify({ versteckt: [], reihenfolge: ["weg-seit-gestern"] }));
  const sichtbar = R.widgetsOrdnen(alle, start).sichtbar;
  const k = R.konfigVerschieben(start, sichtbar, "team-mail", -1);
  assert.deepStrictEqual(namen(R.widgetsOrdnen(alle, k).sichtbar), ["p11", "team-mail", "p12"]);
  assert.ok(k.reihenfolge.indexOf("weg-seit-gestern") < 0,
            "der Name eines verschwundenen Projekts steht noch in der Reihenfolge");
});

test("SWR-151: ein Schritt ueber den Rand tut NICHTS statt zu springen", () => {
  const alle = [W("p11"), W("p12")];
  const sichtbar = R.widgetsOrdnen(alle, R.konfigLeer()).sichtbar;
  const hoch = R.konfigVerschieben(R.konfigLeer(), sichtbar, "p11", -1);
  const runter = R.konfigVerschieben(R.konfigLeer(), sichtbar, "p12", 1);
  assert.deepStrictEqual(namen(R.widgetsOrdnen(alle, hoch).sichtbar), ["p11", "p12"]);
  assert.deepStrictEqual(namen(R.widgetsOrdnen(alle, runter).sichtbar), ["p11", "p12"]);
});

// ---------------------------------------------------------------- die bestimmende Entscheidung

test("SWR-151: ein NEUES Widget erscheint von selbst — Ausschlussliste, keine Auswahlliste", () => {
  // ⚠⚠ Die bestimmende Entscheidung. Bei einer Auswahlliste waere ein Widget, das ein Team
  // NEU anbietet, unsichtbar — und niemand wuesste, dass es existiert.
  //
  // > **Eine gespeicherte Auswahl altert gegen einen wachsenden Bestand.**
  const gestern = R.konfigUmschalten(R.konfigLeer(), "p12");   // gespeichert, als es 2 gab
  const heute = [W("p11"), W("p12"), W("promt-team")];          // ein Team ist dazugekommen
  const g = R.widgetsOrdnen(heute, gestern);
  assert.ok(namen(g.sichtbar).indexOf("promt-team") >= 0,
            "das neue Widget faellt lautlos aus der Ansicht");
  assert.deepStrictEqual(namen(g.versteckt), ["p12"], "nur das bewusst Versteckte fehlt");
});

test("SWR-151: ein verschwundenes Widget in der Konfiguration stoert nicht", () => {
  const k = R.konfigLesen(JSON.stringify({ versteckt: ["gibt-es-nicht"],
                                           reihenfolge: ["gibt-es-auch-nicht"] }));
  const g = R.widgetsOrdnen([W("p11")], k);
  assert.deepStrictEqual(namen(g.sichtbar), ["p11"]);
  assert.deepStrictEqual(g.versteckt, []);
});

// ---------------------------------------------------------------- DoD 2: die Erklaerung

test("SWR-151/DoD2: was ausgeblendet ist, wird BENANNT — die Auflage aus SWR-133", () => {
  // ⚠⚠ SWR-133 hat die Persistenz mit dem Satz abgelehnt: *„sonst fehlt eine Gruppe und
  // niemand weiss, warum."* Der Einwand verbietet sie nicht, er verlangt die Erklaerung.
  assert.strictEqual(R.verstecktSatz(0), "", "ohne Verstecktes wird nichts behauptet");
  assert.match(R.verstecktSatz(1), /^1 Widget ist durch deine Auswahl ausgeblendet\.$/);
  assert.match(R.verstecktSatz(3), /^3 Widgets sind durch deine Auswahl ausgeblendet\.$/);
});

test("GEGENPROBE: der Satz nennt die Ursache und nicht nur die Zahl", () => {
  // Ein „3 Widgets ausgeblendet" liesse offen, ob das System oder der Mensch es tat.
  assert.match(R.verstecktSatz(2), /deine Auswahl/);
});

// ---------------------------------------------------------------- Runde durch den Speicher

test("SWR-151/DoD2: Schreiben und Lesen ergeben dieselbe Konfiguration", () => {
  const k = R.konfigVerschieben(R.konfigUmschalten(R.konfigLeer(), "p12"),
                                [W("p11"), W("team-mail")], "team-mail", -1);
  assert.deepStrictEqual(R.konfigLesen(R.konfigSchreiben(k)), k);
});

test("SWR-151: die Kennung eines Widgets entsteht an EINER Stelle", () => {
  // ⚠ Stuende sie an drei Stellen, waere sie irgendwann an zweien der Titel — und der
  // Titel aendert sich, waehrend die Konfiguration bleibt.
  assert.strictEqual(R.widgetSchluessel({ projekt: "p11", titel: "Alt" }), "p11");
  assert.strictEqual(R.widgetSchluessel({ projekt: "p11", titel: "Neu" }), "p11");
  assert.strictEqual(R.widgetSchluessel({}), "");
  assert.strictEqual(R.widgetSchluessel(null), "");
});
