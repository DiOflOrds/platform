"""Tests Matrix-Generator (T-0026). Bezug: CR T-0026 (Prozess-Tooling, kein SWR)."""
import os
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import trace_matrix  # noqa: E402

TESTDATEI = textwrap.dedent('''
    """Moduldocstring nennt SWR-101."""
    import unittest

    class A(unittest.TestCase):
        """Klassendocstring nennt SWR-102."""
        def test_methode_gewinnt(self):
            """Verifiziert: SWR-103."""
        def test_erbt_klasse(self):
            pass
    class B(unittest.TestCase):
        def test_erbt_modul(self):
            pass
    class C(unittest.TestCase):
        """Kein SWR hier, Modul auch nicht relevant."""
        def test_ohne_bezug(self):
            """Nur Beschreibung, kein Bezug."""
''')

ANFORDERUNGEN = textwrap.dedent('''
    | ID | Requirement | Trace | Verification | Prio | Status |
    |---|---|---|---|---|---|
    | SWR-101 | A | STK-001 | Unit tests | high | reviewed |
    | SWR-104 | B | STK-001 | Unit tests | high | reviewed |
    | SWR-105 | C | STK-001 | CI workflow run | high | reviewed |
    | SWR-106 | D | STK-001 | API tests | medium | draft |
    | SWR-107 | E | STK-001 | UI acceptance checklist | medium | reviewed |
''')


class TestScannen(unittest.TestCase):
    """Docstring-Auflösung: Methode vor Klasse vor Modul. Bezug: CR T-0026."""

    def _scan(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "test_x.py"), "w", encoding="utf-8").write(TESTDATEI)
            return trace_matrix.tests_scannen(d)

    def test_methode_vor_klasse_vor_modul(self):
        """Methoden-ID gewinnt; ohne Methoden-ID erbt der Test Klasse bzw. Modul."""
        abdeckung, _ = self._scan()
        self.assertIn("test_x.py::A::test_methode_gewinnt", abdeckung["SWR-103"])
        self.assertIn("test_x.py::A::test_erbt_klasse", abdeckung["SWR-102"])
        self.assertIn("test_x.py::B::test_erbt_modul", abdeckung["SWR-101"])

    def test_ohne_bezug_wird_gemeldet(self):
        """Ein Test ohne SWR in Methode/Klasse erbt das Modul; nur ohne alles gilt er als bezuglos."""
        abdeckung, ohne = self._scan()
        self.assertIn("test_x.py::C::test_ohne_bezug", abdeckung["SWR-101"])
        self.assertEqual(ohne, [])


class TestMatrix(unittest.TestCase):
    """Lücken-Regel und CI-Ausnahme. Bezug: CR T-0026."""

    def test_luecken_und_ci_ausnahme(self):
        """reviewed ohne Test = Lücke; CI-Workflow-Verifikation und draft sind keine Lücke."""
        with tempfile.TemporaryDirectory() as d:
            pfad = os.path.join(d, "swr.md")
            open(pfad, "w", encoding="utf-8").write(ANFORDERUNGEN)
            swrs = trace_matrix.swr_lesen(pfad)
        text, luecken = trace_matrix.generiere(
            swrs, {"SWR-101": ["test_x.py::A::test_a"]}, [])
        self.assertEqual(luecken, ["SWR-104"])
        self.assertIn("über CI-Workflow verifiziert", text)
        self.assertIn("offen (Status draft)", text)
        self.assertIn("manuelle Abnahme dokumentiert", text)  # Checklisten-Nachweis (T-0034)

    def test_unbekannte_swr_in_tests_ist_luecke(self):
        """Eine in Tests referenzierte, im Anforderungsdokument fehlende SWR wird gemeldet."""
        with tempfile.TemporaryDirectory() as d:
            pfad = os.path.join(d, "swr.md")
            open(pfad, "w", encoding="utf-8").write(ANFORDERUNGEN)
            swrs = trace_matrix.swr_lesen(pfad)
        _, luecken = trace_matrix.generiere(
            swrs, {"SWR-101": ["t"], "SWR-999": ["t2"], "SWR-104": ["t3"]}, [])
        self.assertEqual(luecken, ["SWR-999"])


class TestIdMuster(unittest.TestCase):
    """T-0048: generalisiertes ID-Muster für Produkt-Repos (Default unverändert)."""

    def test_produkt_muster_wird_erkannt(self):
        """Mit --id-muster-Regex werden Produkt-IDs (SWR-Dxx) in Tests und SWR-Datei erkannt."""
        import re
        muster = re.compile(r"SWR-D\d{2}")
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "test_p.py"), "w", encoding="utf-8").write(
                'class T:\n    def test_a(self):\n        """X. Verifiziert: SWR-D01."""\n')
            abdeckung, ohne = trace_matrix.tests_scannen(d, muster)
            pfad = os.path.join(d, "swr.md")
            open(pfad, "w", encoding="utf-8").write(
                "| ID | Requirement | Trace | Verification | Prio | Status |\n"
                "|---|---|---|---|---|---|\n"
                "| SWR-D01 | A | STK-D01 | Unit tests | high | reviewed |\n")
            swrs = trace_matrix.swr_lesen(pfad, muster)
        self.assertEqual(list(abdeckung), ["SWR-D01"])
        self.assertEqual(ohne, [])
        _, luecken = trace_matrix.generiere(swrs, abdeckung, ohne)
        self.assertEqual(luecken, [])

    def test_default_verhalten_unveraendert(self):
        """Ohne Muster-Angabe gilt weiterhin SWR-\\d{3} (Rückwärtskompatibilität)."""
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "test_p.py"), "w", encoding="utf-8").write(
                'class T:\n    def test_a(self):\n        """X. Verifiziert: SWR-D01."""\n')
            abdeckung, ohne = trace_matrix.tests_scannen(d)
        self.assertEqual(abdeckung, {})
        self.assertEqual(ohne, ["test_p.py::T::test_a"])


if __name__ == "__main__":
    unittest.main()
