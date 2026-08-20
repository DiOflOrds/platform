# Konfigurationsmanagement-Plan: Plattform-Projekt (v1.0, Setup-Nachzieh T-0038, CM@platform)

*2026-08-21. **Verweis-Dokument**: Die CM-Strategie der Organisation (`process/cm/cm-strategie.md`) und das Runbook (`process/cm/runbook.md`) gelten und werden nicht kopiert (B033). Hier steht nur Plattform-Spezifisches.*

## Plattform-Spezifisch

- Schreibweg nach Git ausschließlich über `git_schreiben.py` (SWR-134); Lock-Anatomie SWR-163 (kein Räumen vor einem Aufruf; `git log`/`add`/`commit` sicher, `status --porcelain` hinterlässt auf dem Mount die Sperre).
- Requirements liegen in `p9/requirements/` (p9/D003) — Identität bleibt, der CM-Plan von p9 führt sie als Work Product.
- Baselines: Tags über die Repos + Manifest mit QM-Mitzeichnung (Bestandspraxis seit genesis-v0.2).

## Work Products (SWR-181)

```yaml work-products
- pfad: docs/projektplan.md
  name: Projektplan (Dauerprojekt)
  eigentuemer: pl
  pruefstatus: qm-review bestanden (2026-08-21, pm/T-0075)
- pfad: docs/cm-plan.md
  name: CM-Plan (Verweis-Dokument)
  eigentuemer: cm
  pruefstatus: qm-review bestanden (2026-08-21, pm/T-0075)
- pfad: docs/qm-plan.md
  name: QM-Plan
  eigentuemer: qm
  pruefstatus: qm-review bestanden (2026-08-21, pm/T-0075)
- pfad: docs/historie.md
  name: Historie und Lessons Learned
  eigentuemer: pl
- pfad: verification/strategie.md
  name: Verifikationsstrategie (Ist-Stand)
  eigentuemer: test
  pruefstatus: qm-review bestanden (2026-08-21, pm/T-0075)
- pfad: roles/cm.md
  name: Rollenkarte CM (projektspezifisch)
  eigentuemer: coach
- pfad: roles/dev.md
  name: Rollenkarte DEV (projektspezifisch)
  eigentuemer: coach
- pfad: roles/test.md
  name: Rollenkarte TEST (projektspezifisch)
  eigentuemer: coach
- pfad: architecture/architektur.svg
  name: Architekturbild (generiert, arch_diagramm.py --check)
  eigentuemer: arch
- pfad: docs/betriebsdaten-ticks.md
  name: Betriebsdaten der Ticks (Bestand)
  eigentuemer: cm
  pruefstatus: Bestandsdokument, nachdeklariert (QM-Befund pm/T-0075)
```
