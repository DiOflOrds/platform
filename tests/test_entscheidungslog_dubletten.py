"""Keine NEUE Dublette im Entscheidungslog (SWR-195, platform/T-0036).

⚠⚠ **Der Befund, gegen den diese Datei steht, ist der schwerere der beiden aus
`platform/T-0036`.** `pm` trägt `D005` **dreimal** und `D006` **zweimal** in EINER Datei.

> **`_naechste_d_id` bildet `max + 1` und kann eine Dublette gar nicht erzeugen. Diese
> fünf Zeilen sind von Hand geschrieben — es gibt also einen ZWEITEN SCHREIBWEG ins
> Entscheidungslog, und der hat keine Nummernvergabe.** Das ist B033 mit einem
> *Schreibweg* als vergessener Kopie.

⚠ Der Altbestand wird **nicht repariert** (append-only, Kap. 16) und **nicht rot**: er
ist benannt. Rot wird diese Prüfung bei einer **neuen** Dublette — und dann nennt sie
Einheit und ID.

Ausführung: python -m unittest discover platform/tests
"""
import os
import sys
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
from backend import inbox  # noqa: E402

_WURZEL = os.path.dirname(os.path.dirname(_HIER))


class DublettenTest(unittest.TestCase):
    """Verifiziert: SWR-195."""

    def test_grundmenge_ist_nicht_leer(self):
        """⚠ SWR-128-Familie: ohne Logs misst die Prüfung darunter nichts.

        Gezählt werden die **gefundenen Logs**, nicht die Dubletten — sonst wäre ein
        sauberer Bestand von einer kaputten Entdeckung nicht zu unterscheiden.
        """
        sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
        import board
        logs = [n for n, p in board.projekt_pfade(_WURZEL)
                if os.path.isfile(os.path.join(p, "management", "decisions",
                                               "decision-log.md"))]
        self.assertGreaterEqual(len(logs), 2,
                                f"nur {len(logs)} Entscheidungslog(s) gefunden — die "
                                f"Entdeckung ist vermutlich kaputt")

    def test_keine_NEUE_dublette(self):
        """⚠⚠ Die eigentliche Prüfung: sie nennt Einheit UND ID, nicht nur eine Zahl."""
        ist = inbox.log_dubletten(_WURZEL)
        neu = {}
        for einheit, ids in ist.items():
            bekannt = inbox.DUBLETTEN_ALTBESTAND.get(einheit, {})
            uebrig = {k: v for k, v in ids.items() if bekannt.get(k) != v}
            if uebrig:
                neu[einheit] = uebrig
        self.assertEqual(neu, {}, (
            f"Neue Mehrfachvergabe im Entscheidungslog: {neu}. `_naechste_d_id` bildet "
            f"max+1 und kann das nicht erzeugen — es hat also jemand von Hand "
            f"geschrieben, ohne eine Nummer zu ziehen. Die Zeile gehört korrigiert, "
            f"BEVOR sie committet ist; danach ist sie Historie und nicht mehr reparierbar."))

    def test_der_benannte_altbestand_ist_noch_da(self):
        """⚠ Verschwindet er, ist Historie umgeschrieben worden — das ist ein Befund.

        Append-only heißt, dass eine Zeile nicht still verschwindet. Ein leiser Fix
        dieser fünf Zeilen wäre bequem und würde Kap. 16 brechen.
        """
        ist = inbox.log_dubletten(_WURZEL)
        for einheit, ids in inbox.DUBLETTEN_ALTBESTAND.items():
            self.assertEqual(ist.get(einheit), ids, (
                f"Der benannte Altbestand in {einheit} stimmt nicht mehr: erwartet "
                f"{ids}, gefunden {ist.get(einheit)}. Entweder ist Historie "
                f"umgeschrieben worden, oder die Liste gehört gebucht."))

    def test_das_muster_liest_D_UND_B_zeilen(self):
        """⚠ Beide stehen in derselben Tabelle; nur `D` zu lesen prüfte die halbe Datei."""
        self.assertTrue(inbox.LOG_ID_ZEILE.match("| D000 | 2026-08-15 |"))
        self.assertTrue(inbox.LOG_ID_ZEILE.match("| B012 | 2026-08-16 |"))
        self.assertIsNone(inbox.LOG_ID_ZEILE.match("| X000 | 2026-08-15 |"))
        self.assertIsNone(inbox.LOG_ID_ZEILE.match("D000 | ohne Tabellenrand"))

    def test_gegenprobe_eine_kuenstliche_dublette_wird_gefunden(self):
        """⚠⚠ Ohne sie wäre ein kaputter Leser grün — er fände nie etwas."""
        import shutil
        import tempfile
        wurzel = tempfile.mkdtemp(prefix="swr195-")
        try:
            for name, zeilen in (("eins", ["| D000 | a |", "| D000 | b |"]),
                                 ("zwei", ["| D000 | a |", "| D001 | b |"])):
                d = os.path.join(wurzel, name, "management", "decisions")
                os.makedirs(d)
                os.makedirs(os.path.join(wurzel, name, "tickets"))
                with open(os.path.join(d, "decision-log.md"), "w",
                          encoding="utf-8", newline="\n") as f:
                    f.write("| ID | Datum |\n|---|---|\n" + "\n".join(zeilen) + "\n")
            self.assertEqual(inbox.log_dubletten(wurzel), {"eins": {"D000": 2}})
        finally:
            shutil.rmtree(wurzel, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
