#!/usr/bin/env python3
"""SWR-213 (platform/T-0065): die Post eines Laufs sind Erstbriefe UND Beiträge.

⚠⚠ **Der Anlass ist die eigene Kennzahl von Sprint 34.** Am 2026-08-21 um **12:26** hat
der Auftraggeber geschrieben (`team-dashboard/N-0004`), damit einen seit Sprint 32
gesperrten Vorgang entsperrt und den Brief wieder auf `status: offen` gesetzt.
`kennzahlen.briefe_im_lauf` meldete für denselben Zeitraum **0** und stand so im
Abschlussbericht.

> **„Kein Brief eingegangen" und „kein NEUER Brief eingegangen" sind zwei Sätze, und die
> Kennzahl trug den ersten.**

**DoD 1, gezählt statt geschätzt** (ganzer Bestand, 69 Briefe): **69** Erstbriefe, **74**
Folgebeiträge — **52 % aller Post sind Beiträge**. Damit ist DoD 2 gemessen und nicht
gemeint: Beiträge sind die Mehrheit, nicht der Rand.

⚠⚠ **Und der teuerste Teil war, dass die naheliegende Reparatur nicht gereicht hätte.**
`DATUM_IM_KOPF` endete bis Sprint 35 nach `\\d{2}:\\d{2}` mit Leerzeichen als einzigem
Trenner. Der Kopf `## E. John (2026-08-21T10:26:10+00:00)` — geschrieben von
`BEITRAG_FORMAT` derselben Datei — wurde damit als `2026-08-21` gelesen, also als
**Mitternacht**, und Mitternacht liegt vor jedem Sprintstart.

> **Der Zerleger hat die Uhrzeit weggeschnitten, die er selbst geschrieben hat. Eine
> Kennzahl, die nur ihre eigene Leseseite repariert, hätte weiter 0 gemeldet — und diesmal
> grün aussehend.**
"""
import os
import sys
import unittest
from datetime import datetime

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PLATFORM)
sys.path.insert(0, os.path.join(_PLATFORM, "scripts"))

import kennzahlen  # noqa: E402
from backend import briefkasten  # noqa: E402

_WURZEL = os.path.dirname(_PLATFORM)


class ZerlegerBehaeltDieUhrzeit(unittest.TestCase):
    """Die Ebene unter der Kennzahl — ohne sie ist die Kennzahl blind."""

    def test_volle_iso_zeit_wird_nicht_auf_das_datum_gekuerzt(self):
        treffer = briefkasten.DATUM_IM_KOPF.search("E. John (2026-08-21T10:26:10+00:00)")
        self.assertEqual(treffer.group(0), "2026-08-21T10:26:10+00:00",
                         "der Zerleger darf die Uhrzeit nicht wegschneiden")

    def test_die_drei_bestandsformen_treffen_weiterhin(self):
        for roh in ("2026-08-21", "2026-08-21 11:50", "2026-08-21T10:26:10+00:00"):
            with self.subTest(roh=roh):
                self.assertEqual(briefkasten.DATUM_IM_KOPF.search(roh).group(0), roh)

    def test_klassifikation_wandert_NICHT(self):
        """⚠ Die Gegenprobe. `DATUM_IM_KOPF` entscheidet mit, was ein Beitrag IST —
        ein weiterer Ausdruck darf keinen Abschnitt zum Beitrag machen."""
        self.assertFalse(briefkasten._ist_beitragskopf(
            "⚠ Drei Punkte, die wir vor dem Bau geklärt haben wollen"))
        self.assertFalse(briefkasten._ist_beitragskopf("3. Was eine Entscheidung braucht"))
        self.assertFalse(briefkasten._ist_beitragskopf("Frist 23.08."))
        self.assertTrue(briefkasten._ist_beitragskopf("E. John (2026-08-21T10:26:10+00:00)"))
        self.assertTrue(briefkasten._ist_beitragskopf("Vollzug (Team, 2026-08-16, Routine)"))

    def test_bestand_zerfaellt_unveraendert(self):
        """69 Briefe, 74 Folgebeiträge — vor und nach der Erweiterung dieselbe Menge."""
        briefe = folgen = 0
        for _e, pfad in _briefe():
            briefe += 1
            folgen += sum(1 for b in briefkasten.beitraege(_body(pfad))
                          if not b["ist_erstbeitrag"])
        self.assertGreaterEqual(briefe, 69)
        self.assertGreaterEqual(folgen, 74)
        self.assertGreater(folgen, briefe * 0.9,
                           "Beitraege sind die Mehrheit der Post, nicht der Rand")


class PostImLauf(unittest.TestCase):
    """`kennzahlen.zaehle_post_im_lauf` am echten Bestand."""

    def test_der_beitrag_von_12_26_wird_gezaehlt(self):
        """⚠⚠ Die Gegenprobe aus der DoD, am echten Ereignis und nicht an einer Attrappe.

        Sprint 34 startete 12:07; der Beitrag kam 12:26. Die alte Kennzahl sagte 0.
        """
        p = kennzahlen.zaehle_post_im_lauf(_WURZEL, datetime(2026, 8, 21, 12, 7))
        self.assertGreaterEqual(p["beitraege"], 1,
                                "der Beitrag von 12:26 MUSS im Fenster von Sprint 34 liegen")

    def test_ein_beitrag_von_danach_faellt_heraus(self):
        """Die zweite Hälfte des Paares: ein späterer Start sieht ihn NICHT mehr."""
        p = kennzahlen.zaehle_post_im_lauf(_WURZEL, datetime(2026, 8, 21, 23, 59))
        self.assertEqual(p["beitraege"], 0)

    def test_drei_zahlen_und_keine_summe(self):
        p = kennzahlen.zaehle_post_im_lauf(_WURZEL, datetime(2026, 8, 20, 0, 0))
        self.assertEqual(set(p), {"erstbriefe", "beitraege", "unbestimmbar"})
        self.assertGreater(p["erstbriefe"], 0)
        self.assertGreater(p["beitraege"], 0)

    def test_datum_ohne_uhrzeit_wird_nur_am_starttag_unbestimmbar(self):
        """⚠ Der eigene Fehler dieses Laufs, als Zusicherung festgehalten.

        Der erste Entwurf meldete ALLE 46 datumslosen Beiträge als `unbestimmbar` —
        auch einen vom 15.08., über den das Datum längst entscheidet.

        > **Eine Größe, die Bekanntes als unbekannt führt, ist so falsch wie eine, die
        > Unbekanntes als Null führt; sie irrt nur in die bequemere Richtung.**
        """
        frueh = kennzahlen.zaehle_post_im_lauf(_WURZEL, datetime(2026, 8, 21, 12, 7))
        spaet = kennzahlen.zaehle_post_im_lauf(_WURZEL, datetime(2026, 8, 10, 0, 0))
        self.assertLess(spaet["unbestimmbar"], 46,
                        "ein Datum vor dem Starttag ist BESTIMMT, nicht unbestimmbar")
        self.assertLessEqual(frueh["unbestimmbar"], 46)

    def test_ohne_laufenden_sprint_None_und_nicht_null(self):
        """`None` heisst unbekannt und nie null (Vorgabewert-Fehler aus Sprint 32)."""
        self.assertIsNone(kennzahlen.zaehle_post_im_lauf(os.path.join(_WURZEL, "p0")))

    def test_erstbeitrag_wird_nicht_doppelt_gezaehlt(self):
        """Der Erstbeitrag IST der Brief — sonst zaehlt jede Post zweimal."""
        p = kennzahlen.zaehle_post_im_lauf(_WURZEL, datetime(2026, 8, 20, 0, 0))
        briefe = kennzahlen.zaehle_briefe_im_lauf(_WURZEL, datetime(2026, 8, 20, 0, 0))
        self.assertEqual(p["erstbriefe"], briefe,
                         "die Erstbrief-Haelfte muss der alten Groesse gleichen")


class KeineZweiteZerlegung(unittest.TestCase):
    """DoD 3: die Zerlegung ist GETEILT, nicht kopiert (B033)."""

    def test_kennzahlen_ruft_briefkasten_beitraege(self):
        import inspect
        quelle = inspect.getsource(kennzahlen.zaehle_post_im_lauf)
        self.assertIn("beitraege(", quelle)
        self.assertNotIn("JEDE_H2", quelle,
                         "kein zweiter Parser neben SWR-126")
        self.assertNotIn("re.compile", quelle)


def _briefe():
    import board
    return board.briefkasten_dateien(_WURZEL)


def _body(pfad):
    import io
    with io.open(pfad, encoding="utf-8") as f:
        text = f.read()
    teile = text.split("---")
    return "---".join(teile[2:]) if len(teile) >= 3 else text


if __name__ == "__main__":
    unittest.main()
