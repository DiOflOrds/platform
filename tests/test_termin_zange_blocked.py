# -*- coding: utf-8 -*-
"""`platform/T-0051`: für ein gesperrtes Ticket gibt es keinen zulässigen Terminwert.

⚠⚠ **Diese Datei sichert einen BEKANNTEN MANGEL, nicht eine gewünschte Eigenschaft.** Sie
hält fest, dass `sprint_vergangen` und `unterminierte_tickets` zusammen eine **Zange**
bilden: `geplant_sprint` mit altem Wert ist ein Befund, leer ist ein Befund, und still ist
nur eine Terminzusage über fremdes Handeln.

> **Eine Lage, in der die bequeme Handlung die einzige ist, die grün macht, ist die
> Bauart, gegen die `SWR-166` gebaut wurde.**

Vertreter von `L-2026-08-21cm` (*ein Stellvertreter wird zum Loch, sobald die Sache einen
eigenen Namen bekommt*).

⚠ **Diese Zusicherungen werden mit `T-0051` UMGEDREHT und nicht gelöscht** — die Bauform
aus `SWR-148`/`v1.61`. Eine Prüfung, die nur die Abwesenheit eines Mangels misst, ist nach
einem Kahlschlag ebenfalls grün; deshalb steht der Mangel hier **benannt** da und
verschwindet nicht still, wenn ihn jemand behebt: sie wird rot und verlangt die Umkehr.

⚠ Gemessen an einer **synthetischen** Wurzel (`L-2026-08-20cm`).
"""
import os
import sys
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)

from backend import sprint as sprint_mod  # noqa: E402


def gesperrt(geplant):
    t = {"ref": "pm/T-0071", "titel": "gesperrt", "status": "blocked",
         "typ": "task", "blocked_by": ["pm/T-0077"]}
    if geplant is not None:
        t["geplant_sprint"] = geplant
    return t


class ZangeTest(unittest.TestCase):
    """Beide Backen der Zange, an derselben Aufgabe."""

    def test_backe_1_alter_termin_ist_ein_befund(self):
        """Der Zustand, in dem Sprint 29 die drei Tickets hinterlassen hat."""
        treffer = sprint_mod.sprint_vergangen([gesperrt(29)], 30)
        self.assertEqual(len(treffer), 1)
        self.assertEqual(treffer[0]["status"], "blocked",
                         "die Prüfung sieht den Zustand — sie zieht nur keine Folge daraus")

    def test_backe_2_leerer_termin_ist_KEIN_befund_dieser_pruefung(self):
        """⚠ Wichtig für die Diagnose: `sprint_vergangen` schweigt beim leeren Wert.

        Der zweite Befund kommt von **einer anderen** Prüfung
        (`aggregation.unterminierte_tickets`, `SWR-114/125`). Genau deshalb ist es eine
        Zange und kein Fehler an einer Stelle — und deshalb repariert eine der beiden
        allein den Befund nur an einen anderen Ort.
        """
        self.assertEqual(sprint_mod.sprint_vergangen([gesperrt(None)], 30), [])

    def test_der_einzige_stille_wert_ist_eine_zusage(self):
        """⚠⚠ Der Kern: still wird es erst mit einem Termin in der Zukunft.

        Und der ist eine Zusage über fremdes Handeln — die Sperre hängt an einer
        Entscheidung des Auftraggebers (`pm/T-0077`).
        """
        self.assertEqual(sprint_mod.sprint_vergangen([gesperrt(31)], 30), [])

    def test_decision_request_hat_die_ausnahme_bereits(self):
        """⚠ Der Beleg, dass die Begründung schon im Haus steht — an einem TYP.

        `decision-request` ist ausgenommen, weil *„das Team ihn nicht bewegen kann"*.
        Für `blocked` gilt derselbe Satz; er ist nur nie auf den **Zustand** übertragen
        worden, weil es den Zustand bis `SWR-193` nicht gab.
        """
        dr = dict(gesperrt(29), typ="decision-request", status="open")
        self.assertEqual(sprint_mod.sprint_vergangen([dr], 30), [])

    def test_ein_ungesperrtes_ticket_bleibt_ein_befund(self):
        """Die Gegenrichtung: die Ausnahme darf nicht zum Freibrief werden.

        Nach `T-0051` muss diese Zusicherung **unverändert** grün bleiben — sie ist die
        Hälfte des Paars, die verhindert, dass „gesperrt" zum Wort wird, mit dem man
        Termine abschaltet.
        """
        offen = dict(gesperrt(29), status="open", blocked_by=[])
        self.assertEqual(len(sprint_mod.sprint_vergangen([offen], 30)), 1)


if __name__ == "__main__":
    unittest.main()
