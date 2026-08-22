#!/usr/bin/env python3
"""SWR-216 (pm/T-0085): die nächste doppelte Projektkennung wird rot, die bestehende nicht.

⚠⚠ **Das Ticket hat in Sprint 35 die Frage gemessen, statt sie zu beantworten**, und die
Messung hat die Wahl gegenstandslos gemacht:

| Gemessen | Ergebnis |
|---|---|
| Zugriffe auf ein Feld `projekt` im Quelltext | **47** — alle meinen den **Einheitennamen** |
| `projekt:` aus `process/teams/registry.yaml` gelesen von | **nichts** (weder Python noch JS) |
| p-Nummern in `organigramm.json` | **0** |

> **Die Projektnummer hat keinen Leser. Sie ist eine Beschriftung in Berichten, keine
> Identität — die ist der Repo-/Ordnername (`SWR-175`, `p9/D003`).**

Damit sind beide naheliegenden Handlungen schlechter als das Bewachen: **Umnummerieren**
macht Berichte rückwirkend falsch, die der Auftraggeber gelesen hat; eine **blockierende
Kollisionsprüfung** stolperte beim ersten Lauf über die bestehende Dopplung — die Bauform,
die `SWR-166` dieses Haus 83 abgebrochene Läufe gekostet hat.

⚠⚠ **Und die Ausnahmeliste als Ausweg bringt ihre eigene Falle mit — `SWR-211`, Sprint 34:**
dort konnte die Ausnahme nie feuern, und ihre „Verfallsprüfung" mass etwas anderes als das,
was die Ausnahme verfallen ließe. Sie war spurlos löschbar.

**Deshalb ist die Grundmenge hier in BEIDE Richtungen zugesichert:**

* eine Kollision, die **nicht** im Altbestand steht, ist rot — der eigentliche Wächter;
* ein Eintrag des Altbestands, der **keine** Kollision mehr ist, ist **ebenfalls rot** —
  die Ausnahme muss mit der Wirklichkeit schrumpfen, sonst wird sie zum zweiten Namen für
  Grün.
"""
import os
import sys
import tempfile
import textwrap
import unittest

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PLATFORM)

from backend import organisation  # noqa: E402

_WURZEL = os.path.dirname(_PLATFORM)

#: Der Altbestand, gemessen am 2026-08-22 — **eine** Kollision, namentlich.
#: `pm/B060` hält fest, dass sie bewusst stehen bleibt. Sie darf nur schrumpfen.
ALTBESTAND = {"p13"}


def _welt(tmp, registry, ordner=()):
    os.makedirs(os.path.join(tmp, "process", "teams"), exist_ok=True)
    with open(os.path.join(tmp, "process", "teams", "registry.yaml"),
              "w", encoding="utf-8", newline="\n") as f:
        f.write(textwrap.dedent(registry).lstrip("\n"))
    for o in ordner:
        os.makedirs(os.path.join(tmp, "projects", o), exist_ok=True)


class KollisionenWerdenGefunden(unittest.TestCase):

    def test_registry_gegen_ordner(self):
        """Der echte Fall: `projects/p13` steht in KEINER Registry-Zeile.

        ⚠ Eine Prüfung, die nur die Registry liest, fände diese Dopplung nie — und genau
        so ist sie entstanden.
        """
        with tempfile.TemporaryDirectory() as tmp:
            _welt(tmp, """
                teams:
                  team-mail:
                    repo: team-mail
                    projekt: p13
                """, ordner=("p13", "p11"))
            k = organisation.projektkennung_kollisionen(tmp)
            self.assertEqual(sorted(k), ["p13"])
            self.assertEqual(len(k["p13"]), 2)
            self.assertTrue(any("ordner:projects/p13" in q for q in k["p13"]))
            self.assertTrue(any("registry:team-mail" in q for q in k["p13"]))

    def test_zwei_registry_zeilen_mit_derselben_nummer(self):
        """Die zweite Entstehungsart — sie hat es noch nie gegeben und wäre unsichtbar."""
        with tempfile.TemporaryDirectory() as tmp:
            _welt(tmp, """
                teams:
                  a:
                    repo: a
                    projekt: p20
                  b:
                    repo: b
                    projekt: p20
                """)
            self.assertEqual(sorted(organisation.projektkennung_kollisionen(tmp)), ["p20"])

    def test_saubere_welt_meldet_nichts(self):
        """Die zweite Hälfte des Paares — ohne sie bestünde ein Dauer-Alarm jeden Test."""
        with tempfile.TemporaryDirectory() as tmp:
            _welt(tmp, """
                teams:
                  team-mail:
                    repo: team-mail
                    projekt: p13
                """, ordner=("p11", "p12"))
            self.assertEqual(organisation.projektkennung_kollisionen(tmp), {})

    def test_ordner_ohne_p_nummer_zaehlt_nicht(self):
        """Nur `p<Ziffern>` ist eine Kennung — `projects/gemeinsam` ist ein Ordner.

        ⚠ **Diese Prüfung ist beim Gegenlesen der eigenen Mutationsprobe geschärft
        worden.** Die erste Fassung stellte `p13x` und `gemeinsam` neben eine echte
        `p13`-Kollision — und überlebte die Probe „jeder `p*`-Ordner ist eine Kennung"
        klaglos, weil `p13x` allein ja gar nicht kollidiert. **Sie prüfte die Ausgabe,
        nicht die Regel.** Jetzt steht `pilot` einer Registry-Zeile `projekt: pilot`
        gegenüber: mit der laxen Regel ist das eine Kollision, mit der richtigen nicht.
        """
        with tempfile.TemporaryDirectory() as tmp:
            _welt(tmp, """
                teams:
                  a:
                    repo: a
                    projekt: p13
                  b:
                    repo: b
                    projekt: pilot
                """, ordner=("p13x", "gemeinsam", "pilot", "p13"))
            k = organisation.projektkennung_kollisionen(tmp)
            self.assertEqual(sorted(k), ["p13"],
                             "nur p<Ziffern> ist eine Kennung — 'pilot' darf nicht "
                             "gegen den gleichnamigen Ordner kollidieren")

    def test_kennung_ohne_projekt_feld_ist_keine(self):
        """Ein leeres `projekt:` ist keine Kennung — sonst kollidierten alle Leeren."""
        with tempfile.TemporaryDirectory() as tmp:
            _welt(tmp, """
                teams:
                  a:
                    repo: a
                    projekt: ""
                  b:
                    repo: b
                """)
            self.assertEqual(organisation.projektkennung_kollisionen(tmp), {})


class AltbestandInBeideRichtungen(unittest.TestCase):
    """⚠⚠ Die Lehre aus `SWR-211`, hier von Anfang an eingebaut."""

    def test_keine_neue_dopplung_im_echten_bestand(self):
        """Der eigentliche Wächter: eine Kollision außerhalb des Altbestands ist rot."""
        ist = set(organisation.projektkennung_kollisionen(_WURZEL))
        neu = ist - ALTBESTAND
        self.assertEqual(neu, set(),
                         f"neue doppelte Projektkennung(en): {sorted(neu)} — die Identität "
                         f"ist der Repo-/Ordnername (SWR-175), die Nummer nur eine "
                         f"Beschriftung (pm/B060). Eine neue Dopplung ist ein Versehen, "
                         f"kein Altbestand.")

    def test_altbestand_schrumpft_mit_der_wirklichkeit(self):
        """⚠ Die Verfallsprüfung misst GENAU das, was die Ausnahme verfallen ließe.

        `SWR-211` hatte eine, die etwas anderes mass — die Ausnahme war spurlos löschbar
        und damit ein zweiter Name für Grün. Wird `p13` je aufgelöst, wird **dieser** Test
        rot und verlangt, dass `ALTBESTAND` mit der Wirklichkeit schrumpft.
        """
        ist = set(organisation.projektkennung_kollisionen(_WURZEL))
        verfallen = ALTBESTAND - ist
        self.assertEqual(verfallen, set(),
                         f"Altbestand nennt Kennung(en), die keine Kollision mehr sind: "
                         f"{sorted(verfallen)} — aus ALTBESTAND entfernen.")

    def test_altbestand_ist_nicht_leer_und_nicht_alles(self):
        """Eine Grundmenge, die nie feuern kann, ist keine Zusicherung (`SWR-211`)."""
        self.assertTrue(ALTBESTAND, "ohne Altbestand wäre der Wächter ein Dauerbefund")
        with tempfile.TemporaryDirectory() as tmp:
            _welt(tmp, """
                teams:
                  a:
                    repo: a
                    projekt: p99
                """, ordner=("p99",))
            self.assertNotIn("p99", ALTBESTAND,
                             "eine erfundene Kollision darf nicht im Altbestand stehen")
            self.assertEqual(sorted(organisation.projektkennung_kollisionen(tmp)), ["p99"],
                             "die Prüfung muss eine erfundene Dopplung sehen — sonst "
                             "beweist der grüne Bestand nichts")


if __name__ == "__main__":
    unittest.main()
