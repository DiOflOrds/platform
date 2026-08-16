#!/usr/bin/env python3
"""DR-Benachrichtigung (SWR-033/034/035, P1/T-0013, P2/T-0007, D004).

Nutzung: python dr_benachrichtigung.py --repos <wurzel> [--dry-run]

Zwei Durchgänge je Lauf über offene DRs ALLER Projekte (Discovery, ADR-004):
1. Neu-Benachrichtigung (SWR-033): je DR ohne Versand-Marker eine Mail
   (Projekt, ID, Titel, Frist, Optionen), Marker nur bei ERFOLG.
2. Frist-Warnung (SWR-034/035): je unentschiedenem DR mit Frist in <= 2 Tagen
   oder überschritten genau EINE Warnmail (eigener Marker), mit Default-Hinweis.
Fehlversuche werden geloggt und beim nächsten Lauf wiederholt. Nie blockierend
(Exit immer 0). Skript-Route, Aufruf in abschluss.cmd.
"""
import argparse
import os
import sys
from datetime import date, timedelta

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PLATFORM)
sys.path.insert(0, os.path.join(_PLATFORM, "scripts"))
import board  # noqa: E402
from backend import aggregation, mailer  # noqa: E402

MARKER = "**Benachrichtigt:**"
WARN_MARKER = "**Frist-Warnung:**"
ENTSCHIEDEN = "**Entscheidung ("
FINAL = ("done", "rejected")
WARN_SCHWELLE_TAGE = 2  # SWR-034


def _offene_drs(root):
    """[(projekt, ticket, pfad)] — offene DRs aller Projekte."""
    funde = []
    for name in aggregation.projekte(root):
        repo = aggregation.projekt_pfad(root, name)  # SWR-070: auch projects/<p>
        tickets, _ = board.lade_tickets(repo)
        for t in tickets:
            if t.get("typ") != "decision-request" or t.get("status") in FINAL:
                continue
            funde.append((name, t, os.path.join(repo, "tickets", f"{t['id']}.md")))
    return funde


def unbenachrichtigte(root):
    """[(projekt, ticket, pfad)] — offene DRs ohne Versand-Marker (SWR-033)."""
    return [(p, t, pf) for p, t, pf in _offene_drs(root)
            if MARKER not in t.get("_body", "")]


def warnfaellige(root, heute=None):
    """[(projekt, ticket, pfad)] — unentschiedene DRs, Frist <= heute+2 Tage,
    noch ohne Warn-Marker (SWR-034)."""
    heute = heute or date.today()
    funde = []
    for p, t, pf in _offene_drs(root):
        body = t.get("_body", "")
        if WARN_MARKER in body or ENTSCHIEDEN in body:
            continue
        frist = str(t.get("frist", "")).strip()
        try:
            frist_datum = date.fromisoformat(frist)
        except ValueError:
            continue  # ohne parsebare Frist keine Warnung
        if frist_datum <= heute + timedelta(days=WARN_SCHWELLE_TAGE):
            funde.append((p, t, pf))
    return funde


def _warntext(projekt, t):
    """SWR-035: Projekt/Ticket/Titel/Frist + Default-Hinweis falls definiert."""
    text = (f"Projekt: {projekt}\nTicket: {t['id']}\nTitel: {t.get('titel', '')}\n"
            f"Frist: {t.get('frist', '—')} — läuft ab oder ist überschritten!\n")
    default = str(t.get("default", "") or "").strip()
    if default:
        text += (f"\nDefault-Option: {default} — sie greift, wenn bis zum "
                 f"Fristablauf keine Antwort vorliegt.\n")
    text += "\nBeantworten über Mission Control (Inbox) am Team-Node.\n"
    return text


def lauf(root, sende=mailer.sende, dry_run=False, heute=None):
    """Durchgang 1: Neu-Mails (SWR-033); Durchgang 2: Frist-Warnungen (SWR-034/035).
    Marker jeweils nur bei Erfolg. [(projekt, id, status)]."""
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
    for projekt, t, pfad in warnfaellige(root, heute=heute):
        if dry_run:
            ergebnisse.append((projekt, t["id"], "warnung: dry-run"))
            continue
        ok, meldung = sende(
            f"[{projekt}] FRIST-WARNUNG {t['id']}: {t.get('titel', '')}",
            _warntext(projekt, t))
        if ok:
            with open(pfad, "a", encoding="utf-8", newline="\n") as f:
                f.write(f"\n{WARN_MARKER} {date.today().isoformat()} per E-Mail "
                        f"(SWR-034).\n")
            ergebnisse.append((projekt, t["id"], "warnung gesendet"))
        else:
            ergebnisse.append((projekt, t["id"], f"warnung: {meldung}"))
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
