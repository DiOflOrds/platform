"""Tag und Annotation der Baseline sind zwei Felder (SWR-111, team-dashboard/T-0002).

Der Befund kam vom echten Payload: `letzte_baseline` trug bei `p1` 300 Zeichen —
Tag UND Abnahmebericht unter einem Namen (B033). Die drei Zustaende aus SWR-108
muessen fuer BEIDE Felder gelten und duerfen nie auseinanderlaufen.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from backend import aggregation  # noqa: E402


def trenne(tagzeile, profil="entwicklung"):
    """Die Trennregel aus aggregation.cockpit, isoliert nachgestellt.

    Bewusst dieselbe Formulierung wie in der Quelle: der Test haelt die REGEL fest;
    die Verdrahtung im Payload prueft PayloadTest unten am echten Bestand."""
    tags = [z for z in (tagzeile or "").splitlines() if z.strip()]
    if tags:
        teile = tags[-1].strip().split(None, 1)
        return teile[0], (teile[1].strip() if len(teile) > 1 else "")
    if profil in aggregation.PROFILE_OHNE_G4:
        return None, None
    return "", ""


class TrennregelTest(unittest.TestCase):

    def test_tag_mit_langer_annotation(self):
        zeile = ("p1-v1.0         Abschluss-Baseline P1: Mission Control 2.0 (G4/D009). "
                 "Sprints 0-3, STK-013 + SWR-025-033, 3 Inbox-Entscheidungen.")
        tag, text = trenne(zeile)
        self.assertEqual(tag, "p1-v1.0")
        self.assertTrue(text.startswith("Abschluss-Baseline P1:"))
        self.assertLess(len(tag), 40, "der Tag muss in eine Kachelzeile passen")
        self.assertGreater(len(text), 40, "der Text ist der lange Teil")

    def test_tag_ohne_annotation_gibt_leeren_text_und_nicht_null(self):
        """⚠ Gegenprobe zu `null`. Die Annotation WURDE erhoben und ist leer —
        das ist eine echte Null im Sinne von SWR-108, keine fehlende Messung."""
        tag, text = trenne("p8-v1.0")
        self.assertEqual(tag, "p8-v1.0")
        self.assertEqual(text, "")
        self.assertIsNotNone(text)

    def test_kein_tag_ohne_g4_gibt_beide_null(self):
        for profil in aggregation.PROFILE_OHNE_G4:
            tag, text = trenne("", profil=profil)
            self.assertIsNone(tag)
            self.assertIsNone(text)

    def test_kein_tag_mit_g4_gibt_beide_leer(self):
        tag, text = trenne("", profil="entwicklung")
        self.assertEqual((tag, text), ("", ""))

    def test_annotation_wird_nur_einmal_getrennt(self):
        """Mehrere Leerzeichen in der Annotation duerfen sie nicht zerlegen."""
        tag, text = trenne("p2-v1.0   erst  zweit  dritt")
        self.assertEqual(tag, "p2-v1.0")
        self.assertEqual(text, "erst  zweit  dritt")

    def test_juengster_tag_gewinnt(self):
        """`_tags` sortiert nach creatordate; gelesen wird weiter die letzte Zeile."""
        tag, _ = trenne("p1-v0.9  alt\np1-v1.0  neu")
        self.assertEqual(tag, "p1-v1.0")


class PayloadTest(unittest.TestCase):
    """Am ECHTEN Bestand gemessen (DoD 2 des Tickets), nicht an einer Testwelt."""

    @classmethod
    def setUpClass(cls):
        wurzel = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
        roh = aggregation.cockpit_alle(wurzel)
        eintraege = roh if isinstance(roh, list) else roh.get("projekte", roh)
        cls.eintraege = {e["projekt"]: e for e in eintraege
                         if isinstance(e, dict) and "letzte_baseline" in e}

    def test_beide_felder_sind_im_payload(self):
        self.assertTrue(self.eintraege, "kein Eintrag mit Baseline gefunden")
        for name, e in self.eintraege.items():
            self.assertIn("letzte_baseline_text", e, f"{name} ohne das neue Feld")

    def test_zustaende_laufen_nie_auseinander(self):
        """Die Kernzusage: `null`/`""`/Wert gelten fuer BEIDE Felder gleich."""
        for name, e in self.eintraege.items():
            tag, text = e["letzte_baseline"], e["letzte_baseline_text"]
            if tag is None:
                self.assertIsNone(text, f"{name}: Tag null, Text nicht")
            elif tag == "":
                self.assertEqual(text, "", f"{name}: Tag leer, Text nicht")
            else:
                self.assertIsInstance(text, str, f"{name}: Tag gesetzt, Text kein String")

    def test_kein_tag_ist_laenger_als_die_vertragszusage(self):
        """`max_zeichen: 40` im Widget-Vertrag ist eine Zusage der Quelle."""
        for name, e in self.eintraege.items():
            tag = e["letzte_baseline"]
            if tag:
                self.assertLessEqual(len(tag), 40, f"{name}: Tag {len(tag)} Zeichen")

    def test_p1_war_der_anlass_und_ist_jetzt_geteilt(self):
        e = self.eintraege.get("p1")
        if e is None:
            self.skipTest("p1 nicht im Bestand")
        self.assertEqual(e["letzte_baseline"], "p1-v1.0")
        self.assertGreater(len(e["letzte_baseline_text"]), 200,
                           "der lange Teil muss erhalten bleiben, nur woanders")

    def test_kein_tag_enthaelt_noch_leerraum(self):
        """Die Trennung ist vollzogen — ein Tagfeld mit Leerzeichen waere ein Rueckfall."""
        for name, e in self.eintraege.items():
            tag = e["letzte_baseline"]
            if tag:
                self.assertNotIn(" ", tag, f"{name}: Tagfeld traegt noch Annotation")


if __name__ == "__main__":
    unittest.main()
