#!/usr/bin/env python3
"""SWR-212 (platform/T-0060): ein gescheiterter Lauf nennt den Provider, den er versucht hat.

⚠⚠ **Der Anlass ist eine Diagnose, die in DREI Sprints hintereinander falsch war — und
jedes Mal aus derselben Quelle gezogen wurde.**

Die Run-Registry ist nach `guardrails.logging.run_registry: required` die Beweisgrundlage
des Hauses für jeden Gateway-Lauf. Gemessen am Bestand (2026-08-21, alle drei Registries):

    {"rolle": "dev", …, "provider": "", "modell": "", "status": "fehler", …}

**9 von 9 ollama-Einträgen sind so geschrieben.** Der Kern erzeugte den Fehlerausgang als

    Ergebnis(status="fehler", meldung=letzter_fehler, dauer_s=…)

— also ohne `provider` und ohne `modell`. Beide blieben auf ihrem Vorgabewert `""`.

Was daraus geworden ist, ist keine Vermutung, sondern steht in den Berichten:

| Sprint | Diagnose aus der Registry | tatsächlich |
|---|---|---|
| 32 | „das Modell fehlt" | zutreffend, aber am 20.08. 22:05 behoben |
| 33 | „seit der Reparatur kein einziger Versuch" | **6 Versuche**, alle `404 llama3.1:8b` |
| 34 | „aus dieser Sandbox unerreichbar" | misst den falschen Rechner — der Takt läuft auf `DESKTOP-8OOO6JS` |

> **⚠⚠ Ein Fehlereintrag, der nicht sagt, WAS gescheitert ist, unterscheidet nicht
> zwischen „nichts wurde versucht" und „ollama hat mit 404 geantwortet". Beide sehen aus
> wie der erste Fall — und der erste Fall lädt zum Warten ein statt zum Nachsehen.**

Die Wahrheit lag die ganze Zeit im Feld `meldung`. Das ist das Feld, das keine Auswertung
dieses Hauses liest; gelesen werden `provider` und `modell`.

⚠ **Jede Zusicherung hier ist ein PAAR** (Bauform aus `SWR-148`): neben „der Fehler nennt
seinen Provider" steht „die echte Leere bleibt leer". Ohne die zweite Hälfte bestünde eine
Fassung, die einfach immer das erste Kettenglied hinschreibt, jeden Test in dieser Datei —
und würde aus „nicht versucht" eine Falschaussage machen, also genau den Schaden
verdoppeln, gegen den gebaut wird.
"""
import json
import os
import sys
import tempfile
import unittest

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PLATFORM)

from gateway import core  # noqa: E402
from gateway.executors import ollama_executor  # noqa: E402


def _kontext(tmp, kette, guardrails_pfad):
    return {
        "arbeitsverzeichnis": tmp,
        "systemprompt": "",
        "provider_kette": kette,
        "guardrails_pfad": guardrails_pfad,
        "registry_pfad": os.path.join(tmp, "run-registry.jsonl"),
        "ticket": "T-0001",
        "aufgaben_typ": "runbook-pflege",
        "geraet": "PRUEFSTAND",
    }


def _guardrails(tmp):
    pfad = os.path.join(tmp, "guardrails.yaml")
    with open(pfad, "w", encoding="utf-8") as f:
        f.write("budget:\n"
                "  limit_month_eur: 20\n"
                "  limit_tick_eur: 1.0\n"
                "  on_limit: stop_and_notify\n"
                "providers:\n  ollama:\n    model: llama3.1:8b\n"
                "permissions:\n  forbidden_actions: []\n"
                "logging:\n  run_registry: required\n")
    return pfad


def _eintraege(tmp):
    pfad = os.path.join(tmp, "run-registry.jsonl")
    if not os.path.exists(pfad):
        return []
    with open(pfad, encoding="utf-8") as f:
        return [json.loads(z) for z in f if z.strip()]


class FehlerNenntSeinenProvider(unittest.TestCase):
    """Der Fehlerausgang von `core.execute`."""

    def setUp(self):
        self._alt = dict(core.EXECUTORS)
        self.addCleanup(lambda: core.EXECUTORS.update(self._alt) or
                        [core.EXECUTORS.pop(k) for k in list(core.EXECUTORS)
                         if k not in self._alt])

    # ---- Hälfte 1: der Versuch wird benannt ---------------------------------

    def test_gescheiterter_ollama_lauf_nennt_provider_und_modell(self):
        """Der Fall aus dem Betrieb: ollama antwortet 404, das Modell fehlt."""
        def kaputt(rolle, aufgabe, kontext, cfg):
            raise ollama_executor._mit_modell(
                NotImplementedError("ollama: Anfrage fehlgeschlagen (404): "
                                    "{\"error\":\"model 'llama3.1:8b' not found\"}"),
                "llama3.1:8b")

        with tempfile.TemporaryDirectory() as tmp:
            core.EXECUTORS["ollama"] = kaputt
            erg = core.execute("CM", "Aufgabe",
                               _kontext(tmp, ["ollama"], _guardrails(tmp)))
            self.assertEqual(erg.status, "fehler")
            self.assertEqual(erg.provider, "ollama",
                             "der Fehler muss den versuchten Provider nennen")
            self.assertEqual(erg.modell, "llama3.1:8b",
                             "das Modell kommt vom Executor, der es aufgeloest hat")
            e = _eintraege(tmp)
            self.assertEqual(len(e), 1)
            self.assertEqual(e[0]["provider"], "ollama")
            self.assertEqual(e[0]["modell"], "llama3.1:8b")
            self.assertEqual(e[0]["versuchte_provider"], ["ollama"])

    def test_kette_nennt_alle_wirklich_versuchten(self):
        """[ollama, claude]: beide gerufen, beide gescheitert — beide in der Registry."""
        def kaputt(rolle, aufgabe, kontext, cfg):
            raise NotImplementedError("nicht verfuegbar")

        with tempfile.TemporaryDirectory() as tmp:
            core.EXECUTORS["ollama"] = kaputt
            core.EXECUTORS["claude"] = kaputt
            erg = core.execute("CM", "Aufgabe",
                               _kontext(tmp, ["ollama", "claude"], _guardrails(tmp)))
            self.assertEqual(erg.versuchte_provider, ["ollama", "claude"])
            self.assertEqual(erg.provider, "claude", "`provider` ist der LETZTE Versuch")
            self.assertEqual(_eintraege(tmp)[0]["versuchte_provider"],
                             ["ollama", "claude"])

    def test_modell_wird_NICHT_vom_vorgaenger_geerbt(self):
        """⚠⚠ Befund 2 des Gegenlesens, als Zusicherung festgehalten.

        Der erste Bau schrieb `letztes_modell = getattr(e, "modell", "") or
        letztes_modell`. Gemessen ergab das bei `[ollama, claude]` den Eintrag
        `provider='claude' modell='gemma3:27b'` — **claude hat gemma3 nie angefasst.**

        > **Ein Feld, das den Wert seines Vorgängers erbt, behauptet einen Versuch, den
        > es nicht gab.**
        """
        def mit_modell(rolle, aufgabe, kontext, cfg):
            raise ollama_executor._mit_modell(
                NotImplementedError("ollama: 404"), "gemma3:27b")

        def ohne_modell(rolle, aufgabe, kontext, cfg):
            raise RuntimeError("claude kaputt")

        with tempfile.TemporaryDirectory() as tmp:
            core.EXECUTORS["ollama"] = mit_modell
            core.EXECUTORS["claude"] = ohne_modell
            erg = core.execute("CM", "Aufgabe",
                               _kontext(tmp, ["ollama", "claude"], _guardrails(tmp)))
            self.assertEqual(erg.provider, "claude")
            self.assertEqual(erg.modell, "",
                             "claude hat kein Modell gemeldet -> das Feld bleibt LEER, "
                             "es erbt nicht das Modell von ollama")
            self.assertEqual(_eintraege(tmp)[0]["modell"], "")

    def test_unbekanntes_letztes_glied_loescht_die_echte_meldung_nicht(self):
        """⚠⚠ Befund 3 des Gegenlesens, als Zusicherung festgehalten.

        Bei `[ollama, gibtsnicht]` folgte `meldung` der KETTE und `provider` dem
        VERSUCH. Der Leser sah *„ollama/gemma3:27b gescheitert, weil ein unbekannter
        Provider da war"* — der echte 404-Text war weg, also genau das Feld, in dem
        laut dieser Anforderung „die Wahrheit lag".
        """
        def mit_modell(rolle, aufgabe, kontext, cfg):
            raise ollama_executor._mit_modell(
                NotImplementedError("ollama: Anfrage fehlgeschlagen (404)"), "gemma3:27b")

        with tempfile.TemporaryDirectory() as tmp:
            core.EXECUTORS["ollama"] = mit_modell
            core.EXECUTORS.pop("gibtsnicht", None)
            erg = core.execute("CM", "Aufgabe",
                               _kontext(tmp, ["ollama", "gibtsnicht"], _guardrails(tmp)))
            self.assertEqual(erg.provider, "ollama")
            self.assertEqual(erg.modell, "gemma3:27b")
            self.assertIn("404", erg.meldung,
                          "die Meldung des ECHTEN Versuchs darf nicht ueberschrieben werden")
            self.assertIn("gibtsnicht", erg.meldung,
                          "das uebersprungene Glied geht auch nicht verloren")

    def test_keine_zweite_modellaufloesung_im_kern(self):
        """⚠⚠ Befund 1 des Gegenlesens: der Halbsatz *„never re-resolved in the core"*
        hatte KEINEN Vertreter.

        Gemessen: die volle `SWR-169`-Rangfolge liess sich in `core.execute` nachbauen,
        ohne dass ein einziger Test rot wurde — dieselbe Kopie, die am 2026-08-20 sechs
        Ticks gekostet hat.

        > **Ein Halbsatz in einer Anforderung, den keine Zusicherung vertritt, ist eine
        > Absichtserklärung.**

        Geprüft wird die ABWESENHEIT der Auflösungsquellen im Kern — nicht die
        Anwesenheit eines Namens (`SWR-202`: Anwesenheit ist nicht Verwendung, und ihre
        Umkehrung gilt hier).
        """
        import inspect
        quelle = inspect.getsource(core.execute)
        for verboten in ("OLLAMA_MODEL", "modell_name", "modell_der_besetzung",
                         "llama3.1", '["model"]', '"model"'):
            self.assertNotIn(verboten, quelle,
                             f"der Kern loest das Modell NICHT selbst auf ({verboten})")
        self.assertIn('getattr(e, "modell"', quelle,
                      "das Modell kommt vom Executor, der es aufgeloest hat")

    def test_erfolg_traegt_die_versuchte_kette_mit(self):
        """Auch der gute Ausgang sagt, was davor scheiterte — sonst ist die Kette blind."""
        def kaputt(rolle, aufgabe, kontext, cfg):
            raise NotImplementedError("nicht verfuegbar")

        def gut(rolle, aufgabe, kontext, cfg):
            return {"modell": "claude-x", "log": "fertig", "kosten_eur": 0.0}

        with tempfile.TemporaryDirectory() as tmp:
            core.EXECUTORS["ollama"] = kaputt
            core.EXECUTORS["claude"] = gut
            erg = core.execute("CM", "Aufgabe",
                               _kontext(tmp, ["ollama", "claude"], _guardrails(tmp)))
            self.assertEqual(erg.status, "ok")
            self.assertEqual(erg.provider, "claude")
            self.assertEqual(erg.versuchte_provider, ["ollama", "claude"],
                             "der gescheiterte erste Versuch darf nicht verschwinden")

    # ---- Hälfte 2: die echte Leere bleibt leer ------------------------------

    def test_unbekannter_provider_wird_NICHT_als_versuch_gezaehlt(self):
        """⚠ Die Gegenprobe. Ein Kettenglied ohne Executor wurde nie gerufen."""
        with tempfile.TemporaryDirectory() as tmp:
            core.EXECUTORS.pop("gibtsnicht", None)
            erg = core.execute("CM", "Aufgabe",
                               _kontext(tmp, ["gibtsnicht"], _guardrails(tmp)))
            self.assertEqual(erg.status, "fehler")
            self.assertEqual(erg.provider, "",
                             "kein Executor gerufen -> die Leere ist eine AUSSAGE")
            self.assertEqual(erg.versuchte_provider, [])
            self.assertEqual(_eintraege(tmp)[0]["versuchte_provider"], [])

    def test_leere_kette_faellt_auf_claude_zurueck_und_sagt_es(self):
        """⚠ Befund 16 des Gegenlesens: die erste Fassung nahm mit `assertIn(…, ("",
        "claude"))` **beide** Antworten an und leitete die Erwartung der Folgezeile aus
        dem beobachteten Wert ab.

        > **Eine Zusicherung, die ihre Erwartung aus dem Ergebnis bildet, prüft nur noch
        > Widerspruchsfreiheit — nicht Verhalten.**

        Gemessen ist das Verhalten eindeutig: eine leere Kette fällt im Kern auf
        `["claude"]` zurück, der Executor wird gerufen und scheitert.
        """
        def kaputt(rolle, aufgabe, kontext, cfg):
            raise NotImplementedError("claude nicht verfuegbar")

        with tempfile.TemporaryDirectory() as tmp:
            core.EXECUTORS["claude"] = kaputt
            k = _kontext(tmp, [], _guardrails(tmp))
            k["provider_kette"] = []
            erg = core.execute("CM", "Aufgabe", k)
            self.assertEqual(erg.provider, "claude")
            self.assertEqual(erg.versuchte_provider, ["claude"])

    # ---- Rueckbau-Waechter (SWR-148-Paarform) -------------------------------

    def test_rueckbauwaechter_fehlerausgang_setzt_provider(self):
        """⚠⚠ Ohne diese Zusicherung ist der Rueckbau auf `Ergebnis(status="fehler",
        meldung=…)` eine Zeile Arbeit — und der Schaden kehrt lautlos zurueck.

        Geprueft wird die VERWENDUNG, nicht die Anwesenheit: `SWR-202` hat gemessen, was
        eine Konstante wert ist, die dasteht und nicht gerufen wird.
        """
        import ast
        import inspect
        quelle = inspect.getsource(core.execute)
        baum = ast.parse("def f():\n" + "\n".join(
            "    " + z for z in quelle.splitlines()[1:]))
        gefunden = False
        for knoten in ast.walk(baum):
            if not (isinstance(knoten, ast.Call)
                    and getattr(knoten.func, "id", "") == "Ergebnis"):
                continue
            args = {k.arg for k in knoten.keywords}
            if any(k.arg == "status" and getattr(k.value, "value", None) == "fehler"
                   for k in knoten.keywords):
                gefunden = True
                self.assertIn("provider", args,
                              "der Fehlerausgang MUSS provider setzen (SWR-212)")
                self.assertIn("versuchte_provider", args)
                self.assertIn("modell", args)
        self.assertTrue(gefunden, "kein Fehlerausgang gefunden — Zusicherung waere leer")


if __name__ == "__main__":
    unittest.main()
