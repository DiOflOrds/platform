# -*- coding: utf-8 -*-
"""Tests workproducts.py (SWR-181/182, platform/T-0039): Block-Parsing, Lücken-Paar,
keine-Daten-Fall."""
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import workproducts  # noqa: E402

CM_PLAN = """# CM-Plan Test

## Work Products (SWR-181)

```yaml work-products
- pfad: docs/projektplan.md
  name: Projektplan
  eigentuemer: pl
  pruefstatus: qm-review offen
- pfad: docs/fehlt-noch.md
  name: Noch nicht angelegt
  eigentuemer: rm
```
"""


def _schreib(pfad, text):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with io.open(pfad, "w", encoding="utf-8") as f:
        f.write(text)


class TestWorkproducts(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "projects", "p99", "tickets"))
        _schreib(os.path.join(self.root, "projects", "p99", "docs", "cm-plan.md"), CM_PLAN)
        _schreib(os.path.join(self.root, "projects", "p99", "docs", "projektplan.md"), "# Plan\n")
        # undeklariert: existiert, steht aber nicht im Block (SWR-182, zweite Richtung)
        _schreib(os.path.join(self.root, "projects", "p99", "docs", "historie.md"), "# H\n")
        os.makedirs(os.path.join(self.root, "projects", "p98", "tickets"))  # ohne CM-Plan

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_luecken_paar(self):
        """SWR-182: deklariert-aber-fehlt UND vorhanden-aber-undeklariert sind BEIDE Befunde."""
        d = workproducts.einheit(self.root, "p99")
        self.assertTrue(d["cm_plan"])
        je_pfad = {w["pfad"]: w for w in d["work_products"]}
        self.assertTrue(je_pfad["docs/projektplan.md"]["vorhanden"])
        self.assertFalse(je_pfad["docs/fehlt-noch.md"]["vorhanden"])
        self.assertEqual(je_pfad["docs/fehlt-noch.md"]["stand"], "—")
        self.assertIn("docs/historie.md", d["undeklariert"])
        # der CM-Plan selbst ist undeklariert, wenn er sich nicht selbst führt — sichtbar
        self.assertIn("docs/cm-plan.md", d["undeklariert"])

    def test_keine_daten_statt_leerer_gesunder_liste(self):
        """SWR-182/096: fehlender CM-Plan ist 'keine Daten', keine leere Erfolgsmeldung."""
        d = workproducts.einheit(self.root, "p98")
        self.assertFalse(d["cm_plan"])
        self.assertIn("keine Daten", d["hinweis"])
        self.assertEqual(d["work_products"], [])

    def test_alle_fuehrt_beide(self):
        a = workproducts.alle(self.root)
        namen = [e["einheit"] for e in a["einheiten"]]
        self.assertEqual(namen, ["p98", "p99"])


if __name__ == "__main__":
    unittest.main()
