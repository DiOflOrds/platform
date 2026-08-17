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

# SWR-126 (pm/T-0059, Brief pm/N-0031): Ein Brief ist ein VERLAUF aus Beiträgen.
# Jede `##`-Zeile, die ein Beitragskopf ist, beginnt einen neuen Beitrag.
JEDE_H2 = re.compile(r"(?m)^## (?P<titel>.+?)[ \t]*$")
# Die Klammer am Ende einer Überschrift — dort steht bei einem Beitrag die Zeit.
KLAMMER_AM_ENDE = re.compile(r"\(([^)]*)\)\s*$")
# Format neuer Beiträge: `## <Absender> (<ISO-Zeit>)`
BEITRAG_FORMAT = "## %s (%s)"


def _ist_beitragskopf(titel):
    """Beginnt diese `##`-Zeile einen Beitrag — oder ist sie ein Abschnitt darin?

    **Diese Unterscheidung ist der ganze Kern von `pm/T-0059`**, und sie ist gemessen
    und nicht geraten. Im Bestand vom 2026-08-17 stehen in 41 Briefen:

    * **52** Überschriften `## Antwort…` — **alle** mit ISO-Datum. (52 > 41: es gibt
      längst Briefe mit **mehreren** Team-Beiträgen, von Hand angelegt. Der Wunsch des
      Auftraggebers beschreibt also keine neue Idee, sondern eine bestehende Praxis
      ohne Werkzeug.)
    * **11** andere `##`-Überschriften, die **Abschnitte innerhalb** einer Antwort sind
      (`## 1. Was heute fehlt`, `## 3. Was davon eine Entscheidung von dir braucht`).
      Genau **eine** davon trägt ein ISO-Datum in Klammern:
      `## Vollzug (Team, 2026-08-16, Routine-Session)` in `pm/N-0015` — und die **ist**
      ein zweiter Beitrag, kein Abschnitt.

    Ein naives „jede `##` ist ein Beitrag" zerlegte also **11 Briefe falsch**. Die Regel
    lautet deshalb: Beitragskopf ist, was mit `Antwort` beginnt (der Einstieg aus B054,
    verallgemeinert statt ersetzt) **oder** eine Klammer am Ende trägt, in der ein
    ISO-Datum steht. Beides trifft auf alle 52 zu, auf `Vollzug` — und auf keinen der
    zehn Abschnitte (`Frist 23.08.` ist kein ISO-Datum).
    """
    if titel.startswith("Antwort"):
        return True
    klammer = KLAMMER_AM_ENDE.search(titel)
    return bool(klammer and DATUM_IM_KOPF.search(klammer.group(1)))


def beitraege(body):
    """Body -> Liste von Beiträgen `[{absender, zeit, text, ist_erstbeitrag}]` (SWR-126).

    **Keine zweite Parserlogik neben `spalte_antwort`** (B033): `spalte_antwort` ist ab
    hier eine Sicht **auf** dieser Funktion, kein eigener Leser. B054 hat gezeigt, was
    passiert, wenn zwei Stellen dieselbe Datei verschieden lesen — dort blieb bei zehn
    von dreißig Briefen die Antwort unsichtbar.

    **Die 41 Bestandsbriefe bleiben ohne Migration lesbar.** Der Text vor dem ersten
    Beitragskopf ist der Erstbeitrag des Menschen; sein Absender und seine Zeit stehen
    nicht in einer Überschrift, sondern im Frontmatter (`von`, `zeit`). Deshalb bleiben
    die beiden Felder hier **leer** statt geraten — sie zu erfinden wäre B038. Der
    Aufrufer kennt sie.
    """
    koepfe = [m for m in JEDE_H2.finditer(body) if _ist_beitragskopf(m.group("titel"))]
    erst = body[:koepfe[0].start()] if koepfe else body
    liste_ = []
    if erst.strip():
        liste_.append({"absender": "", "zeit": "", "text": erst.strip(),
                       "ist_erstbeitrag": True})
    for i, m in enumerate(koepfe):
        ende = koepfe[i + 1].start() if i + 1 < len(koepfe) else len(body)
        titel = m.group("titel").strip()
        datum = DATUM_IM_KOPF.search(titel)
        klammer = KLAMMER_AM_ENDE.search(titel)
        absender = (titel[:klammer.start()] if klammer else titel).strip()
        liste_.append({"absender": absender, "zeit": datum.group(0) if datum else "",
                       "text": body[m.end():ende].strip(), "ist_erstbeitrag": False})
    return liste_


class BriefkastenFehler(Exception):
    def __init__(self, code, meldung):
        super().__init__(meldung)
        self.code = code


def _entsperre(repo):
    """SWR-123 (pm/T-0055 Teil 2): verwaiste Git-Sperren dieses Repos wegräumen.

    **Kein zweiter Räummechanismus.** Die Organisation hat seit Sprint 5 genau einen —
    `preflight.finde_lock_artefakte` / `entferne_artefakte`, zweistufig (löschen, sonst
    wegbenennen), weil dieser Mount kein `unlink` erlaubt. Einen eigenen daneben zu
    stellen wäre B033: zwei Stellen, die dieselbe Frage beantworten und irgendwann
    verschieden.

    Der Import steht **hier drin** und nicht oben: `preflight` importiert `board` und
    `backend`, ein Modulimport an der Dateispitze schlösse einen Zyklus. Schlägt er
    fehl, ist das kein Fehler des Schreibpfads — dann bleibt es beim alten Verhalten,
    also bei der ehrlichen Meldung aus SWR-121.

    Rückgabe: Anzahl weggeräumter Artefakte (0 = nichts zu tun oder nicht möglich).
    """
    try:
        import sys
        skripte = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "scripts")
        if skripte not in sys.path:
            sys.path.insert(0, skripte)
        import preflight as _preflight
    except Exception:
        return 0
    try:
        locks = _preflight.finde_lock_artefakte(repo)
        if not locks:
            return 0
        entfernt, geparkt, _kaputt = _preflight.entferne_artefakte(locks)
        return len(entfernt) + len(geparkt)
    except Exception:
        return 0


def _verbuche(repo, rel, meldung):
    """SWR-123: `git add` + `commit`, bei verwaister Sperre EINMAL wiederholen.

    Der gemessene Ablauf des Fehlers (pm/N-0039): `git add` hinterlässt auf diesem Mount
    eine `index.lock`, die es nicht mehr löschen kann, und der **nachfolgende** `commit`
    scheitert an ihr. Der Fehler entsteht also zwischen den beiden Schritten, die diese
    Funktion macht — und genau dort wird er behandelt.

    **Warum genau einmal.** Eine Schleife würde einen echten, dauerhaften Fehler in eine
    Wartezeit verwandeln und ihn am Ende trotzdem melden. Der Fall, den wir kennen, ist
    nach einem Räumen behoben; jeder andere gehört gemeldet statt wiederholt.

    Rückgabe: `(ok, fehlertext, wiederholt)`.
    """
    def lauf():
        add = subprocess.run(["git", "-C", repo, "add", "--", rel], capture_output=True,
                             text=True, encoding="utf-8", errors="replace")
        commit = subprocess.run(
            ["git", "-C", repo] + COMMIT_IDENTITAET + ["commit", "-m", meldung],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        ok = not (add.returncode or commit.returncode)
        return ok, (add.stderr + commit.stderr).strip()

    ok, fehler = lauf()
    if ok:
        return True, "", False
    # Der Aufruf ist eingefasst, obwohl `_entsperre` selbst schon fängt: die Zusicherung
    # lautet, dass eine **scheiternde Reparatur** nie schlimmer ist als keine. Wer sie
    # ersetzt (Test, Fork, späterer Umbau), soll diese Zusicherung nicht brechen können.
    try:
        geraeumt = _entsperre(repo)
    except Exception:
        geraeumt = 0
    if not geraeumt:
        return False, fehler, False
    ok, fehler2 = lauf()
    return ok, fehler2, True


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

    **SWR-126 (pm/T-0059): ab jetzt eine Sicht auf `beitraege`, kein eigener Leser.**
    Zwei Stellen, die dieselbe Datei verschieden zerlegen, sind B033 — und B054 ist der
    Beleg, was das kostet. Die Zusage dieser Funktion bleibt unverändert: zwei Blöcke,
    der zweite mit **allem** darunter, damit die Chat-Ansicht (`app.js`: `if (b.antwort)`)
    weiterarbeitet, solange `pm/T-0060` die Verlaufsansicht nicht gebaut hat.
    """
    liste_ = beitraege(body)
    team = [b for b in liste_ if not b["ist_erstbeitrag"]]
    if not team:
        return body.strip(), "", ""
    # Der erste Beitragskopf trennt; darunter bleibt alles zusammen (Zusage s. o.).
    koepfe = [m for m in JEDE_H2.finditer(body) if _ist_beitragskopf(m.group("titel"))]
    erster = koepfe[0]
    return (body[:erster.start()].strip(), body[erster.end():].strip(),
            team[0]["zeit"])


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
    # SWR-126: der Verlauf zusätzlich zu den beiden Blöcken. Kein Ersatz — `pm/T-0060`
    # baut die Ansicht darauf; bis dahin liest `app.js` weiter `nachricht`/`antwort`.
    verlauf = beitraege(body)
    for b in verlauf:
        if b["ist_erstbeitrag"]:
            b["absender"] = felder.get("von", "?")
            b["zeit"] = felder.get("zeit", "")
    return {"id": os.path.splitext(os.path.basename(pfad))[0],
            "von": felder.get("von", "?"), "zeit": felder.get("zeit", ""),
            "status": felder.get("status", "offen"),
            "nachricht": nachricht, "antwort": antwort,
            "antwort_datum": antwort_datum,
            "beitraege": verlauf}


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


def _beitrag_anhaengen(repo, verz, projekt, brief_id, text, von):
    """SWR-126: einen Beitrag an einen bestehenden Brief hängen. Siehe `sende`.

    Die ID wird geprüft, bevor irgendetwas geschrieben wird — und **nicht** durch
    Zusammensetzen von Pfaden aus Nutzereingabe. `N-\\d{4}` ist die einzige zulässige
    Form; alles andere wird abgelehnt, statt einen Pfad daraus zu bauen (ein `..` in
    einer ID darf nie ein Verzeichnis verlassen).
    """
    if not re.fullmatch(r"N-\d{4}", brief_id):
        raise BriefkastenFehler(400, f"Keine gültige Brief-Kennung: {brief_id!r}")
    pfad = os.path.join(verz, f"{brief_id}.md")
    if not os.path.isfile(pfad):
        raise BriefkastenFehler(404, f"Brief {brief_id} gibt es nicht in {projekt}")
    with open(pfad, encoding="utf-8") as f:
        alt = f.read()
    zeit = datetime.now(timezone.utc).isoformat(timespec="seconds")
    kopf = BEITRAG_FORMAT % (von, zeit)
    neu, status_geaendert = _status_auf_offen(alt)
    neu = neu.rstrip("\n") + f"\n\n{kopf}\n\n{text}\n"
    with open(pfad, "w", encoding="utf-8", newline="\n") as f:
        f.write(neu)
    rel = os.path.relpath(pfad, repo)
    ok, fehler, _wiederholt = _verbuche(
        repo, rel, f"Briefkasten {brief_id}: weiterer Beitrag vom Menschen"
                   + (" (Status zurück auf offen)" if status_geaendert else ""))
    if not ok:
        # Dieselbe Ehrlichkeit wie in `sende` (SWR-121): der Beitrag steht auf der
        # Platte, bevor Git läuft. „Nicht verbucht" ist nicht „verloren".
        raise BriefkastenFehler(503,
            f"Dein Beitrag zu {brief_id} ist GESPEICHERT — aber noch nicht in Git "
            f"verbucht. Bitte NICHT erneut senden; die nächste Routine-Session nimmt "
            f"ihn mit. Ursache: " + fehler[:300])
    return {"brief": brief_id, "projekt": projekt, "zeit": zeit,
            "beitrag": True, "status_zurueckgesetzt": status_geaendert}


def _status_auf_offen(text):
    """Frontmatter-Status auf `offen` zurücksetzen (SWR-126, DoD 3 von pm/T-0059).

    **Ohne diesen Schritt wäre der CR schädlich statt nützlich**, und das ist keine
    Vorsicht, sondern gemessen: `offene()` trägt die Preflight-Zeile
    `[pm] BRIEFKASTEN: N offene(r) Brief(e) — zuerst beantworten!` und die
    Cockpit-Kachel. Ein Beitrag an einem bereits `beantwortet`-en Brief würde von
    **keiner** Session gesehen — der Auftraggeber hätte geschrieben, das System hätte
    es angenommen, und niemand hätte es gelesen. Das ist B038 in seiner teuersten
    Form: eine Zusage, die nur aussieht wie eine.

    Gibt `(neuer_text, geaendert)` zurück. Fehlt das Feld, wird nichts erfunden —
    `status` ist Pflicht im Format, und ein fehlendes Feld ist ein anderer Fehler.
    """
    neu, n = re.subn(r"(?m)^status:[ \t]*\S.*$", "status: offen", text, count=1)
    return neu, bool(n) and neu != text


def sende(root, projekt, text, von="E. John", brief=None):
    """SWR-050: Brief als Datei + sofortiger Commit. Gibt Brief-ID zurück.

    **SWR-126 (pm/T-0059, Brief pm/N-0031): mit `brief="N-0031"` wird angehängt**
    statt neu angelegt — der Wunsch des Auftraggebers, *„auf meine Fragen und deine
    Antworten direkt weiter zu kommentieren"*. Fehlt `brief`, bleibt alles wie zuvor;
    der Bestandspfad ist unberührt.

    Zwei Dinge passieren dabei **im selben Commit** wie der neue Beitrag: der Text wird
    angehängt **und** `status` geht auf `offen` zurück. Getrennte Commits wären zwei
    Zustände, von denen einer ohne den anderen sichtbar werden kann — dieselbe Regel wie
    bei SWR-124 (ausgelagerter Volltext im Commit seiner Zeile).

    Dass hier immer der **Mensch** schreibt, ist keine Annahme: `COMMIT_IDENTITAET` steht
    fest auf „Mensch via Briefkasten", dies ist der HMI-Schreibpfad. Das Team antwortet,
    indem es die Datei bearbeitet — nicht über diese Funktion. Deshalb wird der Status
    unbedingt zurückgesetzt und nicht an einer Absenderprüfung aufgehängt, die sich
    fälschen ließe.
    """
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
    if brief is not None:
        return _beitrag_anhaengen(repo, verz, projekt, str(brief).strip(), text, von)
    os.makedirs(verz, exist_ok=True)
    nummern = [int(m.group(1)) for n in os.listdir(verz)
               if (m := re.fullmatch(r"N-(\d{4})\.md", n))]
    brief_id = f"N-{(max(nummern) + 1 if nummern else 1):04d}"
    zeit = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pfad = os.path.join(verz, f"{brief_id}.md")
    with open(pfad, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"---\nvon: {von}\nzeit: {zeit}\nstatus: offen\n---\n\n{text}\n")
    rel = os.path.relpath(pfad, repo)
    # SWR-123 (pm/T-0055 Teil 2): Sperre räumen und EINMAL wiederholen, bevor gemeldet
    # wird. Damit tritt der Fall, den der Auftraggeber gemeldet hat, für ihn gar nicht
    # mehr auf; die ehrliche Meldung aus SWR-121 bleibt für alles, was danach noch
    # scheitert.
    ok, fehler, _wiederholt = _verbuche(
        repo, rel, f"Briefkasten {brief_id}: Nachricht vom Menschen")
    if not ok:
        # SWR-121 (pm/T-0055, Brief pm/N-0039): Die Nachricht steht zu diesem Zeitpunkt
        # BEREITS auf der Platte — sie wird oben geschrieben, bevor Git überhaupt läuft.
        # Scheitert der Commit, ist sie also gespeichert und nur nicht verbucht.
        #
        # ⚠ Die alte Meldung sagte nur „Git-Commit fehlgeschlagen" samt Git-Rohtext. Für
        # den Leser liest sich das wie „deine Nachricht ist weg" — und das ist die
        # falsche Hälfte der Wahrheit. Der Auftraggeber hat es am 2026-08-17 gemeldet und
        # sich die richtige Hälfte selbst erschlossen („wird aber trotzdem gespeichert").
        # Am Bestand belegt: `pm/N-0038` hat nie einen eigenen Commit bekommen und wurde
        # erst zwei Stunden später von einem fremden Commit mitgenommen; `pm/N-0039` —
        # die Meldung über genau diesen Fehler — kam durch. Beide standen bis dahin
        # unverbucht in der Arbeitskopie, also in dem Zustand, den SWR-110 zum Befund
        # erklärt.
        #
        # Eine Fehlermeldung, die den Ausgang schlechter darstellt, als er ist, kostet
        # dasselbe wie eine, die ihn besser darstellt: Der Leser handelt am Sachverhalt
        # vorbei — hier, indem er die Nachricht ein zweites Mal schickt.
        raise BriefkastenFehler(503,
            f"Deine Nachricht ist GESPEICHERT ({brief_id}) — aber noch nicht in Git "
            f"verbucht. Bitte NICHT erneut senden; die nächste Routine-Session nimmt sie "
            f"mit. Ursache: " + fehler[:300])
    return {"brief": brief_id, "projekt": projekt, "zeit": zeit}
