# -*- coding: utf-8 -*-
"""P7-Tests: Team-Daten (SWR-053), Cockpit-Kachel (SWR-055), Konfigurator (SWR-056).
Hermetisch nach gb-02: eigenes Temp-Repo, Env-Scrub für MC_PIN, kein Netz."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import aggregation, teams  # noqa: E402


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t"]
                          + list(args), capture_output=True, text=True)


class TeamsTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="teams-test-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        for k in ("MC_PIN",):  # gb-02: Maschinen-Env nie in Tests wirken lassen
            os.environ.pop(k, None)
        repo = os.path.join(self.root, "team-x")
        for d in ("tickets", "digest", "docs", os.path.join("management", "decisions")):
            os.makedirs(os.path.join(repo, d))
        with open(os.path.join(repo, "team.yaml"), "w", encoding="utf-8") as f:
            f.write('name: "Team X"\ntyp: projekt\nprofil: "wiederkehrend"\n'
                    "datenklasse: sensibel\nrollen: [MAIL-RED, QM]\nsla:\n"
                    '  - "digest: je Session"\ngegruendet: "2026-08-15"\n')
        with open(os.path.join(repo, "konfiguration.yaml"), "w", encoding="utf-8") as f:
            f.write("zeitraum_tage: 1\nkonten:\n  - name: a@b.de\n    env_suffix: \"\"\n"
                    "abschnitt_rechnungen: ja\nzustellung_mail: nein\n")
        with open(os.path.join(repo, "docs", "01-team-charter.md"), "w", encoding="utf-8") as f:
            f.write("# Team-Charter Team X\n\nAuftrag.\n")
        for name in ("2026-08-14-digest.md", "2026-08-15-digest.md"):
            with open(os.path.join(repo, "digest", name), "w", encoding="utf-8") as f:
                f.write(f"# Digest {name[:10]}\n\nInhalt.\n")
        _git(repo, "init", "-b", "main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "init")
        self.repo = repo

    def test_team_daten_vollstaendig(self):
        """SWR-053: Steckbrief, Konfiguration, Charta und Digest-Verlauf in einer Antwort."""
        t = teams.team_daten(self.root, "team-x")
        self.assertEqual(t["steckbrief"]["profil"], "wiederkehrend")
        self.assertEqual(t["steckbrief"]["rollen"], ["MAIL-RED", "QM"])
        self.assertEqual(t["steckbrief"]["datenklasse"], "sensibel")
        self.assertEqual([d["datum"] for d in t["digests"]],
                         ["2026-08-15", "2026-08-14"])  # neueste zuerst
        self.assertEqual(t["letzter_digest"], "2026-08-15")
        self.assertIn("Team-Charter", t["charta"])
        self.assertEqual(t["konfiguration"]["zeitraum_tage"], 1)
        self.assertEqual(t["konfiguration"]["konten"][0]["name"], "a@b.de")

    def test_digest_inhalt_und_pfadschutz(self):
        """SWR-053: Digest-Volltext; Pfad-Ausbruch und Unbekanntes werden abgelehnt."""
        d = teams.digest_inhalt(self.root, "team-x", "2026-08-15-digest.md")
        self.assertIn("Inhalt.", d["inhalt"])
        with self.assertRaises(teams.TeamFehler) as k:
            teams.digest_inhalt(self.root, "team-x", "../team.yaml")
        self.assertEqual(k.exception.code, 400)
        with self.assertRaises(teams.TeamFehler) as k:
            teams.digest_inhalt(self.root, "team-x", "gibtsnicht.md")
        self.assertEqual(k.exception.code, 404)

    def test_kein_team_projekt(self):
        """SWR-053: Projekte ohne team.yaml liefern 404 mit klarer Meldung."""
        os.makedirs(os.path.join(self.root, "p9", "tickets"))
        with self.assertRaises(teams.TeamFehler) as k:
            teams.team_daten(self.root, "p9")
        self.assertEqual(k.exception.code, 404)
        self.assertIn("kein Team-Projekt", str(k.exception))

    def test_cockpit_team_kachel(self):
        """SWR-055: Cockpit enthält Team-Info mit Datum des letzten Digests."""
        c = aggregation.cockpit(self.root, "team-x")
        self.assertEqual(c["team"], {"letzter_digest": "2026-08-15"})

    def test_konfiguration_schreiben_und_commit(self):
        """SWR-056: gültige Änderung → Datei + sofortiger Commit, Konten unverändert."""
        erg = teams.konfiguration_schreiben(self.root, "team-x",
                                            {"zeitraum_tage": 7, "zustellung_mail": True})
        self.assertEqual(erg["konfiguration"]["zeitraum_tage"], 7)
        self.assertTrue(erg["konfiguration"]["zustellung_mail"])
        self.assertEqual(erg["konfiguration"]["konten"][0]["name"], "a@b.de")
        status = _git(self.repo, "status", "--porcelain").stdout.strip()
        self.assertEqual(status, "", "Arbeitskopie muss nach dem Sofort-Commit sauber sein")
        log = _git(self.repo, "log", "-1", "--pretty=%an %s").stdout
        self.assertIn("Mensch via HMI", log)

    def test_konfiguration_validierung(self):
        """SWR-056: ungültiger Zeitraum → 400; Konten-Änderung → 400 (Klasse A)."""
        with self.assertRaises(teams.TeamFehler) as k:
            teams.konfiguration_schreiben(self.root, "team-x", {"zeitraum_tage": 5})
        self.assertEqual(k.exception.code, 400)
        self.assertIn("erlaubt sind 1", str(k.exception))
        with self.assertRaises(teams.TeamFehler) as k:
            teams.konfiguration_schreiben(self.root, "team-x", {"konten": []})
        self.assertEqual(k.exception.code, 400)
        self.assertIn("Klasse A", str(k.exception))


if __name__ == "__main__":
    unittest.main()
