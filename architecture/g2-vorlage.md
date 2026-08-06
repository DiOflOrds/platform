# G2-Vorlage — Plattform-Architektur/Technologie Backend/Frontend-MVP (Sprint 3, T-0031)

*An: Mensch (Gate G2). Von: ARCH. Datum: 2026-08-06.*

## Gegenstand

Architektur des Backend/Frontend-MVP („Mission Control v1"): 5 Komponenten (Server, Aggregation, Inbox, Mailer, PWA), API v1 (5 GET + 1 POST), Datenquelle ausschließlich die Git-Arbeitskopie. Details: `platform/architecture/architektur.md`.

## Kernentscheidungen (je als ADR dokumentiert)

1. **ADR-001 — Standardbibliothek statt FastAPI:** null neue Abhängigkeiten (Lesson T-0027: schon pyyaml verursachte CI-Drift); Abweichung von der FastAPI-Nennung in P0 Kap. 5, Migration bleibt offen. **← bewusste Abweichung, bitte bestätigen.**
2. **ADR-002 — No-build-Vanilla-PWA:** vier Ansichten + ein Formular ohne Build-Toolchain; WebSocket/Push bewusst außerhalb des MVP (P0 Kap. 8).
3. **ADR-003 — Inbox schreibt Datei + sofortigen Git-Commit:** Entscheidungen sind einzeln in der Historie evident; Arbeitskopie bleibt tick-tauglich sauber (SWR-015/024).

## Nachweise

Trace vollständig: SWR-020–024 ↔ Komponenten (Kap. 6 Architekturdokument). Verteilungsfähigkeit: API-first, zustandsfrei, Deployment identisch auf Team-Node und Hub-VM (`platform/infra/docker-compose.yml`, folgt mit T-0032). Review: DEV-Kontext (umsetzbar), QM-Kontext (konsistent, ADR-Pflicht erfüllt).

## Empfehlung

Freigabe der Architektur inkl. ADR-001-Abweichung. Bei Ablehnung von ADR-001: Umstieg auf FastAPI kostet ca. ein Ticket (Komponenten sind framework-frei gekapselt), plus Abhängigkeits-Setup auf allen Geräten.

**Entscheidung Mensch:** ☐ freigeben · ☐ mit Auflagen · ☐ zurückweisen — im Sprint-3-Review (G4) oder vorab per Decision-Inbox/E-Mail.
