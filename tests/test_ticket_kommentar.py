"""Kommentare an Aufgaben — ein Schreibweg, kein zweiter Speicher (SWR-192, T-0030).

⚠⚠ **Die teuerste Zusicherung dieser Datei ist die negative:** ein Kommentar darf
**kein** Frontmatter-Feld anfassen — auch `geändert` nicht. Ohne sie wäre der bequeme
Bau (einmal durch `aktualisiere` schicken) grün gewesen, und jeder Beitrag hätte
ausgesehen wie eine Bearbeitung. `unverbuchte_status` und `uebergang_historie` lesen
genau diese Felder.

⚠ Gebaut wird an **synthetischen** Repos unter `tempfile` (`L-2026-08-17ai`,
`L-2026-08-20cm`) und nicht an den Live-Repos, in die der Schnelltakt greift.

Ausführung: python -m unittest discover platform/tests
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HIER)))
sys.path.insert(0, os.path.join(_HIER, ".."))
import board  # noqa: E402

TICKET = """---
id: T-0001
titel: "Ein Ticket zum Bereden"
typ: task
prozess: swe3
rolle: dev
sprint: 1
status: {status}
prio: mittel
erstellt: 2026-08-01
---

## Auftrag

Der ursprüngliche Rumpf. Er darf nicht verlorengehen.
"""


class KommentarTest(unittest.TestCase):
    """Verifiziert: SWR-192."""

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="swr192-")
        os.makedirs(os.path.join(self.repo, "tickets"))
        self._schreibe("open")

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def _schreibe(self, status):
        with open(os.path.join(self.repo, "tickets", "T-0001.md"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(TICKET.format(status=status))

    def _text(self):
        with open(os.path.join(self.repo, "tickets", "T-0001.md"), encoding="utf-8") as f:
            return f.read()

    def _frontmatter(self):
        _t, fm = board.lies_ticket(self.repo, "T-0001")
        return {k: v for k, v in fm.items() if not k.startswith("_")}

    # --- die negative Zusicherung: ein Kommentar ist keine Bearbeitung ---------

    def test_kein_frontmatter_feld_aendert_sich(self):
        """⚠⚠ DoD 9 — ohne diese Pruefung waere der bequeme Bau gruen gewesen."""
        vorher = self._frontmatter()
        board.kommentiere(self.repo, "T-0001", "Wie ist der Stand?")
        self.assertEqual(self._frontmatter(), vorher)

    def test_kein_geaendert_sprung(self):
        """`geändert` ist das Feld, das nach einer Bearbeitung aussieht."""
        board.kommentiere(self.repo, "T-0001", "Ein Beitrag.")
        self.assertNotIn("geändert:", self._text().split("---")[1])

    def test_kein_bearbeitet_vermerk(self):
        """Der Verlauf datiert sich selbst — ein zweiter Vermerk waere ein zweiter Ort."""
        board.kommentiere(self.repo, "T-0001", "Ein Beitrag.")
        self.assertNotIn("**Bearbeitet (", self._text())

    def test_board_md_wird_nicht_geschrieben(self):
        """⚠ Sonst bewegt jeder Beitrag die Stand-Zeile (SWR-110-Rauschen)."""
        board.kommentiere(self.repo, "T-0001", "Ein Beitrag.")
        self.assertFalse(os.path.exists(os.path.join(self.repo, "BOARD.md")))

    # --- der Kanal selbst -----------------------------------------------------

    def test_beitrag_steht_im_rumpf_und_der_alte_rumpf_bleibt(self):
        board.kommentiere(self.repo, "T-0001", "Wie ist der Stand?")
        text = self._text()
        self.assertIn("Wie ist der Stand?", text)
        self.assertIn("Der ursprüngliche Rumpf.", text)
        self.assertIn(board.KOMMENTAR_UEBERSCHRIFT, text)

    def test_neueste_zuerst(self):
        """DoD 5 — wie im Team-Chat bestellt (SWR-083)."""
        board.kommentiere(self.repo, "T-0001", "erster",
                          jetzt=datetime(2026, 8, 21, 10, 0))
        board.kommentiere(self.repo, "T-0001", "zweiter",
                          jetzt=datetime(2026, 8, 21, 11, 0))
        text = self._text()
        self.assertLess(text.index("zweiter"), text.index("erster"),
                        "der neueste Beitrag steht nicht oben")
        self.assertIn("erster", text, "der aeltere Beitrag ist verlorengegangen")

    def test_leser_und_schreiber_passen_zusammen(self):
        """⚠ Die Gegenprobe zum Schreiber: laufen sie auseinander, wird das hier leer."""
        board.kommentiere(self.repo, "T-0001", "erster",
                          jetzt=datetime(2026, 8, 21, 10, 0))
        board.kommentiere(self.repo, "T-0001", "zweiter",
                          jetzt=datetime(2026, 8, 21, 11, 0))
        k = board.kommentare(self.repo, "T-0001")
        self.assertEqual([x["text"] for x in k], ["zweiter", "erster"])
        self.assertEqual(k[0]["zeit"], "2026-08-21 11:00")
        self.assertEqual(k[0]["von"], "Mensch via HMI")

    def test_ohne_verlauf_ist_der_leser_leer_und_wirft_nicht(self):
        self.assertEqual(board.kommentare(self.repo, "T-0001"), [])

    def test_zeitstempel_kommt_aus_der_einen_quelle(self):
        """SWR-084 — eine zweite Zeitquelle waere nach B025 ein kuenftiger Befund."""
        jetzt = datetime(2026, 8, 21, 9, 30)
        board.kommentiere(self.repo, "T-0001", "x", jetzt=jetzt)
        self.assertIn(board.zeitpunkt(jetzt), self._text())

    # --- DoD 6: die Sperre gilt dem Formular, nicht dem Gespraech --------------

    def test_auch_an_erledigten_aufgaben(self):
        """⚠⚠ Der haeufigste Anlass fuer eine Rueckfrage ist eine erledigte Aufgabe."""
        for status in ("done", "rejected"):
            with self.subTest(status=status):
                self._schreibe(status)
                board.kommentiere(self.repo, "T-0001", f"Rueckfrage an {status}")
                self.assertIn(f"Rueckfrage an {status}", self._text())
                self.assertEqual(self._frontmatter()["status"], status)

    def test_gegenprobe_die_archivsperre_gilt_fuer_aenderungen_weiterhin(self):
        """⚠ Ohne sie waere DoD 6 eine Abschaltung von SWR-077 statt einer Ausnahme."""
        self._schreibe("done")
        with self.assertRaises(ValueError):
            board.aktualisiere(self.repo, "T-0001", {"prio": "hoch"})

    # --- SWR-080: derselbe Konfliktschutz wie am Editor ------------------------

    def test_falscher_fingerabdruck_wird_abgelehnt(self):
        with self.assertRaises(board.KonfliktFehler):
            board.kommentiere(self.repo, "T-0001", "x",
                              erwarteter_fingerprint="dieser-passt-nicht")

    def test_richtiger_fingerabdruck_geht_durch(self):
        text, _ = board.lies_ticket(self.repo, "T-0001")
        erg = board.kommentiere(self.repo, "T-0001", "x",
                                erwarteter_fingerprint=board.fingerprint(text))
        self.assertEqual(erg["beitraege"], 1)

    def test_fingerabdruck_wandert_nach_jedem_beitrag(self):
        """Sonst waere der Schutz nach dem ersten Beitrag wertlos."""
        text, _ = board.lies_ticket(self.repo, "T-0001")
        alt = board.fingerprint(text)
        neu = board.kommentiere(self.repo, "T-0001", "x")["fingerprint"]
        self.assertNotEqual(alt, neu)

    # --- Eingaben -------------------------------------------------------------

    def test_leerer_beitrag_wird_abgelehnt(self):
        for leer in ("", "   ", "\n\n"):
            with self.subTest(leer=repr(leer)):
                with self.assertRaises(ValueError):
                    board.kommentiere(self.repo, "T-0001", leer)

    def test_unbekanntes_ticket_wirft(self):
        with self.assertRaises(ValueError):
            board.kommentiere(self.repo, "T-0009", "x")

    def test_mehrzeiliger_beitrag_bleibt_mehrzeilig(self):
        board.kommentiere(self.repo, "T-0001", "Zeile eins\n\nZeile zwei")
        k = board.kommentare(self.repo, "T-0001")
        self.assertEqual(k[0]["text"], "Zeile eins\n\nZeile zwei")

    def test_das_ticket_bleibt_nach_dem_beitrag_gueltig(self):
        board.kommentiere(self.repo, "T-0001", "x")
        tickets, probleme = board.lade_tickets(self.repo)
        self.assertEqual(probleme, [])
        self.assertEqual(board.validiere_alle(tickets, self.repo, git_pruefen=False), [])


class EinSchreibwegTest(unittest.TestCase):
    """Verifiziert: SWR-192 — DoD 3, derselbe Schreibweg wie der Editor (B033)."""

    def test_backend_nutzt_git_schreiben_und_baut_keine_zweite_regelpruefung(self):
        pfad = os.path.join(_HIER, "..", "backend", "tickets.py")
        with open(pfad, encoding="utf-8") as f:
            quelle = f.read()
        koerper = quelle.split("def kommentiere(", 1)[1].split("\n\n\n", 1)[0]
        self.assertIn("git_schreiben.verbuche", koerper,
                      "der Kommentar laeuft nicht ueber den einen Schreibweg (SWR-134)")
        self.assertIn("board.kommentiere", koerper,
                      "die Regeln stehen nicht in der Skript-Route")
        self.assertNotIn("BOARD_DATEI", koerper,
                         "BOARD.md ist Ziel des Kommentar-Commits — das bewegt bei "
                         "jedem Beitrag die Stand-Zeile")

    def test_die_route_liegt_hinter_dem_pin_gate(self):
        """DoD 7 — das Gate steht EINMAL am Kopf von do_POST, nicht je Route."""
        pfad = os.path.join(_HIER, "..", "backend", "server.py")
        with open(pfad, encoding="utf-8") as f:
            quelle = f.read()
        self.assertIn('/api/ticket/kommentar', quelle, "Route fehlt")
        vor_route = quelle.split('if self.path == "/api/ticket/kommentar"', 1)[0]
        self.assertIn("schreibschutz_pruefen", vor_route.split("def do_POST", 1)[1],
                      "die Route liegt nicht hinter dem PIN-Gate")

    def test_ueberschrift_steht_an_einer_stelle(self):
        """SWR-131 — drei Literale waeren drei Gelegenheiten auseinanderzulaufen."""
        pfad = os.path.join(_HIER, "..", "scripts", "board.py")
        with open(pfad, encoding="utf-8") as f:
            quelle = f.read()
        self.assertEqual(quelle.count('"## Verlauf"'), 1,
                         "die Ueberschrift steht mehr als einmal als Literal")


class KommentarUeberDenSchreibwegTest(unittest.TestCase):
    """Verifiziert: SWR-192 — der ganze Weg inkl. Commit, an einem echten Git-Repo."""

    def setUp(self):
        self.wurzel = tempfile.mkdtemp(prefix="swr192-git-")
        self.repo = os.path.join(self.wurzel, "p0")
        os.makedirs(os.path.join(self.repo, "tickets"))
        with open(os.path.join(self.repo, "tickets", "T-0001.md"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(TICKET.format(status="done"))
        for args in (["init", "-q", "."], ["config", "user.email", "t@t"],
                     ["config", "user.name", "T"], ["add", "-A"],
                     ["commit", "-qm", "init"]):
            subprocess.run(["git", "-C", self.repo] + args, capture_output=True,
                           env=dict(os.environ, GIT_AUTHOR_NAME="T",
                                    GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="T",
                                    GIT_COMMITTER_EMAIL="t@t"))

    def tearDown(self):
        shutil.rmtree(self.wurzel, ignore_errors=True)

    def test_beitrag_wird_sofort_committet_und_das_ticket_bleibt_done(self):
        from backend import tickets as backend_tickets
        text, _ = board.lies_ticket(self.repo, "T-0001")
        erg = backend_tickets.kommentiere(
            self.wurzel, "p0", "T-0001",
            {"text": "Rueckfrage an eine erledigte Aufgabe",
             "fingerprint": board.fingerprint(text)})
        self.assertTrue(erg["ok"])
        self.assertEqual(erg["beitraege"], 1)
        self.assertEqual([k["text"] for k in erg["kommentare"]],
                         ["Rueckfrage an eine erledigte Aufgabe"])
        offen = subprocess.run(["git", "-C", self.repo, "status", "--porcelain"],
                               capture_output=True, text=True).stdout.strip()
        self.assertEqual(offen, "", f"nicht sofort committet: {offen!r}")
        _t, fm = board.lies_ticket(self.repo, "T-0001")
        self.assertEqual(fm["status"], "done")


if __name__ == "__main__":
    unittest.main()
