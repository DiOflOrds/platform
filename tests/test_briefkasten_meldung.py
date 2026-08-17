"""Die Fehlermeldung des Briefkasten-Schreibpfads (SWR-121, pm/T-0055).

Anlass: Brief `pm/N-0039` des Auftraggebers. Der Commit scheiterte, die Meldung lautete
„Git-Commit fehlgeschlagen: fatal: Unable to create index.lock ..." — und die Nachricht
war trotzdem gespeichert. Der Leser musste sich die richtige Haelfte selbst erschliessen.

Am Bestand belegt: `pm/N-0038` hat NIE einen eigenen Commit bekommen (erster Commit auf
die Datei ist zwei Stunden spaeter ein fremder), `pm/N-0039` kam durch.
"""
import os
import subprocess
import sys
import tempfile
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
from backend import briefkasten  # noqa: E402


class MeldungTest(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.repo = os.path.join(self.root, "p0")
        os.makedirs(os.path.join(self.repo, "tickets"))
        subprocess.run(["git", "-C", self.repo, "init", "-q", "-b", "main"],
                       capture_output=True)

    def _sende(self):
        return briefkasten.sende(self.root, "p0", "Testnachricht", von="E. John")

    def test_bei_gescheitertem_commit_bleibt_die_nachricht_auf_der_platte(self):
        """Der Kern: die Datei wird VOR dem Git-Aufruf geschrieben. „Commit
        gescheitert" heisst deshalb nie „Nachricht verloren"."""
        # Git unbrauchbar machen: index.lock belegen -> add/commit scheitern.
        with open(os.path.join(self.repo, ".git", "index.lock"), "w") as f:
            f.write("")
        try:
            self._sende()
            fehler = None
        except briefkasten.BriefkastenFehler as e:
            fehler = e
        self.assertIsNotNone(fehler, "gescheiterter Commit muss gemeldet werden")
        verz = os.path.join(self.repo, "management", "briefkasten")
        briefe = [d for d in os.listdir(verz) if d.endswith(".md")]
        self.assertEqual(len(briefe), 1, "die Nachricht muss trotzdem da sein")

    def test_meldung_nennt_zuerst_dass_gespeichert_wurde(self):
        """⚠ Die Meldung darf den Ausgang nicht schlechter darstellen, als er ist.

        Sie kostet sonst dasselbe wie eine beschoenigende: der Leser handelt am
        Sachverhalt vorbei — hier, indem er dieselbe Nachricht ein zweites Mal schickt.
        """
        with open(os.path.join(self.repo, ".git", "index.lock"), "w") as f:
            f.write("")
        with self.assertRaises(briefkasten.BriefkastenFehler) as ctx:
            self._sende()
        text = str(ctx.exception)
        self.assertIn("GESPEICHERT", text)
        self.assertIn("NICHT erneut senden", text)
        self.assertIn("N-0001", text, "die Meldung nennt die Brief-ID zum Nachsehen")

    def test_meldung_verschweigt_die_ursache_nicht(self):
        """Der Gegentest zur Beruhigung: „gespeichert" darf den technischen Grund nicht
        ersetzen, sonst ist die Meldung nur anders einseitig."""
        with open(os.path.join(self.repo, ".git", "index.lock"), "w") as f:
            f.write("")
        with self.assertRaises(briefkasten.BriefkastenFehler) as ctx:
            self._sende()
        self.assertIn("Ursache:", str(ctx.exception))
        self.assertEqual(ctx.exception.code, 503)

    def test_erfolgreicher_weg_meldet_keinen_fehler(self):
        """Gegenprobe: ohne Sperre laeuft der Schreibpfad durch und committet."""
        subprocess.run(["git", "-C", self.repo, "config", "user.name", "T"],
                       capture_output=True)
        subprocess.run(["git", "-C", self.repo, "config", "user.email", "t@e.invalid"],
                       capture_output=True)
        ergebnis = self._sende()
        self.assertEqual(ergebnis["brief"], "N-0001")
        log = subprocess.run(["git", "-C", self.repo, "log", "--oneline"],
                             capture_output=True, text=True).stdout
        self.assertIn("N-0001", log, "der erfolgreiche Weg verbucht die Nachricht")


if __name__ == "__main__":
    unittest.main()
