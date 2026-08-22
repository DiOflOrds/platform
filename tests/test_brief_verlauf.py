"""Der Brief wird ein Verlauf (SWR-126, pm/T-0059 aus pm/T-0039 / Brief pm/N-0031).

Der Auftraggeber: "Ich moechte gerne auf meine Fragen und deine Antworten direkt
weiter kommentieren". Das Elternticket wurde VIERMAL um genau einen Sprint
verschoben, jedes Mal mit wortgleicher Begruendung; Sprint 10 hat es zerlegt und
diesen Teil als erste Sacharbeit von Sprint 11 zugesagt.

Der Kern ist nicht das Anhaengen, sondern die ZERLEGUNG bestehender Briefe ohne
Migration. Die Regel dafuer ist am Bestand gemessen — `BestandTest` unten ist die
Gegenprobe, die gegen ein naives "jede ## ist ein Beitrag" rot wird.
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from backend import briefkasten  # noqa: E402

WURZEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")

ALT = """Ich moechte gerne weiter kommentieren.

## Antwort des Teams (Sprint 9, 2026-08-17)

Angenommen als T-0039.

## 1. Was heute fehlt

Ein Beitragsformat.

## 2. Was gebaut wird (pm/T-0040, Frist 23.08.)

Der Schreibpfad.
"""


# SWR-221 (platform/T-0074): der Wächter dieser Zusicherungen fragt ihre EIGENE Eingabe.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bestandswaechter  # noqa: E402


class ZerlegungTest(unittest.TestCase):

    def test_bestandsbrief_hat_genau_zwei_beitraege(self):
        """Zwei — nicht vier. Die beiden numerierten Ueberschriften sind ABSCHNITTE
        innerhalb der Antwort. Gegen ein naives '##' waeren es vier."""
        b = briefkasten.beitraege(ALT)
        self.assertEqual(len(b), 2)
        self.assertTrue(b[0]["ist_erstbeitrag"])
        self.assertEqual(b[0]["text"], "Ich moechte gerne weiter kommentieren.")
        self.assertEqual(b[1]["absender"], "Antwort des Teams")
        self.assertEqual(b[1]["zeit"], "2026-08-17")
        self.assertIn("## 1. Was heute fehlt", b[1]["text"])

    def test_zweiter_teambeitrag_von_hand_wird_erkannt(self):
        """`pm/N-0015` hat einen zweiten Block '## Vollzug (Team, 2026-08-16, …)'.
        Er IST ein Beitrag — die Praxis gab es vor dem Werkzeug."""
        text = ALT + "\n## Vollzug (Team, 2026-08-16, Routine-Session)\n\nGetan.\n"
        b = briefkasten.beitraege(text)
        self.assertEqual(len(b), 3)
        self.assertEqual(b[2]["absender"], "Vollzug")
        self.assertEqual(b[2]["zeit"], "2026-08-16")
        self.assertEqual(b[2]["text"], "Getan.")

    def test_abschnitt_ohne_iso_datum_zerlegt_nicht(self):
        """'Frist 23.08.' ist kein ISO-Datum — genau daran haengt die Abgrenzung."""
        self.assertFalse(briefkasten._ist_beitragskopf(
            "2. Was gebaut wird (pm/T-0040, Frist 23.08.)"))
        self.assertTrue(briefkasten._ist_beitragskopf("E. John (2026-08-17T10:00:00+00:00)"))

    def test_brief_ohne_antwort_ist_ein_beitrag(self):
        b = briefkasten.beitraege("Nur eine Frage.")
        self.assertEqual(len(b), 1)
        self.assertTrue(b[0]["ist_erstbeitrag"])

    def test_erstbeitrag_erfindet_absender_und_zeit_nicht(self):
        """Sie stehen im Frontmatter, nicht in einer Ueberschrift. Sie hier zu raten
        waere B038; `_parse` setzt sie aus den Feldern nach."""
        b = briefkasten.beitraege(ALT)
        self.assertEqual(b[0]["absender"], "")
        self.assertEqual(b[0]["zeit"], "")

    def test_spalte_antwort_bleibt_wortgleich(self):
        """Die Zusage von B054 ist unveraendert: zwei Bloecke, der zweite mit ALLEM
        darunter. `app.js` liest sie weiter, bis pm/T-0060 den Verlauf zeigt."""
        nachricht, antwort, datum = briefkasten.spalte_antwort(ALT)
        self.assertEqual(nachricht, "Ich moechte gerne weiter kommentieren.")
        self.assertTrue(antwort.startswith("Angenommen als T-0039."))
        self.assertIn("## 2. Was gebaut wird", antwort)
        self.assertEqual(datum, "2026-08-17")


@bestandswaechter.am_bestand("pm/management/briefkasten", "platform/management/briefkasten")
class BestandTest(unittest.TestCase):
    """⚠ Die Gegenprobe an allen echten Briefen — sie ist der eigentliche Beweis.

    Gegen ein naives 'jede ## ist ein Beitrag' wird dieser Test rot: 11 Briefe
    tragen Abschnittsueberschriften innerhalb ihrer Antwort.
    """

    def test_kein_bestandsbrief_wird_an_einem_abschnitt_zerlegt(self):
        import glob
        import re
        gepruefte = 0
        for pfad in glob.glob(os.path.join(WURZEL, "*", "management", "briefkasten",
                                           "N-*.md")) + \
                glob.glob(os.path.join(WURZEL, "projects", "*", "management",
                                       "briefkasten", "N-*.md")):
            with open(pfad, encoding="utf-8") as f:
                text = f.read()
            m = re.match(r"(?s)^---\n(.*?)\n---\n?(.*)$", text)
            body = m.group(2) if m else text
            alle_h2 = briefkasten.JEDE_H2.findall(body)
            beitraege = briefkasten.beitraege(body)
            koepfe = [b for b in beitraege if not b["ist_erstbeitrag"]]
            # Jeder erkannte Beitragskopf ist auch eine ##-Zeile, aber nicht umgekehrt.
            self.assertLessEqual(len(koepfe), len(alle_h2), msg=pfad)
            # Kein Brief verliert seinen Erstbeitrag.
            self.assertTrue(beitraege and beitraege[0]["ist_erstbeitrag"], msg=pfad)
            # Jeder erkannte Beitrag traegt eine Zeitangabe (das ist die Regel selbst).
            for b in koepfe:
                self.assertTrue(b["zeit"], msg="%s: %s" % (pfad, b["absender"]))
            gepruefte += 1
        self.assertGreaterEqual(gepruefte, 41, "Bestand unerwartet klein")

    def test_zerlegung_stimmt_mit_spalte_antwort_ueberein(self):
        """B033: eine Quelle. Was `spalte_antwort` als Nachricht sieht, muss der
        Erstbeitrag sein — an jedem echten Brief."""
        import glob
        import re
        for pfad in glob.glob(os.path.join(WURZEL, "pm", "management", "briefkasten",
                                           "N-*.md")):
            with open(pfad, encoding="utf-8") as f:
                text = f.read()
            m = re.match(r"(?s)^---\n(.*?)\n---\n?(.*)$", text)
            body = m.group(2) if m else text
            nachricht, _antwort, _d = briefkasten.spalte_antwort(body)
            erst = briefkasten.beitraege(body)[0]
            self.assertEqual(nachricht, erst["text"], msg=pfad)


class AnhaengenTest(unittest.TestCase):
    """Der Schreibpfad — in einem echten Git-Repo, weil der Commit Teil der Zusage ist."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.repo = os.path.join(self.root, "p0")
        self.verz = os.path.join(self.repo, "management", "briefkasten")
        os.makedirs(self.verz)
        # `tickets/` braucht die Projekt-Discovery — ohne sie scheitert der Aufruf an
        # "unbekanntes Projekt" und der Test pruefte eine andere Meldung als die, die in
        # seinem Namen steht (Lehre aus test_briefkasten_meldung, Sprint 10).
        os.makedirs(os.path.join(self.repo, "tickets"))
        for cmd in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"],
                    ["config", "user.name", "T"]):
            subprocess.run(["git", "-C", self.repo] + cmd, capture_output=True)
        self.brief = os.path.join(self.verz, "N-0001.md")
        self._schreibe("beantwortet", "Erste Frage.\n\n"
                       "## Antwort des Teams (Sprint 10, 2026-08-17)\n\nErste Antwort.\n")
        subprocess.run(["git", "-C", self.repo, "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", self.repo, "commit", "-qm", "start"],
                       capture_output=True)

    def _schreibe(self, status, body):
        with open(self.brief, "w", encoding="utf-8", newline="\n") as f:
            f.write("---\nvon: E. John\nzeit: 2026-08-17T06:00:00+00:00\n"
                    "status: %s\n---\n\n%s" % (status, body))

    def _lies(self):
        with open(self.brief, encoding="utf-8") as f:
            return f.read()

    def test_beitrag_wird_mit_absender_und_zeit_angehaengt(self):
        erg = briefkasten.sende(self.root, "p0", "Nachfrage im selben Brief.",
                                brief="N-0001")
        self.assertEqual(erg["brief"], "N-0001")
        self.assertTrue(erg["beitrag"])
        text = self._lies()
        self.assertIn("Nachfrage im selben Brief.", text)
        self.assertIn("## E. John (%s)" % erg["zeit"], text)
        self.assertIn("Erste Antwort.", text)   # nichts ueberschrieben

    def test_beitrag_des_menschen_setzt_status_auf_offen(self):
        """⚠ Ohne diesen Punkt waere der CR schaedlich: `offene()` traegt die
        Preflight-Zeile. Ein Beitrag an einem beantworteten Brief waere still verloren."""
        erg = briefkasten.sende(self.root, "p0", "Nachfrage.", brief="N-0001")
        self.assertTrue(erg["status_zurueckgesetzt"])
        self.assertIn("status: offen", self._lies())
        self.assertEqual(briefkasten.offene(self.root, "p0"), 1)

    def test_offener_brief_bleibt_offen_ohne_zweite_meldung(self):
        self._schreibe("offen", "Frage.\n")
        erg = briefkasten.sende(self.root, "p0", "Und noch was.", brief="N-0001")
        self.assertFalse(erg["status_zurueckgesetzt"])
        self.assertIn("status: offen", self._lies())

    def test_text_und_status_liegen_im_selben_commit(self):
        """Getrennte Commits waeren zwei Zustaende, von denen einer allein sichtbar
        werden kann — dieselbe Regel wie bei SWR-124."""
        briefkasten.sende(self.root, "p0", "Nachfrage.", brief="N-0001")
        zeig = subprocess.run(["git", "-C", self.repo, "show", "--stat", "--format=%s",
                               "HEAD"], capture_output=True, text=True)
        self.assertIn("weiterer Beitrag vom Menschen", zeig.stdout)
        diff = subprocess.run(["git", "-C", self.repo, "show", "HEAD"],
                              capture_output=True, text=True).stdout
        self.assertIn("+status: offen", diff)
        self.assertIn("Nachfrage.", diff)
        rein = subprocess.run(["git", "-C", self.repo, "status", "--porcelain"],
                              capture_output=True, text=True).stdout
        self.assertEqual(rein.strip(), "")

    def test_verlauf_enthaelt_den_neuen_beitrag(self):
        briefkasten.sende(self.root, "p0", "Nachfrage.", brief="N-0001")
        b = briefkasten.liste(self.root, "p0")["briefe"][0]
        self.assertEqual(len(b["beitraege"]), 3)
        self.assertEqual(b["beitraege"][0]["absender"], "E. John")   # aus Frontmatter
        self.assertEqual(b["beitraege"][2]["text"], "Nachfrage.")

    def test_unbekannte_kennung_wird_abgelehnt(self):
        with self.assertRaises(briefkasten.BriefkastenFehler) as f:
            briefkasten.sende(self.root, "p0", "Text.", brief="N-0099")
        self.assertEqual(f.exception.code, 404)

    def test_ungueltige_kennung_wird_vor_dem_pfadbau_abgelehnt(self):
        """Ein `..` in einer Kennung darf nie ein Verzeichnis verlassen."""
        for schlecht in ("../../etc/passwd", "N-1", "", "N-00001", "nonsense"):
            with self.assertRaises(briefkasten.BriefkastenFehler) as f:
                briefkasten.sende(self.root, "p0", "Text.", brief=schlecht)
            self.assertEqual(f.exception.code, 400, msg=schlecht)

    def test_leerer_beitrag_wird_abgelehnt(self):
        with self.assertRaises(briefkasten.BriefkastenFehler):
            briefkasten.sende(self.root, "p0", "   ", brief="N-0001")

    def test_ohne_brief_bleibt_der_alte_pfad(self):
        """Der Bestandspfad ist unberuehrt: ein neuer Brief bekommt eine neue Datei."""
        erg = briefkasten.sende(self.root, "p0", "Ganz neue Sache.")
        self.assertEqual(erg["brief"], "N-0002")
        self.assertNotIn("beitrag", erg)
        self.assertTrue(os.path.isfile(os.path.join(self.verz, "N-0002.md")))

    def test_gescheiterter_commit_verliert_den_beitrag_nicht(self):
        """SWR-121: 'nicht verbucht' ist nicht 'verloren' — und die Meldung sagt das."""
        echt = briefkasten._verbuche
        briefkasten._verbuche = lambda *a, **k: (False, "kaputt", False)
        try:
            with self.assertRaises(briefkasten.BriefkastenFehler) as f:
                briefkasten.sende(self.root, "p0", "Wichtig.", brief="N-0001")
            self.assertEqual(f.exception.code, 503)
            self.assertIn("GESPEICHERT", str(f.exception))
            self.assertIn("NICHT erneut senden", str(f.exception))
            self.assertIn("Wichtig.", self._lies())
        finally:
            briefkasten._verbuche = echt


if __name__ == "__main__":
    unittest.main()
