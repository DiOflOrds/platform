# Rollenkarte (projektspezifisch): TEST@platform (v1, 2026-08-21, T-0038)

*Ergänzt `process/roles/test.md` (gilt zuerst). Instanz: Core Team (implizit).*

## 1. Auftrag in diesem Projekt

Verifikation der Plattform: Python-Suite (~1180+ Tests), JS-Zusicherungen, Matrix, Mutationsproben.

## 2. Projektspezifisches Hintergrundwissen

- Strategie: `verification/strategie.md` (Ist-Stand, kein Wunschbild).
- Mutationsproben nur mit Wirksamkeits-Nachweis — ein alter `__pycache__` hat einmal grün gelogen (L-2026-08-20cm): Cache leeren, Mutation nachlesen.
- Volle Suite läuft nur am PC (Sandbox-Mount) — Teilmengen je Session sind normal, aber der Sprint-Report nennt, was NICHT lief.
- Bedingungen so formulieren, dass ein Fehlschlag sie nicht erfüllt (T-0071: „status ok UND ≥1 Artefakt").

## 3. Projektspezifische Tools

`js_tests.py`, `trace_matrix.py`, unittest discover; Goldset-Werkzeuge (`goldset_baseline.py`).

## 4. Historie und Lessons Learned

Pflicht-Lektüre: `docs/historie.md`. Kern: Prüfungen sind Paare; Teststrecken werden umgedreht, nie gelöscht.

## 5. Abweichungen vom Bauplan

Keine.
