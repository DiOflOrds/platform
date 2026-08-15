# -*- coding: utf-8 -*-
"""teams.py (P7): Team-Daten für die HMI (SWR-053) + Konfigurations-Schreibpfad (SWR-056).

Ein "Team-Repo" ist ein entdecktes Projekt mit team.yaml (Playbook Kap. 15).
Lesen liefert Steckbrief, Charta, Konfiguration, SLA und Digest-Verlauf.
Schreiben ändert ausschließlich die drei freigegebenen Eckparameter
(zeitraum_tage 1/7/30, abschnitt_rechnungen, zustellung_mail) in
konfiguration.yaml mit sofortigem Commit (Identität "Mensch via HMI") —
Konten sind Klasse A und werden hier nie verändert (SWR-056).
"""
import os
import re
import subprocess

GUELTIGE_ZEITRAEUME = (1, 7, 30)
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
           "zustellung_mail": False, "vorhanden": False}
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
    ]
    pfad = _pfad(root, projekt, "konfiguration.yaml")
    with open(pfad, "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen))
    repo = os.path.join(root, projekt)
    subprocess.run(["git", "-C", repo, "add", "konfiguration.yaml"],
                   capture_output=True, text=True)
    lauf = subprocess.run(["git", "-C", repo] + _COMMIT_IDENT +
                          ["commit", "-m", f"Konfiguration via HMI: takte={takte}, "
                           f"rechnungen={_bool_text(rechnungen)}, mail={_bool_text(zustellung)}"],
                          capture_output=True, text=True)
    if lauf.returncode != 0 and "nothing to commit" not in (lauf.stdout + lauf.stderr):
        raise TeamFehler(500, "Konfiguration geschrieben, aber Commit fehlgeschlagen: "
                              + (lauf.stderr or lauf.stdout)[:200])
    return {"projekt": projekt, "konfiguration": lade_konfiguration(root, projekt)}


def digest_jetzt(root, projekt, runner=None):
    """SWR-063 (P8): stößt den Sofort-Lauf des Team-Werkzeugs an (holen → Ollama →
    Digest → ggf. Mail). runner injizierbar für Tests; Default: subprocess."""
    werkzeug = _pfad(root, projekt, "tools", "mail_digest.py")
    if not os.path.isfile(werkzeug):
        raise TeamFehler(404, f"'{projekt}' hat kein Digest-Werkzeug (tools/mail_digest.py).")
    if runner is None:
        import sys as _sys

        def runner(pfad):  # noqa: ANN001
            lauf = subprocess.run([_sys.executable, pfad, "--jetzt"],
                                  capture_output=True, text=True, timeout=600,
                                  cwd=os.path.join(root, projekt))
            return lauf.returncode, (lauf.stdout + lauf.stderr).strip()
    try:
        code, ausgabe = runner(werkzeug)
    except subprocess.TimeoutExpired:
        raise TeamFehler(504, "Zeitüberschreitung — Ollama/IMAP antworten nicht (Werkzeuglauf abgebrochen).")
    if code != 0:
        raise TeamFehler(502, "Werkzeuglauf fehlgeschlagen: " + ausgabe[-300:])
    return {"projekt": projekt, "meldung": ausgabe[-600:] or "Lauf abgeschlossen."}
