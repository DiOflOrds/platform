#!/usr/bin/env python3
"""Feedback-Routing v1 (T-0055, Masterplan 5.5): Feedback-Ticket → Problem/CR.

Nutzung: python feedback_route.py <projekt-repo> [--feedback T-xxxx] [--dry-run]

Klassifikation v1 (Heuristik): Fehler-Wörter → problem (SUP.9), sonst
change-request (SUP.10). Erzeugt das Folge-Ticket (nächste freie ID) mit
Rückverweis und Feedback-Wortlaut, setzt das Feedback auf in_progress
(Abschluss auf done folgt mit dem Folge-Ticket — Statusregeln Playbook Kap. 5)
und regeneriert BOARD.md. Skript-Route: kein LLM nötig.
"""
import argparse
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import board  # noqa: E402

FEHLER_WOERTER = re.compile(
    r"\b(fehler|bug|falsch|absturz|crash|defekt|kaputt|error|broken)\b", re.I)


def klassifiziere(fb):
    """'problem' bei Fehler-Wortlaut, sonst 'change-request' (v1-Heuristik)."""
    text = f"{fb.get('titel', '')} {fb.get('_body', '')}"
    return "problem" if FEHLER_WOERTER.search(text) else "change-request"


def naechste_id(tickets):
    n = max((int(t["id"][2:]) for t in tickets if t.get("id")), default=0)
    return f"T-{n + 1:04d}"


def route(projekt_repo, nur_id=None, dry_run=False):
    """Offene Feedback-Tickets routen. Rückgabe: Liste (feedback, neu, typ)."""
    tickets, probleme = board.lade_tickets(projekt_repo)
    probleme += board.validiere_alle(tickets, projekt_repo, git_pruefen=False)
    if probleme:
        raise RuntimeError("Board invalide vor Routing: " + "; ".join(probleme))
    heute = date.today().isoformat()
    ergebnisse = []
    for fb in [t for t in tickets if t.get("typ") == "feedback"
               and t.get("status") == "open"
               and (not nur_id or t.get("id") == nur_id)]:
        ziel_typ = klassifiziere(fb)
        rolle, prozess = (("prob", "sup9") if ziel_typ == "problem"
                          else ("chg", "sup10"))
        neu = naechste_id(tickets)
        ergebnisse.append((fb["id"], neu, ziel_typ))
        if dry_run:
            continue
        praefix = "Problem" if ziel_typ == "problem" else "CR"
        with open(os.path.join(projekt_repo, "tickets", f"{neu}.md"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(f"""---
id: {neu}
titel: "{praefix} (aus Feedback {fb['id']}): {fb.get('titel', '')}"
typ: {ziel_typ}
prozess: {prozess}
rolle: {rolle}
sprint: {fb.get('sprint', '')}
status: open
prio: {fb.get('prio', 'mittel')}
blocked_by: []
repo: {fb.get('repo', 'p0')}
erstellt: {heute}
---

Automatisch geroutet aus Feedback {fb['id']} (feedback_route.py v1, T-0055).

## Feedback-Wortlaut

{fb.get('_body', '')}
""")
        # Feedback: open -> in_progress + Routing-Notiz (done folgt mit dem Folge-Ticket)
        pfad = os.path.join(projekt_repo, "tickets", f"{fb['id']}.md")
        text = open(pfad, encoding="utf-8").read().replace("\r\n", "\n")
        text = re.sub(r"(?m)^status:.*$", "status: in_progress", text, count=1)
        text = text.rstrip() + (f"\n\n**Routing ({heute}, feedback_route v1):** "
                                f"als {ziel_typ} → {neu}.\n")
        open(pfad, "w", encoding="utf-8", newline="\n").write(text)
        tickets, _ = board.lade_tickets(projekt_repo)
    if not dry_run and ergebnisse:
        tickets, probleme = board.lade_tickets(projekt_repo)
        probleme += board.validiere_alle(tickets, projekt_repo, git_pruefen=False)
        if probleme:
            raise RuntimeError("Board invalide nach Routing: " + "; ".join(probleme))
        open(os.path.join(projekt_repo, "BOARD.md"), "w", encoding="utf-8",
             newline="\n").write(board.generiere_board(tickets))
    return ergebnisse


def main():
    p = argparse.ArgumentParser(description="Feedback-Routing v1 (T-0055)")
    p.add_argument("projekt_repo")
    p.add_argument("--feedback", help="nur dieses Feedback-Ticket routen")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    for fb, neu, typ in route(a.projekt_repo, a.feedback, a.dry_run):
        print(f"{fb} -> {neu} ({typ}){' [dry-run]' if a.dry_run else ''}")


if __name__ == "__main__":
    main()
