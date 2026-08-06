#!/usr/bin/env python3
"""board.py — Git-natives Ticket-Board (Sprint-0-Basisversion).

Tickets liegen als Markdown-Dateien mit YAML-Frontmatter in <projekt>/tickets/.
Dieses Skript validiert die Tickets und generiert BOARD.md als Übersicht.
Teil der Skript-Route (kein LLM nötig). Nutzung:
    python3 board.py <pfad-zum-projekt-repo>
"""
import os, re, sys
from datetime import date

FELDER = ["id", "titel", "typ", "prozess", "rolle", "sprint", "status", "prio", "erstellt"]
STATUS = ["open", "in_analysis", "in_progress", "in_review", "blocked", "done", "rejected"]
TYPEN = ["task", "problem", "change-request", "decision-request", "clarification", "finding", "feedback", "skriptifizierung"]

def parse(pfad):
    text = open(pfad, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return None, f"{pfad}: kein Frontmatter"
    fm = {}
    for zeile in m.group(1).splitlines():
        if ":" in zeile:
            k, v = zeile.split(":", 1)
            fm[k.strip()] = v.strip().strip('"')
    fm["_body"] = m.group(2).strip()
    return fm, None

def validiere(t, alle_ids):
    fehler = []
    for f in FELDER:
        if f not in t:
            fehler.append(f"Pflichtfeld fehlt: {f}")
    if t.get("status") not in STATUS:
        fehler.append(f"ungültiger status: {t.get('status')}")
    if t.get("typ") not in TYPEN:
        fehler.append(f"ungültiger typ: {t.get('typ')}")
    bb = t.get("blocked_by", "[]").strip("[]")
    for ref in [r.strip() for r in bb.split(",") if r.strip()]:
        if ref not in alle_ids:
            fehler.append(f"blocked_by verweist auf unbekanntes Ticket: {ref}")
    return fehler

def main(repo):
    tdir = os.path.join(repo, "tickets")
    tickets, probleme = [], []
    dateien = sorted(f for f in os.listdir(tdir) if f.endswith(".md"))
    ids = {f[:-3] for f in dateien}
    for f in dateien:
        t, err = parse(os.path.join(tdir, f))
        if err:
            probleme.append(err); continue
        for e in validiere(t, ids):
            probleme.append(f"{f}: {e}")
        tickets.append(t)
    if probleme:
        print("VALIDIERUNG FEHLGESCHLAGEN:", *probleme, sep="\n  ")
        sys.exit(1)

    zeilen = ["# Board (generiert von platform/scripts/board.py — nicht von Hand editieren)",
              f"\nStand: {date.today().isoformat()} · Tickets: {len(tickets)}\n"]
    for st in STATUS:
        gruppe = [t for t in tickets if t["status"] == st]
        if not gruppe:
            continue
        zeilen.append(f"\n## {st} ({len(gruppe)})\n")
        zeilen.append("| ID | Titel | Typ | Rolle | Prio | Sprint | blockiert durch |")
        zeilen.append("|---|---|---|---|---|---|---|")
        for t in sorted(gruppe, key=lambda x: (x.get("prio") != "kritisch", x.get("prio") != "hoch", x["id"])):
            bb = t.get("blocked_by", "").strip("[]") or "—"
            zeilen.append(f"| [{t['id']}](tickets/{t['id']}.md) | {t['titel']} | {t['typ']} | {t['rolle']} | {t['prio']} | {t['sprint']} | {bb} |")
    open(os.path.join(repo, "BOARD.md"), "w", encoding="utf-8").write("\n".join(zeilen) + "\n")
    print(f"OK: {len(tickets)} Tickets validiert, BOARD.md aktualisiert.")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
