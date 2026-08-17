"""Auswertung der Lauftelemetrie je Rolle (SWR-140, promt-team/T-0005).

⚠⚠ **Die schärfste Zusicherung hier ist `test_teilmessung_traegt_ihren_nenner`.** Der
Bestand ist leer (7 Läufe, 0 mit Token), und die naheliegende Auswertung — ein Mittelwert
je Rolle — wäre auf ihn angewandt eine Behauptung:

> **Ein Mittel über die Läufe, die zufällig gemeldet haben, ist kein Mittel über die
> Läufe. Ohne seinen Nenner gedruckt ist es von einer vollständigen Messung nicht zu
> unterscheiden.**

Ausführung: python -m unittest discover platform/tests
"""
import ast
import json
import os
import sys
import tempfile
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
from backend import auswertung  # noqa: E402
from backend.aggregation import (ZUSTAND_ECHTE_NULL,  # noqa: E402
                                 ZUSTAND_NICHT_GELIEFERT, ZUSTAND_WERT)

REGISTRY_YAML = """roles:
  PL:
    name: Projektleiter
    besetzung: ki
    provider_chain: [claude]
    script_tasks: [board-hygiene, kosten-report]
    aufgaben_typen:
      sprint-planning:      { chain: [claude], tier: strong }
      status-zusammenfassung: { chain: [ollama, claude], tier: cheap }
    status: active
  CM:
    name: Konfigurationsmanager
    provider_chain: [claude]
    script_tasks: [board-generierung]
    aufgaben_typen:
      cm-strategie:         { chain: [ollama, session, claude], tier: standard }
    status: active
"""


def lauf(**kw):
    e = {"rolle": "pl", "ticket": "T-0001", "aufgaben_typ": "sprint-planning",
         "provider": "claude", "status": "ok"}
    e.update(kw)
    return e


class AggregatTest(unittest.TestCase):
    """Verifiziert: SWR-140."""

    def test_ohne_messung_ist_nicht_geliefert_und_nicht_null(self):
        """⚠ Ein Aggregat ohne eine einzige Messung ist NICHT GELIEFERT — eine `0` dort
        waere die teuerste Form der Schaetzung, weil sie wie ein Ergebnis aussieht.
        Verifiziert: SWR-140."""
        a = auswertung.aggregat([lauf(), lauf(), lauf()], "token_statisch")
        self.assertEqual(a["zustand"], ZUSTAND_NICHT_GELIEFERT)
        self.assertIsNone(a["summe"])
        self.assertIsNone(a["mittel"])
        self.assertEqual((a["n_gemessen"], a["n_gesamt"]), (0, 3))

    def test_teilmessung_traegt_ihren_nenner(self):
        """⚠⚠ DIE Zusicherung dieses Tickets: melden nur 2 von 5 Laeufen, steht das am
        Ergebnis — `n_gemessen < n_gesamt`. Wer nur `mittel` liest, liest ein Mittel
        ueber eine unbekannte Teilmenge. Verifiziert: SWR-140."""
        eintraege = [lauf(token_statisch=100), lauf(token_statisch=300),
                     lauf(), lauf(), lauf()]
        a = auswertung.aggregat(eintraege, "token_statisch")
        self.assertEqual(a["summe"], 400)
        self.assertEqual(a["mittel"], 200)
        self.assertEqual(a["n_gemessen"], 2)
        self.assertEqual(a["n_gesamt"], 5)
        self.assertLess(a["n_gemessen"], a["n_gesamt"])

    def test_gemeldete_null_zaehlt_als_gemessen(self):
        """Die Gegenrichtung, und sie ist ebenso wichtig: eine gemeldete `0` IST eine
        Messung und hebt `n_gemessen`. Ein Ollama-Lauf kostet wirklich nichts.
        Verifiziert: SWR-140."""
        a = auswertung.aggregat([lauf(kosten_eur=0.0), lauf(kosten_eur=0.0)],
                                "kosten_eur")
        self.assertEqual(a["n_gemessen"], 2)
        self.assertEqual(a["summe"], 0)
        self.assertEqual(a["zustand"], ZUSTAND_ECHTE_NULL)

    def test_echter_wert_ist_wert(self):
        """Gegenprobe: eine Summe groesser null traegt den Zustand `wert`.
        Verifiziert: SWR-140."""
        a = auswertung.aggregat([lauf(dauer_s=1.5)], "dauer_s")
        self.assertEqual(a["zustand"], ZUSTAND_WERT)


class JeRolleTest(unittest.TestCase):
    """Verifiziert: SWR-140."""

    def test_gruppierung_und_blocker_aus_der_telemetrie(self):
        """Die Blocker werden GELESEN, nicht neu hergeleitet — hier am Ergebnis,
        gleich darunter am Syntaxbaum. Verifiziert: SWR-140."""
        r = auswertung.je_rolle([lauf(rolle="pl"), lauf(rolle="cm")])
        self.assertEqual(sorted(r), ["CM", "PL"])
        self.assertIn("token_statisch", r["PL"]["blocker"])
        self.assertEqual(r["PL"]["blocker"]["token_statisch"], 1)

    def test_blocker_werden_nicht_neu_hergeleitet(self):
        """⚠ B033: zwei Herleitungen derselben Frage sind eine zu viel, und die zweite
        ist die, die niemand pflegt. Zugesichert am Syntaxbaum.
        Verifiziert: SWR-140."""
        pfad = os.path.join(_HIER, "..", "backend", "auswertung.py")
        baum = ast.parse(open(pfad, encoding="utf-8").read())
        ruft = [k for k in ast.walk(baum)
                if isinstance(k, ast.Attribute) and k.attr == "blocker"]
        self.assertTrue(ruft, "auswertung leitet Blocker selbst her statt zu lesen")

    def test_vorhandene_blockerliste_wird_uebernommen(self):
        """Traegt der Eintrag schon eine `blocker`-Liste (SWR-137 schreibt sie), wird
        SIE gezaehlt — nicht eine zweite Meinung. Verifiziert: SWR-140."""
        r = auswertung.je_rolle([lauf(blocker=["aufgaben_typ"])])
        self.assertEqual(r["PL"]["blocker"], {"aufgaben_typ": 1})


class SollIstTest(unittest.TestCase):
    """Verifiziert: SWR-140."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.yaml = os.path.join(self.tmp.name, "registry.yaml")
        with open(self.yaml, "w", encoding="utf-8", newline="\n") as f:
            f.write(REGISTRY_YAML)
        self.rollen = auswertung.lies_rollen_registry(self.yaml)

    def tearDown(self):
        self.tmp.cleanup()

    def test_aufloesung_script_vor_typ_vor_default(self):
        """Die Reihenfolge steht im Kopf von `registry.yaml`; sie hier anders zu
        beantworten hiesse, zwei Wahrheiten zu fuehren. Verifiziert: SWR-140."""
        self.assertEqual(
            auswertung.geplante_kette(self.rollen, "PL", "board-hygiene"), ["script"])
        self.assertEqual(
            auswertung.geplante_kette(self.rollen, "PL", "status-zusammenfassung"),
            ["ollama", "claude"])
        self.assertEqual(
            auswertung.geplante_kette(self.rollen, "PL", "irgendwas-anderes"), ["claude"])

    def test_erste_stufe_passt(self):
        """Verifiziert: SWR-140."""
        r = auswertung.soll_ist([lauf(aufgaben_typ="sprint-planning",
                                      provider="claude")], self.rollen)
        self.assertEqual(r["zuordnungen"][0]["urteil"], auswertung.SOLL_IST_PASST)

    def test_provider_in_der_kette_ist_kein_verstoss(self):
        """⚠ Die Kette ist eine RUECKFALLLEITER (`on_unavailable: next_in_chain`). Wer
        `[ollama, claude]` plant und auf `claude` landet, hat sie benutzt, wie sie gemeint
        ist — ein roter Report darueber waere ein Dauerbefund ueber richtiges Verhalten
        und trainierte das Wegsehen an (SWR-131). Verifiziert: SWR-140."""
        r = auswertung.soll_ist([lauf(aufgaben_typ="status-zusammenfassung",
                                      provider="claude")], self.rollen)
        self.assertEqual(r["zuordnungen"][0]["urteil"],
                         auswertung.SOLL_IST_ABWEICHEND_MIT_GRUND)

    def test_provider_ausserhalb_der_kette_ist_abweichung(self):
        """Gegenprobe zur vorigen: ausserhalb der Kette IST es eine Abweichung — sonst
        waere das Urteil nutzlos. Verifiziert: SWR-140."""
        r = auswertung.soll_ist([lauf(aufgaben_typ="sprint-planning",
                                      provider="copilot")], self.rollen)
        self.assertEqual(r["zuordnungen"][0]["urteil"], auswertung.SOLL_IST_ABWEICHUNG)

    def test_lauf_ohne_aufgaben_typ_wird_genannt_und_mitgezaehlt(self):
        """⚠⚠ Der Kern: ein nicht zuordenbarer Lauf faellt NICHT aus dem Nenner. Ihn
        wegzulassen machte jede Quote besser, als sie ist — also genau die Luecke
        unsichtbar, um deren Sichtbarkeit es geht. Verifiziert: SWR-140."""
        r = auswertung.soll_ist([lauf(aufgaben_typ="sprint-planning"),
                                 lauf(aufgaben_typ="", ticket="T-0036")], self.rollen)
        self.assertEqual(r["n_gesamt"], 2)
        self.assertEqual(len(r["zuordnungen"]), 1)
        self.assertEqual(len(r["nicht_zuordenbar"]), 1)
        self.assertEqual(r["nicht_zuordenbar"][0]["ticket"], "T-0036")

    def test_unbekannte_rolle_ist_unbekannt_und_kein_verstoss(self):
        """Eine Rolle ohne Registry-Eintrag ist `unbekannt` — sie als Abweichung zu
        melden hiesse, eine fehlende Planung als Fehlverhalten zu buchen.
        Verifiziert: SWR-140."""
        r = auswertung.soll_ist([lauf(rolle="xyz")], self.rollen)
        self.assertEqual(r["zuordnungen"][0]["urteil"], auswertung.SOLL_IST_UNBEKANNT)


class BestandTest(unittest.TestCase):
    """Der Bestand wird NACHGEZAEHLT statt zitiert (SWR-140, wie SWR-137).

    ⚠ Der Tag, an dem ein Lauf Token meldet, macht diesen Test rot — und dann wird das
    TICKET korrigiert, statt dass die Zahl still im Bericht altert.
    """

    def setUp(self):
        self.wurzel = os.path.normpath(os.path.join(_HIER, "..", ".."))
        self.registry = os.path.join(self.wurzel, "p0", "management", "runs",
                                     "run-registry.jsonl")

    def test_bestand_traegt_noch_keine_token(self):
        """Verifiziert: SWR-140."""
        if not os.path.exists(self.registry):
            self.skipTest("Run-Registry am Bestand nicht vorhanden")
        eintraege, _ = auswertung.lies_registry(self.registry)
        self.assertTrue(eintraege, "Registry leer — der Befund waere ein anderer")
        a = auswertung.aggregat(eintraege, "token_statisch")
        self.assertEqual(
            a["n_gemessen"], 0,
            "Ein Lauf meldet jetzt Token — promt-team/T-0005 korrigieren, nicht "
            "diesen Test")

    def test_bericht_nennt_die_nicht_zuordenbaren_namentlich(self):
        """Der Report ist die Antwort auf `promt-team/N-0001`, und solange die Luecke
        besteht, ist er die BENANNTE Luecke. Verifiziert: SWR-140."""
        if not os.path.exists(self.registry):
            self.skipTest("Run-Registry am Bestand nicht vorhanden")
        text = auswertung.bericht(
            self.registry,
            os.path.join(self.wurzel, "process", "roles", "registry.yaml"))
        self.assertIn("NICHT GELIEFERT", text)
        self.assertIn("NICHT ZUORDENBAR", text)

    def test_unlesbare_zeile_wird_gezaehlt_nicht_verschwiegen(self):
        """Eine kaputte Zeile still zu ueberspringen verkleinert den Nenner — dieselbe
        Regel wie bei `nicht_zuordenbar`. Verifiziert: SWR-140."""
        with tempfile.TemporaryDirectory() as d:
            pfad = os.path.join(d, "r.jsonl")
            with open(pfad, "w", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(lauf()) + "\n{kaputt\n" + json.dumps(lauf()) + "\n")
            eintraege, kaputt = auswertung.lies_registry(pfad)
            self.assertEqual((len(eintraege), kaputt), (2, 1))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
