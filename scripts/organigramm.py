#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Organigramm-Generator (Orga-Rework, process/docs/03-rollenmodell-v2-orga-rework.md Kap. 8).

Erzeugt aus den Registries (teams/registry.yaml, roles/registry.yaml,
roles/besetzungen.yaml) und den Projekt-Steckbriefen deterministisch:

  1. ORGANIGRAMM.md je Einheit (Team-/Projekt-Repo, neben BOARD.md) — Mermaid.
  2. process/ORGANIGRAMM.md — Gesamtorganisation.
  3. platform/backend/static/organigramm.json — dieselben Daten fürs Frontend.

Quelle ist die Registry, nie Handpflege (Muster arch_diagramm.py). Kein Zeitstempel
im Ergebnis — sonst wäre --check nie grün.

Nutzung:
    python organigramm.py --repos <wurzel>
    python organigramm.py --repos <wurzel> --check   # Exit 1, wenn Dateien nicht zur Quelle passen
"""
import argparse
import io
import json
import os
import sys

try:
    import yaml
except ImportError:
    yaml = None

MOTOR_ZEICHEN = {"cowork": "Cowork/Session", "ollama": "Ollama (lokal)",
                 "api": "Claude-API", "script": "Skript", "mensch": "Mensch"}


def _lies_yaml(pfad):
    if not os.path.isfile(pfad):
        return {}
    with io.open(pfad, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _steckbrief(pfad):
    daten = _lies_yaml(os.path.join(pfad, "steckbrief.yaml"))
    return daten.get("beschreibung", ""), daten.get("status", "")


def entdecke_einheiten(root):
    """Discovery wie aggregation.projekte: Top-Level-Repos mit tickets/ + .git,
    dazu projects/<d> mit tickets/. Liefert {name: pfad}, sortiert."""
    einheiten = {}
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d)
        if os.path.isdir(os.path.join(p, "tickets")) and os.path.isdir(os.path.join(p, ".git")):
            einheiten[d] = p
    sammel = os.path.join(root, "projects")
    if os.path.isdir(sammel):
        for d in sorted(os.listdir(sammel)):
            p = os.path.join(sammel, d)
            if os.path.isdir(os.path.join(p, "tickets")) and d not in einheiten:
                einheiten[d] = p
    return einheiten


def sammle(root):
    """Registries + Steckbriefe -> ein Datenmodell (deterministisch sortiert)."""
    proc = os.path.join(root, "process")
    teams = (_lies_yaml(os.path.join(proc, "teams", "registry.yaml")) or {}).get("teams", {})
    rollen = (_lies_yaml(os.path.join(proc, "roles", "registry.yaml")) or {}).get("roles", {})
    besetzungen = (_lies_yaml(os.path.join(proc, "roles", "besetzungen.yaml")) or {}).get("besetzungen", {})
    einheiten_pfade = entdecke_einheiten(root)

    # Team-Zuordnung: repo -> Team-Eintrag (teams-Registry nennt das Haupt-Repo)
    team_je_repo = {}
    for kuerzel, t in teams.items():
        team_je_repo[t.get("repo", kuerzel)] = dict(t, kuerzel=kuerzel)

    einheiten = []
    for name in sorted(einheiten_pfade):
        pfad = einheiten_pfade[name]
        beschreibung, status = _steckbrief(pfad)
        team = team_je_repo.get(name)
        typ = (team or {}).get("typ") or "projekt"
        eintrag = {
            "einheit": name,
            "typ": typ,
            "team": (team or {}).get("kuerzel"),
            "anzeigename": (team or {}).get("name") or name,
            "profil": (team or {}).get("profil") or ("entwicklung" if name.startswith("p") else ""),
            "status": (team or {}).get("status") or status or "ohne Status",
            "datenklasse": (team or {}).get("datenklasse") or "intern",
            "beschreibung": beschreibung,
            "rollen": [],
        }
        # Besetzungen dieser Einheit
        besetzt = set()
        for instanz in sorted(besetzungen):
            b = besetzungen[instanz]
            if b.get("einheit") != name:
                continue
            rolle = b.get("rolle", "")
            besetzt.add(rolle)
            eintrag["rollen"].append({
                "instanz": instanz,
                "rolle": rolle,
                "name": (rollen.get(rolle) or {}).get("name") or rolle,
                "motor": b.get("motor", ""),
                "modell": b.get("modell", ""),
                "takt": b.get("takt", ""),
                "status": b.get("status", ""),
                "hinweis": b.get("hinweis", ""),
                "quelle": "besetzung",
            })
        # Rollen laut Team-Registry ohne Besetzung -> sichtbar als unbesetzt
        for rolle in (team or {}).get("rollen") or []:
            if rolle not in besetzt:
                eintrag["rollen"].append({
                    "instanz": "%s@%s" % (rolle, name), "rolle": rolle,
                    "name": (rollen.get(rolle) or {}).get("name") or rolle,
                    "motor": "", "modell": "", "takt": "", "status": "unbesetzt",
                    "hinweis": "", "quelle": "registry",
                })
        einheiten.append(eintrag)
    return {"einheiten": einheiten,
            "koordination": "PM-Team koordiniert alle PL-Instanzen (Charter pm/docs/01-team-charter.md)",
            "mensch": "Auftraggeber / Eskalationsinstanz (Klasse A, Gates)"}


def _mermaid_rolle(r):
    zeile = r["instanz"]
    if r["status"] == "unbesetzt":
        return "%s<br/>(unbesetzt)" % zeile
    motor = MOTOR_ZEICHEN.get(r["motor"], r["motor"])
    if r.get("modell"):
        motor += " · " + r["modell"]
    return "%s<br/>%s" % (zeile, motor)


def _knoten_id(text):
    return "".join(c if c.isalnum() else "_" for c in text)


def mermaid_einheit(e, gesamt=False):
    """Eine Einheit als Mermaid-Graph: Mensch -> PM -> Einheit -> Instanzen."""
    z = ["```mermaid", "graph TB"]
    z.append('  MENSCH["Mensch<br/>Auftraggeber / Gates"]')
    z.append('  PM["PM-Team<br/>koordiniert alle PL"]')
    z.append("  MENSCH --> PM")
    kid = _knoten_id(e["einheit"])
    kopf = e["anzeigename"] if e["anzeigename"] != e["einheit"] else e["einheit"]
    z.append('  %s["%s<br/>%s · %s"]' % (kid, kopf, e["profil"] or e["typ"], e["status"]))
    z.append("  PM --> %s" % kid)
    for r in e["rollen"]:
        rid = _knoten_id(r["instanz"])
        z.append('  %s["%s"]' % (rid, _mermaid_rolle(r)))
        z.append("  %s --> %s" % (kid, rid))
        if r["status"] == "unbesetzt":
            z.append("  style %s stroke-dasharray: 5 5" % rid)
    z.append("```")
    return "\n".join(z)


def md_einheit(e):
    kopf = ("# Organigramm: %s\n\n"
            "*Generiert aus den Registries (`process/teams/registry.yaml`, "
            "`process/roles/besetzungen.yaml`) durch `platform/scripts/organigramm.py` — "
            "**nicht von Hand pflegen**, Änderungen gehören in die Registry "
            "(Konzept `process/docs/03-rollenmodell-v2-orga-rework.md` Kap. 8).*\n\n"
            % (e["anzeigename"] if e["anzeigename"] != e["einheit"] else e["einheit"]))
    if e["beschreibung"]:
        kopf += "**Auftrag:** %s\n\n" % e["beschreibung"]
    kopf += mermaid_einheit(e) + "\n\n## Beteiligte\n\n"
    kopf += "| Instanz | Rolle | Motor | Takt | Status | Hinweis |\n|---|---|---|---|---|---|\n"
    for r in e["rollen"]:
        motor = MOTOR_ZEICHEN.get(r["motor"], r["motor"]) or "—"
        if r.get("modell"):
            motor += " (%s)" % r["modell"]
        kopf += "| %s | %s | %s | %s | %s | %s |\n" % (
            r["instanz"], r["name"], motor, r["takt"] or "—", r["status"], r["hinweis"] or "—")
    kopf += ("\nRollen-Bauplan: `process/roles/<rolle>.md` · projektspezifischer Teil: "
             "`roles/<rolle>.md` in diesem Repo · Historie: `docs/historie.md`\n")
    return kopf


def md_gesamt(modell):
    z = ["# Organigramm der Gesamtorganisation", "",
         "*Generiert durch `platform/scripts/organigramm.py` — nicht von Hand pflegen. "
         "Je Einheit liegt ein eigenes `ORGANIGRAMM.md` im Repo.*", "",
         "```mermaid", "graph TB",
         '  MENSCH["Mensch<br/>Auftraggeber / Gates (Klasse A)"]',
         '  PM["PM-Team<br/>Intake · Staffing · PL-Koordination"]',
         "  MENSCH --> PM"]
    for e in modell["einheiten"]:
        # Nur laufende Einheiten ins Bild; abgeschlossene/status-lose stehen in der Tabelle.
        if e["einheit"] == "pm" or e["status"] not in ("aktiv", "in_gruendung", "pausiert"):
            continue
        kid = _knoten_id(e["einheit"])
        z.append('  %s["%s<br/>%s · %d Rollen"]' % (
            kid, e["einheit"], e["profil"] or e["typ"], len(e["rollen"])))
        z.append("  PM --> %s" % kid)
    z.append("```")
    z.append("")
    z.append("| Einheit | Typ | Profil | Status | Datenklasse | Besetzungen |")
    z.append("|---|---|---|---|---|---|")
    for e in modell["einheiten"]:
        besetzt = [r for r in e["rollen"] if r["quelle"] == "besetzung"]
        z.append("| %s | %s | %s | %s | %s | %s |" % (
            e["einheit"], e["typ"], e["profil"] or "—", e["status"], e["datenklasse"],
            ", ".join(r["instanz"] for r in besetzt) or "—"))
    z.append("")
    return "\n".join(z)


def ziele(root, modell):
    """Alle Zieldateien -> {pfad: inhalt} (deterministisch)."""
    pfad_je_einheit = entdecke_einheiten(root)
    dateien = {}
    for e in modell["einheiten"]:
        repo = pfad_je_einheit.get(e["einheit"])
        if repo:
            dateien[os.path.join(repo, "ORGANIGRAMM.md")] = md_einheit(e)
    dateien[os.path.join(root, "process", "ORGANIGRAMM.md")] = md_gesamt(modell)
    dateien[os.path.join(root, "platform", "backend", "static", "organigramm.json")] = (
        json.dumps(modell, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    return dateien


def main(argv=None):
    ap = argparse.ArgumentParser(description="Organigramme aus den Registries erzeugen")
    ap.add_argument("--repos", default=".", help="Wurzel der Arbeitskopien")
    ap.add_argument("--check", action="store_true",
                    help="nur prüfen: Exit 1, wenn eine Zieldatei nicht zur Quelle passt")
    args = ap.parse_args(argv)
    if yaml is None:
        print("FEHLER: PyYAML fehlt (pip install pyyaml)")
        return 2
    root = os.path.abspath(args.repos)
    modell = sammle(root)
    dateien = ziele(root, modell)
    abweichungen = []
    for pfad in sorted(dateien):
        soll = dateien[pfad]
        ist = None
        if os.path.isfile(pfad):
            with io.open(pfad, "r", encoding="utf-8") as f:
                ist = f.read()
        if ist == soll:
            continue
        abweichungen.append(pfad)
        if not args.check:
            os.makedirs(os.path.dirname(pfad), exist_ok=True)
            with io.open(pfad, "w", encoding="utf-8", newline="\n") as f:
                f.write(soll)
    if args.check:
        if abweichungen:
            print("ORGANIGRAMM veraltet (%d Datei(en)) — organigramm.py laufen lassen:" % len(abweichungen))
            for p in abweichungen:
                print("  " + os.path.relpath(p, root))
            return 1
        print("Organigramme passen zur Quelle (%d Dateien)." % len(dateien))
        return 0
    print("Geschrieben/aktuell: %d Dateien (%d geändert)." % (len(dateien), len(abweichungen)))
    for p in abweichungen:
        print("  " + os.path.relpath(p, root))
    return 0


if __name__ == "__main__":
    # ⚠ platform/T-0009: Wer ein `__main__` hat, kann Befunde drucken — und darf daran
    # nicht sterben. Auf einer cp1252-Konsole reicht ein „ä" in einem Rollennamen, und
    # der Lauf endet im UnicodeEncodeError statt in der Meldung.
    #
    # ⚠⚠ Diese Zeilen fehlten in der ersten Fassung dieses Skripts (Orga-Rework,
    # 2026-08-20). Gefunden hat das nicht der Autor, sondern
    # `test_konsole.test_jeder_einstiegspunkt_sichert_seine_ausgabe` — eine Regel über
    # den GESAMTEN Produktionscode, die jeden neuen Einstiegspunkt automatisch erfasst.
    # Vierter Lauf in Folge, in dem eine ältere Zusicherung einen frischen Entwurf
    # verwirft (`L-2026-08-20cf`).
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import konsole
    konsole.sichere_ausgabe()  # platform/T-0009: am Melden nicht sterben
    sys.exit(main())
