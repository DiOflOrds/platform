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

Vertreter von `L-2026-08-21dc` — und, nach dem Gegenlesen, von `L-2026-08-21dg`:
zwei der drei dort benannten Faelle (der ungeprueft gebliebene Halbsatz `status: aktiv`
und die behauptete statt hergestellte Mengengleichheit) stehen hier als Zusicherung.
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


# SWR-221 (platform/T-0074): der Wächter dieser Zusicherungen fragt ihre EIGENE Eingabe.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bestandswaechter  # noqa: E402


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

    def test_jeder_gruendungsweg_schreibt_status_aktiv(self):
        """⚠⚠ Der Halbsatz von `SWR-208`, der beim ersten Bau OHNE Zusicherung blieb.

        Gefunden vom unabhängigen Gegenlesen: `status: aktiv` aus **beiden**
        Gründungswegen entfernt — und **kein einziger** von 139 Tests wurde rot. Genau
        dieser fehlende Halbsatz hat `projects/p13` sein Core Team gekostet, und die
        Anforderung, die ihn repariert, hatte ihn selbst nicht abgesichert.

        > **Ein Halbsatz in einer Anforderung, den keine Zusicherung vertritt, ist eine
        > Absichtserklärung. Er hält bis zum nächsten Bau — und der war hier derselbe.**
        """
        pfad = self._erzeuge("team-s", "sensibel")
        self.assertIn("status: aktiv", _feldzeilen(os.path.join(pfad, "steckbrief.yaml")),
                      "projekt_setup schreibt keinen Status — organigramm."
                      "effektive_besetzungen überspringt die Einheit stillschweigend")
        # Der ZWEITE Gründungsweg: der Pool-Knopf. ⚠ Er wird über seinen Quelltext
        # geprüft und nicht ausgeführt: `gruendung_ausfuehren` schreibt nach Git, und
        # eine Vorrichtung, die das täte, hätte einen Fuß im echten Bestand (SWR-207).
        with open(os.path.join(WURZEL, "backend", "pool.py"), encoding="utf-8") as f:
            quelle = f.read()
        i = quelle.index("steckbrief = ")
        self.assertIn("status: aktiv", quelle[i:i + 400],
                      "der Pool-Knopf schreibt wieder einen Steckbrief ohne Status — "
                      "das ist der gemessene Fall von projects/p13")

    def test_die_datenklassen_sind_EINE_menge_und_keine_kopie(self):
        """⚠⚠ Zweiter Befund des Gegenlesens: der Kommentar behauptete die Gleichheit.

        `projekt_setup` trug `("sensibel",)` und `pool` `("sensibel", "geheim")`, dazu
        zwei gegen vier Klassen — mit einem Kommentar daneben, das sei *„dieselbe Menge"*.

        > **Ein Ticket, das die B033-Falle benennt, und ein Bau, der sie im selben Atemzug
        > wieder aufstellt. Ein Kommentar, der Gleichheit BEHAUPTET, stellt sie nicht her —
        > `assertIs` tut es.**
        """
        from backend import pool
        self.assertIs(pool.KLASSEN_OHNE_REMOTE, projekt_setup.KLASSEN_OHNE_REMOTE)
        self.assertEqual(list(pool.STECKBRIEF_KLASSEN), projekt_setup.DATENKLASSEN)

    def test_auch_geheim_landet_ohne_remote(self):
        """Die Folge des Befunds, als eigener Fall: `geheim` war hier gar nicht zulässig."""
        pfad = self._erzeuge("team-g", "geheim")
        self.assertEqual(os.path.join(self.root, "team-g"), pfad)
        self.assertTrue(os.path.isfile(os.path.join(pfad, ".kein-remote")))

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


@bestandswaechter.am_bestand("team-mail/.kein-remote", "promt-team/.kein-remote")
class AmEchtenBestandGemessen(unittest.TestCase):
    """⚠ Eine Zusicherung, die den ECHTEN Bestand liest (`SWR-189`-Bauform).

    Ohne sie prüft diese Datei nur ihre eigenen Vorrichtungen — und die Vorrichtung ist
    das, was der Autor sich vorgestellt hat.
    """

    def test_jede_einheit_mit_kein_remote_ist_sensibel(self):
        # ⚠ HIER STAND EIN WÄCHTER AUF `process` (bis Sprint 39, platform/T-0074).
        # Er hat nicht gehalten: die CI von `platform` checkt `process` MIT aus. Die
        # Eingabe dieser Zusicherung sind die Einheiten MIT `.kein-remote` —
        # `team-mail` und `promt-team` —, und die fehlen dort. Genannt wird jetzt,
        # was gelesen wird (SWR-221, `am_bestand` über der Klasse).
        daten = organigramm.sammle(HAUS)
        klasse = {e["einheit"]: e["datenklasse"] for e in daten["einheiten"]}
        ohne_remote = [n for n, p in organigramm.entdecke_einheiten(HAUS).items()
                       if os.path.isfile(os.path.join(p, ".kein-remote"))]
        self.assertTrue(ohne_remote,
                        "Grundmenge leer: keine Einheit trägt .kein-remote — die "
                        "Zusicherung sagt damit nichts (SWR-128-Familie)")
        # ⚠ Gegen die MENGE und nicht gegen das Wort „sensibel": `pool` führt zwei
        # Klassen ohne Remote (`sensibel`, `geheim`). Der erste Bau prüfte hart auf
        # „sensibel" — eine zulässige `geheim`-Einheit hätte diese Zusicherung
        # falsch-rot gemacht. Gefunden vom Gegenlesen.
        for name in ohne_remote:
            self.assertIn(klasse.get(name), projekt_setup.KLASSEN_OHNE_REMOTE,
                          "%s trägt .kein-remote, wird aber als %r ausgewiesen — "
                          "Aufschrift und Ablage widersprechen sich"
                          % (name, klasse.get(name)))


if __name__ == "__main__":
    unittest.main()
