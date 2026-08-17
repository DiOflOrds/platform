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
from . import git_schreiben  # noqa: E402  — SWR-134: der eine Schreibweg nach Git

HERKUNFT = "Mensch via HMI"
COMMIT_IDENTITAET = ["-c", f"user.name={HERKUNFT}", "-c", "user.email=mensch@hmi.local"]

# Team-Kandidaten tragen einen kurzen, technischen Namen (wie ein künftiger
# Team-Ordner: "team-x") — Technik-Kandidaten sind freier Backlog-Text
# (Bestand: "B4 Integrationsstrategie · B8 …", "JS-Frontend-Tests" — kein
# Kebab-Zwang, das wären keine echten Kandidatennamen).
NAME_MUSTER = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
# pm/N-0023 (2026-08-16): 200 Zeichen war für eine "Aufgabe" (Kurzbeschreibung
# bzw. bei Technik-Kandidaten der Kandidat-Text selbst) zu knapp — das gilt
# ausdrücklich auch für Kandidaten, die eine KI vorschlägt (typischerweise
# mehrsätzig). Deutlich angehoben statt entfernt: die Zeile bleibt EINE Zeile
# einer Markdown-Tabelle (Speicherformat, siehe `_zeile_bauen`), ein Vielfaches
# an Text ist aber möglich. Nur `|` bleibt hart verboten (sprengt die Tabelle);
# Zeilenumbrüche werden ab jetzt normalisiert statt abgelehnt (`_text_bereinigen`).
#
# pm/N-0024 (2026-08-16): Auch 4000 Zeichen reichten für ein reales "Quelle"-Feld
# nicht — zweiter Fehlversuch, eine konkrete Zahl zu raten (dieselbe Zusatzspalte
# lief seit T-0027 durch dieselbe Prüfung wie Kurzbeschreibung/Kandidat-Text, nur
# eben mit derselben Zahl). Der eigentliche Grund für eine Obergrenze war nie ein
# inhaltliches Limit, sondern der Schutz der Markdown-Tabellenzeile — und dafür
# ist, wie in T-0027 bereits festgehalten, einzig `|` das Zeichen, das wirklich
# etwas sprengt. FELD_MAX ist deshalb keine Inhaltsgrenze mehr, sondern nur noch
# eine technische Notbremse gegen einen versehentlichen Mega-Paste.
FELD_MAX = 200_000


def _text_bereinigen(wert):
    """pm/N-0023: Freitext für die Markdown-Tabellenzeile mehrheitsfähig machen.

    Zeilenumbrüche (Copy/Paste aus mehrsätzigem, auch KI-generiertem Text)
    werden zu Leerzeichen statt das Feld abzulehnen — die Zeile bleibt eine
    einzelne Tabellenzeile, aber der Mensch muss den Text nicht mehr selbst
    umformatieren. Mehrfache Leerzeichen dabei entstehend werden zusammengezogen.
    """
    ohne_umbrueche = re.sub(r"\s*[\r\n]+\s*", " ", str(wert or ""))
    return re.sub(r" {2,}", " ", ohne_umbrueche).strip()

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


# SWR-124 (pm/T-0057): ab wann ein Freitext NICHT mehr in die Tabellenzelle gehört.
#
# ⚠ Die Zahl ist gemessen, nicht geschätzt. Die längsten Zellen im Bestand vor diesem
# Ticket: 229 und 153 Zeichen (die 229 ist die Handreparatur aus Sprint 9). Der Fall,
# der das Ticket ausgelöst hat, hatte rund 9.000. 400 liegt deutlich über allem, was je
# als Tabellenzelle gemeint war, und weit unter dem, was eine Tabelle unlesbar macht.
#
# **Das ist keine Inhaltsgrenze.** Der Auftraggeber wird zu nichts gezwungen: Text
# oberhalb der Schwelle wird ausgelagert und verlinkt, nicht abgelehnt und nicht
# gekürzt. `FELD_MAX` bleibt daneben stehen, weil es eine andere Frage beantwortet
# (Notbremse gegen einen versehentlichen Mega-Paste), und wird davon nicht berührt.
ZELLE_MAX = 400
KANDIDATEN_VERZ = ("pm", "management", "kandidaten")


UMLAUTE = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}


def _slug(wert):
    """Dateinamensicherer Kurzname — kebab-case, wie die Kandidatennamen selbst.

    Umlaute werden umschrieben statt entfernt: aus „CSV-Export für Reports" wird
    `csv-export-fuer-reports` und nicht `csv-export-f-r-reports`. Der Dateiname wird
    von Menschen gelesen, und ein Wort mit einem Loch darin ist schlechter zu finden
    als eines mit einer Umschrift.
    """
    s = str(wert or "").lower()
    for a, b in UMLAUTE.items():
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s or "kandidat")[:60]


def _auslagern(root, name, feld, wert):
    """SWR-124: langen Freitext in eine eigene Datei legen, Zelle wird Kurztext + Verweis.

    **Warum auslagern und nicht begrenzen.** Eine Zeichengrenze im Formular zwänge den
    Auftraggeber, seinen Text zu kürzen — das ist die schlechtere Hälfte einer Wahl, bei
    der es eine bessere gibt. Der Text ist nicht das Problem; die **Tabellenzelle** ist
    der falsche Ort dafür.

    **Der Wortlaut wird nicht angetastet** — bis auf die Zeilenumbrüche, die
    `_text_bereinigen` schon vorher zu Leerzeichen gemacht hat. Rekonstruieren wäre
    Raten (B038); die Datei sagt deshalb ausdrücklich, dass sie den Text so führt, wie
    er angekommen ist.

    Rückgabe: `(zellentext, geschriebene_datei|None)`.
    """
    if len(wert) <= ZELLE_MAX:
        return wert, None
    verz = os.path.join(root, *KANDIDATEN_VERZ)
    os.makedirs(verz, exist_ok=True)
    datei = f"{_slug(name)}-{_slug(feld)}.md"
    pfad = os.path.join(verz, datei)
    kopf = (f"# {name} — {feld}\n\n"
            f"> Angelegt über das Pool-Formular. Der Text steht hier **im Wortlaut, wie er "
            f"angekommen ist**: Zeilenumbrüche werden vom Formular zu Leerzeichen "
            f"zusammengezogen und lassen sich nicht zurückrechnen (SWR-124, pm/T-0057).\n\n")
    with open(pfad, "w", encoding="utf-8", newline="\n") as f:
        f.write(kopf + wert.strip() + "\n")
    rel = "/".join(KANDIDATEN_VERZ[1:]) + "/" + datei     # relativ zur Pool-Datei im pm-Repo
    kurz = wert[:ZELLE_MAX // 2].rstrip()
    return f"{kurz} … ([Volltext](../{rel}))", pfad


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
        if "|" in kurz:
            raise PoolFehler(400, "Kurzbeschreibung: '|' ist nicht erlaubt (sprengt die "
                                  "Pool-Tabelle) — bitte umformulieren.")
        kurz = _text_bereinigen(kurz)
        if not kurz or len(kurz) > FELD_MAX:
            raise PoolFehler(400, f"Kurzbeschreibung: 1-{FELD_MAX} Zeichen (Zeilenumbrüche "
                                  "werden automatisch zu Leerzeichen).")
    else:
        if "|" in name:
            raise PoolFehler(400, "Kandidat: '|' ist nicht erlaubt (sprengt die Pool-Tabelle) "
                                  "— bitte umformulieren.")
        name = _text_bereinigen(name)
        if not name or len(name) > FELD_MAX:
            raise PoolFehler(400, f"Kandidat: 1-{FELD_MAX} Zeichen (Zeilenumbrüche werden "
                                  "automatisch zu Leerzeichen).")
        kurz = ""
    werte_bereinigt = {}
    for feld in kat["extra_spalten"]:
        wert = str((werte or {}).get(feld, "")).strip()
        if "|" in wert:
            raise PoolFehler(400, f"{feld}: '|' ist nicht erlaubt (sprengt die Pool-Tabelle) "
                                  "— bitte umformulieren.")
        wert = _text_bereinigen(wert)
        if not wert or len(wert) > FELD_MAX:
            raise PoolFehler(400, f"{feld}: 1-{FELD_MAX} Zeichen (Zeilenumbrüche werden "
                                  "automatisch zu Leerzeichen).")
        werte_bereinigt[feld] = wert  # bereinigt weiterreichen (_zeile_bauen liest daraus)
    werte = werte_bereinigt

    # SWR-124 (pm/T-0057): Freitext oberhalb von ZELLE_MAX wandert in eine eigene Datei;
    # die Tabelle behält Kurztext + Verweis. Erst hier, nach der Bereinigung — sonst
    # entschiede die Länge VOR dem Zusammenziehen der Umbrüche über die Auslagerung, und
    # zwei Texte mit gleichem Inhalt landeten verschieden.
    ausgelagert = []
    if kategorie == "team" and kurz:
        kurz, datei = _auslagern(root, name, "Kurzbeschreibung", kurz)
        if datei:
            ausgelagert.append(datei)
    for feld in list(werte):
        werte[feld], datei = _auslagern(root, name, feld, werte[feld])
        if datei:
            ausgelagert.append(datei)

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
    # SWR-124: die ausgelagerten Volltexte gehören in DENSELBEN Commit wie die Zeile, die
    # auf sie verweist. Getrennt committet gäbe es einen Zustand, in dem die Tabelle auf
    # eine Datei zeigt, die es in Git nicht gibt — ein toter Verweis, den niemand sieht.
    pfade = [rel] + [os.path.relpath(p, repo) for p in ausgelagert]
    _v = git_schreiben.verbuche(  # SWR-134
        repo, pfade,
        f"Projekt-Pool: Kandidat '{name}' angelegt (#{nummer}, {kategorie}) — {HERKUNFT}",
        COMMIT_IDENTITAET)
    if not _v.ok:
        open(pfad, "w", encoding="utf-8", newline="\n").write(text)  # Rücknahme (Muster tickets.py)
        # SWR-124: die Rücknahme muss auch die ausgelagerten Dateien mitnehmen — sonst
        # bliebe der Volltext eines Kandidaten liegen, den es im Pool nicht gibt.
        for p in ausgelagert:
            try:
                os.remove(p)
            except OSError:
                pass
        raise PoolFehler(503, "Git-Commit fehlgeschlagen — die Änderung wurde zurückgenommen: "
                          + _v.fehler[:400])
    return {"ok": True, "kategorie": kategorie, "kandidat": name, "nummer": nummer,
            "meldung": f"Kandidat '{name}' angelegt (#{nummer}, {kat['ueberschrift']}) — "
                      "committet, ohne Serverneustart im Pool-Reiter sichtbar."}


# ---------------------------------------------------------------------------
# Teil "Starten" (pm/T-0022, zweiter Ticketteil)
# ---------------------------------------------------------------------------

_PROJEKT_MUSTER = re.compile(r"^p(\d+)$")
G0_FRIST_TAGE = 7  # wie p10/T-0002, p5/T-0001: eine Woche zum Lesen des Entwurfs

# pm/T-0037 (B051, Befund 2) — Kopf des Decision-Logs, wortgleich zu den von Hand
# angelegten Logs (P10/P11) und passend zur Zeile aus `inbox.entscheide`.
LOG_TABELLENKOPF = ("| ID | Datum | Entscheider | Entscheidung | Optionen | Begründung "
                    "| Betroffene Artefakte |\n|---|---|---|---|---|---|---|\n")

# pm/T-0037 (B051, Befund 1) — Ein gestarteter Kandidat wird VERSCHOBEN, nicht
# gelöscht (Lesson B029: „ein Kandidat, der aus der Liste verschwindet, sieht aus
# wie einer, den nie jemand wollte"). Der Abschnitt wurde am 16.08. von Hand für
# Kandidat #13 eingeführt; der Knopf war da schon gebaut und kannte ihn nicht.
REALISIERT_UEBERSCHRIFT = "Realisiert"
REALISIERT_ABSCHNITT = (
    "## Realisiert (aus dem Pool herausgelaufen — Nummern werden nicht neu vergeben)\n\n"
    "| # | Kandidat | Wohin | Beleg |\n|---|---|---|---|\n")


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


def _realisiert_zeile_bauen(nummer_text, name, quelle, neuer_name, heute_iso):
    """pm/T-0037: Zeile für den Abschnitt „Realisiert" (# | Kandidat | Wohin | Beleg).

    „Wohin" und „Beleg" sind der Zweck des Abschnitts: nachvollziehbar bleibt nicht,
    DASS der Kandidat weg ist, sondern WOHIN er gegangen ist und woran das zu prüfen
    ist. `|` ist in `name` bereits verboten (siehe `kandidat_starten`); `quelle` kommt
    aus einer Tabellenzelle und kann es bauartbedingt nicht enthalten.
    """
    kandidat = name + (f" (Quelle: {quelle})" if quelle else "")
    wohin = (f"Projekt **{neuer_name.upper()}** (`projects/{neuer_name}`) — über den "
             "„Starten\"-Knopf angelegt (pm/T-0022 Teil 2)")
    beleg = f"{neuer_name}/T-0001 (G0-Antrag, gestartet {heute_iso})"
    return f"| {nummer_text or '—'} | {kandidat} | {wohin} | {beleg} |"


def _realisiert_zeile_einfuegen(text, neue_zeile):
    """pm/T-0037: Zeile ans Ende der „Realisiert"-Tabelle. Fehlt der Abschnitt,
    wird er am Dateiende angelegt — der Knopf darf nicht daran scheitern, dass
    eine von Hand gewachsene Konvention in einer Pool-Datei noch nicht steht."""
    ergebnis = _zeile_einfuegen(text, REALISIERT_UEBERSCHRIFT, neue_zeile)
    if ergebnis is not None:
        return ergebnis
    basis = text if text.endswith("\n") else text + "\n"
    return basis + "\n" + REALISIERT_ABSCHNITT + neue_zeile + "\n"


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

    # pm/T-0037 (B051, Befund 2): MIT Tabellenkopf. Bis dahin schrieb der Knopf
    # nur einen Platzhaltersatz — `inbox.entscheide` hängt die D000-Zeile darunter
    # an, und ohne Kopfzeile ist das keine Tabelle, sondern eine Zeile Pipe-Text
    # (so geschehen bei P12). Der Platzhaltersatz entfällt: die leere Tabelle sagt
    # dasselbe, ohne nach der ersten Entscheidung falsch zu werden. Kopf wortgleich
    # zu den von Hand angelegten Logs (P10/P11) und zur Zeile aus `inbox.entscheide`.
    log = (
        f"# Decision Log {neuer_name}\n\n"
        "*Append-only — Entscheidungen werden nie überschrieben, nur ergänzt (Playbook Kap. 16).*\n\n"
        + LOG_TABELLENKOPF
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

    commit_msg = (f"{neuer_name}: aus dem Projekt-Pool gestartet („{name}“, "
                 f"Technik-Kandidat) — Ordner + G0-Antrag T-0001, {HERKUNFT}")
    _v1 = git_schreiben.verbuche(projects_repo, [neuer_name], commit_msg,  # SWR-134
                                 COMMIT_IDENTITAET)
    if not _v1.ok:
        shutil.rmtree(projekt_pfad, ignore_errors=True)
        raise PoolFehler(503, "Git-Commit fehlgeschlagen — der Projektordner wurde nicht "
                              "angelegt, es steht nichts auf der Platte: " +
                          _v1.fehler[:400])

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

    # pm/T-0037 (B051, Befund 1): verschieben statt löschen — die Kandidatenzeile
    # wandert in denselben Schreibvorgang/Commit unter „Realisiert".
    neuer_pool_text = _realisiert_zeile_einfuegen(
        neuer_pool_text,
        _realisiert_zeile_bauen(nummer_text, name, quelle, neuer_name, heute_iso))

    pm_repo = os.path.join(root, aggregation.POOL_DATEI[0])
    rel = os.path.join(*aggregation.POOL_DATEI[1:])
    open(pool_pfad, "w", encoding="utf-8", newline="\n").write(neuer_pool_text)
    _v2 = git_schreiben.verbuche(  # SWR-134
        pm_repo, [rel],
        f"Projekt-Pool: '{name}' gestartet als {neuer_name} (pm/T-0022 Teil 2) "
        f"— nach 'Realisiert' verschoben (pm/T-0037) — {HERKUNFT}",
        COMMIT_IDENTITAET)
    if not _v2.ok:
        open(pool_pfad, "w", encoding="utf-8", newline="\n").write(pool_text)  # Rücknahme nur hier
        return {"ok": True, "kandidat": name, "projekt": neuer_name, "ticket": "T-0001", "ref": ref,
                "meldung": grundmeldung + " ACHTUNG: der Kandidat konnte NICHT im Pool "
                          "nachgeführt werden (Git-Commit fehlgeschlagen: " +
                          _v2.fehler[:200] +
                          ") — bitte die Zeile manuell in pm/management/projekt-pool.md prüfen."}

    return {"ok": True, "kandidat": name, "projekt": neuer_name, "ticket": "T-0001", "ref": ref,
            "meldung": grundmeldung + " Im Pool nach „Realisiert“ verschoben, committet."}


# --------------------------------------------------------------- Team-Gründung
# SWR-127 (pm/T-0062, erster Teil von pm/T-0028 aus Brief pm/N-0022).
#
# Die Feldliste selbst ist **nicht** hier entschieden worden — sie steht seit Sprint 10
# als Tabelle in `pm/T-0028`, mit Begründung je Feld. Dieses Modul ist die Stelle, an der
# sie **gilt**: genau das, was SWR-125 an SWR-106 gefehlt hat. Eine Feldliste in einem
# Ticket, die kein Code prüft, ist eine Absichtserklärung.
STECKBRIEF_PROFILE = ("entwicklung", "dienstleistung", "wiederkehrend")
STECKBRIEF_KLASSEN = ("offen", "intern", "sensibel", "geheim")
# Datenklassen, bei denen der Gründungs-DR die Folge im KLARTEXT nennen muss und das
# Repo ohne Remote bleibt (Guardrail F17 / Playbook Kap. 16).
KLASSEN_OHNE_REMOTE = ("sensibel", "geheim")
# Pflichtfelder — und warum genau diese zwei:
#   `auftrag`  ohne ihn ist der Charter leer.
#   `grenzen`  ⚠ ein leeres Feld wird hier als „keine Grenzen" gelesen. Das ist der
#              einzige Fall in der Liste, in dem Schweigen die WEITERE Auslegung hat;
#              deshalb ist es Pflicht und nicht bloß empfohlen.
STECKBRIEF_PFLICHT = ("auftrag", "grenzen")
STECKBRIEF_FELDER = ("auftrag", "profil", "rollen", "datenklasse", "zugaenge", "grenzen")


def steckbrief_pruefen(felder):
    """Steckbrief eines Gründungsantrags prüfen und bereinigen (SWR-127).

    Gibt `(werte, auflagen)` zurück: `werte` sind die bereinigten Felder,
    `auflagen` die Folgen, die der Gründungs-DR **im Klartext** nennen muss.
    Wirft `PoolFehler(400, …)`, wenn ein Feld fehlt oder außerhalb seiner Liste liegt.

    **Was diese Funktion ausdrücklich NICHT tut: entscheiden.** Eine Team-Gründung ist
    Klasse A (Playbook Kap. 16) und bleibt beim Menschen; hier wird ein Antrag geprüft,
    nicht bewilligt. `pm/T-0063` baut daraus Charter-Entwurf und DR.

    **Warum die Auflage ein Rückgabewert ist und keine Prüfung.** Bei `sensibel` oder
    `geheim` verlangt Kap. 16 zwei Dinge: der DR benennt es im Klartext, und das Repo
    bleibt ohne Remote (`.kein-remote`). Beides sind Handlungen **späterer** Schritte.
    Sie hier nur zu *wissen* und nicht weiterzugeben wäre genau der Fehler von SWR-122
    (berechnet, von niemandem gelesen) — deshalb verlässt die Auflage die Funktion als
    Wert, den der Aufrufer nicht übersehen kann, statt als Kommentar.

    **Warum Freitextfelder keine Längengrenze bekommen.** Langer Text läuft seit
    SWR-124 in eine eigene Datei statt in eine Tabellenzelle. Eine Grenze hier wäre die
    dritte Antwort auf eine Frage, die dort schon beantwortet ist (B033) — und die
    Geschichte von `FELD_MAX` (200 → 4.000 → 200.000) ist der Beleg, dass die richtige
    Antwort nie eine Zahl war, sondern ein Zielort.
    """
    if not isinstance(felder, dict):
        raise PoolFehler(400, "Steckbrief fehlt")
    werte, auflagen = {}, []
    for feld in STECKBRIEF_FELDER:
        werte[feld] = _text_bereinigen(felder.get(feld, ""))
    for feld in STECKBRIEF_PFLICHT:
        if not werte[feld]:
            raise PoolFehler(400, f"Steckbrief-Feld „{feld}“ ist Pflicht und fehlt")
    for feld, erlaubt in (("profil", STECKBRIEF_PROFILE),
                          ("datenklasse", STECKBRIEF_KLASSEN)):
        if werte[feld] not in erlaubt:
            raise PoolFehler(400, f"Steckbrief-Feld „{feld}“: „{werte[feld]}“ ist keine "
                                  f"der zulässigen Angaben ({', '.join(erlaubt)})")
    if werte["datenklasse"] in KLASSEN_OHNE_REMOTE:
        auflagen.append(
            f"Datenklasse „{werte['datenklasse']}“ (Playbook Kap. 16 / F17): das Repo "
            f"bleibt OHNE GitHub-Remote und trägt .kein-remote; sensible Inhalte werden "
            f"nie committet, sondern per Pfad verwiesen.")
    return werte, auflagen


# ------------------------------------------------- Gründung VORLEGEN (SWR-147)
# pm/T-0063, zweiter Teil von pm/T-0028 aus Brief pm/N-0022 — bei der VIERTEN Berührung
# gebaut. Acht wortgleiche Verschiebungen stehen in der Historie des Elterntickets.
#
# ⚠ **Diese Funktion kann nicht gründen, und das ist die Anforderung.** Team-Gründung ist
# Klasse A (Playbook Kap. 16). Sie schreibt zwei Dateien — einen Charter-**Entwurf** und
# einen Gründungs-DR — und danach ist der Mensch am Zug. Kein Repo, kein Remote, kein
# Registry-Eintrag: das sind Schritte 3/4 aus `intake.md` und passieren **nach** der
# Freigabe. Die Gegenprobe dazu ist eine Zusicherung und kein Vorsatz im Docstring.

#: Frist des Gründungs-DR in Tagen. ⚠ Ein **Kalenderdatum** und keine Sprintnummer:
#: SWR-125 hat Kalenderdaten an TEAMAUFGABEN abgeschafft, und der Grund war, dass Teams in
#: 60-Minuten-Läufen arbeiten. Hier wartet ein **Mensch**, dessen Antwortzeit in Tagen
#: läuft — für ihn IST die `frist` die Steuerung (so steht es im Widget-Vertrag bei
#: `kalenderfristen_gesamt`, wo der `decision-request` ausdrücklich ausgenommen ist).
TG_FRIST_TAGE = 7

#: Wohin der Charter-Entwurf geht. Bewusst **nicht** in ein Team-Repo: es gibt keins, und
#: eines anzulegen wäre die Gründung, die hier nicht stattfindet.
CHARTER_VERZEICHNIS = ("pm", "management", "kandidaten")

CHARTER_VORLAGE = ("process", "templates", "team-repo", "docs", "01-team-charter.md")


def _naechste_ticket_id(repo):
    """Die nächste freie `T-xxxx` — gegen Arbeitskopie **und** HEAD zugleich.

    ⚠ Beide Quellen, und die Vereinigung ihrer Maxima. Eine Nummer, die in der
    Arbeitskopie frei ist, kann in HEAD belegt sein (ein Ticket, das eine parallele
    Session committet und die Arbeitskopie noch nicht kennt) — und umgekehrt kann eine in
    HEAD freie Nummer als ungetrackte Datei schon dastehen. Gemessen am eigenen Bestand
    am 2026-08-16: genau so entstand eine Kollision, und die Lesson verlangt seither die
    Prüfung gegen HEAD.
    """
    hoechste = 0
    verz = os.path.join(repo, "tickets")
    if os.path.isdir(verz):
        for name in os.listdir(verz):
            m = re.fullmatch(r"T-(\d{4})\.md", name)
            if m:
                hoechste = max(hoechste, int(m.group(1)))
    lauf = subprocess.run(["git", "-C", repo, "ls-tree", "--name-only", "HEAD", "tickets/"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    for zeile in (lauf.stdout or "").splitlines():
        m = re.search(r"T-(\d{4})\.md$", zeile.strip())
        if m:
            hoechste = max(hoechste, int(m.group(1)))
    return "T-%04d" % (hoechste + 1)


def _charter_entwurf(name, werte, dr_ref, heute_iso):
    """Den Charter-Entwurf aus der Vorlage füllen — Platzhalter für Platzhalter.

    ⚠ Aus der **Vorlagendatei** und nicht aus einem String hier: `process/templates/`
    ist die Stelle, an der die Charter-Gestalt der Organisation steht. Eine zweite
    Fassung im Code wäre B033, und sie würde beim ersten Vorlagenwechsel still falsch.
    """
    pfad = os.path.join(*CHARTER_VORLAGE)
    ersetzungen = {
        "TEAM_NAME": name,
        "DATUM": heute_iso,
        "GRUENDUNGS_DR": dr_ref,
        "WAS_MACHT_DAS_TEAM_UND_WARUM": werte["auftrag"],
        "PROFIL": werte["profil"],
        # ⚠ Der SLA-Platzhalter wird BENANNT und nicht leer gelassen: eine leere Stelle im
        # Entwurf ist von einer vergessenen nicht zu unterscheiden.
        "BEI_WIEDERKEHREND_SLA_TABELLE": (
            "SLA-Tabelle je Aufgabentyp ist beim Profil `wiederkehrend` Pflicht (statt G4) "
            "und wird nach der Freigabe ergänzt."
            if werte["profil"] == "wiederkehrend"
            else "Profil ohne SLA-Tabelle — G4 gilt regulär."),
        "ROLLEN_MIT_KURZBESCHREIBUNG": werte["rollen"] or
            "*Im Steckbrief nicht angegeben — vor der Freigabe zu ergänzen.*",
        "DATENKLASSE": werte["datenklasse"],
        "ZUGAENGE_ODER_KEINE": werte["zugaenge"] or "keine",
        "TEAM_SPEZIFISCHE_GRENZEN": werte["grenzen"],
    }
    return pfad, ersetzungen


def gruendung_vorlegen(root, name, felder, heute=None):
    """SWR-147 (pm/T-0063): Charter-Entwurf + Gründungs-DR in **einem** Commit.

    Gibt `{ok, team, dr, ref, charter, auflagen, meldung}` zurück. Wirft `PoolFehler`.

    **Was diese Funktion nicht kann: gründen.** Sie legt kein Repo an, setzt kein Remote,
    schreibt keinen Registry-Eintrag. Das ist keine Sparsamkeit, sondern Klasse A: der
    Mensch entscheidet, und ein Code, der die Gründung nebenbei ausführen *könnte*, wäre
    die Gelegenheit, bei der es einmal passiert.

    ⚠ **Die Auflagen aus SWR-127 stehen im DR-Text als Sätze.** Nicht als Feldwert: ein
    Feld liest, wer weiß, dass er danach suchen muss, und dieser Text muss von jemandem
    gelesen werden, der es **nicht** weiß.

    > **Eine Auflage, die eine Funktion als Wert verlässt und in kein Dokument eingeht,
    > ist berechnet und nicht angewandt.**

    ⚠ **Ein Commit für beide Dateien.** Scheitert er, bleibt **keine** von beiden auf der
    Platte — dieselbe Regel wie bei `kandidat_starten` und SWR-124. Eine halbe Gründung
    ist schlimmer als keine, weil sie niemandem auffällt.
    """
    name = (name or "").strip()
    if not name:
        raise PoolFehler(400, "Teamname fehlt")
    if "|" in name or '"' in name or "\n" in name or "/" in name:
        raise PoolFehler(400, "Teamname enthält ein Zeichen (| \" / oder Zeilenumbruch), das im "
                              "Ticket-Frontmatter oder im Dateipfad das Format sprengen würde.")
    # SWR-127: prüfen, nicht bewilligen. Die Auflagen sind der Rückgabewert, den DoD 3
    # dieses Tickets einlöst.
    werte, auflagen = steckbrief_pruefen(felder)

    pm_repo = os.path.join(root, "pm")
    if not os.path.isdir(os.path.join(pm_repo, ".git")):
        raise PoolFehler(404, "Repo 'pm' fehlt oder ist kein Git-Repo.")
    heute = heute or date.today()
    heute_iso = heute.isoformat()
    frist = (heute + timedelta(days=TG_FRIST_TAGE)).isoformat()
    tid = _naechste_ticket_id(pm_repo)
    dr_ref = aggregation.ref("pm", tid)

    vorlage_pfad, ersetzungen = _charter_entwurf(name, werte, dr_ref, heute_iso)
    vorlage_abs = os.path.join(root, vorlage_pfad)
    try:
        with open(vorlage_abs, encoding="utf-8") as f:
            charter = f.read()
    except OSError:
        raise PoolFehler(404, f"Charter-Vorlage fehlt: {vorlage_pfad}")
    for marke, wert in ersetzungen.items():
        charter = charter.replace("{{%s}}" % marke, wert)
    # ⚠ Unersetzte Platzhalter werden GEMELDET und nicht stehen gelassen: ein Entwurf mit
    # `{{...}}` darin geht als fertig durch, wenn niemand ihn liest — und der DR bittet
    # ausdrücklich darum, ihn zu lesen.
    offen = sorted(set(re.findall(r"\{\{([A-Z_]+)\}\}", charter)))
    if offen:
        raise PoolFehler(500, "Charter-Vorlage hat Platzhalter, die dieser Code nicht kennt: "
                              + ", ".join(offen) + " — bitte pm/T-0063 nachziehen, statt einen "
                              "Entwurf mit Lücken vorzulegen.")

    auflagen_text = ("\n".join(f"- {a}" for a in auflagen) if auflagen else
                     "- Keine besonderen Auflagen aus der Steckbrief-Prüfung "
                     "(Datenklasse ohne Remote-Einschränkung).")
    ticket = (
        "---\n"
        f"id: {tid}\n"
        f'titel: "DR: Team-Gründung {name} freigeben (Klasse A)"\n'
        "typ: decision-request\n"
        "prozess: sup10\n"
        "rolle: chg\n"
        "sprint: 0\n"
        "status: open\n"
        "prio: mittel\n"
        "reviewer: qm\n"
        "blocked_by: []\n"
        "repo: pm\n"
        "optionen: [TG-a, TG-b, TG-c]\n"
        f"frist: {frist}\n"
        "default: TG-a\n"
        f"geändert: {heute_iso}\n"
        f"erstellt: {heute_iso}\n"
        "---\n\n"
        "## Sachverhalt\n\n"
        f"Gründungsantrag für das Team **{name}**, geprüft nach SWR-127 "
        "(`pool.steckbrief_pruefen`). Vorgelegt von `pm/T-0063` — **es ist nichts gegründet "
        "worden**: es gibt kein Repo, kein Remote und keinen Registry-Eintrag. Das sind "
        "Schritte 3/4 aus `intake.md` und folgen **nach** deiner Freigabe (Playbook Kap. 16, "
        "Klasse A).\n\n"
        f"Charter-**Entwurf** zum Lesen: `{'/'.join(CHARTER_VERZEICHNIS[1:])}/"
        f"{name}-charter-entwurf.md`.\n\n"
        "## Der geprüfte Steckbrief\n\n"
        "| Feld | Angabe |\n"
        "|---|---|\n"
        + "".join(f"| {f} | {werte[f] or '—'} |\n" for f in STECKBRIEF_FELDER)
        + "\n## ⚠ Auflagen, die mit einer Freigabe gelten\n\n"
        "*Aus der Steckbrief-Prüfung (SWR-127). Sie stehen hier im Klartext und nicht als "
        "Feldwert, weil ein Feld nur liest, wer weiß, dass er danach suchen muss.*\n\n"
        + auflagen_text + "\n\n"
        "## Optionen\n\n"
        "- **TG-a (Empfehlung/Default):** gründen — Repo/Registry nach `intake.md` "
        "Schritt 3/4, Charter aus dem Entwurf.\n"
        "- **TG-b:** mit Änderungen gründen (bitte in der Begründung benennen).\n"
        "- **TG-c:** nicht gründen — der Entwurf bleibt als Beleg stehen, es entsteht "
        "nichts.\n\n"
        "## Stichproben (P1-E4-Konvention)\n\n"
        "| # | Artefakt | Wie | Status |\n"
        "|---|---|---|---|\n"
        f"| 1 | Charter-Entwurf — trifft der Auftrag, was du wolltest? | "
        f"`{'/'.join(CHARTER_VERZEICHNIS)}/{name}-charter-entwurf.md` | offen — 3 Min Lesen |\n"
        "| 2 | Auflagen oben — ist die Datenklasse richtig eingestuft? | dieses Ticket | "
        "offen — 1 Min Lesen |\n\n"
        "Zähler: 0 erledigt / 2 offen.\n\n"
        "## Antwortfrist und Default\n\n"
        f"**Frist:** {frist} · **Default:** TG-a.\n"
    )

    charter_verz = os.path.join(root, *CHARTER_VERZEICHNIS)
    charter_datei = os.path.join(charter_verz, f"{name}-charter-entwurf.md")
    ticket_datei = os.path.join(pm_repo, "tickets", f"{tid}.md")
    board_pfad = os.path.join(pm_repo, "BOARD.md")
    if os.path.exists(ticket_datei):
        raise PoolFehler(409, f"{tid} existiert bereits — Nummernkollision, bitte CM/Session "
                              "informieren (Lesson 2026-08-16).")
    vorher_board = open(board_pfad, encoding="utf-8").read() if os.path.isfile(board_pfad) else None

    def zuruecknehmen():
        for p in (charter_datei, ticket_datei):
            try:
                os.remove(p)
            except OSError:
                pass
        if vorher_board is not None:
            open(board_pfad, "w", encoding="utf-8", newline="\n").write(vorher_board)

    os.makedirs(charter_verz, exist_ok=True)
    open(charter_datei, "w", encoding="utf-8", newline="\n").write(charter)
    open(ticket_datei, "w", encoding="utf-8", newline="\n").write(ticket)
    tickets_alle, probleme = board.lade_tickets(pm_repo)
    probleme += board.validiere_alle(tickets_alle, pm_repo, git_pruefen=False)
    if probleme:
        zuruecknehmen()
        raise PoolFehler(500, "Erzeugter Gründungs-DR ist ungültig: " + "; ".join(probleme))
    open(board_pfad, "w", encoding="utf-8", newline="\n").write(
        board.generiere_board(tickets_alle))

    ziele = [os.path.join("tickets", f"{tid}.md"), "BOARD.md",
             os.path.join(*CHARTER_VERZEICHNIS[1:], f"{name}-charter-entwurf.md")]
    v = git_schreiben.verbuche(  # SWR-134: der eine Schreibweg
        pm_repo, ziele,
        f"Team-Gründung „{name}“ VORGELEGT (pm/T-0063, SWR-147): Charter-Entwurf + "
        f"Gründungs-DR {tid} — nichts gegründet, Klasse A bleibt beim Menschen — {HERKUNFT}",
        COMMIT_IDENTITAET)
    if not v.ok:
        zuruecknehmen()
        raise PoolFehler(503, "Git-Commit fehlgeschlagen — es wurde NICHTS vorgelegt, weder "
                              "Entwurf noch DR stehen auf der Platte: " + v.fehler[:400])
    return {"ok": True, "team": name, "dr": tid, "ref": dr_ref,
            "charter": os.path.join(*CHARTER_VERZEICHNIS, f"{name}-charter-entwurf.md"),
            "auflagen": auflagen,
            "meldung": (f"Team-Gründung „{name}“ vorgelegt: Charter-Entwurf und "
                        f"Gründungs-DR {dr_ref} (Frist {frist}, Default TG-a). "
                        f"Es ist nichts gegründet — die Freigabe liegt bei dir.")}
