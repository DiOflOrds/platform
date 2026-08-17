# -*- coding: utf-8 -*-
"""tickets.py (P10, ADR-007): Schreibfassade für Tickets — zweiter Schreibpfad
neben der Skript-Route.

Die Regeln liegen bewusst NICHT hier, sondern in `scripts/board.py`
(`board.aktualisiere`): Validierung, Status-Übergänge und BOARD.md-Regeneration
sind die Regeln der Skript-Route; dieses Modul fügt nur das hinzu, was ein
HTTP-Aufruf braucht — Projektauflösung, deutsche Fehlercodes, Git-Commit mit
erkennbarer Identität und die Rücknahme bei einem gescheiterten Commit
(SWR-077/078/080/081).

Muster übernommen von inbox.py (ADR-003): schreiben, nur die eigenen Ziele
adden, sofort committen.
"""
import os
import subprocess
import sys

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import board  # noqa: E402

from . import aggregation  # noqa: E402
from . import git_schreiben  # noqa: E402  — SWR-134: der eine Schreibweg nach Git

HERKUNFT = "Mensch via HMI"
COMMIT_IDENTITAET = ["-c", f"user.name={HERKUNFT}", "-c", "user.email=mensch@hmi.local"]
BOARD_DATEI = "BOARD.md"


class TicketFehler(Exception):
    """code = HTTP-Status, Meldung deutsch (Muster InboxFehler/TeamFehler)."""

    def __init__(self, code, meldung):
        super().__init__(meldung)
        self.code = code


def _repo(root, projekt):
    try:
        return aggregation.projekt_pfad(root, projekt)
    except ValueError as e:
        raise TicketFehler(404, str(e))


def _historie(body):
    """SWR-081: Änderungsvermerke aus dem Fließtext, neueste zuletzt geschrieben."""
    marke = "**Bearbeitet ("
    return [z.strip() for z in str(body or "").splitlines() if z.strip().startswith(marke)]


def _takt_vokabular(eigener):
    """SWR-104/B059: Auswahlliste für das Takt-Feld — inklusive des Werts, den DIESES
    Ticket schon trägt.

    Das Formular baut aus dieser Liste ein `<select>`. Ein Uhrzeit-Takt
    (`taeglich@14:00`) steht nicht im festen Vokabular; ohne diesen Zusatz fände der
    Browser keine passende Option, fiele auf den ersten Eintrag („einmalig") zurück und
    das **Speichern eines beliebigen anderen Feldes** hätte den Takt stillschweigend
    gelöscht. Ein zweiter Schreibpfad, der Daten wegwirft, die der erste erlaubt, ist
    genau die Falle aus B051 — und still tut er es obendrein (B038).

    Bewusst nicht enthalten: ein Uhrzeit-Wähler. Neue Uhrzeit-Takte werden über die
    Skript-/Session-Route gesetzt; das HMI **erhält** sie, es erzeugt sie nicht.
    """
    vokabular = dict(board.TAKTE)
    wert = str(eigener or "").strip()
    if wert and wert not in vokabular and board.parse_takt(wert):
        vokabular[wert] = board.takt_klartext(wert)
    return vokabular


def editor_daten(root, projekt, ticket_id):
    """SWR-077/080/081: Formularzustand eines Tickets — Werte, Fingerabdruck,
    Vokabulare und die Auskunft, ob (und warum nicht) es bearbeitbar ist.

    Lesen bleibt ohne PIN (SWR-081) — dieser Endpunkt liefert nichts, was die
    Detailansicht nicht ohnehin zeigt, nur maschinenlesbar für das Formular.
    """
    repo = _repo(root, projekt)
    try:
        text, t = board.lies_ticket(repo, ticket_id)
    except ValueError as e:
        raise TicketFehler(404, str(e))
    status = t.get("status", "")
    geschlossen = status in board.GESCHLOSSEN
    felder = {f: t.get(f, "") for f in board.EDITIERBARE_FELDER}
    felder["labels"] = board.parse_liste(t.get("labels"))
    return {
        "projekt": projekt, "id": ticket_id, "ref": aggregation.ref(projekt, ticket_id),
        "felder": felder, "body": t.get("_body", ""),
        "fingerprint": board.fingerprint(text),
        "bearbeitbar": not geschlossen,
        "grund": (f"{ticket_id} ist {status} — erledigte Aufgaben bleiben Archiv; "
                  f"möglich ist nur die Wiedereröffnung." if geschlossen else ""),
        "historie": _historie(t.get("_body", "")),
        "vokabular": {
            "typen": list(board.TYPEN), "prios": list(board.PRIOS),
            "takte": _takt_vokabular(t.get("takt")), "status": list(board.STATUS),
            "status_moeglich": [status] + list(board.UEBERGAENGE.get(status, [])),
            "editierbar": list(board.EDITIERBARE_FELDER),
            "label_max": board.LABEL_MAX,
        },
    }


def _kurz_hash(repo):
    lauf = subprocess.run(["git", "-C", repo, "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    return lauf.stdout.strip()


def speichere(root, projekt, ticket_id, werte):
    """SWR-077/078/080: Änderung annehmen, validieren, schreiben, committen.

    Scheitert der Commit, wird die Arbeitskopie auf den Stand vor dem Schreiben
    zurückgesetzt (Ticket UND BOARD.md) — ein halb geschriebener Zustand wäre
    schlimmer als eine abgelehnte Änderung, weil ihn niemand bemerkt.
    """
    repo = _repo(root, projekt)
    aenderungen = werte.get("felder") or {}
    if not isinstance(aenderungen, dict):
        raise TicketFehler(400, "felder muss ein Objekt sein.")
    erwartet = str(werte.get("fingerprint") or "").strip()
    if not erwartet:
        raise TicketFehler(400, "fingerprint fehlt — bitte das Ticket neu laden "
                                "(Schutz gegen stilles Überschreiben, SWR-080).")
    try:
        vorher_text, _ = board.lies_ticket(repo, ticket_id)
    except ValueError as e:
        raise TicketFehler(404, str(e))
    board_pfad = os.path.join(repo, BOARD_DATEI)
    vorher_board = open(board_pfad, encoding="utf-8").read() if os.path.isfile(board_pfad) else None
    try:
        ergebnis = board.aktualisiere(repo, ticket_id, aenderungen,
                                      body=werte.get("body"),
                                      erwarteter_fingerprint=erwartet,
                                      herkunft=HERKUNFT)
    except board.KonfliktFehler as e:
        raise TicketFehler(409, str(e))
    except ValueError as e:
        raise TicketFehler(400, str(e))

    def zuruecknehmen():
        open(board.ticket_pfad(repo, ticket_id), "w", encoding="utf-8",
             newline="\n").write(vorher_text)
        if vorher_board is not None:
            open(board_pfad, "w", encoding="utf-8", newline="\n").write(vorher_board)

    ziele = [os.path.join("tickets", f"{ticket_id}.md"), BOARD_DATEI]
    nachricht = (f"{ticket_id}: Änderung via HMI ({', '.join(ergebnis['geaendert'])}) "
                 f"— {HERKUNFT}")
    # SWR-134: über den einen Schreibweg. ⚠ Die Rücknahme bleibt unverändert: der
    # Schreibweg räumt eine verwaiste Sperre und wiederholt EINMAL — scheitert es auch
    # dann, war es kein Sperrproblem, und die Änderung gehört zurückgenommen.
    v = git_schreiben.verbuche(repo, ziele, nachricht, COMMIT_IDENTITAET)
    if not v.ok:
        zuruecknehmen()
        raise TicketFehler(503, "Git-Commit fehlgeschlagen — die Änderung wurde "
                                "zurückgenommen, die Dateien stehen unverändert: " +
                           v.fehler[:400])
    return {"ok": True, "projekt": projekt, "ticket": ticket_id,
            "ref": aggregation.ref(projekt, ticket_id),
            "geaendert": ergebnis["geaendert"], "status": ergebnis["status"],
            "fingerprint": ergebnis["fingerprint"], "commit": _kurz_hash(repo),
            "meldung": (f"Gespeichert und committet ({', '.join(ergebnis['geaendert'])}) "
                        f"— {ergebnis['zeitpunkt']}.")}
