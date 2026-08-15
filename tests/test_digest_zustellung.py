# -*- coding: utf-8 -*-
"""P7-Tests SWR-058: Digest-Zustellung — einmalig, idempotent, fehlertolerant.
Hermetisch nach gb-02: Temp-Repo, injizierte sende-Funktion, kein SMTP/Netz."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import digest_zustellung  # noqa: E402


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t"]
                          + list(args), capture_output=True, text=True)


class DigestZustellungTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="zustellung-test-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.repo = os.path.join(self.root, "team-x")
        os.makedirs(os.path.join(self.repo, "digest"))
        os.makedirs(os.path.join(self.repo, "tickets"))
        with open(os.path.join(self.repo, "team.yaml"), "w", encoding="utf-8") as f:
            f.write('name: "Team X"\nprofil: "wiederkehrend"\n')
        self._konfig(zustellung="ja")
        with open(os.path.join(self.repo, "digest", "2026-08-15-digest.md"), "w",
                  encoding="utf-8") as f:
            f.write("# Digest 2026-08-15\n\nInhalt.\n")
        _git(self.repo, "init", "-b", "main")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-m", "init")
        self.gesendet = []

    def _konfig(self, zustellung):
        with open(os.path.join(self.repo, "konfiguration.yaml"), "w", encoding="utf-8") as f:
            f.write(f"zeitraum_tage: 1\nzustellung_mail: {zustellung}\n")

    def _sende_ok(self, betreff, text):
        self.gesendet.append(betreff)
        return True, "ok"

    def test_sendet_einmal_und_vermerkt(self):
        """SWR-058: Versand + Zustellvermerk + Commit; zweiter Lauf sendet nicht erneut."""
        b1 = digest_zustellung.lauf(self.root, self._sende_ok, heute="2026-08-15")
        self.assertEqual(self.gesendet, ["[team-x] Digest 2026-08-15"])
        self.assertIn("[team-x] 2026-08-15-digest.md: zugestellt", b1)
        inhalt = open(os.path.join(self.repo, "digest", "2026-08-15-digest.md"),
                      encoding="utf-8").read()
        self.assertIn("**Zugestellt:** 2026-08-15", inhalt)
        self.assertEqual(_git(self.repo, "status", "--porcelain").stdout.strip(), "",
                         "Vermerk muss committet sein")
        b2 = digest_zustellung.lauf(self.root, self._sende_ok, heute="2026-08-15")
        self.assertEqual(len(self.gesendet), 1, "idempotent: kein Doppelversand")
        self.assertEqual(b2, [])

    def test_deaktivierte_teams_werden_uebersprungen(self):
        """SWR-058: zustellung_mail nein -> kein Versand, kein Vermerk."""
        self._konfig(zustellung="nein")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-m", "aus")
        bericht = digest_zustellung.lauf(self.root, self._sende_ok)
        self.assertEqual(self.gesendet, [])
        self.assertEqual(bericht, [])

    def test_fehler_blockiert_nicht_und_vermerkt_nicht(self):
        """SWR-058: Sendefehler -> kein Vermerk (nächster Lauf versucht erneut), kein Abbruch."""
        def kaputt(betreff, text):
            return False, "SMTP nicht konfiguriert"
        bericht = digest_zustellung.lauf(self.root, kaputt)
        self.assertTrue(any("NICHT zugestellt" in z for z in bericht))
        inhalt = open(os.path.join(self.repo, "digest", "2026-08-15-digest.md"),
                      encoding="utf-8").read()
        self.assertNotIn("**Zugestellt:**", inhalt)
        # danach klappt es — genau ein Versand
        b2 = digest_zustellung.lauf(self.root, self._sende_ok, heute="2026-08-15")
        self.assertIn("[team-x] 2026-08-15-digest.md: zugestellt", b2)

    def test_dry_run_sendet_nichts(self):
        """SWR-058: dry-run meldet, sendet und vermerkt nichts."""
        bericht = digest_zustellung.lauf(self.root, self._sende_ok, dry_run=True)
        self.assertEqual(self.gesendet, [])
        self.assertIn("[team-x] 2026-08-15-digest.md: dry-run", bericht)


if __name__ == "__main__":
    unittest.main()
