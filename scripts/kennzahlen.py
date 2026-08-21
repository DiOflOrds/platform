#!/usr/bin/env python3
"""SWR-173/174 (platform/T-0027, VIERTE Berührung): die Kennzahlen des Abschlussberichts

**entstehen** hier, statt in ihn abgeschrieben zu werden — und eine Zusicherung hält den
Bericht dagegen.

⚠⚠ Der Anlass, gezählt statt behauptet. Seit Sprint 18 stand in **fünf** Berichten eine
fortgeschriebene statt einer gemessenen Zahl; zweimal war die Abweichung beziffert
(1155/1128, 1128/1147). **Fünfmal ist sie vor dem Commit gefunden worden — fünfmal durch
Nachrechnen und kein einziges Mal durch eine Zusicherung.**

> **Jede dieser fünf Korrekturen ist ein Beleg dafür, dass die Sorgfalt DA war. Was fehlt,
> ist nicht Aufmerksamkeit, sondern eine Stelle, an der die Zahl ENTSTEHT.** Das ist der
> Satz aus `platform/T-0027` Frage 1, und diese Datei ist seine Antwort.

⚠ **Warum ein Skript und keine Schablone** (Frage 2 des Tickets): der achte Beleg stand in
einem **Fließtext**, den keine Vorlage vorgibt (`9` statt `11` JS-Zusicherungen, in einem
Abschnitt mit der Überschrift *„gezählt, nicht übersehen"*). Was ihn gefunden hat, war ein
Durchlauf über die Datei. Deshalb: messen und **dagegenhalten**, nicht den Bericht
formatieren.

⚠ **Warum der Parkplatz anders behandelt wird als alles andere hier** (der neunte Beleg):
`9506` war zum Zeitpunkt des Lesens bereits falsch — nicht weil jemand geschätzt hätte,
sondern weil die Zahl **ohne ihren Zeitpunkt** dastand.

> **Eine gemessene Zahl ohne den Zeitpunkt ihrer Messung altert genauso lautlos wie eine
> geschätzte.** Deshalb trägt der Block einen Zeitstempel, und `parkplatz` wird
> ausdrücklich **nicht** auf Gleichheit geprüft, sondern nur darauf, dass er einen hat.

Nutzung:

    python platform/scripts/kennzahlen.py --repos .            # Block ausgeben
    python platform/scripts/kennzahlen.py --repos . --schreibe # Block in den Sprintplan setzen
"""
import argparse
import io
import glob
import os
import re
import sys
import unittest
from datetime import datetime

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PLATFORM)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import board  # noqa: E402  — SWR-205: der Endzustand hat EINEN Namen

MARKE_AUF = "<!-- kennzahlen v1"
MARKE_ZU = "-->"
PLAN = os.path.join("pm", "management", "sprint-aktuell.md")

# ⚠ Die Felder, die auf GLEICHHEIT geprüft werden. `parkplatz` steht bewusst nicht hier:
# er ist eine Momentaufnahme und wächst zwischen Messung und Lesen weiter (der neunte
# Beleg von T-0027). Er wird trotzdem gemessen und ausgegeben — mit Zeitstempel.
VERGLEICHSFELDER = ("tests", "testdateien", "swr", "luecken", "briefkasten_offen",
                    "tickets_offen", "wartet_auf_mensch", "briefe_im_lauf")


def zaehle_tests(root):
    """Tests in der Sammlung und Zahl der Testdateien — die Zahl, die fünfmal falsch war.

    ⚠ Gezählt wird die **Sammlung**, nicht die Summe von Testläufen. Genau deren
    Auseinanderlaufen hat in Sprint 24 den Fehler aufgedeckt (1201 vs. 1208): die Blöcke
    waren nach einer Dateiliste geschnitten, die sich **während** des Laufs geändert hatte.
    Eine Quelle, nicht zwei.
    """
    tests_dir = os.path.join(root, "platform", "tests")
    loader = unittest.defaultTestLoader
    alt = os.getcwd()
    try:
        os.chdir(os.path.join(root, "platform"))
        suite = loader.discover("tests")
    finally:
        os.chdir(alt)

    def tief(x):
        return sum(tief(y) for y in x) if hasattr(x, "__iter__") else 1

    dateien = [f for f in os.listdir(tests_dir)
               if f.startswith("test_") and f.endswith(".py")]
    return tief(suite), len(dateien), list(loader.errors or [])


def lies_matrix(root):
    """SWR-Zahl und Lückenzahl aus dem generierten Matrixbericht — nicht aus dem Gedächtnis."""
    pfad = os.path.join(root, "p0", "verification", "reports", "swr-test-matrix.md")
    if not os.path.isfile(pfad):
        return None, None
    with io.open(pfad, encoding="utf-8") as f:
        kopf = f.read(4000)
    m = re.search(r"SWRs:\s*(\d+)", kopf)
    swr = int(m.group(1)) if m else None
    luecken = len(re.findall(r"\|\s*—\s*\|\s*0 Test", kopf))
    # Die Lücken stehen als Zeilen ohne Test; der Generator meldet sie beim --check.
    tabelle = io.open(pfad, encoding="utf-8").read()
    luecken = len(re.findall(r"\|\s*0 Test\(s\)\s*\|", tabelle))
    return swr, luecken


def _frontmatter(pfad):
    try:
        with io.open(pfad, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return {}
    teile = text.split("---")
    if len(teile) < 3:
        return {}
    d = {}
    for zeile in teile[1].splitlines():
        if ":" in zeile:
            k, _, v = zeile.partition(":")
            d[k.strip()] = v.strip().strip('"')
    return d


def zaehle_briefkasten(root):
    """Offene Briefe über ALLE Einheiten — der Brief ist das Erste, was eine Session anfasst.

    ⚠ SWR-206 (platform/T-0057): die Auflösung steht ab hier in `board.briefkasten_dateien`
    und nicht mehr als eigener Glob. Bis Sprint 33 waren es zwei Wege zu derselben Frage.
    """
    return sum(1 for _e, pfad in board.briefkasten_dateien(root)
               if board.brief_offen(pfad))


def zaehle_briefe_im_lauf(root, seit=None):
    """SWR-206: Wie viele Briefe sind seit `seit` (Default: Start des laufenden Sprints)
    eingegangen — **unabhängig davon, ob sie noch offen sind**.

    ⚠⚠ **Diese Größe existiert, weil ihr Fehlen einen falschen Satz möglich gemacht hat.**
    Der Abschlussbericht von Sprint 31 sagt wörtlich *„Briefkasten: 0 offen, keiner
    eingegangen"* — gemessen am **Anfang**. Im Fenster dieses Sprints (06:13–07:23) sind
    **sieben** Briefe eingegangen; Sprint 31 endete 20 Minuten nach dem letzten, ohne
    einen davon gesehen zu haben, und Sprint 32 hat sie am nächsten Morgen gefunden und
    dem **eigenen** Lauf zugeschrieben.

    > **„0 offen" ist eine Aussage über einen Zeitpunkt. „Keiner eingegangen" ist eine
    > Aussage über ein Zeitfenster. Der Bericht hat die erste gemessen und die zweite
    > behauptet — und dieselbe Zahl trug beide Sätze.**

    Gemessen über alle 21 Briefe seit Registerbeginn: **16** (76 %) kamen, während ein
    Sprint lief. Der späte Brief ist damit **die Regel und nicht die Ausnahme** — das ist
    die Antwort auf DoD 1 des Tickets, und sie hat den Bau bestimmt: eine Nachprüfung am
    Ende genügt nicht als Empfehlung, die Größe gehört in den Kennzahlenblock.
    """
    if seit is None:
        seit = _sprint_start(root)
    if seit is None:
        return None
    anzahl = 0
    for _e, pfad in board.briefkasten_dateien(root):
        zeit = (_frontmatter(pfad).get("zeit") or "").strip()
        if not zeit:
            continue
        try:
            wert = datetime.fromisoformat(zeit.replace("Z", "+00:00"))
        except ValueError:
            continue  # ein unlesbarer Zeitstempel ist kein Ereignis, das wir erfinden
        # ⚠⚠ **Der teuerste Fehler dieses Sprints saß in dieser einen Zeile.** Briefe
        # tragen ihre Zeit in **UTC** (`briefkasten.py`: `datetime.now(timezone.utc)`),
        # das Sprintregister in **Wanduhrzeit** (`sprint_register.py`: `datetime.now()`).
        # Der erste Bau hat `.replace(tzinfo=None)` benutzt — das wirft den Offset weg
        # statt umzurechnen — und damit einen UTC-Wert gegen einen Ortszeit-Wert
        # verglichen. Bei CEST sind das zwei Stunden; bei Sprintlängen von ein bis zwei
        # Stunden hätte die Kennzahl **immer 0** gemeldet.
        #
        # > **Eine Größe, die den Satz „keiner eingegangen" verhindern sollte, hätte ihn
        # > maschinell erzeugt. Und sie hat, bevor das Gegenlesen sie fand, bereits eine
        # > ANFORDERUNG mit einer falschen Aussage gefüllt (SWR-206, erste Fassung).**
        if wert.tzinfo is not None:
            wert = wert.astimezone().replace(tzinfo=None)
        if wert >= seit:
            anzahl += 1
    return anzahl


def _sprint_start(root):
    """Startzeitpunkt des laufenden Sprints — oder `None`, wenn keiner läuft.

    ⚠ `None` heißt **unbekannt** und nie **null**: eine fehlende Antwort in eine
    beruhigende zu verwandeln ist der Vorgabewert-Fehler aus Sprint 32.
    """
    datei = os.path.join(root, "pm", "management", "sprints.jsonl")
    if not os.path.isfile(datei):
        return None
    import json
    sprints = {}
    try:
        with open(datei, encoding="utf-8") as f:
            for zeile in f:
                zeile = zeile.strip()
                if not zeile:
                    continue
                eintrag = json.loads(zeile)
                sprints.setdefault(eintrag["kennung"], {}).update(eintrag)
    except (OSError, ValueError, KeyError):
        return None
    laufend = [s for s in sprints.values()
               if s.get("nr") and s.get("start") and not s.get("ende")]
    if not laufend:
        return None
    neuester = max(laufend, key=lambda s: s["nr"])
    try:
        return datetime.strptime(neuester["start"], "%Y-%m-%d %H:%M")
    except ValueError:
        return None


# SWR-202 (platform/T-0053): „nicht geschlossen" steht ab hier an EINER Stelle.
#
# `SWR-113` (Sprint 7, pm/T-0046) hat die Zählweise festgelegt — und die Festlegung stand
# in einem **Docstring** und in **keiner Zusicherung**. Zwanzig Sprints später ist
# `kennzahlen.py` entstanden und hat sie nicht übernommen; nicht aus Widerspruch, sondern
# weil nichts sie vertrat. Das ist wörtlich `SWR-125`: eine Entscheidung, die keine
# Prüfung mitgeändert hat, ist eine Absichtserklärung.
# ⚠ SWR-205 (platform/T-0054, Sprint 33): der Name bleibt, die MENGE wohnt ab hier
# in `board.STATUS_FINAL`. `SWR-202` hat diese Konstante angelegt und dabei den
# vierten Namen fuer dieselbe Sache erzeugt — eine Heilung, die die Bauform des
# Befunds wiederholt hat.
ENDZUSTAENDE = board.STATUS_FINAL


def zaehle_tickets(root):
    """Offene Tickets und die davon, die auf einen Menschen warten.

    ⚠⚠ **Die Messung hat die Frage des Tickets umgestellt.** `platform/T-0053` fragte,
    welche von **zwei** Zählweisen bleibt (9 gegen 12). Gezählt sind **drei** Erzeuger
    derselben Größe, und das Ergebnis ist keine Mehrheitsentscheidung:

    | Erzeuger | Name | Zahl | Definition |
    |---|---|---|---|
    | `sprint.kennzahlen` | `offen_gesamt` | **12** | nicht `done`/`rejected` (`SWR-113`) |
    | `aggregation.uebersicht` | `tickets_offen` | **12** | nicht `done`/`rejected` (`SWR-113`) |
    | `kennzahlen.zaehle_tickets` | `tickets_offen` | **9** | `status == "open"` |

    > **Zwei von drei Erzeugern folgten der Festlegung bereits — und ausgerechnet die
    > beiden, die sich den NAMEN `tickets_offen` teilen, waren die, die sich
    > widersprachen.** Die Alternative des Tickets („eine Zahl ODER zwei Namen") ist damit
    > gegenstandslos: es gibt nicht zwei berechtigte Größen unter einem Namen, sondern
    > **eine** Größe mit einem abweichenden Erzeuger — dem jüngsten.

    Die Differenz sind genau die **3 gesperrten** Tickets. Ein `blocked`-Ticket ist nicht
    geschlossen; es aus der Zahl „offen" zu nehmen hieße, dass eine Sperre eine Aufgabe
    zum Verschwinden bringt — und das ist die Bauform, gegen die `SWR-193` gebaut wurde.

    ⚠ `warten` zählt aus **derselben** Grundmenge. Liefe es weiter über `== "open"`,
    entstünde genau der Fehler, den `test_offene_tickets_und_wartende_haengen_zusammen`
    seit Sprint 24 fängt: zwei Zahlen über zwei Mengen, die niemand zusammen liest.
    """
    offen = warten = 0
    muster = [os.path.join(root, "*", "tickets", "T-*.md"),
              os.path.join(root, "*", "*", "tickets", "T-*.md")]
    gesehen = set()
    for m in muster:
        for pfad in glob.glob(m):
            echt = os.path.realpath(pfad)
            if echt in gesehen or os.sep + "templates" + os.sep in pfad:
                continue
            gesehen.add(echt)
            fm = _frontmatter(pfad)
            if (fm.get("status") or "") in ENDZUSTAENDE:
                continue
            offen += 1
            if fm.get("typ") == "decision-request":
                warten += 1
    return offen, warten


def zaehle_parkplatz(root):
    """⚠ Momentaufnahme, ausdrücklich KEIN Befund — und ohne Zeitstempel wertlos."""
    n = 0
    for eintrag in sorted(os.listdir(root)):
        pfad = os.path.join(root, eintrag, ".git", "verwaiste-locks")
        if os.path.isdir(pfad):
            n += sum(len(fs) for _, _, fs in os.walk(pfad))
    return n


def miss(root):
    """Alle Kennzahlen aus ihren Quellen — genau einmal je Zahl."""
    tests, dateien, fehler = zaehle_tests(root)
    swr, luecken = lies_matrix(root)
    offen, warten = zaehle_tickets(root)
    return {
        "tests": tests,
        "testdateien": dateien,
        "ladefehler": len(fehler),
        "swr": swr,
        "luecken": luecken,
        "briefkasten_offen": zaehle_briefkasten(root),
        # SWR-206: die Aussage ueber das FENSTER, nicht ueber den Zeitpunkt.
        "briefe_im_lauf": zaehle_briefe_im_lauf(root),
        "tickets_offen": offen,
        "wartet_auf_mensch": warten,
        "parkplatz": zaehle_parkplatz(root),
    }


def block(werte, sprint=None, zeitpunkt=None):
    """Der kanonische Block. ⚠ Der Zeitstempel gehört dazu und ist nicht Zierrat."""
    zp = zeitpunkt or datetime.now().strftime("%Y-%m-%d %H:%M")
    kopf = f"{MARKE_AUF} | gemessen {zp}"
    if sprint:
        kopf += f" | sprint {sprint}"
    zeilen = " ".join(f"{k}={werte[k]}" for k in sorted(werte) if werte[k] is not None)
    return f"{kopf}\n{zeilen}\n{MARKE_ZU}"


def lies_block(text):
    """Den Block aus einem Bericht lesen: (werte, zeitpunkt) — ({}, '') wenn keiner da ist."""
    m = re.search(re.escape(MARKE_AUF) + r"(.*?)\n(.*?)\n\s*" + re.escape(MARKE_ZU),
                  text, re.S)
    if not m:
        return {}, ""
    zp = re.search(r"gemessen\s+([0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2})", m.group(1))
    werte = {}
    for k, v in re.findall(r"(\w+)=(-?\d+)", m.group(2)):
        werte[k] = int(v)
    return werte, (zp.group(1) if zp else "")


def vergleiche(bericht, gemessen):
    """Abweichungen zwischen Bericht und Messung — Liste von (Feld, im Bericht, gemessen).

    ⚠ Geprüft werden nur `VERGLEICHSFELDER`. Eine Zahl, die im Bericht **fehlt**, ist
    ebenfalls eine Abweichung — sonst wäre ein Bericht ohne Zahlen der grünste von allen,
    und das ist genau der Fehler, den SWR-128 fünf Sprints lang verborgen hat.
    """
    ab = []
    for feld in VERGLEICHSFELDER:
        soll = gemessen.get(feld)
        if soll is None:
            continue
        ist = bericht.get(feld)
        if ist != soll:
            ab.append((feld, ist, soll))
    return ab


def main(argv=None):
    p = argparse.ArgumentParser(description="Kennzahlen des Abschlussberichts messen (T-0027)")
    p.add_argument("--repos", default=".")
    p.add_argument("--sprint", default="")
    p.add_argument("--schreibe", action="store_true",
                   help="Block in pm/management/sprint-aktuell.md setzen/ersetzen")
    a = p.parse_args(argv)
    root = os.path.abspath(a.repos)
    werte = miss(root)
    b = block(werte, a.sprint or None)
    print(b)
    if a.schreibe:
        pfad = os.path.join(root, PLAN)
        text = io.open(pfad, encoding="utf-8").read()
        muster = re.compile(re.escape(MARKE_AUF) + r".*?" + re.escape(MARKE_ZU), re.S)
        text = muster.sub(b, text, count=1) if muster.search(text) else text.rstrip() + "\n\n" + b + "\n"
        io.open(pfad, "w", encoding="utf-8", newline="\n").write(text)
        print(f"-> geschrieben nach {PLAN}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    # platform/T-0009: am Melden nicht sterben. ⚠ Diese Zeile fehlte im ersten Entwurf und
    # ist von `test_konsole.RegelUeberDenGesamtenProduktionscode` rot gemacht worden — zum
    # SECHSTEN Lauf in Folge hat eine ältere Zusicherung den frischen Entwurf verworfen,
    # und in Sprint 25 traf es dieselbe Regel und ebenfalls ein neues Skript
    # (`scripts/organigramm.py`). Ein Werkzeug, das Kennzahlen mit Umlauten und ⚠ ausgibt,
    # ist genau der Fall, für den sie geschrieben wurde.
    import konsole
    konsole.sichere_ausgabe()
    sys.exit(main())
