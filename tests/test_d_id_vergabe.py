"""Die D-Nummernvergabe ist ORGANISATIONSWEIT (SWR-203, platform/T-0059).

⚠⚠ **Diese Datei ist der Riegel, den `SWR-197` nicht hatte.**

`SWR-197` hat in Sprint 30 gemessen, dass alle mehrdeutigen Entscheidungs-Zitate aus
`D000`–`D013` stammen, und eine Sperrklinke gebaut, die das Wachsen der Menge **meldet**.
Ihre eigene Begründung sagte, sie sei *„an der Vergabe"* gebaut. Am 2026-08-21 hat der
Auftraggeber drei Anfragen beantwortet — und die Vergabe erzeugte **`D014`, `D015`,
`D016`**, die es in `p0` längst gab.

> **Eine Prüfung, die neben der Vergabe steht und sie nicht anfasst, ist kein Riegel,
> sondern ein Zeuge. Sie hat den Schaden korrekt gemeldet und nicht verhindert — und
> zwar beim allerersten Gebrauch.**

⚠ Die drei Zeilen sind append-only Historie und bleiben. Was hier gesichert wird, ist,
dass es **kein viertes Mal** gibt.

Vertreter von `L-2026-08-21cu`.
"""
import os
import shutil
import sys
import tempfile
import unittest

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, "scripts"))
sys.path.insert(0, WURZEL)
from backend import inbox  # noqa: E402
from backend import entscheidungs_ids as eids  # noqa: E402

KOPF = ("# Decision Log\n\n"
        "| ID | Datum | Entscheider | Entscheidung | Optionen | Begründung | Artefakte |\n"
        "|---|---|---|---|---|---|---|\n")


def _log(pfad, ids):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(KOPF + "".join("| %s | d | e | x | o | b | a |\n" % i for i in ids))


class VergabeIstOrganisationsweit(unittest.TestCase):

    def setUp(self):
        self.wurzel = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.wurzel, ignore_errors=True)

    def _pfad(self, einheit):
        return os.path.join(self.wurzel, einheit, "management", "decisions",
                            "decision-log.md")

    def test_die_nummer_weicht_einer_fremden_einheit_aus(self):
        """⚠⚠ Der gemessene Fall vom 2026-08-21, als Zusicherung.

        `pm` steht bei `D013`, `p0` hat bereits bis `D016`. Die alte Fassung las nur
        `pm` und vergab `D014` — eine ID, die es zweimal gibt. Die neue muss `D017`
        vergeben.
        """
        _log(self._pfad("pm"), ["D012", "D013"])
        _log(self._pfad("p0"), ["D014", "D015", "D016"])
        self.assertEqual(inbox._naechste_d_id(self._pfad("pm"), self.wurzel), "D017")

    def test_auch_verschachtelte_einheiten_zaehlen_mit(self):
        """`projects/<p>/…` ist eine Einheit wie jede andere.

        ⚠ Genau diese zweite Ebene hat in diesem Lauf schon zweimal gefehlt (Briefkasten
        und Ticketsichtung, `L-2026-08-21cs`). Eine Discovery, die sie vergisst, vergibt
        eine ID, die in `projects/p11` längst steht.
        """
        _log(self._pfad("pm"), ["D001"])
        _log(os.path.join(self.wurzel, "projects", "p11", "management", "decisions",
                          "decision-log.md"), ["D040"])
        self.assertEqual(inbox._naechste_d_id(self._pfad("pm"), self.wurzel), "D041")

    def test_ohne_wurzel_bleibt_das_einzelne_log_die_quelle(self):
        """⚠ „Unbekannt" und „unerreichbar" sind zwei Antworten (Auflage aus SWR-193).

        Ein einzeln ausgechecktes Repo ohne Organisationskontext muss weiterhin
        entscheiden können. Der Rückfall auf das eine Log ist deshalb **bewusst** kein
        Fehler — er ist das alte Verhalten an der Stelle, an der es richtig bleibt.
        """
        _log(self._pfad("pm"), ["D003"])
        leer = os.path.join(self.wurzel, "gibtesnicht")
        self.assertEqual(inbox._naechste_d_id(self._pfad("pm"), leer), "D004")

    def test_leeres_log_beginnt_bei_null(self):
        """Grundmenge nicht leer (SWR-128-Familie): ohne Bestand ist D000 richtig."""
        pfad = self._pfad("pm")
        _log(pfad, [])
        self.assertEqual(inbox._naechste_d_id(pfad, self.wurzel), "D000")


class DerRiegelBleibtEinRiegel(unittest.TestCase):
    """⚠⚠ Das Gegenstück — ohne diesen Block wäre ein Rückbau grün."""

    def test_die_vergabe_liest_mehr_als_ein_log(self):
        """Eine Fassung, die wieder nur `log_pfad` liest, bestünde die Blöcke oben nicht —
        aber sie bestünde sie **auch dann nicht**, wenn jemand sie löscht. Diese
        Zusicherung liest den Quelltext und wird rot, wenn die Mehrfach-Discovery
        verschwindet: die Bauform aus `SWR-148` (was weg sein muss UND was dableiben muss).
        """
        with open(os.path.join(WURZEL, "backend", "inbox.py"), encoding="utf-8") as f:
            quelle = f.read()
        rumpf = quelle[quelle.index("def _naechste_d_id"):]
        rumpf = rumpf[:rumpf.index("\n#:")]
        self.assertIn("glob.glob", rumpf,
                      "die Vergabe sucht keine fremden Logs mehr — SWR-203 zurückgebaut")
        self.assertIn("management", rumpf)

    def test_der_altbestand_ist_benannt_und_nicht_gezaehlt(self):
        """⚠ Die Menge wuchs am 2026-08-21 von 14 auf 17, und das darf man SEHEN.

        Als Menge geführt und nicht als Zahl (`L-2026-08-20by`): eine Zahl sagt nicht,
        welche ID verschwunden ist. Verschwindet eine, ist Historie umgeschrieben worden.
        """
        for n in (0, 13, 14, 16):
            self.assertIn("D%03d" % n, eids.ALTBESTAND_MEHRDEUTIG)
        self.assertNotIn("D017", eids.ALTBESTAND_MEHRDEUTIG,
                         "D017 ist nie doppelt vergeben worden — der Altbestand darf "
                         "nicht auf Vorrat wachsen")


if __name__ == "__main__":
    unittest.main()
