"""Die Datenklasse PLATZIERT ein Projekt, sie beschriftet es nicht (SWR-208, platform/T-0063).

⚠⚠ **Der Anlass ist eine Gründung, die in diesem Sprint anstand.** `pm/D016` = B hat
`team-termine` gegründet — ein Projekt, das den **Google-Kalender eines fremden Kontos**
(`dimitri.john83@gmail.com`) liest und schreibt. Beim Ausführen von `pm/T-0083` fiel auf:

* `projekt_setup.py` nimmt `--datenklasse sensibel` entgegen und **prüft** den Wert,
* schreibt ihn als **`#`-Kommentar** in den Steckbrief,
* und legt das Projekt unverändert unter `projects/<kennung>` an — in einem Repo **mit**
  GitHub-Remote, das `abschluss.cmd` bei jedem Lauf pusht.

> **⚠⚠ Eine Datenklasse, die nur beschriftet und nicht platziert, ist keine Schranke,
> sondern eine Aufschrift. Und sie stand in einem Kommentar — an der einzigen Stelle, die
> kein Werkzeug dieses Hauses liest (`aggregation.steckbrief` schneidet jede Zeile bei
> `#` ab).**

⚠ Der Gegenbeleg stand die ganze Zeit daneben: `pool.gruendung_vorlegen`, der Weg der
**Team**-Gründung, sagt dasselbe Wort korrekt an („bleibt OHNE GitHub-Remote und trägt
.kein-remote"). **Zwei Gründungswege, ein Begriff, zwei Bedeutungen** — die B033-Familie
mit einem Gründungsweg als vergessener Kopie.

⚠⚠ Und die zweite Hälfte war schlimmer als die erste: `organigramm.sammle` fiel für
`datenklasse` **fest auf `"intern"`** zurück, wenn eine Einheit nicht in der
Team-Registry steht — und dort steht **kein** Projekt. Ein als `sensibel` gegründetes
Projekt wurde im Organigramm als `intern` ausgewiesen, also als das Gegenteil dessen, was
in seinem eigenen Steckbrief stand.

> **Ein fester Rückfall auf einen der beiden möglichen Werte macht aus „nicht
> nachgesehen" eine Auskunft — und hier bedeutet der erfundene Wert „darf nach außen".**

Vertreter von `L-2026-08-21dc`.
"""
import os
import shutil
import sys
import tempfile
import unittest

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAUS = os.path.dirname(WURZEL)
sys.path.insert(0, os.path.join(WURZEL, "scripts"))
sys.path.insert(0, WURZEL)
import organigramm  # noqa: E402
import projekt_setup  # noqa: E402


def _feldzeilen(pfad):
    """Die Zeilen, die ein Leser dieses Hauses sieht — Kommentare weggeschnitten.

    ⚠ Genau diese Zerlegung macht `aggregation.steckbrief`; sie steht hier nach, weil der
    Befund die **Unsichtbarkeit** war und nicht der Inhalt.
    """
    with open(pfad, encoding="utf-8") as f:
        return [z.split("#", 1)[0].strip() for z in f if z.split("#", 1)[0].strip()]


class DieKlasseEntscheidetDenOrt(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        os.makedirs(os.path.join(self.root, "process", "templates"), exist_ok=True)

    def _erzeuge(self, kennung, klasse):
        return projekt_setup.erzeuge(self.root, kennung, "Testprojekt",
                                     "Ein Satz Auftrag", datenklasse=klasse,
                                     heute="2026-08-21")

    def test_sensibel_entsteht_oberhalb_von_projects_und_ohne_remote(self):
        """⚠⚠ Der gemessene Fall: `projects` hat einen Remote, also darf es dort nicht liegen."""
        pfad = self._erzeuge("team-x", "sensibel")
        self.assertEqual(os.path.join(self.root, "team-x"), pfad)
        self.assertFalse(os.path.exists(os.path.join(self.root, "projects", "team-x")))
        self.assertTrue(os.path.isfile(os.path.join(pfad, ".kein-remote")),
                        ".kein-remote fehlt — abschluss.cmd würde das Repo pushen")

    def test_intern_bleibt_im_sammelrepo(self):
        """Die Gegenrichtung: ohne sie wäre ein Bau grün, der ALLES nach oben legt.

        ⚠ Der Monorepo-Beschluss `pm/D003` gilt unverändert für die Regelklasse.
        """
        pfad = self._erzeuge("p99", "intern")
        self.assertEqual(os.path.join(self.root, "projects", "p99"), pfad)
        self.assertFalse(os.path.exists(os.path.join(pfad, ".kein-remote")),
                         ".kein-remote bei `intern` wäre eine Regel, die nicht gilt "
                         "(dieselbe Überlegung wie bei team-dashboard)")

    def test_die_datenklasse_ist_ein_FELD_und_kein_kommentar(self):
        """⚠⚠ Der Kern des Befunds: sichtbar für die Leser, nicht nur für Menschen."""
        pfad = self._erzeuge("team-y", "sensibel")
        zeilen = _feldzeilen(os.path.join(pfad, "steckbrief.yaml"))
        self.assertIn("datenklasse: sensibel", zeilen,
                      "die Datenklasse überlebt das Wegschneiden der Kommentare nicht — "
                      "genau der Zustand vor SWR-208")
        self.assertIn("profil: entwicklung", zeilen)

    def test_eine_unzulaessige_klasse_schreibt_nichts(self):
        """Unter Unklarheit wird nichts angelegt — auch kein halber Ordner."""
        with self.assertRaises(ValueError):
            self._erzeuge("team-z", "egal")
        self.assertFalse(os.path.exists(os.path.join(self.root, "team-z")))
        self.assertFalse(os.path.exists(os.path.join(self.root, "projects", "team-z")))


class DasOrganigrammErFINDETKeineKlasse(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _einheit(self, name, steckbrief):
        pfad = os.path.join(self.root, name)
        os.makedirs(os.path.join(pfad, "tickets"), exist_ok=True)
        os.makedirs(os.path.join(pfad, ".git"), exist_ok=True)
        with open(os.path.join(pfad, "steckbrief.yaml"), "w", encoding="utf-8") as f:
            f.write(steckbrief)
        return pfad

    def test_der_steckbrief_wird_gelesen(self):
        """⚠⚠ Vorher: `"intern"` — für jedes Projekt, weil kein Projekt in der Registry steht."""
        self._einheit("team-x", 'beschreibung: "x"\nstatus: aktiv\ndatenklasse: sensibel\n')
        daten = organigramm.sammle(self.root)
        eintrag = [e for e in daten["einheiten"] if e["einheit"] == "team-x"][0]
        self.assertEqual("sensibel", eintrag["datenklasse"])

    def test_ohne_angabe_bleibt_es_beim_default(self):
        """Die Gegenprobe — sonst wäre die Zusicherung nach einem Kahlschlag ebenfalls grün."""
        self._einheit("p99", 'beschreibung: "x"\nstatus: aktiv\n')
        daten = organigramm.sammle(self.root)
        eintrag = [e for e in daten["einheiten"] if e["einheit"] == "p99"][0]
        self.assertEqual("intern", eintrag["datenklasse"])


class AmEchtenBestandGemessen(unittest.TestCase):
    """⚠ Eine Zusicherung, die den ECHTEN Bestand liest (`SWR-189`-Bauform).

    Ohne sie prüft diese Datei nur ihre eigenen Vorrichtungen — und die Vorrichtung ist
    das, was der Autor sich vorgestellt hat.
    """

    def test_jede_einheit_mit_kein_remote_ist_sensibel(self):
        if not os.path.isdir(os.path.join(HAUS, "process")):
            self.skipTest("kein Organisationskontext (einzeln ausgechecktes Repo)")
        daten = organigramm.sammle(HAUS)
        klasse = {e["einheit"]: e["datenklasse"] for e in daten["einheiten"]}
        ohne_remote = [n for n, p in organigramm.entdecke_einheiten(HAUS).items()
                       if os.path.isfile(os.path.join(p, ".kein-remote"))]
        self.assertTrue(ohne_remote,
                        "Grundmenge leer: keine Einheit trägt .kein-remote — die "
                        "Zusicherung sagt damit nichts (SWR-128-Familie)")
        for name in ohne_remote:
            self.assertEqual("sensibel", klasse.get(name),
                             "%s trägt .kein-remote, wird aber als %r ausgewiesen — "
                             "Aufschrift und Ablage widersprechen sich"
                             % (name, klasse.get(name)))


if __name__ == "__main__":
    unittest.main()
