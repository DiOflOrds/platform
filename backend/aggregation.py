"""BCK-Aggregation (SWR-022): Board, Sprint-Reports und Kosten/KPI read-only
aus der Git-Arbeitskopie lesen. Kein Cache, kein Zustand (SWR-024).
"""
import glob
import json
import os
import re
import sys
from datetime import date as _datum, timedelta as _zeitspanne

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import board  # noqa: E402


def projekte(root):
    """SWR-025/ADR-004 + SWR-070 (P9): Discovery — Top-Level-Repos mit tickets/
    und .git PLUS Projektordner im Sammel-Repo projects/ (pm/D003)."""
    namen = []
    try:
        for d in sorted(os.listdir(root)):
            p = os.path.join(root, d)
            if os.path.isdir(os.path.join(p, "tickets")) and os.path.isdir(os.path.join(p, ".git")):
                namen.append(d)
        sammel = os.path.join(root, "projects")
        if os.path.isdir(os.path.join(sammel, ".git")):
            for d in sorted(os.listdir(sammel)):
                if os.path.isdir(os.path.join(sammel, d, "tickets")) and d not in namen:
                    namen.append(d)
    except OSError:
        pass
    return sorted(namen)


def projekt_pfad(root, projekt):
    """Projektnamen gegen die Discovery validieren (SWR-025); wirft ValueError.
    SWR-070: Ordner im Sammel-Repo projects/ werden auf ihren Pfad abgebildet."""
    bekannte = projekte(root)
    if projekt not in bekannte:
        raise ValueError(f"unbekanntes Projekt: {projekt} "
                         f"(bekannt: {', '.join(bekannte) or 'keine'})")
    direkt = os.path.join(root, projekt)
    if os.path.isdir(os.path.join(direkt, "tickets")):
        return direkt
    return os.path.join(root, "projects", projekt)


ALLE = "alle"  # SWR-085 (pm/N-0019): Sammelwert statt eines einzelnen Projektnamens


def ref(projekt, ticket_id):
    """SWR-087 (platform/N-0003): eindeutige Kennung einer Aufgabe über die ganze
    Organisation hinweg.

    Ticketnummern sind nur je Repo eindeutig — `T-0002` gibt es in `pm`, in `p2`
    und in `p10`. Eindeutig ist erst das Paar aus Repo und Nummer. Diese Funktion
    ist die EINE Stelle, die daraus eine Kennung macht; jede Ansicht ruft sie auf,
    damit Board, Cockpit, Inbox und Ticket-Detail nicht auseinanderlaufen
    (Lesson 2026-08-16, B025).
    """
    return f"{projekt}/{ticket_id}" if projekt and ticket_id else str(ticket_id or "")


def steckbrief(pfad):
    """SWR-066 (P9): steckbrief.yaml (beschreibung, status) + typ aus team.yaml."""
    info = {"beschreibung": "", "status": "", "typ": ""}
    sp = os.path.join(pfad, "steckbrief.yaml")
    if os.path.isfile(sp):
        for zeile in open(sp, encoding="utf-8"):
            z = zeile.split("#", 1)[0].strip()
            if z.startswith("beschreibung:"):
                info["beschreibung"] = z.split(":", 1)[1].strip().strip('"')
            elif z.startswith("status:"):
                info["status"] = z.split(":", 1)[1].strip()
    ty = os.path.join(pfad, "team.yaml")
    if os.path.isfile(ty):
        for zeile in open(ty, encoding="utf-8"):
            z = zeile.split("#", 1)[0].strip()
            if z.startswith("typ:"):
                info["typ"] = z.split(":", 1)[1].strip().strip('"')
    return info


GRUPPEN_NAMEN = (("festes-team", "Feste Teams"), ("projekt-team", "Projekt-Teams"),
                 ("aktiv", "Aktive Projekte"), ("abgeschlossen", "Abgeschlossen"))


def _tags(pfad):
    import subprocess
    return subprocess.run(["git", "-C", pfad, "tag", "-n1"],
                          capture_output=True, text=True).stdout


def einstufung(root, projekt, pfad=None, tag_text=None):
    """SWR-066/067 + SWR-082: EINE Ableitung von Beschreibung, Status und Gruppe.

    Cockpit (Kacheln) und Navigation (Kopfbereich) rufen dieselbe Funktion — genau
    deshalb können sie nicht auseinanderlaufen (pm/N-0015, T-0012). `pfad`/`tag_text`
    sind Durchreichungen für Aufrufer, die beides ohnehin schon haben.
    """
    pfad = pfad or projekt_pfad(root, projekt)
    sb = steckbrief(pfad)
    if tag_text is None:
        tag_text = _tags(pfad)
    status = sb["status"] or ("abgeschlossen" if (f"{projekt}-v1.0" in tag_text or
                              (projekt == "p0" and "genesis-v1.0" in tag_text)) else "aktiv")
    if sb["typ"] in ("aspice", "pm"):
        gruppe = "festes-team"
    elif sb["typ"] == "projekt":
        gruppe = "projekt-team"
    else:
        gruppe = "abgeschlossen" if status == "abgeschlossen" else "aktiv"
    return {"beschreibung": sb["beschreibung"], "status": status, "gruppe": gruppe}


def navigation(root):
    """SWR-082 (pm/N-0015, pm/T-0012): Navigationsgruppen für den Kopfbereich.

    Liefert dieselbe Menge und Gruppierung wie das Cockpit (`einstufung`), aber ohne
    Ticket-/KPI-Last: aktive Gruppen in fester Reihenfolge, abgeschlossene Projekte
    getrennt unter `weitere` — erreichbar, aber nicht im Weg. Leere Gruppen entfallen.
    """
    aktive, weitere = {}, []
    for name in projekte(root):
        e = einstufung(root, name)
        eintrag = {"projekt": name, "beschreibung": e["beschreibung"], "status": e["status"],
                   "gruppe": e["gruppe"]}
        if e["gruppe"] == "abgeschlossen":
            weitere.append(eintrag)
        else:
            aktive.setdefault(e["gruppe"], []).append(eintrag)
    gruppen = [{"schluessel": s, "name": n, "eintraege": aktive[s]}
               for s, n in GRUPPEN_NAMEN if aktive.get(s)]
    return {"gruppen": gruppen, "weitere": weitere,
            "anzahl_aktiv": sum(len(g["eintraege"]) for g in gruppen),
            "anzahl_weitere": len(weitere)}


def uebersicht(root):
    """SWR-026: je Projekt offene Tickets + offene Decision Requests."""
    eintraege = []
    for name in projekte(root):
        tickets, _ = board.lade_tickets(projekt_pfad(root, name))  # SWR-070
        offen = [t for t in tickets if t.get("status") not in ("done", "rejected")]
        drs = [{"id": t.get("id"), "titel": t.get("titel")} for t in offen
               if t.get("typ") == "decision-request"]
        eintraege.append({"projekt": name, "tickets_gesamt": len(tickets),
                          "tickets_offen": len(offen), "offene_drs": drs})
    return {"projekte": eintraege}


ENDZUSTAENDE = ("done", "rejected")


def ist_altlast(t, heute=None, tage=1):
    """SWR-075 (pm/N-0013): erledigt UND länger als `tage` her → im Board ausblendbar.

    Maßgeblich ist das Feld `geändert`; fehlt oder ist es unlesbar, gilt das Ticket als
    frisch und bleibt sichtbar (nie etwas ohne Datenlage verstecken).
    """
    if t.get("status") not in ENDZUSTAENDE:
        return False
    try:
        geaendert = _datum.fromisoformat(str(t.get("geändert", "")).strip())
    except ValueError:
        return False
    return ((heute or _datum.today()) - geaendert).days > tage


def lade_board(root, projekt="p0"):
    """Tickets gruppiert nach Status (Quelle: <projekt>/tickets/*.md; SWR-025)."""
    tickets, probleme = board.lade_tickets(projekt_pfad(root, projekt))
    gruppen = {}
    for t in sorted(tickets, key=lambda x: (x.get("status", ""), x.get("id", ""))):
        eintrag = {k: t.get(k) for k in
                   ("id", "titel", "typ", "prozess", "rolle", "sprint", "prio", "blocked_by",
                    "takt",       # SWR-074: wiederkehrend vs. einmalig
                    "geändert")}  # SWR-075: Alter erledigter Aufgaben
        eintrag["veraltet"] = ist_altlast(t)  # SWR-075 (pm/N-0013)
        eintrag["ref"] = ref(projekt, t.get("id"))  # SWR-087 (platform/N-0003)
        gruppen.setdefault(t.get("status", "unbekannt"), []).append(eintrag)
    return {"gruppen": gruppen, "anzahl": len(tickets), "validierungsprobleme": probleme}


def lade_ticket(root, projekt="p0", ticket_id=""):
    """SWR-040 (P3): Einzelticket mit allen Metadaten + Body für die Detailansicht."""
    tickets, _ = board.lade_tickets(projekt_pfad(root, projekt))
    for t in tickets:
        if t.get("id") == ticket_id:
            felder = {k: v for k, v in t.items() if not k.startswith("_")}
            felder["body"] = t.get("_body", "")
            felder["projekt"] = projekt
            felder["ref"] = ref(projekt, t.get("id"))  # SWR-087 (platform/N-0003)
            return felder
    raise ValueError(f"unbekanntes Ticket: {ticket_id} in {projekt}")


def lade_reports(root, projekt="p0"):
    """Sprint-Reports (Quelle: <projekt>/management/sprint-*/report.md), neueste zuerst."""
    muster = os.path.join(projekt_pfad(root, projekt), "management", "sprint-*", "report.md")
    reports = []
    for pfad in sorted(glob.glob(muster), reverse=True):
        sprint = os.path.basename(os.path.dirname(pfad))
        reports.append({"sprint": sprint,
                        "text": open(pfad, encoding="utf-8").read()})
    return {"reports": reports}


def parse_md_tabellen(text):
    """SWR-043/044 (P3): Markdown-Tabellen -> [{"spalten": [...], "zeilen": [[...]]}].
    Trennzeilen (|---|) werden verworfen, Fettmarker bleiben Rohtext (Frontend-Sache)."""
    tabellen, aktuelle = [], None
    for zeile in (text or "").splitlines():
        s = zeile.strip()
        if s.startswith("|") and s.endswith("|") and len(s) > 1:
            zellen = [z.strip() for z in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", z) for z in zellen):
                continue
            if aktuelle is None:
                aktuelle = {"spalten": zellen, "zeilen": []}
            else:
                aktuelle["zeilen"].append(zellen)
        else:
            if aktuelle and aktuelle["zeilen"]:
                tabellen.append(aktuelle)
            aktuelle = None
    if aktuelle and aktuelle["zeilen"]:
        tabellen.append(aktuelle)
    return tabellen


def _md_dateien(basis):
    dateien = []
    for pfad in sorted(glob.glob(os.path.join(basis, "**", "*.md"), recursive=True)):
        text = open(pfad, encoding="utf-8").read()
        dateien.append({"datei": os.path.relpath(pfad, basis).replace(os.sep, "/"),
                        "text": text, "tabellen": parse_md_tabellen(text)})
    return {"dateien": dateien}


def _requirements_eines(root, projekt):
    """Requirements-Dateien EINES Projekts, je Datei mit Herkunft (SWR-085)."""
    stufe = einstufung(root, projekt)
    dateien = _md_dateien(os.path.join(projekt_pfad(root, projekt), "requirements"))["dateien"]
    for d in dateien:
        d["projekt"] = projekt
        d["gruppe"] = stufe["gruppe"]
    return dateien


def lade_requirements(root, projekt="p0"):
    """SWR-030/043: Requirements-Markdown read-only + geparste Tabellen.

    SWR-085 (pm/N-0019): `projekt=alle` liefert die Requirements ALLER entdeckten
    Projekte und Teams in einer Antwort — jede Datei trägt ihr Projekt und dessen
    Cockpit-Gruppe, damit im HMI nach Projekt bzw. Team gefiltert werden kann.
    Vorher zeigte die Ansicht ausschließlich das oben gewählte Projekt; wer nicht
    wusste, in welchem Repo eine Anforderung liegt, fand sie nicht.
    """
    namen = projekte(root) if projekt == ALLE else [projekt]
    dateien = []
    for name in namen:
        dateien.extend(_requirements_eines(root, name))
    return {"dateien": dateien, "projekte": namen, "sammel": projekt == ALLE}


POOL_DATEI = ("pm", "management", "projekt-pool.md")


def pool_abschnitte(text):
    """SWR-086: Markdown in `##`-Abschnitte zerlegen und je Abschnitt die Tabellen
    mit dem VORHANDENEN Parser lesen — bewusst keine zweite Tabellenlogik
    (Lesson 2026-08-16: jede Kopie derselben Logik ist ein künftiger Befund)."""
    abschnitte, titel, puffer = [], "", []

    def schliessen():
        tabellen = parse_md_tabellen("\n".join(puffer))
        if tabellen:
            abschnitte.append({"titel": titel, "tabellen": tabellen})

    for zeile in (text or "").splitlines():
        if zeile.startswith("## "):
            schliessen()
            titel, puffer = zeile[3:].strip(), []
        else:
            puffer.append(zeile)
    schliessen()
    return abschnitte


def lade_pool(root):
    """SWR-086 (pm/N-0020): Projekt-Pool des PM-Teams read-only fürs HMI.

    Der Pool (pm/D005) lag bisher nur als Datei im Repo — im HMI war er nirgends
    zu sehen. Diese Ansicht zeigt die Kandidatenliste; Anlegen und Starten
    brauchen den Schreibpfad aus P10 und sind ausdrücklich NICHT Teil davon.
    """
    pfad = os.path.join(root, *POOL_DATEI)
    quelle = "/".join(POOL_DATEI)
    if not os.path.isfile(pfad):
        return {"vorhanden": False, "quelle": quelle, "text": "", "abschnitte": []}
    text = open(pfad, encoding="utf-8").read()
    return {"vorhanden": True, "quelle": quelle, "text": text,
            "abschnitte": pool_abschnitte(text)}


def lade_verifikation(root, projekt="p0"):
    """SWR-031/044: Verifikationsreports (inkl. Matrizen) + geparste Tabellen."""
    return _md_dateien(os.path.join(projekt_pfad(root, projekt), "verification"))


def cockpit(root, projekt="p0", heute=None):
    """SWR-046 (P3): alle relevanten Projektinfos auf einen Blick — Status-Zahlen,
    offene DRs mit Frist-Ampel (rot=überschritten, gelb=<=2 Tage, gruen=später,
    grau=ohne Frist), letzte Baseline, KPI-Kurzfassung."""
    heute = heute or _datum.today()
    pfad = projekt_pfad(root, projekt)
    tickets, _ = board.lade_tickets(pfad)
    status_zahlen = {}
    for t in tickets:
        status_zahlen[t.get("status", "?")] = status_zahlen.get(t.get("status", "?"), 0) + 1
    drs = []
    for t in tickets:
        if t.get("typ") != "decision-request" or t.get("status") in ("done", "rejected"):
            continue
        if "**Entscheidung (" in t.get("_body", ""):
            continue
        frist, ampel = str(t.get("frist", "") or ""), "grau"
        try:
            f = _datum.fromisoformat(frist)
            ampel = "rot" if f < heute else ("gelb" if f <= heute + _zeitspanne(days=2) else "gruen")
        except ValueError:
            pass
        drs.append({"id": t["id"], "ref": ref(projekt, t["id"]),  # SWR-087
                    "titel": t.get("titel"), "frist": frist,
                    "default": t.get("default", ""), "ampel": ampel})
    tag_text = _tags(pfad)
    tags = [z for z in tag_text.splitlines() if z.strip()]
    kpi = lade_kpi(root, projekt)
    # SWR-051 (P4): unbeantwortete Briefkasten-Nachrichten (inline, kein Zirkelimport)
    briefe_offen = 0
    brief_verz = os.path.join(pfad, "management", "briefkasten")
    if os.path.isdir(brief_verz):
        for name in os.listdir(brief_verz):
            if name.endswith(".md") and "status: offen" in open(
                    os.path.join(brief_verz, name), encoding="utf-8").read(300):
                briefe_offen += 1
    # SWR-055 (P7): Team-Kachel — letzter Digest für Team-Repos (team.yaml)
    team = None
    if os.path.isfile(os.path.join(pfad, "team.yaml")):
        dverz = os.path.join(pfad, "digest")
        digests = sorted(n for n in os.listdir(dverz)
                         if n.endswith(".md")) if os.path.isdir(dverz) else []
        team = {"letzter_digest": digests[-1][:10] if digests else ""}
    # SWR-066/068 (P9): Steckbrief, Status-Fallback über Abschluss-Baseline, Gruppe, Aufgaben
    # SWR-082: gemeinsame Einstufung mit der Navigation — eine Quelle, keine Drift.
    stufe = einstufung(root, projekt, pfad=pfad, tag_text=tag_text)
    status, gruppe = stufe["status"], stufe["gruppe"]
    offene = sorted((t for t in tickets if t.get("status") not in ("done", "rejected")),
                    key=lambda t: t.get("id", ""))
    aufgaben = [{"id": t.get("id"), "ref": ref(projekt, t.get("id")),  # SWR-087
                 "titel": t.get("titel", ""),
                 "takt": t.get("takt", "")} for t in offene[:3]]  # SWR-074
    wiederkehrend = sum(1 for t in offene if t.get("takt"))
    return {"projekt": projekt, "status_zahlen": status_zahlen,
            "tickets_gesamt": len(tickets), "offene_drs": drs,
            "letzte_baseline": tags[-1].strip() if tags else "",
            "briefe_offen": briefe_offen, "team": team,
            "beschreibung": stufe["beschreibung"], "status": status, "gruppe": gruppe,
            "aufgaben_offen": len(offene), "aufgaben": aufgaben,
            "aufgaben_wiederkehrend": wiederkehrend,  # SWR-074 (pm/N-0012)
            "kpi": {"laeufe": kpi.get("laeufe", 0),
                    "kosten_eur": kpi.get("kosten_eur_gesamt", 0.0)}}


def cockpit_alle(root, heute=None):
    """SWR-046: Cockpits aller entdeckten Projekte (eine Antwort fürs Frontend)."""
    return {"projekte": [cockpit(root, name, heute) for name in projekte(root)]}


def lade_baselines(root):
    """SWR-032: annotierte Tags (Baselines/Releases) je Repo unter der Wurzel."""
    import subprocess
    ergebnis = []
    for d in sorted(os.listdir(root)):
        if not os.path.isdir(os.path.join(root, d, ".git")):
            continue
        out = subprocess.run(["git", "-C", os.path.join(root, d), "tag", "-n1"],
                             capture_output=True, text=True)
        tags = [z.strip() for z in out.stdout.splitlines() if z.strip()]
        ergebnis.append({"repo": d, "tags": tags})
    return {"repos": ergebnis}


def lade_kpi(root, projekt="p0"):
    """Kosten/KPI aus der Run-Registry des Projekts (JSONL, append-only)."""
    pfad = os.path.join(projekt_pfad(root, projekt), "management", "runs", "run-registry.jsonl")
    laeufe = []
    if os.path.exists(pfad):
        for zeile in open(pfad, encoding="utf-8"):
            zeile = zeile.strip()
            if zeile:
                try:
                    laeufe.append(json.loads(zeile))
                except json.JSONDecodeError:
                    continue
    kosten_gesamt = round(sum(l.get("kosten_eur", 0) or 0 for l in laeufe), 4)
    je_monat, je_provider = {}, {}
    for l in laeufe:
        monat = (l.get("zeit") or "")[:7] or "unbekannt"
        je_monat[monat] = round(je_monat.get(monat, 0) + (l.get("kosten_eur", 0) or 0), 4)
        p = l.get("provider") or "unbekannt"
        je_provider[p] = je_provider.get(p, 0) + 1
    return {"laeufe": len(laeufe), "kosten_eur_gesamt": kosten_gesamt,
            "kosten_eur_je_monat": je_monat, "laeufe_je_provider": je_provider,
            "letzte": laeufe[-5:]}
