#!/usr/bin/env python3
"""SWR-173/174 (platform/T-0027, VIERTE Berührung — gebaut statt ein viertes Mal verschoben).

⚠⚠ Der Befund, um den es geht, ist **kein Rechenfehler**. In fünf von sechs Sprints stand
im Entwurf des Abschlussberichts eine fortgeschriebene statt einer gemessenen Zahl; zweimal
war die Abweichung beziffert (1155/1128, 1128/1147). **Alle fünf sind vor dem Commit
gefunden worden — alle fünf durch Nachrechnen, keine einzige durch eine Zusicherung.**

> **Jede dieser fünf Korrekturen belegt, dass die Sorgfalt DA war. Was fehlte, ist nicht
> Aufmerksamkeit, sondern eine Stelle, an der die Zahl ENTSTEHT statt abgeschrieben zu
> werden — und eine Zusicherung, die den Bericht dagegenhält, BEVOR er gepusht ist**
> (Frage 3 des Tickets: *läuft die Prüfung vor oder nach dem Zeitpunkt, an dem der Fehler
> Schaden anrichtet?*).

⚠ Diese Datei ist die zweite Hälfte. Die erste ist `platform/scripts/kennzahlen.py`.

⚠⚠ **Was hier ausdrücklich NICHT geprüft wird: der Parkplatz.** Er ist eine
Momentaufnahme und wächst zwischen Messung und Lesen weiter — der **neunte** Beleg des
Tickets (`9506` war beim Lesen schon falsch, obwohl korrekt gemessen).

> **Eine gemessene Zahl ohne den Zeitpunkt ihrer Messung altert genauso lautlos wie eine
> geschätzte.** Geprüft wird deshalb, dass der Block einen Zeitpunkt trägt — nicht, dass
> die Zahl noch stimmt.
"""
import io
import os
import sys
import unittest

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PLATFORM)
sys.path.insert(0, os.path.join(_PLATFORM, "scripts"))

import kennzahlen  # noqa: E402

_WURZEL = os.path.dirname(_PLATFORM)
_PLAN = os.path.join(_WURZEL, kennzahlen.PLAN)


def _plantext():
    with io.open(_PLAN, encoding="utf-8") as f:
        return f.read()


class MessungTest(unittest.TestCase):
    """Die Quelle selbst — und die Gegenprobe gegen eine Messung, die nichts misst."""

    @classmethod
    def setUpClass(cls):
        cls.werte = kennzahlen.miss(_WURZEL)

    def test_die_grundmenge_ist_nicht_leer(self):
        """⚠ SWR-128/165: eine Prüfung, die nichts liest, meldet ebenfalls „keine

        Abweichung". Die Größenordnungen stehen hier, damit eine Fassung, die 0 misst,
        nicht als grün durchgeht.
        """
        self.assertGreater(self.werte["tests"], 1000)
        self.assertGreater(self.werte["testdateien"], 50)
        self.assertGreater(self.werte["swr"], 100)

    def test_kein_ladefehler_verkleinert_die_sammlung_still(self):
        """⚠⚠ Der Weg, auf dem diese Zahl **fallen** kann, ohne dass jemand etwas löscht:

        eine Testdatei, die sich nicht importieren lässt, taucht in der Sammlung nicht auf.
        `discover` meldet das in `loader.errors` — und eine Kennzahl, die einen Importfehler
        als „weniger Tests" ausweist, wäre eine falsche Zahl mit korrekter Herkunft.
        """
        self.assertEqual(self.werte["ladefehler"], 0)

    def test_die_matrix_wird_gelesen_und_nicht_geglaubt(self):
        self.assertIsNotNone(self.werte["swr"])
        self.assertEqual(self.werte["luecken"], 0)

    def test_offene_tickets_und_wartende_haengen_zusammen(self):
        """Wer auf einen Menschen wartet, ist offen — sonst zählen zwei Zahlen

        verschiedene Mengen und niemand liest beide (der Fehler aus Sprint 24)."""
        self.assertLessEqual(self.werte["wartet_auf_mensch"], self.werte["tickets_offen"])


class VergleichTest(unittest.TestCase):
    """Der Vergleich selbst — inklusive der Fälle, in denen er rot werden MUSS."""

    def test_gleiche_zahlen_sind_keine_abweichung(self):
        g = {"tests": 10, "testdateien": 2, "swr": 5, "luecken": 0,
             "briefkasten_offen": 0, "tickets_offen": 3, "wartet_auf_mensch": 1}
        self.assertEqual(kennzahlen.vergleiche(dict(g), g), [])

    def test_eine_verfaelschte_zahl_faellt_auf(self):
        """⚠ Genau der Fall aus Sprint 21: der Bericht sagt 1155, gemessen sind 1128."""
        g = {"tests": 1128, "testdateien": 2, "swr": 5, "luecken": 0,
             "briefkasten_offen": 0, "tickets_offen": 3, "wartet_auf_mensch": 1}
        b = dict(g, tests=1155)
        self.assertEqual(kennzahlen.vergleiche(b, g), [("tests", 1155, 1128)])

    def test_eine_fehlende_zahl_ist_auch_eine_abweichung(self):
        """⚠⚠ Ohne diese Zusicherung wäre ein Bericht **ohne** Zahlen der grünste von

        allen — der Fehler, den SWR-128 fünf Sprints lang verborgen hat, hier auf den
        Bericht statt auf die Testmenge angewandt.
        """
        g = {"tests": 1128, "testdateien": 2, "swr": 5, "luecken": 0,
             "briefkasten_offen": 0, "tickets_offen": 3, "wartet_auf_mensch": 1}
        self.assertEqual(kennzahlen.vergleiche({}, g),
                         [(f, None, g[f]) for f in kennzahlen.VERGLEICHSFELDER])

    def test_der_parkplatz_wird_bewusst_nicht_verglichen(self):
        """⚠ Der neunte Beleg des Tickets, als Zusicherung: er ist eine Momentaufnahme.

        Stünde er in `VERGLEICHSFELDER`, wäre diese Prüfung nach wenigen Minuten rot und
        würde damit genau das Wegsehen trainieren, gegen das SWR-166 gebaut worden ist.
        """
        self.assertNotIn("parkplatz", kennzahlen.VERGLEICHSFELDER)
        g = {"parkplatz": 10395}
        self.assertEqual(kennzahlen.vergleiche({"parkplatz": 9506}, g), [])


class BlockTest(unittest.TestCase):
    """Der Block: schreiben und wieder lesen — eine Quelle, zwei Richtungen."""

    def test_geschriebenes_wird_gelesen(self):
        w = {"tests": 1256, "swr": 172, "parkplatz": 10395}
        gelesen, zp = kennzahlen.lies_block(kennzahlen.block(w, sprint=27))
        self.assertEqual(gelesen, w)
        self.assertTrue(zp, "der Block muss seinen Zeitpunkt tragen")

    def test_ohne_block_kommt_leer_zurueck_statt_zufall(self):
        self.assertEqual(kennzahlen.lies_block("nur Fließtext"), ({}, ""))


class SprintplanTest(unittest.TestCase):
    """⚠⚠ Die eigentliche Zusicherung: der Bericht dieses Hauses gegen die Messung.

    Erwartungswert, **vor dem Bauen aufgeschrieben** (die Bauform, die sich in `SWR-170`
    bewährt hat): beim ersten Lauf steht der Block im Plan und ist deckungsgleich —
    **0 Abweichungen**. Wird er das nicht, ist entweder der Bericht falsch oder diese
    Prüfung, und beides ist ein Fund.
    """

    def test_der_sprintplan_traegt_den_block(self):
        werte, _ = kennzahlen.lies_block(_plantext())
        self.assertTrue(werte, "pm/management/sprint-aktuell.md hat keinen Kennzahlenblock "
                               "— python platform/scripts/kennzahlen.py --schreibe")

    def test_der_block_traegt_seinen_zeitpunkt(self):
        _, zp = kennzahlen.lies_block(_plantext())
        self.assertTrue(zp, "eine gemessene Zahl ohne Zeitpunkt altert wie eine geschätzte")

    def test_die_zahlen_im_bericht_stimmen_mit_der_messung(self):
        bericht, _ = kennzahlen.lies_block(_plantext())
        gemessen = kennzahlen.miss(_WURZEL)
        ab = kennzahlen.vergleiche(bericht, gemessen)
        self.assertEqual(ab, [], "Bericht und Messung laufen auseinander: " + "; ".join(
            f"{f}: Bericht {i}, gemessen {s}" for f, i, s in ab) +
            " — python platform/scripts/kennzahlen.py --repos . --schreibe")


if __name__ == "__main__":
    unittest.main()
