"""Org-weite Summe der Tickets ohne Frist (SWR-114, pm/T-0036 Teil b).

Befund B049: der Zaehler aus SWR-091 wird PRO KACHEL gelesen und nie als Summe.
Drei Sessions in Folge erklaerten ihn fuer abgearbeitet, waehrend drei Tickets in
einer anderen Kachel offen blieben. Gemeldet werden Namen, nicht nur eine Zahl.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import preflight  # noqa: E402


class UnterminiertTest(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.verz = os.path.join(self.root, "p0", "tickets")
        os.makedirs(self.verz)

    def ticket(self, tid, **felder):
        zeilen = ["---", "id: %s" % tid]
        felder.setdefault("status", "open")
        felder.setdefault("typ", "task")
        for k, v in felder.items():
            zeilen.append("%s: %s" % (k, v))
        zeilen += ["---", "", "Text."]
        with open(os.path.join(self.verz, "%s.md" % tid), "w", encoding="utf-8") as f:
            f.write("\n".join(zeilen))

    def test_offenes_ticket_ohne_frist_wird_namentlich_gemeldet(self):
        """Das Abnahmekriterium des Tickets: NAMENTLICH, nicht als Zahl."""
        self.ticket("T-0001")
        self.assertEqual(preflight.unterminierte_tickets(self.root), ["p0/T-0001"])

    def test_ticket_mit_frist_ist_kein_treffer(self):
        self.ticket("T-0002", frist="2026-08-30")
        self.assertEqual(preflight.unterminierte_tickets(self.root), [])

    def test_takt_ticket_ist_kein_treffer(self):
        """Takt-Tickets tragen ihr Zeitkonzept im Feld `takt` (SWR-074)."""
        self.ticket("T-0003", takt="je-session")
        self.assertEqual(preflight.unterminierte_tickets(self.root), [])

    def test_decision_request_ist_kein_treffer(self):
        """Ein DR wird ueber frist+default gesteuert (dieselbe Abgrenzung wie SWR-091)."""
        self.ticket("T-0004", typ="decision-request")
        self.assertEqual(preflight.unterminierte_tickets(self.root), [])

    def test_geschlossenes_ticket_ist_kein_treffer(self):
        self.ticket("T-0005", status="done")
        self.ticket("T-0006", status="rejected")
        self.assertEqual(preflight.unterminierte_tickets(self.root), [])

    def test_mehrere_projekte_werden_summiert(self):
        """⚠ Der Kern von B049: die Frage gilt der ORGANISATION, nicht einer Kachel."""
        self.ticket("T-0001")
        zweit = os.path.join(self.root, "p1", "tickets")
        os.makedirs(zweit)
        with open(os.path.join(zweit, "T-0009.md"), "w", encoding="utf-8") as f:
            f.write("---\nid: T-0009\nstatus: open\ntyp: task\n---\n")
        treffer = preflight.unterminierte_tickets(self.root)
        self.assertEqual(sorted(treffer), ["p0/T-0001", "p1/T-0009"])

    def test_leerer_bestand(self):
        self.assertEqual(preflight.unterminierte_tickets(self.root), [])


class BestandTest(unittest.TestCase):
    """Gegen den echten Bestand — die Zahl muss mit der des Cockpits uebereinstimmen."""

    def test_stimmt_mit_der_cockpit_summe_ueberein(self):
        """Zwei Stellen duerfen nicht verschieden zaehlen (B033)."""
        wurzel = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
        sys.path.insert(0, os.path.join(wurzel, "platform"))
        from backend import aggregation
        roh = aggregation.cockpit_alle(wurzel)
        eintraege = roh if isinstance(roh, list) else roh.get("projekte", roh)
        cockpit_summe = sum(e.get("unterminiert", 0) for e in eintraege
                            if isinstance(e, dict))
        self.assertEqual(len(preflight.unterminierte_tickets(wurzel)), cockpit_summe)


if __name__ == "__main__":
    unittest.main()
