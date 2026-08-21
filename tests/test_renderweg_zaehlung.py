"""Ein Renderweg — die Regel von ADR-P12-001 als PRÜFUNG (p12/T-0009, eingelöst p12/T-0006).

⚠ **Warum ein Zähltest und kein Vorsatz.** `p12` ist eine **Zusammenführung**: endet sie mit
zwei Renderwegen statt einem, hat sie ihr Ziel verfehlt, auch wenn alles funktioniert. Die
Bauform ist im Haus belegt — SWR-134 hält die Git-Schreibwege über den Syntaxbaum bei einem,
SWR-146 hat einen Altbestand von drei Inline-Regeln mit einem eingefrorenen Zähler auf null
gezogen.

⚠⚠ **Der Altbestand stand hier als ZAHL und nicht als Warnung — und er ist gesunken:**

> **Ein Altbestand, der als Warnung dasteht, wächst. Einer, der als Zahl dasteht, kann nur
> sinken.**

**Sprint 19 (`p12/T-0006`): 4 → 0.** `tlinks` ist nicht „nicht mehr aufgerufen", sondern
**entfallen**. Drei Zusicherungen dieser Datei sind dabei rot geworden — **genau die drei**,
die Sprint 18 als Befund eingefroren hatte, und **keine vierte**. Sie sind hier umgedreht.

> **Ein Test, der den heutigen Zustand festhält, ist erst dann etwas wert, wenn der Lauf,
> der ihn rot macht, ihn auch umdreht. Sonst ist er eine Warnung mit Zeitstempel.**

Verifiziert: SWR-097, SWR-098, SWR-099, SWR-100.

Ausführung: python -m unittest discover platform/tests
"""
import os
import re
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
_APP_JS = os.path.join(_HIER, "..", "backend", "static", "app.js")

#: Aufrufe von `tlinks` **außerhalb** des Renderers. Gemessen 2026-08-17 (Sprint 18): **4**
#: (Zeilen 126, 829, 943, 1106). Nach `p12/T-0006` (Sprint 19): **0** — die Funktion selbst
#: ist entfallen. ⚠ Die Zahl darf **sinken** und nicht steigen; bei 0 heißt das: sie darf
#: nicht wiederkommen.
ALTBESTAND_TLINKS_AUFRUFE = 0

#: Die eine Funktion, die aus Markdown-Text DOM macht (SWR-059/060, SWR-097).
RENDERER = "mdRender"

#: Der eine Inline-Pass (SWR-098: die Ticket-Erkennung gehört **hierhin** — und tut es).
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


def _rumpf(code, name):
    """Der Rumpf einer Funktionsdeklaration bis zur schließenden Klammer in Spalte 0."""
    m = re.search(rf"function\s+{name}\s*\((.*?)\n\}}", code, re.S)
    return m.group(1) if m else None


class EinRendererTest(unittest.TestCase):
    """Verifiziert: SWR-097."""

    def test_genau_eine_funktion_macht_aus_markdown_dom(self):
        """⚠ Ein zweiter Renderer macht diese Prüfung rot — auch einer, der „nur für Briefe"
        gedacht ist. Genau der wäre die bequemste Lösung und das Scheitern von P12.
        Verifiziert: SWR-097."""
        code = _ohne_kommentare(_quelltext())
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
        self.assertGreaterEqual(len(re.findall(rf"\b{INLINE_PASS}\(", code)), 5,
                                "der Renderer geht nicht überall über den Inline-Pass")

    def test_briefe_und_reports_laufen_ueber_den_renderer(self):
        """⚠ Der **Kern** von SWR-097, und er ist nicht am Zählen der Funktionen abzulesen:
        einen einzigen Renderer zu haben, den die Briefansicht nicht benutzt, erfüllt die
        Zählung und verfehlt die Anforderung.

        Gemessen wird an den zwei Ansichten, die SWR-097 **namentlich** nennt: der
        Brief-Beitrag im Team-Chat und der Sprint-Report. Verifiziert: SWR-097."""
        code = _ohne_kommentare(_quelltext())
        self.assertRegex(code, r"mdRender\(beitrag\.text",
                         "der Brief-Beitrag läuft nicht über den Renderer (SWR-097)")
        self.assertRegex(code, r"mdRender\(r\.text",
                         "der Sprint-Report läuft nicht über den Renderer (SWR-097)")
        # Gegenprobe: keine der beiden Stellen hängt noch am Rohtext-Weg.
        self.assertNotRegex(code, r"preMitLinks\(beitrag\.text")
        self.assertNotRegex(code, r"preMitLinks\(r\.text")


class AltbestandTest(unittest.TestCase):
    """Verifiziert: SWR-098."""

    def test_tlinks_ist_entfallen_und_kommt_nicht_wieder(self):
        """⚠⚠ Der eingefrorene Zähler, **eingelöst**. `tlinks` war der *zweite Wrapper um
        den Rohtext*, den SWR-098 wörtlich verbietet.

        ⚠ Geprüft wird **beides**: null Aufrufe **und** keine Definition. Nur die Aufrufe zu
        zählen ließe eine tote Funktion stehen, die der nächste Lauf wiederfindet und für
        benutzbar hält — ein Altbestand, der auf 0 gezählt wird und trotzdem dasteht.
        Verifiziert: SWR-098."""
        code = _ohne_kommentare(_quelltext())
        alle = len(re.findall(r"\btlinks\(", code))
        definition = len(re.findall(r"function\s+tlinks\(", code))
        aufrufe = alle - definition
        self.assertEqual(definition, 0,
                         "tlinks ist wieder definiert — der zweite Wrapper ist zurück")
        self.assertLessEqual(aufrufe, ALTBESTAND_TLINKS_AUFRUFE,
                             f"{aufrufe} Aufrufe — der Altbestand darf nur SINKEN "
                             f"(eingefroren bei {ALTBESTAND_TLINKS_AUFRUFE})")
        self.assertEqual(aufrufe, ALTBESTAND_TLINKS_AUFRUFE)

    def test_der_inline_pass_KENNT_die_ticketnummer(self):
        """⚠ **Diese Zusicherung ist umgedreht.** Bis Sprint 18 hielt sie den *Befund* fest
        („der Inline-Pass kennt die Ticketnummer heute NICHT") und war ausdrücklich dazu da,
        rot zu werden, sobald `p12/T-0006` baut. Sie ist rot geworden, und dieser Lauf hat
        sie umgedreht statt sie zu löschen — die Richtung der Aussage ist die Historie.
        Verifiziert: SWR-098."""
        code = _ohne_kommentare(_quelltext())
        rumpf = _rumpf(code, INLINE_PASS)
        self.assertIsNotNone(rumpf, "der Inline-Pass ist nicht auffindbar")
        self.assertIn("T-\\d", rumpf,
                      "der Inline-Pass erkennt keine Ticketnummern (ADR-P12-001, E1)")

    def test_der_inline_pass_baut_KEINE_route_sondern_fragt_die_eine_stelle(self):
        """⚠ Die Erkennung zu verschieben, ohne SWR-150 mitzunehmen, wäre der **zweite
        Bauplatz** an neuer Stelle: neun solche Stellen hat Sprint 18 gerade abgeräumt.
        Der Inline-Pass darf eine Nummer erkennen und muss nach dem **Ziel** fragen.
        Verifiziert: SWR-098, SWR-150."""
        code = _ohne_kommentare(_quelltext())
        rumpf = _rumpf(code, INLINE_PASS)
        self.assertIn("Regeln.textRefAnnahme", rumpf,
                      "der Inline-Pass benennt die Annahme nicht")
        self.assertIn("ticketLink(", rumpf,
                      "der Inline-Pass benutzt nicht den einen Bauplatz aus SWR-150")
        # Er setzt selbst KEINE Route zusammen (das Präfix gehört nach `regeln.js`).
        self.assertNotIn("TICKET_ROUTE_PRAEFIX", rumpf)
        self.assertNotIn('"#/ticket', rumpf)

    def test_backtick_gewinnt_gegen_die_ticketnummer(self):
        """⚠ Die **Reihenfolge im Muster** ist Teil der Entscheidung und nicht Kosmetik:
        ein `T-0042` in Backticks ist ein **Zitat**. Verlinkte man es, verlinkte die
        Dokumentation über den Renderer ihre eigenen Beispiele.

        Gemessen wird die **Stellung im Muster** und nicht der Vorsatz: der Backtick-Zweig
        muss im Alternativenmuster **vor** dem Ticket-Zweig stehen. Verifiziert: SWR-098."""
        code = _ohne_kommentare(_quelltext())
        rumpf = _rumpf(code, INLINE_PASS)
        m = re.search(r"var muster = /(.*)/;", rumpf)
        self.assertIsNotNone(m, "das Inline-Muster ist nicht auffindbar")
        muster = m.group(1)
        self.assertIn("`", muster)
        self.assertIn("T-\\d", muster)
        self.assertLess(muster.index("`"), muster.index("T-\\d"),
                        "der Ticket-Zweig steht vor dem Backtick-Zweig — dann wird ein "
                        "zitiertes `T-0042` zum Link (ADR-P12-001, Entscheidung 1)")


class CodeZaunTest(unittest.TestCase):
    """Verifiziert: SWR-099."""

    def test_der_absatzpfad_fuegt_weiterhin_mit_leerzeichen_zusammen(self):
        """Der Absatzpfad ist **unverändert** — das ist die Gegenprobe zum Zaun-Zweig:
        die Reparatur von SWR-099 durfte den Absatz nicht mit umbauen. Der Zaun fügt mit
        `"\\n"`, der Absatz weiter mit `" "`. Verifiziert: SWR-099."""
        code = _ohne_kommentare(_quelltext())
        self.assertIn('absatz.join(" ")', code,
                      "der Absatzpfad wurde geändert — ADR-P12-001 Entscheidung 3 prüfen")
        # SWR-100: der Zaun entsteht über DOM-Aufrufe, nicht als HTML-Zeichenkette.
        self.assertNotIn("<pre><code>", code)

    def test_es_GIBT_einen_block_pass_fuer_zaeune(self):
        """⚠ **Diese Zusicherung ist umgedreht.** Bis Sprint 18 hielt sie fest, dass es
        **keinen** Zaun-Zweig gibt, und war der Merkzettel an der Sache statt im Bericht.
        `p12/T-0006` hat ihn gebaut. Verifiziert: SWR-099."""
        code = _ohne_kommentare(_quelltext())
        self.assertRegex(code, r'strip\.(?:indexOf|startsWith)\(\s*"`{3}"',
                         "kein Zaun-Zweig im Block-Pass (ADR-P12-001, Entscheidung 3)")
        self.assertRegex(code, r'zaunInhalt\.join\("\\n"\)',
                         "der Zaun fügt nicht mit Zeilenumbruch zusammen — dann geht die "
                         "Struktur verloren, die er erhalten soll")

    def test_der_zaun_umgeht_den_inline_pass(self):
        """⚠⚠ Der Punkt von Entscheidung 3, und er ist am Ergebnis **nicht** abzulesen,
        solange kein Beispiel `**` enthält: in einem Codeblock ist `**` ein Sternchenpaar
        und `T-0042` eine Zeichenfolge.

        Gemessen wird am **Zweig selbst**: zwischen dem Öffnen des Zauns und dem Anhängen
        an die Wurzel darf kein Aufruf des Inline-Passes stehen. Verifiziert: SWR-099."""
        code = _ohne_kommentare(_quelltext())
        m = re.search(r'if \(strip\.indexOf\("`{3}"\) === 0\) \{(.*?)\n    \}', code, re.S)
        self.assertIsNotNone(m, "der Zaun-Zweig ist nicht auffindbar")
        self.assertNotIn(INLINE_PASS, m.group(1),
                         "der Zaun-Zweig ruft den Inline-Pass — ein Link im Codebeispiel "
                         "ist ein Fehler, der wie eine Verbesserung aussieht")


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


class RohtextAnsichtTest(unittest.TestCase):
    """Verifiziert: SWR-098 — der **benannte Folgepunkt**, als Zahl statt als Vorsatz."""

    #: Ansichten, die weiterhin **Rohtext im `<pre>`** zeigen und NICHT über den
    #: Block-Renderer laufen: Ticket-Body, DR-Body und die zwei Dokumentenansichten
    #: (`dateiKarten`, Requirements). Das ist die Abgrenzung aus dem Projektauftrag und
    #: der **benannte Folgepunkt**, der mit dem G4-Antrag zur Entscheidung steht.
    #: ⚠ Die Zahl steht hier, damit der Folgepunkt eine **Größe** hat und nicht nur einen
    #: Namen — und damit niemand ihn nebenbei erledigt, ohne dass es auffällt.
    #:
    #: ⚠⚠ **Sprint 29: 4 -> 5, und die Prüfung hat den Zuwachs gefunden, bevor ein Mensch
    #: ihn gesehen hat.** `SWR-192` (`platform/T-0030`) hat den Kommentar-Verlauf gebaut;
    #: sein Beitragstext läuft über **denselben** `preMitLinks` wie der Ticket-Rumpf. Das
    #: ist die richtige Wahl — ein Verweis `T-0042` in einem Kommentar wäre sonst als
    #: einziger Text dieser Ansicht kein Link — aber es ist eine **Vergrößerung des
    #: Folgepunkts**, und die gehört benannt statt gediffed.
    #:
    #: > **Der Zähler hat genau das getan, wofür er dasteht. Er hat eine Entscheidung
    #: > erzwungen, die sonst als Nebenwirkung durchgegangen wäre — und der Zuwachs ist
    #: > hier begründet, statt dass die Zahl still nachgezogen wurde.**
    ROHTEXT_ANSICHTEN = 5

    #: ⚠⚠ **`p12/T-0011`, Sprint 25: die Zahl allein war zu wenig.** Der Zähler darüber
    #: sagt *wie viele* und nicht *welche*. Wer eine der vier auf den Block-Renderer
    #: umstellt und dabei anderswo eine neue Rohtext-Ansicht anlegt, hält die Zahl bei 4
    #: und die Prüfung bleibt grün — der Folgepunkt wäre halb erledigt und halb neu
    #: entstanden, und beides unsichtbar.
    #:
    #:     **Eine Prüfung, die nur die Anzahl misst, kann einen Tausch nicht von
    #:     Stillstand unterscheiden. Neben jedes „es sind vier" gehört „und es sind
    #:     DIESE vier" (`L-2026-08-20by`).**
    #:
    #: Erkannt am **Argument** der Aufrufstelle, nicht an der Zeilennummer: Zeilen
    #: verschieben sich bei jeder Änderung, der Gegenstand nicht.
    ROHTEXT_STELLEN = {
        "Ticket-Body": r"preMitLinks\(t\.body",
        "DR-Body": r"preMitLinks\(dr\.body",
        "Dokumentenansicht (dateiKarten)": r"preMitLinks\(d\.text, projekt\)",
        "Requirements-Ansicht": r"preMitLinks\(d\.text, d\.projekt",
        # SWR-192 (platform/T-0030): der Kommentar-Verlauf am Ticket. Bewusst über
        # DENSELBEN Rohtext-Weg wie der Ticket-Rumpf, den er ergänzt — zwei Textsorten
        # in einer Ansicht wären die schlechtere Antwort auf dieselbe Frage.
        "Kommentar-Verlauf am Ticket": r"preMitLinks\(k\.text",
    }

    def test_es_sind_DIESE_vier_ansichten_und_nicht_irgendwelche(self):
        """⚠⚠ Die zweite Hälfte des Paares zum Zähler darüber (`p12/T-0011`).

        Der Folgepunkt aus dem G4-Antrag von `p12` ist seit dem 17.08. **fünfmal**
        angefasst worden. Was ihn all diese Male blockierte, war der Bau; was gefehlt
        hat, war etwas Kleineres und Fälligeres: **eine Prüfung, die den Gegenstand des
        Folgepunkts nennt statt seine Größe.**

        Damit ist die Frage des Tickets *„welche Ansicht hat welchen Darstellungsgrad?"*
        an einer Stelle beantwortet, die rot wird, wenn sich die Antwort ändert — und
        nicht in einem Satz, den niemand liest (`L-2026-08-17ag`). Verifiziert:
        SWR-097, SWR-098.
        """
        code = _ohne_kommentare(_quelltext())
        for name, muster in self.ROHTEXT_STELLEN.items():
            self.assertRegex(code, muster,
                             f"die Rohtext-Ansicht {name!r} ist nicht mehr an ihrer "
                             f"Stelle — entweder umgestellt (dann gehört das in einen "
                             f"Beschluss, nicht in einen Diff) oder verschoben")
        self.assertEqual(len(self.ROHTEXT_STELLEN), self.ROHTEXT_ANSICHTEN,
                         "die benannte Liste und der Zähler widersprechen sich — zwei "
                         "Quellen für dieselbe Auskunft (B033)")

    def test_der_folgepunkt_hat_eine_groesse(self):
        """⚠ `preMitLinks` ist **kein** zweiter Renderweg: es erzeugt aus Markdown-Blöcken
        kein DOM, sondern zeigt Rohtext und lässt die **Inline**-Regeln vom einen
        Inline-Pass anwenden. Das ist der Unterschied, an dem SWR-097 hängt.

        Steigt diese Zahl, ist eine neue Ansicht am Renderer vorbeigebaut worden; sinkt
        sie, ist der Folgepunkt teilweise erledigt — und dann gehört er entschieden und
        nicht nebenbei getan (B029). Verifiziert: SWR-097, SWR-098."""
        code = _ohne_kommentare(_quelltext())
        alle = len(re.findall(r"\bpreMitLinks\(", code))
        definition = len(re.findall(r"function\s+preMitLinks\(", code))
        self.assertEqual(definition, 1)
        self.assertEqual(alle - definition, self.ROHTEXT_ANSICHTEN,
                         f"{alle - definition} statt {self.ROHTEXT_ANSICHTEN} "
                         f"Rohtext-Ansichten — der benannte Folgepunkt hat seine Größe "
                         f"geändert, das gehört in den G4-Antrag und nicht in einen Diff")

    def test_die_rohtext_ansicht_holt_ihre_links_aus_dem_einen_inline_pass(self):
        """⚠ Das ist der Grund, warum der Zähler auf **0** und nicht auf **1** steht: die
        vier Ansichten behalten ihre Rohtext-**Darstellung**, ihre **Verlinkung** kommt
        aber aus derselben Stelle wie überall sonst. Ein eigener Link-Weg „nur für diese
        vier" wäre wortgleich der zweite Wrapper, den SWR-098 verbietet.
        Verifiziert: SWR-098."""
        code = _ohne_kommentare(_quelltext())
        rumpf = _rumpf(code, "preMitLinks")
        self.assertIsNotNone(rumpf)
        self.assertIn(f"{INLINE_PASS}(", rumpf)
        # ⚠ ZEILENWEISE: ein Muster über Zeilengrenzen findet in einem langen Dokument
        # immer ein zweites `*` und spannt einen `<em>` über 80 Zeilen.
        self.assertIn('split("\\n")', rumpf,
                      "der Inline-Pass läuft über das ganze Dokument statt je Zeile")


class SchreibfreiheitTest(unittest.TestCase):
    """Verifiziert: SWR-101."""

    #: Die eine Stelle, an der die PIN an einen Lese-Endpunkt geht (SWR-049/053).
    PIN_KOPF = "X-MC-PIN"

    def test_der_renderweg_schreibt_nichts(self):
        """⚠ SWR-101 sagt „Rendering shall change presentation only" — ein Satz, den keine
        Prüfung liest, altert lautlos (`L-2026-08-17ag`). Gemessen wird er hier an den
        **Rümpfen** der vier Funktionen des Renderwegs.

        ⚠ Warum nicht dateiweit: `app.js` schreibt selbstverständlich (Ticket-Editor,
        Briefformular). Eine dateiweite Suche wäre entweder rot oder müsste Ausnahmen
        pflegen — und eine Prüfung mit Ausnahmeliste misst am Ende die Liste.
        Verifiziert: SWR-101."""
        code = _ohne_kommentare(_quelltext())
        verboten = ("api(", "fetch(", "localStorage", "sessionStorage",
                    "XMLHttpRequest", "POST")
        for name in (RENDERER, INLINE_PASS, "preMitLinks", "ticketLink"):
            rumpf = _rumpf(code, name)
            self.assertIsNotNone(rumpf, f"{name} ist nicht auffindbar")
            for wort in verboten:
                self.assertNotIn(wort, rumpf,
                                 f"{name!r} enthält {wort!r} — der Renderweg schreibt")

    def test_das_pin_lesegate_ist_unberuehrt(self):
        """⚠ Die zweite Hälfte von SWR-101, und die leicht zu übersehende: die Umstellung
        durfte das **Lesegate** nicht anfassen. Gemessen als **eine** Stelle, an der der
        PIN-Kopf gesetzt wird — nicht als Vorsatz, sie nicht angefasst zu haben.
        Verifiziert: SWR-101, SWR-049, SWR-053."""
        code = _ohne_kommentare(_quelltext())
        self.assertEqual(code.count(self.PIN_KOPF), 1,
                         f"{self.PIN_KOPF} steht an mehr oder weniger als einer Stelle")
        self.assertIn("pinEl.value", code, "die PIN wird nicht mehr aus dem Feld gelesen")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
