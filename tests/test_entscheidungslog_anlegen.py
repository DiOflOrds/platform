"""Das Entscheidungslog wird beim ersten Eintrag angelegt (SWR-152, platform/T-0022).

⚠⚠ **Anlass ist ein Fehlschlag in Produktion, gemeldet vom Auftraggeber.** Er hat
`promt-team/T-0009` — eine **Klasse-A-Entscheidung** — über die Inbox mit „A" entschieden,
und der Schreibweg starb mit:

    [Errno 2] No such file or directory:
    '...\\promt-team\\management\\decisions\\decision-log.md'

`promt-team` hat nie ein `management/decisions/` bekommen. Angelegt wird es von
`pool.gruende` bei der **Gründung** — und die Repos, die anders entstanden sind
(`promt-team`, `platform`), haben keins.

> **Der Schreibweg setzte eine Datei voraus, die ein ANDERER Weg anlegt. Solange jedes Repo
> durch diesen anderen Weg entstanden ist, ist die Annahme unsichtbar richtig.**

⚠ **Was diese Prüfungen NICHT hätten finden können und was sie deshalb messen.** Kein
bestehender Test wäre rot geworden: die Testfixtures legen ihre Verzeichnisse selbst an —
also genau der blinde Fleck aus `L-2026-08-17ai` (*welche Zusicherung prüft etwas, das die
Testdatei selbst eingerichtet hat?*). Die **Gegenprobe** unten baut deshalb ausdrücklich ein
Repo **ohne** `management/decisions/` und zeigt, dass es den Fall überhaupt gibt.

Verifiziert: SWR-152.

Ausführung: python -m unittest discover platform/tests
"""
import os
import shutil
import sys
import tempfile
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
from backend import inbox  # noqa: E402
from backend import pool  # noqa: E402


class LogAnlegenTest(unittest.TestCase):
    """Verifiziert: SWR-152."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.repo = os.path.join(self.root, "promt-team")
        # ⚠ Bewusst NUR `tickets/` — kein `management/decisions/`. Das ist der Zustand,
        # den `promt-team` am 2026-08-17 wirklich hatte.
        os.makedirs(os.path.join(self.repo, "tickets"))
        self.log = os.path.join(self.repo, "management", "decisions", "decision-log.md")

    def test_der_fall_gibt_es_ueberhaupt(self):
        """GEGENPROBE zuerst: ohne sie prüfen die Zusicherungen unten einen Zustand, den
        die Testdatei selbst hergestellt hat (`L-2026-08-17ai`). Verifiziert: SWR-152."""
        self.assertFalse(os.path.exists(os.path.dirname(self.log)),
                         "das Verzeichnis existiert schon — der Fall ist nicht der echte")
        with self.assertRaises(FileNotFoundError):
            open(self.log, "a", encoding="utf-8")

    def test_das_log_wird_angelegt(self):
        """Verifiziert: SWR-152."""
        inbox._log_sicherstellen(self.log, "promt-team")
        self.assertTrue(os.path.isfile(self.log))

    def test_der_kopf_ist_WORTGLEICH_zu_pool(self):
        """⚠⚠ Zwei Wege, die dieselbe Datei in zwei Gestalten anlegen, sind zwei Wahrheiten
        über ihr Format — und die Zeile, die `entscheide` anhängt, passt dann irgendwann nur
        zu einer davon (B033).

        Gemessen am **importierten** Kopf und nicht an einer abgeschriebenen Kopie: eine
        Zusicherung, die das Literal selbst trägt, prüft sich gegen sich selbst
        (`L-2026-08-17an`). Verifiziert: SWR-152."""
        inbox._log_sicherstellen(self.log, "promt-team")
        with open(self.log, encoding="utf-8") as f:
            inhalt = f.read()
        self.assertIn(pool.LOG_TABELLENKOPF, inhalt)
        self.assertIn("Append-only", inhalt)
        self.assertIn("promt-team", inhalt)

    def test_die_herkunft_steht_IN_der_datei(self):
        """⚠ Ein Log, das plötzlich da ist, wirft beim nächsten Leser die Frage auf, wer es
        angelegt hat und ob etwas fehlt. Die Datei beantwortet sie selbst.
        Verifiziert: SWR-152."""
        inbox._log_sicherstellen(self.log, "promt-team")
        with open(self.log, encoding="utf-8") as f:
            self.assertIn("SWR-152", f.read())

    def test_ein_BESTEHENDES_log_wird_NICHT_angefasst(self):
        """⚠⚠ Die wichtigste Zusicherung dieser Datei. Das Log ist **append-only**; ein
        Weg, der unter Umständen überschreibt, ist an dieser Stelle das Schlimmste, was
        passieren kann — er löscht Entscheidungen, und zwar genau die, die jemand später
        sucht.

        Gemessen **byteweise**, nicht an der Länge. Verifiziert: SWR-152."""
        os.makedirs(os.path.dirname(self.log))
        vorher = b"# Decision Log promt-team\n\n| ID |\n|---|\n| D000 | irgendwas |\n"
        with open(self.log, "wb") as f:
            f.write(vorher)
        inbox._log_sicherstellen(self.log, "promt-team")
        with open(self.log, "rb") as f:
            self.assertEqual(f.read(), vorher)

    def test_zweimal_aufrufen_aendert_nichts(self):
        """Idempotenz: der zweite Aufruf trifft den `exists`-Zweig.
        Verifiziert: SWR-152."""
        inbox._log_sicherstellen(self.log, "promt-team")
        with open(self.log, "rb") as f:
            erst = f.read()
        inbox._log_sicherstellen(self.log, "promt-team")
        with open(self.log, "rb") as f:
            self.assertEqual(f.read(), erst)

    def test_entscheide_ruft_es_VOR_dem_schreiben(self):
        """⚠ Die Reihenfolge ist der Grund, warum der Fehlschlag in Produktion **sauber**
        war: das Log wird vor dem Ticket beschrieben, also stand nach dem Absturz weder eine
        Logzeile noch ein Ticketvermerk da.

        Wäre `_log_sicherstellen` nach `_naechste_d_id` gerutscht, hätte die Nummernvergabe
        wieder auf eine fehlende Datei gegriffen. Gemessen an der **Stellung im Quelltext**,
        weil ein Verhaltenstest den Unterschied nicht sieht, solange beides funktioniert.

        ⚠⚠ **Der erste Wurf dieser Zusicherung war falsch rot** — er suchte dateiweit nach
        `_naechste_d_id(log_pfad)` und fand die **Definition** in Zeile 142 statt des
        Aufrufs in Zeile 219.

        > **Eine Textsuche kann eine Definition nicht von ihrem Aufruf unterscheiden — und
        > die Definition steht nun einmal vor dem Aufruf.**

        Sechster Fehlalarm derselben Familie in drei Tagen (nach fünf über Kommentare).
        Gemessen wird deshalb **im Rumpf von `entscheide`** und nicht in der Datei.
        Verifiziert: SWR-152."""
        quelle = open(os.path.join(_HIER, "..", "backend", "inbox.py"),
                      encoding="utf-8").read()
        anfang = quelle.index("def entscheide(")
        rumpf = quelle[anfang:]
        i_sicher = rumpf.index("_log_sicherstellen(log_pfad")
        i_id = rumpf.index("_naechste_d_id(log_pfad)")
        i_schreib = rumpf.index('with open(log_pfad, "a"')
        self.assertLess(i_sicher, i_id, "das Log wird nach der Nummernvergabe angelegt")
        self.assertLess(i_sicher, i_schreib)


class KeinRepoOhneLogTest(unittest.TestCase):
    """Verifiziert: SWR-152 — der Bestand, nicht die Attrappe."""

    def test_der_wirkliche_bestand_wird_gemessen(self):
        """⚠ Die Zusicherungen oben prüfen die Reparatur. Diese hier prüft, ob es den
        Mangel im **echten** Bestand noch gibt — und sie ist bewusst **kein Gate**: ein
        Repo ohne Entscheidungslog ist kein Fehler, solange die Inbox eins anlegt, sobald es
        gebraucht wird.

        Sie steht hier, damit die **Zahl** sichtbar ist. Wächst sie, ist ein neuer Weg
        entstanden, der Repos ohne Pflichtartefakt erzeugt. Verifiziert: SWR-152."""
        wurzel = os.path.dirname(os.path.dirname(_HIER))
        ohne = []
        for name in sorted(os.listdir(wurzel)):
            repo = os.path.join(wurzel, name)
            if not os.path.isdir(os.path.join(repo, "tickets")):
                continue
            if not os.path.isfile(os.path.join(repo, "management", "decisions",
                                               "decision-log.md")):
                ohne.append(name)
        # Gemessen 2026-08-17 (Sprint 20): `platform` — `promt-team` bekommt seins mit der
        # Verbuchung von T-0009. ⚠ Die Liste steht hier NAMENTLICH und nicht als Zahl:
        # eine Zahl sagt nicht, welches Repo dazugekommen ist (B038).
        self.assertLessEqual(len(ohne), 2, f"Repos ohne Entscheidungslog: {ohne}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
