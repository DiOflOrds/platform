#!/usr/bin/env python3
"""sprint_register.py — der Sprintzähler der Organisation (SWR-106, pm/T-0041).

Nach `pm/D006` ist **jeder Routine-Lauf ein Sprint**. Ab SWR-106 wird nicht mehr auf
Kalenderdaten geplant, sondern auf **Sprintnummern**: `geplant_sprint: 42` heißt „das
Team fasst es im 42. Lauf an".

Damit braucht die Organisation genau eine Stelle, die sagt, der wievielte Lauf gerade
läuft. Das ist diese Datei: `pm/management/sprints.jsonl`, eine Zeile je Sprint,
nur angehängt, nie umgeschrieben.

**Warum nicht aus der Git-Historie gezählt.** Das wäre die naheliegende Lösung ohne
neue Datei — und es ist genau der Fehler aus **B056**: eine Session schreibt mehrfach
(am 16.08.: 42 Commits auf rund 30 Läufe), Commits sind also keine Läufe. Eine Zahl,
die sich wie eine Messung liest und eine Schätzung ist, wäre B027/B038.

**Warum eine Kennung statt eines Zeitfensters.** `beginne()` verlangt eine `kennung`,
die der Lauf sich selbst gibt und für seine Dauer behält. Ruft derselbe Lauf zweimal
auf, bekommt er dieselbe Nummer. Die Alternative — „innerhalb von N Minuten ist es
derselbe Lauf" — würde raten; die Identität eines Laufs ist ein Fakt, den der Lauf
nennen kann, und keiner, den man aus Uhrzeiten erschließt.

Nutzung:
    python sprint_register.py --repos <wurzel> [--beginne KENNUNG] [--takt-min 60]
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

REGISTER = os.path.join("pm", "management", "sprints.jsonl")
TAKT_MIN_STANDARD = 60  # Routine-Session laeuft stuendlich (Stand 2026-08-17)


def _pfad(root):
    return os.path.join(root, *REGISTER.split(os.sep) if os.sep in REGISTER
                        else REGISTER.split("/"))


def lies(root):
    """Alle Sprintzeilen, aelteste zuerst. Kaputte Zeilen werden uebersprungen.

    Eine unlesbare Zeile darf den Zaehler nicht zum Stillstand bringen — sie darf
    ihn aber auch nicht zuruecksetzen. Deshalb ueberspringen und weiterzaehlen,
    nicht abbrechen und nicht bei 0 anfangen.
    """
    pfad = _pfad(root)
    if not os.path.isfile(pfad):
        return []
    zeilen = []
    try:
        with open(pfad, encoding="utf-8") as f:
            for z in f:
                z = z.strip()
                if not z:
                    continue
                try:
                    e = json.loads(z)
                except ValueError:
                    continue
                if isinstance(e, dict) and isinstance(e.get("nr"), int):
                    zeilen.append(e)
    except OSError:
        return []
    return sorted(zeilen, key=lambda e: e["nr"])


def aktuell(root):
    """Nummer des laufenden (zuletzt begonnenen) Sprints; 0 = noch keiner."""
    z = lies(root)
    return z[-1]["nr"] if z else 0


def takt_minuten(root, standard=TAKT_MIN_STANDARD):
    """Taktlaenge des letzten Sprints — die Grundlage jeder Zeitschaetzung."""
    z = lies(root)
    for e in reversed(z):
        if isinstance(e.get("takt_min"), int) and e["takt_min"] > 0:
            return e["takt_min"]
    return standard


def beginne(root, kennung, jetzt=None, takt_min=TAKT_MIN_STANDARD, notiz=""):
    """Neuen Sprint eroeffnen und seine Nummer zurueckgeben — **idempotent**.

    Ist `kennung` schon im Register, wird nichts angehaengt und die vorhandene
    Nummer zurueckgegeben. Ein Lauf, der zweimal startet (Wiederholung nach
    Fehler, zweiter Aufruf im selben Skript), erhoeht den Zaehler nicht.
    """
    kennung = str(kennung or "").strip()
    if not kennung:
        raise ValueError("beginne() braucht eine Kennung des Laufs")
    bestand = lies(root)
    for e in bestand:
        if e.get("kennung") == kennung:
            return e["nr"]
    nr = (bestand[-1]["nr"] + 1) if bestand else 1
    eintrag = {"nr": nr, "kennung": kennung,
               "start": (jetzt or datetime.now()).strftime("%Y-%m-%d %H:%M"),
               "takt_min": int(takt_min)}
    if notiz:
        eintrag["notiz"] = str(notiz)
    pfad = _pfad(root)
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(eintrag, ensure_ascii=False) + "\n")
    return nr


def geschaetzte_zeit(ziel_nr, root=None, jetzt=None, jetzt_nr=None, takt_min=None):
    """SWR-106: Wann faellt Sprint `ziel_nr` voraussichtlich? -> datetime.

    **Eine Schaetzung und keine Zusage** — sie unterstellt, dass die Routine
    ununterbrochen im gemessenen Takt weiterlaeuft. Sie existiert nur fuer die
    Kreuzpruefung gegen `frist`; niemand plant damit. Steht die Cowork-App still,
    kommt der Sprint spaeter, und genau darum ist ein Datum an einer Zusage an
    den Menschen weiterhin ein Datum (Entscheidung des Auftraggebers 2026-08-17:
    beide Felder parallel).
    """
    if jetzt_nr is None:
        jetzt_nr = aktuell(root) if root else 0
    if takt_min is None:
        takt_min = takt_minuten(root) if root else TAKT_MIN_STANDARD
    return (jetzt or datetime.now()) + timedelta(minutes=max(0, ziel_nr - jetzt_nr) * takt_min)


def main(argv=None):
    p = argparse.ArgumentParser(description="Sprintzaehler der Organisation (SWR-106)")
    p.add_argument("--repos", default=".")
    p.add_argument("--beginne", metavar="KENNUNG",
                   help="neuen Sprint mit dieser Laufkennung eroeffnen (idempotent)")
    p.add_argument("--takt-min", type=int, default=TAKT_MIN_STANDARD)
    p.add_argument("--notiz", default="")
    a = p.parse_args(argv)
    root = os.path.abspath(a.repos)
    if a.beginne:
        nr = beginne(root, a.beginne, takt_min=a.takt_min, notiz=a.notiz)
        print(f"Sprint {nr} (Takt {takt_minuten(root)} Min)")
    else:
        print(f"Sprint {aktuell(root)} (Takt {takt_minuten(root)} Min, "
              f"{len(lies(root))} Eintraege)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
