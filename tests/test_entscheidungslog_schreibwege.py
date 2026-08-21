"""Wie viele Schreibwege hat das Entscheidungslog? (SWR-200, platform/T-0049, Sprint 31)

⚠⚠ **Diese Datei prüft eine Annahme, die drei Sprints lang gegolten hat, ohne je geprüft
worden zu sein.** `SWR-195` (Sprint 29) hat fünf Dubletten in `pm` gemessen und daraus
geschlossen: *„also gibt es einen ZWEITEN SCHREIBWEG ins Entscheidungslog, und er hat
keine Nummernvergabe."* Der Schluss war richtig — die **Vermutung über seine Gestalt**
war es nicht.

**Gemessen am 2026-08-21 (vierte Berührung der Frage, Sprint 31):**

| Was | Zahl |
|---|---|
| Entscheidungslogs (Discovery, SWR-128-Familie) | **17** |
| Zeilen `D`/`B` insgesamt | **158** |
| davon `via Inbox` — der Code-Weg `inbox.entscheide` | **55** (35 %) |
| davon `via Session` | **37** (23 %) |
| davon ohne Herkunftsangabe | **66** (42 %) |
| Python-Dateien im Betriebscode, die eine `decision-log.md` **schreiben** | **2** |

> **⚠⚠ Der zweite Schreibweg steht in KEINER Datei. Er ist die HAND — eine Session, die
> die Markdown-Tabelle selbst fortschreibt. Und er ist nicht die Ausnahme, sondern die
> MEHRHEIT: 103 von 158 Zeilen (65 %) stammen nicht aus `inbox.entscheide`.**

⚠ Die Git-Historie der fünf Dubletten zeigt außerdem, dass es **kein
Nebenläufigkeitsfenster** war (Vorabfrage 3 des Tickets, damit beantwortet): `D005` steht
um **07:06** vom Commit-Autor *„Mensch via Inbox"* und um **07:08** noch einmal von
*„ASPICE-Team (Routine-Session)"* — eine Session hat dieselbe Entscheidung zwei Minuten
später ausführlicher **nachgeschrieben** und dabei in der Herkunftsspalte weiter
*„via Inbox"* behauptet. `D005`/`D006` um 07:47 und 22:11 sind echte Klasse-B-Beschlüsse,
die eine bereits vergebene Nummer wiederverwendet haben.

> **Die Herkunftsspalte ist das einzige Merkmal, das die beiden Wege unterscheidet — und
> sie ist die Aussage dessen, der schreibt, über sich selbst. Eine Provenienz, die der
> Beschriebene selbst einträgt, trennt nichts.**

⚠ **Was hier bewusst NICHT gebaut wird** (die Schnittentscheidung der vierten Berührung,
Begründung im Ticket): keine Nummernvergabe für die Hand. Ein Werkzeug, das eine Session
vor dem Schreiben **aufrufen muss**, ist genau die Bauform, die dieses Haus in
`platform/T-0034` ausdrücklich verworfen hat (*„eine weitere Zeile im Runbook"*). Der
Schaden, den es verhindern würde, ist seit Sprint 29/30 bereits gefangen: `SWR-195`
meldet eine Dublette **innerhalb** eines Logs, `SWR-197` dieselbe ID in **zwei**
Einheiten. **Die Frage hat ihre eigene Antwort überlebt.**

Gebaut ist deshalb nur das, was drei Sprints lang gefehlt hat: die Zahl der Code-Wege
steht nicht mehr in einer Vermutung, sondern in einer Zusicherung.

Lehre: L-2026-08-21co.
"""
import ast
import os
import re
import sys
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
sys.path.insert(0, os.path.join(_HIER, ".."))

import board  # noqa: E402

#: Die Wurzel der Organisation — dieselbe Ableitung wie in `lehren.py`.
_WURZEL = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: ⚠ **Die benannte Menge der Code-Schreiber**, nicht ihre Anzahl (`L-2026-08-20by`):
#: eine Zusicherung auf „es sind zwei" kann einen **Tausch** nicht von Stillstand
#: unterscheiden.
#:
#: * `inbox.py` — `entscheide()`, hängt die Zeile an und bezieht die Nummer über
#:   `_naechste_d_id` (`max + 1`).
#: * `pool.py` — legt beim Projektstart eine **leere** Tabelle mit Kopf an; es schreibt
#:   nie eine Entscheidungszeile.
#:
#: Kommt ein dritter dazu, ist das eine Bauentscheidung und gehört gebucht.
CODE_SCHREIBER = frozenset({"inbox.py", "pool.py"})

#: Zeilen einer Entscheidungstabelle. ⚠ `D` **und** `B` — sie teilen sich eine Tabelle,
#: und nur `D` zu lesen prüfte die halbe Datei (`SWR-195`).
LOG_ZEILE = re.compile(r"^\|\s*([DB]\d{3})\s*\|([^|]*)\|([^|]*)\|")


def _logs():
    treffer = []
    for name, basis in board.projekt_pfade(_WURZEL):
        p = os.path.join(basis, "management", "decisions", "decision-log.md")
        if os.path.isfile(p):
            treffer.append((name, p))
    return treffer


def _betriebs_py():
    """Python-Dateien des Betriebscodes — ohne Tests, Parkplatz und Fremdcode."""
    for basis, verz, dateien in os.walk(_WURZEL):
        verz[:] = [d for d in verz if d not in (".git", "node_modules",
                                                "verwaiste-locks", "__pycache__",
                                                "tests")]
        for d in dateien:
            if d.endswith(".py"):
                yield os.path.join(basis, d)


#: Schreibmodi, die eine Entscheidungszeile hinterlassen können.
SCHREIBMODI = ("w", "a", "w+", "a+", "wb", "ab")


def _log_ausdruck(knoten):
    """Baut dieser Ausdruck einen Pfad auf `decision-log.md`? (rein syntaktisch)"""
    for teil in ast.walk(knoten):
        if isinstance(teil, ast.Constant) and isinstance(teil.value, str) \
                and "decision-log" in teil.value:
            return True
    return False


def _code_schreiber():
    """Dateinamen des Betriebscodes, die eine `decision-log.md` zum Schreiben öffnen.

    ⚠ Über den **Syntaxbaum** und mit Verfolgung der Zuweisung: `log_pfad = os.path.join(
    …, "decision-log.md")` gefolgt von `open(log_pfad, "a")` ist derselbe Schreibzugriff
    wie ein Einzeiler — eine zeilenweise Textsuche sieht nur den zweiten.
    """
    gefunden = set()
    for p in _betriebs_py():
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                baum = ast.parse(f.read(), filename=p)
        except (OSError, SyntaxError):
            continue
        log_namen = set()
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.Assign) and _log_ausdruck(knoten.value):
                for ziel in knoten.targets:
                    if isinstance(ziel, ast.Name):
                        log_namen.add(ziel.id)
        for knoten in ast.walk(baum):
            if not (isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Name)
                    and knoten.func.id == "open" and knoten.args):
                continue
            ziel = knoten.args[0]
            trifft = _log_ausdruck(ziel) or (isinstance(ziel, ast.Name)
                                             and ziel.id in log_namen)
            if not trifft:
                continue
            modi = [a.value for a in knoten.args[1:]
                    if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            modi += [kw.value.value for kw in knoten.keywords
                     if kw.arg == "mode" and isinstance(kw.value, ast.Constant)]
            if any(m in SCHREIBMODI for m in modi):
                gefunden.add(os.path.basename(p))
    return gefunden


class GrundmengeTest(unittest.TestCase):
    """SWR-128-Familie: eine kaputte Entdeckung darf nicht grün aussehen."""

    def test_es_gibt_ueberhaupt_entscheidungslogs(self):
        self.assertGreaterEqual(len(_logs()), 2,
                                "weniger als zwei Logs gefunden — die Prüfungen "
                                "darunter messen nichts")

    def test_die_logs_tragen_ueberhaupt_zeilen(self):
        zeilen = 0
        for _, p in _logs():
            with open(p, encoding="utf-8") as f:
                zeilen += sum(1 for ln in f if LOG_ZEILE.match(ln.strip()))
        self.assertGreaterEqual(zeilen, 50,
                                "zu wenige Entscheidungszeilen — Muster oder "
                                "Discovery ist kaputt, nicht der Bestand")


class SchreibwegeTest(unittest.TestCase):
    """⚠⚠ Die Zusicherung, die drei Sprints lang gefehlt hat."""

    def test_nur_die_benannten_dateien_schreiben_ins_entscheidungslog(self):
        """Der zweite Schreibweg ist **nicht** im Code — jetzt geprüft statt vermutet.

        ⚠ Gesucht wird der **Schreibzugriff**, nicht die Erwähnung: eine Datei, die
        `decision-log.md` nur liest oder im Kommentar nennt, ist kein Schreiber. Ohne
        diese Unterscheidung wäre die Zusicherung ein Namensfilter und kein Befund
        (`L-2026-08-20by`: vor dem Löschen Träger prüfen, nicht Namen).

        ⚠⚠ **Der erste Entwurf dieser Zusicherung hat `inbox.py` NICHT gefunden — und
        das war ihr eigener Fehler, nicht der des Bestands.** Sie suchte den Schreibmodus
        in **derselben Zeile** wie den Dateinamen; `inbox.entscheide` legt den Pfad aber
        in `log_pfad` ab und öffnet drei Zeilen später. **Eine Textsuche über eine Zeile
        findet nur den Schreiber, der seinen Pfad nicht zwischenspeichert** — sie hätte
        genau den Weg übersehen, der hier der Hauptweg ist. Deshalb liest die Prüfung
        jetzt den **Syntaxbaum** und verfolgt die Zuweisung.
        """
        gefunden = _code_schreiber()
        self.assertEqual(gefunden, CODE_SCHREIBER, (
            "Die Menge der Code-Schreiber ins Entscheidungslog hat sich geändert: %s. "
            "Ein neuer Schreibweg ohne Nummernvergabe ist genau der Zustand, den "
            "SWR-195 gemessen hat — bitte CODE_SCHREIBER mit Begründung nachziehen."
            % (sorted(gefunden),)))

    def test_die_nummernvergabe_steht_an_genau_einer_stelle(self):
        """`_naechste_d_id` ist die einzige Vergabe — und sie bildet `max + 1`.

        ⚠ Diese Zusicherung ist die Gegenprobe zur vorigen: dass nur zwei Dateien
        schreiben, hilft nichts, wenn die Nummer an mehreren Stellen gebildet wird.
        """
        from backend import inbox
        self.assertTrue(hasattr(inbox, "_naechste_d_id"))
        vergaben = set()
        for p in _betriebs_py():
            with open(p, encoding="utf-8", errors="replace") as f:
                if re.search(r"(?m)^\s*def _naechste_d_id\b", f.read()):
                    vergaben.add(os.path.basename(p))
        self.assertEqual(vergaben, {"inbox.py"},
                         "mehr als eine Nummernvergabe gefunden: %s" % (sorted(vergaben),))

    def test_die_mehrheit_der_zeilen_stammt_NICHT_aus_dem_code_weg(self):
        """⚠⚠ Die Messung, die die Schnittentscheidung trägt — als Zusicherung.

        Wären die Handzeilen eine Randerscheinung, wäre eine Nummernvergabe für sie
        billig zu haben. Gemessen sind sie die **Mehrheit** (103 von 158). Eine
        Nummernvergabe, die 65 % der Fälle nur dann greift, wenn jemand daran denkt,
        ist keine Vergabe, sondern eine Bitte.

        ⚠ Die Schwelle steht bewusst **niedrig** (> 40 %): sie sichert die Aussage
        „nicht die Ausnahme", nicht den Tagesstand. Eine Zusicherung auf 65 % wäre
        beim nächsten Inbox-Klick rot und trainierte das Wegsehen (`SWR-166`).

        ⚠⚠ **Diese Zusicherung ist zugleich der Vertreter von `L-2026-08-21cn`** — *eine
        Zusicherung über eine Auswahl prüft ihren ANTEIL, nicht ihre bloße Existenz*.
        Sie steht hier und nicht bei der Lehren-Prüfung selbst, und das ist kein Zufall:
        `lehren.py` und `test_lehren_vertreter.py` sind aus dem Vertreter-Korpus
        **ausgeschlossen** (`NICHT_VERTRETER`, gegen die Tautologie aus `SWR-194`).

        > **Eine Lehre, die BEI der Vertreter-Prüfung gelernt wird, kann ihren Vertreter
        > nicht IN ihr haben. Sie braucht eine zweite Stelle, an der dieselbe Regel
        > wirklich trägt — und wenn es keine gibt, ist die Regel noch keine.**

        Gefunden hat das die Prüfung selbst, im selben Lauf: `ohne_vertreter` stand
        kurzzeitig bei 92 statt 91 und nannte `L-2026-08-21cn` beim Namen.
        """
        gesamt = code = 0
        for _, p in _logs():
            with open(p, encoding="utf-8") as f:
                for ln in f:
                    m = LOG_ZEILE.match(ln.strip())
                    if not m:
                        continue
                    gesamt += 1
                    if "via inbox" in m.group(3).strip().lower():
                        code += 1
        hand = gesamt - code
        self.assertGreater(hand / max(gesamt, 1), 0.4, (
            "Nur noch %d von %d Zeilen stammen nicht aus dem Code-Weg — die "
            "Schnittbegründung von platform/T-0049 hing an dieser Mehrheit und "
            "braucht dann eine neue Messung." % (hand, gesamt)))


if __name__ == "__main__":
    unittest.main()
