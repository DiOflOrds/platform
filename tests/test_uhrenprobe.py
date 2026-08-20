"""SWR-159 (platform/T-0026): Registerzeiten in der Zukunft ihres Commits.

⚠ **Jedes Register in dieser Datei wird GEBAUT, nicht gehofft** — dieselbe Auflage, unter
der `test_pause_zwischen_laeufen.py` (SWR-156) steht. Ein Test, der auf den echten
Bestand zeigt, prüft ab morgen die Uhr statt den Code (SWR-157).

⚠ Und die Gegenprobe am **echten** Bestand steht trotzdem dabei — als *Schranke*, nicht
als Momentaufnahme: der eine belegte Treffer muss weiterhin gefunden werden, sonst hätte
die Prüfung ihren einzigen Beleg verloren, ohne dass es jemandem auffiele.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import sprint_register  # noqa: E402
import uebergang_historie  # noqa: E402

WURZEL = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _probe(root):
    """Material + Regel — dieselbe Naht, die der Preflight zieht (SWR-159).

    ⚠ Die Tests gehen ausdrücklich über die **Naht** und nicht an ihr vorbei: würde hier
    ein Register von Hand zusammengesteckt, prüfte die Strecke die Regel und niemals das
    Zusammenspiel, das in Produktion läuft.
    """
    zeilen = uebergang_historie.zugefuegte_zeilen(
        os.path.join(root, "pm"), os.path.join("management", "sprints.jsonl"))
    return sprint_register.uhrenprobe(zeilen)


class UhrenprobeTest(unittest.TestCase):
    """SWR-159: eine Zeile kann nicht später entstanden sein als ihr Commit."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.repo = os.path.join(self.root, "pm")
        os.makedirs(os.path.join(self.repo, "management"))
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "team@aspice.local")
        self._git("config", "user.name", "ASPICE-Team")

    def _git(self, *args):
        return subprocess.run(["git", "-C", self.repo] + list(args),
                              capture_output=True, text=True)

    def _commit(self, eintrag, commit_zeit):
        """Eine Registerzeile anhängen und mit GESETZTER Commit-Zeit committen.

        ⚠ Die Commit-Zeit wird über die Umgebung vorgegeben und nicht von der Uhr des
        Testrechners genommen — sonst prüfte der Test, wie schnell er selbst läuft.
        """
        pfad = os.path.join(self.repo, "management", "sprints.jsonl")
        with open(pfad, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(eintrag, ensure_ascii=False) + "\n")
        umg = dict(os.environ, GIT_AUTHOR_DATE=commit_zeit, GIT_COMMITTER_DATE=commit_zeit,
                   GIT_AUTHOR_NAME="ASPICE-Team", GIT_COMMITTER_NAME="ASPICE-Team",
                   GIT_AUTHOR_EMAIL="team@aspice.local",
                   GIT_COMMITTER_EMAIL="team@aspice.local")
        subprocess.run(["git", "-C", self.repo, "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", self.repo, "commit", "-q", "-m", "reg"],
                       capture_output=True, env=umg)

    def test_der_belegte_fall_wird_gefunden_und_BENANNT(self):
        """Sprint 16 nachgestellt: `ende` 17:10, Commit 16:32:36.

        ⚠ Gemessen wird nicht nur, DASS etwas gefunden wird, sondern **was**: Kennung,
        Feld, beide Zeiten und der Abstand. Eine Meldung ohne ihren Gegenstand ist keine
        Meldung (B038).
        """
        self._commit({"nr": 16, "kennung": "s16", "start": "2026-08-17 15:41"},
                     "2026-08-17T15:45:44+02:00")
        self._commit({"kennung": "s16", "ende": "2026-08-17 17:10"},
                     "2026-08-17T16:32:36+02:00")
        treffer = _probe(self.root)
        self.assertEqual(len(treffer), 1)
        t = treffer[0]
        self.assertEqual(t["kennung"], "s16")
        self.assertEqual(t["feld"], "ende")
        self.assertEqual(t["registerzeit"], "2026-08-17 17:10")
        self.assertEqual(t["commitzeit"], "2026-08-17 16:32:36")
        self.assertAlmostEqual(t["minuten"], 37.4, places=1)

    def test_der_eingefrorene_altbestand_wird_als_solcher_MARKIERT(self):
        """⚠ Der eine belegte Fall ist nicht reparierbar — die Datei ist append-only.

        Er bleibt als Beleg stehen und wird bei jedem Lauf mit seiner **Zahl** gemeldet.
        Was er nicht tut, ist den Preflight dauerhaft rot färben: ein Dauerbefund
        trainiert das Wegsehen (SWR-109/110/112), und dieselbe Trennung führt der
        Preflight bereits für 52 Altbestands-Statusübergänge und 14 Sprints ohne `ende`.
        """
        self._commit({"kennung": "2026-08-17T1541-cowork-s16", "ende": "2026-08-17 17:10"},
                     "2026-08-17T16:32:36+02:00")
        self._commit({"kennung": "fremd", "ende": "2026-08-17 18:00"},
                     "2026-08-17T17:00:00+02:00")
        treffer = {t["kennung"]: t["altbestand"] for t in _probe(self.root)}
        self.assertTrue(treffer["2026-08-17T1541-cowork-s16"])
        self.assertFalse(treffer["fremd"],
                         "ein NEUER Uhrenstreit darf nicht im Altbestand verschwinden")

    def test_der_NORMALFALL_ist_kein_befund(self):
        """⚠ Die Gegenprobe, und ohne sie belegt der Rest nichts.

        Gemessen an der echten Historie streuen die `start`-Abstände zwischen +0,9 und
        +81,3 Minuten, weil ein Start früh geschrieben und spät committet wird. Eine
        Prüfung mit Schwelle hätte hier wählen müssen; die einseitige braucht das nicht.
        """
        self._commit({"nr": 21, "kennung": "s21", "start": "2026-08-20 10:30"},
                     "2026-08-20T11:11:58+02:00")   # +42,0 Min
        self._commit({"kennung": "s21", "ende": "2026-08-20 11:16"},
                     "2026-08-20T11:16:54+02:00")   # +0,9 Min
        self.assertEqual(_probe(self.root), [])

    def test_nachtrag_ist_kein_befund_und_das_ist_der_UNTERSCHIED(self):
        """Sprint 17 wurde von Sprint 18 nachgetragen: +21,3 Minuten, und trotzdem sauber.

        ⚠ Das ist der Grund, aus dem die Prüfung **einseitig** ist. Ein Nachtrag schreibt
        eine Zeit aus der Vergangenheit — das ist erlaubt und aktenkundig. Nur die
        Gegenrichtung ist unmöglich, und deshalb ist nur sie ein Befund.
        """
        self._commit({"kennung": "s17", "ende": "2026-08-17 19:03"},
                     "2026-08-17T19:24:18+02:00")
        self.assertEqual(_probe(self.root), [])

    def test_minutengenauigkeit_kann_NICHT_faelschlich_ausloesen(self):
        """Das Register schreibt `%H:%M` und schneidet die Sekunden ab.

        Abschneiden macht den Wert **früher**, nie später — der schärfste Fall (Zeile in
        derselben Minute wie der Commit, Commit eine Sekunde nach dem Minutenbeginn) muss
        deshalb grün sein. Ohne diese Zusicherung wäre die Prüfung bei jedem zweiten Lauf
        rot und niemand wüsste, warum.
        """
        self._commit({"nr": 1, "kennung": "s1", "start": "2026-08-20 13:07"},
                     "2026-08-20T13:07:01+02:00")
        self.assertEqual(_probe(self.root), [])

    def test_beobachtungszeilen_werden_MITGEPRUEFT(self):
        """`beobachtet` (SWR-136, Schreibspur) kommt aus derselben Uhr wie `start`/`ende`.

        Sie auszunehmen hiesse, eine Zeitquelle ungeprüft zu lassen, weil an ihr bisher
        nichts aufgefallen ist — dieselbe Vermutung über die Zukunft, die `platform/T-0020`
        Frage 2 verworfen hat.
        """
        self._commit({"kennung": "s9", "beobachtet": "2026-08-17 09:00", "spur": "x"},
                     "2026-08-17T08:00:00+02:00")
        treffer = _probe(self.root)
        self.assertEqual([t["feld"] for t in treffer], ["beobachtet"])

    def test_ohne_register_ist_NICHT_PRUEFBAR_und_nicht_sauber(self):
        """⚠ `None` und `[]` sind zweierlei — SWR-108/135 eine Etage höher.

        „Keine Daten" als „keine Treffer" zu melden ist die Verwechslung, gegen die
        dieses Haus an drei Stellen ausdrücklich gebaut hat.
        """
        leer = tempfile.TemporaryDirectory()
        self.addCleanup(leer.cleanup)
        self.assertIsNone(_probe(leer.name))

    def test_der_sprintzaehler_ruft_SELBST_kein_git_auf(self):
        """⚠⚠ Die Zusicherung, die den ersten Entwurf dieser Prüfung verworfen hat.

        Er holte sich sein Material mit einem eigenen `git log` **in
        `sprint_register`** — und wurde rot an
        `test_sprint_register_ende.test_die_messung_ruft_KEIN_git_auf`, einer Regel aus
        Sprint 16, die seit SWR-134 im Bestand steht: auf diesem Mount hinterlässt schon
        ein lesender Git-Aufruf eine Sperre, die niemand mehr löschen kann.

        *Eine Prüfung, die Uneinigkeit zwischen zwei Läufen erkennen soll und dabei
        selbst sperrt, ist ihr eigener Schadensfall.* Die Zusicherung wird hier
        **wiederholt**, weil sie sonst nur beim Sprintzähler steht und der nächste
        Erweiterer dieser Prüfung sie erneut nicht kennt.
        """
        self.assertIsNone(sprint_register.uhrenprobe(None),
                          "die Regel bekommt ihr Material gereicht und beschafft es nicht")
        self.assertEqual(sprint_register.uhrenprobe([]), [])

    def test_ohne_git_ist_NICHT_PRUEFBAR(self):
        """Ein Register ohne Historie kann die Frage nicht beantworten — und sagt das."""
        ohne = tempfile.TemporaryDirectory()
        self.addCleanup(ohne.cleanup)
        verz = os.path.join(ohne.name, "pm", "management")
        os.makedirs(verz)
        open(os.path.join(verz, "sprints.jsonl"), "w", encoding="utf-8").write(
            '{"nr": 1, "kennung": "x", "start": "2026-01-01 00:00"}\n')
        self.assertIsNone(_probe(ohne.name))


class EchterBestandTest(unittest.TestCase):
    """SWR-159 am **echten** Register — als Schranke, nicht als Momentaufnahme (SWR-157)."""

    def test_der_eine_belegte_treffer_bleibt_auffindbar(self):
        """⚠ Nicht `assertEqual(1)`: neue Läufe dürfen weitere Treffer erzeugen, ohne
        diese Zusicherung rot zu machen — sie meldet der Preflight. Was hier gehalten
        wird, ist die untere Schranke: **der Beleg darf nicht verschwinden.**

        Verschwände er, wäre entweder das Register umgeschrieben worden (es ist
        append-only) oder die Prüfung kaputt — und beides fiele sonst niemandem auf.
        """
        treffer = _probe(WURZEL)
        if treffer is None:
            self.skipTest("kein Git-Bestand in dieser Umgebung")
        s16 = [t for t in treffer if t["kennung"] == "2026-08-17T1541-cowork-s16"]
        self.assertGreaterEqual(len(s16), 1)
        self.assertEqual(s16[0]["feld"], "ende")
        self.assertGreater(s16[0]["minuten"], 30)
        self.assertTrue(s16[0]["altbestand"])

    def test_der_eingefrorene_eintrag_ZEIGT_auf_etwas_vorhandenes(self):
        """⚠⚠ Die Gegenprobe zum Einfrieren: eine Liste, die ins Leere zeigt, ist still.

        `ALTBESTAND_UHRENSTREIT` unterdrückt einen Befund. Verschwände sein Gegenstand —
        durch ein umgeschriebenes Register oder eine kaputte Prüfung —, bliebe die Liste
        stehen und niemand merkte es: *ein Zähler auf 0 ist von einer kaputten Prüfung
        nicht zu unterscheiden* (`L-2026-08-17ai`).
        """
        treffer = _probe(WURZEL)
        if treffer is None:
            self.skipTest("kein Git-Bestand in dieser Umgebung")
        gefunden = {(t["kennung"], t["feld"]) for t in treffer}
        for eintrag in sprint_register.ALTBESTAND_UHRENSTREIT:
            self.assertIn(eintrag, gefunden,
                          "der eingefrorene Altbestand muss weiterhin GEFUNDEN werden")


if __name__ == "__main__":
    unittest.main()
