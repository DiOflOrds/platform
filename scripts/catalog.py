#!/usr/bin/env python3
"""Produktkatalog v0 (T-0056, Masterplan 5.5, REU.2 light) + Check (SWR-036, P2/T-0008).

Registriert/aktualisiert ein Produkt in `process/catalog/products.yaml` und
erzeugt die Detailseite `process/catalog/<name>.md`. Skript-Route beim Release (SPL.2).

Check-Modus (löst die dokumentierte Abweichung aus p0/T-0056 ein — B7):
    python catalog.py --check --repos <wurzel> [--katalog process/catalog]
Prüft jeden Eintrag gegen sein Produkt-Repo (Repo da, Release-Tag v<version>,
pyproject-Version konsistent, Detailseite vorhanden) und findet produkt-*-Repos
mit Release-Tag ohne Katalog-Eintrag. Befunde je Produkt, Exit != 0.

Registrierung:
    python catalog.py --katalog process/catalog --name datakonv --version 1.0.0
        --interface "CLI" --repo produkt-datakonv --projekt p0
        --capabilities "..." --limitations "..." --doku "..."
"""
import argparse
import os
import re
import subprocess
from datetime import date

try:
    import yaml
except ImportError:
    yaml = None


def registriere(katalog_dir, eintrag):
    """Produkt in products.yaml + Detailseite schreiben. Gibt (yaml_pfad, seite) zurück."""
    if yaml is None:
        raise RuntimeError("PyYAML fehlt (pip install -r platform/requirements.txt).")
    os.makedirs(katalog_dir, exist_ok=True)
    yaml_pfad = os.path.join(katalog_dir, "products.yaml")
    daten = {"products": {}}
    if os.path.exists(yaml_pfad):
        daten = yaml.safe_load(open(yaml_pfad, encoding="utf-8")) or {"products": {}}
    name = eintrag["name"]
    daten.setdefault("products", {})[name] = {k: v for k, v in eintrag.items() if k != "name"}
    with open(yaml_pfad, "w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(daten, f, allow_unicode=True, sort_keys=True)
    seite = os.path.join(katalog_dir, f"{name}.md")
    with open(seite, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"""# {name} — Produktkatalog-Eintrag (v0)

*Generiert von platform/scripts/catalog.py — nicht von Hand editieren. Stand: {eintrag['released']}.*

| Feld | Wert |
|---|---|
| Version | {eintrag['version']} |
| Schnittstelle | {eintrag['interface']} |
| Repo | {eintrag['repo']} |
| Zuständiges Projekt | {eintrag['project']} |
| Fähigkeiten | {eintrag['capabilities']} |
| Bekannte Einschränkungen | {eintrag['limitations']} |
| Doku | {eintrag['doc']} |
""")
    return yaml_pfad, seite


def _repo_tags(repo):
    r = subprocess.run(["git", "-C", repo, "tag", "-l"], capture_output=True, text=True)
    return set(r.stdout.split()) if r.returncode == 0 else set()


def _pyproject_version(repo):
    pfad = os.path.join(repo, "pyproject.toml")
    if not os.path.exists(pfad):
        return None
    m = re.search(r'^version\s*=\s*"([^"]+)"', open(pfad, encoding="utf-8").read(), re.M)
    return m.group(1) if m else None


def pruefe(root, katalog_dir=None):
    """SWR-036: Katalog <-> Produkt-Repos abgleichen. [(produkt, befund)] — leer = konsistent."""
    if yaml is None:
        raise RuntimeError("PyYAML fehlt (pip install -r platform/requirements.txt).")
    katalog_dir = katalog_dir or os.path.join(root, "process", "catalog")
    yaml_pfad = os.path.join(katalog_dir, "products.yaml")
    daten = {}
    if os.path.exists(yaml_pfad):
        daten = yaml.safe_load(open(yaml_pfad, encoding="utf-8")) or {}
    produkte = daten.get("products") or {}
    befunde = []
    for name, cfg in sorted(produkte.items()):
        repo_name = cfg.get("repo", "")
        repo = os.path.join(root, repo_name)
        if not os.path.isdir(os.path.join(repo, ".git")):
            befunde.append((name, f"Produkt-Repo fehlt unter der Wurzel: {repo_name}"))
            continue
        version = str(cfg.get("version", ""))
        if f"v{version}" not in _repo_tags(repo):
            befunde.append((name, f"Release-Tag v{version} fehlt in {repo_name}"))
        pv = _pyproject_version(repo)
        if pv is not None and pv != version:
            befunde.append((name, f"Versionskonflikt: Katalog {version} vs. pyproject {pv}"))
        if not os.path.exists(os.path.join(katalog_dir, f"{name}.md")):
            befunde.append((name, "Detailseite fehlt im Katalog"))
    eingetragen = {cfg.get("repo") for cfg in produkte.values()}
    for eintrag in sorted(os.listdir(root)):
        repo = os.path.join(root, eintrag)
        if not eintrag.startswith("produkt-") or not os.path.isdir(os.path.join(repo, ".git")):
            continue
        if eintrag in eingetragen:
            continue
        if any(re.match(r"v\d", t) for t in _repo_tags(repo)):
            befunde.append((eintrag, "Release-Tag vorhanden, aber kein Katalog-Eintrag"))
    return befunde


def main():
    p = argparse.ArgumentParser(description="Produktkatalog v0 (T-0056) + Check (SWR-036)")
    p.add_argument("--check", action="store_true")
    p.add_argument("--repos", default=".")
    p.add_argument("--katalog")
    p.add_argument("--name")
    p.add_argument("--version")
    p.add_argument("--interface")
    p.add_argument("--repo")
    p.add_argument("--projekt")
    p.add_argument("--capabilities")
    p.add_argument("--limitations", default="—")
    p.add_argument("--doku", default="README.md")
    a = p.parse_args()
    if a.check:
        befunde = pruefe(os.path.abspath(a.repos), a.katalog)
        for produkt, befund in befunde:
            print(f"KATALOG-BEFUND [{produkt}]: {befund}")
        if befunde:
            raise SystemExit(1)
        print("Katalog konsistent (SWR-036).")
        return
    pflicht = ["katalog", "name", "version", "interface", "repo", "projekt", "capabilities"]
    fehlend = [f for f in pflicht if not getattr(a, f)]
    if fehlend:
        p.error("ohne --check erforderlich: " + ", ".join("--" + f for f in fehlend))
    yaml_pfad, seite = registriere(a.katalog, {
        "name": a.name, "version": a.version, "released": date.today().isoformat(),
        "interface": a.interface, "repo": a.repo, "project": a.projekt,
        "capabilities": a.capabilities, "limitations": a.limitations, "doc": a.doku})
    print(f"Katalog aktualisiert: {yaml_pfad} + {seite}")


if __name__ == "__main__":
    main()
