# Projektplan: Plattform-Projekt (v1.0, Setup-Nachzieh T-0038)

*2026-08-21, PL@platform. Dauerprojekt — der Plan verweist auf den Masterplan (`process/docs/00-masterplan.md`) und trägt nur, was dort nicht steht: den laufenden Zuschnitt.*

## 1. Ziele (Dauerauftrag)

| # | Ziel | Erfolgskriterium |
|---|---|---|
| Z1 | Die Plattform (Mission Control, board.py, Orchestrator/Gateway, Skripte) trägt alle Projekte | Plattform-Pflicht gelebt: kein Projekt baut eigene Werkzeuge (Konzept 04 Kap. 3.3) |
| Z2 | Werkzeugbedarf der Projekte wird als CR bedient | CR-Durchlaufzeit sichtbar im Board |
| Z3 | Eigene Qualität: Suite grün, Zusicherungen von fremder Hand | Testzahl + Matrix je Sprint im Report |

## 2. Phasen

Dauerbetrieb in Sprints (Register, Takt 60 min). Große Schnitte laufen als beauftragte Projekte (Muster: P11 baut auf der Plattform-Fläche, Plattform liefert).

## 3. Aufgabenstruktur und Workflows

Profil `entwicklung`, volle Gates. Offener Bestand (gemessen 2026-08-21): T-0038 (dieses Setup), T-0039/T-0040 (neue Sichten, Requirements-first — SWR-181–184 draft), T-0041 (typ-Literale, Huckepack), T-0042 (SWR-Nachtrag-Review).

## 4. Team und Rollen

Core Team implizit; Abweichung: PROB@platform (ollama/gemma3:27b, takt schnell — F18). Einziges Projekt mit Schreibrecht auf `platform`.

## 5. Infrastruktur

Repos `platform` (+ Requirements-Heimat in `p9/requirements` — p9/D003, dort bleiben sie). CI: board-check; Sandbox pusht nie; git-Lock-Regeln SWR-163.

## 6. Timeline

Je Sprint aus dem pm-Plan (Kapitel aktuell/nächster); keine erfundenen Fernziele.

## 7. Risiken

| Risiko | Wirkung | Maßnahme | Eigentümer |
|---|---|---|---|
| Anforderungs-Heimat p9 wird übersehen (Name ≠ Ort) | SWRs veralten unbemerkt | Anzeigename gesetzt (SWR-175); Verweis hier + in p9-Plan | RM |
| Ollama-Schnelltakt zieht Falsches | Schaden im Repo | SWR-171-Besetzungsprüfung (aktiv), T-0071-Messfaden | CM/PROB |

## 8. Berichtsweg

PL berichtet an PM je Sprint; Historie: `docs/historie.md` (neu, wird je Sprint fortgeschrieben).
