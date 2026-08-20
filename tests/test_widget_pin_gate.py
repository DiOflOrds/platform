"""SWR-160 (projects/p11/T-0013): der Inhalt des Mail-Widgets hinter dem PIN-Lesegate.

⚠ **Eine Zugriffsentscheidung ist kein Layout.** Genau deshalb wurde dieses Ticket in
Sprint 17 von `p11/T-0012` (Deep-Links) abgetrennt und dreimal nicht als Nebenprodukt
eines anderen Laufs erledigt. Bei der **vierten** Berührung gilt die Regel dieses Hauses:
gebaut oder geschnitten.

⚠⚠ **Die tragende Zusicherung ist die Gegenprobe, nicht der glückliche Fall.** Ohne PIN
darf **nichts** durchkommen — nicht „weniger". Ein Gate, das eine gekürzte Fassung
liefert, ist ein Leck mit gutem Gewissen.
"""
import ast
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import widgets  # noqa: E402

WURZEL = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEAM = "team-mail"

DIGEST = """# Digest

## Braucht Blick oder Reaktion

1. PayPal-Rechnung offen — https://mail.google.com/mail/u/0/#inbox/rfc822msgid:abc
2. Enpal meldet sich wegen des Termins (kontakt@enpal.de)

## Rechnungen/Zahlungen

Keine direkten Rechnungen.
"""


class WortlautUndZahlTest(unittest.TestCase):
    """SWR-160: dieselbe Rubrik, zwei verschiedene Auskünfte."""

    def test_die_zahl_ist_oeffentlich_der_wortlaut_nicht(self):
        """⚠ Der ganze Bau hängt an dieser Unterscheidung.

        *Die ANZAHL offener Punkte ist eine Kennzahl. Ihr WORTLAUT sind Betreffzeilen,
        Absender und Links.* Wären es dieselbe Auskunft, gäbe es nichts zu sperren — und
        wären es zwei Auswahlregeln, zählte die Kachel andere Punkte, als hinter dem Gate
        stehen.
        """
        self.assertEqual(widgets.reaktionspunkte(DIGEST), 2)
        punkte = widgets.reaktionspunkte_text(DIGEST)
        self.assertEqual(len(punkte), 2)
        self.assertEqual(len(punkte), widgets.reaktionspunkte(DIGEST),
                         "Zahl und Wortlaut müssen aus DERSELBEN Auswahl kommen")
        self.assertIn("PayPal", punkte[0])

    def test_fehlende_rubrik_ist_None_und_nicht_die_leere_liste(self):
        """SWR-108/135 eine Etage weiter: „nichts zu tun" ist nicht „nicht erhoben".

        `[]` hiesse, der Digest habe die Frage beantwortet und die Antwort sei leer.
        """
        self.assertIsNone(widgets.reaktionspunkte_text("# Digest\n\nkeine Rubrik hier\n"))
        self.assertEqual(widgets.reaktionspunkte_text("## Braucht Blick oder Reaktion\n"), [])


class GateSitztAmEndpunktTest(unittest.TestCase):
    """DoD 3: *ein Gate, das erst in der Anzeige greift, ist keines.*"""

    def _server_baum(self):
        pfad = os.path.join(os.path.dirname(__file__), "..", "backend", "server.py")
        with open(pfad, encoding="utf-8") as f:
            return ast.parse(f.read())

    def test_widget_inhalt_wird_NUR_im_pin_zweig_aufgerufen(self):
        """⚠⚠ Gemessen über den Syntaxbaum und nicht im Text.

        Eine Textsuche hätte diesen Namen auch in einem Kommentar gefunden — der
        Fehlalarm, der in diesem Haus fünfmal aufgetreten ist (SWR-128/134/157). Gezählt
        wird, wie viele Aufrufe von `widgets.widget_inhalt` **außerhalb** des
        `if pfad.startswith("/api/team")`-Zweiges liegen. Die Zahl ist **0** und darf es
        bleiben: ein zweiter Aufrufer wäre eine zweite Zugriffsregel (B033) an der
        empfindlichsten Stelle des Systems.
        """
        baum = self._server_baum()
        # ⚠ Gesucht ist der ZWEIG, nicht jede Zeile, die den Pfad nennt: `startswith`
        # ist die Klammer um alle `/api/team/...`-Routen. Die erste Fassung dieser
        # Zusicherung zaehlte 8 statt 1, weil sie die inneren Gleichheitsvergleiche
        # mitzaehlte — sie haette einen zweiten Zweig also nie von einer weiteren Route
        # unterscheiden koennen.
        gate = [n for n in ast.walk(baum)
                if isinstance(n, ast.If) and isinstance(n.test, ast.Call)
                and isinstance(n.test.func, ast.Attribute)
                and n.test.func.attr == "startswith"
                and any(isinstance(a, ast.Constant) and a.value == "/api/team"
                        for a in n.test.args)]
        self.assertEqual(len(gate), 1,
                         "genau EIN PIN-Zweig — zwei wären zwei Zugriffsregeln")
        von, bis = gate[0].lineno, max(getattr(k, "lineno", 0) for k in ast.walk(gate[0]))

        aufrufe = [n for n in ast.walk(baum)
                   if isinstance(n, ast.Attribute) and n.attr == "widget_inhalt"]
        self.assertGreaterEqual(len(aufrufe), 1,
                                "die Prüfung muss ihren eigenen Gegenstand FINDEN — "
                                "eine Zählung auf 0 ohne Gegenstand ist von einer "
                                "kaputten Prüfung nicht zu unterscheiden")
        draussen = [n.lineno for n in aufrufe if not von <= n.lineno <= bis]
        self.assertEqual(draussen, [],
                         f"widget_inhalt außerhalb des PIN-Zweigs (Zeilen {draussen})")

    def test_die_ungeschuetzte_widget_route_ruft_ihn_NICHT(self):
        """Die Gegenrichtung, und ohne sie belegt der Rest nichts.

        `/api/widgets` ist bewusst PIN-frei (die Kachel soll sichtbar bleiben). Genau
        deshalb darf sie den Inhalt nicht holen.
        """
        quelle = ast.dump(ast.parse(open(
            os.path.join(os.path.dirname(__file__), "..", "backend", "widgets.py"),
            encoding="utf-8").read()))
        self.assertIn("widget_inhalt", quelle)
        aufrufer = [n for n in ast.walk(ast.parse(open(
            os.path.join(os.path.dirname(__file__), "..", "backend", "widgets.py"),
            encoding="utf-8").read()))
            if isinstance(n, ast.FunctionDef) and n.name in ("widgets", "post_widget")]
        for fn in aufrufer:
            self.assertNotIn("widget_inhalt", ast.dump(fn),
                             f"{fn.name} darf den gesperrten Inhalt nicht anfassen")


class KachelBleibtSichtbarTest(unittest.TestCase):
    """DoD 2: ⚠ die Kachel verschwindet ohne PIN NICHT — nur ihr Inhalt."""

    def setUp(self):
        self.payload = widgets.widgets(WURZEL)
        self.mail = next((w for w in self.payload["widgets"] if w["projekt"] == TEAM), None)
        if self.mail is None:
            self.skipTest("kein Mail-Widget im Bestand")

    def test_die_kachel_steht_ohne_pin_da_und_SAGT_dass_sie_gesperrt_ist(self):
        """*Eine Kachel, die ohne PIN verschwindet, verrät nichts und behauptet dabei, es
        gäbe hier nichts* — dieselbe Verwechslung wie „keine Daten" gegen „0".

        Sie muss also beides tun: dastehen **und** sagen, dass ihr Inhalt woanders liegt.
        Ein stiller gesperrter Inhalt ist von einem nicht vorhandenen nicht zu
        unterscheiden.
        """
        self.assertTrue(self.mail["inhalt_gesperrt"])
        self.assertEqual(self.mail["inhalt_route"], "/api/team/widget-inhalt")
        self.assertTrue(self.mail["eintraege"], "die Kachel behält ihre Takteinträge")

    def test_die_sperre_ist_KEIN_vierter_zustand(self):
        """⚠ Der Vertrag kennt drei Zustände und keinen vierten (SWR-096/108).

        Eine Sperre ist eine **Zugriffsregel** und kein Datenzustand; beide in ein
        Vokabular zu werfen hiesse, „keine Daten" und „nicht für dich" zu verwechseln —
        und jeder Leser des Vertrags müsste ein Wort lernen, das er nicht kennt.
        """
        erlaubt = {widgets.ZUSTAND_WERT, widgets.ZUSTAND_ECHTE_NULL,
                   widgets.ZUSTAND_NICHT_GELIEFERT}
        for e in self.mail["eintraege"]:
            self.assertIn(e["zustand"], erlaubt)
            self.assertNotIn("gesperrt", e["zustand"])

    def test_OHNE_pin_kommt_NICHTS_durch_nicht_weniger(self):
        """⚠⚠ Die Gegenprobe mit Datenschutzgewicht (DoD 4).

        Geprüft wird gegen Zeichenfolgen, die im **echten** Digest nachweislich
        vorkommen. Ein Gate, das eine gekürzte Fassung durchlässt, wäre grün, wenn man
        nur „weniger" prüfte.
        """
        roh = repr(self.payload)
        for verboten in ("mail.google.com", "rfc822msgid", "@gmail.com", "PayPal",
                         "Enpal", "Vedaco"):
            self.assertNotIn(verboten, roh,
                             f"Mailinhalt '{verboten}' steht in der PIN-freien Route")


class InhaltHinterDemGateTest(unittest.TestCase):
    """DoD 1/4: mit PIN genau das Erwartete — und der Grund, wenn es nichts gibt."""

    def test_mit_freigabe_kommt_der_wortlaut(self):
        inhalt = widgets.widget_inhalt(WURZEL, TEAM, "tag")
        if inhalt is None:
            self.skipTest("kein Mail-Widget im Bestand")
        self.assertEqual(inhalt["projekt"], TEAM)
        if inhalt["punkte"] is None:
            self.assertTrue(inhalt["grund"], "ohne Punkte MUSS ein Grund dastehen")
        else:
            self.assertGreaterEqual(len(inhalt["punkte"]), 1)

    def test_team_ohne_widget_liefert_None_und_nicht_eine_leere_huelle(self):
        """Ein Team ohne `widget.yaml` hat kein Widget — auch keinen leeren Inhalt.

        Eine leere Hülle hinter dem Gate behauptete, dort sei etwas, das man mit der
        richtigen PIN sähe.
        """
        self.assertIsNone(widgets.widget_inhalt(WURZEL, "team-dashboard", "tag"))

    def test_unbekannter_takt_ist_KEIN_stiller_rueckfall_auf_den_juengsten(self):
        """⚠ Sonst zeigte das Gate einen anderen Digest als den verlangten.

        Der Aufrufer bekäme Inhalt, hielte ihn für den angefragten und läge falsch —
        dieselbe Falle wie das stillschweigende Zuordnen eines Digests ohne Takt (B038).
        """
        inhalt = widgets.widget_inhalt(WURZEL, TEAM, "jahrhundert")
        if inhalt is None:
            self.skipTest("kein Mail-Widget im Bestand")
        self.assertIsNone(inhalt["punkte"])
        self.assertIn("noch keiner", inhalt["grund"])


if __name__ == "__main__":
    unittest.main()
