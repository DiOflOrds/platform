"""BCK-Inbox (SWR-020, SWR-024; ADR-003): offene Decision Requests listen,
Entscheidungen annehmen — Decision-Log-Zeile + Ticket-Notiz + sofortiger
Git-Commit (nur die eigenen Schreibziele, Lesson T-0014).
"""
import os
import re
import subprocess
import sys
from datetime import date

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import board  # noqa: E402

FINAL = ("done", "rejected")
COMMIT_IDENTITAET = ["-c", "user.name=Mensch via Inbox",
                     "-c", "user.email=geraldine.john90@gmail.com"]


class InboxFehler(Exception):
    def __init__(self, code, meldung):
        super().__init__(meldung)
        self.code = code


def _dr_tickets(p0):
    tickets, _ = board.lade_tickets(p0)
    return [t for t in tickets
            if t.get("typ") == "decision-request" and t.get("status") not in FINAL]


def liste(root):
    """Offene DRs mit Body (Kontext/Optionen/Frist/Default stehen im Ticket-Text)."""
    p0 = os.path.join(root, "p0")
    eintraege = []
    for t in _dr_tickets(p0):
        pfad = os.path.join(p0, "tickets", f"{t['id']}.md")
        body = re.sub(r"(?s)^---.*?---\s*", "", open(pfad, encoding="utf-8").read())
        eintraege.append({"id": t["id"], "titel": t.get("titel"), "status": t.get("status"),
                          "prio": t.get("prio"), "sprint": t.get("sprint"), "body": body.strip()})
    return {"inbox": eintraege}


def _naechste_d_id(log_pfad):
    text = open(log_pfad, encoding="utf-8").read() if os.path.exists(log_pfad) else ""
    ids = [int(m) for m in re.findall(r"\|\s*D(\d{3})\s*\|", text)]
    return f"D{(max(ids) + 1 if ids else 0):03d}"


def entscheide(root, ticket_id, option, begruendung=""):
    """Entscheidung annehmen: Log-Zeile + Ticket-Notiz + BOARD + Commit. Gibt D-ID zurück."""
    if not option or not str(option).strip():
        raise InboxFehler(400, "option darf nicht leer sein")
    p0 = os.path.join(root, "p0")
    ticket_pfad = os.path.join(p0, "tickets", f"{ticket_id}.md")
    if not re.fullmatch(r"T-\d{4}", ticket_id or "") or not os.path.exists(ticket_pfad):
        raise InboxFehler(404, f"unbekanntes Ticket: {ticket_id}")
    offene = {t["id"]: t for t in _dr_tickets(p0)}
    if ticket_id not in offene:
        raise InboxFehler(400, f"{ticket_id} ist kein offener Decision Request")
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
    heute = date.today().isoformat()
    log_pfad = os.path.join(p0, "management", "decisions", "decision-log.md")
    d_id = _naechste_d_id(log_pfad)
    zeile = (f"| {d_id} | {heute} | Mensch (E. John, via Inbox) | **{option.strip()}** "
             f"| lt. {ticket_id} | {begruendung.strip() or '—'} | {ticket_id} |")
    with open(log_pfad, "a", encoding="utf-8", newline="\n") as f:
        f.write(zeile + "\n")
    with open(ticket_pfad, "a", encoding="utf-8", newline="\n") as f:
        f.write(f"\n**Entscheidung ({d_id}, via Inbox, {heute}):** {option.strip()}"
                f"{' — ' + begruendung.strip() if begruendung.strip() else ''}\n")
    tickets, _ = board.lade_tickets(p0)
    open(os.path.join(p0, "BOARD.md"), "w", encoding="utf-8", newline="\n").write(
        board.generiere_board(tickets))
    rel = [os.path.join("management", "decisions", "decision-log.md"),
           os.path.join("tickets", f"{ticket_id}.md"), "BOARD.md"]
    add = subprocess.run(["git", "-C", p0, "add", "--"] + rel, capture_output=True, text=True)
    commit = subprocess.run(["git", "-C", p0] + COMMIT_IDENTITAET +
                            ["commit", "-m", f"{ticket_id}: Entscheidung via Inbox ({d_id})"],
                            capture_output=True, text=True)
    if add.returncode or commit.returncode:
        raise InboxFehler(503, "Git-Commit fehlgeschlagen: " +
                          (add.stderr + commit.stderr + commit.stdout).strip()[:400])
    return {"entscheidung": d_id, "ticket": ticket_id, "option": option.strip()}
