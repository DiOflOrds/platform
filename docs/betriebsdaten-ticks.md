# Betriebsdaten Tick-Pfad (CM, T-0036, Stand 2026-08-06)

Zweck: Der Tick-Pfad war seit Sprint 1 ungenutzt (QM-Punkt 2, Sprint-2-Report). Dieses Dokument sammelt die realen Betriebsdaten aller bisherigen autonomen Ticks als Grundlage für das Budget-Review Sprint 4 (D012) und die Provider-Planung (F13).

## Datenbasis: Run-Registry (`p0/management/runs/run-registry.jsonl`)

| Lauf | Datum | Ticket | Rolle | Gerät | Provider/Modell | Status | Kosten | Dauer |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-08-06 | T-0010 | CM | DESKTOP-8OOO6JS (team-node-1) | ollama/gemma3:27b | ok | 0,00 € | 177,4 s |
| 2 | 2026-08-06 | T-0036 | CM | Cowork-Sandbox | session (Phase 1: wartet) | wartet | 0,00 € | — |
| 3 | 2026-08-06 | T-0036 | CM | Cowork-Sandbox | session (Phase 2: dieses Artefakt) | ok | 0,00 € | — |

## Befunde

1. **Beide API-freien Ketten-Stufen sind real erprobt:** Ollama auf dem Team-Node (Sprint 1, L-003: `OLLAMA_MODEL`-Override nötig) und Session-Austausch in der Cowork-Sandbox (dieser Lauf, zweiphasig mit Warte-Registry-Eintrag). Kumulierte API-Kosten aller Ticks: **0,00 €** — die Kette [ollama, session, claude] hält Kosten strukturell niedrig (D012 bestätigt sich).
2. **Preflight wirkt als Tick-Precondition (T-0024):** Beide Sprint-3-Läufe starteten mit `PREFLIGHT: STARTKLAR` (Locks/Status/Board geprüft); kein Analyse-Block durch Mount-Artefakte im Tick-Pfad.
3. **Claude-Tick weiter ausstehend:** T-0008 (API-Key) liegt beim Menschen; ohne Key keine Kostendaten der Claude-Stufe. Empfehlung an PL: Budget-Review Sprint 4 (D012) nur mit mindestens einem echten Claude-Tick durchführen, sonst erneut verschieben.
4. **Betriebshinweis Sandbox:** Externe Netzzugriffe (auch Git-Read) waren in dieser Session blockiert — strenger als D007 dokumentiert. Ticks in Sandbox-Sessions funktionieren nur mit lokal gemounteten Arbeitskopien und dem Session-Provider; Team-Node/VM bleiben der Normalbetrieb (Geräteregister-Eintrag angepasst per T-0024-Betriebshinweis).

## Nächste Schritte (CM)

Nach T-0008: einen Claude-Tick mit kleinem Auftrag fahren (Kette [claude], tier standard), Kosten je Tick in dieses Dokument nachtragen. Nach T-0035/VM: Tick-Betrieb auf der VM in den Cron-/Runbook-Betrieb überführen (`process/cm/runbook.md`).
