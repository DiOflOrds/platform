"""Das 2×2-Raster des Post-Widgets (SWR-210, team-dashboard/T-0005, Brief N-0004).

Der Auftraggeber hat eine **Design-Vorlage** geliefert
(`projects/p11/design/widget_design_mail.png`) und dazu drei Rückfragen beantwortet:

> *„1. 180 Zeichen ok. 2. Aufklappen 3. die eine Reaktion verlangen"*

⚠⚠ **Der Ertrag des Baus ist eine Kachel, die es nicht geben kann.** Die Vorlage verlangt
vier Zahlen — `IN`, `Reaktion`, `Rechnung`, `SPAM`. Am Bestand gemessen liefert
`team-mail` drei: der Digest führt die Rubriken *„Braucht Blick oder Reaktion"* und
*„Rechnungen/Zahlungen"*, aber **keine SPAM-Rubrik**.

> **Die Vorlage fragt nach einer Zahl, die die Quelle nicht herstellt. `0` anzuzeigen
> hieße „kein Spam" behaupten — und niemand sieht einer `0` an, dass sie erfunden ist.**

⚠ Der zweite Ertrag ist ein Widerspruch, der keiner war: die Vorlage zeigt die
Zusammenfassung **in** der Kachel, ihr **Wortlaut** ist aber genau das, was `SWR-160`
hinter das PIN-Lesegate gestellt hat (Betreffzeilen, Absender, Mail-Links). Der
Auftraggeber hat *„wenn man auf reaktion klickt"* geschrieben — **ein Klick ist genau die
Stelle, an der ein Lesegate hingehört.** Die Kachel zeigt die **Zahl**, das Aufklappen den
**Wortlaut**.

Vertreter von `L-2026-08-21de`.
"""
import os
import sys
import unittest

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAUS = os.path.dirname(WURZEL)
sys.path.insert(0, os.path.join(WURZEL, "scripts"))
sys.path.insert(0, WURZEL)
from backend import widgets  # noqa: E402

DIGEST = """# Digest 2026-08-20 (Tag) — 42 Mail(s)

## Auf einen Blick

Text.

## Braucht Blick oder Reaktion

1. **Erster Punkt:** etwas zu tun. [Mail oeffnen](https://example.invalid/a)
2. **Zweiter Punkt:** noch etwas. [Mail oeffnen](https://example.invalid/b)
3. **Dritter Punkt:** und noch etwas.

## Rechnungen/Zahlungen

Keine direkten Rechnungen.

## Rest kompakt

- egal
"""


class DasRasterHatVierKacheln(unittest.TestCase):

    def test_reihenfolge_und_schluessel_wie_in_der_vorlage(self):
        """`IN` / `Reaktion` oben, `Rechnung` / `SPAM` unten — in dieser Reihenfolge."""
        raster = widgets._kacheln(DIGEST, 42)
        self.assertEqual(["in", "reaktion", "rechnung", "spam"],
                         [k["schluessel"] for k in raster])

    def test_die_drei_vorhandenen_zahlen_stimmen(self):
        raster = {k["schluessel"]: k for k in widgets._kacheln(DIGEST, 42)}
        self.assertEqual(42, raster["in"]["wert"])
        self.assertEqual(3, raster["reaktion"]["wert"])
        self.assertEqual(0, raster["rechnung"]["wert"])

    def test_eine_rubrik_ohne_punkte_ist_echte_null_und_nicht_leer(self):
        """*„Keine direkten Rechnungen"* ist ein **Ergebnis** (SWR-108)."""
        raster = {k["schluessel"]: k for k in widgets._kacheln(DIGEST, 42)}
        self.assertEqual(widgets.ZUSTAND_ECHTE_NULL, raster["rechnung"]["zustand"])
        self.assertEqual("", raster["rechnung"]["grund"])

    def test_spam_ist_nicht_geliefert_MIT_grund_und_niemals_null(self):
        """⚠⚠ Die Kachel, die es nicht geben kann — und die trotzdem dasteht."""
        raster = {k["schluessel"]: k for k in widgets._kacheln(DIGEST, 42)}
        self.assertIsNone(raster["spam"]["wert"])
        self.assertEqual(widgets.ZUSTAND_NICHT_GELIEFERT, raster["spam"]["zustand"])
        self.assertIn("keine Quelle", raster["spam"]["grund"])
        self.assertIn("team-mail/T-0007", raster["spam"]["grund"],
                      "der Grund nennt den Weg nach vorn — ein Dauerbefund ohne Ticket "
                      "ist die Bauform, die SWR-166 83 abgebrochene Läufe gekostet hat")

    def test_ohne_mailzahl_ist_IN_unbekannt_und_nicht_null(self):
        """Die Gegenprobe zu `in`: B038 — eine fehlende Angabe ist keine `0`."""
        raster = {k["schluessel"]: k for k in widgets._kacheln(DIGEST, None)}
        self.assertIsNone(raster["in"]["wert"])
        self.assertEqual(widgets.ZUSTAND_NICHT_GELIEFERT, raster["in"]["zustand"])
        self.assertTrue(raster["in"]["grund"])


class EineAuswahlregelFuerAlleRubriken(unittest.TestCase):
    """⚠⚠ Vor SWR-210 stand derselbe Rumpf zweimal da — mit vier Kacheln wären es vier."""

    def test_zaehlen_und_zitieren_kommen_aus_derselben_stelle(self):
        self.assertEqual(widgets.reaktionspunkte(DIGEST),
                         len(widgets.reaktionspunkte_text(DIGEST)))

    def test_die_doppelten_ruempfe_sind_weg(self):
        """Rückbau-Wächter (`SWR-148`-Paarform): der Quelltext trägt die Auswahl EINMAL."""
        with open(os.path.join(WURZEL, "backend", "widgets.py"), encoding="utf-8") as f:
            quelle = f.read()
        self.assertEqual(1, quelle.count("if _ZAHLPUNKT.match(z):"),
                         "die Auswahlregel steht wieder mehrfach im Modul — genau die "
                         "Doppelung, die der Docstring von reaktionspunkte_text seit "
                         "SWR-160 als Risiko benennt")
        self.assertIn("def _rubrikpunkte", quelle)


class DieZusammenfassungBleibtHinterDemGate(unittest.TestCase):

    def test_der_payload_sagt_nur_DASS_es_eine_gibt(self):
        """⚠ Kein Wortlaut im ungeschützten Widget — `SWR-160` gilt unverändert."""
        eintrag = {"kacheln": widgets._kacheln(DIGEST, 42)}
        for kachel in eintrag["kacheln"]:
            self.assertNotIn("Erster Punkt", str(kachel),
                             "Betreffzeilen im ungeschützten Payload (SWR-160)")

    def test_grenze_ist_180_zeichen_und_zwei_zeilen(self):
        """Die Zahl ist eine **Entscheidung des Auftraggebers**, keine Gewohnheit."""
        self.assertEqual(180, widgets.ZUSAMMENFASSUNG_ZEICHEN)
        self.assertEqual(2, widgets.ZUSAMMENFASSUNG_ZEILEN)

    def test_zusammenfassung_kuerzt_und_nimmt_nur_zwei_punkte(self):
        text = widgets.zusammenfassung(widgets.reaktionspunkte_text(DIGEST))
        self.assertLessEqual(len(text), widgets.ZUSAMMENFASSUNG_ZEICHEN)
        self.assertIn("Erster Punkt", text)
        self.assertIn("Zweiter Punkt", text)
        self.assertNotIn("Dritter Punkt", text,
                         "mehr als zwei Zeilen — die Vorlage sagt „max. zwei Zeilen")

    def test_mail_links_werden_entfernt_und_der_text_bleibt(self):
        """⚠ Ein Link ist im Digest die Adresse EINER Mail — er gehört nicht in eine Kurzfassung."""
        text = widgets.zusammenfassung(widgets.reaktionspunkte_text(DIGEST))
        self.assertNotIn("example.invalid", text)
        self.assertIn("Mail oeffnen", text)

    def test_ohne_rubrik_gibt_es_KEINE_zusammenfassung(self):
        """`None`, nie `""` — ein leerer String behauptet, es sei nichts zu berichten."""
        self.assertIsNone(widgets.zusammenfassung(None))

    def test_zu_langer_text_endet_mit_auslassung(self):
        lang = ["1. " + "x" * 400]
        text = widgets.zusammenfassung(lang)
        self.assertEqual(widgets.ZUSAMMENFASSUNG_ZEICHEN, len(text))
        self.assertTrue(text.endswith("…"))


class AmEchtenBestand(unittest.TestCase):
    """⚠ `SWR-189`-Bauform: eine Zusicherung, die den wirklichen Digest liest."""

    def test_jeder_eintrag_traegt_dieselben_schluessel(self):
        if not os.path.isdir(os.path.join(HAUS, "team-mail")):
            self.skipTest("team-mail nicht vorhanden")
        w = widgets.post_widget(HAUS, "team-mail")
        self.assertIsNotNone(w)
        self.assertTrue(w["eintraege"], "Grundmenge leer — die Zusicherung sagt nichts")
        formen = {tuple(sorted(e)) for e in w["eintraege"]}
        self.assertEqual(1, len(formen),
                         "Einträge mit verschiedenen Schlüsseln: ein fehlender Schlüssel "
                         "zwingt den Leser zu einem Vorgabewert, und ein Vorgabewert ist "
                         "die erfundene Auskunft, gegen die der Vertrag nicht_geliefert führt")
        for e in w["eintraege"]:
            self.assertEqual(4, len(e["kacheln"]))
            self.assertIn(e["zusammenfassung_verfuegbar"], (True, False))


if __name__ == "__main__":
    unittest.main()
