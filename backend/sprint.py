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
ZUSTAND_OFFEN = "unbekannt"    # weder das eine noch das andere

_SPRINT_WORT = re.compile(r"dies\w*\s+sprint", re.I)
_MENSCH_WORT = re.compile(r"wartet[\s-]*auf[\s-]*mensch", re.I)
_TICKET_REF = re.compile(r"([A-Za-z0-9_.-]+)/(T-\d{4})|(T-\d{4})")


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
    if _SPRINT_WORT.search(s):
        return ZUSTAND_SPRINT, "sprint"
    if _MENSCH_WORT.search(s):
        return ZUSTAND_MENSCH, "mensch"
    treffer = re.search(r"\d{4}-\d{2}-\d{2}", s)
    if treffer:
        return ZUSTAND_TERMIN, board.frist_ampel(treffer.group(0), heute)
    return ZUSTAND_OFFEN, "grau"


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


def zeilen(tabelle, heute=None):
    """Plantabelle -> Liste von Zeilen mit Zustand und Ampel."""
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
        ergebnis.append({"aufgabe": aufgabe,
                         "refs": sorted(refs_der_zeile(aufgabe)),
                         "rolle": hole(z, i_rolle),
                         "faellig": faellig,
                         "zustand": zustand,
                         "ampel": ampel,
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
                            "frist": t.get("frist", ""),
                            "takt": t.get("takt", "")})
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


def zaehler(plan_zeilen):
    """Wie viele Zeilen je Zustand — plus die Querzahl „wartet auf Mensch".

    Die ersten vier Zahlen zerlegen den Plan **vollständig und überschneidungsfrei**
    (jede Zeile hat genau einen Zustand); `wartet_auf_mensch` liegt bewusst **quer**
    dazu und darf sich mit `terminiert` überschneiden — eine Aufgabe kann ein Datum
    tragen und trotzdem auf den Menschen warten. Die Zahl heißt deshalb nach dem, was
    sie zählt, und wird nicht in die Zerlegung gemischt (B033/B053).
    """
    z = {ZUSTAND_SPRINT: 0, ZUSTAND_MENSCH: 0, ZUSTAND_TERMIN: 0, ZUSTAND_OFFEN: 0}
    for zeile in plan_zeilen:
        schl = zeile.get("zustand", ZUSTAND_OFFEN)
        z[schl] = z.get(schl, 0) + 1
    return {"dieser_sprint": z[ZUSTAND_SPRINT],
            "terminiert": z[ZUSTAND_TERMIN],
            "ohne_termin": z[ZUSTAND_MENSCH],
            "ohne_zustand": z[ZUSTAND_OFFEN],
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
    plan_zeilen = zeilen(plan_tabelle(text), heute)
    offene = offene_tickets(root)
    fehlend = nicht_geplant(plan_zeilen, offene)

    # Staleness aus SWR-102 wiederverwendet — dieselbe Falle, dieselbe Regel, ein Ort.
    zeiten = session._commit_zeiten(root, projekt, datei)
    letzter = zeiten[0] if zeiten else ""
    veraltet, hinweis = session.stille(letzter, jetzt or session.datetime.now().astimezone())

    return {"text": session.wichtigstes(text),
            "zeilen": plan_zeilen,
            "zaehler": zaehler(plan_zeilen),
            "offen_gesamt": len(offene),
            "nicht_geplant": fehlend,
            "stand": letzter,
            "veraltet": veraltet,
            "hinweis": hinweis,
            "quelle": "%s/%s" % (projekt, datei)}
