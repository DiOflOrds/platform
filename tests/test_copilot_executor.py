"""Unit-Verifikation Copilot-Executor v1 (T-0069). Verifiziert: SWR-008."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gateway.executors import copilot_executor  # noqa: E402

ANTWORT = """Erledigt.

===DATEI: docs/notiz.md===
Inhalt aus Copilot.
===ENDE===
"""


class CopilotExecutorTest(unittest.TestCase):
    def test_fehlende_cli_faellt_zur_naechsten_stufe(self):
        """Ohne installierte CLI: NotImplementedError (Ketten-Fallback). Verifiziert: SWR-008, SWR-007."""
        with mock.patch.object(copilot_executor.shutil, "which", return_value=None):
            with self.assertRaises(NotImplementedError):
                copilot_executor.fuehre_aus("dev", "Aufgabe", {"arbeitsverzeichnis": "."}, {})

    def test_dateibloecke_werden_eingepflegt(self):
        """Erfolgreicher Lauf schreibt Datei-Blöcke ins Arbeitsverzeichnis, Kosten 0. Verifiziert: SWR-008, SWR-009."""
        with tempfile.TemporaryDirectory() as d:
            fertig = mock.Mock(returncode=0, stdout=ANTWORT, stderr="")
            with mock.patch.object(copilot_executor.shutil, "which", return_value="/usr/bin/copilot"), \
                 mock.patch.object(copilot_executor.subprocess, "run", return_value=fertig) as lauf:
                erg = copilot_executor.fuehre_aus(
                    "dev", "Aufgabe", {"arbeitsverzeichnis": d, "systemprompt": "SP"},
                    {"providers": {"copilot": {"befehl": ["copilot", "-p", "{prompt}"]}}})
            self.assertEqual(erg["kosten_eur"], 0.0)
            self.assertIn("SP", lauf.call_args.args[0][2])  # Prompt eingesetzt
            self.assertEqual(open(os.path.join(d, "docs", "notiz.md"),
                                  encoding="utf-8").read().strip(), "Inhalt aus Copilot.")

    def test_cli_fehler_liefert_log_statt_crash(self):
        """Exit != 0 wird als Ergebnis-Log gemeldet (kein Abbruch der Kette nach Start). Verifiziert: SWR-008."""
        fertig = mock.Mock(returncode=1, stdout="", stderr="auth required")
        with mock.patch.object(copilot_executor.shutil, "which", return_value="/usr/bin/copilot"), \
             mock.patch.object(copilot_executor.subprocess, "run", return_value=fertig):
            erg = copilot_executor.fuehre_aus("dev", "A", {"arbeitsverzeichnis": "."}, {})
        self.assertIn("auth required", erg["log"])


if __name__ == "__main__":
    unittest.main()
