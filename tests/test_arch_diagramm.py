"""Unit-Verifikation Architekturbild-Generator (P3/T-0015)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import arch_diagramm  # noqa: E402

QUELLE = {
    "schichten": [
        {"name": "Oben", "komponenten": [{"id": "a", "name": "Komponente A"},
                                         {"id": "b", "name": "Komponente B"}]},
        {"name": "Unten", "komponenten": [{"id": "c", "name": "Komponente C"}]},
    ],
    "beziehungen": [{"von": "a", "nach": "c", "label": "nutzt"},
                    {"von": "b", "nach": "c"}],
}


class ArchDiagrammTest(unittest.TestCase):
    def test_svg_enthaelt_komponenten_und_pfeile(self):
        """Alle Komponenten als Boxen, alle Beziehungen als Pfeile, Label gerendert.
        Verifiziert: SWR-045."""
        svg = arch_diagramm.generiere(QUELLE)
        for name in ("Komponente A", "Komponente B", "Komponente C", "Oben", "Unten", "nutzt"):
            self.assertIn(name, svg)
        self.assertEqual(svg.count("<line "), 2)
        self.assertEqual(svg.count("<rect x="), 3)

    def test_deterministisch_und_drift_erkennbar(self):
        """Gleiche Quelle -> identisches SVG; geänderte Quelle ändert das Bild
        (Grundlage des --check-Gates). Verifiziert: SWR-045."""
        self.assertEqual(arch_diagramm.generiere(QUELLE), arch_diagramm.generiere(QUELLE))
        geaendert = {"schichten": QUELLE["schichten"], "beziehungen": QUELLE["beziehungen"][:1]}
        self.assertNotEqual(arch_diagramm.generiere(QUELLE), arch_diagramm.generiere(geaendert))

    def test_unbekannte_komponente_wird_abgelehnt(self):
        """Beziehung auf nicht deklarierte Komponente -> klarer Fehler. Verifiziert: SWR-045."""
        kaputt = {"schichten": QUELLE["schichten"],
                  "beziehungen": [{"von": "a", "nach": "gibtsnicht"}]}
        with self.assertRaises(ValueError):
            arch_diagramm.generiere(kaputt)

    def test_eingecheckte_quelle_konsistent_zum_bild(self):
        """Die reale komponenten.yaml erzeugt exakt das eingecheckte architektur.svg
        (kein Drift). Verifiziert: SWR-045."""
        svg = arch_diagramm.generiere(arch_diagramm.lade(arch_diagramm.QUELLE))
        self.assertEqual(svg, open(arch_diagramm.ZIEL, encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main()
