"""Org-Kopfblock im Cockpit-Payload (SWR-117, pm/T-0047).

Das Ticket war zweimal mit dem Grund „Vertragsfrage vor Bau" verschoben worden. Die
Messung in Sprint 9 (L-2026-08-17j Regel 2) hat den Grund geleert: die Frage ist nach
Playbook Kap. 16 Klasse C, der B025-Nachbar (SWR-111 an `aggregation.cockpit`) liegt
seit Sprint 7 zurueck, und der als Hindernis genannte „neue Nachbar" `pm/T-0051` wartet
laut eigenem Ticket auf DIESES hier — die Abhaengigkeit zeigte in die falsche Richtung.

Geprueft werden die drei Festlegungen, die SWR-117 trifft:

1. **Schwesterschluessel statt Umhuellung** — `projekte` bleibt unangetastet. Der
   Gegentest dazu ist der Kern: eine Umhuellung waere fuer JEDEN heutigen Leser eine
   Aenderung, um eine Zahl zu liefern, die KEINEN von ihnen betrifft.
2. **Eine Quelle** — `preflight.unterminierte_tickets` und
   `aggregation.unterminierte_tickets` liefern dieselbe Liste. Ohne diesen Test waere
   die Weiterleitung nicht von einer zweiten Kopie zu unterscheiden (B033).
3. **Bei 0 vorhanden, mit 0 und []** — nie `None`, nie weggelassen (SWR-108: echte
   Null vs. nicht geliefert; SWR-114: ein stiller Check ist von einem nicht gelaufenen
   nicht zu unterscheiden).
"""
import os
import subprocess
import sys
import tempfile
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
from backend import aggregation  # noqa: E402
import preflight  # noqa: E402


class OrgKopfblockTest(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.verz = os.path.join(self.root, "p0", "tickets")
        os.makedirs(self.verz)

    def ticket(self, tid, projekt="p0", **felder):
        verz = os.path.join(self.root, projekt, "tickets")
        os.makedirs(verz, exist_ok=True)
        felder.setdefault("status", "open")
        felder.setdefault("typ", "task")
        zeilen = ["---", "id: %s" % tid]
        zeilen += ["%s: %s" % (k, v) for k, v in felder.items()]
        zeilen += ["---", "", "Text."]
        with open(os.path.join(verz, "%s.md" % tid), "w", encoding="utf-8") as f:
            f.write("\n".join(zeilen))

    # ---------------------------------------------------------------- Festlegung 1

    def test_kopfblock_steht_neben_projekte_und_traegt_zahl_und_refs(self):
        """SWR-117 (1): `organisation` als eigener Schluessel, mit Zahl UND Namen."""
        self.ticket("T-0001")
        nutzlast = aggregation.cockpit_alle(self.root)
        self.assertIn("organisation", nutzlast)
        self.assertEqual(nutzlast["organisation"]["unterminiert_gesamt"], 1)
        self.assertEqual(nutzlast["organisation"]["unterminiert_refs"], ["p0/T-0001"])

    def test_projekte_bleibt_in_form_und_reihenfolge_unangetastet(self):
        """SWR-117 (1), der Gegentest gegen eine Umhuellung.

        Wuerde der Kopfblock `projekte` umhuellen oder umsortieren, aendert sich die
        Antwort fuer jeden heutigen Leser (HMI, Widget, beide Uebereinstimmungstests) —
        wegen einer Zahl, die keinen von ihnen betrifft.
        """
        self.ticket("T-0001")
        self.ticket("T-0002", projekt="p1")
        nutzlast = aggregation.cockpit_alle(self.root)
        self.assertIsInstance(nutzlast["projekte"], list)
        self.assertEqual([e["projekt"] for e in nutzlast["projekte"]],
                         aggregation.projekte(self.root))

    def test_ein_weiterer_schluessel_im_block_laesst_leser_unveraendert(self):
        """SWR-117 (1): der Block ist um eine zweite Zahl erweiterbar (pm/T-0051),
        ohne dass ein Leser sich aendert — genau das macht die zweite Zahl zu einer
        Ergaenzung in eine feststehende Form statt zu einer zweiten Vertragsfrage."""
        self.ticket("T-0001")
        block = dict(aggregation.organisation(self.root))
        block["wartet_auf_mensch_gesamt"] = 0  # so wuerde pm/T-0051 anbauen
        self.assertEqual(block["unterminiert_gesamt"], 1)
        self.assertEqual(block["unterminiert_refs"], ["p0/T-0001"])

    # ---------------------------------------------------------------- Festlegung 2

    def test_preflight_und_aggregation_liefern_dieselbe_liste(self):
        """SWR-117 (2): der Test, der eine zweite Quelle widerlegen wuerde (B033).

        Ohne ihn ist eine Weiterleitung von einer Kopie nicht zu unterscheiden — und
        eine Kopie ist genau das Risiko, das `pm/T-0047` Punkt 2 benannt hat.
        """
        self.ticket("T-0001")
        self.ticket("T-0002", projekt="p1")
        self.assertEqual(preflight.unterminierte_tickets(self.root),
                         aggregation.unterminierte_tickets(self.root))

    def test_kopfblock_zaehlt_dieselbe_liste_die_er_nennt(self):
        """SWR-117 (2)/B038: die Zahl ist die Laenge der genannten Liste und keine
        zweite Erhebung — ein Gate, das „82" sagt, nennt nicht, welche fuenf fehlen."""
        self.ticket("T-0001")
        self.ticket("T-0002", projekt="p1")
        block = aggregation.organisation(self.root)
        self.assertEqual(block["unterminiert_gesamt"], len(block["unterminiert_refs"]))

    # ---------------------------------------------------------------- Festlegung 3

    def test_bei_null_ist_der_block_da_mit_null_und_leerer_liste(self):
        """SWR-117 (3): nie weggelassen, nie `None`.

        Die Messung laeuft bei jedem Aufruf — die Null ist damit eine ECHTE Null im
        Sinne von SWR-108 (der leere Wert des Typs) und keine ausgebliebene Erhebung.
        """
        nutzlast = aggregation.cockpit_alle(self.root)
        self.assertIn("organisation", nutzlast)
        self.assertIsNotNone(nutzlast["organisation"])
        self.assertEqual(nutzlast["organisation"]["unterminiert_gesamt"], 0)
        self.assertEqual(nutzlast["organisation"]["unterminiert_refs"], [])

    # ---------------------------------------------------------------- Abgrenzung

    def test_abgrenzung_ist_die_von_swr_091(self):
        """SWR-117: Termin, Takt, decision-request und geschlossene Tickets sind
        ausgenommen — dieselbe Grenze wie die Kachelzahl, sonst zaehlten zwei Stellen
        verschieden (B033).

        ⚠ SWR-125: 'Termin' heisst ab Sprint 11 `geplant_sprint`, beim DR weiter `frist`.
        Zwei Provokationen sind mitgewandert, die ZUSAGE dieses Tests ist unveraendert —
        er prueft, dass Kachel und Org-Summe dieselbe Grenze ziehen, nicht welche.
        Der DR bekommt seine `frist`, weil der Test sie im Docstring als Steuerung nennt
        und sie vorher NICHT hatte (derselbe Fall wie in test_preflight_unterminiert)."""
        self.ticket("T-0001", geplant_sprint="12")
        self.ticket("T-0002", takt="je-session")
        self.ticket("T-0003", typ="decision-request", frist="2026-08-20")
        self.ticket("T-0004", status="done")
        self.ticket("T-0005", status="rejected")
        block = aggregation.organisation(self.root)
        # Geprüft wird die ZAHL dieses Tickets, nicht der ganze Block: seit SWR-120
        # steht eine zweite Kennzahl daneben, und ein Gleichheitsvergleich über den
        # ganzen Block wäre ein Test, der bei jeder Erweiterung bricht, ohne dass an
        # der geprüften Sache etwas falsch wäre.
        self.assertEqual(block["unterminiert_gesamt"], 0)
        self.assertEqual(block["unterminiert_refs"], [])

    def test_zwei_projekte_werden_summiert(self):
        """Der Kern von B049: „Kachel X erledigt" ist keine gueltige Abschlussmeldung,
        wenn die Frage der Organisation gilt."""
        self.ticket("T-0001")
        self.ticket("T-0002", projekt="p1")
        block = aggregation.organisation(self.root)
        self.assertEqual(block["unterminiert_gesamt"], 2)
        self.assertEqual(sorted(block["unterminiert_refs"]), ["p0/T-0001", "p1/T-0002"])


class BestandsUebereinstimmungTest(unittest.TestCase):
    """Gegenprobe am echten Bestand statt nur an gebauten Faellen.

    SWR-114 hat denselben Test gegen die Kachelsumme gestellt; SWR-117 zieht ihn auf
    die dritte Stelle aus, an der die Zahl jetzt steht. Laufen die drei auseinander,
    ist die „eine Quelle" eine Behauptung.
    """

    def setUp(self):
        self.wurzel = os.path.abspath(os.path.join(_HIER, "..", ".."))
        if not os.path.isdir(os.path.join(self.wurzel, "pm", "tickets")):
            self.skipTest("kein Bestand unter der Wurzel")

    def test_kopfblock_kachelsumme_und_preflightzeile_stimmen_ueberein(self):
        nutzlast = aggregation.cockpit_alle(self.wurzel)
        block = nutzlast["organisation"]
        kachelsumme = sum(e.get("unterminiert", 0) for e in nutzlast["projekte"])
        self.assertEqual(block["unterminiert_gesamt"], kachelsumme)
        self.assertEqual(block["unterminiert_refs"],
                         preflight.unterminierte_tickets(self.wurzel))


class HmiKopfblockTest(unittest.TestCase):
    """SWR-117 (3): das HMI rendert den Block ueber den Kacheln — auch bei 0.

    Geprueft am ausgelieferten `app.js` und nicht an einer Beschreibung davon: die
    Reihenfolge im DOM ist die Zusicherung („ueber den Kacheln"), und ein `if (n)` um
    den Aufruf waere genau das Schweigen bei 0, das SWR-114 ausgeschlossen hat.
    """

    def setUp(self):
        pfad = os.path.join(_HIER, "..", "backend", "static", "app.js")
        with open(pfad, encoding="utf-8") as f:
            self.js = f.read()

    def test_kopfblock_wird_vor_den_projektgruppen_eingehaengt(self):
        self.assertIn("orgKopfblock(u.organisation)", self.js)
        self.assertLess(self.js.index("orgKopfblock(u.organisation)"),
                        self.js.index('["festes-team", "Feste Teams"]'))

    def test_kopfblock_haengt_nicht_an_der_zahl_sondern_am_block(self):
        """Der Gegentest: `if (u.organisation)` und nicht
        `if (u.organisation.unterminiert_gesamt)` — sonst verschwaende der Block bei 0
        und ein gepruefter Bestand saehe aus wie ein ungeprueter."""
        self.assertIn("if (u.organisation) teile.push", self.js)
        self.assertNotIn("if (u.organisation.unterminiert_gesamt)", self.js)

    def test_referenzen_stehen_neben_der_zahl(self):
        """B038: die Namen, nicht nur die Zahl."""
        self.assertIn("unterminiert_refs", self.js)


class VertragTest(unittest.TestCase):
    """Der Widget-Vertrag wird nachgezogen (T-0047 DoD 4).

    `team-dashboard/vertrag/widget-vertrag-v2.yaml` ist laut eigenem Kopf DIE EINZIGE
    STELLE, DIE DIE FELDLISTE FUEHRT. Ein neuer Payload-Schluessel, der dort fehlt,
    waere ein Vertrag, der den ausgelieferten Payload nicht mehr beschreibt.
    """

    def test_organisation_steht_im_vertrag(self):
        pfad = os.path.join(_HIER, "..", "..", "team-dashboard", "vertrag",
                            "widget-vertrag-v2.yaml")
        if not os.path.exists(pfad):
            self.skipTest("Vertrag nicht unter der Wurzel")
        with open(pfad, encoding="utf-8") as f:
            vertrag = f.read()
        self.assertIn("organisation", vertrag)
        self.assertIn("unterminiert_gesamt", vertrag)
        self.assertIn("unterminiert_refs", vertrag)


if __name__ == "__main__":
    unittest.main()
