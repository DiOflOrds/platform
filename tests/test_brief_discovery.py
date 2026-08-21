"""Der VERTRETER von SWR-206 (platform/T-0057, Sprint 33).

⚠⚠ **Das Ticket hatte zwei Befunde, und die Messung hat den einen widerlegt und den
anderen verschärft.**

`T-0057` schrieb, sieben Briefe seien *„WÄHREND des Laufs"* von Sprint 32 eingegangen —
und **das Ticket hatte recht**.

> **⚠⚠ DIE ERSTE FASSUNG DIESER DATEI HAT DAS TICKET „KORRIGIERT" UND LAG SELBST FALSCH.**
> Sie verglich den Brief-Zeitstempel (**UTC**, `+00:00`) mit dem Sprintstart
> (**Wanduhrzeit**, CEST) und warf den Offset mit `.replace(tzinfo=None)` weg statt
> umzurechnen. Zwei Stunden Versatz — daraus wurde die Behauptung, die Briefe seien
> während Sprint 31 gekommen. **Gefunden hat es nicht der Autor, sondern das unabhängige
> Gegenlesen; die falsche Zahl stand da bereits in einer ANFORDERUNG und in einer
> eingefrorenen Regressionsschranke.**
>
> **Eine Zeitzone ist keine Formatfrage. Sie ist eine Maßeinheit — und zwei Uhren, die
> nie miteinander verglichen wurden, sind kein gemeinsamer Zeitstrahl.**

Richtiggestellt und in Ortszeit nachgemessen: die sieben Briefe kamen **08:32–09:03**,
**Sprint 32** lief **08:13–10:03**. Der echte Befund bleibt derselbe und wird sogar
schärfer: Sprint 32 hat den Briefkasten am Anfang gemessen, den Haken auf „erfüllt"
gesetzt und ihn während des eigenen Laufs siebenmal ungültig werden lassen.

DoD 1 ist damit beantwortet und die Antwort hat den Bau bestimmt: von **21** Briefen seit
Registerbeginn kamen **17 (81 %)**, während ein Sprint lief. Der späte Brief ist die
**Regel**. Deshalb ist `briefe_im_lauf` eine Kennzahl und keine Empfehlung.

Lehren dieses Baus: `L-2026-08-21cw` (Zeitzone), `L-2026-08-21cy` (eine Tür, ein
Schlüssel), `L-2026-08-21cz` (Anwesenheit ist nicht Verwendung), `L-2026-08-21da`
(„kein Ende" heißt abgebrochen, nicht aktiv).

DoD 3 („wer merkt es, wenn niemand die Kennzahlen zieht?"): die Größe steht im
Kennzahlenblock, den `preflight` und der Abschluss ohnehin ziehen — und Preflight liest
Briefe ab jetzt durch **dieselbe Tür** wie die Kennzahlen.
"""
import ast
import glob as _glob
import os
import sys
import unittest

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, "scripts"))
sys.path.insert(0, WURZEL)
import board  # noqa: E402
import kennzahlen  # noqa: E402

ORGA = os.path.dirname(WURZEL)


class EineDiscoveryFuerBriefe(unittest.TestCase):
    """SWR-206 Richtung 1: es gibt genau EINEN Weg zu den Briefen."""

    def test_deckt_beide_ebenen_ab(self):
        """Der alte Glob und die neue Auflösung liefern dieselbe Menge — am ECHTEN Bestand.

        ⚠ Diese Zusicherung darf **nicht** so gelesen werden, dass beide Wege gleichwertig
        sind. Sie hält fest, dass die Umstellung nichts verloren hat; der zweite Weg ist
        danach weg, und `test_kein_zweiter_glob` sorgt dafür, dass er wegbleibt.
        """
        alt = set(_glob.glob(os.path.join(ORGA, "*", "management", "briefkasten", "N-*.md")))
        alt |= set(_glob.glob(os.path.join(ORGA, "*", "*", "management", "briefkasten",
                                           "N-*.md")))
        neu = {p for _e, p in board.briefkasten_dateien(ORGA)}
        self.assertEqual({os.path.abspath(p) for p in neu},
                         {os.path.abspath(p) for p in alt})
        self.assertGreater(len(neu), 0, "Ohne Briefe sagt dieser Vergleich nichts")

    def test_jeder_brief_traegt_seine_einheit(self):
        for einheit, pfad in board.briefkasten_dateien(ORGA):
            self.assertTrue(einheit, pfad)
            self.assertIn(einheit, pfad.replace("\\", "/").split("/"))

    def test_kein_zweiter_glob(self):
        """⚠⚠ Der eigentliche Gegenstand: kein Modul baut sich seinen Briefpfad selbst.

        Geprüft über den **Syntaxbaum**: gesucht sind String-Literale, die den
        Briefkasten-Pfad zusammensetzen, außerhalb von `board.py`. Ein Textvergleich
        schlüge gegen die eigenen Docstrings an — der Fehler, den Sprint 32 zweimal
        gemacht hat.
        """
        treffer = []
        for verz in ("backend", "scripts", "orchestrator"):
            for wurzel, _d, namen in os.walk(os.path.join(WURZEL, verz)):
                if "__pycache__" in wurzel:
                    continue
                for name in namen:
                    if not name.endswith(".py") or name == "board.py":
                        continue
                    datei = os.path.join(wurzel, name)
                    with open(datei, encoding="utf-8") as f:
                        quelle = f.read()
                    baum = ast.parse(quelle, filename=datei)
                    for knoten in ast.walk(baum):
                        if not isinstance(knoten, ast.Call):
                            continue
                        namen_teile = [a.value for a in knoten.args
                                       if isinstance(a, ast.Constant)
                                       and isinstance(a.value, str)]
                        if "briefkasten" in namen_teile and "management" in namen_teile:
                            treffer.append(f"{os.path.relpath(datei, WURZEL)}:"
                                           f"{knoten.lineno}")
        # ⚠ `aggregation` und `briefkasten.py` loesen den Pfad EINER Einheit auf (aus
        # `projekt_pfad`) und sind damit kein zweiter ORGANISATIONSWEITER Weg. Sie sind
        # namentlich erlaubt, statt die Pruefung stillschweigend weich zu machen.
        erlaubt = {"backend/aggregation.py", "backend/briefkasten.py"}
        uebrig = [t for t in treffer
                  if t.rsplit(":", 1)[0].replace("\\", "/") not in erlaubt]
        self.assertEqual(uebrig, [], "zweiter Brief-Discovery-Weg: " + ", ".join(uebrig))

    @staticmethod
    def _ruft_auf(quelle, modul, funktion, datei="<x>"):
        """Ruft dieser Quelltext `modul.funktion(...)` im RUMPF auf? — ohne Docstrings.

        ⚠⚠ Die erste Fassung suchte den Namen als **Text**. Das Gegenlesen hat gezeigt,
        dass er im Docstring bereits stand: die Zusicherung war allein durch Prosa
        erfüllt. **Anwesenheit ist nicht Verwendung** — derselbe Fehler, den Sprint 32
        an zwei eigenen Prüfern gefunden hat.
        """
        baum = ast.parse(quelle, filename=datei)
        for knoten in ast.walk(baum):
            if (isinstance(knoten, ast.Call)
                    and isinstance(knoten.func, ast.Attribute)
                    and knoten.func.attr == funktion
                    and isinstance(knoten.func.value, ast.Name)
                    and knoten.func.value.id == modul):
                return True
        return False

    def test_kennzahlen_gehen_durch_die_tuer(self):
        """Die Verdrahtung, nicht die Funktion (Review-Befund aus Sprint 32)."""
        import inspect
        quelle = inspect.getsource(kennzahlen.zaehle_briefkasten)
        self.assertTrue(self._ruft_auf(quelle, "board", "briefkasten_dateien"),
                        "zaehle_briefkasten ruft die gemeinsame Tuer nicht auf")
        self.assertFalse(self._ruft_auf(quelle, "glob", "glob"),
                         "zweiter Discovery-Weg in zaehle_briefkasten")

    def test_preflight_geht_durch_dieselbe_tuer(self):
        """⚠ Geprüft wird der AUFRUF, nicht das Vorkommen des Namens in 1248 Zeilen."""
        datei = os.path.join(WURZEL, "scripts", "preflight.py")
        with open(datei, encoding="utf-8") as f:
            quelle = f.read()
        self.assertTrue(self._ruft_auf(quelle, "board", "briefkasten_dateien", datei))
        self.assertTrue(self._ruft_auf(quelle, "board", "brief_offen", datei),
                        "preflight legt die Auslegung von 'offen' wieder selbst fest")

    def test_eine_auslegung_von_offen(self):
        """Nachtrag aus dem Gegenlesen: dieselbe Tür UND derselbe Schlüssel.

        Der erste Bau hat die Discovery vereinheitlicht und die Auslegung des
        Statusfeldes doppelt gelassen (`preflight`: Teilstring in 300 Zeichen;
        `kennzahlen`: Frontmatter, kleingeschrieben).
        """
        import inspect
        self.assertTrue(self._ruft_auf(inspect.getsource(kennzahlen.zaehle_briefkasten),
                                       "board", "brief_offen"))


class AussageUeberDasFenster(unittest.TestCase):
    """SWR-206 Richtung 2: „keiner eingegangen" wird gemessen statt behauptet."""

    def test_zaehlt_briefe_seit_einem_zeitpunkt(self):
        from datetime import datetime
        frueh = datetime(2000, 1, 1)
        spaet = datetime(2100, 1, 1)
        self.assertGreater(kennzahlen.zaehle_briefe_im_lauf(ORGA, seit=frueh), 0)
        self.assertEqual(kennzahlen.zaehle_briefe_im_lauf(ORGA, seit=spaet), 0)

    def test_das_gemessene_fenster_von_sprint_32(self):
        """⚠⚠ Der Beleg: im Fenster von Sprint 32 kamen sieben Briefe — und in dem von 31 keiner.

        Diese Zusicherung ist der Grund, warum die Größe existiert: wäre sie in Sprint 32
        gelaufen, hätte der Haken „Briefkasten erfüllt" nicht stehen bleiben können.

        ⚠ **Die zweite Hälfte ist die eigentliche Zusicherung.** Sie hält den
        Zeitzonenfehler fest, den das Gegenlesen gefunden hat: rechnet jemand UTC wieder
        nicht in Ortszeit um, wandern genau diese sieben Briefe ins Fenster von Sprint 31
        — und **beide** Zeilen werden rot.
        """
        from datetime import datetime
        def im_fenster(a, e):
            return (kennzahlen.zaehle_briefe_im_lauf(ORGA, seit=a)
                    - kennzahlen.zaehle_briefe_im_lauf(ORGA, seit=e))
        self.assertEqual(im_fenster(datetime(2026, 8, 21, 8, 13),
                                    datetime(2026, 8, 21, 10, 3)), 7,
                         "Das Fenster von Sprint 32 traegt sieben Briefe")
        self.assertEqual(im_fenster(datetime(2026, 8, 21, 6, 13),
                                    datetime(2026, 8, 21, 7, 23)), 0,
                         "Im Fenster von Sprint 31 kam KEIN Brief — steht hier 7, ist "
                         "der Zeitzonenfehler zurueck (UTC gegen Wanduhr).")

    def test_zeitzone_wird_umgerechnet_und_nicht_abgeschnitten(self):
        """⚠⚠ Der Befund des Gegenlesens, direkt gesichert.

        `.replace(tzinfo=None)` wirft den Offset weg, `.astimezone()` rechnet um. Der
        Unterschied ist bei CEST zwei Stunden — und damit laenger als ein ganzer Sprint.
        """
        import inspect
        quelle = inspect.getsource(kennzahlen.zaehle_briefe_im_lauf)
        self.assertIn("astimezone", quelle,
                      "ohne astimezone wird UTC gegen Wanduhr verglichen")

    def test_unbekannt_ist_nicht_null(self):
        """⚠ Ohne laufenden Sprint gibt es `None` und nicht `0`.

        Ein Vorgabewert verwandelt eine fehlende Antwort in eine beruhigende — der
        Review-Befund 3 aus Sprint 32, hier von vornherein ausgeschlossen.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as leer:
            self.assertIsNone(kennzahlen.zaehle_briefe_im_lauf(leer))

    def test_nur_der_NEUESTE_sprint_kann_laufen(self):
        """⚠⚠ Beim Sprint-Abschluss gefunden: 15 von 33 Sprints haben nie ein `ende`.

        Die erste Fassung nahm den hoechstnummerierten Sprint **ohne** `ende` und griff
        damit, sobald der laufende beendet war, auf ein altes abgebrochenes Fenster
        zurueck — gemeldet wurden 14 Briefe statt 0.

        > **„Kein Ende" heisst abgebrochen und nicht aktiv.**
        """
        import json
        datei = os.path.join(ORGA, "pm", "management", "sprints.jsonl")
        sprints = {}
        with open(datei, encoding="utf-8") as f:
            for zeile in f:
                if zeile.strip():
                    e = json.loads(zeile)
                    sprints.setdefault(e["kennung"], {}).update(e)
        ohne_ende = [s for s in sprints.values() if s.get("nr") and not s.get("ende")]
        self.assertGreater(len(ohne_ende), 1,
                           "ohne mehrere offen gebliebene Sprints sagt diese Zusicherung "
                           "nichts — der Befund war genau ihre Existenz")
        neuester = max((s for s in sprints.values() if s.get("nr")),
                       key=lambda s: s["nr"])
        erwartet = None if neuester.get("ende") else neuester["start"]
        ist = kennzahlen._sprint_start(ORGA)
        if erwartet is None:
            self.assertIsNone(ist, "ein beendeter neuester Sprint darf kein altes, "
                                   "abgebrochenes Fenster zurueckgeben")
        else:
            self.assertEqual(ist.strftime("%Y-%m-%d %H:%M"), erwartet)

    def test_kennzahlenblock_traegt_die_groesse(self):
        """⚠ Geprüft wird der BLOCK, nicht der Dict-Schlüssel.

        Die erste Fassung prüfte `assertIn("briefe_im_lauf", miss(ORGA))` — also den
        Schlüssel im Zwischenergebnis. `block()` lässt `None`-Werte weg; die Größe hätte
        aus dem Bericht verschwinden können, ohne dass diese Zusicherung es merkt.
        Genau das behauptet ihr Name aber.
        """
        werte = kennzahlen.miss(ORGA)
        text = kennzahlen.block(werte)
        if werte["briefe_im_lauf"] is None:
            # ⚠ Zwischen zwei Sprints ist die Groesse **unbekannt**, nicht null. Sie
            # faellt dann aus dem Block — und `vergleiche` darf das ausdruecklich NICHT
            # als Abweichung melden, sonst waere jeder Bericht zwischen zwei Laeufen rot.
            self.assertNotIn("briefe_im_lauf=", text)
            self.assertEqual(
                [a for a in kennzahlen.vergleiche({}, werte)
                 if a[0] == "briefe_im_lauf"], [],
                "unbekannt darf keine Abweichung sein (konnte nicht messen != 0)")
        else:
            self.assertIn(f"briefe_im_lauf={werte['briefe_im_lauf']}", text)

    def test_groesse_steht_in_den_vergleichsfeldern(self):
        """Sonst darf der Bericht dazu behaupten, was er will.

        ⚠ Bei `parkplatz` ist der Ausschluss aus `VERGLEICHSFELDER` begründet **und**
        zugesichert (er waechst zwischen Messung und Lesen). Fuer `briefe_im_lauf` gilt
        das nicht: die Zahl ist innerhalb eines Sprints stabil, also gehoert sie in den
        Vergleich.
        """
        self.assertIn("briefe_im_lauf", kennzahlen.VERGLEICHSFELDER)


if __name__ == "__main__":
    unittest.main()
