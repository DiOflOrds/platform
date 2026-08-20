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

⚠ **Sprint 23 (SWR-162): aus 10 s sind rund 36 s geworden**, weil der Pfadfilter jetzt
jede Tiefe abdeckt. Die billige Fassung hatte das Sammel-Repo `projects` (p10/p11/p12)
drei Sprints lang **gar nicht angesehen** — *eine Prüfung, die zwei Drittel prüft, ist
nicht zwei Drittel so gut, sie ist grün.*

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
#: ⚠⚠ **52 → 56 in Sprint 23, und der Grund ist keine neue Historie, sondern ein blinder
#: Fleck der Prüfung selbst.** `status_wechsel` filterte auf `tickets/` **relativ zur
#: Repo-Wurzel**. Im Sammel-Repo `projects` (pm/D003, ab P10) liegen die Tickets eine Ebene
#: tiefer (`p11/tickets/`) — der Filter traf dort **nichts**, und **66 Statuswechsel von
#: p10/p11/p12 sind seit SWR-118 (Sprint 9) nie geprüft worden**. Darin verborgen: vier
#: Altfälle und ein neuer.
#:
#:     **Die Prüfung war grün, weil sie ein Drittel des Bestands gar nicht angesehen hat.
#:     Eine Prüfung, die auf einem Bestand grün ist, in dem der geprüfte Zustand nicht
#:     vorkommt, prüft nichts — hier fehlte nicht der Zustand, sondern der Bestand.**
#:
#: ⚠ Die Zahl wird **erhöht und nicht der Stichtag verschoben**: die vier Altfälle liegen
#: nachweislich vor dem 2026-08-17 07:10 und sind keine frischen Verstöße. Ihr fünfter
#: Nachbar liegt **danach** und bleibt deshalb ein Befund (SWR-162).
ALTBESTAND_ERWARTET = 56

_SHA = re.compile(r"^\x00([0-9a-f]{7,40}) (\d+)$")
_ZIEL = re.compile(r"^\+\+\+ b/(.+)$")
_STATUS_ALT = re.compile(r"^-status:\s*(\S+)")
_STATUS_NEU = re.compile(r"^\+status:\s*(\S+)")
#: SWR-162: eine Ticketdatei, gleich wie tief sie liegt. `tickets/T-0001.md` ebenso wie
#: `p11/tickets/T-0013.md`.
_IST_TICKET = re.compile(r"(^|/)tickets/[^/]+$")


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


def zugefuegte_zeilen(repo, relpfad):
    """SWR-159: [(sha, commitzeit_iso, zeile)] — die Zeilen, die eine Datei je Commit BEKAM.

    Das allgemeine Gegenstück zu `status_wechsel`: dort interessiert der Wechsel eines
    Feldes, hier die **neue Zeile selbst** — und mit ihr der Commit, der sie mitgenommen
    hat, samt seiner Zeit. Für eine append-only-Datei ist das ihre gesamte Entstehung.

    ⚠ **Warum das Git-Lesen hier steht und nicht in `sprint_register`.** Der Sprintzähler
    darf nach SWR-134/136 kein git aufrufen: auf diesem Mount hinterlässt schon ein
    lesender Aufruf eine `index.lock`, die nicht mehr gelöscht werden kann, und eine
    Prüfung auf Nebenläufigkeit, die selbst sperrt, ist ihr eigener Schadensfall. Dieses
    Modul liest ohnehin Historie und trägt die Kosten bereits (Messung im Modulkopf) —
    die **Zeitregel** bleibt drüben, wo `_wanduhr()` wohnt. Zwei Rechnungen über dieselbe
    Uhr wären B033, und genau daraus ist `platform/T-0026` entstanden.

    Rückgabe `None` = **nicht prüfbar** (kein Repo, kein Erfolg). Eine leere Liste heißt
    „geprüft, nichts gefunden" — die beiden zu verwechseln ist SWR-108/135.
    """
    if not os.path.isdir(os.path.join(repo, ".git")):
        return None
    rel = relpfad.replace(os.sep, "/")
    out = subprocess.run(
        ["git", "-C", repo, "log", "--reverse", "--no-merges", "-U0",
         "--format=%x00%H|%cI", "--", rel],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        return None
    zeilen, sha, czeit = [], None, None
    for zeile in out.stdout.splitlines():
        if zeile.startswith("\x00"):
            kopf = zeile[1:].split("|", 1)
            sha, czeit = (kopf + [None])[0], (kopf[1] if len(kopf) == 2 else None)
            continue
        if czeit and zeile.startswith("+") and not zeile.startswith("+++"):
            zeilen.append((sha, czeit, zeile[1:]))
    return zeilen


def status_wechsel(repo):
    """[(sha, zeit, datei, alt, neu)] — die committeten Statuswechsel eines Repos.

    EIN `git log` je Repo (siehe Kostenmessung im Modulkopf). `-U0` liefert nur die
    geänderten Zeilen; eine Neuanlage hat kein `-status:` und ist damit kein Wechsel,
    sondern ein Anfangszustand — genau richtig, denn ein neues Ticket kommt aus keinem
    Vorzustand.
    """
    if not os.path.isdir(os.path.join(repo, ".git")):
        return []
    # SWR-162: Pfadfilter mit **Tiefenzusicherung**, dazu ein Filter am Dateinamen.
    #
    # ⚠⚠ Bis Sprint 23 stand hier `-- tickets/`, und das ist **relativ zur Repo-Wurzel**.
    # Im Sammel-Repo `projects` (pm/D003, ab P10) liegen die Tickets eine Ebene tiefer;
    # der Filter traf dort nichts, und p10/p11/p12 sind seit SWR-118 **nie** geprüft
    # worden — 66 Statuswechsel, darunter fünf unzulässige.
    #
    # ⚠ `*/tickets/` wäre die naheliegende Reparatur und die falsche: ohne `:(glob)`
    # behandelt git Pfadangaben als Präfixe, und die nächste Verschachtelungsebene wäre
    # wieder unsichtbar. `:(glob)**/tickets/*` sagt ausdrücklich „in jeder Tiefe".
    #
    # ⚠⚠ Der erste Entwurf liess den Filter GANZ weg und behauptete im Kommentar, das
    # koste „rund 2 s". Das war **geschätzt und danebengelegt** — der sechste Beleg für
    # `platform/T-0027`, im selben Lauf, in dem das Ticket aufgemacht wurde.
    #
    # ⚠ Nachgemessen am echten Bestand, `platform` allein: `tickets/` **3,24 s** ·
    # `:(glob)**/tickets/*` **4,87 s** · ohne jeden Filter **7,68 s**. Über alle 17 Repos
    # steigt der Gesamtlauf dieser Prüfung damit von rund **10 s** auf rund **36 s**.
    #
    # ⚠ **Das ist teurer, und es wird trotzdem bezahlt.** Die billige Fassung hat drei
    # Sprints lang ein Drittel des Bestands nicht angesehen: *eine Prüfung, die zwei
    # Drittel prüft, ist nicht zwei Drittel so gut, sie ist grün.* Der Preflight ohne
    # Tests wächst damit von rund 60 s auf rund 85 s — genannt, damit die nächste
    # Beschleunigung weiss, was sie aufgibt.
    #
    # ⚠ Zusätzlich wird am Dateinamen gefiltert: ein Pfadmuster ist eine Vorauswahl, die
    # Zusicherung über den Gegenstand steht in `_IST_TICKET`.
    out = subprocess.run(
        ["git", "-C", repo, "log", "--reverse", "-U0", "--format=%x00%H %ct",
         "--", ":(glob)**/tickets/*"],
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
            if alt and alt != t.group(1) and _IST_TICKET.search(datei):
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


def _repo_wurzel(basis, root):
    """SWR-162: das Git-Repo, zu dem `basis` gehört — auch wenn es weiter oben liegt.

    Ein Projekt im Sammel-Repo (`projects/p11`, pm/D003) hat kein eigenes `.git`; seine
    Historie steht im Sammel-Repo. Wer nur `basis/.git` prüft, überspringt es **ganz**.

    Gesucht wird nach oben bis `root` einschliesslich; darüber hinaus nicht — sonst fände
    die Prüfung das Repo, in dem der Bestand zufällig liegt, und behauptete Zuständigkeit
    für fremde Historie.
    """
    pfad = os.path.abspath(basis)
    grenze = os.path.abspath(root)
    while True:
        if os.path.isdir(os.path.join(pfad, ".git")):
            return pfad
        if pfad == grenze or os.path.dirname(pfad) == pfad:
            return None
        pfad = os.path.dirname(pfad)


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
        #
        # ⚠⚠ SWR-162: **genau das stand hier als Kommentar und tat der Code NICHT.** Er
        # setzte `wurzel = None`, sobald `basis/.git` fehlte, und übersprang den Eintrag —
        # also jedes Projekt im Sammel-Repo `projects` (p10, p11, p12). Zusammen mit dem
        # Pfadfilter `tickets/` in `status_wechsel` war das Sammel-Repo damit auf **zwei**
        # Wegen unsichtbar, und beide sahen für sich harmlos aus.
        #
        #     **Ein Kommentar, der beschreibt, was der Code tun soll, ist keine
        #     Zusicherung. Hier hat er drei Sprints lang das Gegenteil dessen behauptet,
        #     was danebenstand — und niemand hat die beiden verglichen.**
        wurzel = _repo_wurzel(basis, root)
        if wurzel is None or wurzel in gesehen:
            continue
        gesehen.add(wurzel)
        # ⚠ Der Name des REPOS, nicht des ersten darin gefundenen Projekts. Sonst hiesse
        # ein Befund aus `projects` „p10/p11/tickets/T-0009.md" — eine Referenz, die es
        # nirgends gibt und die beim Nachschlagen ins Leere führt (B038: eine Meldung
        # muss ihren Gegenstand AUFFINDBAR nennen).
        a, b = pruefe_repo(wurzel, os.path.basename(wurzel) if os.path.abspath(wurzel)
                           != os.path.abspath(basis) else name, stichtag)
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
