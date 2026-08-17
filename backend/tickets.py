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
import sprint_register  # noqa: E402  — SWR-144: welcher Sprint der nächste ist, weiß das
                       #                Register (SWR-136) und keine zweite Stelle.

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
    except board.KeineAenderung as e:
        # SWR-144, DoD 4 von pm/T-0065: „nichts passiert" ist ein **Erfolg** und kein
        # Fehler. Vorher lief dieser Fall durch dieselbe 400 wie eine abgewiesene
        # Eingabe — ein Knopf, dessen „schon erledigt" von seinem „hat nicht
        # funktioniert" nicht zu unterscheiden ist, ist eine Anzeige ohne Aussage.
        #
        # ⚠ **Kein Commit.** Ein Commit ohne Änderung schriebe ein Ereignis in die
        # Historie, das nicht stattgefunden hat — und die Historie ist bei uns die
        # Quelle für `uebergang_historie` und `status_in_head`.
        return {"ok": True, "unveraendert": True, "projekt": projekt,
                "ticket": ticket_id, "ref": aggregation.ref(projekt, ticket_id),
                "geaendert": [], "fingerprint": board.fingerprint(vorher_text),
                "meldung": str(e)}
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


#: SWR-144: Die **einzige** Feldmenge, die eine Terminierung anfasst. Als Konstante und
#: nicht als Literal im Aufruf, weil die Zusicherung sie messen muss: das Argument, warum
#: dieser Weg seinen Fingerprint selbst lesen darf, hängt daran, dass es **ein** Feld ist
#: und sein Wert nicht vom Client kommt. Käme ein zweites dazu, wäre das Argument still
#: falsch — deshalb steht die Menge an einer Stelle, die ein Test lesen kann.
TERMINIER_FELDER = ("geplant_sprint",)


def naechster_sprint(root):
    """Die Sprintnummer, auf die der Knopf terminiert: der laufende **+ 1**.

    ⚠ Aus dem **Register** und nicht aus der Ansicht. Der Brief `pm/N-0038` sagt „für den
    nächsten Durchlauf"; welcher das ist, weiß das Sprintregister (SWR-136) und niemand
    sonst. Eine Nummer, die der Client mitbringt, wäre eine zweite Antwort auf dieselbe
    Frage (B033) — und sie wäre genau dann falsch, wenn zwischen Anzeige und Klick ein
    Sprint gewechselt hat.
    """
    return int(sprint_register.aktuell(root) or 0) + 1


def terminiere(root, projekt, ticket_id):
    """SWR-144 (pm/T-0065): `geplant_sprint` auf den nächsten Sprint setzen — ein Klick.

    **Kein zweiter Schreibweg.** Die Funktion rechnet die Zielnummer aus und übergibt
    dann an `speichere()` — dieselbe Validierung, dieselbe Rücknahme, derselbe Commit
    mit derselben Identität. Ein eigener Schreibweg daneben wäre die Bauart, die B033
    heißt, und der Knopf ist ihr denkbar schlechtester Anlass: er ändert **ein** Feld,
    das `board.EDITIERBARE_FELDER` seit SWR-077 führt.

    ⚠ **`prio` bleibt unberührt** (Festlegung aus `pm/T-0054`): „für den nächsten
    Durchlauf" ist eine Aussage über den Termin, nicht über die Wichtigkeit.

    ⚠ **Warum der Fingerprint hier selbst gelesen wird, obwohl SWR-080 existiert.**
    SWR-080 schützt gegen ein **veraltetes Formular**: der Mensch sieht Werte, die
    Routine ändert sie, das Formular schreibt die alten zurück. Geschützt ist der Wert,
    den der Client gesehen hat. Eine Terminierung bringt **keinen** Wert mit — ihr
    einziger Wert ist `naechster_sprint(root)`, und der wird **innerhalb** des
    Schreibvorgangs aus dem Register geholt. Es gibt also nichts Veraltetes zu
    überschreiben. Dieses Argument gilt **genau so lange, wie es ein Feld ist**; darum
    steht die Feldmenge in `TERMINIER_FELDER` und wird zugesichert.
    """
    ziel = naechster_sprint(root)
    repo = _repo(root, projekt)
    try:
        text, _t = board.lies_ticket(repo, ticket_id)
    except ValueError as e:
        raise TicketFehler(404, str(e))
    werte = {"felder": {f: str(ziel) for f in TERMINIER_FELDER},
             "fingerprint": board.fingerprint(text)}
    erg = speichere(root, projekt, ticket_id, werte)
    erg["geplant_sprint"] = ziel
    if erg.get("unveraendert"):
        # SWR-144: Der Klartext, der „schon terminiert" von „hat nicht funktioniert"
        # trennt. Die Meldung von `board` nennt nur „keine Änderung"; hier steht, welche
        # Nummer schon dasteht — ohne sie müsste der Leser das Ticket öffnen, um zu
        # wissen, ob der Knopf etwas gemeint hat.
        erg["meldung"] = (f"{erg['ref']} steht bereits auf Sprint {ziel} — nichts zu tun. "
                          f"Das Ticket ist unverändert und es wurde nichts committet.")
    return erg
