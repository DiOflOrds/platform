"""Unit-Verifikation Feedback-Routing v1 (T-0055). Bezug: Skript-Route, Masterplan 5.5."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import feedback_route  # noqa: E402

FEEDBACK = """---
id: {tid}
titel: "{titel}"
typ: feedback
prozess: sup9
rolle: mensch
sprint: 5
status: open
prio: mittel
blocked_by: []
repo: p0
erstellt: 2026-08-06
---

{body}
"""


def repo_mit(*tickets):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "tickets"))
    for tid, titel, body in tickets:
        open(os.path.join(d, "tickets", f"{tid}.md"), "w", encoding="utf-8").write(
            FEEDBACK.format(tid=tid, titel=titel, body=body))
    return d


class RoutingTest(unittest.TestCase):
    def test_wunsch_wird_change_request(self):
        """Wunsch-Feedback wird als change-request geroutet. Bezug: T-0055."""
        repo = repo_mit(("T-0001", "Wunsch: neue Option", "Bitte eine --indent-Option."))
        erg = feedback_route.route(repo)
        self.assertEqual(erg, [("T-0001", "T-0002", "change-request")])
        neu = open(os.path.join(repo, "tickets", "T-0002.md"), encoding="utf-8").read()
        self.assertIn("typ: change-request", neu)
        self.assertIn("rolle: chg", neu)
        self.assertIn("aus Feedback T-0001", neu)

    def test_fehler_wird_problem(self):
        """Fehler-Wortlaut wird als problem (SUP.9) geroutet. Bezug: T-0055."""
        repo = repo_mit(("T-0001", "Absturz bei grosser Datei", "Das Tool liefert falsche Werte."))
        self.assertEqual(feedback_route.route(repo)[0][2], "problem")

    def test_feedback_geht_in_progress_mit_notiz(self):
        """Das Feedback wird auf in_progress gesetzt und traegt die Routing-Notiz. Bezug: T-0055."""
        repo = repo_mit(("T-0001", "Wunsch", "Bitte Option."))
        feedback_route.route(repo)
        fb = open(os.path.join(repo, "tickets", "T-0001.md"), encoding="utf-8").read()
        self.assertIn("status: in_progress", fb)
        self.assertIn("Routing", fb)
        self.assertTrue(os.path.exists(os.path.join(repo, "BOARD.md")))

    def test_dry_run_aendert_nichts(self):
        """--dry-run klassifiziert nur, schreibt nichts. Bezug: T-0055."""
        repo = repo_mit(("T-0001", "Wunsch", "Bitte Option."))
        erg = feedback_route.route(repo, dry_run=True)
        self.assertEqual(erg[0][1], "T-0002")
        self.assertFalse(os.path.exists(os.path.join(repo, "tickets", "T-0002.md")))
        self.assertIn("status: open",
                      open(os.path.join(repo, "tickets", "T-0001.md"), encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main()
