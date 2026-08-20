# -*- coding: utf-8 -*-
"""organisation.py (Orga-Rework Rollenmodell v2, platform/T-0028): Rollen-Detail
und Besetzungs-Konfiguration für das HMI.

Lesen: Besetzung + Bauplan-Rollenkarte + projektspezifischer Teil + Historie
(Konzept process/docs/03-rollenmodell-v2-orga-rework.md Kap. 2.1).

Schreiben (Mensch via HMI, Konzept Kap. 7 — der Mensch darf Besetzungen jederzeit
direkt ändern; PM zieht nach): Felder einer Besetzung ändern, neue Besetzung
anlegen, Besetzung entfernen. Der Schreibweg ist ein TEXT-Edit auf
process/roles/besetzungen.yaml — Kommentare und Reihenfolge der übrigen Blöcke
bleiben erhalten (PyYAML-Rewrite würde beides zerstören). Danach werden die
Organigramme regeneriert (organigramm.py) und das process-Repo verbucht
(Muster tickets.py: schreiben, nur die eigenen Ziele adden, sofort committen).

⚠ Ehrliche Grenze: Die regenerierten ORGANIGRAMM.md der ANDEREN Repos und
platform/backend/static/organigramm.json werden hier bewusst NICHT verbucht —
sie sind generierte Folgezustände und laufen mit dem nächsten Sprint-/
abschluss-Commit ihres Repos mit (organigramm.py --check hält sie ehrlich).

F20 (pm/D012) wird hier durchgesetzt: höchstens EINE Besetzung je Rolle und
Einheit; eine zweite ist ein 409 mit Verweis auf den Entscheid.
"""
import io
import os
import re
import sys

try:
    import yaml
except ImportError:
    yaml = None

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import organigramm  # noqa: E402

from . import git_schreiben  # noqa: E402

HERKUNFT = "Mensch via HMI"
COMMIT_IDENTITAET = ["-c", f"user.name={HERKUNFT}", "-c", "user.email=mensch@hmi.local"]

MOTOREN = ["cowork", "ollama", "api", "script", "mensch"]
TAKTE = ["sprint", "schnell"]  # "session" gestrichen: seit pm/D006 ist jeder
                               # Session-Lauf ein Sprint — zwei Namen für dieselbe
                               # Sache wären die B033-Falle (Auftraggeber, 2026-08-20)
STATI = ["aktiv", "geplant", "pausiert"]
FELDER_ERLAUBT = ["motor", "modell", "takt", "status", "hinweis"]
INSTANZ_MUSTER = re.compile(r"^[A-Z0-9ÄÖÜ-]+@[a-z0-9-]+$")


class OrgFehler(Exception):
    """code = HTTP-Status, Meldung deutsch (Muster TicketFehler/TeamFehler)."""

    def __init__(self, code, meldung):
        super().__init__(meldung)
        self.code = code


def _pfad_besetzungen(root):
    return os.path.join(root, "process", "roles", "besetzungen.yaml")


def _lies_text(pfad):
    if not os.path.isfile(pfad):
        return None
    with io.open(pfad, "r", encoding="utf-8") as f:
        return f.read()


def _lade_yaml(pfad):
    if yaml is None:
        raise OrgFehler(500, "PyYAML fehlt auf dem Server (pip install pyyaml).")
    text = _lies_text(pfad)
    return (yaml.safe_load(text) or {}) if text else {}


def _einheit_pfad(root, einheit):
    """Discovery wie organigramm.py — bewusst OHNE aggregation-Import (kein Zyklus)."""
    pfade = organigramm.entdecke_einheiten(root)
    if einheit not in pfade:
        raise OrgFehler(404, f"Einheit unbekannt: {einheit}")
    return pfade[einheit]


def katalog(root):
    """Auswahllisten fürs Formular: Rollen (Bauplan-Registry), Motoren, Takte, Stati."""
    rollen = _lade_yaml(os.path.join(root, "process", "roles", "registry.yaml")).get("roles", {})
    return {"rollen": sorted(rollen),
            "rollen_namen": {k: (v or {}).get("name", k) for k, v in rollen.items()},
            "motoren": MOTOREN, "takte": TAKTE, "stati": STATI,
            "hinweis_f20": "Höchstens eine Besetzung je Rolle und Einheit (pm/D012)."}


def detail(root, instanz):
    """Alles zu einer Instanz: Besetzung + die drei Dokument-Ebenen (Konzept Kap. 2.1)."""
    besetzungen = _lade_yaml(_pfad_besetzungen(root)).get("besetzungen", {})
    b = besetzungen.get(instanz)
    if not b:
        raise OrgFehler(404, f"Besetzung unbekannt: {instanz}")
    rolle = b.get("rolle", "")
    einheit = b.get("einheit", "")
    repo = _einheit_pfad(root, einheit)
    bauplan_pfad = os.path.join(root, "process", "roles", rolle.lower() + ".md")
    projekt_pfad = os.path.join(repo, "roles", rolle.lower() + ".md")
    historie_pfad = os.path.join(repo, "docs", "historie.md")
    wissen = os.path.join(root, "process", "knowledge", rolle.lower())
    return {
        "instanz": instanz, "besetzung": b, "katalog": katalog(root),
        "bauplan": _lies_text(bauplan_pfad),
        "bauplan_pfad": os.path.relpath(bauplan_pfad, root).replace(os.sep, "/"),
        "projektteil": _lies_text(projekt_pfad),
        "projektteil_pfad": os.path.relpath(projekt_pfad, root).replace(os.sep, "/"),
        "historie": _lies_text(historie_pfad),
        "historie_pfad": os.path.relpath(historie_pfad, root).replace(os.sep, "/"),
        "wissensbasis": sorted(os.listdir(wissen)) if os.path.isdir(wissen) else [],
        "hinweis_governance": ("Besetzung ändern = Mensch direkt / PM Klasse B (Konzept Kap. 7). "
                               "Rollenkarten ändern läuft als Prozess-CR."),
    }


# ---------- Text-Edit auf besetzungen.yaml (Kommentare bleiben erhalten) ----------

def _block_grenzen(zeilen, instanz):
    """(start, ende) des Instanz-Blocks: '  INSTANZ:' bis zur nächsten Zeile mit
    Einrückung <= 2, die kein Kommentar/Leerraum ist. ende = exklusiv."""
    start = None
    muster = re.compile(r"^  " + re.escape(instanz) + r":\s*(#.*)?$")
    for i, z in enumerate(zeilen):
        if muster.match(z):
            start = i
            break
    if start is None:
        return None, None
    ende = len(zeilen)
    for i in range(start + 1, len(zeilen)):
        z = zeilen[i]
        if not z.strip():
            continue  # Leerzeilen trennen, gehören keinem Block
        if z.startswith("    "):
            continue  # Feld- oder Feld-Kommentar-Zeile des Blocks
        ende = i  # nächste Instanz, Abschnitts-Kommentar oder Top-Level: Block zu Ende
        break
    return start, ende


def _feld_setzen(zeilen, start, ende, feld, wert):
    """Feldzeile im Block ersetzen oder (vor Blockende) einfügen. Leerer Wert bei
    optionalen Feldern (modell, hinweis) entfernt die Zeile."""
    neu = f"    {feld}: {wert}"
    muster = re.compile(r"^    " + re.escape(feld) + r":")
    for i in range(start + 1, ende):
        if muster.match(zeilen[i]):
            if wert == "" and feld in ("modell", "hinweis"):
                del zeilen[i]
                return -1
            zeilen[i] = neu
            return 0
    if wert != "":
        pos = ende  # vor etwaigen Leerzeilen am Blockende einfügen
        while pos > start + 1 and not zeilen[pos - 1].strip():
            pos -= 1
        zeilen.insert(pos, neu)
        return 1
    return 0


def _pruefe_felder(felder):
    unbekannt = [k for k in felder if k not in FELDER_ERLAUBT and k != "rolle"]
    if unbekannt:
        raise OrgFehler(400, f"Unbekannte Felder: {', '.join(unbekannt)} "
                             f"(erlaubt: {', '.join(FELDER_ERLAUBT)})")
    if "motor" in felder and felder["motor"] not in MOTOREN:
        raise OrgFehler(400, f"Ungültiger Motor: {felder['motor']} (erlaubt: {', '.join(MOTOREN)})")
    if "takt" in felder and felder["takt"] not in TAKTE:
        raise OrgFehler(400, f"Ungültiger Takt: {felder['takt']} (erlaubt: {', '.join(TAKTE)})")
    if "status" in felder and felder["status"] not in STATI:
        raise OrgFehler(400, f"Ungültiger Status: {felder['status']} (erlaubt: {', '.join(STATI)})")
    for k in ("modell", "hinweis"):
        if k in felder and ("\n" in str(felder[k]) or "#" in str(felder[k])):
            raise OrgFehler(400, f"Feld {k}: Zeilenumbruch und '#' sind nicht erlaubt.")


def _schreib_und_verbuche(root, zeilen, meldung, verbuchen):
    pfad = _pfad_besetzungen(root)
    with io.open(pfad, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(zeilen) + ("\n" if zeilen and zeilen[-1] != "" else ""))
    organigramm.main(["--repos", root])  # Ansichten ziehen sofort nach (Kap. 8)
    if verbuchen:
        git_schreiben.verbuche(os.path.join(root, "process"),
                               ["roles/besetzungen.yaml", "ORGANIGRAMM.md"],
                               meldung, identitaet=COMMIT_IDENTITAET)


def setzen(root, instanz, felder, verbuchen=True):
    """Felder einer bestehenden Besetzung ändern (motor/modell/takt/status/hinweis)."""
    _pruefe_felder(felder)
    text = _lies_text(_pfad_besetzungen(root))
    if text is None:
        raise OrgFehler(404, "besetzungen.yaml fehlt.")
    zeilen = text.split("\n")
    start, ende = _block_grenzen(zeilen, instanz)
    if start is None:
        raise OrgFehler(404, f"Besetzung unbekannt: {instanz}")
    versatz = 0
    for feld in FELDER_ERLAUBT:
        if feld in felder:
            versatz += _feld_setzen(zeilen, start, ende + versatz, feld, str(felder[feld]))
    _schreib_und_verbuche(root, zeilen,
                          f"Besetzung {instanz} geändert ({HERKUNFT}, Konzept Kap. 7)", verbuchen)
    return {"ok": True, "instanz": instanz}


def anlegen(root, instanz, felder, verbuchen=True):
    """Neue Besetzung ROLLE@einheit anlegen. F20 (pm/D012): eine je Rolle und Einheit."""
    if not INSTANZ_MUSTER.match(instanz or ""):
        raise OrgFehler(400, f"Ungültige Instanz-ID: {instanz} (Muster: ROLLE@einheit)")
    rolle, einheit = instanz.split("@", 1)
    _einheit_pfad(root, einheit)  # 404, wenn Einheit unbekannt
    _pruefe_felder(felder)
    if "motor" not in felder:
        raise OrgFehler(400, "Feld motor ist Pflicht beim Anlegen.")
    bestehend = _lade_yaml(_pfad_besetzungen(root)).get("besetzungen", {})
    if instanz in bestehend:
        raise OrgFehler(409, f"{instanz} existiert bereits.")
    for name, b in bestehend.items():
        if b.get("rolle") == rolle and b.get("einheit") == einheit:
            raise OrgFehler(409, f"F20 (pm/D012): {rolle} ist in {einheit} bereits besetzt "
                                 f"({name}) — höchstens eine Besetzung je Rolle und Einheit.")
    text = _lies_text(_pfad_besetzungen(root))
    zeilen = text.split("\n")
    while zeilen and zeilen[-1] == "":
        zeilen.pop()
    block = [f"  {instanz}:", f"    rolle: {rolle}", f"    einheit: {einheit}",
             f"    motor: {felder['motor']}"]
    for feld in ("modell", "takt", "status", "hinweis"):
        if felder.get(feld):
            block.append(f"    {feld}: {felder[feld]}")
    if "status" not in felder or not felder.get("status"):
        block.append("    status: aktiv")
    zeilen += block
    _schreib_und_verbuche(root, zeilen,
                          f"Besetzung {instanz} angelegt ({HERKUNFT}, Konzept Kap. 7)", verbuchen)
    return {"ok": True, "instanz": instanz}


def entfernen(root, instanz, verbuchen=True):
    """Besetzung entfernen (Block löschen). Die Rolle als Bauplan bleibt unberührt."""
    text = _lies_text(_pfad_besetzungen(root))
    if text is None:
        raise OrgFehler(404, "besetzungen.yaml fehlt.")
    zeilen = text.split("\n")
    start, ende = _block_grenzen(zeilen, instanz)
    if start is None:
        raise OrgFehler(404, f"Besetzung unbekannt: {instanz}")
    del zeilen[start:ende]
    _schreib_und_verbuche(root, zeilen,
                          f"Besetzung {instanz} entfernt ({HERKUNFT}, Konzept Kap. 7)", verbuchen)
    return {"ok": True, "instanz": instanz}
