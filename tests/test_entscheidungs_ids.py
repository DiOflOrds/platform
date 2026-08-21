# -*- coding: utf-8 -*-
"""SWR-197 (`platform/T-0047`): die Menge der mehrdeutigen Entscheidungs-IDs wächst nicht.

⚠⚠ Der Gegenstand ist **nicht** die Zitatstelle, und das ist das Ergebnis einer Messung:
von 1023 praefixlosen `D`-Zitaten sind **214 (21 %)** echt mehrdeutig — und **alle 214**
nennen eine von **vierzehn** IDs (`D000`–`D013`). Ab `D014` ist jede ID
organisationsweit einmal vergeben.

> **Der Mangel ist ein Präfix des Nummernraums. Also wird der Nummernraum gehalten und
> nicht der Korpus geputzt.**

⚠ Die Gegenproben laufen an einer **synthetischen** Wurzel (`L-2026-08-20cm`) — nicht an
den 17 Live-Repos, die eine fremde Automatik alle 15 Minuten anfasst.
"""
import os
import shutil
import sys
import tempfile
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)

from backend import entscheidungs_ids as eids  # noqa: E402

KOPF = "| ID | Datum | Titel |\n|---|---|---|\n"


def log(*ids):
    return KOPF + "".join(f"| {i} | 2026-08-21 | Beschluss |\n" for i in ids)


class SynthetischeWurzel(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="swr197-")
        self.schreibe("alpha", log("D001", "D002", "D014"))
        self.schreibe("beta", log("D001", "D015"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def schreibe(self, einheit, inhalt):
        d = os.path.join(self.root, einheit, "management", "decisions")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "decision-log.md"), "w", encoding="utf-8") as f:
            f.write(inhalt)

    def md(self, relpfad, inhalt):
        p = os.path.join(self.root, *relpfad.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(inhalt)


class GrundmengeTest(SynthetischeWurzel):
    """⚠ Erst die Grundmenge, dann jedes Ergebnis — sonst ist „sauber" von „nichts

    gelesen" nicht zu unterscheiden (`SWR-128/165`).
    """

    def test_beide_logs_werden_gefunden(self):
        self.assertEqual(eids.logs_gefunden(self.root), 2)

    def test_vergabe_nennt_die_einheiten_je_id(self):
        v = eids.vergabe(self.root)
        self.assertEqual(v["D001"], {"alpha", "beta"})
        self.assertEqual(v["D014"], {"alpha"})
        self.assertEqual(v["D015"], {"beta"})

    def test_mehrdeutig_ist_genau_die_doppelt_vergebene(self):
        self.assertEqual(sorted(eids.mehrdeutige(self.root)), ["D001"])


class SperrklinkeTest(SynthetischeWurzel):

    def test_altbestand_ist_still(self):
        """`D001` liegt im benannten Altbestand — kein Befund, wie `SWR-195` es hält."""
        self.assertIn("D001", eids.ALTBESTAND_MEHRDEUTIG)
        self.assertEqual([b for b in eids.befund(self.root) if b.startswith("NEU")], [])

    def test_neue_mehrdeutige_id_wird_gemeldet(self):
        """⚠⚠ Der eigentliche Zweck: ein zweites Repo vergibt `D014` erneut.

        Das ist **eine Zeile** — und sie kostet, unbemerkt, wieder zweihundert
        Zitatstellen. Genau hier ist sie noch billig.
        """
        self.schreibe("beta", log("D001", "D014", "D015"))
        b = eids.befund(self.root)
        neu = [x for x in b if x.startswith("NEU")]
        self.assertEqual(len(neu), 1)
        self.assertIn("D014", neu[0])
        self.assertIn("alpha", neu[0])
        self.assertIn("beta", neu[0])
        self.assertIn("<einheit>/D014", neu[0], "die Absage nennt die Pflichtform (SWR-167)")

    def test_verschwundener_altbestand_wird_gemeldet(self):
        """⚠ Die Gegenrichtung. Entscheidungslogs sind append-only: eine Zeile

        verschwindet dort nicht von allein. Ohne diese Richtung wäre ein **gelöschtes**
        Log grün — eine Prüfung, die nur Zuwachs misst, belohnt das Löschen.
        """
        self.schreibe("beta", log("D015"))          # D001 fällt aus beta heraus
        b = eids.befund(self.root)
        weg = [x for x in b if x.startswith("VERSCHWUNDEN")]
        self.assertTrue(any("D001" in x for x in weg))

    def test_der_altbestand_ist_eine_menge_und_keine_zahl(self):
        """`L-2026-08-20by`: eine Zahl sagt nicht, welche verschwunden ist."""
        self.assertEqual(len(eids.ALTBESTAND_MEHRDEUTIG), 14)
        self.assertEqual(min(eids.ALTBESTAND_MEHRDEUTIG), "D000")
        self.assertEqual(max(eids.ALTBESTAND_MEHRDEUTIG), "D013")


class ZitatBerichtTest(SynthetischeWurzel):

    def test_die_drei_lagen_werden_getrennt(self):
        """⚠⚠ Das Zusammenwerfen hat die 1003 erzeugt, die keine 1003 Probleme waren.

        * `alpha/bericht.md` nennt `D002` — **eigene** Einheit, nicht mehrdeutig.
        * `alpha/bericht.md` nennt `D015` — fremd, aber `D015` gibt es nur einmal.
        * `gamma/bericht.md` nennt `D001` — fremd **und** doppelt vergeben: der Fall.
          ⚠ `gamma` und nicht `alpha`, weil `alpha` selbst ein `D001` führt — siehe
          `test_das_eigene_gewinnt_gegen_das_fremde`.
        """
        vorher = eids.zitat_bericht(self.root)
        self.md("alpha/bericht.md", "Siehe D002 und D015.\n")
        self.md("gamma/bericht.md", "Siehe D001.\n")
        z = eids.zitat_bericht(self.root)
        self.assertEqual(z["im_eigenen"] - vorher["im_eigenen"], 1)
        self.assertEqual(z["aufloesbar"] - vorher["aufloesbar"], 1)
        self.assertEqual(z["mehrdeutig"] - vorher["mehrdeutig"], 1)

    def test_das_eigene_gewinnt_gegen_das_fremde(self):
        """⚠⚠ Von einer Zusicherung gefunden, nicht vorher bedacht.

        `D001` ist in `alpha` **und** `beta` vergeben. Ein `D001` in einer Datei unter
        `alpha` ist trotzdem **nicht** mehrdeutig: die naheliegende Lesart ist die eigene,
        und die Datei sagt, wo sie liegt. Mehrdeutig wird dieselbe ID erst dort, wo
        **keine** eigene Entsprechung steht.

        > **Eine ID ist nicht mehrdeutig, weil sie doppelt vergeben ist, sondern weil sie
        > an ihrer Fundstelle keine naheliegende Lesart hat.** Ohne diese Unterscheidung
        > wären die 214 wieder größer, als das Problem ist — derselbe Fehler wie bei den
        > 1003, eine Ebene tiefer.
        """
        vorher = eids.zitat_bericht(self.root)
        self.md("alpha/eigen.md", "Siehe D001.\n")
        z = eids.zitat_bericht(self.root)
        self.assertEqual(z["im_eigenen"] - vorher["im_eigenen"], 1)
        self.assertEqual(z["mehrdeutig"] - vorher["mehrdeutig"], 0)

    def test_das_entscheidungslog_zitiert_sich_selbst_im_eigenen_repo(self):
        """⚠⚠ Der Grundbestand ist nicht null, und das ist der Kern von `T-0036`.

        Die Logs **sind** Markdown und nennen ihre eigenen IDs — am echten Bestand waren
        genau sie die zwei größten Einzelposten der 1003. Sie sind nicht mehrdeutig: die
        Datei sagt, wo sie liegt. Deshalb misst diese Datei **Differenzen** und keine
        Absolutwerte, und deshalb steht der Grundbestand hier ausdrücklich da statt
        stillschweigend in jeder Erwartung.
        """
        z = eids.zitat_bericht(self.root)
        self.assertEqual(z["mehrdeutig"], 0, "ein Log zitiert sich nur selbst")
        self.assertEqual(z["im_eigenen"], 5, "3 IDs in alpha, 2 in beta")

    def test_wurzeldatei_hat_keine_eigene_einheit(self):
        """⚠ Eine Datei in der Wurzel sagt nichts über den Ort — dort ist jedes

        praefixlose Zitat mehrdeutig. Am echten Bestand ist `PROJEKTSTATUS-UPDATE.md` mit
        47 der größte Einzelposten der ehrlichen Untermenge.
        """
        self.md("PROJEKTSTATUS.md", "Siehe D001.\n")
        self.assertEqual(eids.zitat_bericht(self.root)["mehrdeutig"], 1)

    def test_praefixiertes_zitat_zaehlt_nicht_als_praefixlos(self):
        """⚠ Sonst zählte `alpha/D001` in beiden Mengen — und die Summe wäre keine."""
        vorher = eids.zitat_bericht(self.root)
        self.md("gamma/bericht.md", "Siehe alpha/D001 und beta/D001.\n")
        z = eids.zitat_bericht(self.root)
        self.assertEqual(z["gesamt"], vorher["gesamt"],
                         "ein praefixiertes Zitat darf die praefixlose Menge nicht bewegen")

    def test_die_teile_ergeben_das_ganze(self):
        """⚠ `L-2026-08-21cb`: eine Summe aus Teilmessungen ist keine Summe, wenn die

        Teile nicht dieselbe Grundmenge haben. Hier hält die Zusicherung sie zusammen.
        """
        self.md("alpha/a.md", "D002 D015 D001 D999\n")
        self.md("beta/b.md", "D001 D014\n")
        z = eids.zitat_bericht(self.root)
        self.assertEqual(z["gesamt"],
                         z["im_eigenen"] + z["aufloesbar"] + z["mehrdeutig"] + z["unbekannt"])

    def test_nie_vergebene_id_ist_eine_eigene_lage(self):
        """`D999` steht in keinem Log — das ist weder auflösbar noch mehrdeutig."""
        self.md("alpha/a.md", "D999\n")
        z = eids.zitat_bericht(self.root)
        self.assertEqual(z["unbekannt"], 1)
        self.assertEqual(z["mehrdeutig"], 0)


class TautologieTest(unittest.TestCase):
    """⚠⚠ `L-2026-08-21ch`: eine Prüfung, die sich selbst liest, prüft nicht mehr.

    In Sprint 29 hat `lehren.py` genau das getan — eine echte Lehr-ID in einem Kommentar,
    und die Zählung fiel von 29 auf 28, ohne dass sich an der Sache etwas geändert hätte.
    Hier ist die Trennung **strukturell**: der Prüfer liegt in `.py`, der Korpus besteht
    aus `.md`. Diese Zusicherung hält das fest, statt sich darauf zu verlassen.
    """

    def test_der_pruefer_liegt_nicht_im_geprueften_korpus(self):
        self.assertTrue(eids.__file__.endswith(".py"))
        self.assertNotIn(".md", eids.__file__)

    def test_der_korpus_besteht_ausschliesslich_aus_md(self):
        root = tempfile.mkdtemp(prefix="swr197-tauto-")
        try:
            os.makedirs(os.path.join(root, "alpha"))
            for name in ("a.md", "b.py", "c.txt", "d.yaml"):
                with open(os.path.join(root, "alpha", name), "w", encoding="utf-8") as f:
                    f.write("D001\n")
            self.assertEqual([os.path.basename(p) for p in eids._md_dateien(root)], ["a.md"])
        finally:
            shutil.rmtree(root, ignore_errors=True)


class EchterBestandTest(unittest.TestCase):
    """⚠⚠ Die Sperrklinke am **echten** Bestand — die Bauform von `SWR-194`.

    Eine Prüfung, die nur an synthetischen Wurzeln läuft, ist eine Aussage über
    ausgedachte Fälle. Diese hier wird von allein rot, wenn ein Repo anfängt, seine
    Entscheidungen wieder bei `D001` zu zählen.

    **Gemessen am 2026-08-21 (Sprint 30, `SWR-174`: die Zahl trägt ihren Zeitpunkt):**
    18 Entscheidungslogs, **14** mehrdeutige IDs (`D000`–`D013`), 1030 praefixlose
    Zitatstellen — 746 im eigenen Repo, 67 auflösbar, **216 mehrdeutig**, 1 nie vergeben.

    ⚠ Die **Zitatzahlen stehen bewusst NICHT in einer Zusicherung**, und der Grund ist an
    dieser Session selbst gemessen: sie sind während des Baus von 1023/214 auf 1030/216
    gestiegen — allein dadurch, dass Ticket und Anforderung **über** das Problem
    schreiben und dabei IDs nennen.

    > **Eine Prüfung auf die Zitatzahl würde jeden Bericht bestrafen, der den Befund
    > erklärt. Genau deshalb hält diese Prüfung den NUMMERNRAUM und nicht den Korpus.**
    """

    WURZEL = os.path.dirname(WURZEL)

    def test_die_grundmenge_ist_nicht_leer(self):
        """`SWR-128/165`: eine Prüfung, die nichts liest, findet auch nichts."""
        self.assertGreaterEqual(eids.logs_gefunden(self.WURZEL), 2,
                                "keine Entscheidungslogs gefunden — Discovery kaputt?")

    def test_die_mehrdeutige_menge_waechst_nicht(self):
        """⚠⚠ **Der Zweck dieser Datei.** Vierzehn IDs, und keine fünfzehnte."""
        self.assertEqual(eids.befund(self.WURZEL), [])

    def test_alle_mehrdeutigen_zitate_nennen_eine_der_vierzehn(self):
        """⚠⚠ Der Befund, der die Bauform bestimmt hat — als Zusicherung statt als Satz.

        Ab `D014` ist jede ID organisationsweit einmal vergeben. Dass **alle** mehrdeutigen
        Zitate aus dem unteren Nummernraum stammen, ist der Grund, warum eine Sperrklinke
        an der **Vergabe** genügt und keine an 1030 Zitatstellen nötig ist. Fällt diese
        Zusicherung, ist die Begründung des Baus hinfällig — und das soll auffallen.
        """
        mehrdeutig = set(eids.mehrdeutige(self.WURZEL))
        self.assertTrue(mehrdeutig)
        self.assertTrue(mehrdeutig <= set(eids.ALTBESTAND_MEHRDEUTIG))
        self.assertTrue(all(i < "D014" for i in mehrdeutig),
                        "eine mehrdeutige ID oberhalb von D013 — der Nummernraum ist "
                        "nicht mehr sauber getrennt")

    def test_die_lagen_ergeben_zusammen_die_gesamtzahl(self):
        """`L-2026-08-21cb`: eine Summe aus Teilen mit verschiedenen Grundmengen ist keine."""
        z = eids.zitat_bericht(self.WURZEL)
        self.assertEqual(z["gesamt"],
                         z["im_eigenen"] + z["aufloesbar"] + z["mehrdeutig"] + z["unbekannt"])
        self.assertGreater(z["dateien"], 100, "der Korpus ist zu klein — falsche Wurzel?")

    def test_die_mehrheit_ist_nicht_das_problem(self):
        """⚠ Die Aussage von `T-0036` — *„die 1003 sind nicht 1003 Probleme"* — als Prüfung.

        Läge die Mehrheit der praefixlosen Zitate im mehrdeutigen Topf, wäre der Zuschnitt
        dieses Tickets falsch gewesen und ein Korpus-Umbau die richtige Antwort. Gemessen
        sind es 21 %.
        """
        z = eids.zitat_bericht(self.WURZEL)
        self.assertLess(z["mehrdeutig"], z["im_eigenen"],
                        "mehr mehrdeutige als eigene Zitate — der Zuschnitt von T-0047 "
                        "beruht auf der umgekehrten Lage und wäre neu zu prüfen")


if __name__ == "__main__":
    unittest.main()
