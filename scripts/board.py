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
import os
import re
import subprocess
import sys
from datetime import date

FELDER = ["id", "titel", "typ", "prozess", "rolle", "sprint", "status", "prio", "erstellt"]
STATUS = ["open", "in_analysis", "in_progress", "in_review", "blocked", "done", "rejected"]
TYPEN = ["task", "problem", "change-request", "decision-request", "clarification",
         "finding", "feedback", "skriptifizierung"]
PRIOS = ["kritisch", "hoch", "mittel", "niedrig"]
PRIO_RANG = {p: i for i, p in enumerate(PRIOS)}
ID_MUSTER = re.compile(r"^T-\d{4}$")
DATUM_MUSTER = re.compile(r"^\d{4}-\d{2}-\d{2}$")
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


def status_in_head(repo, datei):
    """Status des Tickets in Git HEAD (None wenn neu/kein Git)."""
    try:
        out = subprocess.run(
            ["git", "-C", repo, "show", f"HEAD:tickets/{datei}"],
            capture_output=True, text=True, timeout=10)
        if out.returncode != 0:
            return None
        alt, err = parse_frontmatter(out.stdout)
        return None if err else alt.get("status")
    except (OSError, subprocess.SubprocessError):
        return None


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
    if t.get("erstellt") and not DATUM_MUSTER.match(t["erstellt"]):
        fehler.append(f"ungültiges Datum erstellt: {t['erstellt']}")
    bb = parse_liste(t.get("blocked_by"))
    for ref in bb:
        if ref == tid:
            fehler.append("blocked_by verweist auf sich selbst")
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
        if t.get("frist") and not DATUM_MUSTER.match(t["frist"]):
            fehler.append(f"ungültiges Datum frist: {t['frist']}")
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
        if alt and alt in STATUS and alt != t["status"]:
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


def offene_blocker(t, tickets_nach_id):
    """IDs der blocked_by-Tickets, die noch nicht done sind."""
    return [ref for ref in parse_liste(t.get("blocked_by"))
            if tickets_nach_id.get(ref, {}).get("status") != "done"]


def generiere_board(tickets, stand=None):
    """BOARD.md-Inhalt deterministisch erzeugen."""
    zeilen = ["# Board (generiert von platform/scripts/board.py — nicht von Hand editieren)",
              f"\nStand: {stand or date.today().isoformat()} · Tickets: {len(tickets)}\n"]
    for st in STATUS:
        gruppe = [t for t in tickets if t.get("status") == st]
        if not gruppe:
            continue
        zeilen.append(f"\n## {st} ({len(gruppe)})\n")
        zeilen.append("| ID | Titel | Typ | Rolle | Prio | Sprint | blockiert durch |")
        zeilen.append("|---|---|---|---|---|---|---|")
        for t in sorted(gruppe, key=lambda x: (PRIO_RANG.get(x.get("prio"), 99), x.get("id", ""))):
            bb = ", ".join(parse_liste(t.get("blocked_by"))) or "—"
            zeilen.append(f"| [{t['id']}](tickets/{t['id']}.md) | {t['titel']} | {t['typ']} "
                          f"| {t['rolle']} | {t['prio']} | {t['sprint']} | {bb} |")
    return "\n".join(zeilen) + "\n"


def setze_status(repo, tid, neu, reviewer=None, notiz=None):
    """T-0062: Statuswechsel als Skript-Route — Übergangsprüfung gegen den
    AKTUELLEN Dateizustand, Pflichtfeld-Logik (reviewer bei in_review),
    geändert-Datum, Validierung, BOARD-Regeneration. Wirft ValueError bei
    unzulässigem Übergang (Session und Tick nutzen denselben Pfad)."""
    pfad = os.path.join(repo, "tickets", f"{tid}.md")
    if not os.path.exists(pfad):
        raise ValueError(f"unbekanntes Ticket: {tid}")
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
    open(pfad, "w", encoding="utf-8", newline="\n").write(text)
    tickets, probleme = lade_tickets(repo)
    probleme += validiere_alle(tickets, repo, git_pruefen=False)
    if probleme:
        raise ValueError("Ticket-Update invalide: " + "; ".join(probleme))
    open(os.path.join(repo, "BOARD.md"), "w", encoding="utf-8", newline="\n").write(
        generiere_board(tickets))


def _status_cli(argv):
    """`board.py <repo> status T-xxxx <neu> [--reviewer r] [--notiz text]` (T-0062)."""
    repo, rest = argv[0], argv[2:]
    reviewer = notiz = None
    pos = []
    i = 0
    while i < len(rest):
        if rest[i] == "--reviewer":
            reviewer, i = rest[i + 1], i + 2
        elif rest[i] == "--notiz":
            notiz, i = rest[i + 1], i + 2
        else:
            pos.append(rest[i])
            i += 1
    if len(pos) != 2:
        print("Nutzung: board.py <repo> status T-xxxx <neu> [--reviewer r] [--notiz text]")
        return 2
    try:
        setze_status(repo, pos[0], pos[1], reviewer, notiz)
    except ValueError as e:
        print(f"STATUS ABGELEHNT: {e}")
        return 1
    print(f"OK: {pos[0]} -> {pos[1]}, BOARD.md aktualisiert.")
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
    sys.exit(main(sys.argv[1:]))
