#!/usr/bin/env python3
"""Produktkatalog v0 (T-0056, Masterplan 5.5, REU.2 light).

Registriert/aktualisiert ein Produkt in `process/catalog/products.yaml` und
erzeugt die Detailseite `process/catalog/<name>.md`. Skript-Route beim Release
(SPL.2); CI-Automatik bewusst nach P0 (dokumentierte Abweichung, T-0056).

Nutzung:
    python catalog.py --katalog process/catalog --name datakonv --version 1.0.0
        --interface "CLI" --repo produkt-datakonv --projekt p0
        --capabilities "..." --limitations "..." --doku "..."
"""
import argparse
import os
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


def main():
    p = argparse.ArgumentParser(description="Produktkatalog v0 (T-0056)")
    p.add_argument("--katalog", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--interface", required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--projekt", required=True)
    p.add_argument("--capabilities", required=True)
    p.add_argument("--limitations", default="—")
    p.add_argument("--doku", default="README.md")
    a = p.parse_args()
    yaml_pfad, seite = registriere(a.katalog, {
        "name": a.name, "version": a.version, "released": date.today().isoformat(),
        "interface": a.interface, "repo": a.repo, "project": a.projekt,
        "capabilities": a.capabilities, "limitations": a.limitations, "doc": a.doku})
    print(f"Katalog aktualisiert: {yaml_pfad} + {seite}")


if __name__ == "__main__":
    main()
