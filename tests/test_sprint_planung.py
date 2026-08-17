"""Unit-Verifikation Sprintplanung (SWR-106, pm/T-0041).

Auftraggeberwunsch 2026-08-17: *„terminierung bitte nicht auf datum, sondern auf sprint.
Aktuell wird ASPICE Routine session jede stunde ausgeführt. Das ist ein Sprint. Alle
Aufgaben müssen auf die Sprint's aufgeplant werden"*

Ausführung: python -m unittest discover platform/tests
"""
import os
import sys
import tempfile
import unittest
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import board  # noqa: E402
import sprint_register  # noqa: E402
from backend import sprint  # noqa: E402


class RegisterTest(unittest.TestCase):
    """Der Zähler. Verifiziert: SWR-106."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def test_leeres_register_ist_sprint_null(self):
        """Vor dem ersten Lauf gibt es keinen Sprint — und die Antwort ist 0, nicht 1.
        Ein Zähler, der ungefragt bei 1 beginnt, behauptet einen Lauf, den es nicht
        gab. Verifiziert: SWR-106."""
        self.assertEqual(sprint_register.aktuell(self.root), 0)
        self.assertEqual(sprint_register.lies(self.root), [])

    def test_beginne_zaehlt_hoch(self):
        """⚠⚠ Diese Zusicherung hat bis Sprint 15 das FEHLVERHALTEN zugesichert.

        Ihre alte Fassung lautete `beginne("lauf-a")` -> 1, `beginne("lauf-b")` -> 2 —
        **ohne** dass „lauf-a" dazwischen endete. Sie hat damit wörtlich verlangt, was
        `platform/T-0013` als Schaden beschreibt: einen zweiten Sprint zu eröffnen,
        während der erste noch schreibt. Der Schaden ist am 2026-08-17 zweimal
        eingetreten, beim zweiten Mal mit einer doppelt vergebenen Anforderungsnummer.

        > **Eine Prüfung, die den Fehler zusichert, ist schlimmer als keine: sie
        > verteidigt ihn gegen jede Änderung.** Sechste Gestalt der Familie
        > (SWR-122/125/128/131/136).

        Die *Absicht* der Zusicherung war der Zähler und nicht die Überlappung — deshalb
        wird sie nicht gelöscht, sondern um das `beende()` ergänzt, das der reguläre
        Ablauf ohnehin ausführt. Die Überlappung selbst ist ab jetzt in
        `test_sprint_register_ende.UeberlappungTest` zugesichert, und zwar als
        **Abweisung**. Verifiziert: SWR-106, SWR-136.
        """
        self.assertEqual(sprint_register.beginne(self.root, "lauf-a"), 1)
        sprint_register.beende(self.root, "lauf-a")
        self.assertEqual(sprint_register.beginne(self.root, "lauf-b"), 2)
        self.assertEqual(sprint_register.aktuell(self.root), 2)

    def test_derselbe_lauf_zaehlt_nicht_zweimal(self):
        """Der Kern der Idempotenz: ein Lauf, der nach einem Fehler wiederholt startet
        oder `beginne()` zweimal aufruft, darf den Zähler nicht bewegen. Die Identität
        des Laufs ist ein Fakt, den er nennt — kein Zeitfenster, aus dem man sie
        erschließt. Verifiziert: SWR-106."""
        self.assertEqual(sprint_register.beginne(self.root, "lauf-a"), 1)
        self.assertEqual(sprint_register.beginne(self.root, "lauf-a"), 1)
        self.assertEqual(sprint_register.beginne(self.root, "lauf-a"), 1)
        self.assertEqual(len(sprint_register.lies(self.root)), 1)

    def test_beginne_ohne_kennung_wird_abgelehnt(self):
        for schlecht in ("", "   ", None):
            with self.assertRaises(ValueError):
                sprint_register.beginne(self.root, schlecht)

    def test_kaputte_zeile_setzt_den_zaehler_nicht_zurueck(self):
        """Eine unlesbare Zeile darf den Zähler nicht anhalten — und erst recht nicht
        bei 0 neu beginnen lassen, denn dann bekäme der nächste Lauf eine Nummer, die
        schon vergeben ist. Verifiziert: SWR-106."""
        sprint_register.beginne(self.root, "a")
        sprint_register.beende(self.root, "a")   # SWR-136: der Vorgänger endet
        sprint_register.beginne(self.root, "b")
        sprint_register.beende(self.root, "b")
        pfad = sprint_register._pfad(self.root)
        with open(pfad, "a", encoding="utf-8") as f:
            f.write("{kein json\n\n")
        self.assertEqual(sprint_register.aktuell(self.root), 2)
        self.assertEqual(sprint_register.beginne(self.root, "c"), 3)

    def test_takt_kommt_aus_dem_letzten_eintrag(self):
        sprint_register.beginne(self.root, "a", takt_min=30)
        sprint_register.beende(self.root, "a")   # SWR-136: der Vorgänger endet
        sprint_register.beginne(self.root, "b", takt_min=60)
        self.assertEqual(sprint_register.takt_minuten(self.root), 60)

    def test_zeitschaetzung_rechnet_mit_dem_takt(self):
        """Die Schätzung ist eine Schätzung — aber sie muss rechnen können.
        Verifiziert: SWR-106."""
        jetzt = datetime(2026, 8, 17, 10, 0)
        z = sprint_register.geschaetzte_zeit(5, jetzt=jetzt, jetzt_nr=1, takt_min=60)
        self.assertEqual(z, datetime(2026, 8, 17, 14, 0))
        # ein bereits vergangener Sprint liegt nicht in der Vergangenheit, sondern jetzt
        self.assertEqual(sprint_register.geschaetzte_zeit(1, jetzt=jetzt, jetzt_nr=5), jetzt)


class FeldTest(unittest.TestCase):
    """Das Ticketfeld. Verifiziert: SWR-106."""

    def test_sprintnummer_in_beiden_schreibweisen(self):
        self.assertEqual(board.parse_sprint_nr("42"), 42)
        self.assertEqual(board.parse_sprint_nr("Sprint 42"), 42)
        self.assertEqual(board.parse_sprint_nr("sprint42"), 42)
        self.assertEqual(board.parse_sprint_nr("  7 "), 7)

    def test_unscharfe_angaben_werden_abgelehnt(self):
        """„nächster Sprint" oder „bald" sind keine Planung, sondern eine Absicht —
        genau das, was die Umstellung beenden soll. Verifiziert: SWR-106."""
        for schlecht in ("bald", "nächster Sprint", "4-5", "", None, "Sprint", "-3", "4.5"):
            self.assertIsNone(board.parse_sprint_nr(schlecht), repr(schlecht))

    def test_validierung_meldet_unscharfen_wert(self):
        repo = tempfile.mkdtemp(prefix="sprintfeld-")
        self.addCleanup(__import__("shutil").rmtree, repo, ignore_errors=True)
        os.makedirs(os.path.join(repo, "tickets"))
        vorlage = ("---\nid: {tid}\ntitel: \"T\"\ntyp: task\nprozess: sup8\nrolle: cm\n"
                   "sprint: 1\nstatus: open\nprio: hoch\nblocked_by: []\n"
                   "geplant_sprint: {gs}\nerstellt: 2026-08-17\n---\n\nBody.\n")
        for tid, gs in (("T-0001", "bald"), ("T-0002", "4")):
            with open(os.path.join(repo, "tickets", f"{tid}.md"), "w", encoding="utf-8") as f:
                f.write(vorlage.format(tid=tid, gs=gs))
        tickets, _ = board.lade_tickets(repo)
        probleme = board.validiere_alle(tickets, git_pruefen=False)
        self.assertTrue(any("T-0001" in p and "geplant_sprint" in p for p in probleme), probleme)
        self.assertFalse([p for p in probleme if "T-0002" in p], probleme)


class WiderspruchTest(unittest.TestCase):
    """Die Absicherung dafür, dass `frist` und `geplant_sprint` parallel laufen.
    Verifiziert: SWR-106."""

    HEUTE = date(2026, 8, 17)

    def ticket(self, sprint_nr, frist, status="open"):
        return {"status": status, "geplant_sprint": str(sprint_nr), "frist": frist}

    def test_sprint_nach_der_frist_wird_gemeldet(self):
        """Der Fall, den niemand von selbst bemerkt: die Frist bleibt grün, bis sie
        reißt, und die Sprintnummer bleibt plausibel, weil sie keiner gegen die Frist
        hält. Verifiziert: SWR-106."""
        w = board.sprint_widerspruch(self.ticket(200, "2026-08-18"), 1, 60, self.HEUTE)
        self.assertIsNotNone(w)
        self.assertIn("Sprint 200", w)
        self.assertIn("2026-08-18", w)

    def test_sprint_vor_der_frist_ist_kein_widerspruch(self):
        self.assertIsNone(board.sprint_widerspruch(self.ticket(3, "2026-08-18"), 1, 60, self.HEUTE))

    def test_nur_der_guenstigste_fall_zaehlt(self):
        """Gemeldet wird, was **auch bei ununterbrochenem Takt** nicht mehr passt. Ein
        Plan, der nur bei Stillstand reißt, ist kein Widerspruch, sondern ein Risiko —
        und ein Melder, der Risiken als Fehler ausgibt, erzieht zum Wegsehen.
        Verifiziert: SWR-106."""
        # 24 Sprints bei 60 Minuten = genau ein Tag: Frist morgen, Sprint 25 -> passt.
        self.assertIsNone(board.sprint_widerspruch(
            self.ticket(25, "2026-08-18"), 1, 60, self.HEUTE))
        # 49 Sprints = zwei Tage: passt nicht mehr zu einer Frist von morgen.
        self.assertIsNotNone(board.sprint_widerspruch(
            self.ticket(49, "2026-08-18"), 1, 60, self.HEUTE))

    def test_geschlossene_tickets_und_leere_felder(self):
        self.assertIsNone(board.sprint_widerspruch(
            self.ticket(200, "2026-08-18", status="done"), 1, 60, self.HEUTE))
        self.assertIsNone(board.sprint_widerspruch({"status": "open", "frist": "2026-08-18"},
                                                   1, 60, self.HEUTE))
        self.assertIsNone(board.sprint_widerspruch({"status": "open", "geplant_sprint": "9"},
                                                   1, 60, self.HEUTE))


class PlansichtTest(unittest.TestCase):
    """Die Kachel. Verifiziert: SWR-106."""

    def test_sprintnummer_ist_kein_datum_und_nie_gruen(self):
        """„Sprint 4" darf keine Datumsampel bekommen — grün hieße „Termin liegt
        komfortabel in der Zukunft", und das hat niemand zugesagt (B038).
        Verifiziert: SWR-106."""
        zustand, ampel = sprint.faellig_zustand("Sprint 4")
        self.assertEqual(zustand, sprint.ZUSTAND_NUMMER)
        self.assertEqual(ampel, "sprint")
        self.assertEqual(sprint.sprint_nummer("Sprint 4"), 4)

    def test_sprint_schlaegt_datum_in_derselben_zelle(self):
        """„Sprint 4 (bis 23.08. zugesagt)" ist eine Planung mit einer Notiz, kein
        Termin. Was zugesagt ist, steht im Feld `frist` des Tickets.
        Verifiziert: SWR-106."""
        zustand, _ = sprint.faellig_zustand("Sprint 4 (2026-08-23 zugesagt)")
        self.assertEqual(zustand, sprint.ZUSTAND_NUMMER)

    def test_takt_dauerlaeufer_sehen_nicht_ungeplant_aus(self):
        """Ohne dieses Muster fielen die fünf Takt-Tickets in „unbekannt" und die
        Kachel meldete sie als planlos — obwohl sie die am festesten geplanten
        Aufgaben der Organisation sind. Verifiziert: SWR-106."""
        for text in ("jeder Sprint", "jedem Sprint", "je Sprint", "je Session", "je Lauf"):
            zustand, ampel = sprint.faellig_zustand(text)
            self.assertEqual(zustand, sprint.ZUSTAND_SPRINT, text)
            self.assertEqual(ampel, "sprint", text)

    def test_horizont_trennt_fest_von_warteschlange(self):
        """Verifiziert: SWR-106."""
        self.assertEqual(sprint.horizont(1, 1), "jetzt")
        self.assertEqual(sprint.horizont(2, 1), "fest")
        self.assertEqual(sprint.horizont(3, 1), "fest")
        self.assertEqual(sprint.horizont(4, 1), "warteschlange")
        self.assertEqual(sprint.horizont(150, 1), "warteschlange")
        self.assertEqual(sprint.horizont(None, 1), "")
        self.assertEqual(sprint.horizont(4, 0), "")  # ohne laufenden Sprint keine Aussage

    def test_zaehler_trennt_fest_und_warteschlange(self):
        """Zwei Zahlen statt einer Summe: dieselbe Nummer, verschiedene
        Verbindlichkeit. Sie zusammenzuwerfen wäre B053. Verifiziert: SWR-106."""
        tabelle = {"spalten": ["Aufgabe", "Rolle", "Fällig", "Status", "Grund"],
                   "zeilen": [["a/T-0001", "pl", "dieser Sprint", "offen", ""],
                              ["a/T-0002", "pl", "Sprint 2", "offen", ""],
                              ["a/T-0003", "pl", "Sprint 3", "offen", ""],
                              ["a/T-0004", "pl", "Sprint 9", "offen", ""],
                              ["a/T-0005", "pl", "jeder Sprint", "erfüllt", ""]]}
        z = sprint.zaehler(sprint.zeilen(tabelle, date(2026, 8, 17), jetzt_nr=1))
        self.assertEqual(z["dieser_sprint"], 2)      # „dieser Sprint" + Takt-Dauerläufer
        self.assertEqual(z["auf_sprint"], 3)
        self.assertEqual(z["fest_geplant"], 2)       # Sprint 2 und 3
        self.assertEqual(z["warteschlange"], 1)      # Sprint 9
        self.assertEqual(z["terminiert"], 0)

    def test_datum_bleibt_lesbar(self):
        """Regression: die Umstellung nimmt Datumszeilen nichts weg — eine Zusage an
        den Menschen bleibt ein Datum. Verifiziert: SWR-106."""
        zustand, ampel = sprint.faellig_zustand("2026-08-15", date(2026, 8, 17))
        self.assertEqual(zustand, sprint.ZUSTAND_TERMIN)
        self.assertEqual(ampel, "rot")


if __name__ == "__main__":
    unittest.main()
