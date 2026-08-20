// SWR-154 (platform/T-0023, Brief pm/N-0043 Punkt 2): die Kachel „Sprint aktuell"
// zeichnet KAPITEL — geprueft am Ergebnis, nicht am Quelltext.
//
// ⚠⚠ **Warum dieser Nachweis ueber das Ergebnis laeuft und nicht ueber eine Zaehlung.**
// `L-2026-08-17az`: Sprint 19 hat einen Zweig gebaut, den niemand erreichen konnte, und
// der Zaehltest war dabei gruen — er sah den Zweig im Quelltext stehen. Hier wird
// deshalb `sprintKachel(...)` wirklich aufgerufen und das Ergebnis abgelesen. Ein
// Kapitel, das im Code steht und nie gezeichnet wird, ist hier rot.
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const { ladeKontext } = require("./_app_laden.cjs");

/** Der gesamte sichtbare Text eines Knotenbaums. */
function text(k) {
  if (k === null || k === undefined) return "";
  if (k.text !== undefined) return String(k.text);
  return (k.kinder || []).map(text).join(" ");
}

/** Eine Planzeile, wie der Server sie liefert. */
const Z = (aufgabe, kapitel, faellig) => ({
  aufgabe, kapitel, faellig: faellig || "", refs: [], rolle: "dev",
  status: "offen", grund: "", ampel: "sprint", horizont: "",
});

const KOPF = (schluessel, titel, anzahl) => ({ schluessel, titel, anzahl, sprint_nr: null });

function kachel(nutzlast) {
  const k = ladeKontext();
  assert.strictEqual(typeof k.sprintKachel, "function",
                     "sprintKachel nicht gefunden — der Nachweis prueft sonst nichts");
  return text(k.sprintKachel(Object.assign({
    quelle: "pm/management/sprint-aktuell.md", stand: "2026-08-20T10:30:00+02:00",
    zaehler: {}, zeilen: [], kapitel: [], nicht_geplant: [], widersprueche: [],
  }, nutzlast)));
}

test("SWR-154: die Kapiteltitel MIT ihrer Sprintnummer stehen in der Ansicht", () => {
  const gezeichnet = kachel({
    zeilen: [Z("platform/T-0023", "aktuell", "dieser Sprint"),
             Z("platform/T-0020", "naechster", "Sprint 22")],
    kapitel: [KOPF("aktuell", "Sprint 21 (aktuell)", 1),
              KOPF("naechster", "Sprint 22 (nächster)", 1)],
  });
  assert.ok(gezeichnet.includes("Sprint 21 (aktuell)"), 'Kapitel aktuell fehlt');
  assert.ok(gezeichnet.includes("Sprint 22 (nächster)"), 'Kapitel naechster fehlt');
});

test("SWR-154: jede Zeile erscheint UNTER ihrem Kapitel und keine zweimal", () => {
  // ⚠ Die Zerlegung ist im Server geprueft; hier geht es darum, dass die Ansicht sie
  // auch anwendet — ein `filter`, der danebengreift, zeigt eine Zeile doppelt oder gar
  // nicht, und beides waere still.
  const gezeichnet = kachel({
    zeilen: [Z("platform/T-0023", "aktuell"), Z("platform/T-0020", "naechster"),
             Z("pm/T-0001", "takt")],
    kapitel: [KOPF("aktuell", "Sprint 21 (aktuell)", 1),
              KOPF("naechster", "Sprint 22 (nächster)", 1),
              KOPF("takt", "Jeder Sprint (Takt)", 1)],
  });
  ["platform/T-0023", "platform/T-0020", "pm/T-0001"].forEach((ref) => {
    const treffer = gezeichnet.split(ref).length - 1;
    assert.strictEqual(treffer, 1, ref + " erscheint " + treffer + "× statt genau einmal");
  });
});

test("SWR-154: ein LEERES Pflichtkapitel wird gezeichnet und sagt, dass es leer ist", () => {
  // ⚠ Die Regel aus SWR-114/SWR-117: ein fehlendes Kapitel ist von „nicht nachgesehen"
  // nicht zu unterscheiden. Der Satz ist deshalb Teil der Zusicherung, nicht Kosmetik.
  const gezeichnet = kachel({
    zeilen: [Z("pm/T-0001", "takt")],
    kapitel: [KOPF("aktuell", "Sprint 21 (aktuell)", 0),
              KOPF("naechster", "Sprint 22 (nächster)", 0),
              KOPF("takt", "Jeder Sprint (Takt)", 1)],
  });
  assert.ok(gezeichnet.includes("Sprint 21 (aktuell)"));
  assert.ok(gezeichnet.includes("Für dieses Kapitel ist nichts geplant."),
            'der leere Fall schweigt - genau das darf er nicht');
});

test("SWR-154: ein Kapitel, das der Server NICHT schickt, wird auch nicht erfunden", () => {
  const gezeichnet = kachel({
    zeilen: [Z("platform/T-0023", "aktuell")],
    kapitel: [KOPF("aktuell", "Sprint 21 (aktuell)", 1),
              KOPF("naechster", "Sprint 22 (nächster)", 0)],
  });
  assert.ok(!gezeichnet.includes("Später"), 'Kapitel Spaeter steht da, obwohl es leer ist');
  assert.ok(!gezeichnet.includes("Ohne Sprintbezug"));
});

test("SWR-154: OHNE Kapitel bleibt die flache Tabelle — es wird nichts unterschlagen", () => {
  // ⚠ Der Fall „kein Sprintregister lesbar". Ohne diese Zusicherung waere die Anzeige
  // dann LEER, und ein leerer Plan sieht aus wie ein erledigter.
  const gezeichnet = kachel({
    zeilen: [Z("platform/T-0023", ""), Z("platform/T-0020", "")],
    kapitel: [],
  });
  assert.ok(gezeichnet.includes("platform/T-0023"));
  assert.ok(gezeichnet.includes("platform/T-0020"));
});

test("SWR-154: die Ansicht rechnet KEINE Sprintnummer selbst aus", () => {
  // ⚠ ADR-P11-001/B033: waere `jetzt + 1` in der Ansicht, stuende hier „Sprint 22",
  // obwohl der Server etwas anderes geschickt hat. Der Titel kommt vom Server —
  // absichtlich ein Titel, den keine Rechnung erzeugen wuerde.
  const gezeichnet = kachel({
    zeilen: [Z("platform/T-0020", "naechster")],
    kapitel: [KOPF("aktuell", "Sprint 21 (aktuell)", 0),
              KOPF("naechster", "Sprint 4711 (nächster)", 1)],
  });
  assert.ok(gezeichnet.includes("Sprint 4711 (nächster)"),
            "die Ansicht hat den Titel des Servers nicht uebernommen");
  assert.ok(!gezeichnet.includes("Sprint 22"));
});

test("SWR-154: der Bestandsabgleich steht VOR dem ersten Kapitel", () => {
  // ⚠ SWR-103: was fehlt, steht vor dem, was stimmt. Unter dem letzten Kapitel saehe es
  // niemand mehr (B049/B044).
  const gezeichnet = kachel({
    zeilen: [Z("platform/T-0023", "aktuell")],
    kapitel: [KOPF("aktuell", "Sprint 21 (aktuell)", 1),
              KOPF("naechster", "Sprint 22 (nächster)", 0)],
    nicht_geplant: [{ ref: "pm/T-0099", titel: "steht in keiner Planzeile" }],
  });
  const iAbgleich = gezeichnet.indexOf("stehen in KEINER Planzeile");
  const iKapitel = gezeichnet.indexOf("Sprint 21 (aktuell)");
  assert.ok(iAbgleich >= 0, "der Bestandsabgleich fehlt");
  assert.ok(iAbgleich < iKapitel,
            "der Bestandsabgleich steht hinter den Kapiteln statt davor");
});
