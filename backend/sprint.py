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
TICKET_GESCHLOSSEN = ("done", "rejected")



def _zellen_text(zelle):
    """Markdown-Auszeichnung aus einer Tabellenzelle nehmen (Fett, Code, Links)."""
    s = str(zelle or "")
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"\*\*([^*]*)\*\*", r"\1", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    return s.strip()


def plan_tabelle(text):
    """Die Plantabelle aus dem Text schneiden (rein, ohne IO).

    Gesucht wird die **erste** Tabelle **nach** der Sprint-Plan-Überschrift. Alles davor
    wird bewusst ignoriert: die Datei beginnt mit dem Kurzblock „Das Wichtigste" (B050),
    und der darf eine Tabelle enthalten, ohne dass sie als Plan gilt. Fehlt die
    Überschrift, ist das Ergebnis leer — die Sicht sagt dann, dass sie keinen Plan
    gefunden hat, statt ersatzweise irgendeine Tabelle der Datei zu zeigen.
    """
    m = PLAN_KOPF.search(text or "")
    if not m:
        return None
    tabellen = aggregation.parse_md_tabellen(text[m.end():])
    return tabellen[0] if tabellen else None


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
            if t.get("status") in ("done", "rejected"):
                continue
            treffer.append({"projekt": name, "id": t.get("id", ""),
                            "ref": aggregation.ref(name, t.get("id", "")),
                            "titel": t.get("titel", ""),
                            "status": t.get("status", ""),
                            "typ": t.get("typ", ""),      # SWR-112: DRs sind ausgenommen
                            "frist": t.get("frist", ""),
                            "takt": t.get("takt", ""),
                            "geplant_sprint": t.get("geplant_sprint", ""),  # SWR-106
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
        ticket = next((nach_ref[r] for r in z.get("refs", []) if r in nach_ref), None)
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
    """
    treffer = []
    for t in offene:
        if (t.get("_ticket") or {}).get("typ") == "decision-request" \
                or t.get("typ") == "decision-request":
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
    zahlen = kennzahlen(offene)                      # SWR-113 (pm/T-0046)
    for o in offene:
        o.pop("_ticket", None)

    # Staleness aus SWR-102 wiederverwendet — dieselbe Falle, dieselbe Regel, ein Ort.
    zeiten = session._commit_zeiten(root, projekt, datei)
    letzter = zeiten[0] if zeiten else ""
    veraltet, hinweis = session.stille(letzter, jetzt or session.datetime.now().astimezone())

    return {"text": session.wichtigstes(text),
            "zeilen": plan_zeilen,
            "zaehler": zaehler(plan_zeilen),
            "offen_gesamt": len(offene),
            "nicht_geplant": fehlend,
            "widersprueche": widerspruch,   # SWR-106
            "plan_drift": drift,            # SWR-109
            "sprint_vergangen": vergangen,  # SWR-112 (pm/T-0045)
            "status_drift": statusdrift,    # SWR-115 (pm/T-0049)
            "kennzahlen": zahlen,           # SWR-113 (pm/T-0046)
            "sprint_nr": jetzt_nr,          # SWR-106: der laufende Sprint
            "takt_min": takt_min,
            "stand": letzter,
            "veraltet": veraltet,
            "hinweis": hinweis,
            "quelle": "%s/%s" % (projekt, datei)}
