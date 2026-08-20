# Historie: Plattform-Projekt — Chronik und Lessons Learned

*Projektgedächtnis (Konzept 03 Kap. 5). Pflicht-Lektüre jeder Rollen-Instanz. Geseedet 2026-08-21 aus P0-Abschlussbericht, PROJEKTSTATUS und Sprint-Reports — Details dort, hier die Landkarte.*

## Steckbrief

- **Auftrag:** Die Plattform (Mission Control, board.py, Orchestrator/Gateway, Skripte) für alle Projekte bauen und betreiben — Dauerprojekt, einziges mit Schreibrecht auf `platform`
- **Gegründet:** 2026-08-02 (P0 Genesis, Masterplan); umgewidmet zum Plattform-Projekt 2026-08-21 (pm/T-0073)
- **Profil / Datenklasse:** entwicklung / intern
- **Status:** aktiv

## Chronik (Meilensteine — Feinstand in den Sprint-Reports)

| Datum | Ereignis | Beleg |
|---|---|---|
| 2026-08-07 | P0 „Genesis" abgeschlossen und abgenommen; Baseline genesis-v1.0; 112 grüne Tests | D024, p0-Abschlussbericht |
| 2026-08-15 | Genesis 2.0: Organisation mit PM-Team + Profilen (F14–F17) | p0/D027 |
| 2026-08-17 | Sprintzähler/Register (SWR-106), Discovery projects/ | pm/T-0041, P9 |
| 2026-08-20 | Sprint 24–27: Rückbau-Wächter-Paar, git-Lock-Anatomie (SWR-163), Preflight-Altbestand (SWR-166), Modell aus Register (SWR-169), Besetzungsprüfung vor Tick (SWR-171/172), Anzeigename (SWR-175) | PROJEKTSTATUS, T-0021–T-0035 |
| 2026-08-20/21 | Orga-Rework 1+2: Rollenmodell v2, Projektmodell, Core Team implizit, ein Besetzungs-Resolver; Organisations-HMI (Organigramm/Live/Planung + Konfiguration) | pm/T-0070–T-0073, T-0028/T-0037 |
| 2026-08-21 | Setup-Nachzieh + neue Sichten Work Products/Kommunikation (SWR-181–184) | T-0038–T-0042 |

## Lessons Learned (Auswahl mit Verbleib — vollständige Lehren in den Rollenkarten v2)

| # | Lehre | Quelle | Übernommen nach |
|---|---|---|---|
| 1 | Eine Gegenprobe, die die Funktion prüft und nicht ihren Aufrufer, misst die Hälfte, die man selbst geschrieben hat | SWR-171 | Rollenkarten DEV/TEST/QM |
| 2 | Der gelingende Aufruf kann die Sperre hinterlassen — Fehler-Anatomie vor Fix | SWR-163 | Rollenkarte CM, roles/cm.md |
| 3 | Was ein Skript zusichern kann, wird nicht abgeschrieben (Zahlen entstehen, statt kopiert zu werden) | SWR-173/174 | Berichtsweg |
| 4 | Eine Bedingung, die ein Fehlschlag erfüllt, ist keine Bedingung | pm/T-0071 | verification/strategie.md |

## Offene Fäden

- pm/T-0071 Schritt 3: Wirkungsmessung Schnelltakt wartet auf ersten Tick mit `status: ok` + Artefakt.
- T-0039/T-0040 Bau nach Review der SWR-181–184; T-0041 Huckepack; T-0042 Review.
