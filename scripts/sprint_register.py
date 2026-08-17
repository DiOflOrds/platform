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

**SWR-136 (platform/T-0013): das Register kennt ein ENDE.** Bis Sprint 14 mass es
Lauferöffnungen und nicht Laufenden — es eröffnete klaglos einen neuen Sprint, während
der vorige noch schrieb. Der Schaden ist zweimal an einem Tag eingetreten (10:25 und
13:19), beim zweiten Mal mit Folgen: zwei Läufe vergaben dieselbe Anforderungsnummer.

Ab SWR-136 ist eine Zeile **ohne `ende` ein laufender Sprint**, und `beginne()`
verweigert die Eröffnung, solange einer läuft.

⚠ **Die Datei bleibt append-only — deshalb sind ihre Zeilen ab hier EREIGNISSE.**
`ende`, `abgebrochen` und `spur` kommen als eigene Zeile mit derselben `kennung` dazu
und werden beim Lesen in den Sprint gefaltet. Eine bestehende Zeile umzuschreiben wäre
der bequemere Weg und gleichzeitig der einzige, der bei zwei gleichzeitigen Schreibern
Daten verliert: genau der Fall, den dieses Modul verhindern soll. Ein Anhängen einer
kurzen Zeile ist unter `O_APPEND` unteilbar, ein Umschreiben nicht.

⚠ **Der Abbruch wird an SCHREIBSPUREN erkannt, nicht an der Uhr** (DoD 3 des Tickets,
korrigiert nach der Messung aus Sprint 13: 12 Abstände, Median 57 Min, Minimum **15**,
**7 von 12 unter 60**). Eine Zeitgrenze („weniger als ein Takt") hätte die Mehrheit der
regulären Folgeläufe abgewiesen. Eine Uhr kann einen arbeitenden Lauf nach 15 Minuten
nicht von einem abgestürzten nach 15 Minuten unterscheiden; nur die Schreibspur kann es.

Der Ablauf ohne jede Zeitgrenze:

1. `beginne()` findet einen Sprint ohne `ende` → misst die Schreibspur aller Repos,
   hängt sie als Beobachtung an und **verweigert** (nennt den laufenden Sprint).
2. Der **nächste** Lauf misst erneut. Hat sich die Spur bewegt, arbeitet der andere
   noch → wieder verweigert, neue Beobachtung. Hat sie sich **nicht** bewegt, ist seit
   der letzten Beobachtung nichts geschrieben worden → der Sprint gilt als abgebrochen,
   bekommt `ende` **mit** `abgebrochen: true` (DoD 6: `ende` auch im Abbruchfall, sonst
   wäre jede zweite Zeile ohne `ende` und die Prüfung eine Dauerwarnung), und die
   Eröffnung ist erlaubt.

Die Wartezeit ist damit **ein Takt** und nicht unendlich — ein Lauf, der stirbt, sperrt
die Routine nicht für immer, und ein Lauf, der arbeitet, wird nicht überholt.

Nutzung:
    python sprint_register.py --repos <wurzel> [--beginne KENNUNG] [--takt-min 60]
    python sprint_register.py --repos <wurzel> --beende KENNUNG
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

REGISTER = os.path.join("pm", "management", "sprints.jsonl")
TAKT_MIN_STANDARD = 60  # Routine-Session laeuft stuendlich (Stand 2026-08-17)

# SWR-136: Stichtag der Ende-Pflicht. Die Sprints 1-14 liefen, bevor `beende()` existierte,
# und tragen deshalb kein `ende`. Sie ruecknachzutragen waere eine erfundene Messung (B038);
# sie als Befund zu melden hiesse, die Pruefung am Tag ihrer Einfuehrung 14-fach rot zu
# starten und damit das Wegsehen zu trainieren — dieselbe Falle wie bei den 42 Altbestands-DRs
# in SWR-131. Ab diesem Sprint ist ein fehlendes `ende` ein Befund.
STICHTAG_ENDE_SPRINT = 15


class SprintLaeuft(RuntimeError):
    """`beginne()` verweigert: ein Sprint ohne `ende` schreibt noch (SWR-136).

    Traegt die Nummer und die Kennung des laufenden Sprints als Felder, damit der
    abgewiesene Lauf sie **nennen** kann statt nur zu scheitern (B038: eine Meldung
    ohne den Gegenstand ist keine Meldung).
    """

    def __init__(self, nr, kennung, spur_bewegt):
        self.nr = nr
        self.kennung = kennung
        self.spur_bewegt = spur_bewegt
        grund = ("er hat seit der letzten Beobachtung geschrieben"
                 if spur_bewegt else "erste Beobachtung, Spur jetzt vermerkt")
        super().__init__(
            f"Sprint {nr} ({kennung}) laeuft noch und traegt kein 'ende' — {grund}. "
            f"Dieser Lauf darf nicht schreiben. Der naechste Lauf uebernimmt, "
            f"wenn bis dahin keine weitere Schreibspur hinzukommt.")


def _pfad(root):
    return os.path.join(root, *REGISTER.split(os.sep) if os.sep in REGISTER
                        else REGISTER.split("/"))


def ereignisse(root):
    """Alle Zeilen der Datei als rohe Ereignisse, in Dateireihenfolge (SWR-136).

    Kaputte Zeilen werden uebersprungen: eine unlesbare Zeile darf den Zaehler nicht zum
    Stillstand bringen — sie darf ihn aber auch nicht zuruecksetzen. Deshalb
    ueberspringen und weiterzaehlen, nicht abbrechen und nicht bei 0 anfangen.
    """
    pfad = _pfad(root)
    if not os.path.isfile(pfad):
        return []
    roh = []
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
                if isinstance(e, dict):
                    roh.append(e)
    except OSError:
        return []
    return roh


def lies(root):
    """Alle Sprints, aelteste zuerst — Ereignisse in den Sprint **gefaltet** (SWR-136).

    Eine Zeile mit `nr` eroeffnet einen Sprint; jede spaetere Zeile mit derselben
    `kennung` und **ohne** `nr` ist eine Ergaenzung (`ende`, `abgebrochen`, `spur`) und
    wird in den Sprint hineingefaltet, spaeter gewinnt.

    ⚠ Damit bleibt die Datei append-only und `lies()` gibt trotzdem **einen** Stand je
    Sprint zurueck. Alle bisherigen Leser (`aktuell`, `takt_minuten`, `backend.sprint`)
    sehen weiter genau das, was sie vorher sahen — die Ergaenzungen sind zusaetzliche
    Schluessel, keine zusaetzlichen Eintraege.
    """
    sprints, nach_kennung = [], {}
    for e in ereignisse(root):
        if isinstance(e.get("nr"), int):
            eintrag = dict(e)
            sprints.append(eintrag)
            k = e.get("kennung")
            if k:
                nach_kennung[k] = eintrag
            continue
        k = e.get("kennung")
        ziel = nach_kennung.get(k)
        if ziel is None:
            continue  # Ergaenzung zu einem unbekannten Lauf: nichts zu falten
        for schluessel, wert in e.items():
            if schluessel == "kennung":
                continue
            ziel[schluessel] = wert
    return sorted(sprints, key=lambda e: e["nr"])


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


def _kopf_sha(repo):
    """SHA von HEAD eines Repos — **ohne** Git-Aufruf, direkt von der Platte.

    ⚠ Absichtlich kein `subprocess`: SWR-134 hat gemessen, dass auf diesem Mount schon
    ein **lesendes** `git status` eine `index.lock` hinterlaesst, die nicht mehr
    geloescht werden kann. Eine Pruefung, die Nebenlaeufigkeit erkennen soll und dabei
    selbst Sperren erzeugt, waere ihr eigener Schadensfall.

    `""`, wenn der Kopf nicht lesbar ist. Ein unlesbarer Kopf ist **keine** Bewegung.
    """
    git = os.path.join(repo, ".git")
    if os.path.isfile(git):  # worktree/submodule: "gitdir: <pfad>"
        try:
            with open(git, encoding="utf-8") as f:
                zeile = f.read().strip()
            if zeile.startswith("gitdir:"):
                git = os.path.normpath(os.path.join(repo, zeile.split(":", 1)[1].strip()))
        except OSError:
            return ""
    kopf = os.path.join(git, "HEAD")
    try:
        with open(kopf, encoding="utf-8") as f:
            inhalt = f.read().strip()
    except OSError:
        return ""
    if not inhalt.startswith("ref:"):
        return inhalt  # abgekoppelter Kopf: der SHA steht direkt drin
    ref = inhalt.split(":", 1)[1].strip()
    losdatei = os.path.join(git, *ref.split("/"))
    try:
        with open(losdatei, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        pass
    try:  # gepackte Referenzen
        with open(os.path.join(git, "packed-refs"), encoding="utf-8") as f:
            for z in f:
                z = z.strip()
                if z.endswith(" " + ref):
                    return z.split(" ", 1)[0]
    except OSError:
        pass
    return ""


def schreibspur(root):
    """Fingerabdruck **aller** Repo-Koepfe unter `root` — die Schreibspur (SWR-136).

    Zwei Aufrufe mit demselben Ergebnis heissen: seit dem ersten hat **kein** Repo einen
    Commit bekommen. Das ist die Messung, die einen arbeitenden Lauf von einem
    abgestuerzten unterscheidet — und die eine Uhr nicht leisten kann.

    ⚠ Bewusst der Kopf und nicht die Uhrzeit des letzten Commits: eine Zeit kann sich
    wiederholen (zwei Commits in derselben Minute), ein SHA nicht.
    """
    teile = []
    try:
        namen = sorted(os.listdir(root))
    except OSError:
        return ""
    for name in namen:
        pfad = os.path.join(root, name)
        if not os.path.isdir(pfad):
            continue
        if not os.path.exists(os.path.join(pfad, ".git")):
            continue
        sha = _kopf_sha(pfad)
        if sha:
            teile.append(f"{name}={sha}")
    return ";".join(teile)


def laufender(root):
    """Der Sprint ohne `ende`, oder `None`. Eine Zeile ohne `ende` ist ein Laufender.

    Geprueft wird ausdruecklich nur der **letzte** Sprint: aeltere ohne `ende` sind
    Buchhaltungsluecken (dafuer gibt es `nicht_beendete`), aber sie blockieren nichts.
    Ein Register, das an Sprint 3 haengt, haette die Routine dauerhaft gesperrt.
    """
    bestand = lies(root)
    if not bestand:
        return None
    letzter = bestand[-1]
    return None if letzter.get("ende") else letzter


def nicht_beendete(root, stichtag=STICHTAG_ENDE_SPRINT):
    """Sprints ab `stichtag`, die kein `ende` tragen und **nicht** der laufende sind.

    Das ist der Befund, den der Preflight liest (DoD 4 von platform/T-0013 — nach
    SWR-122 legt eine neue Pruefung im selben Zug fest, wer ihr Ergebnis liest).

    ⚠ Der **laufende** Sprint ist ausgenommen, und das ist DoD 6: waehrend eines Laufs
    traegt seine eigene Zeile naturgemaess kein `ende`. Ihn mitzuzaehlen hiesse, in
    jedem Lauf einen Befund zu melden — eine Dauerwarnung, die nach zwei Sprints
    niemand mehr liest.
    """
    bestand = lies(root)
    if not bestand:
        return []
    letzte_nr = bestand[-1]["nr"]
    return [e for e in bestand
            if e["nr"] >= stichtag and e["nr"] != letzte_nr and not e.get("ende")]


def _haenge_an(root, eintrag):
    pfad = _pfad(root)
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(eintrag, ensure_ascii=False) + "\n")


def beende(root, kennung, jetzt=None, abgebrochen=False, notiz=""):
    """Den Sprint `kennung` schliessen: `ende` als eigenes Ereignis anhaengen (SWR-136).

    Idempotent wie `beginne()`: ein zweiter Aufruf haengt nichts an. Ein Lauf, der
    seinen Abschluss wiederholt, erfindet keinen zweiten Endezeitpunkt.

    Rueckgabe: die Sprintnummer, oder `None` bei unbekannter Kennung.
    """
    kennung = str(kennung or "").strip()
    if not kennung:
        raise ValueError("beende() braucht eine Kennung des Laufs")
    for e in lies(root):
        if e.get("kennung") != kennung:
            continue
        if e.get("ende"):
            return e["nr"]
        ereignis = {"kennung": kennung,
                    "ende": (jetzt or datetime.now()).strftime("%Y-%m-%d %H:%M")}
        if abgebrochen:
            ereignis["abgebrochen"] = True
        if notiz:
            ereignis["ende_notiz"] = str(notiz)
        _haenge_an(root, ereignis)
        return e["nr"]
    return None


def beginne(root, kennung, jetzt=None, takt_min=TAKT_MIN_STANDARD, notiz=""):
    """Neuen Sprint eroeffnen und seine Nummer zurueckgeben — **idempotent**.

    Ist `kennung` schon im Register, wird nichts angehaengt und die vorhandene
    Nummer zurueckgegeben. Ein Lauf, der zweimal startet (Wiederholung nach
    Fehler, zweiter Aufruf im selben Skript), erhoeht den Zaehler nicht.

    ⚠ **SWR-136:** laeuft noch ein Sprint (Zeile ohne `ende`), wird die Eroeffnung
    verweigert (`SprintLaeuft`) — es sei denn, die Schreibspur belegt, dass seit der
    letzten Beobachtung nichts geschrieben wurde; dann gilt er als abgebrochen, bekommt
    `ende` mit `abgebrochen: true` und die Eroeffnung ist erlaubt.

    **Keine Zeitgrenze und keine Zwangsoption.** Die Zeitgrenze ist an der Messung aus
    Sprint 13 gescheitert (Minimum 15 Min, 7 von 12 Abstaenden unter dem Takt); eine
    Zwangsoption waere binnen zweier Laeufe der Normalfall und die Pruefung damit
    wirkungslos.
    """
    kennung = str(kennung or "").strip()
    if not kennung:
        raise ValueError("beginne() braucht eine Kennung des Laufs")
    bestand = lies(root)
    for e in bestand:
        if e.get("kennung") == kennung:
            return e["nr"]
    alt = laufender(root)
    if alt is not None:
        jetzige_spur = schreibspur(root)
        vorige_spur = alt.get("spur")
        if vorige_spur is None or vorige_spur != jetzige_spur:
            # Erste Beobachtung oder Spur bewegt: der andere Lauf arbeitet (oder wir
            # wissen es noch nicht). Beobachtung anhaengen und abweisen.
            _haenge_an(root, {"kennung": alt.get("kennung"), "spur": jetzige_spur,
                              "beobachtet_von": kennung,
                              "beobachtet": (jetzt or datetime.now()).strftime(
                                  "%Y-%m-%d %H:%M")})
            raise SprintLaeuft(alt["nr"], alt.get("kennung"),
                               spur_bewegt=vorige_spur is not None)
        # Spur unbewegt seit der letzten Beobachtung -> abgebrochen. `ende` wird AUCH
        # hier geschrieben (DoD 6), sonst bliebe die Zeile fuer immer "laufend".
        beende(root, alt.get("kennung"), jetzt=jetzt, abgebrochen=True,
               notiz=f"abgebrochen: keine Schreibspur seit der Beobachtung, "
                     f"festgestellt von {kennung}")
        bestand = lies(root)
    nr = (bestand[-1]["nr"] + 1) if bestand else 1
    eintrag = {"nr": nr, "kennung": kennung,
               "start": (jetzt or datetime.now()).strftime("%Y-%m-%d %H:%M"),
               "takt_min": int(takt_min)}
    if notiz:
        eintrag["notiz"] = str(notiz)
    _haenge_an(root, eintrag)
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
    p.add_argument("--beende", metavar="KENNUNG",
                   help="den Sprint dieser Laufkennung schliessen (SWR-136, idempotent)")
    p.add_argument("--takt-min", type=int, default=TAKT_MIN_STANDARD)
    p.add_argument("--notiz", default="")
    a = p.parse_args(argv)
    root = os.path.abspath(a.repos)
    if a.beginne:
        try:
            nr = beginne(root, a.beginne, takt_min=a.takt_min, notiz=a.notiz)
        except SprintLaeuft as fehler:
            # Rueckgabewert 2, nicht 1: "abgewiesen, weil ein anderer laeuft" ist kein
            # Programmfehler, sondern das erwartete Ergebnis der Pruefung. Ein Aufrufer
            # muss die beiden Faelle unterscheiden koennen.
            print(f"VERWEIGERT: {fehler}")
            return 2
        print(f"Sprint {nr} (Takt {takt_minuten(root)} Min)")
    elif a.beende:
        nr = beende(root, a.beende, notiz=a.notiz)
        if nr is None:
            print(f"VERWEIGERT: Kennung {a.beende} steht nicht im Register")
            return 2
        print(f"Sprint {nr} beendet")
    else:
        offen = laufender(root)
        print(f"Sprint {aktuell(root)} (Takt {takt_minuten(root)} Min, "
              f"{len(lies(root))} Eintraege, "
              f"{'laeuft' if offen else 'beendet'})")
        luecken = nicht_beendete(root)
        if luecken:
            print(f"BEFUND: {len(luecken)} Sprint(s) ohne 'ende': "
                  + ", ".join(str(e['nr']) for e in luecken))
    return 0


if __name__ == "__main__":
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import konsole
    konsole.sichere_ausgabe()  # platform/T-0009: am Melden nicht sterben
    sys.exit(main())
