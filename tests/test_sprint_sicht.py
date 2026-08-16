# -*- coding: utf-8 -*-
"""SWR-103 (pm/T-0016 nach pm/D006): Sprint-Workflow-Sicht in Mission Control —
Plantabelle aus `pm/management/sprint-aktuell.md`, Zustaende statt Fristfarben,
und der Bestandsabgleich, der ungeplante Tickets meldet.

Hermetisch (gb-02): Temp-Root mit echten Mini-Repos, kein Netz, keine Uhr von aussen —
`heute`/`jetzt` werden injiziert, damit die Tests nicht um 00:00 kippen.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import sprint  # noqa: E402

HEUTE = date(2026, 8, 16)

PLAN = """# Sprint aktuell — Genesis-Gesamtsprint (Workflow-Sicht des PM, pm/D006)

## Das Wichtigste

1. **18 offene Aufgaben, alle terminiert.**
2. Nichts wartet ohne Datum.

| diese Tabelle | steht vor der Ueberschrift |
|---|---|
| und | darf nicht als Plan gelten |

## Sprint-Plan

*Sprint = dieser Lauf.*

| Aufgabe | Rolle | Fällig | Status | Grund / nächster Schritt |
|---|---|---|---|---|
| pm/T-0016 | chg | dieser Sprint | in Arbeit | Workflow-Sicht im HMI. |
| pm/T-0034 | prob | 2026-08-17 | wartet-auf-Mensch | Nur am Host pruefbar. |
| team-mail/T-0001 | dev | wartet-auf-Mensch | blockiert | Beginnt mit IMAP. |
| pm/T-0039 | pl | 2026-08-23 | terminiert | Eigene Flaeche. |
| pm/T-0099 | pl | 2026-08-10 | terminiert | Laengst faellig. |

## Nicht in diesem Sprint

| noch eine Tabelle | die nicht zaehlt |
|---|---|
| weil | sie nach der ersten kommt |
"""

TICKET = """---
id: {tid}
titel: "{titel}"
typ: task
prozess: swe1
rolle: pl
sprint: 1
status: {status}
prio: mittel
erstellt: 2026-08-16
---

Rumpf.
"""


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t"]
                          + list(args), capture_output=True, text=True)


def _repo(root, name, tickets):
    """Mini-Repo mit tickets/ und .git — genau das, was die Discovery erwartet."""
    pfad = os.path.join(root, name)
    os.makedirs(os.path.join(pfad, "tickets"))
    for tid, status in tickets:
        with open(os.path.join(pfad, "tickets", tid + ".md"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(TICKET.format(tid=tid, titel="Aufgabe " + tid, status=status))
    _git(pfad, "init", "-b", "main")
    _git(pfad, "add", "-A")
    _git(pfad, "commit", "-m", "init")
    return pfad


class PlanTabelleTest(unittest.TestCase):
    """SWR-103: die richtige Tabelle finden — und nur die."""

    def test_erste_tabelle_nach_der_ueberschrift_gewinnt(self):
        """Die Tabelle im Kurzblock steht vorher und darf nicht der Plan sein."""
        t = sprint.plan_tabelle(PLAN)
        self.assertEqual(len(t["zeilen"]), 5)
        self.assertIn("Aufgabe", t["spalten"][0])

    def test_tabelle_nach_der_naechsten_ueberschrift_zaehlt_nicht(self):
        """Nur die erste Tabelle nach dem Plan-Kopf — keine spaeteren Anhaenge."""
        t = sprint.plan_tabelle(PLAN)
        flach = " ".join(" ".join(z) for z in t["zeilen"])
        self.assertNotIn("die nicht zaehlt", flach)

    def test_ueberschrift_wird_am_anfang_erkannt_nicht_an_ihrer_fassung(self):
        """L-2026-08-16h Regel 2: der Zusatz hinter dem Namen aendert sich je Session."""
        for kopf in ("## Sprint-Plan",
                     "## Sprint-Plan (Workflow-Sicht des PM, Stand 2026-08-16 22:19)",
                     "### Sprint-Plan — alle Repos"):
            text = kopf + "\n\n| Aufgabe | Fällig |\n|---|---|\n| pm/T-0001 | dieser Sprint |\n"
            with self.subTest(kopf=kopf):
                self.assertEqual(len(sprint.plan_tabelle(text)["zeilen"]), 1)

    def test_ohne_ueberschrift_kein_ersatzplan(self):
        """Fehlt der Kopf, ist das Ergebnis leer — nicht irgendeine andere Tabelle."""
        text = "# Titel\n\n| Aufgabe | Fällig |\n|---|---|\n| pm/T-0001 | dieser Sprint |\n"
        self.assertIsNone(sprint.plan_tabelle(text))
        self.assertEqual(sprint.zeilen(sprint.plan_tabelle(text), HEUTE), [])


class ZustandTest(unittest.TestCase):
    """SWR-103: benannte Zustaende sind keine Fristen."""

    def test_dieser_sprint_ist_nie_gruen(self):
        """Gruen heisst „Termin liegt komfortabel in der Zukunft" — hier gibt es keinen."""
        zustand, ampel = sprint.faellig_zustand("dieser Sprint", HEUTE)
        self.assertEqual(zustand, sprint.ZUSTAND_SPRINT)
        self.assertNotEqual(ampel, "gruen")

    def test_wartet_auf_mensch_ist_nie_gruen(self):
        zustand, ampel = sprint.faellig_zustand("wartet-auf-Mensch", HEUTE)
        self.assertEqual(zustand, sprint.ZUSTAND_MENSCH)
        self.assertNotEqual(ampel, "gruen")

    def test_datum_benutzt_die_geteilte_ampelregel(self):
        """SWR-091 ist die eine Quelle — hier wird sie benutzt, nicht nachgebaut (B033)."""
        self.assertEqual(sprint.faellig_zustand("2026-08-10", HEUTE), ("termin", "rot"))
        self.assertEqual(sprint.faellig_zustand("2026-08-17", HEUTE), ("termin", "gelb"))
        self.assertEqual(sprint.faellig_zustand("2026-08-23", HEUTE), ("termin", "gruen"))

    def test_leere_zelle_bleibt_grau_und_ohne_zustand(self):
        self.assertEqual(sprint.faellig_zustand("", HEUTE), (sprint.ZUSTAND_OFFEN, "grau"))

    def test_mensch_wird_auch_aus_der_statusspalte_gelesen(self):
        """Termin UND Zustaendigkeit: `pm/T-0034` hat ein Datum und wartet trotzdem.

        Die erste Fassung las nur die Faelligkeitsspalte und meldete 1 statt 5 — der
        Klartext derselben Datei sagte „5 warten auf eine Handlung am Host". Ein Feld
        mit zwei Bedeutungen ist die Familie aus B053.
        """
        self.assertTrue(sprint.wartet_auf_mensch("2026-08-17", "wartet-auf-Mensch"))
        self.assertTrue(sprint.wartet_auf_mensch("wartet-auf-Mensch", "blockiert"))
        self.assertFalse(sprint.wartet_auf_mensch("2026-08-23", "terminiert"))


class ZeilenUndZaehlerTest(unittest.TestCase):
    """SWR-103: was die Kachel anzeigt."""

    def setUp(self):
        self.zeilen = sprint.zeilen(sprint.plan_tabelle(PLAN), HEUTE)

    def test_spalten_werden_ueber_ihren_kopf_zugeordnet(self):
        z = self.zeilen[0]
        self.assertEqual(z["aufgabe"], "pm/T-0016")
        self.assertEqual(z["rolle"], "chg")
        self.assertEqual(z["status"], "in Arbeit")
        self.assertIn("Workflow-Sicht", z["grund"])

    def test_ueberfaellige_planzeile_ist_rot(self):
        """Ein Datum in der Vergangenheit bleibt rot — auch im Plan, nicht nur im Board."""
        alt = [z for z in self.zeilen if "T-0099" in z["aufgabe"]][0]
        self.assertEqual(alt["ampel"], "rot")

    def test_zaehler_zerlegen_den_plan_vollstaendig(self):
        z = sprint.zaehler(self.zeilen)
        self.assertEqual(z["dieser_sprint"] + z["terminiert"] + z["ohne_termin"]
                         + z["ohne_zustand"], len(self.zeilen))

    def test_wartet_auf_mensch_liegt_quer_zur_zerlegung(self):
        """Die Zahl darf sich mit `terminiert` ueberschneiden — sonst ginge eine Aussage verloren."""
        z = sprint.zaehler(self.zeilen)
        self.assertEqual(z["dieser_sprint"], 1)
        self.assertEqual(z["terminiert"], 3)
        self.assertEqual(z["ohne_termin"], 1)
        self.assertEqual(z["wartet_auf_mensch"], 2)


class RefsTest(unittest.TestCase):
    """SWR-103: der Plan wird von Hand geschrieben — der Vergleich muss tolerant sein."""

    def test_beide_schreibweisen_werden_erkannt(self):
        self.assertEqual(sprint.refs_der_zeile("pm/T-0016"), {"pm/T-0016", "T-0016"})
        self.assertEqual(sprint.refs_der_zeile("T-0016"), {"T-0016"})

    def test_mehrere_refs_in_einer_zelle(self):
        self.assertEqual(sprint.refs_der_zeile("pm/T-0036 + pm/T-0038"),
                         {"pm/T-0036", "T-0036", "pm/T-0038", "T-0038"})

    def test_markdown_auszeichnung_stoert_nicht(self):
        self.assertIn("pm/T-0016", sprint.refs_der_zeile("**`pm/T-0016`**"))


class BestandsabgleichTest(unittest.TestCase):
    """SWR-103 DoD 3: der Kern — was im Plan FEHLT.

    Der Anlass ist belegt: `pm/T-0016` war das einzige unterminierte Ticket der
    Organisation und stand in keiner Agendaliste. Eine Sicht, die nur abschreibt,
    was ihr vorgelegt wird, findet so etwas nie (B049/B044).
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="sprint-abgleich-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        _repo(self.root, "pm", [("T-0016", "in_progress"), ("T-0034", "open"),
                                ("T-0077", "open"), ("T-0002", "done")])
        _repo(self.root, "team-mail", [("T-0001", "open")])

    def test_offene_tickets_aller_repos_werden_gefunden(self):
        refs = sorted(t["ref"] for t in sprint.offene_tickets(self.root))
        self.assertEqual(refs, ["pm/T-0016", "pm/T-0034", "pm/T-0077", "team-mail/T-0001"])

    def test_geschlossene_tickets_zaehlen_nicht(self):
        self.assertNotIn("pm/T-0002",
                         [t["ref"] for t in sprint.offene_tickets(self.root)])

    def test_ungeplantes_ticket_wird_gemeldet(self):
        """`pm/T-0077` steht in keiner Planzeile — genau der Fall, der B049 ausgeloest hat."""
        zeilen = sprint.zeilen(sprint.plan_tabelle(PLAN), HEUTE)
        fehlend = sprint.nicht_geplant(zeilen, sprint.offene_tickets(self.root))
        self.assertEqual([t["ref"] for t in fehlend], ["pm/T-0077"])

    def test_vollstaendiger_plan_meldet_nichts(self):
        """Kein Fehlalarm: ist alles geplant, ist die Liste leer."""
        zeilen = sprint.zeilen(sprint.plan_tabelle(
            PLAN + "\n\n## Sprint-Plan\n\n| Aufgabe | Fällig |\n|---|---|\n"), HEUTE)
        alle = sprint.offene_tickets(self.root)
        voll = zeilen + [{"refs": [t["ref"]]} for t in alle]
        self.assertEqual(sprint.nicht_geplant(voll, alle), [])

    def test_nackte_ticketnummer_im_plan_zaehlt_auch(self):
        """Toleranter Vergleich: ein Fehlalarm hier trainiert das Wegschauen."""
        alle = sprint.offene_tickets(self.root)
        fehlend = sprint.nicht_geplant([{"refs": ["T-0077"]}], alle)
        self.assertNotIn("pm/T-0077", [t["ref"] for t in fehlend])


class PlanEndeZuEndeTest(unittest.TestCase):
    """SWR-103: `plan()` gegen ein echtes Mini-Repo — Datei, Git, Discovery."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="sprint-plan-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        pm = _repo(self.root, "pm", [("T-0016", "in_progress"), ("T-0034", "open")])
        os.makedirs(os.path.join(pm, "management"))
        with open(os.path.join(pm, "management", "sprint-aktuell.md"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(PLAN)
        _git(pm, "add", "-A")
        _git(pm, "commit", "-m", "Sprint-Plan")
        self.jetzt = datetime.now(timezone.utc)

    def test_kurzblock_ohne_ueberschriftzeile(self):
        """Wie SWR-102: die Ueberschrift traegt die Textzeit und wird nicht mitgeliefert."""
        d = sprint.plan(self.root, jetzt=self.jetzt, heute=HEUTE)
        self.assertIn("18 offene Aufgaben", d["text"])
        self.assertNotIn("## Das Wichtigste", d["text"])

    def test_zeitstempel_kommt_aus_dem_commit(self):
        d = sprint.plan(self.root, jetzt=self.jetzt, heute=HEUTE)
        self.assertRegex(d["stand"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
        self.assertFalse(d["veraltet"])

    def test_zwei_stille_takte_machen_den_plan_veraltet(self):
        """Faellt der Lauf aus, sagt die Kachel das — sonst sieht Altes frisch aus (B038)."""
        d = sprint.plan(self.root, jetzt=self.jetzt + timedelta(minutes=61), heute=HEUTE)
        self.assertTrue(d["veraltet"])
        self.assertIn("keine Session", d["hinweis"])

    def test_bestandsabgleich_laeuft_im_plan_mit(self):
        d = sprint.plan(self.root, jetzt=self.jetzt, heute=HEUTE)
        self.assertEqual(d["offen_gesamt"], 2)
        self.assertEqual(d["nicht_geplant"], [])

    def test_fehlende_datei_wirft_nicht(self):
        leer = tempfile.mkdtemp(prefix="sprint-leer-")
        self.addCleanup(shutil.rmtree, leer, ignore_errors=True)
        d = sprint.plan(leer, jetzt=self.jetzt, heute=HEUTE)
        self.assertEqual(d["zeilen"], [])
        self.assertTrue(d["veraltet"])


class EndpunktTest(unittest.TestCase):
    """SWR-103 DoD 1: `GET /api/sprint` liefert die Nutzlast der Kachel.

    Das ist die Gegenprobe ueber den ECHTEN Abrufweg — gegen den Altstand antwortet
    derselbe Aufruf mit HTTP 404 „unbekannter Endpunkt". Ein ImportError haette nur
    belegt, dass ein Modul fehlt, nichts ueber den Schaden (L-2026-08-16h Regel 3).
    """

    def setUp(self):
        import threading
        from backend import server
        self.root = tempfile.mkdtemp(prefix="sprint-http-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        pm = _repo(self.root, "pm", [("T-0016", "in_progress")])
        os.makedirs(os.path.join(pm, "management"))
        with open(os.path.join(pm, "management", "sprint-aktuell.md"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(PLAN)
        _git(pm, "add", "-A")
        _git(pm, "commit", "-m", "Sprint-Plan")
        server.Api.protokoll = lambda *a, **k: None
        self.srv = server.start(self.root, port=0)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)

    def test_endpunkt_liefert_plan_zaehler_und_quelle(self):
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:%d/api/sprint" % self.port) as r:
            daten = json.loads(r.read().decode("utf-8"))
        self.assertEqual(len(daten["zeilen"]), 5)
        self.assertEqual(daten["zeilen"][0]["aufgabe"], "pm/T-0016")
        self.assertEqual(daten["zaehler"]["dieser_sprint"], 1)
        self.assertEqual(daten["zaehler"]["wartet_auf_mensch"], 2)
        self.assertEqual(daten["quelle"], "pm/management/sprint-aktuell.md")
        self.assertIn("18 offene Aufgaben", daten["text"])
        self.assertNotIn("## Das Wichtigste", daten["text"])


if __name__ == "__main__":
    unittest.main()
