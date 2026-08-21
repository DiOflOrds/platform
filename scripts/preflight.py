#!/usr/bin/env python3
"""Session-/Tick-Preflight (p0/T-0024, Retro-CR 1/3 aus Sprint 2).

Ein Lauf je Session-/Tick-Start:
  1. Verwaiste Git-Lock-Artefakte erkennen (index.lock, HEAD.lock,
     objects/maintenance.lock, objects/**/tmp_obj_*, refs/**/*.lock) und
     entfernen — aber NUR, wenn kein Git-Prozess läuft. Schlägt das
     Löschen fehl (Mount ohne unlink-Recht, R7), wird das Artefakt nach
     .git/verwaiste-locks/ weggeräumt (pm/T-0023) — Git ist damit entsperrt.
     Erst wenn auch das scheitert, folgt die Handlungsanweisung an den Menschen.
  2. Arbeitskopie-Status je Repo (dirty-Dateien, ahead/behind origin).
  3. Board-Validierung (board.py --check im Projekt-Repo).
  4. Unit-Tests (platform/tests) — für Ticks per --skip-tests abwählbar.

Exit 0 = startklar; Exit 1 = mindestens ein Befund.
Erwartungswert (p0/T-0024): 0 Analyse-Blöcke durch Mount-Artefakte je Sprint.
"""
import argparse
import glob
import os
import platform as _platform
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import board  # noqa: E402  — gemeinsame Projekt-Discovery (SWR-070, p9/T-0007)
import konsole  # noqa: E402  — Kodierung an beiden Enden eines Laufs (platform/T-0009)
import js_tests  # noqa: E402  — JS-Teststrecke (SWR-128, ADR-008)
import sprint_register  # noqa: E402  — Sprintzaehler mit Ende (SWR-136, platform/T-0013)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import organisation  # noqa: E402  — SWR-170: der eine Leser von besetzungen.yaml

REPOS = ["process", "platform", "p0"]


def repos_im_root(root):
    """REPOS + weitere Git-Repos im Root, z.B. Produkt-Repos (T-0050).

    Bewusst ohne Lock-Altersgrenze: verwaiste Locks entstehen hier session-bedingt
    frisch — der Git-Prozess-Check genügt als Schutz (Retro Sprint 4)."""
    namen = list(REPOS)
    try:
        for d in sorted(os.listdir(root)):
            if d not in namen and os.path.isdir(os.path.join(root, d, ".git")):
                namen.append(d)
    except OSError:
        pass
    return namen


def git_prozess_aktiv():
    """True, wenn auf diesem Gerät gerade ein Git-Prozess läuft (plattformübergreifend).

    `errors="replace"` ist kein Schönheitsfehler-Ausgleich, sondern der Fix zu pm/T-0024:
    `tasklist` antwortet in der OEM-Konsolen-Codepage (850/437), Python decodierte mit
    `text=True` per Default in cp1252. Ein einziges Byte 0x81 (in CP850 das 'ü' aus
    „ausgeführt") ließ den Reader-Thread von subprocess mit UnicodeDecodeError sterben.
    Der Fehler landete unten im `except` und kam als „Git-Prozess aktiv" heraus — die
    Lock-Räumung unterblieb, obwohl gar kein Git lief. Der Prozessname selbst ist ASCII,
    für die Entscheidung geht durch das Ersetzen also nichts verloren.
    """
    try:
        if _platform.system() == "Windows":
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq git.exe"],
                                 capture_output=True, text=True, encoding="utf-8", timeout=10,
                                 errors="replace")
            return "git.exe" in out.stdout
        out = subprocess.run(["pgrep", "-x", "git"], capture_output=True, text=True,
                             encoding="utf-8", timeout=10, errors="replace")
        return out.returncode == 0
    except Exception as fehler:
        # Im Zweifel nichts löschen — aber nicht schweigend. Ein stiller Fallback auf
        # „aktiv" sieht im Protokoll aus wie eine korrekte Beobachtung und kostete drei
        # Auto-Push-Läufe, bis jemand nachsah (pm/T-0024).
        print(f"    [hinweis] Prozess-Abfrage nicht auswertbar "
              f'({type(fehler).__name__}: {fehler}) — vorsichtshalber als „Git läuft“ '
              f"gewertet, es wird nichts entfernt.")
        return True


def finde_lock_artefakte(repo):
    """Bekannte Git-Lock-/Temp-Artefakte im Repo finden (Liste von Pfaden)."""
    g = os.path.join(repo, ".git")
    muster = [
        os.path.join(g, "*.lock"),
        os.path.join(g, "objects", "maintenance.lock"),
        os.path.join(g, "objects", "*", "tmp_obj_*"),
        os.path.join(g, "refs", "**", "*.lock"),
    ]
    funde = []
    for m in muster:
        funde.extend(glob.glob(m, recursive=True))
    return sorted(set(funde))


PARKPLATZ = "verwaiste-locks"


def _parke(pfad, repo_git, stempel):
    """Artefakt nach .git/verwaiste-locks/ wegbenennen. Rückgabe: Zielpfad."""
    ziel_dir = os.path.join(repo_git, PARKPLATZ)
    os.makedirs(ziel_dir, exist_ok=True)
    # Name eindeutig halten: Unterordner-Anteil mit einfließen lassen (refs/heads/main.lock)
    rel = os.path.relpath(pfad, repo_git).replace(os.sep, "_")
    ziel = os.path.join(ziel_dir, f"{rel}.{stempel}")
    n = 0
    while os.path.exists(ziel):
        n += 1
        ziel = os.path.join(ziel_dir, f"{rel}.{stempel}-{n}")
    os.rename(pfad, ziel)
    return ziel


def entferne_artefakte(pfade):
    """Artefakte beseitigen. Rückgabe: (entfernt, geparkt, fehlgeschlagen) als Pfadlisten.

    Zweistufig (Lehre 2026-08-16, pm/T-0023): Erst löschen. Wo der Mount kein
    unlink erlaubt — Cowork-Session auf dem Windows-Ordner, Störung R7 — wird das
    Artefakt stattdessen nach .git/verwaiste-locks/ WEGBENANNT. Für Git ist der
    Lock damit ebenso weg (es prüft ausschließlich den exakten Namen), und die
    Session kann committen, statt ihre gesamte Arbeit unverbucht zu verlieren.
    Umbenennen ist auf diesen Mounts erlaubt, Löschen nicht.
    """
    entfernt, geparkt, fehlgeschlagen = [], [], []
    stempel = time.strftime("%Y%m%dT%H%M%S")
    for p in pfade:
        try:
            os.remove(p)
            entfernt.append(p)
            continue
        except OSError:
            pass
        # .git-Verzeichnis aus dem Fundpfad ableiten (Artefakte liegen immer darunter)
        teile = os.path.abspath(p).split(os.sep)
        try:
            repo_git = os.sep.join(teile[:len(teile) - 1 - teile[::-1].index(".git")] + [".git"])
            _parke(p, repo_git, stempel)
            geparkt.append(p)
        except (OSError, ValueError):
            fehlgeschlagen.append(p)
    return entfernt, geparkt, fehlgeschlagen


def index_gesperrt(repo):
    """True, wenn `.git/index.lock` liegt — der reale Index kann dann nicht auffrischen.

    Bewusst eine reine `stat()`-Frage und ausdrücklich **keine** zweite Messung:
    ein Vergleich „realer Index vs. Baum" würde den plain-`git status` je Repo
    zusätzlich kosten (gemessen: 6,8 s über 17 Repos), um eine Auskunft zu erzeugen,
    die nichts entscheidet.

    ⚠ **Grenze, benannt statt verschwiegen:** ein veralteter Index OHNE Sperre wird
    hiervon nicht erkannt. Das ist hinnehmbar, weil er sich beim nächsten Git-Aufruf
    von allein auffrischt — die Sperre ist genau der Fall, in dem er das nicht kann.
    """
    return os.path.exists(os.path.join(repo, ".git", "index.lock"))


def repo_status(repo):
    """(dirty_zeilen, tracking_zeile) aus `git status --porcelain -b` — gegen den BAUM.

    `-uall` (SWR-110): ohne diese Option fasst git einen nicht getrackten Ordner zu
    EINER Zeile `?? tickets/` zusammen. Ein neu angelegtes Ticket in einem neuen
    Ordner wäre damit unsichtbar — genau der Fall, in dem eine Datei nur in der
    Arbeitskopie existiert. Ein Test hat das gefunden (platform/T-0010).

    ⚠⚠ **SWR-191 (platform/T-0046): der Vergleich läuft gegen einen aus HEAD frisch
    geseedeten Index und nicht gegen den realen.** Der reale Index ist ein
    Zwischenspeicher; die Arbeit ist der Baum. Liegt ein `.git/index.lock`, das auf
    diesem Mount nicht entfernbar ist (`SWR-163/164`, R7), friert der reale Index auf
    dem Stand **vor** dem letzten Commit ein — `git status` meldet dann `MM` für
    Dateien, die mit HEAD byte-identisch sind.

    > **Gemessen am Ende von Sprint 28: 2 Befunde („3 Dateien in `platform`", „1 Datei
    > in `pm`") über Arbeit, die vollständig committet war. Ein falscher Befund ist
    > teurer als kein Befund, weil er dieselbe Wirkung hat wie ein echter — er bricht
    > jeden Tick ab — und keine Handlung kennt, die ihn abstellt. Genau diese Bauart
    > hat `SWR-166` gekostet: 83 abgebrochene Auto-Pushes, 12 nie gelaufene Ticks.**

    ⚠ **Preis, gemessen und nicht geschätzt:** ein `read-tree` je Repo kostet über die
    17 Repos dieses Hauses **+7,6 s** (14,4 s statt 6,8 s). Das ist der Preis dafür,
    dass der Befund die Arbeit misst und nicht den Zwischenspeicher.

    ⚠ Der Temp-Index liegt **außerhalb** des Repos. Er im Repo abzulegen hieße, dem
    Parkplatz bei jedem Preflight-Lauf ein weiteres nicht löschbares Artefakt
    beizulegen — die Reparatur würde die Ursache füttern.

    Fällt das Seeding aus (Repo ohne Commit, `read-tree` scheitert), fällt die Messung
    auf den realen Index zurück: eine Auskunft aus dem Zwischenspeicher ist besser als
    keine, und der Rückfall ist an dieser einen Stelle benannt.
    """
    umgebung, temp = None, None
    try:
        fd, temp = tempfile.mkstemp(prefix="preflight-index-")
        os.close(fd)
        os.remove(temp)  # read-tree legt die Datei selbst an; ein leerer Index wäre falsch
        seed = subprocess.run(["git", "-C", repo, "read-tree", "HEAD"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=dict(os.environ, GIT_INDEX_FILE=temp))
        if seed.returncode == 0 and os.path.exists(temp):
            umgebung = dict(os.environ, GIT_INDEX_FILE=temp)
    except OSError:
        umgebung = None
    try:
        out = subprocess.run(["git", "-C", repo, "status", "--porcelain", "-uall", "-b"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", env=umgebung)
    finally:
        for p in ([temp, temp + ".lock"] if temp else []):
            try:
                os.remove(p)
            except OSError:
                pass
    zeilen = out.stdout.splitlines()
    tracking = zeilen[0] if zeilen else ""
    return [z for z in zeilen[1:] if z.strip()], tracking


# --- SWR-110: Gemessenes gegen Geliefertes -------------------------------------
# trace_matrix und board lesen die ARBEITSKOPIE, `abschluss.cmd [4/5]` pusht HEAD.
# Wo beide in einer Datei auseinandergehen, die eine Verifikation liest, beschreibt
# das grüne Ergebnis einen Zustand, den kein Repository trägt (platform/T-0010:
# Sprint 6 meldete "109 SWRs / 0 Lücken", während SWR-109 nur auf der Platte stand).

def _pfad_aus_statuszeile(zeile):
    """Dateipfad aus einer `git status --porcelain`-Zeile (XY<space>pfad).

    Rename/Copy melden `alt -> neu`; gemeint ist das Ziel. Anführungszeichen setzt
    git bei Sonderzeichen im Namen."""
    pfad = zeile[3:].strip() if len(zeile) > 3 else ""
    if " -> " in pfad:
        pfad = pfad.split(" -> ", 1)[1]
    return pfad.strip('"')


def ist_verifikationsquelle(pfad):
    """Liest eine Verifikation diese Datei?

    Drei Sorten, jede mit einem benennbaren Leser:
      * Anforderungsdokument -> trace_matrix.py (SWR-Bestand und Status)
      * Ticketdatei          -> board.py --check (Validierung, BOARD.md)
      * BOARD.md             -> der CI-Schritt "BOARD.md aktuell?" jedes Projekt-Repos
    BOARD.md steht bewusst mit in der Liste: sie ist der Grund, aus dem es die
    Stand-Zeilen-Ausnahme überhaupt gibt (platform/T-0010)."""
    p = pfad.replace("\\", "/")
    teile = p.split("/")
    if teile[-1] == "BOARD.md":
        return True
    if teile[-1] == "software-requirements.md":
        return "requirements" in teile[:-1] or len(teile) == 1
    return len(teile) >= 2 and teile[-2] == "tickets" and p.endswith(".md")


def nur_stand_zeile(repo, pfad):
    """True, wenn die Änderung an dieser Datei AUSSCHLIESSLICH die `Stand:`-Zeile ist.

    Am tatsächlichen Diff entschieden und nicht am Dateinamen (DoD 3/4 von
    platform/T-0010): `board.py` erzeugt die Stand-Zeile bei jedem Lauf neu, also
    sind fünf Repos jeden Tag unsauber. Eine Ausnahme nach Dateiname würde eine
    BOARD.md mit echter Inhaltsänderung mit durchlassen."""
    out = subprocess.run(["git", "-C", repo, "diff", "--unified=0", "--", pfad],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0 or not out.stdout.strip():
        return False  # nicht getrackt oder nicht lesbar -> keine Ausnahme
    geaendert = [z for z in out.stdout.splitlines()
                 if (z.startswith("+") or z.startswith("-"))
                 and not z.startswith(("+++", "---"))]
    if not geaendert:
        return False
    return all(z[1:].lstrip().startswith("Stand:") for z in geaendert)


_SPRINTSICHT_CACHE = {}


def sprintsicht(root, frisch=False):
    """SWR-122 (platform/T-0011): die Sprintsicht **einmal** laden, oder `None`.

    Drei Preflight-Zeilen (`status_drift`, `plan_drift`, `sprint_vergangen`) beantworten
    drei verschiedene Fragen an **denselben** Bestand. Sie dreimal zu berechnen wäre
    nicht nur teuer, sondern die Bauart aus B033: drei Aufrufe, die zu verschiedenen
    Zeitpunkten laufen, können verschiedene Antworten geben, und niemand würde es merken.
    Deshalb genau ein Aufruf je Preflight-Lauf.

    `None` heißt „konnte nicht prüfen" und ausdrücklich **nicht** „nichts gefunden".
    """
    if not frisch and root in _SPRINTSICHT_CACHE:
        return _SPRINTSICHT_CACHE[root]
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from backend import sprint as _sprint
        sicht = _sprint.plan(root)
    except Exception:
        sicht = None
    _SPRINTSICHT_CACHE[root] = sicht
    return sicht


def pause_zum_vorlauf(root):
    """SWR-156 (platform/T-0025): die Pause seit dem letzten Sprintende, oder `None`.

    ⚠ **Kein eigener Rechenweg.** Die Antwort steht in `backend.session`, weil dort
    schon `stille()` wohnt — die Zeitregel, an der die Kachel „Letzte Session" seit
    SWR-102 hängt. Zwei Rechnungen über dieselbe Stille wären B033.

    ⚠ Warum die Funktion in `backend.session` liegt und nicht in `sprint_register`:
    `session` importiert `sprint_register` bereits (SWR-153). Die Gegenrichtung wäre ein
    Importzyklus — und die einzige Alternative dazu wäre gewesen, `stille()`
    abzuschreiben, was die DoD dieses Tickets ausdrücklich verbietet.

    `None` heißt „konnte nicht prüfen" und **nicht** „keine Pause".
    """
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from backend import session as _session
        return _session.pause_seit_letztem_lauf(root)
    except Exception:
        return None


#: SWR-161 (platform/T-0022 Frage 2/3): Pflichtartefakte, die `pool._projekt_dateien_schreiben`
#: bei der Gründung anlegt und die ein Repo braucht, das DRs führen kann (Playbook Kap. 16).
#:
#: ⚠ **Diese Liste ist kurz, und das ist das Ergebnis der Zählung und keine Bescheidenheit.**
#: Gemessen über alle 17 entdeckten Projekte und Teams fehlt von den sechs Artefakten des
#: Gründungswegs (`README.md`, `steckbrief.yaml`, `BOARD.md`, `tickets/`,
#: `docs/01-projektauftrag.md`, `management/decisions/decision-log.md`) nur **eines** an
#: mehr als einer Stelle. Vier fehlen **nirgends**.
#:
#: ⚠⚠ `docs/01-projektauftrag.md` steht bewusst NICHT hier. Es fehlt in 6 von 17 Repos —
#: aber fünf davon führen stattdessen `01-team-charter.md`, `01-rollenbeschreibung.md` oder
#: `02-initialprojekt-p0.md`. Eine Prüfung müsste **raten**, welcher Name in welchem Repo
#: der richtige ist; das wäre B038, und ein Befund, der auf fünf richtige Fälle zeigt,
#: trainiert das Wegsehen (SWR-109/110/112). Der eine echte Fall (`platform` hat weder das
#: eine noch das andere) ist eine **Frage an das PM** und keine Prüfung.
PFLICHTARTEFAKTE = [os.path.join("management", "decisions", "decision-log.md")]


def fehlende_pflichtartefakte(root):
    """SWR-161: Repos, denen ein Pflichtartefakt des Gründungswegs fehlt.

    ⚠⚠ **Warum es diese Prüfung NEBEN dem selbstheilenden Weg gibt.** SWR-152 legt das
    Entscheidungslog an, wenn es beim Verbuchen fehlt — richtig, denn *eine getroffene
    Entscheidung, die am Ablageort scheitert, ist verloren, sobald das Fenster zu ist.*
    Aber:

    > **Der selbstheilende Weg rettet die eine Entscheidung, die gerade getroffen wird.
    > Den Mangel, in den noch niemand hineingelaufen ist, kann er nicht finden — das kann
    > nur eine Prüfung, die alle Repos durchgeht.**

    Das ist keine Überlegung, sondern gemessen: der Vorfall vom 17.08. betraf
    `promt-team`; dort ist das Log seither da, **weil jemand hineingelaufen ist**. In
    `platform` und `produkt-datakonv` fehlt es unverändert, und `produkt-datakonv` stand
    in keinem Ticket — die Zählung hat es gefunden, nicht der Vorfall.

    Rückgabe: `[(repo, artefakt), ...]`, leer = geprüft und vollständig.
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import board as _board
        fehlend = []
        for name, basis in _board.projekt_pfade(root):
            for artefakt in PFLICHTARTEFAKTE:
                if not os.path.exists(os.path.join(basis, artefakt)):
                    fehlend.append((name, artefakt.replace(os.sep, "/")))
        return fehlend
    except Exception:
        return None


def uhrenprobe_register(root):
    """SWR-159 (platform/T-0026): Registerzeiten, die in der Zukunft ihres Commits liegen.

    ⚠ **Kein eigener Rechenweg** — dieselbe Auflage wie bei `pause_zum_vorlauf`. Die
    Zeitregel steht in `sprint_register`, weil dort `_wanduhr()` wohnt; sie hier
    nachzubauen wäre eine zweite Zeitrechnung über denselben Sachverhalt (B033) — genau
    der Befund, aus dem `platform/T-0026` entstanden ist.

    ⚠⚠ **Und das Material holt ausdrücklich ein DRITTES Modul.** `sprint_register` darf
    nach SWR-134/136 kein git aufrufen (lesende Aufrufe hinterlassen auf diesem Mount
    Sperren); `uebergang_historie` liest ohnehin Historie. Diese Funktion ist die Naht:
    sie fügt Material und Regel zusammen und rechnet selbst nichts.

    `None` heißt „konnte nicht prüfen" und **nicht** „keine Treffer".
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import sprint_register
        import uebergang_historie
        pm = os.path.join(root, "pm")
        zeilen = uebergang_historie.zugefuegte_zeilen(
            pm, os.path.join("management", "sprints.jsonl"))
        return sprint_register.uhrenprobe(zeilen)
    except Exception:
        return None


def statusdrift(root):
    """SWR-115 (pm/T-0049): Planzeilen, deren Statusspalte dem Ticket widerspricht.

    Rückgabe `None`, wenn die Sprintsicht nicht ladbar ist — ausdrücklich **nicht** eine
    leere Liste. „Konnte nicht prüfen" und „nichts gefunden" sind zwei Aussagen, und die
    zweite an der Stelle der ersten ist genau die Sorte stiller Erfolgsmeldung, die dieses
    Ticket ausgelöst hat.
    """
    sicht = sprintsicht(root)
    return None if sicht is None else sicht.get("status_drift", [])


def plannachlauf(root):
    """SWR-201 (platform/T-0052): die Planzeilen, die der LAUFENDE Sprint garantiert erzeugt.

    Gelesen wird derselbe Schlüssel, den `sprint.plan` gefüllt hat — hier wird **nicht**
    ein zweites Mal klassifiziert. Die Trennung steht in `sprint.plan_nachlauf` und
    nirgends sonst; eine zweite Bedingung an dieser Stelle wäre B033 mit einer
    **Begründung** als Kopie, und genau daran ist `SWR-166` 83 Läufe lang gescheitert.

    ⚠⚠ **`None` heißt „konnte nicht prüfen" und deckt AUCH den fehlenden Schlüssel ab.**
    Der erste Entwurf schrieb `sicht.get("plan_nachlauf", [])` — und damit hätte ein
    Ausbau der Verdrahtung in `sprint.plan` eine **leere Liste** ergeben, also die stille
    Erfolgsmeldung, gegen die `statusdrift` oben ausdrücklich argumentiert. Das Review
    dieses Sprints hat es am Bestand vorgeführt: Aufruf und Payload-Schlüssel entfernt,
    alle sechs Zusicherungen blieben grün und der Preflight meldete „0".

    > **Ein Vorgabewert verwandelt eine fehlende Antwort in eine beruhigende.**
    """
    sicht = sprintsicht(root)
    if sicht is None or "plan_nachlauf" not in sicht:
        return None
    return sicht["plan_nachlauf"]


def plandrift(root):
    """SWR-122 (platform/T-0011): Planzeilen, die eine ANDERE Sprintnummer nennen als ihr Ticket.

    Die Kennzahl gibt es seit SWR-109 und sie stand bis heute in keiner Meldung: sie
    wurde von `sprint.plan()` berechnet, in den Payload gelegt und von niemandem gelesen —
    einen Schlüssel neben `status_drift`, das der Preflight liest.

    **Warum sie hierher gehört, steht in SWR-115.** Deren eigene Begründung („sichtbar
    *vor* dem Push und vor dem Bericht an den Auftraggeber, statt einen Sprint später")
    gilt für diesen Nachbarn wörtlich. Am Bestand belegt: der Abschlussbericht von
    Sprint 9 meldete an drei Stellen „Plan-Drift 0", während der Lauf selbst drei Drifts
    hinterließ — die Null war richtig, als sie gemessen wurde, und falsch, als sie
    berichtet wurde. **Eine Messung vor der Änderung, die sie abdecken soll, misst den
    Ausgangszustand.**

    `None` heißt „konnte nicht prüfen" und nicht „nichts gefunden".
    """
    sicht = sprintsicht(root)
    return None if sicht is None else sicht.get("plan_drift", [])


def liegengeblieben_in_arbeit(root):
    """SWR-155 (pm/T-0069, Brief pm/N-0043 Punkt 4): Aufgaben, die auf `in_progress`
    stehen, **ohne dass ein Sprint läuft** — also angefangen und liegengeblieben.

    Der Auftraggeber hat es so formuliert: *„Wenn Sprint vorbei ist, muss ein anderer
    Status drin stehen."*

    ⚠⚠ **Warum diese Prüfung erst seit heute etwas findet.** Bis Sprint 20 wurde
    `in_progress` **kurz vor dem Fertigmelden** gesetzt, nicht beim Anfangen — gemessen
    über die Historie: Median-Aufenthalt **22 Sekunden**, und **159 von 300**
    geschlossenen Aufgaben hatten ihn nie. Eine Prüfung auf einen Zustand, der 22
    Sekunden existiert, ist immer grün und prüft nichts. Erst Stufe 1 von `pm/T-0069`
    (Status beim **Anfangen** setzen) macht sie scharf. Die Reihenfolge der beiden
    Stufen ist deshalb keine Bequemlichkeit.

    ⚠ **Nie still.** Läuft gerade ein Sprint, ist `in_progress` der **richtige**
    Zustand — dann wird die Zahl trotzdem genannt, nur nicht als Befund gewertet. Ein
    Ergebnis zu unterdrücken, weil es gerade unverdächtig ist, macht eine gelaufene
    Prüfung von einer nicht gelaufenen ununterscheidbar (SWR-114, SWR-117, SWR-154).

    ⚠ **Melden, nicht aufräumen.** Ein Skript, das den Status zurückstellt, macht das
    Liegenbleiben unsichtbar; der andere Status entsteht durch eine Entscheidung des PM
    (fertig / mit Grund verschoben / blockiert). Dieselbe Kehrseite hält
    `platform/T-0022` Frage 3 offen.

    Rückgabe: `(liste, sprint_laeuft)`; `None` heißt „konnte nicht prüfen".
    """
    sicht = sprintsicht(root)
    if sicht is None:
        return None
    # Kein zweiter Erhebungsweg: dieselbe Liste, aus der die Sprintsicht `offen_gesamt`
    # zählt (B033) — die Zahl hier und die Zahl dort können nicht auseinanderlaufen.
    treffer = [o for o in sicht.get("offene", []) if o.get("status") == "in_progress"]
    try:
        laeuft = sprint_register.laufender(root) is not None
    except Exception:
        laeuft = False
    return treffer, laeuft


def sprintvergangen(root):
    """SWR-122 (platform/T-0011): offene Tickets, deren geplanter Sprint VORBEI ist.

    Dieselbe Lage wie bei `plandrift`: die Prüfung existiert seit SWR-112 und wurde nie
    gemeldet. `pm/T-0039` belegt den Preis — viermal in Folge wurde `geplant_sprint` um
    genau eins erhöht (6→7→8→9), ohne dass je ein neuer Grund im Ticket stand. SWR-112
    ist für genau diesen Fall gebaut worden und hätte ihn in Sprint 7, 8 und 9 gemeldet;
    gelesen wurde sie in keinem davon.

    `None` heißt „konnte nicht prüfen" und nicht „nichts gefunden".
    """
    sicht = sprintsicht(root)
    return None if sicht is None else sicht.get("sprint_vergangen", [])


def wartet_auf_mensch(root):
    """SWR-120 (pm/T-0051): Weiterleitung auf `aggregation.wartet_auf_mensch`.

    Wie bei `unterminierte_tickets` (SWR-117) ist die Weiterleitung keine zweite
    Quelle, sondern der Beleg, dass es nur eine gibt: Kopfblock und Preflight-Zeile
    beantworten dieselbe Frage und dürfen nicht verschieden zählen (B033).

    `None` heißt „konnte nicht prüfen" und nicht „nichts gefunden".
    """
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from backend import aggregation as _aggregation
        return _aggregation.wartet_auf_mensch(root)
    except Exception:
        return None


def dr_entschieden_nicht_verbucht(root):
    """SWR-131 (platform/T-0014): Weiterleitung auf `aggregation.dr_entschieden_nicht_verbucht`.

    Dieselbe Bauart wie `wartet_auf_mensch` und `unterminierte_tickets`: die
    Weiterleitung ist keine zweite Quelle, sondern der Beleg, dass es nur eine gibt.

    `None` heißt „konnte nicht prüfen" und nicht „nichts gefunden".
    """
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from backend import aggregation as _aggregation
        return _aggregation.dr_entschieden_nicht_verbucht(root)
    except Exception:
        return None


def decision_log_halb_geschrieben(root):
    """SWR-165: Weiterleitung auf `aggregation.decision_log_ohne_marker`.

    Dieselbe Bauart wie `dr_entschieden_nicht_verbucht` — die Weiterleitung ist keine
    zweite Quelle, sondern der Beleg, dass es nur eine gibt.

    `None` heißt „konnte nicht prüfen" und ausdrücklich nicht „nichts gefunden".
    """
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from backend import aggregation as _aggregation
        return _aggregation.decision_log_ohne_marker(root)
    except Exception:
        return None


def uebergangshistorie(root):
    """SWR-118 (pm/T-0048): `(neue, altbestand, register)` oder `None`.

    `None` heißt „konnte nicht prüfen" und ausdrücklich **nicht** „nichts gefunden" —
    dieselbe Unterscheidung, die `statusdrift` oben trifft. Eine stille Erfolgsmeldung
    an der Stelle eines Ausfalls ist genau die Sorte Fehler, die `pm/T-0049`
    ausgelöst hat.
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import uebergang_historie as _uh
        return _uh.pruefe_alle(root)
    except Exception:
        return None


def kalenderfristen(root):
    """SWR-125 (platform/T-0012): Teamaufgaben mit Kalenderdatum — Weiterleitung.

    Dieselbe Bauart wie `unterminierte_tickets` eine Funktion tiefer und aus demselben
    Grund (SWR-117): der Rumpf steht in `backend/aggregation.py`, weil der Cockpit-
    Kopfblock ihn ebenfalls liest und zwei Quellen für eine Frage B033 wären.

    `None` heißt „konnte nicht prüfen" und ausdrücklich nicht „nichts gefunden" —
    dieselbe Unterscheidung wie bei `statusdrift`. Eine stille Erfolgsmeldung an der
    Stelle eines Ausfalls ist genau der Fehler, der `pm/T-0049` ausgelöst hat.
    """
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from backend import aggregation as _aggregation
        return _aggregation.kalenderfristen(root)
    except Exception:
        return None


def unterminierte_tickets(root):
    """SWR-114 (pm/T-0036 Teil b): offene Tickets ohne **Sprintnummer** — org-weit, mit Refs.

    Der Befund B049: der „ohne Frist"-Zähler aus SWR-091 wird **pro Kachel** gelesen und
    nie als Summe. Drei Sessions in Folge erklärten ihn für abgearbeitet, während drei
    Tickets in einer anderen Kachel offen blieben — „Kachel X erledigt" ist keine gültige
    Abschlussmeldung, wenn die Frage der Organisation gilt.

    Gemeldet werden **Namen und nicht nur eine Zahl** (B038: ein Gate, das „82" sagt,
    nennt nicht, welche fünf fehlen). Die Abgrenzung ist dieselbe wie in
    `aggregation` (SWR-091), damit nicht zwei Stellen verschieden zählen (B033):
    Takt-Tickets tragen ihr Zeitkonzept im Feld `takt`, und ein `decision-request` wird
    über `frist` + `default` gesteuert.

    **SWR-117 (pm/T-0047): der Rumpf ist nach `backend/aggregation.py` gewandert.**
    Seit Sprint 9 zeigt der Cockpit-Kopfblock dieselbe Tatsache ein zweites Mal an —
    und zwei Stellen, die eine Frage aus zwei Quellen beantworten, sind B033. Diese
    Funktion bleibt als **Weiterleitung** bestehen: sie ist keine zweite Quelle,
    sondern der Beleg, dass es nur eine gibt, und sie hält die SWR-114-Tests auf dem
    Pfad, der tatsächlich ausgeliefert wird. Die Richtung des Umzugs ist erzwungen —
    `backend` importiert bereits `scripts.board`, der umgekehrte Weg schlösse einen
    Zyklus.

    **⚠ SWR-125 (platform/T-0012, Brief pm/N-0041): die Frage lautet ab Sprint 11
    „hat einen Sprint?" statt „hat ein Datum?".** Der Name der Funktion bleibt, weil
    „unterminiert" die Frage ist und `frist` nur eine ihrer Antworten war. Begründung
    im Rumpf (`aggregation.unterminierte_tickets`).
    """
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from backend import aggregation as _aggregation
    return _aggregation.unterminierte_tickets(root)


def arbeitskopie_befunde(repo, dirty):
    """(befund_pfade, gemeldete_pfade) für einen Repo-Status. SWR-110."""
    befunde, alle = [], []
    for zeile in dirty:
        pfad = _pfad_aus_statuszeile(zeile)
        if not pfad:
            continue
        alle.append(pfad)
        if not ist_verifikationsquelle(pfad):
            continue
        if os.path.basename(pfad) == "BOARD.md" and nur_stand_zeile(repo, pfad):
            continue
        befunde.append(pfad)
    return befunde, alle


def board_check(projekt_repo):
    """board.py --check im Projekt-Repo. Rückgabe: (ok, ausgabe)."""
    if not os.path.isdir(projekt_repo):
        return False, f"Projekt-Repo fehlt: {projekt_repo}"
    skript = os.path.join(os.path.dirname(os.path.abspath(__file__)), "board.py")
    out = subprocess.run([sys.executable, skript, "--check"],
                         capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                         env=konsole.kind_umgebung(), cwd=projekt_repo)
    return out.returncode == 0, (out.stdout + out.stderr).strip()


def unit_tests(platform_repo):
    """Unit-Tests wie in CI (python -m unittest discover tests). (ok, letzte Zeilen)."""
    out = subprocess.run([sys.executable, "-m", "unittest", "discover", "tests"],
                         capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                         env=konsole.kind_umgebung(), cwd=platform_repo)
    tail = "\n".join((out.stdout + out.stderr).strip().splitlines()[-3:])
    return out.returncode == 0, tail


def raeume_locks(root, keep_locks=False, still=False):
    """Lock-Artefakte in allen Repos beseitigen. Rückgabe: Anzahl echter Befunde.

    Wird ZWEIMAL je Lauf gebraucht (pm/T-0023, zweiter Befund): einmal am Anfang,
    damit die Session überhaupt arbeiten kann — und einmal am Ende, weil Git bei
    JEDEM Aufruf (auch `git status`) einen index.lock anlegt und ihn auf einem
    Mount ohne unlink-Recht nicht mehr wegbekommt. Ohne den Schlusslauf hinterlässt
    Preflight genau die Sperre, die es gerade aufgehoben hat.
    """
    befunde = 0
    for name in repos_im_root(root):
        repo = os.path.join(root, name)
        if not os.path.isdir(os.path.join(repo, ".git")):
            continue
        locks = finde_lock_artefakte(repo)
        if not locks:
            continue
        if keep_locks or git_prozess_aktiv():
            print(f"[{name}] {len(locks)} Lock-Artefakt(e) gefunden — NICHT entfernt "
                  f"({'--keep-locks' if keep_locks else 'Git-Prozess aktiv'}):")
            for p in locks:
                print(f"    {p}")
            befunde += 1
            continue
        entfernt, geparkt, kaputt = entferne_artefakte(locks)
        if not still:
            for p in entfernt:
                print(f"[{name}] Lock-Artefakt entfernt: {os.path.relpath(p, repo)}")
            if geparkt:
                # Kein Befund: der Lock ist für Git weg, die Session kann committen.
                # Der Hinweis bleibt, weil die Ursache (Mount ohne unlink-Recht) fortbesteht.
                print(f"[{name}] {len(geparkt)} Lock-Artefakt(e) nicht löschbar (R7) — "
                      f"weggeräumt nach .git/{PARKPLATZ}/:")
                for p in geparkt:
                    print(f"    {os.path.relpath(p, repo)}")
                print("    -> Git ist entsperrt. Ursache bleibt: Mount ohne unlink-Recht; "
                      "Parkplatz gelegentlich auf dem Host leeren.")
        if kaputt:
            befunde += 1
            print(f"[{name}] WEGRÄUMEN FEHLGESCHLAGEN (weder löschen noch umbenennen):")
            for p in kaputt:
                print(f"    {p}")
            print("    -> Auf dem Host löschen bzw. Lösch-Berechtigung der Session "
                  "aktivieren, sonst blockieren Commits.")
    return befunde


def parkplatz_stand(root):
    """SWR-164: wie viele weggeräumte Sperren liegen auf dem Parkplatz? `(gesamt, (repo, n))`.

    Rückgabe `None`, wenn sich kein Repo lesen lässt.

    ⚠⚠ **Das ist die Antwort auf Frage 3 von `platform/T-0021`, und sie lautet ja.** Die
    Räumung ist zweistufig: erst `os.remove`, bei `OSError` **umbenennen** nach
    `.git/verwaiste-locks/`. Auf einem Mount ohne `unlink`-Recht scheitert die erste Stufe
    **immer** — jede geräumte Sperre wird also geparkt und nie gelöscht. Gemessen:

    | Sprint | `pm/.git/verwaiste-locks` |
    |---|---|
    | 21 | 1975 |
    | 24 | 2099 |

    > **Das ist kein Fehler, und es ist auch nicht reparierbar, solange der Mount ist, wie
    > er ist. Es ist eine Größe, die niemand gemessen hat — und eine ungemessene Größe ist
    > von einer, die nicht wächst, nicht zu unterscheiden.**

    ⚠ Diese Funktion räumt **nichts** und ruft **kein git**. Sie zählt Dateien.
    """
    gesamt = 0
    groesster = ("—", 0)
    gesehen = False
    for name in repos_im_root(root):
        pfad = os.path.join(root, name, ".git", PARKPLATZ)
        try:
            n = len(os.listdir(pfad))
        except OSError:
            continue
        gesehen = True
        gesamt += n
        if n > groesster[1]:
            groesster = (name, n)
    return (gesamt, groesster) if gesehen else None


def preflight(root, skip_tests=False, keep_locks=False, nur_locks=False):
    """Alle Checks ausführen. Rückgabe: Anzahl **blockierender** Befunde (0 = startklar).

    ⚠⚠ **SWR-166 (`platform/T-0029`): zwei Zählungen statt einer.** Ein Befund ist
    *blockierend*, wenn der Aufrufer jetzt etwas dagegen tun kann — nicht committete
    Dateien, ungebuchte Statusstände, fehlende Pflichtartefakte, rote Tests, ein
    Statussprung dieses Laufs. Ein Befund ist *fortgeschrieben*, wenn er eine Tatsache
    nennt, die vor Beginn des laufenden Sprints festgeschrieben wurde: ein Statussprung
    aus einem abgeschlossenen Sprint (Historie wird nicht umgeschrieben), eine bereits
    vergangene Pause.

    Fortgeschriebene Befunde erscheinen **unverändert im Wortlaut, namentlich und mit
    Commit** und werden in der Schlusszeile gezählt. Sie setzen nur den Rückgabewert
    nicht. Der Grund ist gemessen: 83 abgebrochene Push-Läufe in drei Tagen und 12 Ticks,
    die nie liefen, weil eine unbehebbare Tatsache dauerhaft Exit 1 erzwang.
    """
    befunde = raeume_locks(root, keep_locks)
    fortgeschrieben = 0
    if nur_locks:
        print(f"PREFLIGHT: {'STARTKLAR' if befunde == 0 else str(befunde) + ' Befund(e)'} "
              "(nur Lock-Räumung)")
        return befunde
    for name in repos_im_root(root):
        repo = os.path.join(root, name)
        if not os.path.isdir(os.path.join(repo, ".git")):
            print(f"[{name}] FEHLT: kein Git-Repo unter {repo}")
            befunde += 1
            continue
        dirty, tracking = repo_status(repo)
        # SWR-191, Vorabfrage 2 aus platform/T-0046: der veraltete Index ist eine
        # Auskunft wert — aber eine ANDERE als „nicht committet". Zwei Sachverhalte
        # unter EINEM Meldetext ist die Bauart, die SWR-116 abgelehnt hat; deshalb
        # eine eigene Zeile mit eigenem Wortlaut.
        #
        # ⚠ Ausdrücklich KEIN Befund: der Zähler ist das Tor vor dem Schnelltakt, und
        # der Aufrufer kann in der Sandbox nichts dagegen tun (`rm` -> R7). Ihn hier
        # hochzuzählen hieße, SWR-166 ein zweites Mal zu bauen — diesmal wissentlich.
        # Auf dem Host räumt `raeume_locks` die Sperre, und die Zeile verschwindet.
        if index_gesperrt(repo):
            print(f"[{name}] Hinweis: Index gesperrt (.git/index.lock) — er kann nicht "
                  f"auffrischen und steht auf dem Stand VOR dem letzten Commit. Die "
                  f"Messung oben lief gegen den BAUM und ist davon unberührt (SWR-191). "
                  f"Auf dem Host löschbar; kein Befund.")
        if dirty:
            # SWR-110: Dateien NENNEN statt zählen. Sechs Zeilen "1 Datei(en)" sahen in
            # Sprint 6 gleich aus — fünfmal eine regenerierte Stand-Zeile, einmal eine
            # ganze Anforderung, die deshalb ungesehen ungepusht blieb (platform/T-0010).
            unverbucht, alle = arbeitskopie_befunde(repo, dirty)
            print(f"[{name}] Arbeitskopie nicht sauber ({len(dirty)} Datei(en)) — {tracking}")
            for pfad in alle:
                marke = "  UNVERBUCHT" if pfad in unverbucht else "  "
                print(f"  {marke} {pfad}")
            if unverbucht:
                print(f"[{name}] BEFUND: {len(unverbucht)} Datei(en), die eine Verifikation "
                      f"liest, sind nicht committet — gemessen wird die Arbeitskopie, "
                      f"gepusht wird HEAD. Committen, sonst gilt das Ergebnis für "
                      f"keinen Repo-Stand.")
                befunde += 1
        else:
            print(f"[{name}] sauber — {tracking}")
    # SWR-139 (platform/T-0017), DoD 4: unverbuchte STATUS-Stände als eigener Befund.
    # SWR-110 oben meldet jede geänderte Datei; was fehlte, ist die Zuspitzung auf
    # `status`. Der Unterschied ist keine Feinheit: ein ergänzter Tickettext ist kein
    # verlorener Zustand, ein nicht gebuchter Statuswechsel ist einer — der nächste
    # Wechsel überschreibt ihn, und in der Historie fehlt eine Stufe (gemessen an
    # `pm/T-0052`, Sprint 15). Nach SWR-122 legt die Prüfung hier ihren Leser fest.
    for _name, _pfad in (board.projekt_pfade(root) or []):
        try:
            _offen = board.unverbuchte_status(_pfad)
        except Exception as e:  # eine scheiternde Prüfung meldet sich, statt zu schweigen
            print(f"[{_name}] unverbuchte Statuswechsel: NICHT PRÜFBAR — {e}")
            continue
        if not _offen:
            continue
        for _zeile in _offen:
            print(f"  UNVERBUCHTER STATUS  {_zeile}")
        print(f"[{_name}] BEFUND: {len(_offen)} Statuswechsel geschrieben und nicht "
              f"gebucht. Ein Zustandswechsel ist EIN Vorgang (SWR-139) — buchen, sonst "
              f"überschreibt ihn der nächste Wechsel lautlos.")
        befunde += 1
    # SWR-029: board-check über ALLE Projekte (Discovery-Konvention, ADR-004);
    # SWR-070/p9-T-0007: inkl. Projektordner im Sammel-Repo projects/ (pm/D003).
    projekte = board.projekt_pfade(root) or [("p0", os.path.join(root, "p0"))]
    for name, pfad in projekte:
        ok, meldung = board_check(pfad)
        print(f"[{name}] board-check: {'OK' if ok else 'FEHLER — ' + meldung}")
        if not ok:
            befunde += 1
    # SWR-114 (pm/T-0036 Teil b): org-weite Summe der Tickets ohne Frist, MIT Namen.
    # Die Stelle, an der eine Session ohnehin hinsieht, bevor sie etwas anderes tut —
    # und die einzige, die die Frage für die ganze Organisation stellt statt je Kachel.
    #
    # SWR-125 (platform/T-0012, Brief pm/N-0041): die Frage lautet ab Sprint 11
    # „hat einen SPRINT?" statt „hat ein DATUM?". Bis dahin hat genau diese Zeile
    # erzwungen, was der Auftraggeber zweimal gerügt hat — wer ein Ticket ohne
    # Kalenderdatum anlegte, machte den Startcheck rot.
    # SWR-136 (platform/T-0013), DoD 4: der Zustand des Sprintregisters wird GEMELDET.
    # Nach SWR-122 legt eine neue Prüfung im selben Zug fest, wer ihr Ergebnis liest —
    # sonst entsteht die vierte Gestalt derselben Familie: eine Prüfung ohne Leser.
    #
    # Die Zeile erscheint IMMER, auch im guten Fall: der Grund steht eine Etage tiefer
    # bei `unterminierte_tickets` und gilt hier wörtlich. ⚠ Der **laufende** Sprint zählt
    # ausdrücklich NICHT als Befund — während eines Laufs trägt seine eigene Zeile
    # naturgemäß kein `ende`, und eine Dauerwarnung liest nach zwei Sprints niemand mehr.
    try:
        nr_jetzt = sprint_register.aktuell(root)
        laeuft = sprint_register.laufender(root)
        luecken = sprint_register.nicht_beendete(root)
    except Exception:
        nr_jetzt, laeuft, luecken = None, None, None
    if nr_jetzt is None:
        print("[org] Sprintregister: nicht prüfbar (Register nicht ladbar).")
    else:
        zustand = "läuft" if laeuft else "beendet"
        print(f"[org] Sprintregister: Sprint {nr_jetzt} ({zustand}), "
              f"Stichtag Ende-Pflicht ab Sprint "
              f"{sprint_register.STICHTAG_ENDE_SPRINT}.")
        if luecken:
            print(f"[org] BEFUND: {len(luecken)} abgeschlossene(r) Sprint(s) ohne "
                  f"'ende' im Register: "
                  + ", ".join(f"{e['nr']} ({e.get('kennung', '?')})" for e in luecken))
            befunde += 1
    # SWR-156 (platform/T-0025, Brief team-mail/N-0004 des Auftraggebers): war es zu
    # lange still? Die Zeile erscheint IMMER — auch bei unauffälliger Pause. Eine stille
    # Prüfung ist von einer nicht gelaufenen nicht zu unterscheiden (SWR-114/117/155),
    # und genau das war der Befund: 60,2 Stunden Pause bei 60 Minuten Takt, von keiner
    # Ausgabe dieses Laufs erwähnt.
    pause = pause_zum_vorlauf(root)
    if pause is None:
        print("[org] Pause seit dem letzten Lauf: nicht prüfbar (Modul nicht ladbar).")
    elif pause["minuten"] is None:
        print(f"[org] Pause seit dem letzten Lauf: nicht berechenbar — "
              f"{pause['unberechenbar']}.")
    elif pause["ueberlappung"]:
        # Nicht auf 0 gekappt: eine negative Pause ist der einzige Beleg dafür, dass die
        # Zeitstempel zweier Läufe aus Uhren stammen, die nicht übereinstimmten.
        print(f"[org] BEFUND: Überlappung im Sprintregister — {pause['hinweis']}.")
        befunde += 1
    else:
        satz = (f"[org] Pause seit dem Ende von Sprint {pause['letzter_nr']} "
                f"({pause['letztes_ende']}) bis {pause['bezug']}: "
                f"{pause['minuten']} Min = {pause['vielfaches']}x Takt "
                f"({pause['takt_min']} Min)")
        if pause["befund"]:
            # SWR-166 (platform/T-0029): FORTGESCHRIEBEN und nicht blockierend. Die
            # Zeile bleibt Wort für Wort stehen — sie ist die Antwort auf den Brief
            # `team-mail/N-0004` und hat ihren Zweck, sobald sie berichtet wird
            # (SWR-125). ⚠ Blockieren kann sie nichts: eine bereits vergangene Pause
            # ist von keinem Aufrufer zu verkürzen, und der Auto-Push-Wächter, den sie
            # 83-mal gestoppt hat, ist genau der, dessen Aufgabe das Arbeiten IN dieser
            # Pause ist. Ein Wächter, der stillsteht, weil es still war, meldet seine
            # eigene Untätigkeit als Grund für sie.
            print(f"{satz} — FORTGESCHRIEBEN: mehr als {pause['takte']} Takte. "
                  f"{pause['hinweis']}.")
            fortgeschrieben += 1
        else:
            print(f"{satz}.")
        if pause["ohne_ende"]:
            print(f"[org] Für {len(pause['ohne_ende'])} Sprint(s) ohne 'ende' ist keine "
                  f"Pause berechenbar (vor dem Stichtag): "
                  + ", ".join(str(n) for n in pause["ohne_ende"]) + ".")
    # SWR-159 (platform/T-0026): stimmen die Uhren der Läufe überein? Gemessen wird eine
    # Unmöglichkeit und keine Schwelle — eine Registerzeile kann nicht später entstanden
    # sein als der Commit, der sie mitnimmt. ⚠ Die Zeile erscheint IMMER, auch bei 0
    # Treffern (SWR-114/117/155): eine stille Prüfung ist von einer nicht gelaufenen
    # nicht zu unterscheiden.
    uhren = uhrenprobe_register(root)
    if uhren is None:
        print("[org] Uhrenprobe Register/Commit: nicht prüfbar (kein Git oder kein Register).")
    else:
        # ⚠ Der eine belegte Fall ist Altbestand und wird mit seiner ZAHL gemeldet, nicht
        # weggelassen: die Datei ist append-only, er ist nicht reparierbar, und ihn zum
        # Dauerbefund zu machen hiesse das Wegsehen zu trainieren (SWR-109/110/112).
        alt = [u for u in uhren if u["altbestand"]]
        neu = [u for u in uhren if not u["altbestand"]]
        print(f"[org] Uhrenprobe Register/Commit: {len(neu)} neue(r), "
              f"{len(alt)} Altbestand (namentlich eingefroren, bewusst nicht geglättet).")
        for u in alt:
            print(f"    ALTBESTAND  {u['kennung']} '{u['feld']}' = {u['registerzeit']}, "
                  f"Commit {u['commit']} um {u['commitzeit']} ({u['minuten']:+.1f} Min)")
        if neu:
            print(f"[org] BEFUND: {len(neu)} Registerzeit(en) liegen in der Zukunft ihres "
                  f"Commits — zwei Uhren waren uneinig:")
            for u in neu:
                print(f"    {u['kennung']} '{u['feld']}' = {u['registerzeit']}, "
                      f"Commit {u['commit']} um {u['commitzeit']} ({u['minuten']:+.1f} Min)")
            befunde += 1
    # SWR-161 (platform/T-0022): fehlt einem Repo ein Pflichtartefakt des Gründungswegs?
    # ⚠ Die Zeile erscheint IMMER — auch bei 0 (SWR-114/117/155).
    artefakte = fehlende_pflichtartefakte(root)
    if artefakte is None:
        print("[org] Pflichtartefakte je Repo: nicht prüfbar (Discovery nicht ladbar).")
    elif artefakte:
        print(f"[org] BEFUND: {len(artefakte)} fehlende(s) Pflichtartefakt(e) — ein Repo "
              f"ohne Entscheidungslog verliert die erste Klasse-A-Entscheidung, die "
              f"darin verbucht werden soll:")
        for repo, artefakt in artefakte:
            print(f"    {repo}: {artefakt} FEHLT")
        befunde += 1
    else:
        print("[org] Pflichtartefakte je Repo: 0 fehlend.")
    # SWR-164 (platform/T-0021, Frage 3): der Parkplatz wächst — und zwar unbegrenzt.
    # ⚠ Die Zeile erscheint IMMER (SWR-114/117/155) und ist **kein Befund**: es gibt
    # nichts zu reparieren, solange der Mount kein `unlink` erlaubt. Sie steht hier, weil
    # eine Größe, die niemand misst, von einer Größe, die nicht wächst, nicht zu
    # unterscheiden ist.
    stand = parkplatz_stand(root)
    if stand is None:
        print("[org] Parkplatz verwaiste-locks: nicht messbar.")
    else:
        gesamt, groesster = stand
        print(f"[org] Parkplatz verwaiste-locks: {gesamt} Datei(en) über alle Repos, "
              f"größter Einzelbestand {groesster[1]} in {groesster[0]}. "
              f"Auf dem Host löschbar, von hier aus nicht (Mount ohne unlink-Recht).")
    # SWR-170: ollama-Besetzungen, deren Registermodell vom Guardrails-Default abweicht.
    # ⚠ Die Zeile steht IMMER da, auch bei 0 (SWR-114/117/155), und sie nennt die
    # Grundmenge mit — eine Prüfung, die das Register gar nicht liest, meldet sonst
    # dasselbe wie eine, bei der alles stimmt (SWR-128, Gegenprobe aus SWR-165).
    # ⚠ Gemeldet, nicht geheilt und NICHT blockierend: welcher der beiden Werte richtig
    # ist, weiß nur, wer das Register pflegt. Ein Dauerbefund, den dieses Werkzeug nicht
    # entscheiden kann, wäre genau der Schalter aus SWR-166.
    try:
        abw, grundmenge, default = organisation.modellabweichungen(root)
        if abw:
            namen = ", ".join(f"{i} -> {m}" for i, m in abw)
            print(f"[org] Modell laut Besetzungsregister abweichend vom Guardrails-Default "
                  f"'{default}': {len(abw)} von {grundmenge} ollama-Besetzung(en) — {namen}. "
                  f"Der Gateway folgt dem Register (SWR-169).")
        else:
            print(f"[org] Modell laut Besetzungsregister abweichend vom Guardrails-Default "
                  f"'{default}': 0 von {grundmenge} ollama-Besetzung(en).")
    except Exception as e:            # noqa: BLE001 — eine unlesbare Datei ist ein Befund
        print(f"[org] Modellabgleich Besetzungsregister/Guardrails: nicht messbar ({e}).")
    ohne_sprint = unterminierte_tickets(root)
    if ohne_sprint:
        print(f"[org] {len(ohne_sprint)} Ticket(s) ohne Sprint: {', '.join(ohne_sprint)}")
        befunde += 1
    else:
        print("[org] 0 Tickets ohne Sprint.")
    # SWR-125, zweite Hälfte: die Gegenrichtung. „Nicht mehr gefordert" genügt nicht —
    # SWR-106 hatte Kalenderdaten schon fünf Sprints früher abgeschafft, und weil ihre
    # Rückkehr niemand meldete, waren kurz darauf wieder 14 Stück da. Zählt deshalb
    # als Befund: eine Zeile, die nichts blockiert, hat den Bericht von Sprint 9 auch
    # nicht verhindert.
    kal = kalenderfristen(root)
    if kal is None:
        print("[org] Kalenderfristen an Teamaufgaben: nicht prüfbar "
              "(Aggregation nicht ladbar).")
    elif kal:
        print(f"[org] BEFUND: {len(kal)} Teamaufgabe(n) tragen ein Kalenderdatum statt "
              f"einer Sprintnummer: {', '.join(kal)}")
        befunde += 1
    else:
        print("[org] Kalenderfristen an Teamaufgaben: 0.")
    # SWR-120 (pm/T-0051): dieselbe Frage für den Menschen — wie viele offene Tickets
    # liegen bei ihm, und WELCHE. Aus derselben Quelle wie der Cockpit-Kopfblock
    # (`aggregation.wartet_auf_mensch`), damit Preflight und HMI nicht verschieden
    # zählen (B033), und mit Namen statt nur einer Zahl (B038).
    #
    # Die Zeile erscheint auch bei 0 — dieselbe Begründung wie eine Zeile höher: ein
    # stiller Check ist von einem nicht gelaufenen nicht zu unterscheiden.
    wartend = wartet_auf_mensch(root)
    if wartend is None:
        print("[org] Wartet auf den Menschen: nicht prüfbar (Aggregation nicht ladbar).")
    elif wartend:
        print(f"[org] {len(wartend)} Ticket(s) warten auf den Menschen: "
              f"{', '.join(wartend)}")
    else:
        print("[org] 0 Tickets warten auf den Menschen.")
    # SWR-131 (platform/T-0014): die zweite Hälfte der Zeile darüber — und ohne sie wäre
    # die erste eine Verschlechterung. Ein entschiedener DR verschwindet ab SWR-131 aus
    # „wartet auf den Menschen" (er wartet auf niemanden); stünde er dann weiter auf
    # `open`, hätte ihn niemand mehr im Blick. Genau der Zustand war am 2026-08-17 um
    # 11:48 der Fall und blieb 16 Minuten lang unbemerkt — lang genug für drei Berichte,
    # die dem Auftraggeber eine Frage vorlegten, die er beantwortet hatte.
    #
    # Zählt als BEFUND, nicht als Zeile: die Verbuchung ist Folgearbeit (entsperren,
    # planen, berichten), und ein Lauf, der sie überspringt, darf nicht startklar melden.
    unverbucht = dr_entschieden_nicht_verbucht(root)
    if unverbucht is None:
        print("[org] Entschiedene, unverbuchte DRs: nicht prüfbar (Aggregation nicht ladbar).")
    elif unverbucht:
        print(f"[org] BEFUND: {len(unverbucht)} entschiedene(r) DR(s) sind nicht verbucht — "
              f"die Antwort liegt vor, der Arbeitsstand kennt sie nicht: "
              f"{', '.join(unverbucht)}")
        befunde += 1
    else:
        print("[org] Entschiedene, unverbuchte DRs: 0.")
    # SWR-165 (platform/T-0022 Frage 1): die Naht zwischen dem ERSTEN und dem ZWEITEN der
    # drei Schreibvorgänge von `inbox.entscheide`. Fällt sie aus, steht die Entscheidung im
    # Log und **jede** Prüfung hält den DR weiter für offen — der Mensch bekommt eine
    # Frage erneut vorgelegt, die er beantwortet hat. Zeile IMMER (SWR-114/117/155).
    halb = decision_log_halb_geschrieben(root)
    if halb is None:
        print("[org] Decision-Log gegen Ticketmarker: nicht prüfbar (Aggregation nicht ladbar).")
    elif halb:
        print(f"[org] BEFUND: {len(halb)} protokollierte Entscheidung(en) ohne Vermerk im "
              f"Ticket — die Entscheidung ist gefallen und für jede Prüfung unsichtbar:")
        for projekt, d_id, ticket_id, grund in halb:
            print(f"    {projekt}/{ticket_id} ({d_id}): {grund}")
        befunde += 1
    else:
        print("[org] Decision-Log gegen Ticketmarker: 0 halb geschriebene Entscheidungen.")
    # SWR-115 (pm/T-0049): die STATUSSPALTE des Sprintplans gegen den Ticketstatus.
    # Hier und nicht später, weil Sprint 7 `platform/T-0010` vierfach als erledigt gemeldet
    # hat — an den Auftraggeber inbegriffen — und `sprint_vergangen` (SWR-112) den Fall
    # frühestens im FOLGESPRINT sehen kann. Eine Prüfung, die den Fehler erst findet,
    # nachdem er berichtet wurde, verhindert die Falschmeldung nicht.
    drift = statusdrift(root)
    if drift is None:
        print("[org] Statusdrift Plan/Ticket: nicht prüfbar (Sprintsicht nicht ladbar).")
    elif drift:
        print(f"[org] BEFUND: {len(drift)} Planzeile(n) widersprechen ihrem Ticket — "
              f"der Plan sagt etwas anderes als das Ticketfeld:")
        for d in drift:
            print(f"    {d['ref']}: {d['meldung']}")
        befunde += 1
    else:
        print("[org] Statusdrift Plan/Ticket: 0.")
    # SWR-201 (platform/T-0052): der Plannachlauf des LAUFENDEN Sprints. Kein Befund und
    # trotzdem eine Zeile — am laufenden Betrieb gemessen (60 Läufe, 7 Sprints): dieses
    # Fenster steht in JEDEM Sprint, 15–45 Min, 24 % der Beobachtungszeit, und hat den
    # Schnelltakt des Auftraggebers dreimal als EINZIGER Befund abgebrochen.
    #
    # ⚠ Die Zeile nennt Referenzen und den GRUND, nicht nur eine Zahl. `SWR-196` hat
    # gemessen, was eine wahre, aber zu enge Meldung kostet: sie lädt ein, es in 15
    # Minuten nochmal zu versuchen — 90-mal geschehen. Wer hier liest, soll wissen, dass
    # Warten die falsche Handlung ist und der Plan am Sprint-Abschluss nachzieht.
    nachlauf = plannachlauf(root)
    if nachlauf is None:
        print("[org] Plannachlauf laufender Sprint: nicht prüfbar (Sprintsicht nicht ladbar).")
    elif nachlauf:
        print(f"[org] {len(nachlauf)} Planzeile(n) hinken dem Ticket nach, weil der Sprint "
              f"LÄUFT — kein Befund (pm/D006: der Plan wird am Sprint-Abschluss "
              f"fortgeschrieben):")
        for d in nachlauf:
            print(f"    {d['ref']}: {d['meldung']}")
    else:
        print("[org] Plannachlauf laufender Sprint: 0.")
    # SWR-122 (platform/T-0011): die beiden Nachbarn von `status_drift`, die bis Sprint 10
    # berechnet und von niemandem gelesen wurden.
    #
    # `plan_drift` (SWR-109) fragt: sagt die FÄLLIGKEITSSPALTE dieselbe Sprintnummer wie
    # das Ticketfeld? `sprint_vergangen` (SWR-112) fragt: liegt der geplante Sprint in der
    # VERGANGENHEIT? Das sind zwei Fragen an denselben Bestand und keine zwei Meinungen
    # über eine — ein Ticket kann in beiden stehen (heute: `pm/T-0028`, `pm/T-0039`) und
    # das ist kein Doppelbefund, sondern zwei Fehler an einem Ticket.
    #
    # Beide Zeilen erscheinen auch bei 0 (SWR-114-Begründung) und nennen Referenzen statt
    # nur einer Zahl (B038). Beide zählen als Befund: eine Zeile, die nichts blockiert,
    # hätte den Bericht von Sprint 9 nicht verhindert.
    pdrift = plandrift(root)
    if pdrift is None:
        print("[org] Plan-Drift Sprintnummer: nicht prüfbar (Sprintsicht nicht ladbar).")
    elif pdrift:
        print(f"[org] BEFUND: {len(pdrift)} Planzeile(n) nennen eine andere Sprintnummer "
              f"als ihr Ticket:")
        for d in pdrift:
            print(f"    {d['ref']}: {d['meldung']}")
        befunde += 1
    else:
        print("[org] Plan-Drift Sprintnummer: 0.")
    vergangen = sprintvergangen(root)
    if vergangen is None:
        print("[org] Offen auf vergangenem Sprint: nicht prüfbar (Sprintsicht nicht ladbar).")
    elif vergangen:
        print(f"[org] BEFUND: {len(vergangen)} offene(s) Ticket(s) auf einem bereits "
              f"vergangenen Sprint:")
        for d in vergangen:
            print(f"    {d['ref']}: {d['meldung']}")
        befunde += 1
    else:
        print("[org] Offen auf vergangenem Sprint: 0.")
    # SWR-155 (pm/T-0069, Brief pm/N-0043 Punkt 4): angefangen und liegengeblieben.
    liegen = liegengeblieben_in_arbeit(root)
    if liegen is None:
        print("[org] In Arbeit liegengeblieben: nicht prüfbar (Sprintsicht nicht ladbar).")
    else:
        offen_in_arbeit, sprint_laeuft = liegen
        if sprint_laeuft:
            # ⚠ Nicht schweigen, nur nicht werten: waehrend eines Sprints ist
            # `in_progress` der richtige Zustand.
            print(f"[org] In Arbeit (ein Sprint läuft, kein Befund): "
                  f"{len(offen_in_arbeit)}.")
        elif offen_in_arbeit:
            print(f"[org] BEFUND: {len(offen_in_arbeit)} Aufgabe(n) stehen auf "
                  f"`in_progress`, obwohl kein Sprint läuft — angefangen und "
                  f"liegengeblieben:")
            for o in offen_in_arbeit:
                print(f"    {o['ref']}: {o.get('titel', '')}")
            befunde += 1
        else:
            print("[org] In Arbeit liegengeblieben: 0.")
    # SWR-118 (pm/T-0048): unzulässige Statusübergänge in der COMMITTETEN Historie.
    #
    # Die Übergangsprüfung in `board.py` hält die Arbeitskopie gegen HEAD und ist damit
    # blind für einen Sprung, der schon committet ist — ihr Ergebnis hing an der
    # REIHENFOLGE der Session. Diese Prüfung liest stattdessen die Folge der
    # `status:`-Werte in der Historie: ein Sachverhalt, der sich nicht dadurch ändert,
    # wann man ihn abfragt.
    #
    # Der Altbestand vor dem Stichtag wird GEMELDET und blockiert NICHT — nicht
    # geglättet, aber auch kein Dauerbefund, der das Wegsehen trainiert.
    uebergaenge = uebergangshistorie(root)
    if uebergaenge is None:
        print("[org] Statusübergänge (Historie): nicht prüfbar (Modul nicht ladbar).")
    else:
        neue, weiter, altbestand, register = uebergaenge
        print(f"[org] Altbestand unzulässiger Statusübergänge (vor dem Stichtag, "
              f"bewusst nicht geglättet): {len(altbestand)}.")
        for z in register:
            print(f"[org] BEFUND: {z}")
            befunde += 1
        # SWR-166 (platform/T-0029): Fälle aus ABGESCHLOSSENEN Sprints. Sie stehen
        # namentlich und mit Commit da — nichts wird geglättet, nichts zusammengefasst
        # (SWR-110: nennen, nicht zählen). Sie setzen nur den Exit-Code nicht mehr.
        # Die Zeile erscheint AUCH bei 0 (SWR-114/117/155).
        if weiter:
            print(f"[org] FORTGESCHRIEBEN: {len(weiter)} unzulässige(r) "
                  f"Statusübergang/-übergänge aus abgeschlossenen Sprints — gemeldet, in "
                  f"deren Berichten benannt, nicht reparierbar (Kap. 16), blockiert nicht:")
            for z in weiter:
                print(f"    {z}")
            fortgeschrieben += len(weiter)
        else:
            print("[org] Fortgeschriebene unzulässige Statusübergänge: 0.")
        if neue:
            print(f"[org] BEFUND: {len(neue)} unzulässige(r) Statusübergang/-übergänge "
                  f"im LAUFENDEN Sprint:")
            for z in neue:
                print(f"    {z}")
            befunde += 1
        else:
            print("[org] Unzulässige Statusübergänge im laufenden Sprint: 0.")
    # SWR-051 (P4): Session-Routine "Briefkasten zuerst" — offene Briefe anzeigen (informativ)
    for name, pfad in projekte:
        verz = os.path.join(pfad, "management", "briefkasten")
        if os.path.isdir(verz):
            offen = sum(1 for d in os.listdir(verz) if d.endswith(".md") and
                        "status: offen" in open(os.path.join(verz, d), encoding="utf-8").read(300))
            if offen:
                print(f"[{name}] BRIEFKASTEN: {offen} offene(r) Brief(e) — zuerst beantworten!")
    if skip_tests:
        print("[platform] Unit-Tests übersprungen (--skip-tests)")
        print("[platform] JS-Tests übersprungen (--skip-tests)")
    else:
        ok, tail = unit_tests(os.path.join(root, "platform"))
        print(f"[platform] Unit-Tests: {'OK' if ok else 'ROT'} — {tail.splitlines()[-1] if tail else ''}")
        if not ok:
            befunde += 1
        # SWR-128 (ADR-008): die JS-Teststrecke. Sie wird IMMER gemeldet — auch wenn sie
        # nicht lief. Ein still übersprungener Test ist von einer Prüfung, die es gar nicht
        # gibt, nicht zu unterscheiden (SWR-114/SWR-122) — und genau so ist der Zustand
        # "741 Python-Tests, null JS-Tests" unbemerkt geblieben, obwohl SWR-098/099/100
        # Nachweise an JavaScript verlangen.
        # Rot zählt als Befund. "Übersprungen" zählt NICHT: solange p12/T-0007 nicht
        # entschieden ist, ist Node keine Voraussetzung des Projekts, und ein fehlendes
        # Werkzeug darf den Lauf des Menschen nicht blockieren. Gemeldet wird es trotzdem,
        # und das genügt — eine Kennzahl steuert, sobald sie berichtet wird (SWR-125).
        js = js_tests.lauf(root)
        print(f"[platform] {js['meldung']}")
        if js["zustand"] == "rot":
            befunde += 1
    # Schlusslauf (pm/T-0023): Die eigenen git-Aufrufe oben haben auf einem Mount ohne
    # unlink-Recht neue index.lock hinterlassen. Ohne dieses Aufräumen meldet Preflight
    # STARTKLAR und der nächste Commit der Session scheitert trotzdem.
    befunde += raeume_locks(root, keep_locks, still=True)
    # SWR-166: BEIDE Zahlen, immer — auch wenn eine 0 ist. Eine Schlusszeile, die nur
    # das Blockierende nennt, macht aus "gemeldet, blockiert nicht" auf dem Weg nach
    # draußen ein "nicht gemeldet" (SWR-114/117/155).
    print(f"PREFLIGHT: {'STARTKLAR' if befunde == 0 else str(befunde) + ' Befund(e)'} "
          f"({fortgeschrieben} fortgeschrieben)")
    return befunde


def main():
    p = argparse.ArgumentParser(description="Session-/Tick-Preflight (T-0024)")
    p.add_argument("--repos", default=".", help="Wurzel mit process/, platform/, p0/")
    p.add_argument("--skip-tests", action="store_true", help="Unit-Tests auslassen (Tick-Modus)")
    p.add_argument("--keep-locks", action="store_true", help="Locks nur melden, nie löschen")
    p.add_argument("--nur-locks", action="store_true",
                   help="Nur Lock-Artefakte räumen (schnelles Entsperren vor einem git-Schreibvorgang)")
    a = p.parse_args()
    sys.exit(1 if preflight(a.repos, a.skip_tests, a.keep_locks, a.nur_locks) else 0)


if __name__ == "__main__":
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import konsole
    konsole.sichere_ausgabe()  # platform/T-0009: am Melden nicht sterben
    main()
