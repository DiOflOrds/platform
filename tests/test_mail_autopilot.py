# -*- coding: utf-8 -*-
"""P8-Tests SWR-062/064/065: Ollama-Verdichtung (injiziert), Takt-Fälligkeit, Zustellung.
Hermetisch (gb-02): Temp-Basis, injizierte Funktionen, kein Netz/IMAP/SMTP.
Übersprungen, wenn team-mail lokal nicht vorliegt (Datenklasse sensibel — nicht in CI)."""
import ast
import datetime
import inspect
import os
import shutil
import sys
import tempfile
import textwrap
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

    def test_was_laeuft_folgt_jetzt_takte(self):
        """SWR-090 (pm/T-0025): Auskunft ohne Wirkung — und aus derselben Quelle.

        `was_laeuft` darf die Takte nicht selbst aus `cfg["takte"]` ableiten, sondern
        muss `jetzt_takte()` benutzen: dieselbe Funktion, die der Lauf verwendet. Der
        Nachweis läuft über den `--tage`-Override, den nur `jetzt_takte()` kennt —
        eine Nachbildung aus der Konfiguration würde ihn nicht abbilden.
        """
        cfg = {"takte": [7], "konten": [], "abschnitt_rechnungen": True,
               "zustellung_mail": True, "ollama_modell": "", "ki_hinweis": " achte auf X "}
        v = self.md.was_laeuft(cfg)
        self.assertEqual(v["takte"], [{"tage": 7, "name": "woche"}])
        self.assertTrue(v["automatisch"])          # leeres Modell = automatisch
        self.assertEqual(v["modell"], "")
        self.assertEqual(v["ki_hinweis"], "achte auf X")   # getrimmt, aber wortgetreu
        self.assertTrue(v["zustellung_mail"])
        self.assertEqual(self.md.was_laeuft(cfg, tage=1)["takte"],
                         [{"tage": 1, "name": "tag"}])     # Override wie im Lauf
        cfg2 = dict(cfg, takte=[1, 7, 30], ollama_modell="llama3", ki_hinweis="")
        self.assertEqual([t["tage"] for t in self.md.was_laeuft(cfg2)["takte"]], [1, 7, 30])
        self.assertFalse(self.md.was_laeuft(cfg2)["automatisch"])
        self.assertEqual(self.md.was_laeuft(cfg2)["ki_hinweis"], "")

    def test_was_laeuft_ohne_wirkung(self):
        """SWR-090: die Auskunft schreibt nichts und ändert die Fälligkeit nicht."""
        vorher = sorted(os.listdir(os.path.join(self.basis, "digest")))
        cfg = {"takte": [7], "konten": [], "abschnitt_rechnungen": True,
               "zustellung_mail": False, "ollama_modell": "", "ki_hinweis": ""}
        self.md.was_laeuft(cfg)
        self.assertEqual(sorted(os.listdir(os.path.join(self.basis, "digest"))), vorher)
        self.assertTrue(self.md.faellig(7, self.basis, datetime.date(2026, 8, 16)))

    def test_digest_marker_in_der_ergebniszeile(self):
        """SWR-090: Die Ergebniszeile trägt `DIGEST_MARKER` — die Plattform liest ihn
        wieder aus (`teams._digest_dateien`), um die geschriebenen Dateien zu benennen."""
        import contextlib
        import io
        cfg = {"takte": [7], "konten": [], "abschnitt_rechnungen": True,
               "zustellung_mail": False, "ollama_modell": "test", "ki_hinweis": ""}
        puffer = io.StringIO()
        with contextlib.redirect_stdout(puffer):
            self.md.lauf_takt(
                7, cfg, basis=self.basis,
                hole=lambda c, t: [{"von": "a", "betreff": "b", "zeit": "z", "link": ""}],
                verdichter=lambda m, c, n: "## Auf einen Blick\nEine Mail.",
                heute=datetime.date(2026, 8, 16))
        zeilen = [z for z in puffer.getvalue().splitlines() if self.md.DIGEST_MARKER in z]
        self.assertEqual(len(zeilen), 1)
        self.assertTrue(zeilen[0].endswith("2026-08-16-woche-digest.md"))

    def _lauf(self, cfg, heute):
        return self.md.lauf_takt(
            1, cfg, basis=self.basis,
            hole=lambda c, t: [{"von": "a", "betreff": "b", "zeit": "z", "link": ""}],
            verdichter=lambda m, c, n: "## Auf einen Blick\nEine Mail.",
            heute=heute)

    def test_lauf_takt_schreibt_und_legt_in_den_ausgang(self):
        """SWR-062/065/219: Lauf schreibt den Digest und legt die FERTIGE Mail in `ausgang/`.

        ⚠ Diese Zusicherung stand bis Sprint 38 auf der anderen Seite: sie verlangte, dass
        `lauf_takt` **sendet**. Der Auftraggeber hat in `N-0005` das Gegenteil aufgetragen
        (*„Gesendet wird nichts"*), und `team-mail/T-0006` baut genau bis zum Ausgang.
        """
        heute = datetime.date(2026, 8, 16)
        cfg = {"takte": [1], "konten": [], "abschnitt_rechnungen": True,
               "zustellung_mail": True, "ollama_modell": "test",
               "zustellung_an": "dimitri.john83@gmail.com"}
        pfad = self._lauf(cfg, heute)
        self.assertTrue(pfad.endswith("2026-08-16-tag-digest.md"))
        inhalt = open(pfad, encoding="utf-8").read()
        self.assertIn("## Auf einen Blick", inhalt)
        self.assertIn(self.md.AUSGANG_VERMERK, inhalt)
        self.assertNotIn(self.md.VERMERK, inhalt, "nichts darf als zugestellt gelten")
        eml = os.path.join(self.basis, self.md.AUSGANG, "2026-08-16-tag-digest.eml")
        self.assertTrue(os.path.exists(eml))
        mail = open(eml, encoding="utf-8").read()
        self.assertIn("To: dimitri.john83@gmail.com", mail)
        self.assertIn("NICHT GESENDET", mail)
        self.assertIn("## Auf einen Blick", mail)
        # idempotent — ein zweiter Lauf legt keine zweite Mail
        self.assertEqual(self.md.lege_in_ausgang(pfad, cfg, basis=self.basis, heute=heute),
                         "bereits im Ausgang")
        self.assertFalse(self.md.faellig(1, self.basis, heute))

    def test_kein_versandweg_aus_dem_lauf(self):
        """⚠⚠ Die Zusicherung, die beim versehentlichen Scharfschalten ROT wird (T-0006 DoD).

        Sie prüft nicht den Text der Funktion, sondern spannt einen Draht: jeder Versuch,
        aus einem vollständigen Takt heraus `mailer.sende` **oder** `sende_digest` zu
        erreichen, schlägt hier auf. Der Versandweg selbst bleibt gebaut — er wird nur
        aus dem Betrieb nicht mehr gerufen.
        """
        gerufen = []
        echt = self.md.sende_digest
        self.md.sende_digest = lambda *a, **k: gerufen.append("sende_digest")
        try:
            cfg = {"takte": [1], "konten": [], "abschnitt_rechnungen": True,
                   "zustellung_mail": True, "ollama_modell": "test",
                   "zustellung_an": "dimitri.john83@gmail.com"}
            self._lauf(cfg, datetime.date(2026, 8, 17))
        finally:
            self.md.sende_digest = echt
        self.assertEqual(gerufen, [], "aus dem Betrieb darf kein Versand ausgehen")
        # ⚠ Über den AST und nicht über den Text: der erste Entwurf prüfte den Quelltext
        # und wurde von einem KOMMENTAR rot, der `sende_digest` bloss ERWÄHNT. Eine
        # Zusicherung, die auf Prosa anschlägt, misst nicht die Regel (SWR-216-Lehre).
        baum = ast.parse(textwrap.dedent(inspect.getsource(self.md.lauf_takt)))
        gerufene = {k.func.id for k in ast.walk(baum)
                    if isinstance(k, ast.Call) and isinstance(k.func, ast.Name)}
        self.assertNotIn("sende_digest", gerufene)
        self.assertNotIn("sende", gerufene)
        argumente = {a.arg for a in baum.body[0].args.args}
        self.assertNotIn("sende", argumente,
                         "ein Parameter, der den Versand scharfschaltet, ist keine Sperre")

    def test_ohne_entscheidung_kein_empfaenger_und_keine_mail(self):
        """SWR-219: fehlt `zustellung_an`, entsteht KEINE Mail — kein erfundener Default.

        Ein Vorgabeempfänger wäre bei einer Handlung mit Außenwirkung die teuerste Art,
        „ich weiß es nicht" zu sagen (`SWR-208`).
        """
        heute = datetime.date(2026, 8, 18)
        cfg = {"takte": [1], "konten": [], "abschnitt_rechnungen": True,
               "zustellung_mail": True, "ollama_modell": "test", "zustellung_an": ""}
        self._lauf(cfg, heute)
        self.assertFalse(os.path.isdir(os.path.join(self.basis, self.md.AUSGANG)))

    def test_empfaenger_steht_nicht_im_quelltext(self):
        """DoD: „Empfänger aus der Entscheidung, nicht aus dem Code."""
        quelle = inspect.getsource(self.md)
        self.assertNotIn("dimitri.john83", quelle)
        self.assertNotIn("geraldine.john90", quelle)

    def test_versandweg_ist_weiterhin_gebaut(self):
        """Gegenrichtung: gesperrt heißt nicht abgerissen — `sende_digest` funktioniert.

        Sonst wäre die Sperre eine Löschung, und nach der Entscheidung des Auftraggebers
        müsste jemand den Weg neu bauen statt ihn zu rufen.
        """
        heute = datetime.date(2026, 8, 19)
        cfg = {"takte": [1], "konten": [], "abschnitt_rechnungen": True,
               "zustellung_mail": False, "ollama_modell": "test"}
        pfad = self._lauf(cfg, heute)
        gesendet = []

        def sende(betreff, text):
            gesendet.append(betreff)
            return True, "ok"
        self.assertEqual(self.md.sende_digest(pfad, basis=self.basis, sende=sende), "zugestellt")
        self.assertEqual(len(gesendet), 1)
        self.assertTrue(gesendet[0].startswith("[team-mail] 2026-08-19"))
        self.assertEqual(self.md.sende_digest(pfad, basis=self.basis, sende=sende),
                         "bereits zugestellt")  # idempotent
        self.assertEqual(len(gesendet), 1)

    def test_betreff_hat_nur_eine_quelle(self):
        """B033: Ausgang und Versand bilden denselben Betreff — aus derselben Funktion."""
        self.assertNotIn('f"[team-mail]', inspect.getsource(self.md.sende_digest))
        self.assertIn("mail_betreff", inspect.getsource(self.md.sende_digest))
        self.assertIn("mail_betreff", inspect.getsource(self.md.lege_in_ausgang))


if __name__ == "__main__":
    unittest.main()
