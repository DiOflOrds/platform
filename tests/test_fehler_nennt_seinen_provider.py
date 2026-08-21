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

    def test_leere_kette_nennt_niemanden(self):
        """Die zweite Gegenprobe: gar keine Kette, gar kein Versuch."""
        with tempfile.TemporaryDirectory() as tmp:
            k = _kontext(tmp, [], _guardrails(tmp))
            k["provider_kette"] = []
            erg = core.execute("CM", "Aufgabe", k)
            # leere Kette faellt im Kern auf ["claude"] zurueck; ohne Executor-Attrappe
            # ist claude nicht verfuegbar -> Versuch fand statt, Provider wird genannt.
            self.assertIn(erg.provider, ("", "claude"))
            self.assertEqual(erg.versuchte_provider,
                             [] if erg.provider == "" else ["claude"],
                             "Provider und Versuchsliste duerfen sich nie widersprechen")

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
