"""BCK-Sprint (SWR-103, pm/T-0016 nach pm/D006).

Mit `pm/D006` ist **jeder** Routine-Lauf ein vollwertiger Genesis-Gesamtsprint: der PM
sichtet alle offenen Aufgaben aller Repos und terminiert sie in
`pm/management/sprint-aktuell.md`. Diese Workflow-Sicht gab es bisher nur als Datei —
kein HMI-Endpunkt hat sie ausgeliefert.

Dieses Modul erzeugt **keinen** zweiten Plan. Es liest dieselbe Datei, die die Session
ohnehin schreibt (eine zweite Quelle wäre B033).

**Der Zeitstempel kommt aus dem Commit, nicht aus dem Text** — dieselbe Regel wie bei
SWR-102, und aus demselben Grund: fällt ein geplanter Lauf aus, bleibt die Datei stehen,
und ihre eigene „Stand:"-Zeile behauptete weiter Frische (B038). Die Staleness-Logik wird
deshalb aus `session` **importiert** und nicht abgeschrieben.

**Der Punkt, an dem diese Sicht mehr tut als abschreiben.** Die Plantabelle ist von Hand
geschrieben — sie ist eine *Entscheidung* des PM (welches Ticket in diesen Sprint geht)
und hat im Ticket kein Feld. Genau darum kann sie vom Bestand abdriften: ein Ticket, das
nach dem Schreiben entsteht, fehlt im Plan und fällt niemandem auf. Deshalb prüft
`plan()` den Plan **gegen die entdeckten Repos** und meldet jedes offene Ticket, das in
keiner Planzeile vorkommt (`nicht_geplant`). Der Anlass ist belegt: `pm/T-0016` — das
Ticket, aus dem dieses Modul stammt — war das einzige unterminierte Ticket der
Organisation und stand in keiner Agendaliste (vierter Auftritt von B049).

Kein Zustand, kein Cache (SWR-024): jede Anfrage liest frisch aus Datei und Git.
"""
import os
import re
import sys
from datetime import date as _datum

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import board  # noqa: E402
import sprint_register  # noqa: E402  — der Sprintzähler (SWR-106)

from . import aggregation  # noqa: E402
from . import session  # noqa: E402

QUELLE_PROJEKT = "pm"
QUELLE_DATEI = "management/sprint-aktuell.md"

# Die Überschrift wird an ihrem **Anfang** erkannt, nicht an ihrer vollen Fassung: was
# dahinter in Klammern steht, ändert sich je Session. Wo ein Parser ein Format liest, das
# andere Teile des Systems schreiben, darf er nicht auf den Wortlaut zielen —
# Lehre L-2026-08-16h/B054, die am 16.08. 10 von 30 Briefen unlesbar gemacht hat.
PLAN_KOPF = re.compile(r"(?m)^#{2,6}\s+Sprint-Plan\b.*$")

# Benannte Zustände der Spalte „Fällig". Sie sind **keine** Datumsangaben und dürfen
# deshalb nie die grüne Ampel bekommen: „grün" heißt „Termin liegt komfortabel in der
# Zukunft" und wäre bei „wartet-auf-Mensch" eine Aussage, die niemand zugesagt hat (B038).
ZUSTAND_SPRINT = "sprint"      # „dieser Sprint"
ZUSTAND_MENSCH = "mensch"      # „wartet-auf-Mensch"
ZUSTAND_TERMIN = "termin"      # ein echtes Datum
ZUSTAND_NUMMER = "sprint_nr"   # SWR-106: „Sprint 4" — die Planeinheit ab 2026-08-17
ZUSTAND_OFFEN = "unbekannt"    # weder das eine noch das andere

# SWR-106: Wie weit voraus eine Sprintnummer noch eine Zusage ist. Bei stündlichem Takt
# sind 24 Sprints ein Tag; eine Nummer 150 Läufe voraus wäre eine Scheingenauigkeit, die
# bei jedem Lauf neu geschrieben werden müsste. Bis `HORIZONT` Sprints voraus gilt eine
# Nummer als **fest**, dahinter als **Warteschlange** — dieselbe Zahl, ehrlich beschriftet.
HORIZONT = 2

_SPRINT_NR = re.compile(r"(?i)\bsprint\s*(\d{1,6})\b")
_SPRINT_WORT = re.compile(r"dies\w*\s+sprint", re.I)
# SWR-106: Takt-Dauerläufer laufen in JEDEM Sprint, also auch in diesem. Sie bekommen
# bewusst keine Nummer — das Feld `takt` sagt es bereits, und eine Nummer daneben wäre
# eine zweite Aussage über dieselbe Sache (B033). Ohne dieses Muster fielen sie in
# „unbekannt" und sähen ungeplant aus, obwohl sie die am festesten geplanten Aufgaben
# der Organisation sind.
_TAKT_WORT = re.compile(r"jede[rmns]?\s+sprint|je\s+(sprint|session|lauf)", re.I)
_MENSCH_WORT = re.compile(r"wartet[\s-]*auf[\s-]*mensch", re.I)
_TICKET_REF = re.compile(r"([A-Za-z0-9_.-]+)/(T-\d{4})|(T-\d{4})")

# SWR-115 (pm/T-0049): Wortlaute der **Statusspalte** der Plantabelle. Sie ist die einzige
# Spalte, die bis Sprint 8 gegen nichts gehalten wurde — `plan_drift` vergleicht die
# Sprintnummer, `sprint_vergangen` die Gegenwart, `nicht_geplant` das Vorkommen.
#
# Bewusst zwei geschlossene Mengen statt einer Heuristik: was hier nicht steht, wird
# **ignoriert** und nicht geraten. Ein Ratefehler in dieser Prüfung wäre ein Fehlalarm über
# einen korrekt geführten Plan — und ein Fehlalarm trainiert das Wegsehen (dieselbe Sorge
# wie SWR-109, SWR-110 und SWR-112).
PLAN_FERTIG = ("erledigt", "fertig", "geschlossen", "done", "abgeschlossen")
PLAN_OFFEN = ("offen", "open", "in arbeit", "in_progress", "in bearbeitung",
              "blockiert", "blocked", "vorgelegt", "geplant", "in review", "in_review")

# SWR-115: „erfüllt" ist der Wortlaut der Takt-Dauerläufer und steht in KEINER der beiden
# Mengen. Ein Dauerläufer wird nie `done` — er trägt dauerhaft „erfüllt" im Plan und `open`
# im Ticket, und **beides ist richtig**. Ohne diese Ausnahme meldete die Prüfung an ihrem
# ersten Tag sechs Fehlalarme.
# SWR-205 (platform/T-0054): ALIAS auf `board.STATUS_FINAL` — siehe dort.
TICKET_GESCHLOSSEN = board.STATUS_FINAL



def _zellen_text(zelle):
    """Markdown-Auszeichnung aus einer Tabellenzelle nehmen (Fett, Code, Links)."""
    s = str(zelle or "")
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"\*\*([^*]*)\*\*", r"\1", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    return s.strip()


def plan_tabelle(text):
    """Die Plantabelle aus dem Text schneiden (rein, ohne IO).

    ⚠⚠ **SWR-226 (Sprint 39): die Tabelle wird an ihren SPALTEN erkannt, nicht an ihrer
    STELLE.** Bis Sprint 39 galt „die **erste** Tabelle nach der Sprint-Plan-Überschrift" —
    und genau daran ist dieses Haus **zweimal** hängengeblieben:

    * **Sprint 37:** eine Befund-Tabelle stand vor der Plantabelle. `plan_drift` meldete
      **0**, weil keine einzige Planzeile geparst wurde. Aufgefallen ist es nur an
      `nicht_geplant: 39`.
    * **Sprint 39:** derselbe Fehler, derselbe Autor-Typ, dieselbe Datei — obwohl die
      Lehre aus Sprint 37 im Bericht stand. Wieder gefunden von `nicht_geplant: 33`.

    > **Eine Lehre, die zweimal denselben Fehler nicht verhindert hat, ist keine Lehre,
    > sondern eine Notiz. Der Vertreter ist diese Funktion.**

    Gesucht wird deshalb ab der Überschrift die erste Tabelle, deren Kopfzeile **sowohl**
    eine „Aufgabe"- **als auch** eine „Fällig"-Spalte trägt — die beiden Spalten, ohne die
    eine Planzeile nichts aussagen kann. Tabellen davor werden übersprungen, statt den
    Plan zu ersetzen.

    ⚠ Findet sich **keine** solche Tabelle, ist das Ergebnis `None` und **nicht** die
    erste beliebige: die Sicht sagt dann, dass sie keinen Plan gefunden hat. Ein
    stillschweigender Rückfall auf „irgendeine Tabelle" wäre wieder genau der Zustand, in
    dem eine Prüfung grün meldet, weil sie nichts gelesen hat.
    """
    m = PLAN_KOPF.search(text or "")
    if not m:
        return None
    for tabelle in aggregation.parse_md_tabellen(text[m.end():]):
        spalten = (tabelle or {}).get("spalten") or []
        if (_spalte(spalten, "aufgabe") is not None
                and _spalte(spalten, "fällig", "faellig") is not None):
            return tabelle
    return None


def _spalte(spalten, *namen):
    """Index der ersten Spalte, deren Kopf mit einem der Namen beginnt (tolerant)."""
    for i, s in enumerate(spalten):
        kopf = _zellen_text(s).lower()
        for n in namen:
            if kopf.startswith(n):
                return i
    return None


def faellig_zustand(wert, heute=None):
    """Spalte „Fällig" -> (zustand, ampel). EINE Regel für alle Zeilen.

    Für echte Datumsangaben wird `board.frist_ampel` benutzt — die Ampelregel steht seit
    SWR-091 an einer Stelle, und sie hier ein zweites Mal zu schreiben wäre wörtlich
    B033. Die benannten Zustände bekommen eigene Werte statt einer Farbe, die eine
    Terminaussage vortäuscht.
    """
    s = _zellen_text(wert)
    if _SPRINT_WORT.search(s) or _TAKT_WORT.search(s):
        return ZUSTAND_SPRINT, "sprint"
    if _MENSCH_WORT.search(s):
        return ZUSTAND_MENSCH, "mensch"
    # SWR-106: „Sprint 4" ist die Planeinheit, kein Datum — und bekommt deshalb wie die
    # anderen benannten Zustände keine Datumsampel. Die Reihenfolge ist Absicht: der
    # Wortlaut wird VOR dem Datumsmuster geprüft, damit eine Zelle wie „Sprint 4 (bis
    # 23.08. zugesagt)" als Sprint gilt und nicht als Termin. Was zugesagt ist, steht im
    # Feld `frist` des Tickets; was geplant ist, hier.
    nr = _SPRINT_NR.search(s)
    if nr:
        return ZUSTAND_NUMMER, "sprint"
    treffer = re.search(r"\d{4}-\d{2}-\d{2}", s)
    if treffer:
        return ZUSTAND_TERMIN, board.frist_ampel(treffer.group(0), heute)
    return ZUSTAND_OFFEN, "grau"


def sprint_nummer(wert):
    """SWR-106: Die Sprintnummer einer „Fällig"-Zelle -> int oder None."""
    m = _SPRINT_NR.search(_zellen_text(wert))
    return int(m.group(1)) if m else None


def horizont(nr, jetzt_nr):
    """SWR-106: Ist diese Nummer **fest geplant** oder **Warteschlange**?

    Der Auftraggeber hat den Horizont so gewählt (2026-08-17): die nächsten Sprints
    tragen feste Zuordnungen, alles dahinter ist eine geordnete Reihenfolge. Beide
    Angaben sind dieselbe Zahl — der Unterschied ist die **Verbindlichkeit**, und die
    auszusprechen ist billiger, als sie zu suggerieren (B038).
    """
    if nr is None or not jetzt_nr:
        return ""
    if nr <= jetzt_nr:
        return "jetzt"
    return "fest" if nr <= jetzt_nr + HORIZONT else "warteschlange"


# SWR-154 (pm/N-0043 Punkt 2): die Kapitel des Plans, in Anzeigereihenfolge.
#
# ⚠ **Die ersten beiden erscheinen AUCH LEER.** Ein leeres Kapitel sagt „hier ist nichts
# geplant"; ein fehlendes ist von „das haben wir nicht nachgesehen" nicht zu
# unterscheiden. Dieselbe Entscheidung hat SWR-114 für die Preflight-Zeile und SWR-117
# für den Org-Kopfblock bereits getroffen — hier zum dritten Mal, aus demselben Grund.
#
# ⚠ Die übrigen drei erscheinen **nur mit Inhalt**. Das ist keine Inkonsequenz, sondern
# der Wortlaut des Auftrags: *„und ggf. spätere Sprints, fall aufgaben geplant sind"*.
# „Aktuell" und „nächster" sind Fragen, die immer gestellt werden; „später", „Takt" und
# „ohne Sprintbezug" sind Behälter, die es nur gibt, wenn etwas darin liegt.
KAPITEL_AKTUELL = "aktuell"
KAPITEL_NAECHSTER = "naechster"
KAPITEL_SPAETER = "spaeter"
KAPITEL_TAKT = "takt"
KAPITEL_OHNE = "ohne"

KAPITEL_REIHENFOLGE = (KAPITEL_AKTUELL, KAPITEL_NAECHSTER, KAPITEL_SPAETER,
                       KAPITEL_TAKT, KAPITEL_OHNE)
KAPITEL_IMMER = (KAPITEL_AKTUELL, KAPITEL_NAECHSTER)


def kapitel(faellig, jetzt_nr):
    """SWR-154: In welches Kapitel gehört diese Planzeile? -> Schlüssel oder "".

    Gelesen wird die **Fällig-Zelle**, dieselbe Eingabe wie bei `faellig_zustand` und
    `sprint_nummer` — kein zweiter Erhebungsweg (B033).

    ⚠ **Takt zuerst.** `faellig_zustand` faltet „dieser Sprint" und „jeder Sprint" in
    denselben Zustand `sprint`, und das ist dort richtig: beide sind in diesem Lauf
    fällig. Für die Kapitel ist der Unterschied genau der Punkt — ein Dauerläufer gehört
    nicht unter eine Sprintnummer, weil er in **jedem** Sprint läuft. Die Reihenfolge
    dieser beiden Prüfungen ist deshalb Absicht und keine Laune.

    ⚠ **Ohne bekannte Sprintnummer gibt es keine Kapitel.** `jetzt_nr == 0` heißt, das
    Register ist nicht lesbar. „Sprint 0 (aktuell)" wäre eine Behauptung, die niemand
    getroffen hat (B038) — die Sicht bleibt dann bei ihrer flachen Tabelle.
    """
    if not jetzt_nr:
        return ""
    s = _zellen_text(faellig)
    if _TAKT_WORT.search(s):
        return KAPITEL_TAKT
    if _SPRINT_WORT.search(s):
        return KAPITEL_AKTUELL
    nr = sprint_nummer(s)
    if nr is None:
        # Datum, „wartet-auf-Mensch" oder gar nichts. ⚠ Solche Zeilen kommen NICHT nach
        # „Später": das wäre eine Aussage über einen Sprint, die im Plan nicht steht. Sie
        # bekommen ihr eigenes Kapitel, das nur erscheint, wenn es Zeilen hat.
        return KAPITEL_OHNE
    if nr <= jetzt_nr:
        return KAPITEL_AKTUELL
    if nr == jetzt_nr + 1:
        return KAPITEL_NAECHSTER
    return KAPITEL_SPAETER


def kapitel_koepfe(plan_zeilen, jetzt_nr):
    """SWR-154: die Kapitelüberschriften in Anzeigereihenfolge, mit Nummer im Titel.

    Der **Server** entscheidet die Zuordnung und liefert sie mit; die Ansicht gruppiert
    nur noch. `sprint_nr == jetzt + 1` in JavaScript wäre eine zweite Antwort auf die
    Frage „welcher ist der nächste Sprint?" neben der, die seit SWR-144 im Payload steht
    (`naechster_sprint`) — und sie wäre genau dann falsch, wenn zwischen Laden und Klick
    ein Sprint gewechselt hat (ADR-P11-001, B033).
    """
    if not jetzt_nr:
        return []
    anzahl = {k: 0 for k in KAPITEL_REIHENFOLGE}
    for z in plan_zeilen:
        k = z.get("kapitel")
        if k in anzahl:
            anzahl[k] += 1
    titel = {KAPITEL_AKTUELL: "Sprint %d (aktuell)" % jetzt_nr,
             KAPITEL_NAECHSTER: "Sprint %d (nächster)" % (jetzt_nr + 1),
             KAPITEL_SPAETER: "Später",
             KAPITEL_TAKT: "Jeder Sprint (Takt)",
             KAPITEL_OHNE: "Ohne Sprintbezug"}
    nummer = {KAPITEL_AKTUELL: jetzt_nr, KAPITEL_NAECHSTER: jetzt_nr + 1}
    koepfe = []
    for k in KAPITEL_REIHENFOLGE:
        if not anzahl[k] and k not in KAPITEL_IMMER:
            continue
        koepfe.append({"schluessel": k, "titel": titel[k],
                       "sprint_nr": nummer.get(k), "anzahl": anzahl[k]})
    return koepfe


def wartet_auf_mensch(*zellen):
    """Wartet diese Zeile auf eine Handlung des Menschen? (quer zum Termin)

    **Termin und Zuständigkeit sind zwei Fakten, nicht einer.** `pm/T-0034` trägt ein
    Datum (17.08.) *und* wartet auf den Host; beides in einen Zustand zu falten,
    verliert eine der beiden Aussagen. Genau dieser Fehler steckte in der ersten Fassung
    dieses Moduls: der Zähler meldete `wartet_auf_mensch = 1`, während der Klartext
    derselben Datei „5 warten auf eine Handlung am Host" sagte — gefunden erst beim Lauf
    gegen den **echten** Bestand, nicht gegen Testdaten (Regel 1 aus L-2026-08-16h).
    Es ist dieselbe Familie wie B053: ein Feld mit zwei Bedeutungen.

    Gelesen wird deshalb über mehrere Spalten (Fälligkeit **und** Status), und das
    Ergebnis steht als eigenes Merkmal neben dem Zustand, nicht an seiner Stelle.
    """
    return any(_MENSCH_WORT.search(_zellen_text(z)) for z in zellen)


def refs_der_zeile(text):
    """Alle Ticket-Kennungen einer Zelle — `repo/T-xxxx` und die nackte Form `T-xxxx`.

    Beide Schreibweisen zählen, weil der Plan von Hand geschrieben wird und eine
    Sicht, die an der Schreibweise scheitert, ein Ticket fälschlich als ungeplant
    meldet. Ein Fehlalarm in dieser Liste ist teurer als ein toleranter Vergleich:
    er trainiert das Wegschauen.
    """
    gefunden = set()
    for m in _TICKET_REF.finditer(text or ""):
        if m.group(1):
            gefunden.add("%s/%s" % (m.group(1), m.group(2)))
            gefunden.add(m.group(2))
        elif m.group(3):
            gefunden.add(m.group(3))
    return gefunden


def zeilen(tabelle, heute=None, jetzt_nr=0):
    """Plantabelle -> Liste von Zeilen mit Zustand, Ampel und (SWR-106) Sprintnummer."""
    if not tabelle:
        return []
    sp = tabelle.get("spalten", [])
    i_auf = _spalte(sp, "aufgabe", "repo", "ticket") or 0
    i_rolle = _spalte(sp, "rolle")
    i_faellig = _spalte(sp, "fällig", "faellig", "frist", "termin")
    i_status = _spalte(sp, "status")
    i_grund = _spalte(sp, "grund", "begründung", "begruendung", "nächster", "naechster")

    def hole(z, i):
        return _zellen_text(z[i]) if i is not None and i < len(z) else ""

    ergebnis = []
    for z in tabelle.get("zeilen", []):
        aufgabe = hole(z, i_auf)
        faellig = hole(z, i_faellig)
        status = hole(z, i_status)
        zustand, ampel = faellig_zustand(faellig, heute)
        nr = sprint_nummer(faellig)
        ergebnis.append({"aufgabe": aufgabe,
                         "refs": sorted(refs_der_zeile(aufgabe)),
                         "rolle": hole(z, i_rolle),
                         "faellig": faellig,
                         "zustand": zustand,
                         "ampel": ampel,
                         "sprint_nr": nr,                      # SWR-106
                         "horizont": horizont(nr, jetzt_nr),   # fest / warteschlange
                         "kapitel": kapitel(faellig, jetzt_nr),  # SWR-154
                         "wartet_auf_mensch": wartet_auf_mensch(faellig, status),
                         "status": status,
                         "grund": hole(z, i_grund)})
    return ergebnis


def offene_tickets(root):
    """Alle offenen Tickets aller entdeckten Repos — die Gegenprobe zum Plan.

    „Offen" heißt hier: Status weder `done` noch `rejected`. Takt-Tickets sind
    ausdrücklich **enthalten**: sie sind Dauerpflichten und gehören in jeden Sprint;
    dass sie kein Datum tragen, macht sie nicht planlos.
    """
    treffer = []
    for name in aggregation.projekte(root):
        try:
            tickets, _ = board.lade_tickets(aggregation.projekt_pfad(root, name))
        except (ValueError, OSError):
            continue
        for t in tickets:
            if t.get("status") in TICKET_GESCHLOSSEN:
                continue
            treffer.append({"projekt": name, "id": t.get("id", ""),
                            "ref": aggregation.ref(name, t.get("id", "")),
                            "titel": t.get("titel", ""),
                            "status": t.get("status", ""),
                            "typ": t.get("typ", ""),      # SWR-112: DRs sind ausgenommen
                            "frist": t.get("frist", ""),
                            "takt": t.get("takt", ""),
                            "geplant_sprint": t.get("geplant_sprint", ""),  # SWR-106
                            # SWR-198: die Sperre gehört in die flache Zeile und nicht
                            # nur nach `_ticket`. `plan()` entfernt `_ticket` vor der
                            # Auslieferung; ohne dieses Feld wäre `blocked_by` für jeden
                            # Leser des Payloads unsichtbar, und `board.gesperrt` hätte
                            # auf der ausgelieferten Zeile eine andere Antwort als auf
                            # der internen — zwei Antworten auf eine Frage (B033).
                            "blocked_by": t.get("blocked_by", ""),
                            # SWR-132 (pm/T-0064, Brief pm/N-0042): die Rollen-Sicht des
                            # Auftraggebers. ⚠ `rolle` und `verantwortlich` bleiben
                            # **getrennte Felder** und werden nicht zu einem verschmolzen:
                            # die Fachrolle (`pl`, `dev`, `cm`, …) und die Frage „handelt
                            # der Mensch oder das Team?" sind zwei Fragen. Ihre
                            # Verschmelzung war der Befund, der zu SWR-116 führte — dort
                            # trug `rolle: mensch` eine zweite, verhaltensändernde
                            # Bedeutung. `verantwortlich` kommt aus
                            # `board.verantwortlich_wert` (dem Auflösungspunkt aus
                            # SWR-116) und nicht aus dem Rohfeld, damit die Liste und die
                            # Board-Spalte nicht verschieden lesen, was leer bedeutet.
                            "rolle": t.get("rolle", ""),
                            "verantwortlich": board.verantwortlich_wert(t),
                            "prio": t.get("prio", ""),
                            "_ticket": t})
    return treffer


def widersprueche(offene, jetzt_nr, takt_min=60, heute=None):
    """SWR-106: Tickets, deren geplanter Sprint nach ihrer eigenen Frist läge.

    Der Auftraggeber führt `frist` und `geplant_sprint` **parallel** (2026-08-17). Das
    ist zulässig, solange beide verschiedene Fragen beantworten — die Zusage nach außen
    und der Lauf, in dem das Team es anfasst. Es ist **nicht** zulässig, wenn sie sich
    widersprechen, und ein Widerspruch fiele hier niemandem auf: die Frist bliebe grün,
    bis sie reißt, und die Sprintnummer bliebe plausibel, weil sie keiner gegen die
    Frist hält. Deshalb prüft die Sicht es und zeigt es **über** der Tabelle — dieselbe
    Regel wie bei `nicht_geplant` (SWR-103): Was fehlt oder klemmt, steht vor dem, was
    stimmt, nicht dahinter.
    """
    treffer = []
    for o in offene:
        t = o.get("_ticket") or {}
        text = board.sprint_widerspruch(t, jetzt_nr, takt_min, heute)
        if text:
            treffer.append({"ref": o["ref"], "titel": o["titel"], "meldung": text})
    return treffer


def nicht_geplant(plan_zeilen, offene):
    """Offene Tickets, die in KEINER Planzeile vorkommen (SWR-103, Kern der DoD).

    Ohne diesen Abgleich wäre die Sicht eine hübschere Abschrift einer Tabelle und
    hätte genau den Befund nicht finden können, der sie ausgelöst hat: `pm/T-0016`
    stand in keiner Liste und war deshalb für niemanden überfällig (B049/B044).
    """
    bekannt = set()
    for z in plan_zeilen:
        bekannt.update(z.get("refs", []))
    fehlend = []
    for t in offene:
        if t["ref"] in bekannt or t["id"] in bekannt:
            continue
        fehlend.append(t)
    return fehlend


def plan_drift(plan_zeilen, offene):
    """SWR-109: Planzeilen, die einen ANDEREN Sprint nennen als das Ticket selbst.

    `nicht_geplant` fragt, ob ein offenes Ticket **vorkommt**. Diese Prüfung fragt, ob
    der Plan dasselbe **sagt** wie das Ticket. Der Unterschied ist nicht akademisch: ein
    Ticket, das im Plan steht und dort eine andere Nummer trägt, ist für `nicht_geplant`
    einwandfrei und für jeden Leser trotzdem falsch terminiert.

    Anlass (Befund 2026-08-17, Sprint 6): Sprint 5 hat fünf Aufgaben in der Plandatei
    „je eine Nummer nach hinten" geschoben und die Ticketfelder nicht angefasst. Sieben
    Zeilen sagten danach etwas anderes als ihr Ticket — unbemerkt, weil beide Quellen
    für sich stimmig aussahen. Genau die Schwäche, die beim Beschluss zu `frist` neben
    `geplant_sprint` benannt worden war (B033): zwei Angaben zu derselben Frage driften.

    Takt-Dauerläufer sind ausgenommen und das ist keine Nachlässigkeit: sie tragen
    absichtlich kein `geplant_sprint` (eine Nummer neben `takt: je-session` wäre selbst
    eine Doppelaussage), und ihre Planzeile sagt „jeder Sprint".
    """
    # Die volle Referenz (`p11/T-0003`) ist eindeutig, die nackte ID (`T-0003`) ist es
    # NICHT: sie kommt in p11 und p12 gleichzeitig vor. Eine nackte ID wird deshalb nur
    # aufgelöst, wenn sie im Bestand genau einmal vorkommt — sonst ordnete die Prüfung
    # eine Planzeile dem falschen Ticket zu und meldete einen Drift, den es nicht gibt.
    # (Gefunden beim ersten Lauf gegen den echten Bestand, nicht beim Schreiben.)
    nach_ref = {t["ref"]: t for t in offene}
    haeufigkeit = {}
    for t in offene:
        haeufigkeit[t["id"]] = haeufigkeit.get(t["id"], 0) + 1
    for t in offene:
        if haeufigkeit[t["id"]] == 1:
            nach_ref.setdefault(t["id"], t)
    treffer = []
    for z in plan_zeilen:
        nr = z.get("sprint_nr")
        if nr is None:                      # „dieser Sprint", „wartet-auf-Mensch", Takt
            continue
        # SWR-176: Nennt die Zeile ein Repo, gilt NUR die qualifizierte Form. Die nackte
        # ID ist der Notnagel fuer handgeschriebene Zeilen ohne Repo - sie darf ein
        # ausdruecklich genanntes Repo nicht ueberstimmen.
        # Der Anlass, gemessen in Sprint 27: die Planzeile `p9/T-0008` (geschlossen, also
        # nicht in `offene`) fiel auf die nackte `T-0008` zurueck, und die war unter den
        # OFFENEN Tickets eindeutig - `promt-team/T-0008`. Gemeldet wurde ein Drift
        # zwischen einer Zeile und einem Ticket, die nichts miteinander zu tun haben.
        # Die Eindeutigkeit ist ueber die OFFENEN Tickets geprueft, die Zeile gehoerte
        # einem GESCHLOSSENEN. Eine ID wird nicht dadurch eindeutig, dass die Restmenge
        # klein ist. Das Schwestermodul `statusdrift` loest ueber ALLE Tickets auf und
        # ist deshalb nie in diese Falle gelaufen - dieselbe Frage, zwei Grundmengen.
        refs = sorted(z.get("refs", []))
        qualifiziert = [r for r in refs if "/" in r]
        ticket = next((nach_ref[r] for r in (qualifiziert or refs) if r in nach_ref), None)
        if ticket is None:
            continue
        gefeldert = str(ticket.get("geplant_sprint", "")).strip()
        if not gefeldert:                   # Takt-Dauerläufer: kein Feld, kein Widerspruch
            continue
        if gefeldert != str(nr):
            treffer.append({"ref": ticket["ref"], "titel": ticket["titel"],
                            "plan": nr, "ticket": gefeldert,
                            "meldung": "Plan sagt Sprint %s, Ticket sagt Sprint %s"
                                       % (nr, gefeldert)})
    return treffer


def sprint_vergangen(offene, jetzt_nr):
    """SWR-112 (pm/T-0045): offene Tickets, deren geplanter Sprint VORBEI ist.

    Die Lücke, die dieses Ticket beschreibt: `widersprueche` (SWR-106) hält den
    geplanten Sprint gegen die **Frist** des Tickets, `plan_drift` (SWR-109) gegen die
    **Planzeile** — niemand hielt ihn gegen die **Gegenwart**. Beim Start von Sprint 6
    standen zwei Tickets auf Sprint 5, und der Abschluss meldete „unterminiert 0,
    überfällig 0". Beide Zahlen waren für sich richtig; nur die Terminierung zeigte in
    die Vergangenheit.

    Drei Abgrenzungen, die dieses Ticket ausdrücklich zur Entscheidung gestellt hat:

    1. **Erledigte Tickets sind kein Fall.** `offene_tickets` liefert nur, was weder
       `done` noch `rejected` ist; `platform/T-0009` darf für immer auf Sprint 6 stehen.
       Die Prüfung lautet deshalb nie „Sprint < jetzt", sondern immer „offen UND
       Sprint < jetzt".
    2. **`in_review` zählt mit.** Ein Ticket, das nach seinem geplanten Sprint noch beim
       Reviewer liegt, ist nicht korrekt geparkt — der Plan hat dann nicht gehalten, und
       genau das soll sichtbar werden. Ein Review ist Teil des Sprints, für den geplant
       wurde, nicht ein Zustand daneben.
    3. **`decision-request` ist ausgenommen**, und zwar nicht aus Nachsicht: ein DR liegt
       beim Menschen, das Team kann ihn nicht bewegen, und eine Sprintnummer daneben wäre
       eine Zusage, die das Team nicht halten kann. Seine Steuerung ist `frist` + `default`
       (Schweigen führt zum Default) — und reißt diese Frist, meldet ihn `ueberfaellig`
       (SWR-091). Er ist also gedeckt, nur von einer anderen Prüfung. Ohne diese Ausnahme
       hätte die Prüfung an ihrem ersten Tag `p11/T-0006` gemeldet, das seit Sprint 6
       ordnungsgemäß beim Auftraggeber liegt — ein Fehlalarm, und ein Fehlalarm an Tag
       eins trainiert das Wegsehen (dieselbe Sorge wie bei SWR-109 und SWR-110).
    4. **`status: blocked` ist ausgenommen** (SWR-198, platform/T-0051, Sprint 31) — und
       zwar aus **derselben** Begründung wie Punkt 3, nicht aus einer zweiten. Sie steht
       deshalb genau einmal, in `board.gesperrt`, und wird hier **aufgerufen** statt
       abgeschrieben: zwei Begründungen für eine Sache laufen auseinander (B033). Punkt 3
       ist der Sonderfall, den `blocked` bis Sprint 29 vertreten musste, weil es ihn noch
       nicht gab; er bleibt stehen, weil ein DR beim Menschen liegt, **ohne** gesperrt zu
       sein.
    """
    treffer = []
    for t in offene:
        if (t.get("_ticket") or {}).get("typ") == "decision-request" \
                or t.get("typ") == "decision-request":
            continue
        # SWR-198: die Begründung steht in `board.gesperrt` — hier nur der Aufruf.
        if board.gesperrt(t.get("_ticket") or t):
            continue
        roh = str(t.get("geplant_sprint", "")).strip()
        if not roh.isdigit():          # Takt-Dauerläufer und leere Felder: kein Termin
            continue
        nr = int(roh)
        if nr < jetzt_nr:
            treffer.append({"ref": t["ref"], "titel": t.get("titel", ""),
                            "status": t.get("status", ""),
                            "geplant_sprint": nr, "jetzt": jetzt_nr,
                            "meldung": "offen auf Sprint %d, laufend ist Sprint %d"
                                       % (nr, jetzt_nr)})
    return treffer


def alle_tickets(root):
    """Alle Tickets aller entdeckten Repos — **einschließlich** `done` und `rejected`.

    SWR-115 braucht die geschlossenen mit: die zweite Melderichtung („Ticket ist fertig,
    der Plan sagt offen") ist über `offene_tickets` grundsätzlich unsichtbar, weil das
    Ticket dort nicht mehr vorkommt. Genau diese Richtung hat in Sprint 7 `pm/T-0043`
    gezeigt.
    """
    treffer = []
    for name in aggregation.projekte(root):
        try:
            tickets, _ = board.lade_tickets(aggregation.projekt_pfad(root, name))
        except (ValueError, OSError):
            continue
        for t in tickets:
            treffer.append({"projekt": name, "id": t.get("id", ""),
                            "ref": aggregation.ref(name, t.get("id", "")),
                            "titel": t.get("titel", ""),
                            "status": t.get("status", ""),
                            "typ": t.get("typ", ""),
                            "takt": t.get("takt", ""),
                            "geplant_sprint": t.get("geplant_sprint", "")})
    return treffer


def _nach_ref(tickets):
    """Referenzauflösung wie in `plan_drift`: volle Ref immer, nackte ID nur wenn eindeutig.

    `T-0003` kommt in `p11` und `p12` gleichzeitig vor. Eine nackte ID wird deshalb nur
    aufgelöst, wenn sie im Bestand genau einmal vorkommt — sonst ordnete die Prüfung eine
    Planzeile dem falschen Ticket zu und meldete einen Drift, den es nicht gibt.
    """
    nach_ref = {t["ref"]: t for t in tickets}
    haeufigkeit = {}
    for t in tickets:
        haeufigkeit[t["id"]] = haeufigkeit.get(t["id"], 0) + 1
    for t in tickets:
        if haeufigkeit[t["id"]] == 1:
            nach_ref.setdefault(t["id"], t)
    return nach_ref


def plan_nachlauf(treffer, laeuft):
    """SWR-201 (platform/T-0052): trennt den GARANTIERTEN Zustand vom Befund.

    Anlass (am laufenden Betrieb gemessen, 2026-08-20/21, `ollama-schnelltakt.log`):
    **60** Läufe über **7** Sprints (25–31). In **14** davon (23 %) meldete
    `status_drift`; in **jedem einzelnen** der 7 Sprints gab es genau ein solches
    Fenster, 15–45 Minuten lang, zusammen **210 von 885** Minuten (24 %) der
    Beobachtungszeit. In 3 Läufen war die Drift der **einzige** Befund — dort und nur
    dort hätte der Tick gearbeitet, wenn sie nicht dagewesen wäre.

    **Zwei richtige Regeln, und dazwischen ein Zustand, den keine von ihnen kennt:**

    * `pm/D006` schreibt den Sprintplan am **Sprint-Abschluss** fort. Richtig — ihn nach
      jedem Ticket umzuschreiben hieße, eine Entscheidung des PM in Raten zu treffen.
    * `SWR-115` meldet jede Planzeile, die ihrem Ticket widerspricht. Richtig und teuer
      erkauft (Sprint 7, `platform/T-0010`, vierfache Falschmeldung).

    Zusammen heißt das: **sobald eine Session ihr erstes Ticket schließt und bevor sie
    ihren Plan neu schreibt, ist der Bestand widersprüchlich — per Konstruktion.** Das
    Fenster ist kein Ausrutscher, es ist die Dauer eines Sprints. Dieselbe Familie wie
    `SWR-198` aus Sprint 31: der Fehler liegt nicht IN einer Prüfung, sondern ZWISCHEN
    zweien.

    ⚠⚠ **Die Messung hat die Bauform entschieden, nicht die Bequemlichkeit.** Über
    dieselben 60 Läufe:

    | Richtung | Zeilen im Log |
    |---|---|
    | `ticket_zu_frueh_fertig` (Ticket `done`, Plan „offen") | **38** |
    | `plan_zu_frueh_fertig` (Plan „erledigt", Ticket offen) | **0** |

    **Die Richtung, die während eines laufenden Sprints garantiert auftritt, ist genau
    die HARMLOSE — und die teure aus Sprint 7 ist in 7 Sprints kein einziges Mal
    vorgekommen.** Deshalb greift die Ausnahme **nur** für
    `ticket_zu_frueh_fertig`: dort ist die Arbeit *fertig* und der Plan hinkt nach; die
    Meldung untertreibt den Fortschritt und kann keine Falschmeldung nach außen
    erzeugen. `plan_zu_frueh_fertig` behauptet Arbeit, die nicht getan ist — das ist der
    Schaden, gegen den `SWR-115` gebaut wurde, und der bleibt in **jedem** Sprint ein
    Befund.

    ⚠ **Gebunden an den laufenden Sprint und damit an etwas, das von allein endet.**
    `laeuft` ist `sprint_register.laufender(root)`; sobald der Sprint beendet ist,
    liefert es `None` und **alle** Zeilen sind wieder Befund. Eine Ausnahme, die auf ein
    Statuswort oder eine Selbstauskunft hörte, wäre ein Schlupfloch für jede unbequeme
    Planzeile (die Lehre aus `SWR-198`: an den Verweis binden, nicht an das Wort). Hier
    ist das bindende Merkmal ein Registereintrag, den die Session nicht nebenbei setzt.

    ⚠ **Stillgestellt wird nichts.** Die Nachlaufzeilen werden **namentlich** gemeldet,
    nur ohne Befundzähler — sonst wäre es `SWR-114` (eine Prüfung, die schweigt, ist von
    einer, die nicht läuft, nicht zu unterscheiden). Und weil `SWR-196` gezeigt hat, dass
    eine wahre, aber zu enge Meldung dasselbe Wegsehen trainiert wie eine falsche, nennt
    die Meldung den **Grund** (`pm/D006`) statt nur die Zeilen.

    Gibt `(befund, nachlauf)` zurück.
    """
    if not laeuft:
        return list(treffer), []
    nr = laeuft.get("nr") if hasattr(laeuft, "get") else None
    befund, nachlauf = [], []
    for t in treffer:
        # ⚠⚠ DREI Bedingungen, und jede einzelne ist im Review dieses Sprints als
        # fehlend nachgewiesen worden — die erste Fassung hatte nur die erste.
        #
        # 1. Die harmlose Richtung. `plan_zu_frueh_fertig` behauptet Arbeit, die das
        #    Ticket nicht bestätigt — der Schaden aus Sprint 7.
        # 2. **`done`, ausdrücklich NICHT `rejected`.** `TICKET_GESCHLOSSEN` enthält
        #    beide, und über diesen Weg wäre die Ausnahme ein Schlupfloch gewesen: eine
        #    Session, die ein unbequemes Ticket auf `rejected` setzt, während der Plan
        #    „offen" sagt, hätte gar keinen Befund mehr erzeugt. Ein verworfenes Ticket
        #    ist kein „fertig, Plan hinkt nach" — es ist eine Entscheidung, die der Plan
        #    abbilden muss.
        # 3. **Die Planzeile muss zum LAUFENDEN Sprint gehören.** Sonst wäre die
        #    Ausnahme an „irgendein Sprint läuft" gebunden — und während gearbeitet
        #    wird, läuft immer einer. Eine Planzeile aus Sprint 7 mit längst `done`
        #    Ticket wäre mit unterdrückt worden, und genau das verbietet die DoD von
        #    `platform/T-0052` („Wirkung für VERGANGENE Sprints nachweislich
        #    unverändert"). `sprint_nr is None` heißt „dieser Sprint" (SWR-106) und
        #    gehört dazu.
        eigener = t.get("plan_sprint") in (None, nr)
        if (t.get("richtung") == "ticket_zu_frueh_fertig"
                and t.get("ticket") == "done" and eigener):
            nachlauf.append(t)
        else:
            befund.append(t)
    return befund, nachlauf


def status_drift(plan_zeilen, alle):
    """SWR-115 (pm/T-0049): Planzeilen, deren STATUSSPALTE dem Ticket widerspricht.

    Anlass (Befund 2026-08-17, Sprint 8): Sprint 7 hat `platform/T-0010` an vier Stellen
    als erledigt gemeldet — Planzeile, Sprintabschluss, Session-Agenda und Statusbericht an
    den Auftraggeber — während das Ticket auf `open` stand. Die Arbeit **war** fertig; nur
    das Feld wurde nie umgelegt.

    **Alle drei vorhandenen Planprüfungen meldeten leer, jede mit gutem Grund:**

    * `nicht_geplant` (SWR-106) fragt nur, ob das Ticket **vorkommt** — es kam vor.
    * `plan_drift` (SWR-109) vergleicht die **Sprintnummer** und überspringt jede Zeile,
      deren Fälligkeitsspalte „dieser Sprint" sagt (`sprint_nr is None`). Das ist genau die
      Zeilenart, die ein laufender Sprint **schließt** — die Prüfung sieht die Zukunft und
      lässt die Gegenwart aus.
    * `sprint_vergangen` (SWR-112) kann nicht anschlagen, solange der fragliche Sprint der
      laufende ist (`7 < 7` ist falsch). Ihr frühester Zeitpunkt liegt **nach** der
      Falschmeldung.

    Die Lücke ist deshalb kein Defekt in einer der drei, sondern eine **Spalte, die keine
    von ihnen liest**.

    Beide Richtungen werden gemeldet. Die zweite — Ticket `done`, Planzeile „offen" — ist
    die, bei der ein geschlossenes Ticket wie unerledigte Arbeit aussieht.
    """
    nach_ref = _nach_ref(alle)
    treffer = []
    for z in plan_zeilen:
        wort = (z.get("status") or "").strip().lower().strip("*_` ")
        if not wort:
            continue
        ticket = next((nach_ref[r] for r in z.get("refs", []) if r in nach_ref), None)
        if ticket is None:                      # Zeile nennt kein bekanntes Ticket
            continue
        # Takt-Dauerläufer: „erfüllt" + `open` ist der Normalzustand, nie ein Befund.
        if str(ticket.get("takt", "")).strip():
            continue
        geschlossen = ticket.get("status") in TICKET_GESCHLOSSEN
        if wort in PLAN_FERTIG and not geschlossen:
            treffer.append({"ref": ticket["ref"], "titel": ticket["titel"],
                            "plan": wort, "ticket": ticket.get("status", ""),
                            "richtung": "plan_zu_frueh_fertig",
                            "meldung": "Plan sagt \u201e%s\u201c, Ticket steht auf \u201e%s\u201c"
                                       % (wort, ticket.get("status", ""))})
        elif wort in PLAN_OFFEN and geschlossen:
            treffer.append({"ref": ticket["ref"], "titel": ticket["titel"],
                            "plan": wort, "ticket": ticket.get("status", ""),
                            # SWR-201: die Sprintnummer der PLANZEILE. Ohne sie kann
                            # `plan_nachlauf` nur wissen, DASS ein Sprint läuft, und
                            # nicht, ob diese Zeile zu ihm gehört — eine Zeile aus
                            # Sprint 7 sähe genauso aus wie eine von heute.
                            "plan_sprint": z.get("sprint_nr"),
                            "richtung": "ticket_zu_frueh_fertig",
                            "meldung": "Ticket steht auf \u201e%s\u201c, Plan sagt \u201e%s\u201c"
                                       % (ticket.get("status", ""), wort)})
    return treffer


def kennzahlen(offene):
    """SWR-113 (pm/T-0046): die Zählweise von „nicht geschlossen", festgelegt.

    Vier Sprints lang stand die Zahl auf **15** und passte zu keiner Zählweise des
    Werkzeugs (17 mit, 11 ohne Takt-Dauerläufer). Der Befund war nicht die Abweichung,
    sondern dass sie **nicht auflösbar** war: nirgends stand, was mitzählt. Eine
    unwiderlegbare Kennzahl ist keine.

    **Festgelegt (pm/T-0046, Sprint 7):** „nicht geschlossen" ist `offen_gesamt` —
    jedes Ticket, dessen Status weder `done` noch `rejected` ist, **Takt-Dauerläufer
    eingeschlossen**. Die Begründung stand schon im Docstring von `offene_tickets` und
    wird hier nur noch angewandt: Takt-Tickets sind Dauerpflichten und gehören in jeden
    Sprint; dass sie kein Datum tragen, macht sie nicht planlos. `sachtickets` steht
    daneben, weil die Frage „wie viel Sacharbeit ist offen" eine andere ist — als
    **eigene Zahl mit eigenem Namen** und nicht als zweite Lesart derselben (B033).

    Die Reihe der Sprints 2–5 wird **nicht** rückwirkend korrigiert: eine still
    ersetzte Zahl nimmt dem nächsten Leser den Hinweis, welche Art Angabe hier
    ungeprüft durchging (L-2026-08-17g Regel 4).
    """
    takt = sum(1 for t in offene if str(t.get("takt", "")).strip())
    return {"offen_gesamt": len(offene),
            "davon_takt": takt,
            "sachtickets": len(offene) - takt}


def zaehler(plan_zeilen):
    """Wie viele Zeilen je Zustand — plus die Querzahl „wartet auf Mensch".

    Die ersten vier Zahlen zerlegen den Plan **vollständig und überschneidungsfrei**
    (jede Zeile hat genau einen Zustand); `wartet_auf_mensch` liegt bewusst **quer**
    dazu und darf sich mit `terminiert` überschneiden — eine Aufgabe kann ein Datum
    tragen und trotzdem auf den Menschen warten. Die Zahl heißt deshalb nach dem, was
    sie zählt, und wird nicht in die Zerlegung gemischt (B033/B053).
    """
    z = {ZUSTAND_SPRINT: 0, ZUSTAND_MENSCH: 0, ZUSTAND_TERMIN: 0, ZUSTAND_NUMMER: 0,
         ZUSTAND_OFFEN: 0}
    for zeile in plan_zeilen:
        schl = zeile.get("zustand", ZUSTAND_OFFEN)
        z[schl] = z.get(schl, 0) + 1
    return {"dieser_sprint": z[ZUSTAND_SPRINT],
            "terminiert": z[ZUSTAND_TERMIN],
            "ohne_termin": z[ZUSTAND_MENSCH],
            "ohne_zustand": z[ZUSTAND_OFFEN],
            # SWR-106: die beiden Sprint-Zahlen liegen in derselben Zerlegung wie die
            # anderen Zustände (jede Zeile hat genau einen), `wartet_auf_mensch` bleibt
            # die einzige Querzahl.
            "fest_geplant": sum(1 for zl in plan_zeilen if zl.get("horizont") == "fest"),
            "warteschlange": sum(1 for zl in plan_zeilen
                                 if zl.get("horizont") == "warteschlange"),
            "auf_sprint": z[ZUSTAND_NUMMER],
            "wartet_auf_mensch": sum(1 for zl in plan_zeilen if zl.get("wartet_auf_mensch"))}


def plan(root, jetzt=None, heute=None, projekt=QUELLE_PROJEKT, datei=QUELLE_DATEI):
    """SWR-103: der aktuelle Genesis-Sprintplan für die Kachel im Cockpit.

    `text`        Kurzblock „Das Wichtigste" der Plandatei (unverändert, kein zweiter Text)
    `zeilen`      Planzeilen mit Rolle, Fälligkeit, Zustand, Ampel, Grund
    `zaehler`     dieser Sprint / wartet auf Mensch / terminiert
    `nicht_geplant`  offene Tickets ohne Planzeile — der Bestandsabgleich aus DoD 3
    `stand`       Zeitpunkt des letzten **Commits** der Datei (nicht aus ihrem Text)
    `veraltet`/`hinweis`  „seit HH:MM keine Session", wenn zwei Takte still waren
    `quelle`      welche Datei gelesen wurde — damit die Kachel prüfbar bleibt
    """
    heute = heute or _datum.today()
    pfad = os.path.join(root, projekt, *datei.split("/"))
    text = ""
    if os.path.isfile(pfad):
        try:
            with open(pfad, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            text = ""
    # SWR-106: Die Planeinheit ist der Sprint, nicht der Kalendertag. Die laufende
    # Nummer kommt aus dem Register — der einzigen Stelle, die sie kennt (B033).
    jetzt_nr = sprint_register.aktuell(root)
    takt_min = sprint_register.takt_minuten(root)
    plan_zeilen = zeilen(plan_tabelle(text), heute, jetzt_nr)
    offene = offene_tickets(root)
    fehlend = nicht_geplant(plan_zeilen, offene)
    widerspruch = widersprueche(offene, jetzt_nr, takt_min, heute)
    drift = plan_drift(plan_zeilen, offene)   # SWR-109
    vergangen = sprint_vergangen(offene, jetzt_nr)   # SWR-112 (pm/T-0045)
    statusdrift = status_drift(plan_zeilen, alle_tickets(root))  # SWR-115 (pm/T-0049)
    # SWR-201 (platform/T-0052): der Nachlauf des Plans im LAUFENDEN Sprint ist ein
    # garantierter Zustand (pm/D006) und kein Befund. Getrennt wird HIER, damit beide
    # Leser — Preflight und Sichtenbau — dieselbe Antwort bekommen; zwei Aufrufer eines
    # Satzes wären B033 (die Lehre aus SWR-198: eine Implementierung, nicht ein Text).
    statusdrift, nachlauf = plan_nachlauf(statusdrift,
                                          sprint_register.laufender(root))
    zahlen = kennzahlen(offene)                      # SWR-113 (pm/T-0046)
    for o in offene:
        o.pop("_ticket", None)

    # Staleness aus SWR-102 wiederverwendet — dieselbe Falle, dieselbe Regel, ein Ort.
    zeiten = session._commit_zeiten(root, projekt, datei)
    letzter = zeiten[0] if zeiten else ""
    veraltet, hinweis = session.stille(letzter, jetzt or session.datetime.now().astimezone())

    return {"text": session.wichtigstes(text),
            "zeilen": plan_zeilen,
            # SWR-154 (pm/N-0043 Punkt 2): die Kapitelüberschriften in Reihenfolge. ⚠ Die
            # ZEILEN stehen weiterhin **einmal** in `zeilen`; hier liegen nur die Köpfe.
            # Die Zeilen zusätzlich je Kapitel mitzuliefern wäre eine zweite Kopie
            # desselben Bestands — und zwei Kopien laufen auseinander (B033). Die
            # Zuordnung ist ein Feld an der Zeile.
            "kapitel": kapitel_koepfe(plan_zeilen, jetzt_nr),
            "zaehler": zaehler(plan_zeilen),
            "offen_gesamt": len(offene),
            # SWR-132 (pm/T-0064, Brief pm/N-0038): die **Liste** zu der Zahl.
            #
            # ⚠ **Kein neuer Erhebungsweg — dieselbe Python-Liste, die `offen_gesamt`
            # zählt.** Der Ticket-Entwurf nannte `aggregation` als Quelle; gemessen ist
            # `offene_tickets` die bessere, weil `offen_gesamt` schon von hier kommt. Eine
            # zweite Erhebung neben dieser hätte genau den Zustand erzeugt, den SWR-131
            # heute gekostet hat: zwei Antworten auf eine Frage, und der Leser weiß nicht,
            # welcher er glauben soll. Zahl und Liste können hier nicht auseinanderlaufen,
            # weil es **ein** Objekt ist — das ist die Zusicherung, nicht eine Absicht.
            #
            # ⚠ **Nicht gekürzt.** `aggregation.cockpit` zeigt `offene[:3]` (SWR-074/094)
            # — dort ist die Kürzung richtig, es ist eine Kachel. Hier wäre sie falsch: der
            # Zweck der Liste ist, dass der Auftraggeber priorisieren kann (pm/N-0038),
            # und eine still gekürzte Liste ist eine zweite Priorisierung neben der, die
            # er selbst treffen will. Das Kompaktmachen gehört in die Ansicht (pm/T-0066:
            # falten statt weglassen), nicht in die Quelle.
            "offene": offene,
            "nicht_geplant": fehlend,
            "widersprueche": widerspruch,   # SWR-106
            "plan_drift": drift,            # SWR-109
            "sprint_vergangen": vergangen,  # SWR-112 (pm/T-0045)
            "status_drift": statusdrift,    # SWR-115 (pm/T-0049)
            # SWR-201 (platform/T-0052): dieselben Zeilen, aber die, die der laufende
            # Sprint per Konstruktion erzeugt. Eigener Schlüssel und eigener Name, weil
            # sie eine ANDERE Aussage sind — nicht eine zweite Lesart von `status_drift`
            # (B033, die Familie platform/T-0027: zwei Größen unter einem Namen).
            "plan_nachlauf": nachlauf,      # SWR-201 (platform/T-0052)
            "kennzahlen": zahlen,           # SWR-113 (pm/T-0046)
            "sprint_nr": jetzt_nr,          # SWR-106: der laufende Sprint
            # SWR-144 (pm/T-0065): die Nummer, die der Knopf setzen wird — damit die
            # Ansicht sie **beschriften** kann, ohne sie zu **rechnen**. `jetzt_nr + 1` in
            # JavaScript wäre eine zweite Antwort auf „welcher ist der nächste Sprint?"
            # (B033), und sie wäre genau dann falsch, wenn zwischen Laden und Klick ein
            # Sprint gewechselt hat. Gesetzt wird der Wert trotzdem serverseitig neu
            # geholt: diese Zahl ist eine Beschriftung, keine Anweisung.
            "naechster_sprint": jetzt_nr + 1,
            "takt_min": takt_min,
            "stand": letzter,
            "veraltet": veraltet,
            "hinweis": hinweis,
            "quelle": "%s/%s" % (projekt, datei)}
