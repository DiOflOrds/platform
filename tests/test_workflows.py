# -*- coding: utf-8 -*-
"""Tests workflows.py (SWR-187, platform/T-0044): Schema, Ketten-Integrität,
Takt-Abdeckung als PAAR, Rollen-Filter, WP-Auflösung meldet statt erfindet."""
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import workflows  # noqa: E402

TAKT_TICKET = """---
id: {tid}
titel: "Takt: {titel}"
typ: task
prozess: man3
rolle: pl
sprint: 0
status: open
prio: mittel
blocked_by: []
takt: je-session
repo: p96
reviewer: qm
geändert: 2026-08-21
erstellt: 2026-08-21
---

## Ziel

x
"""

WF = """workflows:
  - id: WF-P96-A
    name: Gedeckter Takt
    takt: je-session
    geplant_von: pl
    ticket: T-0001
    arch_review: "2026-08-21"
    cm_verankert: "ja"
    schritte:
      - rolle: script
        werkzeug: tool.py
        aktion: laden
        input: extern
        output: docs/plan.md
      - rolle: mail-red
        aktion: verdichten
        input: docs/plan.md
        output: unbekanntes-artefakt
  - id: WF-P96-B
    name: Kaputter Schritt
    takt: je-session
    geplant_von: pl
    ticket: ""
    schritte:
      - rolle: dev
        aktion: bauen
        input: x
        output: ""
"""

CM = """# CM
```yaml work-products
- pfad: docs/plan.md
  name: Plan
  eigentuemer: pl
```
"""


class TestWorkflows(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        p = os.path.join(self.root, "projects", "p96")
        os.makedirs(os.path.join(p, "tickets"))
        for tid, titel in (("T-0001", "gedeckt"), ("T-0002", "UNGEDECKT")):
            with io.open(os.path.join(p, "tickets", tid + ".md"), "w", encoding="utf-8") as f:
                f.write(TAKT_TICKET.format(tid=tid, titel=titel))
        os.makedirs(os.path.join(p, "docs"))
        io.open(os.path.join(p, "docs", "workflows.yaml"), "w", encoding="utf-8").write(WF)
        io.open(os.path.join(p, "docs", "cm-plan.md"), "w", encoding="utf-8").write(CM)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_takt_abdeckung_als_paar(self):
        """SWR-187: gedeckter Takt besteht UND ungedeckter wird gemeldet — die
        Grundmenge sind die Takt-Tickets, nicht die Workflow-Datei (SWR-128)."""
        d = workflows.einheit(self.root, "p96")
        self.assertTrue(d["datei"])
        unabgedeckt = [t["id"] for t in d["unabgedeckte_takte"]]
        self.assertEqual(unabgedeckt, ["T-0002"])

    def test_ketten_integritaet_und_wp_aufloesung(self):
        d = workflows.einheit(self.root, "p96")
        a = {w["id"]: w for w in d["workflows"]}
        self.assertEqual(a["WF-P96-A"]["befunde"], [])
        s1, s2 = a["WF-P96-A"]["schritte"]
        self.assertTrue(s1["output_ist_wp"])    # docs/plan.md steht im CM-Plan
        self.assertFalse(s2["output_ist_wp"])   # gemeldet, nicht erfunden
        self.assertIn("Schritt 1: Feld 'output' fehlt", a["WF-P96-B"]["befunde"])

    def test_rollen_filter(self):
        d = workflows.fuer_rolle(self.root, "mail-red")
        self.assertEqual([w["id"] for w in d["workflows"]], ["WF-P96-A"])
        d = workflows.fuer_rolle(self.root, "qm")
        self.assertEqual(d["workflows"], [])

    def test_fehlende_datei_meldet_takte(self):
        p = os.path.join(self.root, "projects", "p95")
        os.makedirs(os.path.join(p, "tickets"))
        with io.open(os.path.join(p, "tickets", "T-0001.md"), "w", encoding="utf-8") as f:
            f.write(TAKT_TICKET.format(tid="T-0001", titel="x").replace("repo: p96", "repo: p95"))
        d = workflows.einheit(self.root, "p95")
        self.assertFalse(d["datei"])
        self.assertEqual(len(d["unabgedeckte_takte"]), 1)
        self.assertIn("keine Daten", d["hinweis"])


if __name__ == "__main__":
    unittest.main()
