#!/usr/bin/env python3
"""SWR-171/172 (platform/T-0033): der Tick prüft die BESETZUNG, bevor er den Gateway ruft.

⚠⚠ Der Anlass ist der Lauf vom 2026-08-20 um 21:30, den Sprint 26 nicht geplant hatte.
`SWR-169` holt das Ollama-Modell aus dem Besetzungsregister und ist dort in **vier**
Gegenproben belegt. Es hat trotzdem null Wirkung gehabt:

    Gateway: status=fehler … artefakte=[]
    Tick OHNE ERGEBNIS (status=fehler, artefakte=0): ollama: Anfrage fehlgeschlagen (404):
      {"error":"model 'llama3.1:8b' not found"}

`pm/D010` hat den Schnelltakt je **Besetzung** entschieden (`platform/PROB`,
`team-mail/MAIL-RED`); `ollama-schnelltakt.cmd` übergibt nur die **Einheit**. Gezogen
wurden `CM@platform` und `DEV@team-mail`, und für die steht im Register kein Modell.

> **⚠⚠ Alle vier Gegenproben von `platform/T-0032` prüften die Auflösungsfunktion, keine
> ihren Aufrufer. Eine Gegenprobe, die die Funktion prüft und nicht ihren Aufrufer, misst
> die Hälfte, die man selbst geschrieben hat.**

⚠ **Deshalb steht hier ein LAUF und nicht nur eine Funktionsprüfung.** `test_tick_bricht…`
ruft `tick.tick()` über einen echten Ticketbestand und beobachtet, ob `gateway.execute`
überhaupt gerufen wird — genau die Stelle, an der die letzte Runde blind war.

⚠ Und jede Zusicherung ist ein **Paar**: neben „die falsche Besetzung wird abgewiesen"
steht „die richtige läuft durch". Ohne die zweite Hälfte bestünde eine Fassung, die
**immer** abbricht, jeden Test hier.
"""
import os
import sys
import tempfile
import textwrap
import unittest

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PLATFORM)
sys.path.insert(0, os.path.join(_PLATFORM, "scripts"))
sys.path.insert(0, os.path.join(_PLATFORM, "orchestrator"))

from backend import organisation  # noqa: E402
from orchestrator import tick as tick_mod  # noqa: E402

_WURZEL = os.path.dirname(_PLATFORM)

BESETZUNGEN = """
    besetzungen:
      PROB@aspice:
        rolle: PROB
        einheit: platform
        motor: ollama
        modell: gemma3:27b
        takt: schnell
        status: aktiv
      CM@aspice:
        rolle: CM
        einheit: platform
        motor: cowork
        takt: sprint
        status: aktiv
    """

REGISTRY = """
    roles:
      CM:
        besetzung: ki
        status: active
        provider_chain: [claude]
      PROB:
        besetzung: ki
        status: active
        provider_chain: [ollama]
    """

TICKET = """\
---
id: {tid}
titel: "{titel}"
typ: task
prozess: sup8
rolle: {rolle}
sprint: 27
status: open
prio: hoch
blocked_by: []
repo: platform
reviewer: qm
geändert: 2026-08-20
geplant_sprint: 27
erstellt: 2026-08-20
---

Rumpf.
"""


def _baue_wurzel(tickets):
    """Minimalwurzel: process/roles/*, guardrails.yaml und ein platform/tickets/-Bestand."""
    tmp = tempfile.mkdtemp()
    rollen = os.path.join(tmp, "process", "roles")
    os.makedirs(rollen)
    with open(os.path.join(rollen, "besetzungen.yaml"), "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(BESETZUNGEN))
    with open(os.path.join(rollen, "registry.yaml"), "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(REGISTRY))
    cfg = os.path.join(tmp, "platform", "orchestrator", "config")
    os.makedirs(cfg)
    with open(os.path.join(cfg, "guardrails.yaml"), "w", encoding="utf-8") as f:
        f.write("providers:\n  ollama:\n    model: llama3.1:8b\n")
    tdir = os.path.join(tmp, "platform", "tickets")
    os.makedirs(tdir)
    for tid, rolle, titel in tickets:
        with open(os.path.join(tdir, tid + ".md"), "w", encoding="utf-8") as f:
            f.write(TICKET.format(tid=tid, rolle=rolle, titel=titel))
    return tmp


# ---------------------------------------------------------------- SWR-171: die Funktion

class BesetzungMitMotorTest(unittest.TestCase):
    """Die Auflösung selbst — die Hälfte, die letztes Mal auch stimmte."""

    def test_rolle_mit_ollama_besetzung_wird_gefunden(self):
        w = _baue_wurzel([])
        self.assertEqual(
            organisation.besetzung_mit_motor(w, "PROB", "platform", "ollama"), "PROB@aspice")

    def test_cowork_rolle_hat_keine_ollama_besetzung(self):
        w = _baue_wurzel([])
        self.assertEqual(
            organisation.besetzung_mit_motor(w, "CM", "platform", "ollama"), "")

    def test_rolle_ohne_jede_besetzung_in_dieser_einheit(self):
        """⚠ Der Fall aus dem Betrieb, den bisher niemand benannt hat: `DEV@team-mail`

        gibt es im Register **überhaupt nicht** — der Tick hat einer Instanz Arbeit
        gegeben, die niemand besetzt. Der leere Modellname war die Folge, nicht die Ursache.
        """
        w = _baue_wurzel([])
        self.assertEqual(
            organisation.besetzung_mit_motor(w, "DEV", "team-mail", "ollama"), "")

    def test_dieselbe_rolle_in_einer_anderen_einheit_zaehlt_nicht(self):
        w = _baue_wurzel([])
        self.assertEqual(
            organisation.besetzung_mit_motor(w, "PROB", "team-mail", "ollama"), "")

    def test_grundmenge_ist_nicht_leer(self):
        """⚠ Gegenprobe gegen SWR-128: eine Prüfung, die das Register gar nicht liest,

        findet ebenfalls keine Besetzung und wäre damit ununterscheidbar.
        """
        self.assertEqual(organisation.besetzungen_mit_motor(_baue_wurzel([]), "ollama"),
                         ["PROB@aspice"])


class MotorZuordnungTest(unittest.TestCase):
    """⚠ Die Zuordnung Provider → Motor ist absichtlich unvollständig und benannt."""

    def test_ollama_ist_zugeordnet(self):
        self.assertEqual(organisation.MOTOR_JE_PROVIDER.get("ollama"), "ollama")

    def test_claude_ist_bewusst_nicht_zugeordnet(self):
        """`claude`/`copilot` heißen im Besetzungsregister `cowork`, und ob das einen

        Claude-Aufruf meint oder einen Menschen an der Tastatur, steht nirgends. Eine
        erfundene Zeile wäre die Semantik, die `platform/T-0033` als Option 2 verworfen hat.
        """
        for p in ("claude", "copilot", "session"):
            with self.subTest(provider=p):
                self.assertIsNone(organisation.MOTOR_JE_PROVIDER.get(p))


class BesetzungsbefundTest(unittest.TestCase):
    """SWR-171: der Befund, den der Tick meldet — mit seinem Gegenstück."""

    def test_falsche_besetzung_liefert_einen_befund_der_rolle_und_einheit_nennt(self):
        w = _baue_wurzel([])
        befund = tick_mod.besetzungsbefund(w, "CM", "platform", "ollama")
        self.assertTrue(befund)
        self.assertIn("CM", befund)
        self.assertIn("platform", befund)
        self.assertIn("ollama", befund)
        self.assertIn("PROB@aspice", befund)   # was STATT dessen besetzt ist

    def test_richtige_besetzung_liefert_keinen_befund(self):
        w = _baue_wurzel([])
        self.assertEqual(tick_mod.besetzungsbefund(w, "PROB", "platform", "ollama"), "")

    def test_ohne_provider_override_greift_die_pruefung_nicht(self):
        """⚠ Ohne `--provider` gilt die Provider-Kette der Rolle aus `registry.yaml`, und

        über die hat das Besetzungsregister nichts zu sagen. Griffe die Prüfung auch hier,
        stünde der Session-Lauf dieses Hauses ab sofort still.
        """
        w = _baue_wurzel([])
        for p in (None, "", "claude", "session"):
            with self.subTest(provider=p):
                self.assertEqual(tick_mod.besetzungsbefund(w, "CM", "platform", p), "")


# ------------------------------------------------------- SWR-171: der AUFRUFER, im Lauf

class _GatewaySpion:
    """Merkt sich, ob `execute` gerufen wurde — und mit welchem Modellnamen."""

    def __init__(self):
        self.aufrufe = []

    def execute(self, rolle, aufgabe, kontext):
        self.aufrufe.append((rolle, kontext.get("modell_name")))
        raise AssertionError("execute hätte nicht gerufen werden dürfen")


class TickAufruferTest(unittest.TestCase):
    """⚠ Der Lauf, den `platform/T-0033` DoD 3 verlangt: geprüft wird der Kontext, mit dem

    `gateway.execute` **tatsächlich** gerufen wird — nicht die Funktion, die ihn bildet.
    """

    def setUp(self):
        self.gateway_orig = tick_mod.gateway
        self.git_orig = tick_mod.git
        self.git_aufrufe = []

        def _git(repo, *a, **kw):
            # ⚠ `status --porcelain` muss LEER antworten, sonst hält `arbeitskopie_sauber`
            # die Wurzel für schmutzig und der Lauf endet vor der geprüften Stelle. Genau
            # daran ist der erste Entwurf dieses Tests gescheitert — und das ist der Beleg,
            # dass er wirklich durch `tick()` läuft und nicht an ihm vorbei.
            self.git_aufrufe.append(a)
            return "" if a[:1] == ("status",) else "main"

        tick_mod.git = _git

    def tearDown(self):
        tick_mod.gateway = self.gateway_orig
        tick_mod.git = self.git_orig

    def test_tick_bricht_vor_dem_gateway_ab_wenn_die_rolle_nicht_ollama_besetzt_ist(self):
        w = _baue_wurzel([("T-0001", "cm", "Ein CM-Ticket")])
        spion = _GatewaySpion()
        tick_mod.gateway = spion
        rc = tick_mod.tick(w, projekt="platform", provider="ollama")
        self.assertEqual(rc, 0, "der Lauf ist nicht kaputt — es gibt nichts zu tun")
        self.assertEqual(spion.aufrufe, [], "der Gateway wurde trotz falscher Besetzung gerufen")
        self.assertEqual(self.git_aufrufe, [], "es wurde ein Branch angelegt oder committet")

    def test_das_ticket_bleibt_dabei_unangetastet(self):
        """⚠ Die zweite Hälfte des Schadens vom 20.08.: ein Tick, der scheitert, hatte den

        Status vorher schon auf `in_progress` gesetzt. Hier darf die Datei sich nicht
        ändern — der Abbruch steht **vor** jedem Schreibvorgang.
        """
        w = _baue_wurzel([("T-0001", "cm", "Ein CM-Ticket")])
        pfad = os.path.join(w, "platform", "tickets", "T-0001.md")
        with open(pfad, encoding="utf-8") as f:
            vorher = f.read()
        tick_mod.gateway = _GatewaySpion()
        tick_mod.tick(w, projekt="platform", provider="ollama")
        with open(pfad, encoding="utf-8") as f:
            self.assertEqual(f.read(), vorher)

    def test_die_richtige_besetzung_kommt_bis_zum_gateway_und_mit_ihrem_modell(self):
        """⚠⚠ Ohne dieses Paar bestünde eine Fassung, die **immer** abbricht, jeden Test

        oben — und das wäre exakt der Fehler dieses Tickets ein zweites Mal, nur mit
        umgekehrtem Vorzeichen. Geprüft wird zugleich, dass `modell_name` am Aufrufer
        **nicht leer** ist: das ist die Zusicherung, die am 20.08. gefehlt hat.
        """
        w = _baue_wurzel([("T-0001", "prob", "Ein PROB-Ticket")])
        gesehen = {}

        class _Erfolgreich:
            def execute(self, rolle, aufgabe, kontext):
                gesehen["rolle"] = rolle
                gesehen["modell_name"] = kontext.get("modell_name")
                raise RuntimeError("bis hierher und nicht weiter")

        tick_mod.gateway = _Erfolgreich()
        with self.assertRaises(RuntimeError):
            tick_mod.tick(w, projekt="platform", provider="ollama")
        self.assertEqual(gesehen.get("rolle"), "prob")
        self.assertEqual(gesehen.get("modell_name"), "gemma3:27b")


# ---------------------------------------------------------------- SWR-172: der Schalter

class RollenFilterTest(unittest.TestCase):
    """SWR-172: `--rolle` macht ausdrückbar, was `pm/D010` entschieden hat."""

    REGISTRY_DICT = {"CM": {"besetzung": "ki", "status": "active"},
                     "PROB": {"besetzung": "ki", "status": "active"}}

    def _tickets(self):
        return [{"id": "T-0001", "status": "open", "rolle": "cm", "prio": "hoch",
                 "blocked_by": []},
                {"id": "T-0002", "status": "open", "rolle": "prob", "prio": "mittel",
                 "blocked_by": []}]

    def test_ohne_filter_gewinnt_die_prio(self):
        t, _ = tick_mod.waehle_ticket(self._tickets(), self.REGISTRY_DICT)
        self.assertEqual(t["id"], "T-0001")

    def test_mit_filter_wird_die_besetzte_rolle_gezogen(self):
        t, _ = tick_mod.waehle_ticket(self._tickets(), self.REGISTRY_DICT, nur_rolle="PROB")
        self.assertEqual(t["id"], "T-0002")

    def test_filter_ohne_treffer_liefert_nichts_statt_irgendetwas(self):
        """⚠ Die ehrliche Antwort auf den heutigen Bestand: **kein** offenes Ticket trägt

        eine ollama-besetzte Rolle. Ein Filter, der dann das nächstbeste Ticket zurückgibt,
        wäre genau der Fehler, gegen den dieses Ticket gebaut ist.
        """
        self.assertIsNone(
            tick_mod.waehle_ticket(self._tickets(), self.REGISTRY_DICT, nur_rolle="ARCH")[0])

    def test_der_schalter_ist_gebaut_und_nicht_umgelegt(self):
        """⚠⚠ `ollama-schnelltakt.cmd` bleibt unverändert, bis der Auftraggeber entschieden

        hat (`platform/T-0035`). Es ist **seine** alle 15 Minuten laufende Automatik, und
        gemessen am Bestand vom 20.08. wäre die Einschränkung heute eine Abschaltung: 0 von
        14 offenen Tickets tragen eine ollama-besetzte Rolle.

        > **Eine Änderung, die in einem Lauf nicht ganz zu tragen ist, gehört nicht an
        > dessen Ende.**
        """
        pfad = os.path.join(_WURZEL, "ollama-schnelltakt.cmd")
        if not os.path.isfile(pfad):     # ⚠ nicht im Repo — dann ist nichts zuzusichern
            self.skipTest("ollama-schnelltakt.cmd nicht vorhanden")
        with open(pfad, encoding="utf-8", errors="replace") as f:
            self.assertNotIn("--rolle", f.read())


# ----------------------------------------------------------------- am ECHTEN Bestand

class EchterBestandTest(unittest.TestCase):
    """⚠ Am Bestand dieses Hauses, nicht an einer gebauten Wurzel — die Lehre aus dem

    Fehlversuch von Sprint 26, in dem `MAIL-RED@mail` aus dem Team-Kürzel **gebildet**
    statt aus dem Register **gelesen** war (die Instanz heißt `MAIL-RED@team-mail`).

    ⚠⚠ **Sprint 28: `PROB@aspice` → `PROB@platform`.** Der Projektmodell-Rework hat den
    Instanzschlüssel im Register nachgezogen (HEAD trug den Schlüssel `@aspice` bei
    `einheit: platform` — zwei Namen für eine Sache) und diese Klasse nicht gefahren. Die
    Literale hier sind **weiterhin abgelesen und absichtlich nicht abgeleitet**: sie sind
    die einzige Stelle, an der eine Umbenennung im Register überhaupt auffällt. Die
    strukturelle Hälfte steht als SWR-189 in `test_modellaufloesung`.
    """

    def test_die_beiden_schnelltakt_besetzungen_stehen_im_register(self):
        self.assertEqual(organisation.besetzungen_mit_motor(_WURZEL, "ollama"),
                         ["MAIL-RED@team-mail", "PROB@platform"])

    def test_genau_die_rollen_die_der_tick_gezogen_hat_sind_nicht_ollama_besetzt(self):
        """⚠⚠ Die beiden Instanzen aus dem Lauf vom 20.08. um 21:30, namentlich."""
        self.assertEqual(
            organisation.besetzung_mit_motor(_WURZEL, "CM", "platform", "ollama"), "")
        self.assertEqual(
            organisation.besetzung_mit_motor(_WURZEL, "DEV", "team-mail", "ollama"), "")

    def test_und_die_richtigen_beiden_werden_gefunden(self):
        self.assertEqual(
            organisation.besetzung_mit_motor(_WURZEL, "PROB", "platform", "ollama"),
            "PROB@platform")
        self.assertEqual(
            organisation.besetzung_mit_motor(_WURZEL, "MAIL-RED", "team-mail", "ollama"),
            "MAIL-RED@team-mail")


if __name__ == "__main__":
    unittest.main()
