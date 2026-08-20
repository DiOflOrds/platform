# -*- coding: utf-8 -*-
"""kommunikation.py (SWR-183/184, platform/T-0040): eine Kommunikations-Zeitleiste
über alle Einheiten — Briefe (Briefkästen) und Decision Requests (offen + entschieden),
chronologisch, neueste zuerst, mit harter Umfangsgrenze.

⚠ v1 schließt Ticket-Verlaufsvermerke AUSDRÜCKLICH aus (SWR-183): sie stehen in
Ticket-Bodys ohne strukturierten Zeitstempel — sie in eine Zeitleiste zu heben hieße
Zeiten zu erfinden.

⚠ Datenklassen (SWR-184): Einträge sensibler Einheiten erscheinen nur, wenn das
bestehende PIN-Lesegate passiert wurde — dieselbe Funktion wie SWR-053, KEIN zweites
Gate (B033). Blockiert das Gate, werden die zurückgehaltenen Einheiten BENANNT:
Abwesenheit muss von Leere unterscheidbar sein (SWR-128-Familie).
"""
import os
import sys

try:
    import yaml
except ImportError:
    yaml = None

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from . import aggregation, briefkasten, inbox  # noqa: E402

LIMIT_STANDARD = 100
LIMIT_MAX = 300


def _sensible_einheiten(root):
    """repo-Namen mit datenklasse sensibel (Projekt-Registry — eine Quelle)."""
    pfad = os.path.join(root, "process", "teams", "registry.yaml")
    if yaml is None or not os.path.isfile(pfad):
        return set()
    import io
    with io.open(pfad, "r", encoding="utf-8") as f:
        teams = (yaml.safe_load(f) or {}).get("teams", {})
    return {(t or {}).get("repo", k) for k, t in teams.items()
            if (t or {}).get("datenklasse") == "sensibel"}


def _dr_zeit(eintrag):
    """Zeitstempel eines entschiedenen DR — aus dem Entscheidungstext, wenn vorhanden."""
    try:
        z = inbox.entscheidungszeitpunkt(eintrag.get("entscheidung", "") or "")
        return z or ""
    except Exception:  # noqa: BLE001 — Zeit ist Zusatznutzen, nie Absturzgrund
        return ""


def zeitleiste(root, pin_ok, einheit=None, limit=LIMIT_STANDARD):
    """Briefe + DRs aller (oder einer) Einheit(en), neueste zuerst, hart begrenzt."""
    limit = max(1, min(int(limit or LIMIT_STANDARD), LIMIT_MAX))
    sensibel = _sensible_einheiten(root)
    einheiten = aggregation.projekte(root)
    if einheit:
        if einheit not in einheiten:
            raise ValueError(f"Einheit unbekannt: {einheit}")
        einheiten = [einheit]
    gesperrt, eintraege = [], []
    for name in einheiten:
        if name in sensibel and not pin_ok:
            gesperrt.append(name)  # SWR-184: benennen, nicht verschweigen
            continue
        try:
            briefe = briefkasten.liste(root, name).get("briefe", [])
        except Exception:  # noqa: BLE001 — eine kaputte Quelle reißt die Sicht nicht um
            briefe = []
        for b in briefe:
            eintraege.append({"zeit": b.get("zeit", ""), "einheit": name, "art": "brief",
                              "von": b.get("von", ""), "id": b.get("id", ""),
                              "titel": (b.get("nachricht", "") or "")[:200],
                              "status": b.get("status", ""),
                              "beantwortet": bool(b.get("antwort"))})
    # DRs (Quelle ist bereits organisationsweit): entschiedene + offene
    for e in inbox.historie(root).get("historie", []):
        name = e.get("projekt", "")
        if einheit and name != einheit:
            continue
        if name in sensibel and not pin_ok:
            if name not in gesperrt:
                gesperrt.append(name)
            continue
        eintraege.append({"zeit": _dr_zeit(e), "einheit": name, "art": "dr-entschieden",
                          "von": "Mensch", "id": e.get("id", ""),
                          "titel": (e.get("titel", "") or "")[:200],
                          "status": e.get("status", ""), "beantwortet": True})
    for e in inbox.liste(root).get("inbox", []):
        name = e.get("projekt", "")
        if einheit and name != einheit:
            continue
        if name in sensibel and not pin_ok:
            if name not in gesperrt:
                gesperrt.append(name)
            continue
        eintraege.append({"zeit": e.get("zeit", "") or "", "einheit": name, "art": "dr-offen",
                          "von": e.get("rolle", "") or "Team", "id": e.get("id", ""),
                          "titel": (e.get("titel", "") or "")[:200],
                          "status": "wartet auf Mensch", "beantwortet": False})
    # Neueste zuerst; Einträge ohne Zeit ans Ende (ehrlich: unbekannt, nicht uralt)
    eintraege.sort(key=lambda x: (x["zeit"] == "", x["zeit"]), reverse=False)
    eintraege.sort(key=lambda x: x["zeit"], reverse=True)
    mit_zeit = [x for x in eintraege if x["zeit"]]
    ohne_zeit = [x for x in eintraege if not x["zeit"]]
    begrenzt = (mit_zeit + ohne_zeit)[:limit]
    return {"eintraege": begrenzt, "gesamt": len(eintraege), "limit": limit,
            "gesperrt": sorted(gesperrt),
            "hinweis_v1": "Ticket-Verlaufsvermerke sind in v1 ausgeschlossen (SWR-183: "
                          "kein strukturierter Zeitstempel — Zeiten werden nicht erfunden)."}
