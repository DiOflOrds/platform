"""Eine erteilte Abnahme hat einen Tag (SWR-211, platform/T-0056, Brief N-0009).

⚠⚠ **Die Messung hat die Frage des Tickets umgedreht — zum vierten Mal in diesem Lauf.**

Der Brief fragte: *„warum wurden die baselines schon lange für das gesamte Projekt nicht
mehr gezogen?"*, und das Ticket bot zwei Ursachen an (Ollama-Guardrail, stehender Push).

Gemessen an den Git-Tags:

| Frage des Tickets | Messung |
|---|---|
| „seit dem 07.08. keine Baseline" | **Falsch.** Die letzten Baselines sind vom **16.08.** (`p8-v1.0`, `p9-v1.0`, `p10-v1.0`). Der 07.08. gehört `genesis-v1.0` — der **eigenen** Linie der Plattform, nicht den Projekten. |
| Ursache 1: Ollama-Guardrail | **Ausgeschlossen.** Eine G4-Abnahme ist eine Klasse-A-Entscheidung des Menschen über die Inbox; sie ist nie auf Ollama gelaufen und **wurde erteilt**. |
| Ursache 2: der stehende Push | **Ausgeschlossen.** Ein Tag entsteht **lokal**; `p10-v1.0` stand zwei Tage lokal, bevor er hinausging. Der Push war die Folge, nicht die Bedingung. |

**Die wirkliche Ursache ist ein fehlender Schritt zwischen zwei vorhandenen:**

> **⚠⚠ `p12/D003` (2026-08-17 21:57) hat die Baseline `p12-v1.0` abgenommen — Option A auf
> `p12/T-0010`, „DR/G4: Baseline p12-v1.0 abnehmen". Der Tag wurde nie gesetzt. Vier Tage
> lang war ein Projekt abgenommen, ohne dass es einen abgenommenen Stand gab.**

Die Entscheidung und ihr Artefakt sind zwei Schritte, und der zweite hatte keine Prüfung.

⚠ **Ein Nebenbefund über die eigene erste Messung, benannt statt weggelassen:** die erste
Zählung suchte `G4` als **Text** in den Entscheidungslogs und fand 26 Treffer. Drei von
fünf gemeldeten Lücken waren **Falschtreffer** — `pm` zitiert fremde G4-Vorgänge in
B-Zeilen, `p11/D000` enthält die Zeichenfolge in *„Gates G0–G4"*, und `p0`s G4-Zeilen sind
**Sprint**-Abnahmen, keine Projektabnahmen.

> **Ein Wort in einem Fließtext ist keine Entscheidung. Die Entscheidung ist das
> DR-Ticket, auf das die Logzeile zeigt — deshalb fragt diese Prüfung das Ticket und
> nicht den Text.**

Vertreter von `L-2026-08-21df`.
"""
import os
import re
import subprocess
import sys
import unittest

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAUS = os.path.dirname(WURZEL)
sys.path.insert(0, os.path.join(WURZEL, "scripts"))
sys.path.insert(0, WURZEL)
import board  # noqa: E402

#: Ein DR, dessen Titel eine **Projekt-Baseline abnimmt**. ⚠ Nicht „enthält G4": eine
#: Sprint-Abnahme trägt dasselbe Wort und meint etwas anderes.
G4_TITEL = re.compile(r"\bG4\b.*\bBaseline\s+(\S+?-v\d[\d.]*)\b", re.I)
#: ⚠⚠ **Namentlich ausgenommen, mit Grund und mit Verfallsprüfung** (die Lehre aus
#: `SWR-204`). `p0` ist das Genesis-Projekt; seine Baseline heißt `genesis-v1.0` und nicht
#: `p0-v1.0`. Das ist eine Benennung aus Sprint 1 und keine Lücke — der Tag existiert.
BASELINE_NAME_ABWEICHEND = {"p0": "genesis-v1.0"}


def _repo_von(pfad):
    """Das Git-Repo über einem Einheitenpfad (Sammel-Repo mitgedacht)."""
    p = os.path.abspath(pfad)
    while p and p != os.path.dirname(p):
        if os.path.isdir(os.path.join(p, ".git")):
            return p
        p = os.path.dirname(p)
    return None


def _tags(repo):
    if not repo:
        return set()
    r = subprocess.run(["git", "-C", repo, "tag"], capture_output=True, text=True)
    return set(r.stdout.split())


def abgenommene_baselines(wurzel):
    """[(einheit, tag, ticket)] — jede Baseline, deren G4-DR entschieden ist.

    ⚠ Grundmenge sind die **Tickets** der Discovery und nicht eine Liste im Ticketkopf
    (`SWR-128`-Familie, in diesem Haus dreimal bezahlt).
    """
    raus = []
    for name, pfad in board.projekt_pfade(wurzel):
        tickets, _ = board.lade_tickets(pfad)
        for t in tickets:
            if t.get("typ") != "decision-request" or t.get("status") not in board.STATUS_FINAL:
                continue
            m = G4_TITEL.search(t.get("titel") or "")
            if not m:
                continue
            # Nur eine ENTSCHIEDENE Abnahme zählt: der Entscheidungsvermerk im Rumpf.
            if board.ENTSCHEIDUNGSMARKER not in (t.get("_body") or ""):
                continue
            raus.append((name, BASELINE_NAME_ABWEICHEND.get(name, m.group(1)), t["id"]))
    return raus


class JedeAbnahmeHatIhrenTag(unittest.TestCase):

    def setUp(self):
        if not os.path.isdir(os.path.join(HAUS, "process")):
            self.skipTest("kein Organisationskontext (einzeln ausgechecktes Repo)")

    def test_grundmenge_ist_nicht_leer(self):
        """SWR-128: ohne abgenommene Baselines prüft der Block darunter nichts."""
        self.assertTrue(abgenommene_baselines(HAUS),
                        "keine entschiedene G4-Abnahme gefunden — die Prüfung darunter "
                        "wäre grün, weil sie nichts ansieht")

    def test_kein_abgenommenes_projekt_ohne_baseline(self):
        """⚠⚠ Die Prüfung, die vier Tage gefehlt hat.

        Sie fragt das **Ticket** und nicht den Fließtext: ein `G4` in einer Begründung ist
        ein Zitat, kein Vorgang.
        """
        fehlend = []
        for einheit, tag, ticket in abgenommene_baselines(HAUS):
            repo = _repo_von(dict(board.projekt_pfade(HAUS))[einheit])
            if tag not in _tags(repo):
                fehlend.append(f"{einheit}: {tag} fehlt (abgenommen lt. {einheit}/{ticket})")
        self.assertEqual([], fehlend, (
            "Abgenommen, aber ohne Baseline: " + "; ".join(fehlend) + ". ⚠ Die Abnahme "
            "ist erteilt — der Tag ist ihre AUSFÜHRUNG und keine neue Entscheidung. Er "
            "gehört auf den Abschluss-Commit des damaligen Laufs und NICHT auf HEAD: ein "
            "Tag auf heute behauptet, der heutige Stand sei abgenommen worden."))

    def test_die_namensausnahme_beisst_noch(self):
        """⚠ Verfallsprüfung: eine Ausnahme ohne Fundstelle ist Altpapier (`SWR-204`)."""
        einheiten = dict(board.projekt_pfade(HAUS))
        for einheit, tag in BASELINE_NAME_ABWEICHEND.items():
            self.assertIn(einheit, einheiten,
                          f"Ausnahme für {einheit}, das es nicht mehr gibt")
            self.assertIn(tag, _tags(_repo_von(einheiten[einheit])),
                          f"Ausnahme nennt {tag}, den es nicht gibt — dann ist sie keine "
                          f"Benennung, sondern eine echte Lücke")


class DieSprintAbnahmeIstKeineProjektAbnahme(unittest.TestCase):
    """⚠⚠ Die Gegenrichtung — ohne sie wäre die Prüfung entweder blind oder falsch laut."""

    def test_ein_sprint_G4_erzeugt_keine_baseline_forderung(self):
        self.assertIsNone(G4_TITEL.search("G4 Sprint 5 erteilt: 12 Tickets abgenommen"))
        self.assertIsNone(G4_TITEL.search("Projektauftrag: Gates G0–G4 gelten"))

    def test_ein_projekt_G4_wird_erkannt(self):
        m = G4_TITEL.search("DR/G4: Baseline p12-v1.0 abnehmen — und was mit dem Body geschieht")
        self.assertIsNotNone(m)
        self.assertEqual("p12-v1.0", m.group(1))


if __name__ == "__main__":
    unittest.main()
