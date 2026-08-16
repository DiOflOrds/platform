"""Unit-Verifikation ci_status.py (SWR-105, platform/T-0003).

**Ehrlich zur Reichweite dieser Datei:** die Cowork-Sandbox hat keinen GitHub-Zugang
(Guardrail 2). JEDER Test hier injiziert die Abruffunktion. Damit ist die
**Auswertung** belegt — SHA-Vergleich, Zustandslogik, Budget, Exit-Code — und die
**Abfrage** nicht. Der Nachweis für den Netzweg ist der erste Lauf am Host
(Stichprobe im Ticket). Das offen zu sagen ist B027; es als „getestet" zu führen
wäre B038.

Ausführung: python -m unittest discover platform/tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import ci_status  # noqa: E402

SHA = "a" * 40
FREMD = "b" * 40


def lauf(sha=SHA, status="completed", fazit="success", name="Board-Check"):
    return {"head_sha": sha, "status": status, "conclusion": fazit, "name": name,
            "html_url": f"https://github.com/DiOflOrds/x/actions/runs/1"}


def antwort(*laeufe):
    """Eine Abruffunktion, die immer dieselben Läufe liefert."""
    def holen(url, token=None):
        return {"workflow_runs": list(laeufe)}, None
    return holen


class SlugTest(unittest.TestCase):
    """Verifiziert: SWR-105."""

    def test_slug_aus_https_und_ssh(self):
        for url, erwartet in (
                ("https://github.com/DiOflOrds/p0.git", "DiOflOrds/p0"),
                ("https://github.com/DiOflOrds/p0", "DiOflOrds/p0"),
                ("https://github.com/DiOflOrds/p0/", "DiOflOrds/p0"),
                ("git@github.com:DiOflOrds/produkt-datakonv.git", "DiOflOrds/produkt-datakonv")):
            self.assertEqual(ci_status.remote_slug(url), erwartet, url)

    def test_fremder_oder_fehlender_remote_ist_kein_slug(self):
        """Ein Repo mit fremdem Remote ist kein Fehler — nur nichts, was diese
        Prüfung beantworten kann. Verifiziert: SWR-105."""
        for url in ("", None, "https://gitlab.com/x/y.git", "/pfad/zu/lokal.git"):
            self.assertIsNone(ci_status.remote_slug(url))


class BewertungTest(unittest.TestCase):
    """Die Kernregel der Anforderung. Verifiziert: SWR-105."""

    def test_gruen_nur_bei_passendem_commit(self):
        self.assertEqual(ci_status.bewerte(SHA, {"workflow_runs": [lauf()]})["zustand"], "gruen")

    def test_gruener_lauf_eines_fremden_commits_ist_kein_gruener_lauf(self):
        """DoD 2 des Tickets und der Grund, warum es das Skript gibt: die
        Actions-Seite zeigt zuerst die Farbe und erst danach den Commit. Ein
        grüner Lauf von gestern darf die Freigabe von heute nicht erteilen —
        dieselbe Vorsicht wie `session.stille`. Verifiziert: SWR-105."""
        e = ci_status.bewerte(SHA, {"workflow_runs": [lauf(sha=FREMD)]})
        self.assertEqual(e["zustand"], "kein_lauf")
        self.assertNotEqual(e["zustand"], "gruen")

    def test_leere_antwort_und_fehlender_commit(self):
        self.assertEqual(ci_status.bewerte(SHA, {})["zustand"], "kein_lauf")
        self.assertEqual(ci_status.bewerte(SHA, {"workflow_runs": []})["zustand"], "kein_lauf")
        self.assertEqual(ci_status.bewerte("", {"workflow_runs": [lauf(sha="")]})["zustand"],
                         "kein_lauf")

    def test_rot_traegt_fazit_und_lauf_adresse(self):
        e = ci_status.bewerte(SHA, {"workflow_runs": [lauf(fazit="failure")]})
        self.assertEqual(e["zustand"], "rot")
        self.assertEqual(e["fazit"], "failure")
        self.assertIn("actions/runs", e["url"])

    def test_laufend_ist_weder_gruen_noch_rot(self):
        for status in ("queued", "in_progress"):
            e = ci_status.bewerte(SHA, {"workflow_runs": [lauf(status=status, fazit=None)]})
            self.assertEqual(e["zustand"], "laeuft", status)

    def test_ein_rotes_von_mehreren_macht_rot(self):
        """Zwei Workflows auf demselben Commit: grün und rot ist rot, nicht grün.
        Verifiziert: SWR-105."""
        e = ci_status.bewerte(SHA, {"workflow_runs": [lauf(), lauf(fazit="failure", name="CI")]})
        self.assertEqual(e["zustand"], "rot")
        self.assertEqual(e["workflow"], "CI")

    def test_grossschreibung_der_sha_stoert_nicht(self):
        e = ci_status.bewerte(SHA.upper(), {"workflow_runs": [lauf(sha=SHA)]})
        self.assertEqual(e["zustand"], "gruen")


class RepoWelt(unittest.TestCase):
    """Eine kleine echte Git-Welt — Discovery und SHAs kommen aus git, nicht aus Attrappen."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wurzel = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def repo(self, name, remote="https://github.com/DiOflOrds/{n}.git", workflow=True):
        pfad = os.path.join(self.wurzel, name)
        os.makedirs(os.path.join(pfad, "tickets"), exist_ok=True)
        if workflow:
            wf = os.path.join(pfad, ".github", "workflows")
            os.makedirs(wf, exist_ok=True)
            open(os.path.join(wf, "board-check.yml"), "w").write("name: Board-Check\n")
        open(os.path.join(pfad, "README.md"), "w").write("x\n")
        subprocess.run(["git", "-C", pfad, "init", "-q", "-b", "main"], check=True)
        for k, v in (("user.name", "t"), ("user.email", "t@t")):
            subprocess.run(["git", "-C", pfad, "config", k, v], check=True)
        subprocess.run(["git", "-C", pfad, "add", "-A"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "-C", pfad, "commit", "-qm", "init"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if remote:
            subprocess.run(["git", "-C", pfad, "remote", "add", "origin",
                            remote.format(n=name)], check=True)
        return pfad

    def sha(self, name):
        return subprocess.run(["git", "-C", os.path.join(self.wurzel, name), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()


class DiscoveryTest(RepoWelt):
    """Verifiziert: SWR-105."""

    def test_nur_repos_mit_remote_und_workflow(self):
        self.repo("mit-beidem")
        self.repo("ohne-workflow", workflow=False)
        pruefen, ohne_remote = ci_status.zu_pruefen(self.wurzel)
        self.assertEqual([r["repo"] for r in pruefen], ["mit-beidem"])
        self.assertEqual(ohne_remote, [])

    def test_workflow_ohne_remote_wird_gemeldet_nicht_uebergangen(self):
        """`team-dashboard` trägt eine board-check.yml, hat aber keinen Remote — der
        Workflow ist damit nie gelaufen und wird nie laufen. Ihn stillschweigend zu
        überspringen hieße, „alles grün" auch über ein Repo zu sagen, das nie geprüft
        wurde. Ein Gate, das nur als Datei existiert, gehört sichtbar gemacht.
        Verifiziert: SWR-105."""
        self.repo("mit-remote")
        self.repo("nur-datei", remote=None)
        pruefen, ohne_remote = ci_status.zu_pruefen(self.wurzel)
        self.assertEqual([r["repo"] for r in pruefen], ["mit-remote"])
        self.assertEqual([r["repo"] for r in ohne_remote], ["nur-datei"])

    def test_der_lokale_commit_kommt_aus_git(self):
        self.repo("a")
        pruefen, _ = ci_status.zu_pruefen(self.wurzel)
        self.assertEqual(pruefen[0]["commit"], self.sha("a"))
        self.assertEqual(pruefen[0]["slug"], "DiOflOrds/a")


class PruefungTest(RepoWelt):
    """Verifiziert: SWR-105."""

    def test_alles_gruen_wenn_der_lauf_zum_commit_passt(self):
        self.repo("a")
        e = ci_status.pruefe(self.wurzel, holen=antwort(lauf(sha=self.sha("a"))),
                             warten=0, schlafen=lambda s: None)
        self.assertTrue(e["alles_gruen"])
        self.assertEqual(e["repos"][0]["zustand"], "gruen")
        self.assertEqual(e["abfragen"], 1)

    def test_fremder_gruener_lauf_macht_die_pruefung_nicht_gruen(self):
        """Die Regel aus BewertungTest, jetzt über den ganzen Weg. Verifiziert: SWR-105."""
        self.repo("a")
        e = ci_status.pruefe(self.wurzel, holen=antwort(lauf(sha=FREMD)),
                             warten=0, schlafen=lambda s: None)
        self.assertFalse(e["alles_gruen"])
        self.assertEqual(e["repos"][0]["zustand"], "kein_lauf")

    def test_repo_ohne_remote_zaehlt_nicht_gegen_gruen_steht_aber_im_bericht(self):
        """Verifiziert: SWR-105."""
        self.repo("a")
        self.repo("nur-datei", remote=None)
        e = ci_status.pruefe(self.wurzel, holen=antwort(lauf(sha=self.sha("a"))),
                             warten=0, schlafen=lambda s: None)
        self.assertTrue(e["alles_gruen"])
        zustaende = {r["repo"]: r["zustand"] for r in e["repos"]}
        self.assertEqual(zustaende["nur-datei"], "kein_ci")
        self.assertIn("kein CI zu erwarten", ci_status.bericht(e))

    def test_rate_limit_ist_ein_fehler_und_kein_kein_lauf(self):
        """Eine Grenze, die sich als Befund tarnt, wäre die stille Falschaussage aus
        B038: „noch kein Lauf" liest sich wie „gleich fertig", „Rate-Limit" wie das,
        was es ist. Verifiziert: SWR-105."""
        self.repo("a")

        def limit(url, token=None):
            return None, "Rate-Limit erschöpft (unangemeldet 60 Abfragen/Stunde)."

        e = ci_status.pruefe(self.wurzel, holen=limit, warten=0, schlafen=lambda s: None)
        self.assertEqual(e["repos"][0]["zustand"], "fehler")
        self.assertIn("Rate-Limit", e["repos"][0]["meldung"])
        self.assertFalse(e["alles_gruen"])

    def test_budget_stoppt_die_schleife_und_der_bericht_sagt_es(self):
        """Verifiziert: SWR-105."""
        for n in ("a", "b", "c"):
            self.repo(n)
        e = ci_status.pruefe(self.wurzel, holen=antwort(lauf(sha=FREMD)),
                             warten=600, budget=2, schlafen=lambda s: None)
        self.assertTrue(e["budget_erschoepft"])
        self.assertEqual(e["abfragen"], 0)  # 3 offene passen nicht in ein Budget von 2
        self.assertIn("Abfragebudget aufgebraucht", ci_status.bericht(e))

    def test_nur_offene_repos_werden_nachgefragt(self):
        """Die Bedingung dafür, dass 60 Abfragen je Stunde für einen Lauf reichen:
        ein grünes Repo wird in der zweiten Runde nicht erneut abgefragt.
        Verifiziert: SWR-105."""
        self.repo("a")
        self.repo("b")
        gefragt = []

        def holen(url, token=None):
            gefragt.append(url)
            sha = self.sha("a") if "DiOflOrds/a" in url else FREMD
            return {"workflow_runs": [lauf(sha=sha)]}, None

        # 41 Sekunden = eine Wartepause (40 s) und damit genau zwei Runden
        e = ci_status.pruefe(self.wurzel, holen=holen, warten=41, schlafen=lambda s: None)
        self.assertEqual(sum(1 for u in gefragt if "DiOflOrds/a" in u), 1)
        self.assertGreaterEqual(sum(1 for u in gefragt if "DiOflOrds/b" in u), 2)
        self.assertFalse(e["alles_gruen"])

    def test_laufende_pruefung_wird_nicht_als_fertig_gemeldet(self):
        self.repo("a")
        e = ci_status.pruefe(self.wurzel,
                             holen=antwort(lauf(sha=self.sha("a"), status="in_progress",
                                                fazit=None)),
                             warten=0, schlafen=lambda s: None)
        self.assertEqual(e["repos"][0]["zustand"], "laeuft")
        self.assertFalse(e["alles_gruen"])

    def test_ohne_jedes_pruefbare_repo_ist_nichts_gruen(self):
        """Eine leere Menge ist keine Zusage. Verifiziert: SWR-105."""
        self.repo("nur-datei", remote=None)
        e = ci_status.pruefe(self.wurzel, holen=antwort(), warten=0, schlafen=lambda s: None)
        self.assertFalse(e["alles_gruen"])


class AusgabeTest(RepoWelt):
    """Verifiziert: SWR-105."""

    def test_exit_code_und_dateien_ausserhalb_der_repos(self):
        """Der einzige Test, der den **echten** Netzweg anfasst — und er belegt genau
        das, was er belegen kann: **ohne Netz meldet das Skript einen Fehler und
        nichts anderes.** In dieser Sandbox gibt es keinen GitHub-Zugang; `main()`
        läuft hier also durch `hole_json` in einen Verbindungsfehler. Dass daraus
        `fehler` wird und **nicht** `kein_lauf` (das sich wie „gleich fertig" liest)
        und erst recht nicht `gruen`, ist die Aussage. Zusätzlich: der Bericht landet
        außerhalb der Repos — eine Prüfung, die den Zustand verändert, den sie prüft,
        ist keine. Verifiziert: SWR-105."""
        self.repo("a")
        ziel_json = os.path.join(self.wurzel, "CI-STATUS.json")
        ziel_md = os.path.join(self.wurzel, "CI-STATUS.md")
        code = ci_status.main(["--repos", self.wurzel, "--warten", "0",
                               "--json", ziel_json, "--md", ziel_md, "--leise"])
        self.assertEqual(code, 1)
        self.assertTrue(os.path.isfile(ziel_json) and os.path.isfile(ziel_md))
        d = json.load(open(ziel_json, encoding="utf-8"))
        self.assertEqual(d["repos"][0]["zustand"], "fehler")
        self.assertFalse(d["alles_gruen"])
        sauber = subprocess.run(["git", "-C", os.path.join(self.wurzel, "a"),
                                 "status", "--porcelain"], capture_output=True, text=True)
        self.assertEqual(sauber.stdout.strip(), "")

    def test_bericht_nennt_offene_repos_als_ungeprueft(self):
        """„Noch kein Lauf" darf sich nicht wie „in Ordnung" lesen. Verifiziert: SWR-105."""
        self.repo("a")
        e = ci_status.pruefe(self.wurzel, holen=antwort(lauf(sha=FREMD)),
                             warten=0, schlafen=lambda s: None,
                             jetzt=datetime(2026, 8, 17, 9, 0))
        text = ci_status.bericht(e)
        self.assertIn("2026-08-17 09:00", text)
        self.assertIn("NICHT vollständig grün", text)
        self.assertIn("heißt **nicht** in Ordnung", text)


if __name__ == "__main__":
    unittest.main()


# --------------------------------------------------------------------------------------
# SWR-107 (platform/T-0004): ein rotes Ergebnis nennt den fehlgeschlagenen Schritt.
#
# Anlass ist ein echter Befund: der erste Hostlauf von SWR-105 meldete p3, p5 und
# platform als rot. Für platform war die Ursache lokal nachstellbar, für p3/p5 nicht —
# und die naheliegende Erklärung (Board-Format, Push-Reihenfolge) wurde widerlegt.
# Was fehlte, war der Schritt. Er steht eine Abfrage entfernt.
#
# Reichweite wie oben: jede Abruffunktion ist injiziert. Belegt ist die Auswertung.
# --------------------------------------------------------------------------------------

def job(name="board", fazit="failure", schritte=()):
    return {"name": name, "conclusion": fazit,
            "steps": [{"name": n, "conclusion": c} for n, c in schritte]}


def zwei_antworten(laeufe, jobs, protokoll=None):
    """Eine Abruffunktion, die Läufe und Jobs auseinanderhält — und mitschreibt,
    welche Adressen überhaupt gefragt wurden. Ohne dieses Protokoll ließe sich
    „für grüne Repos wird nicht nachgefragt" nur behaupten."""
    def holen(url, token=None):
        if protokoll is not None:
            protokoll.append(url)
        if "/jobs" in url:
            return (jobs, None) if not isinstance(jobs, str) else (None, jobs)
        return {"workflow_runs": list(laeufe)}, None
    return holen


class FehlerschrittTest(unittest.TestCase):
    """Verifiziert: SWR-107."""

    def test_erster_fehlgeschlagener_schritt_des_fehlgeschlagenen_jobs(self):
        d = {"jobs": [job("ok-job", "success", [("a", "success")]),
                      job("board", "failure", [("Secret vorhanden?", "success"),
                                               ("BOARD.md aktuell?", "failure"),
                                               ("Aufräumen", "skipped")])]}
        self.assertEqual(ci_status.fehlerschritt(d),
                         {"job": "board", "schritt": "BOARD.md aktuell?",
                          "schritt_fazit": "failure", "weitere_jobs": 0})

    def test_uebersprungene_schritte_sind_kein_fehler(self):
        """`skipped` ist die Folge eines Fehlers, nicht der Fehler. Wer es als
        Befund liest, meldet den falschen Schritt. Verifiziert: SWR-107."""
        d = {"jobs": [job("board", "failure", [("erster", "failure"), ("zweiter", "skipped")])]}
        self.assertEqual(ci_status.fehlerschritt(d)["schritt"], "erster")

    def test_fehlgeschlagener_job_ohne_fehlgeschlagenen_schritt_faellt_auf_den_job_zurueck(self):
        """Kommt vor: der Job bricht ab, bevor ein Schritt ein Ergebnis hat. Dann ist
        der Jobname die beste verfügbare Antwort — und besser als keine.
        Verifiziert: SWR-107."""
        d = {"jobs": [job("board", "cancelled", [("a", "success")])]}
        self.assertEqual(ci_status.fehlerschritt(d),
                         {"job": "board", "schritt": "", "schritt_fazit": "cancelled",
                          "weitere_jobs": 0})

    def test_ohne_fehlgeschlagenen_job_keine_erfindung(self):
        """Lieber `None` als eine Diagnose, die nicht in der Antwort steht.
        Verifiziert: SWR-107."""
        self.assertIsNone(ci_status.fehlerschritt({"jobs": [job("a", "success")]}))
        self.assertIsNone(ci_status.fehlerschritt({"jobs": []}))
        self.assertIsNone(ci_status.fehlerschritt(None))


class DiagnoseTest(RepoWelt):
    """Verifiziert: SWR-107."""

    def rotlauf(self, sha, lauf_id=4711):
        r = lauf(sha=sha, fazit="failure")
        r["id"] = lauf_id
        return r

    def test_rotes_repo_nennt_job_und_schritt(self):
        self.repo("a")
        jobs = {"jobs": [job("board", "failure", [("Secret PLATFORM_READ_TOKEN vorhanden?",
                                                   "failure")])]}
        e = ci_status.pruefe(self.wurzel,
                             holen=zwei_antworten([self.rotlauf(self.sha("a"))], jobs),
                             warten=0, schlafen=lambda s: None)
        r = e["repos"][0]
        self.assertEqual(r["zustand"], "rot")
        self.assertEqual(r["schritt"], "Secret PLATFORM_READ_TOKEN vorhanden?")
        self.assertEqual(r["job"], "board")
        self.assertIn("Secret PLATFORM_READ_TOKEN vorhanden?", ci_status.bericht(e))

    def test_die_nachfrage_gilt_dem_roten_lauf_nicht_dem_ersten_der_liste(self):
        """Die Liste ist nach Datum sortiert; ganz oben kann ein grüner Lauf eines
        anderen Commits stehen. Dessen ID zu nehmen hieße, den falschen Lauf zu
        diagnostizieren — dieselbe Verwechslung wie bei DoD 2 von SWR-105, eine
        Ebene tiefer. Verifiziert: SWR-107."""
        self.repo("a")
        oben = lauf(sha=FREMD)
        oben["id"] = 1
        protokoll = []
        ci_status.pruefe(self.wurzel,
                         holen=zwei_antworten([oben, self.rotlauf(self.sha("a"), 4711)],
                                              {"jobs": [job()]}, protokoll),
                         warten=0, schlafen=lambda s: None)
        jobabfragen = [u for u in protokoll if "/jobs" in u]
        self.assertEqual(len(jobabfragen), 1)
        self.assertIn("/runs/4711/jobs", jobabfragen[0])

    def test_gruenes_repo_loest_keine_nachfrage_aus(self):
        """60 Abfragen je Stunde sind die harte Grenze. Verifiziert: SWR-107."""
        self.repo("a")
        protokoll = []
        e = ci_status.pruefe(self.wurzel,
                             holen=zwei_antworten([lauf(sha=self.sha("a"))], {"jobs": []},
                                                  protokoll),
                             warten=0, schlafen=lambda s: None)
        self.assertTrue(e["alles_gruen"])
        self.assertEqual([u for u in protokoll if "/jobs" in u], [])
        self.assertEqual(e["abfragen"], 1)

    def test_gescheiterte_nachfrage_laesst_das_repo_rot(self):
        """Der Kern der Vorsichtsregel: eine Diagnose darf einen Befund nie
        verschlucken (B038). Verifiziert: SWR-107."""
        self.repo("a")
        e = ci_status.pruefe(self.wurzel,
                             holen=zwei_antworten([self.rotlauf(self.sha("a"))],
                                                  "Abruf fehlgeschlagen: kein Netz"),
                             warten=0, schlafen=lambda s: None)
        r = e["repos"][0]
        self.assertEqual(r["zustand"], "rot")
        self.assertFalse(e["alles_gruen"])
        self.assertNotIn("schritt", r)
        self.assertIn("kein Netz", r["diagnose_fehler"])
        self.assertIn("Schritt unbekannt", ci_status.bericht(e))

    def test_die_nachfragen_zaehlen_gegen_dasselbe_budget(self):
        """Ein zweiter, stiller Zähler wäre B033. Verifiziert: SWR-107."""
        self.repo("a")
        e = ci_status.pruefe(self.wurzel,
                             holen=zwei_antworten([self.rotlauf(self.sha("a"))],
                                                  {"jobs": [job()]}),
                             warten=0, schlafen=lambda s: None)
        self.assertEqual(e["abfragen"], 2)  # ein Lauf-Abruf + eine Diagnose

    def test_erschoepftes_budget_unterdrueckt_die_nachfrage_und_sagt_es(self):
        """Verifiziert: SWR-107."""
        self.repo("a")
        protokoll = []
        e = ci_status.pruefe(self.wurzel,
                             holen=zwei_antworten([self.rotlauf(self.sha("a"))],
                                                  {"jobs": [job()]}, protokoll),
                             warten=0, budget=1, schlafen=lambda s: None)
        r = e["repos"][0]
        self.assertEqual(r["zustand"], "rot")
        self.assertEqual([u for u in protokoll if "/jobs" in u], [])
        self.assertIn("Abfragebudget", r["diagnose_fehler"])
        self.assertIn("Schritt unbekannt", ci_status.bericht(e))

    def test_roter_lauf_ohne_lauf_id_kostet_keine_abfrage(self):
        """Eine Antwort ohne `id` ist unerwartet — dann wird nicht geraten und auch
        nichts abgefragt. Verifiziert: SWR-107."""
        self.repo("a")
        protokoll = []
        e = ci_status.pruefe(self.wurzel,
                             holen=zwei_antworten([lauf(sha=self.sha("a"), fazit="failure")],
                                                  {"jobs": [job()]}, protokoll),
                             warten=0, schlafen=lambda s: None)
        self.assertEqual(e["repos"][0]["zustand"], "rot")
        self.assertEqual([u for u in protokoll if "/jobs" in u], [])
        self.assertEqual(e["abfragen"], 1)


# --------------------------------------------------------------------------------------
# B063 — Befunde der unabhängigen Gegenprüfung von SWR-107, bei GRÜNER Suite gefunden.
# Dieselbe Familie wie B059: die eigene Suite prüft, was die Änderung tun soll, und
# nicht, was ihre Nachbarn und Grenzfälle daraus machen. Diese Tests sind der
# Regressionsschutz, kein Nachtrag.
# --------------------------------------------------------------------------------------

class GegenpruefungTest(RepoWelt):
    """Verifiziert: SWR-107 (B063)."""

    def rotlauf(self, sha, lauf_id=4711):
        r = lauf(sha=sha, fazit="failure")
        r["id"] = lauf_id
        return r

    def test_unerwartete_nutzlast_reisst_den_bericht_nicht_mit(self):
        """Die Anforderung nennt „unexpected payload" ausdrücklich als Fall für
        „Schritt unbekannt". Vorher warf `fehlerschritt` bei einer Liste statt eines
        Objekts — und `main()` brach ab, ohne die Datei zu schreiben: der rote
        Befund war ermittelt und ging verloren. Verifiziert: SWR-107."""
        for kaputt in ([{"name": "b", "conclusion": "failure"}], {"jobs": {"a": 1}},
                       {"jobs": [None, "x", 7]}, "kein json", 42, [], 0):
            self.assertIsNone(ci_status.fehlerschritt(kaputt), repr(kaputt))
        # Eine Liste statt einer Liste von Objekten an der Schritt-Stelle: der Job ist
        # auswertbar, die Schritte sind es nicht — Rückfall auf den Job, kein Wurf.
        t = ci_status.fehlerschritt({"jobs": [{"steps": {"a": 1}, "name": "b",
                                               "conclusion": "failure"}]})
        self.assertEqual((t["job"], t["schritt"]), ("b", ""))
        self.repo("a")
        e = ci_status.pruefe(self.wurzel,
                             holen=zwei_antworten([self.rotlauf(self.sha("a"))],
                                                  [{"name": "b", "conclusion": "failure"}]),
                             warten=0, schlafen=lambda s: None)
        self.assertEqual(e["repos"][0]["zustand"], "rot")
        self.assertIn("Schritt unbekannt", ci_status.bericht(e))

    def test_budget_das_die_diagnose_verhungern_laesst_steht_auch_im_json(self):
        """Vorher sagte der Fließtext viermal „Abfragebudget aufgebraucht" und das
        maschinenlesbare Feld daneben `false` — zwei Quellen, eine Aussage (B033).
        Verifiziert: SWR-107."""
        for n in ("a", "b"):
            self.repo(n)
        laeufe = [self.rotlauf(self.sha("a")), self.rotlauf(self.sha("b"), 4712)]
        e = ci_status.pruefe(self.wurzel, holen=zwei_antworten(laeufe, {"jobs": [job()]}),
                             warten=0, budget=3, schlafen=lambda s: None)
        self.assertTrue(e["budget_erschoepft"])
        self.assertIn("Abfragebudget aufgebraucht", ci_status.bericht(e))
        self.assertTrue(all(r["zustand"] == "rot" for r in e["repos"]))

    def test_reichendes_budget_meldet_keine_erschoepfung(self):
        """Der Gegentest zum vorigen — sonst meldete das Feld ab jetzt immer `true`
        und wäre wertlos. Verifiziert: SWR-107."""
        self.repo("a")
        e = ci_status.pruefe(self.wurzel,
                             holen=zwei_antworten([self.rotlauf(self.sha("a"))],
                                                  {"jobs": [job()]}),
                             warten=0, schlafen=lambda s: None)
        self.assertFalse(e["budget_erschoepft"])
        self.assertEqual(e["abfragen"], 2)

    def test_neutral_ist_wie_skipped_kein_fehlschlag(self):
        """`neutral` ist ein ausdrücklich folgenloses Ergebnis. Vorher wurde ein
        `neutral`-Job als Ursache gemeldet und der wirklich gescheiterte verschwiegen —
        eine beruhigende Zeile zu einem roten Befund. Verifiziert: SWR-107."""
        d = {"jobs": [job("lint", "neutral", [("n", "neutral")]),
                      job("tests", "failure", [("pytest", "failure")])]}
        t = ci_status.fehlerschritt(d)
        self.assertEqual((t["job"], t["schritt"]), ("tests", "pytest"))

    def test_mehrere_fehlgeschlagene_jobs_werden_gezaehlt_nicht_verschwiegen(self):
        """Eine Zeile, die den ersten nennt, liest sich sonst als DIE Ursache.
        Verifiziert: SWR-107."""
        d = {"jobs": [job("erster", "failure", [("A", "failure")]),
                      job("zweiter", "failure", [("B", "failure")])]}
        t = ci_status.fehlerschritt(d)
        self.assertEqual(t["weitere_jobs"], 1)
        self.assertIn("1 weitere(r) Job(s)", ci_status.schritt_klartext(dict(t)))

    def test_ein_einziger_fehlgeschlagener_job_bekommt_keinen_zusatz(self):
        """Verifiziert: SWR-107."""
        t = ci_status.fehlerschritt({"jobs": [job("nur-einer", "failure", [("A", "failure")])]})
        self.assertEqual(t["weitere_jobs"], 0)
        self.assertNotIn("weitere", ci_status.schritt_klartext(dict(t)))

    def test_geglueckte_nachfrage_ohne_jobnamen_sagt_warum(self):
        """Vorher nicht unterscheidbar von „gar nicht nachgefragt" — die verbrauchte
        Abfrage war unsichtbar. Verifiziert: SWR-107."""
        self.repo("a")
        e = ci_status.pruefe(self.wurzel,
                             holen=zwei_antworten([self.rotlauf(self.sha("a"))],
                                                  {"jobs": [{"conclusion": "failure"}]}),
                             warten=0, schlafen=lambda s: None)
        r = e["repos"][0]
        self.assertEqual(r["zustand"], "rot")
        self.assertIn("ohne Namen", r["diagnose_fehler"])
        self.assertIn("Schritt unbekannt", ci_status.bericht(e))

    def test_schritt_klartext_haelt_jeden_unsinn_aus(self):
        """Verifiziert: SWR-107."""
        for x in (None, [], "x", 7, {}):
            self.assertEqual(ci_status.schritt_klartext(x), "Schritt unbekannt")
