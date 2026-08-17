# -*- coding: utf-8 -*-
"""teams.py (P7): Team-Daten für die HMI (SWR-053) + Konfigurations-Schreibpfad (SWR-056).

Ein "Team-Repo" ist ein entdecktes Projekt mit team.yaml (Playbook Kap. 15).
Lesen liefert Steckbrief, Charta, Konfiguration, SLA und Digest-Verlauf.
Schreiben ändert ausschließlich die drei freigegebenen Eckparameter
(zeitraum_tage 1/7/30, abschnitt_rechnungen, zustellung_mail) in
konfiguration.yaml mit sofortigem Commit (Identität "Mensch via HMI") —
Konten sind Klasse A und werden hier nie verändert (SWR-056).

P8-E4 (CRs pm/T-0006/T-0007): zusätzlich wählbar sind das Ollama-Modell
(SWR-071, Liste live vom LOKALEN Ollama) und ein freier KI-Hinweis für den
Prompt (SWR-072).
"""
import json
import os
import re
import subprocess
import urllib.request

GUELTIGE_ZEITRAEUME = (1, 7, 30)
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
HINWEIS_MAX = 200  # SWR-072: Freitext bleibt einzeilig und kurz
_COMMIT_IDENT = ["-c", "user.name=Mensch via HMI", "-c", "user.email=mensch@hmi.local"]
_DIGEST_NAME = re.compile(r"^[\w][\w.-]*\.md$")


class TeamFehler(Exception):
    """code = HTTP-Status, Meldung deutsch (Muster InboxFehler/BriefkastenFehler)."""

    def __init__(self, code, meldung):
        super().__init__(meldung)
        self.code = code


def ist_team(root, projekt):
    return os.path.isfile(os.path.join(root, projekt, "team.yaml"))


def _pfad(root, projekt, *teile):
    return os.path.join(root, projekt, *teile)


def _lese(pfad):
    with open(pfad, encoding="utf-8") as f:
        return f.read()


def lade_steckbrief(root, projekt):
    """team.yaml (manuell geparst, kein pyyaml — Muster inbox.lade_nutzer)."""
    daten = {"name": projekt, "typ": "", "profil": "", "datenklasse": "intern",
             "rollen": [], "sla": [], "gegruendet": ""}
    pfad = _pfad(root, projekt, "team.yaml")
    if not os.path.isfile(pfad):
        raise TeamFehler(404, f"'{projekt}' ist kein Team-Projekt (keine team.yaml).")
    for zeile in _lese(pfad).splitlines():
        roh = zeile.split("#", 1)[0].rstrip()
        strip = roh.strip()
        if strip.startswith("- ") and daten["sla"] is not None and roh.startswith("  "):
            daten["sla"].append(strip[2:].strip().strip('"'))
        elif ":" in strip and not roh.startswith(" "):
            k, v = strip.split(":", 1)
            k, v = k.strip(), v.strip().strip('"')
            if k == "rollen":
                daten["rollen"] = [r.strip() for r in v.strip("[]").split(",") if r.strip()]
            elif k in ("name", "typ", "profil", "datenklasse", "gegruendet"):
                daten[k] = v
    return daten


def lade_konfiguration(root, projekt):
    """konfiguration.yaml → Eckparameter (Konten nur Namen, nie Zugangsdaten)."""
    cfg = {"zeitraum_tage": 1, "takte": [], "konten": [], "abschnitt_rechnungen": True,
           "zustellung_mail": False, "ollama_modell": "", "ki_hinweis": "",
           "vorhanden": False}
    pfad = _pfad(root, projekt, "konfiguration.yaml")
    if not os.path.isfile(pfad):
        return cfg
    cfg["vorhanden"] = True
    for zeile in _lese(pfad).splitlines():
        roh = zeile.split("#", 1)[0].rstrip()
        strip = roh.strip()
        if strip.startswith("- name:"):
            cfg["konten"].append({"name": strip.split(":", 1)[1].strip(), "env_suffix": ""})
        elif strip.startswith("env_suffix:") and cfg["konten"]:
            cfg["konten"][-1]["env_suffix"] = strip.split(":", 1)[1].strip().strip('"')
        elif ":" in strip and not roh.startswith("    "):
            k, v = strip.split(":", 1)
            k, v = k.strip(), v.strip()
            if k == "zeitraum_tage" and v.isdigit():
                cfg["zeitraum_tage"] = int(v)
            elif k == "takte":  # SWR-064 (P8): Mehrfachauswahl
                cfg["takte"] = sorted({int(t) for t in v.strip("[]").split(",")
                                       if t.strip().isdigit()} & set(GUELTIGE_ZEITRAEUME))
            elif k in ("ollama_modell", "ki_hinweis"):  # SWR-071/072 (P8-E4)
                cfg[k] = v.strip().strip('"')
            elif k in ("abschnitt_rechnungen", "zustellung_mail"):
                cfg[k] = v.lower() in ("ja", "true", "yes")
    if not cfg["takte"]:  # rückwärtskompatibel
        cfg["takte"] = [cfg["zeitraum_tage"]] if cfg["zeitraum_tage"] in GUELTIGE_ZEITRAEUME else [1]
    return cfg


def digest_liste(root, projekt):
    """Digest-Verlauf, neueste zuerst (Dateiname beginnt mit YYYY-MM-DD)."""
    verz = _pfad(root, projekt, "digest")
    if not os.path.isdir(verz):
        return []
    namen = sorted((n for n in os.listdir(verz)
                    if n.endswith(".md") and _DIGEST_NAME.match(n)), reverse=True)
    ergebnis = []
    for n in namen:
        kopf = _lese(os.path.join(verz, n)).lstrip().splitlines()
        titel = kopf[0].lstrip("# ").strip() if kopf else n
        ergebnis.append({"name": n, "datum": n[:10], "titel": titel})
    return ergebnis


def digest_inhalt(root, projekt, name):
    """Ein Digest im Volltext (SWR-053); Namensmuster verhindert Pfad-Ausbruch."""
    if not _DIGEST_NAME.match(name or ""):
        raise TeamFehler(400, "Ungültiger Digest-Name.")
    pfad = _pfad(root, projekt, "digest", name)
    if not os.path.isfile(pfad):
        raise TeamFehler(404, f"Digest '{name}' nicht gefunden.")
    return {"name": name, "inhalt": _lese(pfad)}


def team_daten(root, projekt):
    """SWR-053: alles für den Team-Tab in einer Antwort."""
    steckbrief = lade_steckbrief(root, projekt)
    charta_pfad = _pfad(root, projekt, "docs", "01-team-charter.md")
    charta = _lese(charta_pfad) if os.path.isfile(charta_pfad) else ""
    digests = digest_liste(root, projekt)
    return {"projekt": projekt, "steckbrief": steckbrief,
            "konfiguration": lade_konfiguration(root, projekt),
            "charta": charta, "digests": digests,
            "letzter_digest": digests[0]["datum"] if digests else ""}


def _bool_text(wert):
    return "ja" if wert else "nein"


def _ollama_tags(timeout=5):
    """Installierte Modelle vom LOKALEN Ollama (localhost, nie Cloud — F17/SWR-062)."""
    with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=timeout) as antwort:
        daten = json.loads(antwort.read().decode("utf-8"))
    return [m.get("name", "") for m in daten.get("models", []) if m.get("name")]


def ollama_modelle(root, projekt, abruf=_ollama_tags):
    """SWR-071: Auswahlliste für den Konfigurator + aktuell wirksames Modell.

    `abruf` ist injizierbar (Tests). Ist Ollama nicht erreichbar, bleibt die
    Antwort gültig — mit leerer Liste und deutschem Grund, damit das Formular
    weiter bedienbar ist und den konfigurierten Wert behält.
    """
    if not ist_team(root, projekt):
        raise TeamFehler(404, f"'{projekt}' ist kein Team-Projekt (keine team.yaml).")
    konfiguriert = lade_konfiguration(root, projekt)["ollama_modell"]
    try:
        modelle = list(abruf())
        hinweis = "" if modelle else "Ollama antwortet, hat aber kein Modell installiert."
    except Exception as e:  # noqa: BLE001 — Ausfall ist ein Normalfall, kein Serverfehler
        modelle, hinweis = [], ("Ollama auf diesem Rechner nicht erreichbar (" + str(e)[:80]
                                + ") — gespeicherte Auswahl bleibt unverändert.")
    aktiv = konfiguriert or (modelle[0] if modelle else "")
    return {"projekt": projekt, "modelle": modelle, "konfiguriert": konfiguriert,
            "aktiv": aktiv, "automatisch": not konfiguriert, "hinweis": hinweis}


def _pruefe_hinweis(wert):
    """SWR-072: einzeilig, kurz, ohne '#' (Kommentarzeichen der Konfigurationsdatei)."""
    text = (wert or "").strip()
    if not text:
        return ""
    if len(text) > HINWEIS_MAX:
        raise TeamFehler(400, f"KI-Hinweis ist zu lang (max. {HINWEIS_MAX} Zeichen).")
    if any(z in text for z in ("\n", "\r")):
        raise TeamFehler(400, "KI-Hinweis muss einzeilig sein (keine Zeilenumbrüche).")
    if "#" in text or '"' in text:
        raise TeamFehler(400, "KI-Hinweis darf kein # und keine Anführungszeichen enthalten.")
    return text


def _pruefe_modell(wert):
    """SWR-071: leer = automatisch; sonst schlichter Modellname ohne Sonderzeichen."""
    text = (wert or "").strip().strip('"')
    if not text:
        return ""
    if len(text) > 100 or not re.fullmatch(r"[\w./:+-]+", text):
        raise TeamFehler(400, "Ungültiger Modellname — erlaubt sind Buchstaben, Ziffern "
                              "und . / : + - _ (leer = automatisch).")
    return text


def konfiguration_schreiben(root, projekt, werte):
    """SWR-056: validieren, konfiguration.yaml neu schreiben (Konten unverändert
    übernehmen), sofort committen. Gibt die neue Konfiguration zurück."""
    if not ist_team(root, projekt):
        raise TeamFehler(404, f"'{projekt}' ist kein Team-Projekt (keine team.yaml).")
    alt = lade_konfiguration(root, projekt)
    try:  # SWR-064: Mehrfachauswahl; einzelnes zeitraum_tage bleibt gültig (Altpfad)
        if "takte" in werte:
            takte = sorted({int(t) for t in (werte.get("takte") or [])})
        else:
            takte = [int(werte.get("zeitraum_tage", alt["takte"][0]))]
    except (TypeError, ValueError):
        raise TeamFehler(400, "Takte müssen Zahlen sein (1, 7, 30).")
    if not takte or any(t not in GUELTIGE_ZEITRAEUME for t in takte):
        raise TeamFehler(400, "Ungültige Takt-Auswahl — erlaubt sind 1 (Tag), 7 (Woche), "
                              "30 (Monat), mindestens einer.")
    if "konten" in werte:
        raise TeamFehler(400, "Konten sind Klasse A und werden nicht über das HMI geändert "
                              "(Playbook Kap. 16) — bitte per Brief/Session beantragen.")
    rechnungen = bool(werte.get("abschnitt_rechnungen", alt["abschnitt_rechnungen"]))
    zustellung = bool(werte.get("zustellung_mail", alt["zustellung_mail"]))
    # SWR-071/072 (P8-E4): nicht mitgeschickte Felder bleiben unverändert
    modell = _pruefe_modell(werte["ollama_modell"] if "ollama_modell" in werte
                            else alt["ollama_modell"])
    hinweis = _pruefe_hinweis(werte["ki_hinweis"] if "ki_hinweis" in werte
                              else alt["ki_hinweis"])

    zeilen = [
        "# Konfiguration " + projekt + " (Eckparameter des Teams — P5-Prinzip: Teams sind konfigurierbar)",
        "# Aendern: HMI-Formular (PIN) oder Datei/Brief. NIE Passwoerter hier eintragen.",
        "",
        f"takte: [{', '.join(str(t) for t in takte)}]        # 1 = Tages-, 7 = Wochen-, 30 = Monats-Digest (mehrere gleichzeitig, SWR-064)",
        "",
        "konten:                     # Klasse A — Aenderung nur per Brief/Session (Zugangs-Freigabe)",
    ]
    for konto in alt["konten"]:
        zeilen.append(f"  - name: {konto['name']}")
        zeilen.append(f"    env_suffix: \"{konto['env_suffix']}\"")
    zeilen += [
        "",
        f"abschnitt_rechnungen: {_bool_text(rechnungen)}    # eigener Digest-Abschnitt Rechnungen/Zahlungen",
        f"zustellung_mail: {_bool_text(zustellung)}         # ja = Digest zusaetzlich per Mail (SWR-058)",
        "",
        "# leer = erstes installiertes Ollama-Modell (SWR-071)",
        f"ollama_modell: {modell}",
        "# freier Zusatz-Auftrag an die KI, z. B. 'achte auf Bewerbungen' (SWR-072)",
        f"ki_hinweis: {hinweis}",
        "",
    ]
    pfad = _pfad(root, projekt, "konfiguration.yaml")
    with open(pfad, "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen))
    repo = os.path.join(root, projekt)
    subprocess.run(["git", "-C", repo, "add", "konfiguration.yaml"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    lauf = subprocess.run(["git", "-C", repo] + _COMMIT_IDENT +
                          ["commit", "-m", f"Konfiguration via HMI: takte={takte}, "
                           f"rechnungen={_bool_text(rechnungen)}, mail={_bool_text(zustellung)}, "
                           f"modell={modell or 'automatisch'}, hinweis={'ja' if hinweis else 'nein'}"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if lauf.returncode != 0 and "nothing to commit" not in (lauf.stdout + lauf.stderr):
        raise TeamFehler(500, "Konfiguration geschrieben, aber Commit fehlgeschlagen: "
                              + (lauf.stderr or lauf.stdout)[:200])
    return {"projekt": projekt, "konfiguration": lade_konfiguration(root, projekt)}


def _werkzeug(root, projekt):
    pfad = _pfad(root, projekt, "tools", "mail_digest.py")
    if not os.path.isfile(pfad):
        raise TeamFehler(404, f"'{projekt}' hat kein Digest-Werkzeug (tools/mail_digest.py).")
    return pfad


def _standard_runner(root, projekt, *argumente):
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
    import konsole  # platform/T-0009: Kind schreibt in derselben Kodierung, in der wir lesen

    def runner(pfad):  # noqa: ANN001
        lauf = subprocess.run([_sys.executable, pfad, *argumente],
                              capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", timeout=600,
                              env=konsole.kind_umgebung(),
                              cwd=os.path.join(root, projekt))
        return lauf.returncode, (lauf.stdout + lauf.stderr).strip()
    return runner


# SWR-090: Erkennungszeichen der Ergebniszeile des Werkzeugs. Gegenstueck zu
# `mail_digest.DIGEST_MARKER` — das Werkzeug liegt in einem anderen (lokalen, ggf. gar
# nicht vorhandenen) Repo und wird nie importiert, deshalb steht das Zeichen hier ein
# zweites Mal. Der Test `test_marker_stimmt_mit_werkzeug_ueberein` haelt beide zusammen.
_DIGEST_MARKER = "Digest -> "


def _digest_dateien(ausgabe):
    """SWR-090: Welche Digest-Dateien hat der Lauf geschrieben? Aus seiner eigenen
    Ergebniszeile gelesen — bewusst nicht aus einem Verzeichnis-Vergleich, weil ein
    zweiter Lauf am selben Tag dieselbe Datei ueberschreibt und der Vergleich dann
    faelschlich "nichts passiert" meldete (genau die Unsichtbarkeit aus N-0002)."""
    dateien = []
    for zeile in (ausgabe or "").splitlines():
        stelle = zeile.find(_DIGEST_MARKER)
        if stelle >= 0:
            name = zeile[stelle + len(_DIGEST_MARKER):].strip()
            if name and name not in dateien:
                dateien.append(name)
    return dateien


_TAKT_ANZEIGE = {1: "Tag", 7: "Woche", 30: "Monat"}


def digest_vorschau(root, projekt, runner=None):
    """SWR-090 (pm/T-0025): Womit läuft der Sofort-Knopf? Fragt das Werkzeug selbst
    (`--was-laeuft`, Auskunft ohne Wirkung — kein IMAP, kein Ollama, keine Datei).

    Bewusst kein Nachbau aus der Konfiguration: Die Takte kommen aus
    `mail_digest.jetzt_takte()`, also aus derselben Funktion, die der Lauf benutzt.
    Genau diese Trennung war der Befund aus `team-mail/N-0002` — der Knopf lief auf
    einem anderen Takt als konfiguriert, und nichts sprach darüber."""
    werkzeug = _werkzeug(root, projekt)
    if runner is None:
        runner = _standard_runner(root, projekt, "--was-laeuft")
    try:
        code, ausgabe = runner(werkzeug)
    except subprocess.TimeoutExpired:
        raise TeamFehler(504, "Zeitüberschreitung — das Team-Werkzeug antwortet nicht.")
    if code != 0:
        raise TeamFehler(502, "Auskunft des Werkzeugs fehlgeschlagen: " + (ausgabe or "")[-300:])
    try:
        daten = json.loads((ausgabe or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise TeamFehler(502, "Werkzeug lieferte keine lesbare Auskunft: " + (ausgabe or "")[-200:])
    takte = daten.get("takte") or []
    daten["takt_text"] = " · ".join(_TAKT_ANZEIGE.get(t.get("tage"), str(t.get("name")))
                                    for t in takte) or "—"
    daten["projekt"] = projekt
    return daten


def digest_jetzt(root, projekt, runner=None):
    """SWR-063 (P8): stößt den Sofort-Lauf des Team-Werkzeugs an (holen → Ollama →
    Digest → ggf. Mail). runner injizierbar für Tests; Default: subprocess.
    SWR-090: die entstandenen Digest-Dateien werden zusätzlich einzeln benannt."""
    werkzeug = _werkzeug(root, projekt)
    if runner is None:
        runner = _standard_runner(root, projekt, "--jetzt")
    try:
        code, ausgabe = runner(werkzeug)
    except subprocess.TimeoutExpired:
        raise TeamFehler(504, "Zeitüberschreitung — Ollama/IMAP antworten nicht (Werkzeuglauf abgebrochen).")
    if code != 0:
        raise TeamFehler(502, "Werkzeuglauf fehlgeschlagen: " + ausgabe[-300:])
    return {"projekt": projekt, "meldung": ausgabe[-600:] or "Lauf abgeschlossen.",
            "dateien": _digest_dateien(ausgabe)}
