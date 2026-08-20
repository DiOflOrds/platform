# -*- coding: utf-8 -*-
"""SWR-153 (platform/T-0023, Brief pm/N-0043 Punkt 1): Die Kachel „Letzte Session"
nennt die SPRINTNUMMER des Laufs — aus dem Register über den COMMIT-Zeitpunkt.

⚠ **Die Gegenprobe steht zuerst.** Die Falle dieser Anforderung ist nicht, dass keine
Nummer erscheint, sondern dass die **falsche** erscheint: in der Überschrift der Agenda
steht dieselbe Zahl als Text, und ein ausgefallener Lauf lässt sie stehen. Der erste
Test stellt deshalb genau diesen Zustand her — Text sagt „Sprint 99", Register sagt
etwas anderes — und weist nach, dass die Kachel dem **Register** folgt. Ohne ihn wären
die übrigen Zusicherungen grün, während die Anzeige lügt (`L-2026-08-17ai`).

Hermetisch: Temp-Root mit echtem Mini-Repo, injizierte Zeiten, kein Netz.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import session  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import sprint_register  # noqa: E402

# ⚠ Die Überschrift trägt bewusst eine ANDERE Nummer als das Register. Sie ist der
# Köder: wer sie liest, wird rot.
AGENDA = """# Session-Agenda

## Das Wichtigste (Stand Sprint 99, 2026-08-20)

1. Der Lauf hat drei Aufgaben geschlossen.

---

## Für dich
"""


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t"]
                          + list(args), capture_output=True, text=True)


def _register(root, zeilen):
    pfad = os.path.join(root, "pm", "management", "sprints.jsonl")
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, "w", encoding="utf-8", newline="\n") as f:
        for z in zeilen:
            f.write(json.dumps(z, ensure_ascii=False) + "\n")


class FensterTest(unittest.TestCase):
    """`sprint_register.sprint_zu_zeit` — rein, ohne Git."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="sprintfenster-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        _register(self.root, [
            {"nr": 19, "kennung": "a", "start": "2026-08-17 20:20"},
            {"kennung": "a", "ende": "2026-08-17 21:17"},
            {"nr": 20, "kennung": "b", "start": "2026-08-17 21:59"},
            {"kennung": "b", "ende": "2026-08-17 22:18"},
        ])

    def test_zeitpunkt_im_fenster_trifft_den_sprint(self):
        self.assertEqual(sprint_register.sprint_zu_zeit(
            self.root, "2026-08-17T22:11:03+02:00"), 20)
        self.assertEqual(sprint_register.sprint_zu_zeit(
            self.root, "2026-08-17T20:45:00+02:00"), 19)

    def test_die_raender_gehoeren_dazu(self):
        """Start und Ende sind eingeschlossen — sonst fiele ein Lauf, der in seiner
        ersten Minute schreibt, aus seinem eigenen Sprint."""
        self.assertEqual(sprint_register.sprint_zu_zeit(
            self.root, "2026-08-17T21:59:00+02:00"), 20)
        self.assertEqual(sprint_register.sprint_zu_zeit(
            self.root, "2026-08-17T22:18:00+02:00"), 20)

    def test_luecke_zwischen_zwei_sprints_gehoert_zu_keinem(self):
        """⚠ Nicht auf den nächstgelegenen runden: ein Commit ausserhalb jedes Sprints
        ist selbst ein Befund, und eine geratene Nummer verdeckt ihn (B038)."""
        self.assertIsNone(sprint_register.sprint_zu_zeit(
            self.root, "2026-08-17T21:40:00+02:00"))

    def test_vor_dem_ersten_sprint_gehoert_zu_keinem(self):
        self.assertIsNone(sprint_register.sprint_zu_zeit(
            self.root, "2026-08-15T10:00:00+02:00"))

    def test_laufender_sprint_ohne_ende_reicht_bis_in_die_gegenwart(self):
        _register(self.root, [
            {"nr": 21, "kennung": "c", "start": "2026-08-20 10:20"},
        ])
        self.assertEqual(sprint_register.sprint_zu_zeit(
            self.root, "2026-08-20T11:45:00+02:00"), 21)

    def test_fehlendes_register_liefert_none_statt_ausnahme(self):
        leer = tempfile.mkdtemp(prefix="ohne-register-")
        self.addCleanup(shutil.rmtree, leer, ignore_errors=True)
        self.assertIsNone(sprint_register.sprint_zu_zeit(leer, "2026-08-20T10:30:00+02:00"))

    def test_unlesbare_zeit_liefert_none_statt_ausnahme(self):
        for wert in ("", None, "gestern", "2026-13-45T99:99"):
            with self.subTest(wert=wert):
                self.assertIsNone(sprint_register.sprint_zu_zeit(self.root, wert))


class KachelTest(unittest.TestCase):
    """SWR-153 am echten Lesepfad `session.stand()`."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="sessionnummer-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        repo = os.path.join(self.root, "pm")
        os.makedirs(os.path.join(repo, "management"))
        with open(os.path.join(repo, "management", "session-agenda.md"),
                  "w", encoding="utf-8", newline="\n") as f:
            f.write(AGENDA)
        _git(repo, "init", "-b", "main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "Agenda")
        self.commit_zeit = session._commit_zeiten(self.root)[0]

    def _register_um_den_commit(self, nr):
        """Ein Sprintfenster, das den echten Commit-Zeitpunkt sicher enthält."""
        a = datetime.fromisoformat(self.commit_zeit).replace(tzinfo=None)
        _register(self.root, [
            {"nr": nr, "kennung": "x",
             "start": (a.replace(second=0)).strftime("%Y-%m-%d %H:%M")},
        ])

    def test_die_nummer_kommt_aus_dem_register_und_nicht_aus_der_ueberschrift(self):
        """⚠⚠ Der Kern: die Agenda sagt „Sprint 99", das Register sagt 21."""
        self._register_um_den_commit(21)
        daten = session.stand(self.root)
        self.assertIn("Sprint 99", AGENDA)               # der Köder steht wirklich da
        # ⚠ `.get` und nicht `[...]`: gegen einen Altstand ohne das Feld soll hier eine
        # AUSSAGE stehen („None statt 21") und kein KeyError. Ein Nachweis, der gegen den
        # Vorzustand nur mit einer Ausnahme stirbt, belegt die Anforderung nicht —
        # L-2026-08-16h Regel 3, in dieser Organisation schon einmal teuer bezahlt.
        self.assertEqual(daten.get("sprint_nr"), 21)     # und wird nicht gelesen

    def test_ohne_register_keine_geratene_nummer(self):
        daten = session.stand(self.root)
        self.assertIsNone(daten.get("sprint_nr", "FEHLT"))

    def test_nummer_und_zeitstempel_haengen_an_derselben_eingabe(self):
        """Beide kommen aus `letzter` — sie können nicht auseinanderlaufen."""
        self._register_um_den_commit(7)
        daten = session.stand(self.root)
        self.assertEqual(daten["stand"], self.commit_zeit)
        self.assertEqual(daten.get("sprint_nr"), 7)

    def test_kein_git_repo_liefert_keine_nummer_statt_ausnahme(self):
        leer = tempfile.mkdtemp(prefix="ohne-git-")
        self.addCleanup(shutil.rmtree, leer, ignore_errors=True)
        os.makedirs(os.path.join(leer, "pm", "management"))
        daten = session.stand(leer)
        self.assertIsNone(daten.get("sprint_nr", "FEHLT"))


class EndpunktTest(unittest.TestCase):
    """SWR-153 über den echten Abrufweg — nicht über den Import."""

    def setUp(self):
        import threading
        from backend import server
        self.root = tempfile.mkdtemp(prefix="sessionnummer-http-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        repo = os.path.join(self.root, "pm")
        os.makedirs(os.path.join(repo, "management"))
        with open(os.path.join(repo, "management", "session-agenda.md"),
                  "w", encoding="utf-8", newline="\n") as f:
            f.write(AGENDA)
        _git(repo, "init", "-b", "main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "Agenda")
        a = datetime.fromisoformat(session._commit_zeiten(self.root)[0]).replace(tzinfo=None)
        _register(self.root, [{"nr": 42, "kennung": "x",
                               "start": a.replace(second=0).strftime("%Y-%m-%d %H:%M")}])
        server.Api.protokoll = lambda *a, **k: None
        self.srv = server.start(self.root, port=0)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)

    def test_endpunkt_traegt_die_sprintnummer(self):
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:%d/api/session" % self.port) as r:
            daten = json.loads(r.read().decode("utf-8"))
        self.assertEqual(daten.get("sprint_nr"), 42,
                         "der Endpunkt liefert die Sprintnummer nicht")


if __name__ == "__main__":
    unittest.main()
