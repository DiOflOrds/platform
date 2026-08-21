"""Ein Lehrbuch verliert nichts (SWR-209, platform/T-0061).

⚠⚠ **Der Anlass ist ein Datenverlust, den fünf Sprints lang niemand bemerkt hat — und
seine Prüfung hat ihn als Fortschritt gemeldet.**

Der Abschluss-Commit von Sprint 32 (`process@a82f207`, Betreff *„Lehren cq-cv
verankert"*) kürzte `knowledge/cm/lessons.md` von **1931 auf 26 Zeilen** und
`knowledge/pl/lessons.md` von **831 auf 26**: **91 Lehr-Abschnitte gelöscht, 2
hinzugefügt.** Die Dateien wurden **geschrieben** statt **angehängt**.

Was danach geschah, ist der eigentliche Gegenstand dieser Datei:

| Sprint | Meldung | Wirklichkeit |
|---|---|---|
| 33 | *„Diese Lehre(n) haben einen Vertreter bekommen — bitte `OHNE_VERTRETER_BASIS` nachziehen, damit der **Fortschritt** gebucht ist"* (71 IDs) | 71 Gegenstände sind **verschwunden** |
| 33 | `platform/T-0061`: *„84 von 119 Lehren stehen in KEINEM Lehrbuch … sie leben ausschließlich als Zitat"* | Sie haben dort gelebt, bis ein Commit sie überschrieb |

> **⚠⚠ Eine Prüfung, die Schrumpfen nicht von Fortschritt unterscheiden kann, meldet
> beides beim Namen des angenehmeren Falls. Und ein Bestand kann verschwinden, während
> sein Wächter Erfolg meldet.**

⚠ Der härteste Beleg ist eine Zahl, die niemand erfunden hat: nach der Wiederherstellung
liefert `lehren.ohne_vertreter()` wieder **exakt 91** — Zeichen für Zeichen die Menge
`OHNE_VERTRETER_BASIS` aus Sprint 31, ohne eine einzige Abweichung in beide Richtungen.
**Die Basis hatte die ganze Zeit recht.**

Vertreter von `L-2026-08-21dd`.
"""
import os
import sys
import unittest

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)
from backend import lehren  # noqa: E402


class KeineVerankerteLehreVerschwindet(unittest.TestCase):

    def test_die_menge_ist_nicht_leer(self):
        """SWR-128-Familie: eine Prüfung über eine leere Menge ist immer grün."""
        self.assertGreaterEqual(len(lehren.VERANKERTE_LEHREN), 100,
                                "die verankerte Menge ist zusammengeschrumpft — genau "
                                "der Vorgang, den diese Datei verhindern soll")

    def test_jede_verankerte_lehre_hat_noch_ihren_kopf(self):
        """⚠⚠ Die Prüfung, die in Sprint 32 gefehlt hat. Sie nennt Namen, keine Differenz."""
        weg = lehren.verschwundene()
        self.assertEqual([], weg, (
            "Diese verankerten Lehren haben ihren Kopf in `process/knowledge/*/lessons.md` "
            "verloren: " + ", ".join(weg) + ". ⚠ Das ist kein Fortschritt und keine "
            "Umbenennung, sondern ein Verlust: ein Lehrbuch wird ANGEHÄNGT, nie "
            "geschrieben. Wiederherstellen aus der Git-Historie der Datei — und NICHT "
            "VERANKERTE_LEHREN kürzen, das wäre die bequeme Handlung aus SWR-166."))

    def test_neue_lehren_sind_erlaubt(self):
        """Die Gegenrichtung: die Menge ist eine UNTERgrenze.

        ⚠ Ohne diese Zusicherung liest sich die Datei wie eine Deckelung — und die
        nächste Session, die eine Lehre anlegt, würde die Prüfung für kaputt halten.
        """
        vorhanden = set(lehren.lehren())
        self.assertTrue(lehren.VERANKERTE_LEHREN <= vorhanden)
        # Kein assertEqual: neue Lehren dürfen dazukommen, ohne dass hier etwas rot wird.

    def test_die_pruefung_wuerde_den_verlust_finden(self):
        """⚠⚠ Gegenprobe — an einer synthetischen Menge, nicht an den Live-Dateien.

        `L-2026-08-20cm`: an einer Datei zu mutieren, die eine fremde Automatik anfasst,
        misst den Zustand von vorhin. Hier wird stattdessen der Vergleich selbst geprüft.
        """
        echt = lehren.VERANKERTE_LEHREN
        opfer = sorted(echt)[0]
        try:
            lehren.VERANKERTE_LEHREN = frozenset(echt | {"L-2099-01-01zz"})
            self.assertEqual(["L-2099-01-01zz"], lehren.verschwundene())
        finally:
            lehren.VERANKERTE_LEHREN = echt
        self.assertIn(opfer, lehren.lehren(),
                      "Grundmenge leer oder Vergleich falsch herum: eine verankerte "
                      "Lehre muss im Bestand auffindbar sein")


class DieBasisAusSprint31HatteRecht(unittest.TestCase):
    """⚠⚠ Die Zahl, die den Befund beweist — und die niemand gewählt hat."""

    def test_ohne_vertreter_ist_wieder_genau_die_basis(self):
        """91 = 91, in beide Richtungen leer.

        Vor der Wiederherstellung waren es **20**; die Differenz von 71 hat die Prüfung
        als „gewonnene Vertreter" gemeldet. Nach der Wiederherstellung stimmt die Menge
        aus Sprint 31 **namentlich** wieder — das ist der Nachweis, dass nichts
        „gewonnen" wurde, sondern etwas fehlte.
        """
        from test_lehren_vertreter import OHNE_VERTRETER_BASIS
        ist = set(lehren.ohne_vertreter())
        self.assertEqual(set(), ist - OHNE_VERTRETER_BASIS)
        self.assertEqual(set(), OHNE_VERTRETER_BASIS - ist)


if __name__ == "__main__":
    unittest.main()
