"""Unit-Verifikation Statusdrift zwischen Plan und Ticket (SWR-115, pm/T-0049).

Anlass (Sprint 8, 2026-08-17): Sprint 7 hat `platform/T-0010` an vier Stellen als erledigt
gemeldet — Planzeile, Sprintabschluss, Session-Agenda und Statusbericht an den Auftraggeber
— während das Ticket auf `open` stand. Die Arbeit war fertig; nur das Feld wurde nie
umgelegt. Alle drei vorhandenen Planprüfungen meldeten leer.

Ausführung: python -m unittest discover platform/tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import sprint  # noqa: E402


def zeile(aufgabe, faellig, status, refs=None):
    """Eine Planzeile, wie `sprint.zeilen` sie liefert — nur die hier gelesenen Felder."""
    return {"aufgabe": aufgabe,
            "refs": refs if refs is not None else sorted(sprint.refs_der_zeile(aufgabe)),
            "faellig": faellig,
            "sprint_nr": sprint.sprint_nummer(faellig),
            "status": status}


def ticket(ref, status, takt="", titel="T"):
    projekt, tid = ref.split("/")
    return {"projekt": projekt, "id": tid, "ref": ref, "titel": titel,
            "status": status, "typ": "task", "takt": takt, "geplant_sprint": ""}


class StatusDriftTest(unittest.TestCase):
    """Die Prüfung selbst. Verifiziert: SWR-115."""

    def test_plan_sagt_erledigt_ticket_ist_offen_ist_befund(self):
        """Der Originalfall: `platform/T-0010`, Sprint 7. Verifiziert: SWR-115."""
        zeilen = [zeile("platform/T-0010", "dieser Sprint", "**erledigt**")]
        alle = [ticket("platform/T-0010", "open")]
        treffer = sprint.status_drift(zeilen, alle)
        self.assertEqual(len(treffer), 1)
        self.assertEqual(treffer[0]["ref"], "platform/T-0010")
        self.assertEqual(treffer[0]["richtung"], "plan_zu_frueh_fertig")
        self.assertIn("erledigt", treffer[0]["meldung"])
        self.assertIn("open", treffer[0]["meldung"])

    def test_die_zeile_mit_diesem_sprint_wird_geprueft_und_nicht_uebersprungen(self):
        """**Der Kern des Tickets.** `plan_drift` (SWR-109) überspringt jede Zeile, deren
        Fälligkeitsspalte „dieser Sprint" sagt, weil sie keine Sprintnummer trägt — und das
        ist genau die Zeilenart, die ein laufender Sprint schließt. Diese Prüfung darf
        genau dort **nicht** schweigen. Verifiziert: SWR-115."""
        zeilen = [zeile("platform/T-0010", "dieser Sprint", "erledigt")]
        alle = [ticket("platform/T-0010", "open")]
        # Gegenprobe am echten Verhalten von SWR-109: die Zeile trägt keine Nummer …
        self.assertIsNone(zeilen[0]["sprint_nr"])
        self.assertEqual(sprint.plan_drift(zeilen, alle), [])
        # … und wird von SWR-115 trotzdem geprüft.
        self.assertEqual(len(sprint.status_drift(zeilen, alle)), 1)

    def test_plan_sagt_erledigt_ticket_ist_done_ist_kein_befund(self):
        zeilen = [zeile("platform/T-0010", "dieser Sprint", "**erledigt**")]
        alle = [ticket("platform/T-0010", "done")]
        self.assertEqual(sprint.status_drift(zeilen, alle), [])

    def test_rejected_zaehlt_als_geschlossen(self):
        """`rejected` ist ein Abschluss wie `done` — dieselbe Grenze, die
        `offene_tickets` zieht. Verifiziert: SWR-115."""
        zeilen = [zeile("p0/T-0008", "dieser Sprint", "erledigt")]
        alle = [ticket("p0/T-0008", "rejected")]
        self.assertEqual(sprint.status_drift(zeilen, alle), [])

    def test_ticket_ist_done_plan_sagt_offen_ist_befund(self):
        """Die **zweite Richtung**: ein geschlossenes Ticket sieht im Plan wie
        unerledigte Arbeit aus. Über `offene_tickets` wäre dieser Fall grundsätzlich
        unsichtbar. Verifiziert: SWR-115."""
        zeilen = [zeile("pm/T-0043", "Sprint 8", "offen")]
        alle = [ticket("pm/T-0043", "done")]
        treffer = sprint.status_drift(zeilen, alle)
        self.assertEqual(len(treffer), 1)
        self.assertEqual(treffer[0]["richtung"], "ticket_zu_frueh_fertig")

    def test_vorgelegt_ueber_offenem_dr_ist_kein_befund(self):
        """`p11/T-0006` liegt beim Auftraggeber und trägt im Plan „vorgelegt". Das ist
        eine offene Aussage über ein offenes Ticket. Verifiziert: SWR-115."""
        zeilen = [zeile("p11/T-0006", "wartet-auf-Mensch", "vorgelegt")]
        alle = [ticket("p11/T-0006", "open")]
        self.assertEqual(sprint.status_drift(zeilen, alle), [])

    def test_blockiert_ueber_blockiertem_ticket_ist_kein_befund(self):
        zeilen = [zeile("p11/T-0003", "wartet-auf-Mensch", "**blocked**")]
        alle = [ticket("p11/T-0003", "blocked")]
        self.assertEqual(sprint.status_drift(zeilen, alle), [])


class TaktAusnahmeTest(unittest.TestCase):
    """Die Ausnahme — und die Gegenprobe, die sie widerlegbar macht. Verifiziert: SWR-115."""

    def test_taktdauerlaeufer_ist_kein_befund(self):
        """**Die Gegenprobe zur Ausnahme.** Ein Dauerläufer trägt dauerhaft „erfüllt" im
        Plan und `open` im Ticket, und beides ist richtig — er wird nie `done`. Ohne diese
        Ausnahme meldete die Prüfung an ihrem ersten Tag sechs Fehlalarme, und ein
        Fehlalarm an Tag eins trainiert das Wegsehen. Verifiziert: SWR-115."""
        zeilen = [zeile("pm/T-0001", "jeder Sprint", "erfüllt")]
        alle = [ticket("pm/T-0001", "open", takt="je-session")]
        self.assertEqual(sprint.status_drift(zeilen, alle), [])

    def test_taktdauerlaeufer_auch_mit_wortlaut_erledigt_ausgenommen(self):
        """Die Ausnahme hängt am **Ticketfeld** `takt`, nicht am Wortlaut der Planspalte.
        Schriebe jemand „erledigt" statt „erfüllt", bliebe der Dauerläufer ausgenommen —
        sonst entstünde ein Befund aus einer Formulierung statt aus einem Sachverhalt.
        Verifiziert: SWR-115."""
        zeilen = [zeile("pm/T-0002", "jeder Sprint", "erledigt")]
        alle = [ticket("pm/T-0002", "open", takt="je-session")]
        self.assertEqual(sprint.status_drift(zeilen, alle), [])

    def test_ohne_takt_feld_ist_dieselbe_zeile_ein_befund(self):
        """**Die Gegenprobe, ohne die die Ausnahme nicht widerlegbar wäre.** Dieselbe
        Planzeile, dasselbe Statuswort — nur ohne `takt` im Ticket — **ist** ein Befund.
        Verifiziert: SWR-115."""
        zeilen = [zeile("pm/T-0002", "jeder Sprint", "erledigt")]
        alle = [ticket("pm/T-0002", "open", takt="")]
        self.assertEqual(len(sprint.status_drift(zeilen, alle)), 1)


class AbgrenzungTest(unittest.TestCase):
    """Was die Prüfung bewusst NICHT meldet. Verifiziert: SWR-115."""

    def test_zeile_ohne_bekanntes_ticket_wird_ignoriert(self):
        zeilen = [zeile("irgendeine Fließtextzeile", "dieser Sprint", "erledigt")]
        self.assertEqual(sprint.status_drift(zeilen, [ticket("pm/T-0001", "open")]), [])

    def test_unbekanntes_statuswort_wird_ignoriert_statt_geraten(self):
        """Was in keiner der beiden Mengen steht, wird ignoriert. Ein Ratefehler wäre ein
        Fehlalarm über einen korrekt geführten Plan. Verifiziert: SWR-115."""
        zeilen = [zeile("pm/T-0039", "Sprint 9", "läuft noch ein bisschen")]
        alle = [ticket("pm/T-0039", "done")]
        self.assertEqual(sprint.status_drift(zeilen, alle), [])

    def test_leere_statusspalte_wird_ignoriert(self):
        zeilen = [zeile("pm/T-0039", "Sprint 9", "")]
        alle = [ticket("pm/T-0039", "done")]
        self.assertEqual(sprint.status_drift(zeilen, alle), [])

    def test_nackte_id_wird_nur_bei_eindeutigkeit_aufgeloest(self):
        """`T-0003` gibt es in `p11` und `p12`. Eine nackte ID darf dann keiner Seite
        zugeordnet werden — sonst meldete die Prüfung einen Drift, den es nicht gibt.
        Dieselbe Regel wie in `plan_drift`. Verifiziert: SWR-115."""
        zeilen = [zeile("T-0003", "Sprint 9", "erledigt", refs=["T-0003"])]
        alle = [ticket("p11/T-0003", "open"), ticket("p12/T-0003", "open")]
        self.assertEqual(sprint.status_drift(zeilen, alle), [])

    def test_nackte_id_wird_bei_eindeutigkeit_aufgeloest(self):
        zeilen = [zeile("T-0049", "dieser Sprint", "erledigt", refs=["T-0049"])]
        alle = [ticket("pm/T-0049", "open")]
        self.assertEqual(len(sprint.status_drift(zeilen, alle)), 1)


class BestandTest(unittest.TestCase):
    """Abgleich gegen den echten Bestand. Verifiziert: SWR-115."""

    def test_echter_plan_ist_frei_von_statusdrift(self):
        """Der Plan der Organisation und die Ticketfelder sagen dasselbe. Dieser Test ist
        der Grund, warum der Befund aus Sprint 7 nicht wiederkehren kann, ohne
        aufzufallen. Verifiziert: SWR-115."""
        root = os.path.join(os.path.dirname(__file__), "..", "..")
        if not os.path.isdir(os.path.join(root, "pm", "management")):
            self.skipTest("kein Bestand")
        ergebnis = sprint.plan(root)
        self.assertEqual(ergebnis["status_drift"], [],
                         "Statusdrift im echten Plan: %s" % ergebnis["status_drift"])

    def test_alle_tickets_enthaelt_geschlossene(self):
        """`offene_tickets` lässt `done` weg — `alle_tickets` darf das nicht, sonst ist
        die zweite Melderichtung blind. Verifiziert: SWR-115."""
        root = os.path.join(os.path.dirname(__file__), "..", "..")
        if not os.path.isdir(os.path.join(root, "pm", "tickets")):
            self.skipTest("kein Bestand")
        alle = sprint.alle_tickets(root)
        offen = sprint.offene_tickets(root)
        self.assertGreater(len(alle), len(offen))
        self.assertTrue(any(t["status"] in sprint.TICKET_GESCHLOSSEN for t in alle))


if __name__ == "__main__":
    unittest.main()
