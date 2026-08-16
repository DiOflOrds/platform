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
        """SWR-056/064: gültige Änderung (Mehrfach-Takt) → Datei + Commit, Konten unverändert."""
        erg = teams.konfiguration_schreiben(self.root, "team-x",
                                            {"takte": [7, 30], "zustellung_mail": True})
        self.assertEqual(erg["konfiguration"]["takte"], [7, 30])
        self.assertTrue(erg["konfiguration"]["zustellung_mail"])
        self.assertEqual(erg["konfiguration"]["konten"][0]["name"], "a@b.de")
        status = _git(self.repo, "status", "--porcelain").stdout.strip()
        self.assertEqual(status, "", "Arbeitskopie muss nach dem Sofort-Commit sauber sein")
        log = _git(self.repo, "log", "-1", "--pretty=%an %s").stdout
        self.assertIn("Mensch via HMI", log)

    def test_konfiguration_validierung(self):
        """SWR-056/064: ungültiger Takt oder leere Auswahl → 400; Konten-Änderung → 400 (Klasse A)."""
        for kaputt in ({"takte": [5]}, {"takte": []}, {"zeitraum_tage": 5}):
            with self.assertRaises(teams.TeamFehler) as k:
                teams.konfiguration_schreiben(self.root, "team-x", kaputt)
            self.assertEqual(k.exception.code, 400)
        with self.assertRaises(teams.TeamFehler) as k:
            teams.konfiguration_schreiben(self.root, "team-x", {"konten": []})
        self.assertEqual(k.exception.code, 400)
        self.assertIn("Klasse A", str(k.exception))

    def test_modellwahl_und_ki_hinweis_rundlauf(self):
        """SWR-071/072: Modell + Hinweis werden geschrieben, wieder gelesen und bleiben
        bei Teil-Änderungen erhalten; leer = automatisch (Altverhalten)."""
        alt = teams.lade_konfiguration(self.root, "team-x")
        self.assertEqual((alt["ollama_modell"], alt["ki_hinweis"]), ("", ""))
        erg = teams.konfiguration_schreiben(self.root, "team-x", {
            "takte": [1], "ollama_modell": "llama3.1:8b",
            "ki_hinweis": "achte auf Bewerbungen"})
        neu = erg["konfiguration"]
        self.assertEqual(neu["ollama_modell"], "llama3.1:8b")
        self.assertEqual(neu["ki_hinweis"], "achte auf Bewerbungen")
        # Feld nicht mitgeschickt → unverändert (Konfigurator sendet nur, was er kennt)
        wieder = teams.konfiguration_schreiben(self.root, "team-x", {"takte": [7]})["konfiguration"]
        self.assertEqual(wieder["ollama_modell"], "llama3.1:8b")
        self.assertEqual(wieder["ki_hinweis"], "achte auf Bewerbungen")
        self.assertEqual(wieder["takte"], [7])
        # zurück auf automatisch
        leer = teams.konfiguration_schreiben(self.root, "team-x", {
            "takte": [1], "ollama_modell": "", "ki_hinweis": ""})["konfiguration"]
        self.assertEqual((leer["ollama_modell"], leer["ki_hinweis"]), ("", ""))

    def test_modellwahl_und_hinweis_validierung(self):
        """SWR-071/072: unsinniger Modellname, zu langer/mehrzeiliger Hinweis → 400."""
        for kaputt in ({"ollama_modell": "böse; rm -rf"}, {"ollama_modell": "x" * 101},
                       {"ki_hinweis": "a" * 201}, {"ki_hinweis": "zwei\nzeilen"},
                       {"ki_hinweis": "kommentar # kaputt"}):
            werte = dict({"takte": [1]}, **kaputt)
            with self.assertRaises(teams.TeamFehler) as k:
                teams.konfiguration_schreiben(self.root, "team-x", werte)
            self.assertEqual(k.exception.code, 400)

    def test_ollama_modelle_liste(self):
        """SWR-071: Liste per injiziertem Abruf; Ollama nicht erreichbar → gültige Antwort
        mit leerer Liste, deutschem Hinweis und unverändertem konfiguriertem Wert."""
        erg = teams.ollama_modelle(self.root, "team-x", abruf=lambda: ["a:7b", "b:3b"])
        self.assertEqual(erg["modelle"], ["a:7b", "b:3b"])
        self.assertEqual(erg["aktiv"], "a:7b")  # ohne Konfiguration: erstes installiertes
        self.assertTrue(erg["automatisch"])
        teams.konfiguration_schreiben(self.root, "team-x",
                                      {"takte": [1], "ollama_modell": "b:3b"})

        def _tot():
            raise OSError("Verbindung abgelehnt")

        aus = teams.ollama_modelle(self.root, "team-x", abruf=_tot)
        self.assertEqual(aus["modelle"], [])
        self.assertEqual(aus["konfiguriert"], "b:3b")
        self.assertEqual(aus["aktiv"], "b:3b")
        self.assertIn("nicht erreichbar", aus["hinweis"])
        with self.assertRaises(teams.TeamFehler) as k:
            teams.ollama_modelle(self.root, "kein-team", abruf=lambda: [])
        self.assertEqual(k.exception.code, 404)

    def test_digest_jetzt(self):
        """SWR-063: Sofort-Lauf über injizierten Runner; ohne Werkzeug → 404; Fehler → 502."""
        with self.assertRaises(teams.TeamFehler) as k:
            teams.digest_jetzt(self.root, "team-x")
        self.assertEqual(k.exception.code, 404)
        os.makedirs(os.path.join(self.repo, "tools"), exist_ok=True)
        with open(os.path.join(self.repo, "tools", "mail_digest.py"), "w", encoding="utf-8") as f:
            f.write("# dummy\n")
        erg = teams.digest_jetzt(self.root, "team-x",
                                 runner=lambda p: (0, "[tag] Digest -> digest/x.md"))
        self.assertIn("Digest", erg["meldung"])
        with self.assertRaises(teams.TeamFehler) as k:
            teams.digest_jetzt(self.root, "team-x", runner=lambda p: (1, "kaputt"))
        self.assertEqual(k.exception.code, 502)


if __name__ == "__main__":
    unittest.main()
