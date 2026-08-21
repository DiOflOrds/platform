# -*- coding: utf-8 -*-
"""workflows.py (SWR-187, platform/T-0044): Workflows je Einheit — EINE
maschinenlesbare Quelle (`docs/workflows.yaml`), transparent dargestellt.

Ein Workflow trägt: id, name, takt, geplant_von (PL oder die Rolle selbst), das
wiederkehrende Ticket, Governance-Marken (arch_review, cm_verankert — leer ist
SICHTBAR leer, nicht weggelassen) und Schritte. Jeder Schritt: rolle (oder
`script` + werkzeug), aktion, **input**, **output** — Outputs sind in der Regel
Work Products und werden gegen den CM-Plan (workproducts) aufgelöst; ein Output
ohne bekannte WP-Referenz wird GEMELDET, nicht erfunden.

Abdeckungsprüfung (SWR-128-Familie — die Grundmenge sind die TAKT-TICKETS, nicht
die Workflow-Datei): jedes wiederkehrende Ticket einer Einheit muss von einem
Workflow getragen werden; unabgedeckte werden benannt.
"""
import io
import os
import sys

try:
    import yaml
except ImportError:
    yaml = None

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import board  # noqa: E402
import organigramm  # noqa: E402

from . import workproducts  # noqa: E402  — WP-Auflösung: dieselbe Quelle wie die WP-Sicht


def _lade_datei(repo):
    pfad = os.path.join(repo, "docs", "workflows.yaml")
    if not os.path.isfile(pfad):
        return None
    if yaml is None:
        return []
    with io.open(pfad, "r", encoding="utf-8") as f:
        try:
            return list((yaml.safe_load(f) or {}).get("workflows") or [])
        except yaml.YAMLError:
            return []


def _wp_pfade(root, einheit):
    try:
        d = workproducts.einheit(root, einheit)
    except ValueError:
        return set()
    return {w["pfad"] for w in d.get("work_products", [])}


def _pruefe_schritte(wf, wp_pfade):
    """Ketten-Integrität + WP-Auflösung je Schritt. Liefert (schritte, befunde)."""
    schritte, befunde = [], []
    for i, s in enumerate(wf.get("schritte") or [], start=1):
        s = s or {}
        eintrag = {"nr": i, "rolle": str(s.get("rolle", "")).lower(),
                   "werkzeug": s.get("werkzeug", ""), "aktion": s.get("aktion", ""),
                   "input": s.get("input", ""), "output": s.get("output", "")}
        for pflicht in ("rolle", "aktion", "input", "output"):
            if not eintrag[pflicht]:
                befunde.append(f"Schritt {i}: Feld '{pflicht}' fehlt")
        # Output gegen die Work Products des CM-Plans auflösen — melden, nicht erfinden
        out = str(eintrag["output"])
        eintrag["output_ist_wp"] = any(p in out for p in wp_pfade) if wp_pfade else False
        schritte.append(eintrag)
    if not schritte:
        befunde.append("Workflow ohne Schritte")
    return schritte, befunde


def einheit(root, name):
    """Workflows EINER Einheit inkl. Prüfungen (Kette, WP-Referenz, Takt-Abdeckung)."""
    pfade = organigramm.entdecke_einheiten(root)
    if name not in pfade:
        raise ValueError(f"Einheit unbekannt: {name}")
    repo = pfade[name]
    roh = _lade_datei(repo)
    if roh is None:
        # Grundmenge trotzdem messen: Takt-Tickets ohne Datei sind ALLE unabgedeckt
        takte = _takt_tickets(repo)
        return {"einheit": name, "datei": False, "workflows": [],
                "unabgedeckte_takte": takte,
                "hinweis": "keine Daten — docs/workflows.yaml fehlt"
                           + (f"; {len(takte)} Takt-Ticket(s) unabgedeckt" if takte else "")}
    wp_pfade = _wp_pfade(root, name)
    workflows, getragene = [], set()
    for wf in roh:
        wf = wf or {}
        schritte, befunde = _pruefe_schritte(wf, wp_pfade)
        if wf.get("ticket"):
            getragene.add(str(wf["ticket"]))
        workflows.append({
            "id": wf.get("id", ""), "name": wf.get("name", ""),
            "takt": wf.get("takt", ""), "geplant_von": str(wf.get("geplant_von", "")).lower(),
            "ticket": wf.get("ticket", ""),
            "arch_review": wf.get("arch_review", "") or "",
            "cm_verankert": wf.get("cm_verankert", "") or "",
            "schritte": schritte, "befunde": befunde,
            "rollen": sorted({s["rolle"] for s in schritte if s["rolle"] and s["rolle"] != "script"}
                             | ({str(wf.get("geplant_von", "")).lower()} - {""})),
        })
    unabgedeckt = [t for t in _takt_tickets(repo) if t["id"] not in getragene]
    return {"einheit": name, "datei": True, "workflows": workflows,
            "unabgedeckte_takte": unabgedeckt, "hinweis": ""}


def _takt_tickets(repo):
    tickets, _ = board.lade_tickets(repo)
    return [{"id": t.get("id", ""), "titel": t.get("titel", ""), "takt": t.get("takt", "")}
            for t in tickets
            if t.get("takt") and t.get("status") not in board.STATUS_FINAL]  # SWR-205


def alle(root):
    """Alle Einheiten (aktive zuerst interessant, aber alle sichtbar — keine Daten ≠ leer)."""
    return {"einheiten": [einheit(root, n) for n in sorted(organigramm.entdecke_einheiten(root))],
            "quelle": "docs/workflows.yaml je Einheit (SWR-187)"}


def fuer_rolle(root, rolle):
    """Workflows, an denen eine Rolle beteiligt ist (Schritt-Rolle oder geplant_von)."""
    rolle_l = (rolle or "").lower()
    ergebnis = []
    for name in sorted(organigramm.entdecke_einheiten(root)):
        d = einheit(root, name)
        for wf in d.get("workflows", []):
            if rolle_l in wf["rollen"]:
                ergebnis.append(dict(wf, einheit=name))
    return {"rolle": rolle_l.upper(), "workflows": ergebnis}
