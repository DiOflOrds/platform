"""API-Tests Backend-MVP (T-0032, T-0034). Verifiziert: SWR-020, SWR-022, SWR-023, SWR-024."""
import json
import os
import re
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

    def test_zeitpunkt_mit_uhrzeit_in_log_und_ticket(self):
        """SWR-084 (Wunsch Auftraggeber via Session): Log-Zeile und Ticket-Vermerk tragen Datum UND Uhrzeit —
        und zwar denselben Wert, damit beide Spuren zusammenpassen."""
        inbox.entscheide(self.wurzel, "T-0099", "A", "Testgrund")
        log = open(os.path.join(self.p0, "management", "decisions", "decision-log.md"),
                   encoding="utf-8").read()
        ticket = open(os.path.join(self.p0, "tickets", "T-0099.md"), encoding="utf-8").read()
        muster = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}"
        im_log = re.search(r"\| D001 \| (" + muster + r") \|", log)
        im_ticket = re.search(r"\*\*Entscheidung \(D001, via Inbox, (" + muster + r")\):\*\*",
                              ticket)
        self.assertIsNotNone(im_log, "Decision-Log ohne Uhrzeit:\n" + log)
        self.assertIsNotNone(im_ticket, "Ticket-Vermerk ohne Uhrzeit:\n" + ticket)
        self.assertEqual(im_log.group(1), im_ticket.group(1))

    def test_zeitpunkt_formatiert_uebergebene_uhr(self):
        """SWR-084: reine Formatierfunktion mit injizierter Uhr — exakter Wert prüfbar,
        ohne auf die echte Uhrzeit zu warten."""
        from datetime import datetime as _dt
        self.assertEqual(inbox.entscheidungszeitpunkt(_dt(2026, 8, 16, 7, 5)),
                         "2026-08-16 07:05")
        self.assertEqual(inbox.entscheidungszeitpunkt(_dt(2026, 12, 31, 23, 59)),
                         "2026-12-31 23:59")

    def test_historie_liest_vermerk_mit_uhrzeit(self):
        """SWR-084/042: Der Historien-Endpunkt muss den erweiterten Vermerk weiter
        erkennen — sonst wäre die Uhrzeit gegen die Entscheidungshistorie erkauft."""
        inbox.entscheide(self.wurzel, "T-0099", "A")
        treffer = [e for e in inbox.historie(self.wurzel)["historie"] if e["id"] == "T-0099"]
        self.assertEqual(len(treffer), 1)
        self.assertRegex(treffer[0]["entscheidung"], r"D001, via Inbox, \d{4}-\d{2}-\d{2} \d{2}:\d{2}")

    def test_alte_eintraege_ohne_uhrzeit_bleiben_gueltig(self):
        """SWR-084: Bestandszeilen tragen nur ein Datum — sie dürfen weder die
        D-ID-Vergabe noch die Historie stören (append-only, kein Umschreiben)."""
        log_pfad = os.path.join(self.p0, "management", "decisions", "decision-log.md")
        with open(log_pfad, "a", encoding="utf-8") as f:
            f.write("| D001 | 2026-08-15 | Mensch (E. John, via Inbox) | **X** | — | — | T-0001 |\n")
        e = inbox.entscheide(self.wurzel, "T-0099", "A")
        self.assertEqual(e["entscheidung"], "D002")  # zählt über die alte Zeile hinweg
        log = open(log_pfad, encoding="utf-8").read()
        self.assertIn("| D001 | 2026-08-15 |", log)  # unverändert stehen geblieben
        self.assertRegex(log, r"\| D002 \| \d{4}-\d{2}-\d{2} \d{2}:\d{2} \|")

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

    def test_briefkasten_erkennt_die_ueberschrift_der_sessions(self):
        """B054: Die Antwort-Überschrift, die die Routine-Sessions tatsächlich schreiben,
        muss erkannt werden — nicht nur die Fassung, die der Test selbst erzeugt.

        Gegenprobe zum Altstand: dort trennte ein exaktes Muster
        `## Antwort (Team, JJJJ-MM-TT)`; die Sessions schreiben
        `## Antwort des Teams (Routine-Session, JJJJ-MM-TT HH:MM)`. Folge war kein
        Fehler, sondern ein stiller: `antwort` blieb leer und die vollständige
        Team-Antwort stand im **Nachrichtenblock** — die Chat-Ansicht zeigte Frage und
        Antwort ununterscheidbar. Verifiziert: SWR-050."""
        from backend import briefkasten
        faelle = [
            ("## Antwort (Team, 2026-08-15)", "2026-08-15"),
            ("## Antwort des Teams (Routine-Session, 2026-08-16 20:35)", "2026-08-16 20:35"),
            ("## Antwort des Teams (Routine-Session, 2026-08-16)", "2026-08-16"),
        ]
        for kopf, datum in faelle:
            with self.subTest(kopf=kopf):
                nachricht, antwort, gelesen = briefkasten.spalte_antwort(
                    "Meine Frage.\n\n" + kopf + "\n\nDie Antwort.\n\n## Beleg\n\nTabelle.")
                self.assertEqual(nachricht, "Meine Frage.")
                self.assertIn("Die Antwort.", antwort)
                self.assertIn("## Beleg", antwort,
                              "alles unter der ersten Antwort-Überschrift gehört zur Antwort")
                self.assertEqual(gelesen, datum)
        # Ohne Antwort bleibt die Nachricht unangetastet und die Antwort leer.
        self.assertEqual(briefkasten.spalte_antwort("Nur eine Frage."),
                         ("Nur eine Frage.", "", ""))
        # Nur die *erste* Überschrift trennt — eine zweite bleibt Teil der Antwort.
        _, antwort, _ = briefkasten.spalte_antwort(
            "Frage.\n\n## Antwort (Team, 2026-08-15)\n\nEins.\n\n"
            "## Antwort des Teams (Routine-Session, 2026-08-16 20:35)\n\nZwei.")
        self.assertIn("Eins.", antwort)
        self.assertIn("Zwei.", antwort)

    def test_briefkasten_antwort_steht_nicht_im_nachrichtenblock(self):
        """B054, der Test der den Schaden benennt: Gegen den Altstand landet die
        Team-Antwort **in `nachricht`** — genau das, was die Chat-Ansicht dann als
        eine einzige Nachricht des Menschen darstellt (`app.js`: `if (b.antwort)`).
        Geprüft wird über den echten Lesepfad `liste()`. Verifiziert: SWR-050."""
        from backend import briefkasten
        briefkasten.sende(self.wurzel, "p0", "Wer arbeitet an dem Task?")
        pfad = os.path.join(self.wurzel, "p0", "management", "briefkasten", "N-0001.md")
        text = open(pfad, encoding="utf-8").read().replace("status: offen", "status: beantwortet")
        open(pfad, "w", encoding="utf-8", newline="\n").write(
            text + "\n## Antwort des Teams (Routine-Session, 2026-08-16 20:35)\n\n"
                   "**Kurz:** Das Board kann das heute nicht sagen.\n")
        brief = briefkasten.liste(self.wurzel, "p0")["briefe"][0]
        self.assertEqual(brief["nachricht"], "Wer arbeitet an dem Task?",
                         "die Antwort des Teams darf nicht im Nachrichtenblock stehen")
        self.assertIn("Das Board kann das heute nicht sagen", brief["antwort"])
        self.assertEqual(brief["antwort_datum"], "2026-08-16 20:35")

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

    def test_navigation_endpunkt(self):
        """/api/navigation liefert die Kopfbereichs-Gruppen — dieselbe Menge wie das
        Cockpit, abgeschlossene Projekte getrennt. Verifiziert: SWR-082."""
        _p1_dazu(self.wurzel)
        n = self._get("/api/navigation")
        namen = [e["projekt"] for g in n["gruppen"] for e in g["eintraege"]] + \
                [e["projekt"] for e in n["weitere"]]
        self.assertEqual(sorted(namen), self._get("/api/projekte")["projekte"])
        self.assertEqual(n["anzahl_aktiv"] + n["anzahl_weitere"], len(namen))
        for g in n["gruppen"]:
            self.assertTrue(g["eintraege"])  # leere Gruppen werden nicht ausgeliefert
            self.assertTrue(g["name"])

    def test_unbekanntes_projekt_404(self):
        """Unbekannte Projektnamen liefern 404 statt Serverfehler. Verifiziert: SWR-025."""
        try:
            self._get("/api/board?projekt=nix")
            self.fail("404 erwartet")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)


class VerbindungsabbruchTest(unittest.TestCase):
    """platform/N-0002: Legt die Gegenseite auf, ist das Normalbetrieb — eine
    Logzeile statt eines Tracebacks. Echte Fehler bleiben sichtbar."""

    def test_abbruch_erkannt(self):
        for fehler in (ConnectionResetError(10054, "vom Remotehost geschlossen"),
                       ConnectionAbortedError(), BrokenPipeError()):
            self.assertTrue(server.verbindungsabbruch(fehler), repr(fehler))

    def test_echte_fehler_nicht_als_abbruch(self):
        for fehler in (ValueError("kaputt"), OSError("Platte voll"),
                       KeyError("x"), TimeoutError()):
            self.assertFalse(server.verbindungsabbruch(fehler), repr(fehler))

    def test_handler_verwirft_abbruch_mit_einer_zeile(self):
        """handle_one_request fängt den Abbruch, schließt die Verbindung und
        protokolliert eine Zeile — der Traceback aus N-0002 entfällt."""
        zeilen = []

        class Handler(server.Api):
            protokoll = staticmethod(zeilen.append)

            def __init__(self):  # kein echter Socket nötig
                self.client_address = ("192.168.178.164", 51942)
                self.close_connection = False

        h = Handler()
        original = server.BaseHTTPRequestHandler.handle_one_request
        server.BaseHTTPRequestHandler.handle_one_request = \
            lambda self: (_ for _ in ()).throw(ConnectionResetError(10054, "weg"))
        try:
            self.assertIsNone(h.handle_one_request())
        finally:
            server.BaseHTTPRequestHandler.handle_one_request = original
        self.assertTrue(h.close_connection)
        self.assertEqual(len(zeilen), 1)
        self.assertIn("192.168.178.164", zeilen[0])
        self.assertIn("ConnectionResetError", zeilen[0])
        self.assertIn("kein Fehler", zeilen[0])

    def test_handler_laesst_echte_fehler_durch(self):
        """Ein echter Fehler wird nicht verschluckt — sonst würde die Beruhigung
        des Logs künftige Befunde verstecken."""
        class Handler(server.Api):
            protokoll = staticmethod(lambda _: None)

            def __init__(self):
                self.client_address = ("127.0.0.1", 1)
                self.close_connection = False

        h = Handler()
        original = server.BaseHTTPRequestHandler.handle_one_request
        server.BaseHTTPRequestHandler.handle_one_request = \
            lambda self: (_ for _ in ()).throw(ValueError("kaputt"))
        try:
            with self.assertRaises(ValueError):
                h.handle_one_request()
        finally:
            server.BaseHTTPRequestHandler.handle_one_request = original

    def test_zaehler_wird_auch_bei_abbruch_freigegeben(self):
        """Der Ruhe-Zähler der Neustart-Wache (SWR-073) darf nach einem Abbruch
        nicht hängen bleiben — sonst startet der Server nie wieder selbst neu."""
        class Handler(server.Api):
            protokoll = staticmethod(lambda _: None)

            def __init__(self):
                self.client_address = ("192.168.178.164", 2)
                self.close_connection = False

        original = server.BaseHTTPRequestHandler.handle_one_request
        server.BaseHTTPRequestHandler.handle_one_request = \
            lambda self: (_ for _ in ()).throw(ConnectionResetError())
        try:
            Handler().handle_one_request()
        finally:
            server.BaseHTTPRequestHandler.handle_one_request = original
        self.assertTrue(server._laufende.leer())

    def test_serverklasse_schweigt_nur_bei_abbruch(self):
        """RuhigerServer.handle_error: still bei Abbruch, laut bei echtem Fehler."""
        gemeldet = []

        class Prueflig(server.RuhigerServer):
            def __init__(self):
                pass  # kein Socket binden

        srv = Prueflig()
        original = server.ThreadingHTTPServer.handle_error
        server.ThreadingHTTPServer.handle_error = \
            lambda self, req, adr: gemeldet.append(adr)
        try:
            try:
                raise ConnectionResetError(10054, "weg")
            except ConnectionResetError:
                srv.handle_error(None, ("192.168.178.164", 3))
            self.assertEqual(gemeldet, [])
            try:
                raise ValueError("kaputt")
            except ValueError:
                srv.handle_error(None, ("192.168.178.164", 4))
            self.assertEqual(gemeldet, [("192.168.178.164", 4)])
        finally:
            server.ThreadingHTTPServer.handle_error = original


class EindeutigeKennungTest(unittest.TestCase):
    """SWR-087 (platform/N-0003): Ticketnummern sind nur je Repo eindeutig — jede
    Ansicht liefert deshalb die vollständige Kennung `<projekt>/T-xxxx` mit."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.wurzel = _wurzel_bauen(self._tmp.name)
        _p1_dazu(self.wurzel)
        # Dieselbe Nummer in zwei Repos — genau der Fall aus dem Brief.
        p1 = os.path.join(self.wurzel, "p1")
        open(os.path.join(p1, "tickets", "T-0099.md"), "w", encoding="utf-8").write(
            TICKET_DR.replace("status: open", "status: done"))

    def tearDown(self):
        self._tmp.cleanup()

    def test_ref_ist_eine_quelle(self):
        """Die Kennung entsteht an EINER Stelle; ohne Projekt bleibt die Nummer stehen."""
        self.assertEqual(aggregation.ref("pm", "T-0002"), "pm/T-0002")
        self.assertEqual(aggregation.ref("", "T-0002"), "T-0002")

    def test_gleiche_nummer_zwei_projekte_unterscheidbar(self):
        """Board und Ticket-Detail liefern für dieselbe Nummer verschiedene Kennungen."""
        p0 = aggregation.lade_board(self.wurzel, "p0")["gruppen"]
        p1 = aggregation.lade_board(self.wurzel, "p1")["gruppen"]
        refs0 = [t["ref"] for g in p0.values() for t in g]
        refs1 = [t["ref"] for g in p1.values() for t in g]
        self.assertIn("p0/T-0099", refs0)
        self.assertIn("p1/T-0099", refs1)
        self.assertEqual(aggregation.lade_ticket(self.wurzel, "p1", "T-0099")["ref"],
                         "p1/T-0099")

    def test_cockpit_und_inbox_tragen_die_kennung(self):
        """Genau dort, wo Tickets mehrerer Projekte nebeneinanderstehen (SWR-046/027/042)."""
        c = aggregation.cockpit(self.wurzel, "p0")
        self.assertEqual([d["ref"] for d in c["offene_drs"]], ["p0/T-0099"])
        self.assertTrue(all(a["ref"].startswith("p0/") for a in c["aufgaben"]))
        self.assertEqual(sorted(e["ref"] for e in inbox.liste(self.wurzel)["inbox"]),
                         ["p0/T-0099", "p1/T-0001"])
        self.assertIn("p1/T-0099", [e["ref"] for e in inbox.historie(self.wurzel)["historie"]])


class RequirementsUeberAlleTest(unittest.TestCase):
    """SWR-085 (pm/N-0019): Requirements aller Projekte/Teams sichtbar und filterbar."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.wurzel = _wurzel_bauen(self._tmp.name)
        _p1_dazu(self.wurzel)
        for name, text in (("p0", "# SWRs p0\n\n| ID | Requirement |\n|---|---|\n| SWR-001 | x |\n"),
                           ("p1", "# SWRs p1\n")):
            ordner = os.path.join(self.wurzel, name, "requirements", "software")
            os.makedirs(ordner)
            open(os.path.join(ordner, "software-requirements.md"), "w",
                 encoding="utf-8").write(text)

    def tearDown(self):
        self._tmp.cleanup()

    def test_alle_projekte_in_einer_antwort(self):
        """`projekt=alle` sammelt über alle Projekte — der alte Code kannte nur EIN Projekt."""
        a = aggregation.lade_requirements(self.wurzel, aggregation.ALLE)
        self.assertTrue(a["sammel"])
        self.assertEqual(sorted(a["projekte"]), ["p0", "p1"])
        self.assertEqual(sorted(d["projekt"] for d in a["dateien"]), ["p0", "p1"])

    def test_herkunft_je_datei_fuer_den_filter(self):
        """Jede Datei trägt Projekt UND Gruppe — ohne die beiden ist kein Filter möglich."""
        for d in aggregation.lade_requirements(self.wurzel, aggregation.ALLE)["dateien"]:
            self.assertTrue(d["projekt"])
            self.assertTrue(d["gruppe"])
            self.assertTrue(d["tabellen"] or d["text"])

    def test_einzelprojekt_unveraendert(self):
        """Regression SWR-030: die gescopte Abfrage liefert weiterhin nur ihr Projekt."""
        a = aggregation.lade_requirements(self.wurzel, "p1")
        self.assertFalse(a["sammel"])
        self.assertEqual([d["projekt"] for d in a["dateien"]], ["p1"])
        with self.assertRaises(ValueError):
            aggregation.lade_requirements(self.wurzel, "gibtsnicht")


class ProjektPoolTest(unittest.TestCase):
    """SWR-086 (pm/N-0020): Der Projekt-Pool des PM-Teams ist im HMI sichtbar."""

    POOL = ("# Projekt-Pool\n\nEinleitung.\n\n## Team-Kandidaten\n\n"
            "| # | Kandidat | Nutzen |\n|---|---|---|\n| 1 | team-termine | Termine |\n\n"
            "## Technik-Kandidaten\n\n| # | Kandidat | Quelle |\n|---|---|---|\n"
            "| 6 | Renderer | P7-LeLe |\n")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.wurzel = _wurzel_bauen(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _pool_schreiben(self):
        ordner = os.path.join(self.wurzel, "pm", "management")
        os.makedirs(ordner)
        open(os.path.join(ordner, "projekt-pool.md"), "w", encoding="utf-8").write(self.POOL)

    def test_kandidaten_nach_kategorie(self):
        """Kategorie-Überschrift und Tabelle bleiben zusammen — Karten je Kategorie im HMI."""
        self._pool_schreiben()
        p = aggregation.lade_pool(self.wurzel)
        self.assertTrue(p["vorhanden"])
        self.assertEqual([a["titel"] for a in p["abschnitte"]],
                         ["Team-Kandidaten", "Technik-Kandidaten"])
        self.assertEqual(p["abschnitte"][0]["tabellen"][0]["zeilen"][0][1], "team-termine")

    def test_ohne_datei_keine_ausnahme(self):
        """Fehlt die Pool-Datei, meldet die API das sauber statt zu krachen."""
        p = aggregation.lade_pool(self.wurzel)
        self.assertFalse(p["vorhanden"])
        self.assertEqual(p["abschnitte"], [])
        self.assertIn("projekt-pool.md", p["quelle"])

    def test_abschnitte_ohne_tabelle_werden_uebersprungen(self):
        """Reiner Fließtext erzeugt keine leere Karte."""
        self.assertEqual(aggregation.pool_abschnitte("# X\n\n## Nur Text\n\nkeine Tabelle\n"), [])


if __name__ == "__main__":
    unittest.main()
