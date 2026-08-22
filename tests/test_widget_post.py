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
        """SWR-157 (platform/T-0024): Zahlen ja — eine **Momentaufnahme** nein.

        ⚠⚠ Bis Sprint 22 stand hier `datum == "2026-08-16"`, `mails == 89`,
        `mails == 165`. Am 2026-08-17 um **22:22** — vier Minuten nach dem
        Abschlussbericht von Sprint 20 — ist ein neuer Digest entstanden, und die
        Zusicherung war ab da rot. **Drei Tage** hat es niemand gesehen.

        > **Ein Test gegen den echten Bestand prüft mehr als eine Attrappe — aber wenn
        > er eine Momentaufnahme festschreibt, prüft er ab morgen die Uhr statt den
        > Code.**

        Geblieben ist, was eine Aussage **über den Code** ist: die Rubriken werden
        erkannt, die Zahl wird gefunden, der Zustand stimmt. Weggefallen ist der
        Wortlaut des Tages. ⚠ Das Datum ist **nicht** hochgezählt worden — das hätte
        den Befund nur bis zum nächsten Digest verschoben.
        """
        nach = {e["takt"]: e for e in self.w["eintraege"]}
        for takt in ("tag", "woche"):
            self.assertEqual(nach[takt]["zustand"], widgets.ZUSTAND_WERT, takt)
            self.assertIsNotNone(nach[takt]["mails"], takt)
            self.assertGreaterEqual(nach[takt]["mails"], 1,
                                    "%s: ein Digest ohne Mails wäre keiner" % takt)
            self.assertIsNotNone(nach[takt]["reaktion"],
                                 "die Rubrik steht in beiden Digests")

    def test_der_juengste_tages_digest_ist_wirklich_der_juengste(self):
        """SWR-157: die **Auswahl** ist die Zusicherung, nicht der ausgewählte Tag.

        Das Datum kommt hier aus dem **Verzeichnis** und nicht aus dem Quelltext. Damit
        wächst der Test mit dem Bestand mit, statt an ihm zu zerbrechen — und er prüft
        genau das, was `post_widget` tut: das jüngste Vorkommen je Takt nehmen.
        """
        verz = os.path.join(WURZEL, "team-mail", "digest")
        nach = {e["takt"]: e for e in self.w["eintraege"]}
        for takt in ("tag", "woche"):
            daten = sorted(n[:10] for n in os.listdir(verz)
                           if n.endswith("-%s-digest.md" % takt))
            self.assertTrue(daten, "kein %s-Digest im Bestand" % takt)
            self.assertEqual(nach[takt]["datum"], daten[-1], takt)

    def test_die_digestliste_liefert_die_neuesten_zuerst(self):
        """⚠ Die **unausgesprochene** Annahme von `post_widget`, jetzt ausgesprochen.

        Der Kommentar dort sagt: *„`digest_liste` liefert neueste zuerst — das erste
        Vorkommen ist damit das jüngste, und es wird hier nicht ein zweites Mal
        sortiert."* Diese Annahme trug die ganze Auswahl und war von **keiner**
        Zusicherung gedeckt. Ein Kommentar ist keine Prüfung (`L-2026-08-17ag`).
        """
        from backend import teams
        daten = [e["datum"] for e in teams.digest_liste(WURZEL, "team-mail")]
        self.assertTrue(daten)
        self.assertEqual(daten, sorted(daten, reverse=True))

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


class AblaufdatumTest(unittest.TestCase):
    """SWR-157 (platform/T-0024, Frage 3): **wie viele Zusicherungen dieser Bauart gibt
    es?** — die Zählung, die vor der Reparatur stand, als dauerhafte Prüfung.

    ⚠ **Erst zählen, dann reparieren.** Eine Reparatur je Fundstelle wäre dieselbe
    Annahme noch einmal (dieselbe Auflage wie `platform/T-0022` Frage 2). Gemessen über
    alle 66 Testdateien mit dem Syntaxbaum — nicht mit einer Textsuche, die in dieser
    Organisation schon fünf Fehlalarme an Kommentaren und Nachbarregeln erzeugt hat:

    > **Genau EINE.** Die rote. Drei feste Werte in einer Methode.

    Das ist der beruhigende Teil des Befundes. Der beunruhigende ist, dass die
    Gegenbauart — eine **Schranke** über den echten Bestand
    (`assertGreaterEqual(gepruefte, 41)`) — an **zwei** Stellen längst existierte. Das
    Haus konnte es also, und an dieser einen Stelle hat es das Datum festgeschrieben.

    ⚠ **Was diese Prüfung NICHT leistet, und das gehört dazu:** sie erkennt den
    scharfen Marker — ein ISO-Datum als Literal in einer Methode, die den echten
    Bestand liest. Eine festgeschriebene **Zahl** (89, 165) erkennt sie nicht
    zuverlässig, weil eine Zahl im Testcode tausend legitime Gründe hat. Sie zieht
    also eine Untergrenze und behauptet keine Vollständigkeit.
    """

    WURZELNAMEN = ("WURZEL", "_WURZEL", "ROOT", "_ROOT", "REPOS", "_REPOS")

    def _fundstellen(self):
        import ast
        import re
        treffer = []
        datum = re.compile(r"\d{4}-\d{2}-\d{2}$")

        def nennt_wurzel(knoten):
            return any(isinstance(k, ast.Name) and k.id in self.WURZELNAMEN
                       for k in ast.walk(knoten))

        for name in sorted(os.listdir(_HIER)):
            if not (name.startswith("test_") and name.endswith(".py")):
                continue
            with open(os.path.join(_HIER, name), encoding="utf-8") as f:
                quelle = f.read()
            if not re.search(r"(WURZEL|ROOT|REPOS)\s*=\s*os\.path\.", quelle):
                continue
            baum = ast.parse(quelle)
            for kl in [n for n in ast.walk(baum) if isinstance(n, ast.ClassDef)]:
                vorbereitet = any(
                    nennt_wurzel(m) for m in kl.body
                    if isinstance(m, ast.FunctionDef)
                    and m.name in ("setUp", "setUpClass"))
                for m in [n for n in kl.body if isinstance(n, ast.FunctionDef)
                          and n.name.startswith("test")]:
                    if not (vorbereitet or nennt_wurzel(m)):
                        continue
                    for k in ast.walk(m):
                        if not (isinstance(k, ast.Call)
                                and isinstance(k.func, ast.Attribute)
                                and k.func.attr in ("assertEqual", "assertEquals")):
                            continue
                        for a in k.args[:2]:
                            if (isinstance(a, ast.Constant)
                                    and isinstance(a.value, str)
                                    and datum.match(a.value)):
                                treffer.append("%s:%s %s" % (name, k.lineno, a.value))
        return treffer

    def test_keine_zusicherung_nagelt_ein_datum_an_den_echten_bestand(self):
        """Vor der Reparatur: 1. Danach: 0. Die Zahl ist gemessen, nicht geschätzt."""
        self.assertEqual(self._fundstellen(), [])

    def test_die_pruefung_findet_ihren_eigenen_gegenstand(self):
        """⚠ **Gegenprobe an der Prüfung selbst.** Eine Zählung, die auf 0 steht, ist
        von einer kaputten Zählung nicht zu unterscheiden — genau der Fehlertyp, der
        `L-2026-08-17ai` trägt. Deshalb wird der Fall **hergestellt**: ein Testmodul
        mit exakt der alten Bauart muss gefunden werden.
        """
        verz = tempfile.mkdtemp(prefix="ablaufdatum-")
        self.addCleanup(shutil.rmtree, verz, ignore_errors=True)
        with open(os.path.join(verz, "test_beispiel.py"), "w", encoding="utf-8") as f:
            f.write("import os\n"
                    "WURZEL = os.path.dirname(__file__)\n"
                    "class T:\n"
                    "    def setUp(self):\n"
                    "        self.d = lade(WURZEL)\n"
                    "    def test_x(self):\n"
                    "        self.assertEqual(self.d['datum'], '2026-08-16')\n")
        hier = _HIER
        try:
            globals()["_HIER"] = verz
            self.assertEqual(len(self._fundstellen()), 1)
        finally:
            globals()["_HIER"] = hier


class SichtTakt(unittest.TestCase):
    """Vertrag v2.9 (team-dashboard/T-0001, Brief p0/N-0002): EIN Takt ist sichtbar.

    ⚠⚠ Gemessen am 2026-08-22 am laufenden Renderweg, nicht am Screenshot des
    Auftraggebers: `post_widget(".", "team-mail")` lieferte **3 Eintraege mit 12
    Kacheln** in ein Raster, das fuer EINE Zeitreihe gebaut ist.
    """

    def test_juengster_takt_gewinnt(self):
        """tag vor woche vor monat — der juengste Stand zuerst (Wunsch aus p0/N-0002)."""
        self.assertEqual(widgets._sicht_takt(
            [{"takt": "monat"}, {"takt": "tag"}, {"takt": "woche"}]), "tag")
        self.assertEqual(widgets._sicht_takt([{"takt": "monat"}, {"takt": "woche"}]),
                         "woche")

    def test_nicht_die_reihenfolge_der_zusage(self):
        """⚠ Die Reihenfolge der Liste stammt aus der Zusage und sagt nichts ueber Alter.

        Gegen eine Umsetzung, die einfach `eintraege[0]["takt"]` nimmt, wird das rot.
        """
        self.assertEqual(widgets._sicht_takt([{"takt": "monat"}, {"takt": "tag"}]), "tag")

    def test_leere_liste_gibt_leeren_takt(self):
        """Ein Team ohne versprochenen Takt zeigt nichts — und behauptet nichts."""
        self.assertEqual(widgets._sicht_takt([]), "")

    def test_sicht_takt_kommt_immer_aus_den_eintraegen(self):
        """⚠ Nie ein Takt, den es nicht gibt — sonst entscheidet wieder der Renderer."""
        for eintraege in ([{"takt": "woche"}],
                          [{"takt": "monat"}, {"takt": "woche"}],
                          [{"takt": "tag"}, {"takt": "monat"}]):
            self.assertIn(widgets._sicht_takt(eintraege),
                          [e["takt"] for e in eintraege])

    def test_unbekannter_takt_draengt_sich_nicht_vor(self):
        """Ein Takt ohne Zahl darf nicht durch Zufall der juengste werden."""
        self.assertEqual(widgets._sicht_takt([{"takt": "quartal"}, {"takt": "woche"}]),
                         "woche")
        self.assertEqual(widgets._sicht_takt([{"takt": "quartal"}]), "quartal")

    def test_payload_traegt_den_schluessel(self):
        """Ein Vertragsfeld ohne Lieferung ist eine Zusage ohne Leser (SWR-131)."""
        wurzel = os.path.abspath(os.path.join(_HIER, "..", ".."))
        w = widgets.post_widget(wurzel, "team-mail")
        if w is None:
            self.skipTest("team-mail liegt hier nicht vor")
        self.assertIn("sicht_takt", w)
        self.assertIn(w["sicht_takt"], [e["takt"] for e in w["eintraege"]])


if __name__ == "__main__":
    unittest.main()
