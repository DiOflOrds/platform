"""Dashboard-Konfiguration mit Persistenz (SWR-151, projects/p11/T-0011).

⚠⚠ **Die bestimmende Frage dieses Tickets war nicht „wie speichern", sondern „warum hier
und bei SWR-133 nicht".** Der Faltzustand der Cockpit-Gruppen ist ausdrücklich **flüchtig**,
und die Begründung steht seit Sprint 13 im Code:

> *„Ein Zustand, der einen Neustart überlebt, müsste beim Wiedersehen erklärt werden —
> sonst fehlt eine Gruppe und niemand weiß, warum."*

Zwei benachbarte Ansichten, eine speichert und eine nicht — **wer das nicht begründet, hat
einen Widerspruch gebaut und ihn Absicht genannt** (so steht es wörtlich in der DoD).

Die Auflösung ist nicht „hier ist es anders", sondern:

> **Falten ist ein Griff beim Lesen. Eine Auswahl ist eine Aussage. Der Einwand aus
> SWR-133 verbietet die Persistenz nicht — er verlangt die Erklärung.**

Diese Datei prüft, dass die Erklärung **existiert und erreichbar ist** und dass der
Speicherweg dort bleibt, wo ADR-003 ihn zulässt: **im Browser, nicht im Repo.**

⚠ Das **Verhalten** der Regeln prüft `platform/tests/js/dashboard_konfig.test.cjs`
(15 Zusicherungen, ohne DOM). Hier steht, was eine Textprüfung besser kann als ein
Verhaltenstest: dass ein Weg **nicht** existiert.

Verifiziert: SWR-151.

Ausführung: python -m unittest discover platform/tests
"""
import os
import re
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
_APP_JS = os.path.join(_HIER, "..", "backend", "static", "app.js")
_REGELN_JS = os.path.join(_HIER, "..", "backend", "static", "regeln.js")
_SERVER_PY = os.path.join(_HIER, "..", "backend", "server.py")
_JS_TEST = os.path.join(_HIER, "js", "dashboard_konfig.test.cjs")

#: Der eine Schlüssel im Browser-Speicher.
SCHLUESSEL = "mc_dashboard_widgets"


def _text(pfad):
    with open(pfad, encoding="utf-8") as f:
        return f.read()


def _ohne_kommentare(text):
    """Block- und Zeilenkommentare entfernt — die Lehre aus fünf Fehlalarmen in zwei Tagen:
    eine Textsuche kann eine Erklärung nicht von ihrem Gegenstand unterscheiden."""
    ohne = re.sub(r"(?s)/\*.*?\*/", "", text)
    return "\n".join(re.sub(r"//.*$", "", z) for z in ohne.splitlines())


class KeinSchreibwegZumServerTest(unittest.TestCase):
    """Verifiziert: SWR-151 — DoD 4 (ADR-003/ADR-007)."""

    def test_die_konfiguration_geht_nirgends_zum_server(self):
        """⚠ DoD 4 verlangt: **kein Schreibweg des Menschen, der den Arbeitsstand des Teams
        fortschreibt.** Die Ansichtsvorliebe eines Menschen an einem Gerät ist keine Aussage
        über die Organisation; im Repo wäre sie ein versionierter Teamartefakt.

        ⚠ Geprüft wird die **Abwesenheit** eines Weges — genau das, was ein Verhaltenstest
        nicht kann: er zeigt, dass etwas geht, nie dass nichts anderes geht.
        Verifiziert: SWR-151."""
        server = _text(_SERVER_PY)
        for weg in ("/api/dashboard/konfig", "/api/widgets/konfig", "/api/konfig"):
            self.assertNotIn(weg, server, f"{weg!r} ist eine Route geworden")

    def test_der_speicherweg_liegt_im_browser_und_nur_dort(self):
        """⚠ Ein zweiter Speicherort wäre zwei Aussagen über dieselbe Auswahl. Gemessen
        als **je eine** Stelle für Lesen und Schreiben. Verifiziert: SWR-151."""
        code = _ohne_kommentare(_text(_APP_JS))
        self.assertEqual(len(re.findall(r"localStorage\.getItem\(", code)), 1)
        self.assertEqual(len(re.findall(r"localStorage\.setItem\(", code)), 1)
        # Der Schlüssel steht in `regeln.js` und wird in `app.js` nur benutzt.
        self.assertIn(SCHLUESSEL, _text(_REGELN_JS))
        self.assertNotIn(SCHLUESSEL, code,
                         "app.js trägt den Speicherschlüssel selbst — dann gibt es ihn "
                         "zweimal, und einer altert")

    def test_der_speicherzugriff_ist_gegen_privatmodus_abgesichert(self):
        """⚠ `localStorage` wirft beim **Zugriff**, nicht beim Lesen — im Privatmodus und
        bei abgeschaltetem Speicher. Ohne `try` wäre das Dashboard dort weiß: *eine Ansicht,
        die an ihrer eigenen Voreinstellung stirbt, ist schlimmer als eine ohne
        Voreinstellung.* Verifiziert: SWR-151."""
        code = _ohne_kommentare(_text(_APP_JS))
        for m in re.finditer(r"localStorage\.(get|set)Item\(", code):
            davor = code[max(0, m.start() - 220):m.start()]
            self.assertIn("try", davor,
                          "ein Speicherzugriff ohne `try` — der Privatmodus wirft dort")


class UnterschiedZuSWR133Test(unittest.TestCase):
    """Verifiziert: SWR-151 — DoD 2 (der Unterschied ist zu begründen, nicht zu behaupten)."""

    def test_der_faltzustand_ist_weiterhin_fluechtig(self):
        """⚠ Die eine Hälfte der Begründung ist eine **Messung** und keine Erinnerung: der
        Faltzustand darf durch dieses Ticket nicht mit persistent geworden sein. Wäre er es,
        gäbe es den Widerspruch nicht mehr — und die Begründung wäre gegenstandslos, ohne
        dass jemand sie zurückgenommen hat. Verifiziert: SWR-151, SWR-133."""
        code = _ohne_kommentare(_text(_APP_JS))
        m = re.search(r"var faltung = \{\};", code)
        self.assertIsNotNone(m, "der Faltzustand ist keine Modulvariable mehr")
        self.assertNotRegex(code, r"(local|session)Storage[^\n]*faltung")
        self.assertNotRegex(code, r"faltung[^\n]*(local|session)Storage")

    def test_die_begruendung_steht_am_code_und_nicht_nur_im_ticket(self):
        """⚠⚠ Genau der Fehler, den `L-2026-08-17ag` beschreibt und den `promt-team/T-0007`
        an seiner eigenen DoD gefunden hat: **ein Satz, den keine Prüfung liest, altert
        lautlos.** Die DoD verlangt eine Begründung; sie steht deshalb an der Stelle, an der
        gespeichert wird, und diese Zusicherung hält sie dort fest.

        ⚠ Was hier NICHT geprüft wird: ob die Begründung **gut** ist. Das kann keine
        Textsuche, und so zu tun, als könnte sie es, wäre schlimmer als die Lücke.
        Verifiziert: SWR-151."""
        roh = _text(_APP_JS)
        m = re.search(r"(?s)(.{1500})var dashboardKonfig", roh)
        self.assertIsNotNone(m, "`dashboardKonfig` ist nicht auffindbar")
        kopf = m.group(1)
        self.assertIn("SWR-133", kopf,
                      "der Unterschied zum Faltzustand ist am Code nicht benannt")

    def test_was_ausgeblendet_ist_wird_erklaert_und_nicht_nur_gezaehlt(self):
        """⚠⚠ Die **Auflage**, unter der SWR-133 die Persistenz überhaupt zulässt. Der Satz
        steht in `regeln.js` (prüfbar ohne DOM), und die Ansicht setzt ihn in den **Kopf** —
        nicht in ein Menü, das man aufklappen muss. Verifiziert: SWR-151."""
        regeln = _ohne_kommentare(_text(_REGELN_JS))
        self.assertIn("function verstecktSatz(", regeln)
        self.assertIn("deine Auswahl", regeln,
                      "der Satz nennt die Ursache nicht — dann bleibt offen, ob das "
                      "System oder der Mensch etwas weggenommen hat")
        code = _ohne_kommentare(_text(_APP_JS))
        self.assertIn("Regeln.verstecktSatz(", code)
        # Und ein Weg zurück, ohne die Auswahl von Hand aufzudröseln.
        self.assertIn("Alle zeigen", code)


class RegelnOhneDomTest(unittest.TestCase):
    """Verifiziert: SWR-151 — ADR-008 (Entscheidungen in `regeln.js`, Zeichnen in `app.js`)."""

    def test_die_entscheidungen_liegen_in_regeln_js(self):
        """Verifiziert: SWR-151."""
        regeln = _ohne_kommentare(_text(_REGELN_JS))
        for f in ("konfigLesen", "konfigSchreiben", "widgetsOrdnen", "konfigUmschalten",
                  "konfigVerschieben", "widgetSchluessel", "verstecktSatz"):
            self.assertIn(f"function {f}(", regeln, f"{f} fehlt in regeln.js")
            self.assertIn(f"{f}: {f}", regeln, f"{f} ist nicht exportiert")

    def test_regeln_js_ruehrt_kein_element_an(self):
        """⚠ Die Regel von ADR-008, an der neuen Fläche gemessen: was hier steht,
        beantwortet Fragen und zeichnet nicht. Verifiziert: SWR-151."""
        regeln = _ohne_kommentare(_text(_REGELN_JS))
        for verboten in ("document.", "createElement", "appendChild", "localStorage.",
                         "sessionStorage.", "fetch("):
            self.assertNotIn(verboten, regeln, f"{verboten!r} in regeln.js")

    def test_das_verhalten_hat_eine_eigene_teststrecke(self):
        """⚠ Diese Datei prüft Abwesenheiten und Orte. Das **Verhalten** — was bei leerer,
        kaputter und gefüllter Konfiguration herauskommt — steht in der JS-Strecke, und
        diese Zusicherung hält fest, dass es sie gibt.

        ⚠ Sie ist bewusst schwach: sie liest die Datei und führt sie nicht aus. Eine
        Python-Zusicherung, die JS-Tests startet, wäre ein zweiter Aufrufweg neben
        `js_tests.py` (B033). Verifiziert: SWR-151."""
        self.assertTrue(os.path.isfile(_JS_TEST), "die JS-Teststrecke zu SWR-151 fehlt")
        js = _text(_JS_TEST)
        self.assertGreaterEqual(js.count("test("), 12,
                                "weniger Zusicherungen als beim Bau gezählt")
        for pflicht in ("DoD1", "DoD2", "DoD3"):
            self.assertIn(pflicht, js, f"keine Zusicherung nennt {pflicht}")


class AusschlusslisteTest(unittest.TestCase):
    """Verifiziert: SWR-151 — die bestimmende Entscheidung, als Ort statt als Vorsatz."""

    def test_gespeichert_wird_das_versteckte_und_nicht_das_gewaehlte(self):
        """⚠⚠ Bei einer **Auswahlliste** wäre ein Widget, das ein Team neu anbietet, beim
        nächsten Aufruf unsichtbar — und niemand wüsste, dass es existiert.

        > **Eine gespeicherte Auswahl altert gegen einen wachsenden Bestand: sie sagt „zeig
        > diese", und was danach dazukommt, fällt lautlos aus der Ansicht.**

        Gemessen am **Feldnamen** der gespeicherten Struktur: `versteckt`, nicht `sichtbar`.
        Verifiziert: SWR-151."""
        regeln = _ohne_kommentare(_text(_REGELN_JS))
        m = re.search(r"function konfigLeer\(\) \{ return \{(.*?)\}; \}", regeln)
        self.assertIsNotNone(m, "die leere Konfiguration ist nicht auffindbar")
        felder = m.group(1)
        self.assertIn("versteckt", felder)
        self.assertIn("reihenfolge", felder)
        self.assertNotIn("sichtbar", felder,
                         "die Konfiguration speichert eine AUSWAHL — dann verschwindet "
                         "jedes künftige Widget lautlos")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
