"""API-Tests Backend-MVP (T-0032, T-0034). Verifiziert: SWR-020, SWR-022, SWR-023, SWR-024."""
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
from backend import aggregation, inbox, mailer, server  # noqa: E402

TICKET_DR = """---
id: T-0099
titel: "DR: Testentscheidung"
typ: decision-request
prozess: man3
rolle: pl
sprint: 3
status: open
prio: hoch
blocked_by: []
erstellt: 2026-08-06
---

Optionen: A (Default) / B. Frist: 2026-08-31.
"""

TICKET_TASK = """---
id: T-0098
titel: "Task, kein DR"
typ: task
prozess: swe3
rolle: dev
sprint: 3
status: open
prio: mittel
blocked_by: []
erstellt: 2026-08-06
---
"""

LOG_KOPF = "# Decision Log (Test)\n\n| ID | Datum | Entscheider | Entscheidung | Optionen | Begründung | Artefakte |\n|---|---|---|---|---|---|---|\n| D000 | 2026-08-05 | Mensch | Start | — | — | — |\n"

RUN = ('{"rolle": "cm", "ticket": "T-0010", "provider": "ollama", "status": "ok", '
       '"kosten_eur": 0.5, "zeit": "2026-08-06T10:00:00+00:00"}\n')


def _wurzel_bauen(d):
    p0 = os.path.join(d, "p0")
    os.makedirs(os.path.join(p0, "tickets"))
    os.makedirs(os.path.join(p0, "management", "decisions"))
    os.makedirs(os.path.join(p0, "management", "runs"))
    os.makedirs(os.path.join(p0, "management", "sprint-2"))
    open(os.path.join(p0, "tickets", "T-0099.md"), "w", encoding="utf-8").write(TICKET_DR)
    open(os.path.join(p0, "tickets", "T-0098.md"), "w", encoding="utf-8").write(TICKET_TASK)
    open(os.path.join(p0, "management", "decisions", "decision-log.md"), "w",
         encoding="utf-8").write(LOG_KOPF)
    open(os.path.join(p0, "management", "runs", "run-registry.jsonl"), "w",
         encoding="utf-8").write(RUN * 2)
    open(os.path.join(p0, "management", "sprint-2", "report.md"), "w",
         encoding="utf-8").write("# Sprint-2-Report (Test)\n")
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"]):
        subprocess.run(["git", "-C", p0] + args, check=True, capture_output=True)
    return d


TICKET_DR_P1 = TICKET_DR.replace("T-0099", "T-0001").replace(
    "sprint: 3", "sprint: 1").replace(
    "---\n\nOptionen", "optionen: [A, B]\n---\n\nOptionen")


def _p1_dazu(wurzel):
    """Zweites Projekt für Multi-Projekt-Tests (SWR-025..027)."""
    p1 = os.path.join(wurzel, "p1")
    os.makedirs(os.path.join(p1, "tickets"))
    os.makedirs(os.path.join(p1, "management", "decisions"))
    open(os.path.join(p1, "tickets", "T-0001.md"), "w", encoding="utf-8").write(TICKET_DR_P1)
    open(os.path.join(p1, "management", "decisions", "decision-log.md"), "w",
         encoding="utf-8").write(LOG_KOPF)
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"]):
        subprocess.run(["git", "-C", p1] + args, check=True, capture_output=True)
    return p1


class MultiProjektTest(unittest.TestCase):
    """P1/T-0005+T-0007: Discovery, Scoping, Übersicht, projektübergreifende Inbox."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.wurzel = _wurzel_bauen(self._tmp.name)
        _p1_dazu(self.wurzel)

    def tearDown(self):
        self._tmp.cleanup()

    def test_discovery_und_scoping(self):
        """Projekte werden per Konvention erkannt; Board-API ist je Projekt gescopt, unbekannte Namen werden abgelehnt. Verifiziert: SWR-025."""
        self.assertEqual(aggregation.projekte(self.wurzel), ["p0", "p1"])
        self.assertEqual(aggregation.lade_board(self.wurzel, "p1")["anzahl"], 1)
        self.assertEqual(aggregation.lade_board(self.wurzel)["anzahl"], 2)  # Default p0
        with self.assertRaises(ValueError):
            aggregation.lade_board(self.wurzel, "gibtsnicht")

    def test_uebersicht_je_projekt(self):
        """Die Übersicht listet je Projekt offene Tickets und offene DRs. Verifiziert: SWR-026."""
        u = aggregation.uebersicht(self.wurzel)
        je_name = {e["projekt"]: e for e in u["projekte"]}
        self.assertEqual(je_name["p1"]["tickets_offen"], 1)
        self.assertEqual(je_name["p1"]["offene_drs"][0]["id"], "T-0001")
        self.assertEqual(je_name["p0"]["offene_drs"][0]["id"], "T-0099")

    def test_inbox_ueber_alle_projekte(self):
        """Die Inbox listet DRs aller Projekte mit projekt-Feld. Verifiziert: SWR-027."""
        eintraege = inbox.liste(self.wurzel)["inbox"]
        self.assertEqual([(e["projekt"], e["id"]) for e in eintraege],
                         [("p0", "T-0099"), ("p1", "T-0001")])

    def test_views_requirements_verifikation_baselines(self):
        """Requirements-/Verifikations-Dateien werden je Projekt geliefert, Baselines je Repo. Verifiziert: SWR-030, SWR-031, SWR-032."""
        p0 = os.path.join(self.wurzel, "p0")
        os.makedirs(os.path.join(p0, "requirements", "software"))
        open(os.path.join(p0, "requirements", "software", "software-requirements.md"),
             "w", encoding="utf-8").write("# SWRs\n")
        os.makedirs(os.path.join(p0, "verification", "reports"))
        open(os.path.join(p0, "verification", "reports", "matrix.md"),
             "w", encoding="utf-8").write("# Matrix\n")
        subprocess.run(["git", "-C", p0, "-c", "user.name=t", "-c", "user.email=t@t",
                        "tag", "-a", "demo-v1", "-m", "Demo-Baseline"],
                       check=True, capture_output=True)
        reqs = aggregation.lade_requirements(self.wurzel, "p0")
        self.assertEqual(reqs["dateien"][0]["datei"], "software/software-requirements.md")
        ver = aggregation.lade_verifikation(self.wurzel, "p0")
        self.assertIn("Matrix", ver["dateien"][0]["text"])
        bl = aggregation.lade_baselines(self.wurzel)
        p0_tags = [r["tags"] for r in bl["repos"] if r["repo"] == "p0"][0]
        self.assertTrue(any("demo-v1" in t for t in p0_tags))

    def test_entscheidung_im_richtigen_projekt(self):
        """Entscheidungen landen im Log des jeweiligen Projekts; falsches Projekt → 404. Verifiziert: SWR-027."""
        e = inbox.entscheide(self.wurzel, "T-0001", "A", "Grund", projekt="p1")
        self.assertEqual(e["entscheidung"], "D001")
        log = open(os.path.join(self.wurzel, "p1", "management", "decisions",
                                "decision-log.md"), encoding="utf-8").read()
        self.assertIn("| D001 |", log)
        with self.assertRaises(inbox.InboxFehler) as k:
            inbox.entscheide(self.wurzel, "T-0099", "A", projekt="p1")
        self.assertEqual(k.exception.code, 404)


class AggregationTest(unittest.TestCase):
    """Read-only-Aggregation aus der Arbeitskopie. Verifiziert: SWR-022."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.wurzel = _wurzel_bauen(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_board_gruppiert_nach_status(self):
        """Board-Aggregation liefert Tickets gruppiert nach Status. Verifiziert: SWR-022."""
        b = aggregation.lade_board(self.wurzel)
        self.assertEqual(b["anzahl"], 2)
        self.assertEqual({t["id"] for t in b["gruppen"]["open"]}, {"T-0098", "T-0099"})

    def test_reports_und_kpi(self):
        """Reports und Kosten/KPI kommen aus Dateien bzw. Run-Registry. Verifiziert: SWR-022."""
        self.assertEqual(aggregation.lade_reports(self.wurzel)["reports"][0]["sprint"], "sprint-2")
        kpi = aggregation.lade_kpi(self.wurzel)
        self.assertEqual(kpi["laeufe"], 2)
        self.assertAlmostEqual(kpi["kosten_eur_gesamt"], 1.0)
        self.assertEqual(kpi["laeufe_je_provider"], {"ollama": 2})

    def test_neustart_aequivalenz(self):
        """Zwei frische Lesevorgänge liefern identische Daten — kein Zustand. Verifiziert: SWR-024."""
        self.assertEqual(aggregation.lade_board(self.wurzel),
                         aggregation.lade_board(self.wurzel))


class SelbstNeustartTest(unittest.TestCase):
    """Selbst-Neustart bei neuem Code auf der Platte. Verifiziert: SWR-073 (pm/N-0010)."""

    def test_entscheidung_nur_bei_neuem_stand_ruhe_und_schleife(self):
        """SWR-073: Nur mit Startskript-Marker, geändertem UND entprelltem Stand bei Ruhe."""
        f = server.selbst_neustart_noetig
        # Regelfall: neuer Stand, beim vorigen Durchlauf schon gesehen, Server ruhig
        self.assertTrue(f("alt111", "neu222", "neu222", True, True))
        # Ohne Startskript-Schleife nie — sonst wäre der Server einfach weg
        self.assertFalse(f("alt111", "neu222", "neu222", False, True))
        # Unveränderter Code: kein Grund
        self.assertFalse(f("alt111", "alt111", "alt111", True, True))
        # Erst einmal gesehen (Entprellen): ein Sprint schreibt viele Commits
        self.assertFalse(f("alt111", "neu222", "alt111", True, True))
        # Anfrage läuft gerade: verschieben, nicht abwürgen
        self.assertFalse(f("alt111", "neu222", "neu222", True, False))
        # Kein Git/kein Stand ermittelbar: nichts tun
        for kaputt in ("", "unbekannt"):
            self.assertFalse(f("alt111", kaputt, kaputt, True, True))

    def test_wache_beendet_prozess_mit_42(self):
        """SWR-073/061: Die Wache ruft den Austritt mit dem Neustart-Code der Startskripte."""
        os.environ[server.SCHLEIFEN_MARKER] = "1"
        self.addCleanup(os.environ.pop, server.SCHLEIFEN_MARKER, None)
        staende = iter([server.PROZESS_STAND, "neu222", "neu222"])
        gerufen = []
        server._neustart_wache(intervall=0, austritt=lambda: gerufen.append(server.NEUSTART_CODE),
                               stand=lambda: next(staende), ruhig=lambda: True)
        self.assertEqual(gerufen, [42])

    def test_wache_ohne_marker_beendet_nie(self):
        """SWR-073: Ohne Marker (Handstart/Test) läuft die Wache leer durch."""
        os.environ.pop(server.SCHLEIFEN_MARKER, None)
        staende = iter(["neu222"] * 4)
        gerufen = []
        with self.assertRaises(StopIteration):  # läuft weiter, bis die Stände ausgehen
            server._neustart_wache(intervall=0, austritt=lambda: gerufen.append(1),
                                   stand=lambda: next(staende), ruhig=lambda: True)
        self.assertEqual(gerufen, [])


class InboxTest(unittest.TestCase):
    """Decision-Inbox: listen + entscheiden + Commit. Verifiziert: SWR-020, SWR-024."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.wurzel = _wurzel_bauen(self._tmp.name)
        self.p0 = os.path.join(self.wurzel, "p0")

    def tearDown(self):
        self._tmp.cleanup()

    def test_liste_nur_offene_drs(self):
        """Nur nicht-finale decision-request-Tickets erscheinen in der Inbox. Verifiziert: SWR-020."""
        eintraege = inbox.liste(self.wurzel)["inbox"]
        self.assertEqual([e["id"] for e in eintraege], ["T-0099"])
        self.assertIn("Optionen", eintraege[0]["body"])

    def test_entscheidung_roundtrip_mit_commit(self):
        """Entscheidung: D-ID vergeben, Log + Ticket + BOARD geschrieben, Arbeitskopie sauber committet. Verifiziert: SWR-020, SWR-024."""
        e = inbox.entscheide(self.wurzel, "T-0099", "A", "Testgrund")
        self.assertEqual(e["entscheidung"], "D001")
        log = open(os.path.join(self.p0, "management", "decisions", "decision-log.md"),
                   encoding="utf-8").read()
        self.assertIn("| D001 |", log)
        self.assertIn("via Inbox", log)
        ticket = open(os.path.join(self.p0, "tickets", "T-0099.md"), encoding="utf-8").read()
        self.assertIn("Entscheidung (D001", ticket)
        status = subprocess.run(["git", "-C", self.p0, "status", "--porcelain"],
                                capture_output=True, text=True).stdout.strip()
        self.assertEqual(status, "", "Arbeitskopie muss nach der Entscheidung sauber sein")

    def test_fehlerfaelle(self):
        """Unbekanntes Ticket → 404, Nicht-DR → 400, leere Option → 400. Verifiziert: SWR-020."""
        for tid, opt, code in (("T-1234", "A", 404), ("T-0098", "A", 400), ("T-0099", " ", 400)):
            with self.assertRaises(inbox.InboxFehler) as kontext:
                inbox.entscheide(self.wurzel, tid, opt)
            self.assertEqual(kontext.exception.code, code)

    def test_optionen_validierung(self):
        """T-0039: ungültige Option → 400 ohne Log-Eintrag; gültige Kombination wird angenommen. Verifiziert: SWR-020."""
        open(os.path.join(self.p0, "tickets", "T-0097.md"), "w", encoding="utf-8").write(
            TICKET_DR.replace("T-0099", "T-0097").replace(
                "---\n\nOptionen",
                "optionen: [A1, A2, B1]\nfrist: 2026-08-31\ndefault: A1, B1\n---\n\nOptionen"))
        log_pfad = os.path.join(self.p0, "management", "decisions", "decision-log.md")
        vorher = open(log_pfad, encoding="utf-8").read()
        with self.assertRaises(inbox.InboxFehler) as kontext:
            inbox.entscheide(self.wurzel, "T-0097", "C9")
        self.assertEqual(kontext.exception.code, 400)
        self.assertEqual(open(log_pfad, encoding="utf-8").read(), vorher,
                         "ungültige Option darf keinen Decision-Log-Eintrag erzeugen")
        e = inbox.entscheide(self.wurzel, "T-0097", "A2, B1")
        self.assertEqual(e["option"], "A2, B1")

    def test_freitext_ohne_optionen_feld_bleibt_gueltig(self):
        """T-0039: Alt-DRs ohne optionen-Feld akzeptieren weiter Freitext. Verifiziert: SWR-020."""
        e = inbox.entscheide(self.wurzel, "T-0099", "A")
        self.assertEqual(e["option"], "A")


def _registry(wurzel, text):
    team = os.path.join(wurzel, "process", "team")
    os.makedirs(team, exist_ok=True)
    open(os.path.join(team, "nutzer.yaml"), "w", encoding="utf-8").write(text)


class NutzerUndHaertungTest(unittest.TestCase):
    """P2/T-0009: Registry, Entscheider-Pflicht, Inbox-Härtung."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.wurzel = _wurzel_bauen(self._tmp.name)
        self.p0 = os.path.join(self.wurzel, "p0")

    def tearDown(self):
        self._tmp.cleanup()

    def test_registry_parsen_und_fallback(self):
        """Registry liefert Namen+Rollen; ohne Datei gilt der einzelne Default-Entscheider. Verifiziert: SWR-037."""
        self.assertEqual(inbox.lade_nutzer(self.wurzel),
                         [{"name": "E. John", "rolle": "entscheider"}])
        _registry(self.wurzel, "nutzer:\n  - name: Anna\n    rolle: entscheider\n"
                               "  - name: Ben\n    rolle: leser\n")
        self.assertEqual(inbox.lade_nutzer(self.wurzel),
                         [{"name": "Anna", "rolle": "entscheider"},
                          {"name": "Ben", "rolle": "leser"}])

    def test_entscheider_pflicht(self):
        """Leser und Unbekannte werden abgewiesen (403), registrierte Entscheider protokolliert;
        leer bei mehreren Entscheidern -> 400. Verifiziert: SWR-038."""
        _registry(self.wurzel, "nutzer:\n  - name: Anna\n    rolle: entscheider\n"
                               "  - name: Ben\n    rolle: leser\n"
                               "  - name: Cleo\n    rolle: entscheider\n")
        for wer in ("Ben", "Unbekannt"):
            with self.assertRaises(inbox.InboxFehler) as k:
                inbox.entscheide(self.wurzel, "T-0099", "A", entscheider=wer)
            self.assertEqual(k.exception.code, 403)
        with self.assertRaises(inbox.InboxFehler) as k:
            inbox.entscheide(self.wurzel, "T-0099", "A")
        self.assertEqual(k.exception.code, 400)
        e = inbox.entscheide(self.wurzel, "T-0099", "A", entscheider="Anna")
        self.assertEqual(e["entscheider"], "Anna")
        log = open(os.path.join(self.p0, "management", "decisions", "decision-log.md"),
                   encoding="utf-8").read()
        self.assertIn("Mensch (Anna, via Inbox)", log)

    def test_entschiedener_dr_verschwindet_und_sperrt(self):
        """Nach der Entscheidung: DR nicht mehr in der Inbox (trotz Status open),
        Zweitantwort -> 400 (D001-Befund). Verifiziert: SWR-039."""
        inbox.entscheide(self.wurzel, "T-0099", "A")
        self.assertEqual(inbox.liste(self.wurzel)["inbox"], [])
        with self.assertRaises(inbox.InboxFehler) as k:
            inbox.entscheide(self.wurzel, "T-0099", "B")
        self.assertEqual(k.exception.code, 400)


    def test_inbox_zaehler_fuer_den_menschen(self):
        """Der Inbox-Zähler im Reiter zählt genau die wartenden Entscheidungen und geht
        nach der Antwort auf null. Verifiziert: SWR-076 (pm/N-0016)."""
        self.assertEqual(len(inbox.liste(self.wurzel)["inbox"]), 1)
        inbox.entscheide(self.wurzel, "T-0099", "A")
        self.assertEqual(len(inbox.liste(self.wurzel)["inbox"]), 0)


class HmiSprint2Test(unittest.TestCase):
    """P3/T-0014+T-0016: Tabellen-Parser und Cockpit."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.wurzel = _wurzel_bauen(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_md_tabellen_parser(self):
        """Markdown-Tabellen werden zu Spalten/Zeilen; Trennzeilen fliegen raus;
        Text ohne Tabelle ergibt leere Liste. Verifiziert: SWR-043, SWR-044."""
        text = ("# Doku\n\n| ID | Status |\n|---|---|\n| SWR-001 | reviewed |\n"
                "| SWR-002 | draft |\n\nProsa.\n\n| A |\n|---|\n| 1 |\n")
        tabellen = aggregation.parse_md_tabellen(text)
        self.assertEqual(len(tabellen), 2)
        self.assertEqual(tabellen[0]["spalten"], ["ID", "Status"])
        self.assertEqual(tabellen[0]["zeilen"], [["SWR-001", "reviewed"], ["SWR-002", "draft"]])
        self.assertEqual(aggregation.parse_md_tabellen("nur Prosa"), [])

    def test_requirements_liefern_tabellen(self):
        """/api-Sicht: requirements/verifikation tragen geparste Tabellen je Datei.
        Verifiziert: SWR-043, SWR-044."""
        req_dir = os.path.join(self.wurzel, "p0", "requirements")
        os.makedirs(req_dir)
        open(os.path.join(req_dir, "swr.md"), "w", encoding="utf-8").write(
            "| ID | Requirement |\n|---|---|\n| SWR-001 | The x shall y. |\n")
        daten = aggregation.lade_requirements(self.wurzel, "p0")
        self.assertEqual(daten["dateien"][0]["tabellen"][0]["zeilen"],
                         [["SWR-001", "The x shall y."]])

    def test_cockpit_mit_frist_ampel(self):
        """Cockpit: Status-Zahlen, DRs mit Ampel (rot=überschritten, gelb=<=2 Tage,
        gruen=später, grau=ohne Frist), KPI-Kurzfassung. Verifiziert: SWR-046."""
        import datetime
        p0 = os.path.join(self.wurzel, "p0")
        for tid, frist in (("T-0090", "2026-08-10"), ("T-0091", "2026-08-16"),
                           ("T-0092", "2026-08-30")):
            open(os.path.join(p0, "tickets", f"{tid}.md"), "w", encoding="utf-8").write(
                TICKET_DR.replace("T-0099", tid).replace(
                    "---\n\nOptionen", f"optionen: [A, B]\nfrist: {frist}\n---\n\nOptionen"))
        c = aggregation.cockpit(self.wurzel, "p0", heute=datetime.date(2026, 8, 15))
        self.assertEqual(c["tickets_gesamt"], 5)
        self.assertEqual(c["status_zahlen"]["open"], 5)
        ampeln = {d["id"]: d["ampel"] for d in c["offene_drs"]}
        self.assertEqual(ampeln["T-0090"], "rot")
        self.assertEqual(ampeln["T-0091"], "gelb")
        self.assertEqual(ampeln["T-0092"], "gruen")
        self.assertEqual(ampeln["T-0099"], "grau")
        self.assertIn("laeufe", c["kpi"])

    def test_cockpit_alle_ueber_api_form(self):
        """cockpit_alle liefert je entdecktem Projekt einen Eintrag (Frontend-Antwort).
        Verifiziert: SWR-046."""
        _p1_dazu(self.wurzel)
        alle = aggregation.cockpit_alle(self.wurzel)
        self.assertEqual([p["projekt"] for p in alle["projekte"]], ["p0", "p1"])


class FernzugriffTest(unittest.TestCase):
    """P4/T-0008+T-0009: PIN-Schreibschutz und Briefkasten."""

    def setUp(self):
        self._pin_alt = os.environ.pop("MC_PIN", None)
        self._tmp = tempfile.TemporaryDirectory()
        self.wurzel = _wurzel_bauen(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()
        os.environ.pop("MC_PIN", None)
        if self._pin_alt is not None:
            os.environ["MC_PIN"] = self._pin_alt

    def test_schreibschutz_regeln(self):
        """localhost frei; remote ohne MC_PIN gesperrt; falsche PIN abgelehnt;
        korrekte PIN erlaubt. Verifiziert: SWR-048, SWR-049."""
        from backend import server
        self.assertIsNone(server.schreibschutz_pruefen("127.0.0.1", None))
        self.assertIsNone(server.schreibschutz_pruefen("::1", "egal"))
        meldung = server.schreibschutz_pruefen("192.168.1.50", None)
        self.assertIn("MC_PIN", meldung)  # sicherer Default: gesperrt
        os.environ["MC_PIN"] = "4711"
        self.assertIn("PIN", server.schreibschutz_pruefen("192.168.1.50", "0000"))
        self.assertIn("PIN", server.schreibschutz_pruefen("192.168.1.50", None))
        self.assertIsNone(server.schreibschutz_pruefen("192.168.1.50", "4711"))

    def test_briefkasten_senden_und_lesen(self):
        """Brief -> versionierte Datei + Commit (saubere Arbeitskopie), Konversation
        chronologisch, Antwort-Abschnitt wird erkannt. Verifiziert: SWR-050."""
        from backend import briefkasten
        e = briefkasten.sende(self.wurzel, "p0", "Bitte XML-Support prüfen.", von="E. John")
        self.assertEqual(e["brief"], "N-0001")
        p0 = os.path.join(self.wurzel, "p0")
        status = subprocess.run(["git", "-C", p0, "status", "--porcelain"],
                                capture_output=True, text=True).stdout.strip()
        self.assertEqual(status, "", "Brief muss committet sein")
        briefkasten.sende(self.wurzel, "p0", "Zweite Nachricht.")
        pfad = os.path.join(p0, "management", "briefkasten", "N-0001.md")
        text = open(pfad, encoding="utf-8").read().replace("status: offen", "status: beantwortet")
        open(pfad, "w", encoding="utf-8", newline="\n").write(
            text + "\n## Antwort (Team, 2026-08-15)\n\nMachen wir als CR.\n")
        briefe = briefkasten.liste(self.wurzel, "p0")["briefe"]
        self.assertEqual([b["id"] for b in briefe], ["N-0001", "N-0002"])
        self.assertEqual(briefe[0]["status"], "beantwortet")
        self.assertIn("Machen wir als CR", briefe[0]["antwort"])
        self.assertEqual(briefe[1]["antwort"], "")
        with self.assertRaises(briefkasten.BriefkastenFehler):
            briefkasten.sende(self.wurzel, "p0", "   ")

    def test_cockpit_zaehlt_offene_briefe(self):
        """Unbeantwortete Briefe erscheinen im Cockpit (briefe_offen). Verifiziert: SWR-051."""
        from backend import briefkasten
        briefkasten.sende(self.wurzel, "p0", "Offener Brief.")
        c = aggregation.cockpit(self.wurzel, "p0")
        self.assertEqual(c["briefe_offen"], 1)


class MailerTest(unittest.TestCase):
    """Ausfalltoleranz Mailer. Verifiziert: SWR-023."""

    def test_unkonfiguriert_wirft_nicht(self):
        """Ohne SMTP_HOST: (False, Meldung), keine Exception. Verifiziert: SWR-023."""
        alt = os.environ.pop("SMTP_HOST", None)
        try:
            ok, meldung = mailer.sende("Betreff", "Text")
            self.assertFalse(ok)
            self.assertIn("nicht konfiguriert", meldung)
        finally:
            if alt:
                os.environ["SMTP_HOST"] = alt

    def test_kaputter_host_wirft_nicht(self):
        """Nicht erreichbarer SMTP-Host: (False, Meldung), keine Exception. Verifiziert: SWR-023."""
        alt = dict(os.environ)
        os.environ.update({"SMTP_HOST": "localhost", "SMTP_PORT": "1"})
        try:
            ok, meldung = mailer.sende("Betreff", "Text")
            self.assertFalse(ok)
            self.assertIn("fehlgeschlagen", meldung)
        finally:
            os.environ.clear()
            os.environ.update(alt)


class HttpTest(unittest.TestCase):
    """HTTP-Schicht Ende-zu-Ende auf ephemerem Port. Verifiziert: SWR-020, SWR-022."""

    def setUp(self):
        # p2/T-0002: SMTP-Umgebung isolieren — auf konfigurierten Maschinen (Team-Node)
        # hatte die Suite sonst ECHTE Mails verschickt und war umgebungsabhängig rot.
        self._env_alt = {k: os.environ.pop(k) for k in
                         ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "MAIL_TO")
                         if k in os.environ}
        self._tmp = tempfile.TemporaryDirectory()
        self.wurzel = _wurzel_bauen(self._tmp.name)
        server.Api.protokoll = lambda *a, **k: None
        self.srv = server.start(self.wurzel, port=0)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self._tmp.cleanup()
        os.environ.update(self._env_alt)

    def _get(self, pfad):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{pfad}") as r:
            return json.loads(r.read().decode("utf-8"))

    def test_get_endpunkte(self):
        """/api/board, /api/kpi und /api/inbox liefern JSON aus der Arbeitskopie. Verifiziert: SWR-022."""
        self.assertEqual(self._get("/api/board")["anzahl"], 2)
        self.assertEqual(self._get("/api/kpi")["laeufe"], 2)
        self.assertEqual(len(self._get("/api/inbox")["inbox"]), 1)

    def test_nutzer_endpunkt(self):
        """/api/nutzer liefert die Registry read-only (hier: Fallback-Entscheider);
        das Frontend speist daraus die Entscheider-Auswahl. Verifiziert: SWR-037, SWR-038."""
        self.assertEqual(self._get("/api/nutzer")["nutzer"],
                         [{"name": "E. John", "rolle": "entscheider"}])

    def test_ticket_detail(self):
        """/api/ticket liefert Metadaten + Body fuer die klickbare Detailansicht;
        unbekannte IDs -> 404. Verifiziert: SWR-040."""
        t = self._get("/api/ticket?projekt=p0&id=T-0099")
        self.assertEqual(t["id"], "T-0099")
        self.assertEqual(t["typ"], "decision-request")
        self.assertIn("Optionen", t["body"])
        with self.assertRaises(urllib.error.HTTPError) as k:
            self._get("/api/ticket?projekt=p0&id=T-9999")
        self.assertEqual(k.exception.code, 404)

    def test_board_felder_fuer_filter(self):
        """Board-Eintraege tragen typ/rolle/sprint/prio — Basis der Jira-like
        Spalten- und Filteransicht. Verifiziert: SWR-041."""
        gruppen = self._get("/api/board")["gruppen"]
        eintrag = gruppen["open"][0]
        for feld in ("id", "titel", "typ", "rolle", "sprint", "prio"):
            self.assertIn(feld, eintrag)

    def test_inbox_optionen_und_historie(self):
        """Inbox-Eintraege liefern optionen/frist/default maschinenlesbar (Buttons);
        entschiedene DRs wandern in /api/inbox/historie. Verifiziert: SWR-042."""
        _p1_dazu(self.wurzel)
        eintraege = self._get("/api/inbox")["inbox"]
        p1_dr = [e for e in eintraege if e["projekt"] == "p1"][0]
        self.assertEqual(p1_dr["optionen"], ["A", "B"])
        self.assertEqual(self._get("/api/inbox/historie")["historie"], [])
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/inbox/T-0001/decision",
            data=json.dumps({"option": "A", "projekt": "p1"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req):
            pass
        historie = self._get("/api/inbox/historie")["historie"]
        self.assertEqual([e["id"] for e in historie], ["T-0001"])
        self.assertIn("Entscheidung", historie[0]["entscheidung"])

    def test_version_endpunkt(self):
        """/api/version nennt Prozess- und Code-Stand — Grundlage des
        'Server-Neustart noetig'-Hinweises. Verifiziert: SWR-047."""
        v = self._get("/api/version")
        for feld in ("prozess_stand", "code_stand", "gestartet"):
            self.assertIn(feld, v)
        self.assertEqual(v["prozess_stand"], v["code_stand"])  # im Test kein Versatz

    def test_post_entscheidung(self):
        """POST /api/inbox/<id>/decision nimmt die Entscheidung an (Mail best effort). Verifiziert: SWR-020, SWR-023."""
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/inbox/T-0099/decision",
            data=json.dumps({"option": "B", "begruendung": "per Test"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as r:
            antwort = json.loads(r.read().decode("utf-8"))
        self.assertEqual(antwort["entscheidung"], "D001")
        self.assertFalse(antwort["mail"])  # SMTP unkonfiguriert, API funktioniert trotzdem
        # SWR-039 (P2/T-0009): entschiedener DR verschwindet aus der Inbox
        self.assertEqual(self._get("/api/inbox")["inbox"], [])

    def test_multi_projekt_endpunkte(self):
        """/api/projekte, /api/uebersicht und ?projekt= scopen korrekt; POST trägt das Projekt. Verifiziert: SWR-025, SWR-026, SWR-027."""
        _p1_dazu(self.wurzel)
        self.assertEqual(self._get("/api/projekte")["projekte"], ["p0", "p1"])
        self.assertEqual(len(self._get("/api/uebersicht")["projekte"]), 2)
        self.assertEqual(self._get("/api/board?projekt=p1")["anzahl"], 1)
        self.assertEqual(len(self._get("/api/inbox")["inbox"]), 2)
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/inbox/T-0001/decision",
            data=json.dumps({"option": "A", "projekt": "p1"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as r:
            antwort = json.loads(r.read().decode("utf-8"))
        self.assertEqual(antwort["projekt"], "p1")
        log = open(os.path.join(self.wurzel, "p1", "management", "decisions",
                                "decision-log.md"), encoding="utf-8").read()
        self.assertIn("| D001 |", log)

    def test_unbekanntes_projekt_404(self):
        """Unbekannte Projektnamen liefern 404 statt Serverfehler. Verifiziert: SWR-025."""
        try:
            self._get("/api/board?projekt=nix")
            self.fail("404 erwartet")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)


if __name__ == "__main__":
    unittest.main()
