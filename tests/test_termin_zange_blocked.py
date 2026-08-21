# -*- coding: utf-8 -*-
"""`platform/T-0051`: die Termin-Zange am gesperrten Ticket — **aufgelöst** (SWR-198).

⚠⚠ **DIESE DATEI IST IN SPRINT 31 UMGEDREHT WORDEN, GENAU WIE SIE ES SELBST VERLANGT
HAT.** In Sprint 30 sicherte sie einen **bekannten Mangel**: `sprint_vergangen` und
`unterminierte_tickets` bildeten zusammen eine **Zange** — alter Termin ein Befund, leerer
Termin ein Befund, still nur mit einer Terminzusage über fremdes Handeln.

> **Eine Lage, in der die bequeme Handlung die einzige ist, die grün macht, ist die
> Bauart, gegen die `SWR-166` gebaut wurde.**

Ihr eigener Auftrag lautete: *„Diese Zusicherungen werden mit `T-0051` UMGEDREHT und nicht
gelöscht"* — die Bauform aus `SWR-148`/`v1.61`. Genau das ist geschehen, und **sie hat
ihre Umkehr selbst erzwungen**: nach dem Bau von `SWR-198` wurde sie rot und hat die
Session daran gehindert, den Sprint mit einer Zusicherung zu schließen, die den alten
Zustand behauptet.

> **⚠⚠ Eine Zusicherung, die einen Mangel benennt statt ihn zu verschweigen, meldet
> seine Behebung von allein. Wäre der Mangel nur in Prosa vermerkt gewesen, hätte diese
> Datei nach dem Fix schweigend weiter den alten Zustand beschrieben.**

⚠ **Und sie hat dabei einen zweiten, echten Fehler gefunden**, den keine der neuen
Zusicherungen gesehen hätte: ihre Vorrichtung baut `blocked_by` als **echte Liste**
(`["pm/T-0077"]`) — so, wie ein Mensch die Angabe denkt —, und `board.parse_liste`
scheiterte daran mit `AttributeError`, weil es immer nur Text aus dem Frontmatter kannte.
Eine Zerlegefunktion, die an ihrem eigenen Ergebnis scheitert, ist nicht idempotent.
Repariert in `board.parse_liste`.

Vertreter von `L-2026-08-21cm` (*ein Stellvertreter wird zum Loch, sobald die Sache einen
eigenen Namen bekommt*) und von `L-2026-08-21cp`.

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
    """⚠ Beide Backen der Zange — ab SWR-198 **offen**, an derselben Aufgabe."""

    def test_backe_1_alter_termin_ist_KEIN_befund_mehr(self):
        """UMGEDREHT (Sprint 31): der Zustand aus Sprint 29 ist still geworden.

        ⚠ In Sprint 30 stand hier `len(treffer) == 1` mit dem Vermerk *„die Prüfung
        sieht den Zustand — sie zieht nur keine Folge daraus"*. Sie zieht sie jetzt.
        """
        self.assertEqual(sprint_mod.sprint_vergangen([gesperrt(29)], 30), [])

    def test_backe_2_leerer_termin_bleibt_still(self):
        """⚠ Diese Backe war in `sprint_vergangen` schon immer still — der zweite Befund
        kam von `aggregation.unterminierte_tickets` (`SWR-114/125`) und ist dort mit
        derselben Ausnahme (`board.gesperrt`) aufgelöst.

        Die Zusicherung bleibt **unverändert** stehen: sie war nie die Backe, die dieses
        Modul betraf, und ihr Grünbleiben ist der Beleg, dass hier nichts umgeworfen
        wurde, was schon richtig war.
        """
        self.assertEqual(sprint_mod.sprint_vergangen([gesperrt(None)], 30), [])

    def test_ein_zukuenftiger_termin_ist_nicht_mehr_der_EINZIGE_stille_wert(self):
        """⚠⚠ Der Kern der Umkehr: still war früher **nur** die Zusage über fremdes
        Handeln. Jetzt sind **alle drei** Werte still — und damit ist die Zwangslage weg.

        Das ist die Zusicherung, die den Ertrag von `SWR-198` trägt: nicht „ein Wert ist
        still", sondern „**kein** Wert erzwingt mehr die falsche Handlung".
        """
        for termin in (29, None, 31):
            self.assertEqual(sprint_mod.sprint_vergangen([gesperrt(termin)], 30), [],
                             "Termin %r erzeugt wieder einen Befund am gesperrten "
                             "Ticket — die Zange ist zurück" % (termin,))

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

    def test_blocked_OHNE_verweis_bleibt_ein_befund(self):
        """⚠⚠ SWR-198 bindet die Ausnahme an den **Verweis**, nicht an das Wort.

        Ohne diese Zusicherung wäre „gesperrt" das Wort, mit dem sich jeder Termin
        abschalten lässt — eine Behauptung statt einer Sperre.
        """
        behauptet = dict(gesperrt(29), blocked_by=[])
        self.assertEqual(len(sprint_mod.sprint_vergangen([behauptet], 30)), 1)


if __name__ == "__main__":
    unittest.main()
