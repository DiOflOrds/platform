"""Unit-Verifikation board.py v1 (T-0007). Ausführung: python -m unittest discover platform/tests
bzw. von der Repo-Wurzel: python -m unittest tests.test_board
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import board  # noqa: E402

GUT = """---
id: {tid}
titel: "Testticket"
typ: task
prozess: sup8
rolle: cm
sprint: 1
status: {status}
prio: hoch
blocked_by: {bb}
erstellt: 2026-08-06
{extra}---

Body.
"""


def schreibe(repo, tid, status="open", bb="[]", extra=""):
    os.makedirs(os.path.join(repo, "tickets"), exist_ok=True)
    with open(os.path.join(repo, "tickets", f"{tid}.md"), "w", encoding="utf-8") as f:
        f.write(GUT.format(tid=tid, status=status, bb=bb, extra=extra))


class TestBoard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def probleme(self):
        tickets, probleme = board.lade_tickets(self.repo)
        return probleme + board.validiere_alle(tickets, self.repo, git_pruefen=False)

    def test_gutfall(self):
        schreibe(self.repo, "T-0001")
        self.assertEqual(self.probleme(), [])

    def test_pflichtfeld_fehlt(self):
        schreibe(self.repo, "T-0001")
        pfad = os.path.join(self.repo, "tickets", "T-0001.md")
        text = open(pfad, encoding="utf-8").read().replace("prio: hoch\n", "")
        open(pfad, "w", encoding="utf-8").write(text)
        self.assertTrue(any("prio" in p for p in self.probleme()))

    def test_ungueltiger_status(self):
        schreibe(self.repo, "T-0001", status="fertig")
        self.assertTrue(any("ungültiger status" in p for p in self.probleme()))

    def test_id_dateiname_mismatch(self):
        schreibe(self.repo, "T-0001")
        os.rename(os.path.join(self.repo, "tickets", "T-0001.md"),
                  os.path.join(self.repo, "tickets", "T-0002.md"))
        self.assertTrue(any("passt nicht zum Dateinamen" in p for p in self.probleme()))

    def test_blocked_by_unbekannt(self):
        schreibe(self.repo, "T-0001", bb="[T-9999]")
        self.assertTrue(any("unbekanntes Ticket" in p for p in self.probleme()))

    def test_blocked_by_selbstverweis(self):
        schreibe(self.repo, "T-0001", bb="[T-0001]")
        self.assertTrue(any("sich selbst" in p for p in self.probleme()))

    def test_blocked_ohne_blocker(self):
        schreibe(self.repo, "T-0001", status="blocked")
        self.assertTrue(any("blocked erfordert" in p for p in self.probleme()))

    def test_in_review_ohne_reviewer(self):
        schreibe(self.repo, "T-0001", status="in_review")
        self.assertTrue(any("erfordert Feld reviewer" in p for p in self.probleme()))

    def test_in_review_reviewer_ist_autor(self):
        schreibe(self.repo, "T-0001", status="in_review", extra="reviewer: cm\n")
        self.assertTrue(any("nicht der Autor" in p for p in self.probleme()))

    def test_in_review_mit_reviewer_ok(self):
        schreibe(self.repo, "T-0001", status="in_review", extra="reviewer: pl\n")
        self.assertEqual(self.probleme(), [])

    def test_crlf_toleranz(self):
        schreibe(self.repo, "T-0001")
        pfad = os.path.join(self.repo, "tickets", "T-0001.md")
        inhalt = open(pfad, encoding="utf-8").read().replace("\n", "\r\n")
        open(pfad, "w", encoding="utf-8", newline="").write(inhalt)
        self.assertEqual(self.probleme(), [])

    def test_uebergangsmatrix(self):
        self.assertIn("in_review", board.UEBERGAENGE["in_progress"])
        self.assertNotIn("done", board.UEBERGAENGE["open"])

    def test_mensch_tickets_ohne_uebergangspruefung(self):
        # Validierung mit git_pruefen=True darf für rolle=mensch nicht an
        # status_in_head scheitern (Gates dürfen z.B. open -> done springen).
        schreibe(self.repo, "T-0001")
        pfad = os.path.join(self.repo, "tickets", "T-0001.md")
        text = open(pfad, encoding="utf-8").read().replace("rolle: cm", "rolle: mensch")
        open(pfad, "w", encoding="utf-8").write(text)
        tickets, _ = board.lade_tickets(self.repo)
        # kein Git-Repo im tmp-Verzeichnis: bei mensch wird der Check übersprungen
        self.assertEqual(board.validiere_alle(tickets, self.repo, git_pruefen=True), [])

    def test_board_deterministisch(self):
        schreibe(self.repo, "T-0001", status="open")
        schreibe(self.repo, "T-0002", status="done")
        tickets, _ = board.lade_tickets(self.repo)
        b1 = board.generiere_board(tickets, stand="2026-08-06")
        b2 = board.generiere_board(tickets, stand="2026-08-06")
        self.assertEqual(b1, b2)
        self.assertIn("## open (1)", b1)
        self.assertIn("## done (1)", b1)

    def test_prio_sortierung(self):
        schreibe(self.repo, "T-0001")
        schreibe(self.repo, "T-0002")
        pfad = os.path.join(self.repo, "tickets", "T-0002.md")
        text = open(pfad, encoding="utf-8").read().replace("prio: hoch", "prio: kritisch")
        open(pfad, "w", encoding="utf-8").write(text)
        tickets, _ = board.lade_tickets(self.repo)
        b = board.generiere_board(tickets, stand="2026-08-06")
        self.assertLess(b.index("T-0002"), b.index("T-0001"))

    def test_offene_blocker(self):
        schreibe(self.repo, "T-0001", status="done")
        schreibe(self.repo, "T-0002", bb="[T-0001]")
        schreibe(self.repo, "T-0003", bb="[T-0002]")
        tickets, _ = board.lade_tickets(self.repo)
        nach_id = {t["id"]: t for t in tickets}
        self.assertEqual(board.offene_blocker(nach_id["T-0002"], nach_id), [])
        self.assertEqual(board.offene_blocker(nach_id["T-0003"], nach_id), ["T-0002"])

    def test_main_check_modus(self):
        schreibe(self.repo, "T-0001")
        rc = board.main([self.repo, "--check", "--no-git"])
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(os.path.join(self.repo, "BOARD.md")))

    def test_main_schreibt_board(self):
        schreibe(self.repo, "T-0001")
        rc = board.main([self.repo, "--no-git"])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(os.path.join(self.repo, "BOARD.md")))

    def test_main_fehlerfall(self):
        schreibe(self.repo, "T-0001", status="quatsch")
        rc = board.main([self.repo, "--no-git"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
