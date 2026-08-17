#!/usr/bin/env python3
"""platform/T-0009 — Kodierung an BEIDEN Enden eines Werkzeuglaufs.

Anlass ist ein Hostprotokoll, nicht eine Vermutung: der erste Wächterlauf nach der
T-0007-Reparatur (17.08. 03:59) kam bis `PREFLIGHT: STARTKLAR` — die Reparatur trägt —
und starb dann in `preflight.py` an

    UnicodeEncodeError: 'charmap' codec can't encode character '\\ufffd'
    in position 388: character maps to <undefined>

also am `print` eines Befundes, nicht am Lesen. Zwei Ursachen, die unabhängig
voneinander denselben Absturz erzeugen — beide bekommen hier ihren Test.
"""
import io
import os
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import konsole  # noqa: E402

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
PLATFORM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


class UrsacheAKindSchreibtAndersAlsElternLiest(unittest.TestCase):
    """Ursache A: Sprint 5 hat die LESEseite auf UTF-8 gestellt, die SCHREIBseite des
    eigenen Python-Kindprozesses nicht. Vorher sprachen beide zufällig cp1252."""

    KIND = ("import sys, io; "
            "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='cp1252'); "
            "print('ungültiger status')")

    def _ohne_pythonioencoding(self):
        env = dict(os.environ)
        env.pop("PYTHONIOENCODING", None)
        return env

    def test_altstand_erzeugt_genau_das_zeichen_das_cp1252_nicht_ausgeben_kann(self):
        """Kind schreibt cp1252, Eltern liest utf-8+replace -> U+FFFD.

        Das ist der Altstand (ohne env=). Er fällt gegen die Korrektur um: mit
        kind_umgebung() entsteht das Zeichen gar nicht erst.
        """
        out = subprocess.run([sys.executable, "-c", self.KIND], capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                             env=self._ohne_pythonioencoding())
        self.assertIn("�", out.stdout,
                      "Altstand muss U+FFFD erzeugen — sonst prüft dieser Test nichts")
        # ... und genau dieses Zeichen ist auf dem Host nicht mehr ausgebbar:
        with self.assertRaises(UnicodeEncodeError):
            out.stdout.encode("cp1252")

    def test_mit_kind_umgebung_entsteht_das_zeichen_nicht(self):
        """Die Korrektur: das Kind schreibt in derselben Kodierung, in der wir lesen."""
        kind = "print('ungültiger status')"  # ohne eigenen Wrapper: nimmt PYTHONIOENCODING
        out = subprocess.run([sys.executable, "-c", kind], capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                             env=konsole.kind_umgebung(self._ohne_pythonioencoding()))
        self.assertNotIn("�", out.stdout)
        self.assertIn("ungültiger status", out.stdout)

    def test_kind_umgebung_erbt_die_uebrige_umgebung_und_aendert_os_environ_nicht(self):
        """Gegenprobe: eine leere Umgebung wäre eine zweite, größere Änderung —
        ohne PATH findet ein Kindprozess auf Windows sein eigenes git nicht."""
        vorher = dict(os.environ)
        neu = konsole.kind_umgebung()
        self.assertEqual(neu["PYTHONIOENCODING"], "utf-8")
        for schluessel in ("PATH", "Path"):
            if schluessel in vorher:
                self.assertEqual(neu[schluessel], vorher[schluessel])
                break
        self.assertEqual(dict(os.environ), vorher, "os.environ darf nicht verändert werden")
        self.assertIsNot(neu, os.environ)


class UrsacheBMeldungStirbtAmMelden(unittest.TestCase):
    """Ursache B, unabhängig von A und älter: die Meldungen dieser Organisation
    zitieren Ticketinhalte, und die tragen Zeichen, die cp1252 nicht kennt."""

    def _cp1252_strom(self, fehlerweg="strict"):
        return io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors=fehlerweg)

    def test_ein_pfeil_aus_einem_ticket_beendet_den_lauf(self):
        """Der Altstand: `print` einer Meldung mit → auf einen cp1252-Strom stirbt.

        Kein konstruiertes Zeichen — 121 Ticketdateien dieser Organisation tragen es.
        """
        strom = self._cp1252_strom()
        with self.assertRaises(UnicodeEncodeError):
            strom.write("[p0] board-check: FEHLER — T-0001.md: status open → done unzulässig")
            strom.flush()

    def test_nach_sichere_ausgabe_kommt_die_meldung_an(self):
        """Die Korrektur: die Meldung wird beschädigt, nicht der Lauf."""
        strom = self._cp1252_strom()
        self.assertEqual(konsole.sichere_ausgabe([strom]), 1)
        strom.write("[p0] board-check: FEHLER — status open → done unzulässig")
        strom.flush()
        text = strom.buffer.getvalue().decode("cp1252")
        self.assertIn("board-check: FEHLER", text)
        self.assertIn("unzulässig", text, "Zeichen, die cp1252 KANN, bleiben unangetastet")
        self.assertIn("\\u2192", text, "der Pfeil wird lesbar ersetzt, nicht verschluckt")

    def test_der_fehlerweg_ist_backslashreplace_und_nicht_replace(self):
        """replace erzeugt U+FFFD — also genau das Zeichen, an dem cp1252 scheitert.

        Eine Reparatur, die den Fehler auf die nächste Stufe schiebt, ist keine.
        Dieser Test fällt um, wenn jemand AUSGABE_FEHLERWEG auf "replace" setzt.
        """
        self.assertEqual(konsole.AUSGABE_FEHLERWEG, "backslashreplace")
        strom = self._cp1252_strom()
        konsole.sichere_ausgabe([strom])
        strom.write("→")
        strom.flush()
        self.assertNotIn(b"\xef\xbf\xbd", strom.buffer.getvalue())

    def test_reine_ascii_ausgabe_bleibt_unveraendert(self):
        """Gegenprobe: die Korrektur wird nicht lauter als der Fehler."""
        strom = self._cp1252_strom()
        konsole.sichere_ausgabe([strom])
        strom.write("PREFLIGHT: STARTKLAR")
        strom.flush()
        self.assertEqual(strom.buffer.getvalue(), b"PREFLIGHT: STARTKLAR")

    def test_ein_strom_ohne_reconfigure_wird_uebersprungen_statt_zu_werfen(self):
        """Gegenprobe: sichere_ausgabe darf selbst kein neuer Absturzgrund sein."""
        class Alt:
            pass
        self.assertEqual(konsole.sichere_ausgabe([Alt()]), 0)


class RegelUeberDenGesamtenProduktionscode(unittest.TestCase):
    """L-2026-08-17j: eine Lehre, die nur an ihrem Fundort steht, schützt eine Zeile.

    T-0007 hat diesen Testtyp eingeführt — und sein Regel-Test prüfte nur das LESEN.
    Deshalb ist der Defekt dieses Tickets durch ihn hindurchgelaufen.
    """

    def _produktionsdateien(self):
        for ordner in ("scripts", "backend", "orchestrator", "gateway"):
            wurzel = os.path.join(PLATFORM, ordner)
            if not os.path.isdir(wurzel):
                continue
            for pfad, _, dateien in os.walk(wurzel):
                if "__pycache__" in pfad:
                    continue
                for d in dateien:
                    if d.endswith(".py"):
                        yield os.path.join(pfad, d)

    def test_jeder_python_kindprozess_bekommt_die_kind_kodierung(self):
        """Wer sys.executable im Textmodus aufruft, setzt env=konsole.kind_umgebung().

        Ohne diese Regel ist die T-0007-Korrektur an genau den Stellen ein Rückschritt,
        an denen Python Python aufruft.
        """
        ungesichert = []
        for pfad in self._produktionsdateien():
            text = open(pfad, encoding="utf-8").read()
            for treffer in re.finditer(r"subprocess\.run\(\s*\[\s*(?:_?sys)\.executable",
                                       text):
                aufruf = text[treffer.start():treffer.start() + 700]
                if "kind_umgebung" not in aufruf:
                    zeile = text[:treffer.start()].count("\n") + 1
                    ungesichert.append(f"{os.path.relpath(pfad, PLATFORM)}:{zeile}")
        self.assertEqual(ungesichert, [],
                         "Python-Kindprozesse ohne feste Ausgabekodierung: "
                         + ", ".join(ungesichert))

    def test_jeder_einstiegspunkt_sichert_seine_ausgabe(self):
        """Wer ein __main__ hat, kann Befunde drucken — und darf daran nicht sterben."""
        ohne = []
        for pfad in self._produktionsdateien():
            text = open(pfad, encoding="utf-8").read()
            if '__name__ == "__main__"' not in text:
                continue
            if "sichere_ausgabe()" not in text:
                ohne.append(os.path.relpath(pfad, PLATFORM))
        self.assertEqual(ohne, [],
                         "Einstiegspunkte ohne sichere Ausgabe: " + ", ".join(ohne))


class HostmeldungNachgestellt(unittest.TestCase):
    """Der Beleg aus abschluss-auto.log vom 17.08. 04:00, wörtlich nachgestellt."""

    def test_preflight_meldung_mit_ufffd_toetet_den_lauf_nicht_mehr(self):
        """Genau die Zeile aus preflight.py:239, genau das Zeichen aus dem Protokoll."""
        meldung = "[p1] board-check: FEHLER — " + "T-0001.md: ungültiger status\n" * 12
        meldung = meldung.replace("ü", "�", 1)
        self.assertIn("�", meldung)

        streng = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
        with self.assertRaises(UnicodeEncodeError) as fehler:
            streng.write(meldung)
            streng.flush()
        self.assertIn("\\ufffd", repr(str(fehler.exception)))

        sicher = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
        konsole.sichere_ausgabe([sicher])
        sicher.write(meldung)
        sicher.flush()
        self.assertIn("board-check: FEHLER", sicher.buffer.getvalue().decode("cp1252"))


if __name__ == "__main__":
    unittest.main()
