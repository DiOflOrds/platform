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
Verweise zeigten auf `pm/T-0077`, dessen Antwort `A` den Wartegrund **bestätigt** hat.
Sie standen **namentlich** in `TOTE_SPERREN_BESTAND` und ausdrücklich **nicht** unter
einer Bedingung wie „solange ein DR offen ist" — das wäre wörtlich der Fehler aus
`SWR-201`: eine Bedingung, die während der gesamten Arbeitszeit wahr ist, ist ein
offenes Tor mit einer Aufschrift.

> **⚠⚠ Die Liste ist inzwischen LEER — der Auftraggeber hat `pm/T-0084` vier Stunden
> nach ihrer Entstehung mit `D029` = C beantwortet. Eine Ausnahmeliste, die man leer
> bekommt, war die richtige Bauform; ein vierter Ticket-Zustand wäre geblieben.**

Deshalb prüft `test_ausnahme_greift_oder_ist_weg`, dass **jeder** Eintrag am echten
Bestand noch beißt — diese Verfallsprüfung fehlte in der ersten Fassung und hat das
unabhängige Gegenlesen gebraucht. Der Mechanismus selbst wird an einer **vorübergehend
gesetzten** Ausnahme geprüft, damit die leere Liste ihn nicht unbeobachtet lässt.

Lehren dieses Baus: `L-2026-08-21cx` (eine Ausnahme braucht eine Verfallsprüfung) und
`L-2026-08-21cz` (eine pauschal ausgenommene Datei ist ein blinder Fleck).

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


# SWR-221 (platform/T-0074): der Wächter dieser Zusicherungen fragt ihre EIGENE Eingabe.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bestandswaechter  # noqa: E402


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

    def test_bestand_ist_heute_leer(self):
        """⚠ Der Zustand selbst ist die Aussage — und er ist ERREICHT, nicht Ausgangslage.

        Wächst die Liste wieder, wird diese Zusicherung rot und verlangt, dass jemand
        den Grund in den Bericht schreibt, statt ihn nebenbei einzutragen.
        """
        self.assertEqual(board.TOTE_SPERREN_BESTAND, set(),
                         "Neue Ausnahme — gehoert benannt und begruendet, nicht "
                         "stillschweigend eingetragen (pm/D029 hat die letzte geloest)")

    def test_der_mechanismus_greift_an_einer_gesetzten_ausnahme(self):
        """⚠ Die leere Liste darf den Mechanismus nicht unbeobachtet lassen.

        Eine Zusicherung, die nur den heutigen (leeren) Bestand prüft, sagt nichts über
        das Verhalten — sie wäre die Vakuum-Grün-Bauform, die das Gegenlesen an der
        Schwester-Zusicherung gefunden hat.
        """
        alt = board.TOTE_SPERREN_BESTAND
        board.TOTE_SPERREN_BESTAND = {("pm", "T-0071", "T-0077")}
        try:
            still = [_t("T-0077", "done"), _t("T-0071", "blocked", "[T-0077]")]
            self.assertEqual(board.tote_sperren(still, repo=os.path.join(ORGA, "pm")), [])
            # ⚠ und die Ausnahme gilt NUR fuer den genannten Eintrag
            laut = [_t("T-0077", "done"), _t("T-0099", "blocked", "[T-0077]")]
            self.assertEqual(
                len(board.tote_sperren(laut, repo=os.path.join(ORGA, "pm"))), 1)
        finally:
            board.TOTE_SPERREN_BESTAND = alt

    def test_ausnahme_greift_oder_ist_weg(self):
        """⚠⚠ Nachtrag aus dem Gegenlesen: eine Ausnahme muss noch BEISSEN.

        Die erste Fassung hatte kein Gegenstück zu `test_uhrenprobe`: die Liste wäre
        stehen geblieben, nachdem ihr Grund entfallen ist, und niemand hätte es gemerkt.
        Genau das ist noch im selben Sprint eingetreten — `pm/D029` hat die vier
        Verweise umgehängt, vier Stunden nachdem die Liste entstand.

        > **Eine Ausnahme ohne Verfallsprüfung ist ein Dauerbefund mit umgekehrtem
        > Vorzeichen: sie meldet nicht zu viel, sondern für immer zu wenig.**
        """
        for einheit, tid, ref in board.TOTE_SPERREN_BESTAND:
            pfade = dict(board.projekt_pfade(ORGA))
            self.assertIn(einheit, pfade, f"Ausnahme nennt unbekannte Einheit: {einheit}")
            datei = os.path.join(pfade[einheit], "tickets", f"{tid}.md")
            self.assertTrue(os.path.isfile(datei), f"Ausnahme zeigt ins Leere: {tid}")
            with open(datei, encoding="utf-8") as f:
                fm, _ = board.parse_frontmatter(f.read())
            self.assertIn(ref, board.parse_liste((fm or {}).get("blocked_by")),
                          f"{einheit}/{tid} traegt {ref} nicht mehr — Ausnahme ist tot")

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
        # ⚠⚠ Nachtrag aus dem Gegenlesen: die erste Fassung suchte Textliterale mit
        # DOPPELTEN Anfuehrungszeichen — einfache Anfuehrungszeichen oder eine
        # Hilfsfunktion waeren glatt durchgegangen. Geprueft wird jetzt der Syntaxbaum:
        # im Rumpf darf es genau EINE `continue`-Ausnahme geben, und ihre Bedingung muss
        # die Mitgliedschaft in der Aufzaehlung sein.
        baum = ast.parse(inspect.getsource(board.tote_sperren).lstrip())
        ausnahmen = [k for k in ast.walk(baum)
                     if isinstance(k, ast.If)
                     and any(isinstance(x, ast.Continue) for x in ast.walk(k))]
        self.assertEqual(len(ausnahmen), 2,
                         "Zahl der Ausstiege im Rumpf veraendert — jede weitere "
                         "Bedingung ist eine potenzielle SWR-201-Zange")
        vergleiche = [k for a in ausnahmen for k in ast.walk(a)
                      if isinstance(k, ast.Compare)
                      and any(isinstance(o, ast.In) for o in k.ops)]
        quellen = {ast.unparse(k.comparators[0]) for k in vergleiche}
        self.assertEqual(quellen, {"TOTE_SPERREN_BESTAND", "STATUS_FINAL"},
                         f"unerwartete Ausnahmebedingung: {quellen}")


@bestandswaechter.am_bestand("pm/tickets", "p0/tickets", "team-termine/tickets")
class BestandIstSauber(unittest.TestCase):
    """SWR-204 am ECHTEN Bestand — nicht in einer Vorrichtung."""

    def test_keine_toten_sperren_ausser_dem_bestand(self):
        """⚠ Mit unterer Schranke — sonst ist die Zusicherung vakuum-gruen.

        Das Gegenlesen hat gezeigt: ohne Schranke vergleicht sie `[] == []`, sobald der
        Bestand keine Sperren mehr traegt, und ein `except Exception` haette sogar ein
        komplett unladbares Haus gruen gemacht. Dieselbe Schranke traegt die
        Schwester-Zusicherung `test_deckt_beide_ebenen_ab` seit ihrer ersten Fassung.
        """
        gefunden, geprueft, verweise = [], 0, 0
        for _name, pfad in board.projekt_pfade(ORGA):
            if not os.path.isdir(os.path.join(pfad, "tickets")):
                continue
            tickets, ladefehler = board.lade_tickets(pfad)
            self.assertEqual(ladefehler, [], f"{pfad} nicht ladbar: {ladefehler}")
            geprueft += 1
            for t in tickets:
                if t.get("status") not in board.STATUS_FINAL:
                    verweise += len(board.parse_liste(t.get("blocked_by")))
            gefunden.extend(board.tote_sperren(tickets, repo=pfad))
        self.assertGreater(geprueft, 10, "zu wenige Einheiten geprueft — Discovery kaputt?")
        self.assertGreater(verweise, 0, "kein einziger blocked_by-Verweis im Bestand — "
                                        "diese Zusicherung sagt dann nichts")
        self.assertEqual(gefunden, [], "\n".join(gefunden))


class NurEinName(unittest.TestCase):
    """SWR-205: der Endzustand hat EINE Festlegung, der Rest sind Aliase."""

    def test_aliase_sind_identisch(self):
        self.assertIs(aggregation.ENDZUSTAENDE, board.STATUS_FINAL)
        self.assertIs(kennzahlen.ENDZUSTAENDE, board.STATUS_FINAL)
        self.assertIs(sprint.TICKET_GESCHLOSSEN, board.STATUS_FINAL)
        # ⚠⚠ Der FUENFTE Name, den die Zaehlung dieses Sprints uebersehen hat und den
        # die erste Fassung dieser Zusicherung strukturell nicht finden konnte:
        # sie nahm `board.py` PAUSCHAL aus. Eine Ausnahme fuer eine ganze Datei ist
        # keine Ausnahme, sondern ein blinder Fleck.
        self.assertIs(board.GESCHLOSSEN, board.STATUS_FINAL)

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
            with open(datei, encoding="utf-8") as f:
                baum = ast.parse(f.read(), filename=datei)
            for knoten in ast.walk(baum):
                if not isinstance(knoten, ast.Tuple):
                    continue
                werte = [e.value for e in knoten.elts
                         if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                if set(werte) == {"done", "rejected"}:
                    treffer.append(f"{os.path.relpath(datei, WURZEL)}:{knoten.lineno}")
        # ⚠ Ausgenommen ist die EINE Zuweisungszeile, an der die Menge wohnt — nicht die
        # ganze Datei. Genau diese pauschale Ausnahme hat `board.GESCHLOSSEN` verdeckt.
        with open(os.path.join(WURZEL, "scripts", "board.py"), encoding="utf-8") as f:
            zeilen = f.read().split("\n")
        heimat = [i + 1 for i, z in enumerate(zeilen)
                  if z.startswith("STATUS_FINAL = ")]
        self.assertEqual(len(heimat), 1, "STATUS_FINAL steht nicht genau einmal")
        erlaubt = {f"scripts/board.py:{heimat[0]}"}
        uebrig = [t for t in treffer if t.replace("\\", "/") not in erlaubt]
        self.assertEqual(uebrig, [], "Endzustands-Literal ausserhalb der einen Heimat: "
                                     + ", ".join(uebrig))

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
