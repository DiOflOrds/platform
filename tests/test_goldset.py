"""Das Format eines Goldset-Falls (SWR-142, promt-team/T-0006).

⚠ **Die Gegenprobe ist der Grund für diese Datei.** Ein Fall ohne
`fehlschlag_erkannt_an` wird **abgelehnt** und nicht vorbelegt — ein Vorgabewert dort
machte jede ungeschriebene Prüfung stillschweigend zu einer bestandenen.

Ausführung: python -m unittest discover platform/tests
"""
import json
import os
import sys
import tempfile
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
from backend import goldset  # noqa: E402


def fall(**kw):
    f = {"rolle": "dev", "aufgaben_typ": "code-review", "eingabe": "prüfe diesen Diff",
         "erwartetes_ergebnis": "nennt die fehlende Grenzwertprüfung",
         "fehlschlag_erkannt_an": {"art": "enthaelt", "wert": "Grenzwert"}}
    f.update(kw)
    return f


class FallTest(unittest.TestCase):
    """Verifiziert: SWR-142."""

    def test_vollstaendiger_fall_passiert(self):
        """Nulllage — sonst prueft der Rest gegen einen Dauerfehler.
        Verifiziert: SWR-142."""
        self.assertEqual(goldset.pruefe_fall(fall()), [])

    def test_ohne_fehlschlag_erkannt_an_wird_abgelehnt(self):
        """⚠⚠ DIE Zusicherung dieses Tickets: das Feld fehlt -> Ablehnung, und
        AUSDRUECKLICH keine Vorbelegung. Verifiziert: SWR-142."""
        f = fall()
        del f["fehlschlag_erkannt_an"]
        m = goldset.pruefe_fall(f)
        self.assertTrue(any("fehlschlag_erkannt_an" in x for x in m))
        self.assertNotIn("fehlschlag_erkannt_an", f, "der Pruefer hat vorbelegt")

    def test_prosa_statt_pruefung_wird_abgelehnt(self):
        """'sieht man doch' ist kein Prueffall. Verifiziert: SWR-142."""
        m = goldset.pruefe_fall(fall(fehlschlag_erkannt_an="sieht man doch"))
        self.assertTrue(any("Prosa" in x for x in m), m)

    def test_unbekannte_pruefart_wird_abgelehnt(self):
        """Die Menge ist geschlossen — sonst ist sie keine. Verifiziert: SWR-142."""
        m = goldset.pruefe_fall(
            fall(fehlschlag_erkannt_an={"art": "gefuehl", "wert": "x"}))
        self.assertTrue(any("Pruefart" in x for x in m), m)

    def test_jede_art_der_geschlossenen_menge_wird_angenommen(self):
        """⚠ Die Menge wird GELESEN und nicht wiederholt: eine zweite Schreibweise
        derselben Liste ist die Bauart, die SWR-131 gekostet hat.
        Verifiziert: SWR-142."""
        for art in goldset.PRUEF_ARTEN:
            wert = "a" if art != "regex" else "a+"
            self.assertEqual(
                goldset.pruefe_fall(fall(fehlschlag_erkannt_an={"art": art,
                                                                "wert": wert})),
                [], f"Art '{art}' der geschlossenen Menge wurde abgelehnt")

    def test_kaputte_regex_wird_abgelehnt(self):
        """Eine Pruefung, die selbst nicht laeuft, prueft nichts.
        Verifiziert: SWR-142."""
        m = goldset.pruefe_fall(fall(fehlschlag_erkannt_an={"art": "regex",
                                                            "wert": "("}))
        self.assertTrue(any("regex" in x for x in m), m)

    def test_alle_maengel_auf_einmal(self):
        """Ein Fall, der ueber fuenf Laeufe fuenfmal korrigiert wird, ist der Preis
        eines Pruefers, der beim ersten Mangel aufhoert. Verifiziert: SWR-142."""
        f = fall()
        del f["eingabe"]
        del f["erwartetes_ergebnis"]
        f["fehlschlag_erkannt_an"] = {"art": "gefuehl", "wert": ""}
        m = goldset.pruefe_fall(f)
        self.assertGreaterEqual(len(m), 4, m)

    def test_sensible_auslassung_ohne_grund_wird_abgelehnt(self):
        """⚠ Sensible Daten werden BENANNT und ausgelassen, nicht erfunden — und eine
        unerklaerte Luecke ist von Vollstaendigkeit nicht zu unterscheiden.
        Verifiziert: SWR-142."""
        m = goldset.pruefe_fall(fall(sensibel_ausgelassen=""))
        self.assertTrue(any("Luecke" in x or "Grund" in x for x in m), m)

    def test_sensible_auslassung_mit_grund_passiert(self):
        """Gegenprobe. Verifiziert: SWR-142."""
        self.assertEqual(
            goldset.pruefe_fall(fall(sensibel_ausgelassen="enthielt Klarnamen aus N-0031")),
            [])


class SetTest(unittest.TestCase):
    """Verifiziert: SWR-142."""

    def test_typ_ohne_soll_scheitern_wird_genannt(self):
        """⚠ Hier wird `soll_scheitern_auf` mehr als ein Feld: je Aufgaben-Typ muss
        MINDESTENS EINER ihn setzen, sonst belegt ein gruenes Eval nur, dass die Aufgabe
        leicht war (SWR-125 angewandt statt zitiert). Verifiziert: SWR-142."""
        m = goldset.pruefe_set([fall(), fall()])
        self.assertTrue(any("code-review" in x and "soll_scheitern_auf" in x for x in m),
                        m)

    def test_ein_fall_mit_soll_scheitern_genuegt(self):
        """Gegenprobe: die Regel gilt je TYP, nicht je Fall — sonst waere jeder leichte
        Fall ein Mangel. Verifiziert: SWR-142."""
        m = goldset.pruefe_set([fall(), fall(soll_scheitern_auf="ollama")])
        self.assertEqual(m, [])

    def test_zwei_typen_werden_getrennt_geprueft(self):
        """Der scharfe Fall: ein Typ erfuellt die Regel, der andere nicht — genannt wird
        der andere. Verifiziert: SWR-142."""
        m = goldset.pruefe_set([fall(soll_scheitern_auf="ollama"),
                                fall(aufgaben_typ="doku")])
        self.assertEqual(len(m), 1, m)
        self.assertIn("doku", m[0])


class DateiTest(unittest.TestCase):
    """Verifiziert: SWR-142."""

    def test_anhaengen_prueft_und_bleibt_append_only(self):
        """Der Schreibweg prueft selbst — eine Pruefung, die der Aufrufer anwenden muss,
        ist keine (die Lehre von SWR-134). Und die Datei waechst nur hinten.
        Verifiziert: SWR-142."""
        with tempfile.TemporaryDirectory() as d:
            pfad = os.path.join(d, "goldset.jsonl")
            goldset.haenge_an(pfad, fall())
            vorher = open(pfad, "rb").read()
            goldset.haenge_an(pfad, fall(soll_scheitern_auf="ollama"))
            nachher = open(pfad, "rb").read()
            self.assertEqual(nachher[:len(vorher)], vorher,
                             "die Datei wurde umgeschrieben statt ergaenzt")
            faelle, kaputt = goldset.lies(pfad)
            self.assertEqual((len(faelle), kaputt), (2, 0))

    def test_anhaengen_lehnt_ab_und_schreibt_nichts(self):
        """Ein abgelehnter Fall darf keine Spur hinterlassen. Verifiziert: SWR-142."""
        with tempfile.TemporaryDirectory() as d:
            pfad = os.path.join(d, "goldset.jsonl")
            f = fall()
            del f["fehlschlag_erkannt_an"]
            with self.assertRaises(ValueError):
                goldset.haenge_an(pfad, f)
            self.assertFalse(os.path.exists(pfad))

    def test_kaputte_zeile_wird_gezaehlt(self):
        """Still ueberspringen verkleinert den Nenner. Verifiziert: SWR-142."""
        with tempfile.TemporaryDirectory() as d:
            pfad = os.path.join(d, "g.jsonl")
            with open(pfad, "w", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(fall()) + "\n{kaputt\n")
            faelle, kaputt = goldset.lies(pfad)
            self.assertEqual((len(faelle), kaputt), (1, 1))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
