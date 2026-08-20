# Organigramm: ASPICE-Team

*Generiert aus den Registries (`process/teams/registry.yaml`, `process/roles/besetzungen.yaml`) durch `platform/scripts/organigramm.py` — **nicht von Hand pflegen**, Änderungen gehören in die Registry (Konzept `process/docs/03-rollenmodell-v2-orga-rework.md` Kap. 8).*

**Auftrag:** ASPICE-Team: entwickelt, pflegt und maintained alle Tools/Skripte und Mission Control - fuer Genesis, sich selbst, PM und alle Projekte (festes Team)

```mermaid
graph TB
  MENSCH["Mensch<br/>Auftraggeber / Gates"]
  PM["PM-Team<br/>koordiniert alle PL"]
  MENSCH --> PM
  platform["ASPICE-Team<br/>entwicklung · aktiv"]
  PM --> platform
  ARCH_aspice["ARCH@aspice<br/>Cowork/Session"]
  platform --> ARCH_aspice
  CHG_aspice["CHG@aspice<br/>Cowork/Session"]
  platform --> CHG_aspice
  CM_aspice["CM@aspice<br/>Cowork/Session"]
  platform --> CM_aspice
  COACH_aspice["COACH@aspice<br/>Cowork/Session"]
  platform --> COACH_aspice
  DEV_aspice["DEV@aspice<br/>Cowork/Session"]
  platform --> DEV_aspice
  PL_aspice["PL@aspice<br/>Cowork/Session"]
  platform --> PL_aspice
  PROB_aspice["PROB@aspice<br/>Ollama (lokal) · gemma3:27b"]
  platform --> PROB_aspice
  QM_aspice["QM@aspice<br/>Cowork/Session"]
  platform --> QM_aspice
  RM_aspice["RM@aspice<br/>Cowork/Session"]
  platform --> RM_aspice
  TEST_aspice["TEST@aspice<br/>Cowork/Session"]
  platform --> TEST_aspice
```

## Beteiligte

| Instanz | Rolle | Motor | Takt | Status | Hinweis |
|---|---|---|---|---|---|
| ARCH@aspice | Architekt | Cowork/Session | sprint | aktiv | — |
| CHG@aspice | Change-Manager | Cowork/Session | sprint | aktiv | — |
| CM@aspice | Konfigurationsmanager | Cowork/Session | sprint | aktiv | Nimmt REL wahr (Stufe 1, registry.yaml) |
| COACH@aspice | Prozess-Coach | Cowork/Session | sprint | aktiv | — |
| DEV@aspice | Entwickler | Cowork/Session | sprint | aktiv | — |
| PL@aspice | Projektleiter | Cowork/Session | sprint | aktiv | — |
| PROB@aspice | Problemmanager | Ollama (lokal) (gemma3:27b) | schnell | aktiv | Klassifikation/Trend lokal; Ursachenanalyse per Kette auf Claude |
| QM@aspice | Qualitätsmanager | Cowork/Session | sprint | aktiv | — |
| RM@aspice | Requirements-Manager | Cowork/Session | sprint | aktiv | — |
| TEST@aspice | Verifikationsingenieur | Cowork/Session | sprint | aktiv | — |

Rollen-Bauplan: `process/roles/<rolle>.md` · projektspezifischer Teil: `roles/<rolle>.md` in diesem Repo · Historie: `docs/historie.md`
