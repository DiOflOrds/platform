# -*- coding: utf-8 -*-
"""pm/T-0022 (Teil "Starten"), SWR-089: Technik-Kandidat aus dem Projekt-Pool

als G0-Antrag starten.

Verifiziert: nur Technik-Kandidaten (Team-Kandidaten werden mit Verweis auf die
Team-Gründung abgelehnt), Projekt-Nummer über dieselbe Discovery wie Board/
Matrix/Preflight (Top-Level UND Sammel-Repo `projects/`), Ordner + gültiger
G0-Decision-Request (T-0001) + BOARD.md in einem Commit im Repo `projects`,
Rücknahme (kompletter Ordner weg) bei gescheitertem Commit, Kandidat wird im
Pool nachgeführt — nach „Realisiert" verschoben statt gelöscht, und das
Decision-Log entsteht mit Tabellenkopf (beides pm/T-0037 nach Befund B051) —
(zweiter Commit im Repo `pm`) — bleibt aber stehen, wenn nur
dieser zweite Commit scheitert (das bereits sichtbare Projekt wird nicht
zurückgenommen), Ablehnung unbekannter Kandidaten und verbotener Zeichen,
HTTP-Anbindung inkl. PIN-Schreibschutz (SWR-048).
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import aggregation, pool, server  # noqa: E402
import board  # noqa: E402 (platform/scripts, via pool.py's sys.path-Eintrag)

POOL_TEXT = (
    "# Projekt-Pool (Test)\n\n"
    "*Kandidaten, per Zuruf/Knopf startbar.*\n\n"
    "## Team-Kandidaten (aus deiner ursprünglichen Vision)\n\n"
    "| # | Kandidat | Nutzen | Voraussetzung |\n"
    "|---|---|---|---|\n"
    "| 1 | **team-termine** — Kalender-/Termin-Team | Termine erkennen | keine |\n"
    "| 2 | **team-finanzen** — Rechnungsübersicht | Monatsübersicht | keine |\n\n"
    "## Technik-Kandidaten (ASPICE-Backlog)\n\n"
    "| # | Kandidat | Quelle |\n"
    "|---|---|---|\n"
    "| 6 | mail_digest → Katalog-Produkt | B003 |\n"
    "| 7 | JS-Frontend-Tests | P3-R1 |\n"
)


def _git_init(repo):
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"]):
        subprocess.run(["git", "-C", repo] + args, check=True, capture_output=True)


def _repo_bauen(wurzel, mit_p10=True, mit_toplevel_p9=False):
    """pm-Repo (mit Pool-Datei) + Sammel-Repo `projects` (git-initialisiert,
    optional mit einem Bestandsprojekt p10) — beide unter `wurzel`."""
    pm_dir = os.path.join(wurzel, "pm", "management")
    os.makedirs(pm_dir)
    open(os.path.join(pm_dir, "projekt-pool.md"), "w", encoding="utf-8", newline="\n").write(POOL_TEXT)
    pm_repo = os.path.join(wurzel, "pm")
    _git_init(pm_repo)

    projects_repo = os.path.join(wurzel, "projects")
    os.makedirs(projects_repo)
    open(os.path.join(projects_repo, "README.md"), "w").write("# projects\n")
    if mit_p10:
        os.makedirs(os.path.join(projects_repo, "p10", "tickets"))
        open(os.path.join(projects_repo, "p10", "tickets", ".gitkeep"), "w").close()
    _git_init(projects_repo)

    if mit_toplevel_p9:
        os.makedirs(os.path.join(wurzel, "p9", "tickets"))
        open(os.path.join(wurzel, "p9", "tickets", ".gitkeep"), "w").close()

    return pm_repo, projects_repo


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wurzel = self.tmp.name
        self.pm_repo, self.projects_repo = _repo_bauen(self.wurzel)

    def tearDown(self):
        self.tmp.cleanup()

    def pool_pfad(self):
        return os.path.join(self.pm_repo, "management", "projekt-pool.md")

    def pool_text(self):
        return open(self.pool_pfad(), encoding="utf-8").read()

    def commits(self, repo):
        lauf = subprocess.run(["git", "-C", repo, "log", "--pretty=%an|%s"],
                              capture_output=True, text=True)
        return lauf.stdout.strip().splitlines()


class TestStartenTechnik(Basis):
    """SWR-089: Happy Path — Ordner, G0-Antrag, BOARD.md, Pool-Nachführung.

    pm/T-0037 (B051): „Nachführung" statt „Entfernung" — der Kandidat wird aus der
    Kandidatentabelle nach „Realisiert" verschoben, und das Decision-Log entsteht
    mit Tabellenkopf.
    """

    def test_technik_kandidat_wird_gestartet(self):
        erg = pool.kandidat_starten(self.wurzel, "JS-Frontend-Tests")
        self.assertTrue(erg["ok"])
        self.assertEqual(erg["kandidat"], "JS-Frontend-Tests")
        self.assertEqual(erg["projekt"], "p11")  # p10 existiert bereits -> naechste Nummer
        self.assertEqual(erg["ticket"], "T-0001")
        self.assertEqual(erg["ref"], "p11/T-0001")

    def test_ordner_und_ticket_valide(self):
        pool.kandidat_starten(self.wurzel, "JS-Frontend-Tests")
        projekt = os.path.join(self.projects_repo, "p11")
        self.assertTrue(os.path.isfile(os.path.join(projekt, "tickets", "T-0001.md")))
        self.assertTrue(os.path.isfile(os.path.join(projekt, "docs", "01-projektauftrag.md")))
        self.assertTrue(os.path.isfile(os.path.join(projekt, "steckbrief.yaml")))
        self.assertTrue(os.path.isfile(os.path.join(projekt, "BOARD.md")))
        tickets, probleme = board.lade_tickets(projekt)
        self.assertEqual(probleme, [])
        self.assertEqual(len(tickets), 1)
        t = tickets[0]
        self.assertEqual(t["typ"], "decision-request")
        self.assertEqual(t["status"], "open")
        self.assertEqual(t["default"], "G0a")
        self.assertIn("JS-Frontend-Tests", t["_body"])
        board_probleme = board.validiere_alle(tickets, projekt, git_pruefen=False)
        self.assertEqual(board_probleme, [])

    def test_board_md_enthaelt_ticket(self):
        pool.kandidat_starten(self.wurzel, "JS-Frontend-Tests")
        board_text = open(os.path.join(self.projects_repo, "p11", "BOARD.md"),
                          encoding="utf-8").read()
        self.assertIn("T-0001", board_text)
        self.assertIn("open", board_text)

    def test_kandidat_aus_kandidatentabelle_entfernt(self):
        """pm/T-0037: aus der Technik-Tabelle heraus — aber nicht aus der Datei.

        Vorher pruefte dieser Test `assertNotIn` ueber die ganze Datei; genau das
        hat das spurlose Loeschen (B051/B029) mitgetragen.
        """
        pool.kandidat_starten(self.wurzel, "JS-Frontend-Tests")
        text = self.pool_text()
        technik = text.split("## Technik-Kandidaten")[1].split("\n## ")[0]
        self.assertNotIn("JS-Frontend-Tests", technik)
        self.assertIn("mail_digest", technik)  # anderer Kandidat bleibt unberuehrt

    def test_kandidat_steht_unter_realisiert(self):
        """pm/T-0037 (B051, Befund 1): verschoben statt geloescht — mit Wohin und Beleg."""
        pool.kandidat_starten(self.wurzel, "JS-Frontend-Tests")
        text = self.pool_text()
        self.assertIn("## Realisiert", text)
        realisiert = text.split("## Realisiert")[1]
        self.assertIn("JS-Frontend-Tests", realisiert)
        self.assertIn("P3-R1", realisiert)          # Quelle aus der Kandidatenzeile
        self.assertIn("projects/p11", realisiert)   # Wohin
        self.assertIn("p11/T-0001", realisiert)     # Beleg
        zeile = next(z for z in realisiert.splitlines() if "JS-Frontend-Tests" in z)
        self.assertTrue(zeile.strip().startswith("| 7 |"), zeile)  # Nummer bleibt erhalten
        self.assertEqual(zeile.count("|"), 5)       # vier Spalten, Tabelle nicht gesprengt

    def test_realisiert_abschnitt_wird_angelegt_wenn_er_fehlt(self):
        """Bestandsdateien ohne den (von Hand eingefuehrten) Abschnitt: anlegen statt scheitern."""
        self.assertNotIn("## Realisiert", self.pool_text())  # Gegenprobe: Fixture hat ihn nicht
        pool.kandidat_starten(self.wurzel, "JS-Frontend-Tests")
        text = self.pool_text()
        self.assertIn("## Realisiert", text)
        self.assertIn("| # | Kandidat | Wohin | Beleg |", text)

    def test_zweiter_start_haengt_an_bestehende_realisiert_tabelle_an(self):
        """Zweiter Lauf legt keinen zweiten Abschnitt an, sondern haengt an."""
        pool.kandidat_starten(self.wurzel, "JS-Frontend-Tests")
        pool.kandidat_starten(self.wurzel, "mail_digest → Katalog-Produkt")
        text = self.pool_text()
        self.assertEqual(text.count("## Realisiert"), 1)
        realisiert = text.split("## Realisiert")[1]
        self.assertIn("JS-Frontend-Tests", realisiert)
        self.assertIn("mail_digest", realisiert)

    def test_decision_log_hat_tabellenkopf(self):
        """pm/T-0037 (B051, Befund 2): der Kopf steht, der Platzhaltersatz ist weg.

        Ohne Kopfzeile ist die von `inbox.entscheide` angehaengte D000-Zeile keine
        Tabelle, sondern Pipe-Text (so geschehen bei P12).
        """
        pool.kandidat_starten(self.wurzel, "JS-Frontend-Tests")
        log = open(os.path.join(self.projects_repo, "p11", "management", "decisions",
                                "decision-log.md"), encoding="utf-8").read()
        self.assertIn("| ID | Datum | Entscheider | Entscheidung | Optionen | Begründung "
                      "| Betroffene Artefakte |", log)
        self.assertIn("|---|---|---|---|---|---|---|", log)
        self.assertNotIn("Noch keine Entscheidung", log)
        # Der Kopf ist die letzte Zeile: eine angehaengte Zeile ist damit die erste Datenzeile.
        zeilen = [z for z in log.splitlines() if z.strip()]
        self.assertTrue(zeilen[-1].startswith("|---"), zeilen[-1])

    def test_angehaengte_entscheidungszeile_steht_unter_gueltigem_kopf(self):
        """Gegenprobe zum eigentlichen Schaden: D000 muss als Tabellenzeile lesbar sein."""
        pool.kandidat_starten(self.wurzel, "JS-Frontend-Tests")
        pfad = os.path.join(self.projects_repo, "p11", "management", "decisions",
                            "decision-log.md")
        with open(pfad, "a", encoding="utf-8", newline="\n") as f:
            f.write("| D000 | 2026-08-16 18:04 | Mensch (E. John, via Inbox) | **G0a** "
                    "| lt. T-0001 | — | T-0001 |\n")
        tabellen = aggregation.parse_md_tabellen(open(pfad, encoding="utf-8").read())
        self.assertEqual(len(tabellen), 1, "ohne Kopf erkennt der Parser keine Tabelle")
        self.assertEqual(tabellen[0]["spalten"][0], "ID")
        self.assertEqual(len(tabellen[0]["zeilen"]), 1)
        self.assertEqual(tabellen[0]["zeilen"][0][0], "D000")

    def test_zwei_commits_mit_herkunft(self):
        pool.kandidat_starten(self.wurzel, "JS-Frontend-Tests")
        proj_commit = self.commits(self.projects_repo)[0]
        pm_commit = self.commits(self.pm_repo)[0]
        self.assertTrue(proj_commit.startswith("Mensch via HMI|"), proj_commit)
        self.assertIn("p11", proj_commit)
        self.assertTrue(pm_commit.startswith("Mensch via HMI|"), pm_commit)
        self.assertIn("p11", pm_commit)

    def test_case_und_leerzeichen_insensitiv(self):
        erg = pool.kandidat_starten(self.wurzel, "  js-frontend-tests  ")
        self.assertTrue(erg["ok"])


class TestStartenAblehnungen(Basis):
    def test_team_kandidat_abgelehnt(self):
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.kandidat_starten(self.wurzel, "team-termine")
        self.assertEqual(ctx.exception.code, 400)
        self.assertIn("Team-Gründung", str(ctx.exception))

    def test_unbekannter_kandidat(self):
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.kandidat_starten(self.wurzel, "Gibt es nicht")
        self.assertEqual(ctx.exception.code, 404)

    def test_leerer_kandidat(self):
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.kandidat_starten(self.wurzel, "")
        self.assertEqual(ctx.exception.code, 400)

    def test_verbotenes_zeichen_pipe(self):
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.kandidat_starten(self.wurzel, "Mit | Pipe")
        self.assertEqual(ctx.exception.code, 400)

    def test_verbotenes_zeichen_anfuehrungszeichen(self):
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.kandidat_starten(self.wurzel, 'Mit "Zeichen"')
        self.assertEqual(ctx.exception.code, 400)

    def test_fehlendes_projects_repo(self):
        wurzel2 = tempfile.TemporaryDirectory()
        try:
            pm_dir = os.path.join(wurzel2.name, "pm", "management")
            os.makedirs(pm_dir)
            open(os.path.join(pm_dir, "projekt-pool.md"), "w", encoding="utf-8",
                newline="\n").write(POOL_TEXT)
            _git_init(os.path.join(wurzel2.name, "pm"))
            with self.assertRaises(pool.PoolFehler) as ctx:
                pool.kandidat_starten(wurzel2.name, "JS-Frontend-Tests")
            self.assertEqual(ctx.exception.code, 404)
        finally:
            wurzel2.cleanup()

    def test_fehlende_pool_datei(self):
        os.remove(self.pool_pfad())
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.kandidat_starten(self.wurzel, "JS-Frontend-Tests")
        self.assertEqual(ctx.exception.code, 404)


class TestNummerierung(unittest.TestCase):
    """Projekt-Nummer über dieselbe Discovery wie Board/Matrix/Preflight — Top-Level
    UND Sammel-Repo tragen zum Maximum bei (Lesson p9/T-0007)."""

    def test_nummer_ueber_toplevel_und_sammelrepo(self):
        with tempfile.TemporaryDirectory() as wurzel:
            _repo_bauen(wurzel, mit_p10=True, mit_toplevel_p9=True)
            # p9 (Top-Level) und p10 (Sammel-Repo) vorhanden -> naechste Nummer 11
            self.assertEqual(pool._naechste_projektnummer(wurzel), 11)

    def test_nummer_ohne_bestandsprojekte(self):
        with tempfile.TemporaryDirectory() as wurzel:
            _repo_bauen(wurzel, mit_p10=False)
            self.assertEqual(pool._naechste_projektnummer(wurzel), 1)


class TestCommitRuecknahme(Basis):
    """Rücknahme bei gescheitertem Commit — Muster aus test_pool_kandidat.py."""

    def test_gescheiterter_projekt_commit_nimmt_ordner_zurueck(self):
        vorher_pool = self.pool_text()
        echt = subprocess.run

        def kaputt(befehl, *a, **k):
            if "commit" in befehl and self.projects_repo in befehl:
                class R:
                    returncode, stdout, stderr = 1, "", "simulierter Git-Fehler"
                return R()
            return echt(befehl, *a, **k)

        pool.subprocess.run = kaputt
        try:
            with self.assertRaises(pool.PoolFehler) as ctx:
                pool.kandidat_starten(self.wurzel, "JS-Frontend-Tests")
        finally:
            pool.subprocess.run = echt
        self.assertEqual(ctx.exception.code, 503)
        self.assertFalse(os.path.exists(os.path.join(self.projects_repo, "p11")))
        self.assertEqual(self.pool_text(), vorher_pool)  # Pool nie angefasst
        self.assertEqual(len(self.commits(self.projects_repo)), 1)  # nur init

    def test_gescheiterter_pool_commit_behaelt_projekt(self):
        echt = subprocess.run

        def kaputt(befehl, *a, **k):
            if "commit" in befehl and self.pm_repo in befehl:
                class R:
                    returncode, stdout, stderr = 1, "", "simulierter Git-Fehler"
                return R()
            return echt(befehl, *a, **k)

        pool.subprocess.run = kaputt
        try:
            erg = pool.kandidat_starten(self.wurzel, "JS-Frontend-Tests")
        finally:
            pool.subprocess.run = echt
        # Projekt bleibt bestehen und ist committet — nur der Pool-Eintrag konnte
        # nicht nachgefuehrt werden (kein Datenverlust, sichtbare Warnung statt B038).
        self.assertTrue(erg["ok"])
        self.assertIn("NICHT im Pool nachgeführt", erg["meldung"])
        self.assertTrue(os.path.isfile(
            os.path.join(self.projects_repo, "p11", "tickets", "T-0001.md")))
        self.assertEqual(len(self.commits(self.projects_repo)), 2)  # init + Projekt-Commit
        self.assertEqual(len(self.commits(self.pm_repo)), 1)  # nur init, Pool-Commit scheiterte
        # Arbeitskopie vollstaendig zurueckgenommen: Kandidat steht wieder in der
        # Technik-Tabelle, und es ist KEIN halber "Realisiert"-Abschnitt entstanden (pm/T-0037).
        text = self.pool_text()
        self.assertIn("JS-Frontend-Tests", text.split("## Technik-Kandidaten")[1])
        self.assertNotIn("## Realisiert", text)


class HttpTest(unittest.TestCase):
    """HTTP-Anbindung: /api/pool/start inkl. PIN-Schreibschutz (SWR-048)."""

    def setUp(self):
        self._env_alt = os.environ.pop("MC_PIN", None)
        self.tmp = tempfile.TemporaryDirectory()
        self.wurzel = self.tmp.name
        _repo_bauen(self.wurzel)
        server.Api.protokoll = lambda *a, **k: None
        self.srv = server.start(self.wurzel, port=0)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.tmp.cleanup()
        if self._env_alt is not None:
            os.environ["MC_PIN"] = self._env_alt

    def _post(self, pfad, daten, headers=None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{pfad}", data=json.dumps(daten).encode("utf-8"),
            headers=dict({"Content-Type": "application/json"}, **(headers or {})), method="POST")
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode("utf-8"))

    def test_post_startet_kandidat(self):
        antwort = self._post("/api/pool/start", {"kandidat": "JS-Frontend-Tests"})
        self.assertTrue(antwort["ok"])
        self.assertEqual(antwort["projekt"], "p11")

    def test_unbekannter_kandidat_meldet_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post("/api/pool/start", {"kandidat": "Gibt es nicht"})
        self.assertEqual(ctx.exception.code, 404)

    def test_team_kandidat_meldet_400(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post("/api/pool/start", {"kandidat": "team-termine"})
        self.assertEqual(ctx.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
