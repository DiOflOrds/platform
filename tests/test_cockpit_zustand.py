# -*- coding: utf-8 -*-
"""SWR-146 (platform/T-0016 DoD 2): der Cockpit-Payload trägt den Zustand je Feld.

Der Befund, aus dem dieses Modul entstanden ist, war **kein Anzeigefehler**:
`cockpitKarte` hat die Regel *„`null` heißt keine Daten, `0` heißt 0"* an **drei** Stellen
selbst formuliert, und alle drei waren richtig. Genau das ist die Bauart, die SWR-131
gekostet hat — mehrere Formulierungen eines Begriffs, von denen jede für sich stimmt.

⚠ Der Kern der Zusicherungen hier ist deshalb nicht, **dass** ein Zustand geliefert wird,
sondern dass es **eine** Herleitung ist (`_zustand`, dieselbe wie im Dashboard) und dass
die Menge der gelieferten Schlüssel dem **Vertrag** folgt und nicht der heutigen Ansicht.
"""
import os
import sys
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
from backend import aggregation  # noqa: E402

WURZEL = os.path.abspath(os.path.join(_HIER, "..", ".."))
VERTRAG = os.path.join(WURZEL, "team-dashboard", "vertrag", "widget-vertrag-v2.yaml")


class ZustaendeVonTest(unittest.TestCase):
    """Rein, ohne Bestand: die Herleitung an gebauten Einträgen."""

    def test_die_drei_zustaende_je_feld(self):
        eintrag = {"letzte_baseline": "p0-v1.0", "letzte_baseline_text": "",
                   "team": {"letzter_digest": "2026-08-17"}, "kpi": None}
        z = aggregation.zustaende_von(eintrag)
        self.assertEqual(z["letzte_baseline"], aggregation.ZUSTAND_WERT)
        self.assertEqual(z["letzte_baseline_text"], aggregation.ZUSTAND_ECHTE_NULL)
        self.assertEqual(z["team"], aggregation.ZUSTAND_WERT)
        self.assertEqual(z["kpi"], aggregation.ZUSTAND_NICHT_GELIEFERT)
        self.assertEqual(z["team.letzter_digest"], aggregation.ZUSTAND_WERT)

    def test_kein_team_heisst_auch_kein_digest_und_NICHT_kein_schluessel(self):
        """⚠ Der verschachtelte Fall, und er ist der Grund für `ZUSTAND_PFADE_COCKPIT`.

        Gibt es kein Team, gibt es auch keinen Digest — aber der Schlüssel muss **da**
        sein: eine fehlende Angabe wäre für die Anzeige von einem Wert nicht zu
        unterscheiden, und `Regeln.cockpitFeldText` liest `undefined` bewusst als
        `nicht_geliefert`. Ohne diesen Fall stünde die Anzeige richtig da und aus dem
        falschen Grund.
        """
        z = aggregation.zustaende_von({"team": None})
        self.assertIn("team.letzter_digest", z)
        self.assertEqual(z["team.letzter_digest"], aggregation.ZUSTAND_NICHT_GELIEFERT)
        self.assertEqual(z["team"], aggregation.ZUSTAND_NICHT_GELIEFERT)

    def test_team_ohne_digest_ist_nicht_geliefert_nicht_echte_null(self):
        """`team: {}` heißt: es gibt ein Team, aber der Digest ist nicht erhoben. Die
        Unterscheidung zu `letzter_digest: ""` („führt Digests, hatte noch keinen") ist
        der ganze Grund, warum SWR-108 existiert."""
        self.assertEqual(aggregation.zustaende_von({"team": {}})["team.letzter_digest"],
                         aggregation.ZUSTAND_NICHT_GELIEFERT)
        self.assertEqual(
            aggregation.zustaende_von({"team": {"letzter_digest": ""}})["team.letzter_digest"],
            aggregation.ZUSTAND_ECHTE_NULL)

    def test_eine_null_wird_NIE_zu_echte_null(self):
        """Die Richtung, die der Vertrag wörtlich verbietet: `nicht_geliefert` darf nie
        als `0` erscheinen. Hier an allen vier Feldern auf einmal."""
        z = aggregation.zustaende_von({"letzte_baseline": None,
                                       "letzte_baseline_text": None,
                                       "team": None, "kpi": None})
        for name in aggregation.ZUSTAND_FELDER_COCKPIT:
            self.assertEqual(z[name], aggregation.ZUSTAND_NICHT_GELIEFERT, name)

    def test_null_laeufe_bleiben_eine_MESSUNG(self):
        """⚠ Der schärfste Fall des Vertrags (`kpi.historie`): eine vorhandene, leere
        Registry meldet `{laeufe: 0}` — eine Messung mit dem Ergebnis null. Sie darf
        **nicht** `nicht_geliefert` werden, sonst nimmt die Anzeige einer echten Null
        ihre 0."""
        z = aggregation.zustaende_von({"kpi": {"laeufe": 0, "kosten_eur": 0.0}})
        self.assertEqual(z["kpi"], aggregation.ZUSTAND_WERT)


class SchluesselmengeFolgtDemVertragTest(unittest.TestCase):
    """⚠ Die Zusicherung, die SWR-146 von einer Bequemlichkeit trennt.

    Gemessen wird gegen die **Vertragsdatei** und nicht gegen eine Liste im Test: eine
    Liste hier wäre die dritte Aussage darüber, welche Felder optional sind.
    """

    def setUp(self):
        if not os.path.exists(VERTRAG):
            self.skipTest("Vertrag nicht unter der Wurzel")
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML nicht verfuegbar")
        with open(VERTRAG, encoding="utf-8") as f:
            self.vertrag = yaml.safe_load(f)

    def test_jedes_optionale_vertragsfeld_hat_einen_zustand(self):
        optional = {f["name"] for f in self.vertrag["felder"]
                    if f.get("pflicht") is False}
        geliefert = set(aggregation.ZUSTAND_FELDER_COCKPIT)
        self.assertEqual(optional - geliefert, set(),
                         "Der Vertrag führt optionale Felder ohne Zustand — genau die "
                         "Lücke, die nur im null-Fall sichtbar wäre")

    def test_kein_zustand_fuer_ein_pflichtfeld(self):
        """Die Gegenrichtung: ein Zustand an einem Feld, das immer belegt ist, wäre eine
        Angabe ohne Aussage — und der Vertrag sagt bei den Pflichtfeldern ausdrücklich,
        dass sie keine brauchen."""
        pflicht = {f["name"] for f in self.vertrag["felder"] if f.get("pflicht") is True}
        self.assertEqual(set(aggregation.ZUSTAND_FELDER_COCKPIT) & pflicht, set())

    def test_der_verschachtelte_pfad_steht_im_vertrag(self):
        """`team.letzter_digest` ist kein erfundener Pfad: `team` führt ihn unter
        `felder_innen`. Ohne diese Prüfung könnte ein Pfad zugeliefert werden, den der
        Vertrag nicht kennt — und der Vertrag ist die einzige Stelle, die die Feldliste
        führt."""
        for pfad in aggregation.ZUSTAND_PFADE_COCKPIT:
            eltern, kind = pfad.split(".", 1)
            eintrag = next(f for f in self.vertrag["felder"] if f["name"] == eltern)
            self.assertIn(kind, eintrag.get("felder_innen") or [], pfad)

    def test_vertragsversion_ist_25(self):
        """Der Bump gehört zur Anforderung: `pflege.versionierung` verlangt ihn, sobald
        sich die Feldliste ändert."""
        self.assertEqual(str(self.vertrag["version"]), "2.5")


class EineHerleitungTest(unittest.TestCase):
    """SWR-146: **eine** Herleitung, nicht zwei. Ohne diese Zusicherung wäre der ganze
    Zweck der Anforderung unbelegt — man könnte `zustaende_von` mit einer eigenen
    Fallunterscheidung füllen und alle Tests oben grün halten."""

    def test_cockpit_und_dashboard_urteilen_gleich(self):
        for wert in (None, 0, "", [], {}, "p0-v1.0", 3, {"laeufe": 0}):
            self.assertEqual(aggregation.zustaende_von({"kpi": wert})["kpi"],
                             aggregation._zustand(wert),
                             "abweichendes Urteil für %r — das ist die zweite "
                             "Herleitung, die SWR-146 verbietet" % (wert,))


class EchterBestandTest(unittest.TestCase):
    """Gegen den echten Bestand: der Payload trägt den Block, für jeden Eintrag."""

    def setUp(self):
        if not os.path.isdir(os.path.join(WURZEL, "pm", "tickets")):
            self.skipTest("kein Bestand unter der Wurzel")
        self.eintraege = aggregation.cockpit_alle(WURZEL)["projekte"]

    def test_jeder_eintrag_traegt_alle_zustaende(self):
        erwartet = set(aggregation.ZUSTAND_FELDER_COCKPIT) | set(
            aggregation.ZUSTAND_PFADE_COCKPIT)
        for e in self.eintraege:
            self.assertEqual(set(e["zustaende"]), erwartet, e.get("projekt"))

    def test_die_werte_stammen_aus_der_geschlossenen_menge(self):
        erlaubt = {aggregation.ZUSTAND_WERT, aggregation.ZUSTAND_ECHTE_NULL,
                   aggregation.ZUSTAND_NICHT_GELIEFERT}
        for e in self.eintraege:
            self.assertLessEqual(set(e["zustaende"].values()), erlaubt, e.get("projekt"))

    def test_der_zustand_widerspricht_dem_wert_nicht(self):
        """⚠ Die Übereinstimmungsprüfung am echten Bestand: `nicht_geliefert` genau dann,
        wenn der Wert `None` ist. Ein Block, der neben den Werten steht, kann von ihnen
        abdriften — und dann sagt eine Kachel etwas anderes als ihr eigenes Feld."""
        for e in self.eintraege:
            for name in aggregation.ZUSTAND_FELDER_COCKPIT:
                ist_none = e.get(name) is None
                gemeldet = e["zustaende"][name] == aggregation.ZUSTAND_NICHT_GELIEFERT
                self.assertEqual(ist_none, gemeldet,
                                 f"{e.get('projekt')}/{name}: Wert und Zustand "
                                 f"widersprechen sich")


if __name__ == "__main__":
    unittest.main()
