"""SWR-165 (platform/T-0022 Frage 1): Logzeile ohne Rumpfmarker im Ticket.

⚠⚠ **Die Frage lautete, in welcher REIHENFOLGE `inbox.entscheide` seine drei Dateien
schreibt und was gilt, wenn eine davon ausfaellt.** Gezaehlt statt geraten:

| # | Datei | Art | gegen ihr Fehlen abgesichert |
|---|---|---|---|
| 1 | `management/decisions/decision-log.md` | append | **ja** (SWR-152) |
| 2 | `tickets/T-xxxx.md` (Rumpfmarker) | append | nein |
| 3 | `BOARD.md` | ueberschreiben | nein |

Der Fehlschlag vom 2026-08-17 traf die **erste** und war deshalb sauber — *Glueck in der
Reihenfolge und keine Zusicherung.*

> **Die gefaehrliche Luecke liegt zwischen 1 und 2, und sie ist die schlimmere Richtung:
> `board.dr_entschieden` liest 'entschieden' am RUMPFMARKER. Faellt der zweite Schreibvorgang
> aus, steht die Entscheidung im Log und jede Pruefung haelt den DR weiter fuer offen — der
> Mensch bekommt eine Frage erneut vorgelegt, die er beantwortet hat.**

Das ist woertlich der Vorfall hinter SWR-131, mit vertauschten Rollen.

⚠ Gebaut ist eine **Pruefung** und kein Umbau des Schreibwegs. Ein Bau am Schreibpfad einer
Klasse-A-Entscheidung verlangt eine Aussage darueber, was bei einem Teilausfall gelten soll
(Ruecknahme, Teilzustand, Abbruch vor dem ersten Schreiben); diese Frage ist niemandem
gestellt worden, und sie ungefragt zu beantworten waere der Fehler, den `platform/T-0020`
vier Sprints lang vermieden hat.
"""
import os
import shutil
import sys
import tempfile
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
import board  # noqa: E402
from backend import aggregation  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(_HIER))

KOPF = ("# Decision Log — Test (append-only)\n\n"
        "| ID | Datum | Entscheider | Entscheidung | Optionen | Begründung | "
        "Betroffene Artefakte |\n|---|---|---|---|---|---|---|\n")


class MarkerTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.p = os.path.join(self.tmp, "p0")
        os.makedirs(os.path.join(self.p, "tickets"))
        os.makedirs(os.path.join(self.p, "management", "decisions"))
        with open(os.path.join(self.p, "steckbrief.yaml"), "w", encoding="utf-8") as f:
            f.write("name: p0\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _log(self, *zeilen):
        with open(os.path.join(self.p, "management", "decisions", "decision-log.md"),
                  "w", encoding="utf-8", newline="\n") as f:
            f.write(KOPF + "".join(z + "\n" for z in zeilen))

    def _ticket(self, tid, marker=True):
        text = (f"---\nid: {tid}\ntitel: \"t\"\ntyp: decision-request\nprozess: man3\n"
                f"rolle: pl\nsprint: 0\nstatus: open\nprio: hoch\nblocked_by: []\n"
                f"repo: p0\nreviewer: qm\ngeändert: 2026-08-20\nerstellt: 2026-08-20\n---\n\n"
                f"Rumpf.\n")
        if marker:
            text += f"\n{board.ENTSCHEIDUNGSMARKER}D010, via Inbox, 2026-08-20 10:00):** A\n"
        with open(os.path.join(self.p, "tickets", f"{tid}.md"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(text)

    def test_logzeile_ohne_marker_wird_gefunden(self):
        self._log("| D010 | 2026-08-20 10:00 | Mensch (E. John, via Inbox) | **A** "
                  "| lt. T-0001 | — | T-0001 |")
        self._ticket("T-0001", marker=False)
        treffer = aggregation.decision_log_ohne_marker(self.tmp)
        self.assertEqual([(t[1], t[2]) for t in treffer], [("D010", "T-0001")])

    def test_GEGENPROBE_mit_marker_ist_still(self):
        """Ohne diese Gegenprobe waere die Pruefung auch dann gruen, wenn sie nichts liest."""
        self._log("| D010 | 2026-08-20 10:00 | Mensch (E. John, via Inbox) | **A** "
                  "| lt. T-0001 | — | T-0001 |")
        self._ticket("T-0001", marker=True)
        self.assertEqual(aggregation.decision_log_ohne_marker(self.tmp), [])

    def test_HANDGESCHRIEBENE_zeilen_werden_NICHT_verlangt(self):
        """⚠⚠ Die Lehre der 42 Altbestands-DRs (SWR-131).

        Eine handgeschriebene Logzeile fuehrt in der letzten Spalte eine **Artefaktliste**
        und keinen Ticketverweis. Von ihr einen Rumpfmarker zu verlangen hiesse, die
        Pruefung am Tag ihrer Einfuehrung 47-fach rot zu starten — und eine Pruefung, die
        am ersten Tag rot ist, trainiert das Wegsehen statt etwas zu verhindern.
        """
        self._log("| D000 | 2026-08-05 | Mensch (E. John) | **Gate G0 freigegeben** "
                  "| Freigabe / Ablehnung | weil | Projektauftrag P0, alle Baseline-Dokumente |")
        self.assertEqual(aggregation.decision_log_ohne_marker(self.tmp), [])

    def test_fehlende_ticketdatei_ist_ein_eigener_grund_und_kein_absturz(self):
        """Eine Logzeile, deren Ticket es nicht mehr gibt, ist ein anderer Fall als eine
        ohne Marker — und beide duerfen die Pruefung nicht sprengen."""
        self._log("| D011 | 2026-08-20 10:00 | Mensch (E. John, via Inbox) | **B** "
                  "| lt. T-0099 | — | T-0099 |")
        treffer = aggregation.decision_log_ohne_marker(self.tmp)
        self.assertEqual(len(treffer), 1)
        self.assertIn("fehlt", treffer[0][3])

    def test_der_marker_steht_an_EINER_stelle(self):
        """⚠⚠ `inbox.entscheide` schreibt den Marker, diese Pruefung sucht ihn — und der
        erste Entwurf von SWR-165 legte dafuer eine ZWEITE Konstante in `aggregation` an.

        Rot gemacht hat das nicht der Entwurf, sondern
        `test_dr_verbuchung.test_keine_zweite_kopie_des_markers_im_quelltext` — eine
        Zusicherung aus Sprint 17, die zaehlt, wie viele Dateien das Marker-Literal fuehren.

        > **Eine Anforderung, die 'der Marker steht an einer Stelle' verlangt, und deren
        > erster Entwurf eine zweite anlegt.**

        Geprueft wird deshalb hier, dass der Text, den `inbox` schreibt, mit
        `board.ENTSCHEIDUNGSMARKER` beginnt — die Zaehlung der Kopien steht drueben und
        wird hier nicht wiederholt (das waere dieselbe Dopplung eine Ebene hoeher).
        """
        with open(os.path.join(WURZEL, "platform", "backend", "inbox.py"),
                  encoding="utf-8") as f:
            quelle = f.read()
        self.assertIn(board.ENTSCHEIDUNGSMARKER, quelle,
                      "inbox.entscheide schreibt einen anderen Marker als die Pruefung sucht")

    def test_am_ECHTEN_bestand_ist_die_zahl_NULL_und_die_grundmenge_nicht_leer(self):
        """Die Lehre aus SWR-128: eine gruene Pruefung ueber eine leere Menge sagt nichts.

        Gemessen beim Bau: **93** Logzeilen ueber alle Repos, davon **46** von der Inbox
        geschrieben, **0** ohne Marker. Geprueft wird beides — die Null **und** dass es
        ueberhaupt etwas zu pruefen gab.
        """
        if not os.path.isdir(os.path.join(WURZEL, "p0", "tickets")):
            self.skipTest("Bestand nicht vorhanden (isolierte Testumgebung)")
        self.assertEqual(aggregation.decision_log_ohne_marker(WURZEL), [])
        import re
        import board
        inbox_zeilen = 0
        for _name, basis in board.projekt_pfade(WURZEL):
            log = os.path.join(basis, "management", "decisions", "decision-log.md")
            if not os.path.exists(log):
                continue
            with open(log, encoding="utf-8") as f:
                for z in f:
                    z = z.strip()
                    if not re.match(r"\|\s*D\d+\s*\|", z):
                        continue
                    if re.fullmatch(r"T-\d{4}", z.strip("|").split("|")[-1].strip()):
                        inbox_zeilen += 1
        self.assertGreater(inbox_zeilen, 20,
                           "die Grundmenge ist zu klein — dann sagt die Null nichts")


if __name__ == "__main__":
    unittest.main()
