#!/usr/bin/env python3
"""SWR-226 (pm/T-0001, Sprint 39): die Plantabelle wird an ihren SPALTEN erkannt, nicht

an ihrer STELLE.

## Warum diese Datei existiert — derselbe Fehler, zweimal, in derselben Datei

`plan_tabelle` nahm bis Sprint 39 die **erste** Tabelle nach der Sprint-Plan-Überschrift.
Wer über dieser Tabelle eine zweite einfügt, entzieht damit **allen** Sprintprüfungen
ihre Eingabe — und sie melden dann nicht „kaputt", sondern **0**.

| Lauf | Was passierte | Wie es auffiel |
|---|---|---|
| **Sprint 37** | eine Befund-Tabelle stand vor der Plantabelle | `plan_drift: 0` sah richtig aus; gefunden nur an `nicht_geplant: 39` |
| **Sprint 39** | derselbe Fehler, dieselbe Datei, obwohl die Lehre im Bericht stand | wieder nur an `nicht_geplant: 33` |

> **Eine Prüfung, die nichts findet, weil sie nichts liest, sieht genauso aus wie eine,
> die nichts zu finden hatte.**

> **⚠⚠ Und eine Lehre, die zweimal denselben Fehler nicht verhindert hat, ist keine Lehre,
> sondern eine Notiz. Der Vertreter ist die Erkennung an den Spalten — und diese Datei.**

⚠ Das ist ausdrücklich **kein** Vorwurf an eine Session: die Reihenfolge einer Tabelle ist
eine Eigenschaft des Schreibens, und der Schreibende sieht den Parser nicht (dieselbe
Begründung wie beim Vertragswächter, `L-2026-08-17y`).
"""
import os
import sys
import unittest

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PLATFORM)

from backend import sprint  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bestandswaechter  # noqa: E402

KOPF = "## Sprint-Plan (Sprint 39)\n\n"

PLAN = ("| Aufgabe | Rolle | Fällig | Status | Grund |\n"
        "|---|---|---|---|---|\n"
        "| platform/T-0074 | dev | Sprint 40 | geplant | die rote CI |\n"
        "| pm/T-0080 | dev | Sprint 40 | geplant | Arbeitsverlauf |\n")

VORSPANN = ("| Größe | Start | Ende |\n"
            "|---|---|---|\n"
            "| offene Aufgaben | 41 | 33 |\n")


def refs(tabelle):
    return [z["aufgabe"] for z in sprint.plan_zeilen(tabelle)] if tabelle else []


class DieTabelleWirdAnIhrenSpaltenErkannt(unittest.TestCase):

    def test_ohne_vorspann_findet_sie_den_plan(self):
        t = sprint.plan_tabelle(KOPF + PLAN)
        self.assertIsNotNone(t)
        self.assertEqual(len(t["zeilen"]), 2)

    def test_MIT_vorspann_findet_sie_denselben_plan(self):
        """⚠⚠ Der Kern. Genau dieser Fall hat Sprint 37 und Sprint 39 getroffen."""
        mit = sprint.plan_tabelle(KOPF + VORSPANN + "\n" + PLAN)
        ohne = sprint.plan_tabelle(KOPF + PLAN)
        self.assertIsNotNone(mit, "die Plantabelle wird hinter einer Vorspann-Tabelle "
                                  "nicht mehr gefunden — der Befund aus Sprint 37/39")
        self.assertEqual(mit["zeilen"], ohne["zeilen"])

    def test_zwei_vorspann_tabellen_aendern_nichts(self):
        text = KOPF + VORSPANN + "\n" + VORSPANN + "\n" + PLAN
        self.assertEqual(len(sprint.plan_tabelle(text)["zeilen"]), 2)

    def test_die_alte_bauform_WAERE_hier_rot(self):
        """⚠ Die Gegenprobe zur Zusicherung darüber: ohne sie belegt sie nur, dass sie

        grün ist. Hier wird die alte Regel („nimm die erste Tabelle") nachgestellt und
        gezeigt, dass sie an derselben Eingabe die **falsche** Tabelle liefert.
        """
        from backend import aggregation
        text = KOPF + VORSPANN + "\n" + PLAN
        m = sprint.PLAN_KOPF.search(text)
        alte = aggregation.parse_md_tabellen(text[m.end():])[0]
        self.assertNotEqual(alte["zeilen"], sprint.plan_tabelle(text)["zeilen"],
                            "alte und neue Regel liefern dasselbe — dann misst dieser "
                            "Test die Änderung nicht")
        self.assertEqual(len(alte["zeilen"]), 1, "der Vorspann ist nicht die erste Tabelle")


class OhnePlantabelleGibtEsKEINEN_Rueckfall(unittest.TestCase):
    """⚠⚠ Ein stiller Rückfall auf „irgendeine Tabelle" wäre wieder der Zustand, in dem

    eine Prüfung grün meldet, weil sie das Falsche gelesen hat.
    """

    def test_nur_eine_fremde_tabelle_ergibt_None(self):
        self.assertIsNone(sprint.plan_tabelle(KOPF + VORSPANN))

    def test_ohne_ueberschrift_ergibt_None(self):
        self.assertIsNone(sprint.plan_tabelle(PLAN))

    def test_eine_tabelle_ohne_faellig_ist_kein_plan(self):
        halb = ("| Aufgabe | Rolle | Status |\n|---|---|---|\n"
                "| platform/T-0074 | dev | geplant |\n")
        self.assertIsNone(sprint.plan_tabelle(KOPF + halb),
                          "eine Tabelle ohne Termin ist kein Plan — sonst wäre jede "
                          "Aufzählung von Aufgaben einer")

    def test_eine_tabelle_ohne_aufgabe_ist_kein_plan(self):
        halb = "| Größe | Fällig |\n|---|---|\n| irgendwas | Sprint 40 |\n"
        self.assertIsNone(sprint.plan_tabelle(KOPF + halb))


@bestandswaechter.am_bestand("pm/management/sprint-aktuell.md")
class AmEchtenPlanGemessen(unittest.TestCase):
    """Die Zusicherung, die den Fehler dieses Laufs gefangen hätte."""

    def setUp(self):
        import io
        pfad = os.path.join(bestandswaechter.HAUS, "pm", "management", "sprint-aktuell.md")
        with io.open(pfad, encoding="utf-8") as f:
            self.text = f.read()

    def test_der_echte_plan_wird_gefunden(self):
        t = sprint.plan_tabelle(self.text)
        self.assertIsNotNone(t, "im echten Sprintplan wird keine Plantabelle erkannt")
        self.assertGreater(len(t["zeilen"]), 10,
                           "weniger als 11 Planzeilen — die Erkennung liest vermutlich "
                           "eine Nebentabelle (genau der Befund aus Sprint 37 und 39)")

    def test_die_gefundene_tabelle_traegt_beide_pflichtspalten(self):
        t = sprint.plan_tabelle(self.text)
        kopf = " ".join(str(s).lower() for s in t["spalten"])
        self.assertIn("aufgabe", kopf)
        self.assertTrue("fällig" in kopf or "faellig" in kopf)


if __name__ == "__main__":
    unittest.main()
