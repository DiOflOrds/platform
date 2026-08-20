"""SWR-162: die Übergangsprüfung sieht auch die Projekte im Sammel-Repo.

⚠⚠ **Der Befund ist ein blinder Fleck der Prüfung selbst, und er hat drei Sprints
gehalten.** `uebergang_historie` war auf **zwei** Wegen blind für `projects` (p10, p11,
p12), und beide Wege sahen für sich harmlos aus:

1. `pruefe_alle` übersprang jedes Projekt ohne eigenes `.git` — obwohl der Kommentar
   danebenstand, dass dann *das Sammel-Repo zählt*.
2. `status_wechsel` filterte `git log -- tickets/` **relativ zur Repo-Wurzel**; im
   Sammel-Repo liegen die Tickets eine Ebene tiefer.

**66 Statuswechsel sind seit SWR-118 nie geprüft worden.** Darin: vier Altfälle und ein
neuer — der Buchungsfehler DIESES Laufs.

> **Ein Kommentar, der beschreibt, was der Code tun soll, ist keine Zusicherung. Hier hat
> er drei Sprints lang das Gegenteil dessen behauptet, was danebenstand.**
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import uebergang_historie as uh  # noqa: E402

WURZEL = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class SammelRepoTest(unittest.TestCase):
    """SWR-162: verschachtelte Projekte werden gefunden, gleich wie tief sie liegen."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.repo = os.path.join(self.root, "sammel")
        self.projekt = os.path.join(self.repo, "px", "tickets")
        os.makedirs(self.projekt)
        for arg in (["init", "-q", "-b", "main"],
                    ["config", "user.email", "team@aspice.local"],
                    ["config", "user.name", "ASPICE-Team"]):
            subprocess.run(["git", "-C", self.repo] + arg, capture_output=True)

    def _ticket(self, status):
        pfad = os.path.join(self.projekt, "T-0001.md")
        open(pfad, "w", encoding="utf-8", newline="\n").write(
            "---\nid: T-0001\ntitel: \"x\"\ntyp: task\nprozess: swe3\nrolle: dev\n"
            f"sprint: 0\nstatus: {status}\nprio: mittel\nerstellt: 2026-08-20\n---\n")
        subprocess.run(["git", "-C", self.repo, "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", self.repo, "commit", "-q", "-m", status],
                       capture_output=True,
                       env=dict(os.environ, GIT_AUTHOR_NAME="ASPICE-Team",
                                GIT_COMMITTER_NAME="ASPICE-Team",
                                GIT_AUTHOR_EMAIL="team@aspice.local",
                                GIT_COMMITTER_EMAIL="team@aspice.local"))

    def test_ein_verstoss_EINE_ebene_tiefer_wird_gefunden(self):
        """⚠ Der Fall, der drei Sprints lang unsichtbar war — nachgestellt, nicht beschrieben."""
        self._ticket("open")
        self._ticket("done")
        wechsel = uh.status_wechsel(self.repo)
        self.assertEqual([(w[2], w[3], w[4]) for w in wechsel],
                         [("px/tickets/T-0001.md", "open", "done")])

    def test_ein_kommentar_ist_keine_zusicherung(self):
        """⚠⚠ `_repo_wurzel` findet das Repo über dem Projekt — was der Kommentar versprach.

        Vorher stand dort `basis if os.path.isdir(basis/.git) else None`, gefolgt von
        `continue`. Der Kommentar sagte das Gegenteil.
        """
        projektpfad = os.path.join(self.repo, "px")
        self.assertIsNone(os.path.isdir(os.path.join(projektpfad, ".git")) or None,
                          "Vorbedingung: das Projekt hat KEIN eigenes .git")
        self.assertEqual(uh._repo_wurzel(projektpfad, self.root),
                         os.path.abspath(self.repo))

    def test_die_suche_nach_oben_endet_an_der_wurzel(self):
        """⚠ Sonst fände die Prüfung das Repo, in dem der Bestand zufällig liegt.

        Ein Werkzeug, das über seine Wurzel hinausgreift, behauptet Zuständigkeit für
        fremde Historie — und meldet Befunde über Tickets, die niemandem hier gehören.
        """
        ohne = os.path.join(self.root, "ohne_git", "tief")
        os.makedirs(ohne)
        self.assertIsNone(uh._repo_wurzel(ohne, self.root))

    def test_nur_ticketdateien_zaehlen(self):
        """Die Gegenprobe zum entfernten Pfadfilter.

        Ohne `-- tickets/` liest `git log` **alles**; die Auswahl liegt jetzt am
        Dateinamen. Eine Datei mit `status:` irgendwo sonst im Repo darf kein
        Statuswechsel sein.
        """
        self._ticket("open")
        fremd = os.path.join(self.repo, "notizen.md")
        open(fremd, "w", encoding="utf-8").write("status: open\n")
        subprocess.run(["git", "-C", self.repo, "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", self.repo, "commit", "-q", "-m", "notiz"],
                       capture_output=True)
        open(fremd, "w", encoding="utf-8").write("status: done\n")
        subprocess.run(["git", "-C", self.repo, "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", self.repo, "commit", "-q", "-m", "notiz2"],
                       capture_output=True)
        self.assertEqual([w[2] for w in uh.status_wechsel(self.repo)], [])


class BestandNachDerReparaturTest(unittest.TestCase):
    """SWR-162 am echten Bestand — als Schranke, nicht als Momentaufnahme (SWR-157)."""

    def test_das_sammelrepo_wird_ueberhaupt_geprueft(self):
        """⚠⚠ Die Zusicherung, die den blinden Fleck künftig meldet.

        Sie hält **nicht** eine Zahl fest, sondern die Tatsache, dass Statuswechsel aus
        `projects/` überhaupt gesehen werden. Wäre sie eine Zahl, wäre sie beim nächsten
        Ticket rot und würde hochgezählt statt gelesen (SWR-157).
        """
        wechsel = uh.status_wechsel(os.path.join(WURZEL, "projects"))
        if not os.path.isdir(os.path.join(WURZEL, "projects", ".git")):
            self.skipTest("kein Sammel-Repo in dieser Umgebung")
        self.assertGreaterEqual(len(wechsel), 60,
                                "die Prüfung sah hier drei Sprints lang NULL Wechsel")
        self.assertTrue(any(w[2].startswith("p1") for w in wechsel))

    def test_der_altbestand_stimmt_mit_der_festgenagelten_zahl_ueberein(self):
        """⚠ `ALTBESTAND_ERWARTET` ist in diesem Lauf von 52 auf 56 gestiegen.

        Nicht weil Historie umgeschrieben wurde, sondern weil vier Altfälle **sichtbar**
        geworden sind. Genau dafür ist die Zahl da: sie zwingt jede Änderung am
        Prüfumfang, sich zu erklären.
        """
        if not os.path.exists(os.path.join(WURZEL, uh.BESTANDSMARKE)):
            self.skipTest("nicht dieser Bestand")
        _neue, _weiter, alt, register = uh.pruefe_alle(WURZEL)  # SWR-166: vier Werte
        self.assertEqual(len(alt), uh.ALTBESTAND_ERWARTET)
        self.assertEqual(register, [])


if __name__ == "__main__":
    unittest.main()
