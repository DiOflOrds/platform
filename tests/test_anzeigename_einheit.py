#!/usr/bin/env python3
"""SWR-175 (p9/T-0008, Entscheidung `p9/D003` = A + Umbenennung): eine Einheit, die kein

Team ist, darf einen Anzeigenamen tragen.

⚠ Der Anlass ist eine Frage des Auftraggebers: *„kann dieses projekt geschlossen werden?
warum gibts das noch?"* (`p9/N-0001`). Gemessen: `p9` hat **7 von 7** Tickets `done` und
trotzdem **78 Commits in sieben Tagen**, weil in seinem Requirements-Ordner die
Anforderungen der ganzen Plattform liegen.

> **Keine Prüfung dieses Hauses fragt, ob der Name über einem Ordner noch stimmt. Gefunden
> hat es der Auftraggeber, nicht der Preflight.**

Er hat **A** entschieden — nichts zieht um — und dazu *„Nennen P9 in Org-Cockpit um"*.

⚠ **Der Ordner wird nicht umbenannt.** `p9` bleibt die Discovery-Kennung; geändert wird,
was ein Mensch liest. Diese Datei sichert **beides** zu: dass der Anzeigename ankommt und
dass die Kennung bleibt. Ohne die zweite Hälfte wäre eine Fassung, die den Ordner umbenennt
und damit jeden Querverweis bricht, von der richtigen nicht zu unterscheiden.
"""
import io
import os
import sys
import tempfile
import unittest

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PLATFORM, "scripts"))

import organigramm  # noqa: E402

_WURZEL = os.path.dirname(_PLATFORM)


def _einheit(root, kennung, steckbrief):
    p = os.path.join(root, kennung)
    os.makedirs(os.path.join(p, "tickets"))
    os.makedirs(os.path.join(p, ".git"))
    with io.open(os.path.join(p, "steckbrief.yaml"), "w", encoding="utf-8") as f:
        f.write(steckbrief)
    return p


def _wurzel(steckbriefe, teams_yaml="teams: {}\n"):
    tmp = tempfile.mkdtemp()
    for kennung, sb in steckbriefe.items():
        _einheit(tmp, kennung, sb)
    for unter in ("teams", "roles"):
        os.makedirs(os.path.join(tmp, "process", unter), exist_ok=True)
    with io.open(os.path.join(tmp, "process", "teams", "registry.yaml"), "w",
                 encoding="utf-8") as f:
        f.write(teams_yaml)
    for datei, inhalt in (("registry.yaml", "roles: {}\n"),
                          ("besetzungen.yaml", "besetzungen: {}\n")):
        with io.open(os.path.join(tmp, "process", "roles", datei), "w",
                     encoding="utf-8") as f:
            f.write(inhalt)
    return tmp


def _nach_kennung(daten):
    return {e["einheit"]: e for e in daten["einheiten"]}


class AnzeigenameTest(unittest.TestCase):
    """Die Rangfolge Team-Registry > Steckbrief > Ordnername, jede Stufe einzeln."""

    def test_steckbrief_name_schlaegt_den_ordnernamen(self):
        w = _wurzel({"p9": 'name: "Org-Cockpit"\nbeschreibung: "x"\nstatus: aktiv\n'})
        self.assertEqual(_nach_kennung(organigramm.sammle(w))["p9"]["anzeigename"],
                         "Org-Cockpit")

    def test_ohne_name_bleibt_der_ordnername(self):
        """⚠ Die Gegenprobe gegen den bequemen Bau: eine Fassung, die IMMER etwas

        anderes anzeigt, bestünde den Test darüber. Der Default muss der Ordnername sein.
        """
        w = _wurzel({"p8": 'beschreibung: "x"\nstatus: aktiv\n'})
        self.assertEqual(_nach_kennung(organigramm.sammle(w))["p8"]["anzeigename"], "p8")

    def test_leerer_name_zaehlt_nicht_als_name(self):
        w = _wurzel({"p7": 'name: "   "\nbeschreibung: "x"\nstatus: aktiv\n'})
        self.assertEqual(_nach_kennung(organigramm.sammle(w))["p7"]["anzeigename"], "p7")

    def test_die_team_registry_gewinnt_gegen_den_steckbrief(self):
        """Für ein Team ist `teams/registry.yaml` die Quelle der Wahrheit (Kopfkommentar

        der Registry). Gäbe der Steckbrief hier den Ausschlag, wären es zwei Quellen für
        denselben Namen — B033.
        """
        w = _wurzel({"platform": 'name: "Aus dem Steckbrief"\nbeschreibung: "x"\n'},
                    teams_yaml='teams:\n  aspice:\n    name: ASPICE-Team\n'
                               '    repo: platform\n    typ: aspice\n')
        self.assertEqual(_nach_kennung(organigramm.sammle(w))["platform"]["anzeigename"],
                         "ASPICE-Team")

    def test_die_kennung_bleibt_der_ordnername(self):
        """⚠⚠ Die zweite Hälfte des Paares und der eigentliche Sinn von Option A: die

        Identität ändert sich NICHT. `einheit` ist der Schlüssel, unter dem Tickets,
        Commits, Besetzungen und Querverweise stehen.
        """
        w = _wurzel({"p9": 'name: "Org-Cockpit"\nbeschreibung: "x"\nstatus: aktiv\n'})
        daten = organigramm.sammle(w)
        self.assertEqual([e["einheit"] for e in daten["einheiten"]], ["p9"])


class EchterBestandTest(unittest.TestCase):
    """Am Bestand dieses Hauses — die Anweisung des Auftraggebers, nachgemessen."""

    def test_p9_heisst_im_organigramm_org_cockpit(self):
        daten = _nach_kennung(organigramm.sammle(_WURZEL))
        self.assertIn("p9", daten, "die Discovery-Kennung p9 muss unverändert existieren")
        self.assertEqual(daten["p9"]["anzeigename"], "Org-Cockpit")

    def test_die_uebrigen_einheiten_sind_davon_unberuehrt(self):
        """⚠ Gegenprobe auf eine nicht-leere Grundmenge (SWR-128/165): eine Änderung, die

        allen Projekten einen Namen gäbe, wäre an `p9` allein nicht zu erkennen.
        """
        daten = _nach_kennung(organigramm.sammle(_WURZEL))
        self.assertGreater(len(daten), 10)
        for kennung in ("p0", "p1", "p8"):
            with self.subTest(einheit=kennung):
                self.assertEqual(daten[kennung]["anzeigename"], kennung)


if __name__ == "__main__":
    unittest.main()
