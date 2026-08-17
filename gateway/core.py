"""Gateway-Kern (T-0004): execute(rolle, aufgabe, kontext) -> Ergebnis.

kontext (dict):
    arbeitsverzeichnis  Pfad, in dem der Agent arbeiten darf (Pflicht)
    systemprompt        Rollenkarte + Skill + Wissensbasis (Pflicht für LLM-Route)
    provider_kette      z.B. ["claude"] (Default: ["claude"])
    modell_stufe        strong|standard|cheap (Default: standard)
    aufgaben_typ        für Logging/Registry
    ticket              Ticket-ID für Logging
    guardrails_pfad     Pfad zu guardrails.yaml (Pflicht)
    registry_pfad       Pfad zur Run-Registry JSONL (Pflicht)
    geraet              Ausführungsort für die Registry (Default: hostname)
    max_turns           Obergrenze Agent-Schritte (Default 25)

Guardrails werden vor und nach dem Lauf hart durchgesetzt (T-0006).
"""
import platform as _platform
import subprocess
import time
from dataclasses import dataclass, field

from . import guardrails
from .executors import (claude_executor, copilot_executor, ollama_executor,
                        session_executor)

GuardrailVerletzung = guardrails.GuardrailVerletzung

EXECUTORS = {
    "claude": claude_executor.fuehre_aus,
    "copilot": copilot_executor.fuehre_aus,
    "ollama": ollama_executor.fuehre_aus,
    "session": session_executor.fuehre_aus,
}


@dataclass
class Ergebnis:
    status: str                 # ok | abgebrochen | fehler
    provider: str = ""
    modell: str = ""
    artefakte: list = field(default_factory=list)   # geänderte Dateien (git, relativ)
    log: str = ""
    kosten_eur: float = 0.0
    dauer_s: float = 0.0
    meldung: str = ""
    # SWR-137 (promt-team/T-0004): die Token-Baseline, getrennt nach statisch (Systemprompt,
    # harte Regeln, Tool-Definitionen, eingebettetes Wissen) und dynamisch (Eingabe,
    # Retrieval, Tool-Ergebnisse, Verlauf). ⚠ Vorgabe ist `None` und ausdrücklich **nicht**
    # `0`: ein Executor, der nichts meldet, hat nicht null Token verbraucht, sondern nicht
    # gemessen. Eine 0 hier wäre eine Schätzung, die wie ein Ergebnis aussieht — genau der
    # Fall, den der Bestand siebenmal als `kosten_eur: 0.0` trägt.
    token_statisch: int = None
    token_dynamisch: int = None


def _geaenderte_dateien(verzeichnis):
    """git status --porcelain im Arbeitsverzeichnis (leer, wenn kein Git)."""
    try:
        out = subprocess.run(["git", "-C", verzeichnis, "status", "--porcelain"],
                             capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=15)
        if out.returncode != 0:
            return None
        return {z[3:].strip() for z in out.stdout.splitlines() if z.strip()}
    except (OSError, subprocess.SubprocessError):
        return None


def execute(rolle, aufgabe, kontext):
    """Aufgabe über die Provider-Kette ausführen. Wirft nie — Fehler landen im Ergebnis."""
    start = time.time()
    kette = kontext.get("provider_kette") or ["claude"]
    registry_pfad = kontext["registry_pfad"]
    try:
        cfg = guardrails.lade_guardrails(kontext["guardrails_pfad"])
        guardrails.pruefe_vor_lauf(cfg, registry_pfad)
    except GuardrailVerletzung as e:
        erg = Ergebnis(status="abgebrochen", meldung=str(e), dauer_s=time.time() - start)
        _protokolliere(registry_pfad, rolle, aufgabe, kontext, erg)
        return erg

    vorher = _geaenderte_dateien(kontext["arbeitsverzeichnis"])
    letzter_fehler = "kein Provider in der Kette verfügbar"
    for provider in kette:
        executor = EXECUTORS.get(provider)
        if executor is None:
            letzter_fehler = f"unbekannter Provider: {provider}"
            continue
        try:
            roh = executor(rolle, aufgabe, kontext, cfg)
        except NotImplementedError as e:
            letzter_fehler = str(e)
            continue  # on_unavailable: next_in_chain
        except Exception as e:  # Executor-Fehler: nächste Stufe versuchen
            letzter_fehler = f"{provider}: {type(e).__name__}: {e}"
            continue

        if roh.get("wartet"):
            # Zweiphasiger Provider (session): Prompt erzeugt, Antwort steht aus.
            erg = Ergebnis(status="wartet", provider=provider, modell=roh.get("modell", ""),
                           log=roh.get("log", ""), meldung=roh.get("log", ""),
                           dauer_s=time.time() - start)
            _protokolliere(registry_pfad, rolle, aufgabe, kontext, erg)
            return erg

        erg = Ergebnis(status="ok", provider=provider, modell=roh.get("modell", ""),
                       log=roh.get("log", ""), meldung=roh.get("log", ""),  # BB-1: Log in die
                       kosten_eur=float(roh.get("kosten_eur", 0.0)),        # Registry (Diagnose)
                       dauer_s=time.time() - start)
        nachher = _geaenderte_dateien(kontext["arbeitsverzeichnis"])
        if vorher is not None and nachher is not None:
            erg.artefakte = sorted(nachher - vorher)  # nur durch diesen Lauf geänderte Dateien
        try:
            guardrails.pruefe_nach_lauf(cfg, erg.kosten_eur)
        except GuardrailVerletzung as e:
            erg.status = "abgebrochen"
            erg.meldung = str(e)
        _protokolliere(registry_pfad, rolle, aufgabe, kontext, erg)
        return erg

    erg = Ergebnis(status="fehler", meldung=letzter_fehler, dauer_s=time.time() - start)
    _protokolliere(registry_pfad, rolle, aufgabe, kontext, erg)
    return erg


def _protokolliere(registry_pfad, rolle, aufgabe, kontext, erg):
    """Run-Registry-Pflicht (logging.run_registry: required)."""
    try:
        guardrails.schreibe_run(registry_pfad, {
            "rolle": rolle,
            "ticket": kontext.get("ticket", ""),
            "aufgaben_typ": kontext.get("aufgaben_typ", ""),
            "aufgabe": (aufgabe or "")[:200],
            "geraet": kontext.get("geraet") or _platform.node(),
            "provider": erg.provider,
            "modell": erg.modell,
            "status": erg.status,
            "kosten_eur": round(erg.kosten_eur, 4),
            "dauer_s": round(erg.dauer_s, 1),
            # SWR-137: durchgereicht, **nicht** normalisiert. `None` bleibt `None` —
            # ein `round(None or 0)` wäre die Stelle, an der die fehlende Messung zur
            # gemessenen Null wird.
            "token_statisch": erg.token_statisch,
            "token_dynamisch": erg.token_dynamisch,
            "artefakte": erg.artefakte,
            "meldung": erg.meldung,
        })
    except OSError as e:
        erg.meldung = (erg.meldung + f" | Run-Registry nicht schreibbar: {e}").strip(" |")
