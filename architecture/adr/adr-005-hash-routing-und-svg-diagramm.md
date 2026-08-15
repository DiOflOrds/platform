# ADR-005: Hash-Routing im Frontend + skriptgeneriertes Architektur-SVG (P3, G2)

*2026-08-15, ARCH. Status: vorgeschlagen (G2-DR p3/T-0006). Kontext: P3 „Mission Control 3.0" (STK-015, SWR-040–047) braucht Detailansichten mit verlinkbaren Adressen und ein Architekturbild — unter Beibehaltung von ADR-001 (stdlib-Backend) und ADR-002 (No-Build-PWA, Vanilla JS).*

## Entscheidung

1. **Navigation: Hash-Routing.** Ansichten bekommen Adressen der Form `#/<tab>/<projekt>[/<id>]` (z. B. `#/ticket/p3/T-0001`). Vanilla JS wertet `location.hash` aus (`hashchange`); jede Detailansicht ist damit verlinkbar (Querverweise, Mail-Links später möglich), Browser-Vor/Zurück funktioniert. Kein Framework, kein Build — ADR-002 bleibt unangetastet.
2. **Architekturbild: Quelle + Generator-Skript.** Die Architektur wird maschinenlesbar in `platform/architecture/komponenten.yaml` beschrieben (Komponenten, Schichten, Beziehungen). Das Skript `platform/scripts/arch_diagramm.py` erzeugt daraus ein deterministisches SVG (`platform/architecture/architektur.svg`), das eingecheckt und vom Backend als statische Datei ausgeliefert wird. Kein Client-Layouting, keine externe Diagramm-Bibliothek; Generator-Lauf gehört zum abschluss-Gate (Konsistenz Quelle ↔ Bild prüfbar).
3. **Neue Read-only-Endpunkte** im stdlib-Server: Ticket-Detail, DR-Historie, Cockpit-Aggregation, Version (`/api/version`: Code-Stand + Prozess-Start für SWR-047).

## Verworfene Alternativen

Client-seitiges Diagramm-Layout (Kraftmodelle in ES5: Aufwand/Fragilität), Mermaid/D3 via CDN (externe Abhängigkeit, ADR-002-Bruch, offline-PWA), echtes URL-Routing mit History-API (Server-Rewrites nötig — stdlib-Server bleibt dumm).

## Konsequenzen

app.js wächst um einen kleinen Router; bestehende Tabs erhalten Hash-Adressen (abwärtskompatibel: leerer Hash = Übersicht). Die YAML-Quelle wird CM-gepflegtes Architektur-Artefakt; Drift zwischen Quelle und Bild ist per Generator-Wiederholung erkennbar.
