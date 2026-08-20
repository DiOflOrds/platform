# Verifikationsstrategie: Plattform-Projekt (v1.0 — Ist-Stand, Setup-Nachzieh T-0038, TEST@platform)

*2026-08-21. Beschreibt den real existierenden Verifikationsstand — kein Wunschbild.*

## Ebenen und Träger (gemessen)

| Ebene | Träger | Umfang (Stand 2026-08-21) | Lauf |
|---|---|---|---|
| Python-Unit | `platform/tests/test_*.py` | ~1180+ Tests, 75+ Dateien | volle Suite am PC (Sandbox-Mount zu langsam — ehrliche Grenze); Teilmengen je Session |
| JS-Zusicherungen | `platform/tests/js/` via `js_tests.py` | 111 (app.js) + organisation.html-Anteile | Skript-Route |
| SWR↔Test-Matrix | `trace_matrix.py` | SWR-001–184 | je Sprint |
| CI | board-check (GitHub Actions) | Board-Validität | je Push |

## Grundsätze

1. Zusicherungen von fremder Hand schützen den Autor vor sich selbst (L-2026-08-20cd) — simple Zähltests sind Langstreckenläufer.
2. Prüfungen sind Paare (by); Teststrecken werden geschärft, nie gelöscht (bz).
3. Mutationsproben nur mit Nachweis, dass die Mutation wirksam war (L-2026-08-20cm).
4. Eine Bedingung, die ein Fehlschlag erfüllt, ist keine Bedingung (T-0071-Lehre: „Tick mit status ok UND ≥1 Artefakt").

## Lücken (benannt, nicht versteckt)

- Volle Suite läuft nicht in der Sandbox — Sprint-Läufe am PC tragen sie.
- SWR-177–184 sind draft; ihre Tests existieren, die Review-Anbindung läuft über T-0042.
