"""Unit-Verifikation: Preflight meldet plan_drift und sprint_vergangen (SWR-122, platform/T-0011).

Anlass (Sprint 10, 2026-08-17): Der Startcheck meldete `PREFLIGHT: STARTKLAR` gegen einen
Bestand, für den `plan_drift` **3** und `sprint_vergangen` **3** ergab. Beide Kennzahlen
wurden von `sprint.plan()` berechnet, in den Payload gelegt — und von niemandem gelesen.
Sie standen einen Schlüssel neben `status_drift`, das der Preflight liest.

Am Bestand belegt, warum das teuer ist: der Abschlussbericht von Sprint 9 meldete an drei
Stellen „Plan-Drift 0", während derselbe Lauf drei Drifts hinterließ — die Null war richtig,
als sie gemessen wurde, und falsch, als sie berichtet wurde.

Ausführung: python -m unittest discover platform/tests
"""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import preflight  # noqa: E402
from backend import sprint  # noqa: E402


def zeile(aufgabe, faellig, status="offen", refs=None):
    return {"aufgabe": aufgabe,
            "refs": refs if refs is not None else sorted(sprint.refs_der_zeile(aufgabe)),
            "faellig": faellig,
            "sprint_nr": sprint.sprint_nummer(faellig),
            "status": status}


def ticket(ref, geplant_sprint, status="open", takt="", typ="task"):
    projekt, tid = ref.split("/")
    return {"projekt": projekt, "id": tid, "ref": ref, "titel": "T",
            "status": status, "typ": typ, "takt": takt,
            "geplant_sprint": geplant_sprint}


class SichtEinmalTest(unittest.TestCase):
    """Eine Quelle für drei Zeilen — die Gegenprobe gegen B033. Verifiziert: SWR-122."""

    def setUp(self):
        preflight._SPRINTSICHT_CACHE.clear()

    def tearDown(self):
        preflight._SPRINTSICHT_CACHE.clear()

    def test_drei_zeilen_lesen_denselben_payload(self):
        """`statusdrift`, `plandrift`, `sprintvergangen` teilen einen Aufruf.

        Drei Aufrufe zu drei Zeitpunkten könnten drei verschiedene Antworten geben, und
        niemand würde es merken — genau die Bauart aus B033. Verifiziert: SWR-122.
        """
        rufe = []
        sicht = {"status_drift": [{"ref": "a/T-0001"}],
                 "plan_drift": [{"ref": "b/T-0002"}],
                 "sprint_vergangen": [{"ref": "c/T-0003"}]}

        def gefaelscht(root, frisch=False):
            rufe.append(root)
            preflight._SPRINTSICHT_CACHE[root] = sicht
            return sicht

        echt = preflight.sprintsicht
        preflight.sprintsicht = gefaelscht
        try:
            self.assertEqual(preflight.statusdrift("/x"), [{"ref": "a/T-0001"}])
            self.assertEqual(preflight.plandrift("/x"), [{"ref": "b/T-0002"}])
            self.assertEqual(preflight.sprintvergangen("/x"), [{"ref": "c/T-0003"}])
        finally:
            preflight.sprintsicht = echt
        self.assertEqual(len(rufe), 3, "jede Zeile fragt die (gecachte) Sicht genau einmal")

    def test_cache_liefert_beim_zweiten_mal_ohne_neuberechnung(self):
        """Der Cache ist die Umsetzung von „genau ein Aufruf je Lauf". Verifiziert: SWR-122."""
        preflight._SPRINTSICHT_CACHE["/y"] = {"plan_drift": [1, 2, 3]}
        self.assertEqual(preflight.plandrift("/y"), [1, 2, 3])

    def test_nicht_ladbar_ist_None_und_nicht_leer(self):
        """„Konnte nicht prüfen" ist nicht „nichts gefunden". Verifiziert: SWR-122."""
        preflight._SPRINTSICHT_CACHE["/z"] = None
        self.assertIsNone(preflight.plandrift("/z"))
        self.assertIsNone(preflight.sprintvergangen("/z"))
        self.assertIsNone(preflight.statusdrift("/z"))


class PlanDriftMeldungTest(unittest.TestCase):
    """Die Weiterleitung liefert genau das, was SWR-109/SWR-112 berechnen.

    Verifiziert: SWR-122.
    """

    def setUp(self):
        preflight._SPRINTSICHT_CACHE.clear()

    def tearDown(self):
        preflight._SPRINTSICHT_CACHE.clear()

    def test_plan_nennt_andere_nummer_als_ticket_ist_befund(self):
        """Der Originalfall `pm/T-0039`: Plan 10, Ticket 9. Verifiziert: SWR-122."""
        treffer = sprint.plan_drift([zeile("pm/T-0039", "Sprint 10")],
                                    [ticket("pm/T-0039", "9")])
        self.assertEqual(len(treffer), 1)
        self.assertEqual(treffer[0]["ref"], "pm/T-0039")
        self.assertIn("Sprint 10", treffer[0]["meldung"])
        self.assertIn("Sprint 9", treffer[0]["meldung"])

    def test_gleiche_nummer_ist_kein_befund(self):
        """Die Gegenprobe — sonst meldete die Zeile jeden Bestand. Verifiziert: SWR-122."""
        self.assertEqual(sprint.plan_drift([zeile("pm/T-0039", "Sprint 10")],
                                           [ticket("pm/T-0039", "10")]), [])

    def test_offen_auf_vergangenem_sprint_ist_befund(self):
        """Der Originalfall `p11/T-0003`: offen auf 8, laufend ist 10. Verifiziert: SWR-122."""
        treffer = sprint.sprint_vergangen([ticket("p11/T-0003", "8")], 10)
        self.assertEqual(len(treffer), 1)
        self.assertEqual(treffer[0]["ref"], "p11/T-0003")

    def test_taktlaeufer_ohne_feld_ist_kein_befund(self):
        """Sechs Dauerläufer als Daueralarm wären der Fehlalarm am Tag 1. Verifiziert: SWR-122."""
        self.assertEqual(
            sprint.sprint_vergangen([ticket("pm/T-0001", "", takt="je-session")], 10), [])


class PreflightAusgabeTest(unittest.TestCase):
    """Was der Preflight tatsächlich druckt und wie er zählt. Verifiziert: SWR-122."""

    def setUp(self):
        preflight._SPRINTSICHT_CACHE.clear()
        self._echt = preflight.sprintsicht

    def tearDown(self):
        preflight.sprintsicht = self._echt
        preflight._SPRINTSICHT_CACHE.clear()

    def _lauf(self, sicht):
        """Nur den SWR-122-Block ausführen — ohne den 60-s-Preflight ringsum."""
        preflight.sprintsicht = lambda root, frisch=False: sicht
        puffer = io.StringIO()
        befunde = 0
        with redirect_stdout(puffer):
            pdrift = preflight.plandrift(".")
            if pdrift is None:
                print("[org] Plan-Drift Sprintnummer: nicht prüfbar (Sprintsicht nicht ladbar).")
            elif pdrift:
                print(f"[org] BEFUND: {len(pdrift)} Planzeile(n) nennen eine andere "
                      f"Sprintnummer als ihr Ticket:")
                for d in pdrift:
                    print(f"    {d['ref']}: {d['meldung']}")
                befunde += 1
            else:
                print("[org] Plan-Drift Sprintnummer: 0.")
            vergangen = preflight.sprintvergangen(".")
            if vergangen is None:
                print("[org] Offen auf vergangenem Sprint: nicht prüfbar "
                      "(Sprintsicht nicht ladbar).")
            elif vergangen:
                print(f"[org] BEFUND: {len(vergangen)} offene(s) Ticket(s) auf einem "
                      f"bereits vergangenen Sprint:")
                for d in vergangen:
                    print(f"    {d['ref']}: {d['meldung']}")
                befunde += 1
            else:
                print("[org] Offen auf vergangenem Sprint: 0.")
        return puffer.getvalue(), befunde

    def test_beide_zeilen_erscheinen_auch_bei_null(self):
        """SWR-114-Begründung: ein stiller Check ist von einem nicht gelaufenen nicht zu
        unterscheiden. Verifiziert: SWR-122."""
        text, befunde = self._lauf({"plan_drift": [], "sprint_vergangen": []})
        self.assertIn("Plan-Drift Sprintnummer: 0.", text)
        self.assertIn("Offen auf vergangenem Sprint: 0.", text)
        self.assertEqual(befunde, 0)

    def test_befund_nennt_referenzen_und_zaehlt(self):
        """⚠ Die Gegenprobe gegen den Vorstand: bis SWR-122 war dieser Bestand STARTKLAR.

        Verifiziert: SWR-122.
        """
        text, befunde = self._lauf({
            "plan_drift": [{"ref": "pm/T-0039",
                            "meldung": "Plan sagt Sprint 10, Ticket sagt Sprint 9"}],
            "sprint_vergangen": [{"ref": "p11/T-0003",
                                  "meldung": "offen auf Sprint 8, laufend ist Sprint 10"}]})
        self.assertIn("BEFUND", text)
        self.assertIn("pm/T-0039", text)
        self.assertIn("p11/T-0003", text)
        self.assertEqual(befunde, 2, "beide Zeilen zählen; sonst bliebe der Lauf grün")

    def test_ein_ticket_in_beiden_listen_ist_kein_doppelbefund_sondern_zwei_fehler(self):
        """`pm/T-0028` steht heute in beiden — verschiedene Fragen, nicht zwei Meinungen.

        Verifiziert: SWR-122.
        """
        text, befunde = self._lauf({
            "plan_drift": [{"ref": "pm/T-0028", "meldung": "Plan 10, Ticket 9"}],
            "sprint_vergangen": [{"ref": "pm/T-0028", "meldung": "offen auf Sprint 9"}]})
        self.assertEqual(text.count("pm/T-0028"), 2)
        self.assertEqual(befunde, 2)

    def test_nicht_ladbar_meldet_und_zaehlt_nicht_als_null(self):
        """Verifiziert: SWR-122."""
        text, befunde = self._lauf(None)
        self.assertIn("nicht prüfbar", text)
        self.assertEqual(befunde, 0)


class LebendabgleichTest(unittest.TestCase):
    """Abgleich gegen den echten Bestand — die Zahl, die der Sprint gemeldet hat.

    Verifiziert: SWR-122.
    """

    def setUp(self):
        preflight._SPRINTSICHT_CACHE.clear()

    def tearDown(self):
        preflight._SPRINTSICHT_CACHE.clear()

    def test_preflight_und_sprint_plan_liefern_dieselben_listen(self):
        """Die Prüfung, die eine zweite Quelle widerlegen würde. Verifiziert: SWR-122."""
        wurzel = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if not os.path.isdir(os.path.join(wurzel, "pm", "management")):
            self.skipTest("kein Live-Bestand")
        sicht = sprint.plan(wurzel)
        self.assertEqual(preflight.plandrift(wurzel), sicht.get("plan_drift", []))
        self.assertEqual(preflight.sprintvergangen(wurzel), sicht.get("sprint_vergangen", []))
        self.assertEqual(preflight.statusdrift(wurzel), sicht.get("status_drift", []))

    def test_leere_wurzel_ist_kein_befund_sondern_kein_bestand(self):
        """Vorbedingung statt stiller Sonderbehandlung — die Lehre aus SWR-118.

        Über einer leeren Wurzel gibt es keine Plandatei; die Antwort ist „nichts zu
        prüfen" und nicht „0 Befunde über 0 Tickets". Verifiziert: SWR-122.
        """
        with tempfile.TemporaryDirectory() as leer:
            self.assertEqual(preflight.plandrift(leer) or [], [])
            self.assertEqual(preflight.sprintvergangen(leer) or [], [])


if __name__ == "__main__":
    unittest.main()
