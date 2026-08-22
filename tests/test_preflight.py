"""Tests Preflight-Skript (p0/T-0024). Bezug: CR p0/T-0024 (Prozess-Tooling, kein SWR)."""
import contextlib
import io
import os
import sys
import tempfile
import time
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import preflight  # noqa: E402


def _fake_git(root, *artefakte):
    g = os.path.join(root, ".git")
    os.makedirs(os.path.join(g, "objects", "e5"), exist_ok=True)
    os.makedirs(os.path.join(g, "refs", "heads"), exist_ok=True)
    for a in artefakte:
        pfad = os.path.join(g, a)
        os.makedirs(os.path.dirname(pfad), exist_ok=True)
        open(pfad, "w").close()
    return g


class TestLockArtefakte(unittest.TestCase):
    """Lock-Erkennung findet alle bekannten Artefakt-Klassen. Bezug: CR p0/T-0024."""

    def test_findet_bekannte_artefakte(self):
        """index.lock, HEAD.lock, maintenance.lock, tmp_obj_*, refs-Locks werden erkannt."""
        with tempfile.TemporaryDirectory() as d:
            _fake_git(d, "index.lock", "HEAD.lock",
                      os.path.join("objects", "maintenance.lock"),
                      os.path.join("objects", "e5", "tmp_obj_XYZ"),
                      os.path.join("refs", "heads", "main.lock"))
            funde = preflight.finde_lock_artefakte(d)
            self.assertEqual(len(funde), 5)

    def test_sauberes_repo_ohne_funde(self):
        """Ein Repo ohne Lock-Artefakte liefert eine leere Liste."""
        with tempfile.TemporaryDirectory() as d:
            _fake_git(d)
            self.assertEqual(preflight.finde_lock_artefakte(d), [])

    def test_entfernen_meldet_erfolg(self):
        """Entfernbare Artefakte werden gelöscht und als entfernt gemeldet."""
        with tempfile.TemporaryDirectory() as d:
            _fake_git(d, "index.lock")
            funde = preflight.finde_lock_artefakte(d)
            entfernt, geparkt, kaputt = preflight.entferne_artefakte(funde)
            self.assertEqual(len(entfernt), 1)
            self.assertEqual(geparkt, [])
            self.assertEqual(kaputt, [])
            self.assertEqual(preflight.finde_lock_artefakte(d), [])

    def test_entfernen_meldet_fehlschlag(self):
        """Weder löschbar noch benennbar → Fehlschlag-Liste (R7-Fall), kein Abbruch."""
        entfernt, geparkt, kaputt = preflight.entferne_artefakte(
            [os.path.join(tempfile.gettempdir(), "gibt-es-nicht", ".git", "x.lock")])
        self.assertEqual(entfernt, [])
        self.assertEqual(geparkt, [])
        self.assertEqual(len(kaputt), 1)


class TestLockParkplatz(unittest.TestCase):
    """Fallback für Mounts ohne unlink-Recht (R7). Bezug: pm/T-0023, Befund 2026-08-16.

    Ohne diesen Fallback blieb ein verwaister index.lock liegen und JEDER
    Commit der Session schlug fehl — eine komplette Session verlor am
    2026-08-16 ihre Verbuchung, obwohl die Arbeit fertig war.
    """

    def setUp(self):
        """Hermetik (pm/T-0024): `git_prozess_aktiv()` fragt das GANZE Gerät ab.

        Ein beliebiger laufender git.exe — Auto-Push-Wächter, HMI-Commit, IDE — ließ
        `test_nur_locks_laesst_repos_unberuehrt` rot werden und riss damit `abschluss.cmd`
        mit: kein Push, keine GitHub-Actions, und zwei pm-Tickets warteten auf einen
        grünen Lauf, der nicht mehr stattfinden konnte. Das Fake-Repo in %TEMP% hat mit
        laufenden Git-Prozessen nichts zu tun; die Abfrage gehört hier festgenagelt.
        """
        self._echte_abfrage = preflight.git_prozess_aktiv
        preflight.git_prozess_aktiv = lambda: False

    def tearDown(self):
        preflight.git_prozess_aktiv = self._echte_abfrage

    @staticmethod
    def _ohne_unlink(pfade):
        """os.remove hart abschalten, os.rename unverändert lassen (Mount-Verhalten R7)."""
        echt = os.remove

        def blockiert(p):
            raise PermissionError(1, "Operation not permitted", p)
        os.remove = blockiert
        try:
            return preflight.entferne_artefakte(pfade)
        finally:
            os.remove = echt

    def test_nicht_loeschbarer_lock_wird_geparkt(self):
        """Wenn os.remove scheitert, wird der Lock weggeräumt statt aufzugeben."""
        with tempfile.TemporaryDirectory() as d:
            _fake_git(d, "index.lock")
            funde = preflight.finde_lock_artefakte(d)
            entfernt, geparkt, kaputt = self._ohne_unlink(funde)
            self.assertEqual(entfernt, [])
            self.assertEqual(len(geparkt), 1)
            self.assertEqual(kaputt, [])

    def test_git_sieht_den_lock_danach_nicht_mehr(self):
        """Der eigentliche Zweck: der exakte Pfad .git/index.lock existiert nicht mehr."""
        with tempfile.TemporaryDirectory() as d:
            g = _fake_git(d, "index.lock")
            self._ohne_unlink(preflight.finde_lock_artefakte(d))
            self.assertFalse(os.path.exists(os.path.join(g, "index.lock")))
            self.assertEqual(preflight.finde_lock_artefakte(d), [])

    def test_geparktes_artefakt_bleibt_erhalten(self):
        """Weggeräumt heißt nicht vernichtet — die Datei liegt auf dem Parkplatz."""
        with tempfile.TemporaryDirectory() as d:
            g = _fake_git(d, "index.lock")
            self._ohne_unlink(preflight.finde_lock_artefakte(d))
            parkplatz = os.path.join(g, preflight.PARKPLATZ)
            self.assertTrue(os.path.isdir(parkplatz))
            self.assertEqual(len(os.listdir(parkplatz)), 1)

    def test_parkplatz_wird_nicht_erneut_als_lock_erkannt(self):
        """Sonst räumte jeder Lauf seinen eigenen Parkplatz um (Endlos-Umbenennen)."""
        with tempfile.TemporaryDirectory() as d:
            _fake_git(d, "index.lock", os.path.join("refs", "heads", "main.lock"))
            self._ohne_unlink(preflight.finde_lock_artefakte(d))
            self.assertEqual(preflight.finde_lock_artefakte(d), [])

    def test_preflight_hinterlaesst_keinen_lock(self):
        """Zweiter Befund pm/T-0023: Preflights EIGENE git-Aufrufe legen index.lock an.

        Ohne Schlusslauf meldet Preflight STARTKLAR und hinterlässt genau die Sperre,
        die es gerade aufgehoben hat — der nächste Commit der Session scheitert dann.
        """
        with tempfile.TemporaryDirectory() as d:
            for repo in ("process", "platform", "p0"):
                _fake_git(os.path.join(d, repo))
            preflight.preflight(d, skip_tests=True)
            # Simuliert den Zustand nach den git-Aufrufen: neuer, nicht löschbarer Lock
            nachher = os.path.join(d, "p0", ".git", "index.lock")
            open(nachher, "w").close()
            self._ohne_unlink(preflight.finde_lock_artefakte(os.path.join(d, "p0")))
            self.assertFalse(os.path.exists(nachher))

    def test_nur_locks_laesst_repos_unberuehrt(self):
        """--nur-locks entsperrt schnell, ohne Board-Check und Tests zu fahren."""
        with tempfile.TemporaryDirectory() as d:
            _fake_git(os.path.join(d, "p0"), "index.lock")
            befunde = preflight.preflight(d, skip_tests=True, nur_locks=True)
            self.assertEqual(befunde, 0)
            self.assertFalse(os.path.exists(os.path.join(d, "p0", ".git", "index.lock")))

    def test_artefakte_aus_unterordnern_kollidieren_nicht(self):
        """refs/heads/main.lock und ein gleichnamiger Fund dürfen sich nicht überschreiben."""
        with tempfile.TemporaryDirectory() as d:
            g = _fake_git(d, "index.lock",
                          os.path.join("objects", "e5", "tmp_obj_XYZ"),
                          os.path.join("refs", "heads", "main.lock"))
            entfernt, geparkt, kaputt = self._ohne_unlink(preflight.finde_lock_artefakte(d))
            self.assertEqual(len(geparkt), 3)
            self.assertEqual(kaputt, [])
            self.assertEqual(len(os.listdir(os.path.join(g, preflight.PARKPLATZ))), 3)


class TestProzessAbfrage(unittest.TestCase):
    """Die Prozess-Abfrage darf nie zur Blockade werden. Bezug: pm/T-0024 (SUP.9).

    Befund vom 2026-08-16: Drei Auto-Push-Läufe hintereinander brachen ab, 21 Commits
    und zwei Baseline-Tags blieben lokal liegen — Ursache war ein Decodier-Fehler beim
    Auslesen der Windows-Prozessliste, der sich als „Git-Prozess aktiv" tarnte.
    """

    @staticmethod
    def _mit_fake_run(rohbytes, system="Windows"):
        """Stellt nach, was subprocess mit text=True tut: mit dem übergebenen Codec decodieren."""
        echt_run, echt_system = preflight.subprocess.run, preflight._platform.system

        def fake_run(cmd, **kw):
            text = rohbytes.decode(kw.get("encoding") or "cp1252",
                                   kw.get("errors") or "strict")
            return types.SimpleNamespace(stdout=text, stderr="", returncode=0)

        preflight.subprocess.run = fake_run
        preflight._platform.system = lambda: system
        try:
            return preflight.git_prozess_aktiv()
        finally:
            preflight.subprocess.run, preflight._platform.system = echt_run, echt_system

    def test_fremde_codepage_bricht_die_abfrage_nicht(self):
        """Regression: 'ü' aus der OEM-Codepage 850 ist Byte 0x81 und in cp1252 undefiniert.

        Genau diese Antwort gibt `tasklist`, wenn KEIN git.exe läuft ('… ausgeführt.') —
        die Abfrage scheiterte also ausgerechnet im harmlosen Normalfall und meldete
        das Gegenteil. Gegen den alten Code (ohne errors=) scheitert dieser Test.
        """
        ohne_treffer = "INFO: Es wird kein Task mit den angegebenen Kriterien ausgeführt."
        self.assertFalse(self._mit_fake_run(ohne_treffer.encode("cp850")))

    def test_treffer_wird_trotz_ersatzzeichen_erkannt(self):
        """Der Prozessname ist ASCII — durch das Ersetzen geht die Aussage nicht verloren."""
        mit_treffer = "Abbildname   PID Sitzungsname\ngit.exe   4711 Konsole   ausgeführt\n"
        self.assertTrue(self._mit_fake_run(mit_treffer.encode("cp850")))

    def test_unklare_abfrage_bleibt_vorsichtig_und_meldet_sich(self):
        """Bei echtem Fehler weiter „aktiv" (nichts löschen) — aber sichtbar, nicht stumm."""
        echt_run, echt_system = preflight.subprocess.run, preflight._platform.system

        def kaputt(cmd, **kw):
            raise OSError("Prozessliste nicht verfügbar")

        preflight.subprocess.run = kaputt
        preflight._platform.system = lambda: "Windows"
        puffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(puffer):
                aktiv = preflight.git_prozess_aktiv()
        finally:
            preflight.subprocess.run, preflight._platform.system = echt_run, echt_system
        self.assertTrue(aktiv)
        self.assertIn("Prozess-Abfrage nicht auswertbar", puffer.getvalue())

    def test_laufender_git_prozess_schuetzt_den_frischen_lock_weiterhin(self):
        """Die SCHUTZWIRKUNG bleibt — der BEFUND fällt weg (SWR-217, Paarform SWR-148).

        Vorher zählte diese Lage einen Befund und brach damit den Auto-Abschluss ab.
        Geschützt wird das frische Artefakt weiterhin: es ist nach dem Lauf noch da.
        """
        echt = preflight.git_prozess_aktiv
        preflight.git_prozess_aktiv = lambda: True
        try:
            with tempfile.TemporaryDirectory() as d:
                _fake_git(os.path.join(d, "p0"), "index.lock")
                puffer = io.StringIO()
                with contextlib.redirect_stdout(puffer):
                    befunde = preflight.raeume_locks(d)
                self.assertEqual(befunde, 0, "ein geschützter Lock ist kein Befund")
                self.assertTrue(os.path.exists(
                    os.path.join(d, "p0", ".git", "index.lock")),
                    "der Schutz selbst muss erhalten bleiben")
                self.assertIn("kein Befund", puffer.getvalue())
        finally:
            preflight.git_prozess_aktiv = echt


class TestVerwaisteLocks(unittest.TestCase):
    """SWR-217 (platform/T-0073): geräumt wird nach ALTER, nicht nach Prozessliste.

    Gemessen an 77 Auto-Abschlüssen des Auftraggebers: kein einziger erreichte je
    `PREFLIGHT: 0`; 23 brachen an der Lock-Zeile ab, während `repo_status` dasselbe
    Artefakt im selben Lauf als „kein Befund" führte.
    """

    def setUp(self):
        self._echt = preflight.git_prozess_aktiv

    def tearDown(self):
        preflight.git_prozess_aktiv = self._echt

    @staticmethod
    def _lock(d, alter_s):
        g = _fake_git(os.path.join(d, "p0"), "index.lock")
        pfad = os.path.join(g, "index.lock")
        os.utime(pfad, (time.time() - alter_s, time.time() - alter_s))
        return pfad

    def test_alter_lock_wird_geraeumt_obwohl_git_laeuft(self):
        """Der Kernfall des Hosts: git.exe lebt irgendwo, das Artefakt ist Stunden alt."""
        preflight.git_prozess_aktiv = lambda: True
        with tempfile.TemporaryDirectory() as d:
            pfad = self._lock(d, 3600)
            with contextlib.redirect_stdout(io.StringIO()):
                befunde = preflight.raeume_locks(d)
            self.assertEqual(befunde, 0)
            self.assertFalse(os.path.exists(pfad),
                             "ein stundenalter Lock gehört keinem laufenden Aufruf")

    def test_frischer_lock_bleibt_solange_git_laeuft(self):
        """Gegenrichtung: der Schutz für frische Artefakte bleibt bestehen."""
        preflight.git_prozess_aktiv = lambda: True
        with tempfile.TemporaryDirectory() as d:
            pfad = self._lock(d, 1)
            with contextlib.redirect_stdout(io.StringIO()):
                befunde = preflight.raeume_locks(d)
            self.assertEqual(befunde, 0)
            self.assertTrue(os.path.exists(pfad))

    def test_ohne_git_prozess_bleibt_es_beim_alten_verhalten(self):
        """⚠ Die Frist darf `--nur-locks` NICHT mitnehmen — sonst wandert die Sperre nur.

        `platform/T-0021`: vor einem Commit wird ein sekundenaltes R7-Residuum
        weggeräumt, und zwar sofort. Wäre die Frist hier auch gültig, hätte dieser Lauf
        eine blockierte Stelle gegen eine andere getauscht. Rückbau-Wächter für die
        Schmalheit des Eingriffs.
        """
        preflight.git_prozess_aktiv = lambda: False
        with tempfile.TemporaryDirectory() as d:
            pfad = self._lock(d, 1)
            with contextlib.redirect_stdout(io.StringIO()):
                befunde = preflight.raeume_locks(d)
            self.assertEqual(befunde, 0)
            self.assertFalse(os.path.exists(pfad))

    def test_grenze_beisst_auf_beiden_seiten(self):
        """Knapp jünger bleibt, knapp älter geht — die Frist ist eine Kante, kein Gefühl."""
        with tempfile.TemporaryDirectory() as d:
            pfad = self._lock(d, 0)
            jetzt = os.path.getmtime(pfad)
            self.assertFalse(preflight.lock_ist_verwaist(
                pfad, jetzt=jetzt + preflight.LOCK_GNADENFRIST_S - 1))
            self.assertTrue(preflight.lock_ist_verwaist(
                pfad, jetzt=jetzt + preflight.LOCK_GNADENFRIST_S + 1))

    def test_gnadenfrist_liegt_zwischen_aufruf_und_takt(self):
        """Beide Enden zugesichert, damit die Zahl nicht still in einen Nachbarn rutscht."""
        self.assertGreater(preflight.LOCK_GNADENFRIST_S, 10,
                           "unter 10 s käme ein echter Index-Schreibvorgang in Reichweite")
        self.assertLess(preflight.LOCK_GNADENFRIST_S, 15 * 60,
                        "ab dem 15-Minuten-Takt würde kein Lock je verwaisen")

    def test_unlesbares_mtime_gilt_als_frisch(self):
        """Nichtwissen darf nicht in Richtung Löschen entscheiden."""
        self.assertFalse(preflight.lock_ist_verwaist(
            os.path.join(tempfile.gettempdir(), "gibt-es-nicht", "index.lock")))

    def test_keep_locks_ist_kein_befund(self):
        """Ein befolgter Auftrag des Aufrufers ist keine Störung des Hauses."""
        with tempfile.TemporaryDirectory() as d:
            self._lock(d, 3600)
            puffer = io.StringIO()
            with contextlib.redirect_stdout(puffer):
                befunde = preflight.raeume_locks(d, keep_locks=True)
            self.assertEqual(befunde, 0)
            self.assertIn("kein Befund", puffer.getvalue())

    def test_echter_fehlschlag_bleibt_befund(self):
        """Was weder gelöscht noch weggeräumt werden kann, blockiert wirklich — und zählt.

        Rückbau-Wächter: fiele diese Zusicherung, wäre der Zähler wirkungslos geworden
        statt geschärft, und SWR-166 stünde auf der anderen Seite wieder da.
        """
        preflight.git_prozess_aktiv = lambda: False
        echt = preflight.entferne_artefakte
        preflight.entferne_artefakte = lambda p: ([], [], list(p))
        try:
            with tempfile.TemporaryDirectory() as d:
                self._lock(d, 3600)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(preflight.raeume_locks(d), 1)
        finally:
            preflight.entferne_artefakte = echt


class TestTestCacheAusserhalbDesMounts(unittest.TestCase):
    """SWR-218: die Teststrecke darf keine ältere Fassung messen als die im Repo.

    ⚠⚠ Dieser Befund entstand, als der Lauf seine eigenen Mutationsproben nachmaß:
    sechs Zahlen waren bereits notiert, als auffiel, dass sie aus einem veralteten
    `__pycache__` stammten. Eine Probe ändert EIN Zeichen und behält die Größe —
    genau die Bearbeitung, die Pythons `mtime`+`size`-Prüfung nicht unterscheidet.
    """

    def test_umgebung_leitet_den_cache_aus_dem_repo_heraus(self):
        """Die Variable ist gesetzt und zeigt nicht in den Mount."""
        env = preflight.test_cache_umgebung({})
        ziel = env.get("PYTHONPYCACHEPREFIX", "")
        self.assertTrue(ziel, "ohne die Variable landet der Cache neben der Quelle")
        repo = os.path.dirname(os.path.dirname(os.path.abspath(preflight.__file__)))
        self.assertFalse(os.path.abspath(ziel).startswith(repo + os.sep),
                         "ein Cache IM Repo ist auf diesem Mount nicht löschbar (R7)")

    def test_unit_tests_benutzt_diese_umgebung(self):
        """Rückbau-Wächter: die Funktion darf nicht wieder auf die nackte Umgebung fallen."""
        gesehen = {}

        def fake_run(cmd, **kw):
            gesehen.update(kw.get("env") or {})
            return types.SimpleNamespace(stdout="", stderr="", returncode=0)

        echt = preflight.subprocess.run
        preflight.subprocess.run = fake_run
        try:
            preflight.unit_tests(".")
        finally:
            preflight.subprocess.run = echt
        self.assertIn("PYTHONPYCACHEPREFIX", gesehen)

    def test_veralteter_cache_wuerde_eine_andere_fassung_messen(self):
        """Der Nachweis am echten Mechanismus statt als Behauptung.

        Ein `.pyc`, dessen Kopf zur Quelle passt und dessen Bytecode eine ANDERE
        Fassung trägt, wird ohne Umleitung geladen — mit Umleitung nicht.
        """
        import importlib.util
        import py_compile
        with tempfile.TemporaryDirectory() as d:
            quelle = os.path.join(d, "mut.py")
            with open(quelle, "w", encoding="utf-8") as fh:
                fh.write("WERT = 0\n")          # die „Probe"
            py_compile.compile(quelle, doraise=True)
            with open(quelle, "w", encoding="utf-8") as fh:
                fh.write("WERT = 1\n")          # zurückgenommen, GLEICHE Größe
            pyc = importlib.util.cache_from_source(quelle)
            self.assertTrue(os.path.exists(pyc))
            # Die Quelle auf genau die mtime zurückstellen, die im .pyc-Kopf steht —
            # der Zustand, den `cp` innerhalb derselben Sekunde von allein herstellt.
            quell_mtime = _pyc_quell_mtime(pyc)
            os.utime(quelle, (quell_mtime, quell_mtime))
            sys.path.insert(0, d)
            try:
                import mut
                self.assertEqual(mut.WERT, 0,
                                 "genau diese Verwechslung hat sechs Messungen gekostet")
            finally:
                sys.path.remove(d)
                sys.modules.pop("mut", None)


def _pyc_quell_mtime(pyc):
    """Die Quell-mtime, gegen die ein .pyc validiert wird (Kopf-Bytes 4..8)."""
    import struct
    with open(pyc, "rb") as fh:
        return struct.unpack("<4sIII", fh.read(16))[2]


class TestPreflightGesamt(unittest.TestCase):
    """Gesamtlauf meldet fehlende Repos als Befund. Bezug: CR p0/T-0024."""

    def test_fehlende_repos_sind_befunde(self):
        """Leere Wurzel: 3 fehlende Repos + board-check-Fehler = 4 Befunde."""
        with tempfile.TemporaryDirectory() as d:
            befunde = preflight.preflight(d, skip_tests=True)
            self.assertEqual(befunde, 4)

    def test_schlusszeile_nennt_beide_zahlen_auch_bei_null(self):
        """SWR-166 (platform/T-0029): die Schlusszeile trägt **zwei** Zahlen — immer.

        ⚠ Der Sinn der Trennung ist, dass ein fortgeschriebener Befund weiter GEMELDET
        wird und nur nicht mehr blockiert. Eine Schlusszeile, die davon nichts sagt,
        macht daraus auf dem Weg nach draußen wieder ein „nicht gemeldet" — genau der
        Fehler, den SWR-114/117/155 dreimal kosten musste. Die Zahl steht deshalb auch
        dann da, wenn sie 0 ist: eine stille Prüfung ist von einer nicht gelaufenen
        nicht zu unterscheiden.
        """
        with tempfile.TemporaryDirectory() as d:
            puffer = io.StringIO()
            with contextlib.redirect_stdout(puffer):
                preflight.preflight(d, skip_tests=True)
            schluss = [z for z in puffer.getvalue().splitlines()
                       if z.startswith("PREFLIGHT:")]
            self.assertEqual(len(schluss), 1, "genau eine Schlusszeile")
            self.assertIn("fortgeschrieben", schluss[0])
            self.assertIn("(0 fortgeschrieben)", schluss[0])

    def test_nur_locks_nennt_die_zweite_zahl_nicht(self):
        """⚠ Die Gegenprobe: `--nur-locks` prüft nichts, was fortgeschrieben sein
        könnte, und behauptet deshalb auch keine Zahl darüber. Eine „0" an dieser
        Stelle wäre die Gleichsetzung von *nicht gemessen* und *als 0 gemessen* —
        derselbe Fehler, den SWR-164 für den Parkplatz ausdrücklich vermeidet."""
        with tempfile.TemporaryDirectory() as d:
            puffer = io.StringIO()
            with contextlib.redirect_stdout(puffer):
                preflight.preflight(d, skip_tests=True, nur_locks=True)
            schluss = [z for z in puffer.getvalue().splitlines()
                       if z.startswith("PREFLIGHT:")][0]
            self.assertIn("nur Lock-Räumung", schluss)
            self.assertNotIn("fortgeschrieben", schluss)


class TestReposImRoot(unittest.TestCase):
    """T-0050: Preflight kennt auch Produkt-Repos im Root."""

    def test_produkt_repo_wird_erkannt(self):
        """Zusaetzliche Git-Repos im Root (z.B. produkt-datakonv) werden geprueft. Verifiziert: SWR-015."""
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            for name in ("p0", "produkt-x"):
                os.makedirs(os.path.join(root, name, ".git"))
            os.makedirs(os.path.join(root, "kein-repo"))
            namen = preflight.repos_im_root(root)
            self.assertIn("produkt-x", namen)
            self.assertNotIn("kein-repo", namen)
            self.assertEqual(namen[:3], ["process", "platform", "p0"])


class MultiProjektBoardCheckTest(unittest.TestCase):
    """P1/T-0008: Preflight prüft die Boards ALLER Projekt-Repos in einem Lauf."""

    def test_invalides_zweitprojekt_ist_befund(self):
        """Ein kaputtes Ticket im Zweitprojekt erzeugt einen Befund. Verifiziert: SWR-029."""
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            for name, ticket in (("p0", None), ("p1", "---\nid: T-0001\n---\n\nkaputt\n")):
                repo = os.path.join(root, name)
                os.makedirs(os.path.join(repo, "tickets"))
                if ticket:
                    open(os.path.join(repo, "tickets", "T-0001.md"), "w",
                         encoding="utf-8").write(ticket)
                subprocess.run(["git", "-C", repo, "init", "-q"], check=True)
            self.assertGreaterEqual(preflight.preflight(root, skip_tests=True), 1)

    def test_kaputtes_ticket_im_sammelrepo_ist_befund(self):
        """Ein Projektordner in projects/ läuft mit durch den Board-Check und fällt bei
        kaputtem Ticket auf. Verifiziert: SWR-070."""
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            p0 = os.path.join(root, "p0")
            os.makedirs(os.path.join(p0, "tickets"))
            subprocess.run(["git", "-C", p0, "init", "-q"], check=True)
            sammel = os.path.join(root, "projects")
            nested = os.path.join(sammel, "p10", "tickets")
            os.makedirs(nested)
            open(os.path.join(nested, "T-0001.md"), "w",
                 encoding="utf-8").write("---\nid: T-0001\n---\n\nkaputt\n")
            subprocess.run(["git", "-C", sammel, "init", "-q"], check=True)
            self.assertGreaterEqual(preflight.preflight(root, skip_tests=True), 1)


if __name__ == "__main__":
    unittest.main()
