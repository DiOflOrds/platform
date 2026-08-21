"""Der Baum ist die Arbeit, der Index ist ein Zwischenspeicher (SWR-191, platform/T-0046).

⚠⚠ **Die Gegenprobe ist der Grund für diese Datei.** Eine Prüfung, die nur zeigt, dass
`repo_status` auf einem sauberen Repo nichts meldet, wäre auch mit dem alten Code grün
gewesen — sie hätte den Fehler nicht gesehen, den sie verhindern soll. Deshalb baut
`_repo_mit_veraltetem_index` den Schadensfall aus Sprint 28 **nach**: ein Index, der auf
dem Stand VOR dem letzten Commit steht, während der Baum mit `HEAD` byte-identisch ist.

⚠ Gebaut wird an einem **synthetischen** Repo unter `tempfile` und ausdrücklich nicht an
den 17 Live-Repos dieses Hauses (`L-2026-08-20cm`): an denen greift der Schnelltakt des
Auftraggebers alle 15 Minuten, und eine Prüfung, die dort mutiert, prüft nicht nur sich
selbst, sondern beschädigt einen fremden Lauf.

Ausführung: python -m unittest discover platform/tests
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
sys.path.insert(0, os.path.join(_HIER, ".."))
import preflight  # noqa: E402


def _git(repo, *args, index=None):
    umgebung = dict(os.environ, GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@t",
                    GIT_COMMITTER_NAME="T", GIT_COMMITTER_EMAIL="t@t")
    if index:
        umgebung["GIT_INDEX_FILE"] = index
    return subprocess.run(["git", "-C", repo] + list(args), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", env=umgebung)


class BaumStattIndexTest(unittest.TestCase):
    """Verifiziert: SWR-191."""

    def setUp(self):
        self.wurzel = tempfile.mkdtemp(prefix="swr191-")
        self.repo = os.path.join(self.wurzel, "repo")
        os.makedirs(self.repo)
        _git(self.repo, "init", "-q", ".")
        _git(self.repo, "config", "user.email", "t@t")
        _git(self.repo, "config", "user.name", "T")
        self.datei = os.path.join(self.repo, "akte.md")
        with open(self.datei, "w", encoding="utf-8") as f:
            f.write("stand eins\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "eins")

    def tearDown(self):
        shutil.rmtree(self.wurzel, ignore_errors=True)

    def _veralteter_index(self):
        """Den Schadensfall aus Sprint 28 nachbauen: Index alt, Baum == HEAD.

        Der Weg ist derselbe, den eine nicht entfernbare `index.lock` erzwingt — nur
        ohne Sperre, weil eine Sperre auf diesem Mount nicht wieder wegginge und der
        Test damit seinen eigenen Aufräumer verlöre. Gemessen wird die **Wirkung**
        (Index != HEAD, Baum == HEAD) und nicht ihre Ursache; genau darauf antwortet
        `repo_status`.
        """
        alt = os.path.join(self.repo, ".git", "index")
        sicherung = os.path.join(self.wurzel, "index.alt")
        shutil.copyfile(alt, sicherung)          # Index auf dem Stand von Commit 1
        with open(self.datei, "w", encoding="utf-8") as f:
            f.write("stand zwei\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "zwei")  # HEAD und Baum tragen "stand zwei"
        shutil.copyfile(sicherung, alt)           # Index zurück auf Commit 1: veraltet

    def test_gegenprobe_veralteter_index_meldet_schmutzig_der_baum_nicht(self):
        """⚠⚠ DIE EIGENTLICHE PRUEFUNG: ohne sie waere der alte Code auch gruen.

        Der reale Index behauptet eine Aenderung, die es nicht gibt; der Baum sagt die
        Wahrheit. Beide Haelften stehen hier, weil eine allein nichts zeigt: „Baum ist
        sauber" ist ohne „Index sagt schmutzig" keine Aussage ueber den Fehler.
        """
        self._veralteter_index()
        roh = _git(self.repo, "status", "--porcelain", "-uall").stdout.strip()
        self.assertTrue(roh, "Vorbedingung verfehlt: der reale Index muesste hier "
                             "eine Aenderung behaupten — sonst prueft der Rest nichts")
        dirty, _tracking = preflight.repo_status(self.repo)
        self.assertEqual(dirty, [], f"Der Baum ist mit HEAD identisch, gemeldet wurde: "
                                    f"{dirty} (roher Status: {roh!r})")

    def test_echte_aenderung_wird_weiterhin_gemeldet(self):
        """Nulllage in der anderen Richtung: die Reparatur darf nicht blind machen."""
        with open(self.datei, "w", encoding="utf-8") as f:
            f.write("wirklich geaendert\n")
        dirty, _ = preflight.repo_status(self.repo)
        self.assertTrue(any("akte.md" in z for z in dirty),
                        f"eine echte Aenderung fehlt in {dirty}")

    def test_neue_datei_in_neuem_ordner_bleibt_sichtbar(self):
        """SWR-110 darf durch SWR-191 nicht verlorengehen (`-uall`)."""
        os.makedirs(os.path.join(self.repo, "tickets"))
        with open(os.path.join(self.repo, "tickets", "T-0001.md"), "w",
                  encoding="utf-8") as f:
            f.write("neu\n")
        dirty, _ = preflight.repo_status(self.repo)
        self.assertTrue(any("tickets/T-0001.md" in z.replace("\\", "/") for z in dirty),
                        f"-uall verloren: {dirty}")

    def test_tracking_zeile_bleibt_erhalten(self):
        """`-b`: der Aufrufer druckt sie, ein leerer Wert waere eine stille Regression."""
        _dirty, tracking = preflight.repo_status(self.repo)
        self.assertTrue(tracking.startswith("##"), f"Tracking-Zeile fehlt: {tracking!r}")

    def test_temp_index_liegt_ausserhalb_des_repos_und_bleibt_nicht_liegen(self):
        """⚠ Sonst fuettert die Reparatur genau den Parkplatz, der sie noetig macht."""
        vorher = set(os.listdir(os.path.join(self.repo, ".git")))
        preflight.repo_status(self.repo)
        nachher = set(os.listdir(os.path.join(self.repo, ".git")))
        self.assertEqual(nachher - vorher, set(),
                         "repo_status hat ein Artefakt in .git/ hinterlassen")

    def test_repo_ohne_commit_faellt_zurueck_statt_zu_werfen(self):
        """Seeding scheitert ohne HEAD — die Auskunft aus dem Index ist besser als keine."""
        leer = os.path.join(self.wurzel, "leer")
        os.makedirs(leer)
        _git(leer, "init", "-q", ".")
        with open(os.path.join(leer, "x.md"), "w", encoding="utf-8") as f:
            f.write("x\n")
        dirty, _tracking = preflight.repo_status(leer)  # wirft nicht
        self.assertTrue(any("x.md" in z for z in dirty), f"Rueckfall stumm: {dirty}")


class IndexGesperrtTest(unittest.TestCase):
    """Verifiziert: SWR-191 — der veraltete Index ist eine EIGENE Meldung, kein Befund."""

    def setUp(self):
        self.wurzel = tempfile.mkdtemp(prefix="swr191-lock-")
        self.repo = os.path.join(self.wurzel, "repo")
        os.makedirs(os.path.join(self.repo, ".git"))

    def tearDown(self):
        shutil.rmtree(self.wurzel, ignore_errors=True)

    def test_ohne_sperre_falsch_mit_sperre_wahr(self):
        self.assertFalse(preflight.index_gesperrt(self.repo))
        with open(os.path.join(self.repo, ".git", "index.lock"), "w") as f:
            f.write("")
        self.assertTrue(preflight.index_gesperrt(self.repo))

    def test_die_meldung_zaehlt_keinen_befund(self):
        """⚠⚠ SWR-166 nicht ein zweites Mal bauen — diesmal wissentlich.

        Gemessen wird der QUELLTEXT und nicht das Verhalten: ein Lauf des ganzen
        Preflight ueber 17 Repos in einem Unit-Test waere Minuten teuer und haenge an
        einem Bestand, den dieser Test nicht kontrolliert. Gefragt ist, ob im
        Hinweis-Zweig der Zaehler angefasst wird — das ist am Text entscheidbar.
        """
        pfad = os.path.join(_HIER, "..", "scripts", "preflight.py")
        with open(pfad, encoding="utf-8") as f:
            quelle = f.read()
        marke = "if index_gesperrt(repo):"
        self.assertIn(marke, quelle, "Der Hinweis-Zweig fehlt")
        zweig = quelle.split(marke, 1)[1].split("if dirty:", 1)[0]
        self.assertNotIn("befunde", zweig,
                         "Der Hinweis zaehlt einen Befund — das ist SWR-166 ein "
                         "zweites Mal, und der Aufrufer kann in der Sandbox nichts "
                         "dagegen tun")


class EinImplementierungTest(unittest.TestCase):
    """Verifiziert: SWR-191 — tick haelt keine zweite Kopie derselben Logik (B033)."""

    def test_tick_ruft_preflight_repo_status_und_nicht_git_status(self):
        pfad = os.path.join(_HIER, "..", "orchestrator", "tick.py")
        with open(pfad, encoding="utf-8") as f:
            quelle = f.read()
        koerper = quelle.split("def arbeitskopie_sauber(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("preflight_mod.repo_status", koerper,
                      "arbeitskopie_sauber liest nicht ueber preflight.repo_status")
        self.assertNotIn('"status", "--porcelain"', koerper,
                         "zweite Kopie der Statuslogik in tick.py (B033)")


if __name__ == "__main__":
    unittest.main()
