"""Die Termin-Zange am gesperrten Ticket (SWR-198, platform/T-0051, Sprint 31).

Ein Ticket auf `status: blocked` hatte bis Sprint 30 **keinen zulaessigen Terminwert**:
ein vergangener Sprint erzeugte einen Befund in `sprint.sprint_vergangen` (SWR-112), ein
leerer einen in `aggregation.unterminierte_tickets` (SWR-114/125), und der einzige Wert,
der beide still hielt, war eine Terminzusage ueber fremdes Handeln — also die falsche
Handlung.

⚠ Die Zusicherungen stehen bewusst als **PAAR** je Pruefung: gesperrt -> still UND
ungesperrt -> Befund. Eine Pruefung, die nur die Abwesenheit eines Befundes misst, ist
nach einem Kahlschlag ebenfalls gruen (Bauform aus SWR-148/SWR-135).

⚠ Die Ausnahme haengt am **Verweis** und nicht am Wort: `blocked` ohne `blocked_by` ist
eine Behauptung, und eine Ausnahme, die auf ein blosses Statuswort hoert, waere ein
Schlupfloch (DoD-Punkt 3 des Tickets, ausdruecklich geprueft statt vorausgesetzt).

Lehre: L-2026-08-21cm.
"""
import os
import sys
import tempfile
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
sys.path.insert(0, os.path.join(_HIER, ".."))

import board  # noqa: E402
from backend import aggregation  # noqa: E402
from backend import sprint  # noqa: E402


class GesperrtPraedikatTest(unittest.TestCase):
    """`board.gesperrt` — die EINE Stelle, an der die Begruendung wohnt (SWR-198)."""

    def test_blocked_mit_verweis_ist_gesperrt(self):
        self.assertTrue(board.gesperrt({"status": "blocked",
                                        "blocked_by": "[pm/T-0077]"}))

    def test_blocked_OHNE_verweis_ist_NICHT_gesperrt(self):
        """⚠ Das Schlupfloch, das DoD 3 ausdruecklich zur Entscheidung gestellt hat.

        Wuerde die Ausnahme am Wort haengen, koennte jedes unbequeme Ticket mit einem
        Statuswort aus beiden Pruefungen genommen werden. Sie haengt am Verweis.
        """
        self.assertFalse(board.gesperrt({"status": "blocked", "blocked_by": "[]"}))
        self.assertFalse(board.gesperrt({"status": "blocked"}))

    def test_offenes_ticket_mit_verweis_ist_nicht_gesperrt(self):
        """Ein `blocked_by` allein sperrt nicht — der Status sagt es."""
        self.assertFalse(board.gesperrt({"status": "open",
                                         "blocked_by": "[pm/T-0077]"}))

    def test_validierung_verbietet_blocked_ohne_verweis(self):
        """Die Messung hinter DoD 3: das Loch kann heute gar nicht entstehen.

        ⚠ Diese Zusicherung ist der Grund, warum die Bindung an den Verweis heute
        NICHTS kostet — und sie wird rot, wenn jemand den Validator aufweicht. Die
        Ausnahme in `gesperrt` bleibt davon unberuehrt: zwei Tore, nicht eines.
        """
        fehler = board.validiere({"id": "T-0001", "titel": "x", "typ": "task",
                                  "status": "blocked", "rolle": "dev",
                                  "prozess": "swe3", "prio": "mittel",
                                  "blocked_by": "[]"},
                                 alle_ids={"T-0001"}, repo=None, git_pruefen=False)
        self.assertTrue(any("blocked erfordert blocked_by" in f for f in fehler),
                        "Validator laesst `blocked` ohne Verweis durch: %r" % fehler)


class _Bestand(unittest.TestCase):
    """Gemeinsame synthetische Wurzel (L-2026-08-20cm: NICHT am Live-Bestand)."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.verz = os.path.join(self.root, "p0", "tickets")
        os.makedirs(self.verz)
        # ⚠ `aggregation.projekte` verlangt ein `.git` je Einheit, `board.projekt_pfade`
        # NICHT — zwei Discovery-Wege mit verschieden weiten Grundmengen. Am echten
        # Bestand gemessen (2026-08-21, Sprint 31): beide liefern **dieselben 17**
        # Einheiten, also heute kein Befund. In der Vorrichtung muss der Ordner trotzdem
        # da sein, sonst prueft die Haelfte ueber `sprint.offene_tickets` an einer leeren
        # Menge und waere fuer immer gruen (SWR-128-Familie).
        os.makedirs(os.path.join(self.root, "p0", ".git"))

    def ticket(self, tid, **felder):
        felder.setdefault("status", "open")
        felder.setdefault("typ", "task")
        zeilen = ["---", "id: %s" % tid]
        zeilen += ["%s: %s" % (k, v) for k, v in felder.items()]
        zeilen += ["---", "", "Text."]
        with open(os.path.join(self.verz, "%s.md" % tid), "w", encoding="utf-8") as f:
            f.write("\n".join(zeilen))


class UnterminiertTest(_Bestand):
    """Haelfte 1 der Zange: `geplant_sprint` LEER (SWR-114/125)."""

    def test_gesperrtes_ticket_ohne_termin_ist_STILL(self):
        self.ticket("T-0001", status="blocked", blocked_by="[pm/T-0077]",
                    geplant_sprint="")
        self.assertEqual(aggregation.unterminierte_tickets(self.root), [])

    def test_UNgesperrtes_ticket_ohne_termin_wird_WEITER_gemeldet(self):
        """Die Gegenprobe — ohne sie waere ein Kahlschlag ebenfalls gruen."""
        self.ticket("T-0002", geplant_sprint="")
        self.assertEqual(aggregation.unterminierte_tickets(self.root), ["p0/T-0002"])

    def test_blocked_OHNE_verweis_ohne_termin_wird_gemeldet(self):
        """Das Schlupfloch bleibt zu: die Behauptung befreit nicht vom Termin."""
        self.ticket("T-0003", status="blocked", blocked_by="[]", geplant_sprint="")
        self.assertEqual(aggregation.unterminierte_tickets(self.root), ["p0/T-0003"])


class SprintVergangenTest(_Bestand):
    """Haelfte 2 der Zange: `geplant_sprint` VERGANGEN (SWR-112)."""

    def _vergangen(self, jetzt=31):
        offene = sprint.offene_tickets(self.root)
        return [t["ref"] for t in sprint.sprint_vergangen(offene, jetzt)]

    def test_gesperrtes_ticket_auf_altem_sprint_ist_STILL(self):
        self.ticket("T-0001", status="blocked", blocked_by="[pm/T-0077]",
                    geplant_sprint="29")
        self.assertEqual(self._vergangen(), [])

    def test_UNgesperrtes_ticket_auf_altem_sprint_wird_WEITER_gemeldet(self):
        self.ticket("T-0002", geplant_sprint="29")
        self.assertEqual(self._vergangen(), ["p0/T-0002"])

    def test_blocked_OHNE_verweis_auf_altem_sprint_wird_gemeldet(self):
        self.ticket("T-0003", status="blocked", blocked_by="[]", geplant_sprint="29")
        self.assertEqual(self._vergangen(), ["p0/T-0003"])

    def test_gesperrtes_ticket_traegt_seine_sperre_in_der_flachen_zeile(self):
        """SWR-198: `plan()` entfernt `_ticket` — ohne dieses Feld waere die Sperre
        fuer jeden Leser des Payloads unsichtbar und `board.gesperrt` haette auf der
        ausgelieferten Zeile eine andere Antwort als auf der internen (B033)."""
        self.ticket("T-0001", status="blocked", blocked_by="[pm/T-0077]")
        zeile = sprint.offene_tickets(self.root)[0]
        zeile.pop("_ticket")
        self.assertTrue(board.gesperrt(zeile))


class ZangeTest(_Bestand):
    """⚠⚠ Der eigentliche Befund: BEIDE Werte muessen still sein.

    Eine der beiden Pruefungen allein zu reparieren, verschiebt den Befund nur — genau
    das ist beim Abschluss von Sprint 30 passiert (Termin geleert, Befund umgezogen).
    """

    def test_gesperrt_ist_mit_altem_UND_mit_leerem_termin_befundfrei(self):
        self.ticket("T-0001", status="blocked", blocked_by="[pm/T-0077]",
                    geplant_sprint="29")
        self.ticket("T-0002", status="blocked", blocked_by="[pm/T-0077]",
                    geplant_sprint="")
        offene = sprint.offene_tickets(self.root)
        self.assertEqual(sprint.sprint_vergangen(offene, 31), [])
        self.assertEqual(aggregation.unterminierte_tickets(self.root), [])

    def test_dieselbe_lage_ungesperrt_erzeugt_JE_EINEN_befund(self):
        """Die Zange, wie sie vor SWR-198 fuer jedes gesperrte Ticket aussah."""
        self.ticket("T-0001", geplant_sprint="29")
        self.ticket("T-0002", geplant_sprint="")
        offene = sprint.offene_tickets(self.root)
        self.assertEqual([t["ref"] for t in sprint.sprint_vergangen(offene, 31)],
                         ["p0/T-0001"])
        self.assertEqual(aggregation.unterminierte_tickets(self.root), ["p0/T-0002"])


class EineBegruendungTest(unittest.TestCase):
    """DoD: eine Begruendung, REFERENZIERT statt kopiert.

    ⚠ Diese Zusicherung prueft die Bauform und nicht das Verhalten — sie ist der
    Vertreter der Lehre selbst. Ohne sie koennte die naechste Session die Ausnahme
    bequem in beide Module schreiben, und zwei Begruendungen fuer eine Sache laufen
    auseinander (B033, in diesem Haus mehrfach bezahlt).
    """

    def _quelle(self, *teile):
        with open(os.path.join(_HIER, "..", *teile), encoding="utf-8") as f:
            return f.read()

    def test_beide_pruefungen_rufen_board_gesperrt_auf(self):
        self.assertIn("board.gesperrt", self._quelle("backend", "sprint.py"))
        self.assertIn("board.gesperrt", self._quelle("backend", "aggregation.py"))

    def test_die_begruendung_steht_nur_in_board(self):
        """Der Kernsatz der Begruendung darf genau EINMAL im Betriebscode stehen."""
        satz = "keinen zulässigen Terminwert"
        treffer = [p for p in (("scripts", "board.py"), ("backend", "sprint.py"),
                               ("backend", "aggregation.py"))
                   if satz in self._quelle(*p)]
        self.assertEqual(treffer, [("scripts", "board.py")],
                         "Begruendung kopiert statt referenziert: %r" % (treffer,))


if __name__ == "__main__":
    unittest.main()
