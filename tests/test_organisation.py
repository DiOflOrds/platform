# -*- coding: utf-8 -*-
"""Tests organisation.py (SWR-177/178/179, platform/T-0028/T-0037): Detail-Lektüre,
Text-Edit auf besetzungen.yaml (Kommentar-Erhalt), F20-Durchsetzung, Entfernen,
Core-Team-Expansion und Materialisierung."""
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import organisation  # noqa: E402

BESETZUNGEN = """# Kopf-Kommentar bleibt erhalten
besetzungen:
  # --- Abschnitt A ---
  PL@p99:
    rolle: PL
    einheit: p99
    motor: cowork
    takt: sprint         # Zeilen-Kommentar
    status: aktiv
  # --- Abschnitt B ---
  QM@p99:
    rolle: QM
    einheit: p99
    motor: cowork
    takt: sprint
    status: aktiv
"""


def _schreib(pfad, text):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with io.open(pfad, "w", encoding="utf-8") as f:
        f.write(text)


class TestOrganisation(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "projects", "p99", "tickets"))
        _schreib(os.path.join(self.root, "projects", "p99", "steckbrief.yaml"),
                 'beschreibung: "Testprojekt"\nstatus: aktiv\n')
        _schreib(os.path.join(self.root, "process", "roles", "besetzungen.yaml"), BESETZUNGEN)
        _schreib(os.path.join(self.root, "process", "roles", "registry.yaml"),
                 "roles:\n  PL:\n    name: Projektleiter\n  QM:\n    name: Qualitätsmanager\n")
        _schreib(os.path.join(self.root, "process", "roles", "pl.md"), "# Rollenkarte PL v2\n")
        _schreib(os.path.join(self.root, "projects", "p99", "roles", "pl.md"), "# PL@p99\n")
        _schreib(os.path.join(self.root, "projects", "p99", "docs", "historie.md"), "# Historie p99\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _text(self):
        with io.open(os.path.join(self.root, "process", "roles", "besetzungen.yaml"),
                     encoding="utf-8") as f:
            return f.read()

    def test_detail_liefert_alle_ebenen(self):
        d = organisation.detail(self.root, "PL@p99")
        self.assertEqual(d["besetzung"]["motor"], "cowork")
        self.assertIn("Rollenkarte PL v2", d["bauplan"])
        self.assertIn("PL@p99", d["projektteil"])
        self.assertIn("Historie", d["historie"])
        with self.assertRaises(organisation.OrgFehler):
            organisation.detail(self.root, "GIBTSNICHT@p99")

    def test_setzen_erhaelt_kommentare_und_andere_bloecke(self):
        organisation.setzen(self.root, "PL@p99",
                            {"motor": "ollama", "modell": "gemma3:27b", "takt": "schnell"},
                            verbuchen=False)
        t = self._text()
        self.assertIn("# Kopf-Kommentar bleibt erhalten", t)
        self.assertIn("# --- Abschnitt B ---", t)
        self.assertIn("    motor: ollama", t)
        self.assertIn("    modell: gemma3:27b", t)  # neues Feld eingefügt
        # QM-Block unangetastet
        self.assertIn("  QM@p99:", t)
        self.assertEqual(t.count("motor: cowork"), 1)

    def test_setzen_validiert(self):
        with self.assertRaises(organisation.OrgFehler) as k:
            organisation.setzen(self.root, "PL@p99", {"motor": "zauberei"}, verbuchen=False)
        self.assertEqual(k.exception.code, 400)

    def test_anlegen_und_f20(self):
        organisation.anlegen(self.root, "DEV@p99", {"motor": "cowork", "takt": "sprint"},
                             verbuchen=False)
        self.assertIn("  DEV@p99:", self._text())
        # F20 (pm/D012): zweite Besetzung derselben Rolle in derselben Einheit -> 409
        with self.assertRaises(organisation.OrgFehler) as k:
            organisation.anlegen(self.root, "PL@p99", {"motor": "cowork"}, verbuchen=False)
        self.assertEqual(k.exception.code, 409)
        with self.assertRaises(organisation.OrgFehler):
            organisation.anlegen(self.root, "DEV@gibtsnicht", {"motor": "cowork"},
                                 verbuchen=False)

    def test_entfernen_loescht_nur_den_block(self):
        organisation.entfernen(self.root, "PL@p99", verbuchen=False)
        t = self._text()
        self.assertNotIn("  PL@p99:", t)
        self.assertIn("  QM@p99:", t)
        self.assertIn("# --- Abschnitt B ---", t)  # Abschnitts-Kommentar überlebt

    # ---------- Projektmodell (Konzept 04): implizites Core Team ----------

    def _mit_core(self):
        """Fixture um einen core_team-Block ergänzen (DEV+PL als Core-Rollen)."""
        pfad = os.path.join(self.root, "process", "roles", "besetzungen.yaml")
        with io.open(pfad, encoding="utf-8") as f:
            alt = f.read()
        _schreib(pfad, "core_team:\n  rollen: [PL, DEV]\n  motor: cowork\n  takt: sprint\n"
                       "  status: aktiv\n" + alt)

    def test_core_expansion_und_explizit_gewinnt(self):
        self._mit_core()
        import organigramm
        eff = organigramm.effektive_besetzungen(self.root)
        # DEV@p99 implizit aus dem Core Team
        self.assertEqual(eff["DEV@p99"]["quelle"], "core")
        self.assertEqual(eff["DEV@p99"]["motor"], "cowork")
        # PL@p99 steht explizit (Fixture) und gewinnt gegen die Expansion
        self.assertEqual(eff["PL@p99"]["quelle"], "besetzung")

    def test_detail_und_setzen_materialisiert_core_instanz(self):
        self._mit_core()
        d = organisation.detail(self.root, "DEV@p99")  # implizit, aber Detail-fähig
        self.assertEqual(d["besetzung"]["quelle"], "core")
        erg = organisation.setzen(self.root, "DEV@p99", {"motor": "ollama",
                                                         "modell": "gemma3:27b"},
                                  verbuchen=False)
        self.assertTrue(erg.get("materialisiert"))
        t = self._text()
        self.assertIn("  DEV@p99:", t)          # als expliziter Block materialisiert
        self.assertIn("    modell: gemma3:27b", t)
        import organigramm
        self.assertEqual(organigramm.effektive_besetzungen(self.root)["DEV@p99"]["quelle"],
                         "besetzung")

    def test_core_instanz_nicht_entfernbar_und_nicht_anlegbar(self):
        self._mit_core()
        with self.assertRaises(organisation.OrgFehler) as k:
            organisation.entfernen(self.root, "DEV@p99", verbuchen=False)
        self.assertEqual(k.exception.code, 400)   # pausieren statt löschen
        with self.assertRaises(organisation.OrgFehler) as k:
            organisation.anlegen(self.root, "DEV@p99", {"motor": "cowork"}, verbuchen=False)
        self.assertEqual(k.exception.code, 409)   # implizit besetzt -> setzen, nicht anlegen


if __name__ == "__main__":
    unittest.main()
