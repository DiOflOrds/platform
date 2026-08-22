#!/usr/bin/env python3
"""SWR-221/SWR-222 (platform/T-0074): der Wächter einer Zusicherung fragt ihre EIGENE

Eingabe — namentlich, nicht stellvertretend.

## Der Befund, aus dem diese Datei entstanden ist

Die CI von `platform` checkt `platform`, `process` und `produkt-datakonv` aus — sonst
nichts. Zahlreiche Zusicherungen dieses Hauses messen aber ausdrücklich **am echten
Bestand** (`EchterBestandTest`, `AmEchtenBestandGemessen`, `BestandTest`, …): sie lesen
Briefkästen, Entscheidungslogs, Tickets und Steckbriefe von `pm`, `p0`–`p9`, `team-*` und
`projects`. In der CI ist davon nichts da.

**Gemessen (Sprint 39, nachgestellter CI-Checkout mit genau den drei Repos):** 1616 Tests,
**31 rot** (26 `FAIL`, 5 `ERROR`) — alle 31 aus dieser Familie.

⚠ **Drei der betroffenen Dateien hatten bereits einen Wächter, und er hat nicht gehalten:**

    if not os.path.isdir(os.path.join(HAUS, "process")):
        self.skipTest("kein Organisationskontext (einzeln ausgechecktes Repo)")

`process` **ist** in der CI ausgecheckt. Der Wächter meldet also „Bestand da", während die
Eingabe, die die Zusicherung wirklich liest, fehlt.

> **Ein Wächter, der die Anwesenheit der falschen Datei prüft, misst nicht, ob er arbeiten
> kann.**

Das ist derselbe Fehler, den Sprint 38 an `test_sprintuebergabe` und
`test_motor_abweichung` **vor** dem Push selbst gefunden und korrigiert hat — hier steht
er 18 Mal im Bestand.

## Was diese Datei tut, und was sie ausdrücklich NICHT tut

Sie **überspringt nicht pauschal**. Ein pauschales `skipUnless` wäre die bequeme Handlung
und die schlechteste: dann prüft die CI nichts mehr und meldet grün — genau die Falle aus
`SWR-114`/`SWR-122` (eine Prüfung, die nicht lief, ist von einer grünen nicht zu
unterscheiden, sobald beide dasselbe melden).

Stattdessen **benennt jede Klasse ihre tatsächliche Eingabe** am Aufrufort:

    @bestandswaechter.am_bestand("pm/management/briefkasten", "p0/management/briefkasten")
    class BestandTest(unittest.TestCase):
        ...

Der Wächter überspringt **genau dann**, wenn eine dieser Angaben fehlt, und **nennt sie**
in der Begründung. Fehlt nichts, läuft die Zusicherung — auf dem Host also unverändert.

⚠⚠ **Die Gegenprobe gehört dazu und steht in `test_bestandswaechter.py` (SWR-222):** am
vollständigen Bestand darf **keine** deklarierte Eingabe fehlen. Ohne sie wäre der Weg
offen, eine unbequeme Zusicherung dauerhaft stillzulegen, indem man ihr eine Eingabe
andichtet, die es nirgends gibt — und niemand würde es merken, weil ein Skip so aussieht
wie ein Erfolg.
"""
import os
import unittest

#: Die Organisationswurzel — der Ordner ÜBER `platform`.
HAUS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: Alle Deklarationen dieses Laufs: ``{"modul.Klasse": (eingabe, ...)}``.
#: Wird beim Import der Testmodule durch den Dekorator gefüllt und von `SWR-222` gelesen.
REGISTER = {}


def fehlende(*eingaben, haus=None):
    """Welche der genannten Eingaben fehlt unter `haus`? — Liste, in Deklarationsreihenfolge.

    Eine Eingabe ist ein Pfad **relativ zur Organisationswurzel**, mit `/` geschrieben.
    Datei oder Verzeichnis, beides zählt: gefragt ist, ob die Zusicherung etwas zu lesen
    hat, nicht was für ein Ding es ist.
    """
    wurzel = haus or HAUS
    fehlt = []
    for e in eingaben:
        if not os.path.exists(os.path.join(wurzel, *e.split("/"))):
            fehlt.append(e)
    return fehlt


def am_bestand(*eingaben):
    """Klassendekorator: diese Zusicherungen lesen den echten Bestand — hier ist welchen.

    ⚠ Ohne Angabe ist der Dekorator ein Fehler und kein stiller Freibrief: eine Klasse
    ohne benannte Eingabe könnte nie überspringen, und ein Dekorator, der nichts tut,
    behauptet trotzdem etwas.
    """
    if not eingaben:
        raise ValueError(
            "am_bestand ohne Eingabe: eine Zusicherung, die den echten Bestand liest, "
            "muss sagen WELCHEN — sonst ist der Wächter eine Behauptung ohne Messung.")

    def dekorator(klasse):
        schluessel = "%s.%s" % (klasse.__module__.rsplit(".", 1)[-1], klasse.__name__)
        REGISTER[schluessel] = tuple(eingaben)
        vorher = klasse.setUp if hasattr(klasse, "setUp") else None

        def setUp(self):
            fehlt = fehlende(*eingaben)
            if fehlt:
                raise unittest.SkipTest(
                    "Eingabe fehlt: %s — diese Zusicherung misst den echten Bestand der "
                    "Organisation und hat hier nichts zu lesen (SWR-221). Sie ist NICHT "
                    "abgeschaltet: am vollständigen Bestand läuft sie, und SWR-222 misst, "
                    "dass sie das kann." % ", ".join(fehlt))
            if vorher is not None:
                vorher(self)

        setUp.__doc__ = ("SWR-221: überspringt genau dann, wenn eine der benannten "
                         "Eingaben fehlt — %s." % ", ".join(eingaben))
        klasse.setUp = setUp
        klasse._bestandseingaben = tuple(eingaben)
        return dekorator_marker(klasse)

    return dekorator


def dekorator_marker(klasse):
    """Sichtbare Marke am Testfall — damit ein Leser die Bauform am Objekt erkennt."""
    klasse._am_bestand = True
    return klasse
