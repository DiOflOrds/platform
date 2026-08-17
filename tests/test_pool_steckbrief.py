"""Steckbrief eines Gruendungsantrags (SWR-127, pm/T-0062 aus pm/T-0028).

pm/T-0028 (Brief pm/N-0022) war viermal um genau einen Sprint verschoben worden —
7 -> 8 -> 9 -> 10 -> 11, gemessen an der Git-Historie des Ticketfelds. Genau derselbe
Zaehlerstand, an dem Sprint 10 bei pm/T-0039 die Regel abgeleitet hat: "zu gross ->
zerlegen, nicht schieben". Sprint 11 wendet sie hier an.

Die Feldliste ist NICHT hier entschieden — sie steht seit Sprint 10 als Tabelle mit
Begruendung je Feld in pm/T-0028. Diese Datei prueft, dass sie GILT. Eine Feldliste,
die kein Code prueft, ist eine Absichtserklaerung (die Lehre von SWR-125).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from backend import pool  # noqa: E402

GUT = {"auftrag": "Prompts der KI-Rollen pflegen",
       "profil": "wiederkehrend",
       "rollen": "dev, test",
       "datenklasse": "intern",
       "zugaenge": "keine externen",
       "grenzen": "kein Mailversand, keine Prompt-Aenderung ohne Eval-Gate"}


class SteckbriefTest(unittest.TestCase):

    def test_vollstaendiger_antrag_wird_angenommen(self):
        werte, auflagen = pool.steckbrief_pruefen(GUT)
        self.assertEqual(werte["profil"], "wiederkehrend")
        self.assertEqual(werte["grenzen"], GUT["grenzen"])
        self.assertEqual(auflagen, [])

    def test_auftrag_ist_pflicht(self):
        """Ohne Auftrag ist der Charter leer."""
        with self.assertRaises(pool.PoolFehler) as f:
            pool.steckbrief_pruefen({**GUT, "auftrag": "   "})
        self.assertEqual(f.exception.code, 400)
        self.assertIn("auftrag", str(f.exception))

    def test_grenzen_sind_pflicht(self):
        """⚠ Das einzige Feld, in dem Schweigen die WEITERE Auslegung hat: ein leeres
        Feld 'Grenzen' wird als 'keine Grenzen' gelesen. Deshalb Pflicht."""
        with self.assertRaises(pool.PoolFehler) as f:
            pool.steckbrief_pruefen({**GUT, "grenzen": ""})
        self.assertIn("grenzen", str(f.exception))

    def test_freitextfelder_sind_freiwillig(self):
        """Rollen und Zugaenge duerfen leer sein — eine erfundene geschlossene Liste
        waere gefaehrlicher als keine (Begruendung aus der Tabelle in pm/T-0028)."""
        werte, _ = pool.steckbrief_pruefen({**GUT, "rollen": "", "zugaenge": ""})
        self.assertEqual(werte["rollen"], "")

    def test_profil_ausserhalb_der_liste_wird_abgelehnt(self):
        """Freitext erzeugte Profile, die kein Prozess kennt."""
        with self.assertRaises(pool.PoolFehler) as f:
            pool.steckbrief_pruefen({**GUT, "profil": "agil"})
        self.assertIn("entwicklung", str(f.exception))   # B038: nennt die Alternativen

    def test_datenklasse_ausserhalb_der_liste_wird_abgelehnt(self):
        with self.assertRaises(pool.PoolFehler):
            pool.steckbrief_pruefen({**GUT, "datenklasse": "vertraulich"})

    def test_alle_vier_datenklassen_sind_zulaessig(self):
        for k in ("offen", "intern", "sensibel", "geheim"):
            werte, _ = pool.steckbrief_pruefen({**GUT, "datenklasse": k})
            self.assertEqual(werte["datenklasse"], k)

    def test_sensibel_erzeugt_eine_auflage_im_klartext(self):
        """⚠ Der Kern der Klasse-A-Vorsicht: bei `sensibel` bleibt das Repo ohne Remote.
        Das darf nicht als Feldwert mitlaufen, es muss im DR STEHEN (Kap. 16 / F17)."""
        _werte, auflagen = pool.steckbrief_pruefen({**GUT, "datenklasse": "sensibel"})
        self.assertEqual(len(auflagen), 1)
        self.assertIn(".kein-remote", auflagen[0])
        self.assertIn("OHNE GitHub-Remote", auflagen[0])

    def test_geheim_erzeugt_dieselbe_auflage(self):
        _werte, auflagen = pool.steckbrief_pruefen({**GUT, "datenklasse": "geheim"})
        self.assertEqual(len(auflagen), 1)
        self.assertIn("geheim", auflagen[0])

    def test_intern_und_offen_erzeugen_keine_auflage(self):
        """Die Gegenprobe — sonst waere die Auflage eine Dauerwarnung ohne Aussage."""
        for k in ("offen", "intern"):
            _w, auflagen = pool.steckbrief_pruefen({**GUT, "datenklasse": k})
            self.assertEqual(auflagen, [], msg=k)

    def test_auflage_ist_ein_rueckgabewert_und_kein_kommentar(self):
        """⚠ Die Lehre von SWR-122: eine Erkenntnis, die die Funktion nicht verlaesst,
        liest niemand. Die Auflage ist deshalb Teil des Ergebnisses."""
        self.assertEqual(len(pool.steckbrief_pruefen(GUT)), 2)

    def test_text_wird_bereinigt_wie_im_pool(self):
        """Eine Quelle fuer die Bereinigung (B033): `_text_bereinigen`, nicht daneben."""
        werte, _ = pool.steckbrief_pruefen({**GUT, "auftrag": "  Zeile1\nZeile2  "})
        self.assertNotIn("\n", werte["auftrag"])
        self.assertTrue(werte["auftrag"].startswith("Zeile1"))

    def test_kein_steckbrief_ist_ein_fehler_und_kein_leeres_ergebnis(self):
        for schlecht in (None, "", [], 0):
            with self.assertRaises(pool.PoolFehler, msg=repr(schlecht)):
                pool.steckbrief_pruefen(schlecht)

    def test_unbekannte_felder_werden_nicht_uebernommen(self):
        """Der Antrag traegt genau die sechs entschiedenen Felder — ein siebtes waere
        eine Feldliste, die niemand beschlossen hat."""
        werte, _ = pool.steckbrief_pruefen({**GUT, "budget": "5000 EUR"})
        self.assertNotIn("budget", werte)
        self.assertEqual(set(werte), set(pool.STECKBRIEF_FELDER))

    def test_keine_laengengrenze_neben_swr_124(self):
        """Langer Text laeuft seit SWR-124 in eine eigene Datei. Eine Grenze hier waere
        die dritte Antwort auf dieselbe Frage (B033) — FELD_MAX ist 200 -> 4.000 ->
        200.000 gewandert, und richtig war nie eine Zahl, sondern ein Zielort."""
        werte, _ = pool.steckbrief_pruefen({**GUT, "auftrag": "x" * 9000})
        self.assertEqual(len(werte["auftrag"]), 9000)


if __name__ == "__main__":
    unittest.main()
