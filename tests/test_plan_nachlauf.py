"""Unit-Verifikation Plannachlauf im laufenden Sprint (SWR-201, platform/T-0052).

⚠⚠ **Das Zusicherungs-PAAR ist hier die eigentliche Arbeit, nicht die Ausnahme.**
Eine Fassung, in der `status_drift` gar nichts mehr meldet, besteht jeden Test, der nur
prüft, dass der Nachlauf durchkommt. Neben „der Nachlauf ist kein Befund" steht deshalb
in jedem Block sein Gegenstück: „die Gegenrichtung ist weiterhin einer" und „nach dem
Sprint-Ende ist alles wieder einer". Das ist die Bauform aus `SWR-166`/`SWR-148`, und
sie ist in diesem Haus dreimal die Stelle gewesen, an der ein Kahlschlag aufgefallen
wäre.

⚠ Die DoD von `platform/T-0052` verlangt ausdrücklich, dass die Wirkung von `SWR-115`
für **vergangene** Sprints nachweislich unverändert bleibt. Genau das prüft
`test_ohne_laufenden_sprint_ist_alles_befund` — ohne sie wäre die Ausnahme eine
Behauptung über Sorgfalt statt Sorgfalt (L-2026-08-21ce).
"""
import ast
import os
import sys
import unittest

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, "scripts"))
sys.path.insert(0, WURZEL)
from backend import sprint  # noqa: E402


def _zeile(richtung, ref="platform/T-0099", ticket="done", plan_sprint=None):
    """Ein Treffer in der Gestalt, die `status_drift` liefert."""
    return {"ref": ref, "titel": "t", "plan": "offen", "ticket": ticket,
            "plan_sprint": plan_sprint, "richtung": richtung, "meldung": "m"}


LAEUFT = {"nr": 32, "kennung": "test", "start": "2026-08-21 08:13", "takt_min": 60}


class PlanNachlauf(unittest.TestCase):

    def test_nachlauf_im_laufenden_sprint_ist_kein_befund(self):
        """Ticket `done` / Plan „offen" während der Sprint läuft: der garantierte Zustand."""
        befund, nachlauf = sprint.plan_nachlauf([_zeile("ticket_zu_frueh_fertig")], LAEUFT)
        self.assertEqual(befund, [])
        self.assertEqual(len(nachlauf), 1)

    def test_gegenrichtung_bleibt_befund_auch_im_laufenden_sprint(self):
        """⚠⚠ Der Schaden aus Sprint 7 wird NICHT mitgenommen.

        `plan_zu_frueh_fertig` heißt: der Plan behauptet Arbeit, die das Ticket nicht
        bestätigt. Das ist die Falschmeldung nach außen, gegen die `SWR-115` gebaut
        wurde — sie bleibt in JEDEM Sprint ein Befund. Am Bestand gemessen kostet diese
        Strenge heute nichts: über 60 Läufe und 7 Sprints ist sie **0**-mal aufgetreten.
        Eine Ausnahme, die auch die teure Richtung mitnimmt, wäre bequem und falsch.
        """
        befund, nachlauf = sprint.plan_nachlauf([_zeile("plan_zu_frueh_fertig")], LAEUFT)
        self.assertEqual(len(befund), 1)
        self.assertEqual(nachlauf, [])

    def test_ohne_laufenden_sprint_ist_alles_befund(self):
        """⚠ DoD-Punkt: `SWR-115` wirkt für VERGANGENE Sprints unverändert.

        Sobald kein Sprint läuft, gibt `sprint_register.laufender` `None` zurück — und
        beide Richtungen sind wieder Befund. Damit endet die Ausnahme von ALLEIN und
        hängt an keiner Selbstauskunft der Session (die Lehre aus `SWR-198`: an den
        Verweis binden, nicht an das Wort).
        """
        treffer = [_zeile("ticket_zu_frueh_fertig"), _zeile("plan_zu_frueh_fertig")]
        for leer in (None, {}, False):
            befund, nachlauf = sprint.plan_nachlauf(treffer, leer)
            self.assertEqual(len(befund), 2, "ohne laufenden Sprint blockiert alles")
            self.assertEqual(nachlauf, [])

    def test_vergangene_planzeile_bleibt_befund_obwohl_ein_sprint_laeuft(self):
        """⚠⚠ Der teuerste Befund des Reviews — die erste Fassung hatte ihn nicht.

        Sie band die Ausnahme daran, DASS ein Sprint läuft, und nicht daran, dass die
        Planzeile **zu ihm gehört**. Während gearbeitet wird, läuft aber immer einer:
        eine Planzeile aus Sprint 7 mit längst `done` Ticket wäre mit unterdrückt worden.

        > **Eine Bedingung, die während der gesamten Arbeitszeit wahr ist, ist keine
        > Bedingung — sie ist ein offenes Tor mit einer Aufschrift.**

        Das ist exakt der DoD-Punkt „Wirkung von `SWR-115` für VERGANGENE Sprints
        nachweislich unverändert". `test_ohne_laufenden_sprint_ist_alles_befund` allein
        hat ihn NICHT gedeckt — er prüft einen Zustand, der während der Arbeit nie
        eintritt. Vertreter von `L-2026-08-21cq`.
        """
        alt = _zeile("ticket_zu_frueh_fertig", plan_sprint=7)
        befund, nachlauf = sprint.plan_nachlauf([alt], LAEUFT)
        self.assertEqual(len(befund), 1, "eine alte Planzeile darf nicht mitlaufen")
        self.assertEqual(nachlauf, [])
        # Gegenstück: die Zeile DIESES Sprints und die ohne Nummer („dieser Sprint")
        for eigen in (32, None):
            _, n = sprint.plan_nachlauf(
                [_zeile("ticket_zu_frueh_fertig", plan_sprint=eigen)], LAEUFT)
            self.assertEqual(len(n), 1, "die eigene Planzeile gehört in den Nachlauf")

    def test_rejected_ist_kein_nachlauf(self):
        """⚠⚠ Das Schlupfloch, das das Review gefunden hat.

        `TICKET_GESCHLOSSEN` enthält `done` **und** `rejected`. Hörte die Ausnahme auf
        „geschlossen", könnte eine Session einen unbequemen Befund loswerden, indem sie
        das Ticket **verwirft** — die Planzeile bliebe „offen" und niemand meldete etwas.

        > **Ein verworfenes Ticket ist kein „fertig, der Plan hinkt nach". Es ist eine
        > Entscheidung, und der Plan, der sie nicht kennt, ist ein Befund.**

        Zweiter Vertreter von `L-2026-08-21cq`.
        """
        z = _zeile("ticket_zu_frueh_fertig", ticket="rejected")
        befund, nachlauf = sprint.plan_nachlauf([z], LAEUFT)
        self.assertEqual(len(befund), 1, "rejected darf die Ausnahme nicht bekommen")
        self.assertEqual(nachlauf, [])

    def test_die_verdrahtung_in_plan_wird_geprueft(self):
        """⚠⚠ Ohne diesen Block prüfen alle anderen die Funktion und nicht den BETRIEB.

        Das Review hat die komplette Verdrahtung aus `sprint.plan` entfernt — Aufruf und
        Payload-Schlüssel — und **alle sechs** Zusicherungen blieben grün, weil sie
        `plan_nachlauf` direkt rufen. Der Preflight meldete still „0", weil er den
        fehlenden Schlüssel per Vorgabewert in eine leere Liste verwandelte.

        > **Eine Zusicherung, die nur die Funktion kennt, sagt nichts darüber, ob sie
        > jemals gerufen wird.** Das ist die Lehre aus `SWR-171` an einer neuen Stelle:
        > eine Gegenprobe, die die Funktion prüft und nicht ihren Aufrufer, misst die
        > Hälfte, die man selbst geschrieben hat.

        Vertreter von `L-2026-08-21ct`.
        """
        with open(os.path.join(WURZEL, "backend", "sprint.py"), encoding="utf-8") as f:
            quelle = f.read()
        self.assertIn("plan_nachlauf(statusdrift", quelle,
                      "sprint.plan ruft die Trennung nicht auf")
        self.assertIn('"plan_nachlauf": nachlauf', quelle,
                      "sprint.plan legt das Ergebnis nicht in den Payload")
        # Und der Leser muss den FEHLENDEN Schlüssel von der leeren Liste unterscheiden.
        #
        # ⚠ Geprüft wird der CODE von `plannachlauf`, nicht die Datei. Der erste Entwurf
        # dieses Blocks suchte die schlechte Schreibweise im ganzen Text — und fand sie
        # im **Docstring darüber**, wo sie als abschreckendes Beispiel zitiert steht. Der
        # Prüfer schlug gegen seine eigene Erklärung an. Zweiter Fall derselben Sorte in
        # diesem Lauf (der erste in `test_offen_zaehlweise`), und beide Male hat die
        # Erklärung den Prüfgegenstand nachgeahmt.
        with open(os.path.join(WURZEL, "scripts", "preflight.py"), encoding="utf-8") as f:
            pf = f.read()
        baum = ast.parse(pf)
        fn = next(n for n in baum.body
                  if isinstance(n, ast.FunctionDef) and n.name == "plannachlauf")
        code = ast.dump(ast.Module(
            body=[n for n in fn.body
                  if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))],
            type_ignores=[]))
        self.assertIn("'plan_nachlauf'", code, "der Schlüssel wird nicht gelesen")
        self.assertNotIn("attr='get'", code,
                         "ein Vorgabewert macht aus der fehlenden Antwort eine beruhigende")

    def test_grundmenge_ist_nicht_leer(self):
        """SWR-128-Familie: eine Prüfung auf leerer Grundmenge ist für immer grün.

        Beide Richtungen müssen im Betriebscode überhaupt vorkommen — sonst prüfen die
        Blöcke oben ein Vokabular, das `status_drift` gar nicht mehr schreibt, und
        blieben grün, während ihr Gegenstand verschwindet (der Fehler, den `SWR-199` an
        seiner eigenen Prüfung gefunden hat).
        """
        with open(os.path.join(WURZEL, "backend", "sprint.py"), encoding="utf-8") as f:
            quelle = f.read()
        for richtung in ("ticket_zu_frueh_fertig", "plan_zu_frueh_fertig"):
            self.assertIn('"richtung": "%s"' % richtung, quelle,
                          "status_drift schreibt %s nicht mehr" % richtung)

    def test_trennung_steht_an_genau_einer_stelle(self):
        """⚠ Der Vertreter der Lehre selbst (B033 / SWR-198).

        Die Bedingung „welche Richtung ist Nachlauf" darf in genau EINER Betriebsdatei
        stehen. Schriebe der Preflight sie ein zweites Mal hin, liefen Preflight und
        Sichtenbau auseinander, sobald jemand eine der beiden anfasst — und das fiele
        niemandem auf. `SWR-166` hat diese Bauform 83 abgebrochene Läufe gekostet.
        """
        betrieb = {"backend/sprint.py": 0, "scripts/preflight.py": 0}
        for rel in betrieb:
            with open(os.path.join(WURZEL, *rel.split("/")), encoding="utf-8") as f:
                text = f.read()
            # nur der Code zählt, nicht die Erklärung im Docstring
            betrieb[rel] = sum(1 for z in text.splitlines()
                               if 'richtung' in z and 'ticket_zu_frueh_fertig' in z
                               and z.strip().startswith(("if", "elif", "return", "t.get")))
        self.assertEqual(betrieb["scripts/preflight.py"], 0,
                         "der Preflight klassifiziert selbst — das ist die zweite Kopie")
        self.assertGreaterEqual(betrieb["backend/sprint.py"], 1)

    def test_preflight_zaehlt_den_nachlauf_nicht_als_befund(self):
        """⚠ Und meldet ihn trotzdem — Schweigen wäre SWR-114.

        Gelesen wird der Quelltext des Blocks: hinter der Nachlauf-Ausgabe darf kein
        `befunde += 1` stehen, und die Referenzen müssen gedruckt werden. Eine Ausnahme,
        die still ist, ist von einer Prüfung, die nicht läuft, nicht zu unterscheiden.
        """
        with open(os.path.join(WURZEL, "scripts", "preflight.py"), encoding="utf-8") as f:
            text = f.read()
        block = text[text.index("nachlauf = plannachlauf(root)"):]
        block = block[:block.index("pdrift = plandrift(root)")]
        self.assertNotIn("befunde += 1", block, "der Nachlauf darf nicht blockieren")
        self.assertIn("d['ref']", block, "der Nachlauf muss die Zeilen NENNEN")
        self.assertIn("pm/D006", block, "die Meldung muss den Grund nennen (SWR-196)")


if __name__ == "__main__":
    unittest.main()
