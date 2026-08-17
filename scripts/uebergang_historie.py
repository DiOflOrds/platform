#!/usr/bin/env python3
"""uebergang_historie.py — die Statusübergänge in der COMMITTETEN Historie (SWR-118,
pm/T-0048).

**Der Befund.** In Sprint 7 sind zwei Tickets — `pm/T-0043` und
`team-dashboard/T-0002` — von `open` direkt auf `done` gegangen, in **einem einzigen
Commit**. `UEBERGAENGE` verbietet das. Gemeldet hat es niemand.

**Warum niemand.** `board.py --check` hält den Status der **Arbeitskopie** gegen den in
`HEAD` (`status_in_head`). Das ist richtig für einen **ungespeicherten** Sprung und
blind für einen **gespeicherten**: sobald der Sprung committet ist, sagen beide Seiten
dasselbe. Das Ergebnis der Prüfung hing damit an der **Reihenfolge der Session** — wer
erst committet und dann prüft, bekommt keinen Befund; wer erst prüft, bekommt einen.

**Und SWR-110 verschärft das, statt es zu mildern.** Sie macht eine unverbuchte
Ticketdatei zum Befund und drängt damit auf frühes Committen: je zuverlässiger
committet wird, desto häufiger ist der Sprung schon in HEAD, wenn jemand hinsieht.

Dieses Modul liest deshalb den **Sachverhalt** statt des Zeitpunkts: die Folge der
`status:`-Werte, die eine Ticketdatei in der Historie durchlaufen hat. Sie ändert sich
nicht dadurch, wann man sie abfragt. Das ist die Antwort der Familie L-2026-08-17o
Regel 4 — *läuft die Prüfung vor oder nach dem Zeitpunkt, an dem der Fehler Schaden
anrichtet?* — für diesen Fall: sie hängt an gar keinem Zeitpunkt mehr.

**Kosten, gemessen statt geschätzt.** Das Ticket nannte die Historienprüfung „teuer".
Am echten Bestand: **ein** `git log` je Repo über `tickets/` kostet zusammen rund
**10 s** gegen einen Preflight, der ohne Tests ohnehin rund **60 s** braucht. Ein
Aufruf je Datei wären mehrere hundert — deshalb ein Aufruf je Repo, und deshalb war
„teuer" als Verschiebungsgrund nicht haltbar, sobald man nachgesehen hat.

Nutzung:
    python uebergang_historie.py --repos <wurzel>
"""
import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import board  # noqa: E402

# ---------------------------------------------------------------------------
# ⚠ Der Altbestand — und warum er nicht aus zwei Einträgen besteht
# ---------------------------------------------------------------------------
# `pm/T-0048` nannte **zwei** Altfälle (`pm/T-0043`, `team-dashboard/T-0002`) und
# fragte, was mit ihnen geschehen soll. Der erste Lauf dieser Prüfung über den echten
# Bestand fand **52**:
#
#     28 × open -> done          21 × open -> in_review
#      2 × done -> open           1 × in_progress -> done
#     p1 (15), pm (10), p2 (9), p0 (7), p3 (5), p4 (4), platform (1), team-dashboard (1)
#
# Die beiden genannten sind zwei der 28. Sie fielen nicht auf, weil sie schlimmer
# gewesen wären, sondern weil in Sprint 7 gerade jemand hinsah — SWR-110 war frisch
# gebaut. **Die Fehlerart ist kein Unfall aus Sprint 7, sondern der Normalfall seit
# dem ersten Sprint.** Genau das war die Aussage, die im Ticket ungeprüft stand: eine
# Zahl, die niemand erhoben hatte, und die um den Faktor 25 danebenlag.
#
# Deshalb ist der Altbestand keine Liste von Einträgen, sondern ein **Stichtag**.
# 50 Einträge von Hand zu pflegen wäre ein Register, das niemand liest, und jede
# Ergänzung sähe aus wie die 51. Zeile einer schon vorhandenen Liste.
#
# Nicht rückwirkend geglättet wird trotzdem nichts (pm/T-0048 Punkt 2,
# L-2026-08-17g Regel 4): der Altbestand wird **gemeldet**, nur blockiert er nicht.
#
#: Zeitpunkt, ab dem ein Verstoß blockiert — der Beginn von Sprint 9, in dem diese
#: Prüfung entstanden ist (`pm/management/sprints.jsonl`).
STICHTAG = "2026-08-17 07:10"

#: ⚠ Die festgenagelte Größe des Altbestands. Sie hat zwei Aufgaben, und die zweite
#: ist die wichtigere:
#:
#: 1. **Der Stichtag lässt sich nicht still verschieben.** Wer ihn nach vorn zieht, um
#:    einen frischen Verstoß loszuwerden, ändert damit diese Zahl — und die Abweichung
#:    ist ein Befund. Ohne sie wäre ein Stichtag genau das, wovor ein Register aus
#:    Einträgen bewahren sollte: ein Ort zum stillen Parken.
#: 2. **Sie merkt, wenn jemand die Historie umschreibt.** Der Altbestand kann sich
#:    sonst gar nicht ändern — er liegt in der Vergangenheit. Ändert er sich doch, ist
#:    ein `rebase`/`filter-branch` gelaufen, und genau das verbietet
#:    L-2026-08-17g Regel 4.
ALTBESTAND_ERWARTET = 52

_SHA = re.compile(r"^\x00([0-9a-f]{7,40}) (\d+)$")
_ZIEL = re.compile(r"^\+\+\+ b/(.+)$")
_STATUS_ALT = re.compile(r"^-status:\s*(\S+)")
_STATUS_NEU = re.compile(r"^\+status:\s*(\S+)")


#: Woran erkannt wird, dass die geprüfte Wurzel **dieser** Bestand ist.
#:
#: ⚠ Beim ersten Gesamtlauf hat `test_preflight` diesen Fehler gefunden: über einer
#: leeren Wurzel meldete die Prüfung „Altbestand hat 0, erwartet sind 52" — ein
#: Fehlalarm, und zwar ein grundsätzlicher. `ALTBESTAND_ERWARTET` ist eine **Messung
#: an einem bestimmten Bestand**, keine allgemeine Eigenschaft von Ticket-Repos. Sie
#: gegen eine beliebige Wurzel zu halten ist ein Kategorienfehler.
#:
#: Erkannt wird das an der Datei, aus der auch der Stichtag stammt — dem
#: Sprintregister. Das ist eine **benannte Vorbedingung** und kein Raten an
#: Ordnernamen. Fehlt sie, wird der Altbestand weiterhin gezählt und gemeldet, aber
#: über seine Größe wird nichts behauptet.
BESTANDSMARKE = os.path.join("pm", "management", "sprints.jsonl")


def _ist_dieser_bestand(root):
    return os.path.exists(os.path.join(root, BESTANDSMARKE))


def _stichtag_stempel(text=STICHTAG):
    from datetime import datetime
    return datetime.strptime(text, "%Y-%m-%d %H:%M").timestamp()


def status_wechsel(repo):
    """[(sha, zeit, datei, alt, neu)] — die committeten Statuswechsel eines Repos.

    EIN `git log` je Repo (siehe Kostenmessung im Modulkopf). `-U0` liefert nur die
    geänderten Zeilen; eine Neuanlage hat kein `-status:` und ist damit kein Wechsel,
    sondern ein Anfangszustand — genau richtig, denn ein neues Ticket kommt aus keinem
    Vorzustand.
    """
    if not os.path.isdir(os.path.join(repo, ".git")):
        return []
    out = subprocess.run(
        ["git", "-C", repo, "log", "--reverse", "-U0", "--format=%x00%H %ct", "--",
         "tickets/"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0 or not out.stdout:
        return []
    wechsel, sha, zeit, datei, alt = [], None, 0, None, None
    for zeile in out.stdout.splitlines():
        t = _SHA.match(zeile)
        if t:
            sha, zeit, datei, alt = t.group(1), int(t.group(2)), None, None
            continue
        t = _ZIEL.match(zeile)
        if t:
            datei, alt = t.group(1), None
            continue
        t = _STATUS_ALT.match(zeile)
        if t:
            alt = t.group(1)
            continue
        t = _STATUS_NEU.match(zeile)
        if t and datei and sha:
            if alt and alt != t.group(1):
                wechsel.append((sha, zeit, datei, alt, t.group(1)))
            alt = None
    return wechsel


def _rollen(repo):
    """{datei: rolle} aus der ARBEITSKOPIE — für die Mensch-Ausnahme.

    Sie wird am Ticket gelesen und nicht am Dateinamen: `rolle: mensch` trägt eine
    verhaltensändernde Bedeutung (Gate, Übergänge frei), und die Ausnahme muss an
    diesem Sachverhalt hängen, nicht an einer Namenskonvention (dieselbe Regel, die
    SWR-110 für die `Stand:`-Ausnahme durchgesetzt hat).
    """
    rollen = {}
    verz = os.path.join(repo, "tickets")
    if not os.path.isdir(verz):
        return rollen
    for name in sorted(os.listdir(verz)):
        if not name.endswith(".md"):
            continue
        try:
            with open(os.path.join(verz, name), encoding="utf-8") as f:
                fm, _ = board.parse_frontmatter(f.read())
        except OSError:
            continue
        rollen["tickets/%s" % name] = (fm or {}).get("rolle")
    return rollen


def pruefe_repo(repo, name=None, stichtag=None):
    """(neue_befunde, altbestand) für ein Repo.

    `neue` sind Verstöße **ab** dem Stichtag — sie blockieren. `altbestand` liegt davor
    und wird gemeldet, ohne zu blockieren: nicht geglättet, aber auch kein Dauerbefund,
    der das Wegsehen trainiert.
    """
    name = name or os.path.basename(os.path.abspath(repo))
    grenze = _stichtag_stempel() if stichtag is None else stichtag
    rollen = _rollen(repo)
    neue, alt_liste = [], []
    for sha, zeit, datei, alt, neu in status_wechsel(repo):
        if rollen.get(datei) == "mensch":
            continue  # Gates: Übergänge frei (pm/T-0048 Punkt 3, unverändert)
        if alt not in board.STATUS or neu not in board.STATUS:
            continue
        if neu in board.UEBERGAENGE.get(alt, []):
            continue
        text = "%s/%s: %s -> %s (Commit %s)" % (name, datei, alt, neu, sha[:7])
        (neue if zeit >= grenze else alt_liste).append(text)
    return neue, alt_liste


def pruefe_alle(root, stichtag=None):
    """Über alle entdeckten Projekt-Repos.

    Rückgabe `(neue, altbestand, register)`. `register` trägt den Befund über den
    **Altbestand selbst**: weicht seine Größe von `ALTBESTAND_ERWARTET` ab, ist
    entweder der Stichtag verschoben oder die Historie umgeschrieben worden — beides
    Dinge, die nicht still passieren dürfen.
    """
    neue, altbestand = [], []
    gesehen = set()
    for name, basis in board.projekt_pfade(root):
        # Projekte im Sammel-Repo teilen sich dessen .git — dann zaehlt das Sammel-Repo.
        wurzel = basis if os.path.isdir(os.path.join(basis, ".git")) else None
        if wurzel is None:
            continue
        if wurzel in gesehen:
            continue
        gesehen.add(wurzel)
        a, b = pruefe_repo(wurzel, name, stichtag)
        neue += a
        altbestand += b
    register = []
    if stichtag is None and _ist_dieser_bestand(root) \
            and len(altbestand) != ALTBESTAND_ERWARTET:
        register.append(
            "Altbestand hat %d Eintraege, erwartet sind %d — entweder ist der Stichtag "
            "(%s) verschoben oder die Historie wurde umgeschrieben."
            % (len(altbestand), ALTBESTAND_ERWARTET, STICHTAG))
    return neue, altbestand, register


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repos", default=".")
    args = p.parse_args()
    neue, altbestand, register = pruefe_alle(args.repos)
    # Der Altbestand wird IMMER gemeldet, auch wenn er nicht blockiert — sonst waere
    # er nach einem Lauf aus dem Blick, und „nicht geglaettet" hiesse nur „nicht
    # aufgeraeumt" statt „weiter sichtbar" (pm/T-0048 Punkt 2).
    print("[org] Altbestand unzulaessiger Statusuebergaenge (vor %s, bewusst nicht "
          "geglaettet): %d." % (STICHTAG, len(altbestand)))
    for z in register:
        print("[org] BEFUND: " + z)
    if neue:
        print("[org] BEFUND: %d unzulaessige(r) Statusuebergang/-uebergaenge seit dem "
              "Stichtag" % len(neue))
        for z in neue:
            print("    " + z)
    else:
        print("[org] Unzulaessige Statusuebergaenge seit dem Stichtag: 0.")
    return 1 if (neue or register) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import konsole
    konsole.sichere_ausgabe()
    sys.exit(main())
