"""Unit-Verifikation „Für dich: Handlungen" (SWR-138, pm/T-0052).

Herkunft: Teil e) aus `pm/T-0038`, ursprünglich Brief `pm/N-0031`. Die Frage des
Auftraggebers lautete *„Warum sind die Tasks nicht in der Inbox, wenn sie an Menschen
gerichtet sind?"* — und die Antwort ist, dass die Inbox sie nicht **ablehnt**, sondern
nicht **kennt**: sie zeigt unentschiedene `decision-request`s (SWR-039/042), und ein
Ticket mit `verantwortlich: mensch` und `typ: problem` fällt durch jeden ihrer Filter.

> **Es fehlte kein Filter, sondern der Kanal.**

⚠ Das Ticket stand bei der **fünften** Berührung. Die dort benannte Naht (*zwischen
„Für dich: Entscheidungen" und „Für dich: Handlungen"*) wurde beim Schneiden **gemessen
und als hinfällig befunden**: der Abschnitt „Entscheidungen" existiert seit SWR-042, eine
Zerlegung hätte einen leeren Teil erzeugt. Das steht im Ticket, nicht nur hier.

Ausführung: python -m unittest discover platform/tests
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import aggregation  # noqa: E402

KOPF = """---
id: {id}
titel: "{titel}"
typ: {typ}
prozess: man3
rolle: pl
sprint: 0
status: {status}
prio: mittel
reviewer: qm
blocked_by: []
repo: p0
geändert: 2026-08-17
geplant_sprint: 15
erstellt: 2026-08-17
{extra}---

Rumpf.
"""


class HandlungenTest(unittest.TestCase):
    """Die Partition. Verifiziert: SWR-138."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        self.verz = os.path.join(self.root, "p0", "tickets")
        os.makedirs(self.verz)

    def _ticket(self, tid, typ="problem", status="open", verantwortlich=None,
                titel="Etwas tun"):
        extra = f"verantwortlich: {verantwortlich}\n" if verantwortlich else ""
        with open(os.path.join(self.verz, tid + ".md"), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write(KOPF.format(id=tid, titel=titel, typ=typ, status=status, extra=extra))

    def _refs(self):
        return [h["ref"] for h in aggregation.fuer_dich_handlungen(self.root)]

    def test_handlung_erscheint(self):
        """Der Fall, den die Inbox nie kannte: `typ: problem` mit
        `verantwortlich: mensch`. Verifiziert: SWR-138."""
        self._ticket("T-0001", verantwortlich="mensch")
        self.assertEqual(self._refs(), ["p0/T-0001"])

    def test_dr_erscheint_NICHT_in_den_handlungen(self):
        """⚠ DoD 3, erste Hälfte: ein Entscheidungsersuchen gehört in die Inbox, wo die
        Knöpfe hängen. Verifiziert: SWR-138."""
        self._ticket("T-0002", typ="decision-request")
        self.assertEqual(self._refs(), [])

    def test_ein_ticket_das_BEIDES_erfuellt_gehoert_zu_den_entscheidungen(self):
        """⚠⚠ DoD 3 in seiner scharfen Form — und der einzige Fall, in dem sich die zwei
        Abschnitte überhaupt streiten könnten.

        Ein `decision-request`, der **zusätzlich** `verantwortlich: mensch` trägt, erfüllt
        beide Bedingungen. Er gehört zu den Entscheidungen, weil dort die Optionen, die
        Frist und der Vorgabewert hängen (SWR-042). Ihn in beiden Abschnitten zu zeigen
        hieße, ihn zweimal zu verlangen. Verifiziert: SWR-138.
        """
        self._ticket("T-0003", typ="decision-request", verantwortlich="mensch")
        self.assertEqual(self._refs(), [])

    def test_teamaufgabe_erscheint_nicht(self):
        """Die Gegenprobe nach unten: ohne `verantwortlich: mensch` und ohne DR-Typ liegt
        die Aufgabe beim Team und hat in „Für dich" nichts zu suchen.
        Verifiziert: SWR-138."""
        self._ticket("T-0004")
        self.assertEqual(self._refs(), [])

    def test_geschlossene_tickets_zaehlen_nicht(self):
        """Ein erledigtes Ticket wartet auf niemanden — dieselbe Regel wie in
        `wartet_auf_mensch`. Verifiziert: SWR-138."""
        self._ticket("T-0005", status="done", verantwortlich="mensch")
        self._ticket("T-0006", status="rejected", verantwortlich="mensch")
        self.assertEqual(self._refs(), [])

    def test_leere_liste_ist_eine_liste_und_kein_fehler(self):
        """DoD 4: das Verhalten bei leerer Liste ist festgelegt. Eine leere Liste heißt
        „nachgesehen, nichts gefunden" — die Ansicht zeigt den Abschnitt trotzdem.
        Verifiziert: SWR-138."""
        self.assertEqual(aggregation.fuer_dich_handlungen(self.root), [])

    def test_die_partition_ist_eine_teilmenge_von_wartet_auf_mensch(self):
        """⚠ Die Zusicherung gegen B033: kein zweiter Erhebungsweg.

        Jede Handlung muss auch in `wartet_auf_mensch` stehen — sonst wären es zwei
        Listen, die dieselbe Frage verschieden beantworten, und der Kopfblock im Cockpit
        (SWR-120) würde eine andere Zahl zeigen als dieser Abschnitt.
        Verifiziert: SWR-138.
        """
        self._ticket("T-0007", verantwortlich="mensch")
        self._ticket("T-0008", typ="decision-request")
        self._ticket("T-0009")
        wartend = set(aggregation.wartet_auf_mensch(self.root))
        handlungen = set(self._refs())
        self.assertTrue(handlungen <= wartend)
        self.assertEqual(handlungen, {"p0/T-0007"})
        self.assertEqual(wartend, {"p0/T-0007", "p0/T-0008"})

    def test_die_karte_traegt_ref_titel_rolle_und_sprint(self):
        """B038: eine Liste ohne die Kennung ist keine Handlungsanweisung. `ref` kommt vom
        Server (SWR-087) und wird nicht in der Ansicht zusammengesetzt.
        Verifiziert: SWR-138."""
        self._ticket("T-0010", verantwortlich="mensch", titel="abschluss.cmd prüfen")
        h = aggregation.fuer_dich_handlungen(self.root)[0]
        self.assertEqual(h["ref"], "p0/T-0010")
        self.assertEqual(h["titel"], "abschluss.cmd prüfen")
        self.assertEqual(h["rolle"], "pl")
        self.assertEqual(h["geplant_sprint"], 15)

    def test_die_bedingung_kommt_aus_board_und_nicht_von_hier(self):
        """⚠ Identität statt Gleichheit: `fuer_dich_handlungen` formuliert die Bedingung
        „wartet auf den Menschen" nicht selbst, sondern ruft `board.wartet_auf_mensch` —
        dieselbe Stelle wie Board-Spalte (SWR-119) und Kopfblock (SWR-120). Geprüft wird
        das am **Quelltext**, weil eine Kopie der Bedingung sich nicht am Ergebnis zeigt,
        solange beide gleich lauten — genau die Lage, die SWR-131 gekostet hat.
        Verifiziert: SWR-138."""
        import ast
        quelle = os.path.join(os.path.dirname(__file__), "..", "backend",
                              "aggregation.py")
        with open(quelle, encoding="utf-8") as f:
            baum = ast.parse(f.read())
        funktion = next(n for n in ast.walk(baum) if isinstance(n, ast.FunctionDef)
                        and n.name == "fuer_dich_handlungen")
        aufrufe = {ast.unparse(n.func) for n in ast.walk(funktion)
                   if isinstance(n, ast.Call)}
        self.assertIn("board.wartet_auf_mensch", aufrufe)


if __name__ == "__main__":
    unittest.main()
