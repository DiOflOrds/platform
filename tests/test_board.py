"""Unit-Verifikation board.py v1 (T-0007). Ausführung: python -m unittest discover platform/tests
bzw. von der Repo-Wurzel: python -m unittest tests.test_board
"""
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import board  # noqa: E402

GUT = """---
id: {tid}
titel: "Testticket"
typ: task
prozess: sup8
rolle: cm
sprint: 1
status: {status}
prio: hoch
blocked_by: {bb}
erstellt: 2026-08-06
{extra}---

Body.
"""


def schreibe(repo, tid, status="open", bb="[]", extra=""):
    os.makedirs(os.path.join(repo, "tickets"), exist_ok=True)
    with open(os.path.join(repo, "tickets", f"{tid}.md"), "w", encoding="utf-8") as f:
        f.write(GUT.format(tid=tid, status=status, bb=bb, extra=extra))


class TestBoard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def probleme(self):
        tickets, probleme = board.lade_tickets(self.repo)
        return probleme + board.validiere_alle(tickets, self.repo, git_pruefen=False)

    def test_gutfall(self):
        """Valides Ticket passiert die Schemapruefung. Verifiziert: SWR-001."""
        schreibe(self.repo, "T-0001")
        self.assertEqual(self.probleme(), [])

    def test_pflichtfeld_fehlt(self):
        """Fehlendes Pflichtfeld wird als Fehler gemeldet. Verifiziert: SWR-001."""
        schreibe(self.repo, "T-0001")
        pfad = os.path.join(self.repo, "tickets", "T-0001.md")
        text = open(pfad, encoding="utf-8").read().replace("prio: hoch\n", "")
        open(pfad, "w", encoding="utf-8").write(text)
        self.assertTrue(any("prio" in p for p in self.probleme()))

    def test_ungueltiger_status(self):
        """Unbekannter Statuswert wird abgelehnt. Verifiziert: SWR-001."""
        schreibe(self.repo, "T-0001", status="fertig")
        self.assertTrue(any("ungültiger status" in p for p in self.probleme()))

    def test_id_dateiname_mismatch(self):
        """ID/Dateiname-Abweichung wird abgelehnt. Verifiziert: SWR-001."""
        schreibe(self.repo, "T-0001")
        os.rename(os.path.join(self.repo, "tickets", "T-0001.md"),
                  os.path.join(self.repo, "tickets", "T-0002.md"))
        self.assertTrue(any("passt nicht zum Dateinamen" in p for p in self.probleme()))

    def test_blocked_by_unbekannt(self):
        """Haengender blocked_by-Verweis wird abgelehnt. Verifiziert: SWR-003."""
        schreibe(self.repo, "T-0001", bb="[T-9999]")
        self.assertTrue(any("unbekanntes Ticket" in p for p in self.probleme()))

    def test_blocked_by_selbstverweis(self):
        """Selbstverweis in blocked_by wird abgelehnt. Verifiziert: SWR-003."""
        schreibe(self.repo, "T-0001", bb="[T-0001]")
        self.assertTrue(any("sich selbst" in p for p in self.probleme()))

    def test_blocked_ohne_blocker(self):
        """Status blocked ohne Blocker-Verweis wird abgelehnt. Verifiziert: SWR-001."""
        schreibe(self.repo, "T-0001", status="blocked")
        self.assertTrue(any("blocked erfordert" in p for p in self.probleme()))

    def test_in_review_ohne_reviewer(self):
        """in_review ohne Reviewer wird abgelehnt. Verifiziert: SWR-001."""
        schreibe(self.repo, "T-0001", status="in_review")
        self.assertTrue(any("erfordert Feld reviewer" in p for p in self.probleme()))

    def test_in_review_reviewer_ist_autor(self):
        """Reviewer == Autor wird abgelehnt. Verifiziert: SWR-001."""
        schreibe(self.repo, "T-0001", status="in_review", extra="reviewer: cm\n")
        self.assertTrue(any("nicht der Autor" in p for p in self.probleme()))

    def test_in_review_mit_reviewer_ok(self):
        """in_review mit fremdem Reviewer ist gueltig. Verifiziert: SWR-001."""
        schreibe(self.repo, "T-0001", status="in_review", extra="reviewer: pl\n")
        self.assertEqual(self.probleme(), [])

    def test_crlf_toleranz(self):
        """CRLF-Zeilenenden werden toleriert. Verifiziert: SWR-001."""
        schreibe(self.repo, "T-0001")
        pfad = os.path.join(self.repo, "tickets", "T-0001.md")
        inhalt = open(pfad, encoding="utf-8").read().replace("\n", "\r\n")
        open(pfad, "w", encoding="utf-8", newline="").write(inhalt)
        self.assertEqual(self.probleme(), [])

    def test_uebergangsmatrix(self):
        """Nur Playbook-konforme Statusuebergaenge sind erlaubt. Verifiziert: SWR-002."""
        self.assertIn("in_review", board.UEBERGAENGE["in_progress"])
        self.assertNotIn("done", board.UEBERGAENGE["open"])

    def test_mensch_tickets_ohne_uebergangspruefung(self):
        """Mensch-Tickets sind von der Uebergangspruefung ausgenommen. Verifiziert: SWR-002."""
        # Validierung mit git_pruefen=True darf für rolle=mensch nicht an
        # status_in_head scheitern (Gates dürfen z.B. open -> done springen).
        schreibe(self.repo, "T-0001")
        pfad = os.path.join(self.repo, "tickets", "T-0001.md")
        text = open(pfad, encoding="utf-8").read().replace("rolle: cm", "rolle: mensch")
        open(pfad, "w", encoding="utf-8").write(text)
        tickets, _ = board.lade_tickets(self.repo)
        # kein Git-Repo im tmp-Verzeichnis: bei mensch wird der Check übersprungen
        self.assertEqual(board.validiere_alle(tickets, self.repo, git_pruefen=True), [])

    def test_board_deterministisch(self):
        """Doppelter Lauf erzeugt byte-identisches BOARD.md. Verifiziert: SWR-004."""
        schreibe(self.repo, "T-0001", status="open")
        schreibe(self.repo, "T-0002", status="done")
        tickets, _ = board.lade_tickets(self.repo)
        b1 = board.generiere_board(tickets, stand="2026-08-06")
        b2 = board.generiere_board(tickets, stand="2026-08-06")
        self.assertEqual(b1, b2)
        self.assertIn("## open (1)", b1)
        self.assertIn("## done (1)", b1)

    def test_prio_sortierung(self):
        """Sortierung nach Status, Prio, ID ist stabil. Verifiziert: SWR-004."""
        schreibe(self.repo, "T-0001")
        schreibe(self.repo, "T-0002")
        pfad = os.path.join(self.repo, "tickets", "T-0002.md")
        text = open(pfad, encoding="utf-8").read().replace("prio: hoch", "prio: kritisch")
        open(pfad, "w", encoding="utf-8").write(text)
        tickets, _ = board.lade_tickets(self.repo)
        b = board.generiere_board(tickets, stand="2026-08-06")
        self.assertLess(b.index("T-0002"), b.index("T-0001"))

    def test_takt_wiederkehrend_sichtbar(self):
        """Takt-Aufgaben sind im Board als wiederkehrend erkennbar, einmalige als
        'einmalig'; Kopfzeile zählt sie. Verifiziert: SWR-074 (pm/N-0012)."""
        schreibe(self.repo, "T-0001", extra="takt: je-session\n")
        schreibe(self.repo, "T-0002")  # einmalig, Feld fehlt
        tickets, _ = board.lade_tickets(self.repo)
        self.assertEqual(board.validiere_alle(tickets, self.repo, git_pruefen=False), [])
        b = board.generiere_board(tickets, stand="2026-08-16")
        self.assertIn("davon wiederkehrend: 1", b)
        self.assertIn("| Takt |", b)
        self.assertIn("je Session", b)
        self.assertIn("einmalig", b)

    def test_takt_ohne_feld_unveraendert(self):
        """Ohne takt-Feld bleibt alles wie bisher — keine Kopfzeilen-Zusatzangabe.
        Verifiziert: SWR-074."""
        schreibe(self.repo, "T-0001")
        tickets, _ = board.lade_tickets(self.repo)
        b = board.generiere_board(tickets, stand="2026-08-16")
        self.assertNotIn("wiederkehrend", b)

    def test_takt_ungueltig_wird_abgelehnt(self):
        """Ein Takt außerhalb des Vokabulars ist ein Validierungsfehler.
        Verifiziert: SWR-074."""
        schreibe(self.repo, "T-0001", extra="takt: gelegentlich\n")
        tickets, _ = board.lade_tickets(self.repo)
        probleme = board.validiere_alle(tickets, self.repo, git_pruefen=False)
        self.assertTrue(any("ungültiger takt" in p for p in probleme), probleme)

    def test_offene_blocker(self):
        """Offene Blocker werden im Board ausgewiesen. Verifiziert: SWR-004."""
        schreibe(self.repo, "T-0001", status="done")
        schreibe(self.repo, "T-0002", bb="[T-0001]")
        schreibe(self.repo, "T-0003", bb="[T-0002]")
        tickets, _ = board.lade_tickets(self.repo)
        nach_id = {t["id"]: t for t in tickets}
        self.assertEqual(board.offene_blocker(nach_id["T-0002"], nach_id), [])
        self.assertEqual(board.offene_blocker(nach_id["T-0003"], nach_id), ["T-0002"])

    def test_main_check_modus(self):
        """--check validiert ohne BOARD.md zu schreiben (CI-Gate). Verifiziert: SWR-005."""
        schreibe(self.repo, "T-0001")
        rc = board.main([self.repo, "--check", "--no-git"])
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(os.path.join(self.repo, "BOARD.md")))

    def test_main_schreibt_board(self):
        """Normalmodus schreibt BOARD.md. Verifiziert: SWR-004."""
        schreibe(self.repo, "T-0001")
        rc = board.main([self.repo, "--no-git"])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(os.path.join(self.repo, "BOARD.md")))

    def test_main_fehlerfall(self):
        """Validierungsfehler liefert Exit-Code != 0. Verifiziert: SWR-005."""
        schreibe(self.repo, "T-0001", status="quatsch")
        rc = board.main([self.repo, "--no-git"])
        self.assertEqual(rc, 1)


class DecisionRequestFelderTest(unittest.TestCase):
    """T-0039: maschinenlesbare DR-Felder (optionen/frist/default) in board.py."""

    DR = """---
id: T-0001
titel: "DR"
typ: decision-request
prozess: man3
rolle: pl
sprint: 4
status: open
prio: hoch
blocked_by: []
erstellt: 2026-08-06
{felder}---

Body.
"""

    def _probleme(self, felder, tid="T-0001"):
        with tempfile.TemporaryDirectory() as repo:
            os.makedirs(os.path.join(repo, "tickets"))
            with open(os.path.join(repo, "tickets", f"{tid}.md"), "w", encoding="utf-8") as f:
                f.write(self.DR.replace("T-0001", tid).format(felder=felder))
            tickets, probleme = board.lade_tickets(repo)
            return probleme + board.validiere_alle(tickets, repo, git_pruefen=False)

    def test_gueltige_felder(self):
        """Optionen, gültige Frist und default aus optionen passieren die Prüfung. Verifiziert: SWR-001."""
        self.assertEqual(self._probleme("optionen: [A1, A2, B1]\nfrist: 2026-08-31\ndefault: A1, B1\n"), [])

    def test_ungueltige_frist(self):
        """frist ohne Datumsformat wird abgelehnt. Verifiziert: SWR-001."""
        self.assertTrue(any("frist" in p for p in self._probleme("frist: morgen\n")))

    def test_default_nicht_in_optionen(self):
        """default-Token außerhalb von optionen wird abgelehnt. Verifiziert: SWR-001."""
        self.assertTrue(any("default" in p for p in
                            self._probleme("optionen: [A1, A2]\ndefault: B9\n")))

    def test_neuer_dr_ohne_optionen_abgelehnt(self):
        """T-0051: neue decision-requests ohne optionen-Frontmatter werden abgelehnt. Verifiziert: SWR-001."""
        self.assertTrue(any("optionen" in p for p in self._probleme("")))

    def test_bestands_dr_ausgenommen(self):
        """T-0051: Bestands-DRs (T-0035/T-0041) bleiben ohne optionen gültig. Verifiziert: SWR-001."""
        self.assertEqual(self._probleme("", tid="T-0035"), [])

    def test_optionstoken_zerlegung(self):
        """Kombinationen wie 'A2, B1 + C1' werden deterministisch in Token zerlegt. Verifiziert: SWR-001."""
        self.assertEqual(board.parse_optionstoken("A2, B1 + C1"), ["A2", "B1", "C1"])
        self.assertEqual(board.parse_optionstoken(""), [])


class SetzeStatusTest(unittest.TestCase):
    """T-0062: Status-Subkommando — Übergangsprüfung, Felder, BOARD."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        schreibe(self.repo, "T-0001")

    def tearDown(self):
        self.tmp.cleanup()

    def test_gueltiger_uebergang_schreibt_ticket_und_board(self):
        """open→in_progress wird geschrieben, geändert gesetzt, BOARD regeneriert. Verifiziert: SWR-002."""
        board.setze_status(self.repo, "T-0001", "in_progress")
        text = open(os.path.join(self.repo, "tickets", "T-0001.md"), encoding="utf-8").read()
        self.assertIn("status: in_progress", text)
        self.assertIn("geändert:", text)
        self.assertTrue(os.path.exists(os.path.join(self.repo, "BOARD.md")))

    def test_unzulaessiger_uebergang_wird_abgelehnt(self):
        """open→done wird mit klarer Meldung abgelehnt, Datei unverändert. Verifiziert: SWR-002."""
        with self.assertRaises(ValueError):
            board.setze_status(self.repo, "T-0001", "done")
        self.assertIn("status: open",
                      open(os.path.join(self.repo, "tickets", "T-0001.md"), encoding="utf-8").read())

    def test_in_review_erfordert_reviewer(self):
        """in_review ohne Reviewer wird abgelehnt; mit Reviewer gesetzt. Verifiziert: SWR-002."""
        board.setze_status(self.repo, "T-0001", "in_progress")
        with self.assertRaises(ValueError):
            board.setze_status(self.repo, "T-0001", "in_review")
        board.setze_status(self.repo, "T-0001", "in_review", reviewer="qm")
        self.assertIn("reviewer: qm",
                      open(os.path.join(self.repo, "tickets", "T-0001.md"), encoding="utf-8").read())

    def test_status_cli(self):
        """CLI-Form `<repo> status T-xxxx <neu>` liefert 0/1. Verifiziert: SWR-002."""
        self.assertEqual(board.main([self.repo, "status", "T-0001", "in_progress"]), 0)
        self.assertEqual(board.main([self.repo, "status", "T-0001", "done"]), 1)


class ProjektDiscoveryTest(unittest.TestCase):
    """p9/T-0007: gemeinsame Projekt-Auflösung für Board-Werkzeuge, Preflight und Matrix."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="discovery-")
        self.addCleanup(__import__("shutil").rmtree, self.root, ignore_errors=True)

    def _projekt(self, *teile):
        pfad = os.path.join(self.root, *teile)
        os.makedirs(os.path.join(pfad, "tickets"))
        return pfad

    def test_findet_top_level_und_verschachtelte_projekte(self):
        """Projektordner in projects/ zählen wie Top-Level-Repos. Verifiziert: SWR-070."""
        self._projekt("p9")
        self._projekt("projects", "p10")
        os.makedirs(os.path.join(self.root, "nur-ein-ordner"))
        gefunden = dict(board.projekt_pfade(self.root))
        self.assertIn("p9", gefunden)
        self.assertIn("p10", gefunden)
        self.assertNotIn("nur-ein-ordner", gefunden)
        self.assertTrue(gefunden["p10"].endswith(os.path.join("projects", "p10")))

    def test_top_level_gewinnt_bei_namensgleichheit(self):
        """Gleicher Name oben und im Sammel-Repo: das Bestandsrepo bleibt maßgeblich.
        Verifiziert: SWR-070."""
        self._projekt("p9")
        self._projekt("projects", "p9")
        gefunden = dict(board.projekt_pfade(self.root))
        self.assertEqual(gefunden["p9"], os.path.join(self.root, "p9"))

    def test_fehlender_wurzelordner_ist_leer(self):
        """Eine nicht lesbare Wurzel liefert eine leere Liste statt eines Absturzes.
        Verifiziert: SWR-070."""
        self.assertEqual(board.projekt_pfade(os.path.join(self.root, "gibtsnicht")), [])


class FristTest(unittest.TestCase):
    """pm/T-0030 (Brief pm/N-0025): Backlog-Tickets terminieren. Verifiziert: SWR-091."""

    HEUTE = date(2026, 8, 16)

    def test_ampel_stufen(self):
        """rot = überschritten, gelb = <= 2 Tage, gruen = später, grau = ohne Frist.
        Verifiziert: SWR-091."""
        self.assertEqual(board.frist_ampel("2026-08-15", self.HEUTE), "rot")
        self.assertEqual(board.frist_ampel("2026-08-16", self.HEUTE), "gelb")
        self.assertEqual(board.frist_ampel("2026-08-18", self.HEUTE), "gelb")
        self.assertEqual(board.frist_ampel("2026-08-19", self.HEUTE), "gruen")
        self.assertEqual(board.frist_ampel("", self.HEUTE), "grau")
        self.assertEqual(board.frist_ampel(None, self.HEUTE), "grau")
        self.assertEqual(board.frist_ampel("morgen", self.HEUTE), "grau")

    def test_ampel_ist_dieselbe_regel_wie_im_cockpit(self):
        """Gegenprobe zur Kopie, die vor SWR-091 in aggregation.cockpit stand: die
        alte Inline-Formel und board.frist_ampel müssen über einen ganzen Monat
        Tag für Tag dasselbe sagen — sonst hat die Zusammenführung die Bedeutung
        verschoben statt nur den Ort. Verifiziert: SWR-091."""
        for tag in range(1, 32):
            frist = date(2026, 8, tag)
            alt = ("rot" if frist < self.HEUTE
                   else ("gelb" if frist <= self.HEUTE + timedelta(days=2) else "gruen"))
            self.assertEqual(board.frist_ampel(frist.isoformat(), self.HEUTE), alt,
                             f"Abweichung bei {frist}")

    def test_ueberfaellig_nur_bei_offenen_tickets(self):
        """Eine gerissene Frist an einem erledigten Ticket ist Historie, kein Vorwurf.
        Verifiziert: SWR-091."""
        alt = {"frist": "2026-08-01"}
        for status in ("open", "in_analysis", "in_progress", "in_review", "blocked"):
            self.assertTrue(board.ist_ueberfaellig(dict(alt, status=status), self.HEUTE))
        for status in ("done", "rejected"):
            self.assertFalse(board.ist_ueberfaellig(dict(alt, status=status), self.HEUTE))

    def test_ohne_frist_nie_ueberfaellig(self):
        """Fristen bleiben optional — ohne Frist ist ein Ticket unterminiert, nicht
        überfällig. Verifiziert: SWR-091."""
        self.assertFalse(board.ist_ueberfaellig({"status": "open"}, self.HEUTE))
        self.assertFalse(board.ist_ueberfaellig({"status": "open", "frist": ""}, self.HEUTE))

    def test_frist_wird_auch_bei_change_request_geprueft(self):
        """Der eigentliche Befund aus pm/N-0025: bis SWR-091 galt die Datumsprüfung
        nur für decision-request — ein Tippfehler in der Frist eines CR fiel lautlos
        auf „keine Frist" zurück. Verifiziert: SWR-091."""
        repo = tempfile.mkdtemp(prefix="frist-")
        self.addCleanup(__import__("shutil").rmtree, repo, ignore_errors=True)
        for tid, typ, frist in (("T-0001", "change-request", "23.08.2026"),
                                ("T-0002", "problem", "2026-08-23"),
                                ("T-0003", "task", "2026-13-01")):
            schreibe(repo, tid, extra=f"typ_ueberschrift\nfrist: {frist}\n")
            pfad = os.path.join(repo, "tickets", f"{tid}.md")
            text = open(pfad, encoding="utf-8").read().replace(
                "typ: task", f"typ: {typ}").replace("typ_ueberschrift\n", "")
            open(pfad, "w", encoding="utf-8").write(text)
        tickets, _ = board.lade_tickets(repo)
        probleme = board.validiere_alle(tickets, git_pruefen=False)
        fristfehler = [p for p in probleme if "frist" in p]
        self.assertEqual(len(fristfehler), 2, fristfehler)
        self.assertTrue(any("T-0001" in p for p in fristfehler), fristfehler)
        self.assertTrue(any("T-0003" in p for p in fristfehler), fristfehler)
        self.assertFalse(any("T-0002" in p for p in fristfehler), fristfehler)

    def test_unmoegliches_datum_faellt_nicht_auf_grau_zurueck(self):
        """„2026-13-01" passte auf DATUM_MUSTER, ist aber kein Tag. Ohne diese Prüfung
        sähe ein falsch terminiertes Ticket wie ein unterminiertes aus — die Ampel
        fällt bei unlesbarem Datum bewusst auf „grau". Verifiziert: SWR-091."""
        self.assertFalse(board.ist_datum("2026-13-01"))
        self.assertFalse(board.ist_datum("2026-02-30"))
        self.assertFalse(board.ist_datum("23.08.2026"))
        self.assertTrue(board.ist_datum("2026-08-23"))
        self.assertEqual(board.frist_ampel("2026-13-01", self.HEUTE), "grau")

    def test_frist_am_decision_request_bleibt_geprueft(self):
        """Regression: die Prüfung ist umgezogen, nicht verschwunden.
        Verifiziert: SWR-091."""
        repo = tempfile.mkdtemp(prefix="frist-dr-")
        self.addCleanup(__import__("shutil").rmtree, repo, ignore_errors=True)
        schreibe(repo, "T-0001", extra="optionen: [A, B]\nfrist: 23.08.\ndefault: A\n")
        pfad = os.path.join(repo, "tickets", "T-0001.md")
        text = open(pfad, encoding="utf-8").read().replace("typ: task", "typ: decision-request")
        open(pfad, "w", encoding="utf-8").write(text)
        tickets, _ = board.lade_tickets(repo)
        probleme = board.validiere_alle(tickets, git_pruefen=False)
        self.assertTrue(any("frist" in p for p in probleme), probleme)


class TaktUhrzeitTest(unittest.TestCase):
    """pm/T-0032 Teil 2 (Brief pm/N-0025): echter Uhrzeit-Takt. Verifiziert: SWR-104.

    Der Takt ist KEIN dritter Scheduler, sondern eine Fälligkeitsfrage: „ist dieses
    Ticket seit seiner letzten Erledigung über seine Uhrzeit gelaufen?" — gestellt von
    der ohnehin laufenden Session (Abgrenzung aus T-0032 Teil 1).
    """

    HEUTE = date(2026, 8, 16)          # ein Sonntag
    MITTAGS = datetime(2026, 8, 16, 12, 0)
    ABENDS = datetime(2026, 8, 16, 15, 0)

    def takt_ticket(self, takt, zuletzt=None, status="open"):
        t = {"id": "T-0001", "titel": "Takt", "status": status, "takt": takt}
        if zuletzt is not None:
            t["zuletzt_erledigt"] = zuletzt
        return t

    # --- Syntax -----------------------------------------------------------------

    def test_bestandstakt_ohne_uhrzeit_unveraendert(self):
        """Der Bestand kennt keine Uhrzeit und darf davon nichts merken.
        Verifiziert: SWR-104."""
        self.assertEqual(board.parse_takt("je-session"), ("je-session", None, None))
        self.assertEqual(board.takt_klartext("je-session"), "je Session")
        self.assertEqual(board.takt_klartext("woechentlich"), "wöchentlich")
        self.assertEqual(board.takt_klartext(""), "einmalig")
        self.assertIsNone(board.takt_termin(self.takt_ticket("je-session"), self.MITTAGS))

    def test_uhrzeit_syntax_wird_zerlegt(self):
        """Verifiziert: SWR-104."""
        self.assertEqual(board.parse_takt("taeglich@14:00"), ("taeglich", None, "14:00"))
        self.assertEqual(board.parse_takt("woechentlich@Mo-14:00"), ("woechentlich", 0, "14:00"))
        self.assertEqual(board.parse_takt("woechentlich@So-07:30"), ("woechentlich", 6, "07:30"))
        self.assertEqual(board.takt_klartext("taeglich@14:00"), "täglich 14:00")
        self.assertEqual(board.takt_klartext("woechentlich@Mo-14:00"), "wöchentlich Mo 14:00")

    def test_ungueltige_uhrzeit_takte_werden_abgelehnt(self):
        """Eine Uhrzeit nur dort, wo es eine Regel dafür gibt — `monatlich@14:00` ließe
        offen, welcher Tag gemeint ist; sie zu erfinden wäre Raten (B038).
        Verifiziert: SWR-104."""
        for schlecht in ("taeglich@24:00", "taeglich@14:60", "taeglich@9:00", "taeglich@",
                         "monatlich@14:00", "jaehrlich@Mo-14:00", "woechentlich@Xx-14:00",
                         "woechentlich@14:00", "taeglich@14:00:00", "jeden-tag@14:00"):
            self.assertIsNone(board.parse_takt(schlecht), schlecht)

    def test_validierung_meldet_ungueltigen_uhrzeit_takt(self):
        """Verifiziert: SWR-104."""
        repo = tempfile.mkdtemp(prefix="takt-")
        self.addCleanup(__import__("shutil").rmtree, repo, ignore_errors=True)
        schreibe(repo, "T-0001", extra="takt: monatlich@14:00\n")
        schreibe(repo, "T-0002", extra="takt: taeglich@14:00\n")
        tickets, _ = board.lade_tickets(repo)
        probleme = board.validiere_alle(tickets, git_pruefen=False)
        self.assertTrue(any("T-0001" in p and "takt" in p for p in probleme), probleme)
        self.assertFalse([p for p in probleme if "T-0002" in p], probleme)

    def test_zuletzt_erledigt_wird_geprueft_und_braucht_einen_takt(self):
        """Ein Feld, das dasteht und nichts bewirkt, ist die stille Falschaussage aus
        B038 — `zuletzt_erledigt` ohne `takt` bezieht sich auf nichts.
        Verifiziert: SWR-104."""
        repo = tempfile.mkdtemp(prefix="takt-zul-")
        self.addCleanup(__import__("shutil").rmtree, repo, ignore_errors=True)
        schreibe(repo, "T-0001", extra="takt: taeglich@14:00\nzuletzt_erledigt: 2026-13-01\n")
        schreibe(repo, "T-0002", extra="zuletzt_erledigt: 2026-08-15 14:00\n")
        schreibe(repo, "T-0003", extra="takt: taeglich@14:00\n"
                                       "zuletzt_erledigt: 2026-08-15 14:00\n")
        tickets, _ = board.lade_tickets(repo)
        probleme = board.validiere_alle(tickets, git_pruefen=False)
        self.assertTrue(any("T-0001" in p and "zuletzt_erledigt" in p for p in probleme), probleme)
        self.assertTrue(any("T-0002" in p and "ohne takt" in p for p in probleme), probleme)
        self.assertFalse([p for p in probleme if "T-0003" in p], probleme)

    # --- Fälligkeit -------------------------------------------------------------

    def test_ohne_zuletzt_erledigt_gilt_das_ticket_als_faellig(self):
        """Fehlt der Nachweis, gilt das Ticket als nie erledigt — nie als frisch.
        Dieselbe Vorsichtsregel wie `session.stille` (B038).
        Verifiziert: SWR-104."""
        t = self.takt_ticket("taeglich@14:00")
        self.assertTrue(board.ist_takt_faellig(t, self.ABENDS))
        self.assertTrue(board.ist_takt_faellig(t, self.MITTAGS))
        self.assertEqual(board.takt_termin(t, self.ABENDS)[0], datetime(2026, 8, 16, 14, 0))
        # mittags ist der letzte 14:00-Termin der von GESTERN
        self.assertEqual(board.takt_termin(t, self.MITTAGS)[0], datetime(2026, 8, 15, 14, 0))

    def test_erledigung_nach_dem_termin_macht_frisch_bis_zum_naechsten(self):
        """Verifiziert: SWR-104."""
        t = self.takt_ticket("taeglich@14:00", "2026-08-16 14:05")
        termin, faellig = board.takt_termin(t, self.ABENDS)
        self.assertFalse(faellig)
        self.assertEqual(termin, datetime(2026, 8, 17, 14, 0))  # der nächste, nicht der alte
        # eine Minute vor dem Termin erledigt heißt: der Termin steht noch aus
        t_frueh = self.takt_ticket("taeglich@14:00", "2026-08-16 13:59")
        self.assertTrue(board.ist_takt_faellig(t_frueh, self.ABENDS))

    def test_sessionausfall_fuehrt_zu_ueberfaellig_statt_erledigt(self):
        """Die ehrliche Grenze der Umsetzung: läuft keine Session, feuert nichts — und
        die Anzeige nennt den ÜBERSPRUNGENEN Termin, statt Erledigung zu behaupten
        (Entscheidung 4 aus T-0032 Teil 1, B038). Verifiziert: SWR-104."""
        t = self.takt_ticket("taeglich@14:00", "2026-08-13 14:01")  # drei Tage her
        termin, faellig = board.takt_termin(t, self.ABENDS)
        self.assertTrue(faellig)
        self.assertEqual(termin, datetime(2026, 8, 16, 14, 0))
        self.assertEqual(board.takt_ampel(t, self.ABENDS), "rot")  # nicht „gelb, heute"

    def test_erledigung_ohne_uhrzeit_gilt_ab_tagesbeginn(self):
        """Gegenrichtung zur Frist: ein Termin ohne Uhrzeit endet am Tagesende, eine
        Erledigung ohne Uhrzeit beweist nur den Tagesbeginn. Beide Regeln zeigen in
        dieselbe Richtung — im Zweifel fällig. Verifiziert: SWR-104."""
        t = self.takt_ticket("taeglich@14:00", "2026-08-16")
        self.assertTrue(board.ist_takt_faellig(t, self.ABENDS))
        self.assertEqual(board.erledigt_moment("2026-08-16"), datetime(2026, 8, 16, 0, 0))
        self.assertEqual(board.als_moment("2026-08-16").date(), date(2026, 8, 16))
        self.assertGreater(board.als_moment("2026-08-16"), board.erledigt_moment("2026-08-16"))

    def test_wochentakt_zaehlt_den_richtigen_wochentag(self):
        """Verifiziert: SWR-104."""
        mittwoch = datetime(2026, 8, 19, 10, 0)
        t = self.takt_ticket("woechentlich@Mo-14:00")
        self.assertEqual(board.takt_termin(t, mittwoch)[0], datetime(2026, 8, 17, 14, 0))
        # am Takttag selbst, aber vor der Uhrzeit: der Termin der Vorwoche zählt
        montag_frueh = datetime(2026, 8, 17, 9, 0)
        self.assertEqual(board.takt_termin(t, montag_frueh)[0], datetime(2026, 8, 10, 14, 0))
        erledigt = self.takt_ticket("woechentlich@Mo-14:00", "2026-08-17 14:30")
        termin, faellig = board.takt_termin(erledigt, mittwoch)
        self.assertFalse(faellig)
        self.assertEqual(termin, datetime(2026, 8, 24, 14, 0))  # +7 Tage, nicht +1

    def test_geschlossenes_takt_ticket_ist_nie_faellig(self):
        """Wie bei `ist_ueberfaellig`: ein erledigtes Ticket trägt seinen Takt als
        Historie, nicht als Vorwurf. Verifiziert: SWR-104."""
        for status in ("done", "rejected"):
            t = self.takt_ticket("taeglich@14:00", status=status)
            self.assertIsNone(board.takt_termin(t, self.ABENDS))
            self.assertFalse(board.ist_takt_faellig(t, self.ABENDS))
            self.assertEqual(board.takt_ampel(t, self.ABENDS), "grau")

    # --- eine Ampelregel, zwei Quellen ------------------------------------------

    def test_ampel_kommt_aus_frist_ampel(self):
        """Entscheidung 3 aus T-0032 Teil 1: der abgeleitete Termin geht durch DIESELBE
        Funktion wie eine Frist. Eine zweite Ampelrechnung wäre B033.
        Verifiziert: SWR-104."""
        t = self.takt_ticket("taeglich@14:00", "2026-08-16 14:05")
        termin, faellig = board.takt_termin(t, self.ABENDS)
        self.assertFalse(faellig)
        self.assertEqual(board.takt_ampel(t, self.ABENDS),
                         board.frist_ampel(termin, self.ABENDS))

    def test_ampel_bleibt_fuer_datumsfristen_tag_fuer_tag_dieselbe(self):
        """Gegenprobe zur Umstellung von der Tages- auf die Momentregel: für reine
        Datumsfristen muss die neue Fassung über einen ganzen Monat exakt dasselbe
        sagen wie die alte `f < heute`-Rechnung — sonst hat SWR-104 die Bedeutung von
        SWR-091 verschoben statt sie zu erweitern. Verifiziert: SWR-104."""
        for bezug in range(1, 32):
            heute = date(2026, 8, bezug)
            for tag in range(1, 32):
                frist = date(2026, 8, tag)
                alt = ("rot" if frist < heute
                       else ("gelb" if (frist - heute).days <= 2 else "gruen"))
                self.assertEqual(board.frist_ampel(frist.isoformat(), heute), alt,
                                 f"Abweichung {frist} @ {heute}")

    def test_uhrzeit_termin_desselben_tages_ist_nachmittags_rot(self):
        """Der Kern der Umstellung: „heute 14:00" ist um 15:00 verstrichen, obwohl der
        TAG es nicht ist. Die alte Tagesregel hätte „gelb — heute fällig" gesagt und
        damit zwei Fakten zu einem gefaltet (B057). Verifiziert: SWR-104."""
        self.assertEqual(board.frist_ampel("2026-08-16 14:00", self.ABENDS), "rot")
        self.assertEqual(board.frist_ampel("2026-08-16 16:00", self.ABENDS), "gelb")
        self.assertEqual(board.frist_ampel("2026-08-16", self.ABENDS), "gelb")

    def test_tag_statt_moment_als_bezug_zaehlt_als_verstrichen(self):
        """Wird nur ein TAG als Bezug übergeben, ist die Uhrzeit unbekannt — dann gilt
        der Termin als verstrichen, nicht als frisch. Verifiziert: SWR-104."""
        self.assertEqual(board.frist_ampel("2026-08-16 14:00", self.HEUTE), "rot")

    def test_board_spalte_zeigt_die_uhrzeit_und_bricht_das_format_nicht(self):
        """Kein Formatwechsel am BOARD.md (B053) — dieselbe Spalte, nur mit Uhrzeit.
        Verifiziert: SWR-104."""
        basis = {"id": "T-0001", "titel": "A", "typ": "task", "rolle": "cm", "prio": "hoch",
                 "sprint": "1", "status": "open"}
        ohne = board.generiere_board([dict(basis)], stand="2026-08-16")
        mit = board.generiere_board([dict(basis, takt="taeglich@14:00")], stand="2026-08-16")
        self.assertIn("| einmalig |", ohne)
        self.assertIn("| täglich 14:00 |", mit)
        self.assertEqual(ohne.count("|"), mit.count("|"))  # gleiche Spaltenzahl


class GitAusgabeKodierungTest(unittest.TestCase):
    """platform/T-0007 — `status_in_head` liest die Git-Ausgabe fest als UTF-8, und ein
    Lesefehler wird ein BEFUND statt eines Absturzes.

    Anlass ist kein Testfall, sondern der Host: `pm/tickets/T-0042.md` trägt seit
    Sprint 3 ein „⏳" (UTF-8 `e2 8f b3`) an Byte 10338. `text=True` ohne `encoding`
    nimmt die Locale-Kodierung — auf dem Windows-Host cp1252, in der `8f` unbelegt
    ist. Der Lese-Thread von `subprocess` starb, `out.stdout` wurde `None` bei
    `returncode == 0`, und `parse_frontmatter(None)` warf einen `AttributeError`.
    Folge: `board.py` brach ab, `preflight` meldete einen Befund, `abschluss.cmd`
    brach ab — alle 15 Minuten, drei Sprints lang, ohne dass die Meldung die Datei
    oder die Ursache nannte.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        os.makedirs(os.path.join(self.repo, "tickets"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_cp1252_stellt_den_hostfehler_nach(self):
        """Die nachgestellte FALSCHE Umsetzung: dieselbe Datei über cp1252 gelesen,
        wie `text=True` es ohne `encoding` auf dem Host tut. `stdout` ist dann `None`
        bei `returncode == 0` — genau der Zustand, an dem der Wächter starb.

        Der Test belegt die URSACHE. Ohne ihn steht die Erklärung des Tickets nur da
        (L-2026-08-17h: zu jedem verworfenen Weg gehört ein Test, der ihn nachstellt).
        """
        roh = "---\nstatus: open\n---\nStand: ⏳ warten\n".encode("utf-8")
        self.assertIn(b"\x8f", roh)  # das Byte, das cp1252 nicht kennt
        with self.assertRaises(UnicodeDecodeError):
            roh.decode("cp1252")
        # ... und als UTF-8 gelesen ist derselbe Inhalt unauffällig:
        self.assertEqual(board.parse_frontmatter(roh.decode("utf-8"))[0]["status"], "open")

    def test_stdout_none_ist_befund_und_kein_absturz(self):
        """`stdout is None` bei `returncode == 0` liefert UNLESBAR — nicht `None`.

        Der Unterschied ist der Kern der Korrektur: `None` heißt „Ticket ist neu" und
        lässt die Übergangsprüfung ZU RECHT aus. Ein Lesefehler, der ebenfalls `None`
        zurückgäbe, hätte den Absturz gegen eine still übersprungene Prüfung getauscht
        — und das wäre die schlechtere Hälfte des Tauschs (B038).
        """
        class FakeErgebnis:
            returncode = 0
            stdout = None
            stderr = ""

        echt = board.subprocess.run
        board.subprocess.run = lambda *a, **k: FakeErgebnis()
        try:
            self.assertIs(board.status_in_head(self.repo, "T-0001.md"), board.UNLESBAR)
        finally:
            board.subprocess.run = echt

    def test_unlesbarer_vorgaenger_erscheint_als_befund_mit_datei(self):
        """Der Befund läuft durch den normalen Meldeweg und nennt die Datei.

        Gegen den Altstand steht hier ein `AttributeError: 'NoneType' object has no
        attribute 'replace'` — eine Meldung, die weder das Repo noch das Ticket noch
        die Kodierung nennt. Dieser Test hält fest, dass board.py stattdessen einen
        lesbaren Befund liefert und weiterläuft.
        """
        schreibe(self.repo, "T-0001", status="in_progress")
        tickets, _ = board.lade_tickets(self.repo)

        class FakeErgebnis:
            returncode = 0
            stdout = None
            stderr = ""

        echt = board.subprocess.run
        board.subprocess.run = lambda *a, **k: FakeErgebnis()
        try:
            probleme = board.validiere_alle(tickets, self.repo, git_pruefen=True)
        finally:
            board.subprocess.run = echt
        self.assertEqual(len(probleme), 1, probleme)
        self.assertIn("T-0001.md", probleme[0])
        self.assertIn("nicht lesbar", probleme[0])

    def test_fehlendes_git_bleibt_kein_befund(self):
        """Gegenprobe: `OSError` (git gar nicht installiert) heißt weiter „kein Git"
        und liefert `None`. Ohne diese Trennung würde die Korrektur auf einer Maschine
        ohne git jedes Ticket als Befund melden — eine Reparatur, die lauter ist als
        der Fehler, den sie behebt."""
        echt = board.subprocess.run

        def wirft(*a, **k):
            raise OSError("git nicht gefunden")

        board.subprocess.run = wirft
        try:
            self.assertIsNone(board.status_in_head(self.repo, "T-0001.md"))
        finally:
            board.subprocess.run = echt

    def test_echter_umlaut_ueber_git_wird_korrekt_gelesen(self):
        """Der Normalfall über den ECHTEN Git-Weg: ein Ticket mit „⏳" im Text wird
        gelesen und sein Status korrekt zurückgegeben. Verifiziert: SWR-002."""
        import subprocess as sp

        def git(*args):
            sp.run(["git", "-C", self.repo, "-c", "user.name=t", "-c", "user.email=t@t",
                    *args], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", check=True)

        git("init", "-q")
        schreibe(self.repo, "T-0001", status="open", extra="")
        pfad = os.path.join(self.repo, "tickets", "T-0001.md")
        with open(pfad, "a", encoding="utf-8") as f:
            f.write("\nStand: ⏳ warten auf den Hostlauf\n")
        git("add", "-A")
        git("commit", "-qm", "T-0001 angelegt")
        self.assertEqual(board.status_in_head(self.repo, "T-0001.md"), "open")


class SubprocessKodierungRegelTest(unittest.TestCase):
    """platform/T-0007 — die Regel gilt für den GANZEN Produktionscode, nicht nur für
    die eine Stelle, an der sie aufgefallen ist.

    Der Anlass für diesen Test steht in `preflight.py`: dort trägt `git_laeuft()` seit
    `pm/T-0024` ein `errors="replace"` samt Begründung — und die drei Nachbaraufrufe
    derselben Datei haben es nie bekommen. Eine Lehre, die nur an ihrem Fundort steht,
    schützt genau eine Zeile. Dieser Test macht aus ihr eine Regel, die von selbst
    wieder auffällt (B049: eine Kachel gelesen ist keine Abschlussmeldung).

    Testdateien sind bewusst ausgenommen: sie bauen ihre Eingaben selbst und scheitern
    laut, wenn etwas nicht dekodiert — der stille Ausfall, gegen den die Regel steht,
    kann dort nicht entstehen.
    """

    def test_kein_produktionsaufruf_liest_ohne_feste_kodierung(self):
        import re
        wurzel = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        funde = []
        for ordner, unter, dateien in os.walk(wurzel):
            unter[:] = [d for d in unter
                        if d not in (".git", "__pycache__", "node_modules", "tests")]
            for name in dateien:
                if not name.endswith(".py"):
                    continue
                pfad = os.path.join(ordner, name)
                quelle = open(pfad, encoding="utf-8").read()
                for treffer in re.finditer(
                        r"subprocess\.(run|Popen|check_output)\s*\(", quelle):
                    i = quelle.index("(", treffer.start())
                    tiefe = 0
                    for j in range(i, len(quelle)):
                        if quelle[j] == "(":
                            tiefe += 1
                        elif quelle[j] == ")":
                            tiefe -= 1
                            if tiefe == 0:
                                break
                    aufruf = quelle[treffer.start():j + 1]
                    textmodus = "text=True" in aufruf or "universal_newlines=True" in aufruf
                    if textmodus and "encoding=" not in aufruf:
                        zeile = quelle[:treffer.start()].count("\n") + 1
                        funde.append(f"{os.path.relpath(pfad, wurzel)}:{zeile}")
        self.assertEqual(funde, [], "subprocess im Textmodus ohne encoding= "
                                    "(platform/T-0007): " + ", ".join(funde))


if __name__ == "__main__":
    unittest.main()
