# Board (generiert von platform/scripts/board.py — nicht von Hand editieren)

Stand: 2026-08-20 · Tickets: 32 · davon wiederkehrend: 1


## open (3)

| ID | Titel | Typ | Takt | Rolle | Verantwortlich | Prio | Sprint | blockiert durch |
|---|---|---|---|---|---|---|---|---|
| [T-0001](tickets/T-0001.md) | Takt: Werkzeug- und Plattformpflege (dauerhaft — Tools, Skripte, Mission Control) | task | je Session | cm | Team | hoch | 0 | — |
| [T-0027](tickets/T-0027.md) | Der Abschlussbericht hat für seine EIGENEN Kennzahlen keine Prüfung — fünfmal in sechs Sprints eine fortgeschriebene statt einer gemessenen Zahl | problem | einmalig | cm | Team | hoch | 0 | — |
| [T-0030](tickets/T-0030.md) | Kommentare an Aufgaben — Verlauf im Ticket-Rumpf wie im Team-Chat, ein Schreibweg, kein zweiter Speicher | change-request | einmalig | dev | Team | hoch | 25 | — |

## in_review (2)

| ID | Titel | Typ | Takt | Rolle | Verantwortlich | Prio | Sprint | blockiert durch |
|---|---|---|---|---|---|---|---|---|
| [T-0031](tickets/T-0031.md) | Der Tick meldet „abgeschlossen“, wenn das Gateway `status=fehler` liefert — und er kehrt beim zweiten Lauf desselben Tickets nicht auf den Basis-Branch zurück | problem | einmalig | dev | Team | kritisch | 26 | — |
| [T-0032](tickets/T-0032.md) | Der Guardrails-Default `llama3.1:8b` stoppt jeden Ollama-Tick — das Besetzungsregister trägt seit dem 06.08. `gemma3:27b`, und die Lehre dazu ist vierzehn Tage alt | problem | einmalig | dev | Team | kritisch | 26 | — |

## done (27)

| ID | Titel | Typ | Takt | Rolle | Verantwortlich | Prio | Sprint | blockiert durch |
|---|---|---|---|---|---|---|---|---|
| [T-0029](tickets/T-0029.md) | Der Preflight blockiert auf Befunde, die niemand mehr beheben kann — 83 abgebrochene Push-Läufe in drei Tagen und 12 Ticks, die nie liefen | problem | einmalig | cm | Team | kritisch | 25 | — |
| [T-0002](tickets/T-0002.md) | Problem (N-0006): CI-Lauf 'tests' schlug nach dem pm/T-0024-Push fehl — lokal nicht reproduzierbar | problem | einmalig | prob | Team | hoch | 0 | — |
| [T-0003](tickets/T-0003.md) | CR: CI-Status nach dem Push selbst prüfen — ohne Zugangsdaten (ersetzt den Blick auf die Actions-Seite) | change-request | einmalig | cm | Team | hoch | 0 | — |
| [T-0004](tickets/T-0004.md) | CR: Ein rotes CI-Ergebnis soll den fehlgeschlagenen Schritt nennen — sonst ist ROT kein Befund, sondern eine Farbe | change-request | einmalig | cm | Team | hoch | 0 | — |
| [T-0005](tickets/T-0005.md) | Problem (B064): Ein Projekt im Sammel-Repo erbt die Baseline seines Nachbarn — p11 und p12 trugen p10-v1.0 | problem | einmalig | cm | Team | hoch | 0 | — |
| [T-0006](tickets/T-0006.md) | CR: Der Cockpit-Payload unterscheidet „echte Null\" nicht von „nicht geliefert\" — Eingangsbedingung für SWR-096 | change-request | einmalig | cm | Team | hoch | 0 | — |
| [T-0007](tickets/T-0007.md) | Problem: board.py liest Git-Ausgabe ohne feste Kodierung — der Auto-Wächter brach am Host seit dem 17.08. bei JEDEM Lauf ab | problem | einmalig | cm | Team | hoch | 0 | — |
| [T-0009](tickets/T-0009.md) | Problem: Der Wächter bricht weiter ab — die T-0007-Reparatur hat die Leseseite gerichtet und die Schreibseite mitgerissen | problem | einmalig | cm | Team | hoch | 0 | — |
| [T-0010](tickets/T-0010.md) | Befund: Die Verifikation misst die Arbeitskopie, der Push liefert HEAD — SWR-109 war nie committet | problem | einmalig | cm | Team | hoch | 0 | — |
| [T-0011](tickets/T-0011.md) | Befund: Preflight meldet STARTKLAR, während plan_drift und sprint_vergangen sechs Befunde tragen — zwei berechnete Kennzahlen werden nirgends gemeldet | problem | einmalig | cm | Team | hoch | 0 | — |
| [T-0012](tickets/T-0012.md) | Die Unterminiert-Prüfung fragt in Sprints statt in Kalenderdaten (Brief pm/N-0041) | change-request | einmalig | cm | Team | hoch | 0 | — |
| [T-0013](tickets/T-0013.md) | Sprintregister kennt kein Ende — zwei Routine-Läufe können gleichzeitig in dieselben Repos schreiben | problem | einmalig | cm | Team | hoch | 0 | — |
| [T-0014](tickets/T-0014.md) | Eine entschiedene Frage blieb 16 Minuten lang „liegt beim Menschen" — Inbox und Preflight meinen Verschiedenes mit „entschieden | problem | einmalig | cm | Team | hoch | 0 | — |
| [T-0017](tickets/T-0017.md) | Statuswechsel und sein Commit sind zwei Vorgänge — eine Git-Sperre dazwischen verliert einen Zustand lautlos | problem | einmalig | cm | Team | hoch | 0 | — |
| [T-0018](tickets/T-0018.md) | Die Sperren-Räumung des einen Git-Schreibwegs lief in Produktion nicht — sie fand preflight nur, wenn der Aufrufer ihn mitbrachte | problem | einmalig | cm | Team | hoch | 0 | — |
| [T-0019](tickets/T-0019.md) | trace_matrix.py ohne --alle-projekte überschreibt die echte Matrix mit einer unvollständigen | problem | einmalig | cm | Team | hoch | 0 | — |
| [T-0021](tickets/T-0021.md) | Der Commit hinterlässt die Sperre für den nächsten: tmp_obj-Reste auf einem Mount ohne unlink-Recht | problem | einmalig | cm | Team | hoch | 0 | — |
| [T-0022](tickets/T-0022.md) | Der Entscheidungsweg setzte eine Datei voraus, die ein anderer Weg anlegt (SWR-152) | problem | einmalig | dev | Team | hoch | 0 | — |
| [T-0023](tickets/T-0023.md) | Cockpit: Sprint-Kapitel statt einer Tabelle, und die Sprintnummer an der letzten Session (Brief pm/N-0043) | task | einmalig | dev | Team | hoch | 0 | — |
| [T-0024](tickets/T-0024.md) | Eine Zusicherung nagelt ein Datum an ein Verzeichnis, das von selbst wächst — rot seit 2026-08-17 22:22, gefunden am 2026-08-20 | problem | einmalig | test | Team | hoch | 0 | — |
| [T-0025](tickets/T-0025.md) | Wir messen, ob ein Lauf sauber endete — nicht, ob der nächste jemals anfing: 60,2 Stunden Pause bei 60 Minuten Takt, unbemerkt | problem | einmalig | cm | Team | hoch | 0 | — |
| [T-0028](tickets/T-0028.md) | Orga-Rework: Rollen-Detail und Besetzungs-Konfiguration im HMI (organisation.py, /api/organisation/*, organisation.html v2) | change-request | einmalig | dev | Team | hoch | 24 | — |
| [T-0008](tickets/T-0008.md) | Problem: In verschachtelten Repos (p10/p11/p12 in `projects`) läuft die Status-Übergangsprüfung seit jeher ins Leere — lautlos | problem | einmalig | cm | Team | mittel | 0 | — |
| [T-0015](tickets/T-0015.md) | SWR-123 räumt Git-Locks per unlink — auf dem Cowork-Mount ist das verboten, rename gelingt | problem | einmalig | cm | Team | mittel | 0 | — |
| [T-0016](tickets/T-0016.md) | Die Drei-Zustände-Regel des Widget-Vertrags steht in der Cockpit-Ansicht dreimal inline | problem | einmalig | cm | Team | mittel | 0 | — |
| [T-0020](tickets/T-0020.md) | Die Matrix schrumpft still: kein Vergleich mit dem Bestand beim Schreiben | problem | einmalig | cm | Team | mittel | 0 | T-0019 |
| [T-0026](tickets/T-0026.md) | Eine von sieben Pausen im Sprintregister ist NEGATIV — die Zeitstempel stammen aus der Uhr des jeweils schreibenden Laufs | problem | einmalig | cm | Team | mittel | 0 | — |
