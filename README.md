# platform — Orchestrator, Backend, Frontend, Infrastruktur

Software des virtuellen ASPICE-Teams. Wird ab Sprint 1 (Orchestrator-MVP) bzw. Sprint 3 (Backend/Frontend) vom Team selbst entwickelt — nach den eigenen Prozessen (die Anforderungen an diese Plattform sind das erste echte SWE.1-Requirements-Set, siehe P0 Sprint 2).

## Struktur (Zielbild)

| Pfad | Inhalt | Ab Sprint |
|---|---|---|
| `orchestrator/` | Tick-Loop auf Claude Agent SDK: Board lesen → Skript-Route prüfen → über LLM-Gateway delegieren → Ergebnis zurückschreiben; Guardrails | 1 |
| `orchestrator/config/guardrails.yaml` | Kosten-Limits, Provider-Routing, Rechte, gesperrte Aktionen | 1 |
| `gateway/` | LLM-Gateway: einheitliche Executor-Schnittstelle `execute(rolle, aufgabe, kontext)` mit drei Plugins — `claude` (Agent SDK, Sprint 1), `copilot` (GitHub Copilot CLI auf Team-Nodes, PoC Sprint 6), `ollama` (lokales LLM auf Team-Nodes, PoC Sprint 6) | 1/6 |
| `scripts/` | Deterministische Skripte (Traceability-Generator, Template-/Label-Sync, Feedback-Routing, Baseline-Manifest, KPI-Erhebung) | 1–5 |
| `backend/` | FastAPI: GitLab-Aggregation, HITL-Queue, Aufgaben-Queue mit Lease (Team-Nodes), Run-Registry, Traceability-API, Geräteregister, KPI-Service | 3 |
| `frontend/` | PWA „Mission Control": Live-Board, Decision-Inbox, Requirements, Traceability, Baselines, Produktkatalog, KPIs | 3 |
| `node-runner/` | Team-Node-Dienst für Laptops/PCs (Pull mit Lease, Heartbeat, Fähigkeits-Registrierung) | 6 (PoC) |
| `infra/` | Docker Compose für den Hub (Cloud-VM), Deployment, Monitoring, Backup | 3 |

## Architektur-Leitplanken (aus Masterplan Kap. 5, verbindlich)

API-first; kein Zustand außerhalb von Git/Tickets/Backend-DB; Aufgabenvergabe Pull-Prinzip mit Zeit-Lease; Nodes verbinden nur ausgehend; jede Agent-/Skript-Aktion geloggt mit Kosten und Ausführungsweg; harte Kosten-Limits mit Abschaltung.
