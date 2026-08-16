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
from datetime import datetime, timedelta

# Der Session-Takt aus p0/D027 bzw. pm/D004: die Routine-Session läuft alle 30 Minuten.
TAKT_MINUTEN = 30
# Ab wann die Kachel „seit HH:MM keine Session" sagt (T-0040 DoD 2).
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


def _commit_zeiten(root, projekt=QUELLE_PROJEKT, datei=QUELLE_DATEI):
    """Commit-Zeitpunkte der Agenda-Datei, neueste zuerst (git, frisch je Aufruf)."""
    repo = os.path.join(root, projekt)
    try:
        lauf = subprocess.run(["git", "-C", repo, "log", "--format=%cI", "--", datei],
                              capture_output=True, text=True, timeout=10)
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
    veraltet, hinweis = stille(letzter, jetzt)
    return {"text": wichtigstes(text),
            "stand": letzter,
            "fortschreibungen_heute": fortschreibungen_heute(zeiten, jetzt),
            "veraltet": veraltet,
            "hinweis": hinweis,
            "quelle": "%s/%s" % (projekt, datei)}
