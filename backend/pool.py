# -*- coding: utf-8 -*-
"""pool.py (pm/T-0022): Schreibpfad für den Projekt-Pool.

Zweiter Schreibziel-Typ neben Tickets (tickets.py) und Inbox-Entscheidungen
(inbox.py) — aber dasselbe Muster: schreiben, nur das eigene Ziel `git add`,
sofort committen mit erkennbarer Herkunft, bei einem gescheiterten Commit die
Arbeitskopie zurücknehmen (SWR-078-Analogon). Die Tabellenlogik ist bewusst
NICHT neu geschrieben — sie nutzt `aggregation.pool_abschnitte` /
`parse_md_tabellen`, denselben Parser, den `/api/pool` zum Lesen benutzt
(Lesson 2026-08-16: keine zweite Tabellenlogik für dieselbe Datei).

Teil "Anlegen" (`kandidat_anlegen`): Kandidat in die Pool-Tabelle schreiben.

Teil "Starten" (`kandidat_starten`, Routine-Session 2026-08-16, direkte
Fortsetzung): Nur für Technik-Kandidaten (Team-Kandidaten brauchen die
vollere Team-Gründung aus intake.md — Steckbrief, Profil, Datenklasse,
Zugänge — bewusst außerhalb dieses Tickets, siehe pm/T-0022 "Nicht im
Umfang"). Legt den Projektordner unter `projects/<pN>` an und stellt einen
G0-Decision-Request (T-0001) hinein — **Variante A** aus dem Ticket (keine
Antwort im Briefkasten, Default lt. Ticket): Der Knopf entscheidet nichts,
er bereitet vor (Playbook Kap. 16, Klasse A bleibt beim Menschen). Nutzt für
die Projekt-Nummerierung dieselbe Discovery wie Board/Matrix/Preflight
(`board.projekt_pfade`, Lesson p9/T-0007 — keine zweite Auflösungskopie) und
für BOARD.md dieselbe Generierung wie die Skript-Route (`board.generiere_board`).
"""
import os
import re
import shutil
import subprocess
import sys
from datetime import date, timedelta

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import board  # noqa: E402

from . import aggregation  # noqa: E402

HERKUNFT = "Mensch via HMI"
COMMIT_IDENTITAET = ["-c", f"user.name={HERKUNFT}", "-c", "user.email=mensch@hmi.local"]

# Team-Kandidaten tragen einen kurzen, technischen Namen (wie ein künftiger
# Team-Ordner: "team-x") — Technik-Kandidaten sind freier Backlog-Text
# (Bestand: "B4 Integrationsstrategie · B8 …", "JS-Frontend-Tests" — kein
# Kebab-Zwang, das wären keine echten Kandidatennamen).
NAME_MUSTER = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
FELD_MAX = 200

KATEGORIEN = {
    "team": {"ueberschrift": "Team-Kandidaten", "extra_spalten": ["Nutzen", "Voraussetzung"]},
    "technik": {"ueberschrift": "Technik-Kandidaten", "extra_spalten": ["Quelle"]},
}


class PoolFehler(Exception):
    """code = HTTP-Status, Meldung deutsch (Muster TicketFehler/InboxFehler)."""

    def __init__(self, code, meldung):
        super().__init__(meldung)
        self.code = code


def _naechste_nummer(text):
    """Laufende Nummer ÜBER BEIDE Kategorien hinweg (Auftrag platform/N-0005)."""
    ids = [int(m) for m in re.findall(r"(?m)^\|\s*(\d+)\s*\|", text)]
    return (max(ids) + 1) if ids else 1


def _zeile_bauen(nummer, kategorie, kat, name, kurzbeschreibung, werte):
    kandidat_zelle = f"**{name}** — {kurzbeschreibung}" if kategorie == "team" else name
    zellen = [str(nummer), kandidat_zelle] + [
        str((werte or {}).get(feld, "")).strip() for feld in kat["extra_spalten"]]
    return "| " + " | ".join(zellen) + " |"


def _zeile_einfuegen(text, ueberschrift, neue_zeile):
    """Neue Zeile ans ENDE der Tabelle im genannten Abschnitt (Auftrag: "neue
    Einträge ans Ende ihrer Kategorie"). None, wenn der Abschnitt fehlt."""
    zeilen = text.splitlines()
    start = None
    for i, z in enumerate(zeilen):
        s = z.strip()
        if s.startswith("## ") and ueberschrift in s:
            start = i
            break
    if start is None:
        return None
    letzte = None
    for i in range(start + 1, len(zeilen)):
        s = zeilen[i].strip()
        if s.startswith("## "):
            break
        if s.startswith("|"):
            letzte = i
    if letzte is None:
        return None
    neu = zeilen[:letzte + 1] + [neue_zeile] + zeilen[letzte + 1:]
    ergebnis = "\n".join(neu)
    if text.endswith("\n"):
        ergebnis += "\n"
    return ergebnis


def kandidat_anlegen(root, kategorie, kandidat, kurzbeschreibung, werte):
    """pm/T-0022 (Anlegen): Kandidat validieren, ans Ende seiner Kategorie
    anhängen, committen. Sofort im Pool-Reiter sichtbar (nächster GET
    /api/pool liest die Datei frisch) — kein Serverneustart nötig."""
    kat = KATEGORIEN.get(kategorie)
    if not kat:
        raise PoolFehler(400, f"unbekannte Kategorie '{kategorie}' — zulässig: "
                              + ", ".join(KATEGORIEN))
    name = (kandidat or "").strip()
    kurz = (kurzbeschreibung or "").strip()
    if kategorie == "team":
        if not (2 <= len(name) <= 40) or not NAME_MUSTER.fullmatch(name):
            raise PoolFehler(400, "Kandidat (Team): nur Kleinbuchstaben/Ziffern/Bindestrich, "
                                  "2-40 Zeichen, z. B. 'team-urlaub'")
        if not kurz or "\n" in kurz or len(kurz) > FELD_MAX:
            raise PoolFehler(400, f"Kurzbeschreibung: 1-{FELD_MAX} Zeichen, keine Zeilenumbrüche")
    else:
        if not name or "\n" in name or len(name) > FELD_MAX:
            raise PoolFehler(400, f"Kandidat: 1-{FELD_MAX} Zeichen, keine Zeilenumbrüche")
        kurz = ""
    for feld in kat["extra_spalten"]:
        wert = str((werte or {}).get(feld, "")).strip()
        if not wert or "\n" in wert or len(wert) > FELD_MAX:
            raise PoolFehler(400, f"{feld}: 1-{FELD_MAX} Zeichen, keine Zeilenumbrüche")

    pfad = os.path.join(root, *aggregation.POOL_DATEI)
    if not os.path.isfile(pfad):
        raise PoolFehler(404, "Projekt-Pool-Datei fehlt — " + "/".join(aggregation.POOL_DATEI))
    text = open(pfad, encoding="utf-8").read()

    # Doppelte Kandidaten ablehnen — über den vorhandenen Parser, keine zweite
    # Tabellenlogik (Lesson 2026-08-16).
    # Titel-Vergleich per Teilstring: echte Abschnitte tragen einen Zusatz
    # ("Team-Kandidaten (aus deiner ursprünglichen Vision)") — dieselbe Regel
    # wie beim Einfügen weiter unten (_zeile_einfuegen).
    abschnitte = aggregation.pool_abschnitte(text)
    ziel = next((a for a in abschnitte if kat["ueberschrift"] in (a["titel"] or "")), None)
    vorhandene = ziel["tabellen"][0]["zeilen"] if ziel and ziel["tabellen"] else []
    for z in vorhandene:
        zelle = (z[1] if len(z) > 1 else "").strip()
        if kategorie == "team" and f"**{name}**" in zelle:
            raise PoolFehler(409, f"Kandidat '{name}' existiert bereits im Pool")
        if kategorie == "technik" and zelle.lower() == name.lower():
            raise PoolFehler(409, f"Kandidat '{name}' existiert bereits im Pool")

    nummer = _naechste_nummer(text)
    neue_zeile = _zeile_bauen(nummer, kategorie, kat, name, kurz, werte)
    neuer_text = _zeile_einfuegen(text, kat["ueberschrift"], neue_zeile)
    if neuer_text is None:
        raise PoolFehler(404, f"Abschnitt '{kat['ueberschrift']}' nicht in der Pool-Datei gefunden")

    open(pfad, "w", encoding="utf-8", newline="\n").write(neuer_text)
    repo = os.path.join(root, aggregation.POOL_DATEI[0])
    rel = os.path.join(*aggregation.POOL_DATEI[1:])
    add = subprocess.run(["git", "-C", repo, "add", "--", rel], capture_output=True, text=True)
    commit = subprocess.run(
        ["git", "-C", repo] + COMMIT_IDENTITAET +
        ["commit", "-m", f"Projekt-Pool: Kandidat '{name}' angelegt (#{nummer}, {kategorie}) — {HERKUNFT}"],
        capture_output=True, text=True)
    if add.returncode or commit.returncode:
        open(pfad, "w", encoding="utf-8", newline="\n").write(text)  # Rücknahme (Muster tickets.py)
        raise PoolFehler(503, "Git-Commit fehlgeschlagen — die Änderung wurde zurückgenommen: "
                          + (add.stderr + commit.stderr + commit.stdout).strip()[:400])
    return {"ok": True, "kategorie": kategorie, "kandidat": name, "nummer": nummer,
            "meldung": f"Kandidat '{name}' angelegt (#{nummer}, {kat['ueberschrift']}) — "
                      "committet, ohne Serverneustart im Pool-Reiter sichtbar."}


# ---------------------------------------------------------------------------
# Teil "Starten" (pm/T-0022, zweiter Ticketteil)
# ---------------------------------------------------------------------------

_PROJEKT_MUSTER = re.compile(r"^p(\d+)$")
G0_FRIST_TAGE = 7  # wie p10/T-0002, p5/T-0001: eine Woche zum Lesen des Entwurfs


def _naechste_projektnummer(root):
    """Nächste freie Projektnummer p<N> — höchste bestehende + 1.

    Nutzt `board.projekt_pfade` (dieselbe Discovery wie Board/Matrix/Preflight,
    Top-Level UND Sammel-Repo `projects/`) statt eines eigenen Verzeichnis-Scans
    — Lesson p9/T-0007: keine zweite Kopie derselben Auflösung.
    """
    hoechste = 0
    for name, _pfad in board.projekt_pfade(root):
        m = _PROJEKT_MUSTER.match(name)
        if m:
            hoechste = max(hoechste, int(m.group(1)))
    return hoechste + 1


def _technik_spalten_und_zeilen(text):
    """(spalten, zeilen) der Technik-Kandidaten-Tabelle, ([], []) wenn keine da."""
    kat = KATEGORIEN["technik"]
    abschnitte = aggregation.pool_abschnitte(text)
    ziel = next((a for a in abschnitte if kat["ueberschrift"] in (a["titel"] or "")), None)
    if not ziel or not ziel["tabellen"]:
        return [], []
    return ziel["tabellen"][0]["spalten"], ziel["tabellen"][0]["zeilen"]


def _technik_zeile_finden(text, kandidat):
    """Zellen der Technik-Kandidaten-Zeile mit passendem 'Kandidat'-Text (Groß-/
    Kleinschreibung und Randleerzeichen egal). None, wenn nicht gefunden."""
    spalten, zeilen = _technik_spalten_und_zeilen(text)
    if not spalten:
        return None
    idx = spalten.index("Kandidat") if "Kandidat" in spalten else 1
    gesucht = kandidat.strip().lower()
    for zeile in zeilen:
        zelle = (zeile[idx] if len(zeile) > idx else "").strip()
        if zelle.lower() == gesucht:
            return zeile
    return None


def _ist_team_kandidat(text, kandidat):
    """True, wenn der Text (auch als Teilstring, wegen '**name** — Kurzbeschreibung')
    in einer Zeile der Team-Kandidaten-Tabelle vorkommt — für die Fehlermeldung."""
    kat = KATEGORIEN["team"]
    abschnitte = aggregation.pool_abschnitte(text)
    ziel = next((a for a in abschnitte if kat["ueberschrift"] in (a["titel"] or "")), None)
    if not ziel or not ziel["tabellen"]:
        return False
    gesucht = kandidat.strip().lower()
    return any(gesucht in " ".join(z).lower() for z in ziel["tabellen"][0]["zeilen"])


def _technik_zeile_entfernen(text, ueberschrift, spalten_index, gesucht):
    """Die Tabellenzeile mit dem gesuchten Kandidat-Text aus dem genannten Abschnitt
    entfernen (Muster: `_zeile_einfuegen`, nur umgekehrt). Gibt (neuer_text,
    entfernte_rohzeile) zurück, (None, None) wenn nichts gefunden wurde."""
    zeilen = text.splitlines()
    start = None
    for i, z in enumerate(zeilen):
        s = z.strip()
        if s.startswith("## ") and ueberschrift in s:
            start = i
            break
    if start is None:
        return None, None
    ende = len(zeilen)
    for i in range(start + 1, len(zeilen)):
        if zeilen[i].strip().startswith("## "):
            ende = i
            break
    for i in range(start + 1, ende):
        s = zeilen[i].strip()
        if not s.startswith("|"):
            continue
        zellen = [z.strip() for z in s.strip("|").split("|")]
        if len(zellen) > spalten_index and zellen[spalten_index].strip().lower() == gesucht:
            neu = zeilen[:i] + zeilen[i + 1:]
            ergebnis = "\n".join(neu)
            if text.endswith("\n"):
                ergebnis += "\n"
            return ergebnis, zeilen[i]
    return None, None


def _projekt_dateien_schreiben(pfad, neuer_name, name, quelle, nummer_text, frist, heute_iso):
    """Skelett eines neuen Projekts vor G0 — README, Auftrags-Entwurf, leeres
    Decision-Log, Steckbrief, der G0-DR selbst (T-0001) und das dazu passende
    BOARD.md (über `board.generiere_board` erzeugt, keine zweite Kopie der
    Board-Formatierung — Lesson 2026-08-16)."""
    os.makedirs(os.path.join(pfad, "docs"), exist_ok=True)
    os.makedirs(os.path.join(pfad, "management", "decisions"), exist_ok=True)
    os.makedirs(os.path.join(pfad, "tickets"), exist_ok=True)

    herkunft_zeile = f"Technik-Kandidat #{nummer_text}" + (f", Quelle: {quelle}" if quelle else "")

    readme = (
        f"# {neuer_name}\n\n"
        f"Projektordner, über den Projekt-Pool gestartet (pm/T-0022) — Kandidat "
        f"„{name}“ ({herkunft_zeile}). Wartet auf G0-Freigabe, siehe `tickets/T-0001.md`; "
        f"Auftrags-Entwurf in `docs/01-projektauftrag.md`.\n"
    )
    open(os.path.join(pfad, "README.md"), "w", encoding="utf-8", newline="\n").write(readme)

    auftrag = (
        f"# Projektauftrag {neuer_name} — „{name}“ (v0.1, Entwurf vor G0)\n\n"
        f"*{heute_iso}, PL. Herkunft: Projekt-Pool (`pm/management/projekt-pool.md`, pm/D005), "
        f"{herkunft_zeile}.*\n\n"
        "## Was und Warum\n\n"
        f"Kandidat aus dem ASPICE-Backlog: **{name}**"
        + (f" ({quelle})" if quelle else "") + ". Dieser Auftrag ist ein Entwurf, automatisch "
        "aus dem Pool-Eintrag erzeugt — Ziel, Abnahmekriterien und Rahmen werden mit der "
        "Sprint-0-Planung nach der G0-Freigabe geschärft (intake.md v3, Schritt 5). Der Knopf, "
        "der diesen Ordner angelegt hat, hat nichts entschieden (Playbook Kap. 16, Klasse A "
        "bleibt beim Menschen) — die Freigabe steht als `tickets/T-0001.md` in der Inbox.\n\n"
        "## Abnahmekriterien\n\n"
        "*Wird mit der Sprint-0-Planung nach G0 ergänzt.*\n\n"
        "## Rahmen\n\n"
        f"**Umsetzung als Ordner `projects/{neuer_name}`** (pm/D003, Sammel-Repo) — kein neues "
        "GitHub-Repo nötig.\n\n"
        "## Abgrenzung\n\n"
        "*Wird mit der Sprint-0-Planung nach G0 ergänzt.*\n"
    )
    open(os.path.join(pfad, "docs", "01-projektauftrag.md"), "w",
        encoding="utf-8", newline="\n").write(auftrag)

    log = (
        f"# Decision Log {neuer_name}\n\n"
        "*Append-only — Entscheidungen werden nie überschrieben, nur ergänzt (Playbook Kap. 16).*\n\n"
        "Noch keine Entscheidung — D000 folgt mit der Antwort auf T-0001 (G0).\n"
    )
    open(os.path.join(pfad, "management", "decisions", "decision-log.md"), "w",
        encoding="utf-8", newline="\n").write(log)

    steckbrief = f'beschreibung: "{name}"\n'
    open(os.path.join(pfad, "steckbrief.yaml"), "w", encoding="utf-8", newline="\n").write(steckbrief)

    ticket = (
        "---\n"
        "id: T-0001\n"
        f'titel: "DR: G0 — Projektauftrag {neuer_name} „{name}“ freigeben"\n'
        "typ: decision-request\n"
        "prozess: man3\n"
        "rolle: pl\n"
        "sprint: 0\n"
        "status: open\n"
        "prio: mittel\n"
        "reviewer: qm\n"
        "blocked_by: []\n"
        f"repo: {neuer_name}\n"
        "optionen: [G0a, G0b, G0c]\n"
        f"frist: {frist}\n"
        "default: G0a\n"
        f"geändert: {heute_iso}\n"
        f"erstellt: {heute_iso}\n"
        "---\n\n"
        "## Sachverhalt\n\n"
        f"Kandidat aus dem Projekt-Pool (`pm/management/projekt-pool.md`, pm/D005): **{name}**"
        + (f" — Quelle: {quelle}" if quelle else "") + ". Über den „Starten“-Knopf "
        "(pm/T-0022, Variante A) angelegt: Der Knopf hat den Ordner "
        f"`projects/{neuer_name}` und diesen Antrag erzeugt, aber **nichts entschieden** — die "
        "Freigabe bleibt bei dir (Playbook Kap. 16). Entwurf des Projektauftrags: "
        "`docs/01-projektauftrag.md`.\n\n"
        "## Optionen\n\n"
        "- **G0a (Empfehlung/Default):** freigeben — Sprint-0-Planung (Anforderungen, "
        "Abnahmekriterien) startet.\n"
        "- **G0b:** mit Änderungen (bitte in der Begründung benennen).\n"
        "- **G0c:** zurückweisen — der Kandidat bleibt aus dem Pool entfernt; bei Bedarf neu "
        "einreichen.\n\n"
        "## Stichproben (P1-E4-Konvention)\n\n"
        "| # | Artefakt | Wie | Status |\n"
        "|---|---|---|---|\n"
        "| 1 | Projektauftrag-Entwurf — trifft die Beschreibung den Kandidaten? | "
        f"`{neuer_name}/docs/01-projektauftrag.md` | offen — 2 Min Lesen |\n\n"
        "Zähler: 0 erledigt / 1 offen.\n\n"
        "## Antwortfrist und Default\n\n"
        f"**Frist:** {frist} · **Default:** G0a.\n"
    )
    open(os.path.join(pfad, "tickets", "T-0001.md"), "w",
        encoding="utf-8", newline="\n").write(ticket)

    tickets, probleme = board.lade_tickets(pfad)
    probleme += board.validiere_alle(tickets, pfad, git_pruefen=False)
    if probleme:
        # Sollte nie passieren (Ticket wird oben aus einer festen Vorlage gebaut) —
        # wenn doch, lieber laut scheitern als ein kaputtes Board committen.
        raise PoolFehler(500, "Erzeugter G0-Antrag ist ungültig: " + "; ".join(probleme))
    open(os.path.join(pfad, "BOARD.md"), "w", encoding="utf-8", newline="\n").write(
        board.generiere_board(tickets))


def kandidat_starten(root, kandidat):
    """pm/T-0022 Teil 2 ("Starten"), Variante A (keine Antwort im Briefkasten,
    Default lt. Ticket): Der Knopf ENTSCHEIDET NICHTS (Klasse A bleibt beim
    Menschen, Playbook Kap. 16) — er legt den Projektordner unter
    `projects/<pN>` an und stellt den G0-Decision-Request (T-0001) hinein, in
    genau einem Commit im Sammel-Repo `projects` (SWR-Analogon zu 078/088:
    scheitert der Commit, bleibt nichts auf der Platte zurück).

    Nur Technik-Kandidaten — Team-Kandidaten brauchen die vollere Team-Gründung
    aus `intake.md` (Steckbrief, Profil, Datenklasse, Zugänge) und sind bewusst
    außerhalb dieses Tickets ("Nicht im Umfang").

    Zweiter Schritt, bestmöglich statt hart gekoppelt: der gestartete Kandidat
    wird aus dem Pool entfernt (eigener Commit im Repo `pm`) — er ist kein
    Kandidat mehr, sondern ein Projekt mit eigenem G0-Antrag. Scheitert NUR
    dieser zweite Commit, bleibt das neue Projekt bestehen (eine Rücknahme
    würde einen bereits sichtbaren G0-Antrag wieder verschwinden lassen, was
    schlimmer ist als ein doppelt geführter Kandidat) — die Meldung sagt das
    in Klartext, damit es nicht wie B038 in einer Logdatei verschwindet.
    """
    name = (kandidat or "").strip()
    if not name:
        raise PoolFehler(400, "kandidat fehlt")
    if "|" in name or '"' in name or "\n" in name:
        raise PoolFehler(400, "Kandidat enthält ein Zeichen (| oder \" oder Zeilenumbruch), das "
                              "im Ticket-Frontmatter oder in einer Markdown-Tabelle das Format "
                              "sprengen würde — bitte den Pool-Eintrag zuerst bereinigen.")

    pool_pfad = os.path.join(root, *aggregation.POOL_DATEI)
    if not os.path.isfile(pool_pfad):
        raise PoolFehler(404, "Projekt-Pool-Datei fehlt — " + "/".join(aggregation.POOL_DATEI))
    pool_text = open(pool_pfad, encoding="utf-8").read()

    zeile = _technik_zeile_finden(pool_text, name)
    if zeile is None:
        if _ist_team_kandidat(pool_text, name):
            raise PoolFehler(400, f"'{name}' ist ein Team-Kandidat — Team-Gründungen laufen über "
                                  "den vollen Weg aus intake.md (Steckbrief, Profil, Datenklasse, "
                                  "Zugänge) und sind bewusst nicht Teil dieses Knopfs (pm/T-0022, "
                                  "\"Nicht im Umfang\"). Bitte per Briefkasten anstoßen.")
        raise PoolFehler(404, f"Technik-Kandidat '{name}' nicht im Pool gefunden.")
    nummer_text = zeile[0].strip() if zeile else ""
    quelle = zeile[2].strip() if len(zeile) > 2 else ""

    projects_repo = os.path.join(root, "projects")
    if not os.path.isdir(os.path.join(projects_repo, ".git")):
        raise PoolFehler(404, "Sammel-Repo 'projects' fehlt oder ist kein Git-Repo.")
    nummer = _naechste_projektnummer(root)
    neuer_name = f"p{nummer}"
    projekt_pfad = os.path.join(projects_repo, neuer_name)
    if os.path.exists(projekt_pfad):
        raise PoolFehler(409, f"Projektordner {neuer_name} existiert bereits — bitte CM/Session "
                              "informieren (Nummernkollision).")

    heute = date.today()
    frist = (heute + timedelta(days=G0_FRIST_TAGE)).isoformat()
    heute_iso = heute.isoformat()

    try:
        _projekt_dateien_schreiben(projekt_pfad, neuer_name, name, quelle, nummer_text,
                                   frist, heute_iso)
    except (OSError, PoolFehler):
        shutil.rmtree(projekt_pfad, ignore_errors=True)
        raise

    add = subprocess.run(["git", "-C", projects_repo, "add", "--", neuer_name],
                         capture_output=True, text=True)
    commit_msg = (f"{neuer_name}: aus dem Projekt-Pool gestartet („{name}“, "
                 f"Technik-Kandidat) — Ordner + G0-Antrag T-0001, {HERKUNFT}")
    commit = subprocess.run(["git", "-C", projects_repo] + COMMIT_IDENTITAET +
                            ["commit", "-m", commit_msg], capture_output=True, text=True)
    if add.returncode or commit.returncode:
        shutil.rmtree(projekt_pfad, ignore_errors=True)
        raise PoolFehler(503, "Git-Commit fehlgeschlagen — der Projektordner wurde nicht "
                              "angelegt, es steht nichts auf der Platte: " +
                          (add.stderr + commit.stderr + commit.stdout).strip()[:400])

    ref = aggregation.ref(neuer_name, "T-0001")
    grundmeldung = (f"'{name}' gestartet: {neuer_name} angelegt, G0-Antrag {ref} in der Inbox "
                    f"(Frist {frist}, Default G0a).")

    spalten, _zeilen = _technik_spalten_und_zeilen(pool_text)
    idx = spalten.index("Kandidat") if spalten and "Kandidat" in spalten else 1
    neuer_pool_text, _entfernt = _technik_zeile_entfernen(
        pool_text, KATEGORIEN["technik"]["ueberschrift"], idx, name.strip().lower())
    if neuer_pool_text is None:
        # Kandidat ist zwischen Lesen und Schreiben verschwunden (Race mit einer
        # parallelen Session/Anlegen) — das Projekt steht trotzdem, kein Datenverlust,
        # nur eine sichtbare Dopplung im Pool.
        return {"ok": True, "kandidat": name, "projekt": neuer_name, "ticket": "T-0001", "ref": ref,
                "meldung": grundmeldung + " ACHTUNG: der Kandidat konnte nicht mehr aus dem Pool "
                          "entfernt werden (Datei änderte sich zwischen Lesen und Schreiben) — "
                          "bitte die Zeile manuell in pm/management/projekt-pool.md prüfen."}

    pm_repo = os.path.join(root, aggregation.POOL_DATEI[0])
    rel = os.path.join(*aggregation.POOL_DATEI[1:])
    open(pool_pfad, "w", encoding="utf-8", newline="\n").write(neuer_pool_text)
    add2 = subprocess.run(["git", "-C", pm_repo, "add", "--", rel], capture_output=True, text=True)
    commit2 = subprocess.run(
        ["git", "-C", pm_repo] + COMMIT_IDENTITAET +
        ["commit", "-m", f"Projekt-Pool: '{name}' gestartet als {neuer_name} (pm/T-0022 Teil 2) "
                         f"— {HERKUNFT}"],
        capture_output=True, text=True)
    if add2.returncode or commit2.returncode:
        open(pool_pfad, "w", encoding="utf-8", newline="\n").write(pool_text)  # Rücknahme nur hier
        return {"ok": True, "kandidat": name, "projekt": neuer_name, "ticket": "T-0001", "ref": ref,
                "meldung": grundmeldung + " ACHTUNG: der Kandidat konnte NICHT aus dem Pool "
                          "entfernt werden (Git-Commit fehlgeschlagen: " +
                          (add2.stderr + commit2.stderr + commit2.stdout).strip()[:200] +
                          ") — bitte die Zeile manuell in pm/management/projekt-pool.md prüfen."}

    return {"ok": True, "kandidat": name, "projekt": neuer_name, "ticket": "T-0001", "ref": ref,
            "meldung": grundmeldung + " Aus dem Pool entfernt, committet."}
