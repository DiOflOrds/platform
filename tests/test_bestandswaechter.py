#!/usr/bin/env python3
"""SWR-222 (platform/T-0074): die Gegenprobe zum Wächter — er darf nicht stilllegen.

## Warum diese Datei existiert

`bestandswaechter.am_bestand` erlaubt einer Zusicherung, sich zu überspringen, wenn ihre
Eingabe fehlt. Das ist notwendig (die CI von `platform` sieht nur drei Repos) und
**gefährlich**: ein Skip sieht in jedem Protokoll genauso aus wie ein Erfolg.

> **Die bequeme Handlung wäre, eine unbequeme Zusicherung dauerhaft stillzulegen, indem
> man ihr eine Eingabe andichtet, die es nirgends gibt. Niemand würde es merken — außer
> jemand misst, dass am vollständigen Bestand nichts übersprungen wird.**

Genau das tut diese Datei. Sie läuft dort, wo der Bestand vollständig ist (Host, Sandbox
mit allen Repos), und ist dort **rot**, sobald eine Deklaration ins Leere zeigt.

⚠ Sie überspringt sich selbst **nicht** über `am_bestand` — das wäre die Schlange, die
sich in den Schwanz beißt. Ihr eigener Wächter fragt genau eine Sache: ist hier überhaupt
ein vollständiges Haus? Und er fragt sie an einer Datei, die in der CI von `platform`
**nicht** liegt (`pm/management/sprints.jsonl`) — nicht an `process`, das dort liegt.
"""
import importlib
import io
import os
import re
import sys
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HIER)

import bestandswaechter  # noqa: E402

HAUS = bestandswaechter.HAUS

#: Die Datei, an der dieses Haus „vollständig" erkennt. ⚠ Bewusst NICHT `process`: das
#: checkt die CI von `platform` mit aus, und genau daran ist der alte Wächter gescheitert.
VOLLSTAENDIG_WENN = "pm/management/sprints.jsonl"


def _testmodule():
    """Alle Testmodule dieses Ordners importieren — sonst ist das Register leer.

    ⚠ Ohne diesen Schritt hinge das Ergebnis an der Reihenfolge der Testausführung: ein
    Register, das erst beim Import gefüllt wird, ist beim ersten Test noch leer. Eine
    Prüfung, deren Grundmenge von der Reihenfolge abhängt, ist keine.
    """
    namen = sorted(n[:-3] for n in os.listdir(_HIER)
                   if n.startswith("test_") and n.endswith(".py"))
    for n in namen:
        try:
            importlib.import_module(n)
        except Exception:  # noqa: BLE001 — ein nicht importierbares Modul ist nicht
            continue      # die Frage DIESER Datei; die Teststrecke meldet es ohnehin.
    return namen


class DasRegisterIstNichtLeer(unittest.TestCase):
    """SWR-128-Familie: ohne Deklarationen prüft die Gegenprobe unten nichts."""

    def test_es_gibt_ueberhaupt_deklarationen(self):
        _testmodule()
        self.assertGreaterEqual(
            len(bestandswaechter.REGISTER), 15,
            "weniger als 15 Klassen mit `am_bestand` gefunden — entweder ist der "
            "Dekorator aus dem Bestand verschwunden oder der Import oben greift nicht. "
            "In beiden Fällen sagt die Gegenprobe darunter nichts.")

    def test_jede_deklaration_nennt_mindestens_eine_eingabe(self):
        _testmodule()
        leer = [k for k, v in bestandswaechter.REGISTER.items() if not v]
        self.assertEqual(leer, [], "Deklaration ohne Eingabe: %s" % leer)


class AmVollenBestandUeberspringtNichts(unittest.TestCase):
    """⚠⚠ Der Kern: hier, wo alles da ist, darf keine einzige Eingabe fehlen."""

    def setUp(self):
        if bestandswaechter.fehlende(VOLLSTAENDIG_WENN):
            self.skipTest(
                "kein vollständiges Haus (%s fehlt) — diese Gegenprobe gehört an den "
                "Ort mit allen Repos; in der CI von `platform` kann sie nichts messen."
                % VOLLSTAENDIG_WENN)

    def test_keine_deklarierte_eingabe_fehlt(self):
        _testmodule()
        fehlt = {}
        for schluessel, eingaben in sorted(bestandswaechter.REGISTER.items()):
            weg = bestandswaechter.fehlende(*eingaben)
            if weg:
                fehlt[schluessel] = weg
        self.assertEqual(
            fehlt, {},
            "Diese Zusicherungen überspringen sich AUCH am vollständigen Bestand — "
            "sie sind damit stillgelegt und nicht gewartet: %s" % fehlt)

    def test_die_zusicherungen_laufen_hier_wirklich(self):
        """Die zweite Hälfte: „Eingabe da" ist nicht dasselbe wie „Test lief".

        ⚠ Gegenprobe gegen einen Dekorator, der IMMER überspringt — der bestünde den
        Test darüber, weil dort nur Pfade geprüft werden.
        """
        _testmodule()
        klasse = None
        for name in ("test_anzeigename_einheit", "test_deep_links"):
            modul = sys.modules.get(name)
            if modul is None:
                continue
            for obj in vars(modul).values():
                if getattr(obj, "_am_bestand", False):
                    klasse = obj
                    break
            if klasse:
                break
        self.assertIsNotNone(klasse, "keine dekorierte Klasse gefunden")
        erg = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(klasse))
        self.assertEqual(
            erg.skipped, [],
            "am vollständigen Bestand wurde übersprungen: %s" % (erg.skipped,))
        self.assertGreater(erg.testsRun, 0, "keine Zusicherung ausgeführt")


class DerWaechterFragtNichtDieFalscheDatei(unittest.TestCase):
    """⚠⚠ Der Rückfall-Test gegen genau den Fehler, der 31 Zusicherungen rot machte.

    `process` liegt in der CI von `platform`. Ein Wächter, der IHN fragt, hält dort
    stand und lässt durch, was er sperren sollte. Diese Zusicherung ist rot, sobald
    jemand die alte Bauform zurückbringt.
    """

    MUSTER = re.compile(r'isdir\(os\.path\.join\(\s*(?:HAUS|_?WURZEL)\s*,\s*"process"\s*\)\)')

    def test_keine_zusicherung_haengt_ihren_skip_an_process(self):
        treffer = []
        for name in sorted(os.listdir(_HIER)):
            if not (name.startswith("test_") and name.endswith(".py")):
                continue
            with io.open(os.path.join(_HIER, name), encoding="utf-8") as f:
                zeilen = f.read().splitlines()
            for i, z in enumerate(zeilen):
                if not self.MUSTER.search(z):
                    continue
                fenster = "\n".join(zeilen[i:i + 3])
                if "skipTest" in fenster or "skipUnless" in fenster:
                    treffer.append("%s:%d" % (name, i + 1))
        self.assertEqual(
            treffer, [],
            "Ein Skip hängt an `process` — das checkt die CI von `platform` MIT aus, "
            "der Wächter hält dort also stand und misst nichts. Die Eingabe der "
            "Zusicherung benennen (bestandswaechter.am_bestand, SWR-221): %s" % treffer)

    def test_das_muster_findet_die_alte_bauform_wirklich(self):
        """SWR-128: eine Suche, die nichts findet, weil sie nichts sucht, sieht aus wie

        eine, die nichts zu finden hatte. Hier die Probe an der Bauform selbst.
        """
        alt = '        if not os.path.isdir(os.path.join(HAUS, "process")):'
        self.assertTrue(self.MUSTER.search(alt),
                        "das Muster erkennt die alte Bauform nicht mehr")


class DerDekoratorVerweigertDenFreibrief(unittest.TestCase):
    """Ohne benannte Eingabe ist `am_bestand` ein Fehler — kein stiller Freibrief."""

    def test_ohne_eingabe_ein_fehler(self):
        with self.assertRaises(ValueError):
            bestandswaechter.am_bestand()

    def test_fehlende_nennt_die_fehlende_eingabe_beim_namen(self):
        weg = bestandswaechter.fehlende("gibt/es/nicht", "auch/nicht", haus=HAUS)
        self.assertEqual(weg, ["gibt/es/nicht", "auch/nicht"])

    def test_vorhandene_eingabe_fehlt_nicht(self):
        self.assertEqual(bestandswaechter.fehlende("scripts", haus=os.path.dirname(_HIER)),
                         [])


if __name__ == "__main__":
    unittest.main()
