# ADR-006: LAN-Betrieb mit PIN-Schutz + Briefkasten-Ablage (P4, G2)

*2026-08-15, ARCH. Status: vorgeschlagen (G2-DR p4/T-0006). Kontext: P4 „Mission Control 3.1" (STK-016, SWR-048–052) öffnet den Server ins Heim-LAN und braucht einen Schreibschutz sowie ein Ablageformat für den Briefkasten-Chat — innerhalb von ADR-001/002/003.*

## Entscheidung

1. **Schreibschutz: lokal frei, remote nur mit PIN.** Der Server läuft im LAN-Modus über den vorhandenen `--host 0.0.0.0` (Runbook-Prozedur inkl. Windows-Firewall-Freigabe; Start-Skript `mission-control-lan.cmd`). Schreib-Endpunkte (Entscheidungen, Briefkasten) prüfen die Client-Adresse: **localhost braucht keine PIN** (abwärtskompatibel), alle anderen Clients müssen die PIN aus der lokalen Umgebungsvariable `MC_PIN` im Header `X-MC-PIN` mitsenden (Vergleich per `hmac.compare_digest`). Ohne gesetzte `MC_PIN` bleiben Remote-Schreibzugriffe komplett gesperrt (sicherer Default). Lese-Endpunkte sind PIN-frei. **Grenze (dokumentiert):** kein TLS, PIN ist Heimnetz-Schutz, kein Passwortersatz — deshalb harte Leitplanke „kein Port-Forwarding/Internet-Expose" (Runbook).
2. **Briefkasten-Ablage: Dateien im Projekt-Repo, Commit sofort.** Nachrichten liegen als `<projekt>/management/briefkasten/N-XXXX.md` (laufende Nummer) mit Frontmatter (`von`, `zeit`, `status: offen|beantwortet`) und Fließtext; die Team-Antwort wird als Abschnitt **„## Antwort (Team, Datum)"** in derselben Datei ergänzt und setzt `status: beantwortet`. Schreiben = Datei + sofortiger Git-Commit (ADR-003-Muster, Identität „Mensch via Briefkasten"). Die Cowork-Session beantwortet offene Briefe zu Sitzungsbeginn; `preflight` weist auf offene Briefe hin.
3. **Kein neuer Zustand:** Konversation = Dateien im Repo (Quelle der Wahrheit), API nur Lese-/Schreibfassade — verteilungsfähig wie alles andere.

## Verworfene Alternativen

Basic-Auth/Session-Cookies (mehr Fläche, kein Gewinn im Heimnetz), TLS mit Self-Signed-Zertifikat (Zertifikatswarnungs-Hölle am Handy; bei Internet-Expose ohnehin verboten), Briefkasten in einer Datenbank (bricht Git-als-Quelle), Live-API-Chat (kostenpflichtig — per Intake zurückgestellt, Folge-CR).

## Konsequenzen

server.py bekommt eine kleine PIN-Prüfung im Schreibpfad und den Briefkasten-Endpunkt; app.js einen Chat-Tab + PIN-Feld; Runbook ein Kapitel „LAN-Betrieb" (Firewall, PIN setzen per `setx MC_PIN`, Grenzen). Die Session-Routine erweitert sich um „Briefkasten zuerst".

## Delta 2026-08-15 (P7, SWR-053): PIN-Lesegate für Team-Inhalte

Das PIN-Modell galt bisher nur für Schreibzugriffe. Mit den Team-Ansichten (P7) liefert die API erstmals **sensible Inhalte** aus (Mail-Digests, Datenklasse `sensibel` nach Playbook Kap. 16). Darum wird die bestehende Prüfung `schreibschutz_pruefen` unverändert auch auf die `/api/team*`-**Lese**-Endpunkte angewendet: localhost bleibt frei, remote nur mit `MC_PIN`, ohne gesetzte PIN sind Remote-Zugriffe auf Team-Inhalte gesperrt (sicherer Default). Kein neues Mechanikstück, dieselbe Funktion an einer zweiten Stelle — bewusst kein generisches Rechtemodell (YAGNI, Heimnetz-Kontext). Frontend sendet die PIN daher bei allen Anfragen mit, nicht nur bei POST. Guardrail 2 (kein GitHub-Remote für sensible Repos) bleibt unberührt — Mission Control liest lokal.
