# -*- coding: utf-8 -*-
"""entscheidungs_ids.py (SWR-197, platform/T-0047): wo Entscheidungs-IDs mehrdeutig werden.

⚠⚠ **Dieses Modul ist an einer Messung gebaut, die die Frage des Tickets verändert hat —
zum dritten Mal in vier Sprints.** `T-0036` hatte gezählt: **1003** Zitatstellen ohne
Repo-Präfix gegen 319 mit, und dabei selbst gewarnt, *„die 1003 sind nicht 1003
Probleme"*. `T-0047` sollte die **ehrliche Untermenge** bilden. Gemessen am 2026-08-21
über 803 Markdown-Dateien:

| Lage der praefixlosen Zitatstelle | Zahl | Anteil |
|---|---|---|
| **im besitzenden Repo** — die Datei sagt, wo sie liegt | 743 | 73 % |
| außerhalb, aber die ID ist nur **einmal** vergeben → auflösbar | 65 | 6 % |
| **außerhalb UND die ID ist mehrfach vergeben** → echt mehrdeutig | **214** | **21 %** |
| ID nirgends im Log vergeben (Altlast) | 1 | 0 % |

⚠⚠ **Und dann kam der Befund, der den Bau bestimmt hat: alle 214 nennen eine von
VIERZEHN IDs — `D000` bis `D013`.** Ab `D014` ist jede ID organisationsweit genau einmal
vergeben; dort ist ein praefixloses Zitat **schon heute eindeutig**.

> **Der Mangel ist ein PRÄFIX DES NUMMERNRAUMS und keine Eigenschaft des Korpus.**

Damit ist die Bauform **gefunden und nicht erfunden** — dieselbe Bewegung wie bei
`platform/T-0034`, wo die Messung die Grundmenge von 108 auf 34 gesenkt und damit die
Bauart bestimmt hat.

⚠ **Was dieses Modul deshalb NICHT tut:** es macht keine Zitatstelle rot. 1023 wären
`SWR-166` ein drittes Mal, und 214 wären es auch. Gehalten wird die **Menge der
mehrdeutigen IDs** — sie steht bei vierzehn, und wächst sie, fällt das mit Namen auf.

⚠ **Der einzige Weg, auf dem der Schaden wachsen kann**, ist ein Repo, dessen erstes
Entscheidungslog wieder bei `D001` zu zählen beginnt (`_naechste_d_id` bildet `max + 1`
**je Log**). Genau den fängt diese Prüfung. Sie ergänzt `SWR-195` statt es zu
wiederholen: dort dieselbe ID **zweimal in einem** Log (ein Fehler), hier dieselbe ID in
**zwei** Logs (kein Fehler, aber die Quelle der Mehrdeutigkeit).

⚠ Der Prüfer liegt in `.py`, der geprüfte Korpus besteht aus `.md`: er kann seine eigene
Frage nicht beantworten (`L-2026-08-21ch` — *eine Prüfung, die sich selbst liest, prüft
nicht mehr*).
"""
import collections
import os
import re

#: Eine Zeile des Entscheidungslogs. `D` **und** `B` teilen sich die Tabelle; hier zählt
#: nur `D` — die `B`-Reihe ist je Log fortlaufend und wird nirgends repo-übergreifend
#: zitiert. ⚠ Der Unterschied ist gemessen und nicht angenommen: `SWR-195` liest beide,
#: weil es Dubletten **innerhalb** einer Datei sucht; hier geht es um Zitierbarkeit.
LOG_ZEILE = re.compile(r"^\|\s*\*{0,2}(D\d{3})\*{0,2}\s*\|", re.M)
#: Zitat **mit** Repo-Präfix (`pm/D010`) — die Form, die dieses Ticket zur Pflichtform für
#: neu geschriebene Berichte machen wollte.
ZITAT_MIT = re.compile(r"\b([a-z0-9][a-z0-9\-]*)/(D\d{3})\b")
#: Zitat **ohne** Präfix. ⚠ Wird erst gesucht, nachdem die Treffer von `ZITAT_MIT`
#: entfernt sind — sonst zählte `pm/D010` in beiden Mengen.
ZITAT_OHNE = re.compile(r"(?<![\w/])(D\d{3})\b")
#: Verzeichnisse, die kein Korpus sind.
AUSGESCHLOSSEN = {".git", "node_modules", "verwaiste-locks", "__pycache__"}

#: ⚠⚠ **Der benannte Altbestand — gemessen am 2026-08-21, nicht gesetzt.** Vierzehn IDs
#: sind in mehr als einer Einheit vergeben. Sie sind **kein Befund**: die Logs sind
#: append-only, und dieses Haus schreibt Historie nicht um (Playbook Kap. 16). Dieselbe
#: Kategorie wie die fortgeschriebenen Statusübergänge und der Dubletten-Altbestand von
#: `SWR-195` — gemeldet, namentlich, nicht blockierend.
#:
#: ⚠ Als **Menge** geführt und nicht als Zahl (`L-2026-08-20by`): eine Zahl sagt nicht,
#: welche verschwunden ist.
ALTBESTAND_MEHRDEUTIG = frozenset(
    "D%03d" % n for n in range(14)  # D000 … D013
)


def _wurzel(start=None):
    """Die Organisationswurzel: der Ordner, der `process/` und mehrere Einheiten trägt."""
    p = os.path.abspath(start or os.path.join(os.path.dirname(__file__), "..", ".."))
    return p


def _md_dateien(wurzel):
    for root, dirs, files in os.walk(wurzel):
        dirs[:] = [d for d in dirs if d not in AUSGESCHLOSSEN]
        for f in files:
            if f.endswith(".md"):
                yield os.path.join(root, f)


def _einheit(wurzel, pfad):
    """Die Einheit, in der eine Datei liegt — `''` für Dateien in der Wurzel.

    ⚠ Wurzeldateien (`PROJEKTSTATUS-UPDATE.md`) gehören **keiner** Einheit, und das ist
    kein Sonderfall, sondern der Kern: dort ist jedes praefixlose Zitat mehrdeutig, weil
    die Datei selbst nichts über den Ort aussagt. Sie sind der größte Einzelposten der
    ehrlichen Untermenge (47 von 214).
    """
    rel = os.path.relpath(pfad, wurzel).replace("\\", "/")
    teile = rel.split("/")
    return teile[0] if len(teile) > 1 else ""


def vergabe(wurzel=None):
    """`{D-ID: {Einheit, …}}` aus **jedem** Entscheidungslog der Discovery.

    ⚠ Grundmenge ist, was gefunden wird — keine Liste, die jemand in ein Ticket getippt
    hat (`SWR-128`-Familie, dieselbe Stelle in Sprint 26, 27, 28 und 29).
    """
    wurzel = _wurzel(wurzel)
    aus = collections.defaultdict(set)
    for p in _md_dateien(wurzel):
        if "decision-log" not in os.path.basename(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            for m in LOG_ZEILE.finditer(f.read()):
                aus[m.group(1)].add(_einheit(wurzel, p))
    return dict(aus)


def logs_gefunden(wurzel=None):
    """Wie viele Entscheidungslogs gelesen wurden — die Grundmenge der Prüfung.

    ⚠ Ohne sie wäre „sauberer Bestand" von „Discovery kaputt" nicht zu unterscheiden
    (`SWR-128/165`): eine Prüfung, die null Dateien liest, findet ebenfalls nichts.
    """
    wurzel = _wurzel(wurzel)
    return sum(1 for p in _md_dateien(wurzel) if "decision-log" in os.path.basename(p))


def mehrdeutige(wurzel=None):
    """Die IDs, die in **mehr als einer** Einheit vergeben sind — heute die Quelle allen Schadens."""
    return {i: sorted(e) for i, e in vergabe(wurzel).items() if len(e) > 1}


def befund(wurzel=None):
    """Die Sperrklinke: `[]` heißt, die mehrdeutige Menge steht unverändert bei vierzehn.

    Zwei Richtungen, und beide sind nötig:

    * **neu** — eine ID wird in einer zweiten Einheit vergeben: der Schaden wächst, und
      genau das soll auffallen, solange es eine einzige Zeile ist statt zweihundert
      Zitatstellen.
    * **verschwunden** — eine benannte ID ist nicht mehr doppelt vergeben: die Logs sind
      append-only, eine Zeile verschwindet dort nicht von allein. Ohne diese Richtung wäre
      ein gelöschtes Log grün (dieselbe Gegenrichtung wie in `SWR-195`).
    """
    ist = mehrdeutige(wurzel)
    aus = []
    for i in sorted(set(ist) - ALTBESTAND_MEHRDEUTIG):
        aus.append(f"NEU mehrdeutig: {i} ist in mehreren Einheiten vergeben "
                   f"({', '.join(ist[i])}) — ein praefixloses Zitat dieser ID ist ab jetzt "
                   f"nicht mehr auflösbar. Pflichtform: <einheit>/{i}.")
    for i in sorted(ALTBESTAND_MEHRDEUTIG - set(ist)):
        aus.append(f"VERSCHWUNDEN: {i} war am 2026-08-21 in mehreren Einheiten vergeben und "
                   f"ist es nicht mehr — Entscheidungslogs sind append-only (Kap. 16).")
    return aus


def zitat_bericht(wurzel=None):
    """Die Zitatzahlen — **berichtet, nicht blockierend** (`SWR-174`: mit Zeitpunkt).

    Rückgabe: `{gesamt, im_eigenen, aufloesbar, mehrdeutig, unbekannt, dateien}`.

    ⚠ Die drei Lagen sind **getrennt** und nicht summiert, weil genau das Zusammenwerfen
    die 1003 erzeugt hat, die keine 1003 Probleme waren.
    """
    wurzel = _wurzel(wurzel)
    besitzer = vergabe(wurzel)
    mehrfach = {i for i, e in besitzer.items() if len(e) > 1}
    z = dict(gesamt=0, im_eigenen=0, aufloesbar=0, mehrdeutig=0, unbekannt=0, dateien=0)
    for p in _md_dateien(wurzel):
        z["dateien"] += 1
        einheit = _einheit(wurzel, p)
        with open(p, encoding="utf-8", errors="replace") as f:
            txt = ZITAT_MIT.sub(" ", f.read())
        for m in ZITAT_OHNE.finditer(txt):
            did = m.group(1)
            z["gesamt"] += 1
            eigner = besitzer.get(did)
            if not eigner:
                z["unbekannt"] += 1
            elif einheit and einheit in eigner:
                z["im_eigenen"] += 1
            elif did in mehrfach:
                z["mehrdeutig"] += 1
            else:
                z["aufloesbar"] += 1
    return z
