"""Guardrails v1 (T-0006): guardrails.yaml laden und hart durchsetzen.

Limits (budget.limit_tick_eur, budget.limit_month_eur) führen bei Überschreitung
zu Abbruch + Meldung (GuardrailVerletzung). Jede Aktion wird in der Run-Registry
(JSONL, append-only) protokolliert — Monatsbudget wird daraus berechnet.
Kosten in USD werden konservativ 1:1 als EUR gezählt.
"""
import json
import os
from datetime import datetime, timezone

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


class GuardrailVerletzung(Exception):
    """Hartes Limit verletzt oder verbotene Aktion — Abbruch + Meldung."""


def lade_guardrails(pfad):
    if yaml is None:
        raise GuardrailVerletzung("PyYAML fehlt (pip install pyyaml) — ohne Guardrails kein Lauf.")
    with open(pfad, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    for schluessel in ("budget", "permissions", "logging"):
        if schluessel not in cfg:
            raise GuardrailVerletzung(f"guardrails.yaml unvollständig: Abschnitt '{schluessel}' fehlt.")
    return cfg


def monatskosten_eur(registry_pfad, jetzt=None):
    """Summe der Kosten des laufenden Monats aus der Run-Registry (JSONL)."""
    jetzt = jetzt or datetime.now(timezone.utc)
    monat = jetzt.strftime("%Y-%m")
    summe = 0.0
    if not os.path.exists(registry_pfad):
        return 0.0
    with open(registry_pfad, encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                e = json.loads(zeile)
            except json.JSONDecodeError:
                continue  # defekte Zeile zählt nicht — wird von pruefe_registry gemeldet
            if str(e.get("zeit", "")).startswith(monat):
                summe += float(e.get("kosten_eur", 0.0))
    return summe


def pruefe_vor_lauf(cfg, registry_pfad):
    """Vor jedem LLM-Lauf: Monatsbudget-Reserve für einen Tick vorhanden?"""
    budget = cfg["budget"]
    limit_monat = float(budget["limit_month_eur"])
    limit_tick = float(budget["limit_tick_eur"])
    bisher = monatskosten_eur(registry_pfad)
    if bisher >= limit_monat:
        raise GuardrailVerletzung(
            f"Monatslimit erreicht: {bisher:.2f} € >= {limit_monat:.2f} € — {budget['on_limit']}.")
    if bisher + limit_tick > limit_monat:
        raise GuardrailVerletzung(
            f"Monatsbudget-Reserve zu klein für einen Tick ({bisher:.2f} € + "
            f"{limit_tick:.2f} € > {limit_monat:.2f} €) — {budget['on_limit']}.")
    return bisher


def pruefe_nach_lauf(cfg, kosten_eur):
    """Nach dem Lauf: Tick-Limit prüfen (Überschreitung → Abbruch + Meldung)."""
    limit_tick = float(cfg["budget"]["limit_tick_eur"])
    if kosten_eur > limit_tick:
        raise GuardrailVerletzung(
            f"Tick-Limit überschritten: {kosten_eur:.2f} € > {limit_tick:.2f} € — Lauf gestoppt, Ergebnis verworfen bis Review.")


def aktion_verboten(cfg, aktion):
    return aktion in (cfg.get("permissions", {}).get("forbidden_actions") or [])


def schreibe_run(registry_pfad, eintrag):
    """Run-Registry-Eintrag (JSONL, append-only). Pflicht laut logging.run_registry."""
    os.makedirs(os.path.dirname(registry_pfad), exist_ok=True)
    eintrag = dict(eintrag)
    eintrag.setdefault("zeit", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    with open(registry_pfad, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(eintrag, ensure_ascii=False) + "\n")
    return eintrag
