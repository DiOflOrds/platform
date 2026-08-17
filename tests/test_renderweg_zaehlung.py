"""Ein Renderweg — die Regel von ADR-P12-001 als PRÜFUNG (projects/p12/T-0009).

⚠ **Warum ein Zähltest und kein Vorsatz.** `p12` ist eine **Zusammenführung**: endet sie mit
zwei Renderwegen statt einem, hat sie ihr Ziel verfehlt, auch wenn alles funktioniert. DoD 2
von `p12/T-0009` verlangt die Antwort deshalb ausdrücklich als Prüfung. Die Bauform ist im
Haus belegt — SWR-134 hält die Git-Schreibwege über den Syntaxbaum bei einem, SWR-146 hat
einen Altbestand von drei Inline-Regeln mit einem eingefrorenen Zähler auf null gezogen.

⚠⚠ **Der Altbestand steht hier als ZAHL und nicht als Warnung:**

> **Ein Altbestand, der als Warnung dasteht, wächst. Einer, der als Zahl dasteht, kann nur
> sinken.**

Verifiziert: SWR-097, SWR-098, SWR-099, SWR-100.

Ausführung: python -m unittest discover platform/tests
"""
import os
import re
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
_APP_JS = os.path.join(_HIER, "..", "backend", "static", "app.js")

#: Aufrufe von `tlinks` **außerhalb** des Renderers, gemessen 2026-08-17 (Sprint 18):
#: Zeilen 126 (`preMitLinks`), 829, 943, 1106. ⚠ Diese Zahl ist eine **Zusage an einen
#: künftigen Lauf**: sie darf **sinken** und nicht steigen. `p12/T-0006` zieht sie auf 0,
#: und dieses Senken ist der Nachweis der Zusammenführung.
ALTBESTAND_TLINKS_AUFRUFE = 4

#: Die eine Funktion, die aus Markdown-Text DOM macht (SWR-059/060, SWR-097).
RENDERER = "mdRender"

#: Der eine Inline-Pass (SWR-098: die Ticket-Erkennung gehört **hierhin**).
INLINE_PASS = "mdInline"


def _quelltext():
    with open(_APP_JS, encoding="utf-8") as f:
        return f.read()


def _ohne_kommentare(text):
    """Block- und Zeilenkommentare entfernt.

    ⚠ Nicht Kosmetik, sondern die Lehre aus dem ersten Wurf von `test_deep_links`: eine
    Textsuche kann eine **Erklärung** nicht von ihrem **Gegenstand** unterscheiden, und die
    Erklärung steht nun einmal genau dort, wo der Gegenstand ist. Fünf Fehlalarme dieser Art
    in zwei Tagen (SWR-141, SWR-148, SWR-150).
    """
    ohne = re.sub(r"(?s)/\*.*?\*/", "", text)
    return "\n".join(re.sub(r"//.*$", "", z) for z in ohne.splitlines())


class EinRendererTest(unittest.TestCase):
    """Verifiziert: SWR-097."""

    def test_genau_eine_funktion_macht_aus_markdown_dom(self):
        """⚠ Ein zweiter Renderer macht diese Prüfung rot — auch einer, der „nur für Briefe"
        gedacht ist. Genau der wäre die bequemste Lösung und das Scheitern von P12.
        Verifiziert: SWR-097."""
        code = _ohne_kommentare(_quelltext())
        # Kandidaten: Funktionen, deren Name auf einen Markdown-Renderer deutet.
        namen = set(re.findall(r"function\s+(\w*[Mm]d\w*|\w*[Mm]arkdown\w*)\s*\(", code))
        renderer = {n for n in namen if n != INLINE_PASS}
        self.assertEqual(renderer, {RENDERER},
                         f"erwartet genau {RENDERER!r} als Renderer, gefunden: "
                         f"{sorted(renderer)}")

    def test_der_inline_pass_ist_einer_und_wird_vom_renderer_gerufen(self):
        """Gegenprobe zur Zählung: dass es **einen** Renderer gibt, heißt nicht, dass er
        den Inline-Pass benutzt. Verifiziert: SWR-097, SWR-098."""
        code = _ohne_kommentare(_quelltext())
        self.assertEqual(len(re.findall(rf"function\s+{INLINE_PASS}\s*\(", code)), 1)
        # Der Renderer ruft ihn an jeder Stelle, an der Text zu Kindknoten wird:
        # Überschrift, Tabellenzelle, Listenpunkt, Absatz.
        self.assertGreaterEqual(len(re.findall(rf"\b{INLINE_PASS}\(", code)), 5,
                                "der Renderer geht nicht überall über den Inline-Pass")


class AltbestandTest(unittest.TestCase):
    """Verifiziert: SWR-098."""

    def test_tlinks_aufrufe_stehen_bei_der_gemessenen_zahl(self):
        """⚠⚠ Der eingefrorene Zähler. `tlinks` ist der **zweite Wrapper um den Rohtext**,
        den SWR-098 wörtlich verbietet. Er darf nicht wachsen, und `p12/T-0006` zieht ihn
        auf 0 — dann wird DIESE Zahl gesenkt, und das ist der Nachweis.
        Verifiziert: SWR-098."""
        code = _ohne_kommentare(_quelltext())
        # Aufrufe, nicht die Definition: `tlinks(` ohne vorangestelltes `function `.
        alle = len(re.findall(r"\btlinks\(", code))
        definition = len(re.findall(r"function\s+tlinks\(", code))
        aufrufe = alle - definition
        self.assertEqual(definition, 1, "tlinks ist mehr als einmal definiert")
        self.assertLessEqual(aufrufe, ALTBESTAND_TLINKS_AUFRUFE,
                             f"{aufrufe} Aufrufe — der Altbestand darf nur SINKEN "
                             f"(eingefroren bei {ALTBESTAND_TLINKS_AUFRUFE})")
        self.assertEqual(aufrufe, ALTBESTAND_TLINKS_AUFRUFE,
                         f"{aufrufe} statt {ALTBESTAND_TLINKS_AUFRUFE} Aufrufe — wenn das "
                         f"eine Verbesserung ist, gehört die Konstante gesenkt; ein "
                         f"stillschweigend richtiger Zähler ist kein Nachweis")

    def test_der_inline_pass_kennt_die_ticketnummer_heute_NICHT(self):
        """⚠ Diese Zusicherung hält den **Befund** fest, nicht die Lösung. Sie wird rot,
        sobald `p12/T-0006` die Erkennung in den Inline-Pass holt — und **das ist ihr
        Zweck**: sie sagt dem Lauf, der es tut, dass er den Altbestand mitzunehmen hat,
        statt die Erkennung ZWEIMAL stehen zu lassen (B033).

        Ein Test, der nur den Zielzustand kennt, wäre bis dahin rot und würde ignoriert
        (die Falle aus SWR-131). Verifiziert: SWR-098."""
        code = _ohne_kommentare(_quelltext())
        m = re.search(rf"function\s+{INLINE_PASS}\s*\((.*?)\n\}}", code, re.S)
        self.assertIsNotNone(m, "der Inline-Pass ist nicht auffindbar")
        self.assertNotIn("T-\\d", m.group(1),
                         "der Inline-Pass erkennt jetzt Ticketnummern — dann muss "
                         "ALTBESTAND_TLINKS_AUFRUFE gesenkt und diese Zusicherung "
                         "umgedreht werden (ADR-P12-001, Entscheidung 1)")


class CodeZaunTest(unittest.TestCase):
    """Verifiziert: SWR-099."""

    def test_der_absatzpfad_fuegt_heute_mit_leerzeichen_zusammen(self):
        """⚠ Das ist der **Darstellungsbefund** aus `p12/T-0008`, hier messbar gemacht:
        der Inhalt von Code-Zäunen geht nicht verloren, aber der Absatzpfad fügt Zeilen mit
        `" "` zusammen — der Verlust ist nicht an Zeichen, sondern an **Struktur**.

        Kein Vollständigkeitsfehler und deshalb kein roter Test: eine Zusicherung, die
        einen bekannten, benannten Zustand als Fehler meldet, erzieht zum Wegsehen
        (SWR-131). Sie hält ihn fest, damit `p12/T-0006` ihn nicht neu entdecken muss.
        Verifiziert: SWR-099."""
        code = _ohne_kommentare(_quelltext())
        self.assertIn('absatz.join(" ")', code,
                      "der Absatzpfad wurde geändert — ADR-P12-001 Entscheidung 3 prüfen")
        self.assertNotIn("<pre><code>", code)

    def test_es_gibt_noch_keinen_block_pass_fuer_zaeune(self):
        """Die Gegenprobe zur Entscheidung 3: heute **kein** Zaun-Zweig im Block-Pass. Wird
        einer gebaut, wird diese Zusicherung rot und ist umzudrehen — sie ist der Merkzettel
        an der Sache statt im Bericht. Verifiziert: SWR-099."""
        code = _ohne_kommentare(_quelltext())
        self.assertNotRegex(code, r'strip\.(?:indexOf|startsWith)\(\s*"`{3}"')


class KeinInnerHtmlTest(unittest.TestCase):
    """Verifiziert: SWR-100."""

    def test_der_renderweg_benutzt_kein_innerhtml(self):
        """⚠ Briefe sind **freier Text eines Menschen**. `innerHTML` auf diesem Weg wäre
        nicht Bequemlichkeit, sondern eine Ausführungsstelle. Verifiziert: SWR-100."""
        code = _ohne_kommentare(_quelltext())
        self.assertNotIn("innerHTML", code)
        self.assertNotIn("outerHTML", code)
        self.assertNotIn("insertAdjacentHTML", code)

    def test_keine_externe_bibliothek_auf_dem_renderweg(self):
        """ADR-002 bleibt gültig: kein Build, kein Bundler, keine Bibliothek.
        Verifiziert: SWR-100."""
        code = _ohne_kommentare(_quelltext())
        for verboten in ("import ", "require(", "cdn.", "unpkg", "jsdelivr"):
            self.assertNotIn(verboten, code, f"{verboten!r} auf dem Renderweg")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
