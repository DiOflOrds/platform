# -*- coding: utf-8 -*-
"""P9-Tests SWR-066/068/070: Steckbrief, Status-Fallback, Gruppen, projects-Discovery.
Hermetisch (gb-02): Temp-Root, eigene Git-Repos, kein Netz."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import aggregation  # noqa: E402

TICKET = ("---\nid: T-0001\ntitel: \"x\"\ntyp: task\nprozess: man3\nrolle: pl\n"
          "sprint: 0\nstatus: open\nprio: hoch\nblocked_by: []\nrepo: %s\n"
          "geändert: 2026-08-16\nerstellt: 2026-08-16\n---\n\n## Ziel\n\nx\n")


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t"]
                          + list(args), capture_output=True, text=True)


class RepoWelt(unittest.TestCase):
    """Gemeinsame Testwelt: Temp-Root mit echten Mini-Repos (hermetisch, gb-02)."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="orgcockpit-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _repo(self, name, steckbrief=None, team_typ=None, tag=None, nested=False):
        basis = os.path.join(self.root, "projects", name) if nested else os.path.join(self.root, name)
        os.makedirs(os.path.join(basis, "tickets"))
        with open(os.path.join(basis, "tickets", "T-0001.md"), "w", encoding="utf-8") as f:
            f.write(TICKET % name)
        if steckbrief:
            with open(os.path.join(basis, "steckbrief.yaml"), "w", encoding="utf-8") as f:
                f.write(steckbrief)
        if team_typ:
            with open(os.path.join(basis, "team.yaml"), "w", encoding="utf-8") as f:
                f.write(f"typ: {team_typ}\n")
        wurzel = os.path.join(self.root, "projects") if nested else basis
        if not os.path.isdir(os.path.join(wurzel, ".git")):
            _git(wurzel, "init", "-b", "main")
        _git(wurzel, "add", "-A")
        _git(wurzel, "commit", "-m", "init")
        if tag:
            _git(wurzel, "tag", tag)
        return basis


class OrgCockpitTest(RepoWelt):
    def test_steckbrief_und_gruppen(self):
        """SWR-066/068: Beschreibung/Status aus Steckbrief; typ-basierte Gruppen; Aufgabenliste."""
        self._repo("alpha", steckbrief='beschreibung: "Testprojekt Alpha"\nstatus: aktiv\n')
        self._repo("crew", team_typ="pm")
        c = aggregation.cockpit(self.root, "alpha")
        self.assertEqual(c["beschreibung"], "Testprojekt Alpha")
        self.assertEqual(c["gruppe"], "aktiv")
        self.assertEqual(c["aufgaben_offen"], 1)
        self.assertEqual(c["aufgaben"][0]["id"], "T-0001")
        self.assertEqual(aggregation.cockpit(self.root, "crew")["gruppe"], "festes-team")

    def test_takt_im_cockpit_und_board(self):
        """SWR-074 (pm/N-0012): wiederkehrende Aufgaben sind als solche erkennbar —
        Cockpit zählt sie und reicht den Takt je Aufgabe durch, Board ebenso."""
        basis = self._repo("takt-team", team_typ="pm")
        pfad = os.path.join(basis, "tickets", "T-0001.md")
        text = open(pfad, encoding="utf-8").read().replace(
            "status: open\n", "status: open\ntakt: je-session\n")
        open(pfad, "w", encoding="utf-8").write(text)
        c = aggregation.cockpit(self.root, "takt-team")
        self.assertEqual(c["aufgaben_wiederkehrend"], 1)
        self.assertEqual(c["aufgaben"][0]["takt"], "je-session")
        b = aggregation.lade_board(self.root, "takt-team")
        self.assertEqual(b["gruppen"]["open"][0]["takt"], "je-session")
        # Gegenprobe: einmalige Aufgabe bleibt ohne Takt und zählt nicht mit
        self._repo("einmal-team", team_typ="pm")
        c2 = aggregation.cockpit(self.root, "einmal-team")
        self.assertEqual(c2["aufgaben_wiederkehrend"], 0)
        self.assertFalse(c2["aufgaben"][0]["takt"])

    def test_altlasten_erkennung(self):
        """SWR-075 (pm/N-0013): erledigt + älter als 1 Tag → ausblendbar; alles andere bleibt.
        Ohne Änderungsdatum gilt ein Ticket als frisch (nie ohne Datenlage verstecken)."""
        from datetime import date
        heute = date(2026, 8, 16)
        f = aggregation.ist_altlast
        self.assertTrue(f({"status": "done", "geändert": "2026-08-10"}, heute=heute))
        self.assertTrue(f({"status": "rejected", "geändert": "2026-08-14"}, heute=heute))
        self.assertFalse(f({"status": "done", "geändert": "2026-08-15"}, heute=heute))  # Grenze
        self.assertFalse(f({"status": "done", "geändert": "2026-08-16"}, heute=heute))
        self.assertFalse(f({"status": "open", "geändert": "2026-01-01"}, heute=heute))
        self.assertFalse(f({"status": "in_review", "geändert": "2026-01-01"}, heute=heute))
        self.assertFalse(f({"status": "done"}, heute=heute))
        self.assertFalse(f({"status": "done", "geändert": "kaputt"}, heute=heute))

    def test_board_reicht_veraltet_durch(self):
        """SWR-075: Das Board-API markiert jede Karte, damit das HMI filtern kann."""
        basis = self._repo("altlast", team_typ="pm")
        pfad = os.path.join(basis, "tickets", "T-0001.md")
        text = open(pfad, encoding="utf-8").read().replace(
            "status: open", "status: done").replace("geändert: 2026-08-16", "geändert: 2000-01-01")
        open(pfad, "w", encoding="utf-8").write(text)
        b = aggregation.lade_board(self.root, "altlast")
        self.assertTrue(b["gruppen"]["done"][0]["veraltet"])

    def test_status_fallback_ueber_baseline_tag(self):
        """SWR-066: <repo>-v1.0-Tag ohne Steckbrief-Status -> abgeschlossen."""
        self._repo("beta", tag="beta-v1.0")
        c = aggregation.cockpit(self.root, "beta")
        self.assertEqual(c["status"], "abgeschlossen")
        self.assertEqual(c["gruppe"], "abgeschlossen")

    def test_projects_sammelrepo_discovery(self):
        """SWR-070: Projektordner in projects/ werden entdeckt und aufgeloest."""
        self._repo("gamma")
        self._repo("p10", nested=True, steckbrief='beschreibung: "Nested-Projekt"\n')
        namen = aggregation.projekte(self.root)
        self.assertIn("gamma", namen)
        self.assertIn("p10", namen)
        pfad = aggregation.projekt_pfad(self.root, "p10")
        self.assertTrue(pfad.endswith(os.path.join("projects", "p10")))
        c = aggregation.cockpit(self.root, "p10")
        self.assertEqual(c["beschreibung"], "Nested-Projekt")
        self.assertEqual(c["aufgaben_offen"], 1)


class NavigationTest(RepoWelt):
    """SWR-082 (pm/N-0015, pm/T-0012): Navigationsgruppen für den Kopfbereich."""

    def _welt(self):
        self._repo("aspice-team", team_typ="aspice")
        self._repo("pm", team_typ="pm")
        self._repo("team-mail", team_typ="projekt")
        self._repo("aktiv-projekt", steckbrief='beschreibung: "läuft noch"\nstatus: aktiv\n')
        self._repo("alt", tag="alt-v1.0")
        self._repo("p10", nested=True, steckbrief='beschreibung: "Nested"\n')

    def test_gruppen_reihenfolge_und_trennung(self):
        """SWR-082: feste Teams, Projekt-Teams, aktive Projekte in fester Reihenfolge;
        abgeschlossene Projekte separat unter `weitere` (erreichbar, aber nicht im Weg)."""
        self._welt()
        n = aggregation.navigation(self.root)
        self.assertEqual([g["schluessel"] for g in n["gruppen"]],
                         ["festes-team", "projekt-team", "aktiv"])
        namen = dict((g["schluessel"], [e["projekt"] for e in g["eintraege"]])
                     for g in n["gruppen"])
        self.assertEqual(namen["festes-team"], ["aspice-team", "pm"])
        self.assertEqual(namen["projekt-team"], ["team-mail"])
        self.assertIn("aktiv-projekt", namen["aktiv"])
        self.assertIn("p10", namen["aktiv"])          # verschachteltes Projekt (SWR-070)
        self.assertNotIn("alt", namen["aktiv"])
        self.assertEqual([e["projekt"] for e in n["weitere"]], ["alt"])
        self.assertEqual(n["anzahl_weitere"], 1)
        self.assertEqual(n["anzahl_aktiv"], 5)

    def test_gleiche_einstufung_wie_cockpit(self):
        """SWR-082: Kopf und Cockpit dürfen nie auseinanderlaufen — beide Ansichten
        nutzen dieselbe Ableitung, also muss jede Gruppe/Status-Angabe deckungsgleich sein."""
        self._welt()
        n = aggregation.navigation(self.root)
        alle = [e for g in n["gruppen"] for e in g["eintraege"]] + n["weitere"]
        self.assertEqual(len(alle), len(aggregation.projekte(self.root)))
        for e in alle:
            c = aggregation.cockpit(self.root, e["projekt"])
            self.assertEqual(e["gruppe"], c["gruppe"], e["projekt"])
            self.assertEqual(e["status"], c["status"], e["projekt"])
            self.assertEqual(e["beschreibung"], c["beschreibung"], e["projekt"])

    def test_leere_gruppen_entfallen(self):
        """SWR-082: Ohne Teams gibt es keine leeren Überschriften im Kopfbereich."""
        self._repo("nur-projekt")
        n = aggregation.navigation(self.root)
        self.assertEqual([g["schluessel"] for g in n["gruppen"]], ["aktiv"])
        self.assertEqual(n["weitere"], [])

    def test_nur_abgeschlossene_bleiben_erreichbar(self):
        """SWR-082: Sind alle Projekte abgeschlossen, bleiben sie über `weitere` erreichbar —
        der Kopfbereich darf nie leer sein und Boards/Berichte nie unaufrufbar machen."""
        self._repo("alt1", tag="alt1-v1.0")
        self._repo("alt2", tag="alt2-v1.0")
        n = aggregation.navigation(self.root)
        self.assertEqual(n["gruppen"], [])
        self.assertEqual([e["projekt"] for e in n["weitere"]], ["alt1", "alt2"])


if __name__ == "__main__":
    unittest.main()
