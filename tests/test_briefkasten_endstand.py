"""Der Briefkasten wird am ENDE gemessen, nicht nur am Anfang (L-2026-08-21cs).

⚠⚠ Sprint 32 hat den Briefkasten als erstes gesichtet — **0 offen**, richtig gemessen —
und beim Zusammenstellen der Abschlusszahlen standen **7** offen. Alle sieben waren
zwischen 06:32 und 07:03 eingegangen, also **während** des Laufs.

> **„Briefkasten zuerst" ist eine Reihenfolge und keine Zusicherung. Ein Zustand, der
> einmal am Anfang gemessen und am Ende als Ergebnis berichtet wird, ist eine
> Momentaufnahme in der Aufmachung einer Garantie.**

⚠ Diese Datei ist der **heute schon tragende** Teil des Vertreters: sie hält die beiden
Discovery-Wege zusammen, die in diesem Lauf auseinandergelaufen sind. Der **zweite** Teil
— wie oft ein Brief während eines Laufs eintrifft und was dann die richtige Handlung ist —
wird in `platform/T-0057` **gezählt, bevor** er gebaut wird; ihn hier vorwegzunehmen wäre
die Bauform, die dieses Haus „erst bauen, dann zählen" nennt.

Vertreter von `L-2026-08-21cs`.
"""
import glob
import os
import sys
import unittest

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, "scripts"))
ORGA = os.path.dirname(WURZEL)

import kennzahlen  # noqa: E402


class BriefkastenDiscovery(unittest.TestCase):

    def test_das_werkzeug_reicht_weiter_als_die_oberste_ebene(self):
        """⚠⚠ Der Handlauf dieses Sprints sah eine ENGERE Menge als das Werkzeug.

        Er suchte nur `*/management/briefkasten/`; `zaehle_briefkasten` liest zusätzlich
        `*/*/management/briefkasten/`. Und dort liegt tatsächlich ein Brief
        (`projects/p11/management/briefkasten/N-0001.md`) — **die enge Sicht hat also
        nicht zufällig dasselbe gesehen, sie hat einen Brief nicht gesehen.** Er war
        beantwortet, deshalb ist nichts passiert; das ist Glück und keine Eigenschaft.

        ⚠ **Was hier NICHT geprüft wird und warum.** Der erste Entwurf verlangte, dass
        beide Wege dieselbe Menge liefern — und war damit sofort und dauerhaft rot, ohne
        dass irgendjemand etwas richtig machen konnte: der verschachtelte Brief ist
        rechtmäßig dort, wo er liegt.

        > **Eine Prüfung, die von einem Bestand verlangt, sich anders anzuordnen, damit
        > ein Werkzeug einfacher sein darf, ist kein Befund — sie ist ein Dauerärgernis,
        > und `SWR-166` hat 83 abgebrochene Läufe gekostet, um das zu lernen.**

        Gesichert ist deshalb die **Reichweite des Werkzeugs**: es muss beide Ebenen
        lesen, und dass die zweite Ebene nicht leer ist, steht daneben — sonst wäre die
        Forderung ab dem Tag folgenlos, an dem jemand sie erfüllt, ohne sie zu erfüllen.
        """
        tief = glob.glob(os.path.join(ORGA, "*", "*", "management", "briefkasten", "N-*.md"))
        self.assertTrue(tief,
                        "kein Brief auf der zweiten Ebene — die Forderung unten wäre "
                        "folgenlos (SWR-128-Familie)")
        # ⚠ SWR-206 (Sprint 33): die Reichweite wohnt nicht mehr in `zaehle_briefkasten`,
        # sondern in `board.briefkasten_dateien` — die Forderung ist an die neue Tür
        # umgezogen und **nicht** gelöscht. Geprüft wird sie am ECHTEN Bestand, also
        # schärfer als vorher: nicht „der Quelltext nennt zwei Ebenen", sondern „die
        # Auflösung findet den Brief, der auf der zweiten Ebene liegt".
        import board  # noqa: PLC0415 — lokal, damit die Datei ohne board importierbar bleibt
        gefunden = {os.path.abspath(p) for _e, p in board.briefkasten_dateien(ORGA)}
        for brief in tief:
            self.assertIn(os.path.abspath(brief), gefunden,
                          "briefkasten_dateien liest die zweite Ebene nicht — ein Brief "
                          "in einem verschachtelten Repo wäre unsichtbar")

    def test_die_zaehlung_liest_das_statusfeld_und_nicht_den_dateinamen(self):
        """SWR-128-Familie: eine leere Grundmenge wäre ebenfalls „0 offen"."""
        pfade = glob.glob(os.path.join(ORGA, "*", "management", "briefkasten", "N-*.md"))
        self.assertGreater(len(pfade), 10, "Grundmenge zu klein — Discovery kaputt?")
        stati = {(kennzahlen._frontmatter(p).get("status") or "").lower() for p in pfade}
        self.assertTrue(stati - {""},
                        "kein Brief trägt ein Statusfeld — die Zählung liest ins Leere")


if __name__ == "__main__":
    unittest.main()
