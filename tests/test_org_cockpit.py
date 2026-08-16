# -*- coding: utf-8 -*-
"""P9-Tests SWR-066/068/070: Steckbrief, Status-Fallback, Gruppen, projects-Discovery.
Hermetisch (gb-02): Temp-Root, eigene Git-Repos, kein Netz."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import aggregation  # noqa: E402

TICKET = ("---\nid: T-0001\ntitel: \"x\"\ntyp: task\nprozess: man3\nrolle: pl\n"
          "sprint: 0\nstatus: open\nprio: hoch\nblocked_by: []\nrepo: %s\n"
          "geändert: 2026-08-16\nerstellt: 2026-08-16\n---\n\n## Ziel\n\nx\n")


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t"]
                          + list(args), capture_output=True, text=True)


class OrgCockpitTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="orgcockpit-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _repo(self, name, steckbrief=None, team_typ=None, tag=None, nested=False):
        basis = os.path.join(self.root, "projects", name) if nested else os.path.join(self.root, name)
        os.makedirs(os.path.join(basis, "tickets"))
        with open(os.path.join(basis, "tickets", "T-0001.md"), "w", encoding="utf-8") as f:
            f.write(TICKET % name)
        if steckbrief:
            with open(os.path.join(basis, "steckbrief.yaml"), "w", encoding="utf-8") as f:
                f.write(steckbrief)
        if team_typ:
            with open(os.path.join(basis, "team.yaml"), "w", encoding="utf-8") as f:
                f.write(f"typ: {team_typ}\n")
        wurzel = os.path.join(self.root, "projects") if nested else basis
        if not os.path.isdir(os.path.join(wurzel, ".git")):
            _git(wurzel, "init", "-b", "main")
        _git(wurzel, "add", "-A")
        _git(wurzel, "commit", "-m", "init")
        if tag:
            _git(wurzel, "tag", tag)
        return basis

    def test_steckbrief_und_gruppen(self):
        """SWR-066/068: Beschreibung/Status aus Steckbrief; typ-basierte Gruppen; Aufgabenliste."""
        self._repo("alpha", steckbrief='beschreibung: "Testprojekt Alpha"\nstatus: aktiv\n')
        self._repo("crew", team_typ="pm")
        c = aggregation.cockpit(self.root, "alpha")
        self.assertEqual(c["beschreibung"], "Testprojekt Alpha")
        self.assertEqual(c["gruppe"], "aktiv")
        self.assertEqual(c["aufgaben_offen"], 1)
        self.assertEqual(c["aufgaben"][0]["id"], "T-0001")
        self.assertEqual(aggregation.cockpit(self.root, "crew")["gruppe"], "festes-team")

    def test_status_fallback_ueber_baseline_tag(self):
        """SWR-066: <repo>-v1.0-Tag ohne Steckbrief-Status -> abgeschlossen."""
        self._repo("beta", tag="beta-v1.0")
        c = aggregation.cockpit(self.root, "beta")
        self.assertEqual(c["status"], "abgeschlossen")
        self.assertEqual(c["gruppe"], "abgeschlossen")

    def test_projects_sammelrepo_discovery(self):
        """SWR-070: Projektordner in projects/ werden entdeckt und aufgeloest."""
        self._repo("gamma")
        self._repo("p10", nested=True, steckbrief='beschreibung: "Nested-Projekt"\n')
        namen = aggregation.projekte(self.root)
        self.assertIn("gamma", namen)
        self.assertIn("p10", namen)
        pfad = aggregation.projekt_pfad(self.root, "p10")
        self.assertTrue(pfad.endswith(os.path.join("projects", "p10")))
        c = aggregation.cockpit(self.root, "p10")
        self.assertEqual(c["beschreibung"], "Nested-Projekt")
        self.assertEqual(c["aufgaben_offen"], 1)


if __name__ == "__main__":
    unittest.main()
