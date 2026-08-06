"""Ollama-Executor v1 (T-0011, vorgezogen aus Sprint 6).

Lokales LLM auf dem Team-Node über die Ollama-HTTP-API (Standard:
http://localhost:11434, übersteuerbar per OLLAMA_HOST). Kostenlos, offline-fähig,
text-only: Dateien entstehen über die Datei-Block-Konvention (gateway/dateiblock.py).

Modellwahl: OLLAMA_MODEL > guardrails providers.ollama.model > 'llama3.1:8b'.
Nicht erreichbar / Modell fehlt -> NotImplementedError (nächste Stufe der Kette).
"""
import json
import os
import urllib.error
import urllib.request

from ..dateiblock import AUSGABE_ANWEISUNG, schreibe_dateibloecke


def _host():
    h = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    return h if h.startswith("http") else f"http://{h}"


def fuehre_aus(rolle, aufgabe, kontext, cfg):
    host = _host()
    p_cfg = (cfg.get("providers", {}).get("ollama", {}) or {})
    modell = os.environ.get("OLLAMA_MODEL") or p_cfg.get("model") or "llama3.1:8b"

    try:
        with urllib.request.urlopen(host + "/api/tags", timeout=3) as r:
            json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise NotImplementedError(f"ollama: nicht erreichbar unter {host} ({e})")

    nutzlast = {
        "model": modell,
        "stream": False,
        "options": {"temperature": 0.2},
        "messages": [
            {"role": "system",
             "content": (kontext.get("systemprompt", "") + "\n\n" + AUSGABE_ANWEISUNG)},
            {"role": "user", "content": aufgabe},
        ],
    }
    req = urllib.request.Request(host + "/api/chat",
                                 data=json.dumps(nutzlast).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=int(kontext.get("timeout_s", 900))) as r:
            antwort = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise NotImplementedError(f"ollama: Anfrage fehlgeschlagen ({e.code}): {detail} "
                                  f"— Modell installiert? (ollama pull {modell})")

    text = (antwort.get("message") or {}).get("content", "")
    dateien = schreibe_dateibloecke(text, kontext["arbeitsverzeichnis"])
    log = (f"{len(dateien)} Datei(en) aus Datei-Blöcken geschrieben: {', '.join(dateien)}"
           if dateien else "KEINE Datei-Blöcke in der Antwort — Rohantwort im Log:\n" + text)
    return {"modell": f"ollama/{modell}", "log": log, "kosten_eur": 0.0}
