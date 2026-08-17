#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""digest_zustellung.py (P7, SWR-058): Digests per Mail zustellen — idempotent, nie blockierend.

Findet alle Team-Repos (team.yaml) mit `zustellung_mail: ja` in der Konfiguration
und sendet jeden Digest ohne Zustellvermerk an die registrierten Team-Adressen
(SWR-033-Kanal, mailer.py). Nach erfolgreichem Versand wird ein Zustellvermerk
ans Dateiende geschrieben und committet — wiederholte Läufe senden nie doppelt.
Fehler (kein SMTP, Netz weg) werden gemeldet, brechen aber nichts ab: der
Vermerk bleibt dann aus, der nächste Lauf versucht es erneut.

Aufruf (abschluss.cmd, nach der DR-Benachrichtigung): --repos . [--dry-run]
"""
import argparse
import datetime
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import teams  # noqa: E402
from backend import git_schreiben  # noqa: E402  — SWR-134: der eine Schreibweg nach Git

VERMERK = "**Zugestellt:**"
_COMMIT_IDENT = ["-c", "user.name=ASPICE-Team", "-c", "user.email=team@aspice.local"]


def _team_repos(root):
    for name in sorted(os.listdir(root)):
        if os.path.isdir(os.path.join(root, name, ".git")) and teams.ist_team(root, name):
            yield name


def offene_digests(root, projekt):
    """Digests ohne Zustellvermerk (älteste zuerst — chronologischer Versand)."""
    ergebnis = []
    for d in reversed(teams.digest_liste(root, projekt)):
        pfad = os.path.join(root, projekt, "digest", d["name"])
        with open(pfad, encoding="utf-8") as f:
            if VERMERK not in f.read():
                ergebnis.append(d["name"])
    return ergebnis


def _vermerken(root, projekt, name, heute):
    pfad = os.path.join(root, projekt, "digest", name)
    with open(pfad, "a", encoding="utf-8") as f:
        f.write(f"\n{VERMERK} {heute} per E-Mail (SWR-058).\n")
    repo = os.path.join(root, projekt)
    # SWR-134: über den einen Schreibweg. ⚠ Der Rückgabewert wird hier bewusst **nicht**
    # geprüft — SWR-058 verlangt ausdrücklich, dass die Zustellung nie blockiert. Was
    # dieser Weg beiträgt, ist die Sperren-Räumung: vorher blieb der Zustellvermerk auf
    # diesem Mount an einer verwaisten `index.lock` hängen und der nächste Lauf hätte
    # denselben Digest erneut versandt — genau die Doppelzustellung, die SWR-058 verbietet.
    git_schreiben.verbuche(repo, [os.path.join("digest", name)],
                           f"Digest {name}: Zustellvermerk (SWR-058)", _COMMIT_IDENT)


def lauf(root, sende, dry_run=False, heute=None):
    """Kern, testbar: sende(betreff, text) -> (ok, meldung). Gibt Berichtzeilen zurück."""
    heute = heute or datetime.date.today().isoformat()
    bericht = []
    for projekt in _team_repos(root):
        try:
            cfg = teams.lade_konfiguration(root, projekt)
            if not cfg.get("zustellung_mail"):
                continue
            for name in offene_digests(root, projekt):
                if dry_run:
                    bericht.append(f"[{projekt}] {name}: dry-run")
                    continue
                with open(os.path.join(root, projekt, "digest", name), encoding="utf-8") as f:
                    inhalt = f.read()
                ok, meldung = sende(f"[{projekt}] Digest {name[:10]}", inhalt)
                if ok:
                    _vermerken(root, projekt, name, heute)
                    bericht.append(f"[{projekt}] {name}: zugestellt")
                else:
                    bericht.append(f"[{projekt}] {name}: NICHT zugestellt ({meldung}) — nächster Lauf versucht es erneut")
        except Exception as e:  # noqa: BLE001 — nie blockierend (SWR-058)
            bericht.append(f"[{projekt}] FEHLER: {e} — übersprungen")
    return bericht


def main():
    p = argparse.ArgumentParser(description="Digest-Zustellung per Mail (SWR-058)")
    p.add_argument("--repos", default=".")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    from backend import mailer
    for zeile in lauf(os.path.abspath(a.repos), mailer.sende, dry_run=a.dry_run):
        print(zeile)
    return 0  # nie blockierend


if __name__ == "__main__":
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import konsole
    konsole.sichere_ausgabe()  # platform/T-0009: am Melden nicht sterben
    sys.exit(main())
