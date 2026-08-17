"""Zaehler „wartet auf den Menschen" mit Referenzen (SWR-120, pm/T-0051).

Das Ticket verlangte ausdruecklich die REIHENFOLGE: erst `pm/T-0047` (die FORM des
Kopfblocks), dann diese Zahl als Ergaenzung hinein. Der Test dazu ist
`test_projekte_und_erste_zahl_bleiben_unveraendert` — er belegt, dass die Form aus
SWR-117 die Ergaenzung ueberlebt hat und die zweite Zahl deshalb keine zweite
Vertragsfrage war.

Und die Vereinigung zweier Bedingungen (`verantwortlich: mensch` ODER
`decision-request`) wird an EINER Stelle gebildet. Das ist kein B033: es sind zwei
verschiedene Sachverhalte, nicht zwei Meinungen ueber denselben. Ein DR liegt qua Typ
beim Auftraggeber, auch ohne gesetztes Feld.
"""
import os
import sys
import tempfile
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
from backend import aggregation  # noqa: E402
import preflight  # noqa: E402


class WartetAufMenschTest(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "p0", "tickets"))

    def ticket(self, tid, projekt="p0", rumpf="Text.", **felder):
        verz = os.path.join(self.root, projekt, "tickets")
        os.makedirs(verz, exist_ok=True)
        felder.setdefault("status", "open")
        felder.setdefault("typ", "task")
        zeilen = ["---", "id: %s" % tid]
        zeilen += ["%s: %s" % (k, v) for k, v in felder.items()]
        zeilen += ["---", "", rumpf]
        with open(os.path.join(verz, "%s.md" % tid), "w", encoding="utf-8") as f:
            f.write("\n".join(zeilen))

    # ------------------------------------------------------------- die zwei Quellen

    def test_verantwortlich_mensch_zaehlt(self):
        self.ticket("T-0001", verantwortlich="mensch",
                    rumpf="## Handlung beim Menschen\n\nEntscheiden.")
        self.assertEqual(aggregation.wartet_auf_mensch(self.root), ["p0/T-0001"])

    def test_decision_request_zaehlt_auch_ohne_das_feld(self):
        """Ein DR liegt QUA TYP beim Auftraggeber. Wuerde nur das Feld gelesen, fehlten
        genau die Tickets, bei denen am eindeutigsten jemand anderes am Zug ist."""
        self.ticket("T-0002", typ="decision-request")
        self.assertEqual(aggregation.wartet_auf_mensch(self.root), ["p0/T-0002"])

    def test_beides_zusammen_zaehlt_nur_einmal(self):
        """Die Vereinigung wird an EINER Stelle gebildet — sonst zaehlte ein Ticket,
        das beide Bedingungen erfuellt, doppelt, und die Zahl waere groesser als die
        Liste, die sie erklaeren soll."""
        self.ticket("T-0003", typ="decision-request", verantwortlich="mensch",
                    rumpf="## Handlung beim Menschen\n\nEntscheiden.")
        treffer = aggregation.wartet_auf_mensch(self.root)
        self.assertEqual(treffer, ["p0/T-0003"])
        self.assertEqual(len(treffer), len(set(treffer)))

    # ------------------------------------------------------------------ Gegentests

    def test_team_default_zaehlt_nicht(self):
        """Der aufgeloeste Default ist `team` — ohne diesen Gegentest wuerde ein
        fehlendes Feld womoeglich als „unbekannt, also Mensch" gelesen, und der Zaehler
        naehme jedes Ticket der Organisation auf."""
        self.ticket("T-0001")
        self.ticket("T-0002", verantwortlich="team")
        self.assertEqual(aggregation.wartet_auf_mensch(self.root), [])

    def test_geschlossene_zaehlen_nicht(self):
        """Ein entschiedener DR wartet auf niemanden."""
        self.ticket("T-0001", typ="decision-request", status="done")
        self.ticket("T-0002", typ="decision-request", status="rejected")
        self.ticket("T-0003", status="done", verantwortlich="mensch",
                    rumpf="## Handlung beim Menschen\n\nx")
        self.assertEqual(aggregation.wartet_auf_mensch(self.root), [])

    def test_zwei_projekte_werden_summiert_und_namentlich_genannt(self):
        """B038: die Namen, nicht nur die Zahl."""
        self.ticket("T-0001", typ="decision-request")
        self.ticket("T-0002", projekt="p1", typ="decision-request")
        self.assertEqual(sorted(aggregation.wartet_auf_mensch(self.root)),
                         ["p0/T-0001", "p1/T-0002"])

    # ---------------------------------------------------------------- eine Quelle

    def test_preflight_und_aggregation_liefern_dieselbe_liste(self):
        """Der Test, der eine zweite Quelle widerlegen wuerde (B033) — wie bei
        SWR-117 fuer `unterminierte_tickets`."""
        self.ticket("T-0001", typ="decision-request")
        self.assertEqual(preflight.wartet_auf_mensch(self.root),
                         aggregation.wartet_auf_mensch(self.root))

    # ------------------------------------------------------- die Form aus SWR-117

    def test_projekte_und_erste_zahl_bleiben_unveraendert(self):
        """⚠ DER TEST, AUF DEN `pm/T-0051` SEINE REIHENFOLGE GESTUETZT HAT.

        Die zweite Zahl kommt als weiterer SCHLUESSEL in den bestehenden Block. Waere
        dafuer der Block oder `projekte` umzuformen gewesen, waere es die zweite
        Vertragsaenderung am selben Payload in einem Lauf — B025, und das Ticket haette
        zu Recht auf einen eigenen Lauf gewartet.
        """
        self.ticket("T-0001", typ="decision-request")
        nutzlast = aggregation.cockpit_alle(self.root)
        self.assertIsInstance(nutzlast["projekte"], list)
        block = nutzlast["organisation"]
        self.assertIn("unterminiert_gesamt", block)
        self.assertIn("unterminiert_refs", block)
        self.assertIn("wartet_auf_mensch_gesamt", block)
        self.assertIn("wartet_auf_mensch_refs", block)
        self.assertEqual(block["wartet_auf_mensch_gesamt"], 1)

    def test_bei_null_sind_beide_schluessel_da(self):
        """SWR-117 Festlegung 3 gilt fuer die zweite Zahl genauso: vorhanden, `0`, `[]`
        — nie `null`, nie weggelassen."""
        block = aggregation.organisation(self.root)
        self.assertEqual(block["wartet_auf_mensch_gesamt"], 0)
        self.assertEqual(block["wartet_auf_mensch_refs"], [])

    def test_zahl_ist_die_laenge_der_liste(self):
        self.ticket("T-0001", typ="decision-request")
        self.ticket("T-0002", projekt="p1", typ="decision-request")
        block = aggregation.organisation(self.root)
        self.assertEqual(block["wartet_auf_mensch_gesamt"],
                         len(block["wartet_auf_mensch_refs"]))


class BestandTest(unittest.TestCase):
    """Gegenprobe am echten Bestand: Kopfblock und Preflight-Zeile sagen dasselbe."""

    def setUp(self):
        self.wurzel = os.path.abspath(os.path.join(_HIER, "..", ".."))
        if not os.path.isdir(os.path.join(self.wurzel, "pm", "tickets")):
            self.skipTest("kein Bestand unter der Wurzel")

    def test_boardspalte_und_orgzaehler_widersprechen_sich_nie(self):
        """⚠ DER TEST, DER DEN WIDERSPRUCH DIESES SPRINTS GEFUNDEN HÄTTE.

        Beim Bau von SWR-119/120 schrieb die Board-Spalte bei `projects/p11/T-0006`
        „Team", während der Org-Zähler dasselbe Ticket als „wartet auf den Menschen"
        führte: die Spalte las das FELD, der Zähler las Feld ODER Typ. Beide Aussagen
        waren für sich begründet und zusammen falsch (B033).

        Aufgefallen ist es beim Hinsehen, nicht durch eine Prüfung — deshalb steht sie
        jetzt hier. Sie hält die beiden Anzeigen über den **ganzen Bestand** gegen
        einander, nicht an einem gebauten Fall.
        """
        import sys as _sys
        _sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
        import board  # noqa: E402
        zaehler = set(aggregation.wartet_auf_mensch(self.wurzel))
        for name, pfad in board.projekt_pfade(self.wurzel):
            tickets, _ = board.lade_tickets(pfad)
            for t in tickets:
                if t.get("status") in ("done", "rejected"):
                    continue
                spalte = board.wartet_auf_mensch(t)
                gezaehlt = aggregation.ref(name, t.get("id")) in zaehler
                self.assertEqual(spalte, gezaehlt,
                                 "%s/%s: Board-Spalte sagt %s, Org-Zaehler sagt %s"
                                 % (name, t.get("id"), spalte, gezaehlt))

    def test_kopfblock_und_preflightzeile_stimmen_ueberein(self):
        block = aggregation.cockpit_alle(self.wurzel)["organisation"]
        self.assertEqual(block["wartet_auf_mensch_refs"],
                         preflight.wartet_auf_mensch(self.wurzel))
        self.assertEqual(block["wartet_auf_mensch_gesamt"],
                         len(block["wartet_auf_mensch_refs"]))


class HmiZweiteZahlTest(unittest.TestCase):
    """Die zweite Zahl steht im SELBEN Kopfblock und nicht in einer zweiten Kachel."""

    def setUp(self):
        pfad = os.path.join(_HIER, "..", "backend", "static", "app.js")
        with open(pfad, encoding="utf-8") as f:
            self.js = f.read()

    def test_zweite_zahl_haengt_im_selben_kopf(self):
        block = self.js[self.js.index("function orgKopfblock"):]
        block = block[:block.index("\nfunction ")]
        self.assertIn("wartet_auf_mensch_gesamt", block)
        self.assertIn("wartet_auf_mensch_refs", block)
        self.assertEqual(block.count("orgKopfblock"), 1)

    def test_refs_werden_genannt_nicht_nur_gezaehlt(self):
        self.assertIn("Wartet auf dich: ", self.js)


if __name__ == "__main__":
    unittest.main()
