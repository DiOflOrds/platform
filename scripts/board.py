#!/usr/bin/env python3
"""board.py — Git-natives Ticket-Board (v1, Sprint 1, T-0007).

Tickets liegen als Markdown-Dateien mit YAML-Frontmatter in <projekt>/tickets/.
Dieses Skript validiert die Tickets und generiert BOARD.md deterministisch.
Teil der Skript-Route (kein LLM nötig). Läuft bei jedem Tick und in CI.

Nutzung:
    python board.py <pfad-zum-projekt-repo> [--check] [--no-git]

    --check   nur validieren, BOARD.md nicht schreiben (CI-Gate)
    --no-git  Status-Übergangs-Prüfung gegen Git HEAD überspringen

Exit-Codes: 0 = ok, 1 = Validierung fehlgeschlagen, 2 = Aufruf-/IO-Fehler.

Importierbar für den Orchestrator:
    from board import lade_tickets, validiere_alle, generiere_board
"""
import hashlib
import os
import re
import subprocess
import sys
from datetime import date, datetime, time, timedelta

FELDER = ["id", "titel", "typ", "prozess", "rolle", "sprint", "status", "prio", "erstellt"]
STATUS = ["open", "in_analysis", "in_progress", "in_review", "blocked", "done", "rejected"]
TYPEN = ["task", "problem", "change-request", "decision-request", "clarification",
         "finding", "feedback", "skriptifizierung"]
PRIOS = ["kritisch", "hoch", "mittel", "niedrig"]
PRIO_RANG = {p: i for i, p in enumerate(PRIOS)}
# SWR-074 (pm/N-0012): Wiederkehrende Aufgaben sind dauerhaft `open` — der Takt sagt,
# dass das Absicht ist und nicht Liegenbleiben. Feld optional; leer = einmalige Aufgabe.
TAKTE = {"je-session": "je Session", "taeglich": "täglich", "woechentlich": "wöchentlich",
         "monatlich": "monatlich", "quartalsweise": "quartalsweise", "jaehrlich": "jährlich"}
# SWR-104 (pm/T-0032 Teil 2, Brief pm/N-0025): Uhrzeit-Takt. NUR `taeglich` und
# `woechentlich` dürfen eine Uhrzeit tragen — für `monatlich`/`quartalsweise`/`jaehrlich`
# gibt es keinen Wunsch und damit keine Regel, was „der Tag" wäre; sie stillschweigend
# zuzulassen hieße raten (B038). Die Trennlinie aus T-0032 Teil 1: der Uhrzeit-Takt ist
# KEIN Scheduler, sondern eine Fälligkeitsfrage, die die ohnehin laufende Session stellt.
TAKTE_MIT_UHRZEIT = ("taeglich", "woechentlich")
WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]  # Index = date.weekday()
UHRZEIT_MUSTER = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
ID_MUSTER = re.compile(r"^T-\d{4}$")
# SWR-116 (pm/T-0038 Teil a, B053, Brief pm/N-0030): WER handelt — Team oder Mensch.
#
# Bewusst ein **eigenes** Feld statt einer Umdeutung von `rolle`. `rolle` sagt die
# FACHROLLE (pl, cm, dev, qm …) und trägt in `board.validiere` bereits eine zweite,
# verhaltensändernde Bedeutung: Tickets mit `rolle: mensch` sind Gates und von der
# Status-Übergangsprüfung ausgenommen. Vorhandene Tickets auf diese Bedeutung
# umzustellen, würde ihnen still die Übergangsprüfung abschalten — ein Feld für zwei
# Zwecke, genau die Familie aus B033.
#
# Feld OPTIONAL, leer = `team`. Ein Pflichtfeld hätte 200+ Tickets in einem Zug ungültig
# gemacht und wäre damit dieselbe Formatänderung, die Teil b) (pm/T-0050) bewusst
# abgetrennt bekommen hat.
VERANTWORTLICH = ["team", "mensch"]
VERANTWORTLICH_DEFAULT = "team"
# SWR-116: Steht `mensch`, verlangt die Validierung einen Abschnitt, der die Handlung
# BENENNT. Ohne ihn wäre „ein Mensch muss ran" eine Behauptung ohne Beleg (B038) — und
# der Kanal aus pm/T-0052 würde eine Liste von Tickets zeigen, bei denen niemand sagen
# kann, was zu tun ist.
HANDLUNG_UEBERSCHRIFT = "## Handlung beim Menschen"
DATUM_MUSTER = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ZEITPUNKT_MUSTER = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]([01]\d|2[0-3]):([0-5]\d)$")
# SWR-079 (P10, pm/N-0013): frei gewählte Mehrfach-Labels. Bewusst konservativer
# Zeichensatz — Labels landen in einer Kommaliste im Frontmatter, in BOARD.md-Zellen
# und in Git-Commit-Nachrichten; Komma, eckige Klammer, Pipe und Zeilenumbruch
# würden genau dort das Format sprengen. Feld optional; ohne Feld bleibt alles wie bisher.
LABEL_MUSTER = re.compile(r"^[0-9A-Za-zÄÖÜäöüß][0-9A-Za-zÄÖÜäöüß _.+/-]{0,39}$")
LABEL_MAX = 12
# T-0051: Bestands-DRs vor Sprint 5 (Freitext-Optionen) — neue DRs brauchen `optionen`.
DR_BESTAND = {"T-0022", "T-0035", "T-0041"}

# Erlaubte Status-Übergänge (Playbook Kap. 5). Gleicher Status ist immer erlaubt.
UEBERGAENGE = {
    "open": ["in_analysis", "in_progress", "blocked", "rejected"],
    "in_analysis": ["open", "in_progress", "blocked", "rejected"],
    "in_progress": ["open", "in_review", "blocked"],
    "in_review": ["in_progress", "done", "rejected"],
    "blocked": ["open", "in_analysis", "in_progress"],
    "done": ["in_progress"],  # Wiedereröffnung (KPI: Wiederöffnungsquote)
    "rejected": ["open"],
}

# Sammel-Repo für neue Projekte ab P10 (pm/D003) — Projekte sind dort Ordner statt Repos.
SAMMEL_REPO = "projects"

# SWR-077 (P10): Was ein Mensch über den zweiten Schreibpfad (HMI) ändern darf.
# `id`, `prozess`, `erstellt`, `repo` und `blocked_by` bleiben draußen: Identität und
# Abhängigkeitsgraph gehören der Skript-/Session-Route, sonst entsteht ein zweiter
# Weg für Dinge, die genau einen haben müssen (ADR-007).
EDITIERBARE_FELDER = ("titel", "typ", "prio", "rolle", "sprint", "status",
                      "takt", "labels", "reviewer", "frist", "zuletzt_erledigt",
                      "geplant_sprint", "verantwortlich")  # SWR-116
GESCHLOSSEN = ("done", "rejected")  # SWR-077: Archiv — nur Wiedereröffnung


def zeitpunkt(jetzt=None):
    """SWR-084: Zeitstempel `JJJJ-MM-TT HH:MM` — EINE Quelle für alle Vermerke.

    Entscheidungen (inbox.py) und Ticket-Änderungen (SWR-081) datieren identisch;
    eine zweite Implementierung wäre nach der Lesson vom 16.08. (B025) ein
    künftiger Befund und keine Bequemlichkeit.
    """
    return (jetzt or datetime.now()).strftime("%Y-%m-%d %H:%M")


def fingerprint(text):
    """SWR-080 (P10): Inhalts-Fingerabdruck einer Ticketdatei.

    Zeilenenden werden vorher vereinheitlicht — sonst meldete ein Windows-Editor
    einen Konflikt, wo inhaltlich nichts passiert ist. Gekürzt auf 16 Zeichen:
    Kollisionsschutz genügt hier, der Wert läuft durch URLs und Formulare.
    """
    roh = str(text or "").replace("\r\n", "\n")
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()[:16]


class KonfliktFehler(ValueError):
    """SWR-080: Die Datei auf der Platte ist nicht mehr die, aus der das Formular
    geladen wurde (parallele Routine-Session). Eigener Typ, damit der Aufrufer
    409 statt 400 melden kann — es ist kein Eingabefehler des Menschen."""


class KeineAenderung(ValueError):
    """SWR-144: Die Felder tragen die gewünschten Werte bereits.

    **Ein eigener Typ und kein Textvergleich auf die Meldung.** Bis Sprint 16 war
    dieser Fall von einem abgewiesenen Schreibvorgang nur an seiner Prosa zu
    unterscheiden — `tickets.speichere` übersetzte jeden `ValueError` in HTTP 400, und
    ein bereits terminiertes Ticket antwortete damit in derselben Gestalt wie ein
    Fehlschlag. Ein Aufrufer, der das trennen wollte, hätte auf den Wortlaut prüfen
    müssen; dass eine Textsuche eine Warnung nicht von ihrem Gegenstand unterscheiden
    kann, hat `L-2026-08-17ak` in Sprint 16 gemessen.

    ⚠ Bleibt `ValueError`: jeder bestehende Aufrufer, der `ValueError` fängt, verhält
    sich unverändert. Die Unterscheidung ist ein **Angebot** an den Aufrufer, der sie
    braucht, und keine Umschreibung des Vertrags für die, die sie nicht brauchen.
    """


def projekt_pfade(wurzel):
    """SWR-025/ADR-004 + SWR-070: alle Projekte unter `wurzel` als (name, pfad).

    Ein Projekt ist ein Ordner mit `tickets/` — entweder direkt im Wurzelordner
    (Bestandsrepos p0–p9, pm, team-mail …) oder im Sammel-Repo `projects/`
    (pm/D003, ab P10). p9/T-0007: dieselbe Auflösung nutzen preflight (board-check
    je Projekt) und trace_matrix (SWR-Quellen), damit verschachtelte Projekte nicht
    still durch die Gates fallen.
    """
    gefunden, namen = [], set()
    try:
        eintraege = sorted(os.listdir(wurzel))
    except OSError:
        return gefunden
    for d in eintraege:
        pfad = os.path.join(wurzel, d)
        if os.path.isdir(os.path.join(pfad, "tickets")):
            gefunden.append((d, pfad))
            namen.add(d)
    sammel = os.path.join(wurzel, SAMMEL_REPO)
    if os.path.isdir(sammel):
        for d in sorted(os.listdir(sammel)):
            pfad = os.path.join(sammel, d)
            if os.path.isdir(os.path.join(pfad, "tickets")) and d not in namen:
                gefunden.append((d, pfad))
                namen.add(d)
    return gefunden


def parse_frontmatter(text):
    """Frontmatter eines Tickets parsen. Gibt (dict, fehler) zurück."""
    text = text.replace("\r\n", "\n")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return None, "kein Frontmatter"
    fm = {}
    for zeile in m.group(1).splitlines():
        if ":" in zeile and not zeile.startswith(("#", " ", "\t")):
            k, v = zeile.split(":", 1)
            fm[k.strip()] = v.strip().strip('"')
    fm["_body"] = m.group(2).strip()
    return fm, None


def parse_liste(wert):
    """'[A, B]' -> ['A', 'B'] (leere Liste bei '', '[]')."""
    return [r.strip() for r in (wert or "").strip("[]").split(",") if r.strip()]


def parse_optionstoken(wert):
    """T-0039: gewählte Option(en) in Token zerlegen ('A2, B1, C1' / 'A1 + B1' -> Token)."""
    return [x for x in re.split(r"[\s,+/]+", (wert or "").strip()) if x]


def lade_tickets(repo):
    """Alle Tickets aus <repo>/tickets/ laden. Gibt (tickets, probleme) zurück."""
    tdir = os.path.join(repo, "tickets")
    if not os.path.isdir(tdir):
        return [], [f"Ticket-Verzeichnis fehlt: {tdir}"]
    tickets, probleme = [], []
    for f in sorted(x for x in os.listdir(tdir) if x.endswith(".md")):
        pfad = os.path.join(tdir, f)
        try:
            text = open(pfad, encoding="utf-8").read()
        except OSError as e:
            probleme.append(f"{f}: nicht lesbar ({e})")
            continue
        t, err = parse_frontmatter(text)
        if err:
            probleme.append(f"{f}: {err}")
            continue
        t["_datei"] = f
        tickets.append(t)
    return tickets, probleme


def ist_datum(wert):
    """SWR-091: Ist `wert` ein echtes Kalenderdatum JJJJ-MM-TT?

    `DATUM_MUSTER` prüft nur die Form — „2026-13-01" kam bis hierher durch. Für
    `erstellt` war das kosmetisch, für `frist` wäre es ein stiller Ausfall
    gewesen: `frist_ampel` fällt bei einem unmöglichen Datum auf „grau" zurück,
    das Ticket sähe also unterminiert statt falsch terminiert aus (B038 —
    „steht danach im Protokoll, dass geraten wurde?"). Deshalb eine Prüfung für
    beide Datumsfelder, nicht zwei.
    """
    if not DATUM_MUSTER.match(str(wert or "")):
        return False
    try:
        date.fromisoformat(wert)
    except ValueError:
        return False
    return True


def als_moment(wert):
    """SWR-104: Termin-Angabe -> Moment. Ein reines Datum endet am TAGESENDE.

    Bis SWR-104 war die Ampel eine reine Tagesregel. Ein Uhrzeit-Takt
    (`taeglich@14:00`) liefert aber einen Termin MIT Uhrzeit, und „heute 14:00"
    ist um 15:00 verstrichen, obwohl der Tag es nicht ist — eine Tagesregel
    hätte ihn als „gelb, heute fällig" ausgewiesen statt als überfällig. Genau
    dieses Zusammenfalten zweier Fakten war der Befund B057.

    Die Umstellung auf Momente lässt reine Datumsfristen unverändert: ein
    Termin „2026-08-19" ist am 19.08. den ganzen Tag nicht verstrichen und ab
    dem 20.08. rot — dasselbe, was `f < heute` gesagt hat. Deshalb Tagesende
    und nicht Tagesbeginn; ein Test vergleicht beide Fassungen Tag für Tag.
    """
    if isinstance(wert, datetime):
        return wert
    if isinstance(wert, date):
        return datetime.combine(wert, time.max)
    s = str(wert or "").strip()
    if ZEITPUNKT_MUSTER.match(s):
        try:
            return datetime.fromisoformat(s.replace("T", " "))
        except ValueError:
            return None
    return datetime.combine(date.fromisoformat(s), time.max) if ist_datum(s) else None


def _jetzt_moment(heute=None):
    """SWR-104: Bezugsmoment der Ampel.

    `heute` als `date` (der Bestandsaufruf) heißt „irgendwann an diesem Tag" —
    gerechnet wird dann mit dem TAGESENDE. Für Datumsfristen ist das die alte
    Rechnung; für einen Uhrzeit-Termin desselben Tages bedeutet es „im Zweifel
    verstrichen". Diese Richtung ist Absicht: dieselbe Vorsichtsregel wie bei
    `zuletzt_erledigt` und bei `session.stille` — im Zweifel fällig, nie frisch
    (B038).
    """
    if isinstance(heute, datetime):
        return heute
    if isinstance(heute, date):
        return datetime.combine(heute, time.max)
    if heute is None:
        return datetime.now()
    return als_moment(heute) or datetime.now()


def frist_ampel(frist, heute=None):
    """SWR-091 (pm/T-0030), erweitert um SWR-104: Termin -> Ampel.
    EINE Quelle für alle Ansichten.

    rot = überschritten, gelb = <= 2 Tage, gruen = später, grau = keine/ungültige
    Frist. Die Regel stand bis SWR-091 inline in `aggregation.cockpit` und galt
    nur für Decision-Requests; sie ein zweites Mal für Backlog-Tickets zu
    schreiben wäre genau die Falle aus B033 („Welche Regel wäre ich versucht,
    hier noch einmal zu schreiben — und wo steht sie schon?").

    SWR-104 schickt den aus einem Uhrzeit-Takt ABGELEITETEN Termin durch
    dieselbe Funktion — eine Ampelregel, zwei Quellen. Verglichen wird dafür
    auf Momentebene statt auf Tagesebene; die Aussage für reine Datumsfristen
    bleibt Tag für Tag dieselbe (siehe `als_moment`).
    """
    m = als_moment(frist)
    if m is None:
        return "grau"
    jetzt = _jetzt_moment(heute)
    if m < jetzt:
        return "rot"
    return "gelb" if (m.date() - jetzt.date()).days <= 2 else "gruen"


def ist_ueberfaellig(t, heute=None):
    """SWR-091: Ist dieses Ticket über seine Frist gelaufen?

    Nur offene Tickets können überfällig sein — `done`/`rejected` tragen ihre
    Frist als Historie weiter, nicht als Vorwurf. Ohne Frist nie überfällig:
    ein Ticket ohne Termin ist nach wie vor erlaubt (Fristen sind optional),
    es ist dann nur nicht terminiert — und genau das ist die ehrliche Aussage.
    """
    if t.get("status") in GESCHLOSSEN:
        return False
    return frist_ampel(t.get("frist"), heute) == "rot"


def parse_sprint_nr(wert):
    """SWR-106: `geplant_sprint` -> int, sonst None.

    Erlaubt sind eine reine Zahl (`42`) und die Schreibweise `Sprint 42`, weil die
    zweite in Plandatei und Agenda ohnehin steht und ein Feld, das zwei Schreibweisen
    derselben Sache unterschiedlich behandelt, ein künftiger Befund ist.
    """
    s = str(wert or "").strip()
    if not s:
        return None
    m = re.match(r"^(?:[Ss]print\s*)?(\d{1,6})$", s)
    return int(m.group(1)) if m else None


def sprint_widerspruch(t, jetzt_nr, takt_min=60, heute=None):
    """SWR-106: Sagt der geplante Sprint etwas anderes als die Frist? -> Text oder None.

    Der Auftraggeber hat entschieden, **beide** Felder zu führen (2026-08-17):
    `frist` ist die Zusage nach außen bzw. an den Menschen, `geplant_sprint` sagt,
    wann das Team es anfasst. Das sind zwei Fakten und keine zwei Quellen für
    einen — solange sie sich nicht widersprechen.

    **Genau das ist die bekannte Schwachstelle dieser Wahl (B033), und deshalb wird
    sie geprüft statt vorausgesetzt.** Liegt der geplante Sprint nach der Frist,
    ist eine der beiden Angaben falsch, und niemand würde es merken: die Frist
    bleibt grün, bis sie reißt, und der Sprint bleibt plausibel, weil ihn keiner
    gegen die Frist hält.

    Die Zeitschätzung ist eine Schätzung (Takt × Abstand) und wird auch so genannt.
    Gemeldet wird nur, was **auch bei ununterbrochenem Takt** nicht mehr passt —
    ein Widerspruch, den schon der günstigste Fall nicht auflöst.
    """
    if t.get("status") in GESCHLOSSEN:
        return None
    ziel = parse_sprint_nr(t.get("geplant_sprint"))
    frist = t.get("frist")
    if ziel is None or not frist or not ist_datum(str(frist).strip()[:10]):
        return None
    heute = heute or date.today()
    tage = max(0, ziel - jetzt_nr) * takt_min / (60 * 24)
    erreicht = heute + timedelta(days=tage)
    endet = date.fromisoformat(str(frist).strip()[:10])
    if erreicht > endet:
        return (f"geplant für Sprint {ziel} (frühestens {erreicht.isoformat()}), "
                f"Frist ist aber {endet.isoformat()}")
    return None


def parse_takt(wert):
    """SWR-104: Takt zerlegen -> (basis, wochentag|None, uhrzeit|None), sonst None.

    `je-session` -> ("je-session", None, None) — Bestand unverändert.
    `taeglich@14:00` -> ("taeglich", None, "14:00")
    `woechentlich@Mo-14:00` -> ("woechentlich", 0, "14:00")

    Eine Uhrzeit ist nur für `taeglich` und `woechentlich` erlaubt. Für
    `monatlich@…` gäbe es keine Regel, welcher Tag gemeint ist — sie zu erfinden
    wäre Raten, sie stillschweigend zu schlucken wäre ein Feld, das aussieht als
    täte es etwas (B038). Also: Fehler bei der Validierung.
    """
    s = str(wert or "").strip()
    if not s:
        return None
    if "@" not in s:
        return (s, None, None) if s in TAKTE else None
    basis, _, rest = s.partition("@")
    if basis not in TAKTE_MIT_UHRZEIT:
        return None
    if basis == "taeglich":
        return (basis, None, rest) if UHRZEIT_MUSTER.match(rest) else None
    tag, _, uhr = rest.partition("-")
    if tag not in WOCHENTAGE or not UHRZEIT_MUSTER.match(uhr):
        return None
    return (basis, WOCHENTAGE.index(tag), uhr)


def takt_klartext(wert):
    """SWR-074/104: Takt in Klartext für Board und Ansichten ("einmalig" ohne Takt).

    Kein Formatwechsel am BOARD.md — dieselbe Spalte, nur trägt sie bei einem
    Uhrzeit-Takt auch die Uhrzeit. Bestandstickets ergeben Zeichen für Zeichen
    denselben Text wie vorher (Board-Formatänderungen haben am 16.08. alle
    Prüf-Workflows rot gemacht, B053 — diese hier ist keine).
    """
    zerlegt = parse_takt(wert)
    if not zerlegt:
        return "einmalig"
    basis, wochentag, uhrzeit = zerlegt
    if uhrzeit is None:
        return TAKTE[basis]
    if wochentag is None:
        return f"{TAKTE[basis]} {uhrzeit}"
    return f"{TAKTE[basis]} {WOCHENTAGE[wochentag]} {uhrzeit}"


def erledigt_moment(wert):
    """SWR-104: `zuletzt_erledigt` -> Moment. Ein reines Datum beginnt am TAGESBEGINN.

    Gegenrichtung zu `als_moment`, und aus demselben Grund: ein Termin ohne
    Uhrzeit ist erst am Tagesende verstrichen, eine Erledigung ohne Uhrzeit
    beweist nur den Tagesbeginn. Beide Regeln zeigen damit in dieselbe
    Richtung — **im Zweifel fällig, nie frisch**. Fehlt das Feld oder ist es
    unlesbar, gilt das Ticket als nie erledigt (Entscheidung 2 aus T-0032
    Teil 1, dieselbe Vorsicht wie `session.stille`).
    """
    if isinstance(wert, datetime):
        return wert
    if isinstance(wert, date):
        return datetime.combine(wert, time.min)
    s = str(wert or "").strip()
    if ZEITPUNKT_MUSTER.match(s):
        try:
            return datetime.fromisoformat(s.replace("T", " "))
        except ValueError:
            return None
    return datetime.combine(date.fromisoformat(s), time.min) if ist_datum(s) else None


def _takt_termin_vor(jetzt, wochentag, uhrzeit):
    """Letzter Zeitpunkt <= `jetzt`, an dem dieser Takt gelaufen ist."""
    stunde, minute = (int(x) for x in uhrzeit.split(":"))
    kandidat = jetzt.replace(hour=stunde, minute=minute, second=0, microsecond=0)
    if wochentag is None:
        return kandidat if kandidat <= jetzt else kandidat - timedelta(days=1)
    kandidat -= timedelta(days=(jetzt.weekday() - wochentag) % 7)
    return kandidat if kandidat <= jetzt else kandidat - timedelta(days=7)


def takt_termin(t, jetzt=None):
    """SWR-104: Abgeleiteter Termin eines Uhrzeit-Takts -> (moment, faellig).

    `None`, wenn das Ticket keinen Uhrzeit-Takt trägt (Bestand unverändert) oder
    geschlossen ist. Ist es fällig, ist der Moment der ÜBERSPRUNGENE Termin —
    die Anzeige sagt dann „überfällig seit HH:MM" und nicht „erledigt". Läuft
    keine Session, feuert nichts; das ist die ehrliche Grenze dieser Umsetzung
    (T-0032 Teil 1, Entscheidung 4) und keine stille Falschaussage (B038).

    Der Takt ist KEIN Scheduler: er startet nichts, er beantwortet nur die
    Frage „ist dieses Ticket seit seiner letzten Erledigung über seine Uhrzeit
    gelaufen?" — gestellt von der ohnehin laufenden Routine-Session.
    """
    if t.get("status") in GESCHLOSSEN:
        return None
    zerlegt = parse_takt(t.get("takt"))
    if not zerlegt or zerlegt[2] is None:
        return None
    basis, wochentag, uhrzeit = zerlegt
    jetzt = _jetzt_moment(jetzt)
    letzter = _takt_termin_vor(jetzt, wochentag, uhrzeit)
    zul = erledigt_moment(t.get("zuletzt_erledigt"))
    if zul is None or zul < letzter:
        return letzter, True
    return letzter + timedelta(days=7 if basis == "woechentlich" else 1), False


def ist_takt_faellig(t, jetzt=None):
    """SWR-104: Ist dieses Takt-Ticket seit der letzten Erledigung über seine Uhrzeit?"""
    tm = takt_termin(t, jetzt)
    return bool(tm and tm[1])


def takt_ampel(t, jetzt=None):
    """SWR-104: Ampel des abgeleiteten Takt-Termins — durch `frist_ampel`, nicht daneben.

    Eine zweite Ampelrechnung wäre B033 (Entscheidung 3 aus T-0032 Teil 1).
    Fälligkeit und Ampel sind dabei zwei Aussagen, nicht eine: genau in der
    Minute des Termins ist ein nie erledigtes Ticket bereits **fällig**, sein
    Termin aber noch nicht **verstrichen** (gelb). Beides zusammenzufalten wäre
    der Fehler aus B057; die Kachel listet deshalb nach Fälligkeit, nicht nach
    Farbe.
    """
    tm = takt_termin(t, jetzt)
    return frist_ampel(tm[0], jetzt) if tm else "grau"


#: Rückgabe von `status_in_head`, wenn die Git-Ausgabe zwar da, aber nicht lesbar
#: war. Ausdrücklich NICHT `None`: `None` heißt „das Ticket ist neu" und lässt die
#: Übergangsprüfung zu Recht aus. Ein Lesefehler darf sie nicht stillschweigend
#: auslassen — sonst schluckt die Reparatur einen Befund (B038).
UNLESBAR = "\x00unlesbar"


def status_in_head(repo, datei):
    """Status des Tickets in Git HEAD (None wenn neu/kein Git, UNLESBAR bei Lesefehler).

    Die Git-Ausgabe wird AUSDRÜCKLICH als UTF-8 gelesen. Ohne `encoding` nimmt
    `text=True` die Locale-Kodierung des Systems — auf dem Windows-Host cp1252.
    Ein Zeichen wie „⏳" im Ticket (UTF-8 `e2 8f b3`) enthält dann das in cp1252
    unbelegte Byte `8f`, der Lese-Thread von `subprocess` stirbt mit
    `UnicodeDecodeError`, und `out.stdout` ist `None` — bei `returncode == 0`.

    Befund 2026-08-17 (platform/T-0007): genau das ist passiert. `pm/T-0042.md`
    trägt seit Sprint 3 ein „⏳" an Byte 10338; seither brach der Auto-Wächter am
    Host alle 15 Minuten ab — `parse_frontmatter(None)` warf einen
    `AttributeError`, der weder in der `except`-Liste stand noch die Datei nannte.
    Jede DATEI-Lesung in diesem Modul war schon utf-8-fest, nur diese
    GIT-Lesung nicht.
    """
    try:
        # platform/T-0008: `HEAD:` zählt vom REPO-Wurzelverzeichnis, nicht vom
        # Arbeitsordner. Seit dem Monorepo-Beschluss pm/D003 liegen p10/p11/p12 als
        # ORDNER im Repo `projects` — dort ist der Pfad `p11/tickets/…` und nicht
        # `tickets/…`. Der feste Pfad schlug für diese drei still fehl, `git show`
        # gab `returncode != 0`, das galt als „Ticket ist neu", und die
        # Übergangsprüfung (SWR-002) wurde übersprungen. Der board-check meldete OK.
        # Für drei von sechzehn Einträgen hat SWR-002 damit nie geprüft.
        praefix = subprocess.run(
            ["git", "-C", repo, "rev-parse", "--show-prefix"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10)
        # Leer für ein Repo-Wurzelverzeichnis, „p11/" für einen Unterordner. Bei einem
        # Fehler bleibt es leer — das ist genau das bisherige Verhalten und damit kein
        # neuer Fehlermodus.
        #
        # `or ""` ist nicht Vorsicht, sondern ein gefangener Fehler: die erste Fassung
        # dieser Zeile schrieb `praefix.stdout.strip()` und starb an genau dem
        # `AttributeError: 'NoneType' object has no attribute …`, den T-0007 behoben
        # hat — `stdout` IST None, wenn der Lese-Thread stirbt, auch bei returncode 0.
        # Gefangen hat es der Regressionstest aus T-0007, eine Zeile weiter.
        unter = (praefix.stdout or "").strip() if praefix.returncode == 0 else ""
        out = subprocess.run(
            ["git", "-C", repo, "show", f"HEAD:{unter}tickets/{datei}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10)
        if out.returncode != 0:
            return None
        if out.stdout is None:
            # Kann mit `encoding`/`errors` oben nicht mehr aus der Kodierung kommen.
            # Die Prüfung bleibt trotzdem stehen: sie trennt „kein Vorgänger" von
            # „nicht gelesen", und das ist der Unterschied, an dem dieser Fehler
            # drei Sprints lang unentdeckt blieb.
            return UNLESBAR
        alt, err = parse_frontmatter(out.stdout)
        return None if err else alt.get("status")
    except OSError:
        # Git gar nicht vorhanden — das ist „kein Git" und bleibt `None`, wie bisher.
        return None
    except (subprocess.SubprocessError, UnicodeDecodeError, ValueError):
        # Timeout oder unlesbare Ausgabe — ein Lesefehler, kein fehlender Vorgänger.
        return UNLESBAR


#: SWR-193 (platform/T-0045): die **qualifizierte** Sperr-Kennung `<einheit>/T-xxxx`.
#: Dieselbe Form, die `aggregation.ref` (SWR-087) erzeugt und die `SWR-176` bereits
#: gegenüber der nackten ID bevorzugt — **keine zweite Schreibweise für dieselbe Sache**.
#: ⚠ Die nackte `T-xxxx` bleibt unverändert repo-lokal. Sie umzudeuten hätte den ganzen
#: Bestand angefasst; hier kommt eine Form **dazu**, es wird keine ersetzt.
QUALIFIZIERTE_REF = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)/(T-\d{4})$")
#: Wie viele Ebenen `_org_wurzel` nach oben sucht. `projects/p11` liegt zwei Ebenen unter
#: der Wurzel; drei gibt einen Schritt Luft und schließt eine Wanderung bis `/` aus.
_WURZEL_TIEFE = 3


def _org_wurzel(repo):
    """Die Organisationswurzel über einem Repo — oder `None`, wenn sie nicht zu finden ist.

    ⚠⚠ `None` heißt **„unerreichbar"** und ausdrücklich nicht „leer". Der Unterschied
    trägt die ganze Zusicherung von `SWR-193`: eine Sperre, deren Repo nicht gefunden
    wird, ist etwas anderes als eine Sperre, die auf ein Ticket zeigt, das es dort nicht
    gibt. Nur die zweite ist ein Befund.

    ⚠ Die Wurzel ist die **oberste** Ebene, die dieses Repo **selbst als Einheit sieht**
    und dabei mindestens zwei Einheiten trägt. Beide Hälften sind nötig, und beide sind
    an einem Fehlschlag gelernt:

    * **„oberste"**, weil über `projects/p11` das Sammel-Repo `projects` liegt: drei
      Einheiten (p10–p12), die **erste** passende Ebene — und die falsche. Sie kennt `pm`
      nicht, und eine Sperre auf `pm/T-0077` fiele still in die Lage „unerreichbar",
      obwohl die echte Wurzel jede Einheit sieht (`projekt_pfade` nimmt das Sammel-Repo
      ausdrücklich mit).
    * **⚠⚠ „sieht dieses Repo"**, weil „oberste Ebene mit ≥ 2 Einheiten" allein
      **weiterläuft, als sie darf**. Eine Zusicherung hat es gefunden: unter `/tmp` liegen
      die Arbeitsordner nebenläufiger Testläufe, jeder mit `tickets/` — `/tmp` sah damit
      aus wie eine Organisationswurzel. Die Bedingung, dass die Ebene **das eigene Repo**
      unter ihren Einheiten führt, endet von selbst dort, wo die Organisation endet.

    > **Ein Aufwärtsgang braucht ein Abbruchkriterium, das aus dem Gegenstand kommt, und
    > nicht nur eine Zählung. Eine Zahl sagt „hier sind mehrere Ordner"; sie sagt nicht
    > „und einer davon bin ich".**
    """
    ziel = os.path.abspath(repo or ".")
    pfad, treffer = ziel, None
    for _ in range(_WURZEL_TIEFE):
        pfad = os.path.dirname(pfad)
        if not pfad or pfad == os.path.dirname(pfad):
            break
        einheiten = projekt_pfade(pfad)
        if len(einheiten) >= 2 and any(os.path.abspath(p) == ziel for _n, p in einheiten):
            treffer = pfad
    return treffer


def _pruefe_fremde_sperre(ref, repo):
    """[fehler] für eine qualifizierte `blocked_by`-Kennung. Leer = in Ordnung.

    ⚠⚠ **Drei Lagen, und nur EINE davon ist ein Befund** (`SWR-096`/`SWR-108`-Familie):

    * die Einheit gibt es und das Ticket auch → **still**, die Sperre ist gültig;
    * die Einheit gibt es und das Ticket **nicht** → **Befund**, das ist ein Tippfehler
      oder eine Kennung, die jemand nicht nachgezogen hat;
    * die Wurzel oder die Einheit ist **nicht auffindbar** → **kein Befund**.

    ⚠ Die dritte Lage ist der Grund, warum diese Funktion überhaupt so ausführlich ist.
    `board.py --check` läuft auch in einem einzeln ausgecheckten Repo und in CI, wo die
    Nachbarrepos schlicht nicht daliegen. Dort einen Befund zu melden hieße, eine
    **Aussage über die Umgebung** als **Aussage über das Ticket** auszugeben — und ein
    Gate, das aus einem unerreichbaren Nachbarn einen Fehler macht, ist genau die
    Bauart, die `SWR-166` 83 abgebrochene Läufe gekostet hat.

    > **„Unbekannt" und „unerreichbar" sind zwei Antworten, und nur eine darf blockieren.
    > Sie unter einem Meldetext zusammenzufassen wäre B033 an der Stelle, an der es am
    > teuersten ist: an einem Gate.**
    """
    m = QUALIFIZIERTE_REF.match(ref)
    einheit, tid = m.group(1), m.group(2)
    wurzel = _org_wurzel(repo)
    if wurzel is None:
        return []  # unerreichbar — kein Befund, siehe Rumpf
    pfade = dict(projekt_pfade(wurzel))
    if einheit not in pfade:
        return []  # dieselbe Lage: die Einheit liegt hier nicht, das sagt nichts über sie
    if not os.path.isfile(os.path.join(pfade[einheit], "tickets", f"{tid}.md")):
        return [f"blocked_by verweist auf unbekanntes Ticket: {ref} "
                f"(Einheit {einheit} gefunden, {tid} nicht)"]
    return []


def validiere(t, alle_ids, repo=None, git_pruefen=True):
    """Einzelticket validieren. Gibt Fehlerliste zurück."""
    fehler = []
    for f in FELDER:
        if not t.get(f):
            fehler.append(f"Pflichtfeld fehlt: {f}")
    tid = t.get("id", "")
    if tid and not ID_MUSTER.match(tid):
        fehler.append(f"ungültige ID: {tid} (erwartet T-nnnn)")
    if tid and t.get("_datei") and t["_datei"] != f"{tid}.md":
        fehler.append(f"ID {tid} passt nicht zum Dateinamen {t['_datei']}")
    if t.get("status") not in STATUS:
        fehler.append(f"ungültiger status: {t.get('status')}")
    if t.get("typ") not in TYPEN:
        fehler.append(f"ungültiger typ: {t.get('typ')}")
    if t.get("prio") not in PRIOS:
        fehler.append(f"ungültige prio: {t.get('prio')}")
    # SWR-116 (pm/T-0038 Teil a): `verantwortlich` ist optional, aber wenn gesetzt, gültig —
    # und `mensch` verlangt einen Beleg, was der Mensch tun soll.
    if t.get("verantwortlich"):
        if t["verantwortlich"] not in VERANTWORTLICH:
            fehler.append(f"ungültiges verantwortlich: {t['verantwortlich']} "
                          f"(erlaubt: {', '.join(VERANTWORTLICH)})")
        elif t["verantwortlich"] == "mensch" and \
                HANDLUNG_UEBERSCHRIFT not in (t.get("_body") or ""):
            fehler.append(f"verantwortlich: mensch ohne Abschnitt "
                          f"„{HANDLUNG_UEBERSCHRIFT}\" — wer handeln soll, muss auch "
                          f"lesen können, was zu tun ist (B038)")
    if t.get("erstellt") and not ist_datum(t["erstellt"]):
        fehler.append(f"ungültiges Datum erstellt: {t['erstellt']}")
    if t.get("takt") and not parse_takt(t["takt"]):  # SWR-074/104: optional, aber wenn, dann gültig
        fehler.append(f"ungültiger takt: {t['takt']} (erlaubt: {', '.join(TAKTE)}; "
                      f"mit Uhrzeit nur {'/'.join(TAKTE_MIT_UHRZEIT)}, "
                      f"z. B. taeglich@14:00 oder woechentlich@Mo-14:00)")
    # SWR-104: `zuletzt_erledigt` ist der Fortschritt eines Takt-Tickets — ohne Takt
    # gibt es nichts, worauf es sich bezieht. Ein Feld, das dasteht und nichts bewirkt,
    # ist die stille Falschaussage aus B038; deshalb Fehler statt schweigend ignorieren.
    if t.get("zuletzt_erledigt"):
        if erledigt_moment(t["zuletzt_erledigt"]) is None:
            fehler.append(f"ungültiges zuletzt_erledigt: {t['zuletzt_erledigt']} "
                          f"(erwartet JJJJ-MM-TT oder JJJJ-MM-TT HH:MM)")
        elif not t.get("takt"):
            fehler.append("zuletzt_erledigt ohne takt: das Feld bezieht sich auf einen Takt")
    # SWR-106: Sprintnummern sind fortlaufend und ganzzahlig. „nächster Sprint" oder
    # „bald" wären keine Planung, sondern eine Absichtserklärung — genau das, was die
    # Umstellung von Datum auf Sprint beenden soll.
    if t.get("geplant_sprint") and parse_sprint_nr(t["geplant_sprint"]) is None:
        fehler.append(f"ungültiger geplant_sprint: {t['geplant_sprint']} "
                      f"(erwartet eine Sprintnummer, z. B. 42 oder 'Sprint 42')")
    # SWR-091 (pm/T-0030): `frist` ist ab jetzt für JEDEN Typ zulässig und wird für
    # jeden Typ geprüft. Bis hierher galt die Datumsprüfung nur für Decision-Requests —
    # ein Tippfehler in der Frist eines CR wäre stillschweigend als „keine Frist"
    # durchgegangen, und ein Termin, den niemand prüft, ist keiner (B038).
    if t.get("frist") and not ist_datum(t["frist"]):
        fehler.append(f"ungültiges Datum frist: {t['frist']}")
    labels = parse_liste(t.get("labels"))  # SWR-079: optional, frei gewählt, aber prüfbar
    if len(labels) > LABEL_MAX:
        fehler.append(f"zu viele labels: {len(labels)} (erlaubt: höchstens {LABEL_MAX})")
    for lab in labels:
        if not LABEL_MUSTER.match(lab):
            fehler.append(f"ungültiges label: {lab} (erlaubt: Buchstaben, Ziffern, "
                          f"Leerzeichen und _ . + / -, höchstens 40 Zeichen)")
    bb = parse_liste(t.get("blocked_by"))
    for ref in bb:
        if ref == tid:
            fehler.append("blocked_by verweist auf sich selbst")
        elif QUALIFIZIERTE_REF.match(ref):
            # SWR-193 (platform/T-0045): eine Sperre darf ein fremdes Repo nennen.
            fehler.extend(_pruefe_fremde_sperre(ref, repo))
        elif ref not in alle_ids:
            fehler.append(f"blocked_by verweist auf unbekanntes Ticket: {ref}")
    # Status-Regeln (Playbook Kap. 5)
    if t.get("status") == "in_review":
        rev = t.get("reviewer", "")
        if not rev:
            fehler.append("in_review erfordert Feld reviewer")
        elif rev == t.get("rolle"):
            fehler.append("reviewer darf nicht der Autor (rolle) sein")
    if t.get("status") == "blocked" and not bb:
        fehler.append("blocked erfordert blocked_by-Verweis")
    # T-0039: decision-request — maschinenlesbare Optionen/Frist/Default
    if t.get("typ") == "decision-request":
        opts = parse_liste(t.get("optionen"))
        # Datumsprüfung der Frist steht seit SWR-091 weiter oben und gilt für alle Typen.
        if opts and t.get("default"):
            for tok in parse_optionstoken(t["default"]):
                if tok not in opts:
                    fehler.append(f"default-Token '{tok}' nicht in optionen")
        if not opts and tid not in DR_BESTAND:
            fehler.append("decision-request ohne optionen-Frontmatter "
                          "(T-0051; Bestands-DRs ausgenommen)")
    # Status-Übergang gegen HEAD (Mensch-Tickets sind Gates: Übergänge frei)
    if git_pruefen and repo and t.get("_datei") and t.get("status") in STATUS \
            and t.get("rolle") != "mensch":
        alt = status_in_head(repo, t["_datei"])
        if alt is UNLESBAR:
            # Als Befund, nicht als übersprungene Prüfung: board.py meldet die DATEI
            # und den Grund, statt mit einem `AttributeError` zu sterben, der beides
            # verschweigt (platform/T-0007).
            fehler.append("Vorgängerstand in Git nicht lesbar — "
                          "Status-Übergang ungeprüft")
        elif alt and alt in STATUS and alt != t["status"]:
            if t["status"] not in UEBERGAENGE.get(alt, []):
                fehler.append(f"unzulässiger Status-Übergang: {alt} -> {t['status']}")
    return fehler


def validiere_alle(tickets, repo=None, git_pruefen=True):
    """Alle Tickets validieren (inkl. Duplikat-Check). Gibt Problemliste zurück."""
    probleme = []
    ids = [t.get("id") for t in tickets if t.get("id")]
    for doppelt in {i for i in ids if ids.count(i) > 1}:
        probleme.append(f"doppelte Ticket-ID: {doppelt}")
    alle_ids = set(ids)
    for t in tickets:
        for e in validiere(t, alle_ids, repo, git_pruefen):
            probleme.append(f"{t.get('_datei', '?')}: {e}")
    return probleme


def verantwortlich_wert(t):
    """SWR-116: Wer handelt — `team` (Default) oder `mensch`.

    Eine Stelle, die die Frage beantwortet. Ohne sie läse jeder Leser das leere Feld
    selbst und entschiede selbst, was leer bedeutet — zwei Leser, zwei Antworten (B033).
    """
    wert = (t.get("verantwortlich") or "").strip()
    return wert if wert in VERANTWORTLICH else VERANTWORTLICH_DEFAULT


ENTSCHEIDUNGSMARKER = "**Entscheidung ("  # SWR-039/SWR-131: die Rumpfzeile der Inbox
STATUS_FINAL = ("done", "rejected")


def dr_entschieden(t):
    """SWR-131 (platform/T-0014): Ist dieser DR entschieden? — die **eine** Antwort.

    ⚠ **Der Anlass ist ein gemessener Fehler gegenüber dem Auftraggeber.** Am
    2026-08-17 um 11:48:25 hat er `projects/p12/T-0007` über die Inbox mit
    `B-node-optional` entschieden. Die Inbox nahm die Entscheidung an, schrieb sie in
    den Ticketrumpf und committete sie. Danach schrieb derselbe Sprint drei Berichte —
    Sprintplan, Agenda, Projektstatus —, die alle sagten, die Frage liege noch bei ihm.

    **Die Ursache waren zwei Wahrheiten über ein Wort.** `inbox._dr_tickets` und
    `inbox.historie` lesen „entschieden" am **Rumpfmarker** (SWR-039);
    `wartet_auf_mensch`, `aggregation` und der Preflight lasen ihn am **Status**. Und
    `inbox.entscheide` fasst `status` nie an — es schreibt Decision-Log, Rumpfzeile,
    Commit, sonst nichts, und das ist nach ADR-003 auch richtig so: der Schreibpfad des
    Menschen darf den Arbeitsstand des Teams nicht fortschreiben.

    > **Eine Entscheidung im Fließtext ist für jede Prüfung unsichtbar.**

    Diese Funktion ist deshalb der eine Auflösungspunkt — dieselbe Bauart wie
    `verantwortlich_wert` (SWR-116) und `wartet_auf_mensch` (SWR-120), und aus
    demselben Grund: zwei Formulierungen einer Bedingung sind zwei Antworten in
    Wartestellung (B033). `inbox.ENTSCHIEDEN` delegiert ab SWR-131 hierher, statt eine
    zweite Kopie zu führen; die Importrichtung erlaubt das (`inbox` kennt `board`).

    **Zwei Quellen, ein Sachverhalt — und das ist hier kein B033.** Entschieden ist ein
    DR, wenn die Inbox ihn entschieden hat (Marker) **oder** wenn das Team ihn bereits
    verbucht hat (finaler Status). Das ist nicht zweimal dieselbe Aussage, sondern
    Anfang und Ende **eines** Vorgangs: 42 der 43 entschiedenen DRs im Bestand tragen
    beides, `p12/T-0007` trug nur das erste. Wer nur den Status läse, übersähe genau
    den Fall, der diese Anforderung ausgelöst hat; wer nur den Marker läse, übersähe
    die Altfälle, deren Entscheidung vor SWR-039 anders vermerkt wurde.

    ⚠ **Der Marker wird am Zeilenanfang gesucht, nicht irgendwo im Text.** Ein Rumpf,
    der die Entscheidung nur *erwähnt* („die Entscheidung (D002) steht noch aus"), ist
    keine Entscheidung — die Gegenprobe dazu steht in den Tests. `_body` liefert
    `parse_frontmatter` bereits mit; fehlt es (Aufrufer mit reinem Frontmatter-Dict),
    entscheidet der Status allein, statt eine Ausnahme zu werfen.
    """
    if t.get("status") in STATUS_FINAL:
        return True
    body = t.get("_body") or ""
    return any(z.lstrip().startswith(ENTSCHEIDUNGSMARKER) for z in body.splitlines())


def wartet_auf_mensch(t):
    """SWR-120: Muss der MENSCH handeln? — die eine Antwort für alle Anzeigen.

    ⚠ **Beim Bau von SWR-119/120 haben zwei Anzeigen sich widersprochen.** Die
    Board-Spalte las `verantwortlich_wert` und schrieb bei `projects/p11/T-0006`
    „Team"; der Org-Zähler zählte dasselbe Ticket als „wartet auf den Menschen", weil
    es ein `decision-request` ist. Beide Aussagen waren für sich begründet und
    zusammen falsch — zwei Leser, zwei Antworten auf eine Frage (B033), und zwar
    entstanden **im selben Lauf**, in dem die zweite Anzeige gebaut wurde.

    Diese Funktion ist deshalb die eine Stelle. Sie ist **nicht** dasselbe wie
    `verantwortlich_wert`, und die Trennung ist Absicht:

    * `verantwortlich_wert` beantwortet, was das **Feld** sagt (mit Default). Sie ist
      der Auflösungspunkt aus SWR-116 und bleibt unverändert.
    * `wartet_auf_mensch` beantwortet, ob der **Mensch am Zug** ist. Das ist das Feld
      **oder** der Typ `decision-request` — ein DR liegt qua Typ beim Auftraggeber,
      auch wenn niemand das Feld gesetzt hat.

    Ein DR bekommt also **nicht** still `verantwortlich: mensch` untergeschoben: das
    Feld bliebe sonst leer und läse sich trotzdem als gesetzt, und SWR-116 verlangt bei
    `mensch` einen Abschnitt `## Handlung beim Menschen`, den ein DR nicht führt (seine
    Handlung steht in `optionen` + `default`).

    ⚠ **SWR-131: ein entschiedener DR wartet auf niemanden.** Dieser Satz stand seit
    SWR-120 wörtlich im Docstring von `aggregation.wartet_auf_mensch` — und war
    **richtig und unwirksam**, weil „entschieden" dort über `status` bestimmt wurde und
    die Inbox `status` nie setzt. Er wird hier erstmals wirksam, an der Stelle, die alle
    Anzeigen lesen.

    ⚠ Die Ergänzung allein wäre die **falsche** Reparatur: das entschiedene, aber nicht
    verbuchte Ticket verschwände aus jeder Anzeige und stünde weiter auf `open`, mit
    unerledigter Folgearbeit und ohne Leser — wieder SWR-122, eine Etage tiefer. Die
    zweite Hälfte ist deshalb Pflicht und steht im Preflight
    (`dr_entschieden_nicht_verbucht`): **nicht behaupten, jemand warte — und nicht
    schweigen, dass etwas offen ist.**
    """
    if t.get("typ") == "decision-request" and dr_entschieden(t):
        return False
    return verantwortlich_wert(t) == "mensch" or t.get("typ") == "decision-request"


def gesperrt(t):
    """SWR-198 (platform/T-0051): Ist dieses Ticket **gesperrt** — und damit unplanbar?

    **Die eine Begründung, an einer Stelle.** Zwei Prüfungen brauchen sie:
    `sprint.sprint_vergangen` (SWR-112) und `aggregation._ist_unterminiert`
    (SWR-114/125). Beide sind einzeln richtig, und genau deshalb bildeten sie bis
    Sprint 30 eine **Zange**:

    | `geplant_sprint` eines gesperrten Tickets | Prüfung | Ergebnis |
    |---|---|---|
    | vergangen (`29`) | `sprint_vergangen` | Befund „offen auf vergangenem Sprint" |
    | leer | `unterminierte_tickets` | Befund „Ticket ohne Sprint" |
    | Zukunft (`31`) | — | still, **aber** eine Zusage über fremdes Handeln |

    **Für ein gesperrtes Ticket gibt es keinen zulässigen Terminwert.** Der einzige
    Wert, der beide Prüfungen still hält, ist eine Terminzusage, die das Team nicht
    halten kann — die Sperre hängt an einer Entscheidung des Auftraggebers. Eine Lage,
    in der die bequeme Handlung die einzige ist, die grün macht, ist genau die Bauart,
    gegen die SWR-166 gebaut wurde.

    **Warum die Lücke niemandes Versäumnis ist.** `sprint.py` nahm bereits **einen Typ**
    aus, `decision-request`, mit wörtlich dieser Begründung: *„ein DR liegt beim
    Menschen, das Team kann ihn nicht bewegen, und eine Sprintnummer daneben wäre eine
    Zusage, die das Team nicht halten kann."* Sie stand nur an einem **Typ** statt an
    einem **Zustand** — weil `decision-request` bis Sprint 29 der einzige Weg war,
    *„das Team kann hier nicht handeln"* auszudrücken. `blocked` mit `blocked_by` gibt
    es erst seit SWR-193, **einen Sprint alt**.

    > **Ein Stellvertreter, der lange mit der Sache zusammenfiel, wird zum Loch in dem
    > Moment, in dem die Sache einen eigenen Namen bekommt.** Dieselbe Familie wie
    > SWR-196: dort war die Besetzungsprüfung an der falschen Stelle in der Reihenfolge,
    > hier die Ausnahme an der falschen Sorte Merkmal.

    **⚠ Gebunden an den VERWEIS, nicht an das Wort.** „Gesperrt" ohne `blocked_by` ist
    eine Behauptung, keine Sperre — und eine Ausnahme, die auf ein bloßes Wort hört,
    wäre ein Schlupfloch: jedes unbequeme Ticket ließe sich mit einem Statuswort
    aus beiden Prüfungen nehmen. Gemessen (2026-08-21, Sprint 31): `validiere` lehnt
    `blocked` ohne `blocked_by` bereits ab (*„blocked erfordert blocked_by-Verweis"*),
    und alle **3** gesperrten Tickets des Bestands tragen einen Verweis. Die Bindung an
    den Verweis kostet heute also **nichts** und schließt den Weg trotzdem — und wird
    nicht dadurch tautologisch, dass eine zweite Prüfung dasselbe fordert: die beiden
    laufen an verschiedenen Toren, und ein aufgeweichter Validator macht diese Ausnahme
    nicht auf.

    ⚠ **Nicht ausgenommen: die Frist.** Ein gesperrtes Ticket, das eine `frist` trägt,
    bleibt für `ueberfaellig` (SWR-091) sichtbar. Eine Sperre verschiebt keinen Termin
    nach außen; sie sagt nur, dass das Team ihn nicht durch Arbeit halten kann.
    """
    return t.get("status") == "blocked" and bool(parse_liste(t.get("blocked_by")))


def offene_blocker(t, tickets_nach_id):
    """IDs der blocked_by-Tickets, die noch nicht done sind."""
    return [ref for ref in parse_liste(t.get("blocked_by"))
            if tickets_nach_id.get(ref, {}).get("status") != "done"]


def generiere_board(tickets, stand=None):
    """BOARD.md-Inhalt deterministisch erzeugen."""
    wiederkehrend = sum(1 for t in tickets if t.get("takt"))
    kopf = f"\nStand: {stand or date.today().isoformat()} · Tickets: {len(tickets)}"
    if wiederkehrend:  # SWR-074: dauerhaft offene Takt-Aufgaben sichtbar von einmaligen trennen
        kopf += f" · davon wiederkehrend: {wiederkehrend}"
    zeilen = ["# Board (generiert von platform/scripts/board.py — nicht von Hand editieren)",
              kopf + "\n"]
    for st in STATUS:
        gruppe = [t for t in tickets if t.get("status") == st]
        if not gruppe:
            continue
        zeilen.append(f"\n## {st} ({len(gruppe)})\n")
        # SWR-119 (pm/T-0050): Spalte „Verantwortlich" — steht NEBEN `Rolle` und nicht
        # an deren Stelle. Die beiden beantworten verschiedene Fragen: `rolle` sagt,
        # welche Disziplin zuständig ist (`pl`, `cm`, …), `verantwortlich` sagt, ob
        # überhaupt das TEAM handelt oder der Mensch. Sie zusammenzulegen wäre B033 —
        # und hätte `rolle: mensch` still zur zweiten Bedeutung gemacht, was SWR-116
        # ausdrücklich vermeidet.
        zeilen.append("| ID | Titel | Typ | Takt | Rolle | Verantwortlich | Prio "
                      "| Sprint | blockiert durch |")
        zeilen.append("|---|---|---|---|---|---|---|---|---|")
        for t in sorted(gruppe, key=lambda x: (PRIO_RANG.get(x.get("prio"), 99), x.get("id", ""))):
            bb = ", ".join(parse_liste(t.get("blocked_by"))) or "—"
            takt = takt_klartext(t.get("takt"))  # SWR-074/104
            # Der Wert kommt aus `verantwortlich_wert` und wird NICHT hier aufgelöst:
            # eine zweite Auflösung des leeren Feldes wäre die zweite Antwort auf eine
            # Frage, für die SWR-116 genau eine Stelle gebaut hat.
            # SWR-119/120: EINE Antwort fuer Board-Spalte und Org-Zaehler. Vor der
            # Zusammenlegung schrieb die Spalte bei einem `decision-request` „Team",
            # waehrend der Zaehler dasselbe Ticket als „wartet auf den Menschen"
            # fuehrte — zwei Leser, zwei Antworten (B033).
            v_text = "MENSCH" if wartet_auf_mensch(t) else "Team"
            zeilen.append(f"| [{t['id']}](tickets/{t['id']}.md) | {t['titel']} | {t['typ']} "
                          f"| {takt} | {t['rolle']} | {v_text} | {t['prio']} "
                          f"| {t['sprint']} | {bb} |")
    return "\n".join(zeilen) + "\n"


def unverbuchte_status(repo):
    """Tickets, deren `status` in der Arbeitskopie von `HEAD` abweicht (SWR-139).

    ⚠ **Die Zuspitzung auf `status` ist der Punkt.** SWR-110 meldet die Arbeitskopie
    ohnehin; ein Befund über *jede* Änderung wäre bei laufender Arbeit dauernd rot und
    trainierte das Wegsehen an — dieselbe Falle wie die 42 Alt-DRs in SWR-131. Ein
    ergänzter Tickettext ist kein verlorener Zustand; ein nicht gebuchter
    **Statuswechsel** ist einer, weil der nächste Wechsel ihn überschreibt.

    Gelesen wird durch :func:`status_in_head` — die Funktion, die es **schon gab**.
    ⚠ Beim Bau von SWR-139 wurde daneben eine zweite gleichen Namens geschrieben, die
    die erste stillschweigend überschrieb; Python meldet das nicht. Gefunden hat es
    `test_board.VerschachteltesRepoUebergangTest`, weil die vorhandene Fassung drei
    Dinge kann, die die neue nicht konnte: den Monorepo-Präfix `p11/tickets/…`
    (platform/T-0008), das ausdrückliche UTF-8 (platform/T-0007) und die Unterscheidung
    von „neu" (`None`) und „unlesbar" (:data:`UNLESBAR`).

    :data:`UNLESBAR` ist hier **kein** Befund: `validiere_alle` meldet ihn bereits, und
    ein zweiter Melder derselben Sache wäre B033.

    Rückgabe: Liste von Meldungen, jede nennt Ticket, Dateistand und HEAD-Stand (B038).
    """
    befunde = []
    tickets, _ = lade_tickets(repo)
    for t in tickets:
        if not t.get("_datei"):
            continue
        in_head = status_in_head(repo, t["_datei"])
        if in_head is None or in_head is UNLESBAR:
            continue
        if in_head != t.get("status"):
            befunde.append(f"{os.path.basename(os.path.abspath(repo))}/{t.get('id')}: "
                           f"Statuswechsel unverbucht — Datei '{t.get('status')}', "
                           f"HEAD '{in_head}'")
    return befunde


def setze_status(repo, tid, neu, reviewer=None, notiz=None, meldung=None,
                 head_pruefen=True, _verbuche=None):
    """T-0062 / SWR-139: Statuswechsel als **ein** Vorgang — schreiben **und** buchen.

    Übergangsprüfung gegen den AKTUELLEN Dateizustand, Pflichtfeld-Logik (reviewer bei
    in_review), geändert-Datum, Validierung, BOARD-Regeneration. Wirft ValueError bei
    unzulässigem Übergang (Session und Tick nutzen denselben Pfad).

    ⚠⚠ **Warum diese Funktion committet.** Bis Sprint 15 war ein Statuswechsel zwei
    Aufrufe: erst schreiben, dann buchen. Scheitert der zweite an einer verwaisten
    `.git/index.lock`, steht der Zustand in der Datei und **nicht** in der Historie —
    der nächste Wechsel überschreibt ihn, und eine Stufe fehlt. Das ist in **einem** Lauf
    zweimal eingetreten und einmal committet worden (`pm/T-0052`: `in_progress -> done`).

    > **Ein Zustandswechsel, der aus zwei Vorgängen besteht, hat einen Zwischenzustand —
    > und jeder Zwischenzustand, den niemand bucht, ist ein verlorener Zustand.**

    `meldung` ist die Commit-Meldung; der Aufrufer **baut keinen Commit**. Ohne `meldung`
    wird wie bisher nur geschrieben — die bestehenden Aufrufer (Orchestrator-Tick,
    `feedback_route`) schreiben mitten in ihrer **eigenen** Transaktion und dürfen davon
    nicht überrascht werden.

    **Scheitert die Buchung, gilt der Wechsel als nicht geschehen**: Ticketdatei und
    `BOARD.md` werden auf ihre Bytes von vorher zurückgesetzt und der Fehler geworfen.
    ⚠ Das ist die wichtigere Hälfte — ein Wechsel, der die Datei ändert und den Fehler
    *nur meldet*, ist genau der Zustand, gegen den SWR-139 existiert.

    `head_pruefen=False` wählt die Prüfung „kein zweiter Wechsel auf einem unverbuchten"
    ab; sie ist für den Aufrufer gedacht, der selbst mitten in einer Transaktion steckt
    (der Tick schreibt drei Stände innerhalb eines Branches).

    `_verbuche` ist die **Naht für die Gegenprobe** und keine Konfiguration: ohne sie
    ließe sich die Zusicherung „gescheiterte Buchung = kein Wechsel" nicht prüfen, und
    eine Zusicherung ohne Prüfung ist die Lage aus SWR-125.
    """
    pfad = os.path.join(repo, "tickets", f"{tid}.md")
    if not os.path.exists(pfad):
        raise ValueError(f"unbekanntes Ticket: {tid}")
    if head_pruefen:
        in_head = status_in_head(repo, f"{tid}.md")
        if in_head is not None and in_head is not UNLESBAR:
            _text, _t = lies_ticket(repo, tid)
            if _t.get("status") != in_head:
                raise ValueError(
                    f"{tid}: unverbuchter Statuswechsel — die Datei steht auf "
                    f"'{_t.get('status')}', HEAD auf '{in_head}'. Erst buchen, dann "
                    f"weiterbewegen (SWR-139).")
    text = open(pfad, encoding="utf-8").read().replace("\r\n", "\n")
    t, err = parse_frontmatter(text)
    if err:
        raise ValueError(f"{tid}: {err}")
    alt = t.get("status")
    if neu != alt and neu not in UEBERGAENGE.get(alt, []):
        raise ValueError(f"unzulässiger Status-Übergang: {alt} -> {neu} "
                         f"(erlaubt: {', '.join(UEBERGAENGE.get(alt, []))})")
    if neu == "in_review" and not (reviewer or t.get("reviewer")):
        raise ValueError("in_review erfordert --reviewer")
    text = re.sub(r"(?m)^status:.*$", f"status: {neu}", text, count=1)
    heute = date.today().isoformat()
    for feld, wert in (("reviewer", reviewer), ("geändert", heute)):
        if not wert:
            continue
        if re.search(rf"(?m)^{feld}:", text):
            text = re.sub(rf"(?m)^{feld}:.*$", f"{feld}: {wert}", text, count=1)
        else:
            text = re.sub(r"(?m)^erstellt:", f"{feld}: {wert}\nerstellt:", text, count=1)
    if notiz:
        text = text.rstrip() + f"\n\n{notiz}\n"
    # Bytes von VORHER merken — sie sind der Rückweg, falls die Buchung scheitert.
    board_pfad = os.path.join(repo, "BOARD.md")
    alt_ticket = open(pfad, "rb").read()
    alt_board = open(board_pfad, "rb").read() if os.path.exists(board_pfad) else None
    open(pfad, "w", encoding="utf-8", newline="\n").write(text)
    tickets, probleme = lade_tickets(repo)
    probleme += validiere_alle(tickets, repo, git_pruefen=False)
    if probleme:
        open(pfad, "wb").write(alt_ticket)
        raise ValueError("Ticket-Update invalide: " + "; ".join(probleme))
    open(board_pfad, "w", encoding="utf-8", newline="\n").write(generiere_board(tickets))
    if not meldung:
        return
    verbuche = _verbuche
    if verbuche is None:
        hier = os.path.dirname(os.path.abspath(__file__))
        oben = os.path.normpath(os.path.join(hier, ".."))
        if oben not in sys.path:
            sys.path.insert(0, oben)
        from backend import git_schreiben  # in der Funktion: sonst Zyklus (SWR-134)
        verbuche = git_schreiben.verbuche
    ergebnis = verbuche(repo, [os.path.relpath(pfad, repo), "BOARD.md"], meldung)
    if getattr(ergebnis, "ok", False):
        return
    # Gescheiterte Buchung: der Wechsel gilt als NICHT GESCHEHEN.
    open(pfad, "wb").write(alt_ticket)
    if alt_board is None:
        if os.path.exists(board_pfad):
            os.remove(board_pfad)
    else:
        open(board_pfad, "wb").write(alt_board)
    raise ValueError(
        f"{tid}: Buchung gescheitert, Wechsel {alt} -> {neu} zurückgenommen — "
        f"{(getattr(ergebnis, 'stderr', '') or '').strip()[:300]}")


def ticket_pfad(repo, tid):
    return os.path.join(repo, "tickets", f"{tid}.md")


def lies_ticket(repo, tid):
    """(text, frontmatter-dict) eines Tickets. Wirft ValueError, wenn es fehlt."""
    pfad = ticket_pfad(repo, tid)
    if not ID_MUSTER.match(str(tid or "")) or not os.path.exists(pfad):
        raise ValueError(f"unbekanntes Ticket: {tid}")
    text = open(pfad, encoding="utf-8").read().replace("\r\n", "\n")
    t, err = parse_frontmatter(text)
    if err:
        raise ValueError(f"{tid}: {err}")
    t["_datei"] = f"{tid}.md"
    return text, t


OPTIONALE_FELDER = ("takt", "labels", "reviewer", "frist", "zuletzt_erledigt",
                    "geplant_sprint")  # leer = Zeile entfällt


def _feld_schreiben(text, feld, wert):
    """Frontmatter-Feld setzen, einfügen oder (bei leerem optionalem Wert) entfernen.

    Eingefügt wird vor `erstellt:` — dieselbe Stelle, die `setze_status` benutzt,
    damit die Dateien unabhängig vom Schreibweg gleich aussehen.
    """
    vorhanden = re.search(rf"(?m)^{re.escape(feld)}:.*$", text)
    if wert == "" and feld in OPTIONALE_FELDER:
        return re.sub(rf"(?m)^{re.escape(feld)}:.*\n", "", text, count=1) if vorhanden else text
    zeile = f"{feld}: {wert}"
    if vorhanden:
        return re.sub(rf"(?m)^{re.escape(feld)}:.*$", zeile, text, count=1)
    return re.sub(r"(?m)^erstellt:", f"{zeile}\nerstellt:", text, count=1)


def _wert_normieren(feld, wert):
    """Formularwert in die Frontmatter-Schreibweise bringen (Liste -> '[a, b]')."""
    if feld == "labels":
        roh = wert if isinstance(wert, (list, tuple)) else parse_liste(wert)
        sauber = [str(x).strip() for x in roh if str(x).strip()]
        return f"[{', '.join(sauber)}]" if sauber else ""
    wert = "" if wert is None else str(wert).strip()
    if feld == "titel":
        return f'"{wert}"'
    return wert


def _anzeigewert(feld, roh):
    """Aktueller Wert eines Feldes in derselben Schreibweise wie `_wert_normieren`."""
    return _wert_normieren(feld, roh if roh is not None else "")


def aktualisiere(repo, tid, aenderungen, body=None, erwarteter_fingerprint=None,
                 herkunft="Mensch via HMI", jetzt=None):
    """SWR-077/078/080/081 (P10, ADR-007): zweiter Schreibpfad auf Tickets.

    Absichtlich hier und nicht im Backend: Validierung, Status-Übergänge und die
    BOARD.md-Regeneration sind die Regeln der Skript-Route — ein Nachbau im Server
    wäre die zweite Kopie derselben Logik (Lesson 16.08.) und würde genau das
    Auseinanderlaufen erzeugen, das Risiko R2 des Sprint-0-Plans beschreibt.

    Reihenfolge (bewusst): Konflikt -> Editierbarkeit -> Übergang -> Vollvalidierung
    -> erst dann schreiben. Bis zur letzten Zeile ist die Arbeitskopie unberührt;
    jeder Abbruch lässt sie exakt so zurück, wie sie war (SWR-078).

    Gibt {"fingerprint", "geaendert", "status"} zurück; wirft KonfliktFehler
    (SWR-080) bzw. ValueError mit den Meldungen, die auch `board.py` ausgibt.
    """
    text, t = lies_ticket(repo, tid)
    ist_fingerprint = fingerprint(text)
    if erwarteter_fingerprint and erwarteter_fingerprint != ist_fingerprint:
        raise KonfliktFehler(
            f"{tid} wurde inzwischen von einer anderen Stelle geändert (sehr wahrscheinlich "
            f"die laufende Routine-Session). Deine Eingaben wurden NICHT gespeichert, damit "
            f"nichts still überschrieben wird — bitte das Ticket neu laden und die Änderung "
            f"erneut eintragen.")
    unbekannt = [f for f in aenderungen if f not in EDITIERBARE_FELDER]
    if unbekannt:
        raise ValueError(f"Feld nicht über das HMI änderbar: {', '.join(sorted(unbekannt))} "
                         f"(änderbar: {', '.join(EDITIERBARE_FELDER)})")
    alt_status = t.get("status")
    neu_status = str(aenderungen.get("status", alt_status) or "").strip()
    # SWR-077: erledigte/abgelehnte Tickets sind Archiv — nur die Wiedereröffnung
    # über den erlaubten Übergang, und dabei nichts anderes nebenbei.
    if alt_status in GESCHLOSSEN:
        andere = [f for f in aenderungen if f != "status"]
        if andere or neu_status == alt_status:
            raise ValueError(
                f"{tid} ist {alt_status} und damit Archiv — änderbar ist hier nur die "
                f"Wiedereröffnung (Status {alt_status} -> "
                f"{', '.join(UEBERGAENGE.get(alt_status, [])) or 'kein Übergang'}).")
    if neu_status != alt_status and neu_status not in UEBERGAENGE.get(alt_status, []):
        raise ValueError(f"unzulässiger Status-Übergang: {alt_status} -> {neu_status} "
                         f"(erlaubt: {', '.join(UEBERGAENGE.get(alt_status, []))})")
    geaendert = []
    neu_text = text
    for feld in EDITIERBARE_FELDER:
        if feld not in aenderungen:
            continue
        wert = _wert_normieren(feld, aenderungen[feld])
        if "\n" in wert or '"' in wert.strip('"'):
            raise ValueError(f"{feld} darf weder Anführungszeichen noch Zeilenumbrüche "
                             f"enthalten")
        if wert == _anzeigewert(feld, t.get(feld)):
            continue
        neu_text = _feld_schreiben(neu_text, feld, wert)
        geaendert.append(feld)
    neuer_body = t.get("_body", "") if body is None else str(body).replace("\r\n", "\n").strip()
    if body is not None and neuer_body != t.get("_body", ""):
        geaendert.append("Fließtext")
    if not geaendert:
        raise KeineAenderung(
            f"{tid}: keine Änderung — die Felder tragen bereits diese Werte.")
    stempel = zeitpunkt(jetzt)
    neu_text = _feld_schreiben(neu_text, "geändert", (jetzt or datetime.now()).date().isoformat())
    kopf = re.match(r"^---\n.*?\n---\n", neu_text, re.S).group(0)
    # SWR-081: Historie im Ticket selbst — unabhängig von Git lesbar, auch am Handy.
    vermerk = f"**Bearbeitet ({stempel}, {herkunft}):** {', '.join(geaendert)}"
    neu_text = kopf + "\n" + (neuer_body + "\n\n" if neuer_body else "") + vermerk + "\n"
    # Vollvalidierung mit GENAU den Regeln der Skript-Route (SWR-077).
    tickets, probleme = lade_tickets(repo)
    entwurf, err = parse_frontmatter(neu_text)
    if err:
        raise ValueError(f"{tid}: {err}")
    entwurf["_datei"] = f"{tid}.md"
    tickets = [entwurf if x.get("id") == tid else x for x in tickets]
    probleme += validiere_alle(tickets, repo, git_pruefen=False)
    if probleme:
        raise ValueError("; ".join(probleme))
    open(ticket_pfad(repo, tid), "w", encoding="utf-8", newline="\n").write(neu_text)
    open(os.path.join(repo, "BOARD.md"), "w", encoding="utf-8", newline="\n").write(
        generiere_board(tickets))
    return {"fingerprint": fingerprint(neu_text), "geaendert": geaendert,
            "status": entwurf.get("status"), "zeitpunkt": stempel}


#: SWR-192 (platform/T-0030, Brief platform/N-0007): die Überschrift, unter der der
#: Verlauf steht. Als Konstante und nicht als Literal, weil drei Stellen sie brauchen
#: (Schreiber, Leser, Zusicherung) — drei Literale wären drei Gelegenheiten, sie
#: auseinanderlaufen zu lassen (SWR-131).
KOMMENTAR_UEBERSCHRIFT = "## Verlauf"
#: Der Kopf eines einzelnen Beitrags. `%s` = Absender, `%s` = Zeitstempel.
KOMMENTAR_FORMAT = "**%s (%s):**"
_KOMMENTAR_KOPF = re.compile(r"^\*\*(?P<von>.+?) \((?P<zeit>[^)]+)\):\*\*$", re.M)


def kommentiere(repo, tid, text, von="Mensch via HMI", erwarteter_fingerprint=None,
                jetzt=None):
    """SWR-192: einen Beitrag an den Ticket-Rumpf hängen — der dritte Schreibpfad.

    ⚠⚠ **Der Brief hat die Bauart mitbestellt und nicht nur das Merkmal:** *„ähnlich wie
    hier beim Team-Chat"*. Der Team-Chat ist **kein eigener Speicher** — ein Beitrag
    wird an **dieselbe Datei** gehängt (`briefkasten._beitrag_anhaengen`). Deshalb steht
    ein Kommentar im **Ticket-Rumpf** und nicht in einer Kommentardatei, einer Tabelle
    oder einem zweiten Ordner. Der bequeme Bau wäre ein zweiter Ort gewesen, und dieses
    Haus hat B033 dreimal bezahlt (`p9/T-0007`, `pm/T-0017`, `platform/T-0028`).

    ⚠⚠ **Ein Kommentar ist KEINE Bearbeitung, und daran hängt der ganze Zuschnitt.**
    Deshalb ausdrücklich **nicht** über `aktualisiere`:

    * **kein Frontmatter-Feld** wird angefasst — auch `geändert` nicht. Ein
      `geändert`-Sprung nach einem Kommentar sähe aus wie eine Bearbeitung, und
      `unverbuchte_status`/`uebergang_historie` lesen genau diese Felder.
    * **kein `Bearbeitet`-Vermerk** — der Verlauf datiert sich selbst.
    * **die Archivsperre gilt nicht.** `SWR-077` sperrt `done`/`rejected` gegen
      **Änderungen**; DoD 6 des Tickets sagt den Grund: *die Sperre gilt dem Formular,
      nicht dem Gespräch.* Eine erledigte Aufgabe ist der häufigste Anlass für eine
      Rückfrage, und ein Kanal, der genau dort schweigt, ist keiner.

    ⚠ **Neuester Beitrag zuerst** (DoD 5, wie im Team-Chat bestellt, `SWR-083`): der
    neue Kopf steht **direkt unter** der Überschrift, die alten rutschen nach unten.

    ⚠ Der Zeitstempel kommt aus `zeitpunkt()` — **eine** Zeitquelle (`SWR-084`). Eine
    zweite Implementierung wäre nach B025 ein künftiger Befund.

    ⚠ Der Konfliktschutz ist derselbe wie am Editor (`SWR-080`): die Routine-Session
    schreibt in dieselben Dateien, und ein Fingerabdruck ist der einzige Weg, ein
    stilles Überschreiben zu bemerken. `None` heißt „nicht geprüft" und ist den
    Aufrufern vorbehalten, die keinen Client-Zustand haben.

    Gibt {"fingerprint", "zeitpunkt", "beitraege"} zurück; wirft `KonfliktFehler`
    bzw. `ValueError`.
    """
    beitrag = str(text or "").replace("\r\n", "\n").strip()
    if not beitrag:
        raise ValueError("Ein Kommentar ohne Text ist keiner — bitte etwas schreiben.")
    absender = str(von or "").strip() or "Mensch via HMI"
    if "\n" in absender:
        raise ValueError("Absender darf keine Zeilenumbrüche enthalten")
    alt_text, t = lies_ticket(repo, tid)
    ist = fingerprint(alt_text)
    if erwarteter_fingerprint and erwarteter_fingerprint != ist:
        raise KonfliktFehler(
            f"{tid} wurde inzwischen von einer anderen Stelle geändert (sehr wahrscheinlich "
            f"die laufende Routine-Session). Dein Beitrag wurde NICHT gespeichert, damit "
            f"nichts still überschrieben wird — bitte das Ticket neu laden und den Beitrag "
            f"erneut eintragen.")
    stempel = zeitpunkt(jetzt)
    kopf = re.match(r"^---\n.*?\n---\n", alt_text, re.S).group(0)
    body = t.get("_body", "")
    neuer_kopf = KOMMENTAR_FORMAT % (absender, stempel)
    if KOMMENTAR_UEBERSCHRIFT in body:
        vorher, nachher = body.split(KOMMENTAR_UEBERSCHRIFT, 1)
        body = (vorher + KOMMENTAR_UEBERSCHRIFT + "\n\n" + neuer_kopf + "\n\n" + beitrag
                + "\n" + nachher.lstrip("\n").rstrip() + "\n").rstrip()
    else:
        body = (body.rstrip() + "\n\n" + KOMMENTAR_UEBERSCHRIFT + "\n\n"
                + neuer_kopf + "\n\n" + beitrag).strip()
    neu_text = kopf + "\n" + body + "\n"
    # ⚠ Vollvalidierung mit GENAU denselben Regeln wie jeder andere Schreibpfad. Ein
    # Kommentar darf das Ticket nicht ungültig machen — und weil er das Frontmatter
    # nicht anfasst, ist ein Fehler hier ein Befund über den BESTAND und nicht über
    # den Beitrag. Er wird trotzdem gemeldet statt geschluckt.
    tickets, probleme = lade_tickets(repo)
    entwurf, err = parse_frontmatter(neu_text)
    if err:
        raise ValueError(f"{tid}: {err}")
    entwurf["_datei"] = f"{tid}.md"
    tickets = [entwurf if x.get("id") == tid else x for x in tickets]
    probleme += validiere_alle(tickets, repo, git_pruefen=False)
    if probleme:
        raise ValueError("; ".join(probleme))
    if entwurf.get("status") != t.get("status"):  # kann nicht passieren — deshalb geprüft
        raise ValueError(f"{tid}: ein Kommentar hat den Status verändert — abgebrochen")
    open(ticket_pfad(repo, tid), "w", encoding="utf-8", newline="\n").write(neu_text)
    # ⚠ **BOARD.md wird NICHT neu geschrieben.** Es zeigt Frontmatter-Felder, und der
    # Kommentar ändert keines. Es trotzdem zu regenerieren hieße, bei jedem Beitrag
    # die `Stand:`-Zeile zu bewegen — genau die Sorte Rauschen, für die `SWR-110`
    # eigens eine Ausnahme bauen musste.
    return {"fingerprint": fingerprint(neu_text), "zeitpunkt": stempel,
            "beitraege": len(_KOMMENTAR_KOPF.findall(body))}


def kommentare(repo, tid):
    """[{von, zeit, text}] — der Verlauf eines Tickets, neueste zuerst.

    Der Leser zur Konstante oben. Er parst denselben Text, den `kommentiere` schreibt,
    und ist damit die Gegenprobe zum Schreiber: laufen die beiden auseinander, wird
    diese Funktion leer — und eine Zusicherung sieht es.
    """
    _text, t = lies_ticket(repo, tid)
    body = t.get("_body", "")
    if KOMMENTAR_UEBERSCHRIFT not in body:
        return []
    abschnitt = body.split(KOMMENTAR_UEBERSCHRIFT, 1)[1]
    treffer = list(_KOMMENTAR_KOPF.finditer(abschnitt))
    ergebnis = []
    for i, m in enumerate(treffer):
        ende = treffer[i + 1].start() if i + 1 < len(treffer) else len(abschnitt)
        ergebnis.append({"von": m.group("von"), "zeit": m.group("zeit"),
                         "text": abschnitt[m.end():ende].strip()})
    return ergebnis


def _status_cli(argv):
    """`board.py <repo> status T-xxxx <neu> [--reviewer r] [--notiz t] [--meldung m]`.

    T-0062, erweitert um SWR-139: mit `--meldung` ist der Wechsel **ein** Vorgang —
    geschrieben und gebucht. Ohne sie bleibt es beim alten Verhalten, denn der Aufrufer,
    der mitten in seiner eigenen Transaktion steckt, darf nicht dazwischen committen.
    """
    repo, rest = argv[0], argv[2:]
    reviewer = notiz = meldung = None
    head_pruefen = True
    pos = []
    i = 0
    while i < len(rest):
        if rest[i] == "--reviewer":
            reviewer, i = rest[i + 1], i + 2
        elif rest[i] == "--notiz":
            notiz, i = rest[i + 1], i + 2
        elif rest[i] == "--meldung":
            meldung, i = rest[i + 1], i + 2
        elif rest[i] == "--ohne-head-pruefung":
            head_pruefen, i = False, i + 1
        else:
            pos.append(rest[i])
            i += 1
    if len(pos) != 2:
        print("Nutzung: board.py <repo> status T-xxxx <neu> [--reviewer r] "
              "[--notiz text] [--meldung commit-text] [--ohne-head-pruefung]")
        return 2
    try:
        setze_status(repo, pos[0], pos[1], reviewer, notiz, meldung=meldung,
                     head_pruefen=head_pruefen)
    except ValueError as e:
        print(f"STATUS ABGELEHNT: {e}")
        return 1
    gebucht = " und GEBUCHT" if meldung else ""
    print(f"OK: {pos[0]} -> {pos[1]}, BOARD.md aktualisiert{gebucht}.")
    return 0


def main(argv):
    if len(argv) >= 2 and argv[1] == "status":
        return _status_cli(argv)
    args = [a for a in argv if not a.startswith("--")]
    repo = args[0] if args else "."
    nur_check = "--check" in argv
    git_pruefen = "--no-git" not in argv
    tickets, probleme = lade_tickets(repo)
    probleme += validiere_alle(tickets, repo, git_pruefen)
    if probleme:
        print("VALIDIERUNG FEHLGESCHLAGEN:", *probleme, sep="\n  ")
        return 1
    if not nur_check:
        with open(os.path.join(repo, "BOARD.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(generiere_board(tickets))
        print(f"OK: {len(tickets)} Tickets validiert, BOARD.md aktualisiert.")
    else:
        print(f"OK: {len(tickets)} Tickets validiert (Check-Modus, BOARD.md unverändert).")
    return 0


if __name__ == "__main__":
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import konsole
    konsole.sichere_ausgabe()  # platform/T-0009: am Melden nicht sterben
    sys.exit(main(sys.argv[1:]))
