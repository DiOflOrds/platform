# ADR-002: Frontend — No-build-Vanilla-PWA, vom Backend ausgeliefert

*Status: entschieden (ARCH, 2026-08-06, T-0031). Gate: G2-Vorlage.*

## Kontext

SWR-021: Board/Reports/KPI/Inbox smartphone-tauglich ohne Git-Zugriff. MVP-Schnitt fixiert: lesend + Inbox (P0 Kap. 8); WebSocket/Push bewusst nicht gezogen (Sprint-3-Plan).

## Optionen

1. **SPA-Framework (React/Vue) mit Build-Pipeline:** mächtig, aber Node-Toolchain auf jedem Entwicklungsgerät, Build-Artefakte im Repo oder CI-Build nötig.
2. **Vanilla HTML/JS/CSS (eine Seite, fetch auf die API) + Web-App-Manifest:** kein Build, versionierbar als Klartext, vom Backend direkt ausgeliefert; PWA-Basis (installierbar) ohne Push.

## Entscheidung

Option 2. Der MVP zeigt vier Ansichten und ein Formular — dafür ist eine Build-Toolchain unverhältnismäßig; Klartext-Artefakte passen zum Prinzip „Artefakt = Evidenz".

## Konsequenzen

Bewusster Verzicht auf Komponenten-Ökosystem; bei wachsendem Frontend-Scope (nach P0) neu bewerten. Manifest + eine JS-Datei; Abnahme per UI-Checkliste (T-0034) statt automatisierter UI-Tests im MVP.
