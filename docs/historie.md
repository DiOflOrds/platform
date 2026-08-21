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
| 2026-08-21 | **Sprint 35** — **SWR-212** (ein gescheiterter Gateway-Lauf nennt Provider, Versuchskette und Modell; alle 11 `fehler`-Einträge der Run-Registries trugen `provider: ""`) und **SWR-213** (Post im Lauf = Erstbriefe **und** Beiträge; 52 % aller Post sind Beiträge, die Kennzahl sah 0 %). ⚠⚠ **Der Fund des Laufs war der MESSPUNKT:** der Ollama-Takt läuft auf dem Rechner des Auftraggebers — **87 Läufe, 138 Abbrüche, 0 Erfolge** —, und alle 138 Abbrüche gehen auf **zwei Preflight-Befunde zurück, die Sprint 34 selbst erzeugt hat**. Drei Sprints lang wurde die Erreichbarkeit einer Maschine diskutiert, auf der der Takt gar nicht läuft. Blocker geräumt. ⚠ Danach **17 Befunde des unabhängigen Gegenlesens** an eben dieser Arbeit — vierter Sprint in Folge, und wieder keinen davon der Autor. | SWR-212/213, T-0060, T-0065, T-0066, T-0067 |
| 2026-08-21 | **Sprint 34** — **SWR-207** (Organisationswurzel kommt vom Aufrufer; sieben seit Sprint 32 rote Zusicherungen grün, ohne Anpassung ihrer Erwartung), **SWR-208** (Datenklasse platziert statt beschriftet; `p13` bekommt seine 10 Core-Instanzen), **SWR-209** (91 in Sprint 32 gelöschte Lehren wiederhergestellt), **SWR-210** (2×2-Raster des Post-Widgets), **SWR-211** (eine erteilte Abnahme hat ihren Tag; `p12-v1.0` nachgetragen). ⚠ Danach **sieben Befunde des unabhängigen Gegenlesens** an eben dieser Arbeit behoben. | SWR-207–211, T-0056, T-0061–T-0065 |
| 2026-08-07 | P0 „Genesis" abgeschlossen und abgenommen; Baseline genesis-v1.0; 112 grüne Tests | D024, p0-Abschlussbericht |
| 2026-08-15 | Genesis 2.0: Organisation mit PM-Team + Profilen (F14–F17) | p0/D027 |
| 2026-08-17 | Sprintzähler/Register (SWR-106), Discovery projects/ | pm/T-0041, P9 |
| 2026-08-20 | Sprint 24–27: Rückbau-Wächter-Paar, git-Lock-Anatomie (SWR-163), Preflight-Altbestand (SWR-166), Modell aus Register (SWR-169), Besetzungsprüfung vor Tick (SWR-171/172), Anzeigename (SWR-175) | PROJEKTSTATUS, T-0021–T-0035 |
| 2026-08-20/21 | Orga-Rework 1+2: Rollenmodell v2, Projektmodell, Core Team implizit, ein Besetzungs-Resolver; Organisations-HMI (Organigramm/Live/Planung + Konfiguration) | pm/T-0070–T-0073, T-0028/T-0037 |
| 2026-08-21 | Setup-Nachzieh + neue Sichten Work Products/Kommunikation (SWR-181–184) | T-0038–T-0042 |
| 2026-08-21 | **Sprint 28:** Nachverbuchung des kompletten Projektmodell-Rework (125 Dateien, 16 Repos — in KEINEM Repo committet, obwohl der Befund zweimal „nach abschluss.cmd" meldete); Testdurchlauf über **alle 85** Module statt einer Auswahl fand **drei rote** (SWR-189 Instanzschlüssel, SWR-171-Zusicherung, `projekt_setup` ohne `sichere_ausgabe`); SWR-190 Goldset-Abdeckung als stehende Prüfung; p11-Frontend-Rückbau ausgeführt | Sprint-28-Commits, T-0045, SWR-189/190 |
| 2026-08-21 | **Sprint 29:** `SWR-191` Commit-Prüfung misst den **Baum** statt den Index (beide falschen Befunde aus Sprint 28 weg, `pm` 1→0); `SWR-192` Kommentare an Aufgaben im Ticket-Rumpf, **auch an erledigten** (vierte Berührung von T-0030 **gebaut**); `SWR-193` repo-übergreifende Sperre ausdrückbar — `promt-team/T-0003`/`T-0012` stehen nach **vier** Terminierungen erstmals ehrlich auf `blocked`; `SWR-194` Lehre ohne Vertreter als **Sperrklinke** (29 von 34 benannt, nicht rot); `SWR-195` keine neue Dublette im Entscheidungslog | T-0030/T-0034/T-0036/T-0045/T-0046, SWR-191–195 |
| 2026-08-21 | **Sprint 30:** `SWR-196` Besetzung als **Kandidatenfilter** statt Veto nach der Auswahl — der Schnelltakt lief nach `SWR-191` erstmals bis zur Auswahl durch und endete trotzdem **2 von 2** ohne Ergebnis (**0 von 8** offenen Tickets ollama-fähig); die Absage nennt jetzt den **Bestand** statt ein Exemplar. `SWR-197` Sperrklinke am **Nummernraum**: von 1023 praefixlosen Entscheidungs-Zitaten sind **214 (21 %)** echt mehrdeutig, und **alle** nennen eine von **14** IDs (`D000`–`D013`) — gebaut an der Vergabe, nicht am Korpus. ⚠ Befund über die eigene Prüfung aus Sprint 29: `SWR-194` zählt eine **Schreibweise** (34 von 111) und übersieht **76** Lehren — drei Lehren dieses Laufs wären unbemerkt durchgerutscht (`T-0050`) | T-0047/T-0048, T-0049/T-0050, SWR-196/197 |
| 2026-08-21 | **Sprint 32:** `SWR-201` Plannachlauf des laufenden Sprints ist ein **benannter Nicht-Befund** — am Betrieb gemessen: 60 Läufe, 7 Sprints, in **jedem** ein Drift-Fenster von 15–45 Min (24 % der Zeit); die Richtungszählung **38 : 0** hat die Bauform entschieden (die garantierte Richtung ist die harmlose). `SWR-202` „offenes Ticket" hat **eine** Zählweise über alle **drei** Erzeuger, und `SWR-113` bekommt nach **zwanzig Sprints** endlich einen Vertreter. ⚠⚠ **Das unabhängige Review fand VIER Befunde der Schwere *hoch* an `SWR-201`** — u. a. eine Ausnahme, deren Bedingung während der ganzen Arbeitszeit wahr war, ein Schlupfloch über `rejected`, und eine Verdrahtung, deren Entfernung **alle sechs** Zusicherungen grün ließ. Alle behoben und am Bestand gegengeprüft. ⚠ **7 Briefe kamen WÄHREND des Laufs** (06:32–07:03) — beantwortet, qualifiziert, 2 als Klasse-A-DR. | T-0052/T-0053, SWR-201/202, T-0054–T-0057 |
| 2026-08-21 | **Sprint 33: SWR-204/205/206.** Eine Sperre muss auf ein OFFENES Ticket zeigen — gemessen zeigte **kein einziger** `blocked_by` des Hauses auf eins; **vierter Ticket-Zustand VERWORFEN** (Preis 9 Dateien/153 Literale gegen einen Anlass in 386 Tickets), Prüfung statt Vokabular. Endzustand auf EINEN Namen (**5** gefunden, nicht 3). EINE Brief-Discovery + EINE Auslegung von „offen". ⚠⚠ **Das unabhängige Gegenlesen fand 3 ernste eigene Fehler in fertig gemeldeter Arbeit** — darunter einen **Zeitzonenfehler**, der `SWR-206` mit der falschen Aussage gefüllt hatte (UTC gegen Wanduhr, 2 h Versatz). | T-0054/57/58, SWR-204–206, L-2026-08-21cw/cx/cy/cz |

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
| 18 | Eine Prüfung nach der Auswahl ist kein Filter, sondern ein Veto gegen genau einen Kandidaten — die Gegenprobe braucht einen **hinteren** Treffer | SWR-196 | Rollenkarte DEV, `L-2026-08-21cj` |
| 19 | Eine **wahre, aber zu enge** Meldung über einen strukturellen Zustand ist der Zwilling des falschen Befunds: sie erneuert bei jedem Lauf die Hoffnung auf eine andere Antwort | SWR-196 | Rollenkarte DEV, `L-2026-08-21cl` |
| 20 | Der Mangel war ein **Präfix des Nummernraums**, keine Eigenschaft des Korpus — gesichert wird die endliche Ursache, nie der Korpus, der über sie berichtet | SWR-197 | Rollenkarte CM, `L-2026-08-21ck` |
| 21 | Eine Sperrklinke, die man mit einem anders gesetzten Doppelpunkt umgeht, ist keine — `SWR-194` liest eine Schreibweise (34) und übersieht 76 Lehren | T-0050 | Ticket `platform/T-0050`, Rollenkarte COACH |

## Offene Fäden

- pm/T-0071 Schritt 3 bleibt **blocked** (`blocked_by: [T-0077]`). ⚠ **Sprint 30 hat den Grund verschoben, nicht behoben:** der Preflight-Abbruch ist weg (`SWR-191`, gemessen 04:15), aber **0 von 8** offenen Tickets tragen eine ollama-besetzte Rolle. Der Takt kann jetzt laufen und hat nichts zu tun — `SWR-196` sagt das im Log.
- ⚠⚠ **`platform/T-0050` (neu):** `SWR-194` liest eine **Schreibweise** statt einer Konvention — 34 von 111 Lehren gezählt, **76 übersehen**. Drei Lehren dieses Laufs wären unbemerkt durchgerutscht.
- ✅ **`platform/T-0047` geschlossen (Sprint 30, `SWR-197`):** die ehrliche Untermenge ist gemessen — **214 von 1023 (21 %)**, und alle nennen eine von **14** IDs. Gebaut an der Vergabe. Offen daraus: `platform/T-0049` (zweiter Schreibweg ins Entscheidungslog, **dritte Berührung**, Sprint 31).
- T-0039/T-0040 Bau nach Review der SWR-181–184; T-0041 Huckepack; T-0042 Review.

## Sprint 31 (2026-08-21) — der Fehler liegt zwischen den Prüfungen, dreimal am selben Tag

**Geschlossen:** `T-0051` (SWR-198), `T-0050` (SWR-199), `T-0049` (SWR-200 — vierte
Berührung, entschieden). **Neu:** `T-0052`, `T-0053`. **1429 Tests / 95 Dateien,
Matrix 200/0.**

**Lehre 22 — ein Stellvertreter wird zum Loch, sobald die Sache einen eigenen Namen
bekommt.** Für ein gesperrtes Ticket gab es **keinen** zulässigen Terminwert: alter
Sprint → Befund, leer → Befund, Zukunft → still, aber eine Zusage über fremdes Handeln.
Die Ausnahme existierte längst — an einem **Typ** (`decision-request`) statt an einem
**Zustand**, weil `blocked` erst seit `SWR-193` existiert, einen Sprint alt. Gebaut ist
`board.gesperrt` als **eine** Begründung, von beiden Prüfungen aufgerufen; gebunden an
den `blocked_by`-**Verweis** und nicht an das Wort. Am echten Bestand gemessen:
`unterminierte_tickets` **3 → 0**. `L-2026-08-21cm`.

**Lehre 23 — eine Zusicherung, die ein Verhältnis meint und eine Ungleichung schreibt,
bleibt grün, während ihr Gegenstand verschwindet.** Die „ehrliche Untermenge" von
`SWR-194` war eine **Schreibweise**: Vertreterquote 24 % innerhalb, 15 % außerhalb —
nahezu gleich. Und zwischen „Muster erweitern" (111 von 112) und „Filter weglassen" (112)
liegen **null** Lehren. Von zwei gleichwertigen Bauformen ist die mit einem Begriff
weniger die richtige; der Ausstieg heißt jetzt `**Beobachtung:**` und ist eine Handlung
statt eines Nebeneffekts der Zeichensetzung. `L-2026-08-21cn`.

**Lehre 24 — die Frage hat ihre eigene Antwort überlebt.** Der „zweite Schreibweg" ins
Entscheidungslog ist **keine Funktion**, sondern die **Hand** — und mit 103 von 158 Zeilen
(65 %) die **Mehrheit**. Der Schaden war seit `SWR-195`/`SWR-197` bereits gefangen, von
Tickets, die **nach** der Frage entstanden. Eine Weiterreichung wurde dreimal auf ihren
**Grund** geprüft und nie auf ihre **Gültigkeit**. `L-2026-08-21co`.

**Lehre 25 — eine Zerlegefunktion, die an ihrem eigenen Ergebnis scheitert, ist nicht
idempotent.** `board.parse_liste` brach an einer echten Liste; gefunden hat es eine
Zusicherung aus dem **Vorsprint**, die ihre Vorrichtung so baut, wie ein Mensch die Angabe
denkt. Dieselbe Datei hat sich selbst umgedreht, wie ihr Docstring es verlangte —
**eine Zusicherung, die einen Mangel BENENNT, meldet seine Behebung von allein.**
`L-2026-08-21cp`.

⚠ **Am laufenden Betrieb gemessen und nicht im Test:** der Schnelltakt war um 06:15
zweimal `STARTKLAR` und ab 06:30 dreimal blockiert — durch die Statusdrift, die **dieser
Sprint selbst** erzeugt hat. Der Plan wird laut `pm/D006` am Abschluss geschrieben, also
ist der Bestand während **jedes** Sprints widersprüchlich. `T-0052`.
