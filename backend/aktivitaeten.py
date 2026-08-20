# -*- coding: utf-8 -*-
"""aktivitaeten.py (SWR-186, platform/T-0043): Aktivitäten je Rollen-Instanz.

Quellen (alle bestehend, keine zweite Auflösung — B033):
  1. Tickets je Einheit (board.lade_tickets): erledigt / offen / in Arbeit als Rolle,
     plus Tickets, die die Rolle REVIEWT (reviewer-Feld).
  2. Run-Registry (management/runs/run-registry.jsonl je Einheit): Läufe der Rolle —
     Provider, Status, Artefakte, Zeit, Dauer, Kosten (Skript- wie LLM-Läufe).

⚠ v1 behauptet Prosa-Vermerke in Ticket-Bodys NICHT als Aktivität (SWR-186, Ausschluss
aus derselben Familie wie SWR-183): sie tragen weder strukturierten Autor noch Zeit —
beides zu erfinden wäre eine Behauptung, die niemand gemacht hat.
"""
import json
import os
import sys

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import board  # noqa: E402
import organigramm  # noqa: E402

LAUF_LIMIT = 30  # je Einheit: die jüngsten Läufe genügen der Sicht

OFFEN = ("open", "in_analysis", "in_progress", "blocked")


def _runs(repo, rolle):
    pfad = os.path.join(repo, "management", "runs", "run-registry.jsonl")
    if not os.path.isfile(pfad):
        return []
    laeufe = []
    with open(pfad, encoding="utf-8", errors="replace") as f:
        for zeile in f:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                e = json.loads(zeile)
            except json.JSONDecodeError:
                continue  # eine kaputte Zeile reißt die Sicht nicht um
            if (e.get("rolle") or "").lower() != rolle.lower():
                continue
            laeufe.append({"zeit": e.get("zeit", ""), "ticket": e.get("ticket", ""),
                           "provider": e.get("provider", ""), "status": e.get("status", ""),
                           "artefakte": len(e.get("artefakte") or []),
                           "dauer_s": e.get("dauer_s", ""), "kosten_eur": e.get("kosten_eur", 0)})
    return laeufe[-LAUF_LIMIT:][::-1]  # jüngste zuerst


def _ticket_kurz(t, einheit):
    return {"einheit": einheit, "id": t.get("id", ""), "titel": t.get("titel", ""),
            "status": t.get("status", ""), "prio": t.get("prio", ""),
            "takt": t.get("takt", ""), "geaendert": str(t.get("geändert", "") or "")}


def fuer_rolle(root, rolle, einheit=None):
    """Aktivitäten einer Rolle — über eine Einheit oder alle aktiven (SWR-186)."""
    rolle_l = (rolle or "").lower()
    if not rolle_l:
        raise ValueError("Rolle fehlt.")
    pfade = organigramm.entdecke_einheiten(root)
    if einheit:
        if einheit not in pfade:
            raise ValueError(f"Einheit unbekannt: {einheit}")
        pfade = {einheit: pfade[einheit]}
    erledigt, offen, reviews, laeufe = [], [], [], []
    for name in sorted(pfade):
        repo = pfade[name]
        tickets, _probleme = board.lade_tickets(repo)
        for t in tickets:
            kurz = _ticket_kurz(t, name)
            if (t.get("rolle") or "").lower() == rolle_l:
                if t.get("status") == "done":
                    erledigt.append(kurz)
                elif t.get("status") in OFFEN or t.get("status") == "in_review":
                    offen.append(kurz)
            if (t.get("reviewer") or "").lower() == rolle_l and \
                    (t.get("rolle") or "").lower() != rolle_l:
                reviews.append(kurz)
        for lauf in _runs(repo, rolle_l):
            lauf["einheit"] = name
            laeufe.append(lauf)
    erledigt.sort(key=lambda x: x["geaendert"], reverse=True)
    offen.sort(key=lambda x: (x["status"] != "in_progress", x["geaendert"]), reverse=False)
    laeufe.sort(key=lambda x: x.get("zeit", ""), reverse=True)
    return {"rolle": rolle_l.upper(), "einheit": einheit or "alle",
            "erledigt": erledigt[:50], "offen": offen, "reviews": reviews[:50],
            "laeufe": laeufe[:LAUF_LIMIT],
            "zaehler": {"erledigt": len(erledigt), "offen": len(offen),
                        "reviews": len(reviews), "laeufe": len(laeufe)},
            "hinweis_v1": "Prosa-Vermerke in Ticket-Bodys werden nicht als Aktivität "
                          "behauptet (SWR-186: kein strukturierter Autor/Zeitstempel)."}
