# -*- coding: utf-8 -*-
"""Langer Freitext wandert aus der Tabellenzelle (SWR-124, pm/T-0057).

Anlass: Der Auftraggeber hat am 2026-08-17 seine vollständige Rollenbeschreibung in das
Beschreibungsfeld des Pool-Formulars eingefügt — Ergebnis war **eine** Tabellenzeile mit
rund 9.000 Zeichen.

⚠ Zwei der drei Ursachen, die das Ticket nannte, halten der Messung nicht stand:

* „die Beschreibung wird gar nicht geprüft" — doch: `_text_bereinigen`, `|`-Ablehnung
  und `FELD_MAX` laufen alle über sie.
* „die Zeilenumbrüche gingen beim Einfügen verloren" — sie werden **absichtlich** zu
  Leerzeichen zusammengezogen, seit Brief `pm/N-0023` genau darum bat.

Gefehlt hat weder eine Prüfung noch eine Grenze, sondern ein **Zielort**.

Ausführung: python -m unittest discover platform/tests
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import pool  # noqa: E402
from tests.test_pool_kandidat import _repo_bauen  # noqa: E402


LANG = ("Rollenbeschreibung. " * 700).strip()      # ~14.000 Zeichen, wie der Originalfall
KURZ = "Kalender-/Termin-Team"


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wurzel = self.tmp.name
        self.repo = _repo_bauen(self.wurzel)

    def tearDown(self):
        self.tmp.cleanup()

    def pool_text(self):
        return open(os.path.join(self.repo, "management", "projekt-pool.md"),
                    encoding="utf-8").read()

    def zeile(self, name):
        for z in self.pool_text().splitlines():
            if name in z and z.startswith("|"):
                return z
        return ""

    def kandidatendatei(self, datei):
        return os.path.join(self.wurzel, "pm", "management", "kandidaten", datei)


class AuslagerungTest(Basis):
    """Verifiziert: SWR-124."""

    def test_langer_text_landet_in_eigener_datei_und_die_zelle_wird_lesbar(self):
        """⚠ Der Originalfall: 9.000 Zeichen in einer Zelle. Verifiziert: SWR-124."""
        pool.kandidat_anlegen(self.wurzel, "team", "team-lang", LANG,
                              {"Nutzen": "n", "Voraussetzung": "v"})
        zeile = self.zeile("team-lang")
        self.assertLess(len(zeile), 700, "die Tabellenzeile bleibt lesbar")
        self.assertIn("Volltext", zeile)
        datei = self.kandidatendatei("team-lang-kurzbeschreibung.md")
        self.assertTrue(os.path.isfile(datei), "der Volltext hat eine eigene Datei")
        inhalt = open(datei, encoding="utf-8").read()
        self.assertIn(LANG, inhalt, "der Wortlaut ist vollständig erhalten")
        self.assertIn("wie er angekommen ist", inhalt,
                      "die Datei sagt, dass sie nicht rekonstruiert")

    def test_kurzer_kandidat_verhaelt_sich_unveraendert(self):
        """⚠ Die Gegenprobe — ohne sie wäre jede Zeile ein Verweis. Verifiziert: SWR-124."""
        pool.kandidat_anlegen(self.wurzel, "team", "team-kurz", KURZ,
                              {"Nutzen": "n", "Voraussetzung": "v"})
        zeile = self.zeile("team-kurz")
        self.assertIn(KURZ, zeile)
        self.assertNotIn("Volltext", zeile)
        self.assertFalse(os.path.isdir(os.path.join(self.wurzel, "pm", "management",
                                                    "kandidaten")),
                         "ohne langen Text entsteht das Verzeichnis gar nicht")

    def test_die_schwelle_selbst_wird_nicht_ausgelagert(self):
        """Genau `ZELLE_MAX` bleibt in der Zelle — die Grenze ist benannt, nicht gefühlt.

        Verifiziert: SWR-124.
        """
        genau = "x" * pool.ZELLE_MAX
        wert, datei = pool._auslagern(self.wurzel, "t", "Feld", genau)
        self.assertEqual(wert, genau)
        self.assertIsNone(datei)
        wert, datei = pool._auslagern(self.wurzel, "t", "Feld", genau + "x")
        self.assertIsNotNone(datei)

    def test_extraspalte_wird_genauso_ausgelagert(self):
        """Nutzen/Voraussetzung/Quelle sind dieselbe Fläche. Verifiziert: SWR-124."""
        pool.kandidat_anlegen(self.wurzel, "team", "team-nutzen", KURZ,
                              {"Nutzen": LANG, "Voraussetzung": "v"})
        self.assertTrue(os.path.isfile(self.kandidatendatei("team-nutzen-nutzen.md")))
        self.assertIn("Volltext", self.zeile("team-nutzen"))

    def test_zeilenumbrueche_zerbrechen_die_tabelle_nicht(self):
        """Verifiziert: SWR-124."""
        pool.kandidat_anlegen(self.wurzel, "team", "team-umbruch",
                              "Zeile eins\nZeile zwei\n\nZeile drei",
                              {"Nutzen": "n", "Voraussetzung": "v"})
        zeile = self.zeile("team-umbruch")
        self.assertEqual(zeile.count("\n"), 0)
        self.assertIn("Zeile eins Zeile zwei Zeile drei", zeile)

    def test_pipe_wird_weiterhin_abgelehnt(self):
        """Der `|`-Schutz bleibt — Auslagern ersetzt ihn nicht. Verifiziert: SWR-124."""
        with self.assertRaises(pool.PoolFehler):
            pool.kandidat_anlegen(self.wurzel, "team", "team-pipe", "a | b",
                                  {"Nutzen": "n", "Voraussetzung": "v"})

    def test_feld_max_bleibt_unberuehrt(self):
        """ZELLE_MAX und FELD_MAX beantworten zwei Fragen. Verifiziert: SWR-124."""
        self.assertEqual(pool.FELD_MAX, 200_000)
        self.assertLess(pool.ZELLE_MAX, pool.FELD_MAX)


class CommitTest(Basis):
    """Der ausgelagerte Text und die Zeile, die auf ihn zeigt, gehören zusammen.

    Verifiziert: SWR-124.
    """

    def test_volltext_liegt_im_selben_commit_wie_die_zeile(self):
        """Sonst zeigt die Tabelle auf eine Datei, die es in Git nicht gibt.

        Verifiziert: SWR-124.
        """
        pool.kandidat_anlegen(self.wurzel, "team", "team-lang", LANG,
                              {"Nutzen": "n", "Voraussetzung": "v"})
        dateien = subprocess.run(
            ["git", "-C", self.repo, "show", "--name-only", "--format=", "HEAD"],
            capture_output=True, text=True).stdout.split()
        self.assertIn("management/projekt-pool.md", dateien)
        self.assertIn("management/kandidaten/team-lang-kurzbeschreibung.md", dateien)

    def test_gescheiterter_commit_nimmt_den_volltext_mit_zurueck(self):
        """Sonst bliebe der Volltext eines Kandidaten liegen, den es nicht gibt.

        Verifiziert: SWR-124.
        """
        with open(os.path.join(self.repo, ".git", "config"), "w") as f:
            f.write("[core\nkaputt")
        with self.assertRaises(pool.PoolFehler):
            pool.kandidat_anlegen(self.wurzel, "team", "team-lang", LANG,
                                  {"Nutzen": "n", "Voraussetzung": "v"})
        self.assertFalse(os.path.isfile(self.kandidatendatei(
            "team-lang-kurzbeschreibung.md")))
        self.assertNotIn("team-lang", self.pool_text())


if __name__ == "__main__":
    unittest.main()
