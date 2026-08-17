"""Arbeitskopie-Befunde des Preflight (SWR-110, platform/T-0010).

Gemessen wird die Arbeitskopie, gepusht wird HEAD. Wo beide in einer Datei
auseinandergehen, die eine Verifikation liest, beschreibt ein grünes Ergebnis
einen Zustand, den kein Repository trägt.
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import preflight  # noqa: E402


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


class _RepoFall(unittest.TestCase):
    """Ein echtes Git-Repo je Test — die Ausnahme wird am Diff entschieden,
    also braucht der Test einen Diff und keine nachgebaute Statuszeile."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo = os.path.join(self.tmp, "r")
        os.makedirs(self.repo)
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.email", "t@test.local")
        _git(self.repo, "config", "user.name", "T")

    def schreibe(self, relpfad, inhalt):
        voll = os.path.join(self.repo, relpfad)
        os.makedirs(os.path.dirname(voll), exist_ok=True)
        with open(voll, "w", encoding="utf-8") as f:
            f.write(inhalt)

    def committe(self, nachricht="c"):
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", nachricht)

    def auswerten(self):
        dirty, _ = preflight.repo_status(self.repo)
        return preflight.arbeitskopie_befunde(self.repo, dirty)


class VerifikationsquelleTest(unittest.TestCase):
    """Welche Dateien liest eine Verifikation? (SWR-110)"""

    def test_anforderungsdokument_ist_quelle(self):
        self.assertTrue(preflight.ist_verifikationsquelle(
            "requirements/software/software-requirements.md"))

    def test_ticketdatei_ist_quelle(self):
        self.assertTrue(preflight.ist_verifikationsquelle("tickets/T-0010.md"))
        self.assertTrue(preflight.ist_verifikationsquelle("projects/p11/tickets/T-0003.md"))

    def test_board_ist_quelle(self):
        """BOARD.md liest der CI-Schritt 'BOARD.md aktuell?' — sie ist der Grund
        für die Stand-Zeilen-Ausnahme und muss deshalb in der Liste stehen."""
        self.assertTrue(preflight.ist_verifikationsquelle("BOARD.md"))

    def test_beliebige_datei_ist_keine_quelle(self):
        self.assertFalse(preflight.ist_verifikationsquelle("README.md"))
        self.assertFalse(preflight.ist_verifikationsquelle("scripts/preflight.py"))
        self.assertFalse(preflight.ist_verifikationsquelle("management/notiz.md"))

    def test_ticketaehnlicher_pfad_ohne_ticketordner_ist_keine_quelle(self):
        """`tickets` muss der ELTERNORDNER sein, nicht irgendwo im Pfad."""
        self.assertFalse(preflight.ist_verifikationsquelle("tickets/alt/entwurf.md"))


class UnverbuchtTest(_RepoFall):
    """Der Fall, der Sprint 6 durchgerutscht ist."""

    def test_unverbuchtes_anforderungsdokument_ist_befund_und_wird_genannt(self):
        self.schreibe("requirements/software/software-requirements.md", "SWR-001\n")
        self.committe()
        self.schreibe("requirements/software/software-requirements.md", "SWR-001\nSWR-002\n")
        unverbucht, alle = self.auswerten()
        self.assertEqual(unverbucht, ["requirements/software/software-requirements.md"])
        self.assertIn("requirements/software/software-requirements.md", alle)

    def test_unverbuchte_ticketdatei_ist_befund(self):
        self.schreibe("tickets/T-0001.md", "---\nid: T-0001\n---\n")
        self.committe()
        self.schreibe("tickets/T-0001.md", "---\nid: T-0001\nstatus: done\n---\n")
        unverbucht, _ = self.auswerten()
        self.assertEqual(unverbucht, ["tickets/T-0001.md"])

    def test_neue_unverbuchte_ticketdatei_ist_befund(self):
        """Auch eine noch nie committete Datei zählt — genau so entsteht ein
        Ticket, das niemand ausser der Arbeitskopie kennt."""
        self.schreibe("README.md", "x\n")
        self.committe()
        self.schreibe("tickets/T-0002.md", "---\nid: T-0002\n---\n")
        unverbucht, _ = self.auswerten()
        self.assertEqual(unverbucht, ["tickets/T-0002.md"])

    def test_fremde_datei_wird_genannt_ist_aber_kein_befund(self):
        self.schreibe("README.md", "alt\n")
        self.committe()
        self.schreibe("README.md", "neu\n")
        unverbucht, alle = self.auswerten()
        self.assertEqual(unverbucht, [])
        self.assertEqual(alle, ["README.md"])

    def test_sauberes_repo_ergibt_nichts(self):
        self.schreibe("README.md", "x\n")
        self.committe()
        unverbucht, alle = self.auswerten()
        self.assertEqual((unverbucht, alle), ([], []))


class StandZeilenAusnahmeTest(_RepoFall):
    """Die Ausnahme und ihre Gegenprobe (DoD 3 und 4 von platform/T-0010)."""

    BOARD_ALT = "# Board\n\nStand: 2026-08-16 · Tickets: 22\n\n## done (21)\n"

    def test_board_nur_stand_zeile_ist_kein_befund_bleibt_aber_sichtbar(self):
        self.schreibe("BOARD.md", self.BOARD_ALT)
        self.committe()
        self.schreibe("BOARD.md", self.BOARD_ALT.replace("2026-08-16", "2026-08-17"))
        unverbucht, alle = self.auswerten()
        self.assertEqual(unverbucht, [])
        self.assertEqual(alle, ["BOARD.md"], "die Zeile darf nicht verschwinden — "
                                             "'sauber' und 'unsauber, aber harmlos' "
                                             "bleiben unterscheidbar")

    def test_board_mit_weiterer_zeile_ist_befund(self):
        """⚠ Gegenprobe. Ohne diesen Test wäre eine Ausnahme nach DATEINAME
        nicht widerlegbar — und liesse jede BOARD.md-Änderung durch."""
        self.schreibe("BOARD.md", self.BOARD_ALT)
        self.committe()
        self.schreibe("BOARD.md", self.BOARD_ALT.replace("2026-08-16", "2026-08-17")
                                                 .replace("## done (21)", "## done (22)"))
        unverbucht, _ = self.auswerten()
        self.assertEqual(unverbucht, ["BOARD.md"])

    def test_board_ohne_stand_aenderung_ist_befund(self):
        self.schreibe("BOARD.md", self.BOARD_ALT)
        self.committe()
        self.schreibe("BOARD.md", self.BOARD_ALT.replace("## done (21)", "## done (22)"))
        unverbucht, _ = self.auswerten()
        self.assertEqual(unverbucht, ["BOARD.md"])

    def test_neue_board_ohne_historie_ist_befund(self):
        """Eine nie committete BOARD.md hat keinen Diff — die Ausnahme darf
        nicht greifen, sonst wäre sie über eine neue Datei aushebelbar."""
        self.schreibe("README.md", "x\n")
        self.committe()
        self.schreibe("BOARD.md", self.BOARD_ALT)
        unverbucht, _ = self.auswerten()
        self.assertEqual(unverbucht, ["BOARD.md"])

    def test_ausnahme_liest_den_diff_und_nicht_den_pfad(self):
        """Die Ausnahme gilt nur für BOARD.md — ein Anforderungsdokument, dessen
        einzige Änderung zufällig mit 'Stand:' beginnt, bleibt ein Befund."""
        self.schreibe("requirements/software/software-requirements.md",
                      "Stand: 2026-08-16\nSWR-001\n")
        self.committe()
        self.schreibe("requirements/software/software-requirements.md",
                      "Stand: 2026-08-17\nSWR-001\n")
        unverbucht, _ = self.auswerten()
        self.assertEqual(unverbucht, ["requirements/software/software-requirements.md"])


class StatuszeileTest(unittest.TestCase):
    """Pfad aus der Porcelain-Zeile (Rename, Anführungszeichen)."""

    def test_einfacher_pfad(self):
        self.assertEqual(preflight._pfad_aus_statuszeile(" M BOARD.md"), "BOARD.md")

    def test_neue_datei(self):
        self.assertEqual(preflight._pfad_aus_statuszeile("?? tickets/T-0010.md"),
                         "tickets/T-0010.md")

    def test_rename_meint_das_ziel(self):
        self.assertEqual(preflight._pfad_aus_statuszeile("R  alt.md -> tickets/T-0011.md"),
                         "tickets/T-0011.md")

    def test_anfuehrungszeichen_fallen_weg(self):
        self.assertEqual(preflight._pfad_aus_statuszeile(' M "tickets/T-0012.md"'),
                         "tickets/T-0012.md")


if __name__ == "__main__":
    unittest.main()
