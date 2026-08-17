# -*- coding: utf-8 -*-
"""pm/T-0022 (Teil "Anlegen"), SWR-088: Kandidat im Projekt-Pool anlegen.

Verifiziert: Validierung je Kategorie (Team: Name + Kurzbeschreibung + Nutzen +
Voraussetzung; Technik: freier Titel + Quelle), laufende Nummer ÜBER BEIDE
Kategorien hinweg, neue Zeile ans Ende der eigenen Kategorie, Sofort-Commit mit
erkennbarer Herkunft, Rücknahme bei gescheitertem Commit, Ablehnung doppelter
Kandidaten, HTTP-Anbindung inkl. PIN-Schreibschutz (SWR-048).
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
from backend import pool, server  # noqa: E402

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


def _repo_bauen(wurzel):
    pm = os.path.join(wurzel, "pm", "management")
    os.makedirs(pm)
    open(os.path.join(pm, "projekt-pool.md"), "w", encoding="utf-8", newline="\n").write(POOL_TEXT)
    repo = os.path.join(wurzel, "pm")
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"]):
        subprocess.run(["git", "-C", repo] + args, check=True, capture_output=True)
    return repo


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wurzel = self.tmp.name
        self.repo = _repo_bauen(self.wurzel)

    def tearDown(self):
        self.tmp.cleanup()

    def pfad(self):
        return os.path.join(self.repo, "management", "projekt-pool.md")

    def _wortlaut_gesamt(self):
        """Pool-Datei PLUS ausgelagerte Volltexte (SWR-124).

        Die Zusicherung „der Text wird angenommen und nicht gekürzt" ist eine Aussage
        über den Wortlaut, nicht über die Datei, in der er steht.
        """
        text = open(self.pfad(), encoding="utf-8").read()
        verz = os.path.join(self.repo, "management", "kandidaten")
        if os.path.isdir(verz):
            for name in sorted(os.listdir(verz)):
                text += "\n" + open(os.path.join(verz, name), encoding="utf-8").read()
        return text

    def text(self):
        return open(self.pfad(), encoding="utf-8").read()

    def commits(self):
        lauf = subprocess.run(["git", "-C", self.repo, "log", "--pretty=%an|%s"],
                              capture_output=True, text=True)
        return lauf.stdout.strip().splitlines()


class TestAnlegenTeam(Basis):
    """SWR-088: Team-Kandidat mit Nutzen + Voraussetzung, Zeile im Team-Stil."""

    def test_team_kandidat_wird_angelegt(self):
        erg = pool.kandidat_anlegen(self.wurzel, "team", "team-urlaub", "Urlaubsplanung",
                                    {"Nutzen": "Enpal-Termine bündeln", "Voraussetzung": "keine"})
        self.assertTrue(erg["ok"])
        self.assertEqual(erg["kategorie"], "team")
        self.assertEqual(erg["kandidat"], "team-urlaub")
        # laufende Nummer ueber beide Kategorien: hoechste bisherige (7) + 1
        self.assertEqual(erg["nummer"], 8)
        neu = self.text()
        self.assertIn("| 8 | **team-urlaub** — Urlaubsplanung | Enpal-Termine bündeln | keine |", neu)

    def test_zeile_landet_am_ende_der_eigenen_kategorie(self):
        pool.kandidat_anlegen(self.wurzel, "team", "team-urlaub", "Urlaubsplanung",
                              {"Nutzen": "x", "Voraussetzung": "keine"})
        zeilen = self.text().splitlines()
        team_start = next(i for i, z in enumerate(zeilen) if "Team-Kandidaten" in z)
        technik_start = next(i for i, z in enumerate(zeilen) if "Technik-Kandidaten" in z)
        neue_zeile_index = next(i for i, z in enumerate(zeilen) if "team-urlaub" in z)
        self.assertTrue(team_start < neue_zeile_index < technik_start)

    def test_ungueltiger_name_abgelehnt(self):
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.kandidat_anlegen(self.wurzel, "team", "Team Urlaub", "x",
                                  {"Nutzen": "x", "Voraussetzung": "x"})
        self.assertEqual(ctx.exception.code, 400)

    def test_kurzbeschreibung_pflicht(self):
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.kandidat_anlegen(self.wurzel, "team", "team-urlaub", "",
                                  {"Nutzen": "x", "Voraussetzung": "x"})
        self.assertEqual(ctx.exception.code, 400)

    def test_pflichtfeld_fehlt(self):
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.kandidat_anlegen(self.wurzel, "team", "team-urlaub", "Urlaubsplanung",
                                  {"Nutzen": "x", "Voraussetzung": ""})
        self.assertEqual(ctx.exception.code, 400)

    def test_zeilenumbruch_wird_zu_leerzeichen(self):
        """pm/N-0023: Zeilenumbrüche (Copy/Paste, KI-Text) werden normalisiert
        statt die Eingabe abzulehnen — die Pool-Zeile bleibt eine Tabellenzeile."""
        erg = pool.kandidat_anlegen(self.wurzel, "team", "team-urlaub", "Zeile1\nZeile2",
                                    {"Nutzen": "x", "Voraussetzung": "x"})
        self.assertTrue(erg["ok"])
        neu = self.text()
        self.assertIn("Zeile1 Zeile2", neu)
        self.assertNotIn("\n", neu.split("Zeile1 Zeile2")[1].split("|")[0])

    def test_langer_text_wird_akzeptiert(self):
        """pm/N-0023: 'lang' im Sinne von deutlich über den früheren 200 Zeichen —
        typisch für einen mehrsätzigen, auch KI-formulierten Kandidatentext.

        ⚠ Angepasst in Sprint 10 (SWR-124, pm/T-0057). Die Zusicherung aus `pm/N-0023`
        lautet **„wird angenommen und nicht gekürzt"** — bis hierher prüfte der Test
        stattdessen, wo der Text danach *liegt*, und band die Zusicherung damit an ihre
        damalige Umsetzung. Seit SWR-124 wandert ein Text über `ZELLE_MAX` in eine eigene
        Datei; die Zusicherung gilt unverändert, ihre Umsetzung ist eine andere.
        Geprüft wird deshalb der **Wortlaut**, nicht sein Aufbewahrungsort.
        """
        lang = "Ein ausführlich begründeter Kandidatentext. " * 10  # > 200 Zeichen
        self.assertGreater(len(lang), 200)
        erg = pool.kandidat_anlegen(self.wurzel, "team", "team-lang", lang,
                                    {"Nutzen": "x", "Voraussetzung": "x"})
        self.assertTrue(erg["ok"])
        self.assertIn(lang.strip(), self._wortlaut_gesamt())

    def test_zu_langer_text_bleibt_abgelehnt(self):
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.kandidat_anlegen(self.wurzel, "team", "team-zulang", "x" * (pool.FELD_MAX + 1),
                                  {"Nutzen": "x", "Voraussetzung": "x"})
        self.assertEqual(ctx.exception.code, 400)

    def test_pipe_im_text_abgelehnt(self):
        """'|' bleibt hart verboten — würde die Markdown-Tabelle sprengen."""
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.kandidat_anlegen(self.wurzel, "team", "team-urlaub", "Text mit | Pipe",
                                  {"Nutzen": "x", "Voraussetzung": "x"})
        self.assertEqual(ctx.exception.code, 400)

    def test_doppelter_kandidat_abgelehnt(self):
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.kandidat_anlegen(self.wurzel, "team", "team-termine", "Nochmal",
                                  {"Nutzen": "x", "Voraussetzung": "x"})
        self.assertEqual(ctx.exception.code, 409)


class TestAnlegenTechnik(Basis):
    """SWR-088: Technik-Kandidat mit freiem Titel + Quelle, keine Fettschrift."""

    def test_technik_kandidat_wird_angelegt(self):
        erg = pool.kandidat_anlegen(self.wurzel, "technik", "CSV-Export für Reports", "",
                                    {"Quelle": "Support-Ticket #4"})
        self.assertTrue(erg["ok"])
        self.assertEqual(erg["nummer"], 8)
        neu = self.text()
        self.assertIn("| 8 | CSV-Export für Reports | Support-Ticket #4 |", neu)
        self.assertNotIn("**CSV-Export", neu)  # keine Fettschrift, anders als bei Team

    def test_quelle_pflicht(self):
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.kandidat_anlegen(self.wurzel, "technik", "CSV-Export", "", {"Quelle": ""})
        self.assertEqual(ctx.exception.code, 400)

    def test_langer_technik_text_wird_akzeptiert_und_umbrueche_normalisiert(self):
        """pm/N-0023: der Kandidat-Text TRÄGT bei Technik-Kandidaten die ganze
        Aufgabe (keine separate Kurzbeschreibung) — muss also lang sein dürfen,
        auch mit Zeilenumbrüchen aus KI-generiertem Text."""
        lang = "Zeile eins der Aufgabe.\nZeile zwei mit weiterer Begründung. " * 5
        self.assertGreater(len(lang), 200)
        erg = pool.kandidat_anlegen(self.wurzel, "technik", lang, "", {"Quelle": "KI-Vorschlag"})
        self.assertTrue(erg["ok"])
        self.assertNotIn("\n", self.text().split("KI-Vorschlag")[0].splitlines()[-1])

    def test_lange_quelle_ueber_alten_4000er_deckel_wird_akzeptiert(self):
        """pm/N-0024: Selbst die auf 4000 Zeichen angehobene Grenze aus T-0027
        reichte für ein reales "Quelle"-Feld nicht — FELD_MAX ist jetzt eine
        technische Notbremse (200_000), keine Inhaltsgrenze mehr. Regressionstest
        gegen den alten Code: Bei FELD_MAX = 4000 hätte dieser Text abgelehnt."""
        quelle_lang = "Auszug aus einem weitergeleiteten Gespräch als Herkunftsbeleg. " * 100
        self.assertGreater(len(quelle_lang), 4000)
        erg = pool.kandidat_anlegen(self.wurzel, "technik", "CSV-Export für Reports", "",
                                    {"Quelle": quelle_lang})
        self.assertTrue(erg["ok"])
        # Wortlaut statt Ort — siehe test_langer_text_wird_akzeptiert (SWR-124).
        self.assertIn(" ".join(quelle_lang.split()), self._wortlaut_gesamt())

    def test_doppelter_kandidat_abgelehnt_technik(self):
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.kandidat_anlegen(self.wurzel, "technik", "JS-Frontend-Tests", "",
                                  {"Quelle": "nochmal"})
        self.assertEqual(ctx.exception.code, 409)


class TestLaufendeNummer(Basis):
    """Auftrag platform/N-0005: eine Nummernfolge über beide Kategorien hinweg."""

    def test_nummer_steigt_kategorieuebergreifend(self):
        a = pool.kandidat_anlegen(self.wurzel, "technik", "Erster Kandidat", "",
                                  {"Quelle": "x"})
        b = pool.kandidat_anlegen(self.wurzel, "team", "team-zweite", "Beschreibung",
                                  {"Nutzen": "x", "Voraussetzung": "x"})
        self.assertEqual(a["nummer"], 8)
        self.assertEqual(b["nummer"], 9)


class TestValidierungAllgemein(Basis):
    def test_unbekannte_kategorie(self):
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.kandidat_anlegen(self.wurzel, "sonstiges", "x", "y", {})
        self.assertEqual(ctx.exception.code, 400)

    def test_fehlende_pool_datei(self):
        os.remove(self.pfad())
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.kandidat_anlegen(self.wurzel, "team", "team-x", "y",
                                  {"Nutzen": "x", "Voraussetzung": "x"})
        self.assertEqual(ctx.exception.code, 404)


class TestCommit(Basis):
    """Ein Commit je Kandidat mit erkennbarer Herkunft; Rücknahme bei Fehlschlag."""

    def test_commit_mit_herkunft(self):
        pool.kandidat_anlegen(self.wurzel, "team", "team-urlaub", "Urlaubsplanung",
                              {"Nutzen": "x", "Voraussetzung": "keine"})
        letzte = self.commits()[0]
        self.assertTrue(letzte.startswith("Mensch via HMI|"), letzte)
        self.assertIn("team-urlaub", letzte)
        geaendert = subprocess.run(
            ["git", "-C", self.repo, "show", "--name-only", "--pretty=", "HEAD"],
            capture_output=True, text=True).stdout
        self.assertIn("management/projekt-pool.md", geaendert.replace("\\", "/"))

    def test_gescheiterter_commit_nimmt_zurueck(self):
        vorher = self.text()
        echt = subprocess.run

        def kaputt(befehl, *a, **k):
            if "commit" in befehl:
                class R:
                    returncode, stdout, stderr = 1, "", "simulierter Git-Fehler"
                return R()
            return echt(befehl, *a, **k)

        pool.subprocess.run = kaputt
        try:
            with self.assertRaises(pool.PoolFehler) as ctx:
                pool.kandidat_anlegen(self.wurzel, "team", "team-urlaub", "Urlaubsplanung",
                                      {"Nutzen": "x", "Voraussetzung": "keine"})
        finally:
            pool.subprocess.run = echt
        self.assertEqual(ctx.exception.code, 503)
        self.assertEqual(self.text(), vorher)
        self.assertEqual(len(self.commits()), 1)  # nur der init-Commit aus setUp


class HttpTest(unittest.TestCase):
    """HTTP-Anbindung: /api/pool (GET liest, POST legt an) inkl. PIN-Schreibschutz."""

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

    def test_post_legt_kandidat_an_und_get_zeigt_ihn_sofort(self):
        antwort = self._post("/api/pool", {"kategorie": "technik", "kandidat": "Neuer Kandidat",
                                           "felder": {"Quelle": "Test"}})
        self.assertTrue(antwort["ok"])
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/pool") as r:
            gelesen = json.loads(r.read().decode("utf-8"))
        text_aller_zellen = json.dumps(gelesen["abschnitte"])
        self.assertIn("Neuer Kandidat", text_aller_zellen)

    def test_ungueltige_eingabe_meldet_400(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post("/api/pool", {"kategorie": "team", "kandidat": "Ungültiger Name"})
        self.assertEqual(ctx.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
