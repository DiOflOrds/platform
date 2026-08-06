"""Unit-Verifikation Orchestrator-MVP (T-0005): Auswahl, Routing, Statusfortschreibung.
Ausführung von der platform-Wurzel: python -m unittest discover tests
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from orchestrator import tick as orch  # noqa: E402

REGISTRY = {
    "PL": {"besetzung": "ki", "status": "active", "provider_chain": ["claude"], "model_tier": "strong",
           "script_tasks": ["board-hygiene"],
           "aufgaben_typen": {"dr-qualifizierung": {"chain": ["claude"], "tier": "strong", "gate_relevant": True}}},
    "CM": {"besetzung": "ki", "status": "active", "provider_chain": ["claude"], "model_tier": "standard",
           "script_tasks": ["baseline-manifest"],
           "aufgaben_typen": {"cm-strategie": {"chain": ["claude"], "tier": "standard"}}},
    "DEV": {"besetzung": "ki", "status": "planned", "provider_chain": ["copilot", "claude"]},
    "MENSCH": {"besetzung": "mensch", "status": "active"},
}


def ticket(tid, status="open", rolle="cm", prio="hoch", bb="", typ=""):
    t = {"id": tid, "titel": f"Titel {tid}", "typ": "task", "prozess": "sup8", "rolle": rolle,
         "sprint": "1", "status": status, "prio": prio, "erstellt": "2026-08-06",
         "_datei": f"{tid}.md", "_body": "Body"}
    if bb:
        t["blocked_by"] = bb
    if typ:
        t["aufgaben_typ"] = typ
    return t


class AuswahlTest(unittest.TestCase):
    def test_waehlt_hoechste_prio(self):
        ts = [ticket("T-0002", prio="mittel"), ticket("T-0001", prio="kritisch")]
        self.assertEqual(orch.waehle_ticket(ts, REGISTRY)["id"], "T-0001")

    def test_ignoriert_nicht_open(self):
        ts = [ticket("T-0001", status="done"), ticket("T-0002", status="in_review")]
        self.assertIsNone(orch.waehle_ticket(ts, REGISTRY))

    def test_ignoriert_blockierte(self):
        ts = [ticket("T-0001", status="open", bb="[T-0002]"), ticket("T-0002", status="in_progress")]
        self.assertIsNone(orch.waehle_ticket(ts, REGISTRY))

    def test_blocker_done_gibt_frei(self):
        ts = [ticket("T-0001", bb="[T-0002]"), ticket("T-0002", status="done")]
        self.assertEqual(orch.waehle_ticket(ts, REGISTRY)["id"], "T-0001")

    def test_ignoriert_inaktive_und_mensch_rollen(self):
        ts = [ticket("T-0001", rolle="dev"), ticket("T-0002", rolle="mensch")]
        self.assertIsNone(orch.waehle_ticket(ts, REGISTRY))

    def test_nur_ticket_filter(self):
        ts = [ticket("T-0001", prio="kritisch"), ticket("T-0002")]
        self.assertEqual(orch.waehle_ticket(ts, REGISTRY, nur_ticket="T-0002")["id"], "T-0002")


class RoutingTest(unittest.TestCase):
    def test_script_route(self):
        route, typ, _ = orch.aufloese_route(ticket("T-0001", typ="baseline-manifest"), REGISTRY["CM"])
        self.assertEqual((route, typ), ("script", "baseline-manifest"))

    def test_aufgaben_typ_kette(self):
        route, kette, stufe = orch.aufloese_route(ticket("T-0001", typ="cm-strategie"), REGISTRY["CM"])
        self.assertEqual((route, kette, stufe), ("llm", ["claude"], "standard"))

    def test_default_kette(self):
        route, kette, stufe = orch.aufloese_route(ticket("T-0001"), REGISTRY["CM"])
        self.assertEqual((route, kette, stufe), ("llm", ["claude"], "standard"))

    def test_gate_relevanter_typ(self):
        route, kette, stufe = orch.aufloese_route(
            ticket("T-0001", rolle="pl", typ="dr-qualifizierung"), REGISTRY["PL"])
        self.assertEqual(stufe, "strong")


class StatusTest(unittest.TestCase):
    def test_setze_status_und_board(self):
        with tempfile.TemporaryDirectory() as repo:
            os.makedirs(os.path.join(repo, "tickets"))
            open(os.path.join(repo, "tickets", "T-0001.md"), "w", encoding="utf-8").write(
                "---\nid: T-0001\ntitel: \"X\"\ntyp: task\nprozess: sup8\nrolle: cm\n"
                "sprint: 1\nstatus: open\nprio: hoch\nblocked_by: []\nerstellt: 2026-08-06\n---\n\nBody.\n")
            orch.setze_status(repo, "T-0001", "in_review", {"reviewer": "pl"}, notiz="Notiz.")
            text = open(os.path.join(repo, "tickets", "T-0001.md"), encoding="utf-8").read()
            self.assertIn("status: in_review", text)
            self.assertIn("reviewer: pl", text)
            self.assertIn("Notiz.", text)
            self.assertTrue(os.path.exists(os.path.join(repo, "BOARD.md")))

    def test_setze_status_invalide_wirft(self):
        with tempfile.TemporaryDirectory() as repo:
            os.makedirs(os.path.join(repo, "tickets"))
            open(os.path.join(repo, "tickets", "T-0001.md"), "w", encoding="utf-8").write(
                "---\nid: T-0001\ntitel: \"X\"\ntyp: task\nprozess: sup8\nrolle: cm\n"
                "sprint: 1\nstatus: open\nprio: hoch\nblocked_by: []\nerstellt: 2026-08-06\n---\n\nBody.\n")
            with self.assertRaises(RuntimeError):
                orch.setze_status(repo, "T-0001", "in_review")  # reviewer fehlt -> invalide


class SlugTest(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(orch.slug("CM-Strategie v1 erstellen!"), "cm-strategie-v1-erstellen")


class ArbeitskopieTest(unittest.TestCase):
    """T-0014: Precondition gegen das Einsammeln unbeteiligter Änderungen."""

    def _git(self, repo, *args):
        import subprocess
        return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)

    def setUp(self):
        import shutil
        if shutil.which("git") is None:
            self.skipTest("git nicht verfügbar")
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        self._git(self.repo, "init")
        self._git(self.repo, "config", "user.email", "test@test")
        self._git(self.repo, "config", "user.name", "Test")
        open(os.path.join(self.repo, "a.txt"), "w").write("a")
        self._git(self.repo, "add", "-A")
        self._git(self.repo, "commit", "-m", "init")

    def tearDown(self):
        if hasattr(self, "tmp"):
            self.tmp.cleanup()

    def test_sauber(self):
        self.assertTrue(orch.arbeitskopie_sauber(self.repo))

    def test_unsauber(self):
        open(os.path.join(self.repo, "b.txt"), "w").write("b")
        self.assertFalse(orch.arbeitskopie_sauber(self.repo))

    def test_ausnahme_praefix(self):
        d = os.path.join(self.repo, "management", "runs", "session-austausch")
        os.makedirs(d)
        open(os.path.join(d, "T-0010-antwort.md"), "w").write("x")
        self.assertTrue(orch.arbeitskopie_sauber(self.repo, "management/runs/session-austausch/"))
        self.assertFalse(orch.arbeitskopie_sauber(self.repo))

    def test_auftrag_enthaelt_repo_hinweis(self):
        text = orch.baue_auftrag(ticket("T-0010"), "process")
        self.assertIn("OHNE 'process/'", text)


if __name__ == "__main__":
    unittest.main()
