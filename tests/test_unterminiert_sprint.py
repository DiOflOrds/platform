"""Terminierung in SPRINTS statt in Kalenderdaten (SWR-125, platform/T-0012).

Anlass ist Brief pm/N-0041 — die ZWEITE Meldung derselben Sache durch den
Auftraggeber. Die erste fuehrte zu SWR-106 ("Terminierung auf Sprints statt auf
Kalenderdaten", Anforderungen v1.12). Geaendert wurde damals der Beschluss, nicht
die Pruefung: `unterminierte_tickets` fragte weiter nach `frist`, und weil
"unterminiert 0" zu den Zahlen gehoert, die jeder Sprintabschluss BERICHTET,
schrieb jeder Lauf pflichtbewusst ein Datum hinein.

  Eine Entscheidung, die keine Pruefung mitgeaendert hat, ist eine
  Absichtserklaerung.

Gegenprobe zu jedem Test dieser Datei: er scheitert gegen den Vorstand von
Sprint 10. Die beiden Faelle, die dort GRUEN waren und hier ROT sein muessen,
stehen zuerst.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import preflight  # noqa: E402
from backend import aggregation  # noqa: E402


class Bestand(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.verz = os.path.join(self.root, "p0", "tickets")
        os.makedirs(self.verz)

    def ticket(self, tid, **felder):
        felder.setdefault("status", "open")
        felder.setdefault("typ", "task")
        zeilen = ["---", "id: %s" % tid]
        zeilen += ["%s: %s" % (k, v) for k, v in felder.items()]
        zeilen += ["---", "", "Text."]
        with open(os.path.join(self.verz, "%s.md" % tid), "w", encoding="utf-8") as f:
            f.write("\n".join(zeilen))


class UmkehrungTest(Bestand):
    """Die Frage lautet ab jetzt 'hat einen Sprint?' statt 'hat ein Datum?'."""

    def test_nur_ein_kalenderdatum_terminiert_nicht_mehr(self):
        """DER Fall. Gegen den Vorstand war das gruen — genau daran lag es.

        Gemessen am Bestand vom 2026-08-17: alle 14 offenen Nicht-DR-Tickets trugen
        eine Frist +168 bis +408 Sprints hinter ihrem geplanten Sprint (Median +240).
        Eine Frist, die 240 Laeufe hinter der Aufgabe liegt, kann nicht reissen.
        """
        self.ticket("T-0001", frist="2026-09-03")
        self.assertEqual(preflight.unterminierte_tickets(self.root), ["p0/T-0001"])

    def test_sprintnummer_ohne_datum_terminiert(self):
        """Die Gegenrichtung — gegen den Vorstand war GENAU DAS der Befund."""
        self.ticket("T-0002", geplant_sprint="12")
        self.assertEqual(preflight.unterminierte_tickets(self.root), [])

    def test_sprint_null_ist_eine_angabe_und_kein_fehlendes_feld(self):
        """`0` ist falsy in Python — die Abgrenzung fragt nach dem TEXT, nicht nach
        Wahrheit. Ein Ticket auf Sprint 0 ist terminiert (und wird, wenn die Nummer
        vorbei ist, von `sprint_vergangen` gemeldet — das ist die andere Frage)."""
        self.ticket("T-0003", geplant_sprint="0")
        self.assertEqual(preflight.unterminierte_tickets(self.root), [])

    def test_leeres_sprintfeld_zaehlt_nicht_als_angabe(self):
        self.ticket("T-0004", geplant_sprint="")
        self.assertEqual(preflight.unterminierte_tickets(self.root), ["p0/T-0004"])

    def test_takt_dauerlaeufer_bleiben_unberuehrt(self):
        """SWR-074: ihr Zeitkonzept steht im Feld `takt`, in keinem der beiden anderen."""
        self.ticket("T-0005", takt="je-session")
        self.assertEqual(preflight.unterminierte_tickets(self.root), [])

    def test_geschlossene_sind_nie_gegenstand(self):
        self.ticket("T-0006", status="done", frist="2026-09-03")
        self.ticket("T-0007", status="rejected")
        self.assertEqual(preflight.unterminierte_tickets(self.root), [])


class MenschTest(Bestand):
    """Wo ein Mensch wartet, bleibt das Datum — an BEIDEN Enden gleich gezogen."""

    def test_entscheidungsvorlage_mit_frist_ist_terminiert(self):
        """Die Antwortzeit eines Menschen laeuft in Tagen, nicht in 60-Minuten-Laeufen.
        Dieselbe Grenze zieht `sprint_vergangen` (SWR-112) bereits in der
        Gegenrichtung."""
        self.ticket("T-0010", typ="decision-request", frist="2026-08-20")
        self.assertEqual(preflight.unterminierte_tickets(self.root), [])

    def test_entscheidungsvorlage_ohne_frist_ist_unterminiert(self):
        """⚠ Gegen den Vorstand gruen: dort war JEDER DR ausgenommen, auch einer voellig
        ohne Termin. Im Bestand tragen 3 von 46 DRs keine Frist (p0/T-0022, T-0035,
        T-0041) — die Pruefung konnte sie nicht sehen."""
        self.ticket("T-0011", typ="decision-request")
        self.assertEqual(preflight.unterminierte_tickets(self.root), ["p0/T-0011"])

    def test_entscheidungsvorlage_braucht_keinen_sprint(self):
        """Eine Sprintnummer am DR waere eine Zusage ueber einen fremden Kalender."""
        self.ticket("T-0012", typ="decision-request", frist="2026-08-20")
        self.assertEqual(aggregation.kalenderfristen(self.root), [])


class KalenderfristTest(Bestand):
    """Die zweite Haelfte, und die wichtigere: die Rueckkehr wird GEMELDET.

    'Nicht mehr gefordert' ist genau der Zustand, aus dem der Befund entstand —
    SWR-106 hatte Kalenderdaten fuenf Sprints frueher abgeschafft, und weil ihre
    Rueckkehr niemand meldete, waren kurz darauf wieder 14 Stueck da.
    """

    def test_teamaufgabe_mit_datum_wird_gemeldet(self):
        self.ticket("T-0020", geplant_sprint="12", frist="2026-08-24")
        self.assertEqual(aggregation.kalenderfristen(self.root), ["p0/T-0020"])

    def test_teamaufgabe_ohne_datum_ist_kein_treffer(self):
        self.ticket("T-0021", geplant_sprint="12")
        self.assertEqual(aggregation.kalenderfristen(self.root), [])

    def test_entscheidungsvorlage_mit_datum_ist_kein_treffer(self):
        """Dort IST das Datum die Steuerung — kein Befund, sondern der Sollzustand."""
        self.ticket("T-0022", typ="decision-request", frist="2026-08-20")
        self.assertEqual(aggregation.kalenderfristen(self.root), [])

    def test_geschlossene_werden_nicht_nachtraeglich_geruegt(self):
        """Der Bestand von 46 erledigten DRs und dutzenden Tickets bleibt, wie er ist —
        dieselbe Regel wie bei `sprint_vergangen` (SWR-112, Abgrenzung 1)."""
        self.ticket("T-0023", status="done", frist="2026-08-24")
        self.assertEqual(aggregation.kalenderfristen(self.root), [])

    def test_meldet_referenzen_und_nicht_nur_eine_zahl(self):
        """B038: ein Gate, das '2' sagt, nennt nicht, welche zwei."""
        self.ticket("T-0024", geplant_sprint="12", frist="2026-08-24")
        zweit = os.path.join(self.root, "p1", "tickets")
        os.makedirs(zweit)
        with open(os.path.join(zweit, "T-0030.md"), "w", encoding="utf-8") as f:
            f.write("---\nid: T-0030\nstatus: open\ntyp: task\nfrist: 2026-08-30\n---\n")
        self.assertEqual(sorted(aggregation.kalenderfristen(self.root)),
                         ["p0/T-0024", "p1/T-0030"])

    def test_weiterleitung_und_rumpf_liefern_dasselbe(self):
        """SWR-117: eine Quelle. Die Weiterleitung ist der Beleg, keine zweite Meinung."""
        self.ticket("T-0025", geplant_sprint="12", frist="2026-08-24")
        self.assertEqual(preflight.kalenderfristen(self.root),
                         aggregation.kalenderfristen(self.root))


class EineAbgrenzungTest(Bestand):
    """B033: Kachelzahl und Org-Summe duerfen nicht verschieden zaehlen."""

    def test_kachel_und_orgsumme_nutzen_dieselbe_abgrenzung(self):
        """Die Regel steht genau einmal — in `_ist_unterminiert`. Dieser Test haelt sie
        dort fest: waere sie zweimal geschrieben, koennte eine der beiden Stellen bei
        der naechsten Aenderung stehenbleiben. Genau das ist SWR-125 passiert."""
        faelle = [
            ({"typ": "task", "geplant_sprint": "12"}, False),
            ({"typ": "task", "frist": "2026-09-03"}, True),
            ({"typ": "task"}, True),
            ({"typ": "task", "takt": "je-session"}, False),
            ({"typ": "decision-request", "frist": "2026-08-20"}, False),
            ({"typ": "decision-request"}, True),
        ]
        for fm, erwartet in faelle:
            self.assertEqual(aggregation._ist_unterminiert(fm), erwartet, msg=str(fm))


if __name__ == "__main__":
    unittest.main()


class KopfblockTest(Bestand):
    """Der Kopfblock zeigt die Kalenderfristen — dort sieht der Auftraggeber hin.

    Eine Pruefung, deren Ergebnis nur im Startcheck erscheint, ist die halbe
    Wiederholung von SWR-122: die Rueckkehr der Kalenderdaten hat niemand bemerkt,
    weil sie niemandem angezeigt wurde.
    """

    def test_block_nennt_zahl_und_referenzen(self):
        self.ticket("T-0040", geplant_sprint="12", frist="2026-08-24")
        block = aggregation.organisation(self.root)
        self.assertEqual(block["kalenderfristen_gesamt"], 1)
        self.assertEqual(block["kalenderfristen_refs"], ["p0/T-0040"])

    def test_block_ist_bei_null_da_und_nicht_weggelassen(self):
        """SWR-108/SWR-114: eine echte Null, keine ausgebliebene Erhebung."""
        self.ticket("T-0041", geplant_sprint="12")
        block = aggregation.organisation(self.root)
        self.assertEqual(block["kalenderfristen_gesamt"], 0)
        self.assertEqual(block["kalenderfristen_refs"], [])

    def test_die_bestehenden_schluessel_bleiben_unveraendert(self):
        """Vertrags-ERWEITERUNG, nicht -aenderung — die Form aus SWR-117 haelt."""
        block = aggregation.organisation(self.root)
        for schluessel in ("unterminiert_gesamt", "unterminiert_refs",
                           "wartet_auf_mensch_gesamt", "wartet_auf_mensch_refs"):
            self.assertIn(schluessel, block)
