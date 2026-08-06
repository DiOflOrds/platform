# ADR-001: HTTP-Stack — Python-Standardbibliothek statt FastAPI (MVP)

*Status: entschieden (ARCH, 2026-08-06, T-0031). Gate: G2-Vorlage.*

## Kontext

P0 Kap. 5 nennt FastAPI als Beispiel für das Backend. Die Plattform ist bislang bewusst abhängigkeitsarm (einzige externe Abhängigkeit: pyyaml — und selbst die verursachte CI-Drift, T-0027/L-Lesson). Betriebsorte sind heterogen: Windows-Team-Node, Cloud-Sandbox ohne verlässlichen Paket-Zugriff, künftige VM.

## Optionen

1. **FastAPI + uvicorn:** komfortabel (Validierung, OpenAPI), Industriestandard; aber 2 externe Abhängigkeiten + Installationspflicht auf jedem Gerät, CI-Anpassung, Sandbox-Risiko.
2. **Standardbibliothek (`http.server.ThreadingHTTPServer` + `json`):** null neue Abhängigkeiten, läuft überall sofort, vollständig offline testbar; dafür Handarbeit bei Routing/Validierung.

## Entscheidung

Option 2 für den MVP. Der API-Umfang (5 GET, 1 POST, statische Dateien) rechtfertigt kein Framework; Zero-Dependency ist auf Sandbox/Node/VM der robustere Betriebsmodus (Lesson T-0027).

## Konsequenzen

Routing/Fehlerbehandlung selbst geschrieben (klein halten, Unit-Tests decken sie ab). Kein automatisches OpenAPI — API-Tabelle im Architekturdokument ist der Vertrag. Migration auf FastAPI bleibt möglich (Komponenten kapseln die Logik framework-frei); Wiedervorlage, wenn API-Umfang oder Nutzerzahl wächst (nach P0).
