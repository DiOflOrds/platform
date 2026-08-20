# -*- coding: utf-8 -*-
"""SWR-156 (platform/T-0025, Brief `team-mail/N-0004` des Auftraggebers): war es zu
lange still?

> *„in der konfiguration ist tägliches routine eigerichtet, jedoch wurde das nicht
> ausgeführt. die letzten 2 tage war server down, aber im aktuellen sprint müsste das
> aufgefallen sein!?"*

⚠⚠ **Die tragende Zusicherung dieser Datei ist die Gegenprobe an einem HERGESTELLTEN
Register.** Der echte Bestand ist heute unauffällig (56 Min = 0,93 Takte), und eine
Prüfung, die nur gegen ihn läuft, wäre grün, ohne etwas zu prüfen (`L-2026-08-17ai`).
Jeder Test hier **baut** deshalb sein Register: einen mit 3 612 Minuten (der echte
Ausfall vom 17.–20.08.) und einen mit 42 Minuten (die echte Pause vor Sprint 20).

⚠ Und die Fälle 3 und 4 sind nicht erfunden, sondern **im eigenen Bestand gemessen**:
eine **negative** Pause (Sprint 17 startet 16:49, Sprint 16 endet 17:10) und **14**
Sprints ohne `ende` vor dem Stichtag.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import session  # noqa: E402
import preflight  # noqa: E402
import sprint_register  # noqa: E402


def register(*zeilen):
    """Ein Wurzelverzeichnis mit genau diesem Sprintregister — hergestellt, nicht erhofft."""
    root = tempfile.mkdtemp(prefix="pause-")
    verz = os.path.join(root, "pm", "management")
    os.makedirs(verz)
    with open(os.path.join(verz, "sprints.jsonl"), "w", encoding="utf-8") as f:
        for z in zeilen:
            f.write(json.dumps(z, ensure_ascii=False) + "\n")
    return root


def lauf(nr, start, ende=None, takt=60):
    z = [{"nr": nr, "kennung": "k%s" % nr, "start": start, "takt_min": takt}]
    if ende:
        z.append({"kennung": "k%s" % nr, "ende": ende})
    return z


class GegenprobeTest(unittest.TestCase):
    """DoD 4 von T-0025: gegen 60,2 h **rot**, gegen 42 Min **grün**."""

    def setUp(self):
        self._roots = []

    def tearDown(self):
        for r in self._roots:
            shutil.rmtree(r, ignore_errors=True)

    def _root(self, *zeilen):
        r = register(*zeilen)
        self._roots.append(r)
        return r

    def test_der_echte_ausfall_ist_ein_befund(self):
        """3 612 Min = 60,2x Takt — genau die Pause zwischen Sprint 20 und 21."""
        root = self._root(*lauf(20, "2026-08-17 21:59", "2026-08-17 22:18"),
                          *lauf(21, "2026-08-20 10:30"))
        p = session.pause_seit_letztem_lauf(root)
        self.assertEqual(p["minuten"], 3612)
        self.assertEqual(p["vielfaches"], 60.2)
        self.assertTrue(p["befund"])
        self.assertIn("22:18", p["hinweis"])

    def test_die_echte_normale_pause_ist_kein_befund(self):
        """42 Min = 0,7x Takt — die Pause vor Sprint 20. Grün, und zwar begründet."""
        root = self._root(*lauf(19, "2026-08-17 20:20", "2026-08-17 21:17"),
                          *lauf(20, "2026-08-17 21:59"))
        p = session.pause_seit_letztem_lauf(root)
        self.assertEqual(p["minuten"], 42)
        self.assertEqual(p["vielfaches"], 0.7)
        self.assertFalse(p["befund"])
        self.assertEqual(p["hinweis"], "")

    def test_die_schwelle_liegt_bei_zwei_takten_und_nirgends_sonst(self):
        """⚠ Die Grenze ist geprüft und nicht behauptet: 120 Min grün, 121 rot.

        Zwei Takte sind **nicht** an den Bestand angepasst, sondern **dieselbe** Zahl,
        die die Kachel „Letzte Session" seit SWR-102 benutzt (`STILLE_TAKTE`). Am
        Bestand gemessen liegt die größte unauffällige Pause bei 56 Minuten und die
        einzige auffällige bei 3 612 — jede Schwelle dazwischen träfe die Messung, und
        eine an den Bestand angepasste Zahl wäre an sechs Werten gefittet.
        """
        for minuten, erwartet in ((119, False), (120, False), (121, True)):
            std, rest = divmod(minuten, 60)
            root = self._root(*lauf(1, "2026-08-17 00:00", "2026-08-17 01:00"),
                              *lauf(2, "2026-08-17 %02d:%02d" % (1 + std, rest)))
            p = session.pause_seit_letztem_lauf(root)
            self.assertEqual(p["minuten"], minuten)
            self.assertIs(p["befund"], erwartet, minuten)


class GemesseneSonderfaelleTest(unittest.TestCase):
    """Fälle, die es im eigenen Register wirklich gibt — keine erfundenen."""

    def setUp(self):
        self._roots = []

    def tearDown(self):
        for r in self._roots:
            shutil.rmtree(r, ignore_errors=True)

    def _root(self, *zeilen):
        r = register(*zeilen)
        self._roots.append(r)
        return r

    def test_negative_pause_wird_gemeldet_und_nicht_auf_null_geklemmt(self):
        """⚠⚠ Sprint 17 startet 16:49, Sprint 16 endet 17:10 — 21 Minuten Überlappung.

        Der Fall steht so im Register. Er belegt, dass die Zeitstempel aus den Uhren der
        jeweils schreibenden Läufe stammen und mindestens einmal uneinig waren. Auf 0 zu
        klemmen wäre die bequeme Glättung und löschte den einzigen Beleg.
        """
        root = self._root(*lauf(16, "2026-08-17 15:41", "2026-08-17 17:10"),
                          *lauf(17, "2026-08-17 16:49"))
        p = session.pause_seit_letztem_lauf(root)
        self.assertEqual(p["minuten"], -21)
        self.assertTrue(p["ueberlappung"])
        self.assertFalse(p["befund"], "Überlappung ist ein EIGENER Fall, keine Stille")
        self.assertIn("16:49", p["hinweis"])

    def test_sprints_ohne_ende_werden_genannt_statt_erfunden(self):
        """SWR-136: vor dem Stichtag hat kein Lauf ein `ende` — 14 Stück, gezählt."""
        zeilen = []
        for nr in range(1, 4):
            zeilen += lauf(nr, "2026-08-17 0%d:00" % nr)
        zeilen += lauf(4, "2026-08-17 05:00", "2026-08-17 06:00")
        zeilen += lauf(5, "2026-08-17 06:30")
        p = session.pause_seit_letztem_lauf(self._root(*zeilen))
        self.assertEqual(p["ohne_ende"], [1, 2, 3])
        self.assertEqual(p["letzter_nr"], 4)
        self.assertEqual(p["minuten"], 30)

    def test_ohne_vorgaenger_wird_nicht_berechnet_sondern_gesagt(self):
        """Der allererste Lauf hat keine Pause. `None` mit Grund, niemals 0."""
        p = session.pause_seit_letztem_lauf(self._root(*lauf(1, "2026-08-17 00:23")))
        self.assertIsNone(p["minuten"])
        self.assertIn("kein vorangegangener Sprint", p["unberechenbar"])
        self.assertFalse(p["befund"])

    def test_leeres_register_ist_kein_befund_sondern_kein_bestand(self):
        p = session.pause_seit_letztem_lauf(self._root())
        self.assertIsNone(p["minuten"])
        self.assertTrue(p["unberechenbar"])
        self.assertFalse(p["befund"])

    def test_ohne_laufenden_sprint_zaehlt_die_gegenwart(self):
        """Läuft keiner, ist der Bezug `jetzt` — die Stille dauert ja an."""
        root = self._root(*lauf(1, "2026-08-17 00:00", "2026-08-17 01:00"))
        p = session.pause_seit_letztem_lauf(root, jetzt=datetime(2026, 8, 17, 4, 0))
        self.assertEqual(p["minuten"], 180)
        self.assertTrue(p["befund"])
        self.assertIn("kein Sprint läuft", p["bezug"])


class EineZeitrechnungTest(unittest.TestCase):
    """⚠ DoD 3: `stille()` wird IMPORTIERT und nicht abgeschrieben (B033)."""

    def test_der_takt_kommt_aus_dem_register_und_nicht_aus_dem_quelltext(self):
        """⚠⚠ Der stille Befund dieses Tickets: `session.TAKT_MINUTEN` stand auf **30**,
        während das Register seit dem 17.08. **60** führt. Zwei Werte für denselben
        Sachverhalt — die Kachel meldete Stille nach einer statt nach zwei Stunden."""
        root = register(*lauf(1, "2026-08-17 00:00", "2026-08-17 01:00", takt=60))
        try:
            self.assertEqual(session.takt(root), 60)
            self.assertNotEqual(session.takt(root), session.TAKT_MINUTEN,
                                "der Rückfallwert ist NICHT die Quelle")
            self.assertEqual(session.pause_seit_letztem_lauf(root)["takt_min"], 60)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_kein_zweiter_schwellenvergleich_im_modul(self):
        """Die Entscheidung fällt genau einmal — in `stille()`.

        Gezählt wird der Aufruf, nicht das Wort: eine zweite Stelle, die `takt_min *
        takte` selbst vergleicht, wäre die zweite Antwort auf dieselbe Frage.
        """
        with open(session.__file__.replace(".pyc", ".py"), encoding="utf-8") as f:
            quelle = f.read()
        rumpf = quelle.split("def pause_seit_letztem_lauf", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("stille(", rumpf)
        for verboten in ("takt_min * ", "takt_minuten * ", "* takte"):
            self.assertNotIn(verboten, rumpf, verboten)

    def test_die_kachel_und_die_pause_benutzen_dieselbe_schwelle(self):
        """Kachel und Preflight dürfen über dieselbe Stille nichts Verschiedenes sagen."""
        root = register(*lauf(1, "2026-08-17 00:00", "2026-08-17 01:00"),
                        *lauf(2, "2026-08-17 04:00"))
        try:
            p = session.pause_seit_letztem_lauf(root)
            veraltet, _ = session.stille("2026-08-17 01:00",
                                         datetime(2026, 8, 17, 4, 0),
                                         takt_minuten=p["takt_min"])
            self.assertIs(p["befund"], veraltet)
        finally:
            shutil.rmtree(root, ignore_errors=True)


class PreflightAusgabeTest(unittest.TestCase):
    """⚠ SWR-114/117/155: die Zeile erscheint AUCH im guten Fall.

    Der Befund von T-0025 ist nicht, dass die Pause falsch berechnet wurde — sie wurde
    **gar nicht genannt**. Eine Prüfung, die nur bei schlechtem Ergebnis spricht, ist von
    einer nicht gelaufenen nicht zu unterscheiden.
    """

    def _ausgabe(self, wert):
        alt = preflight.pause_zum_vorlauf
        preflight.pause_zum_vorlauf = lambda root: wert
        puffer = io.StringIO()
        try:
            with redirect_stdout(puffer):
                preflight.preflight(".", skip_tests=True)
        finally:
            preflight.pause_zum_vorlauf = alt
        return puffer.getvalue()

    def test_unauffaellige_pause_wird_trotzdem_genannt(self):
        text = self._ausgabe({"letztes_ende": "2026-08-20 11:16", "letzter_nr": 21,
                              "bezug": "Start von Sprint 22",
                              "bezug_zeit": "2026-08-20 12:12", "minuten": 56,
                              "takt_min": 60, "takte": 2, "vielfaches": 0.93,
                              "befund": False, "hinweis": "", "unberechenbar": "",
                              "ueberlappung": False, "ohne_ende": []})
        self.assertIn("Pause seit dem Ende von Sprint 21", text)
        self.assertIn("0.93x Takt", text)
        self.assertNotIn("Pause seit dem Ende von Sprint 21 (2026-08-20 11:16) bis "
                         "Start von Sprint 22: 56 Min = 0.93x Takt (60 Min) — BEFUND",
                         text)

    def _ausfall(self):
        return self._ausgabe({"letztes_ende": "2026-08-17 22:18", "letzter_nr": 20,
                              "bezug": "Start von Sprint 21",
                              "bezug_zeit": "2026-08-20 10:30", "minuten": 3612,
                              "takt_min": 60, "takte": 2, "vielfaches": 60.2,
                              "befund": True, "hinweis": "seit 22:18 keine Session",
                              "unberechenbar": "", "ueberlappung": False,
                              "ohne_ende": []})

    def test_der_ausfall_wird_gemeldet_mit_zahl_und_zeitraum(self):
        """⚠ **Diese Zusicherung ist GESCHÄRFT, nicht gelöscht** (SWR-166, Sprint 25).

        Sie hielt bis Sprint 24 fest, dass der Ausfall das Wort `BEFUND` trägt. Das Wort
        war nie der Gegenstand — der Gegenstand ist, dass der Ausfall **mit Zahl und
        Zeitraum genannt** wird, statt wie in Sprint 21 gar nicht vorzukommen. Genau das
        stand dem Auftraggeber im Brief `team-mail/N-0004` zu.

        Seit SWR-166 heißt die Marke `FORTGESCHRIEBEN`: eine bereits vergangene Pause ist
        von keinem Aufrufer zu verkürzen, und sie hat als blockierender Befund 83
        Push-Läufe gestoppt. Gemessen wird deshalb weiter der **Inhalt**, und die Marke
        ausdrücklich mit.
        """
        text = self._ausfall()
        self.assertIn("FORTGESCHRIEBEN", text)
        self.assertIn("3612 Min", text)
        self.assertIn("60.2x Takt", text)
        self.assertIn("2026-08-17 22:18", text)
        self.assertIn("seit 22:18 keine Session", text)

    def test_der_ausfall_blockiert_nicht_und_bleibt_trotzdem_gezaehlt(self):
        """⚠⚠ Die zweite Hälfte des Paares (`L-2026-08-20by`): dass er nicht mehr
        blockiert, darf nicht heißen, dass er verschwindet.

        Der Ausfall taucht in der Schlusszeile als **fortgeschriebener** Befund auf —
        eine Zahl, die niemand mehr übersieht — und **nicht** unter den blockierenden.
        Ohne diese Hälfte wäre die Änderung von SWR-166 ein stilles Wegräumen.
        """
        text = self._ausfall()
        schluss = [z for z in text.splitlines() if z.startswith("PREFLIGHT:")][0]
        self.assertRegex(schluss, r"\((?!0 )\d+ fortgeschrieben\)",
                         "die Pause zählt nicht als fortgeschrieben: %s" % schluss)
        # Gegenprobe: dieselbe Zeile ohne Ausfall trägt die Pause NICHT im Zähler.
        ohne = self._ausgabe({"letztes_ende": "2026-08-20 11:16", "letzter_nr": 21,
                              "bezug": "Start von Sprint 22",
                              "bezug_zeit": "2026-08-20 12:12", "minuten": 56,
                              "takt_min": 60, "takte": 2, "vielfaches": 0.93,
                              "befund": False, "hinweis": "", "unberechenbar": "",
                              "ueberlappung": False, "ohne_ende": []})
        schluss_ohne = [z for z in ohne.splitlines()
                        if z.startswith("PREFLIGHT:")][0]
        self.assertIn("(0 fortgeschrieben)", schluss_ohne)

    def test_nicht_pruefbar_sagt_es_und_behauptet_keine_null(self):
        text = self._ausgabe(None)
        self.assertIn("nicht prüfbar", text)


if __name__ == "__main__":
    unittest.main()
