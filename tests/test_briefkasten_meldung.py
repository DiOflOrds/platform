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

    def _git_kaputt(self):
        """Git dauerhaft unbrauchbar machen — .git entfernen.

        ⚠ Bis Sprint 10 haben diese Tests den Fehler mit einer belegten `.git/index.lock`
        erzeugt. Genau diese Sperre raeumt SWR-123 (pm/T-0055 Teil 2) jetzt weg und
        wiederholt den Commit: der Ablauf gelingt, und die drei Tests schlugen fehl,
        obwohl an SWR-121 nichts falsch war.

        **Die Lehre steckt in dieser Zeile:** ein Test, der seinen Fehlerfall ueber einen
        Mechanismus erzeugt, den das System spaeter repariert, prueft ab dann nicht mehr,
        was in seinem Namen steht. Provoziert wird deshalb ein Fehler, den kein Raeumen
        heilt — eine unlesbare `.git/config`. Das `.git`-Verzeichnis bleibt dabei stehen,
        weil die Projekt-Discovery es braucht: entfernte man es, scheiterte der Aufruf
        schon an „unbekanntes Projekt" und der Test pruefte eine ganz andere Meldung. SWR-121 (die ehrliche Meldung) gilt unveraendert und
        wird hier weiter geprueft.
        """
        with open(os.path.join(self.repo, ".git", "config"), "w") as f:
            f.write("[core\nkaputt")

    def test_bei_gescheitertem_commit_bleibt_die_nachricht_auf_der_platte(self):
        """Der Kern: die Datei wird VOR dem Git-Aufruf geschrieben. „Commit
        gescheitert" heisst deshalb nie „Nachricht verloren"."""
        self._git_kaputt()
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
        self._git_kaputt()
        with self.assertRaises(briefkasten.BriefkastenFehler) as ctx:
            self._sende()
        text = str(ctx.exception)
        self.assertIn("GESPEICHERT", text)
        self.assertIn("NICHT erneut senden", text)
        self.assertIn("N-0001", text, "die Meldung nennt die Brief-ID zum Nachsehen")

    def test_meldung_verschweigt_die_ursache_nicht(self):
        """Der Gegentest zur Beruhigung: „gespeichert" darf den technischen Grund nicht
        ersetzen, sonst ist die Meldung nur anders einseitig."""
        self._git_kaputt()
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
