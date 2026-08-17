#!/usr/bin/env python3
"""Architekturbild-Generator (SWR-045, ADR-005, P3/T-0015).

Erzeugt aus `platform/architecture/komponenten.yaml` (Schichten, Komponenten,
Beziehungen) ein deterministisches SVG (`architektur.svg`) — Schichten als Zeilen,
Komponenten als Boxen, Beziehungen als Pfeile mit optionalem Label. Kein Build,
keine externe Bibliothek außer PyYAML (bereits Plattform-Abhängigkeit).

Nutzung:
    python arch_diagramm.py [--quelle X.yaml] [--ziel X.svg]
    python arch_diagramm.py --check     # Exit 1, wenn Bild nicht zur Quelle passt (Gate)
"""
import argparse
import os
import sys

try:
    import yaml
except ImportError:
    yaml = None

_HIER = os.path.dirname(os.path.abspath(__file__))
QUELLE = os.path.join(_HIER, "..", "architecture", "komponenten.yaml")
ZIEL = os.path.join(_HIER, "..", "architecture", "architektur.svg")

BOX_B, BOX_H, LUECKE_X, ZEILE_H, RAND = 240, 52, 28, 130, 30


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def generiere(daten):
    """YAML-Struktur -> SVG-Text (deterministisch: Reihenfolge = Quelle)."""
    schichten = daten.get("schichten") or []
    beziehungen = daten.get("beziehungen") or []
    pos = {}
    max_spalten = max((len(s.get("komponenten") or []) for s in schichten), default=1)
    breite = 2 * RAND + max_spalten * BOX_B + (max_spalten - 1) * LUECKE_X + 160
    hoehe = 2 * RAND + len(schichten) * ZEILE_H
    teile = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {breite} {hoehe}" '
             f'font-family="system-ui, sans-serif" font-size="13">',
             '<defs><marker id="pfeil" markerWidth="9" markerHeight="7" refX="8" refY="3.5" '
             'orient="auto"><polygon points="0 0, 9 3.5, 0 7" fill="#57606a"/></marker></defs>',
             f'<rect width="{breite}" height="{hoehe}" fill="#f6f8fa"/>']
    for zi, schicht in enumerate(schichten):
        y = RAND + zi * ZEILE_H
        teile.append(f'<text x="{RAND}" y="{y + 14}" fill="#57606a" font-size="12" '
                     f'font-weight="600">{_esc(schicht.get("name", ""))}</text>')
        for si, komp in enumerate(schicht.get("komponenten") or []):
            x = RAND + 150 + si * (BOX_B + LUECKE_X)
            by = y + 24
            pos[komp["id"]] = (x + BOX_B / 2, by, by + BOX_H)
            teile.append(f'<rect x="{x}" y="{by}" width="{BOX_B}" height="{BOX_H}" rx="8" '
                         f'fill="#ffffff" stroke="#1a2b3c" stroke-width="1.4"/>')
            teile.append(f'<text x="{x + BOX_B / 2}" y="{by + BOX_H / 2 + 4}" '
                         f'text-anchor="middle">{_esc(komp.get("name", komp["id"]))}</text>')
    for b in beziehungen:
        von, nach = pos.get(b.get("von")), pos.get(b.get("nach"))
        if not von or not nach:
            raise ValueError(f"Beziehung mit unbekannter Komponente: {b}")
        x1, y1 = von[0], von[2]
        x2, y2 = nach[0], nach[1]
        if y2 < y1:  # Ziel liegt oberhalb: Pfeil von Oberkante zu Unterkante
            y1, y2 = von[1], nach[2]
        teile.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#57606a" '
                     f'stroke-width="1.2" marker-end="url(#pfeil)"/>')
        if b.get("label"):
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            teile.append(f'<text x="{mx + 5}" y="{my - 3}" fill="#57606a" '
                         f'font-size="11">{_esc(b["label"])}</text>')
    teile.append("</svg>")
    return "\n".join(teile) + "\n"


def lade(quelle):
    if yaml is None:
        raise RuntimeError("PyYAML fehlt (pip install -r platform/requirements.txt).")
    return yaml.safe_load(open(quelle, encoding="utf-8"))


def main():
    p = argparse.ArgumentParser(description="Architekturbild (SWR-045)")
    p.add_argument("--quelle", default=QUELLE)
    p.add_argument("--ziel", default=ZIEL)
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    svg = generiere(lade(a.quelle))
    if a.check:
        vorhanden = open(a.ziel, encoding="utf-8").read() if os.path.exists(a.ziel) else ""
        if vorhanden != svg:
            print("ARCHITEKTUR-DRIFT: architektur.svg passt nicht zur komponenten.yaml — "
                  "Generator ausführen und mitcommitten.")
            sys.exit(1)
        print("Architekturbild konsistent (SWR-045).")
        return
    with open(a.ziel, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    print(f"Architekturbild geschrieben: {a.ziel}")


if __name__ == "__main__":
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import konsole
    konsole.sichere_ausgabe()  # platform/T-0009: am Melden nicht sterben
    main()
