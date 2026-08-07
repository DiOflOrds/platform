"""Unit-Verifikation DR-Benachrichtigung (P1/T-0013)."""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import dr_benachrichtigung  # noqa: E402

DR = """---
id: T-0001
titel: "DR: Testfrage"
typ: decision-request
prozess: man3
rolle: pl
sprint: 1
status: open
prio: hoch
blocked_by: []
repo: p0
optionen: [A, B]
frist: 2026-08-10
erstellt: 2026-08-07
---

Frage?
"""


def _root_mit_dr():
    d = tempfile.mkdtemp()
    repo = os.path.join(d, "p0")
    os.makedirs(os.path.join(repo, "tickets"))
    open(os.path.join(repo, "tickets", "T-0001.md"), "w", encoding="utf-8").write(DR)
    subprocess.run(["git", "-C", repo, "init", "-q"], check=True)
    return d


class BenachrichtigungTest(unittest.TestCase):
    def test_erfolg_setzt_marker_und_verhindert_doppelversand(self):
        """Bei Versanderfolg wird der Marker gesetzt; der nächste Lauf sendet nichts mehr. Verifiziert: SWR-033."""
        root = _root_mit_dr()
        erg = dr_benachrichtigung.lauf(root, sende=lambda b, t: (True, "ok"))
        self.assertEqual(erg, [("p0", "T-0001", "gesendet")])
        text = open(os.path.join(root, "p0", "tickets", "T-0001.md"), encoding="utf-8").read()
        self.assertIn(dr_benachrichtigung.MARKER, text)
        self.assertEqual(dr_benachrichtigung.lauf(root, sende=lambda b, t: (True, "ok")), [])

    def test_fehlschlag_ohne_marker_wird_wiederholt(self):
        """Bei Versandfehler bleibt der DR unmarkiert (Retry beim nächsten Lauf). Verifiziert: SWR-033."""
        root = _root_mit_dr()
        erg = dr_benachrichtigung.lauf(root, sende=lambda b, t: (False, "SMTP fehlt"))
        self.assertEqual(erg[0][2], "SMTP fehlt")
        text = open(os.path.join(root, "p0", "tickets", "T-0001.md"), encoding="utf-8").read()
        self.assertNotIn(dr_benachrichtigung.MARKER, text)
        self.assertEqual(len(dr_benachrichtigung.lauf(root, dry_run=True)), 1)

    def test_mailinhalt_traegt_projekt_und_frist(self):
        """Betreff/Text enthalten Projekt, ID, Titel, Optionen und Frist. Verifiziert: SWR-033."""
        root = _root_mit_dr()
        gesendet = []
        dr_benachrichtigung.lauf(root, sende=lambda b, t: (gesendet.append((b, t)) or (True, "ok")))
        betreff, text = gesendet[0]
        self.assertIn("[p0]", betreff)
        self.assertIn("T-0001", betreff)
        self.assertIn("2026-08-10", text)
        self.assertIn("[A, B]", text)


if __name__ == "__main__":
    unittest.main()
