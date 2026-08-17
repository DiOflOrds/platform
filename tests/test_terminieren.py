# -*- coding: utf-8 -*-
"""SWR-144 (pm/T-0065, Teil b von pm/T-0054 aus Brief pm/N-0038): der Knopf je Zeile.

Der Knopf selbst ist die kleinere Hälfte. Die Substanz sind **DoD 4** und die
Fingerprint-Begründung:

* **DoD 4** — „nichts passiert" und „hat nicht funktioniert" müssen unterscheidbar
  bleiben. Bis Sprint 16 waren sie es nicht: `board.aktualisiere` wirft bei einem Feld,
  das den Wert schon trägt, einen `ValueError`, und `tickets.speichere` übersetzte
  **jeden** `ValueError` in HTTP 400. Ein bereits terminiertes Ticket antwortete damit in
  derselben Gestalt wie ein abgewiesener Schreibvorgang.
* **Die Feldmenge** — die Begründung, warum dieser Weg seinen Fingerprint selbst lesen
  darf, obwohl SWR-080 existiert, hängt daran, dass **ein** Feld geschrieben wird und
  sein Wert nicht vom Client kommt. Deshalb misst `test_genau_ein_feld_…` die
  **Differenz des Frontmatters** und nicht den Rückgabewert: ein zweites Feld würde die
  Begründung still falsch machen, und ein Rückgabewert kann das nicht zeigen.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import board  # noqa: E402
from backend import tickets  # noqa: E402

TICKET = """---
id: {tid}
titel: "{titel}"
typ: task
prozess: swe3
rolle: dev
sprint: 1
status: open
prio: hoch
blocked_by: []
geplant_sprint: {geplant}
geändert: 2026-08-17
erstellt: 2026-08-17
---

## Ziel

Etwas tun.
"""

REGISTER = ('{"nr": 8, "kennung": "k8", "start": "2026-08-17 10:00", "takt_min": 60}\n'
            '{"kennung": "k8", "ende": "2026-08-17 11:00"}\n'
            '{"nr": 9, "kennung": "k9", "start": "2026-08-17 11:05", "takt_min": 60}\n')


class Basis(unittest.TestCase):
    """Ein Wurzelverzeichnis mit `pm` (Register) und `p0` (Tickets), beides echte Repos."""

    def setUp(self):
        self.wurzel = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.wurzel, True)
        pm = os.path.join(self.wurzel, "pm", "management")
        os.makedirs(pm)
        open(os.path.join(pm, "sprints.jsonl"), "w", encoding="utf-8",
             newline="\n").write(REGISTER)
        self.repo = os.path.join(self.wurzel, "p0")
        os.makedirs(os.path.join(self.repo, "tickets"))
        self.schreibe("T-0100", "Noch nicht terminiert", 9)
        self.schreibe("T-0101", "Schon terminiert", 10)
        tl, _ = board.lade_tickets(self.repo)
        open(os.path.join(self.repo, "BOARD.md"), "w", encoding="utf-8",
             newline="\n").write(board.generiere_board(tl))
        for args in (["init", "-q"], ["add", "-A"],
                     ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"]):
            subprocess.run(["git", "-C", self.repo] + args, check=True, capture_output=True)

    def schreibe(self, tid, titel, geplant):
        open(os.path.join(self.repo, "tickets", tid + ".md"), "w", encoding="utf-8",
             newline="\n").write(TICKET.format(tid=tid, titel=titel, geplant=geplant))

    def text(self, tid):
        return open(board.ticket_pfad(self.repo, tid), encoding="utf-8").read()

    def frontmatter(self, tid):
        kopf = re.match(r"^---\n(.*?)\n---\n", self.text(tid), re.S).group(1)
        felder = {}
        for zeile in kopf.split("\n"):
            if ": " in zeile:
                k, v = zeile.split(": ", 1)
                felder[k.strip()] = v.strip()
        return felder

    def commits(self):
        lauf = subprocess.run(["git", "-C", self.repo, "log", "--pretty=%an|%s"],
                              capture_output=True, text=True, encoding="utf-8")
        return lauf.stdout.strip().splitlines()


class NaechsterSprintTest(Basis):

    def test_naechster_sprint_kommt_aus_dem_register(self):
        """Der laufende Sprint ist 9, der nächste also 10 — aus dem Register, nicht geraten."""
        self.assertEqual(tickets.naechster_sprint(self.wurzel), 10)

    def test_ein_neuer_sprint_verschiebt_das_ziel_mit(self):
        """⚠ Die Zahl ist keine Konstante: eröffnet das Register Sprint 10, zielt der
        Knopf auf 11. Ohne diese Zusicherung wäre `+1` gegen einen Fixwert getestet und
        die Aussage „aus dem Register" unbelegt."""
        pfad = os.path.join(self.wurzel, "pm", "management", "sprints.jsonl")
        with open(pfad, "a", encoding="utf-8", newline="\n") as f:
            f.write('{"kennung": "k9", "ende": "2026-08-17 12:00"}\n')
            f.write('{"nr": 10, "kennung": "k10", "start": "2026-08-17 12:05"}\n')
        self.assertEqual(tickets.naechster_sprint(self.wurzel), 11)


class TerminierenTest(Basis):

    def test_genau_ein_feld_wird_geaendert(self):
        """SWR-144, Kern: gemessen wird die **Differenz des Frontmatters**.

        Der Rückgabewert könnte „geplant_sprint" melden und daneben ein zweites Feld
        geschrieben haben. Diese Zusicherung vergleicht deshalb vorher/nachher Feld für
        Feld — und lässt `geändert` als Zeitstempel ausdrücklich zu, weil er kein
        inhaltliches Feld ist.
        """
        vorher = self.frontmatter("T-0100")
        erg = tickets.terminiere(self.wurzel, "p0", "T-0100")
        nachher = self.frontmatter("T-0100")
        self.assertTrue(erg["ok"])
        self.assertFalse(erg.get("unveraendert"))
        self.assertEqual(nachher["geplant_sprint"], "10")
        abweichend = {k for k in set(vorher) | set(nachher)
                      if vorher.get(k) != nachher.get(k)} - {"geändert"}
        self.assertEqual(abweichend, {"geplant_sprint"},
                         "eine Terminierung darf genau ein inhaltliches Feld anfassen — "
                         "sonst trägt die Fingerprint-Begründung von SWR-144 nicht mehr")

    def test_prio_bleibt_unberuehrt(self):
        """Festlegung aus pm/T-0054: „für den nächsten Durchlauf" ist ein Termin, keine
        Wichtigkeit. Eigene Zusicherung neben der Feldmenge, weil genau dieses Feld der
        naheliegende Mitnahmeeffekt wäre."""
        tickets.terminiere(self.wurzel, "p0", "T-0100")
        self.assertEqual(self.frontmatter("T-0100")["prio"], "hoch")

    def test_feldmenge_ist_eine_konstante_mit_genau_einem_feld(self):
        """⚠ Zähltest über die Konstante selbst — die Begründung, warum dieser Weg den
        Fingerprint selbst lesen darf, hängt an ihrer Größe. Wächst sie, wird das Argument
        still falsch; hier wird es laut."""
        self.assertEqual(tickets.TERMINIER_FELDER, ("geplant_sprint",))

    def test_urheber_steht_im_ticket_und_im_commit(self):
        """DoD 2: ohne den Urheber meldet `plan_drift` beim nächsten Lauf eine Abweichung,
        deren Ursache niemand mehr benennen kann."""
        tickets.terminiere(self.wurzel, "p0", "T-0100")
        self.assertIn("Mensch via HMI", self.text("T-0100"))
        self.assertTrue(any(z.startswith("Mensch via HMI|") for z in self.commits()),
                        "der Commit muss den Urheber tragen: " + repr(self.commits()))

    def test_board_bleibt_deckungsgleich_und_ist_NICHT_im_commit(self):
        """⚠ Beim Schreiben dieser Zusicherung gemessen und nicht vorher gewusst: eine
        Terminierung ändert `BOARD.md` **nicht**.

        Der erste Entwurf verlangte Ticket **und** `BOARD.md` im Commit — nach dem Muster
        von SWR-078 — und wurde rot. Der Grund ist kein Fehler: `generiere_board` führt die
        Spalte `Sprint` aus dem Feld `sprint`, **nicht** aus `geplant_sprint`. Die
        Terminierung ist damit eine Änderung, die auf dem Board unsichtbar ist.

        > **Ein Commit, der eine unveränderte Datei mitnimmt, gibt es nicht — und eine
        > Zusicherung, die ihn verlangt, misst die Absicht des Testschreibers.**

        Gemessen wird deshalb, was wirklich gilt: das Ticket steht im Commit, und
        `BOARD.md` ist danach deckungsgleich mit einer frischen Regeneration — also nicht
        veraltet, sondern gleich geblieben, weil sich an ihrem Inhalt nichts ändert.
        """
        tickets.terminiere(self.wurzel, "p0", "T-0100")
        lauf = subprocess.run(["git", "-C", self.repo, "show", "--name-only",
                               "--pretty=", "HEAD"], capture_output=True, text=True,
                              encoding="utf-8")
        self.assertIn("tickets/T-0100.md", lauf.stdout)
        self.assertNotIn("BOARD.md", lauf.stdout)
        tl, _ = board.lade_tickets(self.repo)
        with open(os.path.join(self.repo, "BOARD.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), board.generiere_board(tl))


class SchonTerminiertTest(Basis):
    """DoD 4 — die Gegenprobe. Ohne sie ist der Knopf eine Anzeige ohne Aussage."""

    def test_schon_terminiert_ist_ein_erfolg_und_kein_fehler(self):
        erg = tickets.terminiere(self.wurzel, "p0", "T-0101")
        self.assertTrue(erg["ok"])
        self.assertTrue(erg["unveraendert"])
        self.assertEqual(erg["geaendert"], [])

    def test_die_meldung_nennt_die_nummer_die_schon_dasteht(self):
        """B038: eine Meldung, die nur „keine Änderung" sagt, zwingt zum Öffnen des
        Tickets, um zu wissen, ob der Knopf etwas gemeint hat."""
        erg = tickets.terminiere(self.wurzel, "p0", "T-0101")
        self.assertIn("Sprint 10", erg["meldung"])
        self.assertIn("unverändert", erg["meldung"])

    def test_datei_bleibt_byteweise_gleich(self):
        """⚠ Byteweise und nicht „inhaltlich": ein neuer Zeitstempel in `geändert` wäre
        eine Änderung an einer Datei, an der nichts geändert werden sollte."""
        vorher = self.text("T-0101")
        tickets.terminiere(self.wurzel, "p0", "T-0101")
        self.assertEqual(self.text("T-0101"), vorher)

    def test_kein_commit_ohne_aenderung(self):
        """Ein Commit ohne Änderung schriebe ein Ereignis in die Historie, das nicht
        stattgefunden hat — und die Historie ist die Quelle von `status_in_head`."""
        vorher = self.commits()
        tickets.terminiere(self.wurzel, "p0", "T-0101")
        self.assertEqual(self.commits(), vorher)

    def test_ein_echter_fehlschlag_ist_KEIN_erfolg(self):
        """⚠ Die Gegenrichtung von DoD 4, und ohne sie belegt der Rest nichts: dass
        „unverändert" ein Erfolg ist, darf nicht dazu führen, dass ein Fehlschlag es
        auch wird. Gemessen an einem unbekannten Ticket."""
        with self.assertRaises(tickets.TicketFehler) as ctx:
            tickets.terminiere(self.wurzel, "p0", "T-9999")
        self.assertEqual(ctx.exception.code, 404)


class EigenerTypTest(Basis):
    """SWR-144: die Unterscheidung ist ein **Typ** und kein Textvergleich."""

    def test_keine_aenderung_ist_ein_eigener_typ(self):
        with self.assertRaises(board.KeineAenderung):
            board.aktualisiere(self.repo, "T-0101", {"geplant_sprint": "10"},
                               erwarteter_fingerprint=board.fingerprint(self.text("T-0101")))

    def test_bleibt_ein_ValueError_fuer_bestehende_aufrufer(self):
        """⚠ Rückwärtskompatibilität als Zusicherung und nicht als Absicht: jeder
        bestehende Aufrufer fängt `ValueError` und muss sich unverändert verhalten."""
        self.assertTrue(issubclass(board.KeineAenderung, ValueError))


class GescheiterterCommitTest(Basis):
    """DoD 3: ein fehlgeschlagener Schreibvorgang lässt das Ticket unverändert."""

    def test_rollback_bei_gescheitertem_commit(self):
        """⚠ Der erste Entwurf dieser Zusicherung hat `.git` **weggeschoben** — und
        gemessen hat er dann etwas anderes: ohne `.git` findet `aggregation.projekte` das
        Projekt nicht mehr, der Aufruf endet mit **404** statt **503**, und die Rücknahme
        wird nie erreicht.

        > **Ein Fehler, den man dem System durch Wegnahme seiner Voraussetzungen beibringt,
        > ist ein anderer Fehler als der, den man messen wollte.**

        Gemessen wird deshalb an einem **kaputten Index**: das Repo bleibt ein Repo, aber
        `git add` scheitert. Kein Monkeypatch auf `verbuche` — die Rücknahme soll im echten
        Fehlerfall gelten, nicht in einer nachgestellten Rückgabe.
        """
        vorher_ticket = self.text("T-0100")
        with open(os.path.join(self.repo, "BOARD.md"), encoding="utf-8") as f:
            vorher_board = f.read()
        with open(os.path.join(self.repo, ".git", "index"), "wb") as f:
            f.write(b"kein gueltiger Git-Index")
        with self.assertRaises(tickets.TicketFehler) as ctx:
            tickets.terminiere(self.wurzel, "p0", "T-0100")
        self.assertEqual(ctx.exception.code, 503)
        self.assertIn("zurückgenommen", str(ctx.exception))
        self.assertEqual(self.text("T-0100"), vorher_ticket)
        with open(os.path.join(self.repo, "BOARD.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), vorher_board)


if __name__ == "__main__":
    unittest.main()
