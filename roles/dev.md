# Rollenkarte (projektspezifisch): DEV@platform (v1, 2026-08-21, T-0038)

*Ergänzt `process/roles/dev.md` (gilt zuerst). Instanz: Core Team (implizit).*

## 1. Auftrag in diesem Projekt

Bau und Pflege der Plattform: Backend (stdlib, kein Framework — ADR-001), Frontend (app.js ES5 ohne Bibliothek — ADR-002), Skripte, Orchestrator/Gateway.

## 2. Projektspezifisches Hintergrundwissen

- app.js trägt **111 JS-Zusicherungen** — kein Edit ohne `js_tests.py`-Lauf; eigenständige Seiten (organisation.html) bleiben außerhalb, Integration nur per CR.
- SWR-Heimat ist `p9/requirements/` (p9/D003) — Anforderungen dort lesen, nicht suchen.
- Ergebniswort-Regeln (SWR-167): Erfolgsmeldungen nie unbedingt vor `return`.
- Ollama-Ticks prüfen die Besetzung VOR dem Aufruf (SWR-171) — beim Anfassen von tick.py diese Reihenfolge nie aufweichen.

## 3. Projektspezifische Tools

`js_tests.py`, `trace_matrix.py`, `arch_diagramm.py --check`, `organigramm.py --check` — Gates, die vor dem Fertigmelden laufen.

## 4. Historie und Lessons Learned

Pflicht-Lektüre: `docs/historie.md`. Kern: „Dein Entwurf sieht für dich richtig aus" — zweimal in Folge hat ein alter Zähltest den Autor widerlegt (L-2026-08-20cd).

## 5. Abweichungen vom Bauplan

Keine.
