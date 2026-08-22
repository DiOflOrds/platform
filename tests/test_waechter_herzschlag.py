#!/usr/bin/env python3
"""SWR-215 (platform/T-0055, Teil A): der Herzschlag des Wächters bekommt einen Leser.

⚠⚠ **Der Befund ist kein fehlender Messwert, sondern ein Messwert ohne Messer.**
`waechter.py` begründet im eigenen Kopfkommentar, warum Frage 4 des Tickets („Wer bewacht
den Wächter?") beantwortet sei:

    Wer bewacht den Waechter (Frage 4): die Aufgabenplanung (ONLOGON-Task, siehe
    waechter-einrichten.cmd) plus der Herzschlag in waechter-status.json - sein
    Ausbleiben ist fuer jeden Leser messbar.

Am 2026-08-21 um 23:25:16 setzte der Herzschlag aus. Er blieb **14 Stunden** aus, während
`abschluss-auto` und `ollama-schnelltakt` im 15-Minuten-Takt weiterschrieben. Gemeldet hat
es kein Werkzeug, sondern der Sprint-36-Abschluss beim Nachsehen von Hand.

> **„Für jeden Leser messbar" hat 14 Stunden lang keinen Leser gehabt. Das ist derselbe
> Fehler wie beim Ollama-Takt (`SWR-214`), nur eine Etage höher: dort stand die wahre
> Aussage im Protokoll eines Dienstes, hier in einer JSON-Datei — beide Male an einer
> Stelle, an der niemand hinsieht.**

⚠ Jede Zusicherung ist ein **Paar** (`SWR-148`): neben „still wird erkannt" steht „lebendig
wird erkannt". Ohne die zweite Hälfte bestünde eine Fassung, die **immer** Alarm schlägt,
jede Prüfung hier — und würde nach drei Tagen so zuverlässig ignoriert wie das
Takt-Protokoll, das dieses Ticket überhaupt erst nötig gemacht hat.
"""
import datetime
import json
import os
import sys
import tempfile
import unittest

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PLATFORM)
sys.path.insert(0, os.path.join(_PLATFORM, "scripts"))

import preflight  # noqa: E402

_WURZEL = os.path.dirname(_PLATFORM)


def _status(tmp, herzschlag, **rest):
    inhalt = {"herzschlag": herzschlag}
    inhalt.update(rest)
    with open(os.path.join(tmp, preflight.WAECHTER_STATUS), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(inhalt, f)


_JETZT = datetime.datetime(2026, 8, 22, 14, 30, 0)


class HerzschlagWirdGelesen(unittest.TestCase):

    def test_frischer_herzschlag_meldet_lebt(self):
        """Die zweite Hälfte des Paares — ohne sie bestünde ein Dauer-Alarm jeden Test."""
        with tempfile.TemporaryDirectory() as tmp:
            _status(tmp, "2026-08-22 14:29:45", waechter_pid=23284)
            zeile = preflight.waechter_herzschlag(tmp, _JETZT)
            self.assertIn("lebt", zeile)
            self.assertIn("23284", zeile)
            self.assertNotIn("STILL", zeile)

    def test_ausgebliebener_herzschlag_wird_gemeldet(self):
        """Der echte Fall vom 21.08.: 14 Stunden still, die Bewachten liefen weiter."""
        with tempfile.TemporaryDirectory() as tmp:
            _status(tmp, "2026-08-21 23:25:16")
            zeile = preflight.waechter_herzschlag(tmp, _JETZT)
            self.assertIn("STILL", zeile)
            self.assertIn("2026-08-21 23:25:16", zeile)
            self.assertIn("905 Min", zeile, "das Alter muss in der Zeile stehen, "
                                            "nicht nur die Behauptung")

    def test_grenze_ist_abgeleitet_nicht_gesetzt(self):
        """⚠ `SWR-156` hatte diesen Zwilling schon: zwei Zahlen, beide plausibel.

        Die Toleranz ist Takt × Geduld. Eine freie Minutenkonstante daneben wäre eine
        zweite Antwort auf „wann gilt er als tot" (B033).
        """
        self.assertEqual(preflight.WAECHTER_TAKT_S, 30,
                         "der Takt muss der Vorgabe aus waechter.Waechter entsprechen")
        grenze_s = preflight.WAECHTER_TAKT_S * preflight.WAECHTER_GEDULD
        with tempfile.TemporaryDirectory() as tmp:
            knapp = _JETZT - datetime.timedelta(seconds=grenze_s - 5)
            _status(tmp, knapp.strftime("%Y-%m-%d %H:%M:%S"))
            self.assertIn("lebt", preflight.waechter_herzschlag(tmp, _JETZT))
            drueber = _JETZT - datetime.timedelta(seconds=grenze_s + 5)
            _status(tmp, drueber.strftime("%Y-%m-%d %H:%M:%S"))
            self.assertIn("STILL", preflight.waechter_herzschlag(tmp, _JETZT))

    def test_waechter_takt_stimmt_mit_waechter_py_ueberein(self):
        """Die Quelle gegengelesen statt abgeschrieben.

        ⚠ Ohne diese Prüfung driftet die Toleranz beim ersten Takt-Wechsel in
        `waechter.py` auseinander, und zwar still — dieselbe Sorte Drift, die dieses
        Haus bei `plan_drift` zwölfmal an einem Tag bezahlt hat.
        """
        pfad = os.path.join(_WURZEL, "waechter.py")
        if not os.path.isfile(pfad):
            self.skipTest("waechter.py liegt in der Arbeitswurzel, hier nicht vorhanden")
        with open(pfad, encoding="utf-8", errors="replace") as f:
            quelle = f.read()
        self.assertIn(f"takt_sekunden={preflight.WAECHTER_TAKT_S}", quelle,
                      "der Takt in preflight stimmt nicht mehr mit waechter.py überein")


class NichtBelegbarIstNichtLaeuft(unittest.TestCase):
    """DoD 2 des Tickets: ein Dienst ohne Beleg darf nicht als „läuft" durchgehen."""

    def test_fehlende_datei_ist_nicht_belegbar(self):
        with tempfile.TemporaryDirectory() as tmp:
            zeile = preflight.waechter_herzschlag(tmp, _JETZT)
            self.assertIn("nicht belegbar", zeile)
            self.assertNotIn("lebt", zeile)

    def test_kaputte_datei_ist_nicht_belegbar_und_nicht_still(self):
        """⚠ Der interessanteste Fall — und der, den eine schlichtere Prüfung verwechselt.

        Eine unlesbare Statusdatei sähe bei „kein Zeitstempel ⇒ tot" wie ein toter
        Wächter aus. Sie ist etwas anderes: **wir wissen es nicht.** Ein Alarm, der
        Unwissen als Befund ausgibt, wird beim dritten Mal weggeklickt.
        """
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, preflight.WAECHTER_STATUS), "w",
                      encoding="utf-8", newline="\n") as f:
                f.write("{kein json")
            zeile = preflight.waechter_herzschlag(tmp, _JETZT)
            self.assertIn("unlesbar", zeile)
            self.assertNotIn("STILL", zeile)

    def test_unlesbarer_zeitstempel_ist_nicht_still(self):
        with tempfile.TemporaryDirectory() as tmp:
            _status(tmp, "gestern abend")
            zeile = preflight.waechter_herzschlag(tmp, _JETZT)
            self.assertIn("unlesbar", zeile)
            self.assertNotIn("STILL", zeile)


class PreflightRuftDenLeser(unittest.TestCase):
    """Ohne diesen Aufruf wäre die Funktion die zweite Stelle ohne Leser."""

    def test_preflight_druckt_die_zeile(self):
        quelle = os.path.join(_PLATFORM, "scripts", "preflight.py")
        with open(quelle, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("print(waechter_herzschlag(root))", text,
                      "preflight ruft den Leser nicht auf — dann hat der Herzschlag "
                      "wieder keinen")

    def test_die_zeile_zaehlt_nicht_als_befund(self):
        """Ein toter Wächter darf den Push des Auftraggebers nicht anhalten."""
        quelle = os.path.join(_PLATFORM, "scripts", "preflight.py")
        with open(quelle, encoding="utf-8") as f:
            zeilen = f.read().split("\n")
        i = next(k for k, z in enumerate(zeilen) if "print(waechter_herzschlag(root))" in z)
        self.assertNotIn("befunde += 1", "\n".join(zeilen[i:i + 3]))


if __name__ == "__main__":
    unittest.main()
