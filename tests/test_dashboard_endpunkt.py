"""SWR-135 (projects/p11/T-0010): der Dashboard-Endpunkt — lesend, ohne zweiten Weg.

Das Ticket war **viermal** verschoben und dem Auftraggeber in Sprint 11 zugesagt. Der
Anlass zum Bauen ist eine Messung (`pm/T-0068`, zwei Aufnahmen seines 4K-Bildschirms):
drei Projektkacheln ohne Scrollen sichtbar, links und rechts je rund ein Fuenftel der
Breite leer.

⚠ Die zentrale Zusicherung ist **nicht**, dass ein Endpunkt Daten liefert, sondern dass er
sie **nirgendwo anders holt** — Risiko R1 aus dem P11-Sprint-0-Plan und `quelle.regel` des
Widget-Vertrags (SWR-092): *driftet ein Widget vom Cockpit ab, ist das ein Fehler des
Widgets.*
"""
import os
import sys
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
from backend import aggregation  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(_HIER))
VERTRAG = os.path.join(WURZEL, "team-dashboard", "vertrag", "widget-vertrag-v2.yaml")


class ZustandTest(unittest.TestCase):
    """Die drei Vertragszustaende (SWR-096/108) — der Kern der Anforderung."""

    def test_none_ist_nicht_geliefert(self):
        self.assertEqual(aggregation._zustand(None),
                         aggregation.ZUSTAND_NICHT_GELIEFERT)

    def test_null_ist_eine_echte_null(self):
        """⚠ Vertrag woertlich: „0 offene Briefe ist ein Ergebnis, kein Loch."""
        self.assertEqual(aggregation._zustand(0), aggregation.ZUSTAND_ECHTE_NULL)

    def test_leerer_string_und_leere_liste_sind_echte_nullen(self):
        """Sie antworten „nichts vorhanden" auf eine Frage, die zutrifft."""
        for leer in ("", [], {}):
            self.assertEqual(aggregation._zustand(leer),
                             aggregation.ZUSTAND_ECHTE_NULL, repr(leer))

    def test_gegenprobe_none_und_null_sind_verschieden(self):
        """⚠ Die ganze Anforderung haengt an dieser Ungleichheit.

        Waeren beide gleich, waere `team: null` (fuehrt keine Digests) nicht von
        `briefe_offen: 0` (keine offenen Briefe) zu unterscheiden — dieselbe Gleichheit,
        die in SWR-128 fuenf Sprints lang „null JS-Tests" verborgen hat.
        """
        self.assertNotEqual(aggregation._zustand(None), aggregation._zustand(0))

    def test_werte_sind_werte(self):
        for wert in (1, 42, "genesis-v1.0", [1], {"a": 1}):
            self.assertEqual(aggregation._zustand(wert), aggregation.ZUSTAND_WERT,
                             repr(wert))


class KeinZweiterErhebungswegTest(unittest.TestCase):
    """⚠ Risiko R1 / SWR-092: `dashboard` liest AUSSCHLIESSLICH aus `cockpit_alle`."""

    def test_ohne_cockpit_bleibt_nichts_uebrig(self):
        """Die Attrappe ersetzt die EINZIGE erlaubte Quelle — dann muss alles leer sein.

        ⚠ Das ist die eigentliche Zusicherung des Tickets. Liefe irgendwo im Endpunkt eine
        eigene Ticket-Lesung oder ein git-Aufruf, kaeme hier trotz leerer Quelle etwas
        heraus. Ein Test, der nur prueft „es kommen Kacheln", haette den zweiten Weg nicht
        bemerkt.
        """
        echt = aggregation.cockpit_alle
        aggregation.cockpit_alle = lambda root, heute=None, jetzt=None: {
            "projekte": [], "organisation": None}
        try:
            d = aggregation.dashboard(WURZEL)
        finally:
            aggregation.cockpit_alle = echt
        self.assertEqual(d["kacheln"], [])
        self.assertIsNone(d["organisation"])

    def test_jede_kachel_stammt_aus_der_quelle(self):
        """Attrappe mit EINEM erfundenen Eintrag — genau er muss ankommen, sonst nichts."""
        echt = aggregation.cockpit_alle
        aggregation.cockpit_alle = lambda root, heute=None, jetzt=None: {
            "projekte": [{"projekt": "attrappe", "beschreibung": "nur im Test",
                          "gruppe": "aktiv", "status": "aktiv",
                          "aufgaben_offen": 0, "briefe_offen": 2, "team": None}],
            "organisation": {"wartet_auf_mensch_gesamt": 0}}
        try:
            d = aggregation.dashboard(WURZEL)
        finally:
            aggregation.cockpit_alle = echt
        self.assertEqual([k["projekt"] for k in d["kacheln"]], ["attrappe"])
        felder = d["kacheln"][0]["felder"]
        self.assertEqual(felder["briefe_offen"],
                         {"wert": 2, "zustand": aggregation.ZUSTAND_WERT})
        self.assertEqual(felder["aufgaben_offen"]["zustand"],
                         aggregation.ZUSTAND_ECHTE_NULL)
        self.assertEqual(felder["team"]["zustand"],
                         aggregation.ZUSTAND_NICHT_GELIEFERT)

    def test_fehlendes_feld_der_quelle_ist_nicht_geliefert(self):
        """Ein Feld, das die Quelle gar nicht fuehrt, wird nicht erfunden (B038)."""
        echt = aggregation.cockpit_alle
        aggregation.cockpit_alle = lambda root, heute=None, jetzt=None: {
            "projekte": [{"projekt": "kahl"}], "organisation": None}
        try:
            d = aggregation.dashboard(WURZEL)
        finally:
            aggregation.cockpit_alle = echt
        for name in aggregation.KACHEL_FELDER:
            self.assertEqual(d["kacheln"][0]["felder"][name]["zustand"],
                             aggregation.ZUSTAND_NICHT_GELIEFERT, name)


class VertragTest(unittest.TestCase):
    """⚠ Der Endpunkt fuegt KEIN Feld hinzu — er ordnet vorhandene (B066)."""

    def setUp(self):
        if not os.path.exists(VERTRAG):
            self.skipTest("Widget-Vertrag nicht vorhanden")
        self.namen = set()
        with open(VERTRAG, encoding="utf-8") as f:
            for zeile in f:
                z = zeile.strip()
                if z.startswith("- name:"):
                    self.namen.add(z.split(":", 1)[1].strip().strip('"\''))
        # SWR-146: die Version wird gegen die DATEI verglichen und nicht gegen ein
        # Literal — mit einem anderen Verfahren als `vertrag_version` (YAML statt
        # Zeilenscanner), damit zwei unabhaengige Lesungen sich bestaetigen.
        try:
            import yaml
        except ImportError:
            self.vertrag = None
            return
        with open(VERTRAG, encoding="utf-8") as f:
            self.vertrag = yaml.safe_load(f)

    def test_jedes_kachelfeld_steht_im_vertrag(self):
        """Sonst waere der Endpunkt ein Vertragsbruch — genau das, was B066 prueft.

        ⚠ Ohne diesen Test waere „kein neues Feld" eine Absicht im Docstring. Der Vertrag
        ist die einzige Stelle, die die Feldliste fuehrt; ein Endpunkt, der daneben ein
        eigenes Feld erfindet, macht sie zur zweiten Liste (B033).
        """
        fremd = [n for n in aggregation.KACHEL_FELDER if n not in self.namen]
        self.assertEqual(fremd, [], f"Felder ohne Vertragseintrag: {fremd}")

    def test_die_vertragsversion_wird_gelesen_nicht_eingetragen(self):
        """Eine Konstante im Code wuerde beim naechsten Bump still falsch (B033).

        ⚠ Der Bump auf v2.5 (SWR-146) hat diesen Test rot gemacht, weil hier die Zahl
        `"2.4"` als Literal stand — und damit stand die Version an einer **zweiten** Stelle,
        genau das, was der Test seinem eigenen Titel nach ausschliessen soll.

        > **Ein Test, der behauptet, ein Wert werde gelesen und nicht eingetragen, darf ihn
        > nicht selbst eintragen.**

        Verglichen wird deshalb gegen die **Datei** — und mit einem anderen Verfahren als
        die Funktion: `yaml.safe_load` gegen den Zeilenscanner in `vertrag_version`. Zwei
        unabhaengige Lesungen, die uebereinstimmen, sind die Zusicherung; ein Literal war
        nur eine dritte Behauptung.
        """
        if self.vertrag is None:
            self.skipTest("PyYAML nicht verfuegbar")
        self.assertEqual(aggregation.vertrag_version(WURZEL),
                         str(self.vertrag["version"]))
        # ⚠ Und die Gegenprobe gegen „beide lesen nichts": eine leere Antwort auf beiden
        # Seiten waere gleich und trotzdem falsch.
        self.assertRegex(aggregation.vertrag_version(WURZEL), r"^\d+\.\d+$")

    def test_fehlender_vertrag_liefert_leer_statt_einer_ausnahme(self):
        self.assertEqual(aggregation.vertrag_version("/gibt/es/nicht"), "")


class BestandTest(unittest.TestCase):
    """Der ECHTE Bestand — die Lehre aus SWR-128: konstruierte Faelle genuegen nicht."""

    def setUp(self):
        if not os.path.isdir(os.path.join(WURZEL, "pm", "tickets")):
            self.skipTest("Bestand nicht vorhanden (isolierte Testumgebung)")
        self.d = aggregation.dashboard(WURZEL)

    def test_es_gibt_genauso_viele_kacheln_wie_projekte(self):
        """Keine Kachel geht verloren, keine kommt hinzu."""
        self.assertEqual(len(self.d["kacheln"]),
                         len(aggregation.projekte(WURZEL)))

    def test_beide_zustaende_kommen_im_bestand_wirklich_vor(self):
        """⚠ Die Unterscheidung wird am echten Bestand nachgewiesen, nicht behauptet.

        `echte_null` und `nicht_geliefert` muessen beide auftreten — kaeme nur einer vor,
        waere die Regel im Bestand ungeprueft und nur an Attrappen gruen. Genau diese
        Luecke hat SWR-128 aufgedeckt.
        """
        zustaende = {f["zustand"] for k in self.d["kacheln"]
                     for f in k["felder"].values()}
        self.assertIn(aggregation.ZUSTAND_ECHTE_NULL, zustaende)
        self.assertIn(aggregation.ZUSTAND_NICHT_GELIEFERT, zustaende)

    def test_die_organisation_ist_dieselbe_wie_im_cockpit(self):
        """Dashboard und Cockpit duerfen nicht verschieden zaehlen (B033)."""
        self.assertEqual(self.d["organisation"],
                         aggregation.cockpit_alle(WURZEL)["organisation"])


class AnsichtTest(unittest.TestCase):
    """ADR-P11-002: die Korridor-Ausnahme sitzt an der ANSICHT, nicht am Korridor."""

    def setUp(self):
        with open(os.path.join(_HIER, "..", "backend", "static", "app.js"),
                  encoding="utf-8") as f:
            self.app = f.read()
        with open(os.path.join(_HIER, "..", "backend", "static", "index.html"),
                  encoding="utf-8") as f:
            self.html = f.read()

    def test_der_globale_korridor_bleibt_ohne_ausnahme(self):
        """⚠ Die Kernaussage des ADR, als Test.

        `main { max-width:62rem }` darf keinen Sonderfall kennen — die Ausnahme ist eine
        EIGENE Regel (`main.breit`). Eine Regel mit Ausnahmeliste zwingt jede kuenftige
        Ansicht zu der Frage „gilt sie hier?", und die Antwort stuende dann nicht in der
        Ansicht.
        """
        self.assertIn("main { padding:1rem; max-width:62rem; margin:0 auto; }", self.html)
        self.assertIn("main.breit { max-width:none; }", self.html)

    def test_die_breite_wird_bei_jedem_zeichnen_abgeraeumt(self):
        """⚠ Gegenprobe: sonst waere die Ausnahme nach einem Dashboard-Besuch global.

        Ohne das `remove` in `zeige()` bliebe `breit` an `main` haengen und jede folgende
        Ansicht haette den Korridor verloren — die Ausnahme waere faktisch ueberall, obwohl
        der ADR sie auf eine Ansicht begrenzt (LAY-b war ausdruecklich verworfen).
        """
        self.assertIn('inhalt.classList.remove("breit")', self.app)
        stelle = self.app.index("function zeige(elemente)")
        ende = self.app.index("function zeigeBreit")
        self.assertIn('remove("breit")', self.app[stelle:ende],
                      "das Abraeumen steht nicht in zeige() — dann muss es jede kuenftige "
                      "Ansicht selbst kennen")

    def test_die_ansicht_liest_die_regeln_und_formuliert_sie_nicht(self):
        """⚠ Die ANZEIGEHAELFTE von SWR-135 ist in Sprint 17 abgeloest (SWR-148).

        Bis dahin stand hier, dass `app.js` `Regeln.kachelFelder` und
        `Regeln.dashboardGruppen` liest — die Projektkacheln des Dashboards. Der
        Auftraggeber hat sie als Dopplung zum Cockpit benannt („ist an sich das gleiche wie
        das cockpit"), und zwei Anzeigen derselben Daten sind B033. Die Kacheln haben das
        Dashboard **verlassen**, `kompaktKachel` ist entfernt.

        ⚠ **Der Test wird deshalb nicht geloescht, sondern umgedreht.** Er ist ab jetzt der
        Waechter gegen die Rueckkehr der Dopplung — und die kaeme als Verbesserung daher
        („das Dashboard zeigt jetzt auch die Projekte"). Dieselbe Bauart wie beim Altbestand
        eine Methode weiter unten.

        Was bleibt: der Endpunkt `/api/dashboard` und die Regelfunktionen sind unveraendert
        geprueft. Ob der Endpunkt ohne Leser bestehen bleibt, entscheidet
        `projects/p11/T-0014` — eine abgenommene Anforderung wird nicht im Vorbeigehen
        geloescht.
        """
        self.assertNotIn("function kompaktKachel", self.app,
                         "die Projektkachel des Dashboards ist zurueck — das ist die "
                         "Dopplung, die der Auftraggeber geruegt hat")
        for name in ("Regeln.widgetZeile", "Regeln.widgetVollstaendig",
                     "Regeln.gruppenTitel"):
            self.assertIn(name, self.app, f"{name} wird in app.js nicht gelesen")

    def _dashboard_bereich(self):
        """Nur der Code, den DIESES Ticket verantwortet."""
        anfang = self.app.index("function widgetKarte")
        ende = self.app.index("function lade() {")
        return self.app[anfang:ende]

    def test_der_dashboard_code_entscheidet_nicht_selbst_was_keine_daten_heisst(self):
        """Gegenprobe gegen eine zweite Kopie der Vertragsregel im neuen Code."""
        verdaechtig = [z for z in self._dashboard_bereich().splitlines()
                       if "keine Daten" in z and "Regeln." not in z
                       and not z.strip().startswith("//")]
        self.assertEqual(verdaechtig, [],
                         f"der Dashboard-Code formuliert die Regel selbst: {verdaechtig}")

    def test_altbestand_der_inline_regel_ist_auf_NULL(self):
        """✅ SWR-146 (platform/T-0016 DoD 4): der Altbestand ist **geschlossen** — 3 -> 0.

        Bis Sprint 16 stand hier `assertEqual(len(kopien), 3)` und der Docstring erklärte,
        warum der Befund **benannt und eingefroren** und nicht geglättet wurde. Der Grund
        für das Einfrieren war eine offene **Vertragsfrage**: `/api/cockpit` führte kein
        `zustand`-Feld, und eine zweite Herleitung in JavaScript wäre ein neuer B033-Fall
        gewesen statt einer Reparatur.

        Die Frage ist in Sprint 16 entschieden (Weg A, Eigentümer `team-dashboard/T-0001`),
        der Payload trägt den Zustand seit Sprint 17 (`zustaende`, Vertrag v2.5), und die
        drei Inline-Prüfungen sind durch **eine** Stelle ersetzt
        (`Regeln.cockpitFeldText`).

        ⚠ Die Prüfung bleibt bestehen und wird **nicht** gelöscht: sie ist ab jetzt der
        Wächter gegen die **Rückkehr**. Genau dieser Fall ist der Organisation schon
        passiert — SWR-106 hatte Kalenderdaten fünf Sprints früher abgeschafft, und weil
        ihre Rückkehr niemand meldete, standen kurz darauf wieder 14 Stück im Bestand
        (SWR-125). Eine Regel, die keine Prüfung vertritt, hält keine drei Sprints.

        ⚠ Gemessen wird weiter der **Textabschnitt** `cockpitKarte`, und die Grenze der
        Messung steht hier ausdrücklich: eine Textsuche kann eine Warnung nicht von ihrem
        Gegenstand unterscheiden (`L-2026-08-17ak`). Kommentarzeilen sind deshalb
        ausgenommen — und die Marke selbst steht seit der Migration in `regeln.js`, wo ein
        eigener JS-Zähltest sie hält (`alle drei migrierten Felder stehen in der Tabelle`).
        Ohne diesen Nachbarn wäre die 0 hier von einer verlorenen Regel nicht zu
        unterscheiden.
        """
        anfang = self.app.index("function cockpitKarte")
        ende = self.app.index("function widgetKarte")
        kopien = [z.strip() for z in self.app[anfang:ende].splitlines()
                  if "keine Daten" in z and not z.strip().startswith("//")]
        self.assertEqual(len(kopien), 0,
                         "Die Zustandsregel steht wieder inline in cockpitKarte "
                         f"(erwartet 0, gefunden {len(kopien)}): {kopien}. Sie gehoert in "
                         "Regeln.cockpitFeldText — SWR-146.")

    def test_die_ansicht_liest_den_zustand_und_leitet_ihn_nicht_ab(self):
        """⚠ Die Gegenrichtung zur 0 darüber, und ohne sie wäre die 0 wertlos.

        Der Altbestand ließe sich auch dadurch auf 0 bringen, dass `cockpitKarte` den
        Zustand **selbst** herleitet und die Marke anders schreibt. Gemessen wird deshalb,
        dass die Karte den Zustand aus dem **Payload** nimmt (`zustaende`) und den Text von
        `Regeln` bezieht — und dass sie keine eigene `=== null`-Prüfung an den drei
        migrierten Feldern mehr trägt.
        """
        anfang = self.app.index("function cockpitKarte")
        ende = self.app.index("function widgetKarte")
        karte = self.app[anfang:ende]
        self.assertIn("Regeln.cockpitFeldText", karte)
        eigene = [z.strip() for z in karte.splitlines()
                  if "=== null" in z and not z.strip().startswith("//")]
        self.assertEqual(eigene, [],
                         f"cockpitKarte leitet den Zustand wieder selbst ab: {eigene}")

    def test_das_dashboard_ist_ein_eigener_reiter(self):
        self.assertIn('["dashboard", "Dashboard"]', self.app)
        self.assertIn("dashboard: ladeDashboard", self.app)

    def test_der_leere_fall_wird_benannt(self):
        """„nichts da" und „nicht geladen" duerfen nicht gleich aussehen (SWR-114)."""
        self.assertIn("kein Ladefehler", self.app)


if __name__ == "__main__":
    unittest.main()
