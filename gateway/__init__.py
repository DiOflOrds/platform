"""LLM-Gateway v1 (Sprint 1, T-0004/T-0006).

Einheitliche Executor-Schnittstelle:
    from gateway import execute
    ergebnis = execute(rolle, aufgabe, kontext)

Provider: claude (Claude Agent SDK, headless) · copilot (Stub, PoC Sprint 6)
· ollama (Stub, PoC Sprint 6). Guardrails werden hart durchgesetzt
(guardrails.yaml); jeder Lauf wird in der Run-Registry (JSONL) protokolliert.
"""
from .core import execute, Ergebnis, GuardrailVerletzung  # noqa: F401
