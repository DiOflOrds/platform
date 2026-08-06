# ADR-003: Inbox-Schreibpfad — Datei + sofortiger Git-Commit

*Status: entschieden (ARCH, 2026-08-06, T-0031). Gate: G2-Vorlage.*

## Kontext

SWR-020 verlangt, Entscheidungen ins Decision Log zu schreiben; SWR-024 verbietet Zustand außerhalb Git; SWR-015 verlangt saubere Arbeitskopien für Ticks. Ein Backend, das nur Dateien schreibt, hinterließe eine dirty Arbeitskopie und blockierte den Orchestrator.

## Optionen

1. **Nur Dateien schreiben, Commit dem Menschen/Tick überlassen:** einfach, aber Arbeitskopie dirty → Tick-Blocker, Entscheidung ohne Audit-Trail bis zum nächsten Commit.
2. **Datei schreiben + sofort committen (Identität „Mensch via Inbox", Ticket-ID in der Message):** Entscheidung ist atomar evident (Prinzip „Artefakt = Evidenz"), Arbeitskopie bleibt sauber; dafür braucht das Backend Git im PATH und Schreibrecht auf die Arbeitskopie.
3. **Warteschlange + periodischer Sammel-Commit:** verletzt SWR-024 (Zustand außerhalb Git zwischen den Läufen).

## Entscheidung

Option 2. Entscheidungen des Menschen sind gate-relevante Ereignisse — sie gehören sofort und einzeln in die Historie.

## Konsequenzen

Backend committet ausschließlich seine eigenen drei Schreibziele (Decision Log, Ticket, BOARD.md — selektives Staging, Lesson T-0014). Push bleibt Sache des Geräts/Menschen (D007). Fehlerfall Commit → 503 an den Client, Entscheidung gilt als nicht angenommen (kein halber Zustand).
