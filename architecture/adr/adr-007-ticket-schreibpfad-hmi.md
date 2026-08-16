# ADR-007: Zweiter Schreibpfad auf Tickets (HMI-Editor)

*2026-08-16, ARCH. Status: vorgeschlagen (G4-DR `p10/T-0007`). Kontext: P10 „Aufgaben bearbeiten im HMI" (STK-020, SWR-077–081) nach G1a/D001. Innerhalb von ADR-001/002/003/006.*

## Kontext

Tickets werden bis heute an genau einer Stelle geschrieben: der Skript-Route (`platform/scripts/board.py`, aufgerufen von Sessions, Ticks und `abschluss.cmd`). Mission Control liest sie nur. Der Auftraggeber will offene Aufgaben direkt im HMI ändern (pm/N-0014) und frei labeln (pm/N-0013) — das ist ein **zweiter Schreibpfad auf dieselben Dateien**, und zwar einer, der parallel zur alle 30 Minuten laufenden Routine-Session arbeitet.

Zwei Dinge daran sind die eigentliche Entscheidung, nicht das Formular: **wo die Regeln leben** und **was passiert, wenn beide Pfade gleichzeitig schreiben**.

## Entscheidung

1. **Die Regeln bleiben in `board.py`; das Backend ist nur Fassade.** Validierung, Status-Übergänge, Pflichtfelder, Label-Prüfung und die BOARD.md-Regeneration liegen in `board.aktualisiere()` — derselben Datei, die auch die Skript-Route benutzt. `backend/tickets.py` löst das Projekt auf, übersetzt Fehler in HTTP-Codes, committet und nimmt bei einem gescheiterten Commit zurück. **Verworfen:** eine eigene Prüfschicht im Server. Sie wäre die zweite Kopie derselben Logik — genau das Risiko R2 des Sprint-0-Plans und die Lesson vom 16.08. (jede Kopie einer Auflösung ist ein künftiger Befund).
2. **Konflikterkennung über einen Inhalts-Fingerabdruck, nicht über Sperren.** Das Formular lädt mit `fingerprint = sha256(dateiinhalt)[:16]` und schickt ihn beim Speichern zurück. Weicht er vom Stand auf der Platte ab, wird **nicht** geschrieben, sondern in Klartext-Deutsch gemeldet, dass die Datei inzwischen geändert wurde, und das Neuladen angeboten. **Verworfen:** Dateisperren (auf einem Mount ohne Löschrecht — siehe R7 im Runbook — wäre eine liegengebliebene Sperre schlimmer als der Konflikt) und Letzter-gewinnt (stilles Überschreiben ist genau das, was Abnahmekriterium 4 ausschließt).
3. **Ein Commit je Änderung, Identität „Mensch via HMI".** ADR-003-Muster: schreiben, nur die eigenen Ziele adden (Ticketdatei + BOARD.md), sofort committen. Scheitert `git add`/`commit`, werden **beide** Dateien auf den Stand davor zurückgeschrieben — ein halb geschriebener Zustand wäre schlimmer als eine abgelehnte Änderung, weil ihn niemand bemerkt.
4. **Schutz über die vorhandene PIN-Prüfung.** Der Schreib-Endpunkt ist ein POST und läuft damit durch `schreibschutz_pruefen` (ADR-006): localhost frei, remote nur mit `MC_PIN`. Der Lese-Endpunkt für den Formularzustand bleibt PIN-frei wie die übrige Leseseite. Kein neues Rechtemodell.
5. **Änderbar ist eine feste Feldmenge**, nicht das ganze Frontmatter: `titel, typ, prio, rolle, sprint, status, takt, labels, reviewer, frist`. Draußen bleiben `id`, `prozess`, `erstellt`, `repo` und `blocked_by` — Identität und Abhängigkeitsgraph gehören der Skript-/Session-Route; für sie einen zweiten Weg zu öffnen hieße, Dinge doppelt zu vergeben, die genau einmal vergeben werden dürfen. **Anlegen und Löschen von Tickets bleiben ganz draußen** (Projektauftrag, Nummernvergabe).
6. **Erledigte Tickets sind Archiv.** Bei `done`/`rejected` ist ausschließlich die im Playbook erlaubte Wiedereröffnung möglich, und dabei nichts nebenbei.
7. **Historie im Ticket, zusätzlich zu Git.** Jede Änderung hängt eine Zeile `**Bearbeitet (Zeitpunkt, Herkunft):** geänderte Felder` an den Fließtext. Git bleibt die Wahrheit; der Vermerk ist das, was man am Handy im Ticket sieht, ohne ein Terminal zu haben.
8. **BOARD.md-Format bleibt unverändert.** Labels erscheinen im HMI (Karte, Detail, Filter), **nicht** als neue Spalte im generierten `BOARD.md`. Grund: Eine Formatänderung am Board hat am 16.08. bereits sämtliche `board-check`-Workflows rot gemacht (pm/T-0013, pm/T-0021); solche Änderungen werden gebündelt und mit der Push-Reihenfolge zusammen ausgerollt, nicht nebenbei in einem Sprint.

## Konsequenzen

`board.py` bekommt `fingerprint`, `zeitpunkt`, `aktualisiere` und die Label-Validierung — und wird damit endgültig zur einzigen Stelle, an der ein Ticket geschrieben wird (auch `inbox.entscheidungszeitpunkt` delegiert jetzt an `board.zeitpunkt`, statt das Format ein zweites Mal zu kennen). Neu: `backend/tickets.py`, `GET /api/ticket/editor`, `POST /api/ticket`, Editor-Ansicht und Label-Filter in `app.js`. Das Architekturbild bekommt die Komponente `tickets` mit einer Schreibkante auf die Repos (Drift-Gate).

**Bewusst offen:** Der Fingerabdruck schützt gegen *unbemerktes* Überschreiben, nicht gegen einen Wettlauf im Millisekundenbereich zwischen Prüfung und Schreiben. Für einen Einzelnutzer im Heimnetz mit einer Session alle 30 Minuten ist das die angemessene Tiefe; sollte je mehr als ein Mensch gleichzeitig schreiben, ist das der Punkt, an dem nachgeschärft werden muss.
