"""Der VERTRETER der Festlegung aus SWR-113 (SWR-202, platform/T-0053).

⚠⚠ **Diese Datei ist der eigentliche Ertrag des Tickets, nicht die geänderte Zahl.**

`SWR-113` hat in Sprint 7 festgelegt, was „offen" heißt: jedes Ticket, dessen Status
weder `done` noch `rejected` ist, Takt-Dauerläufer eingeschlossen. Die Festlegung stand
danach in **einem Docstring** und in **keiner Zusicherung** — und zwanzig Sprints später
ist ein zweites Werkzeug entstanden, das sie nicht übernommen hat. Niemand hat
widersprochen; es hat sie nur niemand vertreten.

> **Eine Entscheidung, die keine Prüfung mitgeändert hat, ist eine Absichtserklärung
> (`SWR-125`). Ohne diese Datei wiederholt sich der Vorgang in zwanzig Sprints wieder —
> das ist die DoD-Auflage von `platform/T-0053` im Wortlaut.**

⚠ Geprüft wird **das Verhältnis der Erzeuger zueinander**, nicht eine Festzahl. Eine
Zusicherung auf „12" wäre beim nächsten geschlossenen Ticket rot und würde damit genau
das Wegsehen trainieren, gegen das `SWR-166` gebaut wurde (die Lehre aus `SWR-164`:
wachsende Größen als Größenordnung, nie als Festzahl).
"""
import ast
import os
import sys
import unittest

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, "scripts"))
sys.path.insert(0, WURZEL)
import kennzahlen  # noqa: E402
from backend import aggregation, sprint  # noqa: E402

ORGA = os.path.dirname(WURZEL)


class ZaehlweiseIstEine(unittest.TestCase):
    """Alle Erzeuger von „offene Tickets" geben dieselbe Zahl — am ECHTEN Bestand."""

    @classmethod
    def setUpClass(cls):
        cls.kz, cls.warten = kennzahlen.zaehle_tickets(ORGA)
        cls.agg = sum(p["tickets_offen"]
                      for p in aggregation.uebersicht(ORGA)["projekte"])
        cls.spr = sprint.kennzahlen(sprint.offene_tickets(ORGA))["offen_gesamt"]

    def test_grundmenge_ist_nicht_leer(self):
        """SWR-128-Familie: drei Nullen wären ebenfalls „deckungsgleich".

        Ohne diesen Block wäre die Prüfung unten in dem Moment für immer grün, in dem
        die Discovery nichts mehr findet — und das ist genau der Zustand, den sie melden
        müsste.
        """
        self.assertGreater(self.spr, 0, "kein Bestand — die Deckungsgleichheit unten wäre wertlos")

    def test_alle_drei_erzeuger_sind_deckungsgleich(self):
        """⚠⚠ Der Vertreter selbst.

        Gemessen 2026-08-21 vor der Reparatur: `sprint.kennzahlen` 12,
        `aggregation.uebersicht` 12, `kennzahlen.zaehle_tickets` **9** — die Differenz
        waren genau die 3 **gesperrten** Tickets. Ein `blocked`-Ticket ist nicht
        geschlossen; es aus „offen" zu nehmen hieße, dass eine Sperre eine Aufgabe zum
        Verschwinden bringt.
        """
        self.assertEqual(self.kz, self.spr,
                         "kennzahlen.py weicht von der SWR-113-Festlegung ab")
        self.assertEqual(self.agg, self.spr,
                         "aggregation.uebersicht weicht von der SWR-113-Festlegung ab")

    def test_gesperrte_zaehlen_mit(self):
        """⚠ Die Richtung, in der die Abweichung lag — ausdrücklich abgesichert.

        Ohne diesen Block wäre eine Fassung grün, in der **alle drei** Erzeuger auf
        `== "open"` umgestellt würden: deckungsgleich und trotzdem gegen `SWR-113`.
        Eine Zusicherung, die nur Gleichheit misst, ist nach einem gleichmäßigen
        Fehlgriff ebenfalls grün — dieselbe Bauform wie das Paar in `SWR-148`.

        ⚠ Die erste Fassung zählte `open + blocked` auf und war damit **rot**, sobald ein
        Ticket auf `in_progress` stand — was in jedem laufenden Sprint vorkommt und in
        diesem sofort eintrat. Eine Zusicherung, die eine Definition durch **Aufzählung**
        ihrer heutigen Fälle nachbaut, ist beim nächsten neuen Statuswort falsch. Geprüft
        wird deshalb die Definition selbst: *nicht geschlossen*.
        """
        alle = sprint.alle_tickets(ORGA)
        gesperrt = [t for t in alle if t.get("status") == "blocked"]
        self.assertTrue(gesperrt, "kein gesperrtes Ticket — die Unterscheidung wäre wertlos")
        nicht_geschlossen = [t for t in alle
                             if t.get("status") not in sprint.TICKET_GESCHLOSSEN]
        self.assertEqual(self.spr, len(nicht_geschlossen),
                         "die Zahl folgt nicht der Definition „nicht geschlossen“")
        for t in gesperrt:
            self.assertIn(t, nicht_geschlossen, "ein gesperrtes Ticket fehlt in der Menge")

    def test_wartende_stammen_aus_derselben_grundmenge(self):
        """Wer auf einen Menschen wartet, ist offen — sonst zählen zwei Zahlen zwei Mengen."""
        self.assertLessEqual(self.warten, self.kz)


class FestlegungHatEinenOrt(unittest.TestCase):
    """⚠ Die Begründung darf nicht wieder nur in einem Docstring wohnen."""

    def test_die_zaehlenden_funktionen_zitieren_die_konstante(self):
        """⚠⚠ Geprüft wird die VERWENDUNG, nicht die Anwesenheit der Konstante.

        Der erste Entwurf dieser Datei prüfte nur, dass `ENDZUSTAENDE` irgendwo im Modul
        **steht** — und blieb grün, während `aggregation.uebersicht` drei Zeilen darüber
        weiter das **Literal** benutzte. Eine Konstante, die dasteht und nicht gerufen
        wird, ist genau so viel wert wie der Docstring, an dem dieses Ticket hängt.

        > **Ein Literal, das mit der Festlegung zufällig zusammenfällt, ist von einem,
        > das sie zitiert, nicht zu unterscheiden — bis eines von beiden sich ändert.**

        ⚠ Grundmenge sind ausdrücklich nur die Funktionen, die die Zahl „offene Tickets"
        **erzeugen**. Die übrigen Vorkommen des Literals im Haus beantworten andere
        Fragen (offene DRs, Digest-Auswahl) und sind in `platform/T-0054` gezählt statt
        hier im Vorbeigehen mitgeändert.
        """
        for rel, funktion in (("scripts/kennzahlen.py", "def zaehle_tickets"),
                              ("backend/aggregation.py", "def uebersicht")):
            with open(os.path.join(WURZEL, *rel.split("/")), encoding="utf-8") as f:
                text = f.read()
            # ⚠ Der Rumpf endet an der ersten Zeile OHNE Einrückung — nicht am nächsten
            # `def`. Der erste Entwurf las bis zum nächsten `def` weiter und verschluckte
            # dabei die Konstantendefinition, die hinter der Funktion stand: die Prüfung
            # wurde rot und meinte den falschen Fund. Eine Zerlegung, die über ihren
            # Gegenstand hinausläuft, misst den Nachbarn mit.
            start = text.index(funktion)
            zeilen = text[start:].splitlines()
            rumpf_zeilen = [zeilen[0]]
            for z in zeilen[1:]:
                if z and not z[0].isspace():
                    break
                rumpf_zeilen.append(z)
            rumpf = "\n".join(rumpf_zeilen)
            # ⚠⚠ Gelesen wird der CODE, nicht der Rumpf. Die erste Fassung prüfte den
            # ganzen Rumpf **inklusive Docstring** — eine Erwähnung der Konstante in der
            # Erklärung hätte genügt, und genau diese Schwäche („anwesend statt
            # verwendet") ist die, die dieser Block heilen soll. Der Prüfer hatte den
            # Fehler, den er prüft. Gefunden hat es das Review, nicht der Autor.
            baum = ast.parse(rumpf if rumpf.startswith("def") else rumpf)
            code = ast.dump(ast.Module(
                body=[n for n in baum.body[0].body
                      if not (isinstance(n, ast.Expr)
                              and isinstance(n.value, ast.Constant)
                              and isinstance(n.value.value, str))],
                type_ignores=[]))
            self.assertIn("ENDZUSTAENDE", code,
                          "%s zitiert die Konstante nicht im CODE" % rel)
            self.assertNotIn("value='done'", code,
                             "%s benutzt weiterhin das Literal" % rel)

    def test_swr113_wird_in_kennzahlen_zitiert(self):
        """Der nächste Leser soll die Festlegung finden, ohne sie zu suchen.

        ⚠ Das ist bewusst eine Zitat- und keine Verhaltensprüfung: das Verhalten sichern
        die Blöcke oben. Diese hier sichert, dass jemand, der `zaehle_tickets` ändern
        will, den Grund vor sich hat — was zwanzig Sprints lang gefehlt hat.
        """
        with open(os.path.join(WURZEL, "scripts", "kennzahlen.py"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("SWR-113", text)


if __name__ == "__main__":
    unittest.main()
