"""SWR-135 (projects/p11/T-0010) — nach dem Rückbau von Sprint 24 die LAYOUT-Hälfte.

Die Anforderung hatte zwei Hälften. Die **Kachelhälfte** (ein Endpunkt, der aus
`cockpit_alle` Kompaktkacheln formt) ist in Sprint 17 als Dopplung zum Cockpit gerügt und
in ihrer Anzeige entfernt worden (SWR-148); `p11/T-0014` hat 2026-08-17 entschieden, auch
den Endpunkt zurückzubauen (Option B), und `p11/T-0015` hat es in Sprint 24 ausgeführt.

Was bleibt und hier geprüft wird:

* die **Zustandsregel** `_zustand` — sie war nie an den Endpunkt gebunden und trägt seit
  SWR-146 den `zustaende`-Block des Cockpits;
* `vertrag_version` — sie wird von `/api/widgets` gelesen;
* die **Layout-Hälfte**: `main.breit`, das Abräumen der Breite in `zeige()`, der eigene
  Reiter, der benannte leere Fall;
* und ⚠ ein **Wächter gegen die Rückkehr** der Kachelhälfte.

⚠ **Die drei Prüfklassen des Endpunkts sind nicht gelöscht, sondern umgedreht.** Dieselbe
Bauform, mit der SWR-148 den Test zu `kompaktKachel` umgedreht hat: eine Dopplung, die
einmal entfernt wurde, kommt als Verbesserung wieder („das Dashboard zeigt jetzt auch die
Projekte"), und eine Regel, die keine Prüfung vertritt, hält keine drei Sprints (SWR-125).
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


class RueckbauTest(unittest.TestCase):
    """⚠ Der Wächter gegen die RÜCKKEHR der Kachelhälfte (`p11/T-0015`, Sprint 24).

    Bis Sprint 23 standen hier drei Klassen — `KeinZweiterErhebungswegTest` (die Attrappe,
    die belegte, dass `dashboard` nirgendwo anders liest), `BestandTest` (dieselbe Zusage
    am echten Bestand) und der `KACHEL_FELDER`-Teil von `VertragTest`. Sie prüften einen
    Endpunkt, den `p11/T-0014` mit **Option B** zum Rückbau bestimmt hat.

    > **Ein gelöschter Test hinterlässt keine Lücke, die jemand sieht. Ein umgedrehter
    > schon: er wird rot, wenn das Entfernte zurückkommt.**
    """

    def test_der_endpunkt_ist_weg_und_kommt_nicht_wieder(self):
        """`aggregation.dashboard` und `KACHEL_FELDER` sind entfernt."""
        self.assertFalse(hasattr(aggregation, "dashboard"),
                         "aggregation.dashboard ist zurück — das ist die Kachelhälfte, "
                         "die p11/T-0014 mit Option B zurückgebaut hat")
        self.assertFalse(hasattr(aggregation, "KACHEL_FELDER"),
                         "KACHEL_FELDER ist zurück — die Feldliste der Kompaktkachel")

    def test_die_route_ist_weg(self):
        """⚠ Zwei Stellen, zwei Prüfungen: das Modul kann leer sein und die Route stehen.

        Eine Route, die auf eine entfernte Funktion zeigt, stirbt erst beim Aufruf — und
        das ist der Leser und nicht der Test.
        """
        with open(os.path.join(_HIER, "..", "backend", "server.py"),
                  encoding="utf-8") as f:
            server = f.read()
        treffer = [z.strip() for z in server.splitlines()
                   if '"/api/dashboard"' in z and not z.strip().startswith("#")]
        self.assertEqual(treffer, [], f"/api/dashboard ist wieder verdrahtet: {treffer}")

    def test_GEGENPROBE_die_zustandsregel_ist_NICHT_mitgenommen_worden(self):
        """⚠⚠ Ohne diese Gegenprobe wäre der Wächter oben auch bei einem Kahlschlag grün.

        `_zustand` und `zustaende_von` sehen aus wie Dashboard-Code und sind es nicht:
        `zustaende_von` trägt seit SWR-146 den `zustaende`-Block **des Cockpits**. Wer sie
        beim Aufräumen mitnimmt, reißt einer abgenommenen Anforderung die Grundlage weg —
        und `test_der_endpunkt_ist_weg` würde das mit einem grünen Haken quittieren.
        """
        self.assertTrue(hasattr(aggregation, "_zustand"))
        self.assertTrue(hasattr(aggregation, "zustaende_von"))
        eintrag = {"letzte_baseline": None, "team": {"letzter_digest": ""}}
        z = aggregation.zustaende_von(eintrag)
        self.assertEqual(z["letzte_baseline"], aggregation.ZUSTAND_NICHT_GELIEFERT)
        self.assertEqual(z["team.letzter_digest"], aggregation.ZUSTAND_ECHTE_NULL)

    def test_GEGENPROBE_der_reiter_und_seine_widgets_bleiben(self):
        """Der Rückbau nimmt den Endpunkt, nicht die Ansicht — `/api/widgets` bleibt."""
        with open(os.path.join(_HIER, "..", "backend", "server.py"),
                  encoding="utf-8") as f:
            server = f.read()
        self.assertIn('"/api/widgets"', server)


class VertragTest(unittest.TestCase):
    """Die Vertragsversion wird GELESEN und nicht eingetragen.

    ⚠ Bis Sprint 23 stand hier zusätzlich `test_jedes_kachelfeld_steht_im_vertrag` — der
    Nachweis, dass der Endpunkt kein Feld erfindet. Er ist mit `KACHEL_FELDER` entfallen
    (`p11/T-0015`); was er schützte, ist mit dem Endpunkt weg. Die Gegenrichtung — dass
    KACHEL_FELDER nicht zurückkommt — steht in `RueckbauTest`.
    """

    def setUp(self):
        if not os.path.exists(VERTRAG):
            self.skipTest("Widget-Vertrag nicht vorhanden")
        # ⚠ Der Zeilenscanner über `- name:` ist mit `test_jedes_kachelfeld_steht_im_vertrag`
        # entfallen; ein setUp, das etwas einliest, das keine Methode mehr liest, wäre
        # genau die stille Altlast, gegen die dieser Rückbau geführt wurde.
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

        ⚠ **Sprint 24 hat die zweite Haelfte nachgezogen.** Bis dahin stand hier, der
        Endpunkt `/api/dashboard` bleibe unveraendert geprueft und ueber sein Schicksal
        entscheide `projects/p11/T-0014`. Die Entscheidung ist am 2026-08-17 mit **Option
        B** gefallen und in `p11/T-0015` ausgefuehrt: der Endpunkt ist weg. Der Waechter
        dagegen steht in `RueckbauTest`, nicht hier — diese Methode verantwortet die
        **Ansicht**.
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
