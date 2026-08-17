"""Vergangener Sprint (SWR-112, pm/T-0045) und die Zaehlweise (SWR-113, pm/T-0046).

Zwei Befunde aus der Planung selbst. Der erste: niemand hielt `geplant_sprint` gegen
die GEGENWART — `widersprueche` haelt ihn gegen die Frist, `plan_drift` gegen die
Planzeile. Der zweite: die Kennzahl "nicht geschlossen" hatte keine dokumentierte
Zaehlweise und war damit weder pruefbar noch widerlegbar.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from backend import sprint  # noqa: E402


def t(ref, sprint_nr, status="open", typ="task", takt="", titel="x"):
    return {"ref": ref, "id": ref.split("/")[-1], "projekt": ref.split("/")[0],
            "titel": titel, "status": status, "typ": typ, "frist": "",
            "takt": takt, "geplant_sprint": sprint_nr}


class SprintVergangenTest(unittest.TestCase):
    """SWR-112 — offen auf einem Sprint, der vorbei ist."""

    def test_offenes_ticket_auf_vergangenem_sprint_wird_gemeldet(self):
        treffer = sprint.sprint_vergangen([t("p11/T-0003", 5)], 6)
        self.assertEqual(len(treffer), 1)
        self.assertEqual(treffer[0]["ref"], "p11/T-0003")
        self.assertEqual(treffer[0]["geplant_sprint"], 5)
        self.assertEqual(treffer[0]["jetzt"], 6)
        self.assertIn("Sprint 5", treffer[0]["meldung"])

    def test_laufender_sprint_ist_kein_befund(self):
        self.assertEqual(sprint.sprint_vergangen([t("pm/T-0045", 7)], 7), [])

    def test_kuenftiger_sprint_ist_kein_befund(self):
        self.assertEqual(sprint.sprint_vergangen([t("p12/T-0003", 10)], 7), [])

    def test_takt_dauerlaeufer_ohne_feld_ist_kein_befund(self):
        """Sie tragen absichtlich kein `geplant_sprint` (B033) — kein Termin,
        also auch kein vergangener."""
        self.assertEqual(
            sprint.sprint_vergangen([t("pm/T-0001", "", takt="je-session")], 7), [])

    def test_leeres_feld_ist_kein_befund(self):
        self.assertEqual(sprint.sprint_vergangen([t("pm/T-0001", None)], 7), [])

    def test_in_review_zaehlt_mit(self):
        """⚠ Entschieden in pm/T-0045: ein Ticket, das nach seinem Sprint noch beim
        Reviewer liegt, ist nicht korrekt geparkt — der Plan hat nicht gehalten."""
        treffer = sprint.sprint_vergangen([t("pm/T-0099", 5, status="in_review")], 7)
        self.assertEqual(len(treffer), 1)
        self.assertEqual(treffer[0]["status"], "in_review")

    def test_decision_request_ist_ausgenommen(self):
        """⚠ Der Fehlalarm an Tag eins, der vermieden werden sollte: p11/T-0006 liegt
        seit Sprint 6 ordnungsgemaess beim Auftraggeber. Seine Steuerung ist
        frist+default; reisst die Frist, meldet ihn `ueberfaellig` (SWR-091)."""
        self.assertEqual(
            sprint.sprint_vergangen([t("p11/T-0006", 6, typ="decision-request")], 7), [])

    def test_mehrere_treffer_bleiben_in_reihenfolge(self):
        treffer = sprint.sprint_vergangen(
            [t("a/T-1", 4), t("b/T-2", 9), t("c/T-3", 6)], 7)
        self.assertEqual([x["ref"] for x in treffer], ["a/T-1", "c/T-3"])

    def test_nicht_numerisches_feld_stuerzt_nicht_ab(self):
        self.assertEqual(sprint.sprint_vergangen([t("a/T-1", "bald")], 7), [])


class KennzahlenTest(unittest.TestCase):
    """SWR-113 — die festgelegte Zaehlweise."""

    def test_zerlegung_ist_vollstaendig(self):
        offene = [t("pm/T-0001", "", takt="je-session"),
                  t("pm/T-0002", "", takt="je-session"),
                  t("pm/T-0045", 7),
                  t("pm/T-0046", 7)]
        z = sprint.kennzahlen(offene)
        self.assertEqual(z, {"offen_gesamt": 4, "davon_takt": 2, "sachtickets": 2})
        self.assertEqual(z["davon_takt"] + z["sachtickets"], z["offen_gesamt"],
                         "die beiden Teilzahlen muessen die Gesamtzahl ergeben")

    def test_takt_zaehlt_mit_in_offen_gesamt(self):
        """Die Festlegung selbst: Takt-Dauerlaeufer sind Dauerpflichten und
        gehoeren in jeden Sprint — sie sind enthalten."""
        z = sprint.kennzahlen([t("pm/T-0001", "", takt="je-session")])
        self.assertEqual(z["offen_gesamt"], 1)
        self.assertEqual(z["sachtickets"], 0)

    def test_leerer_bestand(self):
        self.assertEqual(sprint.kennzahlen([]),
                         {"offen_gesamt": 0, "davon_takt": 0, "sachtickets": 0})

    def test_leeres_takt_feld_zaehlt_nicht_als_takt(self):
        z = sprint.kennzahlen([t("pm/T-0045", 7, takt="   ")])
        self.assertEqual(z["davon_takt"], 0)


class PlanLiefertBeideTest(unittest.TestCase):
    """Eine Pruefung, die nur in ihrer eigenen Funktion existiert, ist fuer die
    Kachel nicht da — der Fehler, den SWR-103 einmal hatte."""

    @classmethod
    def setUpClass(cls):
        wurzel = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
        cls.p = sprint.plan(wurzel)

    def test_plan_liefert_sprint_vergangen(self):
        self.assertIn("sprint_vergangen", self.p)
        self.assertIsInstance(self.p["sprint_vergangen"], list)

    def test_plan_liefert_kennzahlen(self):
        self.assertIn("kennzahlen", self.p)
        for schluessel in ("offen_gesamt", "davon_takt", "sachtickets"):
            self.assertIn(schluessel, self.p["kennzahlen"])

    def test_kennzahlen_stimmen_mit_offen_gesamt_ueberein(self):
        """Zwei Angaben zu derselben Frage duerfen nicht driften (B033) —
        genau der Fehler, aus dem pm/T-0046 entstanden ist."""
        self.assertEqual(self.p["kennzahlen"]["offen_gesamt"], self.p["offen_gesamt"])


if __name__ == "__main__":
    unittest.main()
