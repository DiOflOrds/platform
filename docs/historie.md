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
| 2026-08-21 | **Sprint 28:** Nachverbuchung des kompletten Projektmodell-Rework (125 Dateien, 16 Repos — in KEINEM Repo committet, obwohl der Befund zweimal „nach abschluss.cmd" meldete); Testdurchlauf über **alle 85** Module statt einer Auswahl fand **drei rote** (SWR-189 Instanzschlüssel, SWR-171-Zusicherung, `projekt_setup` ohne `sichere_ausgabe`); SWR-190 Goldset-Abdeckung als stehende Prüfung; p11-Frontend-Rückbau ausgeführt | Sprint-28-Commits, T-0045, SWR-189/190 |
| 2026-08-21 | **Sprint 29:** `SWR-191` Commit-Prüfung misst den **Baum** statt den Index (beide falschen Befunde aus Sprint 28 weg, `pm` 1→0); `SWR-192` Kommentare an Aufgaben im Ticket-Rumpf, **auch an erledigten** (vierte Berührung von T-0030 **gebaut**); `SWR-193` repo-übergreifende Sperre ausdrückbar — `promt-team/T-0003`/`T-0012` stehen nach **vier** Terminierungen erstmals ehrlich auf `blocked`; `SWR-194` Lehre ohne Vertreter als **Sperrklinke** (29 von 34 benannt, nicht rot); `SWR-195` keine neue Dublette im Entscheidungslog | T-0030/T-0034/T-0036/T-0045/T-0046, SWR-191–195 |

## Lessons Learned (Auswahl mit Verbleib — vollständige Lehren in den Rollenkarten v2)

| # | Lehre | Quelle | Übernommen nach |
|---|---|---|---|
| 1 | Eine Gegenprobe, die die Funktion prüft und nicht ihren Aufrufer, misst die Hälfte, die man selbst geschrieben hat | SWR-171 | Rollenkarten DEV/TEST/QM |
| 2 | Der gelingende Aufruf kann die Sperre hinterlassen — Fehler-Anatomie vor Fix | SWR-163 | Rollenkarte CM, roles/cm.md |
| 3 | Was ein Skript zusichern kann, wird nicht abgeschrieben (Zahlen entstehen, statt kopiert zu werden) | SWR-173/174 | Berichtsweg |
| 4 | Eine Bedingung, die ein Fehlschlag erfüllt, ist keine Bedingung | pm/T-0071 | verification/strategie.md |
| 5 | Eine Testauswahl ist eine Behauptung über die Menge, die man NICHT gefahren hat — „78 grün" und „alles grün" sind zwei Sätze | SWR-189 | Rollenkarten TEST/QM, Runbook |
| 6 | Ein Literal, das eine Registry zitiert, ist kein Testfehler, sondern der einzige Ort, an dem eine Umbenennung auffällt — abgeleitet wäre es tautologisch | SWR-189 | Rollenkarte TEST |
| 7 | Eine Begründung, die mit der einzigen erlaubten Handlung zusammenfällt, ist von einer Rationalisierung nicht zu unterscheiden | platform/T-0045 | Rollenkarte PL, Runbook |
| 8 | Ein stehengebliebenes `index.lock` lässt sich mit `GIT_INDEX_FILE` UMGEHEN — ohne Räumen vor einem Aufruf und ohne Eingriff in `.git` | SWR-163/164, Sprint 28 | Rollenkarte CM, roles/cm.md |
| 9 | Ein falscher Befund ist **teurer** als kein Befund: er hat dieselbe Wirkung wie ein echter und kennt keine Handlung, die ihn abstellt | SWR-191 | Rollenkarten DEV/QM, Runbook |
| 10 | Der Fehler war nicht die Zählung, sondern die **Größe**: der Index ist ein Zwischenspeicher, der Baum ist die Arbeit | SWR-191 | Rollenkarte CM, roles/cm.md |
| 11 | Sieben von neun DoD-Punkten waren **Struktur und keine Arbeit** — erst zählen, was schon dasteht, dann schätzen | SWR-192 | Rollenkarte PL, Runbook |
| 12 | Ein **Schalter an einer Sperre** ist keine Sperre — die Ausnahme kommt NEBEN die Regel, nicht hinein | SWR-192 | Rollenkarte DEV |
| 13 | Ein Aufwärtsgang braucht ein Abbruchkriterium **aus dem Gegenstand**: eine Zahl sagt „hier sind mehrere Ordner", nicht „und einer davon bin ich" | SWR-193 | Rollenkarten DEV/TEST |
| 14 | Eine Prüfung, die **sich selbst liest**, kann ihre eigene Frage beantworten — der Prüfer gehört aus der geprüften Menge heraus | SWR-194 | Rollenkarten TEST/QM |
| 15 | Eine Zitierung kann lügen, ein **Schweigen** kann es nicht — deshalb sucht die Prüfung die FEHLENDE Zusicherung, nicht die schlechte | SWR-194 | Rollenkarte QM |
| 16 | B033 mit einem **Schreibweg** als vergessener Kopie ist teurer als mit einer Datei: ein zweiter Schreibweg erzeugt Zustände, die der erste für unmöglich hält | SWR-195 | Rollenkarten CM/DEV |
| 17 | Ein Commit, dessen Erfolg **nicht geprüft** ist, ist kein Commit — ein verschluckter Fehlschlag wird beim nächsten Schreiben zum unzulässigen Statussprung | Sprint 29, zweimal | Rollenkarte CM, Runbook Kap. 16/17 |

## Offene Fäden

- pm/T-0071 Schritt 3: Wirkungsmessung Schnelltakt wartet auf ersten Tick mit `status: ok` + Artefakt. ⚠ Sprint 29: steht jetzt auf **`blocked`** mit `blocked_by: [T-0077]` statt terminiert — und das war die ganze Zeit möglich, `T-0077` liegt im selben Repo.
- `platform/T-0047` (Schnitt aus T-0036): 1003 Zitatstellen ohne Repo-Präfix gegen 319 mit — aber die zwei größten Posten sind die Entscheidungslogs selbst, wo die Angabe **nicht** mehrdeutig ist. Die ehrliche Untermenge fehlt noch.
- T-0039/T-0040 Bau nach Review der SWR-181–184; T-0041 Huckepack; T-0042 Review.
