"""Der VERTRETER von SWR-204 (platform/T-0058, Sprint 33) — und von SWR-205 dazu.

⚠⚠ **Diese Datei sichert eine ENTSCHEIDUNG ab, nicht nur eine Funktion.**

`platform/T-0058` fragte, ob die Organisation einen **vierten Ticket-Zustand** braucht.
Die Zählung hat die Frage umgestellt: es fehlte kein Zustand, es fehlte die **Prüfung,
ob eine Sperre noch gilt**. Vier der acht gemessenen `blocked_by`-Verweise waren
Altpapier — der Blocker war längst erledigt, den Verweis hat nur nie jemand
zurückgenommen, weil nichts danach gefragt hat.

> **Eine Sperre ohne Rücknahme ist kein Zustand, sondern ein Leck. Wer dafür ein neues
> Statuswort baut, hat das Leck mit Vokabular zugedeckt.**

⚠ **Zweitens sichert diese Datei die AUSNAHME, und das ist der heiklere Teil.** Vier
Verweise zeigen auf `pm/T-0077`, dessen Antwort `A` den Wartegrund **bestätigt** hat.
Sie sind **namentlich** ausgenommen (`TOTE_SPERREN_BESTAND`) und ausdrücklich **nicht**
über eine Bedingung wie „solange ein DR offen ist" — das wäre wörtlich der Fehler aus
`SWR-201`: eine Bedingung, die während der gesamten Arbeitszeit wahr ist, ist ein
offenes Tor mit einer Aufschrift. Die Zusicherung `test_ausnahme_ist_aufzaehlung`
unten wird **rot**, wenn jemand die Aufzählung in eine Bedingung verwandelt.

⚠ **Drittens** hält `NurEinName` den Endzustand auf **einer** Festlegung (SWR-205) —
über `assertIs`, nicht über Gleichheit: zwei gleiche Tupel sind von einer Kopie nicht
zu unterscheiden, zwei identische sind es.
"""
import ast
import inspect
import os
import sys
import unittest

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, "scripts"))
sys.path.insert(0, WURZEL)
import board  # noqa: E402
import kennzahlen  # noqa: E402
from backend import aggregation, sprint, workflows  # noqa: E402

ORGA = os.path.dirname(WURZEL)


def _t(tid, status="open", blocked_by="[]"):
    return {"id": tid, "status": status, "blocked_by": blocked_by,
            "_datei": f"{tid}.md"}


class ToteSperreWirdGemeldet(unittest.TestCase):
    """SWR-204, Richtung 1: der Verweis auf ein geschlossenes Ticket ist ein Befund."""

    def test_verweis_auf_done_meldet(self):
        tickets = [_t("T-0001", "done"), _t("T-0002", "blocked", "[T-0001]")]
        befunde = board.tote_sperren(tickets)
        self.assertEqual(len(befunde), 1, befunde)
        self.assertIn("T-0001", befunde[0])
        self.assertIn("SWR-204", befunde[0])

    def test_verweis_auf_rejected_meldet_auch(self):
        """⚠ `rejected` ist ein Endzustand — genau das Loch aus SWR-205.

        `board.offene_blocker` fragte bis Sprint 33 `!= "done"`; ein **verworfener**
        Blocker las sich damit als gültige Sperre und `tick.py` hätte das abhängige
        Ticket dauerhaft übersprungen.
        """
        tickets = [_t("T-0001", "rejected"), _t("T-0002", "blocked", "[T-0001]")]
        self.assertEqual(len(board.tote_sperren(tickets)), 1)

    def test_verweis_auf_offenes_ticket_ist_still(self):
        tickets = [_t("T-0001", "in_progress"), _t("T-0002", "blocked", "[T-0001]")]
        self.assertEqual(board.tote_sperren(tickets), [])

    def test_geschlossenes_ticket_wird_nicht_geprueft(self):
        """Ein `done` Ticket wird nicht mehr entsperrt — es zu melden wäre Lärm."""
        tickets = [_t("T-0001", "done"), _t("T-0002", "done", "[T-0001]")]
        self.assertEqual(board.tote_sperren(tickets), [])

    def test_unerreichbare_einheit_ist_still(self):
        """SWR-193-Regel: „unbekannt" und „unerreichbar" sind zwei Antworten.

        Ein Gate, das aus einem fehlenden Nachbarrepo einen Fehler macht, ist die
        Bauart, die `SWR-166` 83 abgebrochene Läufe gekostet hat.
        """
        tickets = [_t("T-0002", "blocked", "[gibtesnicht/T-0001]")]
        self.assertEqual(board.tote_sperren(tickets, repo=WURZEL), [])

    def test_validiere_alle_ruft_die_pruefung_auf(self):
        """⚠⚠ Die Verdrahtung, nicht die Funktion.

        Sprint 32 hat sechs grüne Zusicherungen geschrieben, deren Bau danach vom
        Review **ausgehängt** werden konnte, ohne dass eine rot wurde: sie riefen die
        Funktion direkt auf statt den Betrieb. Diese Zusicherung geht durch
        `validiere_alle` und wird rot, wenn der Aufruf dort verschwindet.
        """
        tickets = [_t("T-0001", "done"), _t("T-0002", "blocked", "[T-0001]")]
        probleme = board.validiere_alle(tickets, repo=None, git_pruefen=False)
        self.assertTrue(any("SWR-204" in p for p in probleme), probleme)


class AusnahmeIstEineAufzaehlung(unittest.TestCase):
    """SWR-204, Richtung 2: die Ausnahme hat Namen und keine Bedingung."""

    def test_bestand_ist_still(self):
        tickets = [_t("T-0077", "done"), _t("T-0071", "blocked", "[T-0077]")]
        self.assertEqual(board.tote_sperren(tickets, repo=os.path.join(ORGA, "pm")), [])

    def test_bestand_gilt_nur_fuer_die_genannten(self):
        """⚠ Ein anderes Ticket derselben Einheit mit demselben Blocker wird gemeldet."""
        tickets = [_t("T-0077", "done"), _t("T-0099", "blocked", "[T-0077]")]
        befunde = board.tote_sperren(tickets, repo=os.path.join(ORGA, "pm"))
        self.assertEqual(len(befunde), 1, befunde)

    def test_ausnahme_ist_aufzaehlung(self):
        """⚠⚠ Wird rot, wenn jemand die Aufzählung durch eine Bedingung ersetzt.

        Der Fehler aus `SWR-201` in Reinform: dort war die Ausnahme an „ein Sprint
        läuft" gebunden — und während gearbeitet wird, läuft immer einer.
        """
        self.assertIsInstance(board.TOTE_SPERREN_BESTAND, set)
        for eintrag in board.TOTE_SPERREN_BESTAND:
            self.assertEqual(len(eintrag), 3, eintrag)
            for teil in eintrag:
                self.assertIsInstance(teil, str)
        quelle = inspect.getsource(board.tote_sperren)
        self.assertIn("TOTE_SPERREN_BESTAND", quelle)
        for verboten in ("typ", "decision-request", "sprint"):
            self.assertNotIn(f'"{verboten}"', quelle,
                             "Die Ausnahme haengt an einer Eigenschaft statt an "
                             "einer Aufzaehlung — das ist SWR-201 in neu.")


class BestandIstSauber(unittest.TestCase):
    """SWR-204 am ECHTEN Bestand — nicht in einer Vorrichtung."""

    def test_keine_toten_sperren_ausser_dem_bestand(self):
        gefunden = []
        for name, pfad in board.projekt_pfade(ORGA):
            if not os.path.isdir(os.path.join(pfad, "tickets")):
                continue
            try:
                tickets, _ = board.lade_tickets(pfad)
            except Exception:  # noqa: BLE001 — ein unlesbares Repo ist nicht der Gegenstand
                continue
            gefunden.extend(board.tote_sperren(tickets, repo=pfad))
        self.assertEqual(gefunden, [], "\n".join(gefunden))


class NurEinName(unittest.TestCase):
    """SWR-205: der Endzustand hat EINE Festlegung, der Rest sind Aliase."""

    def test_aliase_sind_identisch(self):
        self.assertIs(aggregation.ENDZUSTAENDE, board.STATUS_FINAL)
        self.assertIs(kennzahlen.ENDZUSTAENDE, board.STATUS_FINAL)
        self.assertIs(sprint.TICKET_GESCHLOSSEN, board.STATUS_FINAL)

    def test_kein_literal_ausserhalb_von_board(self):
        """⚠ Geprüft wird der SYNTAXBAUM, nicht der Text.

        Ein Textvergleich schlüge gegen die eigene Erklärung an — Sprint 32 hat
        zweimal genau das getan: die eine Prüfung fand die schlechte Schreibweise im
        Docstring, wo sie als abschreckendes Beispiel zitiert steht.
        """
        dateien = []
        for verz in ("backend", "scripts", "orchestrator"):
            for wurzel, _dirs, namen in os.walk(os.path.join(WURZEL, verz)):
                if "__pycache__" in wurzel:
                    continue
                dateien.extend(os.path.join(wurzel, n) for n in namen if n.endswith(".py"))
        treffer = []
        for datei in dateien:
            if os.path.basename(datei) == "board.py":
                continue  # die eine Stelle, an der die Menge wohnt
            with open(datei, encoding="utf-8") as f:
                baum = ast.parse(f.read(), filename=datei)
            for knoten in ast.walk(baum):
                if not isinstance(knoten, ast.Tuple):
                    continue
                werte = [e.value for e in knoten.elts
                         if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                if set(werte) == {"done", "rejected"}:
                    treffer.append(f"{os.path.relpath(datei, WURZEL)}:{knoten.lineno}")
        self.assertEqual(treffer, [], "Endzustands-Literal ausserhalb board.py: "
                                      + ", ".join(treffer))

    def test_verworfener_blocker_sperrt_nicht_mehr(self):
        """Der Nebenbefund von SWR-205, an `offene_blocker` selbst gemessen."""
        nach_id = {"T-0001": {"id": "T-0001", "status": "rejected"}}
        t = {"id": "T-0002", "blocked_by": "[T-0001]"}
        self.assertEqual(board.offene_blocker(t, nach_id), [])
        nach_id["T-0001"]["status"] = "in_progress"
        self.assertEqual(board.offene_blocker(t, nach_id), ["T-0001"])

    def test_beurteilte_ausnahmen_sind_benannt(self):
        """DoD 1 von T-0054: die drei bewusst NICHT angeschlossenen Stellen stehen da.

        Ohne diese Zusicherung wäre „wir haben sie beurteilt" eine Behauptung im
        Abschlussbericht und in keiner Prüfung (`SWR-125`).
        """
        with open(os.path.join(WURZEL, "scripts", "board.py"), encoding="utf-8") as f:
            quelle = f.read()
        block = quelle[quelle.index("STATUS_FINAL = "):]
        block = block[:block.index("\ndef ")]
        for stelle in ("aktivitaeten", "feedback_route", "PLAN_FERTIG"):
            self.assertIn(stelle, block,
                          f"beurteilte Ausnahme {stelle} ist nicht mehr benannt")

    def test_workflows_nutzt_die_gemeinsame_menge(self):
        self.assertIn("STATUS_FINAL", inspect.getsource(workflows._takt_tickets))


if __name__ == "__main__":
    unittest.main()
