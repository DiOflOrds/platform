"""Statusuebergaenge in der COMMITTETEN Historie (SWR-118, pm/T-0048).

Der Befund: `board.py --check` haelt die Arbeitskopie gegen HEAD und ist damit blind
fuer einen Sprung, der bereits committet ist. In Sprint 7 sind zwei Tickets so
durchgekommen. Das Ergebnis der Pruefung hing an der REIHENFOLGE der Session.

Diese Tests bauen echte Git-Repos, weil die Pruefung eine echte Historie liest — ein
Mock haette genau die Eigenschaft nicht, um die es geht.
"""
import os
import subprocess
import sys
import tempfile
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
import uebergang_historie as uh  # noqa: E402


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo] + list(args),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


class HistorieTest(unittest.TestCase):

    def setUp(self):
        self.repo = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.repo, "tickets"))
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.name", "Test")
        _git(self.repo, "config", "user.email", "test@example.invalid")
        # Stichtag weit in der Zukunft ist nicht noetig: die Tests uebergeben ihn
        # ausdruecklich als 0, damit JEDER Verstoss als "neu" gilt. Der Altbestand
        # hat einen eigenen Test.
        self.stichtag = 0

    def schreibe(self, tid, status, rolle="pl"):
        pfad = os.path.join(self.repo, "tickets", "%s.md" % tid)
        with open(pfad, "w", encoding="utf-8") as f:
            f.write("---\nid: %s\ntyp: task\nrolle: %s\nstatus: %s\n---\n\nText.\n"
                    % (tid, rolle, status))

    def commit(self, text):
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", text)

    def pruefe(self):
        return uh.pruefe_repo(self.repo, "testrepo", stichtag=self.stichtag)

    # ------------------------------------------------------------------ der Fall

    def test_open_nach_done_in_einem_commit_ist_ein_befund(self):
        """⚠ DER FALL AUS SPRINT 7, den keine Pruefung gemeldet hat.

        `pm/T-0043` und `team-dashboard/T-0002` sind genau so durchgekommen: Status im
        Editor gesetzt und committet, ohne dazwischen `board.py --check` zu laufen.
        Beim naechsten Preflight sagten HEAD und Arbeitskopie dasselbe.
        """
        self.schreibe("T-0001", "open")
        self.commit("neu")
        self.schreibe("T-0001", "done")
        self.commit("sprung")
        neue, _alt = self.pruefe()
        self.assertEqual(len(neue), 1)
        self.assertIn("T-0001", neue[0])
        self.assertIn("open -> done", neue[0])

    def test_befund_nennt_ticket_commit_und_paar(self):
        """B038: nicht nur eine Zahl. Ohne den Commit ist der Befund nicht nachpruefbar
        — und ein Befund, den man nicht nachsehen kann, ist eine Behauptung."""
        self.schreibe("T-0001", "open")
        self.commit("neu")
        self.schreibe("T-0001", "done")
        self.commit("sprung")
        sha = _git(self.repo, "rev-parse", "--short=7", "HEAD").stdout.strip()
        neue, _alt = self.pruefe()
        self.assertIn("testrepo/tickets/T-0001.md", neue[0])
        self.assertIn(sha, neue[0])
        self.assertIn("open -> done", neue[0])

    # ------------------------------------------------------------------ Gegentests

    def test_der_regulaere_weg_ueber_mehrere_commits_ist_kein_befund(self):
        """DER GEGENTEST. Ohne ihn wuerde die Pruefung auch den korrekten Ablauf
        melden, und ein Fehlalarm auf dem einzigen richtigen Weg waere schlimmer als
        gar keine Pruefung."""
        self.schreibe("T-0001", "open")
        self.commit("neu")
        for status in ("in_progress", "in_review", "done"):
            self.schreibe("T-0001", status)
            self.commit(status)
        neue, alt = self.pruefe()
        self.assertEqual(neue, [])
        self.assertEqual(alt, [])

    def test_rolle_mensch_bleibt_frei(self):
        """pm/T-0048 Punkt 3, woertlich: die heutige Ausnahme muss erhalten bleiben.
        Mensch-Tickets sind Gates, ihre Uebergaenge sind absichtlich frei."""
        self.schreibe("T-0001", "open", rolle="mensch")
        self.commit("neu")
        self.schreibe("T-0001", "done", rolle="mensch")
        self.commit("sprung")
        neue, _alt = self.pruefe()
        self.assertEqual(neue, [])

    def test_ausnahme_haengt_am_ticket_und_nicht_am_dateinamen(self):
        """Die Gegenprobe zur Mensch-Ausnahme: dasselbe Ticket, dieselbe Datei, nur
        `rolle: pl` — und es IST ein Befund. Ohne diesen Test waere die Ausnahme nicht
        widerlegbar (dieselbe Regel wie bei der `Stand:`-Ausnahme in SWR-110)."""
        self.schreibe("T-0001", "open", rolle="pl")
        self.commit("neu")
        self.schreibe("T-0001", "done", rolle="pl")
        self.commit("sprung")
        neue, _alt = self.pruefe()
        self.assertEqual(len(neue), 1)

    def test_neuanlage_mit_anfangsstatus_ist_kein_uebergang(self):
        """Ein neues Ticket kommt aus keinem Vorzustand. `-U0` liefert dafuer kein
        `-status:` — die Neuanlage ist damit gar kein Wechsel und nicht etwa einer,
        der ausgenommen werden muesste."""
        self.schreibe("T-0001", "in_progress")
        self.commit("neu, direkt in_progress")
        neue, alt = self.pruefe()
        self.assertEqual((neue, alt), ([], []))

    def test_repo_ohne_git_wirft_nicht(self):
        """Ein Befund darf nicht am Melden sterben (platform/T-0009)."""
        leer = tempfile.mkdtemp()
        os.makedirs(os.path.join(leer, "tickets"))
        self.assertEqual(uh.pruefe_repo(leer, "leer", stichtag=0), ([], []))

    def test_mehrere_tickets_in_einem_commit_werden_einzeln_gemeldet(self):
        """Der Sprint-7-Fall war genau das: EIN Commit, ZWEI Tickets. Ein Parser, der
        die Dateigrenze im Diff verliert, meldet einen davon oder keinen."""
        self.schreibe("T-0001", "open")
        self.schreibe("T-0002", "open")
        self.commit("neu")
        self.schreibe("T-0001", "done")
        self.schreibe("T-0002", "done")
        self.commit("zwei Spruenge in einem Commit")
        neue, _alt = self.pruefe()
        self.assertEqual(len(neue), 2)
        self.assertTrue(any("T-0001" in z for z in neue))
        self.assertTrue(any("T-0002" in z for z in neue))


class StichtagTest(unittest.TestCase):
    """Der Altbestand — gemeldet, aber nicht blockierend (pm/T-0048 Punkt 2)."""

    def setUp(self):
        self.repo = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.repo, "tickets"))
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.name", "Test")
        _git(self.repo, "config", "user.email", "test@example.invalid")
        pfad = os.path.join(self.repo, "tickets", "T-0001.md")
        with open(pfad, "w", encoding="utf-8") as f:
            f.write("---\nid: T-0001\ntyp: task\nrolle: pl\nstatus: open\n---\n\nx\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "neu")
        with open(pfad, "w", encoding="utf-8") as f:
            f.write("---\nid: T-0001\ntyp: task\nrolle: pl\nstatus: done\n---\n\nx\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "sprung")

    def test_vor_dem_stichtag_ist_altbestand_und_blockiert_nicht(self):
        import time
        neue, alt = uh.pruefe_repo(self.repo, "r", stichtag=time.time() + 3600)
        self.assertEqual(neue, [])
        self.assertEqual(len(alt), 1, "der Altfall muss GEMELDET werden, nur nicht "
                                      "blockieren — sonst hiesse 'nicht geglaettet' "
                                      "nur 'nicht aufgeraeumt'")

    def test_ab_dem_stichtag_blockiert_derselbe_fall(self):
        neue, alt = uh.pruefe_repo(self.repo, "r", stichtag=0)
        self.assertEqual(len(neue), 1)
        self.assertEqual(alt, [])


class AltbestandRegisterTest(unittest.TestCase):
    """⚠ Der Test, der den Stichtag davon abhaelt, ein Parkplatz zu werden.

    Ein Stichtag ohne festgenagelte Groesse waere genau das, wovor ein Register aus
    Einzeleintraegen bewahren soll: wer ihn nach vorn zieht, wird einen frischen
    Verstoss los, und niemand sieht es. Die Zahl `ALTBESTAND_ERWARTET` macht jede
    Verschiebung sichtbar — und meldet nebenbei ein Umschreiben der Historie, denn
    die Vergangenheit kann sich sonst gar nicht aendern (L-2026-08-17g Regel 4).
    """

    def setUp(self):
        self.wurzel = os.path.abspath(os.path.join(_HIER, "..", ".."))
        if not os.path.isdir(os.path.join(self.wurzel, "pm", "tickets")):
            self.skipTest("kein Bestand unter der Wurzel")

    def test_altbestand_hat_die_festgenagelte_groesse(self):
        _neue, alt, register = uh.pruefe_alle(self.wurzel)
        self.assertEqual(len(alt), uh.ALTBESTAND_ERWARTET)
        self.assertEqual(register, [])

    def test_verschobener_stichtag_wird_zum_befund(self):
        """Der Gegentest: mit einem anderen Stichtag stimmt die Zahl nicht mehr — und
        genau dann muss es einen Befund geben. Ohne ihn waere die Festnagelung eine
        Zusage ohne Wirkung."""
        _neue, alt, _register = uh.pruefe_alle(self.wurzel, stichtag=0)
        self.assertNotEqual(len(alt), uh.ALTBESTAND_ERWARTET)

    def test_fremde_wurzel_behauptet_nichts_ueber_die_groesse(self):
        """⚠ Der Fehlalarm, den `test_preflight` beim ersten Gesamtlauf gefunden hat.

        Über einer leeren Wurzel meldete die Prüfung „Altbestand hat 0, erwartet sind
        52". `ALTBESTAND_ERWARTET` ist eine Messung an EINEM Bestand und keine
        allgemeine Eigenschaft von Ticket-Repos; sie gegen eine beliebige Wurzel zu
        halten ist ein Kategorienfehler. Ohne diesen Test wäre die Bestandsmarke eine
        stille Sonderbehandlung statt einer benannten Vorbedingung.
        """
        fremd = tempfile.mkdtemp()
        neue, alt, register = uh.pruefe_alle(fremd)
        self.assertEqual((neue, alt, register), ([], [], []))
        self.assertFalse(uh._ist_dieser_bestand(fremd))
        self.assertTrue(uh._ist_dieser_bestand(self.wurzel))

    def test_seit_dem_stichtag_gibt_es_keinen_verstoss(self):
        """Die laufende Zusicherung: was dieser Sprint und alle folgenden committen,
        geht den legalen Weg. Schlaegt dieser Test an, hat ein Lauf den Status
        gesprungen — und zwar nachweisbar, nicht je nach Reihenfolge."""
        neue, _alt, _register = uh.pruefe_alle(self.wurzel)
        self.assertEqual(neue, [], "unzulaessige Uebergaenge seit dem Stichtag: %s"
                         % neue)


if __name__ == "__main__":
    unittest.main()
