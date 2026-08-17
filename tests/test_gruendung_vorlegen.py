# -*- coding: utf-8 -*-
"""SWR-147 (pm/T-0063, Teil b von pm/T-0028 aus Brief pm/N-0022): Gründung VORLEGEN.

Die beiden Zusicherungen, an denen diese Anforderung hängt, sind nicht der Charter und
nicht das Ticket:

* **DoD 3** — die Auflagen aus SWR-127 stehen im DR-Text. Das ist eine Regel über das
  **Lesen**: SWR-127 gibt sie als Rückgabewert zurück, damit sie nicht übersehen werden
  *können*; hier werden sie eingelöst. Ohne diese Stelle wäre SWR-127 die dritte Prüfung
  dieses Projekts, deren Ergebnis niemand liest.
* **Die Gegenprobe** — es entsteht **kein** Repo, **kein** Remote, **kein**
  Registry-Eintrag. „Legt vor, gründet nicht" ist sonst nur ein Vorsatz im Docstring, und
  gemessen wird deshalb am **Dateisystem**.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
import board  # noqa: E402
from backend import pool  # noqa: E402

VORLAGE = """# Team-Charter {{TEAM_NAME}} (v0.1, zur Gründungs-Freigabe)

*{{DATUM}}, PM. Gründung als Klasse-A-Entscheid: {{GRUENDUNGS_DR}}.*

## Auftrag und Nutzen

{{WAS_MACHT_DAS_TEAM_UND_WARUM}}

## Profil und Arbeitsweise

Profil **{{PROFIL}}**. {{BEI_WIEDERKEHREND_SLA_TABELLE}}

## Rollen

{{ROLLEN_MIT_KURZBESCHREIBUNG}}

## Daten und Zugänge

Datenklasse: {{DATENKLASSE}}. Zugänge: {{ZUGAENGE_ODER_KEINE}}.

## Grenzen

{{TEAM_SPEZIFISCHE_GRENZEN}}
"""

BESTAND_TICKET = """---
id: T-0009
titel: "Ein vorhandenes Ticket"
typ: task
prozess: man3
rolle: pl
sprint: 1
status: open
prio: mittel
blocked_by: []
repo: pm
geändert: 2026-08-17
erstellt: 2026-08-17
---

Rumpf.
"""

SENSIBEL = {"auftrag": "Belege aus Mails vorsortieren.", "profil": "wiederkehrend",
            "rollen": "dev, test", "datenklasse": "sensibel",
            "zugaenge": "IMAP lesend", "grenzen": "Abgabe bleibt beim Menschen."}
INTERN = dict(SENSIBEL, datenklasse="intern", profil="entwicklung")


class Basis(unittest.TestCase):

    def setUp(self):
        self.wurzel = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.wurzel, True)
        self.pm = os.path.join(self.wurzel, "pm")
        os.makedirs(os.path.join(self.pm, "tickets"))
        os.makedirs(os.path.join(self.pm, "management", "kandidaten"))
        with open(os.path.join(self.pm, "tickets", "T-0009.md"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(BESTAND_TICKET)
        tl, _ = board.lade_tickets(self.pm)
        with open(os.path.join(self.pm, "BOARD.md"), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write(board.generiere_board(tl))
        vorlage = os.path.join(self.wurzel, *pool.CHARTER_VORLAGE[:-1])
        os.makedirs(vorlage)
        with open(os.path.join(vorlage, pool.CHARTER_VORLAGE[-1]), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(VORLAGE)
        for args in (["init", "-q"], ["add", "-A"],
                     ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"]):
            subprocess.run(["git", "-C", self.pm] + args, check=True, capture_output=True)

    def charter_text(self, name):
        with open(os.path.join(self.wurzel, *pool.CHARTER_VERZEICHNIS,
                               f"{name}-charter-entwurf.md"), encoding="utf-8") as f:
            return f.read()

    def ticket_text(self, tid):
        with open(os.path.join(self.pm, "tickets", f"{tid}.md"), encoding="utf-8") as f:
            return f.read()


class AuflagenImKlartextTest(Basis):
    """DoD 3 — die Substanz. ⚠ Verglichen wird gegen den **Rückgabewert** von
    `steckbrief_pruefen` und nicht gegen eine Kopie des Satzes im Test: eine Kopie hier
    wäre die zweite Formulierung der Auflage und würde beim ersten Wortlautwechsel still
    falsch (B033)."""

    def test_die_auflage_steht_wortgleich_im_dr(self):
        _werte, auflagen = pool.steckbrief_pruefen(SENSIBEL)
        self.assertTrue(auflagen, "sensibel muss eine Auflage erzeugen — sonst prüft "
                                  "dieser Test nichts")
        erg = pool.gruendung_vorlegen(self.wurzel, "team-steuer", SENSIBEL)
        text = self.ticket_text(erg["dr"])
        for a in auflagen:
            self.assertIn(a, text)

    def test_die_auflage_ist_PROSA_und_kein_feldwert(self):
        """⚠ Ein Feld liest, wer weiß, dass er danach suchen muss. Gemessen wird, dass die
        Auflage **unter der Überschrift** steht und nicht im Frontmatter."""
        erg = pool.gruendung_vorlegen(self.wurzel, "team-steuer", SENSIBEL)
        text = self.ticket_text(erg["dr"])
        kopf, rumpf = text.split("---\n", 2)[1], text.split("---\n", 2)[2]
        self.assertNotIn("kein-remote", kopf)
        self.assertIn("Auflagen", rumpf)
        self.assertIn(".kein-remote", rumpf)

    def test_ohne_auflage_steht_das_AUCH_da(self):
        """⚠ Der leere Fall wird benannt. Ein Abschnitt, der bei „keine Auflagen" fehlt,
        ist von einem vergessenen nicht zu unterscheiden — dieselbe Begründung wie bei den
        Nullzeilen des Preflights (SWR-114)."""
        _werte, auflagen = pool.steckbrief_pruefen(INTERN)
        self.assertEqual(auflagen, [])
        erg = pool.gruendung_vorlegen(self.wurzel, "team-wissen", INTERN)
        text = self.ticket_text(erg["dr"])
        self.assertIn("Auflagen", text)
        self.assertIn("Keine besonderen Auflagen", text)


class LegtVorGruendetNichtTest(Basis):
    """⚠ Die Gegenprobe, gemessen am DATEISYSTEM."""

    def test_kein_repo_kein_remote_kein_registry_eintrag(self):
        pool.gruendung_vorlegen(self.wurzel, "team-steuer", SENSIBEL)
        self.assertFalse(os.path.exists(os.path.join(self.wurzel, "team-steuer")),
                         "es darf kein Team-Ordner entstehen — das wäre die Gründung")
        for wo, _dirs, dateien in os.walk(self.wurzel):
            if ".git" in wo:
                continue
            self.assertNotIn(".kein-remote", dateien, wo)
        # Registry: keine Datei der Organisation wird angefasst außer den beiden Zielen
        # und dem BOARD.md.
        lauf = subprocess.run(["git", "-C", self.pm, "show", "--name-only", "--pretty=",
                               "HEAD"], capture_output=True, text=True, encoding="utf-8")
        geaendert = sorted(z for z in lauf.stdout.split() if z)
        self.assertEqual(geaendert, sorted([
            "BOARD.md", "management/kandidaten/team-steuer-charter-entwurf.md",
            "tickets/T-0010.md"]))

    def test_der_dr_sagt_im_klartext_dass_nichts_gegruendet_ist(self):
        erg = pool.gruendung_vorlegen(self.wurzel, "team-steuer", SENSIBEL)
        self.assertIn("nichts gegründet", erg["meldung"])
        self.assertIn("kein Repo", self.ticket_text(erg["dr"]))


class DrIstGueltigTest(Basis):

    def test_der_dr_ist_ein_gueltiges_ticket(self):
        erg = pool.gruendung_vorlegen(self.wurzel, "team-steuer", SENSIBEL)
        tickets, probleme = board.lade_tickets(self.pm)
        probleme += board.validiere_alle(tickets, self.pm, git_pruefen=False)
        self.assertEqual(probleme, [])
        t = next(x for x in tickets if x["id"] == erg["dr"])
        self.assertEqual(t["typ"], "decision-request")
        self.assertEqual(t["default"], "TG-a")

    def test_die_frist_ist_ein_KALENDERDATUM(self):
        """SWR-125 hat Kalenderdaten an Teamaufgaben abgeschafft — hier wartet ein
        **Mensch**, dessen Antwortzeit in Tagen läuft. Der Widget-Vertrag nimmt den
        `decision-request` bei `kalenderfristen_gesamt` ausdrücklich aus."""
        erg = pool.gruendung_vorlegen(self.wurzel, "team-steuer", SENSIBEL,
                                      heute=date(2026, 8, 17))
        # ⚠ Als eigene Zeile im Frontmatter geprüft (`re.M`) und nicht als Teilstring: der
        # Wert steht auch im Rumpf, und ein `assertIn` wäre schon von dort grün geworden.
        self.assertRegex(self.ticket_text(erg["dr"]), r"(?m)^frist: 2026-08-24$")
        # Und über `board` gelesen, damit die Zusicherung an derselben Auflösung hängt wie
        # die Prüfungen der Organisation.
        tickets, _ = board.lade_tickets(self.pm)
        t = next(x for x in tickets if x["id"] == erg["dr"])
        self.assertTrue(board.ist_datum(t["frist"]))
        self.assertEqual(t["frist"], (date(2026, 8, 17) + timedelta(days=7)).isoformat())

    def test_wartet_auf_mensch(self):
        """Der DR muss in `wartet_auf_mensch` erscheinen — sonst ist er eine Vorlage, die
        niemandem vorliegt (SWR-120/SWR-138)."""
        erg = pool.gruendung_vorlegen(self.wurzel, "team-steuer", SENSIBEL)
        tickets, _ = board.lade_tickets(self.pm)
        t = next(x for x in tickets if x["id"] == erg["dr"])
        self.assertTrue(board.wartet_auf_mensch(t))


class NummerTest(Basis):

    def test_nummer_ist_in_arbeitskopie_UND_head_frei(self):
        """⚠ Kollisions-Lesson 2026-08-16. Gemessen an einem Fall, in dem die beiden
        Quellen AUSEINANDERGEHEN: `T-0020` steht nur in der Arbeitskopie (nicht
        committet). Eine Prüfung, die allein HEAD liest, würde `T-0010` vergeben und die
        vorhandene Datei später überschreiben."""
        with open(os.path.join(self.pm, "tickets", "T-0020.md"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(BESTAND_TICKET.replace("T-0009", "T-0020"))
        self.assertEqual(pool._naechste_ticket_id(self.pm), "T-0021")

    def test_nummer_aus_head_zaehlt_auch_wenn_die_datei_fehlt(self):
        """Die andere Richtung: eine Datei, die committet und in der Arbeitskopie
        gelöscht ist, hält ihre Nummer belegt — sonst vergibt der nächste Lauf sie neu
        und die Historie trägt zwei verschiedene Tickets unter einer ID."""
        os.remove(os.path.join(self.pm, "tickets", "T-0009.md"))
        self.assertEqual(pool._naechste_ticket_id(self.pm), "T-0010")

    def test_kollision_wird_gemeldet_und_nicht_ueberschrieben(self):
        erg = pool.gruendung_vorlegen(self.wurzel, "team-a", INTERN)
        vorher = self.ticket_text(erg["dr"])
        # Zweiter Antrag: die Nummer zieht weiter, das erste Ticket bleibt unberührt.
        erg2 = pool.gruendung_vorlegen(self.wurzel, "team-b", INTERN)
        self.assertNotEqual(erg2["dr"], erg["dr"])
        self.assertEqual(self.ticket_text(erg["dr"]), vorher)


class CharterEntwurfTest(Basis):

    def test_alle_platzhalter_sind_gefuellt(self):
        erg = pool.gruendung_vorlegen(self.wurzel, "team-steuer", SENSIBEL)
        text = self.charter_text("team-steuer")
        self.assertEqual(re.findall(r"\{\{[A-Z_]+\}\}", text), [])
        self.assertIn("team-steuer", text)
        self.assertIn(SENSIBEL["auftrag"], text)
        self.assertIn(erg["ref"], text)

    def test_unbekannter_platzhalter_wird_GEMELDET(self):
        """⚠ Ein Entwurf mit `{{...}}` darin geht als fertig durch, wenn niemand ihn
        liest — und der DR bittet ausdrücklich darum, ihn zu lesen. Der Fall entsteht
        real, sobald die Vorlage ein Feld dazubekommt."""
        pfad = os.path.join(self.wurzel, *pool.CHARTER_VORLAGE)
        with open(pfad, "a", encoding="utf-8", newline="\n") as f:
            f.write("\n{{NEUES_FELD}}\n")
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.gruendung_vorlegen(self.wurzel, "team-steuer", SENSIBEL)
        self.assertEqual(ctx.exception.code, 500)
        self.assertIn("NEUES_FELD", str(ctx.exception))

    def test_sla_hinweis_haengt_am_profil(self):
        """Beim Profil `wiederkehrend` gilt SLA statt G4 (Playbook Kap. 15). Der Hinweis
        wird **benannt** und nicht leer gelassen: eine leere Stelle im Entwurf ist von
        einer vergessenen nicht zu unterscheiden."""
        pool.gruendung_vorlegen(self.wurzel, "team-w", SENSIBEL)
        self.assertIn("SLA-Tabelle", self.charter_text("team-w"))
        pool.gruendung_vorlegen(self.wurzel, "team-e", INTERN)
        self.assertIn("G4 gilt regulär", self.charter_text("team-e"))


class EinCommitTest(Basis):
    """DoD 4: ein Commit für beide, und bei Fehlschlag bleibt **nichts** liegen."""

    def test_beide_dateien_in_EINEM_commit(self):
        erg = pool.gruendung_vorlegen(self.wurzel, "team-steuer", SENSIBEL)
        lauf = subprocess.run(["git", "-C", self.pm, "show", "--name-only", "--pretty=",
                               "HEAD"], capture_output=True, text=True, encoding="utf-8")
        self.assertIn(f"tickets/{erg['dr']}.md", lauf.stdout)
        self.assertIn("team-steuer-charter-entwurf.md", lauf.stdout)
        anzahl = subprocess.run(["git", "-C", self.pm, "rev-list", "--count", "HEAD"],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(anzahl.stdout.strip(), "2", "init + genau EIN Commit")

    def test_gescheiterter_commit_laesst_NICHTS_liegen(self):
        """⚠ Gemessen an einem kaputten Git-Index und nicht durch Wegnehmen von `.git`:
        ohne `.git` scheitert der Aufruf an einer früheren Prüfung, und dann messe man die
        Rücknahme nicht (Befund aus `test_terminieren.py`, Sprint 17)."""
        vorher_board = open(os.path.join(self.pm, "BOARD.md"), encoding="utf-8").read()
        with open(os.path.join(self.pm, ".git", "index"), "wb") as f:
            f.write(b"kein gueltiger Git-Index")
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.gruendung_vorlegen(self.wurzel, "team-steuer", SENSIBEL)
        self.assertEqual(ctx.exception.code, 503)
        self.assertIn("NICHTS vorgelegt", str(ctx.exception))
        self.assertFalse(os.path.exists(os.path.join(
            self.wurzel, *pool.CHARTER_VERZEICHNIS, "team-steuer-charter-entwurf.md")))
        self.assertFalse(os.path.exists(os.path.join(self.pm, "tickets", "T-0010.md")))
        self.assertEqual(open(os.path.join(self.pm, "BOARD.md"), encoding="utf-8").read(),
                         vorher_board)


class PruefungVorherTest(Basis):
    """Ein ungültiger Steckbrief wird abgewiesen, **bevor** etwas geschrieben wird."""

    def test_fehlende_pflichtangabe_schreibt_nichts(self):
        with self.assertRaises(pool.PoolFehler):
            pool.gruendung_vorlegen(self.wurzel, "team-x", dict(SENSIBEL, auftrag=""))
        self.assertFalse(os.path.exists(os.path.join(self.pm, "tickets", "T-0010.md")))
        self.assertEqual(os.listdir(os.path.join(self.pm, "management", "kandidaten")), [])

    def test_unzulaessige_datenklasse_schreibt_nichts(self):
        with self.assertRaises(pool.PoolFehler):
            pool.gruendung_vorlegen(self.wurzel, "team-x", dict(SENSIBEL, datenklasse="egal"))
        self.assertFalse(os.path.exists(os.path.join(self.pm, "tickets", "T-0010.md")))

    def test_teamname_mit_pfadtrenner_wird_abgewiesen(self):
        with self.assertRaises(pool.PoolFehler) as ctx:
            pool.gruendung_vorlegen(self.wurzel, "a/b", INTERN)
        self.assertEqual(ctx.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
