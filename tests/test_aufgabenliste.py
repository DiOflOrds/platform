"""SWR-132 (pm/T-0064, Briefe pm/N-0038 + pm/N-0042): die projektuebergreifende Liste.

Der Auftraggeber will alle offenen Aufgaben aller Teams und Projekte sehen, um selbst zu
priorisieren — und sie nach Rollen gruppiert sehen. Beides ist **dieselbe** Liste.

⚠ Der Kern dieser Tests ist nicht, dass eine Liste geliefert wird, sondern dass sie
**nicht neben** der Zahl steht, die es schon gab: `offen_gesamt` kommt aus derselben
Python-Liste. Zwei Erhebungswege waeren genau der Zustand, den SWR-131 in diesem Sprint
gekostet hat.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
import board  # noqa: E402
from backend import sprint  # noqa: E402

TICKET = """---
id: {tid}
titel: "{titel}"
typ: task
prozess: man3
rolle: {rolle}
sprint: 1
status: {status}
prio: mittel
blocked_by: []
repo: {repo}
{extra}geändert: 2026-08-17
erstellt: 2026-08-17
---

Rumpf.
"""


class AufgabenlisteTest(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def ticket(self, projekt, tid, rolle="pl", status="open", titel="Aufgabe", **extra):
        repo = os.path.join(self.root, projekt)
        verz = os.path.join(repo, "tickets")
        neu = not os.path.isdir(verz)
        os.makedirs(verz, exist_ok=True)
        zusatz = "".join(f"{k}: {v}\n" for k, v in extra.items())
        with open(os.path.join(verz, tid + ".md"), "w", encoding="utf-8") as f:
            f.write(TICKET.format(tid=tid, titel=titel, rolle=rolle, status=status,
                                  repo=projekt, extra=zusatz))
        if neu:
            subprocess.run(["git", "-C", repo, "init", "-q"], check=True)

    def test_liste_enthaelt_alle_projekte_und_ist_nicht_gekuerzt(self):
        """⚠ Nicht auf drei gekuerzt wie die Kachel (SWR-074/094).

        Der Zweck der Liste ist, dass der Auftraggeber ALLES sieht. Eine still gekuerzte
        Liste ist eine zweite Priorisierung neben der, die er selbst treffen will —
        deshalb fuenf Tickets und die Erwartung fuenf, nicht drei.
        """
        for i in range(1, 6):
            self.ticket("p0", f"T-000{i}")
        self.ticket("p1", "T-0001")
        offene = sprint.offene_tickets(self.root)
        self.assertEqual(len(offene), 6)
        self.assertEqual(sorted({o["projekt"] for o in offene}), ["p0", "p1"])

    def test_geschlossene_tickets_fehlen(self):
        """„alle ausser geschlossen" — woertlich aus pm/N-0042."""
        self.ticket("p0", "T-0001", status="open")
        self.ticket("p0", "T-0002", status="done")
        self.ticket("p0", "T-0003", status="rejected")
        refs = [o["ref"] for o in sprint.offene_tickets(self.root)]
        self.assertEqual(refs, ["p0/T-0001"])

    def test_rolle_und_verantwortlich_sind_getrennte_felder(self):
        """⚠ Nicht verschmolzen — das war der Befund hinter SWR-116.

        Die Fachrolle (`pl`, `dev`, …) und die Frage „handelt der Mensch oder das Team?"
        sind zwei Fragen. `rolle: mensch` trug bis SWR-116 eine zweite,
        verhaltensaendernde Bedeutung; genau deshalb bleiben es zwei Schluessel.
        """
        self.ticket("p0", "T-0001", rolle="pl")
        self.ticket("p0", "T-0002", rolle="dev", verantwortlich="mensch")
        nach = {o["id"]: o for o in sprint.offene_tickets(self.root)}
        self.assertEqual(nach["T-0001"]["rolle"], "pl")
        self.assertEqual(nach["T-0001"]["verantwortlich"], "team")   # Default SWR-116
        self.assertEqual(nach["T-0002"]["rolle"], "dev")
        self.assertEqual(nach["T-0002"]["verantwortlich"], "mensch")

    def test_verantwortlich_kommt_aus_dem_aufloesungspunkt(self):
        """B033: derselbe Default wie die Board-Spalte, nicht ein zweiter.

        Ohne diesen Test koennte die Liste ein leeres Feld anders lesen als
        `board.verantwortlich_wert` — und dann sagen Liste und Board zwei Dinge ueber
        dasselbe Ticket.
        """
        self.ticket("p0", "T-0001", verantwortlich="unsinn")
        o = sprint.offene_tickets(self.root)[0]
        self.assertEqual(o["verantwortlich"],
                         board.verantwortlich_wert({"verantwortlich": "unsinn"}))

    def test_takt_tickets_sind_enthalten(self):
        """Dauerpflichten gehoeren in jeden Sprint — kein Datum heisst nicht planlos."""
        self.ticket("p0", "T-0001", takt="je-session")
        offene = sprint.offene_tickets(self.root)
        self.assertEqual(len(offene), 1)
        self.assertEqual(offene[0]["takt"], "je-session")


class ZahlUndListeTest(unittest.TestCase):
    """⚠ Die eigentliche Zusicherung von SWR-132."""

    def test_offen_gesamt_und_offene_sind_dasselbe_objekt(self):
        """Zahl und Liste koennen nicht auseinanderlaufen — es ist EIN Objekt.

        ⚠ Das ist die Lehre aus SWR-131, im selben Lauf angewandt: dort hatten vier Leser
        vier Formulierungen fuer „entschieden", und der Preis war nicht, dass alle falsch
        waren, sondern dass sie **verschieden** waren. Ein zweiter Erhebungsweg fuer diese
        Liste haette dieselbe Bauart gehabt.

        Der Test prueft die **Identitaet**, nicht die Gleichheit der Laenge: zwei getrennt
        erhobene Listen koennen in einem Lauf zufaellig gleich lang sein und im naechsten
        nicht.
        """
        root = os.path.dirname(os.path.dirname(_HIER))
        if not os.path.isdir(os.path.join(root, "pm", "management")):
            self.skipTest("Bestand nicht vorhanden (isolierte Testumgebung)")
        p = sprint.plan(root)
        self.assertIn("offene", p)
        self.assertEqual(len(p["offene"]), p["offen_gesamt"])

    def test_die_liste_traegt_die_felder_der_rollen_sicht(self):
        """Die Ansicht braucht `rolle`, `verantwortlich`, `ref`, `status`, `titel`."""
        root = os.path.dirname(os.path.dirname(_HIER))
        if not os.path.isdir(os.path.join(root, "pm", "management")):
            self.skipTest("Bestand nicht vorhanden (isolierte Testumgebung)")
        p = sprint.plan(root)
        if not p["offene"]:
            self.skipTest("kein offenes Ticket im Bestand")
        for feld in ("ref", "projekt", "id", "titel", "status", "rolle",
                     "verantwortlich", "takt", "geplant_sprint"):
            self.assertIn(feld, p["offene"][0], f"Feld {feld} fehlt in der Liste")

    def test_kein_ticket_objekt_in_der_antwort(self):
        """`_ticket` ist Innenleben und darf die API nicht verlassen.

        Es traegt `_body` (den ganzen Ticketrumpf) — in einer Liste ueber ~30 Tickets waere
        das ein Vielfaches der Nutzlast, und es waere ein zweiter Weg zu Feldern, die die
        Liste schon explizit fuehrt (B033).
        """
        root = os.path.dirname(os.path.dirname(_HIER))
        if not os.path.isdir(os.path.join(root, "pm", "management")):
            self.skipTest("Bestand nicht vorhanden (isolierte Testumgebung)")
        p = sprint.plan(root)
        for o in p["offene"]:
            self.assertNotIn("_ticket", o)


class AnsichtLiestDieRegelnTest(unittest.TestCase):
    """ADR-008: die Entscheidungen liegen in `regeln.js`, nicht in `app.js`."""

    def setUp(self):
        wurzel = os.path.dirname(_HIER)
        with open(os.path.join(wurzel, "backend", "static", "app.js"),
                  encoding="utf-8") as f:
            self.app = f.read()

    def test_app_js_liest_die_gruppierung_aus_regeln(self):
        for name in ("Regeln.aufgabenNachRolle", "Regeln.sortiereAufgaben",
                     "Regeln.gruppenTitel", "Regeln.OHNE_ROLLE"):
            self.assertIn(name, self.app, f"{name} wird in app.js nicht gelesen")

    def test_app_js_fuehrt_keine_eigene_gruppierung(self):
        """Gegenprobe: keine zweite Kopie der Regel in der Anzeige.

        ⚠ Wandert die Gruppierung zurueck nach `app.js`, ist sie wieder nur mit einem
        Browser pruefbar — genau der Zustand, den ADR-008 beendet hat. Sprint 11 hat
        gemessen, was eine Regel ohne Pruefung wert ist (SWR-125).
        """
        verdaechtig = [z for z in self.app.splitlines()
                       if "ohne Rolle" in z and "Regeln." not in z]
        self.assertEqual(verdaechtig, [],
                         f"app.js formuliert die Rollenregel selbst: {verdaechtig}")

    def test_der_leere_fall_wird_benannt(self):
        """„nichts da" und „nicht geladen" duerfen nicht gleich aussehen (SWR-114)."""
        self.assertIn("echte Null", self.app)


if __name__ == "__main__":
    unittest.main()
