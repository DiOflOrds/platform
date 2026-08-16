# -*- coding: utf-8 -*-
"""P10 Sprint 1 (ADR-007): Ticket-Editor als zweiter Schreibpfad.

Verifiziert SWR-077 (Editor + Validierung wie board.py), SWR-078 (Commit +
BOARD.md + Rücknahme), SWR-079 (Labels), SWR-080 (Konflikterkennung),
SWR-081 (PIN nur beim Schreiben + Historie im Ticket).
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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import board  # noqa: E402
from backend import server, tickets  # noqa: E402

TICKET = """---
id: T-0100
titel: "Erste Aufgabe"
typ: task
prozess: swe3
rolle: dev
sprint: 1
status: open
prio: mittel
blocked_by: []
erstellt: 2026-08-16
---

## Ziel

Etwas tun.
"""

TICKET_FERTIG = TICKET.replace("T-0100", "T-0101").replace(
    "status: open", "status: done").replace("Erste Aufgabe", "Erledigte Aufgabe")


def _repo_bauen(wurzel):
    p = os.path.join(wurzel, "p0")
    os.makedirs(os.path.join(p, "tickets"))
    open(os.path.join(p, "tickets", "T-0100.md"), "w", encoding="utf-8").write(TICKET)
    open(os.path.join(p, "tickets", "T-0101.md"), "w", encoding="utf-8").write(TICKET_FERTIG)
    tl, _ = board.lade_tickets(p)
    open(os.path.join(p, "BOARD.md"), "w", encoding="utf-8").write(board.generiere_board(tl))
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"]):
        subprocess.run(["git", "-C", p] + args, check=True, capture_output=True)
    return p


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wurzel = self.tmp.name
        self.repo = _repo_bauen(self.wurzel)

    def tearDown(self):
        self.tmp.cleanup()

    def fp(self, tid="T-0100"):
        text, _ = board.lies_ticket(self.repo, tid)
        return board.fingerprint(text)

    def text(self, tid="T-0100"):
        return open(board.ticket_pfad(self.repo, tid), encoding="utf-8").read()

    def commits(self):
        lauf = subprocess.run(["git", "-C", self.repo, "log", "--pretty=%an|%s"],
                              capture_output=True, text=True)
        return lauf.stdout.strip().splitlines()


class TestEditorRegeln(Basis):
    """SWR-077: Der Editor prüft mit denselben Regeln wie die Skript-Route."""

    def test_gueltige_aenderung_wird_uebernommen(self):
        """SWR-077: Titel, Prio und Status ändern sich; BOARD.md zieht mit."""
        erg = board.aktualisiere(self.repo, "T-0100",
                                 {"titel": "Neuer Titel", "prio": "hoch",
                                  "status": "in_progress"},
                                 erwarteter_fingerprint=self.fp())
        self.assertEqual(erg["status"], "in_progress")
        self.assertIn("titel", erg["geaendert"])
        self.assertIn('titel: "Neuer Titel"', self.text())
        self.assertIn("Neuer Titel", open(os.path.join(self.repo, "BOARD.md"),
                                          encoding="utf-8").read())

    def test_ungueltiger_typ_wird_mit_board_meldung_abgelehnt(self):
        """SWR-077: Unsinn erzeugt exakt die Meldung, die auch board.py ausgibt."""
        with self.assertRaises(ValueError) as ctx:
            board.aktualisiere(self.repo, "T-0100", {"typ": "quatsch"},
                               erwarteter_fingerprint=self.fp())
        self.assertIn("ungültiger typ: quatsch", str(ctx.exception))
        self.assertIn("typ: task", self.text())  # nichts geschrieben

    def test_unzulaessiger_status_uebergang(self):
        """SWR-077: open -> done gibt es nicht (Playbook Kap. 5)."""
        with self.assertRaises(ValueError) as ctx:
            board.aktualisiere(self.repo, "T-0100", {"status": "done"},
                               erwarteter_fingerprint=self.fp())
        self.assertIn("unzulässiger Status-Übergang: open -> done", str(ctx.exception))

    def test_in_review_ohne_reviewer_abgelehnt(self):
        """SWR-077: Pflichtfeld-Logik der Skript-Route gilt auch hier."""
        board.aktualisiere(self.repo, "T-0100", {"status": "in_progress"},
                           erwarteter_fingerprint=self.fp())
        with self.assertRaises(ValueError) as ctx:
            board.aktualisiere(self.repo, "T-0100", {"status": "in_review"},
                               erwarteter_fingerprint=self.fp())
        self.assertIn("in_review erfordert Feld reviewer", str(ctx.exception))

    def test_nicht_editierbares_feld_wird_abgelehnt(self):
        """SWR-077: id/erstellt/blocked_by gehören der Skript-Route, nicht dem Formular."""
        with self.assertRaises(ValueError) as ctx:
            board.aktualisiere(self.repo, "T-0100", {"id": "T-0999"},
                               erwarteter_fingerprint=self.fp())
        self.assertIn("nicht über das HMI änderbar", str(ctx.exception))

    def test_erledigtes_ticket_ist_archiv(self):
        """SWR-077: An `done` lässt sich nichts ändern — außer der Wiedereröffnung."""
        with self.assertRaises(ValueError) as ctx:
            board.aktualisiere(self.repo, "T-0101", {"titel": "Umbenannt"},
                               erwarteter_fingerprint=self.fp("T-0101"))
        self.assertIn("Archiv", str(ctx.exception))
        erg = board.aktualisiere(self.repo, "T-0101", {"status": "in_progress"},
                                 erwarteter_fingerprint=self.fp("T-0101"))
        self.assertEqual(erg["status"], "in_progress")

    def test_leere_aenderung_wird_abgelehnt(self):
        """SWR-077: Ein Speichern ohne Änderung erzeugt keinen Leer-Commit."""
        with self.assertRaises(ValueError) as ctx:
            board.aktualisiere(self.repo, "T-0100", {"titel": "Erste Aufgabe"},
                               erwarteter_fingerprint=self.fp())
        self.assertIn("keine Änderung", str(ctx.exception))

    def test_fliesstext_wird_ersetzt(self):
        """SWR-077: Der Fließtext ist Teil des Editors."""
        board.aktualisiere(self.repo, "T-0100", {}, body="## Ziel\n\nEtwas anderes.",
                           erwarteter_fingerprint=self.fp())
        self.assertIn("Etwas anderes.", self.text())
        self.assertNotIn("Etwas tun.", self.text())


class TestLabels(Basis):
    """SWR-079: freie Mehrfach-Labels mit Validierung und Board-Filter."""

    def test_labels_setzen_und_lesen(self):
        board.aktualisiere(self.repo, "T-0100", {"labels": ["team-pm", "neues-projekt"]},
                           erwarteter_fingerprint=self.fp())
        self.assertIn("labels: [team-pm, neues-projekt]", self.text())
        _, t = board.lies_ticket(self.repo, "T-0100")
        self.assertEqual(board.parse_liste(t.get("labels")), ["team-pm", "neues-projekt"])

    def test_ungueltiges_label_abgelehnt(self):
        """SWR-079: Zeichen, die das Frontmatter-Format sprengen, sind gesperrt."""
        with self.assertRaises(ValueError) as ctx:
            board.aktualisiere(self.repo, "T-0100", {"labels": ["kaputt|pipe"]},
                               erwarteter_fingerprint=self.fp())
        self.assertIn("ungültiges label", str(ctx.exception))

    def test_zu_viele_labels_abgelehnt(self):
        with self.assertRaises(ValueError) as ctx:
            board.aktualisiere(self.repo, "T-0100",
                               {"labels": ["l%d" % i for i in range(board.LABEL_MAX + 1)]},
                               erwarteter_fingerprint=self.fp())
        self.assertIn("zu viele labels", str(ctx.exception))

    def test_ticket_ohne_labelfeld_bleibt_gueltig(self):
        """SWR-079: Das Feld ist optional — Bestandstickets ändern sich nicht."""
        tl, probleme = board.lade_tickets(self.repo)
        self.assertEqual(probleme + board.validiere_alle(tl, self.repo, git_pruefen=False), [])

    def test_labels_leeren_entfernt_die_zeile(self):
        board.aktualisiere(self.repo, "T-0100", {"labels": ["a"]},
                           erwarteter_fingerprint=self.fp())
        board.aktualisiere(self.repo, "T-0100", {"labels": []},
                           erwarteter_fingerprint=self.fp())
        self.assertNotIn("labels:", self.text())

    def test_board_api_liefert_labels(self):
        """SWR-079: Die Board-Ansicht bekommt die Labels als Liste (Filter im HMI)."""
        from backend import aggregation
        board.aktualisiere(self.repo, "T-0100", {"labels": ["bug", "team-pm"]},
                           erwarteter_fingerprint=self.fp())
        b = aggregation.lade_board(self.wurzel, "p0")
        treffer = [t for t in b["gruppen"]["open"] if t["id"] == "T-0100"][0]
        self.assertEqual(treffer["labels"], ["bug", "team-pm"])


class TestKonflikt(Basis):
    """SWR-080: Fingerabdruck statt stillem Überschreiben."""

    def test_unveraenderte_datei_schreibt(self):
        erg = board.aktualisiere(self.repo, "T-0100", {"prio": "hoch"},
                                 erwarteter_fingerprint=self.fp())
        self.assertEqual(erg["geaendert"], ["prio"])

    def test_veraenderte_datei_wird_abgelehnt(self):
        """SWR-080: Die Routine-Session war schneller — nichts wird überschrieben."""
        alt = self.fp()
        board.setze_status(self.repo, "T-0100", "in_progress")  # Skript-Route dazwischen
        with self.assertRaises(board.KonfliktFehler) as ctx:
            board.aktualisiere(self.repo, "T-0100", {"prio": "hoch"},
                               erwarteter_fingerprint=alt)
        self.assertIn("Routine-Session", str(ctx.exception))
        self.assertIn("prio: mittel", self.text())

    def test_konflikt_ist_eigener_fehlertyp(self):
        """SWR-080: 409 statt 400 — es ist kein Eingabefehler des Menschen."""
        self.assertTrue(issubclass(board.KonfliktFehler, ValueError))

    def test_fingerprint_ignoriert_zeilenenden(self):
        """SWR-080: CRLF allein ist kein Konflikt."""
        self.assertEqual(board.fingerprint("a\r\nb"), board.fingerprint("a\nb"))

    def test_backend_meldet_409(self):
        alt = self.fp()
        board.setze_status(self.repo, "T-0100", "in_progress")
        with self.assertRaises(tickets.TicketFehler) as ctx:
            tickets.speichere(self.wurzel, "p0", "T-0100",
                              {"fingerprint": alt, "felder": {"prio": "hoch"}})
        self.assertEqual(ctx.exception.code, 409)

    def test_backend_verlangt_fingerprint(self):
        with self.assertRaises(tickets.TicketFehler) as ctx:
            tickets.speichere(self.wurzel, "p0", "T-0100", {"felder": {"prio": "hoch"}})
        self.assertEqual(ctx.exception.code, 400)


class TestCommit(Basis):
    """SWR-078: ein Commit je Änderung, BOARD.md mit, Rücknahme bei Fehlschlag."""

    def test_commit_mit_herkunft_und_board(self):
        erg = tickets.speichere(self.wurzel, "p0", "T-0100",
                                {"fingerprint": self.fp(), "felder": {"prio": "hoch"}})
        self.assertTrue(erg["ok"])
        letzte = self.commits()[0]
        self.assertTrue(letzte.startswith("Mensch via HMI|"), letzte)
        self.assertIn("T-0100", letzte)
        geaendert = subprocess.run(
            ["git", "-C", self.repo, "show", "--name-only", "--pretty=", "HEAD"],
            capture_output=True, text=True).stdout
        self.assertIn("BOARD.md", geaendert)
        self.assertIn("tickets/T-0100.md", geaendert)

    def test_abgelehnte_aenderung_committet_nichts(self):
        vorher = len(self.commits())
        with self.assertRaises(tickets.TicketFehler):
            tickets.speichere(self.wurzel, "p0", "T-0100",
                              {"fingerprint": self.fp(), "felder": {"prio": "quatsch"}})
        self.assertEqual(len(self.commits()), vorher)

    def test_gescheiterter_commit_nimmt_die_aenderung_zurueck(self):
        """SWR-078: Kein halb geschriebener Zustand — den bemerkt sonst niemand."""
        vorher_ticket, vorher_board = self.text(), open(
            os.path.join(self.repo, "BOARD.md"), encoding="utf-8").read()
        echt = subprocess.run

        def kaputt(befehl, *a, **k):
            if "commit" in befehl:
                class R:
                    returncode, stdout, stderr = 1, "", "simulierter Git-Fehler"
                return R()
            return echt(befehl, *a, **k)

        tickets.subprocess.run = kaputt
        try:
            with self.assertRaises(tickets.TicketFehler) as ctx:
                tickets.speichere(self.wurzel, "p0", "T-0100",
                                  {"fingerprint": self.fp(), "felder": {"prio": "hoch"}})
        finally:
            tickets.subprocess.run = echt
        self.assertEqual(ctx.exception.code, 503)
        self.assertEqual(self.text(), vorher_ticket)
        self.assertEqual(open(os.path.join(self.repo, "BOARD.md"),
                              encoding="utf-8").read(), vorher_board)

    def test_unbekanntes_ticket_meldet_404(self):
        with self.assertRaises(tickets.TicketFehler) as ctx:
            tickets.speichere(self.wurzel, "p0", "T-0999",
                              {"fingerprint": "x", "felder": {"prio": "hoch"}})
        self.assertEqual(ctx.exception.code, 404)


class TestHistorieUndEditorDaten(Basis):
    """SWR-081: Historie im Ticket (unabhängig von Git) + Formularzustand."""

    def test_historienzeile_wird_angehaengt(self):
        board.aktualisiere(self.repo, "T-0100", {"prio": "hoch"},
                           erwarteter_fingerprint=self.fp(), herkunft="Mensch via HMI")
        self.assertIn("**Bearbeitet (", self.text())
        self.assertIn("Mensch via HMI", self.text())
        self.assertIn("prio", self.text().split("**Bearbeitet (")[1])

    def test_historie_sammelt_sich(self):
        board.aktualisiere(self.repo, "T-0100", {"prio": "hoch"},
                           erwarteter_fingerprint=self.fp())
        board.aktualisiere(self.repo, "T-0100", {"rolle": "qm"},
                           erwarteter_fingerprint=self.fp())
        e = tickets.editor_daten(self.wurzel, "p0", "T-0100")
        self.assertEqual(len(e["historie"]), 2)

    def test_editor_daten_liefern_formularzustand(self):
        e = tickets.editor_daten(self.wurzel, "p0", "T-0100")
        self.assertTrue(e["bearbeitbar"])
        self.assertEqual(e["felder"]["titel"], "Erste Aufgabe")
        self.assertEqual(e["felder"]["labels"], [])
        self.assertEqual(e["fingerprint"], self.fp())
        self.assertIn("in_progress", e["vokabular"]["status_moeglich"])
        self.assertNotIn("done", e["vokabular"]["status_moeglich"])
        self.assertEqual(e["ref"], "p0/T-0100")

    def test_editor_bietet_den_eigenen_uhrzeit_takt_an(self):
        """SWR-104/B059: Das Formular baut aus `vokabular.takte` ein `<select>`. Ein
        Uhrzeit-Takt steht nicht im festen Vokabular — ohne den eigenen Wert in der
        Liste fiele der Browser auf „einmalig" zurück, und das Speichern eines
        BELIEBIGEN anderen Feldes hätte den Takt stillschweigend gelöscht (B051/B038).
        Neue Uhrzeit-Takte bietet das HMI bewusst nicht an; es erhält sie nur."""
        board.aktualisiere(self.repo, "T-0100", {"takt": "taeglich@14:00"},
                           erwarteter_fingerprint=self.fp())
        e = tickets.editor_daten(self.wurzel, "p0", "T-0100")
        self.assertEqual(e["felder"]["takt"], "taeglich@14:00")
        self.assertIn("taeglich@14:00", e["vokabular"]["takte"])
        self.assertEqual(e["vokabular"]["takte"]["taeglich@14:00"], "täglich 14:00")
        # ein Bestandsticket ohne Uhrzeit-Takt bekommt kein zusätzliches Angebot
        f = tickets.editor_daten(self.wurzel, "p0", "T-0101")
        self.assertEqual(set(f["vokabular"]["takte"]), set(board.TAKTE))

    def test_editor_daten_erklaeren_archiv(self):
        e = tickets.editor_daten(self.wurzel, "p0", "T-0101")
        self.assertFalse(e["bearbeitbar"])
        self.assertIn("Archiv", e["grund"])

    def test_zeitpunkt_hat_eine_quelle(self):
        """SWR-081/084: Entscheidungen und Ticket-Änderungen datieren identisch."""
        from backend import inbox
        import datetime as dt
        jetzt = dt.datetime(2026, 8, 16, 10, 5)
        self.assertEqual(inbox.entscheidungszeitpunkt(jetzt), board.zeitpunkt(jetzt))
        self.assertEqual(board.zeitpunkt(jetzt), "2026-08-16 10:05")


class TestApiSchutz(unittest.TestCase):
    """SWR-081: Schreiben braucht die PIN (ADR-006), Lesen nicht."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repo = _repo_bauen(cls.tmp.name)
        server.Api.protokoll = lambda *a, **k: None
        cls.server = server.start(cls.tmp.name, "127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def hole(self, pfad):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{pfad}") as r:
            return json.loads(r.read().decode("utf-8"))

    def test_editor_lesen_ohne_pin(self):
        d = self.hole("/api/ticket/editor?projekt=p0&id=T-0100")
        self.assertEqual(d["id"], "T-0100")
        self.assertTrue(d["fingerprint"])

    def test_editor_unbekanntes_ticket_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.hole("/api/ticket/editor?projekt=p0&id=T-0999")
        self.assertEqual(ctx.exception.code, 404)

    def test_schreiben_ueber_api_localhost(self):
        """SWR-078/081: localhost darf ohne PIN schreiben (ADR-006, abwärtskompatibel)."""
        d = self.hole("/api/ticket/editor?projekt=p0&id=T-0100")
        anfrage = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/ticket", method="POST",
            data=json.dumps({"projekt": "p0", "id": "T-0100",
                             "fingerprint": d["fingerprint"],
                             "felder": {"labels": ["ueber-api"]}}).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(anfrage) as r:
            erg = json.loads(r.read().decode("utf-8"))
        self.assertTrue(erg["ok"])
        self.assertEqual(erg["geaendert"], ["labels"])

    def test_schreibschutz_greift_fuer_fremde_adressen(self):
        """SWR-081: Ohne MC_PIN sind Remote-Schreibzugriffe gesperrt (sicherer Default)."""
        alt = os.environ.pop("MC_PIN", None)
        try:
            self.assertIsNotNone(server.schreibschutz_pruefen("192.168.1.50", None))
            self.assertIsNone(server.schreibschutz_pruefen("127.0.0.1", None))
        finally:
            if alt is not None:
                os.environ["MC_PIN"] = alt


if __name__ == "__main__":
    unittest.main()
