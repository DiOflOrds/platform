"""BCK-Inbox (SWR-020, SWR-024; ADR-003): offene Decision Requests listen,
Entscheidungen annehmen — Decision-Log-Zeile + Ticket-Notiz + sofortiger
Git-Commit (nur die eigenen Schreibziele, Lesson T-0014).
"""
import os
import re
import subprocess
import sys

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import board  # noqa: E402

from . import aggregation  # noqa: E402
from . import git_schreiben  # noqa: E402  — SWR-134: der eine Schreibweg nach Git

FINAL = board.STATUS_FINAL
# SWR-039 hat den Marker eingeführt, SWR-131 hat ihn zur einzigen Quelle gemacht: bis
# dahin wusste die Inbox am Marker, dass ein DR entschieden ist, während Preflight und
# Cockpit am `status` lasen — zwei Wahrheiten über ein Wort, und `entscheide()` setzt
# `status` nie. Am 2026-08-17 kostete das drei Berichte, die dem Auftraggeber eine
# beantwortete Frage erneut vorlegten. Delegation statt zweiter Kopie (B033).
ENTSCHIEDEN = board.ENTSCHEIDUNGSMARKER
NUTZER_FALLBACK = [{"name": "E. John", "rolle": "entscheider"}]  # SWR-037 (Auftraggeber)
COMMIT_IDENTITAET = ["-c", "user.name=Mensch via Inbox",
                     "-c", "user.email=geraldine.john90@gmail.com"]


class InboxFehler(Exception):
    def __init__(self, code, meldung):
        super().__init__(meldung)
        self.code = code


def entscheidungszeitpunkt(jetzt=None):
    """SWR-084 (Wunsch Auftraggeber via Session): Zeitpunkt einer Entscheidung als `JJJJ-MM-TT HH:MM`.

    Bis dahin wurde nur das Datum vermerkt — bei mehreren Entscheidungen an einem
    Tag (Regelfall seit dem 30-Minuten-Takt) war die Reihenfolge nicht mehr aus
    dem Log ablesbar. Ortszeit des Servers, Minutengenauigkeit; eine Quelle für
    Decision-Log-Zeile und Ticket-Vermerk.

    P10: Die Formatierung liegt seit SWR-081 in `board.zeitpunkt` — Entscheidungen
    und Ticket-Änderungen datieren aus derselben Quelle. Diese Funktion bleibt als
    sprechender Name im Entscheidungspfad stehen und delegiert nur noch.
    """
    return board.zeitpunkt(jetzt)


def _dr_tickets(p0):
    """Offene, noch UNENTSCHIEDENE DRs (SWR-039: mit Entscheidungs-Vermerk raus)."""
    tickets, _ = board.lade_tickets(p0)
    return [t for t in tickets
            if t.get("typ") == "decision-request" and t.get("status") not in FINAL
            and ENTSCHIEDEN not in t.get("_body", "")]


def lade_nutzer(root):
    """SWR-037: Registry process/team/nutzer.yaml (Zeilenformat '- name: X' / 'rolle: Y');
    ohne Datei gilt ein einzelner Default-Entscheider (Auftraggeber)."""
    pfad = os.path.join(root, "process", "team", "nutzer.yaml")
    if not os.path.exists(pfad):
        return list(NUTZER_FALLBACK)
    nutzer, aktuell = [], None
    for zeile in open(pfad, encoding="utf-8"):
        z = zeile.strip()
        if z.startswith("#") or not z:
            continue
        m = re.match(r"-\s*name:\s*[\"']?(.+?)[\"']?\s*$", z)
        if m:
            aktuell = {"name": m.group(1), "rolle": "leser"}
            nutzer.append(aktuell)
            continue
        m = re.match(r"rolle:\s*[\"']?(\w+)[\"']?\s*$", z)
        if m and aktuell is not None:
            aktuell["rolle"] = m.group(1)
    return nutzer or list(NUTZER_FALLBACK)


def _entscheider_pruefen(root, entscheider):
    """SWR-038: Namen gegen die Registry validieren; leer -> einziger Default-Entscheider."""
    registriert = lade_nutzer(root)
    entscheider_namen = [n["name"] for n in registriert if n.get("rolle") == "entscheider"]
    name = (entscheider or "").strip()
    if not name:
        if len(entscheider_namen) == 1:
            return entscheider_namen[0]
        raise InboxFehler(400, "entscheider erforderlich — zugelassen: "
                               + (", ".join(entscheider_namen) or "keiner registriert"))
    if name not in entscheider_namen:
        raise InboxFehler(403, f"'{name}' ist kein registrierter Entscheider (SWR-038) — "
                               f"zugelassen: {', '.join(entscheider_namen) or 'keiner'}")
    return name


def liste(root, projekt=None):
    """Offene DRs mit Body — über ALLE Projekte (SWR-027) oder gescopt auf eines.
    SWR-042 (P3): optionen/frist/default maschinenlesbar für die Button-Entscheidung."""
    namen = [projekt] if projekt else (aggregation.projekte(root) or ["p0"])
    eintraege = []
    for name in namen:
        repo = aggregation.projekt_pfad(root, name)  # SWR-070: auch projects/<p>
        for t in _dr_tickets(repo):
            pfad = os.path.join(repo, "tickets", f"{t['id']}.md")
            body = re.sub(r"(?s)^---.*?---\s*", "", open(pfad, encoding="utf-8").read())
            eintraege.append({"projekt": name, "id": t["id"],
                              "ref": aggregation.ref(name, t["id"]),  # SWR-087
                              "titel": t.get("titel"),
                              "status": t.get("status"), "prio": t.get("prio"),
                              "sprint": t.get("sprint"), "body": body.strip(),
                              "optionen": board.parse_liste(t.get("optionen")),
                              "frist": t.get("frist", ""),
                              "default": t.get("default", "")})
    return {"inbox": eintraege}


def historie(root, projekt=None):
    """SWR-042 (P3): entschiedene DRs (read-only) — Entscheidungs-Vermerk im Body
    oder finaler Status, neueste zuerst je Projekt."""
    namen = [projekt] if projekt else (aggregation.projekte(root) or ["p0"])
    eintraege = []
    for name in namen:
        repo = aggregation.projekt_pfad(root, name)  # SWR-070: auch projects/<p>
        tickets, _ = board.lade_tickets(repo)
        for t in tickets:
            if t.get("typ") != "decision-request":
                continue
            body = t.get("_body", "")
            if ENTSCHIEDEN not in body and t.get("status") not in FINAL:
                continue
            m = re.findall(r"\*\*Entscheidung \([^)]*\):\*\*[^\n]*", body)
            eintraege.append({"projekt": name, "id": t["id"],
                              "ref": aggregation.ref(name, t["id"]),  # SWR-087
                              "titel": t.get("titel"),
                              "status": t.get("status"), "sprint": t.get("sprint"),
                              "entscheidung": m[-1] if m else "(Vermerk im Ticket)"})
        eintraege.sort(key=lambda e: (e["projekt"], e["id"]), reverse=True)
    return {"historie": eintraege}


def _naechste_d_id(log_pfad):
    text = open(log_pfad, encoding="utf-8").read() if os.path.exists(log_pfad) else ""
    ids = [int(m) for m in re.findall(r"\|\s*D(\d{3})\s*\|", text)]
    return f"D{(max(ids) + 1 if ids else 0):03d}"


#: SWR-195 (platform/T-0036): eine ID-Zeile im Entscheidungslog. `D` = Klasse-A-Antwort
#: des Menschen, `B` = Klasse-B-Beschluss des Teams — **beide** aus derselben Tabelle und
#: deshalb aus demselben Muster.
LOG_ID_ZEILE = re.compile(r"^\|\s*([DB]\d{3})\s*\|", re.M)
#: ⚠⚠ **Der Altbestand, benannt statt gezählt** (Stand 2026-08-21, `platform/T-0036`).
#:
#: Diese fünf Zeilen kann `_naechste_d_id` **gar nicht erzeugt haben**: es bildet
#: `max + 1`. Sie sind von Hand geschrieben — es gibt also einen **zweiten Schreibweg**
#: ins Entscheidungslog, und der hat keine Nummernvergabe. Das ist B033 mit einem
#: *Schreibweg* als vergessener Kopie.
#:
#: ⚠ Sie werden **nicht repariert**: das Log ist append-only und Historie wird in diesem
#: Haus nicht umgeschrieben (Playbook Kap. 16). Sie stehen damit in derselben Kategorie
#: wie die vier fortgeschriebenen Statusübergänge — **gemeldet, namentlich, nicht
#: blockierend** (`SWR-166`). Das ist eine Entscheidung und keine Selbstverständlichkeit.
DUBLETTEN_ALTBESTAND = {"pm": {"D005": 3, "D006": 2}}


def log_dubletten(root):
    """{einheit: {id: anzahl}} — mehrfach vergebene IDs je Entscheidungslog.

    ⚠ Die Grundmenge sind **alle** Logs der Discovery und nicht die, die jemand im Ticket
    aufgezählt hat (`SWR-128`-Familie, in drei Sprints dreimal dieselbe Stelle).
    """
    import sys as _sys
    _skripte = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "scripts")
    if _skripte not in _sys.path:
        _sys.path.insert(0, _skripte)
    import board as _board
    gefunden = {}
    for name, pfad in _board.projekt_pfade(root):
        log = os.path.join(pfad, "management", "decisions", "decision-log.md")
        if not os.path.isfile(log):
            continue
        with open(log, encoding="utf-8", errors="replace") as f:
            ids = LOG_ID_ZEILE.findall(f.read())
        mehrfach = {}
        for i in ids:
            mehrfach[i] = mehrfach.get(i, 0) + 1
        mehrfach = {k: v for k, v in mehrfach.items() if v > 1}
        if mehrfach:
            gefunden[name] = mehrfach
    return gefunden


def _log_sicherstellen(log_pfad, projekt):
    """Das Entscheidungslog anlegen, wenn es fehlt — SWR-152 (platform/T-0022).

    ⚠⚠ **Der Anlass ist ein Fehlschlag in Produktion.** Der Auftraggeber hat
    `promt-team/T-0009` (**Klasse A**) über die Inbox mit „A" entschieden, und der
    Schreibweg starb an `[Errno 2] No such file or directory` — `promt-team` hat nie ein
    `management/decisions/` bekommen. Angelegt wird es von `pool.py` bei der **Gründung**;
    die Teams, die anders entstanden sind (`promt-team`, `platform`), haben keins.

    > **Der Schreibweg setzte eine Datei voraus, die ein ANDERER Weg anlegt. Solange jedes
    > Repo durch diesen anderen Weg entstanden ist, ist die Annahme unsichtbar richtig.**

    ⚠ **Warum Anlegen und nicht Abweisen.** Ein sauberer 400er („dieses Team hat kein
    Entscheidungslog") wäre ehrlicher gewesen als der Errno — und hätte den Menschen mit
    einer Klasse-A-Entscheidung stehen lassen, die er getroffen hat und nicht verbuchen
    kann. *Eine getroffene Entscheidung, die am Ablageort scheitert, ist verloren, sobald
    das Fenster zu ist.* Das Log ist ein **Pflichtartefakt** jedes Repos, das DRs führen
    kann (Playbook Kap. 16), kein Freiwilliges.

    ⚠ **Der Kopf ist wortgleich zu `pool.py`.** Zwei Wege, die dieselbe Datei in zwei
    Gestalten anlegen, sind zwei Wahrheiten über ihr Format — und die Zeile, die
    `entscheide` anhängt, passt dann irgendwann nur zu einer davon (B033).

    Tut nichts, wenn die Datei existiert: das Log ist **append-only**, und ein Weg, der
    unter Umständen überschreibt, ist an dieser Stelle das Schlimmste, was passieren kann.
    """
    if os.path.exists(log_pfad):
        return
    os.makedirs(os.path.dirname(log_pfad), exist_ok=True)
    # Wortgleich zu `pool.LOG_TABELLENKOPF` — importiert und nicht abgeschrieben.
    from . import pool  # in der Funktion: sonst Import-Zyklus (SWR-134)
    open(log_pfad, "w", encoding="utf-8", newline="\n").write(
        f"# Decision Log {projekt}\n\n"
        "*Append-only — Entscheidungen werden nie überschrieben, nur ergänzt "
        "(Playbook Kap. 16).*\n\n"
        "*Angelegt beim ersten Eintrag über die Inbox (SWR-152): dieses Repo ist nicht "
        "über `pool.gruende` entstanden und hatte deshalb keins.*\n\n"
        + pool.LOG_TABELLENKOPF)



def entscheide(root, ticket_id, option, begruendung="", projekt="p0", entscheider=""):
    """Entscheidung annehmen (je Projekt, SWR-027; Entscheider-Pflicht SWR-038):
    Log + Ticket + BOARD + Commit."""
    if not option or not str(option).strip():
        raise InboxFehler(400, "option darf nicht leer sein")
    entscheider = _entscheider_pruefen(root, entscheider)
    try:
        p0 = aggregation.projekt_pfad(root, projekt)
    except ValueError as e:
        raise InboxFehler(404, str(e))
    ticket_pfad = os.path.join(p0, "tickets", f"{ticket_id}.md")
    if not re.fullmatch(r"T-\d{4}", ticket_id or "") or not os.path.exists(ticket_pfad):
        raise InboxFehler(404, f"unbekanntes Ticket: {ticket_id}")
    offene = {t["id"]: t for t in _dr_tickets(p0)}
    if ticket_id not in offene:
        raise InboxFehler(400, f"{ticket_id} ist kein offener Decision Request "
                               f"(SWR-039: bereits entschiedene DRs sind gesperrt)")
    # T-0039: gewählte Option gegen die Ticket-Optionen validieren (statt Freitext).
    # Ungültige Option -> 400, KEIN Decision-Log-Eintrag. Ohne optionen-Feld
    # (Alt-DRs) bleibt Freitext zulässig.
    zulaessig = board.parse_liste(offene[ticket_id].get("optionen"))
    if zulaessig:
        token = board.parse_optionstoken(option)
        unbekannt = [x for x in token if x not in zulaessig]
        if not token or unbekannt:
            raise InboxFehler(400, f"ungültige Option '{option.strip()}' — zulässig: "
                                   f"{', '.join(zulaessig)} (T-0039)")
    zeitpunkt = entscheidungszeitpunkt()  # SWR-084: Datum UND Uhrzeit
    log_pfad = os.path.join(p0, "management", "decisions", "decision-log.md")
    _log_sicherstellen(log_pfad, projekt)
    d_id = _naechste_d_id(log_pfad)
    zeile = (f"| {d_id} | {zeitpunkt} | Mensch ({entscheider}, via Inbox) | **{option.strip()}** "
             f"| lt. {ticket_id} | {begruendung.strip() or '—'} | {ticket_id} |")
    with open(log_pfad, "a", encoding="utf-8", newline="\n") as f:
        f.write(zeile + "\n")
    with open(ticket_pfad, "a", encoding="utf-8", newline="\n") as f:
        f.write(f"\n**Entscheidung ({d_id}, via Inbox, {zeitpunkt}):** {option.strip()}"
                f"{' — ' + begruendung.strip() if begruendung.strip() else ''}\n")
    tickets, _ = board.lade_tickets(p0)
    open(os.path.join(p0, "BOARD.md"), "w", encoding="utf-8", newline="\n").write(
        board.generiere_board(tickets))
    rel = [os.path.join("management", "decisions", "decision-log.md"),
           os.path.join("tickets", f"{ticket_id}.md"), "BOARD.md"]
    # SWR-134: derselbe Schreibweg wie der Briefkasten. Vorher lief der Weg des Menschen
    # ohne Sperren-Räumung — auf diesem Mount hieß das: die zweite Entscheidung in einer
    # Sitzung scheiterte an der Sperre, die die erste hinterlassen hatte.
    v = git_schreiben.verbuche(p0, rel,
                               f"{ticket_id}: Entscheidung via Inbox ({d_id})",
                               COMMIT_IDENTITAET)
    if not v.ok:
        raise InboxFehler(503, "Git-Commit fehlgeschlagen: " + v.fehler[:400])
    return {"entscheidung": d_id, "ticket": ticket_id, "option": option.strip(),
            "entscheider": entscheider}
