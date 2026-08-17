"""Die Token-Messung an der Quelle (SWR-141, promt-team/T-0005 DoD 1).

**Das Problem, das diese Datei löst.** Ollama meldet je Aufruf `prompt_eval_count` — die
Token des **ganzen** Prompts. Der Feldvertrag aus SWR-137 verlangt **zwei** Zahlen,
statisch und dynamisch. Eine Aufteilung nach Zeichen- oder Wortanteil wäre eine
Schätzung, und der Auftragstext von `promt-team/T-0001` verbietet sie wörtlich.

> **Zwei Messungen und eine Subtraktion sind keine Aufteilung.**

Gemessen wird der statische Anteil mit einem zweiten Aufruf **ohne Erzeugung**
(`num_predict: 0`), der nur die Systemnachricht enthält; der dynamische ist die Differenz.

⚠ Die schärfste Zusicherung hier ist `test_halbe_messung_liefert_gar_nichts`: eine halbe
Messung als ganze auszugeben ist der Fehler aus SWR-140 im Kleinen.

Ausführung: python -m unittest discover platform/tests
"""
import os
import sys
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
from gateway.executors import ollama_executor as ox  # noqa: E402


class TokenMessungTest(unittest.TestCase):
    """Verifiziert: SWR-141."""

    def setUp(self):
        self.echt_chat = ox._chat
        self.echt_urlopen = ox.urllib.request.urlopen
        self.rufe = []

    def tearDown(self):
        ox._chat = self.echt_chat
        ox.urllib.request.urlopen = self.echt_urlopen

    def _erreichbar(self):
        class R:
            def __enter__(self_):
                return self_

            def __exit__(self_, *a):
                return False

            def read(self_):
                return b'{"models": []}'

        ox.urllib.request.urlopen = lambda *a, **kw: R()

    def _antworten(self, *folge):
        rest = list(folge)

        def chat(host, nutzlast, timeout_s):
            self.rufe.append(nutzlast)
            return rest.pop(0)

        ox._chat = chat

    def _lauf(self, tmp):
        return ox.fuehre_aus("cm", "die Aufgabe",
                             {"arbeitsverzeichnis": tmp, "systemprompt": "SYS"}, {})

    def test_statisch_und_dynamisch_summieren_sich_zur_gemessenen_gesamtzahl(self):
        """⚠ Der Kern: BEIDE Zahlen sind gemessen, ihre Summe ist per Konstruktion die
        gemessene Gesamtzahl. Verifiziert: SWR-141."""
        import tempfile
        self._erreichbar()
        self._antworten({"message": {"content": ""}, "prompt_eval_count": 900},
                        {"prompt_eval_count": 700})
        with tempfile.TemporaryDirectory() as d:
            r = self._lauf(d)
        self.assertEqual(r["token_statisch"], 700)
        self.assertEqual(r["token_dynamisch"], 200)
        self.assertEqual(r["token_statisch"] + r["token_dynamisch"], 900)

    def test_die_sondierung_erzeugt_nichts_und_traegt_nur_das_system(self):
        """Der zweite Aufruf darf nichts generieren (`num_predict: 0`) und enthaelt NUR
        die Systemnachricht — sonst maesse er nicht den statischen Anteil.
        Verifiziert: SWR-141."""
        import tempfile
        self._erreichbar()
        self._antworten({"message": {"content": ""}, "prompt_eval_count": 900},
                        {"prompt_eval_count": 700})
        with tempfile.TemporaryDirectory() as d:
            self._lauf(d)
        sondierung = self.rufe[1]
        self.assertEqual(len(sondierung["messages"]), 1)
        self.assertEqual(sondierung["messages"][0]["role"], "system")
        self.assertEqual(sondierung["options"]["num_predict"], 0)

    def test_halbe_messung_liefert_gar_nichts(self):
        """⚠⚠ Fehlt die Sondierung, bleiben BEIDE Felder `None` — eine halbe Messung als
        ganze auszugeben ist der Fehler aus SWR-140 im Kleinen. Verifiziert: SWR-141."""
        import tempfile
        self._erreichbar()
        self._antworten({"message": {"content": ""}, "prompt_eval_count": 900},
                        {"kein_zaehler": True})
        with tempfile.TemporaryDirectory() as d:
            r = self._lauf(d)
        self.assertIsNone(r["token_statisch"])
        self.assertIsNone(r["token_dynamisch"])

    def test_ohne_gesamtzahl_wird_gar_nicht_sondiert(self):
        """Meldet der Hauptaufruf keine Gesamtzahl, ist die Sondierung sinnlos — und ein
        Aufruf, dessen Ergebnis niemand verwenden kann, gehoert nicht gemacht.
        Verifiziert: SWR-141."""
        import tempfile
        self._erreichbar()
        self._antworten({"message": {"content": ""}})
        with tempfile.TemporaryDirectory() as d:
            r = self._lauf(d)
        self.assertEqual(len(self.rufe), 1, "es darf keine zweite Anfrage geben")
        self.assertIsNone(r["token_statisch"])

    def test_negative_differenz_wird_nicht_gemeldet(self):
        """Gegenprobe gegen die eigene Rechnung: waere der statische Anteil groesser als
        das Ganze, ist die Messung kaputt — dann steht die Luecke da und keine Zahl.
        Verifiziert: SWR-141."""
        import tempfile
        self._erreichbar()
        self._antworten({"message": {"content": ""}, "prompt_eval_count": 100},
                        {"prompt_eval_count": 700})
        with tempfile.TemporaryDirectory() as d:
            r = self._lauf(d)
        self.assertIsNone(r["token_statisch"])
        self.assertIsNone(r["token_dynamisch"])

    def test_null_token_ist_eine_messung(self):
        """Die Gegenrichtung: ein statischer Anteil von 0 ist ein Ergebnis und wird
        GEMELDET, nicht als Luecke behandelt. Verifiziert: SWR-141."""
        import tempfile
        self._erreichbar()
        self._antworten({"message": {"content": ""}, "prompt_eval_count": 5},
                        {"prompt_eval_count": 0})
        with tempfile.TemporaryDirectory() as d:
            r = self._lauf(d)
        self.assertEqual(r["token_statisch"], 0)
        self.assertEqual(r["token_dynamisch"], 5)


class DurchreichenTest(unittest.TestCase):
    """Die gemessenen Zahlen kommen in der Run-Registry AN (SWR-141).

    ⚠ Nach SWR-122 entscheidet, wer eine Messung baut, im selben Zug ueber ihren Leser.
    Eine Zahl, die der Executor meldet und `core` verschluckt, ist keine Messung.
    """

    def test_core_reicht_die_token_an_das_ergebnis_durch(self):
        """Zugesichert am Syntaxbaum, weil der Weg vom Executor in die Registry ueber
        zwei Module laeuft. Verifiziert: SWR-141."""
        import ast
        pfad = os.path.join(_HIER, "..", "gateway", "core.py")
        baum = ast.parse(open(pfad, encoding="utf-8").read())
        schluessel = [k.value for k in ast.walk(baum)
                      if isinstance(k, ast.keyword) and k.arg
                      in ("token_statisch", "token_dynamisch")]
        self.assertEqual(len(schluessel), 2,
                         "core baut Ergebnis ohne die Token-Felder")

    def test_kein_default_auf_dem_weg(self):
        """⚠ Ein zweites Argument an `roh.get(...)` waere die Stelle, an der die fehlende
        Messung zur gemessenen Null wird — genau der Fehler, den `kosten_eur: 0.0`
        siebenmal im Bestand vormacht.

        ⚠ Geprueft am **Syntaxbaum** und nicht am Text: die erste Fassung dieses Tests
        suchte die Zeichenkette und wurde von der ERKLAERUNG DIESES FEHLERS im Kommentar
        daneben rot. Eine Textsuche kann eine Warnung nicht von ihrem Gegenstand
        unterscheiden. Verifiziert: SWR-141."""
        import ast
        pfad = os.path.join(_HIER, "..", "gateway", "core.py")
        baum = ast.parse(open(pfad, encoding="utf-8").read())
        for k in ast.walk(baum):
            if not (isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute)
                    and k.func.attr == "get"):
                continue
            if not k.args or not isinstance(k.args[0], ast.Constant):
                continue
            if str(k.args[0].value).startswith("token_"):
                self.assertEqual(len(k.args), 1,
                                 f"{k.args[0].value} bekommt einen Vorgabewert — "
                                 f"eine fehlende Messung wird damit zur gemessenen Zahl")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
