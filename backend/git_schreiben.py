#!/usr/bin/env python3
"""Der eine Schreibweg nach Git (SWR-134, platform/T-0015).

**Warum es diese Datei gibt.** Auf dem Cowork-Mount hinterlässt *jeder* Git-Aufruf eine
`.git/index.lock`, die Git selbst nicht mehr entfernen darf (`unlink` ist verboten,
`rename` erlaubt). Der **nächste schreibende** Aufruf im selben Repo scheitert daran mit
`fatal: Unable to create '.git/index.lock': File exists` — Exit 128.

SWR-123 hat genau dafür die Räumung gebaut, zweistufig (löschen, sonst wegbenennen), und
sie ist **richtig**. Was fehlte, war nicht der Rückfall auf `rename` — den gibt es seit
`pm/T-0023` — sondern die **Reichweite**: von acht Stellen, die in dieser Organisation
`git commit` aufrufen, benutzte genau **eine** sie (der Briefkasten). Die anderen sieben
liefen in denselben Fehler, für den die Reparatur schon im Haus lag.

> **Eine Reparatur, die nur ihr eigener Fundort benutzt, ist eine Reparatur des Fundorts
> und nicht des Fehlers.**

Das ist dieselbe Gestalt wie SWR-131 („eine Antwort auf *ist das entschieden?*, alle
Leser fragen dort") — hier: **ein Schreibweg, alle Schreiber gehen durch ihn**. Und wie
dort wird „alle" von einem **Zähltest** gehalten und nicht von einer Zusage: der Test
`test_git_schreibweg.py` zählt die Stellen, die `commit` selbst zusammenbauen, und
verlangt, dass es genau diese Datei ist.

**Warum in `backend/` und nicht in `scripts/`.** `preflight` (in `scripts/`) importiert
`board` **und** `backend`; ein Modulimport von `preflight` in `backend/*.py` schlösse
einen Zyklus. Diese Datei ist deshalb ein **Blatt**: sie importiert oben nichts aus der
Organisation, und den Import von `preflight` macht sie **in der Funktion** — dieselbe
Begründung, die schon in `briefkasten._entsperre` stand, jetzt an einer Stelle statt in
acht. `backend/` ist der Ort, weil alle acht Aufrufer es erreichen: die
`backend`-Module über `from . import`, `scripts/` und `orchestrator/` über den
`platform`-Pfad, den sie ohnehin schon setzen. Ein Lademechanismus je Aufrufer wäre
B033 in der Form, gegen die dieses Ticket gerichtet ist.

**Was diese Datei ausdrücklich NICHT tut.** Sie räumt nicht vorsorglich vor jedem Aufruf.
Geräumt wird erst, **nachdem** ein Versuch gescheitert ist — ein Lock, das ein *aktiver*
Git-Prozess hält, beiseite zu benennen wäre schlimmer als der Fehler (DoD 2 aus
`platform/T-0015`). Die Voraussetzung „kein Git-Prozess läuft" prüft `preflight`
weiterhin selbst; sie wird hier nicht kopiert (B033).

⚠⚠ **SWR-163 (`platform/T-0021`, Sprint 24): geräumt wird ab jetzt AUCH NACH DEM EIGENEN
GELUNGENEN AUFRUF** — siehe :func:`_nachraeumen`. Das ist kein Widerspruch zu dem Absatz
darüber, sondern seine Fortsetzung mit der Messung aus Sprint 21:

> **Nicht der scheiternde Aufruf hinterlässt die Sperre, sondern der gelingende. Git
> beendet einen SCHREIBENDEN Indexvorgang, indem es `index.lock` über `index` umbenennt —
> das geht auf diesem Mount durch. Einen bloß LESENDEN Refresh (`git status`) beendet es,
> indem es die Sperre LÖSCHT, und das ist hier verboten. Der harmlose Lesevorgang
> hinterlässt die Sperre, an der der nächste Aufruf stirbt.**

Verboten bleibt, was verboten war: das Räumen **vor** dem ersten Git-Aufruf. Dort gibt es
keinen Nachweis darüber, wem die Sperre gehört. Nach dem eigenen Aufruf gibt es zwei:
dieser Aufruf ist zurück, und `preflight.git_prozess_aktiv` sagt, ob sonst noch einer läuft.
"""
import os
import subprocess
import sys

#: Vorgabe-Identität für Commits des Teams (D006). Wer als Mensch schreibt, übergibt
#: seine eigene — der Briefkasten und die Inbox tun genau das.
TEAM_IDENTITAET = ["-c", "user.name=ASPICE-Team", "-c", "user.email=team@aspice.local"]

#: Git sagt „nichts zu committen" auf **stdout**, nicht auf stderr. Wer nur stderr liest,
#: hält einen leeren Commit für einen Fehler (der Fall aus `teams.py`).
LEERTEXTE = ("nothing to commit", "nichts zu committen")


class Verbuchung:
    """Ergebnis eines Schreibversuchs — bewusst ein Objekt und kein Tupel.

    `stderr` und `stdout` bleiben **getrennt**: der Briefkasten meldet dem Menschen nur
    `stderr` (SWR-121), `teams.py` muss „nothing to commit" aus `stdout` erkennen. Beides
    in einen String zu falten hieße, eine der beiden Fragen nicht mehr beantworten zu
    können — zwei Fragen, ein Feld, das ist B033 rückwärts.
    """

    __slots__ = ("ok", "stderr", "stdout", "wiederholt", "geraeumt", "nachgeraeumt")

    def __init__(self, ok, stderr="", stdout="", wiederholt=False, geraeumt=0,
                 nachgeraeumt=0):
        self.ok = bool(ok)
        self.stderr = stderr or ""
        self.stdout = stdout or ""
        self.wiederholt = bool(wiederholt)
        self.geraeumt = int(geraeumt)
        #: SWR-163: wie viele Sperren der **eigene, gelungene** Aufruf hinterlassen hat und
        #: hinter sich weggeräumt wurden. ⚠ Ein **eigenes Feld** und nicht `geraeumt`
        #: mitbenutzt: `geraeumt` beantwortet *„wie viel musste weg, damit ich überhaupt
        #: durchkam"*, dies hier *„wie viel habe ich für den nächsten hinterlassen"*. Zwei
        #: Fragen in ein Feld zu falten hieße, eine von beiden nicht mehr beantworten zu
        #: können — dieselbe Begründung, aus der `stderr` und `stdout` getrennt bleiben.
        self.nachgeraeumt = int(nachgeraeumt)

    @property
    def fehler(self):
        """Der Text, den ein Mensch zu sehen bekommt (stderr **und** stdout)."""
        return (self.stderr + self.stdout).strip()

    @property
    def nichts_zu_committen(self):
        """True, wenn Git nur meldet, dass es nichts zu tun gab.

        Das ist **kein** Fehler: ein Schreibweg, der eine unveränderte Datei speichert,
        hat seine Zusage erfüllt. Wer das als Fehler behandelt, meldet dem Menschen einen
        Ausfall, wo nichts ausgefallen ist — der Befund hinter SWR-121, eine Etage tiefer.
        """
        text = (self.stdout + self.stderr).lower()
        return any(t in text for t in LEERTEXTE)

    def __repr__(self):  # pragma: no cover — Diagnose
        return (f"Verbuchung(ok={self.ok}, wiederholt={self.wiederholt}, "
                f"geraeumt={self.geraeumt}, nachgeraeumt={self.nachgeraeumt})")


def _lade_preflight():
    """Das Räummodul der Organisation — oder `None`, wenn es nicht erreichbar ist.

    Der Pfad wird **relativ zu dieser Datei** bestimmt und nicht aus dem Zustand des
    Aufrufers geraten; die Begründung steht in :func:`entsperre` (SWR-143).
    """
    try:
        hier = os.path.dirname(os.path.abspath(__file__))
        skripte = os.path.normpath(os.path.join(hier, "..", "scripts"))
        if skripte not in sys.path:
            sys.path.insert(0, skripte)
        import preflight as _preflight
        return _preflight
    except Exception:
        return None


def entsperre(repo):
    """Verwaiste Git-Sperren dieses Repos wegräumen. Rückgabe: Anzahl (0 = nichts/geht nicht).

    **Kein zweiter Räummechanismus** (B033). Die Organisation hat seit Sprint 5 genau
    einen — `preflight.finde_lock_artefakte` / `entferne_artefakte`, zweistufig: erst
    `os.remove`, bei `OSError` **umbenennen** nach `.git/verwaiste-locks/`. Auf diesem
    Mount ist genau das der Unterschied zwischen „geht" und „geht nicht".

    Schlägt der Import fehl, ist das **kein** Fehler des Schreibwegs: dann bleibt es beim
    alten Verhalten, also bei der ehrlichen Meldung. Eine scheiternde Reparatur darf nie
    schlimmer sein als keine.

    ⚠⚠ **Gemessener Fehler dieser Funktion, gefunden in Sprint 16 (SWR-143).** Bis dahin
    stand hier ``skripte = os.path.dirname(__file__)`` — und das ist ``backend/``, nicht
    ``scripts/``. ``import preflight`` scheiterte also, ``entsperre`` gab **0** zurück, und
    die Räumung von SWR-134 lief **gar nicht** — es sei denn, der Aufrufer hatte
    ``scripts/`` zufällig schon im Pfad. Genau das taten `board`, `preflight` und die
    Tests, weshalb es nirgends aufgefallen ist.

    > **Die Reparatur wirkte überall dort, wo der Aufrufer sie mitgebracht hat — also
    > genau dort nicht, wo SWR-134 sie hinbringen wollte.**

    Der Pfad wird deshalb **relativ zu dieser Datei** bestimmt (`../scripts`) und nicht
    aus dem Zustand des Aufrufers geraten.
    """
    _preflight = _lade_preflight()
    if _preflight is None:
        return 0
    try:
        locks = _preflight.finde_lock_artefakte(repo)
        if not locks:
            return 0
        entfernt, geparkt, _kaputt = _preflight.entferne_artefakte(locks)
        return len(entfernt) + len(geparkt)
    except Exception:
        return 0


def _nachraeumen(repo, entsperren=None):
    """SWR-163: die Sperre wegräumen, die der **eigene, gerade beendete** Aufruf liegen ließ.

    Rückgabe: Anzahl (0 = nichts da, kein Nachweis, oder Räumung nicht möglich).

    ⚠⚠ **Warum das nicht das verworfene „vorsorgliche Räumen" ist.** `platform/T-0015`
    DoD 2 verbot, **vor** einem Git-Aufruf zu räumen — dort ist über die vorgefundene
    Sperre nichts bekannt, und eine, die ein *laufender* Prozess hält, beiseitezubenennen
    ist schlimmer als sie stehen zu lassen. Hier ist die Lage umgekehrt: der eigene Aufruf
    ist **zurück**. Was jetzt liegt, ist entweder seins oder gehört jemandem, der noch
    arbeitet — und genau diese zweite Möglichkeit fragt die Funktion ab, mit dem
    **vorhandenen** Mechanismus der Organisation (`preflight.git_prozess_aktiv`) und nicht
    mit einem zweiten (B033).

    ⚠ **Diese Funktion ruft KEIN git auf.** Das ist eine Auflage aus SWR-159: ein Werkzeug,
    das an der Nebenläufigkeit arbeitet und dabei selbst eine Sperre erzeugt, ist sein
    eigener Schadensfall — der erste Entwurf der Uhrenprobe ist in Sprint 23 genau daran
    rot geworden (`test_die_messung_ruft_KEIN_git_auf`, SWR-134). `git_prozess_aktiv` liest
    die **Prozessliste** (`tasklist`/`ps`), nicht das Repo.

    ⚠ **Warum das überhaupt nötig ist, obwohl der Rückfall in
    :func:`_einmal_wiederholen` seit SWR-134 existiert.** Der Rückfall repariert den
    Aufruf, der **gescheitert** ist. Gemessen in Sprint 21 hinterlässt aber der Aufruf, der
    **gelingt**, die Sperre: `git status --porcelain` kommt mit Exit 0 zurück und lässt
    `index.lock` liegen, weil Git einen lesenden Refresh durch **Löschen** der Sperre
    beendet und Löschen auf diesem Mount verboten ist. Der Rückfall verlegt die Kosten
    damit auf den **nächsten** Aufrufer, und der sieht eine Fehlermeldung, die nach einem
    fremden Prozess aussieht.
    """
    _preflight = _lade_preflight()
    if _preflight is None:
        return 0
    try:
        if _preflight.git_prozess_aktiv():
            return 0
    except Exception:
        # Im Zweifel nichts anfassen: dieselbe Richtung, die `git_prozess_aktiv` selbst
        # bei einem Fehler wählt („vorsichtshalber als Git läuft gewertet").
        return 0
    try:
        return int((entsperren or entsperre)(repo) or 0)
    except Exception:
        return 0


def _einmal_wiederholen(versuch, repo, entsperren):
    """`versuch()` ausführen; bei Fehlschlag **einmal** entsperren und wiederholen.

    `versuch` liefert `(ok, stderr, stdout)`. Rückgabe: :class:`Verbuchung`.

    Diese Funktion ist die **eine** Stelle, an der „einmal und nicht in einer Schleife"
    steht. Sowohl :func:`verbuche` (add+commit als Paar) als auch :func:`ruf` (ein
    einzelner Git-Aufruf) gehen durch sie — zwei Fassungen derselben Regel wären genau
    das Muster, gegen das dieses Modul gebaut ist.
    """
    ok, err, out = versuch()
    if ok:
        # SWR-163: hinter sich aufräumen, nicht vor dem nächsten.
        return Verbuchung(True, err, out, wiederholt=False,
                          nachgeraeumt=_nachraeumen(repo, entsperren))
    # Eingefasst, obwohl `entsperre` selbst schon fängt: die Zusicherung lautet, dass eine
    # **scheiternde Reparatur** nie schlimmer ist als keine. Wer sie ersetzt (Test, Fork,
    # späterer Umbau), soll diese Zusicherung nicht brechen können.
    try:
        geraeumt = (entsperren or entsperre)(repo)
    except Exception:
        geraeumt = 0
    if not geraeumt:
        return Verbuchung(False, err, out, wiederholt=False, geraeumt=0)
    ok2, err2, out2 = versuch()
    return Verbuchung(ok2, err2, out2, wiederholt=True, geraeumt=geraeumt,
                      # ⚠ Auch der geglückte ZWEITE Versuch hinterlässt seine Sperre. Ohne
                      # diese Zeile wäre die Reparatur genau an den Läufen wirkungslos, die
                      # sie am nötigsten haben.
                      nachgeraeumt=_nachraeumen(repo, entsperren) if ok2 else 0)


def ruf(repo, args, identitaet=None, entsperren=None):
    """**Ein** Git-Aufruf mit derselben Absicherung wie :func:`verbuche`.

    Für Aufrufer, die nicht das Paar `add`+`commit` machen, sondern einzelne Kommandos
    (der Orchestrator-Tick: `checkout`, `add -A`, `commit`). ⚠ Auch **lesende** Aufrufe
    gehören hier durch: auf diesem Mount hinterlässt bereits ein `git status` eine Sperre,
    an der der nächste schreibende Aufruf scheitert — gemessen in Sprint 14. Wer nur die
    schreibenden absichert, sichert die falsche Hälfte.

    Rückgabe: :class:`Verbuchung` (`stdout` trägt die Ausgabe des Kommandos).
    """
    befehl = ["git", "-C", repo] + list(identitaet or []) + list(args)

    def versuch():
        p = subprocess.run(befehl, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        return p.returncode == 0, p.stderr, p.stdout

    return _einmal_wiederholen(versuch, repo, entsperren)


def _lauf(repo, pfade, meldung, identitaet, entsperren=None):
    """`add` + `commit` als Paar — mit der Räumung **zwischen** beiden (SWR-139).

    ⚠⚠ **Nebenbefund an SWR-134, gemessen in Sprint 15.** Der Rückfall in
    :func:`_einmal_wiederholen` ist gegen die Sperre eines **fremden** Laufs gebaut.
    Gegen die **eigene** hilft er nicht: auf diesem Mount hinterlässt das eigene `add`
    eine `index.lock`, an der das folgende `commit` scheitert — und die Wiederholung
    fährt das **Paar** noch einmal, erzeugt die Sperre also erneut. Drei Commits von
    Sprint 15 quittierten `FEHLER | geraeumt: 19` und gingen erst nach einem getrennten
    Lock-Lauf durch.

    > **Der Rückfall ist gegen die Sperre eines fremden Laufs gebaut. Gegen die eigene
    > hilft er nicht, weil er sie zwischen seinen beiden Hälften selbst erzeugt.**

    ⚠ Hier **vor** einem Fehlschlag zu räumen sieht wie das vorsorgliche Räumen aus, das
    `platform/T-0015` DoD 2 ausdrücklich verworfen hat — und ist es nicht. Der
    Unterschied ist ein **Nachweis**: ein `add`, das **gelingt**, belegt, dass beim
    Start keine Sperre lag; die danach liegende ist damit nachweislich die eigene.
    Genau deshalb wird nach einem **gescheiterten** `add` hier nicht geräumt (dann
    gehört die Sperre womöglich einem laufenden Prozess), und ohne `pfade` gibt es kein
    `add` und also auch keinen Nachweis.
    """
    add_ok, add_err, add_out = True, "", ""
    if pfade:
        add = subprocess.run(["git", "-C", repo, "add", "--"] + list(pfade),
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace")
        add_ok, add_err, add_out = add.returncode == 0, add.stderr, add.stdout
        if add_ok:
            # Eingefasst wie in `_einmal_wiederholen`: eine scheiternde Reparatur darf
            # nie schlimmer sein als keine.
            try:
                (entsperren or entsperre)(repo)
            except Exception:
                pass
    commit = subprocess.run(["git", "-C", repo] + list(identitaet) + ["commit", "-m", meldung],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace")
    return (add_ok and commit.returncode == 0,
            (add_err + commit.stderr), (add_out + commit.stdout))


def verbuche(repo, pfade, meldung, identitaet=None, entsperren=None):
    """`git add` + `git commit`; bei Fehlschlag **einmal** entsperren und wiederholen.

    Rückgabe: :class:`Verbuchung`.

    `entsperren` ist die **Naht für die Gegenprobe** und keine Konfiguration: die Tests
    zu SWR-123 setzen dort eine Reparatur ein, die scheitert oder wirft, und prüfen, dass
    der Schreibweg dann *genau* die ehrliche Meldung von vorher liefert. Ohne diesen Haken
    ließe sich die Zusicherung „eine scheiternde Reparatur ist nie schlimmer als keine"
    nicht prüfen — und eine Zusicherung ohne Prüfung ist die Lage aus SWR-125.

    **Warum genau einmal und keine Schleife.** Eine Schleife verwandelt einen echten,
    dauerhaften Fehler in eine Wartezeit und meldet ihn am Ende trotzdem. Der Fall, den
    wir gemessen haben, ist nach *einem* Räumen behoben; jeder andere gehört gemeldet.

    **Warum erst nach dem Fehlschlag geräumt wird.** Vorsorgliches Räumen wäre bequemer
    und falsch: eine Sperre, die ein *laufender* Git-Prozess hält, beiseite zu benennen
    ist schlimmer als sie stehen zu lassen. Erst der gescheiterte Versuch zeigt, dass die
    Sperre niemandem gehört, den dieser Aufruf stören würde.

    `pfade` darf leer sein — dann wird nur committet (der Fall „schon gestaget").
    """
    identitaet = list(identitaet if identitaet is not None else TEAM_IDENTITAET)
    pfade = [pfade] if isinstance(pfade, str) else list(pfade or [])
    return _einmal_wiederholen(lambda: _lauf(repo, pfade, meldung, identitaet, entsperren),
                               repo, entsperren)
