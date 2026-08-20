# -*- coding: utf-8 -*-
"""workproducts.py (SWR-181/182, platform/T-0039): Work-Product-Sicht je Einheit.

Quelle ist der maschinenlesbare Block im CM-Plan des Projekts (`docs/cm-plan.md`,
Zaun ```yaml work-products — die EINE Quelle, SWR-181). Die Sicht liefert je Einheit:
deklarierte Work Products mit Existenz, letzter Änderung (git log, nur lesend —
KEIN Aufruf, der auf diesem Mount eine index.lock hinterlässt, SWR-163) und beide
Lücken-Richtungen: deklariert-aber-fehlt und vorhanden-aber-nirgends-deklariert
(docs/ + verification/). Einheiten ohne CM-Plan melden sichtbar „keine Daten"
(SWR-096-Muster) statt einer leeren gesunden Liste.
"""
import io
import os
import re
import subprocess
import sys

try:
    import yaml
except ImportError:
    yaml = None

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import organigramm  # noqa: E402  — Discovery, eine Quelle (SWR-178-Geist)

BLOCK = re.compile(r"```yaml work-products\s*\n(.*?)```", re.S)
UNDEKLARIERT_ORDNER = ("docs", "verification")


def _cm_block(repo):
    pfad = os.path.join(repo, "docs", "cm-plan.md")
    if not os.path.isfile(pfad):
        return None
    with io.open(pfad, "r", encoding="utf-8") as f:
        text = f.read()
    m = BLOCK.search(text)
    if not m or yaml is None:
        return []
    try:
        return list(yaml.safe_load(m.group(1)) or [])
    except yaml.YAMLError:
        return []


def _stand(repo, rel):
    """Letzte Änderung per git log (Exit 0, hinterlässt KEINE Sperre — SWR-163-Tabelle)."""
    try:
        lauf = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%cs", "--", rel],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=10)
        return lauf.stdout.strip() or "?"
    except (OSError, subprocess.TimeoutExpired):
        return "?"


def einheit(root, name):
    """Work-Product-Stand EINER Einheit."""
    pfade = organigramm.entdecke_einheiten(root)
    if name not in pfade:
        raise ValueError(f"Einheit unbekannt: {name}")
    repo = pfade[name]
    deklariert = _cm_block(repo)
    if deklariert is None:
        return {"einheit": name, "cm_plan": False, "work_products": [],
                "undeklariert": [], "hinweis": "keine Daten — docs/cm-plan.md fehlt "
                "(Setup-Nachzieh, Konzept 04 Kap. 4.2)"}
    eintraege, deklarierte_pfade = [], set()
    for wp in deklariert:
        wp = wp or {}
        rel = str(wp.get("pfad", "")).strip()
        deklarierte_pfade.add(rel)
        voll = os.path.join(repo, rel.replace("/", os.sep))
        vorhanden = os.path.isfile(voll)
        eintraege.append({
            "pfad": rel, "name": wp.get("name", rel),
            "eigentuemer": wp.get("eigentuemer", ""),
            "pruefstatus": wp.get("pruefstatus", ""),
            "vorhanden": vorhanden,
            "stand": _stand(repo, rel) if vorhanden else "—",
        })
    undeklariert = []
    for ordner in UNDEKLARIERT_ORDNER:
        basis = os.path.join(repo, ordner)
        if not os.path.isdir(basis):
            continue
        for datei in sorted(os.listdir(basis)):
            rel = f"{ordner}/{datei}"
            if datei.endswith(".md") and rel not in deklarierte_pfade:
                undeklariert.append(rel)
    return {"einheit": name, "cm_plan": True, "work_products": eintraege,
            "undeklariert": undeklariert, "hinweis": ""}


def alle(root):
    """Alle Einheiten — Einheiten ohne CM-Plan bleiben sichtbar (keine Daten ≠ leer)."""
    return {"einheiten": [einheit(root, n) for n in sorted(organigramm.entdecke_einheiten(root))],
            "quelle": "docs/cm-plan.md je Einheit, Zaun 'yaml work-products' (SWR-181)"}
