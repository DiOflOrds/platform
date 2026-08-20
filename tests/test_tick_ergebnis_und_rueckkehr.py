#!/usr/bin/env python3
"""SWR-167/168 (platform/T-0031): der Tick sagt, was er getan hat, und hinterlässt HEAD,
wo er ihn vorgefunden hat.

⚠⚠ Der Anlass ist gemessen und nicht ausgedacht. `SWR-166` hat am 2026-08-20 den Preflight
entsperrt; danach sind die **ersten drei Ticks überhaupt** durchgelaufen (20:00 platform,
20:15 platform, 20:15 team-mail). Alle drei meldeten:

    Gateway: status=fehler provider= kosten=0.00 € artefakte=[]
    Tick abgeschlossen. Review/PR: Branch feature/t-0001-…

Und der zweite Tick desselben Tickets fuhr HEAD auf die alte Branchspitze zurück, wodurch
`main` auf `in_progress` stehenblieb, während der Arbeitsbaum `open` zeigte — der Preflight
liest den Arbeitsbaum und meldete deshalb „In Arbeit liegengeblieben: 0".

⚠ Jede Zusicherung hier steht als **Paar**: neben „der Fehlerfall sagt nicht abgeschlossen"
steht „der Erfolgsfall sagt es weiterhin". Ohne die zweite Hälfte bestünde eine Fassung,
die das Wort nie mehr benutzt, jeden Test.
"""
import os
import sys
import unittest

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PLATFORM)
sys.path.insert(0, os.path.join(_PLATFORM, "orchestrator"))

from orchestrator import tick as tick_mod  # noqa: E402


class _Erg:
    """Gateway-Ergebnis, so viel davon wie die Schlusszeile anfasst."""

    def __init__(self, status, meldung="", artefakte=()):
        self.status = status
        self.meldung = meldung
        self.artefakte = list(artefakte)


class SchlusszeileTest(unittest.TestCase):
    """SWR-167: das Ergebniswort folgt dem Gateway-Status."""

    def test_fehler_sagt_nicht_abgeschlossen_und_nennt_status_und_meldung(self):
        zeile = tick_mod.schlusszeile(
            _Erg("fehler", "ollama: Anfrage fehlgeschlagen (404): model 'llama3.1:8b' not found"),
            erfolgreich=False, branch="feature/t-0001-x")
        self.assertNotIn("abgeschlossen", zeile.lower())
        self.assertIn("fehler", zeile)
        self.assertIn("404", zeile)

    def test_erfolg_sagt_weiterhin_abgeschlossen(self):
        # ⚠ Die andere Hälfte des Paares: ohne sie wäre eine Fassung, die das Wort nie
        # mehr benutzt, ununterscheidbar von der richtigen.
        zeile = tick_mod.schlusszeile(_Erg("ok", "", ["a.md"]),
                                      erfolgreich=True, branch="feature/t-0001-x")
        self.assertIn("Tick abgeschlossen", zeile)
        self.assertIn("feature/t-0001-x", zeile)

    def test_wartet_ist_weder_abgeschlossen_noch_fehler(self):
        zeile = tick_mod.schlusszeile(_Erg("wartet", "Antwortdatei fehlt"),
                                      erfolgreich=False, branch="feature/t-0001-x")
        self.assertNotIn("abgeschlossen", zeile.lower())
        self.assertIn("wartet", zeile.lower())
        self.assertIn("Antwortdatei fehlt", zeile)

    def test_ok_ohne_artefakt_gilt_nicht_als_abgeschlossen(self):
        """⚠ Der Fall, der die drei Läufe vom 20.08. beschreibt, wenn der Provider

        „ok" meldet und trotzdem nichts liefert: `erfolgreich` verlangt beides.
        """
        zeile = tick_mod.schlusszeile(_Erg("ok", "", []), erfolgreich=False,
                                      branch="feature/t-0001-x")
        self.assertNotIn("abgeschlossen", zeile.lower())
        self.assertIn("artefakte=0", zeile)

    def test_der_status_im_log_ist_derselbe_wie_in_der_registry(self):
        """Log und Run-Registry dürfen nicht auseinanderlaufen — genau das hat am 20.08.

        den Befund verdeckt: die Registry trug `status: fehler`, das Log „abgeschlossen".
        """
        for status in ("fehler", "abgebrochen", "wartet"):
            with self.subTest(status=status):
                zeile = tick_mod.schlusszeile(_Erg(status, "x"), erfolgreich=False,
                                              branch="b")
                self.assertIn(status, zeile)


class RueckkehrTest(unittest.TestCase):
    """SWR-168: ein bestehender Branch zieht HEAD nicht rückwärts, und die Rückkehr wird

    nachgeprüft."""

    def test_bestehender_branch_wird_nachgezogen_statt_ausgecheckt(self):
        """⚠ Der eigentliche Befund vom 20.08.: `checkout <branch>` setzte HEAD auf die

        **alte** Spitze. `checkout -B` legt den Branch auf den aktuellen Stand um; der
        Unterschied ist genau die Divergenz, die `main` und Branch auseinandergetrieben hat.
        """
        with open(os.path.join(_PLATFORM, "orchestrator", "tick.py"),
                  encoding="utf-8") as f:
            quelle = f.read()
        self.assertIn('git(ziel_repo, "checkout", "-B", branch)', quelle)
        self.assertNotIn('git(ziel_repo, "checkout", branch)', quelle)

    def test_die_rueckkehr_wird_nachgeprueft_und_bricht_ab(self):
        """Die Rückkehr stand mit `fehler_ok=True` da und ist am 20.08. stillschweigend

        misslungen. Ohne Nachprüfung ist ein misslungener Rückweg von einem gelungenen
        nicht zu unterscheiden.
        """
        with open(os.path.join(_PLATFORM, "orchestrator", "tick.py"),
                  encoding="utf-8") as f:
            quelle = f.read()
        self.assertIn('steht_auf != basis_branch', quelle)
        self.assertIn("SWR-168", quelle)

    def test_kein_return_im_finally(self):
        """⚠ Gegenprobe gegen den bequemen Bau: ein `return` im `finally` würde eine noch

        fliegende Ausnahme aus dem `try` verschlucken — der Abbruch sähe dann aus wie ein
        ordentliches Ende. Der Befund wird gemerkt und **nach** dem `finally` gewertet.

        ⚠ Geprüft werden **Anweisungen**, nicht das Wort: der erste Entwurf dieses Tests
        suchte nach „return" und wurde von seinem eigenen Kommentar rot gemacht, in dem das
        Wort erklärend vorkommt. *Eine Prüfung auf ein Wort prüft den Text, nicht den Code.*
        """
        with open(os.path.join(_PLATFORM, "orchestrator", "tick.py"),
                  encoding="utf-8") as f:
            quelle = f.read()
        block = quelle.split("    finally:\n", 1)[1].split("\n    if steht_auf", 1)[0]
        anweisungen = [z for z in block.splitlines()
                       if z.strip().startswith("return")]
        self.assertEqual(anweisungen, [], "return im finally verschluckt Ausnahmen")


if __name__ == "__main__":
    unittest.main()
