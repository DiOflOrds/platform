"""Tests Preflight-Skript (T-0024). Bezug: CR T-0024 (Prozess-Tooling, kein SWR)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import preflight  # noqa: E402


def _fake_git(root, *artefakte):
    g = os.path.join(root, ".git")
    os.makedirs(os.path.join(g, "objects", "e5"), exist_ok=True)
    os.makedirs(os.path.join(g, "refs", "heads"), exist_ok=True)
    for a in artefakte:
        pfad = os.path.join(g, a)
        os.makedirs(os.path.dirname(pfad), exist_ok=True)
        open(pfad, "w").close()
    return g


class TestLockArtefakte(unittest.TestCase):
    """Lock-Erkennung findet alle bekannten Artefakt-Klassen. Bezug: CR T-0024."""

    def test_findet_bekannte_artefakte(self):
        """index.lock, HEAD.lock, maintenance.lock, tmp_obj_*, refs-Locks werden erkannt."""
        with tempfile.TemporaryDirectory() as d:
            _fake_git(d, "index.lock", "HEAD.lock",
                      os.path.join("objects", "maintenance.lock"),
                      os.path.join("objects", "e5", "tmp_obj_XYZ"),
                      os.path.join("refs", "heads", "main.lock"))
            funde = preflight.finde_lock_artefakte(d)
            self.assertEqual(len(funde), 5)

    def test_sauberes_repo_ohne_funde(self):
        """Ein Repo ohne Lock-Artefakte liefert eine leere Liste."""
        with tempfile.TemporaryDirectory() as d:
            _fake_git(d)
            self.assertEqual(preflight.finde_lock_artefakte(d), [])

    def test_entfernen_meldet_erfolg(self):
        """Entfernbare Artefakte werden gelöscht und als entfernt gemeldet."""
        with tempfile.TemporaryDirectory() as d:
            _fake_git(d, "index.lock")
            funde = preflight.finde_lock_artefakte(d)
            entfernt, kaputt = preflight.entferne_artefakte(funde)
            self.assertEqual(len(entfernt), 1)
            self.assertEqual(kaputt, [])
            self.assertEqual(preflight.finde_lock_artefakte(d), [])

    def test_entfernen_meldet_fehlschlag(self):
        """Nicht löschbare Pfade landen in der Fehlschlag-Liste (R7-Fall), kein Abbruch."""
        entfernt, kaputt = preflight.entferne_artefakte(
            [os.path.join(tempfile.gettempdir(), "gibt-es-nicht", "x.lock")])
        self.assertEqual(entfernt, [])
        self.assertEqual(len(kaputt), 1)


class TestPreflightGesamt(unittest.TestCase):
    """Gesamtlauf meldet fehlende Repos als Befund. Bezug: CR T-0024."""

    def test_fehlende_repos_sind_befunde(self):
        """Leere Wurzel: 3 fehlende Repos + board-check-Fehler = 4 Befunde."""
        with tempfile.TemporaryDirectory() as d:
            befunde = preflight.preflight(d, skip_tests=True)
            self.assertEqual(befunde, 4)


class TestReposImRoot(unittest.TestCase):
    """T-0050: Preflight kennt auch Produkt-Repos im Root."""

    def test_produkt_repo_wird_erkannt(self):
        """Zusaetzliche Git-Repos im Root (z.B. produkt-datakonv) werden geprueft. Verifiziert: SWR-015."""
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            for name in ("p0", "produkt-x"):
                os.makedirs(os.path.join(root, name, ".git"))
            os.makedirs(os.path.join(root, "kein-repo"))
            namen = preflight.repos_im_root(root)
            self.assertIn("produkt-x", namen)
            self.assertNotIn("kein-repo", namen)
            self.assertEqual(namen[:3], ["process", "platform", "p0"])


if __name__ == "__main__":
    unittest.main()
