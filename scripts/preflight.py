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
                                 capture_output=True, text=True, timeout=10,
                                 errors="replace")
            return "git.exe" in out.stdout
        out = subprocess.run(["pgrep", "-x", "git"], capture_output=True, text=True,
                             timeout=10, errors="replace")
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
    """(dirty_zeilen, tracking_zeile) aus `git status --porcelain -b`."""
    out = subprocess.run(["git", "-C", repo, "status", "--porcelain", "-b"],
                         capture_output=True, text=True)
    zeilen = out.stdout.splitlines()
    tracking = zeilen[0] if zeilen else ""
    return [z for z in zeilen[1:] if z.strip()], tracking


def board_check(projekt_repo):
    """board.py --check im Projekt-Repo. Rückgabe: (ok, ausgabe)."""
    if not os.path.isdir(projekt_repo):
        return False, f"Projekt-Repo fehlt: {projekt_repo}"
    skript = os.path.join(os.path.dirname(os.path.abspath(__file__)), "board.py")
    out = subprocess.run([sys.executable, skript, "--check"],
                         capture_output=True, text=True, cwd=projekt_repo)
    return out.returncode == 0, (out.stdout + out.stderr).strip()


def unit_tests(platform_repo):
    """Unit-Tests wie in CI (python -m unittest discover tests). (ok, letzte Zeilen)."""
    out = subprocess.run([sys.executable, "-m", "unittest", "discover", "tests"],
                         capture_output=True, text=True, cwd=platform_repo)
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
            print(f"[{name}] Arbeitskopie nicht sauber ({len(dirty)} Datei(en)) — {tracking}")
        else:
            print(f"[{name}] sauber — {tracking}")
    # SWR-029: board-check über ALLE Projekte (Discovery-Konvention, ADR-004);
    # SWR-070/p9-T-0007: inkl. Projektordner im Sammel-Repo projects/ (pm/D003).
    projekte = board.projekt_pfade(root) or [("p0", os.path.join(root, "p0"))]
    for name, pfad in projekte:
        ok, meldung = board_check(pfad)
        print(f"[{name}] board-check: {'OK' if ok else 'FEHLER — ' + meldung}")
        if not ok:
            befunde += 1
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
    else:
        ok, tail = unit_tests(os.path.join(root, "platform"))
        print(f"[platform] Unit-Tests: {'OK' if ok else 'ROT'} — {tail.splitlines()[-1] if tail else ''}")
        if not ok:
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
    main()
