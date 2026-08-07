#!/usr/bin/env python3
"""DR-Benachrichtigung (SWR-033, P1/T-0013, D004): eine E-Mail je neuem Decision Request.

Nutzung: python dr_benachrichtigung.py --repos <wurzel> [--dry-run]

Scannt offene DRs ALLER Projekte (Discovery, ADR-004); je DR ohne Versand-Marker
wird eine Mail gesendet (Projekt, ID, Titel, Frist, Optionen) und der Marker nur
bei ERFOLG ans Ticket geschrieben — Fehlversuche werden geloggt und beim nächsten
Lauf wiederholt. Nie blockierend (Exit immer 0). Skript-Route, Aufruf in abschluss.cmd.
"""
import argparse
import os
import sys
from datetime import date

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PLATFORM)
sys.path.insert(0, os.path.join(_PLATFORM, "scripts"))
import board  # noqa: E402
from backend import aggregation, mailer  # noqa: E402

MARKER = "**Benachrichtigt:**"
FINAL = ("done", "rejected")


def unbenachrichtigte(root):
    """[(projekt, ticket, pfad)] — offene DRs ohne Versand-Marker."""
    funde = []
    for name in aggregation.projekte(root):
        repo = os.path.join(root, name)
        tickets, _ = board.lade_tickets(repo)
        for t in tickets:
            if t.get("typ") != "decision-request" or t.get("status") in FINAL:
                continue
            if MARKER in t.get("_body", ""):
                continue
            funde.append((name, t, os.path.join(repo, "tickets", f"{t['id']}.md")))
    return funde


def lauf(root, sende=mailer.sende, dry_run=False):
    """Je unbenachrichtigtem DR eine Mail; Marker nur bei Erfolg. [(projekt, id, status)]."""
    ergebnisse = []
    for projekt, t, pfad in unbenachrichtigte(root):
        if dry_run:
            ergebnisse.append((projekt, t["id"], "dry-run"))
            continue
        ok, meldung = sende(
            f"[{projekt}] Neuer Decision Request {t['id']}: {t.get('titel', '')}",
            f"Projekt: {projekt}\nTicket: {t['id']}\nTitel: {t.get('titel', '')}\n"
            f"Optionen: {t.get('optionen', '—')}\nFrist: {t.get('frist', '—')}\n\n"
            f"Beantworten über Mission Control (Inbox) am Team-Node.\n")
        if ok:
            with open(pfad, "a", encoding="utf-8", newline="\n") as f:
                f.write(f"\n{MARKER} {date.today().isoformat()} per E-Mail (SWR-033).\n")
            ergebnisse.append((projekt, t["id"], "gesendet"))
        else:
            ergebnisse.append((projekt, t["id"], meldung))
    return ergebnisse


def main():
    p = argparse.ArgumentParser(description="DR-Benachrichtigung (SWR-033)")
    p.add_argument("--repos", default=".")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    for projekt, tid, status in lauf(os.path.abspath(a.repos), dry_run=a.dry_run):
        print(f"[{projekt}] {tid}: {status}")
    sys.exit(0)  # SWR-033: nie blockierend


if __name__ == "__main__":
    main()
