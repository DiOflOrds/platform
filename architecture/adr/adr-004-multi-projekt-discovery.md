# ADR-004: Multi-Projekt per Discovery-Konvention statt Registry-Datei

*Status: entschieden (ARCH, 2026-08-07, P1/T-0004). Gate: G2-Vorlage. Bezug: SWR-025–029 (p1-req-v1.0).*

## Kontext

Mission Control soll mehrere Projekte bedienen (STK-013, F8/D023). Zu entscheiden: Wie werden Projekte bekannt — explizite Registry-Datei oder Konvention?

## Optionen

1. **Registry-Datei** (z. B. `projekte.yaml` analog Produkte): explizit, aber zweite Wahrheit neben dem Dateisystem; jedes neue Projekt braucht einen Pflege-Schritt.
2. **Discovery-Konvention:** Ein Projekt ist ein Verzeichnis unter der Repos-Wurzel mit `tickets/` und `.git` — dieselbe Konvention, die Preflight seit T-0050 (`repos_im_root`) nutzt; null Pflegeaufwand, Intake-Schritt „Registrierung" entfällt faktisch.

## Entscheidung

Option 2. Discovery als gemeinsame Funktion im Backend (`aggregation.projekte()`); Tick validiert `--projekt` gegen dieselbe Konvention. Die Produkt-Registry (`produkte.yaml`, T-0064) bleibt unberührt — sie beschreibt Matrix-Parameter je Produkt, nicht Projekte.

## Konsequenzen

Alle Lese-APIs erhalten einen `projekt`-Parameter (Default `p0` — abwärtskompatibel, SWR-028); Übersicht und Inbox iterieren über die Discovery-Liste; ein neues Projekt ist mit dem Clone sofort sichtbar (SWR-025). Repos ohne `tickets/` (process, platform, produkt-*) sind bewusst keine Projekte. Anforderungsdokumente bleiben je Projekt — die Matrix lernt daher mehrere `--swr`-Quellen (SWR-029).
