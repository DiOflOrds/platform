"""Claude-Executor (T-0004): headless über das Claude Agent SDK.

Voraussetzungen auf dem Team-Node:
    pip install claude-agent-sdk        (bringt anyio mit; benötigt Node.js + Claude Code CLI)
    Umgebungsvariable ANTHROPIC_API_KEY (T-0008)

Rückgabe (roh, dict): modell, log, kosten_eur. Kosten: SDK liefert USD;
konservativ 1:1 als EUR gezählt (siehe guardrails.py).
"""
import os


def _modell_fuer_stufe(cfg, stufe):
    modelle = (cfg.get("providers", {}).get("claude", {}).get("models", {}) or {})
    return modelle.get(stufe or "standard", modelle.get("standard", "claude-sonnet-latest"))


def fuehre_aus(rolle, aufgabe, kontext, cfg):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise NotImplementedError(
            "claude: ANTHROPIC_API_KEY nicht gesetzt (T-0008) — Provider nicht verfügbar.")
    try:
        import anyio
        from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions,
                                      ResultMessage, TextBlock, query)
    except ImportError as e:
        raise NotImplementedError(f"claude: SDK fehlt (pip install claude-agent-sdk): {e}")

    modell = _modell_fuer_stufe(cfg, kontext.get("modell_stufe"))
    options = ClaudeAgentOptions(
        system_prompt=kontext.get("systemprompt", ""),
        cwd=kontext["arbeitsverzeichnis"],
        model=modell,
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
        permission_mode="acceptEdits",
        max_turns=int(kontext.get("max_turns", 25)),
    )

    log_zeilen, kosten = [], {"usd": 0.0}

    async def _lauf():
        async for nachricht in query(prompt=aufgabe, options=options):
            if isinstance(nachricht, AssistantMessage):
                for block in nachricht.content:
                    if isinstance(block, TextBlock):
                        log_zeilen.append(block.text)
            elif isinstance(nachricht, ResultMessage):
                kosten["usd"] = float(nachricht.total_cost_usd or 0.0)
                if getattr(nachricht, "is_error", False):
                    log_zeilen.append(f"[FEHLER] {getattr(nachricht, 'result', '')}")

    anyio.run(_lauf)
    return {"modell": modell, "log": "\n".join(log_zeilen), "kosten_eur": kosten["usd"]}
