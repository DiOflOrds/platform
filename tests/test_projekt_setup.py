# -*- coding: utf-8 -*-
"""Tests projekt_setup.py (SWR-180, Projektmodell Konzept 04 Kap. 4): Struktur,
Tickets, G0-bleibt-offen, Abbruchfälle."""
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import projekt_setup  # noqa: E402


class TestProjektSetup(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "process", "templates"))
        with io.open(os.path.join(self.root, "process", "templates", "projektplan.md"),
                     "w", encoding="utf-8") as f:
            f.write("# Projektplan: <Pxx> „<Name>“\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_struktur_und_tickets(self):
        pfad = projekt_setup.erzeuge(self.root, "p99", "Testprojekt", "Ein Testauftrag",
                                     heute="2026-08-21")
        for rel in ("steckbrief.yaml", "README.md", "docs/01-projektauftrag.md",
                    "docs/projektplan.md", "docs/historie.md", "roles/README.md",
                    "BOARD.md", "tickets/T-0001.md", "tickets/T-0012.md"):
            self.assertTrue(os.path.isfile(os.path.join(pfad, rel)), rel)
        # Template-Platzhalter ersetzt
        plan = io.open(os.path.join(pfad, "docs", "projektplan.md"), encoding="utf-8").read()
        self.assertIn("P99", plan)
        self.assertIn("Testprojekt", plan)
        # G0 bleibt offen (der Knopf gruendet, entscheidet nie — Lehre p12)
        auftrag = io.open(os.path.join(pfad, "docs", "01-projektauftrag.md"),
                          encoding="utf-8").read()
        self.assertIn("G0 OFFEN", auftrag)
        # Planung zuerst: alle Initialisierungs-Tickets haengen an T-0001
        t2 = io.open(os.path.join(pfad, "tickets", "T-0002.md"), encoding="utf-8").read()
        self.assertIn("blocked_by: [T-0001]", t2)
        # 12 Tickets: 1 Planung + 9 Rollen-Init + 2 Takt
        self.assertEqual(len(os.listdir(os.path.join(pfad, "tickets"))), 12)
        # Takt-Ticket traegt je-session
        t11 = io.open(os.path.join(pfad, "tickets", "T-0011.md"), encoding="utf-8").read()
        self.assertIn("takt: je-session", t11)

    def test_board_valide(self):
        pfad = projekt_setup.erzeuge(self.root, "p98", "X", "Y", heute="2026-08-21")
        import board
        tickets, probleme = board.lade_tickets(pfad)
        probleme += board.validiere_alle(tickets, pfad, git_pruefen=False)
        self.assertEqual(probleme, [])
        self.assertEqual(len(tickets), 12)

    def test_workflows_scaffold_deckt_takte(self):
        """SWR-188: workflows.yaml existiert, bindet die erzeugten Takt-Tickets,
        Abdeckungsprüfung meldet null Lücken auf frischem Scaffold."""
        projekt_setup.erzeuge(self.root, "p95", "X", "Y", heute="2026-08-21")
        wf = io.open(os.path.join(self.root, "projects", "p95", "docs", "workflows.yaml"),
                     encoding="utf-8").read()
        self.assertIn("ticket: T-0011", wf)
        self.assertIn("ticket: T-0012", wf)
        bk = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if bk not in sys.path:
            sys.path.insert(0, bk)
        from backend import workflows
        d = workflows.einheit(self.root, "p95")
        self.assertTrue(d["datei"])
        self.assertEqual(d["unabgedeckte_takte"], [])
        self.assertEqual(len(d["workflows"]), 2)
        for w in d["workflows"]:
            self.assertEqual(w["befunde"], [])  # jeder Schritt hat rolle/aktion/input/output

    def test_bricht_ab_wenn_vorhanden_und_bei_unsinn(self):
        projekt_setup.erzeuge(self.root, "p97", "X", "Y", heute="2026-08-21")
        with self.assertRaises(ValueError):
            projekt_setup.erzeuge(self.root, "p97", "X", "Y")  # existiert
        with self.assertRaises(ValueError):
            projekt_setup.erzeuge(self.root, "P96", "X", "Y")  # Grossschreibung
        with self.assertRaises(ValueError):
            projekt_setup.erzeuge(self.root, "p96", "X", "Y", profil="zauberei")


if __name__ == "__main__":
    unittest.main()
