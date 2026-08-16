# -*- coding: utf-8 -*-
"""P8-Tests SWR-062/064/065: Ollama-Verdichtung (injiziert), Takt-Fälligkeit, Zustellung.
Hermetisch (gb-02): Temp-Basis, injizierte Funktionen, kein Netz/IMAP/SMTP.
Übersprungen, wenn team-mail lokal nicht vorliegt (Datenklasse sensibel — nicht in CI)."""
import datetime
import os
import shutil
import sys
import tempfile
import unittest

_WURZEL = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_TOOLS = os.path.join(_WURZEL, "team-mail", "tools")


@unittest.skipUnless(os.path.isfile(os.path.join(_TOOLS, "mail_digest.py")),
                     "team-mail liegt lokal nicht vor (CI) — Tests laufen nur auf dem Team-Node")
class MailAutopilotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, _TOOLS)
        import mail_digest
        cls.md = mail_digest

    def setUp(self):
        self.basis = tempfile.mkdtemp(prefix="autopilot-test-")
        self.addCleanup(shutil.rmtree, self.basis, ignore_errors=True)
        os.makedirs(os.path.join(self.basis, "digest"))

    def _konfig(self, text):
        with open(os.path.join(self.basis, "konfiguration.yaml"), "w", encoding="utf-8") as f:
            f.write(text)

    def test_konfiguration_takte_und_fallback(self):
        """SWR-064: takte-Liste wird gelesen; altes zeitraum_tage fällt auf [n] zurück."""
        self._konfig("takte: [1, 7, 30]\nzustellung_mail: ja\n")
        self.assertEqual(self.md.lade_konfiguration(self.basis)["takte"], [1, 7, 30])
        self._konfig("zeitraum_tage: 7\n")
        self.assertEqual(self.md.lade_konfiguration(self.basis)["takte"], [7])

    def test_faelligkeit_je_takt(self):
        """SWR-064/065: fällig nur, wenn im Zeitraum kein Digest dieses Takts existiert."""
        heute = datetime.date(2026, 8, 16)
        self.assertTrue(self.md.faellig(1, self.basis, heute))
        with open(os.path.join(self.basis, "digest", "2026-08-16-tag-digest.md"), "w",
                  encoding="utf-8") as f:
            f.write("# x\n")
        self.assertFalse(self.md.faellig(1, self.basis, heute))
        with open(os.path.join(self.basis, "digest", "2026-08-01-woche-digest.md"), "w",
                  encoding="utf-8") as f:
            f.write("# x\n")
        self.assertTrue(self.md.faellig(7, self.basis, heute))   # 15 Tage alt -> fällig
        self.assertTrue(self.md.faellig(30, self.basis, heute))  # noch nie -> fällig

    def test_verdichte_erfolg_und_fallback(self):
        """SWR-062: injiziertes Ollama liefert Markdown -> Text; Fehler/leer -> None (Fallback)."""
        cfg = {"ollama_modell": "test", "abschnitt_rechnungen": True}
        mails = [{"von": "a", "betreff": "b", "zeit": "z", "link": ""}]
        text = self.md.verdichte(mails, cfg, "tag", ollama=lambda m, p: "## Auf einen Blick\nOK")
        self.assertIn("## Auf einen Blick", text)

        def kaputt(m, p):
            raise OSError("kein Ollama")
        self.assertIsNone(self.md.verdichte(mails, cfg, "tag", ollama=kaputt))
        self.assertIsNone(self.md.verdichte(mails, cfg, "tag", ollama=lambda m, p: "kein markdown"))

    def test_ki_hinweis_im_prompt(self):
        """SWR-072: konfigurierter Hinweis landet als Zusatz-Auftrag im Prompt; leer = wie bisher.
        SWR-071: ollama_modell wird aus der Konfiguration gelesen."""
        self._konfig("takte: [1]\nollama_modell: llama3.1:8b\n"
                     "ki_hinweis: achte auf Bewerbungen\n")
        cfg = self.md.lade_konfiguration(self.basis)
        self.assertEqual(cfg["ollama_modell"], "llama3.1:8b")
        self.assertEqual(cfg["ki_hinweis"], "achte auf Bewerbungen")
        mails = [{"von": "a", "betreff": "b", "zeit": "z", "link": ""}]
        gesehen = []
        self.md.verdichte(mails, cfg, "tag",
                          ollama=lambda m, p: gesehen.append((m, p)) or "## Auf einen Blick\nOK")
        modell, prompt = gesehen[0]
        self.assertEqual(modell, "llama3.1:8b")
        self.assertIn("achte auf Bewerbungen", prompt)
        self.assertIn("ZUSATZ-AUFTRAG", prompt)
        self.assertIn("## Auf einen Blick", prompt)  # feste Struktur bleibt erhalten
        ohne = self.md._prompt(mails, "tag", True, "")
        self.assertNotIn("ZUSATZ-AUFTRAG", ohne)

    def test_jetzt_takte_folgt_konfiguration(self):
        """SWR-063 (team-mail/T-0003): „Jetzt zusammenfassen" nimmt die gespeicherten Takte.

        Regression zu Brief `team-mail/N-0002`: `--jetzt` rief fest `lauf_takt(1, cfg)`,
        während das Team auf `takte: [7]` steht — jeder Klick erzeugte einen Tages- statt
        des konfigurierten Wochen-Digests, ohne Fehlermeldung, erkennbar nur am Dateinamen.
        Gegen den alten Code scheitert der erste Fall nachweislich.
        """
        self.assertEqual(self.md.jetzt_takte({"takte": [7]}), [7])
        self.assertEqual(self.md.jetzt_takte({"takte": [1, 7, 30]}), [1, 7, 30])
        self.assertEqual(self.md.jetzt_takte({"takte": []}), [1])   # rueckwaertskompatibel
        self.assertEqual(self.md.jetzt_takte({"takte": [7]}, tage=1), [1])   # Override greift
        self.assertEqual(self.md.jetzt_takte({"takte": [7]}, tage=99), [1])  # ungueltig -> Tag

    def test_lauf_takt_schreibt_und_stellt_zu(self):
        """SWR-062/065: Lauf schreibt Digest-Datei mit Takt-Namen und stellt genau einmal zu."""
        heute = datetime.date(2026, 8, 16)
        cfg = {"takte": [1], "konten": [], "abschnitt_rechnungen": True,
               "zustellung_mail": True, "ollama_modell": "test"}
        gesendet = []

        def sende(betreff, text):
            gesendet.append(betreff)
            return True, "ok"
        pfad = self.md.lauf_takt(
            1, cfg, basis=self.basis,
            hole=lambda c, t: [{"von": "a", "betreff": "b", "zeit": "z", "link": ""}],
            verdichter=lambda m, c, n: "## Auf einen Blick\nEine Mail.",
            sende=sende, heute=heute)
        self.assertTrue(pfad.endswith("2026-08-16-tag-digest.md"))
        inhalt = open(pfad, encoding="utf-8").read()
        self.assertIn("## Auf einen Blick", inhalt)
        self.assertIn(self.md.VERMERK, inhalt)
        self.assertEqual(len(gesendet), 1)
        self.assertEqual(self.md.sende_digest(pfad, basis=self.basis, sende=sende),
                         "bereits zugestellt")  # idempotent
        self.assertEqual(len(gesendet), 1)
        self.assertFalse(self.md.faellig(1, self.basis, heute))


if __name__ == "__main__":
    unittest.main()
