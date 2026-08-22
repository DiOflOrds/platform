# -*- coding: utf-8 -*-
"""SWR-220 (pm/T-0079, Brief N-0045, Entscheidung pm/B061): eine zulässige Abweichung
der Besetzung wird SICHTBAR — und ausdrücklich nicht zum Befund.

⚠⚠ Der Auftraggeber hat die einzige uneinheitliche Rolle dieses Hauses gefunden, bevor
es irgendein Werkzeug konnte. Gemessen am 2026-08-22: **86 Instanzen, 13 Rollen, genau
eine uneinheitlich** (`PROB`: 7× cowork, 1× ollama) — seine Beobachtung war exakt richtig
und exakt vollständig.
"""
import ast

import os
import sys

import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from backend import organisation  # noqa: E402
import preflight  # noqa: E402

_WURZEL = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


class _Register:
    """Register-Ersatz: `effektive_besetzungen` ist der EINZIGE Resolver (SWR-170)."""

    def __init__(self, testfall, besetzungen):
        self.t, self.b = testfall, besetzungen

    def __enter__(self):
        self._echt = organisation.organigramm.effektive_besetzungen
        organisation.organigramm.effektive_besetzungen = lambda root: self.b
        return self

    def __exit__(self, *a):
        organisation.organigramm.effektive_besetzungen = self._echt


def _inst(rolle, einheit, motor):
    return {"rolle": rolle, "einheit": einheit, "motor": motor}


class TestMotorAbweichungen(unittest.TestCase):

    def test_uneinheitliche_rolle_wird_namentlich_gemeldet(self):
        """Nicht „1 Abweichung", sondern welche Instanz auf welchem Motor läuft."""
        with _Register(self, {
                "PROB@platform": _inst("PROB", "platform", "ollama"),
                "PROB@p9": _inst("PROB", "p9", "cowork"),
                "PROB@pm": _inst("PROB", "pm", "cowork")}):
            abw = organisation.motor_abweichungen(".")
        self.assertEqual(list(abw), ["PROB"])
        self.assertEqual(abw["PROB"], {"cowork": ["PROB@p9", "PROB@pm"],
                                       "ollama": ["PROB@platform"]})

    def test_einheitliche_welt_meldet_nichts(self):
        """Sonst wäre die Zeile Rauschen und würde beim dritten Mal weggelesen."""
        with _Register(self, {"PROB@platform": _inst("PROB", "platform", "cowork"),
                              "PROB@p9": _inst("PROB", "p9", "cowork"),
                              "CM@p9": _inst("CM", "p9", "cowork")}):
            self.assertEqual(organisation.motor_abweichungen("."), {})

    def test_einzige_instanz_weicht_nicht_ab(self):
        """⚠ Die Falle dieser Prüfung: „einzig" ist nicht „abweichend".

        `MAIL-RED@team-mail` läuft auf `ollama` und ist die einzige Instanz seiner Rolle.
        Sie zu melden hieße, eine projektspezifische Rolle für uneinheitlich zu erklären,
        obwohl es niemanden gibt, mit dem sie uneinheitlich sein könnte.
        """
        with _Register(self, {"MAIL-RED@team-mail": _inst("MAIL-RED", "team-mail", "ollama"),
                              "PROB@p9": _inst("PROB", "p9", "cowork")}):
            self.assertEqual(organisation.motor_abweichungen("."), {})

    def test_mehr_als_zwei_motoren_werden_alle_genannt(self):
        """Eine Rolle auf drei Motoren darf nicht auf zwei gekürzt werden."""
        with _Register(self, {"CM@a": _inst("CM", "a", "cowork"),
                              "CM@b": _inst("CM", "b", "ollama"),
                              "CM@c": _inst("CM", "c", "script")}):
            self.assertEqual(sorted(organisation.motor_abweichungen(".")["CM"]),
                             ["cowork", "ollama", "script"])

    def test_am_echten_bestand_genau_eine_abweichung(self):
        """Die Messung, die `pm/B061` trägt — gegen den ECHTEN Bestand, nicht gegen ein Muster.

        ⚠ Schrumpft die Menge auf 0, wird dieser Test rot und zwingt dazu, die
        Entscheidung nachzulesen statt die Zahl stillschweigend anzupassen
        (Verfallsprüfung nach der `SWR-211`-Lehre).
        """
        # ⚠ Nach dem Sprintregister fragen, nicht nach `process/` — die CI von
        # `platform` checkt `process` mit aus, und eine halbe Organisation liefert
        # eine halbe Besetzungsmenge (grün hier, rot beim Auftraggeber).
        if not os.path.isfile(os.path.join(_WURZEL, "pm", "management", "sprints.jsonl")):
            self.skipTest("vollständige Arbeitskopie liegt hier nicht vor")
        abw = organisation.motor_abweichungen(_WURZEL)
        self.assertEqual(list(abw), ["PROB"],
                         "Ändert sich das, ist pm/B061 neu zu lesen — nicht der Test")
        self.assertEqual(abw["PROB"]["ollama"], ["PROB@platform"])
        self.assertGreater(len(abw["PROB"]["cowork"]), 1)

    def test_preflight_nennt_die_entscheidung_und_die_instanzen(self):
        """Eine Meldung ohne ihren Grund erzeugt beim Leser genau die Frage von N-0045."""
        echt = preflight.organisation.motor_abweichungen
        preflight.organisation.motor_abweichungen = lambda root: {
            "PROB": {"cowork": ["PROB@p9"], "ollama": ["PROB@platform"]}}
        try:
            zeilen = preflight.motor_zeilen(".")
        finally:
            preflight.organisation.motor_abweichungen = echt
        self.assertEqual(len(zeilen), 1)
        self.assertIn("PROB@platform", zeilen[0])
        self.assertIn("PROB@p9", zeilen[0])
        self.assertIn("pm/B061", zeilen[0])
        self.assertIn("kein Befund", zeilen[0])

    def test_einheitliche_welt_meldet_das_ausdruecklich(self):
        """„Einheitlich" muss dastehen — sonst ist Schweigen von Nichtprüfen ununterscheidbar."""
        echt = preflight.organisation.motor_abweichungen
        preflight.organisation.motor_abweichungen = lambda root: {}
        try:
            zeilen = preflight.motor_zeilen(".")
        finally:
            preflight.organisation.motor_abweichungen = echt
        self.assertEqual(len(zeilen), 1)
        self.assertIn("einheitlich", zeilen[0])

    def test_registerdefekt_ist_eine_auskunft_und_kein_absturz(self):
        """Ein Werkzeug, dessen Aufgabe das Melden ist, darf am Melden nicht sterben."""
        echt = preflight.organisation.motor_abweichungen

        def kaputt(root):
            raise ValueError("Register unlesbar")
        preflight.organisation.motor_abweichungen = kaputt
        try:
            zeilen = preflight.motor_zeilen(".")
        finally:
            preflight.organisation.motor_abweichungen = echt
        self.assertIn("nicht prüfbar", zeilen[0])

    def test_meldung_zaehlt_keinen_befund(self):
        """⚠ Der Kern von SWR-166: eine erlaubte Abweichung darf keinen Lauf anhalten.

        Rückbau-Wächter — käme im Aufrufer je ein `befunde += 1` daneben, bräche der
        Auto-Abschluss des Auftraggebers an einer Lage ab, die das PM beschlossen hat.
        """
        quelle = open(preflight.__file__, encoding="utf-8").read()
        baum = ast.parse(quelle)
        rumpf = next(k for k in ast.walk(baum)
                     if isinstance(k, ast.FunctionDef) and k.name == "motor_zeilen")
        self.assertNotIn("befunde", ast.get_source_segment(quelle, rumpf) or "")
        # und der Aufrufer verrechnet den Rückgabewert nicht
        for knoten in ast.walk(baum):
            if (isinstance(knoten, ast.AugAssign)
                    and isinstance(knoten.target, ast.Name)
                    and knoten.target.id == "befunde"):
                self.assertNotIn("motor_zeilen",
                                 ast.get_source_segment(quelle, knoten) or "")


if __name__ == "__main__":
    unittest.main()
