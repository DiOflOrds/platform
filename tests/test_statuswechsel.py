"""Ein Zustandswechsel ist EIN Vorgang (SWR-139, platform/T-0017).

**Der Anlass ist ein Befund eines Laufs über sich selbst.** In Sprint 15 ist derselbe
Fehler **zweimal** eingetreten und einmal committet worden:

| Fall | Ticket | Ausgang |
|---|---|---|
| 1 | `platform/T-0013` | `in_review`-Commit abgewiesen, `done` stand schon in der Datei. **Vor** dem Commit bemerkt. |
| 2 | `pm/T-0052` | Derselbe Ablauf, diesmal **committet**: `in_progress -> done` steht in der Historie. |

> **Es ist beim ersten Mal gut ausgegangen, weil jemand hingesehen hat — nicht, weil eine
> Vorkehrung gegriffen hätte.**

⚠ **Die Gegenprobe ist die wichtigere Hälfte dieser Datei.** Ein Wechsel, der die Datei
ändert und den Fehler *nur meldet*, ist genau der Zustand, gegen den SWR-139 existiert —
`test_gescheiterte_buchung_laesst_datei_unveraendert` ist deshalb die schärfste
Zusicherung hier und prüft **Ticketdatei und BOARD.md byteweise**.

Ausführung: python -m unittest discover platform/tests
"""
import os
import subprocess
import sys
import tempfile
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
import board  # noqa: E402

TICKET = """---
id: {tid}
titel: "Testticket"
typ: task
prozess: sup8
rolle: cm
sprint: 1
status: {status}
prio: hoch
reviewer: qm
blocked_by: []
erstellt: 2026-08-17
---

Body.
"""


class StatuswechselTest(unittest.TestCase):
    """Verifiziert: SWR-139."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.join(self.tmp.name, "repo")
        os.makedirs(os.path.join(self.repo, "tickets"))
        subprocess.run(["git", "-C", self.repo, "init", "-q", "-b", "main"],
                       capture_output=True)

    def tearDown(self):
        self.tmp.cleanup()

    # -- Hilfen ---------------------------------------------------------------

    def _ticket(self, tid="T-0001", status="open"):
        pfad = os.path.join(self.repo, "tickets", f"{tid}.md")
        with open(pfad, "w", encoding="utf-8", newline="\n") as f:
            f.write(TICKET.format(tid=tid, status=status))
        return pfad

    def _git(self, *args):
        return subprocess.run(["git", "-C", self.repo] + list(args),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")

    def _commit_alles(self, meldung="init"):
        self._git("add", "-A")
        self._git("-c", "user.name=T", "-c", "user.email=t@t", "commit", "-q",
                  "-m", meldung)

    def _commits(self):
        p = self._git("rev-list", "--count", "HEAD")
        return int((p.stdout or "0").strip() or 0)

    def _bytes(self, *teile):
        pfad = os.path.join(self.repo, *teile)
        if not os.path.exists(pfad):
            return None
        return open(pfad, "rb").read()

    # -- DoD 1: ein Vorgang ---------------------------------------------------

    def test_wechsel_mit_meldung_schreibt_und_bucht(self):
        """Ein Wechsel mit Meldung erzeugt GENAU EINEN Commit. Verifiziert: SWR-139."""
        self._ticket()
        self._commit_alles()
        vorher = self._commits()
        board.setze_status(self.repo, "T-0001", "in_progress",
                           meldung="T-0001 -> in_progress")
        self.assertEqual(self._commits(), vorher + 1)
        self.assertIn("status: in_progress", self._bytes("tickets", "T-0001.md").decode())
        # und der Stand ist GEBUCHT, nicht nur geschrieben
        p = self._git("status", "--porcelain")
        self.assertEqual(p.stdout.strip(), "")

    def test_zwei_wechsel_zwei_commits(self):
        """Zwei Wechsel hintereinander = ZWEI Commits, keine uebersprungene Stufe.

        Das ist die Zusicherung gegen den Schadensfall selbst: `pm/T-0052` hat
        `in_progress -> done` in der Historie, weil die Zwischenstufe nie gebucht wurde.
        Verifiziert: SWR-139."""
        self._ticket()
        self._commit_alles()
        vorher = self._commits()
        board.setze_status(self.repo, "T-0001", "in_progress", meldung="a")
        board.setze_status(self.repo, "T-0001", "in_review", reviewer="qm", meldung="b")
        self.assertEqual(self._commits(), vorher + 2)
        log = self._git("log", "--format=%s", "-2").stdout.split("\n")
        self.assertEqual([z for z in log if z][:2], ["b", "a"])

    def test_ohne_meldung_wird_nicht_gebucht(self):
        """Ein Aufruf OHNE Meldung bucht nichts — die bestehenden Aufrufer (Tick,
        feedback_route) schreiben mitten in ihrer eigenen Transaktion und duerfen davon
        nicht ueberrascht werden. Verifiziert: SWR-139."""
        self._ticket()
        self._commit_alles()
        vorher = self._commits()
        board.setze_status(self.repo, "T-0001", "in_progress")
        self.assertEqual(self._commits(), vorher)
        self.assertIn("status: in_progress", self._bytes("tickets", "T-0001.md").decode())

    # -- DoD 2: die Gegenprobe (die wichtigere Haelfte) ------------------------

    def test_gescheiterte_buchung_laesst_datei_unveraendert(self):
        """⚠ DIE Zusicherung dieses Tickets: scheitert die Buchung, ist der Wechsel NICHT
        GESCHEHEN — Ticketdatei UND BOARD.md byteweise wie vorher, und der Fehler wird
        GEWORFEN statt gemeldet.

        Ein Wechsel, der die Datei aendert und den Fehler nur meldet, ist der Zustand,
        gegen den SWR-139 existiert. Verifiziert: SWR-139."""
        self._ticket()
        self._commit_alles()
        board.setze_status(self.repo, "T-0001", "in_progress", meldung="a")
        vorher_ticket = self._bytes("tickets", "T-0001.md")
        vorher_board = self._bytes("BOARD.md")
        vorher_commits = self._commits()

        def bucht_nie(repo, pfade, meldung, identitaet=None, entsperren=None):
            class R:
                ok = False
                stderr = "fatal: Unable to create '.git/index.lock': File exists"
                stdout = ""
                geraeumt = 0
            return R()

        with self.assertRaises(ValueError) as ctx:
            board.setze_status(self.repo, "T-0001", "in_review", reviewer="qm",
                               meldung="b", _verbuche=bucht_nie)
        self.assertIn("index.lock", str(ctx.exception))
        self.assertEqual(self._bytes("tickets", "T-0001.md"), vorher_ticket)
        self.assertEqual(self._bytes("BOARD.md"), vorher_board)
        self.assertEqual(self._commits(), vorher_commits)

    def test_gescheiterte_buchung_stellt_auch_neu_erzeugtes_board_zurueck(self):
        """Gab es vorher KEINE BOARD.md, darf danach auch keine dastehen — sonst
        haette der gescheiterte Wechsel doch eine Spur hinterlassen.
        Verifiziert: SWR-139."""
        self._ticket()
        self._commit_alles()
        self.assertIsNone(self._bytes("BOARD.md"))

        def bucht_nie(repo, pfade, meldung, identitaet=None, entsperren=None):
            class R:
                ok, stderr, stdout, geraeumt = False, "kaputt", "", 0
            return R()

        with self.assertRaises(ValueError):
            board.setze_status(self.repo, "T-0001", "in_progress", meldung="a",
                               _verbuche=bucht_nie)
        self.assertIsNone(self._bytes("BOARD.md"))

    # -- DoD 3: kein zweiter Wechsel auf einem unverbuchten --------------------

    def test_unverbuchter_stand_wird_abgelehnt(self):
        """Weicht die Arbeitskopie von HEAD ab, verweigert der naechste Wechsel — und
        die Meldung NENNT den unverbuchten Stand (B038). Verifiziert: SWR-139."""
        self._ticket()
        self._commit_alles()
        # Wechsel OHNE Buchung — genau die Lage aus dem Schadensfall
        board.setze_status(self.repo, "T-0001", "in_progress")
        with self.assertRaises(ValueError) as ctx:
            board.setze_status(self.repo, "T-0001", "in_review", reviewer="qm",
                               meldung="b")
        meldung = str(ctx.exception)
        self.assertIn("in_progress", meldung)   # der unverbuchte Stand, beim Namen
        self.assertIn("open", meldung)          # und der Stand in HEAD

    def test_neues_ticket_ohne_head_ist_kein_befund(self):
        """Ein Ticket, das es in HEAD NOCH NICHT gibt, ist kein unverbuchter Stand —
        sonst waere Anlegen und Bewegen in einem Lauf unmoeglich.
        Verifiziert: SWR-139."""
        self._ticket("T-0001")
        self._commit_alles()
        self._ticket("T-0002")          # neu, nie committet
        board.setze_status(self.repo, "T-0002", "in_progress", meldung="neu")
        self.assertIn("status: in_progress", self._bytes("tickets", "T-0002.md").decode())

    def test_pruefung_ist_fuer_den_transaktions_aufrufer_abwaehlbar(self):
        """Der Orchestrator-Tick schreibt drei Staende innerhalb EINES Branches und ist
        selbst mitten in einer Transaktion — fuer ihn ist die HEAD-Pruefung abwaehlbar.
        Verifiziert: SWR-139."""
        self._ticket()
        self._commit_alles()
        board.setze_status(self.repo, "T-0001", "in_progress")
        board.setze_status(self.repo, "T-0001", "in_review", reviewer="qm",
                           head_pruefen=False)
        self.assertIn("status: in_review", self._bytes("tickets", "T-0001.md").decode())

    def test_unveraendertes_ticket_passiert(self):
        """Gegenprobe zur Pruefung: ist die Arbeitskopie gleich HEAD, laeuft der Wechsel
        durch — die Pruefung darf nicht der neue Dauerbefund werden.
        Verifiziert: SWR-139."""
        self._ticket()
        self._commit_alles()
        board.setze_status(self.repo, "T-0001", "in_progress", meldung="a")
        board.setze_status(self.repo, "T-0001", "in_review", reviewer="qm", meldung="b")
        self.assertIn("status: in_review", self._bytes("tickets", "T-0001.md").decode())


class UnverbuchtBefundTest(unittest.TestCase):
    """Der Preflight meldet unverbuchte STATUS-Staende als eigenen Befund.

    SWR-110 liest die Arbeitskopie schon; was fehlte, ist die Zuspitzung auf `status` —
    und nach SWR-122 entscheidet, wer eine Pruefung baut, im selben Zug ueber ihren Leser.
    Verifiziert: SWR-139."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.join(self.tmp.name, "repo")
        os.makedirs(os.path.join(self.repo, "tickets"))
        subprocess.run(["git", "-C", self.repo, "init", "-q", "-b", "main"],
                       capture_output=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _ticket(self, tid="T-0001", status="open"):
        with open(os.path.join(self.repo, "tickets", f"{tid}.md"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(TICKET.format(tid=tid, status=status))

    def _commit_alles(self):
        subprocess.run(["git", "-C", self.repo, "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", self.repo, "-c", "user.name=T",
                        "-c", "user.email=t@t", "commit", "-q", "-m", "init"],
                       capture_output=True)

    def test_kein_befund_ohne_abweichung(self):
        """Nulllage: keine Abweichung, kein Befund. Verifiziert: SWR-139."""
        self._ticket()
        self._commit_alles()
        self.assertEqual(board.unverbuchte_status(self.repo), [])

    def test_befund_nennt_ticket_und_beide_staende(self):
        """Der Befund nennt Ticket, Stand in der Datei und Stand in HEAD — eine Meldung,
        die nur 'irgendwas weicht ab' sagt, verschiebt das Raetsel nur.
        Verifiziert: SWR-139."""
        self._ticket()
        self._commit_alles()
        board.setze_status(self.repo, "T-0001", "in_progress")
        befunde = board.unverbuchte_status(self.repo)
        self.assertEqual(len(befunde), 1)
        text = befunde[0]
        self.assertIn("T-0001", text)
        self.assertIn("in_progress", text)
        self.assertIn("open", text)

    def test_geaenderter_body_ohne_statuswechsel_ist_kein_befund(self):
        """⚠ Die Zuspitzung auf `status` ist der Punkt: wer waehrend der Arbeit den
        Tickettext ergaenzt, hat KEINEN verlorenen Zustand — ein Befund dafuer waere
        der Dauerbefund, der das Wegsehen antrainiert (die Falle aus SWR-131).
        Verifiziert: SWR-139."""
        self._ticket()
        self._commit_alles()
        pfad = os.path.join(self.repo, "tickets", "T-0001.md")
        with open(pfad, "a", encoding="utf-8", newline="\n") as f:
            f.write("\nNachtrag waehrend der Arbeit.\n")
        self.assertEqual(board.unverbuchte_status(self.repo), [])

    def test_preflight_liest_den_befund(self):
        """⚠ Nach SWR-122 entscheidet, wer eine Pruefung baut, im selben Zug ueber ihren
        LESER — sonst entsteht die naechste Gestalt der Familie: eine Pruefung, die
        niemand liest. Zugesichert am **Syntaxbaum** des Preflights und nicht an einer
        Zusage im Kommentar. Verifiziert: SWR-139."""
        import ast
        pfad = os.path.join(_HIER, "..", "scripts", "preflight.py")
        baum = ast.parse(open(pfad, encoding="utf-8").read())
        aufrufe = [k for k in ast.walk(baum)
                   if isinstance(k, ast.Attribute) and k.attr == "unverbuchte_status"]
        self.assertTrue(aufrufe, "preflight liest unverbuchte_status nicht")

    def test_status_in_head_ist_genau_einmal_definiert(self):
        """⚠⚠ Beinahe-Vorfall beim Bau von SWR-139, hier festgehalten statt erzaehlt.

        Der erste Entwurf schrieb eine **zweite** `status_in_head` unter demselben Namen;
        Python meldet das nicht, die spaetere Definition gewinnt lautlos. Die vorhandene
        Fassung kann drei Dinge, die die neue nicht konnte — den Monorepo-Praefix
        `p11/tickets/…` (platform/T-0008), das ausdrueckliche UTF-8 (platform/T-0007)
        und die Unterscheidung von `None` (neu) und `UNLESBAR` (Lesefehler). Gefunden hat
        es kein Nachdenken, sondern `test_board.VerschachteltesRepoUebergangTest`.

        > **Eine zweite Antwort auf dieselbe Frage muss nicht widersprechen, um zu
        > schaden — es genuegt, dass sie weniger weiss als die erste.**

        Zugesichert am **Syntaxbaum**, weil ein Vorsatz die naechste Fassung nicht haelt.
        Verifiziert: SWR-139."""
        import ast
        pfad = os.path.join(_HIER, "..", "scripts", "board.py")
        baum = ast.parse(open(pfad, encoding="utf-8").read())
        defs = [k for k in baum.body
                if isinstance(k, ast.FunctionDef) and k.name == "status_in_head"]
        self.assertEqual(len(defs), 1,
                         f"status_in_head {len(defs)}-mal definiert — die spaetere "
                         f"ueberschreibt die fruehere lautlos")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
