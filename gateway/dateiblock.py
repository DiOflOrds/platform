"""Datei-Block-Konvention für Provider ohne Datei-Werkzeuge (ollama, session).

Das Modell (oder die Session) liefert Dateien als Textblöcke:

    ===DATEI: relativer/pfad.md===
    ...Inhalt...
    ===ENDE===

Dieses Modul parst solche Blöcke und schreibt sie sicher ins Arbeitsverzeichnis
(nur relative Pfade, kein '..', kein Laufwerk).
"""
import os
import re

MUSTER = re.compile(r"===DATEI:\s*(.+?)\s*===\r?\n(.*?)\r?\n===ENDE===", re.S)

AUSGABE_ANWEISUNG = """
## Ausgabeformat (zwingend)

Gib jede zu erstellende oder zu ändernde Datei als eigenen Block aus — ohne Text
zwischen den Blöcken, ohne Markdown-Codezäune um die Blöcke:

===DATEI: relativer/pfad/zur/datei.md===
(vollständiger Dateiinhalt)
===ENDE===

Nur relative Pfade innerhalb des Arbeitsverzeichnisses — das Arbeitsverzeichnis
IST bereits die Wurzel des Ziel-Repositories, also KEINEN Repository-Namen als
Präfix voranstellen (richtig: `cm/strategie.md`, falsch: `process/cm/strategie.md`).
Jede Datei vollständig (kein „Rest unverändert"). Keine weiteren Erklärungen
außerhalb der Blöcke.
""".strip()


def parse_dateibloecke(text):
    """Gibt Liste (pfad, inhalt) zurück. Ungültige Pfade -> ValueError."""
    bloecke = []
    for m in MUSTER.finditer(text or ""):
        pfad = m.group(1).strip().replace("\\", "/")
        if pfad.startswith("/") or re.match(r"^[A-Za-z]:", pfad) or ".." in pfad.split("/"):
            raise ValueError(f"unzulässiger Pfad im Datei-Block: {pfad}")
        bloecke.append((pfad, m.group(2)))
    return bloecke


def schreibe_dateibloecke(text, verzeichnis, repo_name=None):
    """Blöcke ins Verzeichnis schreiben. Gibt sortierte Liste der Pfade zurück.

    repo_name: Name des Ziel-Repos. Beginnt ein Pfad fälschlich mit
    '<repo_name>/', wird das Präfix entfernt (Problem T-0013: Modelle
    übernehmen Pfade aus dem Ticket-Text wörtlich inkl. Repo-Präfix).
    """
    repo_name = repo_name or os.path.basename(os.path.normpath(verzeichnis))
    geschrieben = []
    for pfad, inhalt in parse_dateibloecke(text):
        if repo_name and pfad.startswith(repo_name + "/"):
            pfad = pfad[len(repo_name) + 1:]
        ziel = os.path.join(verzeichnis, *pfad.split("/"))
        os.makedirs(os.path.dirname(ziel) or verzeichnis, exist_ok=True)
        with open(ziel, "w", encoding="utf-8", newline="\n") as f:
            f.write(inhalt.rstrip("\n") + "\n")
        geschrieben.append(pfad)
    return sorted(geschrieben)
