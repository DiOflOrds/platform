"""Unit-Verifikation Lauftelemetrie (SWR-137, promt-team/T-0004).

Teil **a** der Naht aus `promt-team/T-0001` (*erheben und schreiben*), gezogen nach der
**fünften** Verschiebung. Der Auftrag verbietet das Schätzen zweimal wörtlich (*„Token je
Artefakt messen, nicht schätzen"*, *„Fehlt eine Eingabe, wird das im Report als Blocker
vermerkt und nicht geschätzt"*), und die Zusicherungen hier sind fast alle Gegenproben
gegen genau dieses Schätzen.

⚠ Gemessen am Bestand vor dem Bauen (7 Läufe): **0 von 7** tragen ein Token-Feld,
**1 von 7** einen `aufgaben_typ`, und `kosten_eur: 0.0` steht **siebenmal** da, wo es
einmal „kostenlos gemessen" und zweimal „nie erhoben" bedeutet.

Ausführung: python -m unittest discover platform/tests
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import telemetrie  # noqa: E402
from gateway import guardrails  # noqa: E402
from gateway.core import Ergebnis  # noqa: E402


class ZustandTest(unittest.TestCase):
    """Die drei Zustände je Feld. Verifiziert: SWR-137."""

    def test_null_ist_eine_messung_und_kein_loch(self):
        """⚠⚠ Die Zusicherung, an der die ganze Anforderung hängt.

        Ein Ollama-Lauf kostet wirklich nichts. Diese `0` ist ein **Ergebnis**. Ein
        Session-Austausch erhebt keine Kosten — dort ist dasselbe Feld ein **Loch**. Der
        Bestand schreibt beides als `0.0`, und deshalb ist die Baseline von
        `promt-team/T-0001` aus ihm nicht ableitbar. Verifiziert: SWR-137.
        """
        z = telemetrie.zustaende({"kosten_eur": 0.0, "dauer_s": 12.5})
        self.assertEqual(z["kosten_eur"]["zustand"], telemetrie.ZUSTAND_ECHTE_NULL)
        self.assertEqual(z["kosten_eur"]["wert"], 0.0)
        self.assertEqual(z["dauer_s"]["zustand"], telemetrie.ZUSTAND_WERT)

    def test_fehlendes_feld_ist_nicht_geliefert_und_NICHT_null(self):
        """Die Gegenrichtung derselben Zusicherung, in beide Richtungen geprüft — zwei
        gleiche Werte an zwei verschiedenen Zuständen wären genau der Fehler.
        Verifiziert: SWR-137."""
        z = telemetrie.zustaende({})
        for feld in telemetrie.FELDER:
            self.assertEqual(z[feld]["zustand"], telemetrie.ZUSTAND_NICHT_GELIEFERT, feld)
            self.assertIsNone(z[feld]["wert"], feld)
        self.assertNotEqual(telemetrie.ZUSTAND_NICHT_GELIEFERT,
                            telemetrie.ZUSTAND_ECHTE_NULL)

    def test_die_zustandsnamen_kommen_aus_dem_vertrag(self):
        """⚠ Nicht abgeschrieben, sondern importiert: eine vierte Schreibweise von
        „keine Daten" ist die Bauart, die `platform/T-0016` als Altbestand führt. Geprüft
        wird **Identität**, nicht Gleichheit — zwei gleiche Zeichenketten in zwei Dateien
        sind exakt der Zustand, der SWR-131 gekostet hat. Verifiziert: SWR-137."""
        from backend import aggregation
        self.assertIs(telemetrie.ZUSTAND_ECHTE_NULL, aggregation.ZUSTAND_ECHTE_NULL)
        self.assertIs(telemetrie.ZUSTAND_NICHT_GELIEFERT,
                      aggregation.ZUSTAND_NICHT_GELIEFERT)
        self.assertIs(telemetrie.ZUSTAND_WERT, aggregation.ZUSTAND_WERT)

    def test_zustaende_liest_die_feldliste_und_keine_eigene(self):
        """Ein neues Telemetriefeld darf nicht an zwei Stellen eingetragen werden müssen.
        Verifiziert: SWR-137."""
        z = telemetrie.zustaende({})
        self.assertEqual(list(z.keys()), telemetrie.FELDER)


class BlockerTest(unittest.TestCase):
    """Fehlende Eingaben werden **genannt**, nicht geschätzt. Verifiziert: SWR-137."""

    def test_blocker_nennt_die_felder_namentlich(self):
        """B038: eine Zahl ohne den Gegenstand ist keine Meldung — wie SWR-114/SWR-120.
        Verifiziert: SWR-137."""
        b = telemetrie.blocker({"rolle": "cm", "provider": "ollama",
                                "aufgaben_typ": "cm-strategie",
                                "kosten_eur": 0.0, "dauer_s": 3.0})
        self.assertEqual(sorted(b), ["token_dynamisch", "token_statisch"])

    def test_eine_null_ist_KEIN_blocker(self):
        """⚠ Die Gegenprobe. Eine Messung als Lücke zu melden ist derselbe Fehler
        rückwärts — und würde jeden Ollama-Lauf zum Blocker erklären.
        Verifiziert: SWR-137."""
        b = telemetrie.blocker({"rolle": "cm", "provider": "ollama",
                                "aufgaben_typ": "cm-strategie", "kosten_eur": 0.0,
                                "dauer_s": 0.0, "token_statisch": 0,
                                "token_dynamisch": 0})
        self.assertEqual(b, [])

    def test_leerer_aufgaben_typ_ist_ein_blocker(self):
        """⚠ Der Befund am Bestand, als Zusicherung: `aufgaben_typ` ist in **6 von 7**
        Läufen leer, und ohne ihn ist der Soll/Ist-Vergleich je Aufgaben-Typ, den
        `promt-team/T-0001` verlangt, nicht rechenbar. Ein leerer String ist nach der
        Vertragsregel eine „echte Null" — für einen **Schlüssel** ist genau das die
        Lücke, und deshalb steht `aufgaben_typ` in `PFLICHT`. Verifiziert: SWR-137."""
        b = telemetrie.blocker({"rolle": "cm", "provider": "", "aufgaben_typ": "",
                                "kosten_eur": 0.0, "dauer_s": 1.0,
                                "token_statisch": 10, "token_dynamisch": 20})
        self.assertIn("aufgaben_typ", b)
        self.assertIn("provider", b)

    def test_leerer_schluessel_und_gemessene_null_im_SELBEN_eintrag(self):
        """⚠⚠ Die schärfste Form der Zusicherung: beide Fälle in **einem** Eintrag.

        `aufgaben_typ: ""` ist eine Lücke, `kosten_eur: 0.0` ist eine Messung — und die
        erste Fassung von `blocker()` hat beides gleich behandelt und damit den
        Hauptbefund dieses Tickets durchgewinkt (`aufgaben_typ` leer in 6 von 7 Läufen).

        > **Eine Regel über Messwerte auf einen Schlüssel anzuwenden ist eine
        > Kategorienverwechslung.**

        Getrennte Tests hätten das nicht gezeigt: jeder für sich war grün zu bekommen,
        indem man die Regel in die eine oder andere Richtung verschiebt. Verifiziert:
        SWR-137.
        """
        b = telemetrie.blocker({"rolle": "cm", "provider": "ollama", "aufgaben_typ": "",
                                "kosten_eur": 0.0, "dauer_s": 0.0,
                                "token_statisch": 0, "token_dynamisch": 0})
        self.assertEqual(b, ["aufgaben_typ"])

    def test_vollstaendiger_eintrag_hat_keinen_blocker(self):
        b = telemetrie.blocker({"rolle": "pl", "provider": "claude",
                                "aufgaben_typ": "sprint-planning", "kosten_eur": 0.42,
                                "dauer_s": 9.1, "token_statisch": 8000,
                                "token_dynamisch": 1200})
        self.assertEqual(b, [])

    def test_ergaenze_erfindet_nichts_und_laesst_den_bestand_stehen(self):
        """Die Altläufe müssen weiter gültig sein: `ergaenze` beschreibt, es überschreibt
        nicht. Verifiziert: SWR-137."""
        alt = {"rolle": "cm", "ticket": "T-0010", "kosten_eur": 0.0, "dauer_s": 177.4}
        neu = telemetrie.ergaenze(alt)
        self.assertEqual(alt, {"rolle": "cm", "ticket": "T-0010",
                              "kosten_eur": 0.0, "dauer_s": 177.4})
        self.assertEqual(neu["ticket"], "T-0010")
        self.assertIn("token_statisch", neu["blocker"])
        self.assertNotIn("token_statisch", neu, "das fehlende Feld wurde erfunden")


class SchreibwegTest(unittest.TestCase):
    """Die Anreicherung sitzt am **einen** Schreibweg. Verifiziert: SWR-137."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pfad = os.path.join(self.tmp.name, "runs", "run-registry.jsonl")

    def _letzte(self):
        with open(self.pfad, encoding="utf-8") as f:
            return json.loads(f.read().strip().splitlines()[-1])

    def test_schreibe_run_haengt_telemetrie_und_blocker_an(self):
        guardrails.schreibe_run(self.pfad, {"rolle": "cm", "provider": "ollama",
                                           "aufgaben_typ": "runbook-pflege",
                                           "kosten_eur": 0.0, "dauer_s": 2.0})
        e = self._letzte()
        self.assertEqual(e["telemetrie"]["kosten_eur"]["zustand"],
                         telemetrie.ZUSTAND_ECHTE_NULL)
        self.assertEqual(sorted(e["blocker"]), ["token_dynamisch", "token_statisch"])

    def test_die_registry_bleibt_append_only(self):
        guardrails.schreibe_run(self.pfad, {"rolle": "cm"})
        with open(self.pfad, encoding="utf-8") as f:
            vorher = f.read()
        guardrails.schreibe_run(self.pfad, {"rolle": "dev"})
        with open(self.pfad, encoding="utf-8") as f:
            self.assertTrue(f.read().startswith(vorher))

    def test_ergebnis_traegt_die_tokenfelder_mit_None_als_vorgabe(self):
        """⚠ Die Vorgabe ist `None` und nicht `0`. Ein Executor, der nichts meldet, hat
        nicht null Token verbraucht — er hat nicht gemessen. Verifiziert: SWR-137."""
        erg = Ergebnis(status="ok")
        self.assertIsNone(erg.token_statisch)
        self.assertIsNone(erg.token_dynamisch)

    def test_eine_gemeldete_null_kommt_als_null_durch(self):
        """Die Gegenprobe zum Durchreichen: wer wirklich 0 meldet, bekommt `echte_null`
        und keinen Blocker. Verifiziert: SWR-137."""
        guardrails.schreibe_run(self.pfad, {"rolle": "cm", "provider": "ollama",
                                           "aufgaben_typ": "runbook-pflege",
                                           "kosten_eur": 0.0, "dauer_s": 0.0,
                                           "token_statisch": 0, "token_dynamisch": 0})
        e = self._letzte()
        self.assertEqual(e["blocker"], [])
        self.assertEqual(e["telemetrie"]["token_statisch"]["zustand"],
                         telemetrie.ZUSTAND_ECHTE_NULL)


class BestandTest(unittest.TestCase):
    """Der gemessene Bestand, als Zusicherung statt als Behauptung im Bericht."""

    def test_die_sieben_altlaeufe_sind_lueckenhaft_und_das_ist_messbar(self):
        """⚠ Die Zahl im Ticket wird hier **nachgerechnet** und nicht zitiert: 0 von 7
        Läufen tragen ein Token-Feld. Läuft die Registry irgendwann voll, misst dieser
        Test den neuen Stand — und genau das ist erwünscht, denn eine Zahl im Bericht
        veraltet still. Verifiziert: SWR-137."""
        pfad = os.path.join(os.path.dirname(__file__), "..", "..", "p0", "management",
                            "runs", "run-registry.jsonl")
        if not os.path.isfile(pfad):
            self.skipTest("Run-Registry nicht vorhanden")
        with open(pfad, encoding="utf-8") as f:
            zeilen = [json.loads(z) for z in f if z.strip()]
        self.assertGreater(len(zeilen), 0)
        mit_token = [z for z in zeilen if not any(
            f in telemetrie.blocker(z) for f in ("token_statisch", "token_dynamisch"))]
        ohne_typ = [z for z in zeilen if "aufgaben_typ" in telemetrie.blocker(z)]
        self.assertEqual(len(mit_token), 0,
                         "ein Lauf trägt Token — die Zahl im Ticket ist veraltet")
        self.assertGreaterEqual(len(ohne_typ), 1,
                                "der Soll/Ist-Vergleich ist plötzlich vollständig "
                                "rechenbar — Ticket nachziehen")


if __name__ == "__main__":
    unittest.main()
