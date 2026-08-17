"""SWR-148 (team-mail/T-0004): das erste echte Dashboard-Widget.

Anlass: der Auftraggeber hat am 2026-08-17 gesagt, das Dashboard sei *„an sich das gleiche
wie das cockpit"*. Das ist nach den Regeln dieser Organisation ein **Befund** — zwei
Anzeigen derselben Daten sind B033, und SWR-135 hatte genau das gebaut.

> **Eine Kachel zeigt den Zustand eines Projekts. Ein Widget zeigt das Ergebnis einer
> Arbeit.**

Die teuersten Zusicherungen hier sind die **Unterscheidungen**: „Rubrik fehlt" gegen „null
Punkte", „nicht eingerichtet" gegen „noch keiner erstellt", „kein Widget" gegen „leeres
Widget". Jede davon ist ein Paar, das ohne Test gleich aussieht.
"""
import os
import shutil
import sys
import tempfile
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
from backend import widgets  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(_HIER))


class TaktAusDateinameTest(unittest.TestCase):

    def test_takt_wird_gelesen(self):
        self.assertEqual(widgets.takt_aus_dateiname("2026-08-16-tag-digest.md"), "tag")
        self.assertEqual(widgets.takt_aus_dateiname("2026-08-16-woche-digest.md"), "woche")

    def test_altformat_ohne_takt_wird_KEINEM_takt_zugeschlagen(self):
        """⚠ GEGENPROBE am echten Altfall `2026-08-15-digest.md`.

        Die Datei sagt selbst nichts ueber ihren Takt. Sie als Tagesdigest zu zaehlen waere
        eine Annahme ueber eine Datei (B038) — und der Mensch saehe ein Datum, das fuer
        einen Takt gilt, den niemand behauptet hat.
        """
        self.assertEqual(widgets.takt_aus_dateiname("2026-08-15-digest.md"), "")
        self.assertEqual(widgets.takt_aus_dateiname("irgendwas.md"), "")
        self.assertEqual(widgets.takt_aus_dateiname(""), "")
        self.assertEqual(widgets.takt_aus_dateiname(None), "")


class ReaktionspunkteTest(unittest.TestCase):

    def test_punkte_werden_gezaehlt(self):
        text = ("# Digest\n\n## Auf einen Blick\n\nx\n\n## Braucht Blick oder Reaktion\n\n"
                "1. **Eins.** Text\n2. **Zwei.** Text\n3. **Drei.** Text\n\n"
                "## Rest kompakt\n\n4. hier nicht mehr\n")
        self.assertEqual(widgets.reaktionspunkte(text), 3)

    def test_zaehlung_stoppt_an_der_naechsten_ueberschrift(self):
        """Sonst zaehlte die Rubrik die Punkte aller folgenden Abschnitte mit."""
        text = ("## Braucht Blick oder Reaktion\n\n1. eins\n\n## Rechnungen (5)\n\n"
                "1. a\n2. b\n3. c\n4. d\n5. e\n")
        self.assertEqual(widgets.reaktionspunkte(text), 1)

    def test_fortsetzungszeilen_zaehlen_nicht_mit(self):
        """Der echte Bestand hat mehrzeilige Punkte mit `[Mail oeffnen](...)` darunter."""
        text = ("## Braucht Blick oder Reaktion\n\n"
                "1. **Eins.** Erste Zeile\n   zweite Zeile\n"
                "   [Mail oeffnen](https://example.invalid/x)\n"
                "2. **Zwei.** Text\n")
        self.assertEqual(widgets.reaktionspunkte(text), 2)

    def test_fehlende_rubrik_ist_None_und_nicht_0(self):
        """⚠ Die teuerste Verwechslung dieser Anzeige.

        Ein Digest ohne die Rubrik sagt **nichts** ueber offene Punkte. `0` zu melden hiesse
        „nichts zu tun" behaupten — und der Mensch verliesse sich darauf.
        """
        self.assertIsNone(widgets.reaktionspunkte("# Digest\n\n## Rest kompakt\n\nx\n"))
        self.assertIsNone(widgets.reaktionspunkte(""))
        self.assertIsNone(widgets.reaktionspunkte(None))

    def test_rubrik_ohne_punkte_ist_eine_echte_null(self):
        """Rubrik da, kein Punkt: `0`. Das ist ein Ergebnis, kein Loch."""
        text = ("## Braucht Blick oder Reaktion\n\nDiese Woche nichts.\n\n## Rest\n")
        self.assertEqual(widgets.reaktionspunkte(text), 0)


class ZusageTest(unittest.TestCase):
    """`widget.yaml` — die Zusage des Teams."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.team = os.path.join(self.root, "t")
        os.makedirs(self.team)

    def schreibe(self, text):
        with open(os.path.join(self.team, "widget.yaml"), "w", encoding="utf-8") as f:
            f.write(text)

    def test_ohne_datei_kein_widget(self):
        """⚠ `None`, nicht ein leeres Widget. Ein leeres behauptet einen Ort."""
        self.assertIsNone(widgets.widget_zusage(self.root, "t"))

    def test_hashroute_im_ziel_wird_NICHT_als_kommentar_abgeschnitten(self):
        """⚠ GEGENPROBE zum eigenen ersten Entwurf.

        Der erste Parser schnitt am ersten `#` ab. Das Klickziel eines Widgets ist aber eine
        **Hash-Route** (ADR-005) — daraus wurde ein leerer String, also ein Widget, das
        aussieht wie eines und nirgendwo hinfuehrt. Gefunden am echten `widget.yaml`, nicht
        an einem Modell.
        """
        self.schreibe('id: x\ntitel: "T"\nauftrag: "a"\nziel: "#/team/t"\ntakte: [tag]\n')
        self.assertEqual(widgets.widget_zusage(self.root, "t")["ziel"], "#/team/t")

    def test_echter_kommentar_wird_entfernt(self):
        """Die Gegenrichtung: ein Kommentar hinter Leerraum gilt weiter als Kommentar."""
        self.schreibe("id: x   # das ist ein Kommentar\ntitel: T\nauftrag: a\n"
                      "ziel: #/t\ntakte: [tag]\n")
        z = widgets.widget_zusage(self.root, "t")
        self.assertEqual(z["id"], "x")
        self.assertEqual(z["ziel"], "#/t")

    def test_mehrzeiliger_auftrag_wird_zusammengefuegt(self):
        self.schreibe('id: x\ntitel: T\nauftrag: >-\n  Zeile eins\n  Zeile zwei\n'
                      'ziel: "#/t"\ntakte: [tag, woche]\n')
        z = widgets.widget_zusage(self.root, "t")
        self.assertEqual(z["auftrag"], "Zeile eins Zeile zwei")
        self.assertEqual(z["takte"], ["tag", "woche"])

    def test_ohne_id_kein_widget(self):
        self.schreibe("titel: T\nauftrag: a\n")
        self.assertIsNone(widgets.widget_zusage(self.root, "t"))


class BestandTest(unittest.TestCase):
    """Der ECHTE Bestand — die Lehre aus SWR-128: Attrappen genuegen nicht."""

    # ⚠ EINMAL je Klasse und nicht je Testmethode: `widgets()` laeuft ueber alle
    # entdeckten Repos, und `aggregation.projekte` ruft dabei git. Als `setUp` lief die
    # Klasse in den Zeitausfall — gemessen, nicht vermutet.
    d = None
    w = None

    @classmethod
    def setUpClass(cls):
        if os.path.isdir(os.path.join(WURZEL, "team-mail", "digest")):
            cls.d = widgets.widgets(WURZEL)
            cls.w = cls.d["widgets"][0] if cls.d["widgets"] else None

    def setUp(self):
        if self.d is None:
            self.skipTest("team-mail nicht vorhanden")

    def test_genau_ein_team_bietet_heute_ein_widget_an(self):
        """Der Stand, nicht eine Luecke: nur `team-mail` hat eine `widget.yaml`."""
        self.assertEqual([w["projekt"] for w in self.d["widgets"]], ["team-mail"])

    def test_der_auftrag_ist_belegt(self):
        self.assertTrue(self.w["auftrag"].strip())
        self.assertTrue(self.w["ziel"].startswith("#/"))

    def test_tag_und_woche_liefern_echte_zahlen(self):
        """Gemessen am Bestand: 89 Mails (Tag) und 165 (Woche), je 4 Reaktionspunkte."""
        nach = {e["takt"]: e for e in self.w["eintraege"]}
        self.assertEqual(nach["tag"]["zustand"], widgets.ZUSTAND_WERT)
        self.assertEqual(nach["tag"]["datum"], "2026-08-16")
        self.assertEqual(nach["tag"]["mails"], 89)
        self.assertEqual(nach["woche"]["mails"], 165)
        for takt in ("tag", "woche"):
            self.assertIsNotNone(nach[takt]["reaktion"],
                                 "die Rubrik steht in beiden Digests")

    def test_die_mailzahl_wird_wirklich_gefunden(self):
        """⚠ GEGENPROBE zum eigenen ersten Entwurf.

        Das erste Muster verlangte die Zahl **in Klammern** (`\\((\\d+)\\s*Mail`) und lieferte
        am echten Bestand fuer JEDEN Digest `None` — die Titel lauten
        `… (Tag) — 89 Mail(s)`, die Zahl steht ausserhalb. An einem selbstgebauten Beispiel
        waere das nie aufgefallen.
        """
        for e in self.w["eintraege"]:
            if e["zustand"] == widgets.ZUSTAND_WERT:
                self.assertIsNotNone(e["mails"], f"{e['takt']}: Mailzahl nicht erkannt")

    def test_monat_ist_nicht_geliefert_MIT_grund(self):
        """Der Takt ist eingerichtet, es gibt nur noch keinen — und das steht da."""
        nach = {e["takt"]: e for e in self.w["eintraege"]}
        self.assertEqual(nach["monat"]["zustand"], widgets.ZUSTAND_NICHT_GELIEFERT)
        self.assertIn("noch keiner", nach["monat"]["grund"])
        self.assertIsNone(nach["monat"]["datum"])

    def test_der_digest_ohne_takt_wird_gezaehlt_und_genannt(self):
        """`2026-08-15-digest.md` — gezaehlt, keinem Takt zugeschlagen (SWR-114)."""
        self.assertEqual(self.w["digests_ohne_takt"], 1)

    def test_KEINE_mailinhalte_im_payload(self):
        """⚠⚠ Die Zusicherung mit Datenschutzgewicht.

        Mission Control ist per `mission-control-lan.cmd` auch im LAN erreichbar, und diese
        Route liegt **nicht** hinter dem PIN-Leser (SWR-053). Betreffzeilen, Absender und
        Mail-Links duerfen sie deshalb nicht verlassen. Geprueft wird gegen Zeichenfolgen,
        die im echten Digest nachweislich vorkommen.
        """
        roh = repr(self.d)
        for verboten in ("mail.google.com", "rfc822msgid", "@gmail.com", "PayPal",
                         "Enpal", "Vedaco"):
            self.assertNotIn(verboten, roh,
                             f"Mailinhalt '{verboten}' steht im Dashboard-Payload")

    def test_der_takt_name_stimmt_mit_dem_werkzeug_des_teams_ueberein(self):
        """⚠ Die eine bewusste Doppelung dieser Anforderung — hier gehalten.

        `_TAKT_ZAHL` ist eine zweite Fassung von `mail_digest.TAKTE`; das Werkzeug liegt
        beim Team und ist von der Plattform nicht importierbar. Weil genau diese Bauart
        SWR-131 gekostet hat, wird sie **gegen das Original gehalten**, sobald es da ist —
        statt sich auf Sorgfalt zu verlassen.
        """
        pfad = os.path.join(WURZEL, "team-mail", "tools", "mail_digest.py")
        if not os.path.isfile(pfad):
            self.skipTest("Werkzeug des Teams nicht vorhanden (darf fehlen)")
        with open(pfad, encoding="utf-8") as f:
            quelle = f.read()
        import ast
        for knoten in ast.walk(ast.parse(quelle)):
            if (isinstance(knoten, ast.Assign)
                    and any(getattr(z, "id", "") == "TAKTE" for z in knoten.targets)):
                self.assertEqual(ast.literal_eval(knoten.value), widgets._TAKT_ZAHL)
                return
        self.fail("mail_digest.TAKTE nicht gefunden — die Doppelung ist ungehalten")


class KeinZweiterErhebungswegTest(unittest.TestCase):
    """SWR-092: das Widget liest ueber `teams.digest_liste`, nicht selbst."""

    def test_ohne_digestliste_bleibt_nichts_uebrig(self):
        if not os.path.isdir(os.path.join(WURZEL, "team-mail")):
            self.skipTest("team-mail nicht vorhanden")
        from backend import teams
        echt = teams.digest_liste
        teams.digest_liste = lambda root, projekt: []
        try:
            w = widgets.post_widget(WURZEL, "team-mail")
        finally:
            teams.digest_liste = echt
        # Das Widget bleibt (die Zusage steht), aber jeder Takt ist nicht_geliefert.
        self.assertIsNotNone(w)
        for e in w["eintraege"]:
            self.assertEqual(e["zustand"], widgets.ZUSTAND_NICHT_GELIEFERT)
            self.assertTrue(e["grund"])


class AnsichtTest(unittest.TestCase):
    """Die Ansicht liest die Regeln — und zeigt die Projektkacheln NICHT mehr."""

    def setUp(self):
        with open(os.path.join(_HIER, "..", "backend", "static", "app.js"),
                  encoding="utf-8") as f:
            self.app = f.read()
        with open(os.path.join(_HIER, "..", "backend", "static", "index.html"),
                  encoding="utf-8") as f:
            self.html = f.read()

    def test_das_dashboard_zeichnet_keine_projektkacheln_mehr(self):
        """⚠⚠ Der Test gegen die Rueckkehr der Dopplung.

        `kompaktKachel` ist in Sprint 17 entfernt worden. Ohne diese Zusicherung koennte die
        Kopie, die der Auftraggeber geruegt hat, im naechsten Lauf zurueckkommen — und sie
        kaeme als Verbesserung daher („das Dashboard zeigt jetzt auch die Projekte").
        """
        self.assertNotIn("function kompaktKachel", self.app)
        self.assertIn("Regeln.widgetZeile", self.app)

    def test_das_ganze_widget_ist_das_klickziel(self):
        """„soll klickbar sein (Touchscreen geeignet)" — ein `<a>`, kein Link im Text."""
        stelle = self.app.index("function widgetKarte")
        block = self.app[stelle:stelle + 900]
        self.assertIn('el("a"', block)
        self.assertIn("Regeln.TOUCH_MIN_PX", block)

    def test_die_touchflaeche_steht_nicht_zweimal_im_widget_css(self):
        """B033: die Zahl kommt aus `regeln.js`, nicht zusaetzlich als Literal ins CSS.

        ⚠ Die erste Fassung dieses Tests verbot `min-height:44px` in der **ganzen** Datei
        und wurde an einer **richtigen** Nachbarregel rot: `.knopf` traegt sie seit einem
        frueheren Sprint fuer die Handy-Ansicht. **Vierter Fehlalarm derselben Art an einem
        Tag** — nach dem Kommentar in SWR-128, dem Literal in `test_org_kopfblock` und dem
        Wort „commit" in `test_git_schreibweg`.

        > **Eine Pruefung, die ueber die ganze Datei sucht, prueft die ganze Datei — auch
        > die Teile, die sie nicht meint.**

        Gesucht wird deshalb nur in den `.widget`-Regeln.
        """
        anfang = self.html.index(".widget {")
        ende = self.html.index(".karte {")
        widget_css = self.html[anfang:ende].replace(" ", "")
        self.assertNotIn("min-height:44px", widget_css)
        # Gegenprobe: die Nachbarregel darf sie weiterhin tragen — sonst haette der
        # engere Test nur den Fehlalarm verschoben statt ihn zu verstehen.
        self.assertIn("min-height:44px", self.html.replace(" ", ""))

    def test_touch_rueckmeldung_ist_vorhanden(self):
        """Auf einem Touchscreen gibt es kein Hover — ohne `:active` weiss der Finger
        nicht, ob er getroffen hat."""
        self.assertIn(".widget:active", self.html)
        self.assertIn("pointer: coarse", self.html)

    def test_der_auftrag_wird_angezeigt(self):
        self.assertIn('"class": "auftrag"', self.app)

    def test_unvollstaendige_widgets_werden_gemeldet_nicht_uebergangen(self):
        """SWR-114: ein stiller Ausschluss ist von „gibt es nicht" nicht zu unterscheiden."""
        self.assertIn("Regeln.widgetMaengel", self.app)

    def test_der_leere_fall_wird_benannt(self):
        self.assertIn("kein Ladefehler", self.app)


if __name__ == "__main__":
    unittest.main()
