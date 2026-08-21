"""Die Vertragsversion steht an EINER Stelle — und wer sie zitiert, zitiert sie richtig.

⚠⚠ **Nachtrag aus dem unabhängigen Gegenlesen von Sprint 34** (`SWR-210`).
Vertreter von `L-2026-08-21dg`.

`widget-vertrag-v2.yaml` trägt seit Sprint 34 `version: 2.8`. Zwei Dateien meldeten
weiterhin *„v2.7 in Betrieb"*: `team-dashboard/docs/cm-plan.md` und
`team-dashboard/roles/dash-red.md`.

⚠ Es ist **kein Altbestand, sondern ein Rückfall**: beide wurden beim Sprung auf v2.7
mitgezogen (`ffe3f18`) und beim Sprung auf v2.8 (`52c0dc4`) vergessen.

> **Eine Zahl, die an drei Stellen steht und an einer gepflegt wird, ist keine Angabe,
> sondern eine Verabredung — und Verabredungen halten in diesem Haus keine drei Sprints
> (`SWR-125`).**

Die Zahl wird hier **nicht** aus den Zitaten entfernt: sie steht in Prosa, die ein Mensch
liest, und ein Verweis „siehe Vertragsdatei" wäre für ihn schlechter. Gesichert wird
stattdessen, dass jedes Zitat mit der **einen Quelle** übereinstimmt.
"""
import os
import re
import sys
import unittest

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAUS = os.path.dirname(WURZEL)
VERTRAG = os.path.join(HAUS, "team-dashboard", "vertrag", "widget-vertrag-v2.yaml")
#: Dateien, die die Version in Prosa zitieren. ⚠ Über ein Muster **gefunden** und nicht
#: aufgezählt: eine feste Liste wäre an dem Tag falsch, an dem eine dritte Datei zitiert
#: (dieselbe Stelle, die `SWR-128` dreimal gekostet hat).
ZITAT = re.compile(r"[Vv]ertrag\s+v(\d+\.\d+)\s+in Betrieb|pruefstatus:\s*v(\d+\.\d+)\s+in Betrieb")


def _version():
    with open(VERTRAG, encoding="utf-8") as f:
        m = re.search(r"(?m)^version:\s*([\d.]+)\s*$", f.read())
    return m.group(1) if m else None


def _zitate():
    """[(datei, zitierte Version)] über `team-dashboard/` — gefunden, nicht aufgezählt."""
    raus = []
    basis = os.path.join(HAUS, "team-dashboard")
    for wurzel, verz, dateien in os.walk(basis):
        verz[:] = [d for d in verz if d not in (".git", "vertrag")]
        for name in dateien:
            if not name.endswith(".md"):
                continue
            pfad = os.path.join(wurzel, name)
            with open(pfad, encoding="utf-8", errors="replace") as f:
                for treffer in ZITAT.finditer(f.read()):
                    raus.append((os.path.relpath(pfad, HAUS),
                                 treffer.group(1) or treffer.group(2)))
    return raus


class EineZahlEineQuelle(unittest.TestCase):

    def setUp(self):
        if not os.path.isfile(VERTRAG):
            self.skipTest("kein Organisationskontext")

    def test_die_quelle_traegt_eine_version(self):
        self.assertIsNotNone(_version(), "die Vertragsdatei nennt keine Version")

    def test_es_gibt_ueberhaupt_zitate(self):
        """SWR-128: ohne Zitate prüft der Block darunter nichts."""
        self.assertTrue(_zitate(),
                        "keine Fundstelle — dann ist diese Prüfung vakuum-grün, und "
                        "genau so ist der Befund entstanden")

    def test_jedes_zitat_stimmt_mit_der_quelle(self):
        """⚠⚠ Der Befund: zwei Zitate standen drei Sprints hinterher."""
        soll = _version()
        falsch = [f"{d}: v{v} statt v{soll}" for d, v in _zitate() if v != soll]
        self.assertEqual([], falsch, (
            "Vertragsversion zitiert und nicht nachgezogen: " + "; ".join(falsch)
            + ". ⚠ Die Quelle ist widget-vertrag-v2.yaml — sie wird nicht an das Zitat "
            "angepasst, sondern das Zitat an sie."))


if __name__ == "__main__":
    unittest.main()
