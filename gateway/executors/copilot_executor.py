"""Copilot-Executor v1 (T-0069, PoC Sprint 6, F13/D023: Abo vorhanden).

GitHub Copilot CLI auf Team-Nodes (Flatrate, zählt nicht aufs API-Budget).
Läuft nur, wo die CLI installiert und eingeloggt ist (requires: node_with_gh_auth) —
sonst NotImplementedError und die Kette fällt zur nächsten Stufe (wie ollama).

Aufrufform konfigurierbar über guardrails `providers.copilot.befehl` (Liste mit
Platzhalter "{prompt}"), Default: ["copilot", "-p", "{prompt}"] — bei CLI-Updates
nur die Konfiguration anpassen (Runbook, Störungsbehandlung). Text-only:
Dateien entstehen über die Datei-Block-Konvention (gateway/dateiblock.py).

Härtung (BB-1-Erstlauf 2026-08-15, real ok aber 0 Artefakte): Die CLI dekoriert
ihre Ausgabe (ANSI-Codes, Statuszeilen) und Modelle setzen trotz Anweisung gern
Markdown-Zäune um die Blöcke. Daher: ANSI strippen, bei 0 Treffern Zäune
entfernen und erneut parsen, und bei weiterhin 0 Artefakten den Antwort-Anfang
ins Log legen (Diagnose statt Blindflug).
"""
import re
import shutil
import subprocess

from ..dateiblock import AUSGABE_ANWEISUNG, schreibe_dateibloecke

DEFAULT_BEFEHL = ["copilot", "-p", "{prompt}"]
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_ZAUN = re.compile(r"^\s*```[^\n]*$", re.M)


def _bereinigt(text):
    """ANSI-Escape-Sequenzen entfernen (CLI-Dekoration)."""
    return _ANSI.sub("", text or "")


def fuehre_aus(rolle, aufgabe, kontext, cfg):
    p_cfg = (cfg.get("providers", {}).get("copilot", {}) or {})
    befehl = p_cfg.get("befehl") or DEFAULT_BEFEHL
    if shutil.which(befehl[0]) is None:
        raise NotImplementedError(
            f"copilot: CLI '{befehl[0]}' nicht gefunden — nur auf Team-Nodes "
            f"mit installierter/eingeloggter Copilot CLI (F13/D023).")
    prompt = (f"{kontext.get('systemprompt', '')}\n\n{AUSGABE_ANWEISUNG}\n\n"
              f"## Auftrag\n\n{aufgabe}")
    kommando = [prompt if a == "{prompt}" else a for a in befehl]
    try:
        lauf = subprocess.run(kommando, capture_output=True,
            text=True, encoding="utf-8", errors="replace",
                              timeout=int(p_cfg.get("timeout_s", 300)),
                              cwd=kontext.get("arbeitsverzeichnis"))
    except (OSError, subprocess.TimeoutExpired) as e:
        raise NotImplementedError(f"copilot: Aufruf fehlgeschlagen ({e})")
    if lauf.returncode != 0:
        return {"modell": "copilot-cli", "kosten_eur": 0.0,
                "log": f"copilot: Exit {lauf.returncode}: {lauf.stderr.strip()[:300]}"}
    antwort = _bereinigt(lauf.stdout)
    dateien = schreibe_dateibloecke(antwort, kontext["arbeitsverzeichnis"])
    if not dateien:  # zweiter Versuch: Markdown-Zäune entfernen (Modelle ignorieren die Anweisung gern)
        dateien = schreibe_dateibloecke(_ZAUN.sub("", antwort), kontext["arbeitsverzeichnis"])
    if not dateien:
        return {"modell": "copilot-cli", "kosten_eur": 0.0,
                "log": ("copilot: Antwort ohne Datei-Blöcke. Rohantwort (Anfang): "
                        + " ".join(antwort.split())[:400])}
    return {"modell": "copilot-cli", "kosten_eur": 0.0,
            "log": f"copilot: {len(dateien)} Datei(en) eingepflegt: {', '.join(dateien)}"}
