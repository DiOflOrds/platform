"""Eine Lehre ohne Vertreter (SWR-194, platform/T-0034 · SWR-199, platform/T-0050).

⚠⚠ **Diese Datei ist eine Sperrklinke und kein Anklagezettel.** Am gemessenen Bestand
(2026-08-21, Sprint 31) haben **91 von 112** Lehren keine Zusicherung, die sie zitiert.
Sie alle rot zu machen wäre **91 Dauerbefunde** — und ein Dauerbefund trainiert genau das
Wegsehen, gegen das `SWR-166` gebaut wurde (83 abgebrochene Läufe, 12 nie gelaufene Ticks).

> **Der Bestand ist BENANNT und nicht rot. Rot wird diese Prüfung, wenn eine NEUE Lehre
> ohne Vertreter dazukommt — und dann sagt sie dessen Namen.**

⚠⚠ **SWR-199 hat die Grundmenge gewechselt, und der Anlass war diese Datei selbst.** Bis
Sprint 30 zählte nur, wer `**Regel:**` schrieb; drei Lehren aus Sprint 30 standen als
`**Regel.**` da und waren unsichtbar — **die Prüfung blieb dabei grün**. Eine
Sperrklinke, die man mit einem anders gesetzten Doppelpunkt umgeht, ist keine. Der
Ausstieg heißt jetzt `**Beobachtung:**` und ist eine Handlung statt eines Nebeneffekts
der Zeichensetzung.

⚠ Das ist die Bauform von `SWR-190`: eine Prüfung, die die Regel von allein wiederholt,
statt eines Satzes im Runbook, der auf Sorgfalt hofft. Das Ticket sagt ausdrücklich, was
**nicht** die Lösung ist: *„eine weitere Zeile im Runbook … das ist genau die Bauform, die
hier gerade vierzehn Tage lang versagt hat."*

Ausführung: python -m unittest discover platform/tests
"""
import os
import re
import sys
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
from backend import lehren  # noqa: E402

#: ⚠⚠ **Der Bestand am 2026-08-21 (Sprint 29), gemessen von `lehren.ohne_vertreter`
#: selbst und nicht von einem zweiten Skript** — sonst wären es zwei Zählungen für
#: dieselbe Auskunft (B033), und die Sperrklinke stünde auf einer Zahl, die die Prüfung
#: nie gesehen hat.
#:
#: ⚠ Als **Menge** und nicht als Zahl (`L-2026-08-20by`): eine Prüfung, die nur die
#: Anzahl misst, kann einen **Tausch** nicht von **Stillstand** unterscheiden. Neben
#: jedes „es sind 29" gehört „und es sind DIESE 29".
#:
#: Wächst die Menge → eine neue Lehre hat keinen Vertreter bekommen: **Befund.**
#: Schrumpft sie → eine Lehre hat einen bekommen: **das gehört gebucht** und nicht
#: nebenbei getan (dieselbe Regel wie bei `ROHTEXT_ANSICHTEN`).
#: ⚠⚠ **SWR-199 (platform/T-0050, Sprint 31): die Basis ist von 29 auf 91 gewachsen —
#: ohne dass eine einzige Lehre ihren Vertreter verloren hätte.**
#:
#: Der Zuwachs ist die **Grundmenge**, nicht der Bestand: bis Sprint 30 sah die Prüfung
#: nur Lehren mit `**Regel:**` (38 von 112) und war für die übrigen **62 blind**. Das
#: Muster zu erweitern hätte dieselben 91 ergeben wie es wegzulassen — deshalb ist es
#: weggelassen. Die Begründung steht bei `lehren.BEOBACHTUNG_ZEILE`; hier ihr Ergebnis.
OHNE_VERTRETER_BASIS = frozenset({
    "L-2026-08-16b", "L-2026-08-16c", "L-2026-08-16d", "L-2026-08-16e",
    "L-2026-08-16f", "L-2026-08-16g", "L-2026-08-16i", "L-2026-08-16j",
    "L-2026-08-16k", "L-2026-08-16l", "L-2026-08-17aa", "L-2026-08-17ab",
    "L-2026-08-17ac", "L-2026-08-17ad", "L-2026-08-17ae", "L-2026-08-17af",
    "L-2026-08-17ah", "L-2026-08-17aj", "L-2026-08-17al", "L-2026-08-17am",
    "L-2026-08-17ao", "L-2026-08-17ap", "L-2026-08-17aq", "L-2026-08-17ar",
    "L-2026-08-17as", "L-2026-08-17at", "L-2026-08-17au", "L-2026-08-17av",
    "L-2026-08-17aw", "L-2026-08-17ax", "L-2026-08-17ay", "L-2026-08-17b",
    "L-2026-08-17ba", "L-2026-08-17bb", "L-2026-08-17bc", "L-2026-08-17bd",
    "L-2026-08-17be", "L-2026-08-17bf", "L-2026-08-17bg", "L-2026-08-17c",
    "L-2026-08-17d", "L-2026-08-17e", "L-2026-08-17f", "L-2026-08-17i",
    "L-2026-08-17l", "L-2026-08-17m", "L-2026-08-17n", "L-2026-08-17p",
    "L-2026-08-17q", "L-2026-08-17r", "L-2026-08-17s", "L-2026-08-17t",
    "L-2026-08-17u", "L-2026-08-17v", "L-2026-08-17w", "L-2026-08-17x",
    "L-2026-08-17y", "L-2026-08-17z", "L-2026-08-20bh", "L-2026-08-20bi",
    "L-2026-08-20bj", "L-2026-08-20bk", "L-2026-08-20bl", "L-2026-08-20bm",
    "L-2026-08-20bn", "L-2026-08-20bo", "L-2026-08-20bp", "L-2026-08-20bq",
    "L-2026-08-20br", "L-2026-08-20bs", "L-2026-08-20bt", "L-2026-08-20bu",
    "L-2026-08-20bv", "L-2026-08-20bw", "L-2026-08-20bx", "L-2026-08-20bz",
    "L-2026-08-20ca", "L-2026-08-20cb", "L-2026-08-20cc", "L-2026-08-20cd",
    "L-2026-08-20ce", "L-2026-08-20cg", "L-2026-08-20ch", "L-2026-08-20ci",
    "L-2026-08-20cj", "L-2026-08-20ck", "L-2026-08-20cl", "L-2026-08-20cn",
    "L-2026-08-20co", "L-2026-08-20cp", "L-2026-08-20cq",
})


class GrundmengeTest(unittest.TestCase):
    """Verifiziert: SWR-194 — die Grundmenge ist nicht leer (SWR-128-Familie)."""

    def test_es_gibt_ueberhaupt_lehren(self):
        """⚠ Ohne diese Zusicherung wäre eine kaputte Entdeckung **grün**."""
        self.assertGreaterEqual(len(lehren.lehren()), 1,
                                "keine Lehre gefunden — die Prüfung darunter misst nichts")

    def test_die_grundmenge_ist_nicht_leer(self):
        """⚠ SWR-199: Grundmenge ist `grundmenge()`, nicht mehr `mit_regel()`.

        Die alte Zusicherung an dieser Stelle lautete `len(mit_regel) < len(alle)` und
        sollte sichern, dass die Konvention überhaupt etwas **trennt**. Gemessen wäre
        sie bei **111 von 112** erfüllt gewesen — eine echte Ungleichung, die eine
        Verhältnisaussage meinte.

        > **Eine Zusicherung, die ein Verhältnis meint und eine Ungleichung schreibt,
        > bleibt grün, während ihr Gegenstand verschwindet.** Derselbe Fehler, den
        > `platform/T-0050` an seinem eigenen Gegenstand gefunden hat.
        """
        self.assertGreaterEqual(len(lehren.grundmenge()), 1,
                                "leere Grundmenge — die Prüfung darunter misst nichts")

    def test_die_regel_konvention_trennt_praktisch_nichts(self):
        """⚠⚠ Die Messung, die den Umbau entschieden hat — als Zusicherung, nicht als Zahl.

        `SWR-194` nannte die Regel-Zeile *„die Konvention, mit der dieses Haus selbst
        schon unterscheidet"*. Gemessen tragen **111 von 112** Lehren eine Regel in
        irgendeiner Schreibweise — als Auswahlkriterium ist das keine Auswahl.

        ⚠ Diese Zusicherung ist bewusst an das **Verhältnis** gebunden und nicht an eine
        Ungleichung: die Vorgängerin an dieser Stelle prüfte `len(mit_regel) < len(alle)`
        und wäre bei 111 von 112 grün geblieben. Genau das ist der Gegenstand von
        `platform/T-0050`.
        """
        alle = lehren.lehren()
        irgendeine_regel = [k for k, t in alle.items()
                            if re.search(r"(?m)^\*\*Regeln?\b", t)]
        anteil = len(irgendeine_regel) / max(len(alle), 1)
        self.assertGreater(anteil, 0.9, (
            "Die Regel-Konvention trennt heute wieder etwas (%d von %d) — dann war die "
            "Begründung von SWR-199 an einen Bestand gebunden, der sich bewegt hat: "
            "bitte neu messen, statt diese Zusicherung anzupassen."
            % (len(irgendeine_regel), len(alle))))

    def test_erweitern_und_weglassen_sind_dasselbe_ergebnis(self):
        """⚠⚠ Der Grund, warum der Filter FÄLLT statt erweitert zu werden.

        Zwischen „irgendeine Regel-Schreibweise" und „gar kein Filter" liegt am
        gemessenen Bestand **null** Lehren. Von zwei gleichwertigen Bauformen ist die
        mit einem Begriff weniger die richtige — und diese Zusicherung wird rot, sobald
        die Gleichwertigkeit endet, statt dass es jemand fünf Sprints später nachmisst.
        """
        korpus = lehren._vertreter_korpus(lehren._wurzel())
        alle = lehren.lehren()

        def ohne(namen):
            return {k for k in namen if not any(k in t for t in korpus)}

        mit_irgendeiner = [k for k, t in alle.items()
                           if re.search(r"(?m)^\*\*Regeln?\b", t)]
        self.assertEqual(ohne(lehren.grundmenge()), ohne(mit_irgendeiner),
                         "Erweitern und Weglassen liefern nicht mehr dasselbe — die "
                         "Wahl von SWR-199 braucht dann eine neue Begründung")

    def test_beobachtung_ist_ein_ausgang_und_kein_schlupfloch(self):
        """SWR-199: der Ausstieg ist eine HANDLUNG, kein Nebeneffekt der Zeichensetzung.

        ⚠ Die Gegenprobe steht daneben: ohne den Marker wäre der Text in der Grundmenge.
        Eine Prüfung, die nur die Wirkung des Markers misst, kann nicht unterscheiden,
        ob er wirkt oder ob die Lehre ohnehin fehlte.
        """
        self.assertTrue(lehren.BEOBACHTUNG_ZEILE.search("**Beobachtung:** nur gesehen."))
        self.assertTrue(lehren.BEOBACHTUNG_ZEILE.search("**Beobachtung** nur gesehen."))
        self.assertIsNone(lehren.BEOBACHTUNG_ZEILE.search("Eine **Beobachtung:** mittig"))

    def test_kein_bestand_wird_still_als_beobachtung_geparkt(self):
        """⚠⚠ Der Marker darf nicht zum bequemen Weg werden, einen Befund loszuwerden.

        Am 2026-08-21 trägt **0** Lehre den Marker. Wächst die Zahl, ist das eine
        Entscheidung und gehört gebucht — genau wie ein gewonnener Vertreter.
        """
        self.assertEqual(lehren.beobachtungen(), [], (
            "Diese Lehre(n) sind als reine Beobachtung geführt: " +
            ", ".join(lehren.beobachtungen()) + ". Das ist zulässig und soll sichtbar "
            "sein — bitte diese Zusicherung mit der Begründung nachziehen, damit der "
            "Ausstieg eine gebuchte Entscheidung bleibt und keine stille Gewohnheit."))


class SperrklinkeTest(unittest.TestCase):
    """Verifiziert: SWR-194 — der Bestand ist benannt, ein Zuwachs ist ein Befund."""

    def test_keine_NEUE_lehre_ohne_vertreter(self):
        """⚠⚠ Die eigentliche Prüfung. Sie nennt den Namen, nicht nur die Zahl."""
        ist = set(lehren.ohne_vertreter())
        neu = sorted(ist - OHNE_VERTRETER_BASIS)
        self.assertEqual(neu, [], (
            "Diese Lehre(n) tragen eine ausformulierte **Regel:** und werden von KEINER "
            "Zusicherung zitiert: " + ", ".join(neu) + ". Genau diese Lage hat `L-003` "
            "vierzehn Tage lang null Wirkung gekostet. Entweder eine Zusicherung bauen, "
            "die die Lehr-ID nennt — oder die Lehre bewusst als Beobachtung ohne Regel "
            "führen. Beides ist eine Entscheidung; sie hier auszusitzen ist keine."))

    def test_ein_gewonnener_vertreter_wird_gebucht_und_nicht_nebenbei_getan(self):
        """⚠ Schrumpft die Menge, ist das ein FORTSCHRITT — und er gehört in die Basis.

        Rot in diese Richtung ist Absicht: sonst verschwände der Ertrag lautlos, und
        niemand könnte später sagen, ob die Zahl gefallen ist oder die Prüfung kaputt.
        """
        ist = set(lehren.ohne_vertreter())
        weg = sorted(OHNE_VERTRETER_BASIS - ist)
        self.assertEqual(weg, [], (
            "Diese Lehre(n) haben einen Vertreter bekommen: " + ", ".join(weg) +
            " — bitte OHNE_VERTRETER_BASIS nachziehen, damit der Fortschritt gebucht "
            "ist und nicht nur passiert."))


class KeineTautologieTest(unittest.TestCase):
    """Verifiziert: SWR-194 — die Prüfung darf ihre eigene Frage nicht beantworten."""

    def test_die_pruefung_selbst_zaehlt_nicht_als_vertreter(self):
        """⚠⚠ An einem echten Fehlschlag gelernt, nicht vorsorglich gebaut.

        Der erste Entwurf von `lehren.py` nannte eine **existierende** Lehr-ID in einem
        erklärenden Kommentar — und hat ihr damit einen Vertreter verschafft. Die Zählung
        fiel von 29 auf 28, ohne dass sich an der Sache etwas geändert hatte.
        """
        self.assertIn("lehren.py", lehren.NICHT_VERTRETER)
        self.assertIn(os.path.basename(__file__), lehren.NICHT_VERTRETER)

    def test_gegenprobe_eine_id_in_der_pruefung_verschafft_keinen_vertreter(self):
        """Die Zusicherung zur Zusicherung: der Ausschluss WIRKT.

        `OHNE_VERTRETER_BASIS` in dieser Datei nennt 29 Lehr-IDs im Klartext. Zählte
        diese Datei als Korpus, wären alle 29 „vertreten" und die Menge leer — die
        Prüfung wäre für immer grün und vollkommen wertlos.
        """
        self.assertTrue(lehren.ohne_vertreter(),
                        "die Menge ist leer — sehr wahrscheinlich liest die Prüfung ihre "
                        "eigene Basisliste als Korpus und ist damit tautologisch grün")

    def test_der_parkplatz_zaehlt_nicht(self):
        """⚠ 11000+ Kopien alter Stände; ein Treffer dort wäre ein Vertreter von gestern."""
        with open(os.path.join(_HIER, "..", "backend", "lehren.py"),
                  encoding="utf-8") as f:
            quelle = f.read()
        for aus in ("verwaiste-locks", "node_modules", ".git"):
            self.assertIn(aus, quelle, f"{aus} wird nicht ausgeschlossen")

    def test_tickets_zaehlen_nicht_als_vertreter(self):
        """⚠⚠ Ein Ticket ist ein Vorsatz mit Datum; eine Zusicherung ist der Vollzug.

        Ein Ticket als Vertreter zu zählen hieße, den Befund mit dem zu beantworten, was
        ihn erzeugt hat — `L-003` hatte drei Ablagen und kein einziges Ticket, das sie
        vollzogen hätte.
        """
        self.assertNotIn(".md", lehren.VERTRETER_ENDUNGEN)


if __name__ == "__main__":
    unittest.main()
