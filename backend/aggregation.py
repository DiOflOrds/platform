"""BCK-Aggregation (SWR-022): Board, Sprint-Reports und Kosten/KPI read-only
aus der Git-Arbeitskopie lesen. Kein Cache, kein Zustand (SWR-024).
"""
import glob
import json
import os
import re
import sys

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import board  # noqa: E402


def lade_board(root):
    """Tickets gruppiert nach Status (Quelle: p0/tickets/*.md)."""
    p0 = os.path.join(root, "p0")
    tickets, probleme = board.lade_tickets(p0)
    gruppen = {}
    for t in sorted(tickets, key=lambda x: (x.get("status", ""), x.get("id", ""))):
        eintrag = {k: t.get(k) for k in
                   ("id", "titel", "typ", "prozess", "rolle", "sprint", "prio", "blocked_by")}
        gruppen.setdefault(t.get("status", "unbekannt"), []).append(eintrag)
    return {"gruppen": gruppen, "anzahl": len(tickets), "validierungsprobleme": probleme}


def lade_reports(root):
    """Sprint-Reports (Quelle: p0/management/sprint-*/report.md), neueste zuerst."""
    muster = os.path.join(root, "p0", "management", "sprint-*", "report.md")
    reports = []
    for pfad in sorted(glob.glob(muster), reverse=True):
        sprint = os.path.basename(os.path.dirname(pfad))
        reports.append({"sprint": sprint,
                        "text": open(pfad, encoding="utf-8").read()})
    return {"reports": reports}


def lade_kpi(root):
    """Kosten/KPI aus der Run-Registry (JSONL, append-only)."""
    pfad = os.path.join(root, "p0", "management", "runs", "run-registry.jsonl")
    laeufe = []
    if os.path.exists(pfad):
        for zeile in open(pfad, encoding="utf-8"):
            zeile = zeile.strip()
            if zeile:
                try:
                    laeufe.append(json.loads(zeile))
                except json.JSONDecodeError:
                    continue
    kosten_gesamt = round(sum(l.get("kosten_eur", 0) or 0 for l in laeufe), 4)
    je_monat, je_provider = {}, {}
    for l in laeufe:
        monat = (l.get("zeit") or "")[:7] or "unbekannt"
        je_monat[monat] = round(je_monat.get(monat, 0) + (l.get("kosten_eur", 0) or 0), 4)
        p = l.get("provider") or "unbekannt"
        je_provider[p] = je_provider.get(p, 0) + 1
    return {"laeufe": len(laeufe), "kosten_eur_gesamt": kosten_gesamt,
            "kosten_eur_je_monat": je_monat, "laeufe_je_provider": je_provider,
            "letzte": laeufe[-5:]}
