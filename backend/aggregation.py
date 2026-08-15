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


def projekte(root):
    """SWR-025/ADR-004: Projekt-Discovery — Verzeichnisse mit tickets/ und .git."""
    namen = []
    try:
        for d in sorted(os.listdir(root)):
            p = os.path.join(root, d)
            if os.path.isdir(os.path.join(p, "tickets")) and os.path.isdir(os.path.join(p, ".git")):
                namen.append(d)
    except OSError:
        pass
    return namen


def projekt_pfad(root, projekt):
    """Projektnamen gegen die Discovery validieren (SWR-025); wirft ValueError."""
    bekannte = projekte(root)
    if projekt not in bekannte:
        raise ValueError(f"unbekanntes Projekt: {projekt} "
                         f"(bekannt: {', '.join(bekannte) or 'keine'})")
    return os.path.join(root, projekt)


def uebersicht(root):
    """SWR-026: je Projekt offene Tickets + offene Decision Requests."""
    eintraege = []
    for name in projekte(root):
        tickets, _ = board.lade_tickets(os.path.join(root, name))
        offen = [t for t in tickets if t.get("status") not in ("done", "rejected")]
        drs = [{"id": t.get("id"), "titel": t.get("titel")} for t in offen
               if t.get("typ") == "decision-request"]
        eintraege.append({"projekt": name, "tickets_gesamt": len(tickets),
                          "tickets_offen": len(offen), "offene_drs": drs})
    return {"projekte": eintraege}


def lade_board(root, projekt="p0"):
    """Tickets gruppiert nach Status (Quelle: <projekt>/tickets/*.md; SWR-025)."""
    tickets, probleme = board.lade_tickets(projekt_pfad(root, projekt))
    gruppen = {}
    for t in sorted(tickets, key=lambda x: (x.get("status", ""), x.get("id", ""))):
        eintrag = {k: t.get(k) for k in
                   ("id", "titel", "typ", "prozess", "rolle", "sprint", "prio", "blocked_by")}
        gruppen.setdefault(t.get("status", "unbekannt"), []).append(eintrag)
    return {"gruppen": gruppen, "anzahl": len(tickets), "validierungsprobleme": probleme}


def lade_ticket(root, projekt="p0", ticket_id=""):
    """SWR-040 (P3): Einzelticket mit allen Metadaten + Body für die Detailansicht."""
    tickets, _ = board.lade_tickets(projekt_pfad(root, projekt))
    for t in tickets:
        if t.get("id") == ticket_id:
            felder = {k: v for k, v in t.items() if not k.startswith("_")}
            felder["body"] = t.get("_body", "")
            felder["projekt"] = projekt
            return felder
    raise ValueError(f"unbekanntes Ticket: {ticket_id} in {projekt}")


def lade_reports(root, projekt="p0"):
    """Sprint-Reports (Quelle: <projekt>/management/sprint-*/report.md), neueste zuerst."""
    muster = os.path.join(projekt_pfad(root, projekt), "management", "sprint-*", "report.md")
    reports = []
    for pfad in sorted(glob.glob(muster), reverse=True):
        sprint = os.path.basename(os.path.dirname(pfad))
        reports.append({"sprint": sprint,
                        "text": open(pfad, encoding="utf-8").read()})
    return {"reports": reports}


def lade_requirements(root, projekt="p0"):
    """SWR-030: Requirements-Markdown eines Projekts read-only (relativer Pfad + Text)."""
    basis = os.path.join(projekt_pfad(root, projekt), "requirements")
    dateien = []
    for pfad in sorted(glob.glob(os.path.join(basis, "**", "*.md"), recursive=True)):
        dateien.append({"datei": os.path.relpath(pfad, basis).replace(os.sep, "/"),
                        "text": open(pfad, encoding="utf-8").read()})
    return {"dateien": dateien}


def lade_verifikation(root, projekt="p0"):
    """SWR-031: Verifikationsreports (inkl. Traceability-Matrizen) eines Projekts."""
    basis = os.path.join(projekt_pfad(root, projekt), "verification")
    dateien = []
    for pfad in sorted(glob.glob(os.path.join(basis, "**", "*.md"), recursive=True)):
        dateien.append({"datei": os.path.relpath(pfad, basis).replace(os.sep, "/"),
                        "text": open(pfad, encoding="utf-8").read()})
    return {"dateien": dateien}


def lade_baselines(root):
    """SWR-032: annotierte Tags (Baselines/Releases) je Repo unter der Wurzel."""
    import subprocess
    ergebnis = []
    for d in sorted(os.listdir(root)):
        if not os.path.isdir(os.path.join(root, d, ".git")):
            continue
        out = subprocess.run(["git", "-C", os.path.join(root, d), "tag", "-n1"],
                             capture_output=True, text=True)
        tags = [z.strip() for z in out.stdout.splitlines() if z.strip()]
        ergebnis.append({"repo": d, "tags": tags})
    return {"repos": ergebnis}


def lade_kpi(root, projekt="p0"):
    """Kosten/KPI aus der Run-Registry des Projekts (JSONL, append-only)."""
    pfad = os.path.join(projekt_pfad(root, projekt), "management", "runs", "run-registry.jsonl")
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
