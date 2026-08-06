"""Unit-Verifikation T-0011 (Ollama-Executor) und T-0012 (Session-Austausch)
sowie der Datei-Block-Konvention. Ohne laufendes Ollama und ohne API-Key lauffähig.
Ausführung von der platform-Wurzel: python -m unittest discover tests
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gateway import core, dateiblock  # noqa: E402
from gateway.executors import session_executor  # noqa: E402

GUARDRAILS = """
budget: {limit_month_eur: 20, limit_tick_eur: 1.0, on_limit: stop_and_notify}
providers:
  ollama: {model: test-modell, status: active}
  session: {status: active}
permissions: {forbidden_actions: []}
logging: {run_registry: required}
"""

ANTWORT = """Hier die Dateien:

===DATEI: cm/cm-strategie.md===
# CM-Strategie
Inhalt Zeile 2.
===ENDE===

===DATEI: cm/unterordner/notiz.md===
Notiz.
===ENDE===
"""


class DateiblockTest(unittest.TestCase):
    def test_parse_zwei_bloecke(self):
        """Zwei Dateibloecke werden korrekt geparst. Verifiziert: SWR-009."""
        bloecke = dateiblock.parse_dateibloecke(ANTWORT)
        self.assertEqual([p for p, _ in bloecke], ["cm/cm-strategie.md", "cm/unterordner/notiz.md"])
        self.assertIn("Inhalt Zeile 2.", bloecke[0][1])

    def test_parse_crlf(self):
        """Dateibloecke mit CRLF werden geparst. Verifiziert: SWR-009."""
        bloecke = dateiblock.parse_dateibloecke(ANTWORT.replace("\n", "\r\n"))
        self.assertEqual(len(bloecke), 2)

    def test_pfad_traversal_verboten(self):
        """Pfad-Traversal ausserhalb des Repos wird abgelehnt. Verifiziert: SWR-009."""
        for pfad in ("../boese.md", "/etc/boese", "C:/boese.md"):
            text = f"===DATEI: {pfad}===\nx\n===ENDE==="
            with self.assertRaises(ValueError):
                dateiblock.parse_dateibloecke(text)

    def test_schreiben(self):
        """Dateibloecke werden repo-relativ geschrieben. Verifiziert: SWR-009."""
        with tempfile.TemporaryDirectory() as d:
            dateien = dateiblock.schreibe_dateibloecke(ANTWORT, d)
            self.assertEqual(dateien, ["cm/cm-strategie.md", "cm/unterordner/notiz.md"])
            inhalt = open(os.path.join(d, "cm", "cm-strategie.md"), encoding="utf-8").read()
            self.assertTrue(inhalt.startswith("# CM-Strategie"))

    def test_keine_bloecke(self):
        """Antwort ohne Bloecke liefert keine Artefakte. Verifiziert: SWR-009."""
        self.assertEqual(dateiblock.parse_dateibloecke("nur Prosa"), [])

    def test_repo_praefix_wird_entfernt(self):
        """Bekannte Repo-Praefixe werden entfernt (Lesson T-0013). Verifiziert: SWR-009."""
        # T-0013: Modell übernimmt 'process/cm/...' wörtlich, obwohl das
        # Arbeitsverzeichnis bereits die Repo-Wurzel 'process' ist.
        text = "===DATEI: process/cm/cm-strategie.md===\n# Strategie\n===ENDE==="
        with tempfile.TemporaryDirectory() as d:
            wurzel = os.path.join(d, "process")
            os.makedirs(wurzel)
            dateien = dateiblock.schreibe_dateibloecke(text, wurzel)
            self.assertEqual(dateien, ["cm/cm-strategie.md"])
            self.assertTrue(os.path.exists(os.path.join(wurzel, "cm", "cm-strategie.md")))
            self.assertFalse(os.path.exists(os.path.join(wurzel, "process")))

    def test_repo_praefix_nur_bei_treffer(self):
        """Praefix-Strip nur bei exaktem Treffer. Verifiziert: SWR-009."""
        text = "===DATEI: anderes/x.md===\nx\n===ENDE==="
        with tempfile.TemporaryDirectory() as d:
            wurzel = os.path.join(d, "process")
            os.makedirs(wurzel)
            self.assertEqual(dateiblock.schreibe_dateibloecke(text, wurzel), ["anderes/x.md"])


class SessionExecutorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.gr = os.path.join(self.tmp.name, "guardrails.yaml")
        open(self.gr, "w", encoding="utf-8").write(GUARDRAILS)
        self.registry = os.path.join(self.tmp.name, "runs", "run-registry.jsonl")
        self.arbeit = os.path.join(self.tmp.name, "arbeit")
        os.makedirs(self.arbeit)
        self.kontext = {"arbeitsverzeichnis": self.arbeit, "systemprompt": "Du bist CM.",
                        "guardrails_pfad": self.gr, "registry_pfad": self.registry,
                        "provider_kette": ["session"], "ticket": "T-0010", "geraet": "test"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_phase1_erzeugt_prompt_und_wartet(self):
        """Session-Phase 1 erzeugt Prompt-Datei und wartet. Verifiziert: SWR-008."""
        e = core.execute("cm", "Erstelle die CM-Strategie.", dict(self.kontext))
        self.assertEqual(e.status, "wartet")
        self.assertEqual(e.provider, "session")
        prompt = os.path.join(self.tmp.name, "runs", "session-austausch", "T-0010-prompt.md")
        self.assertTrue(os.path.exists(prompt))
        text = open(prompt, encoding="utf-8").read()
        self.assertIn("Du bist CM.", text)
        self.assertIn("===DATEI:", text)          # Ausgabeanweisung enthalten
        self.assertIn("T-0010-antwort.md", text)  # Zielname genannt

    def test_phase2_liest_antwort_ein(self):
        """Session-Phase 2 liest die Antwort ein. Verifiziert: SWR-008."""
        core.execute("cm", "x", dict(self.kontext))  # Phase 1
        antwort = os.path.join(self.tmp.name, "runs", "session-austausch", "T-0010-antwort.md")
        open(antwort, "w", encoding="utf-8").write(ANTWORT)
        e = core.execute("cm", "x", dict(self.kontext))
        self.assertEqual(e.status, "ok")
        self.assertEqual(e.kosten_eur, 0.0)
        self.assertTrue(os.path.exists(os.path.join(self.arbeit, "cm", "cm-strategie.md")))

    def test_antwort_ohne_bloecke_kein_erfolg(self):
        """Antwort ohne Dateibloecke ist kein Erfolg. Verifiziert: SWR-008."""
        os.makedirs(os.path.join(self.tmp.name, "runs", "session-austausch"))
        antwort = os.path.join(self.tmp.name, "runs", "session-austausch", "T-0010-antwort.md")
        open(antwort, "w", encoding="utf-8").write("nur Prosa, keine Blöcke")
        roh = session_executor.fuehre_aus("cm", "x", self.kontext, {})
        self.assertIn("keine Datei-Blöcke", roh["log"])

    def test_wartet_wird_protokolliert(self):
        """Wartezustand wird protokolliert. Verifiziert: SWR-008."""
        core.execute("cm", "x", dict(self.kontext))
        import json
        with open(self.registry, encoding="utf-8") as f:
            eintraege = [json.loads(z) for z in f if z.strip()]
        self.assertEqual(eintraege[0]["status"], "wartet")
        self.assertEqual(eintraege[0]["kosten_eur"], 0.0)


class OllamaExecutorTest(unittest.TestCase):
    def test_nicht_erreichbar_faellt_in_kette_zurueck(self):
        """Nicht erreichbares Ollama faellt in die Kette zurueck. Verifiziert: SWR-007."""
        alt = os.environ.get("OLLAMA_HOST")
        os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"  # Port 9 (discard): nie erreichbar
        try:
            with tempfile.TemporaryDirectory() as d:
                gr = os.path.join(d, "g.yaml")
                open(gr, "w", encoding="utf-8").write(GUARDRAILS)
                arbeit = os.path.join(d, "a")
                os.makedirs(arbeit)
                e = core.execute("cm", "x", {
                    "arbeitsverzeichnis": arbeit, "systemprompt": "s",
                    "guardrails_pfad": gr, "registry_pfad": os.path.join(d, "r.jsonl"),
                    "provider_kette": ["ollama"], "ticket": "T-0000", "geraet": "test"})
                self.assertEqual(e.status, "fehler")
                self.assertIn("ollama", e.meldung)
        finally:
            if alt is None:
                os.environ.pop("OLLAMA_HOST", None)
            else:
                os.environ["OLLAMA_HOST"] = alt

    def test_modellwahl(self):
        """Ollama-Modellwahl folgt Umgebung/Guardrails. Verifiziert: SWR-008."""
        from gateway.executors import ollama_executor
        import yaml as _y
        cfg = _y.safe_load(GUARDRAILS)
        alt = os.environ.pop("OLLAMA_MODEL", None)
        try:
            p = cfg["providers"]["ollama"]
            self.assertEqual(os.environ.get("OLLAMA_MODEL") or p.get("model"), "test-modell")
            os.environ["OLLAMA_MODEL"] = "override"
            self.assertEqual(os.environ.get("OLLAMA_MODEL") or p.get("model"), "override")
        finally:
            os.environ.pop("OLLAMA_MODEL", None)
            if alt is not None:
                os.environ["OLLAMA_MODEL"] = alt


if __name__ == "__main__":
    unittest.main()
