"""Eine Lehre ohne Vertreter (SWR-194, platform/T-0034).

⚠⚠ **Diese Datei ist eine Sperrklinke und kein Anklagezettel.** Am gemessenen Bestand
haben **29 von 34** Lehren mit ausformulierter Regel keine Zusicherung, die sie zitiert.
Sie alle rot zu machen wäre **29 Dauerbefunde** — und ein Dauerbefund trainiert genau das
Wegsehen, gegen das `SWR-166` gebaut wurde (83 abgebrochene Läufe, 12 nie gelaufene Ticks).

> **Der Bestand ist BENANNT und nicht rot. Rot wird diese Prüfung, wenn eine NEUE Lehre
> mit Regel ohne Vertreter dazukommt — und dann sagt sie dessen Namen.**

⚠ Das ist die Bauform von `SWR-190`: eine Prüfung, die die Regel von allein wiederholt,
statt eines Satzes im Runbook, der auf Sorgfalt hofft. Das Ticket sagt ausdrücklich, was
**nicht** die Lösung ist: *„eine weitere Zeile im Runbook … das ist genau die Bauform, die
hier gerade vierzehn Tage lang versagt hat."*

Ausführung: python -m unittest discover platform/tests
"""
import os
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
OHNE_VERTRETER_BASIS = frozenset({
    "L-2026-08-16c", "L-2026-08-16d", "L-2026-08-16e", "L-2026-08-16f",
    "L-2026-08-16g", "L-2026-08-17aj", "L-2026-08-17al", "L-2026-08-17am",
    "L-2026-08-17ap", "L-2026-08-17aq", "L-2026-08-17ar", "L-2026-08-17as",
    "L-2026-08-17at", "L-2026-08-17au", "L-2026-08-17av", "L-2026-08-17aw",
    "L-2026-08-17ax", "L-2026-08-17ay", "L-2026-08-17ba", "L-2026-08-17bb",
    "L-2026-08-17bc", "L-2026-08-17be", "L-2026-08-17bf", "L-2026-08-17bg",
    "L-2026-08-20bh", "L-2026-08-20bi", "L-2026-08-20bj", "L-2026-08-20bk",
    "L-2026-08-20bl",
})


class GrundmengeTest(unittest.TestCase):
    """Verifiziert: SWR-194 — die Grundmenge ist nicht leer (SWR-128-Familie)."""

    def test_es_gibt_ueberhaupt_lehren(self):
        """⚠ Ohne diese Zusicherung wäre eine kaputte Entdeckung **grün**."""
        self.assertGreaterEqual(len(lehren.lehren()), 1,
                                "keine Lehre gefunden — die Prüfung darunter misst nichts")

    def test_die_untermenge_mit_regel_ist_nicht_leer_und_echt_kleiner(self):
        """⚠ Beide Hälften: nicht leer (sonst prüft nichts) UND kleiner als alles.

        Wäre sie so groß wie der Bestand, wäre die 'ehrliche Untermenge' aus Vorabfrage 3
        gar keine Auswahl — und die Prüfung forderte für jede Beobachtung einen Vertreter.
        """
        alle, regel = lehren.lehren(), lehren.mit_regel()
        self.assertGreaterEqual(len(regel), 1)
        self.assertLess(len(regel), len(alle),
                        "jede Lehre trägt eine Regel — dann trennt die Konvention nichts")


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
