#!/usr/bin/env python3
"""Der Telemetrie-Report je KI-Rolle (SWR-140, promt-team/T-0005).

Die Antwort auf `promt-team/N-0001` — *„welche Rollen über Claude, welche über Ollama?"*.

⚠ Solange kein Lauf Token meldet, ist die Antwort die **benannte Lücke** und nicht eine
Null, die wie eine Messung aussieht. Genau dafür ist dieses Skript da: es macht die
Baseline **als leer erkennbar**.

Nutzung: python platform/scripts/telemetrie_report.py [--wurzel .] [--nach DATEI]
"""
import argparse
import os
import sys

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HIER, "..")))
from backend import auswertung  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wurzel", default=os.path.normpath(os.path.join(_HIER, "..", "..")))
    p.add_argument("--nach", default=None, help="Zieldatei (Vorgabe: Ausgabe auf stdout)")
    a = p.parse_args(argv)
    text = auswertung.bericht(
        os.path.join(a.wurzel, "p0", "management", "runs", "run-registry.jsonl"),
        os.path.join(a.wurzel, "process", "roles", "registry.yaml"))
    if a.nach:
        os.makedirs(os.path.dirname(os.path.abspath(a.nach)), exist_ok=True)
        with open(a.nach, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"OK: Report nach {a.nach}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, _HIER)
    import konsole
    konsole.sichere_ausgabe()
    sys.exit(main())
