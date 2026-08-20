# -*- coding: utf-8 -*-
"""Tests aktivitaeten.py (SWR-186, platform/T-0043): done/offen/Review-Aufteilung,
Run-Registry-Zuordnung, Einheiten-Filter, Ausschluss dokumentiert."""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import aktivitaeten  # noqa: E402

TICKET = """---
id: {tid}
titel: "{titel}"
typ: task
prozess: man3
rolle: {rolle}
sprint: 0
status: {status}
prio: mittel
blocked_by: []
repo: {repo}
reviewer: {reviewer}
geändert: 2026-08-21
erstellt: 2026-08-21
---

## Ziel

x
"""


def _t(root, repo, tid, rolle, status, reviewer="qm", titel="T"):
    p = os.path.join(root, repo, "tickets", tid + ".md")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(TICKET.format(tid=tid, titel=titel, rolle=rolle, status=status,
                              repo=repo, reviewer=reviewer))


class TestAktivitaeten(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        for repo in ("p97", "p98"):
            os.makedirs(os.path.join(self.root, "projects", repo, "tickets"))
        base = os.path.join(self.root, "projects")
        _t(base, "p97", "T-0001", "pl", "done")
        _t(base, "p97", "T-0002", "pl", "open")
        _t(base, "p97", "T-0003", "dev", "open", reviewer="pl")  # PL reviewt fremdes
        _t(base, "p98", "T-0001", "pl", "in_progress")
        runs = os.path.join(base, "p97", "management", "runs")
        os.makedirs(runs)
        with io.open(os.path.join(runs, "run-registry.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"rolle": "pl", "ticket": "T-0001", "provider": "session",
                                "status": "ok", "artefakte": ["a.md"], "zeit": "2026-08-21T10:00:00",
                                "dauer_s": 5, "kosten_eur": 0}) + "\n")
            f.write(json.dumps({"rolle": "dev", "ticket": "T-0003", "provider": "ollama",
                                "status": "fehler", "artefakte": [], "zeit": "2026-08-21T11:00:00"}) + "\n")
            f.write("KAPUTTE ZEILE\n")  # reißt die Sicht nicht um

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_aufteilung_und_review(self):
        d = aktivitaeten.fuer_rolle(self.root, "pl")
        self.assertEqual(d["zaehler"]["erledigt"], 1)
        self.assertEqual(d["zaehler"]["offen"], 2)   # p97 open + p98 in_progress
        self.assertEqual(d["zaehler"]["reviews"], 1)  # T-0003 (dev), Reviewer pl
        self.assertEqual(d["reviews"][0]["id"], "T-0003")

    def test_laeufe_der_rolle_und_kaputte_zeile(self):
        d = aktivitaeten.fuer_rolle(self.root, "pl")
        self.assertEqual(d["zaehler"]["laeufe"], 1)   # nur der pl-Lauf, dev nicht, Müll nicht
        self.assertEqual(d["laeufe"][0]["provider"], "session")
        self.assertEqual(d["laeufe"][0]["artefakte"], 1)

    def test_einheiten_filter_und_fehler(self):
        d = aktivitaeten.fuer_rolle(self.root, "pl", einheit="p98")
        self.assertEqual(d["zaehler"]["offen"], 1)
        self.assertEqual(d["zaehler"]["erledigt"], 0)
        with self.assertRaises(ValueError):
            aktivitaeten.fuer_rolle(self.root, "pl", einheit="gibtsnicht")
        with self.assertRaises(ValueError):
            aktivitaeten.fuer_rolle(self.root, "")

    def test_ausschluss_dokumentiert(self):
        d = aktivitaeten.fuer_rolle(self.root, "pl")
        self.assertIn("nicht als Aktivität", d["hinweis_v1"])


if __name__ == "__main__":
    unittest.main()
