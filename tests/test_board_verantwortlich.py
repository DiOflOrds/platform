"""Unit-Verifikation Feld `verantwortlich` (SWR-116, pm/T-0038 Teil a).

Anlass: B053 aus Brief `pm/N-0030` — *„Tickets nennen keinen Verantwortlichen; `rolle` sagt
die Fachrolle, nicht wer die Handlung tut."*

Sprint 8 (2026-08-17) hat `pm/T-0038` zerlegt, nachdem der Verschiebungsgrund gemessen und
leer befunden wurde: der Bündelungspartner `pm/T-0036` war seit Sprint 7 geschlossen und
hatte nie ein Board-Format geändert. Dieses Ticket ist Teil a) — Feld und Validierung,
**ohne** Formatwirkung. Die Anzeige ist `pm/T-0050`.

Ausführung: python -m unittest discover platform/tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import board  # noqa: E402

ALLE_IDS = {"T-0001"}


def ticket(**kw):
    """Ein gültiges Minimalticket; einzelne Felder je Test überschrieben."""
    t = {"id": "T-0001", "titel": "T", "typ": "task", "prozess": "man3", "rolle": "pl",
         "sprint": "0", "status": "open", "prio": "hoch", "erstellt": "2026-08-17",
         "_datei": "T-0001.md", "_body": ""}
    t.update(kw)
    return t


def fehler(t):
    return board.validiere(t, ALLE_IDS, git_pruefen=False)


class DefaultTest(unittest.TestCase):
    """Das leere Feld hat genau eine Bedeutung. Verifiziert: SWR-116."""

    def test_fehlendes_feld_ist_team(self):
        self.assertEqual(board.verantwortlich_wert(ticket()), "team")

    def test_leeres_feld_ist_team(self):
        self.assertEqual(board.verantwortlich_wert(ticket(verantwortlich="")), "team")

    def test_unsinniger_wert_faellt_auf_team_zurueck_wird_aber_als_fehler_gemeldet(self):
        """Die Auflösung rät nicht, und die Validierung schweigt nicht. Zwei Aufgaben,
        zwei Stellen. Verifiziert: SWR-116."""
        t = ticket(verantwortlich="vielleicht")
        self.assertEqual(board.verantwortlich_wert(t), "team")
        self.assertTrue(any("verantwortlich" in f for f in fehler(t)))

    def test_fehlendes_feld_ist_kein_fehler(self):
        """Optional heißt optional — ein Pflichtfeld hätte jedes vorhandene Ticket in
        einem Zug ungültig gemacht. Verifiziert: SWR-116."""
        self.assertEqual(fehler(ticket()), [])


class WertTest(unittest.TestCase):
    """Erlaubte Werte. Verifiziert: SWR-116."""

    def test_team_ist_gueltig(self):
        self.assertEqual(fehler(ticket(verantwortlich="team")), [])
        self.assertEqual(board.verantwortlich_wert(ticket(verantwortlich="team")), "team")

    def test_mensch_mit_abschnitt_ist_gueltig(self):
        """**Die Gegenprobe zur Belegpflicht.** Ohne sie wäre die Regel nicht
        widerlegbar — man sähe nur, dass etwas abgelehnt wird, nie dass etwas
        durchgeht. Verifiziert: SWR-116."""
        t = ticket(verantwortlich="mensch",
                   _body="## Handlung beim Menschen\n\nAPI-Key im Repo hinterlegen.")
        self.assertEqual(fehler(t), [])
        self.assertEqual(board.verantwortlich_wert(t), "mensch")

    def test_unbekannter_wert_ist_fehler(self):
        t = ticket(verantwortlich="niemand")
        self.assertTrue(any("ungültiges verantwortlich" in f for f in fehler(t)))


class BelegpflichtTest(unittest.TestCase):
    """`mensch` ohne Handlungsangabe ist eine Behauptung ohne Beleg. Verifiziert: SWR-116."""

    def test_mensch_ohne_abschnitt_ist_fehler(self):
        t = ticket(verantwortlich="mensch", _body="## Ziel\n\nirgendwas")
        meldungen = fehler(t)
        self.assertTrue(any("Handlung beim Menschen" in f for f in meldungen), meldungen)

    def test_mensch_mit_leerem_body_ist_fehler(self):
        t = ticket(verantwortlich="mensch", _body="")
        self.assertTrue(any("Handlung beim Menschen" in f for f in fehler(t)))

    def test_team_braucht_keinen_abschnitt(self):
        self.assertEqual(fehler(ticket(verantwortlich="team", _body="## Ziel\n\nx")), [])


class TrennungVonRolleTest(unittest.TestCase):
    """Der Grund, warum das Feld überhaupt existiert. Verifiziert: SWR-116."""

    def test_rolle_mensch_bedeutet_nicht_verantwortlich_mensch(self):
        """`rolle: mensch` trägt in `validiere` bereits eine zweite Bedeutung (Gate,
        Übergangsprüfung ausgenommen). Würde `verantwortlich` daraus abgeleitet, hätte ein
        Feld zwei Zwecke — B033, genau die Falle, wegen der dieses Feld eigenständig ist.
        Verifiziert: SWR-116."""
        t = ticket(rolle="mensch")
        self.assertEqual(board.verantwortlich_wert(t), "team")
        self.assertEqual(fehler(t), [])

    def test_verantwortlich_mensch_bei_fachrolle_pl_ist_zulaessig(self):
        """Die Umkehrung: eine Fachrolle bleibt fachlich, auch wenn der Mensch handelt.
        Verifiziert: SWR-116."""
        t = ticket(rolle="pl", verantwortlich="mensch",
                   _body="## Handlung beim Menschen\n\nEntscheidung treffen.")
        self.assertEqual(fehler(t), [])


class SchreibpfadTest(unittest.TestCase):
    """SWR-077: der zweite Schreibpfad (HMI) darf das Feld setzen. Verifiziert: SWR-116."""

    def test_feld_ist_ueber_hmi_editierbar(self):
        self.assertIn("verantwortlich", board.EDITIERBARE_FELDER)

    def test_identitaetsfelder_bleiben_draussen(self):
        for f in ("id", "prozess", "erstellt", "repo", "blocked_by"):
            self.assertNotIn(f, board.EDITIERBARE_FELDER)


class BestandTest(unittest.TestCase):
    """Abgleich gegen den echten Bestand. Verifiziert: SWR-116."""

    def test_alle_repos_validieren_unveraendert(self):
        """Das Feld ist optional — kein vorhandenes Ticket darf durch SWR-116 ungültig
        werden. Das ist der Unterschied zu Teil b) (`pm/T-0050`), der genau deshalb
        abgetrennt wurde. Verifiziert: SWR-116."""
        root = os.path.join(os.path.dirname(__file__), "..", "..")
        projekte = board.projekt_pfade(root)
        if not projekte:
            self.skipTest("kein Bestand")
        for name, pfad in projekte:
            tickets, probleme = board.lade_tickets(pfad)
            probleme += board.validiere_alle(tickets, pfad, git_pruefen=False)
            self.assertEqual(probleme, [], f"{name}: {probleme}")

    def test_bestand_hat_fuer_jedes_ticket_eine_antwort(self):
        root = os.path.join(os.path.dirname(__file__), "..", "..")
        projekte = board.projekt_pfade(root)
        if not projekte:
            self.skipTest("kein Bestand")
        for name, pfad in projekte:
            tickets, _ = board.lade_tickets(pfad)
            for t in tickets:
                self.assertIn(board.verantwortlich_wert(t), board.VERANTWORTLICH)


if __name__ == "__main__":
    unittest.main()
