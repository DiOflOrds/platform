"""Verwaiste Sperre räumen und einmal wiederholen (SWR-123, pm/T-0055 Teil 2).

Anlass: Brief `pm/N-0039` des Auftraggebers. SWR-121 hat in Sprint 9 die **Meldung**
geradegezogen („Deine Nachricht ist GESPEICHERT …"). Dieses Ticket nimmt den Anlass weg:
auf diesem Mount hinterlässt `git add` eine `.git/index.lock`, die es nicht mehr löschen
kann, und der **nachfolgende** `commit` scheitert an ihr. Der Fehler entsteht also
zwischen den beiden Schritten, die der Schreibpfad selbst macht.

Geräumt wird über den Mechanismus, den die Organisation seit Sprint 5 hat
(`preflight.finde_lock_artefakte` / `entferne_artefakte`) — kein zweiter daneben (B033).

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
from backend import briefkasten  # noqa: E402


class LockRaeumenTest(unittest.TestCase):
    """Verifiziert: SWR-123."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.repo = os.path.join(self.root, "p0")
        os.makedirs(os.path.join(self.repo, "tickets"))
        subprocess.run(["git", "-C", self.repo, "init", "-q", "-b", "main"],
                       capture_output=True)
        self._echt_entsperre = briefkasten._entsperre

    def tearDown(self):
        briefkasten._entsperre = self._echt_entsperre

    def _lock(self):
        pfad = os.path.join(self.repo, ".git", "index.lock")
        with open(pfad, "w") as f:
            f.write("")
        return pfad

    def _sende(self):
        return briefkasten.sende(self.root, "p0", "Testnachricht", von="E. John")

    # --- der Originalfall ------------------------------------------------------

    def test_gesperrter_commit_gelingt_nach_dem_raeumen(self):
        """⚠ Der Fall aus `pm/N-0039`: mit belegter index.lock ging bis SWR-123 nichts.

        Gegenprobe gegen den Vorstand: vor dieser Änderung endete derselbe Ablauf in
        `BriefkastenFehler(503)`. Verifiziert: SWR-123.
        """
        self._lock()
        ergebnis = self._sende()
        self.assertTrue(ergebnis["brief"].startswith("N-"))
        log = subprocess.run(["git", "-C", self.repo, "log", "--oneline"],
                             capture_output=True, text=True).stdout
        self.assertIn("Briefkasten", log, "die Nachricht ist verbucht, nicht nur gespeichert")
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".git", "index.lock")))

    def test_geraeumt_wird_genau_einmal_und_wiederholt_wird_genau_einmal(self):
        """Keine Schleife: ein echter Dauerfehler gehört gemeldet, nicht abgewartet.

        Verifiziert: SWR-123.
        """
        rufe = []

        def zaehlend(repo):
            rufe.append(repo)
            return self._echt_entsperre(repo)

        briefkasten._entsperre = zaehlend
        self._lock()
        self._sende()
        self.assertEqual(len(rufe), 1)

    def test_ohne_sperre_wird_gar_nicht_geraeumt(self):
        """Die Gegenprobe: der Normalfall fasst die Sperrdateien nicht an.

        Verifiziert: SWR-123.
        """
        rufe = []
        briefkasten._entsperre = lambda repo: rufe.append(repo) or 0
        self._sende()
        self.assertEqual(rufe, [], "der gelungene Commit räumt nichts")

    # --- die Grenze: was das Räumen NICHT heilt --------------------------------

    def test_unheilbarer_fehler_meldet_weiter_ehrlich(self):
        """⚠ Die Gegenprobe gegen ein verschlucktes Problem.

        Räumt der Mechanismus nichts weg (oder hilft es nicht), muss die Meldung aus
        SWR-121 unverändert kommen — „GESPEICHERT", Brief-ID, „NICHT erneut senden",
        „Ursache:" und Code 503. Eine Reparatur, die den ehrlichen Bericht ersetzt,
        wäre teurer als der Fehler. Verifiziert: SWR-123 (und SWR-121).
        """
        briefkasten._entsperre = lambda repo: 0   # nichts geräumt
        self._lock()
        with self.assertRaises(briefkasten.BriefkastenFehler) as ctx:
            self._sende()
        self.assertEqual(ctx.exception.code, 503)
        text = str(ctx.exception)
        self.assertIn("GESPEICHERT", text)
        self.assertIn("NICHT erneut senden", text)
        self.assertIn("Ursache:", text)

    def test_nachricht_liegt_auch_bei_unheilbarem_fehler_auf_der_platte(self):
        """Die Datei entsteht vor Git — daran ändert SWR-123 nichts. Verifiziert: SWR-123."""
        briefkasten._entsperre = lambda repo: 0
        self._lock()
        with self.assertRaises(briefkasten.BriefkastenFehler):
            self._sende()
        verz = os.path.join(self.repo, "management", "briefkasten")
        self.assertTrue([d for d in os.listdir(verz) if d.endswith(".md")])

    def test_kaputter_raeummechanismus_wirft_keinen_neuen_fehlertyp(self):
        """Ein Ausfall der Reparatur darf nicht schlimmer sein als kein Versuch.

        Verifiziert: SWR-123.
        """
        def explodiert(repo):
            raise RuntimeError("Räumen kaputt")

        briefkasten._verbuche.__globals__  # noqa: B018 — Doku: _entsperre wird gerufen
        briefkasten._entsperre = explodiert
        self._lock()
        with self.assertRaises(briefkasten.BriefkastenFehler):
            self._sende()

    # --- der geteilte Mechanismus ---------------------------------------------

    def test_entsperre_benutzt_den_preflight_mechanismus(self):
        """Kein zweiter Räummechanismus (B033) — geräumt wird, was preflight findet.

        Verifiziert: SWR-123.
        """
        import preflight
        self._lock()
        self.assertTrue(preflight.finde_lock_artefakte(self.repo),
                        "Vorbedingung: preflight sieht die Sperre")
        self.assertGreaterEqual(briefkasten._entsperre(self.repo), 1)
        self.assertEqual(preflight.finde_lock_artefakte(self.repo), [])

    def test_entsperre_ohne_sperre_meldet_null(self):
        """Verifiziert: SWR-123."""
        self.assertEqual(briefkasten._entsperre(self.repo), 0)


if __name__ == "__main__":
    unittest.main()
