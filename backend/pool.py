# -*- coding: utf-8 -*-
"""pool.py (pm/T-0022, Teil "Anlegen"): Schreibpfad für den Projekt-Pool.

Zweiter Schreibziel-Typ neben Tickets (tickets.py) und Inbox-Entscheidungen
(inbox.py) — aber dasselbe Muster: schreiben, nur das eigene Ziel `git add`,
sofort committen mit erkennbarer Herkunft, bei einem gescheiterten Commit die
Arbeitskopie zurücknehmen (SWR-078-Analogon). Die Tabellenlogik ist bewusst
NICHT neu geschrieben — sie nutzt `aggregation.pool_abschnitte` /
`parse_md_tabellen`, denselben Parser, den `/api/pool` zum Lesen benutzt
(Lesson 2026-08-16: keine zweite Tabellenlogik für dieselbe Datei).

"Starten" (Projektordner + G0-Decision-Request) ist NICHT Teil dieses Moduls —
bewusst zurückgestellt (pm/T-0022, Abschnitt "Nicht in dieser Session"): das
ist ein größerer, riskanterer Schreibvorgang (Ordner, Requirements, CI-Listen
— siehe der frische Befund pm/T-0026 am selben Tag, als ein neuer Projekt-
Ordner ein Matrix-Gate unsichtbar brach) und verdient eine eigene Session.
"""
import os
import re
import subprocess

from . import aggregation

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
