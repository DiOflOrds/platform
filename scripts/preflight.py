#!/usr/bin/env python3
"""Session-/Tick-Preflight (T-0024, Retro-CR 1/3 aus Sprint 2).

Ein Lauf je Session-/Tick-Start:
  1. Verwaiste Git-Lock-Artefakte erkennen (index.lock, HEAD.lock,
     objects/maintenance.lock, objects/**/tmp_obj_*, refs/**/*.lock) und
     entfernen — aber NUR, wenn kein Git-Prozess läuft. Schlägt das
     Entfernen fehl (z. B. Mount ohne unlink-Recht, R7), wird eine klare
     Handlungsanweisung ausgegeben statt eines späteren Analyse-Blocks.
  2. Arbeitskopie-Status je Repo (dirty-Dateien, ahead/behind origin).
  3. Board-Validierung (board.py --check im Projekt-Repo).
  4. Unit-Tests (platform/tests) — für Ticks per --skip-tests abwählbar.

Exit 0 = startklar; Exit 1 = mindestens ein Befund.
Erwartungswert (T-0024): 0 Analyse-Blöcke durch Mount-Artefakte je Sprint.
"""
import argparse
import glob
import os
import platform as _platform
import subprocess
import sys

REPOS = ["process", "platform", "p0"]


def git_prozess_aktiv():
    """True, wenn auf diesem Gerät gerade ein Git-Prozess läuft (plattformübergreifend)."""
    try:
        if _platform.system() == "Windows":
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq git.exe"],
                                 capture_output=True, text=True, timeout=10)
            return "git.exe" in out.stdout
        out = subprocess.run(["pgrep", "-x", "git"], capture_output=True, text=True, timeout=10)
        return out.returncode == 0
    except Exception:
        return True  # im Zweifel: nichts löschen


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


def entferne_artefakte(pfade):
    """Artefakte löschen. Rückgabe: (entfernt, fehlgeschlagen) als Pfadlisten."""
    entfernt, fehlgeschlagen = [], []
    for p in pfade:
        try:
            os.remove(p)
            entfernt.append(p)
        except OSError:
            fehlgeschlagen.append(p)
    return entfernt, fehlgeschlagen


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


def preflight(root, skip_tests=False, keep_locks=False):
    """Alle Checks ausführen. Rückgabe: Anzahl Befunde (0 = startklar)."""
    befunde = 0
    for name in REPOS:
        repo = os.path.join(root, name)
        if not os.path.isdir(os.path.join(repo, ".git")):
            print(f"[{name}] FEHLT: kein Git-Repo unter {repo}")
            befunde += 1
            continue
        locks = finde_lock_artefakte(repo)
        if locks:
            if keep_locks or git_prozess_aktiv():
                print(f"[{name}] {len(locks)} Lock-Artefakt(e) gefunden — NICHT entfernt "
                      f"({'--keep-locks' if keep_locks else 'Git-Prozess aktiv'}):")
                for p in locks:
                    print(f"    {p}")
                befunde += 1
            else:
                entfernt, kaputt = entferne_artefakte(locks)
                for p in entfernt:
                    print(f"[{name}] Lock-Artefakt entfernt: {os.path.relpath(p, repo)}")
                if kaputt:
                    befunde += 1
                    print(f"[{name}] LÖSCHEN FEHLGESCHLAGEN (Mount ohne unlink-Recht? R7):")
                    for p in kaputt:
                        print(f"    {p}")
                    print("    -> Auf dem Host löschen bzw. Lösch-Berechtigung der Session "
                          "aktivieren, sonst blockieren Commits.")
        dirty, tracking = repo_status(repo)
        if dirty:
            print(f"[{name}] Arbeitskopie nicht sauber ({len(dirty)} Datei(en)) — {tracking}")
        else:
            print(f"[{name}] sauber — {tracking}")
    ok, meldung = board_check(os.path.join(root, "p0"))
    print(f"[p0] board-check: {'OK' if ok else 'FEHLER — ' + meldung}")
    if not ok:
        befunde += 1
    if skip_tests:
        print("[platform] Unit-Tests übersprungen (--skip-tests)")
    else:
        ok, tail = unit_tests(os.path.join(root, "platform"))
        print(f"[platform] Unit-Tests: {'OK' if ok else 'ROT'} — {tail.splitlines()[-1] if tail else ''}")
        if not ok:
            befunde += 1
    print(f"PREFLIGHT: {'STARTKLAR' if befunde == 0 else str(befunde) + ' Befund(e)'}")
    return befunde


def main():
    p = argparse.ArgumentParser(description="Session-/Tick-Preflight (T-0024)")
    p.add_argument("--repos", default=".", help="Wurzel mit process/, platform/, p0/")
    p.add_argument("--skip-tests", action="store_true", help="Unit-Tests auslassen (Tick-Modus)")
    p.add_argument("--keep-locks", action="store_true", help="Locks nur melden, nie löschen")
    a = p.parse_args()
    sys.exit(1 if preflight(a.repos, a.skip_tests, a.keep_locks) else 0)


if __name__ == "__main__":
    main()
