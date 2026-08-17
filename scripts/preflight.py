#!/usr/bin/env python3
"""Session-/Tick-Preflight (p0/T-0024, Retro-CR 1/3 aus Sprint 2).

Ein Lauf je Session-/Tick-Start:
  1. Verwaiste Git-Lock-Artefakte erkennen (index.lock, HEAD.lock,
     objects/maintenance.lock, objects/**/tmp_obj_*, refs/**/*.lock) und
     entfernen — aber NUR, wenn kein Git-Prozess läuft. Schlägt das
     Löschen fehl (Mount ohne unlink-Recht, R7), wird das Artefakt nach
     .git/verwaiste-locks/ weggeräumt (pm/T-0023) — Git ist damit entsperrt.
     Erst wenn auch das scheitert, folgt die Handlungsanweisung an den Menschen.
  2. Arbeitskopie-Status je Repo (dirty-Dateien, ahead/behind origin).
  3. Board-Validierung (board.py --check im Projekt-Repo).
  4. Unit-Tests (platform/tests) — für Ticks per --skip-tests abwählbar.

Exit 0 = startklar; Exit 1 = mindestens ein Befund.
Erwartungswert (p0/T-0024): 0 Analyse-Blöcke durch Mount-Artefakte je Sprint.
"""
import argparse
import glob
import os
import platform as _platform
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import board  # noqa: E402  — gemeinsame Projekt-Discovery (SWR-070, p9/T-0007)
import konsole  # noqa: E402  — Kodierung an beiden Enden eines Laufs (platform/T-0009)
import js_tests  # noqa: E402  — JS-Teststrecke (SWR-128, ADR-008)
import sprint_register  # noqa: E402  — Sprintzaehler mit Ende (SWR-136, platform/T-0013)

REPOS = ["process", "platform", "p0"]


def repos_im_root(root):
    """REPOS + weitere Git-Repos im Root, z.B. Produkt-Repos (T-0050).

    Bewusst ohne Lock-Altersgrenze: verwaiste Locks entstehen hier session-bedingt
    frisch — der Git-Prozess-Check genügt als Schutz (Retro Sprint 4)."""
    namen = list(REPOS)
    try:
        for d in sorted(os.listdir(root)):
            if d not in namen and os.path.isdir(os.path.join(root, d, ".git")):
                namen.append(d)
    except OSError:
        pass
    return namen


def git_prozess_aktiv():
    """True, wenn auf diesem Gerät gerade ein Git-Prozess läuft (plattformübergreifend).

    `errors="replace"` ist kein Schönheitsfehler-Ausgleich, sondern der Fix zu pm/T-0024:
    `tasklist` antwortet in der OEM-Konsolen-Codepage (850/437), Python decodierte mit
    `text=True` per Default in cp1252. Ein einziges Byte 0x81 (in CP850 das 'ü' aus
    „ausgeführt") ließ den Reader-Thread von subprocess mit UnicodeDecodeError sterben.
    Der Fehler landete unten im `except` und kam als „Git-Prozess aktiv" heraus — die
    Lock-Räumung unterblieb, obwohl gar kein Git lief. Der Prozessname selbst ist ASCII,
    für die Entscheidung geht durch das Ersetzen also nichts verloren.
    """
    try:
        if _platform.system() == "Windows":
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq git.exe"],
                                 capture_output=True, text=True, encoding="utf-8", timeout=10,
                                 errors="replace")
            return "git.exe" in out.stdout
        out = subprocess.run(["pgrep", "-x", "git"], capture_output=True, text=True,
                             encoding="utf-8", timeout=10, errors="replace")
        return out.returncode == 0
    except Exception as fehler:
        # Im Zweifel nichts löschen — aber nicht schweigend. Ein stiller Fallback auf
        # „aktiv" sieht im Protokoll aus wie eine korrekte Beobachtung und kostete drei
        # Auto-Push-Läufe, bis jemand nachsah (pm/T-0024).
        print(f"    [hinweis] Prozess-Abfrage nicht auswertbar "
              f'({type(fehler).__name__}: {fehler}) — vorsichtshalber als „Git läuft“ '
              f"gewertet, es wird nichts entfernt.")
        return True


def finde_lock_artefakte(repo):
    """Bekannte Git-Lock-/Temp-Artefakte im Repo finden (Liste von Pfaden)."""
    g = os.path.join(repo, ".git")
    muster = [
        os.path.join(g, "*.lock"),
        os.path.join(g, "objects", "maintenance.lock"),
        os.path.join(g, "objects", "*", "tmp_obj_*"),
        os.path.join(g, "refs", "**", "*.lock"),
    ]
    funde = []
    for m in muster:
        funde.extend(glob.glob(m, recursive=True))
    return sorted(set(funde))


PARKPLATZ = "verwaiste-locks"


def _parke(pfad, repo_git, stempel):
    """Artefakt nach .git/verwaiste-locks/ wegbenennen. Rückgabe: Zielpfad."""
    ziel_dir = os.path.join(repo_git, PARKPLATZ)
    os.makedirs(ziel_dir, exist_ok=True)
    # Name eindeutig halten: Unterordner-Anteil mit einfließen lassen (refs/heads/main.lock)
    rel = os.path.relpath(pfad, repo_git).replace(os.sep, "_")
    ziel = os.path.join(ziel_dir, f"{rel}.{stempel}")
    n = 0
    while os.path.exists(ziel):
        n += 1
        ziel = os.path.join(ziel_dir, f"{rel}.{stempel}-{n}")
    os.rename(pfad, ziel)
    return ziel


def entferne_artefakte(pfade):
    """Artefakte beseitigen. Rückgabe: (entfernt, geparkt, fehlgeschlagen) als Pfadlisten.

    Zweistufig (Lehre 2026-08-16, pm/T-0023): Erst löschen. Wo der Mount kein
    unlink erlaubt — Cowork-Session auf dem Windows-Ordner, Störung R7 — wird das
    Artefakt stattdessen nach .git/verwaiste-locks/ WEGBENANNT. Für Git ist der
    Lock damit ebenso weg (es prüft ausschließlich den exakten Namen), und die
    Session kann committen, statt ihre gesamte Arbeit unverbucht zu verlieren.
    Umbenennen ist auf diesen Mounts erlaubt, Löschen nicht.
    """
    entfernt, geparkt, fehlgeschlagen = [], [], []
    stempel = time.strftime("%Y%m%dT%H%M%S")
    for p in pfade:
        try:
            os.remove(p)
            entfernt.append(p)
            continue
        except OSError:
            pass
        # .git-Verzeichnis aus dem Fundpfad ableiten (Artefakte liegen immer darunter)
        teile = os.path.abspath(p).split(os.sep)
        try:
            repo_git = os.sep.join(teile[:len(teile) - 1 - teile[::-1].index(".git")] + [".git"])
            _parke(p, repo_git, stempel)
            geparkt.append(p)
        except (OSError, ValueError):
            fehlgeschlagen.append(p)
    return entfernt, geparkt, fehlgeschlagen


def repo_status(repo):
    """(dirty_zeilen, tracking_zeile) aus `git status --porcelain -b`.

    `-uall` (SWR-110): ohne diese Option fasst git einen nicht getrackten Ordner zu
    EINER Zeile `?? tickets/` zusammen. Ein neu angelegtes Ticket in einem neuen
    Ordner wäre damit unsichtbar — genau der Fall, in dem eine Datei nur in der
    Arbeitskopie existiert. Ein Test hat das gefunden (platform/T-0010)."""
    out = subprocess.run(["git", "-C", repo, "status", "--porcelain", "-uall", "-b"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    zeilen = out.stdout.splitlines()
    tracking = zeilen[0] if zeilen else ""
    return [z for z in zeilen[1:] if z.strip()], tracking


# --- SWR-110: Gemessenes gegen Geliefertes -------------------------------------
# trace_matrix und board lesen die ARBEITSKOPIE, `abschluss.cmd [4/5]` pusht HEAD.
# Wo beide in einer Datei auseinandergehen, die eine Verifikation liest, beschreibt
# das grüne Ergebnis einen Zustand, den kein Repository trägt (platform/T-0010:
# Sprint 6 meldete "109 SWRs / 0 Lücken", während SWR-109 nur auf der Platte stand).

def _pfad_aus_statuszeile(zeile):
    """Dateipfad aus einer `git status --porcelain`-Zeile (XY<space>pfad).

    Rename/Copy melden `alt -> neu`; gemeint ist das Ziel. Anführungszeichen setzt
    git bei Sonderzeichen im Namen."""
    pfad = zeile[3:].strip() if len(zeile) > 3 else ""
    if " -> " in pfad:
        pfad = pfad.split(" -> ", 1)[1]
    return pfad.strip('"')


def ist_verifikationsquelle(pfad):
    """Liest eine Verifikation diese Datei?

    Drei Sorten, jede mit einem benennbaren Leser:
      * Anforderungsdokument -> trace_matrix.py (SWR-Bestand und Status)
      * Ticketdatei          -> board.py --check (Validierung, BOARD.md)
      * BOARD.md             -> der CI-Schritt "BOARD.md aktuell?" jedes Projekt-Repos
    BOARD.md steht bewusst mit in der Liste: sie ist der Grund, aus dem es die
    Stand-Zeilen-Ausnahme überhaupt gibt (platform/T-0010)."""
    p = pfad.replace("\\", "/")
    teile = p.split("/")
    if teile[-1] == "BOARD.md":
        return True
    if teile[-1] == "software-requirements.md":
        return "requirements" in teile[:-1] or len(teile) == 1
    return len(teile) >= 2 and teile[-2] == "tickets" and p.endswith(".md")


def nur_stand_zeile(repo, pfad):
    """True, wenn die Änderung an dieser Datei AUSSCHLIESSLICH die `Stand:`-Zeile ist.

    Am tatsächlichen Diff entschieden und nicht am Dateinamen (DoD 3/4 von
    platform/T-0010): `board.py` erzeugt die Stand-Zeile bei jedem Lauf neu, also
    sind fünf Repos jeden Tag unsauber. Eine Ausnahme nach Dateiname würde eine
    BOARD.md mit echter Inhaltsänderung mit durchlassen."""
    out = subprocess.run(["git", "-C", repo, "diff", "--unified=0", "--", pfad],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0 or not out.stdout.strip():
        return False  # nicht getrackt oder nicht lesbar -> keine Ausnahme
    geaendert = [z for z in out.stdout.splitlines()
                 if (z.startswith("+") or z.startswith("-"))
                 and not z.startswith(("+++", "---"))]
    if not geaendert:
        return False
    return all(z[1:].lstrip().startswith("Stand:") for z in geaendert)


_SPRINTSICHT_CACHE = {}


def sprintsicht(root, frisch=False):
    """SWR-122 (platform/T-0011): die Sprintsicht **einmal** laden, oder `None`.

    Drei Preflight-Zeilen (`status_drift`, `plan_drift`, `sprint_vergangen`) beantworten
    drei verschiedene Fragen an **denselben** Bestand. Sie dreimal zu berechnen wäre
    nicht nur teuer, sondern die Bauart aus B033: drei Aufrufe, die zu verschiedenen
    Zeitpunkten laufen, können verschiedene Antworten geben, und niemand würde es merken.
    Deshalb genau ein Aufruf je Preflight-Lauf.

    `None` heißt „konnte nicht prüfen" und ausdrücklich **nicht** „nichts gefunden".
    """
    if not frisch and root in _SPRINTSICHT_CACHE:
        return _SPRINTSICHT_CACHE[root]
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from backend import sprint as _sprint
        sicht = _sprint.plan(root)
    except Exception:
        sicht = None
    _SPRINTSICHT_CACHE[root] = sicht
    return sicht


def statusdrift(root):
    """SWR-115 (pm/T-0049): Planzeilen, deren Statusspalte dem Ticket widerspricht.

    Rückgabe `None`, wenn die Sprintsicht nicht ladbar ist — ausdrücklich **nicht** eine
    leere Liste. „Konnte nicht prüfen" und „nichts gefunden" sind zwei Aussagen, und die
    zweite an der Stelle der ersten ist genau die Sorte stiller Erfolgsmeldung, die dieses
    Ticket ausgelöst hat.
    """
    sicht = sprintsicht(root)
    return None if sicht is None else sicht.get("status_drift", [])


def plandrift(root):
    """SWR-122 (platform/T-0011): Planzeilen, die eine ANDERE Sprintnummer nennen als ihr Ticket.

    Die Kennzahl gibt es seit SWR-109 und sie stand bis heute in keiner Meldung: sie
    wurde von `sprint.plan()` berechnet, in den Payload gelegt und von niemandem gelesen —
    einen Schlüssel neben `status_drift`, das der Preflight liest.

    **Warum sie hierher gehört, steht in SWR-115.** Deren eigene Begründung („sichtbar
    *vor* dem Push und vor dem Bericht an den Auftraggeber, statt einen Sprint später")
    gilt für diesen Nachbarn wörtlich. Am Bestand belegt: der Abschlussbericht von
    Sprint 9 meldete an drei Stellen „Plan-Drift 0", während der Lauf selbst drei Drifts
    hinterließ — die Null war richtig, als sie gemessen wurde, und falsch, als sie
    berichtet wurde. **Eine Messung vor der Änderung, die sie abdecken soll, misst den
    Ausgangszustand.**

    `None` heißt „konnte nicht prüfen" und nicht „nichts gefunden".
    """
    sicht = sprintsicht(root)
    return None if sicht is None else sicht.get("plan_drift", [])


def sprintvergangen(root):
    """SWR-122 (platform/T-0011): offene Tickets, deren geplanter Sprint VORBEI ist.

    Dieselbe Lage wie bei `plandrift`: die Prüfung existiert seit SWR-112 und wurde nie
    gemeldet. `pm/T-0039` belegt den Preis — viermal in Folge wurde `geplant_sprint` um
    genau eins erhöht (6→7→8→9), ohne dass je ein neuer Grund im Ticket stand. SWR-112
    ist für genau diesen Fall gebaut worden und hätte ihn in Sprint 7, 8 und 9 gemeldet;
    gelesen wurde sie in keinem davon.

    `None` heißt „konnte nicht prüfen" und nicht „nichts gefunden".
    """
    sicht = sprintsicht(root)
    return None if sicht is None else sicht.get("sprint_vergangen", [])


def wartet_auf_mensch(root):
    """SWR-120 (pm/T-0051): Weiterleitung auf `aggregation.wartet_auf_mensch`.

    Wie bei `unterminierte_tickets` (SWR-117) ist die Weiterleitung keine zweite
    Quelle, sondern der Beleg, dass es nur eine gibt: Kopfblock und Preflight-Zeile
    beantworten dieselbe Frage und dürfen nicht verschieden zählen (B033).

    `None` heißt „konnte nicht prüfen" und nicht „nichts gefunden".
    """
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from backend import aggregation as _aggregation
        return _aggregation.wartet_auf_mensch(root)
    except Exception:
        return None


def dr_entschieden_nicht_verbucht(root):
    """SWR-131 (platform/T-0014): Weiterleitung auf `aggregation.dr_entschieden_nicht_verbucht`.

    Dieselbe Bauart wie `wartet_auf_mensch` und `unterminierte_tickets`: die
    Weiterleitung ist keine zweite Quelle, sondern der Beleg, dass es nur eine gibt.

    `None` heißt „konnte nicht prüfen" und nicht „nichts gefunden".
    """
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from backend import aggregation as _aggregation
        return _aggregation.dr_entschieden_nicht_verbucht(root)
    except Exception:
        return None


def uebergangshistorie(root):
    """SWR-118 (pm/T-0048): `(neue, altbestand, register)` oder `None`.

    `None` heißt „konnte nicht prüfen" und ausdrücklich **nicht** „nichts gefunden" —
    dieselbe Unterscheidung, die `statusdrift` oben trifft. Eine stille Erfolgsmeldung
    an der Stelle eines Ausfalls ist genau die Sorte Fehler, die `pm/T-0049`
    ausgelöst hat.
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import uebergang_historie as _uh
        return _uh.pruefe_alle(root)
    except Exception:
        return None


def kalenderfristen(root):
    """SWR-125 (platform/T-0012): Teamaufgaben mit Kalenderdatum — Weiterleitung.

    Dieselbe Bauart wie `unterminierte_tickets` eine Funktion tiefer und aus demselben
    Grund (SWR-117): der Rumpf steht in `backend/aggregation.py`, weil der Cockpit-
    Kopfblock ihn ebenfalls liest und zwei Quellen für eine Frage B033 wären.

    `None` heißt „konnte nicht prüfen" und ausdrücklich nicht „nichts gefunden" —
    dieselbe Unterscheidung wie bei `statusdrift`. Eine stille Erfolgsmeldung an der
    Stelle eines Ausfalls ist genau der Fehler, der `pm/T-0049` ausgelöst hat.
    """
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from backend import aggregation as _aggregation
        return _aggregation.kalenderfristen(root)
    except Exception:
        return None


def unterminierte_tickets(root):
    """SWR-114 (pm/T-0036 Teil b): offene Tickets ohne **Sprintnummer** — org-weit, mit Refs.

    Der Befund B049: der „ohne Frist"-Zähler aus SWR-091 wird **pro Kachel** gelesen und
    nie als Summe. Drei Sessions in Folge erklärten ihn für abgearbeitet, während drei
    Tickets in einer anderen Kachel offen blieben — „Kachel X erledigt" ist keine gültige
    Abschlussmeldung, wenn die Frage der Organisation gilt.

    Gemeldet werden **Namen und nicht nur eine Zahl** (B038: ein Gate, das „82" sagt,
    nennt nicht, welche fünf fehlen). Die Abgrenzung ist dieselbe wie in
    `aggregation` (SWR-091), damit nicht zwei Stellen verschieden zählen (B033):
    Takt-Tickets tragen ihr Zeitkonzept im Feld `takt`, und ein `decision-request` wird
    über `frist` + `default` gesteuert.

    **SWR-117 (pm/T-0047): der Rumpf ist nach `backend/aggregation.py` gewandert.**
    Seit Sprint 9 zeigt der Cockpit-Kopfblock dieselbe Tatsache ein zweites Mal an —
    und zwei Stellen, die eine Frage aus zwei Quellen beantworten, sind B033. Diese
    Funktion bleibt als **Weiterleitung** bestehen: sie ist keine zweite Quelle,
    sondern der Beleg, dass es nur eine gibt, und sie hält die SWR-114-Tests auf dem
    Pfad, der tatsächlich ausgeliefert wird. Die Richtung des Umzugs ist erzwungen —
    `backend` importiert bereits `scripts.board`, der umgekehrte Weg schlösse einen
    Zyklus.

    **⚠ SWR-125 (platform/T-0012, Brief pm/N-0041): die Frage lautet ab Sprint 11
    „hat einen Sprint?" statt „hat ein Datum?".** Der Name der Funktion bleibt, weil
    „unterminiert" die Frage ist und `frist` nur eine ihrer Antworten war. Begründung
    im Rumpf (`aggregation.unterminierte_tickets`).
    """
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from backend import aggregation as _aggregation
    return _aggregation.unterminierte_tickets(root)


def arbeitskopie_befunde(repo, dirty):
    """(befund_pfade, gemeldete_pfade) für einen Repo-Status. SWR-110."""
    befunde, alle = [], []
    for zeile in dirty:
        pfad = _pfad_aus_statuszeile(zeile)
        if not pfad:
            continue
        alle.append(pfad)
        if not ist_verifikationsquelle(pfad):
            continue
        if os.path.basename(pfad) == "BOARD.md" and nur_stand_zeile(repo, pfad):
            continue
        befunde.append(pfad)
    return befunde, alle


def board_check(projekt_repo):
    """board.py --check im Projekt-Repo. Rückgabe: (ok, ausgabe)."""
    if not os.path.isdir(projekt_repo):
        return False, f"Projekt-Repo fehlt: {projekt_repo}"
    skript = os.path.join(os.path.dirname(os.path.abspath(__file__)), "board.py")
    out = subprocess.run([sys.executable, skript, "--check"],
                         capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                         env=konsole.kind_umgebung(), cwd=projekt_repo)
    return out.returncode == 0, (out.stdout + out.stderr).strip()


def unit_tests(platform_repo):
    """Unit-Tests wie in CI (python -m unittest discover tests). (ok, letzte Zeilen)."""
    out = subprocess.run([sys.executable, "-m", "unittest", "discover", "tests"],
                         capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                         env=konsole.kind_umgebung(), cwd=platform_repo)
    tail = "\n".join((out.stdout + out.stderr).strip().splitlines()[-3:])
    return out.returncode == 0, tail


def raeume_locks(root, keep_locks=False, still=False):
    """Lock-Artefakte in allen Repos beseitigen. Rückgabe: Anzahl echter Befunde.

    Wird ZWEIMAL je Lauf gebraucht (pm/T-0023, zweiter Befund): einmal am Anfang,
    damit die Session überhaupt arbeiten kann — und einmal am Ende, weil Git bei
    JEDEM Aufruf (auch `git status`) einen index.lock anlegt und ihn auf einem
    Mount ohne unlink-Recht nicht mehr wegbekommt. Ohne den Schlusslauf hinterlässt
    Preflight genau die Sperre, die es gerade aufgehoben hat.
    """
    befunde = 0
    for name in repos_im_root(root):
        repo = os.path.join(root, name)
        if not os.path.isdir(os.path.join(repo, ".git")):
            continue
        locks = finde_lock_artefakte(repo)
        if not locks:
            continue
        if keep_locks or git_prozess_aktiv():
            print(f"[{name}] {len(locks)} Lock-Artefakt(e) gefunden — NICHT entfernt "
                  f"({'--keep-locks' if keep_locks else 'Git-Prozess aktiv'}):")
            for p in locks:
                print(f"    {p}")
            befunde += 1
            continue
        entfernt, geparkt, kaputt = entferne_artefakte(locks)
        if not still:
            for p in entfernt:
                print(f"[{name}] Lock-Artefakt entfernt: {os.path.relpath(p, repo)}")
            if geparkt:
                # Kein Befund: der Lock ist für Git weg, die Session kann committen.
                # Der Hinweis bleibt, weil die Ursache (Mount ohne unlink-Recht) fortbesteht.
                print(f"[{name}] {len(geparkt)} Lock-Artefakt(e) nicht löschbar (R7) — "
                      f"weggeräumt nach .git/{PARKPLATZ}/:")
                for p in geparkt:
                    print(f"    {os.path.relpath(p, repo)}")
                print("    -> Git ist entsperrt. Ursache bleibt: Mount ohne unlink-Recht; "
                      "Parkplatz gelegentlich auf dem Host leeren.")
        if kaputt:
            befunde += 1
            print(f"[{name}] WEGRÄUMEN FEHLGESCHLAGEN (weder löschen noch umbenennen):")
            for p in kaputt:
                print(f"    {p}")
            print("    -> Auf dem Host löschen bzw. Lösch-Berechtigung der Session "
                  "aktivieren, sonst blockieren Commits.")
    return befunde


def preflight(root, skip_tests=False, keep_locks=False, nur_locks=False):
    """Alle Checks ausführen. Rückgabe: Anzahl Befunde (0 = startklar)."""
    befunde = raeume_locks(root, keep_locks)
    if nur_locks:
        print(f"PREFLIGHT: {'STARTKLAR' if befunde == 0 else str(befunde) + ' Befund(e)'} "
              "(nur Lock-Räumung)")
        return befunde
    for name in repos_im_root(root):
        repo = os.path.join(root, name)
        if not os.path.isdir(os.path.join(repo, ".git")):
            print(f"[{name}] FEHLT: kein Git-Repo unter {repo}")
            befunde += 1
            continue
        dirty, tracking = repo_status(repo)
        if dirty:
            # SWR-110: Dateien NENNEN statt zählen. Sechs Zeilen "1 Datei(en)" sahen in
            # Sprint 6 gleich aus — fünfmal eine regenerierte Stand-Zeile, einmal eine
            # ganze Anforderung, die deshalb ungesehen ungepusht blieb (platform/T-0010).
            unverbucht, alle = arbeitskopie_befunde(repo, dirty)
            print(f"[{name}] Arbeitskopie nicht sauber ({len(dirty)} Datei(en)) — {tracking}")
            for pfad in alle:
                marke = "  UNVERBUCHT" if pfad in unverbucht else "  "
                print(f"  {marke} {pfad}")
            if unverbucht:
                print(f"[{name}] BEFUND: {len(unverbucht)} Datei(en), die eine Verifikation "
                      f"liest, sind nicht committet — gemessen wird die Arbeitskopie, "
                      f"gepusht wird HEAD. Committen, sonst gilt das Ergebnis für "
                      f"keinen Repo-Stand.")
                befunde += 1
        else:
            print(f"[{name}] sauber — {tracking}")
    # SWR-139 (platform/T-0017), DoD 4: unverbuchte STATUS-Stände als eigener Befund.
    # SWR-110 oben meldet jede geänderte Datei; was fehlte, ist die Zuspitzung auf
    # `status`. Der Unterschied ist keine Feinheit: ein ergänzter Tickettext ist kein
    # verlorener Zustand, ein nicht gebuchter Statuswechsel ist einer — der nächste
    # Wechsel überschreibt ihn, und in der Historie fehlt eine Stufe (gemessen an
    # `pm/T-0052`, Sprint 15). Nach SWR-122 legt die Prüfung hier ihren Leser fest.
    for _name, _pfad in (board.projekt_pfade(root) or []):
        try:
            _offen = board.unverbuchte_status(_pfad)
        except Exception as e:  # eine scheiternde Prüfung meldet sich, statt zu schweigen
            print(f"[{_name}] unverbuchte Statuswechsel: NICHT PRÜFBAR — {e}")
            continue
        if not _offen:
            continue
        for _zeile in _offen:
            print(f"  UNVERBUCHTER STATUS  {_zeile}")
        print(f"[{_name}] BEFUND: {len(_offen)} Statuswechsel geschrieben und nicht "
              f"gebucht. Ein Zustandswechsel ist EIN Vorgang (SWR-139) — buchen, sonst "
              f"überschreibt ihn der nächste Wechsel lautlos.")
        befunde += 1
    # SWR-029: board-check über ALLE Projekte (Discovery-Konvention, ADR-004);
    # SWR-070/p9-T-0007: inkl. Projektordner im Sammel-Repo projects/ (pm/D003).
    projekte = board.projekt_pfade(root) or [("p0", os.path.join(root, "p0"))]
    for name, pfad in projekte:
        ok, meldung = board_check(pfad)
        print(f"[{name}] board-check: {'OK' if ok else 'FEHLER — ' + meldung}")
        if not ok:
            befunde += 1
    # SWR-114 (pm/T-0036 Teil b): org-weite Summe der Tickets ohne Frist, MIT Namen.
    # Die Stelle, an der eine Session ohnehin hinsieht, bevor sie etwas anderes tut —
    # und die einzige, die die Frage für die ganze Organisation stellt statt je Kachel.
    #
    # SWR-125 (platform/T-0012, Brief pm/N-0041): die Frage lautet ab Sprint 11
    # „hat einen SPRINT?" statt „hat ein DATUM?". Bis dahin hat genau diese Zeile
    # erzwungen, was der Auftraggeber zweimal gerügt hat — wer ein Ticket ohne
    # Kalenderdatum anlegte, machte den Startcheck rot.
    # SWR-136 (platform/T-0013), DoD 4: der Zustand des Sprintregisters wird GEMELDET.
    # Nach SWR-122 legt eine neue Prüfung im selben Zug fest, wer ihr Ergebnis liest —
    # sonst entsteht die vierte Gestalt derselben Familie: eine Prüfung ohne Leser.
    #
    # Die Zeile erscheint IMMER, auch im guten Fall: der Grund steht eine Etage tiefer
    # bei `unterminierte_tickets` und gilt hier wörtlich. ⚠ Der **laufende** Sprint zählt
    # ausdrücklich NICHT als Befund — während eines Laufs trägt seine eigene Zeile
    # naturgemäß kein `ende`, und eine Dauerwarnung liest nach zwei Sprints niemand mehr.
    try:
        nr_jetzt = sprint_register.aktuell(root)
        laeuft = sprint_register.laufender(root)
        luecken = sprint_register.nicht_beendete(root)
    except Exception:
        nr_jetzt, laeuft, luecken = None, None, None
    if nr_jetzt is None:
        print("[org] Sprintregister: nicht prüfbar (Register nicht ladbar).")
    else:
        zustand = "läuft" if laeuft else "beendet"
        print(f"[org] Sprintregister: Sprint {nr_jetzt} ({zustand}), "
              f"Stichtag Ende-Pflicht ab Sprint "
              f"{sprint_register.STICHTAG_ENDE_SPRINT}.")
        if luecken:
            print(f"[org] BEFUND: {len(luecken)} abgeschlossene(r) Sprint(s) ohne "
                  f"'ende' im Register: "
                  + ", ".join(f"{e['nr']} ({e.get('kennung', '?')})" for e in luecken))
            befunde += 1
    ohne_sprint = unterminierte_tickets(root)
    if ohne_sprint:
        print(f"[org] {len(ohne_sprint)} Ticket(s) ohne Sprint: {', '.join(ohne_sprint)}")
        befunde += 1
    else:
        print("[org] 0 Tickets ohne Sprint.")
    # SWR-125, zweite Hälfte: die Gegenrichtung. „Nicht mehr gefordert" genügt nicht —
    # SWR-106 hatte Kalenderdaten schon fünf Sprints früher abgeschafft, und weil ihre
    # Rückkehr niemand meldete, waren kurz darauf wieder 14 Stück da. Zählt deshalb
    # als Befund: eine Zeile, die nichts blockiert, hat den Bericht von Sprint 9 auch
    # nicht verhindert.
    kal = kalenderfristen(root)
    if kal is None:
        print("[org] Kalenderfristen an Teamaufgaben: nicht prüfbar "
              "(Aggregation nicht ladbar).")
    elif kal:
        print(f"[org] BEFUND: {len(kal)} Teamaufgabe(n) tragen ein Kalenderdatum statt "
              f"einer Sprintnummer: {', '.join(kal)}")
        befunde += 1
    else:
        print("[org] Kalenderfristen an Teamaufgaben: 0.")
    # SWR-120 (pm/T-0051): dieselbe Frage für den Menschen — wie viele offene Tickets
    # liegen bei ihm, und WELCHE. Aus derselben Quelle wie der Cockpit-Kopfblock
    # (`aggregation.wartet_auf_mensch`), damit Preflight und HMI nicht verschieden
    # zählen (B033), und mit Namen statt nur einer Zahl (B038).
    #
    # Die Zeile erscheint auch bei 0 — dieselbe Begründung wie eine Zeile höher: ein
    # stiller Check ist von einem nicht gelaufenen nicht zu unterscheiden.
    wartend = wartet_auf_mensch(root)
    if wartend is None:
        print("[org] Wartet auf den Menschen: nicht prüfbar (Aggregation nicht ladbar).")
    elif wartend:
        print(f"[org] {len(wartend)} Ticket(s) warten auf den Menschen: "
              f"{', '.join(wartend)}")
    else:
        print("[org] 0 Tickets warten auf den Menschen.")
    # SWR-131 (platform/T-0014): die zweite Hälfte der Zeile darüber — und ohne sie wäre
    # die erste eine Verschlechterung. Ein entschiedener DR verschwindet ab SWR-131 aus
    # „wartet auf den Menschen" (er wartet auf niemanden); stünde er dann weiter auf
    # `open`, hätte ihn niemand mehr im Blick. Genau der Zustand war am 2026-08-17 um
    # 11:48 der Fall und blieb 16 Minuten lang unbemerkt — lang genug für drei Berichte,
    # die dem Auftraggeber eine Frage vorlegten, die er beantwortet hatte.
    #
    # Zählt als BEFUND, nicht als Zeile: die Verbuchung ist Folgearbeit (entsperren,
    # planen, berichten), und ein Lauf, der sie überspringt, darf nicht startklar melden.
    unverbucht = dr_entschieden_nicht_verbucht(root)
    if unverbucht is None:
        print("[org] Entschiedene, unverbuchte DRs: nicht prüfbar (Aggregation nicht ladbar).")
    elif unverbucht:
        print(f"[org] BEFUND: {len(unverbucht)} entschiedene(r) DR(s) sind nicht verbucht — "
              f"die Antwort liegt vor, der Arbeitsstand kennt sie nicht: "
              f"{', '.join(unverbucht)}")
        befunde += 1
    else:
        print("[org] Entschiedene, unverbuchte DRs: 0.")
    # SWR-115 (pm/T-0049): die STATUSSPALTE des Sprintplans gegen den Ticketstatus.
    # Hier und nicht später, weil Sprint 7 `platform/T-0010` vierfach als erledigt gemeldet
    # hat — an den Auftraggeber inbegriffen — und `sprint_vergangen` (SWR-112) den Fall
    # frühestens im FOLGESPRINT sehen kann. Eine Prüfung, die den Fehler erst findet,
    # nachdem er berichtet wurde, verhindert die Falschmeldung nicht.
    drift = statusdrift(root)
    if drift is None:
        print("[org] Statusdrift Plan/Ticket: nicht prüfbar (Sprintsicht nicht ladbar).")
    elif drift:
        print(f"[org] BEFUND: {len(drift)} Planzeile(n) widersprechen ihrem Ticket — "
              f"der Plan sagt etwas anderes als das Ticketfeld:")
        for d in drift:
            print(f"    {d['ref']}: {d['meldung']}")
        befunde += 1
    else:
        print("[org] Statusdrift Plan/Ticket: 0.")
    # SWR-122 (platform/T-0011): die beiden Nachbarn von `status_drift`, die bis Sprint 10
    # berechnet und von niemandem gelesen wurden.
    #
    # `plan_drift` (SWR-109) fragt: sagt die FÄLLIGKEITSSPALTE dieselbe Sprintnummer wie
    # das Ticketfeld? `sprint_vergangen` (SWR-112) fragt: liegt der geplante Sprint in der
    # VERGANGENHEIT? Das sind zwei Fragen an denselben Bestand und keine zwei Meinungen
    # über eine — ein Ticket kann in beiden stehen (heute: `pm/T-0028`, `pm/T-0039`) und
    # das ist kein Doppelbefund, sondern zwei Fehler an einem Ticket.
    #
    # Beide Zeilen erscheinen auch bei 0 (SWR-114-Begründung) und nennen Referenzen statt
    # nur einer Zahl (B038). Beide zählen als Befund: eine Zeile, die nichts blockiert,
    # hätte den Bericht von Sprint 9 nicht verhindert.
    pdrift = plandrift(root)
    if pdrift is None:
        print("[org] Plan-Drift Sprintnummer: nicht prüfbar (Sprintsicht nicht ladbar).")
    elif pdrift:
        print(f"[org] BEFUND: {len(pdrift)} Planzeile(n) nennen eine andere Sprintnummer "
              f"als ihr Ticket:")
        for d in pdrift:
            print(f"    {d['ref']}: {d['meldung']}")
        befunde += 1
    else:
        print("[org] Plan-Drift Sprintnummer: 0.")
    vergangen = sprintvergangen(root)
    if vergangen is None:
        print("[org] Offen auf vergangenem Sprint: nicht prüfbar (Sprintsicht nicht ladbar).")
    elif vergangen:
        print(f"[org] BEFUND: {len(vergangen)} offene(s) Ticket(s) auf einem bereits "
              f"vergangenen Sprint:")
        for d in vergangen:
            print(f"    {d['ref']}: {d['meldung']}")
        befunde += 1
    else:
        print("[org] Offen auf vergangenem Sprint: 0.")
    # SWR-118 (pm/T-0048): unzulässige Statusübergänge in der COMMITTETEN Historie.
    #
    # Die Übergangsprüfung in `board.py` hält die Arbeitskopie gegen HEAD und ist damit
    # blind für einen Sprung, der schon committet ist — ihr Ergebnis hing an der
    # REIHENFOLGE der Session. Diese Prüfung liest stattdessen die Folge der
    # `status:`-Werte in der Historie: ein Sachverhalt, der sich nicht dadurch ändert,
    # wann man ihn abfragt.
    #
    # Der Altbestand vor dem Stichtag wird GEMELDET und blockiert NICHT — nicht
    # geglättet, aber auch kein Dauerbefund, der das Wegsehen trainiert.
    uebergaenge = uebergangshistorie(root)
    if uebergaenge is None:
        print("[org] Statusübergänge (Historie): nicht prüfbar (Modul nicht ladbar).")
    else:
        neue, altbestand, register = uebergaenge
        print(f"[org] Altbestand unzulässiger Statusübergänge (vor dem Stichtag, "
              f"bewusst nicht geglättet): {len(altbestand)}.")
        for z in register:
            print(f"[org] BEFUND: {z}")
            befunde += 1
        if neue:
            print(f"[org] BEFUND: {len(neue)} unzulässige(r) Statusübergang/-übergänge "
                  f"seit dem Stichtag:")
            for z in neue:
                print(f"    {z}")
            befunde += 1
        else:
            print("[org] Unzulässige Statusübergänge seit dem Stichtag: 0.")
    # SWR-051 (P4): Session-Routine "Briefkasten zuerst" — offene Briefe anzeigen (informativ)
    for name, pfad in projekte:
        verz = os.path.join(pfad, "management", "briefkasten")
        if os.path.isdir(verz):
            offen = sum(1 for d in os.listdir(verz) if d.endswith(".md") and
                        "status: offen" in open(os.path.join(verz, d), encoding="utf-8").read(300))
            if offen:
                print(f"[{name}] BRIEFKASTEN: {offen} offene(r) Brief(e) — zuerst beantworten!")
    if skip_tests:
        print("[platform] Unit-Tests übersprungen (--skip-tests)")
        print("[platform] JS-Tests übersprungen (--skip-tests)")
    else:
        ok, tail = unit_tests(os.path.join(root, "platform"))
        print(f"[platform] Unit-Tests: {'OK' if ok else 'ROT'} — {tail.splitlines()[-1] if tail else ''}")
        if not ok:
            befunde += 1
        # SWR-128 (ADR-008): die JS-Teststrecke. Sie wird IMMER gemeldet — auch wenn sie
        # nicht lief. Ein still übersprungener Test ist von einer Prüfung, die es gar nicht
        # gibt, nicht zu unterscheiden (SWR-114/SWR-122) — und genau so ist der Zustand
        # "741 Python-Tests, null JS-Tests" unbemerkt geblieben, obwohl SWR-098/099/100
        # Nachweise an JavaScript verlangen.
        # Rot zählt als Befund. "Übersprungen" zählt NICHT: solange p12/T-0007 nicht
        # entschieden ist, ist Node keine Voraussetzung des Projekts, und ein fehlendes
        # Werkzeug darf den Lauf des Menschen nicht blockieren. Gemeldet wird es trotzdem,
        # und das genügt — eine Kennzahl steuert, sobald sie berichtet wird (SWR-125).
        js = js_tests.lauf(root)
        print(f"[platform] {js['meldung']}")
        if js["zustand"] == "rot":
            befunde += 1
    # Schlusslauf (pm/T-0023): Die eigenen git-Aufrufe oben haben auf einem Mount ohne
    # unlink-Recht neue index.lock hinterlassen. Ohne dieses Aufräumen meldet Preflight
    # STARTKLAR und der nächste Commit der Session scheitert trotzdem.
    befunde += raeume_locks(root, keep_locks, still=True)
    print(f"PREFLIGHT: {'STARTKLAR' if befunde == 0 else str(befunde) + ' Befund(e)'}")
    return befunde


def main():
    p = argparse.ArgumentParser(description="Session-/Tick-Preflight (T-0024)")
    p.add_argument("--repos", default=".", help="Wurzel mit process/, platform/, p0/")
    p.add_argument("--skip-tests", action="store_true", help="Unit-Tests auslassen (Tick-Modus)")
    p.add_argument("--keep-locks", action="store_true", help="Locks nur melden, nie löschen")
    p.add_argument("--nur-locks", action="store_true",
                   help="Nur Lock-Artefakte räumen (schnelles Entsperren vor einem git-Schreibvorgang)")
    a = p.parse_args()
    sys.exit(1 if preflight(a.repos, a.skip_tests, a.keep_locks, a.nur_locks) else 0)


if __name__ == "__main__":
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import konsole
    konsole.sichere_ausgabe()  # platform/T-0009: am Melden nicht sterben
    main()
