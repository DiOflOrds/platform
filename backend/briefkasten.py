"""BCK-Briefkasten (SWR-050, P4/T-0009; ADR-006): Nachrichten des Menschen ans Team.

Briefe liegen als `<projekt>/management/briefkasten/N-XXXX.md` mit Frontmatter
(von, zeit, status offen|beantwortet); die Team-Antwort wird als Abschnitt
"## Antwort (Team, <Datum>)" in derselben Datei ergänzt. Schreiben = Datei +
sofortiger Git-Commit (ADR-003-Muster). Kein Zustand außerhalb von Git.
"""
import os
import re
import subprocess
from datetime import datetime, timezone

from . import aggregation

COMMIT_IDENTITAET = ["-c", "user.name=Mensch via Briefkasten",
                     "-c", "user.email=geraldine.john90@gmail.com"]


class BriefkastenFehler(Exception):
    def __init__(self, code, meldung):
        super().__init__(meldung)
        self.code = code


def _verzeichnis(root, projekt):
    return os.path.join(aggregation.projekt_pfad(root, projekt), "management", "briefkasten")


def _parse(pfad):
    text = open(pfad, encoding="utf-8").read()
    m = re.match(r"(?s)^---\n(.*?)\n---\n?(.*)$", text)
    felder, body = {}, text
    if m:
        for zeile in m.group(1).splitlines():
            if ":" in zeile:
                k, v = zeile.split(":", 1)
                felder[k.strip()] = v.strip()
        body = m.group(2).strip()
    teile = re.split(r"\n## Antwort \(Team, ([0-9-]+)\)\n", body, maxsplit=1)
    nachricht = teile[0].strip()
    antwort = teile[2].strip() if len(teile) == 3 else ""
    return {"id": os.path.splitext(os.path.basename(pfad))[0],
            "von": felder.get("von", "?"), "zeit": felder.get("zeit", ""),
            "status": felder.get("status", "offen"),
            "nachricht": nachricht, "antwort": antwort,
            "antwort_datum": teile[1] if len(teile) == 3 else ""}


def liste(root, projekt="p0"):
    """SWR-050: Konversation chronologisch (Briefe inkl. Antworten)."""
    verz = _verzeichnis(root, projekt)
    briefe = []
    if os.path.isdir(verz):
        for name in sorted(os.listdir(verz)):
            if re.fullmatch(r"N-\d{4}\.md", name):
                briefe.append(_parse(os.path.join(verz, name)))
    return {"briefe": briefe}


def offene(root, projekt):
    """Anzahl unbeantworteter Briefe (SWR-051: Cockpit-Hinweis, Preflight)."""
    return sum(1 for b in liste(root, projekt)["briefe"] if b["status"] == "offen")


def sende(root, projekt, text, von="E. John"):
    """SWR-050: Brief als Datei + sofortiger Commit. Gibt Brief-ID zurück."""
    text = (text or "").strip()
    if not text:
        raise BriefkastenFehler(400, "Nachricht darf nicht leer sein")
    if len(text) > 20000:
        raise BriefkastenFehler(400, "Nachricht zu lang (max. 20000 Zeichen)")
    try:
        repo = aggregation.projekt_pfad(root, projekt)
    except ValueError as e:
        raise BriefkastenFehler(404, str(e))
    verz = _verzeichnis(root, projekt)
    os.makedirs(verz, exist_ok=True)
    nummern = [int(m.group(1)) for n in os.listdir(verz)
               if (m := re.fullmatch(r"N-(\d{4})\.md", n))]
    brief_id = f"N-{(max(nummern) + 1 if nummern else 1):04d}"
    zeit = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pfad = os.path.join(verz, f"{brief_id}.md")
    with open(pfad, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"---\nvon: {von}\nzeit: {zeit}\nstatus: offen\n---\n\n{text}\n")
    rel = os.path.relpath(pfad, repo)
    add = subprocess.run(["git", "-C", repo, "add", "--", rel], capture_output=True, text=True)
    commit = subprocess.run(["git", "-C", repo] + COMMIT_IDENTITAET +
                            ["commit", "-m", f"Briefkasten {brief_id}: Nachricht vom Menschen"],
                            capture_output=True, text=True)
    if add.returncode or commit.returncode:
        raise BriefkastenFehler(503, "Git-Commit fehlgeschlagen: " +
                                (add.stderr + commit.stderr).strip()[:400])
    return {"brief": brief_id, "projekt": projekt, "zeit": zeit}
