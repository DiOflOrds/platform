# -*- coding: utf-8 -*-
"""Tests kommunikation.py (SWR-183/184, platform/T-0040): Mischung/Sortierung,
Umfangsgrenze, Einheiten-Filter, PIN-Gate benennt Zurückgehaltenes."""
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import kommunikation  # noqa: E402

BRIEFE = {
    "pm": {"briefe": [
        {"id": "N-0001", "von": "E. John", "zeit": "2026-08-20T10:00:00+00:00",
         "status": "beantwortet", "nachricht": "Frage A", "antwort": "Antwort A"},
        {"id": "N-0002", "von": "E. John", "zeit": "2026-08-21T09:00:00+00:00",
         "status": "offen", "nachricht": "Frage B", "antwort": ""}]},
    "team-mail": {"briefe": [
        {"id": "N-0001", "von": "E. John", "zeit": "2026-08-19T08:00:00+00:00",
         "status": "beantwortet", "nachricht": "SENSIBLER INHALT", "antwort": "x"}]},
}
HISTORIE = {"historie": [
    {"projekt": "pm", "id": "T-0009", "titel": "DR X", "status": "done",
     "entscheidung": "**Entscheidung (D000, via Inbox, 2026-08-20 22:01)** ..."}]}


def _briefe(root, projekt):
    return BRIEFE.get(projekt, {"briefe": []})


class TestKommunikation(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "process", "teams"))
        with io.open(os.path.join(self.root, "process", "teams", "registry.yaml"),
                     "w", encoding="utf-8") as f:
            f.write("teams:\n  team-mail:\n    repo: team-mail\n    datenklasse: sensibel\n"
                    "  pm:\n    repo: pm\n    datenklasse: intern\n")
        self.patches = [
            mock.patch.object(kommunikation.aggregation, "projekte",
                              lambda root: ["pm", "team-mail"]),
            mock.patch.object(kommunikation.briefkasten, "liste", _briefe),
            mock.patch.object(kommunikation.inbox, "historie", lambda root: HISTORIE),
            mock.patch.object(kommunikation.inbox, "liste", lambda root: {"inbox": []}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_neueste_zuerst_und_arten_gemischt(self):
        d = kommunikation.zeitleiste(self.root, pin_ok=True)
        zeiten = [e["zeit"] for e in d["eintraege"] if e["zeit"]]
        self.assertEqual(zeiten, sorted(zeiten, reverse=True))
        arten = {e["art"] for e in d["eintraege"]}
        self.assertIn("brief", arten)
        self.assertIn("dr-entschieden", arten)
        self.assertEqual(d["gesperrt"], [])

    def test_pin_gate_benennt_zurueckgehaltenes(self):
        """SWR-184: blockiert -> sensible Einheit benannt, Eintraege abwesend (nicht leer)."""
        d = kommunikation.zeitleiste(self.root, pin_ok=False)
        self.assertEqual(d["gesperrt"], ["team-mail"])
        self.assertFalse(any(e["einheit"] == "team-mail" for e in d["eintraege"]))
        self.assertFalse(any("SENSIBEL" in (e.get("titel") or "") for e in d["eintraege"]))
        # pin_ok=True: dieselbe Einheit erscheint (Paar-Prüfung, L-2026-08-20by)
        d2 = kommunikation.zeitleiste(self.root, pin_ok=True)
        self.assertTrue(any(e["einheit"] == "team-mail" for e in d2["eintraege"]))
        self.assertEqual(d2["gesperrt"], [])

    def test_limit_und_filter(self):
        d = kommunikation.zeitleiste(self.root, pin_ok=True, limit=2)
        self.assertEqual(len(d["eintraege"]), 2)
        self.assertGreaterEqual(d["gesamt"], 3)
        d = kommunikation.zeitleiste(self.root, pin_ok=True, einheit="pm")
        self.assertTrue(all(e["einheit"] == "pm" for e in d["eintraege"]))
        with self.assertRaises(ValueError):
            kommunikation.zeitleiste(self.root, pin_ok=True, einheit="gibtsnicht")

    def test_gate_ist_die_gemeinsame_funktion(self):
        """SWR-184: kein zweites Gate — das Modul kennt KEINE eigene PIN-Prüfung;
        die Entscheidung (pin_ok) kommt vom Aufrufer, der schreibschutz_pruefen nutzt."""
        import inspect
        quelle = inspect.getsource(kommunikation)
        self.assertNotIn("MC_PIN", quelle)
        self.assertNotIn("hmac", quelle)


if __name__ == "__main__":
    unittest.main()
