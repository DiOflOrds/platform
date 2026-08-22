"""Die gemessene Goldset-Baseline (SWR-149, promt-team/T-0007 DoD 4).

⚠ **Die Zusicherung, um die es hier geht, ist der DRITTE Zustand.** Ein Fall ohne
`ergebnis_heute` ist **nicht** durchgefallen — ihn als Fehlschlag zu zählen machte die
Quote schlechter, ihn wegzulassen machte sie besser, und beides wäre eine erfundene Zahl.
Das ist die Lehre von SWR-137 am Nachbarfall.

Ausführung: python -m unittest discover platform/tests
"""
import os
import sys
import tempfile
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
import goldset_baseline as gb  # noqa: E402
from backend import goldset  # noqa: E402

_WURZEL = os.path.dirname(os.path.dirname(_HIER))


def fall(**kw):
    f = {"rolle": "dev", "aufgaben_typ": "code-review", "eingabe": "x",
         "erwartetes_ergebnis": "y",
         "fehlschlag_erkannt_an": {"art": "enthaelt", "wert": "HERKUNFT_TRENNER"},
         "herkunft": ["promt-team/tickets/T-0007.md::Grenzfälle"],
         "ergebnis_heute": "platform/backend/goldset.py"}
    f.update(kw)
    return f


# SWR-221 (platform/T-0074): der Wächter dieser Zusicherungen fragt ihre EIGENE Eingabe.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bestandswaechter  # noqa: E402


@bestandswaechter.am_bestand("promt-team/management/goldset.jsonl", "promt-team/tickets")
class MessungTest(unittest.TestCase):
    """Verifiziert: SWR-149."""

    def test_erfuellt_und_nicht_erfuellt_am_echten_bestand(self):
        """Nulllage in beide Richtungen — sonst prueft der Rest gegen einen Dauerwert.
        Verifiziert: SWR-149."""
        zu, grund = gb.messe_fall(fall(), _WURZEL)
        self.assertEqual(zu, "erfuellt", grund)
        zu, grund = gb.messe_fall(
            fall(fehlschlag_erkannt_an={"art": "enthaelt",
                                        "wert": "diesen Satz gibt es dort nicht"}),
            _WURZEL)
        self.assertEqual(zu, "nicht_erfuellt", grund)

    def test_ohne_ergebnis_heute_ist_NICHT_durchgefallen(self):
        """⚠⚠ DIE Zusicherung: der dritte Zustand ist ein eigener Ausgang und keine
        Verlegenheit. Verifiziert: SWR-149."""
        f = fall()
        del f["ergebnis_heute"]
        zu, grund = gb.messe_fall(f, _WURZEL)
        self.assertEqual(zu, "nicht_entscheidbar", grund)
        self.assertNotEqual(zu, "nicht_erfuellt")

    def test_drei_zustaende_und_keine_vier(self):
        """Die Zustandsmenge steht an EINER Stelle und wird gelesen (SWR-131).
        Verifiziert: SWR-149."""
        self.assertEqual(len(gb.ZUSTAENDE), 3)
        for f in ({}, fall(), fall(fehlschlag_erkannt_an={"art": "quatsch", "wert": "x"})):
            zu, _ = gb.messe_fall(f, _WURZEL)
            self.assertIn(zu, gb.ZUSTAENDE)

    def test_datei_existiert_braucht_kein_ergebnis_heute(self):
        """⚠ Gegenprobe: diese Pruefart TRAEGT ihren Pfad. Sie als unentscheidbar zu
        fuehren hiesse, eine ausfuehrbare Pruefung nicht auszufuehren.
        Verifiziert: SWR-149."""
        f = fall(fehlschlag_erkannt_an={"art": "datei_existiert",
                                        "wert": "platform/backend/goldset.py"})
        del f["ergebnis_heute"]
        self.assertEqual(gb.messe_fall(f, _WURZEL)[0], "erfuellt")
        f2 = fall(fehlschlag_erkannt_an={"art": "datei_existiert",
                                         "wert": "gibt/es/nicht.py"})
        del f2["ergebnis_heute"]
        self.assertEqual(gb.messe_fall(f2, _WURZEL)[0], "nicht_erfuellt")

    def test_unlesbares_artefakt_ist_unentscheidbar_nicht_rot(self):
        """Ein fehlendes Artefakt ist keine Aussage ueber die Rolle. Verifiziert: SWR-149."""
        zu, _ = gb.messe_fall(fall(ergebnis_heute="gibt/es/nicht.md"), _WURZEL)
        self.assertEqual(zu, "nicht_entscheidbar")

    def test_kaputte_regex_ist_unentscheidbar(self):
        """Eine Pruefung, die nicht laeuft, hat nicht bestanden und ist nicht gescheitert.
        Verifiziert: SWR-149."""
        zu, _ = gb.messe_fall(
            fall(fehlschlag_erkannt_an={"art": "regex", "wert": "([unvollstaendig"}),
            _WURZEL)
        self.assertEqual(zu, "nicht_entscheidbar")

    def test_json_pfad_am_echten_register(self):
        """`json_pfad` laeuft gegen JSONL und findet ein Feld der ersten Zeile.
        Verifiziert: SWR-149."""
        f = fall(fehlschlag_erkannt_an={"art": "json_pfad", "wert": "0.nr"},
                 ergebnis_heute="pm/management/sprints.jsonl")
        self.assertEqual(gb.messe_fall(f, _WURZEL)[0], "erfuellt")
        f2 = fall(fehlschlag_erkannt_an={"art": "json_pfad", "wert": "0.gibtsnicht"},
                  ergebnis_heute="pm/management/sprints.jsonl")
        self.assertEqual(gb.messe_fall(f2, _WURZEL)[0], "nicht_erfuellt")


class TrennschaerfeTest(unittest.TestCase):
    """Verifiziert: SWR-149."""

    def test_ein_suchtext_der_ueberall_steht_wird_gezaehlt(self):
        """⚠⚠ Die Messung gegen die bequemste Art, ein Goldset gruen zu bekommen.
        Verifiziert: SWR-149."""
        breit = fall(fehlschlag_erkannt_an={"art": "enthaelt", "wert": "import"},
                     ergebnis_heute="platform/backend/goldset.py")
        anderer = fall(ergebnis_heute="platform/scripts/board.py")
        werte = gb.trennschaerfe([breit, anderer], _WURZEL)
        self.assertGreaterEqual(werte[0], 1, "ein Allerweltswort blieb unbemerkt")

    def test_ein_scharfer_suchtext_hat_null_fremdtreffer(self):
        """Gegenprobe — sonst zaehlte die Messung nur hoch. Verifiziert: SWR-149."""
        scharf = fall(fehlschlag_erkannt_an={"art": "enthaelt",
                                             "wert": "HERKUNFT_TRENNER"},
                      ergebnis_heute="platform/backend/goldset.py")
        anderer = fall(ergebnis_heute="platform/scripts/board.py")
        self.assertEqual(gb.trennschaerfe([scharf, anderer], _WURZEL)[0], 0)

    def test_datei_existiert_wird_nicht_gemessen(self):
        """Es gibt kein fremdes Artefakt, in dem sie aufgehen koennte — `None` statt 0,
        damit der Nenner nicht heimlich waechst. Verifiziert: SWR-149."""
        f = fall(fehlschlag_erkannt_an={"art": "datei_existiert", "wert": "x"})
        self.assertIsNone(gb.trennschaerfe([f], _WURZEL)[0])


class BerichtTest(unittest.TestCase):
    """Verifiziert: SWR-149."""

    def test_bericht_nennt_zuerst_was_nicht_gemessen_ist(self):
        """⚠ Die Einschraenkung steht VOR der Zahl. Eine Quote, deren Vorbehalt hinter ihr
        steht, wird ohne ihn gelesen. Verifiziert: SWR-149."""
        text = gb.bericht(gb.messe(_WURZEL))
        stelle_vorbehalt = text.index("NICHT gemessen")
        stelle_tabelle = text.index("| Rolle | Aufgaben-Typ")
        self.assertLess(stelle_vorbehalt, stelle_tabelle)

    def test_quote_traegt_immer_ihren_nenner(self):
        """Eine Quote ohne Nenner ist von einer vollstaendigen Messung nicht zu
        unterscheiden (SWR-140). Verifiziert: SWR-149."""
        self.assertIn("(3 von 4)", gb._quote(3, 4))
        self.assertIn("NICHT MESSBAR", gb._quote(0, 0))

    def test_bericht_warnt_dass_eine_hohe_quote_kein_zeugnis_ist(self):
        """⚠⚠ Die Pruefausdruecke sind aus den Artefakten abgeleitet — eine hohe Quote ist
        zum Teil Bauart. Ohne diesen Satz wird die Zahl als Qualitaetsaussage gelesen.
        Verifiziert: SWR-149."""
        text = gb.bericht(gb.messe(_WURZEL))
        self.assertIn("KEIN gutes Zeugnis", text)

    def test_unentscheidbare_faelle_werden_mit_beleg_genannt(self):
        """⚠ 'Namentlich' heisst mit der Belegstelle — vier Zeilen 'dev/bugfix' sind eine
        Zaehlung und keine Nennung (SWR-140). Verifiziert: SWR-149."""
        daten = gb.messe(_WURZEL)
        offen = [f for f, (zu, _) in zip(daten["faelle"], daten["messungen"])
                 if zu == "nicht_entscheidbar"]
        text = gb.bericht(daten)
        if not offen:
            self.skipTest("kein unentscheidbarer Fall im Bestand")
        for f in offen:
            self.assertIn(f["herkunft"][0], text)

    def test_leeres_goldset_schreibt_nichts(self):
        """⚠ Ein leerer Bericht an der Stelle des echten ist woertlich SWR-145.
        Verifiziert: SWR-149."""
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(gb.main(["--repos", d, "--schreibe"]), 1)
            self.assertFalse(os.path.exists(
                os.path.join(d, *gb.BERICHT.split("/"))))


@bestandswaechter.am_bestand("promt-team/management/goldset.jsonl", "promt-team/tickets")
class BestandTest(unittest.TestCase):
    """Verifiziert: SWR-149 — das wirkliche Goldset, nicht eine Attrappe."""

    def test_goldset_im_bestand_ist_mangelfrei(self):
        """⚠ Gemessen am echten Set: Form, Herkunft aufgeloest, Registry. Verifiziert:
        SWR-142, SWR-149."""
        daten = gb.messe(_WURZEL)
        self.assertEqual(daten["maengel"], [])
        self.assertEqual(daten["kaputte_zeilen"], 0)

    def test_mindestens_zwanzig_faelle_je_betrachteter_rolle(self):
        """⚠ DoD 1 von promt-team/T-0007 als Zusicherung und nicht als Zusage im Text.
        Verifiziert: SWR-149."""
        daten = gb.messe(_WURZEL)
        je_rolle = {}
        for f in daten["faelle"]:
            je_rolle[f["rolle"]] = je_rolle.get(f["rolle"], 0) + 1
        self.assertTrue(je_rolle, "kein Fall im Bestand")
        for rolle, n in je_rolle.items():
            self.assertGreaterEqual(n, 20, f"{rolle} hat nur {n} Faelle")

    def test_jeder_fall_belegt_sich_mit_einer_stelle(self):
        """⚠ Ein Beleg, der nur einen Dateinamen nennt, ist schwaecher, als er aussieht —
        eine Datei existiert auch fuer einen erfundenen Fall. Verifiziert: SWR-149."""
        for f in gb.messe(_WURZEL)["faelle"]:
            self.assertTrue(
                any(goldset.HERKUNFT_TRENNER in h for h in f["herkunft"]),
                f"{f['rolle']}/{f['aufgaben_typ']} belegt sich ohne Stelle")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
