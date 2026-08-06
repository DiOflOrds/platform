"""Unit-Verifikation Produktkatalog v0 (T-0056). Bezug: Masterplan 5.5, Skript-Route."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import catalog  # noqa: E402

EINTRAG = {"name": "datakonv", "version": "1.0.0", "released": "2026-08-06",
           "interface": "CLI", "repo": "produkt-datakonv", "project": "p0",
           "capabilities": "CSV<->JSON", "limitations": "flat only", "doc": "README.md"}


class KatalogTest(unittest.TestCase):
    def test_neuer_eintrag_erzeugt_yaml_und_seite(self):
        """Registrierung erzeugt products.yaml und Detailseite. Bezug: T-0056."""
        with tempfile.TemporaryDirectory() as d:
            yaml_pfad, seite = catalog.registriere(d, dict(EINTRAG))
            import yaml as y
            daten = y.safe_load(open(yaml_pfad, encoding="utf-8"))
            self.assertEqual(daten["products"]["datakonv"]["version"], "1.0.0")
            self.assertIn("CSV<->JSON", open(seite, encoding="utf-8").read())

    def test_update_ersetzt_version(self):
        """Erneute Registrierung aktualisiert den Eintrag statt zu duplizieren. Bezug: T-0056."""
        with tempfile.TemporaryDirectory() as d:
            catalog.registriere(d, dict(EINTRAG))
            neu = dict(EINTRAG, version="1.1.0")
            yaml_pfad, _ = catalog.registriere(d, neu)
            import yaml as y
            daten = y.safe_load(open(yaml_pfad, encoding="utf-8"))
            self.assertEqual(len(daten["products"]), 1)
            self.assertEqual(daten["products"]["datakonv"]["version"], "1.1.0")


if __name__ == "__main__":
    unittest.main()
