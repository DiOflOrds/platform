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
        """⚠⚠ Befund 4 des Gegenlesens: diese Gegenprobe war BLIND.

        Alle drei Negativbeispiele der ersten Fassung (`⚠ Drei Punkte…`, `3. Was eine
        Entscheidung braucht`, `Frist 23.08.`) haben **keine Klammer am Ende**.
        `KLAMMER_AM_ENDE` scheitert dann vorher, und `DATUM_IM_KOPF` wird nie befragt —
        der Ausdruck, den die Zusicherung bewachen soll, wurde nicht ausgeführt.
        Gemessen: `DATUM_IM_KOPF` um die deutsche Datumsform erweitert → Bestand springt
        von 74 auf 75 Beiträge, Testlauf **11/11 grün**.

        > **Ein Negativbeispiel, dem der Teil fehlt, an dem die Prüfung greift, prüft
        > nichts — es beruhigt.**

        Die Negativbeispiele tragen jetzt ihre Klammer und damit den echten Wortlaut aus
        dem Bestand.
        """
        # MIT Klammer — hier wird `DATUM_IM_KOPF` wirklich befragt:
        self.assertFalse(briefkasten._ist_beitragskopf(
            "2. Was gebaut wird (`pm/T-0040`, Frist 23.08.)"),
            "eine deutsche Datumsform darf keinen Abschnitt zum Beitrag machen")
        self.assertFalse(briefkasten._ist_beitragskopf("Was jetzt zu sehen ist (Stand 21.08.)"))
        self.assertFalse(briefkasten._ist_beitragskopf("Ehrliche Grenze (benannt)"))
        # OHNE Klammer — die alte, schwaechere Haelfte bleibt zusaetzlich stehen:
        self.assertFalse(briefkasten._ist_beitragskopf(
            "⚠ Drei Punkte, die wir vor dem Bau geklärt haben wollen"))
        self.assertFalse(briefkasten._ist_beitragskopf("3. Was eine Entscheidung braucht"))
        self.assertTrue(briefkasten._ist_beitragskopf("E. John (2026-08-21T10:26:10+00:00)"))
        self.assertTrue(briefkasten._ist_beitragskopf("Vollzug (Team, 2026-08-16, Routine)"))

    def test_bestand_zerfaellt_unveraendert(self):
        """⚠ Befund 16: hier stand `assertGreaterEqual` und der Docstring sagte
        „dieselbe Menge" — zwei verschiedene Aussagen unter einem Namen. Bei 75
        Beiträgen wäre die Zusicherung grün geblieben.

        Gemessen am Bestand vom 2026-08-21: **69** Briefe, **74** Folgebeiträge.
        Wächst der Bestand, ist die Zahl hier nachzuziehen — das ist Absicht: eine
        Schranke, die mitwächst, hält nichts fest.
        """
        briefe = folgen = 0
        for _e, pfad in _briefe():
            briefe += 1
            folgen += sum(1 for b in briefkasten.beitraege(_body(pfad))
                          if not b["ist_erstbeitrag"])
        self.assertEqual((briefe, folgen), (69, 74),
                         "die Zerlegung des Bestands darf sich durch die Erweiterung "
                         "von DATUM_IM_KOPF NICHT verschieben")
        self.assertGreater(folgen, briefe,
                           "Beitraege sind die MEHRHEIT der Post (74 > 69), "
                           "nicht 'mehr als 90 Prozent von'")


class PostImLauf(unittest.TestCase):
    """`kennzahlen.zaehle_post_im_lauf` am echten Bestand.

    ⚠⚠ **Befund 9 des Gegenlesens: diese Klasse war zeitzonenabhängig und unter `TZ=UTC`
    rot.** Die Briefe tragen UTC, das Sprintregister Wanduhrzeit; der eine reale Beitrag
    mit Uhrzeit (`10:26:10+00:00`) fällt nur bei Offset ≥ +2 h hinter den Sprintstart
    12:07. Auf einem Läufer in UTC wurde die Zusicherung rot, **ohne dass etwas kaputt
    war** — und westlich davon wäre sie grün geblieben, obwohl die Zeitzonenrechnung
    ausgebaut ist.

    > **Eine Zusicherung, die an der Uhr ihres Läufers hängt, misst den Läufer.**

    Die Zone ist deshalb festgenagelt — auf die des Betriebs, weil das Sprintregister
    Wanduhrzeit führt (`SWR-206`).
    """

    @classmethod
    def setUpClass(cls):
        import time
        cls._tz = os.environ.get("TZ")
        os.environ["TZ"] = "Europe/Berlin"
        if hasattr(time, "tzset"):
            time.tzset()

    @classmethod
    def tearDownClass(cls):
        import time
        if cls._tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = cls._tz
        if hasattr(time, "tzset"):
            time.tzset()

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

        ⚠ Befund 16: die zweite Hälfte stand als `assertLessEqual(…, 46)` da und galt
        damit für **jede denkbare** Implementierung, auch für den Fehler, gegen den sie
        geschrieben war. Sie prüft jetzt die Sache selbst: `unbestimmbar` zählt nur den
        **Starttag**, also verschiebt ein anderer Starttag die Zahl.
        """
        am_21 = kennzahlen.zaehle_post_im_lauf(_WURZEL, datetime(2026, 8, 21, 12, 7))
        am_10 = kennzahlen.zaehle_post_im_lauf(_WURZEL, datetime(2026, 8, 10, 0, 0))
        self.assertEqual(am_10["unbestimmbar"], 0,
                         "am 10.08. gibt es keine datumslose Post -> 0, nicht 'weniger "
                         "als alle'")
        self.assertGreater(am_21["unbestimmbar"], 0,
                           "am 21.08. gibt es datumslose Post -> sie MUSS unbestimmbar "
                           "heissen und darf nicht still verschwinden")
        gesamt = _datumslose_beitraege()
        self.assertLess(am_21["unbestimmbar"], gesamt,
                        f"nur der Starttag ist unbestimmbar, nicht alle {gesamt}")

    def test_erstbrief_ohne_uhrzeit_faellt_nicht_durch_alle_drei_zahlen(self):
        """⚠⚠ Befund 10 des Gegenlesens: die Datumsregel galt nur für BEITRÄGE.

        Ein Erstbrief mit `zeit: 2026-08-25` (nur Datum, nach dem Start) wurde weder
        gezählt noch `unbestimmbar` — er verschwand spurlos. Gemessen: `briefe_im_lauf`
        meldete 1, `post_im_lauf` 0/0/0.

        > **Der Fehler, den diese Größe für Beiträge benennt, stand für Erstbriefe im
        > eigenen Code — und schärfer: hier verschwand auch BEKANNTES.**

        Dass er heute nichts kostet (0 von 69 Briefen tragen ein datumsloses `zeit`), ist
        ein Zufall des Bestands. Deshalb eine Vorrichtung statt einer Bestandsmessung.
        """
        import tempfile
        import textwrap
        with tempfile.TemporaryDirectory() as tmp:
            verz = os.path.join(tmp, "pm", "management", "briefkasten")
            os.makedirs(verz)
            os.makedirs(os.path.join(tmp, "pm", "tickets"))
            with open(os.path.join(tmp, "pm", "management", "sprints.jsonl"), "w",
                      encoding="utf-8") as f:
                f.write('{"nr": 1, "kennung": "k", "start": "2026-08-20 08:00"}\n')
            for name, zeit in (("N-0001.md", "2026-08-25"),       # nur Datum, DANACH
                               ("N-0002.md", "2026-08-20"),       # nur Datum, STARTTAG
                               ("N-0003.md", "2026-08-15")):      # nur Datum, DAVOR
                with open(os.path.join(verz, name), "w", encoding="utf-8") as f:
                    f.write(textwrap.dedent(f"""\
                        ---
                        von: E. John
                        zeit: {zeit}
                        status: offen
                        ---

                        Text.
                        """))
            p = kennzahlen.zaehle_post_im_lauf(tmp)
            self.assertEqual(p, {"erstbriefe": 1, "beitraege": 0, "unbestimmbar": 1},
                             "danach = gezaehlt, Starttag = unbestimmbar, davor = weg — "
                             "und KEINER faellt durch alle drei Zahlen")

    def test_ohne_laufenden_sprint_None_und_nicht_null(self):
        """`None` heisst unbekannt und nie null (Vorgabewert-Fehler aus Sprint 32).

        ⚠ Befund 16: die erste Fassung zeigte auf `p0`, wo `sprints.jsonl` ganz FEHLT —
        geprüft wurde der Zweig „Datei fehlt", nicht der benannte Fall „kein Sprint
        läuft". Beide stehen jetzt da.
        """
        import tempfile
        self.assertIsNone(kennzahlen.zaehle_post_im_lauf(os.path.join(_WURZEL, "p0")),
                          "Datei fehlt")
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "pm", "management"))
            with open(os.path.join(tmp, "pm", "management", "sprints.jsonl"), "w",
                      encoding="utf-8") as f:
                f.write('{"nr": 1, "kennung": "k", "start": "2026-08-20 08:00"}\n')
                f.write('{"kennung": "k", "ende": "2026-08-20 09:00"}\n')
            self.assertIsNone(kennzahlen.zaehle_post_im_lauf(tmp),
                              "Register da, aber der letzte Sprint ist BEENDET")

    def test_erstbeitrag_wird_nicht_doppelt_gezaehlt(self):
        """Der Erstbeitrag IST der Brief — sonst zaehlt jede Post zweimal."""
        p = kennzahlen.zaehle_post_im_lauf(_WURZEL, datetime(2026, 8, 20, 0, 0))
        briefe = kennzahlen.zaehle_briefe_im_lauf(_WURZEL, datetime(2026, 8, 20, 0, 0))
        self.assertEqual(p["erstbriefe"], briefe,
                         "die Erstbrief-Haelfte muss der alten Groesse gleichen")


class KeineZweiteZerlegung(unittest.TestCase):
    """DoD 3: die Zerlegung ist GETEILT, nicht kopiert (B033).

    ⚠⚠ **Befund 7 des Gegenlesens: die erste Fassung war eine Stichwortsuche.** Sie
    prüfte drei Zeichenketten; ein kompletter zweiter Parser liess sich danebenstellen
    und blieb **11/11 grün**, während allein das Wort `re.compile` in einem *Kommentar*
    sie rot machte.

    > **Ein Wächter, der Zeichenketten zählt, bewacht den Quelltext und nicht die Sache.**

    Er prüft jetzt den **Aufrufgraphen** (AST) und das **Verhalten**: wird die geteilte
    Zerlegung ersetzt, muss die Zahl fallen.
    """

    def test_kennzahlen_ruft_die_geteilte_zerlegung_wirklich_auf(self):
        import ast
        import inspect
        baum = ast.parse(inspect.getsource(kennzahlen.zaehle_post_im_lauf).lstrip())
        aufrufe = {ast.unparse(k.func) for k in ast.walk(baum)
                   if isinstance(k, ast.Call)}
        self.assertIn("_bk._parse", aufrufe,
                      "der Rumpf kommt aus briefkasten._parse — nicht aus einem "
                      "zweiten text.split('---')")
        for eigenbau in ("re.compile", "re.finditer", "re.match", "re.search"):
            self.assertNotIn(eigenbau, aufrufe, "kein zweiter Parser neben SWR-126")
        self.assertNotIn("open", aufrufe,
                         "die Datei wird EINMAL gelesen, von briefkasten._parse")

    def test_ohne_die_geteilte_zerlegung_faellt_die_zahl(self):
        """Die Verhaltenshälfte: wird `beitraege` stillgelegt, muss es auffallen."""
        vorher = kennzahlen.zaehle_post_im_lauf(_WURZEL, datetime(2026, 8, 20, 0, 0))
        alt = briefkasten.beitraege
        try:
            briefkasten.beitraege = lambda body: []
            nachher = kennzahlen.zaehle_post_im_lauf(_WURZEL,
                                                     datetime(2026, 8, 20, 0, 0))
        finally:
            briefkasten.beitraege = alt
        self.assertGreater(vorher["beitraege"], 0)
        self.assertEqual(nachher["beitraege"], 0,
                         "die Zaehlung haengt WIRKLICH an briefkasten.beitraege")


def _briefe():
    import board
    return board.briefkasten_dateien(_WURZEL)


def _datumslose_beitraege():
    """Wie viele Folgebeiträge tragen NUR ein Datum? Gemessen, nicht als Zahl gepflegt."""
    n = 0
    for _e, pfad in _briefe():
        for b in briefkasten.beitraege(_body(pfad)):
            if not b["ist_erstbeitrag"] and 0 < len(b["zeit"]) <= 10:
                n += 1
    return n


def _body(pfad):
    import io
    with io.open(pfad, encoding="utf-8") as f:
        text = f.read()
    teile = text.split("---")
    return "---".join(teile[2:]) if len(teile) >= 3 else text


if __name__ == "__main__":
    unittest.main()
