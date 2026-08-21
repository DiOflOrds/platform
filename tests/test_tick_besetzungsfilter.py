"""SWR-196 (`platform/T-0048`): die Besetzung ist ein Kandidaten-FILTER, kein Veto danach.

⚠⚠ Der Anlass ist eine Messung und keine Vermutung. Am 2026-08-21 um 04:15 lief der
Schnelltakt zum **ersten Mal** bis zur Ticketauswahl durch — `SWR-191` hatte den falschen
Preflight-Befund beseitigt, der 65 Ticks vorher abgebrochen hatte. Und dann endeten
**2 von 2** Ticks trotzdem ohne Ergebnis:

    Gewählt: T-0001 … — Rolle CM, Route: llm (['ollama'])
    Tick OHNE ERGEBNIS (Besetzung): Rolle CM hat in Einheit 'platform' keine Besetzung …

`waehle_ticket` gab `kandidaten[0]` zurück, `besetzungsbefund` lief **danach**.

> **Eine Prüfung nach der Auswahl ist kein Filter, sondern ein Veto gegen genau einen
> Kandidaten. Die Zweitplatzierten werden nie angesehen.**

⚠ Die zentrale Gegenprobe dieser Datei ist deshalb `test_hinterer_kandidat_wird_gefunden`:
sie stellt ein Ticket der besetzten Rolle **hinter** ein unbesetztes und verlangt, dass die
Auswahl das hintere findet. **Vor der Reparatur wäre sie rot** — und keine andere Zusicherung
hier unterscheidet Filter von Veto. Eine Zusicherung, die nur „am Ende kommt nichts heraus"
prüft, wäre bei einem Veto ebenfalls grün.

⚠ Gegenprobe an einer **synthetischen** Wurzel und nicht an den 17 Live-Repos, die eine
fremde Automatik alle 15 Minuten anfasst (`L-2026-08-20cm`).
"""
import os
import shutil
import sys
import tempfile
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(WURZEL, "orchestrator"))
sys.path.insert(0, WURZEL)

import tick as tick_mod  # noqa: E402

REGISTRY = {"CM":   {"besetzung": "ki", "status": "active"},
            "PROB": {"besetzung": "ki", "status": "active"},
            "DEV":  {"besetzung": "ki", "status": "active"}}

BESETZUNGEN = """\
core_team:
  rollen: [PL, RM, ARCH, DEV, TEST, QM, CM, PROB, CHG, COACH]
  motor: cowork
  takt: sprint
  status: aktiv
besetzungen:
  PROB@einheit_a:
    rolle: PROB
    einheit: einheit_a
    motor: ollama
    modell: gemma3:27b
    takt: schnell
    status: aktiv
"""

TEAMS = """\
teams:
  einheit_a:
    typ: projekt
    status: aktiv
"""


def ticket(tid, rolle, prio="mittel", status="open"):
    return {"id": tid, "status": status, "rolle": rolle, "prio": prio, "blocked_by": []}


class SyntheticWurzel(unittest.TestCase):
    """Eine Wurzel mit genau einer ollama-Besetzung: `PROB@einheit_a`."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="swr196-")
        pr = os.path.join(self.root, "process", "roles")
        os.makedirs(pr)
        with open(os.path.join(pr, "besetzungen.yaml"), "w", encoding="utf-8") as f:
            f.write(BESETZUNGEN)
        with open(os.path.join(pr, "registry.yaml"), "w", encoding="utf-8") as f:
            f.write("roles:\n  PROB: {name: Problemmanager, besetzung: ki, status: active}\n"
                    "  CM: {name: Konfigurationsmanager, besetzung: ki, status: active}\n"
                    "  DEV: {name: Entwickler, besetzung: ki, status: active}\n")
        tr = os.path.join(self.root, "process", "teams")
        os.makedirs(tr)
        with open(os.path.join(tr, "registry.yaml"), "w", encoding="utf-8") as f:
            f.write(TEAMS)
        for e in ("einheit_a", "einheit_b"):
            os.makedirs(os.path.join(self.root, e, "tickets"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def waehle(self, tickets, einheit="einheit_a", provider="ollama"):
        return tick_mod.waehle_ticket(tickets, REGISTRY, repos=self.root,
                                      einheit=einheit, provider=provider)


class FilterStattVetoTest(SyntheticWurzel):

    def test_hinterer_kandidat_wird_gefunden(self):
        """⚠⚠ DIE Gegenprobe: das besetzte Ticket steht HINTER dem unbesetzten.

        Vertreter von `L-2026-08-21cj` (*eine Prüfung nach der Auswahl ist kein Filter,
        sondern ein Veto gegen genau einen Kandidaten*).

        `T-0001` (Rolle CM, prio hoch) gewinnt jede Sortierung; `T-0002` (Rolle PROB,
        prio niedrig) ist das einzige, das diese Besetzung bearbeiten darf. Ein Veto nach
        der Auswahl gäbe hier **nichts** zurück — der Filter findet `T-0002`.
        """
        ts = [ticket("T-0001", "cm", prio="hoch"),
              ticket("T-0002", "prob", prio="niedrig")]
        t, befund = self.waehle(ts)
        self.assertIsNotNone(t, "Veto statt Filter: der hintere Kandidat wurde nie angesehen")
        self.assertEqual(t["id"], "T-0002")
        self.assertEqual(befund, "", "ein Treffer trägt keinen Bestandsbefund")

    def test_ohne_passende_rolle_kein_kandidat(self):
        """Trägt kein offenes Ticket eine besetzte Rolle, wird nichts gewählt."""
        ts = [ticket("T-0001", "cm", prio="hoch"), ticket("T-0002", "dev")]
        t, befund = self.waehle(ts)
        self.assertIsNone(t)
        self.assertTrue(befund, "die Absage muss ihren Grund tragen (SWR-167)")

    def test_befund_nennt_bestand_statt_exemplar(self):
        """⚠⚠ Der eigentliche Ertrag: die Meldung ist eine Aussage über den BESTAND.

        Vertreter von `L-2026-08-21cl` (*eine wahre, aber zu enge Meldung über einen
        strukturellen Zustand ist der Zwilling des falschen Befunds*).

        Die alte lautete *„… T-0001 bleibt unangetastet"* und las sich wie ein Zufall.
        Diese nennt die **Anzahl** der geprüften Tickets, die **Rollen** im Bestand und
        die in dieser Einheit besetzten Instanzen — und sagt, dass ein weiterer Lauf
        daran nichts ändert.
        """
        ts = [ticket("T-0001", "cm"), ticket("T-0002", "dev"), ticket("T-0003", "cm")]
        _, befund = self.waehle(ts)
        self.assertIn("3 offene(s) Ticket(s) geprüft", befund)
        self.assertIn("CM", befund)
        self.assertIn("DEV", befund)
        self.assertIn("PROB@einheit_a", befund)
        self.assertIn("ein weiterer Lauf ändert das nicht", befund)
        self.assertNotIn("T-0001", befund,
                         "eine Aussage über den Bestand nennt kein einzelnes Ticket")

    def test_einheit_ohne_besetzung_nennt_keine_fremde_instanz(self):
        """⚠ Die Handlung, die den Befund abstellt, liegt in DIESER Einheit.

        `PROB@einheit_a` in einem Befund über `einheit_b` zu nennen wäre eine
        Nebelkerze: dort hilft sie niemandem.
        """
        ts = [ticket("T-0001", "cm")]
        _, befund = self.waehle(ts, einheit="einheit_b")
        self.assertIn("einheit_b", befund)
        self.assertIn("besetzt in dieser Einheit: keine", befund)
        self.assertNotIn("PROB@einheit_a", befund)

    def test_ohne_provider_bleibt_die_auswahl_unveraendert(self):
        """⚠ Die benannte Grenze: ohne `--provider` sagt das Register nichts.

        Dann gilt die Provider-Kette der Rolle aus `registry.yaml` — dieselbe Grenze, die
        `besetzungsbefund` seit `SWR-171` benennt. Der Filter darf sie nicht heimlich
        erweitern, sonst änderte diese Anforderung das Verhalten aller Sprint-Läufe mit.
        """
        ts = [ticket("T-0001", "cm", prio="hoch"), ticket("T-0002", "prob")]
        t, befund = self.waehle(ts, provider=None)
        self.assertEqual(t["id"], "T-0001")
        self.assertEqual(befund, "")

    def test_ohne_repos_bleibt_die_auswahl_unveraendert(self):
        """Fehlt die Wurzel, wird nicht geraten — dieselbe Lage wie ohne Provider."""
        ts = [ticket("T-0001", "cm", prio="hoch"), ticket("T-0002", "prob")]
        t, befund = tick_mod.waehle_ticket(ts, REGISTRY, provider="ollama")
        self.assertEqual(t["id"], "T-0001")
        self.assertEqual(befund, "")

    def test_leerer_bestand_traegt_keinen_besetzungsbefund(self):
        """⚠ „Nichts offen" und „nichts Besetztes offen" sind zwei Antworten.

        Nur die zweite darf den Bestandssatz tragen; sonst behauptete eine leere
        Ticketliste einen Besetzungsmangel, den niemand gemessen hat.
        """
        t, befund = self.waehle([])
        self.assertIsNone(t)
        self.assertEqual(befund, "")


class ZweiteLinieBleibtTest(SyntheticWurzel):
    """⚠ `besetzungsbefund` (SWR-171) ist NICHT verschoben worden.

    Es deckt die **erzwungene** Auswahl ab, die der Filter nie sieht. Ohne diese
    Zusicherung wäre die Reparatur eine Verschiebung mit einem neuen Loch dahinter — und
    genau die Sorte Lücke hat `SWR-171` selbst gefunden (*eine Gegenprobe, die die Funktion
    prüft und nicht ihren Aufrufer*).
    """

    def test_erzwungenes_ticket_wird_weiterhin_abgelehnt(self):
        befund = tick_mod.besetzungsbefund(self.root, "CM", "einheit_a", "ollama")
        self.assertTrue(befund)
        self.assertIn("keine Besetzung mit motor", befund)

    def test_besetzte_rolle_passiert_die_zweite_linie(self):
        self.assertEqual(
            tick_mod.besetzungsbefund(self.root, "PROB", "einheit_a", "ollama"), "")

    def test_beide_linien_lesen_denselben_resolver(self):
        """⚠ Kein B033: eine Frage an zwei Mengen, nicht zwei Kopien einer Antwort.

        Filter und zweite Linie rufen `organisation.besetzung_mit_motor` — der Ausdruck
        existiert **einmal**. Diese Zusicherung hält die beiden aneinander: wer eine der
        Stellen auf eine eigene Auslegung umbaut, macht sie rot.
        """
        ts = [ticket("T-0001", "prob")]
        t, _ = self.waehle(ts)
        self.assertIsNotNone(t)
        self.assertEqual(
            tick_mod.besetzungsbefund(self.root, "PROB", "einheit_a", "ollama"), "",
            "Filter und zweite Linie widersprechen sich — zwei Auslegungen einer Regel")

        ts = [ticket("T-0001", "cm")]
        t, _ = self.waehle(ts)
        self.assertIsNone(t)
        self.assertTrue(
            tick_mod.besetzungsbefund(self.root, "CM", "einheit_a", "ollama"),
            "Filter verwirft, zweite Linie lässt durch — zwei Auslegungen einer Regel")


class GrundmengeTest(SyntheticWurzel):
    """SWR-128-Familie: eine Prüfung, die das Register gar nicht liest, ist von einer,

    die keine Besetzung findet, nicht zu unterscheiden. Deshalb wird die Grundmenge
    ausdrücklich gemessen, bevor irgendein Ergebnis etwas bedeutet.
    """

    def test_die_synthetische_wurzel_traegt_genau_eine_ollama_besetzung(self):
        from backend import organisation
        self.assertEqual(organisation.besetzungen_mit_motor(self.root, "ollama"),
                         ["PROB@einheit_a"])


if __name__ == "__main__":
    unittest.main()
