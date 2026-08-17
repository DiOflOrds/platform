"""BCK-Aggregation (SWR-022): Board, Sprint-Reports und Kosten/KPI read-only
aus der Git-Arbeitskopie lesen. Kein Cache, kein Zustand (SWR-024).
"""
import glob
import json
import os
import re
import sys
from datetime import date as _datum  # Fristarithmetik: board.frist_ampel (SWR-091)
from datetime import datetime as _zeit  # Uhrzeit-Takt: board.takt_termin (SWR-104)

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
    """SWR-066 (P9): steckbrief.yaml (beschreibung, status) + typ aus team.yaml.

    SWR-108 (platform/T-0006): dazu `profil` aus **derselben** Datei und derselben
    Schleife. Das Feld entscheidet nach Playbook Kap. 15, ob für diesen Eintrag
    überhaupt ein G4 und damit eine Baseline vorgesehen ist — `wiederkehrend` hat
    „SLA statt G4". Kein zweiter Leseweg: `process/teams/registry.yaml` ist die Quelle
    der Wahrheit, `team.yaml` ihre bewusst gehaltene lokale Kopie (Kopfkommentar der
    Registry); ein Eintrag antwortet damit über sich selbst, statt quer ins Repo
    `process` zu greifen. Beide stimmen heute für alle vier Teams überein.
    """
    info = {"beschreibung": "", "status": "", "typ": "", "profil": "", "sla_arten": []}
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
        in_sla = False
        for zeile in open(ty, encoding="utf-8"):
            z = zeile.split("#", 1)[0].strip()
            if z.startswith("typ:"):
                info["typ"] = z.split(":", 1)[1].strip().strip('"')
            elif z.startswith("profil:"):
                info["profil"] = z.split(":", 1)[1].strip().strip('"')
            elif z == "sla:":
                in_sla = True
            elif in_sla and z.startswith("- "):
                # SWR-108: die SLA-Einträge sind nach Konvention `- "<art>: <text>"`; nur
                # die Art vor dem Doppelpunkt wird gelesen, der Text ist Prosa für Menschen.
                art = z[2:].strip().strip('"').split(":", 1)[0].strip()
                if art:
                    info["sla_arten"].append(art)
            elif z:
                in_sla = False
    return info


# SWR-108 (platform/T-0006): Profile OHNE G4. Playbook Kap. 15 nennt für `wiederkehrend`
# ausdrücklich „Statt G4 gilt ein SLA je Aufgabentyp" — für einen solchen Eintrag ist eine
# Baseline nicht vorgesehen, `""` wäre dort eine Aussage, die niemand gemacht hat.
# `entwicklung` fährt G0–G4 mit „Baselines als Tags + Manifest", `dienstleistung` hat G4
# je Lieferung; beide erwarten also eine und melden `""` als echte Null.
#
# Die Unterscheidung hängt am `profil` und NICHT an der Cockpit-`gruppe`. Genau daran ist
# der erste Entwurf des Widget-Vertrags gescheitert: „Teams haben kein G4" (also
# festes-team/projekt-team) wurde von `platform` widerlegt — festes Team, aber Profil
# `entwicklung`, und es trägt eine Baseline. Die Gruppe sagt, WER etwas ist; das Profil
# sagt, WELCHE Gates gelten. Nur die zweite Frage ist hier gestellt.
PROFILE_OHNE_G4 = ("wiederkehrend",)


GRUPPEN_NAMEN = (("festes-team", "Feste Teams"), ("projekt-team", "Projekt-Teams"),
                 ("aktiv", "Aktive Projekte"), ("abgeschlossen", "Abgeschlossen"))


def _tags(pfad):
    """B065 (Gegenprüfung zu platform/T-0005): **nach Alter** sortiert, nicht nach Namen.

    `git tag` sortiert per Default nach Refname. Wer davon die letzte Zeile als „letzte
    Baseline" nimmt, bekommt die **lexikografisch** letzte: `platform` zeigte `p9-v1.0`,
    während `p10-v1.0` dreieinhalb Stunden jünger war — und `p10-v1.10` stünde vor
    `p10-v1.2`. `--sort=creatordate` ist aufsteigend, die letzte Zeile ist damit die
    jüngste; alle Aufrufer lesen weiter `[-1]`.
    """
    import subprocess
    return subprocess.run(["git", "-C", pfad, "tag", "-n1", "--sort=creatordate"],
                          capture_output=True,
                              text=True, encoding="utf-8", errors="replace").stdout


def _tagnamen(tag_text):
    """Die reinen Tag-NAMEN aus der `git tag -n1`-Ausgabe (erstes Feld je Zeile).

    Wer über den ganzen Text sucht, sucht auch in der **Annotation**: ein Tag
    `p11-v0.9` mit der Nachricht „Vorbereitung auf p11-v1.0" hätte `p11` als
    abgeschlossen ausgewiesen. Ein Name wird gegen Namen verglichen.
    """
    return {z.split(None, 1)[0] for z in tag_text.splitlines() if z.split(None, 1)}


def projekt_tags(pfad, projekt):
    """B064 (platform/T-0005): die Tag-Zeilen, die DIESEM Projekt gehören.

    `git tag` beantwortet die Frage nach dem **Repository**, nicht nach dem Ordner. Seit
    dem Monorepo-Beschluss `pm/D003` liegen Projekte ab P10 als Ordner im Sammel-Repo
    `projects` — `git -C projects/p11 tag` liefert deshalb die Tags von `projects`, also
    auch `p10-v1.0`. Das Cockpit hat davon die **letzte** Zeile als „letzte Baseline"
    dieses Projekts ausgegeben: `p11` und `p12` haben nie eine Baseline gehabt und trugen
    trotzdem die von `p10`. Keine fehlende Angabe, sondern eine falsche.

    Ein Projekt **ohne eigenes `.git`** bekommt deshalb nur die Tags, deren Name mit
    `<projekt>-` beginnt. Eigenständige Repos bleiben unberührt: ihre Tags folgen keiner
    Namenskonvention (`p0` trägt `genesis-v1.0`), und für sie stellt sich die Frage nicht.

    Dieselbe Quelle wird von den **beiden Cockpit-Lesern** (`cockpit` und `einstufung`)
    gelesen; beide gehen ab hier durch diese Funktion. Eine geteilte Quelle mit zwei
    Auflösungen war der Kern von B059 — genau das lag hier vor: `einstufung` filterte
    (über den Namen), die Baseline nicht. **Nicht** betroffen ist `lade_baselines`
    (SWR-032, `GET /api/baselines`): die Ansicht ist ausdrücklich repo-bezogen und
    beschriftet ihre Karten mit dem Repo-Namen.

    `os.path.exists` und nicht `isdir`: bei einem Submodul oder Worktree ist `.git` eine
    **Datei**, und auch dann hat der Ordner sein eigenes Tag-Verzeichnis. `projekte()`
    fragt dasselbe mit `isdir` — dort geht es um die Discovery bestehender Repos, hier um
    „antwortet `git tag` über mich oder über meinen Behälter".
    """
    text = _tags(pfad)
    if os.path.exists(os.path.join(pfad, ".git")):
        return text
    behalten = [z for z in text.splitlines()
                if z.split(None, 1) and z.split(None, 1)[0].startswith(projekt + "-")]
    return "".join(z + "\n" for z in behalten)


def einstufung(root, projekt, pfad=None, tag_text=None):
    """SWR-066/067 + SWR-082: EINE Ableitung von Beschreibung, Status und Gruppe.

    Cockpit (Kacheln) und Navigation (Kopfbereich) rufen dieselbe Funktion — genau
    deshalb können sie nicht auseinanderlaufen (pm/N-0015, T-0012). `pfad`/`tag_text`
    sind Durchreichungen für Aufrufer, die beides ohnehin schon haben.
    """
    pfad = pfad or projekt_pfad(root, projekt)
    sb = steckbrief(pfad)
    if tag_text is None:
        tag_text = projekt_tags(pfad, projekt)  # B064: nicht die Tags des Sammel-Repos
    # B064/Gegenprüfung: Namen gegen Namen. Der frühere `in tag_text` durchsuchte auch
    # die Tag-ANNOTATION — ein Tag `p11-v0.9` mit der Nachricht „Vorbereitung auf
    # p11-v1.0" hätte das Projekt als abgeschlossen ausgewiesen, ohne Baseline.
    namen = _tagnamen(tag_text)
    status = sb["status"] or ("abgeschlossen" if (f"{projekt}-v1.0" in namen or
                              (projekt == "p0" and "genesis-v1.0" in namen)) else "aktiv")
    if sb["typ"] in ("aspice", "pm"):
        gruppe = "festes-team"
    elif sb["typ"] == "projekt":
        gruppe = "projekt-team"
    else:
        gruppe = "abgeschlossen" if status == "abgeschlossen" else "aktiv"
    # SWR-108: `profil` wird durchgereicht, nicht neu gelesen — `einstufung` ist seit
    # SWR-082 die EINE Ableitung aus dem Steckbrief, und ein zweiter Leser derselben
    # Datei wäre die geteilte Quelle mit zwei Auflösungen aus B059/B064.
    return {"beschreibung": sb["beschreibung"], "status": status, "gruppe": gruppe,
            "profil": sb["profil"], "sla_arten": sb["sla_arten"]}


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
        eintrag["labels"] = board.parse_liste(t.get("labels"))  # SWR-079 (P10)
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
            felder["labels"] = board.parse_liste(t.get("labels"))  # SWR-079 (P10)
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


def cockpit(root, projekt="p0", heute=None, jetzt=None):
    """SWR-046 (P3): alle relevanten Projektinfos auf einen Blick — Status-Zahlen,
    offene DRs mit Frist-Ampel (rot=überschritten, gelb=<=2 Tage, gruen=später,
    grau=ohne Frist), letzte Baseline, KPI-Kurzfassung.

    SWR-104: **Tag und Moment sind zwei Fakten** (B057). Die Fristarithmetik rechnet
    in Tagen, der Uhrzeit-Takt in Minuten — deshalb zwei Parameter statt eines
    überladenen. Ohne Angabe: heutiger Tag und aktueller Moment. Einen Tag zum
    Moment zu machen hieße hier, `taeglich@23:00` schon morgens als fällig zu
    melden; das wäre nicht Vorsicht, sondern eine falsche Aussage.
    """
    jetzt = jetzt or (heute if isinstance(heute, _zeit) else None) or _zeit.now()
    heute = heute.date() if isinstance(heute, _zeit) else (heute or _datum.today())
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
        # SWR-091: die Ampel-Regel liegt seit pm/T-0030 in board.frist_ampel —
        # sie galt hier inline und wird jetzt von DRs und Backlog-Tickets geteilt.
        frist = str(t.get("frist", "") or "")
        ampel = board.frist_ampel(frist, heute)
        drs.append({"id": t["id"], "ref": ref(projekt, t["id"]),  # SWR-087
                    "titel": t.get("titel"), "frist": frist,
                    "default": t.get("default", ""), "ampel": ampel})
    tag_text = projekt_tags(pfad, projekt)  # B064: Tags dieses Projekts, nicht des Repos
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
    # SWR-066/068 (P9): Steckbrief, Status-Fallback über Abschluss-Baseline, Gruppe, Aufgaben
    # SWR-082: gemeinsame Einstufung mit der Navigation — eine Quelle, keine Drift.
    # SWR-108: steht jetzt VOR der Team-Kachel, weil diese `sla_arten` braucht. Die
    # Alternative wäre ein zweiter Aufruf von `steckbrief` gewesen — dieselbe Datei mit
    # zwei Lesern ist die Bauart von B059/B064 und wird hier nicht wiederholt.
    stufe = einstufung(root, projekt, pfad=pfad, tag_text=tag_text)
    status, gruppe = stufe["status"], stufe["gruppe"]
    # SWR-055 (P7): Team-Kachel — letzter Digest für Team-Repos (team.yaml)
    # SWR-108: `letzter_digest` unterscheidet jetzt zwei Fälle, die vorher beide `""`
    # waren. Die Tatsache ist die **Zusage**, nicht das Verzeichnis: nennt die SLA des
    # Teams keinen `digest`, führt das Team keine (nicht geliefert → None); nennt sie
    # einen und es liegt noch keiner vor, ist das eine echte Null → "".
    #
    # Bewusst NICHT `os.path.isdir("digest")`: das Verzeichnis entsteht erst mit dem
    # ersten Digest. Vor dem allerersten hätte die Verzeichnisregel „führt keine
    # Digests" gesagt — und genau dieser Moment ist der, für den die Unterscheidung
    # gebraucht wird. `team-mail` trägt die Zusage („digest: in jeder Session, in der
    # er fällig ist"), war aber bis zur IMAP-Einrichtung ohne Verzeichnis.
    team = None
    if os.path.isfile(os.path.join(pfad, "team.yaml")):
        if "digest" in stufe["sla_arten"]:
            dverz = os.path.join(pfad, "digest")
            digests = sorted(n for n in os.listdir(dverz)
                             if n.endswith(".md")) if os.path.isdir(dverz) else []
            team = {"letzter_digest": digests[-1][:10] if digests else ""}
        else:
            team = {"letzter_digest": None}
    offene = sorted((t for t in tickets if t.get("status") not in ("done", "rejected")),
                    key=lambda t: t.get("id", ""))
    aufgaben = [{"id": t.get("id"), "ref": ref(projekt, t.get("id")),  # SWR-087
                 "titel": t.get("titel", ""), "frist": t.get("frist", ""),  # SWR-091
                 "ampel": board.frist_ampel(t.get("frist"), heute),  # SWR-091
                 "takt": t.get("takt", "")} for t in offene[:3]]  # SWR-074
    wiederkehrend = sum(1 for t in offene if t.get("takt"))
    # SWR-091 (pm/T-0030): Überfällige Backlog-Tickets stehen eigenständig in der Kachel —
    # NICHT in `aufgaben` versteckt, das auf drei Einträge gekürzt ist. Ein Termin, der erst
    # nach dem Aufklappen einer Liste sichtbar wird, ist die Unsichtbarkeit aus B038 in neuem
    # Gewand: „Wo wird ein Fehlschlag sichtbar für jemanden, der nicht danach sucht?"
    ueberfaellig = [{"id": t.get("id"), "ref": ref(projekt, t.get("id")),
                     "titel": t.get("titel", ""), "frist": t.get("frist", ""),
                     "typ": t.get("typ", ""), "prio": t.get("prio", ""),
                     # SWR-104/B059: Der Filter daneben (`ist_ueberfaellig`) liest die Frist
                     # seit SWR-104 über `board.als_moment` und akzeptiert damit auch eine
                     # Uhrzeit. Diese Zeile parste weiter nur ein reines Datum — ein Ticket
                     # mit `frist: 2026-08-15 14:00` kam durch den Filter und ließ die
                     # Wertberechnung mit ValueError platzen, und zwar erst NACH Ablauf des
                     # Termins und für das GESAMTE Cockpit (`cockpit_alle`). Eine geteilte
                     # Regel zu erweitern heißt, ihre Nachbarn mitzuziehen.
                     "tage": (heute - board.als_moment(t["frist"]).date()).days}
                    for t in offene if board.ist_ueberfaellig(t, heute)]
    # SWR-104 (pm/T-0032): Takt-Tickets mit Uhrzeit tragen keine `frist` und sind damit für
    # `ueberfaellig` unsichtbar — ihr Termin wird abgeleitet, nicht eingetragen. Sie stehen
    # deshalb daneben, nach derselben Regel sichtbar: eigene Liste, vor den Statuszahlen.
    # Gelistet wird nach FÄLLIGKEIT, nicht nach Ampelfarbe — in der Minute des Termins ist
    # ein nie erledigtes Ticket fällig, sein Termin aber noch nicht verstrichen (B057).
    takt_faellig = [{"id": t.get("id"), "ref": ref(projekt, t.get("id")),
                     "titel": t.get("titel", ""), "takt": t.get("takt", ""),
                     "takt_klartext": board.takt_klartext(t.get("takt")),
                     "typ": t.get("typ", ""), "prio": t.get("prio", ""),
                     "zuletzt_erledigt": t.get("zuletzt_erledigt", ""),
                     "seit": board.takt_termin(t, jetzt)[0].strftime("%Y-%m-%d %H:%M"),
                     "ampel": board.takt_ampel(t, jetzt)}
                    for t in offene if board.ist_takt_faellig(t, jetzt)]
    # Ohne Frist ist ein offenes Backlog-Ticket nicht „in Ordnung", sondern unterminiert —
    # Takt-Tickets ausgenommen, die tragen ihr Zeitkonzept im Feld `takt` (SWR-074).
    unterminiert = sum(1 for t in offene
                       if not t.get("frist") and not t.get("takt")
                       and t.get("typ") != "decision-request")
    # SWR-108: „nicht geliefert" ist `None`, „echte Null" bleibt der leere Wert des Typs.
    #
    # `letzte_baseline`: ein Eintrag mit einem Profil ohne G4 (Playbook Kap. 15) bekommt
    # gar keine Baseline — dort ist `""` keine Aussage „noch keine", sondern gar keine.
    # Sobald ein Tag da IST, wird er gezeigt, auch bei solch einem Profil: die Tatsache
    # schlägt die Erwartung. Ohne diese Zeile hätte die Regel `platform` unterdrückt,
    # und genau dieser Fehler wurde am ersten Vertragsentwurf schon einmal gefunden.
    #
    # `kpi`: entscheidend ist, ob die Run-Registry EXISTIERT, nicht ob sie Zeilen hat.
    # Eine vorhandene, leere Registry meldet `{laeufe: 0}` — das ist eine Messung mit
    # dem Ergebnis null. Fehlt die Datei, wurde nichts erhoben, und 15 von 16 Einträgen
    # haben bis heute `0` gemeldet, als sei es gemessen worden (B038 in Zahlenform).
    #
    # SWR-111 (team-dashboard/T-0002): `letzte_baseline` trug TAG UND ANNOTATION in einem
    # String — bei `p1` 300 Zeichen, mehr als eine Kachelreihe fasst. Das ist nicht in
    # erster Linie ein Längen-, sondern ein B033-Problem: zwei Tatsachen unter einem Namen.
    # Getrennt wird HIER, wo `git tag -n1` sie ohnehin durch Leerraum getrennt liefert —
    # nicht im Vertrag und nicht im Widget (ADR-P11-001 Punkt 3: eine Kürzungsregel im
    # JavaScript sucht niemand, und Cockpit und Dashboard sagten dann Verschiedenes).
    # Die drei Zustände aus SWR-108 gelten für BEIDE Felder und dürfen nicht auseinander-
    # laufen: kein Tag -> beide `None` bzw. beide `""`; Tag ohne Annotation -> Name und
    # `""`, denn die Annotation ist dann eine echte Leere und keine fehlende Erhebung.
    if tags:
        teile = tags[-1].strip().split(None, 1)
        letzte_baseline = teile[0]
        letzte_baseline_text = teile[1].strip() if len(teile) > 1 else ""
    elif stufe["profil"] in PROFILE_OHNE_G4:
        letzte_baseline = letzte_baseline_text = None
    else:
        letzte_baseline = letzte_baseline_text = ""
    return {"projekt": projekt, "status_zahlen": status_zahlen,
            "tickets_gesamt": len(tickets), "offene_drs": drs,
            "letzte_baseline": letzte_baseline,
            "letzte_baseline_text": letzte_baseline_text,  # SWR-111
            "briefe_offen": briefe_offen, "team": team,
            "beschreibung": stufe["beschreibung"], "status": status, "gruppe": gruppe,
            "aufgaben_offen": len(offene), "aufgaben": aufgaben,
            "aufgaben_wiederkehrend": wiederkehrend,  # SWR-074 (pm/N-0012)
            "ueberfaellig": ueberfaellig,  # SWR-091 (pm/T-0030, Brief pm/N-0025)
            "takt_faellig": takt_faellig,  # SWR-104 (pm/T-0032, Brief pm/N-0025)
            "unterminiert": unterminiert,  # SWR-091
            "kpi": ({"laeufe": kpi.get("laeufe", 0),
                     "kosten_eur": kpi.get("kosten_eur_gesamt", 0.0)}
                    if kpi.get("registry_vorhanden") else None)}  # SWR-108


def unterminierte_tickets(root):
    """SWR-117 (pm/T-0047): offene Tickets ohne Frist — org-weit, MIT Referenzen.

    **Die eine Quelle.** Diese Funktion stand bis Sprint 9 in `scripts/preflight.py`
    (SWR-114, pm/T-0036 Teil b). `pm/T-0047` will dieselbe Tatsache ein zweites Mal
    anzeigen — im Cockpit-Kopfblock — und genau dort entsteht B033: zwei Stellen,
    die dieselbe Frage aus zwei Quellen beantworten und auseinanderlaufen können.

    **Warum sie hierher wandert und nicht umgekehrt.** `backend` importiert bereits
    `scripts.board` (siehe Kopf dieser Datei). Der umgekehrte Weg — `aggregation`
    importiert aus `preflight` — schlösse einen Zyklus. Die Richtung ist damit keine
    Geschmacksfrage. `preflight.unterminierte_tickets` bleibt als **Weiterleitung**
    stehen: sie ist keine zweite Quelle, sondern der Beleg, dass es nur eine gibt,
    und sie hält die vorhandenen SWR-114-Tests auf dem ausgelieferten Pfad.

    **Die Abgrenzung ist die von SWR-091**, damit Kachelzahl und Org-Summe nicht
    verschieden zählen: Takt-Tickets tragen ihr Zeitkonzept im Feld `takt`, ein
    `decision-request` wird über `frist` + `default` gesteuert.
    """
    treffer = []
    for name, basis in board.projekt_pfade(root):
        verz = os.path.join(basis, "tickets")
        if not os.path.isdir(verz):
            continue
        for datei in sorted(os.listdir(verz)):
            if not datei.endswith(".md"):
                continue
            try:
                with open(os.path.join(verz, datei), encoding="utf-8") as f:
                    fm, _ = board.parse_frontmatter(f.read())
            except OSError:
                continue
            fm = fm or {}
            if fm.get("status") in ("done", "rejected"):
                continue
            if fm.get("frist") or fm.get("takt") or fm.get("typ") == "decision-request":
                continue
            treffer.append(ref(name, fm.get("id") or datei[:-3]))
    return treffer


def wartet_auf_mensch(root):
    """SWR-120 (pm/T-0051): offene Tickets, bei denen der MENSCH am Zug ist — mit Refs.

    **Zwei Quellen, eine Frage — und das ist hier kein B033.** Ein Ticket wartet auf
    den Menschen, wenn es `verantwortlich: mensch` trägt (SWR-116) **oder** wenn es ein
    `decision-request` ist. Das zweite ist keine zweite Meinung über dasselbe, sondern
    ein anderer Sachverhalt: ein DR liegt qua Typ beim Auftraggeber, auch ohne dass
    jemand das Feld gesetzt hätte. Beide zusammen sind die vollständige Antwort auf die
    Frage „liegt es bei uns oder bei dir?" — und die Vereinigung wird **hier** gebildet
    und nicht in zwei Anzeigen, die dann verschieden zählen.

    **Mit Referenzen, nicht nur der Zahl** (B038): ein Zähler, der „3" sagt, sagt nicht,
    welche drei. SWR-114 hat dieselbe Entscheidung für „unterminiert" getroffen und ist
    die Vorlage; `pm/T-0051` verlangt sie ausdrücklich.

    **Geschlossene Tickets zählen nicht.** Ein entschiedener DR wartet auf niemanden.
    """
    treffer = []
    for name, basis in board.projekt_pfade(root):
        verz = os.path.join(basis, "tickets")
        if not os.path.isdir(verz):
            continue
        for datei in sorted(os.listdir(verz)):
            if not datei.endswith(".md"):
                continue
            try:
                with open(os.path.join(verz, datei), encoding="utf-8") as f:
                    fm, _ = board.parse_frontmatter(f.read())
            except OSError:
                continue
            fm = fm or {}
            if fm.get("status") in ("done", "rejected"):
                continue
            # Die Bedingung steht in `board.wartet_auf_mensch` und NICHT hier: die
            # Board-Spalte (SWR-119) stellt dieselbe Frage, und zwei Formulierungen
            # derselben Bedingung sind zwei Antworten in Wartestellung (B033).
            if board.wartet_auf_mensch(fm):
                treffer.append(ref(name, fm.get("id") or datei[:-3]))
    return treffer


def organisation(root):
    """SWR-117 (pm/T-0047): der Kopfblock — Aussagen über die ORGANISATION, nicht über
    ein Projekt.

    **Warum ein eigener Block und keine Umhüllung von `projekte`.** Jeder heutige Leser
    — HMI, Widget, die beiden Übereinstimmungstests — greift auf `payload["projekte"]`
    zu. Eine Umhüllung änderte die Antwort für **alle** von ihnen, um eine Zahl zu
    liefern, die **keinen** von ihnen betrifft. Ein zusätzlicher Schlüssel ist eine
    Vertrags**erweiterung**, eine umgeformte Hülle eine Vertrags**änderung** — und nur
    die zweite braucht die Abstimmung, die dieses Ticket zweimal verschoben hat.

    **Verhalten bei 0.** Der Block ist immer da, mit `0` und `[]` — nie `None`, nie
    weggelassen. Die Messung läuft bei jedem Aufruf, die Null ist also eine **echte
    Null** im Sinne von SWR-108 (der leere Wert des Typs) und keine ausgebliebene
    Erhebung. Und nach der Begründung von SWR-114 ist ein stiller Check von einem nicht
    gelaufenen nicht zu unterscheiden.

    **Erweiterbar um einen zweiten Schlüssel** (der Zähler aus `pm/T-0051`), ohne dass
    ein Leser sich ändert — das ist es, was die zweite Zahl zu einer Ergänzung in eine
    feststehende Form macht statt zu einer zweiten Vertragsfrage.
    """
    refs = unterminierte_tickets(root)
    wartend = wartet_auf_mensch(root)  # SWR-120 (pm/T-0051)
    return {"unterminiert_gesamt": len(refs), "unterminiert_refs": refs,
            "wartet_auf_mensch_gesamt": len(wartend),
            "wartet_auf_mensch_refs": wartend}


def cockpit_alle(root, heute=None, jetzt=None):
    """SWR-046: Cockpits aller entdeckten Projekte (eine Antwort fürs Frontend).

    SWR-117: dazu der Org-Kopfblock als **Schwesterschlüssel** neben `projekte` —
    `projekte` bleibt in Form und Reihenfolge unangetastet.
    """
    return {"projekte": [cockpit(root, name, heute, jetzt) for name in projekte(root)],
            "organisation": organisation(root)}  # SWR-117 (pm/T-0047)


def lade_baselines(root):
    """SWR-032: annotierte Tags (Baselines/Releases) je Repo unter der Wurzel."""
    import subprocess
    ergebnis = []
    for d in sorted(os.listdir(root)):
        if not os.path.isdir(os.path.join(root, d, ".git")):
            continue
        out = subprocess.run(["git", "-C", os.path.join(root, d), "tag", "-n1"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        tags = [z.strip() for z in out.stdout.splitlines() if z.strip()]
        ergebnis.append({"repo": d, "tags": tags})
    return {"repos": ergebnis}


def lade_kpi(root, projekt="p0"):
    """Kosten/KPI aus der Run-Registry des Projekts (JSONL, append-only).

    SWR-108 (platform/T-0006): `registry_vorhanden` meldet, ob es die Datei überhaupt
    gibt. Das ist **keine** zweite Angabe neben `laeufe` (das wäre B033), sondern die
    einzige Tatsache, die `laeufe: 0` deuten lässt: ohne Registry ist die Null nicht
    gemessen, sondern nie erhoben. Die Zahlen selbst bleiben unverändert — wer die
    Registry hat und keine Läufe, bekommt weiterhin 0.
    """
    pfad = os.path.join(projekt_pfad(root, projekt), "management", "runs", "run-registry.jsonl")
    laeufe = []
    vorhanden = os.path.exists(pfad)
    if vorhanden:
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
            "letzte": laeufe[-5:], "registry_vorhanden": vorhanden}  # SWR-108
