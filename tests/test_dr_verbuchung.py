"""SWR-131 (platform/T-0014): eine entschiedene Frage darf nicht als offen gelten —
und ein entschiedener, nicht verbuchter DR darf nicht still verschwinden.

⚠ **Anlass, gemessen.** Am 2026-08-17 um 11:48:25 hat der Auftraggeber
`projects/p12/T-0007` ueber die Inbox mit `B-node-optional` entschieden. Sechzehn Minuten
spaeter legten ihm drei Berichte dieselbe Frage erneut vor. Ursache: `inbox` liest
„entschieden" am Rumpfmarker, `board`/`aggregation`/`preflight` lasen ihn am `status` —
und `inbox.entscheide` setzt `status` nie.

Die Tests hier sichern **beide** Haelften. Die erste allein waere eine Verschlechterung:
sie laesst den Fall aus jeder Anzeige verschwinden, ohne dass ihn jemand sieht.
"""
import os
import shutil
import sys
import tempfile
import textwrap
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
import board  # noqa: E402
from backend import aggregation  # noqa: E402
from backend import inbox  # noqa: E402


def _ticket(**felder):
    """Ein Ticket-Dict wie `parse_frontmatter` es liefert — inklusive `_body`."""
    t = {"id": "T-0001", "typ": "decision-request", "status": "open", "_body": ""}
    t.update(felder)
    return t


ENTSCHEIDUNGSZEILE = ("**Entscheidung (D002, via Inbox, 2026-08-17 11:48):** "
                      "B-node-optional")


class DrEntschiedenTest(unittest.TestCase):
    """`board.dr_entschieden` — der eine Aufloesungspunkt."""

    def test_marker_im_rumpf_gilt_als_entschieden(self):
        """Der Fall p12/T-0007: Status offen, Entscheidung im Rumpf."""
        t = _ticket(_body="## Herkunft\n\n" + ENTSCHEIDUNGSZEILE)
        self.assertTrue(board.dr_entschieden(t))

    def test_finaler_status_gilt_als_entschieden(self):
        """Die 42 Altfaelle: verbucht auf `done` bzw. `rejected`."""
        self.assertTrue(board.dr_entschieden(_ticket(status="done")))
        self.assertTrue(board.dr_entschieden(_ticket(status="rejected")))

    def test_offener_dr_ohne_marker_ist_nicht_entschieden(self):
        """GEGENPROBE (a): sonst haette die Reparatur jeden DR stillgelegt."""
        t = _ticket(_body="## Optionen\n\n| A | B | C |\n\nFrist 2026-08-24.")
        self.assertFalse(board.dr_entschieden(t))

    def test_blosse_erwaehnung_ist_keine_entscheidung(self):
        """GEGENPROBE (b): das Wort im Fliesstext ist keine Entscheidung.

        ⚠ Ohne diesen Test genuegte ein Satz wie *„die Entscheidung (D002) steht noch
        aus"*, um ein offenes Ticket als erledigt gelten zu lassen — die Pruefung haette
        dann genau die Textsorte bestraft, die einen offenen Punkt **erklaert**.
        Dieselbe Falle wie der Kommentar-Fehlalarm beim Bau von SWR-128.
        """
        self.assertFalse(board.dr_entschieden(
            _ticket(_body="Die **Entscheidung (D002)** steht noch aus, siehe Frist.")))
        self.assertFalse(board.dr_entschieden(
            _ticket(_body="Wir erwarten eine Entscheidung (D002) bis zum 24.08.")))

    def test_marker_eingerueckt_zaehlt(self):
        """Eingerueckt (Listenpunkt, Zitat) zaehlt — nur mitten im Satz nicht."""
        self.assertTrue(board.dr_entschieden(_ticket(_body="  " + ENTSCHEIDUNGSZEILE)))

    def test_fehlender_body_faellt_auf_den_status_zurueck(self):
        """Aufrufer mit reinem Frontmatter-Dict bekommen keine Ausnahme."""
        self.assertFalse(board.dr_entschieden({"typ": "decision-request",
                                               "status": "open"}))
        self.assertTrue(board.dr_entschieden({"typ": "decision-request",
                                              "status": "done"}))

    def test_inbox_fuehrt_keine_zweite_kopie(self):
        """B033: `inbox.ENTSCHIEDEN` IST der Marker aus `board`, keine Abschrift.

        ⚠ Geprueft wird die **Identitaet der Quelle**, nicht nur der Wert: zwei
        gleichlautende Zeichenketten in zwei Dateien sind genau der Zustand, der den
        Fehler erzeugt hat, und ein Wertvergleich wuerde ihn durchlassen.
        """
        self.assertIs(inbox.ENTSCHIEDEN, board.ENTSCHEIDUNGSMARKER)
        self.assertIs(inbox.FINAL, board.STATUS_FINAL)


class WartetAufMenschTest(unittest.TestCase):
    """Der Satz aus dem SWR-120-Docstring wird erstmals wirksam."""

    def test_entschiedener_dr_wartet_auf_niemanden(self):
        t = _ticket(verantwortlich="mensch", _body=ENTSCHEIDUNGSZEILE)
        self.assertFalse(board.wartet_auf_mensch(t))

    def test_unentschiedener_dr_wartet_weiterhin(self):
        """GEGENPROBE (a), zweite Haelfte: der Zaehler ist nicht abgeschaltet."""
        self.assertTrue(board.wartet_auf_mensch(_ticket(_body="offen, Frist 24.08.")))

    def test_nicht_dr_mit_verantwortlich_mensch_bleibt_unberuehrt(self):
        """SWR-116 gilt unveraendert — die Aenderung betrifft nur `decision-request`."""
        t = _ticket(typ="task", verantwortlich="mensch", _body=ENTSCHEIDUNGSZEILE)
        self.assertTrue(board.wartet_auf_mensch(t))


class DrNichtVerbuchtTest(unittest.TestCase):
    """`aggregation.dr_entschieden_nicht_verbucht` — der Leser (SWR-122)."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def ticket(self, tid, projekt="pm", **felder):
        verz = os.path.join(self.root, projekt, "tickets")
        os.makedirs(verz, exist_ok=True)
        felder.setdefault("typ", "decision-request")
        felder.setdefault("status", "open")
        felder.setdefault("repo", projekt)
        kopf = "\n".join(f"{k}: {v}" for k, v in felder.items())
        rumpf = felder.pop("_rumpf", "")
        with open(os.path.join(verz, tid + ".md"), "w", encoding="utf-8") as f:
            f.write(f"---\nid: {tid}\n{kopf}\n---\n\n{rumpf}\n")

    def test_befund_nennt_das_ticket(self):
        """B038: eine Zahl sagt nicht, welches — der Befund nennt die Kennung."""
        self.ticket("T-0007")
        with open(os.path.join(self.root, "pm", "tickets", "T-0007.md"),
                  "a", encoding="utf-8") as f:
            f.write("\n" + ENTSCHEIDUNGSZEILE + "\n")
        treffer = aggregation.dr_entschieden_nicht_verbucht(self.root)
        self.assertEqual(len(treffer), 1)
        self.assertIn("T-0007", treffer[0])

    def test_verbuchter_dr_erzeugt_keinen_befund(self):
        """GEGENPROBE (c): sonst waere der Befund am Einfuehrungstag 42-fach rot.

        ⚠ Ein Befund, der beim Einschalten sofort an Altbestand anschlaegt, wird binnen
        eines Laufs als Rauschen gelesen — dieselbe Fehlerart, die den Altbestand von 52
        unzulaessigen Statusuebergaengen bis heute unbereinigt laesst.
        """
        self.ticket("T-0007", status="done")
        with open(os.path.join(self.root, "pm", "tickets", "T-0007.md"),
                  "a", encoding="utf-8") as f:
            f.write("\n" + ENTSCHEIDUNGSZEILE + "\n")
        self.assertEqual(aggregation.dr_entschieden_nicht_verbucht(self.root), [])

    def test_offener_unentschiedener_dr_ist_kein_befund(self):
        """Ein DR, der wirklich beim Menschen liegt, ist der Normalfall."""
        self.ticket("T-0007")
        with open(os.path.join(self.root, "pm", "tickets", "T-0007.md"),
                  "a", encoding="utf-8") as f:
            f.write("\nOptionen A/B/C. Die Entscheidung (D00x) steht noch aus.\n")
        self.assertEqual(aggregation.dr_entschieden_nicht_verbucht(self.root), [])

    def test_nicht_dr_wird_nicht_eingesammelt(self):
        """Der Befund ist ueber DRs, nicht ueber Tickets mit dem Wort im Rumpf."""
        self.ticket("T-0008", typ="task")
        with open(os.path.join(self.root, "pm", "tickets", "T-0008.md"),
                  "a", encoding="utf-8") as f:
            f.write("\n" + ENTSCHEIDUNGSZEILE + "\n")
        self.assertEqual(aggregation.dr_entschieden_nicht_verbucht(self.root), [])

    def test_beide_haelften_greifen_am_selben_ticket(self):
        """⚠ Der eigentliche Test der Anforderung — beide Haelften an EINEM Fall.

        Der entschiedene, unverbuchte DR verschwindet aus „wartet auf den Menschen"
        **und** erscheint im Befund. Faellt eine der beiden Haelften weg, ist das
        Ergebnis entweder die alte Falschmeldung (er wartet) oder ein stiller Verlust
        (er wartet nicht und niemand sieht ihn) — die zweite ist die schlimmere.
        """
        self.ticket("T-0007", verantwortlich="mensch")
        with open(os.path.join(self.root, "pm", "tickets", "T-0007.md"),
                  "a", encoding="utf-8") as f:
            f.write("\n" + ENTSCHEIDUNGSZEILE + "\n")
        self.assertEqual(aggregation.wartet_auf_mensch(self.root), [])
        self.assertEqual(len(aggregation.dr_entschieden_nicht_verbucht(self.root)), 1)


class AlleLeserTest(unittest.TestCase):
    """⚠ SWR-131 sagt „**jeder** Leser" — und der erste Anlauf hat zwei uebersehen.

    Beim Bau dieser Anforderung wurden zunaechst nur `board`/`aggregation`/`preflight`
    umgestellt. Die Nachpruefung fand **zwei weitere** Leser mit eigener Kopie des
    Markers: `aggregation.cockpit` (Zeile 435) und `dr_benachrichtigung`. Der zweite ist
    der schwerere Fall — er verschickt E-Mails, und sein Filter kannte „entschieden"
    nicht.

    Diese Klasse ist deshalb keine Wiederholung, sondern der Test gegen die
    **Vollstaendigkeit** der Umstellung: sie zaehlt die Kopien im Quelltext.
    """

    def test_keine_zweite_kopie_des_markers_im_quelltext(self):
        """Der Zaehler gegen die Rueckkehr: ausser `board` fuehrt keine Datei ihn selbst.

        ⚠ Ohne diesen Test waere „eine Stelle" eine Aussage ueber den Tag der Einfuehrung
        und nicht ueber den Bestand — genau die Lehre aus SWR-125 (eine Regel ohne
        Pruefung kehrt zurueck: SWR-106 schaffte Kalenderdaten ab, fuenf Sprints spaeter
        waren 14 wieder da).

        ⚠⚠ **Diese Zusicherung hat auf eine ZEILENNUMMER geprueft** (`scripts/board.py:673`)
        und wurde in Sprint 17 rot, weil SWR-144 zwanzig Zeilen weiter oben eine
        Ausnahmeklasse eingefuegt hat. Der Marker stand unveraendert genau einmal da; falsch
        war die Zusicherung.

        > **Eine Zeilennummer ist keine Eigenschaft des Bestands, sondern eine Eigenschaft
        > des Tages, an dem gemessen wurde.**

        Ein Fehlalarm ist hier besonders teuer: dieser Test existiert gegen das Wegsehen
        (SWR-125), und ein Test, der bei jeder fremden Einfuegung rot wird, erzieht genau
        dazu. Geprueft wird deshalb die **Datei** und die **Anzahl** — die beiden Aussagen,
        die der Docstring macht.
        """
        wurzel = os.path.dirname(_HIER)
        literal = '"**Entscheidung ('
        treffer = []
        for verz in ("backend", "scripts"):
            for name in sorted(os.listdir(os.path.join(wurzel, verz))):
                if not name.endswith(".py"):
                    continue
                pfad = os.path.join(wurzel, verz, name)
                with open(pfad, encoding="utf-8") as f:
                    for nr, zeile in enumerate(f, 1):
                        if literal in zeile:
                            treffer.append(f"{verz}/{name}:{nr}")
        dateien = sorted({t.rsplit(":", 1)[0] for t in treffer})
        self.assertEqual(dateien, ["scripts/board.py"],
                         f"Marker-Kopien ausserhalb von board.py: {treffer}")
        self.assertEqual(len(treffer), 1, f"erwartet genau eine Definition, gefunden: {treffer}")

    def test_benachrichtigungsweg_delegiert_ebenfalls(self):
        """⚠ Der Fall mit Aussenwirkung — hier nur die Delegation, das Verhalten prueft
        `test_dr_benachrichtigung.py` an seinem eigenen Fixture (dort liegt der
        Versandpfad, und zwei Fixtures fuer eine Sache waeren B033).
        """
        sys.path.insert(0, os.path.join(os.path.dirname(_HIER), "scripts"))
        import dr_benachrichtigung
        self.assertIs(dr_benachrichtigung.ENTSCHIEDEN, board.ENTSCHEIDUNGSMARKER)
        self.assertIs(dr_benachrichtigung.FINAL, board.STATUS_FINAL)


class BestandTest(unittest.TestCase):
    """Der ECHTE Bestand, nicht ein Modell in tmp.

    ⚠ Diese Zusicherung ist die Lehre aus SWR-128: konstruierte Faelle koennen alle
    gruen sein, waehrend die Flaeche, um die es geht, ungeprueft bleibt.
    """

    def test_kein_entschiedener_dr_ist_unverbucht(self):
        root = os.path.dirname(os.path.dirname(_HIER))
        if not os.path.isdir(os.path.join(root, "pm", "tickets")):
            self.skipTest("Bestand nicht vorhanden (isolierte Testumgebung)")
        self.assertEqual(aggregation.dr_entschieden_nicht_verbucht(root), [])


if __name__ == "__main__":
    unittest.main()
