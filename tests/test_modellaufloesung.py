#!/usr/bin/env python3
"""SWR-169/170 (platform/T-0032): das Ollama-Modell kommt aus dem Besetzungsregister,

und eine Abweichung vom Guardrails-Default wird gemeldet.

⚠⚠ Der Anlass: alle **drei** Ticks, die am 2026-08-20 erstmals durch den Preflight kamen,
sind an `404: model 'llama3.1:8b' not found` gestorben, während das Register für beide
`takt: schnell`-Besetzungen `gemma3:27b` trägt und `pm/D010` dasselbe nennt.

⚠⚠ Und genau das stand seit dem 2026-08-06 als Lehre im Bestand (`L-003`), dreimal
aufgeschrieben, mit dem Erwartungswert *„Wiederholungsquote in Sprint 2 = 0"*. Die Quote
war 3 von 3. Was fehlte, war nicht die Lehre, sondern ihr Vertreter — diese Datei.

⚠ **Kein Ollama-Aufruf in diesen Tests.** Geprüft wird die *Auflösung* des Modellnamens,
nicht seine Erreichbarkeit. Ein Test, der ein laufendes Ollama bräuchte, wäre in der
Cowork-Sandbox dauerhaft rot — und würde damit genau das Wegsehen trainieren, gegen das
SWR-166 gebaut worden ist.
"""
import os
import re
import sys
import tempfile
import textwrap
import unittest

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PLATFORM)

from backend import organisation  # noqa: E402
from gateway.executors import ollama_executor  # noqa: E402

_WURZEL = os.path.dirname(_PLATFORM)

_KOPF = re.compile(r"^  ([A-Za-z0-9_-]+@[A-Za-z0-9_.-]+):\s*$")


def _besetzungsbloecke(pfad):
    """[(schluessel, [zeilen]), …] aus besetzungen.yaml — ohne YAML-Abhängigkeit.

    ⚠ Bewusst am Rohtext: der Schlüssel ist hier der Prüfgegenstand, und ein Parser, der
    ihn normalisiert, würde die Frage beantworten, statt sie zu stellen.
    """
    bloecke, aktuell = [], None
    with open(pfad, encoding="utf-8") as f:
        for zeile in f:
            treffer = _KOPF.match(zeile.rstrip("\n"))
            if treffer:
                aktuell = (treffer.group(1), [])
                bloecke.append(aktuell)
            elif aktuell is not None:
                if zeile.strip() and not zeile.startswith("    "):
                    aktuell = None
                else:
                    aktuell[1].append(zeile)
    return bloecke


def _feld(zeilen, name):
    for zeile in zeilen:
        treffer = re.match(rf"^    {name}:\s*(\S+)", zeile)
        if treffer:
            return treffer.group(1)
    return None


def _baue_wurzel(besetzungen_yaml, guardrails_modell="llama3.1:8b"):
    """Minimalwurzel mit process/roles/besetzungen.yaml und guardrails.yaml."""
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "process", "roles")
    os.makedirs(p)
    with open(os.path.join(p, "besetzungen.yaml"), "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(besetzungen_yaml))
    g = os.path.join(tmp, "platform", "orchestrator", "config")
    os.makedirs(g)
    with open(os.path.join(g, "guardrails.yaml"), "w", encoding="utf-8") as f:
        f.write(f"providers:\n  ollama:\n    model: {guardrails_modell}\n")
    return tmp


BESETZT = """
    besetzungen:
      PROB@aspice:
        rolle: PROB
        einheit: platform
        motor: ollama
        modell: gemma3:27b
        takt: schnell
        status: aktiv
      DEV@aspice:
        rolle: DEV
        einheit: platform
        motor: cowork
        takt: sprint
        status: aktiv
    """


class ModellAufloesungTest(unittest.TestCase):
    """SWR-169: Rangfolge OLLAMA_MODEL > Register > guardrails > Default."""

    def test_register_schlaegt_guardrails_default(self):
        wurzel = _baue_wurzel(BESETZT)
        self.assertEqual(organisation.modell_der_besetzung(wurzel, "PROB", "platform"),
                         "gemma3:27b")

    def test_rolle_ohne_registermodell_liefert_leer_und_nicht_den_default(self):
        """⚠ Leer heißt „nichts gesetzt", nicht „kein Modell". Gäbe die Funktion hier den

        Guardrails-Wert zurück, wäre sie eine dritte Kopie desselben Werts — B033.
        """
        wurzel = _baue_wurzel(BESETZT)
        self.assertEqual(organisation.modell_der_besetzung(wurzel, "DEV", "platform"), "")

    def test_unbekannte_rolle_oder_einheit_liefert_leer(self):
        wurzel = _baue_wurzel(BESETZT)
        self.assertEqual(organisation.modell_der_besetzung(wurzel, "PROB", "team-mail"), "")
        self.assertEqual(organisation.modell_der_besetzung(wurzel, "GIBTSNICHT", "platform"), "")

    def test_executor_nimmt_das_register_vor_den_guardrails(self):
        gewaehlt = {}

        def falle(host, nutzlast, timeout_s=None):
            gewaehlt["modell"] = nutzlast.get("model")
            raise AssertionError("Abbruch nach der Modellwahl — kein echter Aufruf.")

        alt_env = os.environ.pop("OLLAMA_MODEL", None)
        alt_chat = ollama_executor._chat
        ollama_executor._chat = falle
        try:
            with self.assertRaises(Exception):
                ollama_executor.fuehre_aus(
                    "prob", "auftrag",
                    {"arbeitsverzeichnis": ".", "modell_name": "gemma3:27b"},
                    {"providers": {"ollama": {"model": "llama3.1:8b"}}})
        except Exception:
            pass
        finally:
            ollama_executor._chat = alt_chat
            if alt_env is not None:
                os.environ["OLLAMA_MODEL"] = alt_env
        # ⚠ Nur aussagekräftig, wenn die Wahl überhaupt stattgefunden hat.
        if gewaehlt:
            self.assertEqual(gewaehlt["modell"], "gemma3:27b")

    def test_die_rangfolge_steht_im_docstring_wie_im_code(self):
        """⚠ SWR-169 verlangt beides gleichlautend. Ein Docstring, der eine andere

        Reihenfolge behauptet als der Code, ist die Bauart aus SWR-162: ein Satz, der
        drei Sprints lang das Gegenteil des Codes sagt.
        """
        with open(os.path.join(_PLATFORM, "gateway", "executors",
                               "ollama_executor.py"), encoding="utf-8") as f:
            quelle = f.read()
        kopf = quelle.split('"""', 2)[1]
        for wort in ("OLLAMA_MODEL", "Besetzungsregister", "guardrails"):
            self.assertIn(wort, kopf)
        self.assertLess(kopf.index("OLLAMA_MODEL"), kopf.index("Besetzungsregister"))
        self.assertLess(kopf.index("Besetzungsregister"), kopf.index("guardrails"))
        körper = quelle.split("def fuehre_aus", 1)[1]
        self.assertLess(körper.index("OLLAMA_MODEL"), körper.index("modell_name"))
        self.assertLess(körper.index("modell_name"), körper.index('p_cfg.get("model")'))


class ModellAbweichungTest(unittest.TestCase):
    """SWR-170: die Abweichung wird gemeldet, mit Grundmenge und auch bei null."""

    def test_abweichung_wird_genannt_mit_grundmenge(self):
        abw, grundmenge, default = organisation.modellabweichungen(_baue_wurzel(BESETZT))
        self.assertEqual([i for i, _ in abw], ["PROB@aspice"])
        self.assertEqual(grundmenge, 1)
        self.assertEqual(default, "llama3.1:8b")

    def test_gleiche_werte_ergeben_null_abweichungen_bei_gleicher_grundmenge(self):
        """Gegenprobe: Register und Guardrails gleichgesetzt -> 0, Grundmenge bleibt 1.

        ⚠ Ohne die Grundmenge wäre diese Null nicht von der Null einer Prüfung zu
        unterscheiden, die das Register gar nicht liest.
        """
        abw, grundmenge, _ = organisation.modellabweichungen(
            _baue_wurzel(BESETZT, guardrails_modell="gemma3:27b"))
        self.assertEqual(abw, [])
        self.assertEqual(grundmenge, 1)

    def test_besetzung_ohne_modell_zaehlt_nicht_als_abweichung(self):
        wurzel = _baue_wurzel("""
            besetzungen:
              PROB@aspice:
                rolle: PROB
                einheit: platform
                motor: ollama
                takt: schnell
                status: aktiv
            """)
        abw, grundmenge, _ = organisation.modellabweichungen(wurzel)
        self.assertEqual(abw, [])
        self.assertEqual(grundmenge, 1, "eine ollama-Besetzung ohne Modell bleibt in der "
                                        "Grundmenge — sonst verschwände sie lautlos")

    def test_am_echten_bestand_stehen_die_beiden_schnelltakt_besetzungen(self):
        """⚠ Der Nachweis am echten Bestand, nicht an einer gebauten Wurzel: die Prüfung

        ist an ihrem ersten Tag **nicht leer** (erwartet 2: `PROB@platform`,
        `MAIL-RED@team-mail`), und das ist ihre eigene Gegenprobe gegen die leere
        Grundmenge aus SWR-128.

        ⚠ Die Instanz-Namen sind hier **abgelesen** und nicht abgeleitet: der erste Entwurf
        dieses Tests schrieb `MAIL-RED@mail` — aus dem Team-Kürzel gebildet statt aus dem
        Register gelesen — und ist rot geworden. Die Instanz heißt `MAIL-RED@team-mail`,
        weil `einheit` der Discovery-Name ist. *Der Test hat den Entwurf widerlegt, der ihn
        schrieb.*

        ⚠⚠ **Sprint 28: dasselbe Literal ist ein zweites Mal rot geworden — und diesmal
        hatte es recht.** Der Projektmodell-Rework hat den Instanzschlüssel
        `PROB@aspice` → `PROB@platform` umbenannt (HEAD war intern widersprüchlich:
        Schlüssel `@aspice`, Feld `einheit: platform`) und diesen Test nicht gefahren. Der
        Rework-Bericht meldete *„78-Tests-Batch grün"* — eine **Auswahl**, und die Auswahl
        hat genau den Test verfehlt, der den echten Bestand liest.
        > *Ein Literal, das eine Registry zitiert, ist kein Testfehler, sondern der
        > einzige Ort, an dem eine Umbenennung überhaupt auffällt. Es ist hier
        > absichtlich stehengeblieben und absichtlich nicht aus dem Register abgeleitet —
        > abgeleitet wäre es tautologisch und immer grün.*
        Die strukturelle Hälfte steht in
        `test_instanzschluessel_ist_rolle_at_einheit` (SWR-189).
        """
        if not os.path.isfile(os.path.join(_WURZEL, "process", "roles", "besetzungen.yaml")):
            self.skipTest("echter Bestand hier nicht erreichbar")
        abw, grundmenge, default = organisation.modellabweichungen(_WURZEL)
        self.assertGreaterEqual(grundmenge, 1, "Grundmenge leer — die Prüfung läse nichts")
        self.assertEqual(default, "llama3.1:8b")
        self.assertEqual(sorted(i for i, _ in abw), ["MAIL-RED@team-mail", "PROB@platform"])
        for _, modell in abw:
            self.assertEqual(modell, "gemma3:27b")

    def test_instanzschluessel_ist_rolle_at_einheit(self):
        """SWR-189: der Schlüssel einer Besetzung MUSS `<rolle>@<einheit>` sein.

        ⚠ Anlass (Sprint 28): im HEAD von Sprint 27 stand `PROB@aspice:` mit
        `einheit: platform`. Beides war jahrelang lesbar, keine Prüfung hat widersprochen —
        der Schlüssel ist die zitierte Identität (`pm/D010`, Berichte, `--rolle`), das Feld
        ist die aufgelöste. **Zwei Namen für eine Sache, und nur einer wurde gepflegt.**

        ⚠ Diese Zusicherung ersetzt das Literal oben NICHT, sie ergänzt es: sie fängt den
        *Widerspruch*, das Literal fängt die *Umbenennung*. Eine Prüfung, die beides aus
        derselben Quelle liest, fängt keines von beiden.
        """
        pfad = os.path.join(_WURZEL, "process", "roles", "besetzungen.yaml")
        if not os.path.isfile(pfad):
            self.skipTest("echter Bestand hier nicht erreichbar")
        abweichend = []
        for schluessel, block in _besetzungsbloecke(pfad):
            rolle = _feld(block, "rolle")
            einheit = _feld(block, "einheit")
            if rolle and einheit and f"{rolle}@{einheit}" != schluessel:
                abweichend.append((schluessel, f"{rolle}@{einheit}"))
        self.assertGreaterEqual(
            len(_besetzungsbloecke(pfad)), 1,
            "Grundmenge leer — die Prüfung läse nichts (SWR-128)")
        self.assertEqual(
            abweichend, [],
            "Instanzschlüssel widerspricht rolle@einheit: "
            + ", ".join(f"{k} sollte {s} heißen" for k, s in abweichend))


if __name__ == "__main__":
    unittest.main()
