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

# B054: Die Antwort-Überschrift wird an ihrem Anfang erkannt, nicht an ihrer vollen
# Fassung — die Sessions schreiben sie mit Zusatz ("des Teams", "Routine-Session",
# Uhrzeit). Das Datum kommt aus derselben Kopfzeile.
ANTWORT_KOPF = re.compile(r"(?m)^## Antwort\b(.*)$")
DATUM_IM_KOPF = re.compile(r"\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2})?")


class BriefkastenFehler(Exception):
    def __init__(self, code, meldung):
        super().__init__(meldung)
        self.code = code


def _verzeichnis(root, projekt):
    return os.path.join(aggregation.projekt_pfad(root, projekt), "management", "briefkasten")


def spalte_antwort(body):
    """Nachricht und Team-Antwort trennen (SWR-050) — Befund **B054**.

    Bis hierher wurde exakt auf `## Antwort (Team, JJJJ-MM-TT)` getrennt, also auf
    genau die Fassung, die der Test selbst erzeugt. Die Routine-Sessions schreiben
    seit dem 15.08. daneben `## Antwort des Teams (Routine-Session, JJJJ-MM-TT HH:MM)`
    — bei zehn von dreißig beantworteten pm-Briefen lief die Trennung deshalb ins
    Leere: `antwort` blieb leer, die vollständige Team-Antwort stand ungetrennt im
    Nachrichtenblock, und die Chat-Ansicht (`app.js`: `if (b.antwort)`) zeigte Frage
    und Antwort als einen Block. Betroffen war unter anderem `pm/N-0030`.

    Erkannt wird deshalb die **Überschrift**, nicht ihre Fassung; das Datum wird aus
    der Kopfzeile gelesen (mit Uhrzeit, wenn sie dasteht). Getrennt wird weiterhin
    an der **ersten** Antwort-Überschrift — alles darunter gehört zur Antwort.
    """
    m = ANTWORT_KOPF.search(body)
    if not m:
        return body.strip(), "", ""
    datum = DATUM_IM_KOPF.search(m.group(1) or "")
    return (body[:m.start()].strip(), body[m.end():].strip(),
            datum.group(0) if datum else "")


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
    nachricht, antwort, antwort_datum = spalte_antwort(body)
    return {"id": os.path.splitext(os.path.basename(pfad))[0],
            "von": felder.get("von", "?"), "zeit": felder.get("zeit", ""),
            "status": felder.get("status", "offen"),
            "nachricht": nachricht, "antwort": antwort,
            "antwort_datum": antwort_datum}


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
    add = subprocess.run(["git", "-C", repo, "add", "--", rel], capture_output=True,
        text=True, encoding="utf-8", errors="replace")
    commit = subprocess.run(["git", "-C", repo] + COMMIT_IDENTITAET +
                            ["commit", "-m", f"Briefkasten {brief_id}: Nachricht vom Menschen"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if add.returncode or commit.returncode:
        raise BriefkastenFehler(503, "Git-Commit fehlgeschlagen: " +
                                (add.stderr + commit.stderr).strip()[:400])
    return {"brief": brief_id, "projekt": projekt, "zeit": zeit}
