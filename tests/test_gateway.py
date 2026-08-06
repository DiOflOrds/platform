"""Unit-Verifikation Gateway v1 (T-0004: Schnittstellen-Vertrag) und
Guardrails v1 (T-0006: Limit-Überschreitung bricht ab).
Ausführung von der platform-Wurzel: python -m unittest discover tests
Benötigt: pyyaml (requirements.txt). Kein API-Key nötig (Fake-Executor).
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gateway import core, guardrails  # noqa: E402

GUARDRAILS = """
budget:
  limit_month_eur: 20
  limit_tick_eur: 1.0
  on_limit: stop_and_notify
providers:
  claude:
    models: {strong: m-strong, standard: m-standard, cheap: m-cheap}
routing: {}
permissions:
  forbidden_actions: [force_push, delete_tag]
logging:
  run_registry: required
"""


def fake_executor(kosten_eur=0.05, log="ok"):
    def _f(rolle, aufgabe, kontext, cfg):
        return {"modell": "fake-1", "log": log, "kosten_eur": kosten_eur}
    return _f


class GatewayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.gr = os.path.join(self.tmp.name, "guardrails.yaml")
        open(self.gr, "w", encoding="utf-8").write(GUARDRAILS)
        self.registry = os.path.join(self.tmp.name, "runs", "run-registry.jsonl")
        self.arbeit = os.path.join(self.tmp.name, "arbeit")
        os.makedirs(self.arbeit)
        self._executors_orig = dict(core.EXECUTORS)

    def tearDown(self):
        core.EXECUTORS.clear()
        core.EXECUTORS.update(self._executors_orig)
        self.tmp.cleanup()

    def kontext(self, **extra):
        k = {"arbeitsverzeichnis": self.arbeit, "systemprompt": "sp",
             "guardrails_pfad": self.gr, "registry_pfad": self.registry,
             "provider_kette": ["fake"], "ticket": "T-0000", "geraet": "test-node"}
        k.update(extra)
        return k

    def registry_eintraege(self):
        with open(self.registry, encoding="utf-8") as f:
            return [json.loads(z) for z in f if z.strip()]

    # --- T-0004: Schnittstellen-Vertrag ---

    def test_vertrag_ok(self):
        """execute() liefert Artefakte, Log, Kosten und Provider. Verifiziert: SWR-006."""
        core.EXECUTORS["fake"] = fake_executor(kosten_eur=0.10)
        e = core.execute("cm", "tu was", self.kontext())
        self.assertEqual(e.status, "ok")
        self.assertEqual(e.provider, "fake")
        self.assertEqual(e.modell, "fake-1")
        self.assertAlmostEqual(e.kosten_eur, 0.10)
        self.assertIsInstance(e.artefakte, list)
        self.assertIn("ok", e.log)

    def test_run_registry_wird_geschrieben(self):
        """Jede Aktion erzeugt einen vollstaendigen JSONL-Registry-Eintrag. Verifiziert: SWR-013."""
        core.EXECUTORS["fake"] = fake_executor()
        core.execute("cm", "tu was", self.kontext())
        eintraege = self.registry_eintraege()
        self.assertEqual(len(eintraege), 1)
        for feld in ("rolle", "ticket", "geraet", "provider", "status", "kosten_eur", "zeit"):
            self.assertIn(feld, eintraege[0])

    def test_kettenfallback_bei_notimplemented(self):
        """Nicht verfuegbarer Provider faellt auf naechste Kettenstufe zurueck. Verifiziert: SWR-007."""
        core.EXECUTORS["fake"] = fake_executor()
        e = core.execute("cm", "x", self.kontext(provider_kette=["ollama", "fake"]))
        self.assertEqual(e.status, "ok")
        self.assertEqual(e.provider, "fake")

    def test_stub_executoren_nicht_verfuegbar(self):
        """Copilot-Stub meldet NotImplemented bis Sprint 6. Verifiziert: SWR-008."""
        # copilot ist Stub (Sprint 6); ollama ist seit T-0011 real und meldet
        # ohne laufenden Server "nicht erreichbar" — beides fällt durch die Kette.
        e = core.execute("cm", "x", self.kontext(provider_kette=["copilot"]))
        self.assertEqual(e.status, "fehler")
        self.assertIn("Sprint 6", e.meldung)

    def test_unbekannter_provider(self):
        """Unbekannter Provider wird sauber abgewiesen. Verifiziert: SWR-006."""
        e = core.execute("cm", "x", self.kontext(provider_kette=["gibtsnicht"]))
        self.assertEqual(e.status, "fehler")

    # --- T-0006: Guardrails hart ---

    def test_tick_limit_ueberschreitung_bricht_ab(self):
        """Tick-Kostenlimit bricht vor weiteren LLM-Aufrufen ab. Verifiziert: SWR-011."""
        core.EXECUTORS["fake"] = fake_executor(kosten_eur=1.50)  # > 1.0
        e = core.execute("cm", "teuer", self.kontext())
        self.assertEqual(e.status, "abgebrochen")
        self.assertIn("Tick-Limit", e.meldung)
        self.assertEqual(self.registry_eintraege()[0]["status"], "abgebrochen")

    def test_monatslimit_verhindert_lauf(self):
        """Monatslimit stoppt den autonomen Betrieb. Verifiziert: SWR-012."""
        guardrails.schreibe_run(self.registry, {"kosten_eur": 20.0})
        aufgerufen = {"n": 0}

        def zaehler(rolle, aufgabe, kontext, cfg):
            aufgerufen["n"] += 1
            return {"modell": "x", "log": "", "kosten_eur": 0.0}
        core.EXECUTORS["fake"] = zaehler
        e = core.execute("cm", "x", self.kontext())
        self.assertEqual(e.status, "abgebrochen")
        self.assertIn("Monatslimit", e.meldung)
        self.assertEqual(aufgerufen["n"], 0)  # Executor wurde NICHT aufgerufen

    def test_monatsreserve_zu_klein(self):
        """Zu kleine Monatsreserve verhindert den Lauf. Verifiziert: SWR-012."""
        guardrails.schreibe_run(self.registry, {"kosten_eur": 19.5})  # 19.5 + 1.0 > 20
        core.EXECUTORS["fake"] = fake_executor()
        e = core.execute("cm", "x", self.kontext())
        self.assertEqual(e.status, "abgebrochen")

    def test_monatskosten_nur_laufender_monat(self):
        """Monatskosten zaehlen nur den laufenden Monat. Verifiziert: SWR-012."""
        guardrails.schreibe_run(self.registry, {"kosten_eur": 5.0, "zeit": "2001-01-01T00:00:00+00:00"})
        self.assertEqual(guardrails.monatskosten_eur(self.registry), 0.0)

    def test_verbotene_aktion(self):
        """Verbotene Aktionen werden unabhaengig von Rolle/Provider abgelehnt. Verifiziert: SWR-014."""
        cfg = guardrails.lade_guardrails(self.gr)
        self.assertTrue(guardrails.aktion_verboten(cfg, "force_push"))
        self.assertFalse(guardrails.aktion_verboten(cfg, "commit"))

    def test_unvollstaendige_guardrails(self):
        """Unvollstaendige Guardrails-Konfiguration verhindert den Lauf. Verifiziert: SWR-011."""
        kaputt = os.path.join(self.tmp.name, "kaputt.yaml")
        open(kaputt, "w", encoding="utf-8").write("budget: {limit_month_eur: 1, limit_tick_eur: 1, on_limit: x}\n")
        with self.assertRaises(guardrails.GuardrailVerletzung):
            guardrails.lade_guardrails(kaputt)

    def test_modellaufloesung(self):
        """Gate-relevante Typen laufen ausschliesslich auf der starken Claude-Stufe. Verifiziert: SWR-010."""
        from gateway.executors import claude_executor
        import yaml as _y
        cfg = _y.safe_load(GUARDRAILS)
        self.assertEqual(claude_executor._modell_fuer_stufe(cfg, "strong"), "m-strong")
        self.assertEqual(claude_executor._modell_fuer_stufe(cfg, None), "m-standard")

    def test_claude_ohne_key_nicht_verfuegbar(self):
        """Claude ohne API-Key gilt als nicht verfuegbar (Kettenfallback). Verifiziert: SWR-007."""
        alt = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            e = core.execute("cm", "x", self.kontext(provider_kette=["claude"]))
            self.assertEqual(e.status, "fehler")
            self.assertIn("ANTHROPIC_API_KEY", e.meldung)
        finally:
            if alt is not None:
                os.environ["ANTHROPIC_API_KEY"] = alt


if __name__ == "__main__":
    unittest.main()
