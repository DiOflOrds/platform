"""Unit-Verifikation Sprintregister mit ENDE (SWR-136, platform/T-0013).

Anlass, gemessen und zweimal an einem Tag eingetreten:
`SESSION-BEFUND-2026-08-17-1105-nebenlaeufigkeit.md` (10:25 gegen den seit 10:04
laufenden Sprint 11) und `SESSION-BEFUND-2026-08-17-1339-nebenlaeufigkeit.md`
(13:19 gegen den 13:31 registrierten Sprint 14). Beim zweiten Mal mit Folgen: **beide
Läufe vergaben die Anforderungsnummer SWR-134**, entdeckt beim Lesen des fremden
Commits und nicht von einer Prüfung.

Das Register maß bis Sprint 14 **Lauferöffnungen und keine Laufenden** — es eröffnete
klaglos einen neuen Sprint, während der vorige schrieb.

⚠ **Die Zeitgrenze ist vor dem Bauen gemessen und verworfen** (Sprint 13, jetzt im
Ticket verankert): 12 Abstände, Median 57 Min, Minimum **15**, **7 von 12 unter 60**.
Die ursprüngliche DoD 2 („kein `ende` **und** Start weniger als einen Takt zurück")
hätte die Mehrheit der regulären Folgeläufe abgewiesen. Mehrere Zusicherungen hier sind
**Gegenproben gegen diese verworfene Bauart** und stehen absichtlich drin: eine
Entscheidung, die nur im Bericht steht, ist keine (`L-2026-08-17ag`).

Ausführung: python -m unittest discover platform/tests
"""
import ast
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sprint_register  # noqa: E402
import preflight  # noqa: E402


def _repo(root, name, sha):
    """Ein Repo-Skelett mit lesbarem Kopf — ohne git, ohne subprocess."""
    git = os.path.join(root, name, ".git")
    os.makedirs(os.path.join(git, "refs", "heads"), exist_ok=True)
    with open(os.path.join(git, "HEAD"), "w", encoding="utf-8") as f:
        f.write("ref: refs/heads/main\n")
    with open(os.path.join(git, "refs", "heads", "main"), "w", encoding="utf-8") as f:
        f.write(sha + "\n")


class EndeTest(unittest.TestCase):
    """DoD 1: `beende()` schreibt `ende`; eine Zeile ohne `ende` ist ein laufender Sprint."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def _zeilen(self):
        with open(sprint_register._pfad(self.root), encoding="utf-8") as f:
            return f.read()

    def test_zeile_ohne_ende_ist_ein_laufender_sprint(self):
        """Der Kernsatz der Anforderung, direkt geprüft. Verifiziert: SWR-136."""
        self.assertIsNone(sprint_register.laufender(self.root))  # leer: keiner läuft
        sprint_register.beginne(self.root, "a")
        self.assertIsNotNone(sprint_register.laufender(self.root))
        sprint_register.beende(self.root, "a")
        self.assertIsNone(sprint_register.laufender(self.root))

    def test_beende_faltet_ende_in_den_sprint(self):
        sprint_register.beginne(self.root, "a")
        sprint_register.beende(self.root, "a", jetzt=datetime(2026, 8, 17, 15, 5))
        bestand = sprint_register.lies(self.root)
        self.assertEqual(len(bestand), 1, "die Ergänzung darf kein zweiter Sprint sein")
        self.assertEqual(bestand[0]["ende"], "2026-08-17 15:05")
        self.assertEqual(bestand[0]["nr"], 1)
        self.assertEqual(bestand[0]["kennung"], "a")

    def test_beende_ist_idempotent(self):
        """Ein Lauf, der seinen Abschluss wiederholt, erfindet keinen zweiten
        Endezeitpunkt. Verifiziert: SWR-136."""
        sprint_register.beginne(self.root, "a")
        sprint_register.beende(self.root, "a", jetzt=datetime(2026, 8, 17, 15, 5))
        vorher = self._zeilen()
        self.assertEqual(sprint_register.beende(
            self.root, "a", jetzt=datetime(2026, 8, 17, 16, 0)), 1)
        self.assertEqual(self._zeilen(), vorher, "zweiter Aufruf hat angehängt")
        self.assertEqual(sprint_register.lies(self.root)[0]["ende"], "2026-08-17 15:05")

    def test_beende_auf_unbekannte_kennung_erfindet_nichts(self):
        """`None` heißt „diese Kennung steht nicht im Register" — und ausdrücklich nicht
        „erledigt". Ein stillschweigendes Anlegen wäre B038. Verifiziert: SWR-136."""
        sprint_register.beginne(self.root, "a")
        self.assertIsNone(sprint_register.beende(self.root, "gibt-es-nicht"))
        self.assertEqual(len(sprint_register.lies(self.root)), 1)

    def test_beende_ohne_kennung_wird_abgelehnt(self):
        for schlecht in ("", "   ", None):
            with self.assertRaises(ValueError):
                sprint_register.beende(self.root, schlecht)

    def test_datei_wird_nur_angehaengt_nie_umgeschrieben(self):
        """⚠ Die Zusicherung, die die ganze Bauart trägt.

        `ende` in die bestehende Zeile zu schreiben wäre der bequemere Weg — und der
        einzige, der bei zwei gleichzeitigen Schreibern Daten verliert, also genau in dem
        Fall, für den dieses Modul existiert. Geprüft wird deshalb nicht das Ergebnis,
        sondern die **Unveränderlichkeit des Anfangs der Datei**.
        Verifiziert: SWR-136.
        """
        sprint_register.beginne(self.root, "a")
        vorher = self._zeilen()
        sprint_register.beende(self.root, "a")
        nachher = self._zeilen()
        self.assertTrue(nachher.startswith(vorher),
                        "die bestehenden Zeilen wurden verändert statt ergänzt")
        self.assertGreater(len(nachher.splitlines()), len(vorher.splitlines()))

    def test_ergaenzung_zu_unbekanntem_lauf_erzeugt_keinen_phantomsprint(self):
        """Eine Ergänzungszeile ohne passenden Sprint wird übersprungen — sie darf keinen
        Eintrag erfinden und den Zähler nicht bewegen. Verifiziert: SWR-136."""
        sprint_register.beginne(self.root, "a")
        with open(sprint_register._pfad(self.root), "a", encoding="utf-8") as f:
            f.write('{"kennung": "fremd", "ende": "2026-01-01 00:00"}\n')
        self.assertEqual(len(sprint_register.lies(self.root)), 1)
        self.assertEqual(sprint_register.aktuell(self.root), 1)


class UeberlappungTest(unittest.TestCase):
    """DoD 2/3/5/6: die Eröffnung wird verweigert, solange ein Sprint läuft."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        _repo(self.root, "pm", "a" * 40)

    def test_zweiter_lauf_im_selben_takt_wird_abgewiesen(self):
        """Der Vorfall selbst, als Zusicherung. Verifiziert: SWR-136."""
        sprint_register.beginne(self.root, "lauf-1")
        with self.assertRaises(sprint_register.SprintLaeuft) as ctx:
            sprint_register.beginne(self.root, "lauf-2")
        self.assertEqual(ctx.exception.nr, 1)
        self.assertEqual(ctx.exception.kennung, "lauf-1")
        self.assertEqual(sprint_register.aktuell(self.root), 1,
                         "der abgewiesene Lauf hat trotzdem eine Nummer bekommen")

    def test_die_meldung_nennt_den_laufenden_sprint(self):
        """⚠ B038: eine Meldung ohne den Gegenstand ist keine Meldung. Der abgewiesene
        Lauf muss sagen können, WER läuft — sonst kann er es nicht berichten.
        Verifiziert: SWR-136."""
        sprint_register.beginne(self.root, "lauf-1")
        with self.assertRaises(sprint_register.SprintLaeuft) as ctx:
            sprint_register.beginne(self.root, "lauf-2")
        text = str(ctx.exception)
        self.assertIn("lauf-1", text)
        self.assertIn("Sprint 1", text)

    def test_abweisung_vermerkt_die_beobachtung(self):
        """Die Abweisung ist nicht nur ein Nein, sie **misst**: die Schreibspur wird
        angehängt, damit der nächste Lauf vergleichen kann. Ohne diesen Vermerk gäbe es
        keine Übernahme und ein abgestürzter Lauf sperrte für immer.
        Verifiziert: SWR-136."""
        sprint_register.beginne(self.root, "lauf-1")
        with self.assertRaises(sprint_register.SprintLaeuft):
            sprint_register.beginne(self.root, "lauf-2")
        eintrag = sprint_register.lies(self.root)[0]
        self.assertIn("spur", eintrag)
        self.assertEqual(eintrag["beobachtet_von"], "lauf-2")

    def test_eigene_kennung_wird_nie_abgewiesen(self):
        """Idempotenz schlägt Überlappungsschutz: der laufende Lauf selbst darf
        `beginne()` beliebig oft aufrufen. Wäre es anders, würde jeder zweite Aufruf im
        eigenen Skript den Lauf abwürgen. Verifiziert: SWR-136/SWR-106."""
        self.assertEqual(sprint_register.beginne(self.root, "lauf-1"), 1)
        self.assertEqual(sprint_register.beginne(self.root, "lauf-1"), 1)
        self.assertEqual(len(sprint_register.lies(self.root)), 1)

    # ------------------------------------------------------------------ Gegenproben
    def test_regulaerer_folgelauf_wird_NICHT_abgewiesen(self):
        """⚠⚠ DoD 5, die Gegenprobe, ohne die diese Anforderung die Routine anhielte.

        Ein Sprint, der ordentlich beendet wurde, blockiert den nächsten nicht — und zwar
        **unabhängig davon, wie kurz** der Abstand ist. Verifiziert: SWR-136.
        """
        sprint_register.beginne(self.root, "lauf-1", jetzt=datetime(2026, 8, 17, 10, 0))
        sprint_register.beende(self.root, "lauf-1", jetzt=datetime(2026, 8, 17, 10, 14))
        self.assertEqual(
            sprint_register.beginne(self.root, "lauf-2",
                                    jetzt=datetime(2026, 8, 17, 10, 15)), 2)

    def test_keine_zeitgrenze_in_beide_richtungen(self):
        """⚠⚠ Die Gegenprobe gegen die **verworfene** Bauart der ersten DoD.

        Gemessen (Sprint 13): 7 von 12 Abständen lagen unter dem Takt, das Minimum bei
        15 Minuten. Deshalb darf die Uhr in **keiner** Richtung entscheiden:

        * 15 Minuten Abstand und `ende` vorhanden -> **erlaubt** (die alte DoD hätte
          abgewiesen und die Mehrheit der regulären Folgeläufe getroffen);
        * 10 Tage Abstand und **kein** `ende` -> **abgewiesen** (das Alter allein macht
          einen Sprint nicht zum Abbruch; nur die Schreibspur kann das entscheiden).

        Verifiziert: SWR-136.
        """
        sprint_register.beginne(self.root, "alt", jetzt=datetime(2026, 8, 1, 9, 0))
        with self.assertRaises(sprint_register.SprintLaeuft):
            sprint_register.beginne(self.root, "neu", jetzt=datetime(2026, 8, 11, 9, 0))

    def test_abbruch_wird_an_der_schreibspur_erkannt(self):
        """DoD 3: kein Commit seit der letzten Beobachtung -> abgebrochen, Übernahme
        erlaubt. Die Wartezeit ist damit **ein** Takt und nicht unendlich.
        Verifiziert: SWR-136."""
        sprint_register.beginne(self.root, "toter-lauf")
        with self.assertRaises(sprint_register.SprintLaeuft):
            sprint_register.beginne(self.root, "naechster")  # erste Beobachtung
        self.assertEqual(sprint_register.beginne(self.root, "naechster"), 2)

    def test_ende_wird_auch_im_abbruchfall_geschrieben(self):
        """⚠ DoD 6. Ohne diese Zeile wäre jede zweite Registerzeile ohne `ende` und die
        Prüfung eine Dauerwarnung, die niemand mehr liest. Verifiziert: SWR-136."""
        sprint_register.beginne(self.root, "toter-lauf")
        with self.assertRaises(sprint_register.SprintLaeuft):
            sprint_register.beginne(self.root, "naechster")
        sprint_register.beginne(self.root, "naechster")
        alt = sprint_register.lies(self.root)[0]
        self.assertTrue(alt.get("ende"), "der abgebrochene Sprint trägt kein 'ende'")
        self.assertTrue(alt.get("abgebrochen"))
        self.assertIn("naechster", alt.get("ende_notiz", ""))

    def test_arbeitender_lauf_wird_nicht_ueberholt(self):
        """⚠ Die Gegenprobe zur Abbrucherkennung: bewegt sich die Spur, arbeitet der
        andere noch — und wird **wieder** abgewiesen. Eine Uhr sieht bei 15 Minuten
        Abstand denselben Wert wie bei einem Absturz nach 15 Minuten; nur die
        Schreibspur unterscheidet die beiden. Verifiziert: SWR-136."""
        sprint_register.beginne(self.root, "arbeitet")
        with self.assertRaises(sprint_register.SprintLaeuft):
            sprint_register.beginne(self.root, "naechster")
        _repo(self.root, "pm", "b" * 40)  # der andere Lauf hat committet
        with self.assertRaises(sprint_register.SprintLaeuft) as ctx:
            sprint_register.beginne(self.root, "naechster")
        self.assertTrue(ctx.exception.spur_bewegt)
        self.assertEqual(sprint_register.aktuell(self.root), 1)


class SchreibspurTest(unittest.TestCase):
    """Die Messung, auf der die Abbrucherkennung ruht."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def test_spur_ist_stabil_wenn_nichts_geschrieben_wird(self):
        _repo(self.root, "pm", "a" * 40)
        _repo(self.root, "platform", "c" * 40)
        self.assertEqual(sprint_register.schreibspur(self.root),
                         sprint_register.schreibspur(self.root))

    def test_spur_bewegt_sich_bei_einem_commit_in_IRGENDEINEM_repo(self):
        """„in irgendeinem Repo" ist wörtlich gemeint — ein Lauf, der nur `p9` anfasst,
        ist genauso am Leben wie einer, der `pm` anfasst. Verifiziert: SWR-136."""
        _repo(self.root, "pm", "a" * 40)
        _repo(self.root, "p9", "d" * 40)
        vorher = sprint_register.schreibspur(self.root)
        _repo(self.root, "p9", "e" * 40)
        self.assertNotEqual(sprint_register.schreibspur(self.root), vorher)

    def test_ordner_ohne_git_zaehlt_nicht(self):
        _repo(self.root, "pm", "a" * 40)
        os.makedirs(os.path.join(self.root, "kein-repo"), exist_ok=True)
        self.assertEqual(sprint_register.schreibspur(self.root), "pm=" + "a" * 40)

    def test_kopf_liest_abgekoppelten_stand_und_gepackte_refs(self):
        git = os.path.join(self.root, "los", ".git")
        os.makedirs(git)
        with open(os.path.join(git, "HEAD"), "w", encoding="utf-8") as f:
            f.write("f" * 40 + "\n")
        self.assertEqual(sprint_register._kopf_sha(os.path.join(self.root, "los")),
                         "f" * 40)
        git2 = os.path.join(self.root, "gepackt", ".git")
        os.makedirs(git2)
        with open(os.path.join(git2, "HEAD"), "w", encoding="utf-8") as f:
            f.write("ref: refs/heads/main\n")
        with open(os.path.join(git2, "packed-refs"), "w", encoding="utf-8") as f:
            f.write("# pack-refs with: peeled\n" + "9" * 40 + " refs/heads/main\n")
        self.assertEqual(sprint_register._kopf_sha(os.path.join(self.root, "gepackt")),
                         "9" * 40)

    def test_unlesbarer_kopf_ist_keine_bewegung(self):
        """⚠ Ein Repo, dessen Kopf nicht lesbar ist, darf nicht als „hat geschrieben"
        gelten — sonst wäre jede Übernahme durch einen Lesefehler blockiert, und der
        Fehler sähe aus wie Leben. Verifiziert: SWR-136."""
        os.makedirs(os.path.join(self.root, "leer", ".git"))
        self.assertEqual(sprint_register._kopf_sha(os.path.join(self.root, "leer")), "")
        self.assertEqual(sprint_register.schreibspur(self.root), "")

    def test_die_messung_ruft_KEIN_git_auf(self):
        """⚠⚠ Die Gegenprobe aus der Lehre von SWR-134.

        Dort wurde gemessen, dass auf diesem Mount schon ein **lesendes** `git status`
        eine `index.lock` hinterlässt, die nicht mehr gelöscht werden kann. Eine Prüfung,
        die Nebenläufigkeit erkennen soll und dabei selbst Sperren erzeugt, wäre ihr
        eigener Schadensfall — deshalb liest `schreibspur` von der Platte.

        Gezählt wird über den **Syntaxbaum** und nicht im Text, damit ein Wort in einem
        Kommentar nicht rot wird (der Fehlalarm aus SWR-128 und SWR-134).
        Verifiziert: SWR-136.
        """
        quelle = os.path.join(os.path.dirname(__file__), "..", "scripts",
                              "sprint_register.py")
        with open(quelle, encoding="utf-8") as f:
            baum = ast.parse(f.read())
        importe = [n for n in ast.walk(baum)
                   if isinstance(n, (ast.Import, ast.ImportFrom))]
        namen = set()
        for n in importe:
            if isinstance(n, ast.Import):
                namen.update(a.name.split(".")[0] for a in n.names)
            elif n.module:
                namen.add(n.module.split(".")[0])
        self.assertNotIn("subprocess", namen,
                         "der Sprintzähler ruft git auf und erzeugt damit Sperren")


class BefundTest(unittest.TestCase):
    """DoD 4: der Zustand wird gemeldet — und der Stichtag verhindert Lärm am Tag 1."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        _repo(self.root, "pm", "a" * 40)

    def _bis(self, nr, ende=True):
        for i in range(1, nr + 1):
            k = f"s{i}"
            if ende:
                sprint_register.beginne(self.root, k)
                sprint_register.beende(self.root, k)
            else:
                self._roh(i, k)  # Altbestand: eroeffnet, nie beendet

    def _roh(self, nr, kennung):
        """Eine Registerzeile von Hand — der Zustand VOR SWR-136.

        ⚠ Bewusst nicht über `beginne()`: das würde ab SWR-136 abgewiesen. Genau darum
        braucht der Altbestand einen eigenen Weg in den Test — er ist der Zustand, den
        die neue Regel **nicht** rückwirkend bestrafen darf.
        """
        pfad = sprint_register._pfad(self.root)
        os.makedirs(os.path.dirname(pfad), exist_ok=True)
        with open(pfad, "a", encoding="utf-8") as f:
            f.write('{"nr": %d, "kennung": "%s", "start": "2026-08-17 09:00", '
                    '"takt_min": 60}\n' % (nr, kennung))

    def test_laufender_sprint_ist_KEIN_befund(self):
        """⚠ DoD 6 als Gegenprobe: während eines Laufs trägt seine eigene Zeile
        naturgemäß kein `ende`. Ihn zu melden hieße, in **jedem** Lauf einen Befund zu
        erzeugen — eine Dauerwarnung, die nach zwei Sprints niemand mehr liest.
        Verifiziert: SWR-136."""
        self._bis(sprint_register.STICHTAG_ENDE_SPRINT)
        k = "laeuft-gerade"
        sprint_register.beginne(self.root, k)
        self.assertIsNotNone(sprint_register.laufender(self.root))
        self.assertEqual(sprint_register.nicht_beendete(self.root), [])

    def test_altbestand_vor_dem_stichtag_ist_kein_befund(self):
        """⚠ Dieselbe Falle wie bei den 42 Altbestands-DRs in SWR-131: eine Prüfung, die
        am Tag ihrer Einführung vierzehnfach rot startet, trainiert das Wegsehen.
        Verifiziert: SWR-136."""
        self._bis(sprint_register.STICHTAG_ENDE_SPRINT, ende=False)
        # keiner der Altsprints trägt ein `ende` — Befund trotzdem 0
        self.assertEqual(sprint_register.nicht_beendete(self.root), [])

    def test_luecke_ab_dem_stichtag_wird_gefunden(self):
        """Die Gegenrichtung: ein abgeschlossener Sprint ab dem Stichtag ohne `ende` ist
        ein echter Befund — sonst wäre der Stichtag eine Amnestie ohne Ende.
        Verifiziert: SWR-136."""
        stichtag = sprint_register.STICHTAG_ENDE_SPRINT
        self._bis(stichtag - 1)                     # 1..stichtag-1, alle beendet
        self._roh(stichtag, "vergessen")            # ab Stichtag, kein `ende`
        self._roh(stichtag + 1, "danach")           # der laufende Sprint
        luecken = sprint_register.nicht_beendete(self.root)
        self.assertEqual([e["nr"] for e in luecken], [stichtag])
        self.assertEqual(luecken[0]["kennung"], "vergessen")

    def test_preflight_meldet_den_registerzustand_immer(self):
        """SWR-122: wer eine Prüfung baut, legt im selben Zug fest, wer ihr Ergebnis
        liest. Die Zeile erscheint auch im guten Fall — ein stiller Check ist von einem
        nicht gelaufenen nicht zu unterscheiden. Verifiziert: SWR-136."""
        self._bis(2)
        puffer = io.StringIO()
        with redirect_stdout(puffer):
            preflight.preflight(self.root, skip_tests=True, keep_locks=True)
        ausgabe = puffer.getvalue()
        self.assertIn("Sprintregister:", ausgabe)
        self.assertIn("Sprint 2", ausgabe)

    def test_preflight_zaehlt_die_luecke_als_befund(self):
        stichtag = sprint_register.STICHTAG_ENDE_SPRINT
        self._bis(stichtag - 1)
        self._roh(stichtag, "vergessen")
        self._roh(stichtag + 1, "danach")
        puffer = io.StringIO()
        with redirect_stdout(puffer):
            befunde = preflight.preflight(self.root, skip_tests=True, keep_locks=True)
        ausgabe = puffer.getvalue()
        self.assertIn("ohne 'ende'", ausgabe)
        self.assertIn("vergessen", ausgabe, "der Befund nennt die Kennung nicht (B038)")
        self.assertGreaterEqual(befunde, 1)


class BestandTest(unittest.TestCase):
    """Die alten Leser sehen weiter, was sie vorher sahen."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def test_aktuell_und_takt_ueberleben_die_faltung(self):
        """`aktuell` und `takt_minuten` zählen Sprints, nicht Zeilen. Nach SWR-136 gibt
        es mehr Zeilen als Sprints — beide Zahlen dürfen sich davon nicht bewegen.
        Verifiziert: SWR-136/SWR-106."""
        sprint_register.beginne(self.root, "a", takt_min=30)
        sprint_register.beende(self.root, "a")
        sprint_register.beginne(self.root, "b", takt_min=60)
        sprint_register.beende(self.root, "b")
        self.assertEqual(sprint_register.aktuell(self.root), 2)
        self.assertEqual(sprint_register.takt_minuten(self.root), 60)
        self.assertEqual(len(sprint_register.lies(self.root)), 2)
        self.assertEqual(len(sprint_register.ereignisse(self.root)), 4)

    def test_kaputte_ergaenzung_haelt_den_zaehler_nicht_an(self):
        sprint_register.beginne(self.root, "a")
        sprint_register.beende(self.root, "a")
        with open(sprint_register._pfad(self.root), "a", encoding="utf-8") as f:
            f.write("{kein json\n\n[1,2,3]\n")
        self.assertEqual(sprint_register.aktuell(self.root), 1)
        self.assertEqual(sprint_register.beginne(self.root, "b"), 2)


if __name__ == "__main__":
    unittest.main()
