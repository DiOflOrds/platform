"""Eine Organisationswurzel kommt vom AUFRUFER (SWR-207, platform/T-0062).

⚠⚠ **Der Anlass sind sieben rote Zusicherungen, die zwei Sprints lang niemand gesehen
hat.** `tests/test_backend` baut ein leeres Repo im Temp-Ordner und erwartet die erste
Entscheidung als `D001`. Sie bekam `D030` — die nächste freie Nummer des **echten**
Hauses.

Die Ursache stand in einer Zeile von `inbox._naechste_d_id`:

```python
wurzel = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
```

> **⚠⚠ Eine Funktion, die „die ganze Organisation" liest, bestimmt damit selbst, welche
> Organisation gemeint ist — und die Antwort lautet immer: die, in der der Quelltext
> zufällig liegt. Ein Vorgabewert aus dem eigenen Standort ist kein Vorgabewert, sondern
> eine stille Annahme über die Welt.**

⚠ Der teuerste Teil ist nicht die falsche Zahl, sondern der **tote Rückfall**: `SWR-203`
hat ausdrücklich vorgesehen, dass eine unbekannte Wurzel auf das einzelne Log
zurückfällt (Auflage aus `SWR-193`, „unbekannt" und „unerreichbar" sind zwei Antworten).
Dieser Zweig **konnte nie erreicht werden** — die Wurzel war nie unbekannt, sie wurde
erfunden. Ein Test dafür stand nicht daneben, und deshalb ist er hier der zweite Block.

Vertreter von `L-2026-08-21db`.
"""
import ast
import os
import shutil
import sys
import tempfile
import unittest

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, "scripts"))
sys.path.insert(0, WURZEL)
from backend import inbox  # noqa: E402

KOPF = ("# Decision Log\n\n"
        "| ID | Datum | Entscheider | Entscheidung | Optionen | Begründung | Artefakte |\n"
        "|---|---|---|---|---|---|---|\n")


def _log(pfad, ids):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(KOPF + "".join("| %s | d | e | x | o | b | a |\n" % i for i in ids))


def _einheit(basis, name, mit_tickets=True):
    """Eine Einheit im Sinne der Discovery: ein Ordner mit `tickets/`."""
    pfad = os.path.join(basis, name)
    if mit_tickets:
        os.makedirs(os.path.join(pfad, "tickets"), exist_ok=True)
    return pfad


# SWR-221 (platform/T-0074): der Wächter dieser Zusicherungen fragt ihre EIGENE Eingabe.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bestandswaechter  # noqa: E402


@bestandswaechter.am_bestand("pm/management/decisions/decision-log.md")
class DieVorrichtungBleibtInIhremEigenenHaus(unittest.TestCase):
    """⚠⚠ Der gemessene Fall: `D030` statt `D001`, sieben Mal."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.haus = os.path.join(self.tmp, "haus")
        for name in ("pm", "p0"):
            _einheit(self.haus, name)

    def _pfad(self, einheit):
        return os.path.join(self.haus, einheit, "management", "decisions",
                            "decision-log.md")

    def test_ein_leeres_haus_beginnt_bei_null_und_nicht_beim_echten_bestand(self):
        """Ohne `wurzel`-Angabe zählt das Haus des Aufrufers — nicht das des Quelltextes.

        ⚠ Genau diese Zusicherung war es, die vorher `D030` sah. Ihre Erwartung ist
        **nicht** angepasst worden (`SWR-166`: das wäre die bequeme Handlung gewesen).
        """
        _log(self._pfad("pm"), [])
        self.assertEqual(inbox._naechste_d_id(self._pfad("pm")), "D000")

    def test_die_nachbareinheit_desselben_hauses_zaehlt_mit(self):
        """Die organisationsweite Vergabe aus `SWR-203` bleibt — nur ihr Bezug ist richtig."""
        _log(self._pfad("pm"), ["D000"])
        _log(self._pfad("p0"), ["D007"])
        self.assertEqual(inbox._naechste_d_id(self._pfad("pm")), "D008")

    def test_das_echte_haus_wird_nicht_gelesen(self):
        """⚠⚠ Die Gegenprobe zur Zahl: das echte Haus steht weit über `D008`.

        Eine Vorrichtung, die eine Entscheidung schreibt, hätte damit einen Fuß im echten
        Bestand — heute nur lesend, aber das ist eine Eigenschaft des Aufrufs und keine
        Zusicherung.
        """
        _log(self._pfad("pm"), ["D000"])
        echt = inbox._naechste_d_id(
            os.path.join(os.path.dirname(WURZEL), "pm", "management", "decisions",
                         "decision-log.md"))
        self.assertGreater(int(echt[1:]), 8,
                           "Grundmenge leer: das echte Haus steht nicht über D008, "
                           "die Gegenprobe sagt damit nichts (SWR-128-Familie)")
        self.assertEqual(inbox._naechste_d_id(self._pfad("pm")), "D001")


class DerRueckfallAusSWR193IstErreichbar(unittest.TestCase):
    """⚠⚠ Der Zweig, den `SWR-203` vorgesehen und `__file__` tot gemacht hat."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_ein_einzeln_ausgechecktes_repo_hat_keine_wurzel(self):
        """Eine Einheit ohne Nachbarn ist kein Haus — die Antwort ist `None`, nicht `""`."""
        einsam = _einheit(os.path.join(self.tmp, "allein"), "repo")
        log = os.path.join(einsam, "management", "decisions", "decision-log.md")
        _log(log, ["D003"])
        self.assertIsNone(inbox._wurzel_vom_aufrufer(log),
                          "die Wurzel eines einzeln ausgecheckten Repos ist unerreichbar "
                          "und darf nicht erfunden werden")

    def test_ohne_wurzel_bleibt_das_einzelne_log_die_quelle(self):
        """Und dann entscheidet das Repo weiter — aus seinem eigenen Log.

        ⚠ Das ist das alte Verhalten an der Stelle, an der es richtig bleibt. Vor
        `SWR-207` war dieser Pfad **unerreichbar**: `os.path.isdir(wurzel)` war immer
        wahr, weil `wurzel` aus dem Dateipfad dieses Moduls kam.
        """
        einsam = _einheit(os.path.join(self.tmp, "allein"), "repo")
        log = os.path.join(einsam, "management", "decisions", "decision-log.md")
        _log(log, ["D003"])
        self.assertEqual(inbox._naechste_d_id(log), "D004")


#: ⚠⚠ **Namentlich ausgenommen, mit Grund — und mit Verfallsprüfung** (die Lehre aus
#: `SWR-204`: eine Ausnahmeliste ohne Verfallsprüfung ist ein Dauerbefund mit umgekehrtem
#: Vorzeichen). Beide Funktionen sind **Diagnose-Leser über das echte Haus** und werden
#: ausschließlich aus Zusicherungen aufgerufen; für sie ist „das Haus, in dem der
#: Quelltext liegt" die gemeinte Antwort. ⚠ Ausgenommen ist die **einzelne Funktion** und
#: nicht die Datei — die Lehre aus `SWR-205`, wo eine pauschale Dateiausnahme den fünften
#: Namen strukturell unsichtbar gemacht hat.
DIAGNOSE_LESER = {
    ("entscheidungs_ids.py", "_wurzel"):
        "misst die Mehrdeutigkeit der D-IDs im echten Bestand (SWR-197)",
    ("lehren.py", "_wurzel"):
        "misst die Lehren-Vertreter im echten Bestand (platform/T-0034/T-0061)",
}
#: Namen, die eine ORGANISATIONSwurzel bezeichnen. `sys.path`-Auflösungen sind bewusst
#: nicht dabei: ein Schwestermodul liegt zu Recht relativ zum eigenen Quelltext.
WURZEL_NAMEN = ("wurzel", "_wurzel", "org_wurzel", "_org_wurzel")


def _wurzel_aus_dateipfad(quelle, datei):
    """[(datei, funktion)] — jede Stelle, die eine ORGANISATIONSwurzel aus `__file__` bildet.

    Getroffen wird eine Zuweisung, die (a) auf einen Wurzel-Namen zielt **oder** (b) in
    einer Funktion mit Wurzel-Namen steht, und deren Wert `__file__` enthält.
    """
    baum = ast.parse(quelle)
    treffer = []

    def enthaelt_file(knoten):
        return any(isinstance(k, ast.Name) and k.id == "__file__"
                   for k in ast.walk(knoten))

    def geh(knoten, funktion):
        for kind in ast.iter_child_nodes(knoten):
            if isinstance(kind, (ast.FunctionDef, ast.AsyncFunctionDef)):
                geh(kind, kind.name)
                continue
            if isinstance(kind, ast.Assign) and enthaelt_file(kind.value):
                ziele = [t.id for t in kind.targets if isinstance(t, ast.Name)]
                if (any(z.lower() in WURZEL_NAMEN for z in ziele)
                        or (funktion or "").lower() in WURZEL_NAMEN):
                    treffer.append((datei, funktion or "<modul>"))
                    continue
            geh(kind, funktion)

    geh(baum, None)
    return treffer


class KeineOrganisationswurzelAusDemDateipfad(unittest.TestCase):
    """⚠⚠ Der Riegel — sonst käme dieselbe Zeile an der nächsten Stelle wieder."""

    def _alle_treffer(self):
        gefunden = []
        for ordner in ("backend", "scripts"):
            basis = os.path.join(WURZEL, ordner)
            for name in sorted(os.listdir(basis)):
                if not name.endswith(".py"):
                    continue
                with open(os.path.join(basis, name), encoding="utf-8") as f:
                    gefunden.extend(_wurzel_aus_dateipfad(f.read(), name))
        return gefunden

    def test_nur_die_beiden_diagnose_leser_duerfen_es(self):
        """Gemessen am 2026-08-21 (DoD 1 von `platform/T-0062`): **drei** Stellen, nicht eine.

        Das Ticket nannte `inbox._naechste_d_id`. Gezählt über `backend/` und `scripts/`
        sind es drei — dieselbe Familie wie `SWR-205` (vier Namen statt drei) und
        `SWR-204` (acht Verweise statt drei): **die Zählung stellt die Frage des Tickets
        um.** Zwei der drei sind Diagnose-Leser und bleiben; die dritte war der Schaden.
        """
        unerlaubt = [t for t in self._alle_treffer() if t not in DIAGNOSE_LESER]
        self.assertEqual([], unerlaubt,
                         "Organisationswurzel aus dem eigenen Dateipfad (SWR-207): "
                         + ", ".join("%s:%s" % t for t in unerlaubt))

    def test_jede_ausnahme_beisst_noch(self):
        """⚠ Verfallsprüfung: eine Ausnahme, deren Fundstelle verschwunden ist, ist Altpapier.

        Ohne diesen Block bliebe die Liste stehen, nachdem ihr Grund entfallen ist — die
        Lage, die `SWR-204` vier Stunden nach ihrer Entstehung eingeholt hat.
        """
        gefunden = set(self._alle_treffer())
        for eintrag in DIAGNOSE_LESER:
            self.assertIn(eintrag, gefunden,
                          "Ausnahme ohne Fundstelle: %s:%s — Grund entfallen, Eintrag "
                          "gehört gelöscht" % eintrag)

    def test_die_pruefung_wuerde_den_rueckbau_finden(self):
        """⚠⚠ Gegenprobe an einer **synthetischen** Quelle statt an der Live-Datei.

        `L-2026-08-20cm`: eine Mutation an einer Datei, die eine fremde Automatik alle 15
        Minuten anfasst, misst den Zustand von vorhin. Hier wird die exakte Zeile geprüft,
        die `SWR-207` entfernt hat.
        """
        rueckbau = ("import os\n"
                    "def f(log_pfad, wurzel=None):\n"
                    "    if wurzel is None:\n"
                    "        wurzel = os.path.abspath(os.path.join(\n"
                    "            os.path.dirname(__file__), '..', '..'))\n"
                    "    return wurzel\n")
        self.assertEqual([("synthetisch.py", "f")],
                         _wurzel_aus_dateipfad(rueckbau, "synthetisch.py"))

    def test_eine_sys_path_aufloesung_ist_kein_befund(self):
        """Die Gegenrichtung: ein Schwestermodul liegt zu Recht relativ zum Quelltext.

        Ohne diese Zusicherung wäre die Prüfung entweder blind oder unbrauchbar laut —
        `platform/` trägt **64** `__file__`-Stellen, und die große Mehrheit davon löst
        Code-Pfade auf und keine Organisationswurzel.
        """
        pfadcode = ("import os, sys\n"
                    "_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(\n"
                    "    os.path.abspath(__file__))), 'scripts')\n"
                    "sys.path.insert(0, _SCRIPTS)\n")
        self.assertEqual([], _wurzel_aus_dateipfad(pfadcode, "synthetisch.py"))


if __name__ == "__main__":
    unittest.main()
