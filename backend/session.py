"""BCK-Session (SWR-102, pm/T-0040 aus den Briefen pm/N-0032/N-0033).

Der Auftraggeber will nach jedem geplanten Lauf **in Mission Control** lesen, was
passiert ist. Die Zusammenfassung existiert bereits — jede Routine-Session schreibt
sie in `pm/management/session-agenda.md`, ganz oben als Block „Das Wichtigste"
(max. fünf Zeilen seit B050). Kein HMI-Endpunkt hat sie bisher ausgeliefert.

Dieses Modul erzeugt **keinen** zweiten Text. Es liest dieselbe Datei, die die
Session ohnehin schreibt (T-0040 DoD 3; eine zweite Quelle wäre B033).

**Der Zeitstempel kommt aus dem Commit, nicht aus dem Text** (T-0040 DoD 1/Befund c).
Im Block steht zwar eine Zeile „Stand: …", aber sie ist Text: fällt der geplante Lauf
aus, bleibt die Datei stehen und ihr eigener Zeitstempel behauptet weiter Frische.
Deshalb liefert `stand()` die Überschriftzeile bewusst **nicht** mit aus — die einzige
Zeitangabe der Kachel stammt aus der Git-Historie (B038).

Kein Zustand, kein Cache (SWR-024): jede Anfrage liest frisch aus Datei und Git.
"""
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import sprint_register  # noqa: E402  — SWR-153: der Sprintzähler ist die EINE Quelle

# RÜCKFALL-Takt, wenn das Register keinen nennt (p0/D027 bzw. pm/D004: damals 30 Min).
#
# ⚠⚠ SWR-156 (platform/T-0025): diese Zahl war bis Sprint 22 die EINZIGE Quelle der
# Kachel — und sie war seit dem 17.08. **falsch**. Der Takt der Routine steht seither auf
# **60** Minuten und wird je Lauf im Register mitgeschrieben (`takt_min`);
# `sprint_register.TAKT_MIN_STANDARD` nennt ebenfalls 60. Zwei Module trugen damit zwei
# verschiedene Werte für denselben Sachverhalt, und die Kachel meldete Stille nach
# 2x30 statt nach 2x60 Minuten. Gemerkt hat es niemand, weil beide Werte für sich
# plausibel aussahen — B033 in seiner leisesten Gestalt.
#
# Gelesen wird ab jetzt das **Register** (`sprint_register.takt_minuten`), weil dort der
# Takt als Tatsache je Lauf steht und nicht als Annahme im Quelltext. Diese Konstante
# bleibt ausschließlich der Rückfall für „kein Register lesbar".
TAKT_MINUTEN = 30
# Ab wann die Kachel „seit HH:MM keine Session" sagt (T-0040 DoD 2) — und ab wann der
# Preflight eine Pause zwischen zwei Läufen einen Befund nennt (SWR-156). **Dieselbe**
# Zahl an beiden Stellen: Kachel und Preflight dürfen über denselben Sachverhalt nicht
# Verschiedenes sagen.
STILLE_TAKTE = 2

QUELLE_PROJEKT = "pm"
QUELLE_DATEI = "management/session-agenda.md"

# Die Überschrift wird an ihrem Anfang erkannt, nicht an ihrer vollen Fassung — der
# Zusatz in Klammern ändert sich je Session (Lehre L-2026-08-16h/B054: wo ein Parser
# ein Format liest, das andere Teile des Systems schreiben, darf er nicht auf den
# Wortlaut zielen).
WICHTIGSTES_KOPF = re.compile(r"(?m)^##\s+Das Wichtigste\b.*$")
# Ende des Blocks: die nächste Überschrift beliebiger Ebene oder ein Trennstrich.
BLOCK_ENDE = re.compile(r"(?m)^(?:#{1,6}\s|---\s*$)")


def wichtigstes(text):
    """Den Block „Das Wichtigste" aus dem Agenda-Text schneiden (rein, ohne IO).

    Zurück kommt **nur der Rumpf**, nicht die Überschriftzeile: die trägt ein
    „(Stand …)" aus dem Text, und genau diese Angabe darf die Kachel nicht als
    Zeitstempel verwenden (T-0040 Befund c). Findet sich der Block nicht, ist das
    Ergebnis leer — die Kachel sagt dann, dass sie nichts gefunden hat, statt
    ersatzweise irgendeinen Anfang der Datei zu zeigen.
    """
    m = WICHTIGSTES_KOPF.search(text or "")
    if not m:
        return ""
    rest = text[m.end():]
    ende = BLOCK_ENDE.search(rest)
    return (rest[:ende.start()] if ende else rest).strip()


def _iso(zeit):
    """ISO-8601 mit Zeitzonen-Offset (git %cI) in ein datetime; None bei Unsinn."""
    try:
        return datetime.fromisoformat((zeit or "").strip())
    except ValueError:
        return None


def stille(letzter_commit, jetzt, takt_minuten=TAKT_MINUTEN, takte=STILLE_TAKTE):
    """Rein und testbar: liegt der letzte Lauf länger zurück als `takte` Takte?

    Rückgabe `(veraltet, hinweis)`. Der Hinweis ist der Satz, den der Auftraggeber
    wirklich braucht, wenn der geplante Task ausgefallen ist — „seit HH:MM keine
    Session". Eine Kachel, die bei ausgefallenem Lauf einfach den alten Stand
    zeigt, ist die stille Falschaussage aus B038.

    Ohne lesbaren Commit-Zeitpunkt gilt der Stand als veraltet, nicht als frisch:
    im Zweifel lieber „unbekannt" melden als Frische behaupten.
    """
    a = _iso(letzter_commit)
    if a is None or jetzt is None:
        return True, "kein lesbarer Zeitpunkt der letzten Session"
    if a.tzinfo is not None and jetzt.tzinfo is None:
        jetzt = jetzt.replace(tzinfo=a.tzinfo)
    if a.tzinfo is None and jetzt.tzinfo is not None:
        a = a.replace(tzinfo=jetzt.tzinfo)
    if jetzt - a <= timedelta(minutes=takt_minuten * takte):
        return False, ""
    return True, "seit %s keine Session" % a.strftime("%H:%M")


def takt(root):
    """Der Takt der Routine in Minuten — aus dem **Register**, nicht aus dem Quelltext.

    SWR-156: `sprint_register.takt_minuten()` liest den Wert, den der letzte Lauf
    tatsächlich mitgeschrieben hat. `TAKT_MINUTEN` ist nur noch der Rückfall, wenn das
    Register nicht lesbar ist — und genau als solcher benannt, weil er drei Tage lang
    unbemerkt eine andere Zahl trug als das Register.
    """
    try:
        return int(sprint_register.takt_minuten(root))
    except Exception:
        return TAKT_MINUTEN


def pause_seit_letztem_lauf(root, jetzt=None, takte=STILLE_TAKTE):
    """SWR-156 (platform/T-0025, Brief `team-mail/N-0004`): wie lange war es still?

    Beantwortet die Frage, die **keine** bestehende Prüfung beantworten konnte:
    *ist der nächste Lauf jemals angefangen?* `sprint_register.nicht_beendete()`
    (SWR-136) prüft Läufe **ohne `ende`**, also solche, die mittendrin abbrachen — das
    ist eine Prüfung auf eine **Spur**. Ein Lauf, der ausfällt, hinterlässt keine Spur;
    er ist der einzige, der sich nicht selbst melden kann. Gemessen wird deshalb nicht
    der ausgefallene Lauf, sondern der **Abstand** zwischen dem letzten Ende und dem
    Anfang von jetzt — eine Größe, die auch dann existiert, wenn dazwischen nichts war.

    ⚠ **Keine zweite Zeitrechnung.** Ob die Pause zu lang ist, entscheidet `stille()` —
    dieselbe Funktion, die die Kachel „Letzte Session" seit SWR-102 benutzt. Der Takt
    kommt aus dem Register (`takt()`). Sagten Kachel und Preflight verschiedene Dinge
    über dieselbe Stille, wäre genau das der Fehler, den dieses Ticket beschreibt (B033).

    Rückgabe ist ein Wörterbuch und **nie** `None`; „nicht berechenbar" ist ein Feld und
    kein fehlender Wert:

    `minuten`        Pause in Minuten, oder `None`
    `unberechenbar`  warum `minuten` fehlt — im Klartext, nie stillschweigend 0
    `vielfaches`     Pause in Vielfachen des Takts (das, was der Auftraggeber liest)
    `befund`         True, wenn die Pause `takte` Takte überschreitet
    `ueberlappung`   True, wenn die Pause **negativ** ist (siehe unten)
    `ohne_ende`      Sprintnummern ohne `ende` vor dem Stichtag — für sie ist keine
                     Pause berechenbar, und das wird gesagt statt erfunden (SWR-136)

    ⚠ **Eine negative Pause ist ein eigener Fall und wird nicht auf 0 gekappt.** Gemessen
    über den Bestand (Sprint 22): von sieben berechenbaren Pausen ist **eine negativ** —
    Sprint 17 nennt einen Start (16:49) **vor** dem Ende von Sprint 16 (17:10). Die
    Zeitstempel des Registers stammen aus der Uhr des jeweils schreibenden Laufs, und
    mindestens einmal waren zwei dieser Uhren um 21 Minuten uneinig. Eine Prüfung, die
    Differenzen dieser Stempel liest, muss das **sagen** können; sie auf 0 zu klemmen
    machte den einzigen Beleg dafür unsichtbar.
    """
    jetzt = jetzt or datetime.now()
    ergebnis = {"letztes_ende": "", "letzter_nr": None, "bezug": "", "bezug_zeit": "",
                "minuten": None, "takt_min": takt(root), "takte": int(takte),
                "vielfaches": None, "befund": False, "hinweis": "",
                "unberechenbar": "", "ueberlappung": False, "ohne_ende": []}
    try:
        sprints = sprint_register.lies(root)
    except Exception:
        sprints = []
    if not sprints:
        ergebnis["unberechenbar"] = "Register nicht lesbar oder leer"
        return ergebnis

    # Der laufende Sprint ist die Zeile ohne `ende` am Ende des Registers. Läuft einer,
    # ist sein START der Bezugspunkt: die Pause ist dann die, die wirklich verstrichen
    # ist, und nicht die, die bis zum Aufruf dieser Funktion noch weiterläuft.
    laufend = sprints[-1] if not sprints[-1].get("ende") else None
    vorher = [e for e in sprints if e.get("ende")
              and (laufend is None or e["nr"] != laufend["nr"])]
    ergebnis["ohne_ende"] = [e["nr"] for e in sprints
                            if not e.get("ende")
                            and (laufend is None or e["nr"] != laufend["nr"])]
    if not vorher:
        ergebnis["unberechenbar"] = ("kein vorangegangener Sprint mit 'ende' im Register"
                                     + (" (Stichtag: ab Sprint %s)"
                                        % sprint_register.STICHTAG_ENDE_SPRINT))
        return ergebnis

    letzter = vorher[-1]
    ergebnis["letzter_nr"] = letzter["nr"]
    ergebnis["letztes_ende"] = str(letzter.get("ende") or "")
    if laufend is not None:
        ergebnis["bezug"] = "Start von Sprint %s" % laufend["nr"]
        ergebnis["bezug_zeit"] = str(laufend.get("start") or "")
    else:
        ergebnis["bezug"] = "jetzt (kein Sprint läuft)"
        ergebnis["bezug_zeit"] = jetzt.strftime("%Y-%m-%d %H:%M")

    a, b = _iso(ergebnis["letztes_ende"]), _iso(ergebnis["bezug_zeit"])
    if a is None or b is None:
        ergebnis["unberechenbar"] = "Zeitangabe im Register nicht lesbar"
        return ergebnis
    minuten = int(round((b - a).total_seconds() / 60.0))
    ergebnis["minuten"] = minuten
    ergebnis["vielfaches"] = round(minuten / float(max(1, ergebnis["takt_min"])), 2)
    if minuten < 0:
        ergebnis["ueberlappung"] = True
        ergebnis["hinweis"] = ("Start %s liegt VOR dem Ende von Sprint %s (%s)"
                               % (ergebnis["bezug_zeit"], letzter["nr"],
                                  ergebnis["letztes_ende"]))
        return ergebnis
    # ⚠ Die Entscheidung fällt in `stille()` und nicht hier — eine zweite
    # Schwellenrechnung wäre die zweite Antwort auf dieselbe Frage.
    veraltet, hinweis = stille(ergebnis["letztes_ende"], b,
                               takt_minuten=ergebnis["takt_min"], takte=takte)
    ergebnis["befund"] = bool(veraltet)
    ergebnis["hinweis"] = hinweis
    return ergebnis


def _commit_zeiten(root, projekt=QUELLE_PROJEKT, datei=QUELLE_DATEI):
    """Commit-Zeitpunkte der Agenda-Datei, neueste zuerst (git, frisch je Aufruf)."""
    repo = os.path.join(root, projekt)
    try:
        lauf = subprocess.run(["git", "-C", repo, "log", "--format=%cI", "--", datei],
                              capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return []
    if lauf.returncode:
        return []
    return [z.strip() for z in lauf.stdout.splitlines() if z.strip()]


def fortschreibungen_heute(zeiten, jetzt):
    """Wie oft die Agenda **heute** fortgeschrieben wurde (rein, ohne IO).

    Bewusst gezählt werden **Commits**, nicht Sessions — siehe Befund B056 und der
    DoD-Vermerk in `pm/T-0040`: eine Session schreibt die Agenda mehrfach (am 16.08.
    42 Commits auf rund 30 Läufe), und Commits über eine Zeitlücke zu Sessions zu
    bündeln unterschätzt nachweislich (16:35 → 16:51 sind 16 Minuten und trotzdem
    zwei Sessions). Eine Zahl, die sich wie eine Messung liest und eine Schätzung
    ist, wäre B027/B038. Gezählt wird deshalb das, was belegbar ist, und es heißt
    auch so.
    """
    if jetzt is None:
        return 0
    heute = jetzt.date()
    treffer = 0
    for z in zeiten:
        a = _iso(z)
        if a is not None and a.date() == heute:
            treffer += 1
    return treffer


def stand(root, jetzt=None, projekt=QUELLE_PROJEKT, datei=QUELLE_DATEI):
    """SWR-102: Was die letzte Session getan hat — für die Kachel im Cockpit.

    `text`      Block „Das Wichtigste" aus der Agenda (unverändert, kein zweiter Text)
    `stand`     Zeitpunkt des letzten **Commits** dieser Datei (nicht aus dem Text)
    `fortschreibungen_heute`  Zahl der Agenda-Commits des laufenden Tages
    `veraltet`/`hinweis`      „seit HH:MM keine Session", wenn zwei Takte still waren
    `sprint_nr` SWR-153: zu welchem Sprint dieser Lauf gehörte — aus dem **Register**
                über den **Commit**-Zeitpunkt, nie aus der Überschrift der Datei
    `quelle`    welche Datei gelesen wurde — damit die Kachel prüfbar bleibt
    """
    jetzt = jetzt or datetime.now().astimezone()
    pfad = os.path.join(root, projekt, *datei.split("/"))
    text = ""
    if os.path.isfile(pfad):
        try:
            with open(pfad, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            text = ""
    zeiten = _commit_zeiten(root, projekt, datei)
    letzter = zeiten[0] if zeiten else ""
    # SWR-156: der Takt kommt aus dem REGISTER. Bis Sprint 22 stand hier der
    # Vorgabewert 30 aus dem Quelltext, während das Register seit dem 17.08. 60 führt —
    # die Kachel meldete Stille nach einer statt nach zwei Stunden, und niemand hat den
    # Widerspruch gesehen, weil beide Zahlen für sich plausibel waren.
    veraltet, hinweis = stille(letzter, jetzt, takt_minuten=takt(root))
    return {"text": wichtigstes(text),
            "stand": letzter,
            "fortschreibungen_heute": fortschreibungen_heute(zeiten, jetzt),
            "veraltet": veraltet,
            "hinweis": hinweis,
            # SWR-153 (pm/N-0043 Punkt 1): die Sprintnummer des Laufs. Sie hängt am
            # **selben** Zeitstempel wie die Staleness-Aussage — an `letzter` und damit
            # am Commit. Damit können Zeit und Nummer der Kachel nicht auseinanderlaufen:
            # es ist eine Eingabe, nicht zwei.
            "sprint_nr": sprint_register.sprint_zu_zeit(root, letzter),
            "quelle": "%s/%s" % (projekt, datei)}
