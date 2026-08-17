# -*- coding: utf-8 -*-
"""SWR-128 (ADR-008, projects/p12/T-0004): die JS-Teststrecke und ihre Meldung.

Die Zusicherung dieses Moduls ist **nicht** „JS-Tests laufen". Sie lautet: *der Zustand
der JS-Teststrecke ist am Ende jedes Laufs sichtbar* — ob sie lief, ob sie gruen war, und
wenn sie nicht lief, warum nicht. Genau diese Sichtbarkeit hat fuenf Sprints lang gefehlt:
die Organisation hatte 741 Python-Tests und null JS-Tests, und keine Zeile sagte es.

Deshalb ist der wichtigste Test hier der ueber den **uebersprungenen** Fall.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PLATFORM, "scripts"))
import js_tests  # noqa: E402

WURZEL = os.path.dirname(PLATFORM)


class Teststrecke(unittest.TestCase):

    def test_die_testdateien_werden_gefunden(self):
        dateien = js_tests.testdateien(WURZEL)
        self.assertTrue(dateien, "keine JS-Testdatei gefunden — die Strecke ist leer")
        self.assertTrue(all(d.endswith(".cjs") or d.endswith(".js") for d in dateien))

    def test_ohne_verzeichnis_keine_dateien_und_kein_fehler(self):
        with tempfile.TemporaryDirectory() as leer:
            self.assertEqual(js_tests.testdateien(leer), [])

    @unittest.skipUnless(shutil.which("node"), "node nicht im PATH")
    def test_die_strecke_laeuft_gruen_und_zaehlt_ihre_tests(self):
        erg = js_tests.lauf(WURZEL)
        self.assertEqual(erg["zustand"], "ok", erg["meldung"])
        self.assertGreater(erg["tests"], 0, "eine gruene Strecke ohne Tests ist keine Strecke")
        self.assertEqual(erg["fehler"], 0)

    def test_ohne_node_ist_der_zustand_uebersprungen_und_NICHT_ok(self):
        """⚠ Der Kern. `uebersprungen` darf nie als `ok` durchgehen.

        Die Gegenprobe zu genau dem Fehler, den SWR-114 und SWR-122 beschreiben: eine
        Pruefung, die nicht lief, ist von einer gruenen nicht zu unterscheiden, sobald
        beide dasselbe melden.
        """
        echtes_which = js_tests.shutil.which
        js_tests.shutil.which = lambda name: None
        try:
            erg = js_tests.lauf(WURZEL)
        finally:
            js_tests.shutil.which = echtes_which
        self.assertEqual(erg["zustand"], "uebersprungen")
        self.assertNotEqual(erg["zustand"], "ok")
        self.assertIn("UEBERSPRUNGEN", erg["meldung"])
        self.assertIn("node", erg["meldung"])
        self.assertIn("p12/T-0007", erg["meldung"],
                      "die Meldung nennt die Entscheidung nicht — dann weiss der "
                      "Leser nicht, woran der Zustand haengt")
        # SWR-131: die Meldung nennt die GETROFFENE Entscheidung, nicht mehr eine Frist.
        # ⚠ Gegenprobe gegen den Zustand vom 2026-08-17: ein Verweis auf einen offenen
        # DR mit Frist 24.08. schickt den Leser nach der Entscheidung ins Leere und
        # laesst ihn eine Handlung erwarten, die es nicht gibt.
        self.assertIn("B-node-optional", erg["meldung"])
        self.assertNotIn("2026-08-24", erg["meldung"])

    def test_leere_strecke_meldet_das_und_gibt_sich_nicht_gruen(self):
        with tempfile.TemporaryDirectory() as leer:
            erg = js_tests.lauf(leer)
        self.assertEqual(erg["zustand"], "uebersprungen")
        self.assertIn("keine Testdateien", erg["meldung"])

    @unittest.skipUnless(shutil.which("node"), "node nicht im PATH")
    def test_eine_rote_strecke_ist_rot_und_nennt_den_fall(self):
        """Gegenprobe: die Strecke muss ueberhaupt rot werden koennen."""
        with tempfile.TemporaryDirectory() as tmp:
            verz = os.path.join(tmp, "platform", "tests", "js")
            os.makedirs(verz)
            with open(os.path.join(verz, "rot.test.cjs"), "w", encoding="utf-8") as f:
                f.write('const test=require("node:test");const a=require("node:assert");\n'
                        'test("absichtlich rot", () => { a.strictEqual(1, 2); });\n')
            erg = js_tests.lauf(tmp)
        self.assertEqual(erg["zustand"], "rot")
        self.assertGreaterEqual(erg["fehler"], 1)
        self.assertIn("absichtlich rot", erg["meldung"])


class PreflightMeldetDieStrecke(unittest.TestCase):
    """Die Zeile muss im Preflight stehen — sonst liest sie niemand (SWR-122)."""

    def test_preflight_druckt_eine_js_zeile_auch_bei_skip_tests(self):
        erg = subprocess.run([sys.executable, os.path.join(PLATFORM, "scripts", "preflight.py"),
                              "--repos", WURZEL, "--skip-tests", "--keep-locks"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=600)
        self.assertIn("JS-Tests", erg.stdout + erg.stderr,
                      "Preflight schweigt ueber die JS-Teststrecke")


if __name__ == "__main__":
    unittest.main()


class RegelnBleibenOhneDOM(unittest.TestCase):
    """ADR-008 „Konsequenzen": eine Regel, die nach `app.js` zurueckwandert, ist wieder
    ungeprueft. Sprint 11 hat dreimal gemessen, was eine aufgeschriebene Regel ohne
    Pruefung wert ist — deshalb steht die Pruefung hier und nicht nur im ADR.
    """

    REGELN = os.path.join(PLATFORM, "backend", "static", "regeln.js")
    APP = os.path.join(PLATFORM, "backend", "static", "app.js")
    VERBOTEN = ("document.", "window.addEventListener", "fetch(", "location.",
                "sessionStorage", "localStorage", "XMLHttpRequest")

    def _quelle(self, pfad):
        return open(pfad, encoding="utf-8").read()

    @staticmethod
    def _ohne_kommentare(text):
        """Die Regel gilt fuer Code, nicht fuer Prosa.

        `regeln.js` erklaert in seinem Kopf, warum es `document.createElement` NICHT
        anfasst — eine Pruefung, die daran anschlaegt, bestrafte die Begruendung. Erster
        Entwurf dieses Tests tat genau das (gemessen, nicht vermutet): er wurde rot an
        einer Kommentarzeile.
        """
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        return "\n".join(re.sub(r"//.*$", "", z) for z in text.splitlines())

    def test_regeln_js_fasst_kein_dom_und_kein_netz_an(self):
        text = self._ohne_kommentare(self._quelle(self.REGELN))
        # Die Zuweisung am Dateiende ist der einzige zugelassene Kontakt zum Browser:
        # sie stellt das Modul bereit und liest nichts.
        text = text.replace('else if (typeof window === "object") { window.Regeln = Regeln; }', "")
        treffer = [w for w in self.VERBOTEN if w in text]
        self.assertEqual(treffer, [], "regeln.js beruehrt Browser-Umgebung: " + ", ".join(treffer))

    def test_die_pruefung_wuerde_einen_echten_dom_zugriff_finden(self):
        """Gegenprobe: die Nachsicht gegenueber Kommentaren darf nicht alles durchlassen."""
        code = self._ohne_kommentare('// document.createElement ist hier nur Prosa\n'
                                     'var x = document.getElementById("a");\n')
        self.assertIn("document.", code)

    def test_app_js_liest_die_regeln_statt_sie_zu_wiederholen(self):
        """Die drei Entscheidungen des Briefverlaufs kommen aus `Regeln`, nicht aus app.js."""
        text = self._quelle(self.APP)
        for name in ("Regeln.sortiereBriefe", "Regeln.verlauf", "Regeln.istWiederOffen",
                     "Regeln.briefIdAusFehler"):
            self.assertIn(name, text, f"app.js benutzt {name} nicht (mehr) — "
                                      f"die Regel ist zurueckgewandert und damit ungeprueft")

    def test_index_html_laedt_die_regeln_vor_app_js(self):
        """Sonst ist `Regeln` beim ersten Aufruf undefiniert — und die Ansicht bleibt leer."""
        html = self._quelle(os.path.join(PLATFORM, "backend", "static", "index.html"))
        # Verglichen werden die <script>-Zeilen, nicht die Erwaehnungen: der Kommentar
        # ueber dem Einbinden nennt `app.js` und stuende sonst gegen seine eigene Regel.
        self.assertIn('<script src="regeln.js">', html)
        self.assertLess(html.index('<script src="regeln.js">'),
                        html.index('<script src="app.js">'))


class JsNachweisImBestand(unittest.TestCase):
    """SWR-129, SWR-130: der Nachweis der beiden HMI-Regeln — und warum er hier steht.

    Die Traceability-Matrix liest SWR-Kennungen aus **Python**-Docstrings. Eine Regel,
    die nur eine JS-Datei prueft, waere darin eine Luecke — und eine Luecke, die man mit
    einem Satz im Verification-Feld wegerklaert, ist genau B027/B038, was
    `projects/p12/T-0004` fuer diesen Fall ausdruecklich verbietet.

    Diese Klasse ist deshalb kein Ersatznachweis, sondern eine **Bruecke**: sie laesst die
    JS-Strecke laufen und verlangt, dass die namentlich genannten Zusicherungen darin
    gruen sind. Faellt eine davon weg oder wird sie umbenannt, wird dieser Test rot — die
    Matrix kann also nicht auf eine Zusicherung zeigen, die es nicht mehr gibt.
    """

    ERWARTET_129 = [
        "Erstbeitrag ist immer vom Menschen",
        "ein zweiter Beitrag des Menschen unter ANDEREM Namen ist Mensch",
        "'Vollzug (Team, 2026-08-16, Routine-Session)' ist Team",
        "istWiederOffen: offen MIT Team-Antwort ist die Nachfrage des Menschen",
        "ein frischer Brief ist offen und NICHT wieder-offen",
        "ein beantworteter Brief ist nicht wieder-offen",
        "verlauf bleibt lesbar, wenn die Antwort kein beitraege-Feld hat",
        "sortiereBriefe dreht die Anzeige um und laesst die Eingabe unangetastet",
    ]
    ERWARTET_130 = [
        "briefIdAusFehler liest die Kennung aus der SWR-121-Meldung",
        "ohne Kennung wird keine erfunden",
        "eine Ticket-Kennung ist keine Brief-Kennung",
    ]

    def test_die_zusicherungen_stehen_in_der_js_strecke(self):
        """Ohne node pruefbar: die Faelle sind da, auch wenn sie gerade nicht laufen."""
        quelle = open(os.path.join(WURZEL, "platform", "tests", "js", "regeln.test.cjs"),
                      encoding="utf-8").read()
        for name in self.ERWARTET_129 + self.ERWARTET_130:
            self.assertIn(name, quelle, f"Zusicherung verschwunden: {name}")

    @unittest.skipUnless(shutil.which("node"), "node nicht im PATH")
    def test_die_zusicherungen_sind_gruen(self):
        datei = os.path.join(WURZEL, "platform", "tests", "js", "regeln.test.cjs")
        erg = subprocess.run(["node", "--test", datei], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=120)
        ausgabe = erg.stdout + erg.stderr
        gruen = [z for z in ausgabe.splitlines() if z.startswith("ok ")]
        for name in self.ERWARTET_129 + self.ERWARTET_130:
            self.assertTrue(any(name in z for z in gruen), f"nicht gruen: {name}")
        self.assertNotIn("\nnot ok ", "\n" + ausgabe)
