"""Der Widget-Vertrag wird gegen den echten Payload gehalten (B066, Sprint 9).

**Der Befund.** `widget-vertrag-v2.yaml` sagt von sich in Grossbuchstaben: DIESE DATEI
IST DIE EINZIGE STELLE, DIE DIE FELDLISTE FUEHRT. In v2.1 (Sprint 7, SWR-111) wurde
`letzte_baseline_text` direkt ueber den `team`-Eintrag geschoben — und dessen Zeile
`- name: team` ging dabei verloren. YAML hat daraus keinen Fehler gemacht, sondern aus
zwei Eintraegen stillschweigend EINEN gebaut: bei doppelten Schluesseln gewinnt der
hintere, also stand `letzte_baseline_text` fortan mit `typ: objekt|null`,
`nur_bei: "Eintraege mit team.yaml"` und `felder_innen: [letzter_digest]` im Vertrag,
und `team` kam in der Feldliste ueberhaupt nicht mehr vor — obwohl der Payload es
liefert und ein Widget es anzeigt.

**Warum es zwei Sprints ueberlebt hat.** Die Datei parste durchgehend sauber. Es gab
keine rote Zeile, keinen Befund, keinen Test: die einzige Pruefung, die der Vertrag
kannte, war, dass er lesbar ist. Ein Vertrag, gegen den nichts geprueft wird, ist eine
Beschreibung und keine Zusicherung — dieselbe Familie wie die Statusspalte aus
SWR-115, die zwei Sprints lang gegen nichts gehalten wurde.

**Was dieser Test tut.** Er haelt die Feldliste gegen einen echten `cockpit`-Eintrag,
in beide Richtungen. Die zweite Richtung ist die, die B066 gefunden haette: ein Feld
IM PAYLOAD, das im Vertrag FEHLT. Die erste (Vertragsfeld ohne Payload) faengt den
umgekehrten Fall — ein Feld, das aus der Quelle verschwindet und im Vertrag stehen
bleibt. Dazu die Ursache selbst: doppelte Schluessel in einem Mapping, roh am Text
geprueft, weil `yaml.safe_load` sie ja gerade NICHT meldet.
"""
import os
import re
import sys
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
from backend import aggregation  # noqa: E402

VERTRAG = os.path.join(_HIER, "..", "..", "team-dashboard", "vertrag",
                       "widget-vertrag-v2.yaml")
WURZEL = os.path.abspath(os.path.join(_HIER, "..", ".."))


def _yaml():
    try:
        import yaml
    except ImportError:  # pragma: no cover
        return None
    with open(VERTRAG, encoding="utf-8") as f:
        return yaml.safe_load(f)


class VertragFeldlisteTest(unittest.TestCase):

    def setUp(self):
        if not os.path.exists(VERTRAG):
            self.skipTest("Vertrag nicht unter der Wurzel")
        self.vertrag = _yaml()
        if self.vertrag is None:
            self.skipTest("PyYAML nicht verfuegbar")
        if not os.path.isdir(os.path.join(WURZEL, "pm", "tickets")):
            self.skipTest("kein Bestand unter der Wurzel")
        self.namen = {f["name"] for f in self.vertrag["felder"]}
        self.eintrag = aggregation.cockpit_alle(WURZEL)["projekte"][0]

    def test_jedes_payloadfeld_steht_im_vertrag(self):
        """⚠ DIE RICHTUNG, DIE B066 GEFUNDEN HAETTE.

        `team` war aus der Feldliste verschwunden, wurde aber weiter geliefert. Ein
        Widget, das sich an den Vertrag haelt, ignoriert unbekannte Felder (so steht es
        unter `pflege.unbekannte_felder`) — es haette `team` also stillschweigend nicht
        mehr angezeigt, und der Vertrag haette das gedeckt.
        """
        fehlend = sorted(set(self.eintrag) - self.namen)
        self.assertEqual(fehlend, [],
                         "Payload liefert Felder, die der Vertrag nicht fuehrt: %s"
                         % fehlend)

    def test_jedes_vertragsfeld_kommt_im_payload_vor(self):
        """Die Gegenrichtung: ein Feld, das aus der Quelle verschwindet, darf nicht
        unbemerkt im Vertrag stehen bleiben — sonst sagt der Vertrag etwas zu, das
        niemand mehr liefert (`pflege.unbekannte_felder`: das waere ein Vertragsbruch
        und muss als solcher sichtbar werden)."""
        ueberzaehlig = sorted(self.namen - set(self.eintrag))
        self.assertEqual(ueberzaehlig, [],
                         "Vertrag fuehrt Felder, die der Payload nicht liefert: %s"
                         % ueberzaehlig)

    def test_team_steht_wieder_in_der_feldliste(self):
        """B066 namentlich — der Fall, an dem der Test entstanden ist, bleibt als
        eigener Test stehen und nicht nur als Sonderfall der Summe."""
        self.assertIn("team", self.namen)

    def test_letzte_baseline_text_hat_seinen_eigenen_typ_zurueck(self):
        """B066, die zweite Haelfte: durch die Verschmelzung stand `objekt|null` an
        einem Feld, das laut SWR-111 `string|null` ist. Ein Widget haette hier ein
        Objekt erwartet und einen String bekommen."""
        feld = next(f for f in self.vertrag["felder"]
                    if f["name"] == "letzte_baseline_text")
        self.assertEqual(feld["typ"], "string|null")

    def test_keine_doppelten_schluessel_in_einem_feldeintrag(self):
        """⚠ DIE URSACHE, nicht das Symptom.

        `yaml.safe_load` meldet doppelte Schluessel NICHT — es nimmt den hinteren. Genau
        deshalb konnte B066 zwei Sprints lang bestehen, ohne dass etwas rot wurde. Diese
        Pruefung geht deshalb roh ueber den Text und nicht ueber das geparste Ergebnis:
        gegen einen Fehler, den der Parser schluckt, hilft der Parser nicht.
        """
        with open(VERTRAG, encoding="utf-8") as f:
            zeilen = f.read().splitlines()
        block, doppelte = [], []
        for zeile in zeilen:
            if re.match(r"^  - name:", zeile):
                block = []
            treffer = re.match(r"^  [ -] (\w+):", zeile)
            if treffer:
                schluessel = treffer.group(1)
                if schluessel in block:
                    doppelte.append(schluessel)
                block.append(schluessel)
        self.assertEqual(doppelte, [],
                         "Doppelte Schluessel in einem Feldeintrag: %s" % doppelte)

    def test_organisation_ist_kein_feld_der_projektliste(self):
        """SWR-117: der Kopfblock beschreibt die Organisation, nicht einen Eintrag. Er
        gehoert deshalb NICHT in `felder` — stuende er dort, waere die Aussage „jedes
        Vertragsfeld kommt im Payload eines Projekts vor" verletzt, und die Trennung
        der beiden Ebenen waere schon im Vertrag verwischt."""
        self.assertNotIn("organisation", self.namen)
        self.assertIn("organisation", self.vertrag)
        innen = {f["name"] for f in self.vertrag["organisation"]["felder_innen"]}
        self.assertEqual(innen, set(aggregation.organisation(WURZEL)))


if __name__ == "__main__":
    unittest.main()
