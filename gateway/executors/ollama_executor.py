"""Ollama-Executor v1 (T-0011, vorgezogen aus Sprint 6).

Lokales LLM auf dem Team-Node über die Ollama-HTTP-API (Standard:
http://localhost:11434, übersteuerbar per OLLAMA_HOST). Kostenlos, offline-fähig,
text-only: Dateien entstehen über die Datei-Block-Konvention (gateway/dateiblock.py).

Modellwahl (SWR-169): OLLAMA_MODEL > Besetzungsregister (kontext['modell_name'])
> guardrails providers.ollama.model > 'llama3.1:8b'.
⚠ Die Reihenfolge steht hier und im Code gleichlautend — sie war es einmal nicht, und
das Register fehlte in beiden: alle drei Ticks vom 2026-08-20 sind mit
`404: model 'llama3.1:8b' not found` gestorben, während das Register `gemma3:27b` trug.
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


def _chat(host, nutzlast, timeout_s):
    """Ein `/api/chat`-Aufruf. Eigene Funktion, damit die Messung prüfbar ist."""
    req = urllib.request.Request(host + "/api/chat",
                                 data=json.dumps(nutzlast).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        return json.loads(r.read().decode("utf-8"))


def messe_statisch(host, modell, systemtext, timeout_s=60):
    """Die Token des **statischen** Anteils — gemessen, nicht geschätzt (SWR-141).

    Ollama meldet je Aufruf `prompt_eval_count`: die Token des **ganzen** Prompts. Das
    ist eine Zahl, und der Vertrag aus SWR-137 verlangt **zwei** — statisch (Systemprompt,
    harte Regeln, Ausgabeanweisung) und dynamisch (die Aufgabe). Eine Aufteilung nach
    Zeichenanteil wäre eine Schätzung, und der Auftragstext verbietet sie wörtlich.

    Gemessen wird sie stattdessen mit einem **zweiten Aufruf ohne Erzeugung**
    (`num_predict: 0`), der nur die Systemnachricht enthält. Dessen `prompt_eval_count`
    ist der statische Anteil **einschließlich** seiner Vorlagenhülle; der dynamische ist
    die Differenz zum vollen Aufruf. Beide Zahlen sind damit gemessen und ihre Summe ist
    per Konstruktion die gemessene Gesamtzahl — keine Aufteilung, sondern zwei Messungen
    und eine Subtraktion.

    ⚠ Der Preis ist eine zusätzliche Prompt-Auswertung je Lauf. Er ist lokal und
    kostenlos, und er ist der Unterschied zwischen einer Baseline und einer Vermutung.

    Rückgabe: `int` oder `None` (nicht messbar — dann steht das Feld als Lücke im
    Blocker und **nicht** als `0`).
    """
    try:
        antwort = _chat(host, {"model": modell, "stream": False,
                               "options": {"temperature": 0.0, "num_predict": 0},
                               "messages": [{"role": "system", "content": systemtext}]},
                        timeout_s)
    except Exception:
        return None
    wert = antwort.get("prompt_eval_count")
    return wert if isinstance(wert, int) else None


def fuehre_aus(rolle, aufgabe, kontext, cfg):
    host = _host()
    p_cfg = (cfg.get("providers", {}).get("ollama", {}) or {})
    # SWR-169: Rangfolge wie im Modul-Docstring. Das Besetzungsregister steht VOR den
    # Guardrails, weil es die Stelle ist, die der Auftraggeber pflegt — eine falsche
    # Angabe ist dort sichtbar und in einem Zug korrigierbar.
    modell = (os.environ.get("OLLAMA_MODEL")
              or (kontext.get("modell_name") or "").strip()
              or p_cfg.get("model")
              or "llama3.1:8b")

    try:
        with urllib.request.urlopen(host + "/api/tags", timeout=3) as r:
            json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise NotImplementedError(f"ollama: nicht erreichbar unter {host} ({e})")

    systemtext = kontext.get("systemprompt", "") + "\n\n" + AUSGABE_ANWEISUNG
    nutzlast = {
        "model": modell,
        "stream": False,
        "options": {"temperature": 0.2},
        "messages": [
            {"role": "system", "content": systemtext},
            {"role": "user", "content": aufgabe},
        ],
    }
    try:
        antwort = _chat(host, nutzlast, int(kontext.get("timeout_s", 900)))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise NotImplementedError(f"ollama: Anfrage fehlgeschlagen ({e.code}): {detail} "
                                  f"— Modell installiert? (ollama pull {modell})")

    text = (antwort.get("message") or {}).get("content", "")
    dateien = schreibe_dateibloecke(text, kontext["arbeitsverzeichnis"])
    log = (f"{len(dateien)} Datei(en) aus Datei-Blöcken geschrieben: {', '.join(dateien)}"
           if dateien else "KEINE Datei-Blöcke in der Antwort — Rohantwort im Log:\n" + text)

    # SWR-141: die Token-Baseline. `gesamt` ist gemessen, `statisch` ist gemessen —
    # `dynamisch` ist ihre Differenz und keine Aufteilung. Fehlt eine der beiden
    # Messungen, bleiben BEIDE Felder `None`: eine halbe Messung als ganze auszugeben
    # wäre der Fehler aus SWR-140 im Kleinen.
    gesamt = antwort.get("prompt_eval_count")
    statisch = (messe_statisch(host, modell, systemtext)
                if isinstance(gesamt, int) else None)
    dynamisch = None
    if statisch is None or not isinstance(gesamt, int) or gesamt - statisch < 0:
        statisch = None
    else:
        dynamisch = gesamt - statisch
    return {"modell": f"ollama/{modell}", "log": log, "kosten_eur": 0.0,
            "token_statisch": statisch, "token_dynamisch": dynamisch}
