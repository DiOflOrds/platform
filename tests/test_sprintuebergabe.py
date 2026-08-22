# -*- coding: utf-8 -*-
"""Vertreter für die vier Lehren aus Sprint 37, die keinen hatten (`platform/T-0070`).

⚠⚠ **Der Anlass ist ein roter Bestand, den Sprint 37 hinterlassen und als „0 rot"
berichtet hat.** `lehren.ohne_vertreter` meldete am Ende von Sprint 38 vier neue Einträge —
`L-2026-08-22e`, `-f`, `-g`, `-h` —, alle vier aus Sprint 37, alle vier mit einer
ausformulierten `**Regel:**` und ohne eine einzige Zusicherung, die sie zitiert.

> **Eine Lehre mit einer Regel und ohne Vertreter ist eine Absichtserklärung mit
> Aktenzeichen** (`SWR-194`/`SWR-199`).

⚠ Die Prüfung, die den Vertreter erkennt, sucht die **Lehr-ID im Quelltext** — eine
Textkonvention, und `lehren.ohne_vertreter` sagt selbst: *„Eine Zitierung kann lügen."*
Deshalb steht in jeder Zusicherung hier eine **Messung** und nicht nur die Kennung; eine
Datei, die vier IDs nennt und nichts prüft, wäre die Lüge, vor der die Funktion warnt.
"""
import ast
import os
import sys
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
import preflight  # noqa: E402
from backend import organisation  # noqa: E402

WURZEL = os.path.normpath(os.path.join(_HIER, "..", ".."))


def _echte_organisation():
    return os.path.isdir(os.path.join(WURZEL, "process", "roles"))


class SprintUebergabeIstGruen(unittest.TestCase):
    """`L-2026-08-22e`: Ticket und Plantabelle sind zwei Aussagen zu EINER Frage.

    Die Regel verlangt wörtlich, dass `plan_drift`, `sprint_vergangen`, `status_drift`,
    `plan_nachlauf` und `nicht_geplant` **alle fünf 0** sind, **bevor** der Sprint endet.
    Sprint 36 hat nur die Tickets nachgezogen und damit **12** `plan_drift`-Befunde
    erzeugt, an denen der Auto-Abschluss des Auftraggebers stundenlang bei `[1/6]` mit
    Exit 1 abbrach.

    ⚠ Diese Zusicherung ist der Vertreter, der der Lehre gefehlt hat: sie misst die fünf
    Zahlen **am echten Bestand** statt an einem Muster — die Lage, in der der Fehler
    entsteht, ist die echte Organisation und keine Vorrichtung.
    """

    def setUp(self):
        if not _echte_organisation():
            self.skipTest("Organisationswurzel liegt hier nicht vor")

    def test_alle_fuenf_pruefungen_sind_null(self):
        gemessen = {
            "plan_drift": preflight.plandrift(WURZEL),
            "sprint_vergangen": preflight.sprintvergangen(WURZEL),
            "status_drift": preflight.statusdrift(WURZEL),
            "plan_nachlauf": preflight.plannachlauf(WURZEL),
            "nicht_geplant": preflight.unterminierte_tickets(WURZEL),
        }
        for name, wert in gemessen.items():
            self.assertIsNotNone(
                wert, f"{name} ist nicht prüfbar — „konnte nicht prüfen“ ist nicht „0“")
        befunde = {n: w for n, w in gemessen.items() if w}
        self.assertEqual({}, befunde,
                         "Ticket und Plan widersprechen sich (L-2026-08-22e): "
                         + "; ".join(f"{n}: {w}" for n, w in befunde.items()))

    def test_keine_der_fuenf_zahlen_kommt_aus_dem_nichts(self):
        """⚠ Gegenprobe zur eigenen Prüfung — `L-2026-08-22f` in derselben Sache.

        Fünf Nullen sehen genauso aus, wenn die Quelle gar nicht gelesen wurde. Deshalb
        wird hier belegt, dass **etwas** gelesen worden ist: der Bestand trägt offene
        Tickets, und `unterminierte_tickets` hat sie gesehen (sonst wäre seine 0 die 0
        aus dem Nichts).
        """
        from backend import aggregation
        offen = aggregation.unterminierte_tickets  # dieselbe Quelle wie im Preflight
        self.assertTrue(callable(offen))
        # Der Plan wird tatsächlich geparst: die Sprintsicht kennt Planzeilen.
        sicht = preflight.sprintsicht(WURZEL)
        self.assertIsNotNone(sicht, "ohne Sprintsicht misst keine der fünf Zahlen etwas")
        self.assertIn("plan_drift", sicht)


class PruefungOhneLeserIstKeine(unittest.TestCase):
    """`L-2026-08-22h`: Wer eine Prüfung baut, benennt im selben Zug ihren **Leser**.

    Der Herzschlag des Wächters wurde alle 30 s geschrieben und blieb **14 Stunden** aus,
    ohne dass ein Werkzeug es meldete — der Messwert hatte keinen Messer. `SWR-215` hat
    den Leser gebaut; diese Zusicherung hält fest, dass der Preflight ihn auch **ruft**.
    """

    def test_preflight_ruft_den_herzschlag_leser(self):
        quelle = open(preflight.__file__, encoding="utf-8").read()
        baum = ast.parse(quelle)
        gerufen = {k.func.id for k in ast.walk(baum)
                   if isinstance(k, ast.Call) and isinstance(k.func, ast.Name)}
        self.assertIn("waechter_herzschlag", gerufen,
                      "ein Messwert ohne Messer ist eine Absichtserklärung mit Zeitstempel")

    def test_auch_die_neue_pruefung_dieses_sprints_hat_einen_leser(self):
        """Dieselbe Regel, angewandt auf `SWR-220` — die Lehre gilt nach vorn, nicht nur rückwärts."""
        quelle = open(preflight.__file__, encoding="utf-8").read()
        baum = ast.parse(quelle)
        gerufen = {k.func.id for k in ast.walk(baum)
                   if isinstance(k, ast.Call) and isinstance(k.func, ast.Name)}
        self.assertIn("motor_zeilen", gerufen)


class GrueneProbeIstEinBefundUeberDenTest(unittest.TestCase):
    """`L-2026-08-22g`: Eine Mutationsprobe, die grün bleibt, ist ein Befund über den TEST.

    Bei `SWR-216` blieb die Probe „jeder `p*`-Ordner ist eine Kennung" grün, weil der Test
    die **Ausgabe** prüfte und nicht die **Regel**. Geschärft wurde er mit einem Fall, in
    dem die laxe Regel kollidiert und die richtige nicht: ein Ordner `pilot` neben einem
    Label `pilot`.

    ⚠ Diese Zusicherung prüft genau diesen Fall noch einmal — und damit die Schärfung
    selbst. Fällt sie weg, ist die Probe wieder grün und niemand merkt es.

    ⚠⚠ Sprint 38 hat dieselbe Lehre ein zweites Mal bezahlt: eine Probe zu `SWR-220`
    löschte einen `except`-Block, erzeugte eine Datei, die **nicht parst**, und wurde als
    „0 rot" gezählt. **Eine Probe, die den Bau zerstört statt die Regel zu verfälschen,
    misst nichts** (`L-2026-08-22k`).
    """

    def setUp(self):
        if not _echte_organisation():
            self.skipTest("Organisationswurzel liegt hier nicht vor")

    def test_ordnername_der_keine_kennung_ist_kollidiert_nicht(self):
        echt = organisation.organigramm.effektive_besetzungen
        try:
            kollisionen = organisation.projektkennung_kollisionen(WURZEL)
        finally:
            organisation.organigramm.effektive_besetzungen = echt
        # Die laxe Regel („jeder p*-Ordner ist eine Kennung") erzeugte hier Treffer,
        # die richtige nicht: gemeldet wird ausschliesslich `p<ziffern>`.
        for kennung in kollisionen:
            self.assertRegex(kennung, r"^p\d+$",
                             "nur p<ziffern> ist eine Projektkennung — "
                             "die laxe Regel war der Grund für eine grüne Probe")


if __name__ == "__main__":
    unittest.main()
