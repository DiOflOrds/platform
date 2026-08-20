# Rollenkarte (projektspezifisch): CM@platform (v1, 2026-08-21, T-0038)

*Ergänzt `process/roles/cm.md` (gilt zuerst). Instanz: Core Team (implizit).*

## 1. Auftrag in diesem Projekt

Betrieb und Konfigurationsführung der Plattform selbst: Repos, Baselines, CI, der eine Git-Schreibweg, Geräteregister.

## 2. Projektspezifisches Hintergrundwissen

- **git-Lock-Anatomie dieses Mounts (SWR-163):** `git status --porcelain` beendet einen lesenden Refresh durch LÖSCHEN — verboten auf dem Mount, die Sperre bleibt trotz Exit 0 liegen. `add`/`commit`/`log`/`diff` sind sicher. Räumen VOR einem Aufruf bleibt verboten (T-0015 DoD 2), erlaubt DANACH mit zwei Nachweisen.
- Parkplatz `verwaiste-locks` wächst systembedingt — Größenordnung zusichern, nie Festzahl (SWR-164).
- Schreibweg ausschließlich `git_schreiben.py` (SWR-134); Preflight-Altbestand-Grenzen SWR-166.

## 3. Projektspezifische Tools

`preflight.py`, `git_schreiben.py`, `sprint_register.py`, `board.py` — alles Skript-Routen dieses Repos.

## 4. Historie und Lessons Learned

Pflicht-Lektüre: `docs/historie.md`. Wichtigste Lehre: Fehler-Anatomie vor Fix — der Rückfall aus SWR-134 sah drei Sprints wie die Lösung aus.

## 5. Abweichungen vom Bauplan

Keine.
