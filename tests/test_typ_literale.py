# -*- coding: utf-8 -*-
"""Tests T-0041: typ-Literal `plattform` gilt, `aspice` bleibt lesend toleriert.
Das PAAR ist Pflicht (L-2026-08-20by): neu funktioniert UND alt bricht nicht."""
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from backend import aggregation  # noqa: E402
import organigramm  # noqa: E402


def _repo(root, name, typ):
    p = os.path.join(root, name)
    os.makedirs(os.path.join(p, "tickets"))
    os.makedirs(os.path.join(p, ".git"))
    with io.open(os.path.join(p, "team.yaml"), "w", encoding="utf-8") as f:
        f.write(f'name: "{name}"\ntyp: {typ}\nprofil: "entwicklung"\n')
    with io.open(os.path.join(p, "steckbrief.yaml"), "w", encoding="utf-8") as f:
        f.write('beschreibung: "x"\nstatus: aktiv\n')
    return p


class TestTypLiterale(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_plattform_ist_festes_team(self):
        p = _repo(self.root, "neu", "plattform")
        e = aggregation.einstufung(self.root, "neu", pfad=p, tag_text="")
        self.assertEqual(e["gruppe"], "festes-team")

    def test_aspice_bleibt_toleriert(self):
        """Alt-Literal bricht nicht — die bestehenden Fixtures (test_org_cockpit,
        test_anzeigename_einheit) sind der große Toleranz-Beleg; hier das Minimalpaar."""
        p = _repo(self.root, "alt", "aspice")
        e = aggregation.einstufung(self.root, "alt", pfad=p, tag_text="")
        self.assertEqual(e["gruppe"], "festes-team")

    def test_core_team_expandiert_bei_plattform(self):
        _repo(self.root, "platform", "plattform")
        os.makedirs(os.path.join(self.root, "process", "roles"))
        os.makedirs(os.path.join(self.root, "process", "teams"))
        with io.open(os.path.join(self.root, "process", "teams", "registry.yaml"),
                     "w", encoding="utf-8") as f:
            f.write("teams:\n  aspice:\n    repo: platform\n    typ: plattform\n"
                    "    status: aktiv\n")
        with io.open(os.path.join(self.root, "process", "roles", "besetzungen.yaml"),
                     "w", encoding="utf-8") as f:
            f.write("core_team:\n  rollen: [PL, DEV]\n  motor: cowork\n  takt: sprint\n"
                    "  status: aktiv\nbesetzungen: {}\n")
        eff = organigramm.effektive_besetzungen(self.root)
        self.assertIn("PL@platform", eff)  # plattform ist ein Projekt -> Core Team gilt


if __name__ == "__main__":
    unittest.main()
