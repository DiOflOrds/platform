# -*- coding: utf-8 -*-
"""SWR-154 (platform/T-0023, Brief pm/N-0043 Punkt 2): Der Sprintplan als KAPITEL —
„Sprint N (aktuell)", „Sprint N+1 (nächster)", „Später", „Jeder Sprint (Takt)",
„Ohne Sprintbezug" — statt einer flachen Tabelle.

Zwei Zusicherungen tragen diese Anforderung, und beide sind leicht zu übersehen:

1. **Die Zerlegung ist vollständig und überschneidungsfrei.** Jede Planzeile gehört zu
   genau einem Kapitel, und die Vereinigung aller Kapitel ist der Plan. Ohne diese
   Zusicherung könnte eine Zeile still aus der Anzeige fallen — genau der Vorgang, gegen
   den `nicht_geplant` (SWR-103) gebaut ist, eine Etage weiter oben.
2. **Leer ist nicht dasselbe wie abwesend.** „aktuell" und „nächster" erscheinen auch
   ohne Zeilen; „später", „Takt" und „ohne" nur mit. Die erste Hälfte ist die Regel aus
   SWR-114/SWR-117, die zweite der Wortlaut des Auftrags.
"""
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import sprint  # noqa: E402

HEUTE = date(2026, 8, 20)
JETZT = 21

PLAN = """## Sprint-Plan (Sprint 21)

| Aufgabe | Rolle | Fällig | Status | Grund |
|---|---|---|---|---|
| platform/T-0023 | dev | dieser Sprint | in Arbeit | Kapitel bauen. |
| pm/T-0069 | pl | Sprint 21 | in Arbeit | Statusfuehrung. |
| platform/T-0020 | cm | Sprint 22 | offen | Dritte Beruehrung. |
| projects/p12/T-0011 | pl | Sprint 24 | offen | Weit hinten. |
| pm/T-0001 | pl | jeder Sprint | erfüllt | Takt-Dauerlaeufer. |
| team-mail/T-0001 | dev | wartet-auf-Mensch | offen | Zugangsdaten fehlen. |
| pm/T-0034 | prob | 2026-08-23 | offen | Echtes Datum. |
"""


def _zeilen(text=PLAN, jetzt_nr=JETZT):
    return sprint.zeilen(sprint.plan_tabelle(text), HEUTE, jetzt_nr)


class ZuordnungTest(unittest.TestCase):
    """Jede Sorte „Fällig"-Zelle landet in dem Kapitel, das im Ticket benannt ist."""

    def test_takt_zeile_geht_in_das_takt_kapitel_und_nicht_in_aktuell(self):
        """⚠ `faellig_zustand` faltet „dieser Sprint" und „jeder Sprint" zusammen —
        für die Kapitel ist genau dieser Unterschied der Punkt."""
        self.assertEqual(sprint.kapitel("jeder Sprint", JETZT), sprint.KAPITEL_TAKT)
        self.assertEqual(sprint.kapitel("je Session", JETZT), sprint.KAPITEL_TAKT)
        # Gegenprobe: derselbe Wert hat denselben ZUSTAND wie „dieser Sprint" ...
        self.assertEqual(sprint.faellig_zustand("jeder Sprint", HEUTE)[0],
                         sprint.faellig_zustand("dieser Sprint", HEUTE)[0])
        # ... und trotzdem ein anderes KAPITEL.
        self.assertNotEqual(sprint.kapitel("jeder Sprint", JETZT),
                            sprint.kapitel("dieser Sprint", JETZT))

    def test_dieser_sprint_geht_nach_aktuell(self):
        self.assertEqual(sprint.kapitel("dieser Sprint", JETZT), sprint.KAPITEL_AKTUELL)

    def test_die_laufende_nummer_geht_nach_aktuell(self):
        self.assertEqual(sprint.kapitel("Sprint 21", JETZT), sprint.KAPITEL_AKTUELL)

    def test_eine_vergangene_nummer_geht_nach_aktuell_und_nicht_verloren(self):
        """Eine Zeile, die auf einem vergangenen Sprint stehen blieb, ist FÄLLIG —
        sie in ein Kapitel „Vergangenheit" zu schieben hiesse, sie wegzusortieren."""
        self.assertEqual(sprint.kapitel("Sprint 19", JETZT), sprint.KAPITEL_AKTUELL)

    def test_die_naechste_nummer_geht_nach_naechster(self):
        self.assertEqual(sprint.kapitel("Sprint 22", JETZT), sprint.KAPITEL_NAECHSTER)

    def test_eine_weitere_nummer_geht_nach_spaeter(self):
        self.assertEqual(sprint.kapitel("Sprint 23", JETZT), sprint.KAPITEL_SPAETER)
        self.assertEqual(sprint.kapitel("Sprint 99", JETZT), sprint.KAPITEL_SPAETER)

    def test_datum_und_mensch_gehen_nach_ohne_sprintbezug(self):
        """⚠ NICHT nach „Später": das waere eine Aussage ueber einen Sprint, die im
        Plan nicht steht."""
        self.assertEqual(sprint.kapitel("2026-08-23", JETZT), sprint.KAPITEL_OHNE)
        self.assertEqual(sprint.kapitel("wartet-auf-Mensch", JETZT), sprint.KAPITEL_OHNE)
        self.assertEqual(sprint.kapitel("", JETZT), sprint.KAPITEL_OHNE)

    def test_ohne_bekannte_sprintnummer_gibt_es_keine_kapitel(self):
        """„Sprint 0 (aktuell)" waere eine Behauptung, die niemand getroffen hat."""
        self.assertEqual(sprint.kapitel("dieser Sprint", 0), "")
        self.assertEqual(sprint.kapitel("Sprint 22", 0), "")
        self.assertEqual(sprint.kapitel_koepfe(_zeilen(jetzt_nr=0), 0), [])


class ZerlegungTest(unittest.TestCase):
    """⚠⚠ Die Zusicherung, ohne die eine Zeile still verschwinden könnte."""

    def test_jede_zeile_gehoert_zu_genau_einem_kapitel(self):
        zeilen = _zeilen()
        schluessel = [z["kapitel"] for z in zeilen]
        self.assertEqual(len(schluessel), len(zeilen))
        for k in schluessel:
            self.assertIn(k, sprint.KAPITEL_REIHENFOLGE)

    def test_die_vereinigung_der_kapitel_ist_der_plan(self):
        zeilen = _zeilen()
        koepfe = sprint.kapitel_koepfe(zeilen, JETZT)
        summe = sum(k["anzahl"] for k in koepfe)
        self.assertEqual(summe, len(zeilen))

    def test_die_zahlen_der_koepfe_stimmen_mit_den_zeilen_ueberein(self):
        zeilen = _zeilen()
        for k in sprint.kapitel_koepfe(zeilen, JETZT):
            gezaehlt = sum(1 for z in zeilen if z["kapitel"] == k["schluessel"])
            with self.subTest(kapitel=k["schluessel"]):
                self.assertEqual(k["anzahl"], gezaehlt)

    def test_der_beispielplan_verteilt_sich_wie_erwartet(self):
        """Gegen einen Plan mit allen fuenf Sorten — nicht gegen einen bequemen."""
        zeilen = _zeilen()
        verteilt = {}
        for z in zeilen:
            verteilt[z["kapitel"]] = verteilt.get(z["kapitel"], 0) + 1
        self.assertEqual(verteilt, {sprint.KAPITEL_AKTUELL: 2,
                                    sprint.KAPITEL_NAECHSTER: 1,
                                    sprint.KAPITEL_SPAETER: 1,
                                    sprint.KAPITEL_TAKT: 1,
                                    sprint.KAPITEL_OHNE: 2})


class KoepfeTest(unittest.TestCase):
    """Reihenfolge, Titel mit Nummer, und die Regel „leer ist nicht abwesent"."""

    def test_die_reihenfolge_ist_aktuell_naechster_spaeter_takt_ohne(self):
        koepfe = sprint.kapitel_koepfe(_zeilen(), JETZT)
        self.assertEqual([k["schluessel"] for k in koepfe],
                         [sprint.KAPITEL_AKTUELL, sprint.KAPITEL_NAECHSTER,
                          sprint.KAPITEL_SPAETER, sprint.KAPITEL_TAKT,
                          sprint.KAPITEL_OHNE])

    def test_die_nummer_steht_im_titel(self):
        koepfe = {k["schluessel"]: k for k in sprint.kapitel_koepfe(_zeilen(), JETZT)}
        self.assertEqual(koepfe[sprint.KAPITEL_AKTUELL]["titel"], "Sprint 21 (aktuell)")
        self.assertEqual(koepfe[sprint.KAPITEL_NAECHSTER]["titel"], "Sprint 22 (nächster)")
        self.assertEqual(koepfe[sprint.KAPITEL_AKTUELL]["sprint_nr"], 21)
        self.assertEqual(koepfe[sprint.KAPITEL_NAECHSTER]["sprint_nr"], 22)

    def test_aktuell_und_naechster_erscheinen_auch_leer(self):
        """SWR-114/SWR-117: ein fehlendes Kapitel ist von „nicht nachgesehen" nicht
        zu unterscheiden."""
        nur_takt = """## Sprint-Plan

| Aufgabe | Fällig |
|---|---|
| pm/T-0001 | jeder Sprint |
"""
        koepfe = sprint.kapitel_koepfe(_zeilen(nur_takt), JETZT)
        schluessel = [k["schluessel"] for k in koepfe]
        self.assertIn(sprint.KAPITEL_AKTUELL, schluessel)
        self.assertIn(sprint.KAPITEL_NAECHSTER, schluessel)
        leer = [k for k in koepfe if k["schluessel"] == sprint.KAPITEL_AKTUELL][0]
        self.assertEqual(leer["anzahl"], 0)

    def test_spaeter_takt_und_ohne_erscheinen_nur_mit_inhalt(self):
        """Der Wortlaut des Auftrags: „ggf. spätere Sprints, fall aufgaben geplant sind"."""
        nur_aktuell = """## Sprint-Plan

| Aufgabe | Fällig |
|---|---|
| pm/T-0002 | dieser Sprint |
"""
        schluessel = [k["schluessel"] for k in sprint.kapitel_koepfe(_zeilen(nur_aktuell), JETZT)]
        self.assertEqual(schluessel, [sprint.KAPITEL_AKTUELL, sprint.KAPITEL_NAECHSTER])

    def test_leerer_plan_liefert_die_beiden_pflichtkapitel(self):
        self.assertEqual([k["schluessel"] for k in sprint.kapitel_koepfe([], JETZT)],
                         [sprint.KAPITEL_AKTUELL, sprint.KAPITEL_NAECHSTER])


class NutzlastTest(unittest.TestCase):
    """Das Feld steht an der Zeile — die Ansicht rechnet nicht (ADR-P11-001)."""

    def test_jede_zeile_traegt_ihr_kapitel_als_feld(self):
        for z in _zeilen():
            with self.subTest(aufgabe=z["aufgabe"]):
                self.assertIn("kapitel", z)
                self.assertTrue(z["kapitel"])

    def test_die_zeilen_stehen_nur_einmal_in_der_nutzlast(self):
        """⚠ Die Köpfe tragen ZAHLEN, keine Kopien der Zeilen — zwei Kopien desselben
        Bestands laufen auseinander (B033)."""
        for k in sprint.kapitel_koepfe(_zeilen(), JETZT):
            with self.subTest(kapitel=k["schluessel"]):
                self.assertNotIn("zeilen", k)


class EndpunktTest(unittest.TestCase):
    """SWR-154 über den echten Abrufweg `GET /api/sprint` — nicht über den Import."""

    def setUp(self):
        import json
        import shutil
        import subprocess
        import tempfile
        import threading
        from backend import server
        self.root = tempfile.mkdtemp(prefix="kapitel-http-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        repo = os.path.join(self.root, "pm")
        os.makedirs(os.path.join(repo, "management"))
        with open(os.path.join(repo, "management", "sprint-aktuell.md"),
                  "w", encoding="utf-8", newline="\n") as f:
            f.write(PLAN)
        with open(os.path.join(repo, "management", "sprints.jsonl"),
                  "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"nr": JETZT, "kennung": "x",
                                "start": "2026-08-20 10:20"}) + "\n")
        subprocess.run(["git", "-C", repo, "init", "-b", "main"], capture_output=True)
        subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t",
                        "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t",
                        "commit", "-m", "Plan"], capture_output=True)
        server.Api.protokoll = lambda *a, **k: None
        self.srv = server.start(self.root, port=0)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)

    def test_endpunkt_traegt_koepfe_und_das_feld_je_zeile(self):
        import json
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:%d/api/sprint" % self.port) as r:
            daten = json.loads(r.read().decode("utf-8"))
        # ⚠ `.get` mit leerer Vorgabe: gegen einen Altstand ohne Kapitel steht hier
        # eine Aussage („[] statt fuenf Kapitel") und kein KeyError (L-2026-08-16h R3).
        self.assertEqual([k["schluessel"] for k in daten.get("kapitel", [])],
                         list(sprint.KAPITEL_REIHENFOLGE),
                         "der Endpunkt liefert keine Kapitel")
        self.assertEqual(daten.get("kapitel", [{}])[0].get("titel"), "Sprint 21 (aktuell)")
        for z in daten["zeilen"]:
            self.assertIn(z.get("kapitel"), sprint.KAPITEL_REIHENFOLGE,
                          "Planzeile ohne Kapitelfeld: " + z.get("aufgabe", "?"))


if __name__ == "__main__":
    unittest.main()
