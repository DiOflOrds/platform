# Software-Architektur Plattform — Backend/Frontend (v1.5, P10 Sprint 1; v1.4 P7; v1.3 P4; v1.2 P3; v1.1 P1; v1 Sprint 3, T-0031)

*Rolle ARCH (SWE.2). Basis: SWR-020–024 (reviewed, T-0030) + SWR-025–029 (p1-req-v1.0, T-0004). Leitplanke (P0 Kap. 5): verteilungsfähig — API-first, kein Zustand außerhalb von Git/Hub. Entscheidungen: siehe `adr/`.*

> **Delta v1.5 (P10 Sprint 1, p10/T-0003, SWR-077–081):** Tickets sind nicht mehr nur lesbar — zweiter Schreibpfad neben der Skript-Route (**ADR-007**). Die Regeln bleiben in `scripts/board.py` (`aktualisiere`, `fingerprint`, `zeitpunkt`, Label-Validierung); neu ist die Fassade `backend/tickets.py` mit `GET /api/ticket/editor` (PIN-frei, Formularzustand) und `POST /api/ticket` (PIN über den vorhandenen Schreibschutz, ADR-006). Konflikte gegen die parallele Routine-Session werden über einen Inhalts-Fingerabdruck erkannt, ein gescheiterter Commit nimmt Ticket **und** BOARD.md zurück. Frontend: Editor-Ansicht im Ticket-Detail, Label-Pillen und Label-Filter im Board. Unverändert: BOARD.md-Format (Labels bewusst nur im HMI, siehe ADR-007 Punkt 8).
>
> **Delta v1.3 (P4 Sprint 0, p4/T-0004, SWR-048–052):** LAN-Betrieb mit PIN-Schutz (localhost frei, remote nur mit `MC_PIN`-Header; sicherer Default: ohne PIN keine Remote-Schreibzugriffe) und Briefkasten-Chat (versionierte Briefe je Projekt, Antwort in derselben Datei, Commit sofort). Entscheidung: ADR-006. Leitplanke: nur LAN, kein Internet-Expose.
> **Delta v1.4 (P7 Sprint 1, p7/T-0005, SWR-053–057):** Team-Ansichten — Modul `teams.py` (Steckbrief/Konfiguration/Charta/Digests aus Team-Repos mit `team.yaml`), Endpunkte `/api/team*` mit **PIN-Lesegate** (ADR-006-Delta), Konfigurations-Schreibpfad mit Sofort-Commit (Identität „Mensch via HMI", Konten = Klasse A ausgenommen), Cockpit-Team-Kachel, Frontend-Tab „Team" mit Konfigurator.
>
> **Delta v1.2 (P3 Sprint 0, p3/T-0004, SWR-040–047):** Frontend wird interaktive Arbeitsfläche — Hash-Routing für verlinkbare Detailansichten (Ticket, DR-Historie, Cockpit), Requirements/Traceability als geparste Tabellen, Architekturbild aus versionierter Quelle (`komponenten.yaml` → Generator-Skript → eingechecktes SVG), `/api/version` für Frontend/Backend-Versionsabgleich (SWR-047). Entscheidung: ADR-005. Unverändert: ADR-001/002/003/004.
>
> **Delta v1.1 (P1 Sprint 1, T-0004, SWR-025–029):** Mission Control ist multi-projektfähig — Projekt-Discovery per Konvention (ADR-004), `projekt`-Parameter auf allen Lese-APIs (Default p0), projektübergreifende Übersicht und Inbox; Tick/Preflight/Matrix arbeiten über alle Projekte. Unverändert: stdlib-Stack (ADR-001), No-build-PWA (ADR-002), Inbox-Schreibpfad (ADR-003).

## 1. Kontext

Der Mensch steuert das Team heute über Git-Rohartefakte (BOARD.md, Reports, Decision Log). Der MVP („Mission Control v1") stellt dieselben Informationen als HTTP-API + PWA bereit und macht Entscheidungen (DRs) ohne Git-Zugriff möglich. Datenquelle bleibt ausschließlich die Git-Arbeitskopie der drei Repos (process, platform, p0) auf dem Betriebsgerät (Team-Node, später Hub-VM).

## 2. Komponenten

| Komponente | Ort | Verantwortung | SWR |
|---|---|---|---|
| **BCK-Server** | `platform/backend/server.py` | HTTP-Endpunkte (JSON-API + statisches Frontend); kein eigener Zustand | SWR-020, 022, 024 |
| **BCK-Aggregation** | `platform/backend/aggregation.py` | Lesen/Parsen: Tickets/BOARD, Sprint-Reports, Run-Registry (Kosten/KPI) | SWR-022 |
| **BCK-Inbox** | `platform/backend/inbox.py` | Offene DRs listen; Entscheidung annehmen → Decision-Log-Zeile + Ticket-Notiz + Git-Commit | SWR-020, 024 |
| **BCK-Tickets** | `platform/backend/tickets.py` | Schreibfassade für Tickets (ADR-007): Formularzustand + Fingerabdruck lesen, Änderung an `board.aktualisiere` übergeben, Commit „Mensch via HMI", Rücknahme bei Fehlschlag | SWR-077–081 |
| **BCK-Mailer** | `platform/backend/mailer.py` | E-Mail-Benachrichtigung via SMTP (env-Konfiguration); ausfalltolerant | SWR-023 |
| **FRT-PWA** | `platform/backend/static/` | No-build-Frontend (Board, Reports, KPI, Inbox); nur API-Aufrufe | SWR-021 |

Bestand unverändert: board.py (BRD), Gateway (GW), Guardrails (GRD), Orchestrator (ORC), trace_matrix (CI-Vorstufe).

## 3. Schnittstellen (API v1)

| Endpunkt | Methode | Inhalt |
|---|---|---|
| `/api/board` | GET | Tickets + Statusgruppen (Quelle: `p0/tickets/*.md`) |
| `/api/reports` | GET | Sprint-Reports (Quelle: `p0/management/sprint-*/report.md`) |
| `/api/kpi` | GET | Kosten je Monat/Tick, Provider-Verteilung (Quelle: Run-Registry JSONL) |
| `/api/inbox` | GET | Offene DRs (typ `decision-request`, nicht final) mit Optionen/Frist/Default |
| `/api/inbox/<ticket-id>/decision` | POST | `{option, begruendung}` → Decision Log + Ticket + Commit |
| `/` u. statisch | GET | PWA (index.html, manifest) |

Fehlerfälle: 404 unbekanntes Ticket, 400 invalide Entscheidung, 503 Schreiben fehlgeschlagen; SMTP-Fehler beeinflussen den API-Status nie (SWR-023).

## 4. Dynamik: Entscheidung über die Inbox

1. GET `/api/inbox` liest DR-Tickets direkt aus der Arbeitskopie (kein Cache — SWR-024).
2. POST validiert Option gegen das Ticket, hängt eine Zeile ans Decision Log (append-only), schreibt die Entscheidung als Notiz ans Ticket, regeneriert BOARD.md und committet die drei Dateien (Identität „Mensch via Inbox").
3. Mailer meldet neue DRs bzw. bestätigt Entscheidungen an die E-Mail aus D004 (best effort).

Konsequenz für Ticks: Arbeitskopie bleibt nach jedem Inbox-Schreiben sauber (Commit gehört zur Operation) — verträglich mit SWR-015.

## 5. Verteilung und Deployment

Backend läuft dort, wo die Arbeitskopie liegt: Team-Node (heute) oder Hub-VM (T-0035). API-first: FRT und künftige Team-Nodes sprechen ausschließlich HTTP. Deployment als Infra-as-Code: `platform/infra/docker-compose.yml` (ein Service, Volume = Repo-Wurzel; identisch auf VM und Node). Kein Zustand im Container (SWR-024) — Neustart/Umzug verlustfrei.

## 6. Traceability SWR ↔ Komponente

SWR-020 → BCK-Server + BCK-Inbox · SWR-021 → FRT-PWA · SWR-022 → BCK-Aggregation (+ Server) · SWR-023 → BCK-Mailer · SWR-024 → BCK-Server/Inbox (Architektur-Invariante, per Review + Neustart-Test). Alle Ziel-SWR zugeordnet; keine Komponente ohne SWR.

## 7. Entscheidungen (ADR-Verzeichnis)

- ADR-001: HTTP-Stack — Python-Standardbibliothek statt FastAPI (MVP)
- ADR-002: Frontend — No-build-Vanilla-PWA, vom Backend ausgeliefert
- ADR-003: Inbox-Schreibpfad — Datei + sofortiger Git-Commit
- ADR-004: Multi-Projekt — Discovery per Konvention (tickets/ + .git)
- ADR-005: Hash-Routing im Frontend + skriptgeneriertes Architektur-SVG (P3)
- ADR-006: LAN-Betrieb mit PIN-Schutz + Briefkasten-Ablage (P4)
- ADR-007: Zweiter Schreibpfad auf Tickets — HMI-Editor, Regeln in board.py, Fingerabdruck statt Sperre (P10)
