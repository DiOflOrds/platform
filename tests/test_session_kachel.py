# -*- coding: utf-8 -*-
"""SWR-102 (pm/T-0040 aus den Briefen pm/N-0032/N-0033): Session-Zusammenfassung
in Mission Control — Block „Das Wichtigste", Zeitstempel aus dem Commit, Hinweis
bei ausgefallenem Lauf.

Hermetisch (gb-02): Temp-Root mit echtem Mini-Repo, kein Netz, keine Uhr von aussen —
`jetzt` wird injiziert, damit die Tests nicht um 00:00 kippen.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from backend import session  # noqa: E402
import sprint_register  # noqa: E402

AGENDA = """# Session-Agenda (PM-Team)

## Das Wichtigste (Stand 2026-08-16 20:50)

1. **Drei Briefe waren offen, alle drei sind beantwortet.**
2. Inbox leer, kein wartender DR.

---

## Fuer dich (E. John)

| Frist | Ticket |
|---|---|
| 17.08. | `pm/T-0034` |
"""


def _git(repo, *args, **kw):
    umgebung = dict(os.environ)
    umgebung.update(kw.pop("env_zusatz", {}) or {})
    return subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t"]
                          + list(args), capture_output=True, text=True, env=umgebung)


class WichtigstesTest(unittest.TestCase):
    """SWR-102: den Block schneiden — rein, ohne IO."""

    def test_block_wird_am_naechsten_trenner_beendet(self):
        """SWR-102: nur „Das Wichtigste", nicht der Rest der Agenda."""
        t = session.wichtigstes(AGENDA)
        self.assertIn("Drei Briefe waren offen", t)
        self.assertIn("Inbox leer", t)
        self.assertNotIn("Fuer dich", t)
        self.assertNotIn("T-0034", t)

    def test_ueberschrift_mit_stand_wird_nicht_mitgeliefert(self):
        """SWR-102 (T-0040 Befund c): Die Zeitangabe im Text darf nicht in die Kachel.

        Im Kopf steht „(Stand 2026-08-16 20:50)". Faellt der geplante Lauf aus, bleibt
        diese Zeile stehen und behauptet Frische — der Zeitstempel der Kachel kommt
        deshalb ausschliesslich aus dem Git-Commit (B038).
        """
        self.assertNotIn("Stand 2026-08-16 20:50", session.wichtigstes(AGENDA))
        self.assertNotIn("Das Wichtigste", session.wichtigstes(AGENDA))

    def test_ueberschrift_wird_am_anfang_erkannt_nicht_am_wortlaut(self):
        """SWR-102 (Lehre L-2026-08-16h/B054): kein Parser auf eine exakte Fassung.

        Der Zusatz in Klammern wechselt je Session; ein Parser, der auf den vollen
        Wortlaut zielt, laeuft genau dann ins Leere, wenn die schreibende Seite ihn
        aendert — das war B054.
        """
        for kopf in ["## Das Wichtigste", "## Das Wichtigste (Stand 2026-08-17 06:06)",
                     "##  Das Wichtigste — Kurzfassung"]:
            self.assertEqual(session.wichtigstes(kopf + "\n\nInhalt\n\n## Weiter\n"),
                             "Inhalt", kopf)

    def test_fehlender_block_liefert_leer_statt_dateianfang(self):
        """SWR-102: lieber nichts zeigen als irgendetwas — kein Ersatztext."""
        self.assertEqual(session.wichtigstes("# Agenda\n\nirgendein Text\n"), "")
        self.assertEqual(session.wichtigstes(""), "")


class StilleTest(unittest.TestCase):
    """SWR-102 (T-0040 DoD 2): „seit HH:MM keine Session", wenn der Lauf ausfiel."""

    def setUp(self):
        self.jetzt = datetime(2026, 8, 16, 21, 0, tzinfo=timezone.utc)

    def _vor(self, minuten):
        return (self.jetzt - timedelta(minutes=minuten)).isoformat()

    def test_frischer_lauf_ist_nicht_veraltet(self):
        """SWR-102: innerhalb von zwei Takten (2x30 Min) ist alles in Ordnung."""
        for minuten in (0, 5, 30, 59, 60):
            veraltet, hinweis = session.stille(self._vor(minuten), self.jetzt)
            self.assertFalse(veraltet, minuten)
            self.assertEqual(hinweis, "")

    def test_ausgefallener_lauf_nennt_die_uhrzeit(self):
        """SWR-102: nach zwei stillen Takten sagt die Kachel es ausdruecklich."""
        veraltet, hinweis = session.stille(self._vor(61), self.jetzt)
        self.assertTrue(veraltet)
        self.assertEqual(hinweis, "seit 19:59 keine Session")

    def test_ohne_lesbaren_zeitpunkt_gilt_veraltet_nicht_frisch(self):
        """SWR-102 (B038): im Zweifel „unbekannt" melden, nie Frische behaupten."""
        for kaputt in ("", "gestern", "2026-13-01T00:00:00+02:00"):
            veraltet, hinweis = session.stille(kaputt, self.jetzt)
            self.assertTrue(veraltet, kaputt)
            self.assertTrue(hinweis)

    def test_zeitzonenlose_und_zeitzonenbehaftete_angabe_vergleichbar(self):
        """SWR-102: git liefert %cI mit Offset; ein naives `jetzt` darf nicht crashen."""
        veraltet, _ = session.stille("2026-08-16T20:30:00+00:00",
                                     datetime(2026, 8, 16, 21, 0))
        self.assertFalse(veraltet)


class FortschreibungenTest(unittest.TestCase):
    """SWR-102 (Befund B056): gezaehlt werden Commits, und sie heissen auch so."""

    def test_nur_der_laufende_tag_zaehlt(self):
        jetzt = datetime(2026, 8, 16, 21, 0, tzinfo=timezone.utc)
        zeiten = ["2026-08-16T20:55:38+00:00", "2026-08-16T06:14:37+00:00",
                  "2026-08-15T23:59:59+00:00", "unlesbar"]
        self.assertEqual(session.fortschreibungen_heute(zeiten, jetzt), 2)

    def test_leere_historie_ist_null_kein_fehler(self):
        self.assertEqual(session.fortschreibungen_heute(
            [], datetime(2026, 8, 16, tzinfo=timezone.utc)), 0)


class StandTest(unittest.TestCase):
    """SWR-102: der zusammengesetzte Endpunkt-Inhalt gegen ein echtes Mini-Repo."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="session-kachel-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.repo = os.path.join(self.root, "pm")
        os.makedirs(os.path.join(self.repo, "management"))
        self.agenda = os.path.join(self.repo, "management", "session-agenda.md")
        with open(self.agenda, "w", encoding="utf-8", newline="\n") as f:
            f.write(AGENDA)
        _git(self.repo, "init", "-b", "main")
        _git(self.repo, "add", "-A")
        self.commit_zeit = datetime(2026, 8, 16, 20, 55, tzinfo=timezone.utc)
        _git(self.repo, "commit", "-m", "Agenda",
             env_zusatz={"GIT_AUTHOR_DATE": self.commit_zeit.isoformat(),
                         "GIT_COMMITTER_DATE": self.commit_zeit.isoformat()})

    def test_zeitstempel_kommt_aus_dem_commit_nicht_aus_dem_text(self):
        """SWR-102 (T-0040 DoD 1/Befund c): der Kern dieses Tickets.

        Die Agenda traegt im Text „Stand 2026-08-16 20:50", der Commit liegt auf
        20:55. Geliefert werden muss der Commit — sonst haelt eine stehengebliebene
        Datei ihren eigenen alten Stand fuer den aktuellen.
        """
        s = session.stand(self.root, jetzt=self.commit_zeit + timedelta(minutes=5))
        self.assertTrue(s["stand"].startswith("2026-08-16T20:55"), s["stand"])
        self.assertNotIn("20:50", s["stand"])

    def test_text_ist_der_block_und_kein_zweiter_text(self):
        """SWR-102 (T-0040 DoD 3): dieselbe Datei, nichts neu formuliert (B033)."""
        s = session.stand(self.root, jetzt=self.commit_zeit)
        self.assertIn("Drei Briefe waren offen", s["text"])
        self.assertNotIn("Fuer dich", s["text"])
        self.assertEqual(s["quelle"], "pm/management/session-agenda.md")

    def test_ausgefallener_lauf_meldet_sich_in_der_nutzlast(self):
        """SWR-102: zwei Takte spaeter traegt die Nutzlast den Hinweis.

        ⚠⚠ **Dieser Test stand bis Sprint 22 auf einer festen 95** — und 95 Minuten
        waren „zwei Takte", solange der Takt 30 Minuten betrug. Er war die DRITTE Kopie
        derselben Zahl (neben `session.TAKT_MINUTEN` und `takt_min` im Register) und
        wurde in dem Moment rot, in dem SWR-156 die beiden anderen in Einklang brachte.

        > Ein Test, der eine Zahl festschreibt, die anderswo eine Tatsache ist, haelt
        > nicht den Code fest, sondern den Irrtum. Er war die ganze Zeit gruen.

        Gerechnet wird deshalb aus dem Takt, der **gilt** — die Zusicherung ist „zwei
        Takte", und das ist sie jetzt auch im Wortlaut.
        """
        takt = session.takt(self.root)
        spaeter = takt * session.STILLE_TAKTE + 5
        s = session.stand(self.root, jetzt=self.commit_zeit + timedelta(minutes=spaeter))
        self.assertTrue(s["veraltet"])
        self.assertEqual(s["hinweis"], "seit 20:55 keine Session")
        # Und die Gegenprobe zur selben Grenze: knapp DARUNTER schweigt die Kachel.
        s = session.stand(self.root,
                          jetzt=self.commit_zeit + timedelta(minutes=takt * session.STILLE_TAKTE))
        self.assertFalse(s["veraltet"])

    def test_der_takt_der_kachel_kommt_aus_dem_register(self):
        """SWR-156 (platform/T-0025): die Kachel folgt dem **hinterlegten** Takt.

        ⚠ Der Befund dahinter ist unangenehm leise: `session.TAKT_MINUTEN` stand auf
        **30**, waehrend das Register seit dem 17.08. **60** fuehrt. Die Kachel meldete
        Stille nach einer statt nach zwei Stunden, und beide Zahlen sahen fuer sich
        plausibel aus (B033). Hier wird der Zusammenhang **hergestellt**: dasselbe
        Repo, zwei Register, zwei Antworten.
        """
        verz = os.path.join(self.root, "pm", "management")
        pfad = os.path.join(verz, "sprints.jsonl")
        for takt, veraltet_erwartet in ((30, True), (60, False)):
            with open(pfad, "w", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps({"nr": 1, "kennung": "k1", "takt_min": takt,
                                    "start": "2026-08-16 20:00"}) + "\n")
            self.assertEqual(session.takt(self.root), takt)
            s = session.stand(self.root,
                              jetzt=self.commit_zeit + timedelta(minutes=95))
            self.assertIs(s["veraltet"], veraltet_erwartet, takt)
        os.remove(pfad)
        # Ohne Register gilt der Rueckfall — und er ist ausdruecklich der des
        # Registers (60) und nicht die alte Konstante im Quelltext (30).
        self.assertEqual(session.takt(self.root), sprint_register.TAKT_MIN_STANDARD)

    def test_zweiter_commit_zaehlt_als_zweite_fortschreibung(self):
        """SWR-102: die Tageszahl kommt aus der Historie, nicht aus dem Text."""
        with open(self.agenda, "a", encoding="utf-8", newline="\n") as f:
            f.write("\nNachtrag\n")
        _git(self.repo, "add", "-A")
        spaeter = self.commit_zeit + timedelta(minutes=20)
        _git(self.repo, "commit", "-m", "Agenda 2",
             env_zusatz={"GIT_AUTHOR_DATE": spaeter.isoformat(),
                         "GIT_COMMITTER_DATE": spaeter.isoformat()})
        s = session.stand(self.root, jetzt=spaeter)
        self.assertEqual(s["fortschreibungen_heute"], 2)

    def test_fehlende_datei_bricht_nicht_ab(self):
        """SWR-102: ohne Agenda liefert der Endpunkt eine leere, ehrliche Kachel."""
        os.remove(self.agenda)
        s = session.stand(self.root, jetzt=self.commit_zeit)
        self.assertEqual(s["text"], "")
        self.assertTrue(s["quelle"])

    def test_kein_git_repo_liefert_unbekannt_statt_ausnahme(self):
        """SWR-102: ohne Historie gibt es keinen Zeitstempel — und damit „veraltet"."""
        leer = tempfile.mkdtemp(prefix="session-ohne-git-")
        self.addCleanup(shutil.rmtree, leer, ignore_errors=True)
        os.makedirs(os.path.join(leer, "pm", "management"))
        s = session.stand(leer, jetzt=self.commit_zeit)
        self.assertEqual(s["stand"], "")
        self.assertTrue(s["veraltet"])


class EndpunktTest(unittest.TestCase):
    """SWR-102 (T-0040 DoD 1): `GET /api/session` liefert die Kachel-Nutzlast."""

    def setUp(self):
        import threading
        from backend import server
        self.root = tempfile.mkdtemp(prefix="session-http-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        repo = os.path.join(self.root, "pm")
        os.makedirs(os.path.join(repo, "management"))
        with open(os.path.join(repo, "management", "session-agenda.md"),
                  "w", encoding="utf-8", newline="\n") as f:
            f.write(AGENDA)
        _git(repo, "init", "-b", "main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "Agenda")
        server.Api.protokoll = lambda *a, **k: None
        self.srv = server.start(self.root, port=0)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)

    def test_endpunkt_liefert_block_und_commit_zeitstempel(self):
        """SWR-102: der Endpunkt existiert und traegt beides — Text und Zeitpunkt."""
        import json
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:%d/api/session" % self.port) as r:
            daten = json.loads(r.read().decode("utf-8"))
        self.assertIn("Drei Briefe waren offen", daten["text"])
        self.assertNotIn("Fuer dich", daten["text"])
        self.assertRegex(daten["stand"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
        self.assertEqual(daten["quelle"], "pm/management/session-agenda.md")
        self.assertFalse(daten["veraltet"])


if __name__ == "__main__":
    unittest.main()
