"""SWR-161 (platform/T-0022 Frage 2/3): fehlende Pflichtartefakte MELDEN statt heilen.

⚠⚠ **Die Auflage dieses Tickets war „erst zählen, dann reparieren", und die Zählung hat
die Vermutung verkleinert.** Von den sechs Artefakten, die der Gründungsweg
(`pool._projekt_dateien_schreiben`) anlegt, fehlte über alle 17 entdeckten Projekte und
Teams nur **eines** an mehr als einer Stelle. Vier fehlten **nirgends**.

> **Eine Reparatur je Fundstelle wäre dieselbe Annahme noch einmal gewesen — und eine
> Prüfung über alle sechs Artefakte ein Dauerbefund über fünf richtige Fälle.**
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import preflight  # noqa: E402
from backend import pool  # noqa: E402

WURZEL = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class PflichtartefakteTest(unittest.TestCase):
    """SWR-161: die Prüfung, die den Mangel findet, in den noch niemand gelaufen ist."""

    def test_der_echte_bestand_ist_vollstaendig(self):
        """⚠ Diese Zusicherung ist erst seit diesem Lauf grün, und der Weg dahin ist der Punkt.

        Vor der Zählung fehlte `management/decisions/decision-log.md` in `platform` —
        seit der Gründung, unbemerkt, obwohl der Vorfall vom 17.08. **genau diesen**
        Mangel in einem anderen Repo zur Klasse-A-Entscheidung eskaliert hat.
        """
        fehlend = preflight.fehlende_pflichtartefakte(WURZEL)
        self.assertEqual(fehlend, [], f"Pflichtartefakt(e) fehlen: {fehlend}")

    def test_die_pruefung_FINDET_ihren_gegenstand_wenn_er_fehlt(self):
        """⚠⚠ Die Gegenprobe, ohne die der Test darüber nichts belegt.

        *Eine Prüfung, die auf einem Bestand grün ist, in dem der geprüfte Zustand gar
        nicht vorkommt, prüft nichts* (`L-2026-08-17ai`, inzwischen dritter Beleg).
        Deshalb erzeugt dieser Test seinen eigenen Gegenstand: ein Repo mit `tickets/`
        (sonst ist es für die Discovery kein Projekt) und **ohne** Entscheidungslog —
        genau der Zustand, den `platform` bis zu diesem Lauf hatte.
        """
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "neurepo", "tickets"))
            fehlend = preflight.fehlende_pflichtartefakte(d)
            self.assertEqual(
                fehlend, [("neurepo", "management/decisions/decision-log.md")])

    def test_der_selbstheilende_weg_ERSETZT_diese_pruefung_nicht(self):
        """⚠⚠ Die Antwort auf Frage 3 des Tickets — gemessen, nicht abgewogen.

        SWR-152 legt das Log an, **wenn** eine Entscheidung verbucht wird. Das ist
        richtig: *eine getroffene Entscheidung, die am Ablageort scheitert, ist verloren,
        sobald das Fenster zu ist.* Aber es heilt genau die Stelle, an der jemand
        hineingelaufen ist — `promt-team` hat sein Log seit dem Vorfall vom 17.08.,
        `platform` hatte bis zu diesem Lauf keins.

        Gehalten wird hier die **Arbeitsteilung**: der heilende Weg schreibt, die Prüfung
        liest. Ruft die Prüfung ihrerseits etwas an, das anlegt, ist sie kein Melder mehr,
        und der Mangel wird wieder unsichtbar — die Kehrseite, die das Ticket ausdrücklich
        benannt hat.
        """
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "neurepo", "tickets"))
            preflight.fehlende_pflichtartefakte(d)
            self.assertFalse(
                os.path.exists(os.path.join(d, "neurepo", "management")),
                "die Prüfung darf MELDEN und nichts anlegen")

    def test_der_kopf_des_logs_ist_IMPORTIERT_und_nicht_abgeschrieben(self):
        """⚠ Das in Sprint 23 angelegte Log muss denselben Kopf tragen wie jedes andere.

        Ein abgeschriebener Tabellenkopf ist die Bauart, die SWR-131 gekostet hat: zwei
        Fassungen derselben Zeile, die auseinanderlaufen können, ohne dass etwas rot wird.
        """
        pfad = os.path.join(WURZEL, "platform", "management", "decisions",
                            "decision-log.md")
        self.assertTrue(os.path.isfile(pfad))
        with open(pfad, encoding="utf-8") as f:
            self.assertIn(pool.LOG_TABELLENKOPF.strip().splitlines()[0], f.read())

    def test_die_liste_ist_KURZ_und_das_ist_das_ergebnis_der_zaehlung(self):
        """⚠ `docs/01-projektauftrag.md` steht bewusst NICHT in der Pflichtliste.

        Es fehlt in **6 von 17** Repos — aber fünf davon führen stattdessen
        `01-team-charter.md`, `01-rollenbeschreibung.md` oder `02-initialprojekt-p0.md`.
        Eine Prüfung müsste **raten**, welcher Name gilt (B038), und ein Befund, der auf
        fünf richtige Fälle zeigt, trainiert das Wegsehen.

        Diese Zusicherung friert die Kürze ein: wächst die Liste, soll das eine
        **Entscheidung** sein und kein Nebenbei.
        """
        self.assertEqual(len(preflight.PFLICHTARTEFAKTE), 1)
        self.assertNotIn("projektauftrag",
                         " ".join(preflight.PFLICHTARTEFAKTE).lower())


if __name__ == "__main__":
    unittest.main()
