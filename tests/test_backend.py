"""API-Tests Backend-MVP (T-0032, T-0034). Verifiziert: SWR-020, SWR-022, SWR-023, SWR-024."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
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
        self._tmp = tempfile.TemporaryDirectory()
        self.wurzel = _wurzel_bauen(self._tmp.name)
        server.Api.protokoll = lambda *a, **k: None
        self.srv = server.start(self.wurzel, port=0)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self._tmp.cleanup()

    def _get(self, pfad):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{pfad}") as r:
            return json.loads(r.read().decode("utf-8"))

    def test_get_endpunkte(self):
        """/api/board, /api/kpi und /api/inbox liefern JSON aus der Arbeitskopie. Verifiziert: SWR-022."""
        self.assertEqual(self._get("/api/board")["anzahl"], 2)
        self.assertEqual(self._get("/api/kpi")["laeufe"], 2)
        self.assertEqual(len(self._get("/api/inbox")["inbox"]), 1)

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
        self.assertEqual(self._get("/api/inbox")["inbox"][0]["id"], "T-0099")

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
