"""Der eine Schreibweg nach Git (SWR-134, platform/T-0015).

**Was dieses Ticket zuerst korrigiert hat, ist seine eigene Ursachenaussage.** Der
Entwurf von `platform/T-0015` verlangte, die Räumung in SWR-123 solle bei
`PermissionError` auf **umbenennen** zurückfallen. Gemessen in Sprint 14: dieser Rückfall
existiert seit `pm/T-0023` (2026-08-16) in `preflight.entferne_artefakte` — die DoD 1 zu
bauen hätte **nichts geändert**.

Der gemessene Befund ist ein anderer und größer:

| gemessen am 2026-08-17 auf dem Mount | Ergebnis |
|---|---|
| `git status` (rein lesend) im Repo `pm` | hinterlässt `.git/index.lock`, `unlink` verboten |
| darauf folgendes `git add` | `fatal: Unable to create ... index.lock: File exists`, Exit 128 |
| Aufrufer von `git commit` in der Organisation | **8** |
| davon mit Sperren-Räumung | **1** (der Briefkasten) |

> **Eine Reparatur, die nur ihr eigener Fundort benutzt, ist eine Reparatur des Fundorts
> und nicht des Fehlers.**

Ausführung: python -m unittest discover platform/tests
"""
import os
import subprocess
import sys
import tempfile
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
from backend import git_schreiben  # noqa: E402

_PLATFORM = os.path.normpath(os.path.join(_HIER, ".."))


class SchreibwegTest(unittest.TestCase):
    """Verifiziert: SWR-134."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.repo = os.path.join(self.root, "repo")
        os.makedirs(self.repo)
        subprocess.run(["git", "-C", self.repo, "init", "-q", "-b", "main"],
                       capture_output=True)

    def _datei(self, name="a.txt", inhalt="x"):
        with open(os.path.join(self.repo, name), "w", encoding="utf-8") as f:
            f.write(inhalt)
        return name

    def _lock(self):
        """Eine verwaiste `index.lock` pflanzen — der gemessene Zustand des Mounts."""
        p = os.path.join(self.repo, ".git", "index.lock")
        open(p, "w").close()
        return p

    # --- der Kern: räumen und genau einmal wiederholen -------------------------

    def test_gesperrter_commit_gelingt_nach_dem_raeumen(self):
        self._datei()
        self._lock()
        v = git_schreiben.verbuche(self.repo, ["a.txt"], "erster Commit")
        self.assertTrue(v.ok, v.fehler)
        self.assertTrue(v.wiederholt, "die Wiederholung muss stattgefunden haben")

    def test_ohne_sperre_wird_gar_nicht_geraeumt(self):
        """Gegenprobe: der gewöhnliche Weg räumt nicht — sonst räumte jeder Schreibvorgang."""
        self._datei()
        gerufen = []
        v = git_schreiben.verbuche(self.repo, ["a.txt"], "Commit",
                                   entsperren=lambda r: gerufen.append(r) or 1)
        self.assertTrue(v.ok, v.fehler)
        self.assertFalse(v.wiederholt)
        self.assertEqual(gerufen, [], "ohne Fehlschlag darf nicht geräumt werden")

    def test_geraeumt_wird_genau_einmal(self):
        """Keine Schleife: ein dauerhafter Fehler wird gemeldet, nicht ausgesessen."""
        self._datei()
        rufe = []

        def raeumt_nichts_weg(repo):
            rufe.append(repo)
            return 1  # behauptet Erfolg, entfernt aber nichts -> zweiter Versuch scheitert

        self._lock()
        v = git_schreiben.verbuche(self.repo, ["a.txt"], "Commit",
                                   entsperren=raeumt_nichts_weg)
        self.assertFalse(v.ok)
        self.assertEqual(len(rufe), 1, "genau ein Räumversuch, keine Schleife")

    def test_scheiternde_reparatur_ist_nie_schlimmer_als_keine(self):
        """Wirft die Räumung, bleibt es bei der ehrlichen Meldung des ersten Versuchs."""
        self._datei()
        self._lock()

        def wirft(_repo):
            raise RuntimeError("Räummechanismus kaputt")

        v = git_schreiben.verbuche(self.repo, ["a.txt"], "Commit", entsperren=wirft)
        self.assertFalse(v.ok)
        self.assertFalse(v.wiederholt)
        self.assertIn("index.lock", v.fehler)

    def test_raeumung_ohne_fund_meldet_den_ersten_fehler_weiter(self):
        self._datei()
        self._lock()
        v = git_schreiben.verbuche(self.repo, ["a.txt"], "Commit", entsperren=lambda r: 0)
        self.assertFalse(v.ok)
        self.assertFalse(v.wiederholt)
        self.assertEqual(v.geraeumt, 0)

    # --- stderr und stdout bleiben getrennt ------------------------------------

    def test_nichts_zu_committen_ist_kein_fehler_und_steht_auf_stdout(self):
        """`teams.py` braucht diese Unterscheidung — Git meldet sie auf **stdout**."""
        self._datei()
        git_schreiben.verbuche(self.repo, ["a.txt"], "erster Commit")
        v = git_schreiben.verbuche(self.repo, ["a.txt"], "nochmal dasselbe")
        self.assertFalse(v.ok, "git meldet Exit != 0")
        self.assertTrue(v.nichts_zu_committen,
                        f"'nichts zu committen' muss erkannt werden: {v.fehler!r}")

    def test_echter_fehler_ist_nicht_nichts_zu_committen(self):
        """Gegenprobe: sonst würde jeder Ausfall als leerer Commit durchgehen."""
        self._datei()
        self._lock()
        v = git_schreiben.verbuche(self.repo, ["a.txt"], "Commit", entsperren=lambda r: 0)
        self.assertFalse(v.nichts_zu_committen, v.fehler)

    # --- ruf(): auch lesende Aufrufe gehen durch denselben Weg ------------------

    def test_ruf_raeumt_und_wiederholt_ebenfalls(self):
        self._datei()
        git_schreiben.verbuche(self.repo, ["a.txt"], "Commit")
        self._lock()
        v = git_schreiben.ruf(self.repo, ["add", "-A"])
        self.assertTrue(v.ok, v.fehler)
        self.assertTrue(v.wiederholt)

    def test_ruf_liefert_die_ausgabe_auf_stdout(self):
        self._datei()
        git_schreiben.verbuche(self.repo, ["a.txt"], "Commit")
        v = git_schreiben.ruf(self.repo, ["rev-parse", "--abbrev-ref", "HEAD"])
        self.assertTrue(v.ok, v.fehler)
        self.assertEqual(v.stdout.strip(), "main")

    def test_leere_pfadliste_committet_das_bereits_gestagete(self):
        name = self._datei()
        subprocess.run(["git", "-C", self.repo, "add", name], capture_output=True)
        v = git_schreiben.verbuche(self.repo, [], "nur committen")
        self.assertTrue(v.ok, v.fehler)

    def test_pfad_als_string_wird_nicht_in_zeichen_zerlegt(self):
        """Gegenprobe gegen `list("a.txt")` — der Fehler wäre lautlos und absurd."""
        self._datei()
        v = git_schreiben.verbuche(self.repo, "a.txt", "Commit")
        self.assertTrue(v.ok, v.fehler)

    # --- die Räumung ist NICHT neu gebaut, sondern die bestehende ---------------

    def test_entsperre_benutzt_den_preflight_mechanismus(self):
        """B033: kein zweiter Räummechanismus. Der Beweis ist ein Aufruf, keine Zusage."""
        import preflight
        echt = preflight.finde_lock_artefakte
        gesehen = []
        try:
            preflight.finde_lock_artefakte = lambda r: gesehen.append(r) or []
            git_schreiben.entsperre(self.repo)
        finally:
            preflight.finde_lock_artefakte = echt
        self.assertEqual(gesehen, [self.repo])

    def test_entsperre_ohne_sperre_meldet_null(self):
        self.assertEqual(git_schreiben.entsperre(self.repo), 0)

    def test_preflight_raeumung_faellt_auf_umbenennen_zurueck(self):
        """⚠ Die Aussage von `platform/T-0015` DoD 1, **am Bestand geprüft statt gebaut**.

        Das Ticket verlangte einen Rückfall auf `rename`, der seit `pm/T-0023` existiert.
        Dieser Test hält fest, dass er existiert — damit die nächste Fassung des Tickets
        nicht wieder anfängt, ihn zu bauen.
        """
        import preflight
        p = self._lock()
        echt_remove = os.remove

        def kein_unlink(pfad):
            raise PermissionError("Operation not permitted")  # der Mount

        try:
            os.remove = kein_unlink
            entfernt, geparkt, kaputt = preflight.entferne_artefakte([p])
        finally:
            os.remove = echt_remove
        self.assertEqual(entfernt, [])
        self.assertEqual(geparkt, [p], f"kaputt={kaputt}")
        self.assertFalse(os.path.exists(p), "für Git muss die Sperre weg sein")


class GenauEineStelleTest(unittest.TestCase):
    """Verifiziert: SWR-134 — „alle Schreiber" wird **gezählt**, nicht zugesagt.

    ⚠ Die Lehre aus SWR-131: dessen erster Anlauf stellte drei Leser um und übersah zwei;
    gefunden wurden sie erst durch ein `grep` von Hand. Eine Aussage über „alle" ist ohne
    Zähltest eine Aussage über den Tag ihrer Einführung.
    """

    #: Wer `git ... commit` selbst zusammenbaut. Genau eine Datei darf das.
    ERLAUBT = {os.path.join("backend", "git_schreiben.py")}

    def _quelldateien(self):
        for ordner in ("backend", "scripts", "orchestrator"):
            basis = os.path.join(_PLATFORM, ordner)
            for wurzel, _dirs, dateien in os.walk(basis):
                if "__pycache__" in wurzel:
                    continue
                for d in sorted(dateien):
                    if d.endswith(".py"):
                        voll = os.path.join(wurzel, d)
                        yield os.path.relpath(voll, _PLATFORM), voll

    @staticmethod
    def baut_commit_auf(quelltext):
        """Enthält der Quelltext einen `subprocess.run`-Aufruf mit `git` **und** `commit`?

        ⚠ **Gelesen wird der Syntaxbaum, nicht der Text.** Die erste Fassung dieser
        Prüfung suchte schlicht nach `"commit"` und wurde an drei Stellen rot, die alle
        richtig waren: zwei Wörterbuchschlüssel (`{"commit": _kurz_hash(repo)}`) und der
        `git()`-Helfer des Ticks, der seit dieser Umstellung **durch** den Schreibweg
        geht. Sie hätte also genau die Aufrufer bestraft, die korrekt umgestellt sind —
        dieselbe Falle wie der Kommentar-Fehlalarm in SWR-128 und der Zeilen-Fehlalarm in
        `test_org_kopfblock` (Sprint 13), zum dritten Mal.

        Gefragt ist nicht *„steht das Wort da"*, sondern *„wird hier ein Git-Prozess mit
        `commit` gestartet"* — und das ist eine Frage an den Aufrufknoten.
        """
        import ast
        baum = ast.parse(quelltext)
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.Call):
                continue
            ziel = knoten.func
            name = getattr(ziel, "attr", None) or getattr(ziel, "id", None)
            if name != "run":
                continue
            texte = {k.value for k in ast.walk(knoten)
                     if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            if "git" in texte and "commit" in texte:
                return True
        return False

    def test_genau_eine_stelle_baut_einen_commit_aufruf(self):
        treffer = set()
        for rel, voll in self._quelldateien():
            with open(voll, encoding="utf-8") as f:
                if self.baut_commit_auf(f.read()):
                    treffer.add(rel.replace("/", os.sep))
        self.assertEqual(
            treffer, {e.replace("/", os.sep) for e in self.ERLAUBT},
            "Es darf genau EINE Stelle geben, die einen git-commit-Aufruf zusammenbaut. "
            "Kommt eine dazu, läuft sie ohne Sperren-Räumung — genau der Befund aus "
            f"platform/T-0015. Gefunden: {sorted(treffer)}")

    def test_der_zaehltest_wuerde_einen_rueckfall_bemerken(self):
        """Gegenprobe: ein Test, der nichts findet, findet auch keinen Rückfall.

        Ohne diese Zusicherung wäre eine Prüfung, die versehentlich nie greift, von einem
        sauberen Bestand nicht zu unterscheiden — die Gestalt von SWR-128 („Fläche ohne
        Prüfung"), eine Etage tiefer.
        """
        self.assertTrue(self.baut_commit_auf(
            'subprocess.run(["git", "-C", r] + ID + ["commit", "-m", m])'))
        self.assertTrue(self.baut_commit_auf(
            'import subprocess\nsubprocess.run(["git", "-C", r, "commit", "-m", "x"])'))

    def test_der_zaehltest_bestraft_die_richtig_umgestellten_nicht(self):
        """⚠ Die drei Fehlalarme der ersten Fassung, als Zusicherung festgehalten.

        Wer diese Prüfung einmal vergröbert, bekommt sie rot — und nicht erst dann, wenn
        jemand sie durch Eintragen in `ERLAUBT` stillstellt.
        """
        self.assertFalse(self.baut_commit_auf(
            'x = {"fingerprint": f, "commit": _kurz_hash(repo)}'))
        self.assertFalse(self.baut_commit_auf(
            'git(projekt_repo, "commit", "-m", "T-0001: Tick-Ergebnis")'))
        self.assertFalse(self.baut_commit_auf(
            'subprocess.run(["git", "-C", r, "status", "--porcelain"])'))

    def test_jeder_schreibpfad_kennt_den_schreibweg(self):
        """Die andere Richtung: wer schreibt, muss den Weg auch **importieren**.

        Der Zähltest allein ließe eine Datei durchgehen, die ihren Commit ersatzlos
        gestrichen hat statt ihn umzustellen — das wäre ein stiller Verlust und kein
        Fortschritt (die Lehre aus SWR-131, wo die erste Hälfte allein schlimmer gewesen
        wäre als der Fehler).
        """
        erwartet = [
            os.path.join("backend", "briefkasten.py"),
            os.path.join("backend", "inbox.py"),
            os.path.join("backend", "tickets.py"),
            os.path.join("backend", "pool.py"),
            os.path.join("backend", "teams.py"),
            os.path.join("scripts", "digest_zustellung.py"),
            os.path.join("orchestrator", "tick.py"),
        ]
        for rel in erwartet:
            with open(os.path.join(_PLATFORM, rel), encoding="utf-8") as f:
                text = f.read()
            self.assertIn("git_schreiben", text,
                          f"{rel} schreibt nach Git, kennt den Schreibweg aber nicht")


if __name__ == "__main__":
    unittest.main()
