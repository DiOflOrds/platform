#!/usr/bin/env python3
"""SWR-214 (platform/T-0066): der leere Takt-Bestand wird GEMELDET statt wiederholt.

⚠⚠ **Der Anlass ist keine Fehlfunktion, sondern eine korrekte Meldung ohne Leser.**
`ollama-schnelltakt.cmd` läuft auf `DESKTOP-8OOO6JS` im 15-Minuten-Takt und schreibt seit
Sprint 26 wörtlich:

    Kein bearbeitbares Ticket (Besetzung): 3 offene(s) Ticket(s) geprüft, keines trägt
    eine Rolle mit motor 'ollama' in Einheit 'platform'

**87 Läufe, 87 mal dieselbe wahre Aussage, null Wirkung.** Der Satz stand im Protokoll
eines Dienstes; gelesen wird das Preflight. Diese Datei sichert deshalb zwei Dinge, die
man leicht für eines hält: dass die **Messung** stimmt, und dass sie an der Stelle
**auftaucht**, an der jemand hinsieht.

⚠ Die dritte Auflage des Tickets steht als eigene Zusicherung da: die Zeile darf **kein
Befund** sein. Ein Dauerbefund ohne Weg nach vorn ist die Bauform, die `SWR-166` 83
abgebrochene Läufe gekostet hat — und dieser Lauf hat gerade erst einen Preflight-Befund
geräumt, der drei Sprints lang jeden Auto-Abschluss des Auftraggebers gesperrt hat.

⚠ Jede Zusicherung ist ein **Paar** (`SWR-148`): neben „leer wird erkannt" steht „nicht
leer wird erkannt". Ohne die zweite Hälfte bestünde eine Fassung, die **immer** `leer`
meldet, jede Prüfung hier.
"""
import os
import sys
import textwrap
import unittest

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PLATFORM)
sys.path.insert(0, os.path.join(_PLATFORM, "scripts"))

from backend import organisation  # noqa: E402

_WURZEL = os.path.dirname(_PLATFORM)


def _bestand(tmp, tickets, besetzungen):
    """Eine Miniatur-Organisation auf der Platte: Register + Ticketdateien."""
    os.makedirs(os.path.join(tmp, "process", "roles"), exist_ok=True)
    with open(os.path.join(tmp, "process", "roles", "besetzungen.yaml"),
              "w", encoding="utf-8", newline="\n") as f:
        f.write(textwrap.dedent(besetzungen).lstrip("\n"))
    for einheit, tid, rolle, status in tickets:
        d = os.path.join(tmp, *einheit.split("/"), "tickets")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, tid + ".md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(f"---\nid: {tid}\ntitel: \"x\"\nrolle: {rolle}\n"
                    f"status: {status}\nrepo: {einheit}\n---\n\nRumpf.\n")


_NUR_OLLAMA = """
    besetzungen:
      PROB@platform:
        rolle: PROB
        einheit: platform
        motor: ollama
        modell: gemma3:27b
        takt: schnell
        status: aktiv
    """

_OHNE_OLLAMA = """
    besetzungen:
      CM@platform:
        rolle: CM
        einheit: platform
        motor: cowork
        takt: sprint
        status: aktiv
    """


class TaktBestandMisst(unittest.TestCase):
    """Die Messung selbst — beide Richtungen, damit keine Konstante besteht."""

    def test_leere_schnittmenge_wird_als_leer_gemeldet(self):
        """Besetzung vorhanden, kein Ticket dazu → `leer`. Der Zustand seit Sprint 26."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _bestand(tmp, [("platform", "T-0001", "dev", "open"),
                           ("platform", "T-0002", "cm", "open")], _NUR_OLLAMA)
            r = organisation.takt_bestand(tmp, "ollama")
            self.assertEqual(r["besetzungen"], ["PROB@platform"])
            self.assertEqual(r["offen"], 2)
            self.assertEqual(r["treffer"], [])
            self.assertTrue(r["leer"])

    def test_belegte_schnittmenge_ist_nicht_leer(self):
        """Die zweite Hälfte des Paares: ein passendes Ticket wird gefunden.

        Ohne sie bestünde eine Fassung, die `leer` fest verdrahtet, den Test darüber.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _bestand(tmp, [("platform", "T-0001", "dev", "open"),
                           ("platform", "T-0009", "prob", "open")], _NUR_OLLAMA)
            r = organisation.takt_bestand(tmp, "ollama")
            self.assertEqual(r["treffer"], ["platform/T-0009"])
            self.assertFalse(r["leer"])

    def test_kein_register_eintrag_ist_nicht_leere_schnittmenge(self):
        """⚠ `besetzungen == []` heißt „nicht konfiguriert", nicht „nichts zu tun".

        Dieselbe Grenze, die `SWR-128/165` für `besetzungen_mit_motor` gezogen hat: ohne
        sie wäre ein nie eingerichteter Motor von einem eingerichteten ohne Arbeit nicht
        zu unterscheiden — und die Behandlung ist eine völlig andere.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _bestand(tmp, [("platform", "T-0001", "prob", "open")], _OHNE_OLLAMA)
            r = organisation.takt_bestand(tmp, "ollama")
            self.assertEqual(r["besetzungen"], [])
            self.assertFalse(r["leer"], "kein Register-Eintrag darf nicht als leere "
                                        "Schnittmenge durchgehen")

    def test_nur_open_zaehlt_nicht_in_review(self):
        """⚠ Am eigenen Bestand belegt, nicht ausgedacht.

        `platform/T-0069` trägt die ollama-besetzte Rolle `PROB@platform` und steht auf
        `in_review`. `tick.waehle_ticket` wählt ausschließlich `open`. Eine großzügigere
        Grundmenge meldete hier „1 wählbar", und der Takt fände trotzdem nichts — eine
        zweite Antwort auf „was kann der Takt tun" (B033).
        """
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _bestand(tmp, [("platform", "T-0069", "prob", "in_review")], _NUR_OLLAMA)
            r = organisation.takt_bestand(tmp, "ollama")
            self.assertEqual(r["offen"], 0)
            self.assertEqual(r["treffer"], [])

    def test_verschachtelte_einheiten_zaehlen_mit(self):
        """`pl.md` Lehre 6: `projects/<p>/tickets/` ist auch Bestand.

        Sprint 32 ist so eine Projekt-Freigabe des Auftraggebers entgangen.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _bestand(tmp, [("projects/p11", "T-0003", "dev", "open"),
                           ("platform", "T-0001", "dev", "open")], _NUR_OLLAMA)
            r = organisation.takt_bestand(tmp, "ollama")
            self.assertEqual(r["offen"], 2, "projects/* fehlt in der Grundmenge")

    def test_status_im_codeblock_zaehlt_nicht(self):
        """⚠ Gefunden beim ersten Lauf gegen den echten Bestand, nicht beim Schreiben.

        `pm/T-0049` trägt `status: done` im Frontmatter und **ein zweites**
        `status: open` in einem zitierten Shell-Block seines Rumpfes. Eine Prüfung, die
        alle Zeilen absucht statt der ersten, hält ein geschlossenes Ticket für offen.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _bestand(tmp, [("platform", "T-0049", "prob", "done")], _NUR_OLLAMA)
            pfad = os.path.join(tmp, "platform", "tickets", "T-0049.md")
            with open(pfad, "a", encoding="utf-8", newline="\n") as f:
                f.write("\n```\n$ grep -m1 '^status:' x.md\nstatus: open\n```\n")
            r = organisation.takt_bestand(tmp, "ollama")
            self.assertEqual(r["offen"], 0, "ein zitiertes 'status: open' ist kein Status")


class PreflightMeldetDenBestand(unittest.TestCase):
    """Die Meldung — der eigentliche Zweck des Tickets."""

    def test_preflight_nennt_den_ollama_takt(self):
        """Die Zeile existiert — sonst ist die Messung wieder nur im Takt-Protokoll."""
        quelle = os.path.join(_PLATFORM, "scripts", "preflight.py")
        with open(quelle, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("takt_bestand(root,", text,
                      "preflight ruft die Messung nicht auf")
        self.assertIn("[org] ⚠ Ollama-Takt ohne Arbeit:", text,
                      "die Meldung für den leeren Bestand fehlt")

    def test_die_zeile_zaehlt_NICHT_als_befund(self):
        """⚠⚠ Die Auflage, die man beim Bauen am leichtesten übergeht.

        Ein leerer Takt-Bestand ist eine offene Klasse-B-Frage des PM, kein Fehler der
        Buchführung. Blockierend gemacht, hielte er den Betrieb des Auftraggebers für
        eine Entscheidung an, die er selbst treffen muss — `SWR-166`, 83 abgebrochene
        Läufe. Geprüft wird die Quelle: im Ollama-Block darf kein `befunde += 1` stehen.
        """
        quelle = os.path.join(_PLATFORM, "scripts", "preflight.py")
        with open(quelle, encoding="utf-8") as f:
            zeilen = f.read().split("\n")
        start = next(i for i, z in enumerate(zeilen) if "takt_bestand(root," in z)
        ende = next(i for i, z in enumerate(zeilen[start:], start)
                    if "vergangen = sprintvergangen" in z)
        block = "\n".join(zeilen[start:ende])
        self.assertNotIn("befunde += 1", block,
                         "der leere Takt-Bestand darf den Abschluss nicht blockieren")

    def test_die_meldung_nennt_den_weg_nicht_nur_den_zustand(self):
        """Ein Befund ohne Weg nach vorn ist eine Sackgasse mit Zeitstempel."""
        quelle = os.path.join(_PLATFORM, "scripts", "preflight.py")
        with open(quelle, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("platform/T-0066", text,
                      "die Meldung nennt das Ticket nicht, das den Weg beschreibt")


class BestandDerOrganisation(unittest.TestCase):
    """Die Gegenprobe am echten Haus — die Zahl, die das Ticket verlangt."""

    def test_echter_bestand_ist_messbar(self):
        """Kein Sollwert, sondern die Zusicherung, dass die Messung überhaupt läuft.

        ⚠ Ein fester Erwartungswert wäre hier falsch: die Zahl **soll** sich ändern,
        sobald das PM die Besetzung entscheidet. Eine Zusicherung, die den heutigen
        Mangel festschreibt, würde seine Behebung rot machen.
        """
        r = organisation.takt_bestand(_WURZEL, "ollama")
        self.assertIsInstance(r["besetzungen"], list)
        self.assertIsInstance(r["treffer"], list)
        self.assertGreater(r["offen"], 0, "kein offenes Ticket im Bestand — unplausibel")
        self.assertEqual(r["leer"], bool(r["besetzungen"]) and not r["treffer"])


if __name__ == "__main__":
    unittest.main()
