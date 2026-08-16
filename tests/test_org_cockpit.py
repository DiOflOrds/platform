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


DR_TICKET = ("---\nid: T-0002\ntitel: \"DR: Freigabe\"\ntyp: decision-request\n"
             "prozess: man3\nrolle: pl\nsprint: 0\nstatus: open\nprio: hoch\n"
             "blocked_by: []\noptionen: [G1a, G1b]\nfrist: 2026-08-23\n"
             "default: G1a\ngeändert: 2026-08-16\nerstellt: 2026-08-16\n---\n\n"
             "## Sachverhalt\n\nBitte freigeben.\n")


class UeberfaelligTest(RepoWelt):
    """pm/T-0030 (Brief pm/N-0025): „offene aufgaben ... müssen auch terminiert werden."

    Bis SWR-091 hatte nur der Decision-Request ein Zeitkonzept; ein CR mit
    `prio: mittel` konnte beliebig lange offen bleiben, ohne dass irgendein
    Werkzeug das gemeldet hätte (belegt an pm/T-0025, sechs Sessions).
    """

    HEUTE = __import__("datetime").date(2026, 8, 16)

    def _ticket(self, basis, tid, **felder):
        text = TICKET.replace("id: T-0001", f"id: {tid}")
        for feld, wert in felder.items():
            if feld in text:
                text = _ersetze_feld(text, feld, wert)
            else:
                text = text.replace("status: open\n", f"status: open\n{feld}: {wert}\n")
        with open(os.path.join(basis, "tickets", f"{tid}.md"), "w", encoding="utf-8") as f:
            f.write(text)

    def test_ueberfaelliges_backlog_ticket_steht_in_der_kachel(self):
        """SWR-091: Ein offenes CR über seiner Frist erscheint eigenständig samt
        Tagen-über — nicht nur irgendwo in der auf drei gekürzten Aufgabenliste."""
        basis = self._repo("pm-test", team_typ="pm")
        os.remove(os.path.join(basis, "tickets", "T-0001.md"))
        self._ticket(basis, "T-0001", typ="change-request", frist="2026-08-12")
        self._ticket(basis, "T-0002", typ="change-request", frist="2026-08-30")
        c = aggregation.cockpit(self.root, "pm-test", heute=self.HEUTE)
        self.assertEqual([u["id"] for u in c["ueberfaellig"]], ["T-0001"])
        self.assertEqual(c["ueberfaellig"][0]["frist"], "2026-08-12")
        self.assertEqual(c["ueberfaellig"][0]["tage"], 4)
        self.assertEqual(c["unterminiert"], 0)

    def test_erledigtes_ticket_ist_nie_ueberfaellig(self):
        """SWR-091: Eine gerissene Frist an einem abgeschlossenen Ticket ist Historie."""
        basis = self._repo("pm-done", team_typ="pm")
        os.remove(os.path.join(basis, "tickets", "T-0001.md"))
        self._ticket(basis, "T-0001", typ="change-request",
                     frist="2026-08-01", status="done")
        c = aggregation.cockpit(self.root, "pm-done", heute=self.HEUTE)
        self.assertEqual(c["ueberfaellig"], [])

    def test_unterminierte_tickets_werden_gezaehlt_takte_nicht(self):
        """SWR-091: Ein offenes Backlog-Ticket ohne Frist ist unterminiert und wird
        als solches benannt. Takt-Tickets (SWR-074) tragen ihr Zeitkonzept im Feld
        `takt` und zählen deshalb nicht mit — sonst stünde die Kachel dauerhaft auf
        Alarm und die Zahl verlöre ihre Bedeutung."""
        basis = self._repo("pm-ohne", team_typ="pm")
        os.remove(os.path.join(basis, "tickets", "T-0001.md"))
        self._ticket(basis, "T-0001", typ="change-request")
        self._ticket(basis, "T-0002", typ="task", takt="je-session")
        self._ticket(basis, "T-0003", typ="change-request", frist="2026-08-30")
        c = aggregation.cockpit(self.root, "pm-ohne", heute=self.HEUTE)
        self.assertEqual(c["unterminiert"], 1)
        self.assertEqual(c["ueberfaellig"], [])

    def test_dr_ampel_kommt_aus_board(self):
        """SWR-091: Die Ampel der offenen DRs ist dieselbe Funktion wie die der
        Backlog-Fristen — Gegenprobe gegen eine zweite Kopie der Regel (B033)."""
        basis = self._repo("pm-dr", team_typ="pm")
        with open(os.path.join(basis, "tickets", "T-0002.md"), "w", encoding="utf-8") as f:
            f.write(DR_TICKET)
        c = aggregation.cockpit(self.root, "pm-dr", heute=self.HEUTE)
        dr = c["offene_drs"][0]
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        import board
        self.assertEqual(dr["ampel"], board.frist_ampel(dr["frist"], self.HEUTE))
        self.assertEqual(dr["ampel"], "gruen")


class TaktFaelligTest(RepoWelt):
    """pm/T-0032 Teil 2 (Brief pm/N-0025): Uhrzeit-Takte in der Kachel. SWR-104.

    Ein Takt-Ticket trägt keine `frist` — es wäre für `ueberfaellig` und für den
    „ohne Frist"-Zähler gleichermaßen unsichtbar, obwohl sein Termin ableitbar ist.
    """

    ABENDS = __import__("datetime").datetime(2026, 8, 16, 15, 0)
    MITTAGS = __import__("datetime").datetime(2026, 8, 16, 12, 0)

    _ticket = UeberfaelligTest._ticket

    def test_faelliger_uhrzeit_takt_steht_in_der_kachel(self):
        """SWR-104: Ein Takt-Ticket, dessen Uhrzeit seit der letzten Erledigung
        vorbei ist, erscheint eigenständig — mit dem übersprungenen Termin im
        Klartext („überfällig seit"), nicht als „erledigt" (B038)."""
        basis = self._repo("pm-takt", team_typ="pm")
        os.remove(os.path.join(basis, "tickets", "T-0001.md"))
        self._ticket(basis, "T-0001", typ="task", takt="taeglich@14:00",
                     zuletzt_erledigt="2026-08-15 14:30")
        self._ticket(basis, "T-0002", typ="task", takt="taeglich@14:00",
                     zuletzt_erledigt="2026-08-16 14:30")
        c = aggregation.cockpit(self.root, "pm-takt", jetzt=self.ABENDS)
        self.assertEqual([u["id"] for u in c["takt_faellig"]], ["T-0001"])
        self.assertEqual(c["takt_faellig"][0]["seit"], "2026-08-16 14:00")
        self.assertEqual(c["takt_faellig"][0]["takt_klartext"], "täglich 14:00")
        self.assertEqual(c["takt_faellig"][0]["ampel"], "rot")

    def test_takt_ohne_uhrzeit_bleibt_aus_der_liste(self):
        """SWR-104: `je-session` sagt „bei jedem Lauf", nicht „zu einer Uhrzeit" —
        stünde es hier, meldete die Kachel dauerhaft Alarm und die Zahl verlöre
        ihre Bedeutung (derselbe Grund wie beim „ohne Frist"-Zähler)."""
        basis = self._repo("pm-takt-alt", team_typ="pm")
        os.remove(os.path.join(basis, "tickets", "T-0001.md"))
        self._ticket(basis, "T-0001", typ="task", takt="je-session")
        self._ticket(basis, "T-0002", typ="task", takt="woechentlich")
        c = aggregation.cockpit(self.root, "pm-takt-alt", jetzt=self.ABENDS)
        self.assertEqual(c["takt_faellig"], [])
        self.assertEqual(c["unterminiert"], 0)

    def test_der_moment_entscheidet_nicht_der_tag(self):
        """SWR-104/B057: Derselbe Bestand, derselbe TAG, zwei verschiedene Momente —
        um 12:00 ist der 14:00-Takt von heute noch nicht fällig, um 15:00 schon.
        Ein Cockpit, das nur den Tag kennt, könnte diese Frage nicht beantworten;
        genau deshalb hat `cockpit` seit SWR-104 zwei Bezüge statt eines."""
        basis = self._repo("pm-takt-moment", team_typ="pm")
        os.remove(os.path.join(basis, "tickets", "T-0001.md"))
        self._ticket(basis, "T-0001", typ="task", takt="taeglich@14:00",
                     zuletzt_erledigt="2026-08-16 09:00")
        mittags = aggregation.cockpit(self.root, "pm-takt-moment", jetzt=self.MITTAGS)
        abends = aggregation.cockpit(self.root, "pm-takt-moment", jetzt=self.ABENDS)
        self.assertEqual(mittags["takt_faellig"], [])
        self.assertEqual([u["id"] for u in abends["takt_faellig"]], ["T-0001"])

    def test_frist_mit_uhrzeit_laesst_die_kachel_nicht_platzen(self):
        """SWR-104/B059: Regression. `ist_ueberfaellig` akzeptiert seit SWR-104 auch
        eine Frist MIT Uhrzeit — die Tage-über-Rechnung daneben parste weiter nur ein
        reines Datum und riss mit `ValueError` das **gesamte** Cockpit mit
        (`cockpit_alle` läuft über alle Projekte), und zwar erst NACH Ablauf des
        Termins. Vor SWR-104 fiel derselbe Wert harmlos auf „grau"."""
        basis = self._repo("pm-frist-uhrzeit", team_typ="pm")
        os.remove(os.path.join(basis, "tickets", "T-0001.md"))
        self._ticket(basis, "T-0001", typ="change-request", frist="2026-08-15 14:00")
        c = aggregation.cockpit(self.root, "pm-frist-uhrzeit",
                                heute=__import__("datetime").date(2026, 8, 16))
        self.assertEqual([u["id"] for u in c["ueberfaellig"]], ["T-0001"])
        self.assertEqual(c["ueberfaellig"][0]["tage"], 1)

    def test_ohne_nachweis_gilt_der_takt_als_faellig(self):
        """SWR-104: Fehlt `zuletzt_erledigt`, gilt das Ticket als nie erledigt —
        nie als frisch. Dieselbe Vorsichtsregel wie `session.stille`."""
        basis = self._repo("pm-takt-neu", team_typ="pm")
        os.remove(os.path.join(basis, "tickets", "T-0001.md"))
        self._ticket(basis, "T-0001", typ="task", takt="taeglich@14:00")
        c = aggregation.cockpit(self.root, "pm-takt-neu", jetzt=self.ABENDS)
        self.assertEqual([u["id"] for u in c["takt_faellig"]], ["T-0001"])
        self.assertEqual(c["takt_faellig"][0]["zuletzt_erledigt"], "")


def _ersetze_feld(text, feld, wert):
    import re as _re
    return _re.sub(rf"(?m)^{feld}: .*$", f"{feld}: {wert}", text)


class VerschachtelteDrsTest(RepoWelt):
    """pm/T-0017: Ein Decision Request in `projects/<p>` muss den Menschen erreichen.

    Der Befund: `aggregation.projekte()` fand p10, aber Inbox, Übersicht und
    Frist-Warnmail bauten den Pfad weiter als `root/<name>` — der G1-DR war damit
    unsichtbar, während der Default still auf seine Frist zulief.
    """

    def _mit_dr(self, name, nested):
        basis = self._repo(name, nested=nested)
        with open(os.path.join(basis, "tickets", "T-0002.md"), "w", encoding="utf-8") as f:
            f.write(DR_TICKET)
        wurzel = os.path.join(self.root, "projects") if nested else basis
        _git(wurzel, "add", "-A")
        _git(wurzel, "commit", "-m", "dr")
        return basis

    def test_inbox_zeigt_dr_aus_sammelrepo(self):
        """SWR-027/070: Offene DRs verschachtelter Projekte stehen in der Inbox."""
        from backend import inbox
        self._mit_dr("p10", nested=True)
        eintraege = inbox.liste(self.root)["inbox"]
        self.assertEqual([(e["projekt"], e["id"]) for e in eintraege], [("p10", "T-0002")])
        e = eintraege[0]
        self.assertEqual(e["optionen"], ["G1a", "G1b"])   # Buttons (SWR-042)
        self.assertEqual(e["frist"], "2026-08-23")
        self.assertEqual(e["default"], "G1a")
        self.assertIn("Bitte freigeben", e["body"])

    def test_uebersicht_zaehlt_tickets_aus_sammelrepo(self):
        """SWR-026/070: Die Übersicht darf verschachtelte Projekte nicht als leer melden."""
        self._mit_dr("p10", nested=True)
        eintrag = {e["projekt"]: e for e in
                   aggregation.uebersicht(self.root)["projekte"]}["p10"]
        self.assertEqual(eintrag["tickets_gesamt"], 2)
        self.assertEqual(eintrag["tickets_offen"], 2)
        self.assertEqual([d["id"] for d in eintrag["offene_drs"]], ["T-0002"])

    def test_fristwarnung_sieht_dr_aus_sammelrepo(self):
        """SWR-033/034/070: Ohne diesen Pfad liefe der Default ohne Warnung ab."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        import dr_benachrichtigung
        self._mit_dr("p10", nested=True)
        funde = [(p, t["id"]) for p, t, _ in dr_benachrichtigung._offene_drs(self.root)]
        self.assertEqual(funde, [("p10", "T-0002")])

    def test_historie_zeigt_entschiedene_drs_aus_sammelrepo(self):
        """SWR-042/070: Auch die Entscheidungshistorie kennt verschachtelte Projekte."""
        from backend import inbox
        basis = self._mit_dr("p10", nested=True)
        pfad = os.path.join(basis, "tickets", "T-0002.md")
        text = open(pfad, encoding="utf-8").read().replace("status: open", "status: done")
        with open(pfad, "w", encoding="utf-8") as f:
            f.write(text)
        eintraege = inbox.historie(self.root)["historie"]
        self.assertIn(("p10", "T-0002"), [(e["projekt"], e["id"]) for e in eintraege])

    def test_top_level_projekte_unveraendert(self):
        """Regressionsschutz: die Auflösung darf Bestandsrepos nicht verschieben."""
        from backend import inbox
        self._mit_dr("p3", nested=False)
        self._mit_dr("p10", nested=True)
        self.assertEqual(sorted(e["projekt"] for e in inbox.liste(self.root)["inbox"]),
                         ["p10", "p3"])
        self.assertEqual(aggregation.projekt_pfad(self.root, "p3"),
                         os.path.join(self.root, "p3"))


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
