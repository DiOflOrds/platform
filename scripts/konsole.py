#!/usr/bin/env python3
"""Kodierung an den beiden Enden eines Werkzeuglaufs (platform/T-0009).

Anlass: Sprint 5 hat mit `platform/T-0007` die **Leseseite** jedes Subprozess-Aufrufs
fest auf UTF-8 gestellt. Das war richtig für fremde Programme (`git`), hat aber an den
Stellen, an denen Python **Python** aufruft, eine bis dahin funktionierende Paarung
zerstört: der Kindprozess schrieb weiter in der Locale-Kodierung des Hosts (cp1252),
der Elternprozess las UTF-8 — jeder Umlaut wurde zu U+FFFD. Und U+FFFD ist das eine
Zeichen, das cp1252 auf dem Rückweg nicht ausgeben kann.

Zwei Enden, zwei Funktionen — und beide werden gebraucht:

* `kind_umgebung()` sorgt dafür, dass ein Python-Kindprozess in derselben Kodierung
  **schreibt**, in der der Elternprozess **liest**. Das ist die Ursachenbehebung.
* `sichere_ausgabe()` sorgt dafür, dass ein Werkzeug am **Melden** nicht stirbt. Das
  ist keine Absicherung gegen den obigen Fall, sondern gegen einen zweiten, davon
  unabhängigen: die Meldungen dieser Organisation zitieren Ticketinhalte, und 121
  Ticketdateien tragen ein „→", das cp1252 nicht kennt. Ohne diese Funktion beendet
  ein Pfeil in einem Ticket-Titel den Preflight-Lauf mit einem UnicodeEncodeError —
  an genau der Stelle, an der er einen Befund melden wollte.
"""
import os
import sys

# Der Wert, den Python für "so schreibt ein Kindprozess" versteht. Bewusst genau die
# Kodierung, mit der die Aufrufer seit T-0007 lesen — die beiden Zeilen gehören
# zusammen und stehen deshalb hier und nicht je Aufrufstelle.
KIND_KODIERUNG = "utf-8"

# backslashreplace und nicht replace: replace erzeugt U+FFFD, also genau das Zeichen,
# an dem cp1252 scheitert — eine "Reparatur", die den Fehler auf die nächste Stufe
# schiebt (das ist die Lehre aus T-0007). backslashreplace erzeugt reines ASCII und
# ist auf JEDEM Ausgabestrom darstellbar; der Leser sieht → statt eines Pfeils,
# aber er sieht die Meldung.
AUSGABE_FEHLERWEG = "backslashreplace"


def kind_umgebung(env=None):
    """Umgebung für einen Python-Kindprozess, der in UTF-8 schreiben soll.

    Gibt eine **Kopie** zurück (nie os.environ selbst) und setzt darin nur
    PYTHONIOENCODING. Alles andere bleibt stehen — insbesondere PATH und die
    Git-Variablen; eine leere Umgebung wäre eine zweite, größere Änderung.

    Warum nicht `-X utf8`: das wirkt nur bei Aufrufen mit Interpreter-Flags und
    ginge bei `python skript.py` verloren, sobald jemand die Argumentliste umbaut.
    PYTHONIOENCODING hängt am Prozess und nicht an der Kommandozeile.
    """
    neu = dict(os.environ if env is None else env)
    neu["PYTHONIOENCODING"] = KIND_KODIERUNG
    return neu


def sichere_ausgabe(stroeme=None):
    """stdout/stderr so einstellen, dass ein nicht darstellbares Zeichen die Meldung
    beschädigt statt den Lauf zu beenden.

    Ein Werkzeug, dessen Aufgabe das Melden von Befunden ist, darf am Melden nicht
    sterben (L-2026-08-17k, Ausgaberichtung). Die Kodierung des Stroms bleibt
    unangetastet — auf einer deutschen Windows-Konsole weiter cp1252 —, geändert wird
    nur, was bei einem unbekannten Zeichen passiert.

    Rückgabe: Anzahl der tatsächlich umgestellten Ströme (für den Test; ein Strom
    ohne `reconfigure`, etwa eine umgeleitete Pipe in älteren Umgebungen, wird
    übersprungen und nicht zum Fehler gemacht).
    """
    umgestellt = 0
    for strom in (stroeme if stroeme is not None else (sys.stdout, sys.stderr)):
        rekonf = getattr(strom, "reconfigure", None)
        if rekonf is None:
            continue
        try:
            rekonf(errors=AUSGABE_FEHLERWEG)
            umgestellt += 1
        except (ValueError, OSError):
            # Strom lässt sich nicht umstellen (z.B. bereits detached). Der Lauf ist
            # deshalb nicht schlechter dran als vorher — also weiter, nicht abbrechen.
            continue
    return umgestellt
