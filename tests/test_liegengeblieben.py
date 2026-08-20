# -*- coding: utf-8 -*-
"""SWR-155 (pm/T-0069, Brief pm/N-0043 Punkt 4): „Wenn Sprint vorbei ist, muss ein
anderer Status drin stehen." — der Preflight meldet Aufgaben, die auf `in_progress`
stehen, obwohl kein Sprint läuft.

⚠⚠ **Die wichtigste Zusicherung dieser Datei ist die GEGENPROBE.** Die Prüfung ist
gegen den heutigen Bestand grün — und das wäre bis Sprint 20 auch dann so gewesen, wenn
sie gar nichts täte: `in_progress` hat im Median **22 Sekunden** existiert, und **159
von 300** geschlossenen Aufgaben hatten ihn nie. Eine Prüfung, die auf einem Bestand
grün ist, in dem der geprüfte Zustand nicht vorkommt, prüft nichts (`L-2026-08-17ai`).
Deshalb stellt jeder Test hier den Zustand **her**, statt ihn zu erhoffen.
"""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import preflight  # noqa: E402
import sprint_register  # noqa: E402


def ticket(ref, status):
    projekt, tid = ref.split("/", 1)
    return {"projekt": projekt, "id": tid, "ref": ref,
            "titel": "Aufgabe " + tid, "status": status}


class ErkennungTest(unittest.TestCase):
    """Was gilt als „angefangen und liegengeblieben"."""

    def setUp(self):
        preflight._SPRINTSICHT_CACHE.clear()
        self._sicht = preflight.sprintsicht
        self._laufender = sprint_register.laufender

    def tearDown(self):
        preflight.sprintsicht = self._sicht
        sprint_register.laufender = self._laufender
        preflight._SPRINTSICHT_CACHE.clear()

    def _stelle_her(self, tickets, sprint_laeuft):
        preflight.sprintsicht = lambda root, frisch=False: {"offene": tickets}
        sprint_register.laufender = lambda root: ({"nr": 21} if sprint_laeuft else None)

    def test_in_progress_OHNE_laufenden_sprint_ist_ein_befund(self):
        """⚠ Der hergestellte Zustand — genau der, den der Brief meint."""
        self._stelle_her([ticket("pm/T-0069", "in_progress"),
                          ticket("pm/T-0001", "open")], sprint_laeuft=False)
        treffer, laeuft = preflight.liegengeblieben_in_arbeit(".")
        self.assertFalse(laeuft)
        self.assertEqual([t["ref"] for t in treffer], ["pm/T-0069"])

    def test_in_progress_MIT_laufendem_sprint_ist_kein_befund(self):
        """Während eines Sprints ist `in_progress` der RICHTIGE Zustand."""
        self._stelle_her([ticket("pm/T-0069", "in_progress")], sprint_laeuft=True)
        treffer, laeuft = preflight.liegengeblieben_in_arbeit(".")
        self.assertTrue(laeuft)
        self.assertEqual([t["ref"] for t in treffer], ["pm/T-0069"])

    def test_offene_und_blockierte_aufgaben_zaehlen_nicht_mit(self):
        """Die Gegenprobe: sonst meldete die Prüfung jeden Bestand."""
        self._stelle_her([ticket("a/T-0001", "open"), ticket("b/T-0002", "blocked"),
                          ticket("c/T-0003", "in_review")], sprint_laeuft=False)
        treffer, _ = preflight.liegengeblieben_in_arbeit(".")
        self.assertEqual(treffer, [])

    def test_in_review_ist_bewusst_NICHT_enthalten(self):
        """⚠ Frage 3 des Tickets ist offen: erst messen, ob der Zustand am Sprintende
        vorkommt, bevor eine Regel dafür erfunden wird (B038)."""
        self._stelle_her([ticket("c/T-0003", "in_review")], sprint_laeuft=False)
        treffer, _ = preflight.liegengeblieben_in_arbeit(".")
        self.assertEqual(treffer, [])

    def test_nicht_ladbare_sicht_ist_None_und_nicht_leer(self):
        """„Konnte nicht prüfen" ist nicht „nichts gefunden"."""
        preflight.sprintsicht = lambda root, frisch=False: None
        self.assertIsNone(preflight.liegengeblieben_in_arbeit("."))

    def test_kein_zweiter_erhebungsweg(self):
        """⚠ Die Liste kommt aus DERSELBEN Sicht wie `offen_gesamt` (B033) — die
        Prüfung sieht denselben Bestand wie die Anzeige, oder sie wäre eine zweite
        Antwort auf dieselbe Frage."""
        rufe = []

        def zaehlend(root, frisch=False):
            rufe.append(root)
            return {"offene": [ticket("pm/T-0069", "in_progress")]}

        preflight.sprintsicht = zaehlend
        sprint_register.laufender = lambda root: None
        preflight.liegengeblieben_in_arbeit(".")
        self.assertEqual(len(rufe), 1)


class AusgabeTest(unittest.TestCase):
    """Was der Preflight druckt — und dass er NIE schweigt."""

    def setUp(self):
        preflight._SPRINTSICHT_CACHE.clear()
        self._sicht = preflight.sprintsicht
        self._laufender = sprint_register.laufender

    def tearDown(self):
        preflight.sprintsicht = self._sicht
        sprint_register.laufender = self._laufender
        preflight._SPRINTSICHT_CACHE.clear()

    def _druck(self, tickets, sprint_laeuft):
        """Nur den SWR-155-Block, wortgleich mit `preflight.preflight`."""
        preflight.sprintsicht = lambda root, frisch=False: {"offene": tickets}
        sprint_register.laufender = lambda root: ({"nr": 21} if sprint_laeuft else None)
        puffer = io.StringIO()
        befunde = 0
        with redirect_stdout(puffer):
            liegen = preflight.liegengeblieben_in_arbeit(".")
            if liegen is None:
                print("[org] In Arbeit liegengeblieben: nicht prüfbar "
                      "(Sprintsicht nicht ladbar).")
            else:
                offen_in_arbeit, laeuft = liegen
                if laeuft:
                    print(f"[org] In Arbeit (ein Sprint läuft, kein Befund): "
                          f"{len(offen_in_arbeit)}.")
                elif offen_in_arbeit:
                    print(f"[org] BEFUND: {len(offen_in_arbeit)} Aufgabe(n) stehen auf "
                          f"`in_progress`, obwohl kein Sprint läuft — angefangen und "
                          f"liegengeblieben:")
                    for o in offen_in_arbeit:
                        print(f"    {o['ref']}: {o.get('titel', '')}")
                    befunde += 1
                else:
                    print("[org] In Arbeit liegengeblieben: 0.")
        return puffer.getvalue(), befunde

    def test_der_befund_nennt_die_refs_und_zaehlt(self):
        """⚠ Eine Zahl ohne Refs sagt „82" und nicht, welche fünf fehlen (B038)."""
        text, befunde = self._druck([ticket("pm/T-0069", "in_progress")],
                                    sprint_laeuft=False)
        self.assertIn("BEFUND", text)
        self.assertIn("pm/T-0069", text)
        self.assertEqual(befunde, 1)

    def test_bei_null_steht_trotzdem_eine_zeile_da(self):
        """SWR-114: ein stiller Check ist von einem nicht gelaufenen nicht zu
        unterscheiden."""
        text, befunde = self._druck([ticket("a/T-0001", "open")], sprint_laeuft=False)
        self.assertIn("In Arbeit liegengeblieben: 0.", text)
        self.assertEqual(befunde, 0)

    def test_waehrend_eines_sprints_wird_gezaehlt_aber_nicht_gewertet(self):
        """⚠ Nicht schweigen, nur nicht werten — das ist der Unterschied zum
        Unterdrücken."""
        text, befunde = self._druck([ticket("pm/T-0069", "in_progress")],
                                    sprint_laeuft=True)
        self.assertIn("ein Sprint läuft, kein Befund", text)
        self.assertIn("1", text)
        self.assertNotIn("BEFUND:", text)
        self.assertEqual(befunde, 0)


if __name__ == "__main__":
    unittest.main()
