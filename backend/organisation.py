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


GUARDRAILS_DEFAULT_MODELL = "llama3.1:8b"   # nur Rückfall, siehe modell_der_besetzung


def _guardrails_ollama_modell(root):
    """Der Guardrails-Wert — Rückfall, nicht Vorgabe. Fehlt die Datei, gilt der Default."""
    pfad = os.path.join(root, "platform", "orchestrator", "config", "guardrails.yaml")
    try:
        cfg = _lade_yaml(pfad)
    except OrgFehler:
        return GUARDRAILS_DEFAULT_MODELL
    p = ((cfg.get("providers") or {}).get("ollama") or {})
    return p.get("model") or GUARDRAILS_DEFAULT_MODELL


def modell_der_besetzung(root, rolle, einheit):
    """SWR-169: das Ollama-Modell der Rolle aus dem Besetzungsregister ('' wenn keins).

    ⚠ Warum diese Quelle und nicht der Guardrails-Default: Am 2026-08-20 sind die ersten
    **drei** Ticks, die je durch den Preflight kamen, alle an derselben Stelle gestorben —
    `404: model 'llama3.1:8b' not found`. Das Register trägt für beide `takt: schnell`-
    Besetzungen (PROB@aspice, MAIL-RED@mail) `gemma3:27b`, `pm/D010` nennt dasselbe, und
    der Gateway hat keine der beiden Stellen gelesen.

    ⚠⚠ Genau das steht seit dem 2026-08-06 als Lehre im Bestand (`L-003`, T-0011/F13):
    *„Modell-Defaults gegen das Geräteregister prüfen; Abweichungen als
    Registry-/Guardrails-CR nachziehen."* Dreimal aufgeschrieben, mit Erwartungswert
    *„Wiederholungsquote in Sprint 2 = 0"*. Die Quote war 3 von 3. Es fehlte nicht die
    Sorgfalt beim Aufschreiben, sondern die Überführung in etwas, das von allein
    wiederkommt.

    Rangfolge (gleichlautend im Code und im Docstring von ollama_executor):
    ``OLLAMA_MODEL`` > Besetzungsregister > guardrails > ``llama3.1:8b``.

    Projektmodell (Konzept 04): gelesen wird die EFFEKTIVE Besetzung (Core-Team-Expansion
    + explizite Einträge, organigramm.effektive_besetzungen) — Core-Instanzen tragen kein
    Modell, explizite Abweichungen gewinnen.
    """
    besetzungen = organigramm.effektive_besetzungen(root)
    rolle_ob = (rolle or "").upper()
    for b in besetzungen.values():
        b = b or {}
        if (b.get("rolle") or "").upper() != rolle_ob:
            continue
        if (b.get("einheit") or "") != einheit:
            continue
        return (b.get("modell") or "").strip()
    return ""


def modellabweichungen(root):
    """SWR-170: ollama-Besetzungen, deren Registermodell vom Guardrails-Default abweicht.

    Liefert (abweichungen, grundmenge): Liste von (Instanz, Registermodell) und die Zahl
    der ollama-Besetzungen überhaupt. ⚠ Die Grundmenge wird mitgeliefert, damit eine
    Prüfung, die das Register gar nicht liest, nicht als „keine Abweichung" durchgeht —
    der Fehler aus SWR-128 und die Gegenprobe aus SWR-165.

    ⚠ Diese Prüfung **meldet** und heilt nicht: welcher der beiden Werte der richtige ist,
    ist eine Frage an den, der das Register pflegt, und keine an ein Werkzeug.
    """
    besetzungen = organigramm.effektive_besetzungen(root)  # Projektmodell: inkl. Core
    default = _guardrails_ollama_modell(root)
    abweichungen, grundmenge = [], 0
    for instanz, b in sorted(besetzungen.items()):
        b = b or {}
        if (b.get("motor") or "") != "ollama":
            continue
        grundmenge += 1
        modell = (b.get("modell") or "").strip()
        if modell and modell != default:
            abweichungen.append((instanz, modell))
    return abweichungen, grundmenge, default


# SWR-171: Welcher Motor des Besetzungsregisters gehört zu welchem `--provider`?
# ⚠ Die Zuordnung ist ABSICHTLICH unvollständig und benannt statt geraten. `ollama` heißt
# in beiden Registern gleich; `claude`/`copilot` heißen im Besetzungsregister `cowork`,
# und ob ein cowork-Motor einen Claude-Aufruf meint oder einen Menschen an der Tastatur,
# steht nirgends. Eine erfundene Zeile hier wäre eine Semantik, die im Register nicht
# steht — derselbe Fehler, den `platform/T-0033` als Option 2 ausdrücklich verworfen hat.
MOTOR_JE_PROVIDER = {"ollama": "ollama"}


def besetzung_mit_motor(root, rolle, einheit, motor):
    """SWR-171: die Instanz-ID der Besetzung `rolle@einheit` mit diesem Motor ('' wenn keine).

    ⚠⚠ Der Anlass ist die Gegenprobe, die Sprint 26 nicht geplant hatte. `SWR-169` holt das
    Ollama-Modell aus dem Besetzungsregister und ist in vier Gegenproben belegt — es bekommt
    Rolle und Einheit zur Laufzeit nur nie die richtigen. `pm/D010` hat den Schnelltakt **je
    Besetzung** entschieden (`platform/PROB`, `team-mail/MAIL-RED`), `ollama-schnelltakt.cmd`
    übergibt aber nur die **Einheit**, und `waehle_ticket` zieht daraufhin das nächste Ticket
    **jeder** aktiven KI-Rolle. Gezogen wurden `CM@platform` und `DEV@team-mail`.

    > **Und `DEV@team-mail` steht im Besetzungsregister überhaupt nicht.** Der Tick hat also
    > nicht nur das falsche Modell angefragt, sondern Arbeit an eine Instanz gegeben, die
    > niemand besetzt hat. Der leere Modellname war die Folge und nicht die Ursache.

    ⚠ Deshalb prüft diese Funktion den **Motor** und nicht das Modell: ein fehlendes Modell
    ist ein Konfigurationsloch, eine fehlende Besetzung ist eine Zuständigkeitsverletzung.
    Sie ist auch dann richtig beantwortet, wenn irgendwann jedes Register ein Modell trägt.

    Projektmodell (Konzept 04): geprüft wird die EFFEKTIVE Besetzung — `DEV@team-mail`
    existiert jetzt implizit über das Core Team, aber mit `motor: cowork`; für einen
    ollama-Tick bleibt der Befund damit korrekt „keine Besetzung mit diesem Motor".
    """
    besetzungen = organigramm.effektive_besetzungen(root)
    rolle_ob = (rolle or "").upper()
    for instanz, b in sorted(besetzungen.items()):
        b = b or {}
        if (b.get("rolle") or "").upper() != rolle_ob:
            continue
        if (b.get("einheit") or "") != einheit:
            continue
        if (b.get("motor") or "") != motor:
            continue
        return instanz
    return ""


def besetzungen_mit_motor(root, motor):
    """Alle Instanzen mit diesem Motor — die Grundmenge zur Prüfung von `besetzung_mit_motor`.

    ⚠ Ohne sie wäre eine Prüfung, die das Register gar nicht liest, von einer, die keine
    Besetzung findet, nicht zu unterscheiden (SWR-128/165).
    """
    besetzungen = organigramm.effektive_besetzungen(root)  # Projektmodell: inkl. Core
    return sorted(i for i, b in besetzungen.items() if ((b or {}).get("motor") or "") == motor)


def motor_abweichungen(root):
    """Rollen, deren Instanzen NICHT denselben Motor tragen — je Rolle namentlich. SWR-220.

    ⚠⚠ **Herkunft: `pm/N-0045` des Auftraggebers** — *„alle rollen im CoreTeam sollen
    gleich sein: z.B. der Prob Role in Plattform ist auf Ollama, alle anderen Prob-Rollen
    sind CoWork."* Entschieden als `pm/B061` (Klasse B, vierte Berührung von `pm/T-0079`):
    **die Rollen-DEFINITION ist organisationsweit eine, die BESETZUNG ist je Instanz
    konfigurierbar** (Konzept 04; `pm/D010` lebt davon, dass der Ollama-Versuch an EINER
    Stelle läuft). Was fehlte, war nicht die Gleichheit, sondern ihre **Sichtbarkeit**.

    > **Eine zulässige Abweichung, die niemand sehen kann, ist von einem Versehen nicht
    > zu unterscheiden — und der Auftraggeber hat sie vor jedem Werkzeug dieses Hauses
    > gefunden.**

    ⚠ **Ausdrücklich KEIN Befund** (`SWR-166`): die Abweichung ist erlaubt und gewollt.
    Sie wird **genannt**, nicht gezählt — eine Dauermeldung ohne Weg nach vorn ist die
    Bauart, die 83 abgebrochene Läufe gekostet hat.

    ⚠ Eine Rolle mit nur EINER Instanz kann nicht abweichen; sie taucht nie auf. Das ist
    der Grund, warum `MAIL-RED@team-mail` (ebenfalls `ollama`) hier fehlt und fehlen
    muss: eine projektspezifische Rolle hat niemanden, mit dem sie uneinheitlich sein
    könnte. **Sie stattdessen zu melden hieße, „einzig" als „abweichend" zu lesen.**

    Rückgabe: `{rolle: {motor: [instanz, …], …}, …}`, nur für Rollen mit ≥ 2 Motoren.
    """
    proRolle = {}
    for instanz, b in organigramm.effektive_besetzungen(root).items():
        d = b or {}
        proRolle.setdefault(d.get("rolle") or "?", {}).setdefault(
            d.get("motor") or "?", []).append(instanz)
    return {r: {m: sorted(i) for m, i in sorted(motoren.items())}
            for r, motoren in sorted(proRolle.items()) if len(motoren) > 1}


def katalog(root):
    """Auswahllisten fürs Formular: Rollen (Bauplan-Registry), Motoren, Takte, Stati."""
    rollen = _lade_yaml(os.path.join(root, "process", "roles", "registry.yaml")).get("roles", {})
    core = _lade_yaml(_pfad_besetzungen(root)).get("core_team", {}) or {}
    return {"rollen": sorted(rollen),
            "rollen_namen": {k: (v or {}).get("name", k) for k, v in rollen.items()},
            "motoren": MOTOREN, "takte": TAKTE, "stati": STATI,
            "core_team": core.get("rollen") or [],
            "hinweis_core": ("Core-Rollen sind in jedem aktiven Projekt implizit besetzt "
                             "(Konzept 04, Kap. 3.1) — Abweichungen per Speichern, nicht per Anlegen."),
            "hinweis_f20": "Höchstens eine Besetzung je Rolle und Einheit (pm/D012)."}


def detail(root, instanz):
    """Alles zu einer Instanz: Besetzung + die drei Dokument-Ebenen (Konzept 03 Kap. 2.1).
    Projektmodell (Konzept 04): auch implizite Core-Team-Instanzen sind Detail-fähig."""
    besetzungen = organigramm.effektive_besetzungen(root)
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
    """Felder einer Besetzung ändern (motor/modell/takt/status/hinweis).

    Projektmodell (Konzept 04): Ist die Instanz nur implizit über das Core Team besetzt,
    wird sie hier MATERIALISIERT — die Änderung entsteht als expliziter Abweichungs-Block
    (Core-Defaults + Felder). Der core_team-Block selbst wird nie angefasst.
    """
    _pruefe_felder(felder)
    text = _lies_text(_pfad_besetzungen(root))
    if text is None:
        raise OrgFehler(404, "besetzungen.yaml fehlt.")
    zeilen = text.split("\n")
    start, ende = _block_grenzen(zeilen, instanz)
    if start is None:
        eff = organigramm.effektive_besetzungen(root)
        basis = eff.get(instanz)
        if not basis or basis.get("quelle") != "core":
            raise OrgFehler(404, f"Besetzung unbekannt: {instanz}")
        werte = {k: basis.get(k, "") for k in FELDER_ERLAUBT}
        werte.update({k: str(v) for k, v in felder.items() if k in FELDER_ERLAUBT})
        while zeilen and zeilen[-1] == "":
            zeilen.pop()
        zeilen += [f"  {instanz}:", f"    rolle: {basis['rolle']}",
                   f"    einheit: {basis['einheit']}"]
        for feld in FELDER_ERLAUBT:
            if werte.get(feld):
                zeilen.append(f"    {feld}: {werte[feld]}")
        if not werte.get("hinweis"):
            zeilen.append("    hinweis: Abweichung vom Core-Team-Default (materialisiert via HMI)")
        _schreib_und_verbuche(root, zeilen,
                              f"Besetzung {instanz} als Core-Abweichung materialisiert "
                              f"({HERKUNFT}, Konzept 04 Kap. 3.1)", verbuchen)
        return {"ok": True, "instanz": instanz, "materialisiert": True}
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
    explizit = _lade_yaml(_pfad_besetzungen(root)).get("besetzungen", {})
    if instanz in explizit:
        raise OrgFehler(409, f"{instanz} existiert bereits.")
    bestehend = organigramm.effektive_besetzungen(root)  # Projektmodell: inkl. Core
    if instanz in bestehend:
        raise OrgFehler(409, f"{instanz} ist bereits implizit über das Core Team besetzt "
                             f"(Konzept 04, Kap. 3.1) — zum Abweichen die Instanz anklicken "
                             f"und speichern (setzen), nicht neu anlegen.")
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
    """Explizite Besetzung entfernen (Block löschen). Die Rolle als Bauplan bleibt unberührt.

    ⚠ Implizite Core-Team-Instanzen sind NICHT entfernbar — sie stehen in keiner Zeile,
    die man löschen könnte (Konzept 04, Kap. 3.1). Wer eine Core-Rolle in einem Projekt
    stilllegen will, setzt `status: pausiert` (materialisiert die Abweichung).
    """
    text = _lies_text(_pfad_besetzungen(root))
    if text is None:
        raise OrgFehler(404, "besetzungen.yaml fehlt.")
    zeilen = text.split("\n")
    start, ende = _block_grenzen(zeilen, instanz)
    if start is None:
        eff = organigramm.effektive_besetzungen(root)
        if (eff.get(instanz) or {}).get("quelle") == "core":
            raise OrgFehler(400, f"{instanz} ist implizit über das Core Team besetzt und "
                                 f"nicht entfernbar — zum Stilllegen status: pausiert "
                                 f"setzen (Konzept 04, Kap. 3.1).")
        raise OrgFehler(404, f"Besetzung unbekannt: {instanz}")
    del zeilen[start:ende]
    _schreib_und_verbuche(root, zeilen,
                          f"Besetzung {instanz} entfernt ({HERKUNFT}, Konzept Kap. 7)", verbuchen)
    return {"ok": True, "instanz": instanz}


# ---------------------------------------------------------------------------
# SWR-214 (platform/T-0066): der Bestand, auf den ein Motor-Takt zugreifen kann.
# ---------------------------------------------------------------------------

def takt_bestand(root, motor, einheit=None):
    """SWR-214: Wie viele offene Tickets kann ein Takt mit diesem Motor überhaupt wählen?

    **Der Anlass ist eine Zahl, die 87 Läufe lang dieselbe war.** `ollama-schnelltakt.log`
    meldete seit Sprint 26 wörtlich *„Kein bearbeitbares Ticket (Besetzung)"* — einmal je
    Lauf, im Protokoll eines Dienstes, das niemand liest. Die Aussage war jedes Mal
    richtig und jedes Mal folgenlos.

    ⚠⚠ **Die maßgebliche Auflösung ist die BESETZUNG, und das ist gemessen, nicht
    gewählt.** Drei Register beantworten die Frage „wer darf auf Ollama":

    | Register | Was es sagt | Wirkt es auf die Ticketwahl? |
    |---|---|---|
    | `process/roles/besetzungen.yaml` (via `organigramm.effektive_besetzungen`) | welche **Instanz** welchen `motor` hat | **JA** — `tick.waehle_ticket` verwirft jedes Ticket, dessen Rolle in dieser Einheit keine Besetzung mit dem Motor hat |
    | `process/roles/registry.yaml` | welche **Kette** ein `aufgaben_typ` nimmt | nein — sie wird erst gelesen, **nachdem** ein Ticket gewählt ist |
    | `--projekt <einheit>` am Aufruf | in welcher **Einheit** gesucht wird | Aufrufargument, kein Register |

    Damit ist die Antwort auf die B033-Frage des Tickets („welche der drei ist
    maßgeblich?") keine Abwägung: **nur eine davon steht im Pfad, der ein Ticket
    verwirft.** Die anderen beiden können übereinstimmen oder nicht, ohne dass sich am
    Bestand etwas ändert — genau deshalb konnte die Schnittmenge seit Sprint 26 leer sein,
    während `registry.yaml` neun ollama-Ketten führte.

    Rückgabe (nie eine gefaltete Zahl — `T-0027`-Familie):

    * `besetzungen`  Instanzen mit diesem Motor (leer = das Register kennt den Motor nicht)
    * `offen`        offene Tickets in der Grundmenge
    * `treffer`      die Referenzen, die ein Takt wählen könnte
    * `leer`         True, wenn `besetzungen` nicht leer ist und `treffer` es ist —
                     **der Zustand, der 87 Läufe lang gemeldet und nie behandelt wurde.**

    ⚠ `besetzungen == []` und `treffer == []` sind **nicht** dasselbe: das erste heißt
    „kein Register-Eintrag", das zweite „Einträge vorhanden, aber kein Ticket dazu".
    Ohne die Unterscheidung wäre ein nie konfigurierter Motor von einem konfigurierten
    ohne Arbeit nicht zu trennen (dieselbe Grenze, die `SWR-128/165` für
    `besetzungen_mit_motor` gezogen hat).
    """
    besetzungen = besetzungen_mit_motor(root, motor)
    offene = _offene_tickets(root)
    if einheit:
        offene = [t for t in offene if t["einheit"] == einheit]
    treffer = [t["ref"] for t in offene
               if besetzung_mit_motor(root, t["rolle"], t["einheit"], motor)]
    return {"motor": motor,
            "einheit": einheit or "",
            "besetzungen": besetzungen,
            "offen": len(offene),
            "treffer": sorted(treffer),
            "leer": bool(besetzungen) and not treffer}


def _offene_tickets(root):
    """Offene Tickets mit Rolle und Einheit — die Grundmenge von `takt_bestand`.

    ⚠ Gelesen wird `status: open` und nicht „alles außer done": `tick.waehle_ticket`
    wählt ausschließlich `open`. Ein `in_review`-Ticket mitzuzählen würde einen Bestand
    behaupten, den der Takt nicht anfassen kann — und wäre damit eine zweite Antwort auf
    „was kann der Takt tun" (B033). Am Bestand belegt: `platform/T-0069` trägt die
    ollama-besetzte Rolle `PROB@platform` und steht auf `in_review`; eine großzügigere
    Grundmenge hätte hier `1 Treffer` gemeldet, und der Takt hätte trotzdem nichts
    gefunden.

    ⚠ Verschachtelte Einheiten (`projects/<p>/tickets/`) zählen mit — `pl.md` Lehre 6.
    """
    import glob
    treffer = []
    muster = [os.path.join(root, "*", "tickets", "T-*.md"),
              os.path.join(root, "projects", "*", "tickets", "T-*.md")]
    for m in muster:
        for pfad in glob.glob(m):
            try:
                with open(pfad, encoding="utf-8", errors="replace") as f:
                    txt = f.read()
            except OSError:
                continue
            def feld(name, _t=txt):
                m2 = re.search(r"(?m)^%s:\s*(.*)$" % name, _t)
                return m2.group(1).strip().strip('"') if m2 else ""
            if feld("status") != "open":
                continue
            rel = os.path.relpath(pfad, root).replace("\\", "/")
            teile = rel.split("/")
            einheit = "/".join(teile[:2]) if teile[0] == "projects" else teile[0]
            tid = feld("id") or os.path.basename(pfad)[:-3]
            treffer.append({"ref": f"{einheit}/{tid}", "rolle": feld("rolle").upper(),
                            "einheit": einheit})
    # Ein Ticket kann über beide Muster gefunden werden (projects/* matcht auch */*).
    gesehen, eindeutig = set(), []
    for t in treffer:
        if t["ref"] in gesehen:
            continue
        gesehen.add(t["ref"])
        eindeutig.append(t)
    return sorted(eindeutig, key=lambda t: t["ref"])


# ---------------------------------------------------------------------------
# SWR-216 (pm/T-0085): Projektkennungen — zwei Quellen, eine Zahl.
# ---------------------------------------------------------------------------

def projektkennung_kollisionen(root):
    """SWR-216: welche p-Nummer wird von mehr als einer Identität beansprucht?

    **Die Vorgeschichte macht den Zuschnitt.** `pm/T-0085` hat in Sprint 35 gemessen, dass
    die Projektnummer **keinen Leser** hat: 47 Zugriffe auf ein Feld `projekt` im
    Quelltext meinen ausnahmslos den **Einheitennamen**, das `projekt:`-Feld aus
    `process/teams/registry.yaml` liest weder Python noch JS, und `organigramm.json` führt
    null p-Nummern. Die Identität ist der Ordner-/Reponame (`SWR-175`, `p9/D003`); die
    Nummer ist eine **Beschriftung in Berichten**.

    > **Deshalb ist die Kollision auch nicht zu reparieren, sondern nur zu bewachen:
    > Umnummerieren macht Berichte rückwirkend falsch, die der Auftraggeber gelesen hat —
    > für eine Beschriftung, die kein Programm liest** (`pm/B060`).

    ⚠ **Beide Quellen zählen, und das ist der Punkt.** Eine Kennung entsteht auf zwei
    Wegen: als Feld `projekt:` in der Registry **und** als Ordnername unter `projects/`.
    `projects/p13` steht in keiner Registry-Zeile — eine Prüfung, die nur die Registry
    liest, fände die Dopplung nie, und genau so ist sie entstanden.

    Rückgabe: `{kennung: [quelle, …]}` **nur** für Kennungen mit mehr als einer Quelle.
    Jede Quelle ist benannt (`registry:<kuerzel> (repo …)` / `ordner:projects/<p>`) —
    eine Zahl ohne Namen wäre B038.
    """
    quellen = {}
    daten = _lade_yaml(os.path.join(root, "process", "teams", "registry.yaml")) or {}
    for kuerzel, eintrag in (daten.get("teams") or {}).items():
        kennung = str(((eintrag or {}).get("projekt") or "")).strip().lower()
        if kennung:
            quellen.setdefault(kennung, []).append(
                f"registry:{kuerzel} (repo {(eintrag or {}).get('repo')})")
    projekte = os.path.join(root, "projects")
    if os.path.isdir(projekte):
        for name in sorted(os.listdir(projekte)):
            if (os.path.isdir(os.path.join(projekte, name))
                    and re.fullmatch(r"p\d+", name)):
                quellen.setdefault(name, []).append(f"ordner:projects/{name}")
    return {k: sorted(v) for k, v in sorted(quellen.items()) if len(v) > 1}
