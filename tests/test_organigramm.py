# -*- coding: utf-8 -*-
"""Tests organigramm.py (SWR-178 Resolver-Umfeld, Orga-Rework Kap. 8): Sammeln,
Ziele, --check-Gate."""
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import organigramm  # noqa: E402


def _schreib(pfad, text):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with io.open(pfad, "w", encoding="utf-8") as f:
        f.write(text)


class TestOrganigramm(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        # Mini-Organisation: ein Team-Repo (pm) + ein Projekt unter projects/
        os.makedirs(os.path.join(self.root, "pm", "tickets"))
        os.makedirs(os.path.join(self.root, "pm", ".git"))
        os.makedirs(os.path.join(self.root, "projects", "p99", "tickets"))
        _schreib(os.path.join(self.root, "projects", "p99", "steckbrief.yaml"),
                 'beschreibung: "Testprojekt"\nstatus: aktiv\n')
        _schreib(os.path.join(self.root, "process", "teams", "registry.yaml"),
                 "teams:\n  pm:\n    name: PM-Team\n    typ: pm\n    profil: wiederkehrend\n"
                 "    repo: pm\n    status: aktiv\n    rollen: [PL, QM]\n    datenklasse: intern\n")
        _schreib(os.path.join(self.root, "process", "roles", "registry.yaml"),
                 "roles:\n  PL:\n    name: Projektleiter\n  QM:\n    name: Qualitätsmanager\n")
        _schreib(os.path.join(self.root, "process", "roles", "besetzungen.yaml"),
                 "besetzungen:\n  PL@pm:\n    rolle: PL\n    einheit: pm\n    motor: cowork\n"
                 "    takt: sprint\n    status: aktiv\n  PL@p99:\n    rolle: PL\n    einheit: p99\n"
                 "    motor: ollama\n    modell: gemma3:27b\n    takt: schnell\n    status: aktiv\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_sammle_instanzen_und_unbesetzte(self):
        m = organigramm.sammle(self.root)
        namen = [e["einheit"] for e in m["einheiten"]]
        self.assertEqual(namen, ["p99", "pm"])  # deterministisch sortiert
        pm = m["einheiten"][1]
        instanzen = {r["instanz"]: r for r in pm["rollen"]}
        self.assertEqual(instanzen["PL@pm"]["quelle"], "besetzung")
        # QM steht in der Team-Registry, hat keine Besetzung -> sichtbar als unbesetzt
        self.assertEqual(instanzen["QM@pm"]["status"], "unbesetzt")
        p99 = m["einheiten"][0]
        self.assertEqual(p99["rollen"][0]["modell"], "gemma3:27b")

    def test_ziele_und_check_gate(self):
        # Erst schreiben, dann muss --check gruen sein; nach Registry-Aenderung rot.
        self.assertEqual(organigramm.main(["--repos", self.root]), 0)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "pm", "ORGANIGRAMM.md")))
        self.assertTrue(os.path.isfile(os.path.join(self.root, "projects", "p99", "ORGANIGRAMM.md")))
        self.assertTrue(os.path.isfile(os.path.join(
            self.root, "platform", "backend", "static", "organigramm.json")))
        self.assertEqual(organigramm.main(["--repos", self.root, "--check"]), 0)
        _schreib(os.path.join(self.root, "process", "roles", "besetzungen.yaml"),
                 "besetzungen:\n  QM@pm:\n    rolle: QM\n    einheit: pm\n    motor: cowork\n"
                 "    takt: sprint\n    status: aktiv\n")
        self.assertEqual(organigramm.main(["--repos", self.root, "--check"]), 1)

    def test_gesamt_zeigt_nur_laufende(self):
        _schreib(os.path.join(self.root, "projects", "p99", "steckbrief.yaml"),
                 'beschreibung: "Testprojekt"\nstatus: abgeschlossen\n')
        m = organigramm.sammle(self.root)
        gesamt = organigramm.md_gesamt(m)
        # Abgeschlossene Einheit: nicht im Mermaid-Bild, aber in der Tabelle
        self.assertNotIn('p99["p99', gesamt)
        self.assertIn("| p99 |", gesamt)


if __name__ == "__main__":
    unittest.main()
