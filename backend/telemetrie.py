#!/usr/bin/env python3
"""Der Feldvertrag der Lauftelemetrie (SWR-137, promt-team/T-0004).

**Warum es diese Datei gibt.** `promt-team/T-0001` verlangt eine Baseline je KI-Rolle:
Token **statisch** (Systemprompt, harte Regeln, Tool-Definitionen, eingebettetes Wissen)
und **dynamisch** (Eingabe, Retrieval, Tool-Ergebnisse, Verlauf), Kosten, Latenz — und
sein eigener Auftragstext verbietet das Schätzen zweimal wörtlich:

> *„Token je Artefakt messen, nicht schätzen."*
> *„Fehlt eine Eingabe, wird das im Report als Blocker vermerkt und nicht geschätzt."*

**Gemessen am Bestand, bevor hier eine Zeile entstand** (`p0/management/runs/run-registry.jsonl`,
7 Läufe, Sprint 15):

| Feld | mit Inhalt |
|---|---|
| `rolle`, `ticket`, `status`, `kosten_eur`, `dauer_s`, `zeit` | 7 von 7 |
| `provider`, `modell` | **5 von 7** |
| `aufgaben_typ` | **1 von 7** |
| irgendein Token-Feld | **0 von 7** |
| `kosten_eur > 0` | **0 von 7** |

Zwei Befunde daraus, und beide sind der Grund für die Bauart dieser Datei:

1. **Das Feld, das die Auswertung braucht, existiert im Schema und ist leer.** Der
   Soll/Ist-Vergleich je Aufgaben-Typ, den `promt-team/T-0001` verlangt, ist für **6 von
   7** Läufen nicht rechenbar — nicht weil das Feld fehlt, sondern weil niemand
   bemerkt hat, dass es leer bleibt. Ein Pflichtfeld ohne Prüfung ist ein Wunsch.
2. **`kosten_eur: 0.0` steht siebenmal da und bedeutet zweierlei.** Für einen
   Ollama-Lauf ist die Null eine **Messung** (lokal, kostenlos); für einen
   Session-Austausch ist sie **„nicht erhoben"**. Beides als `0.0` zu schreiben ist genau
   der Fehler, den `SWR-108` im Cockpit-Payload gefunden und `SWR-135` erstmals
   ausgewertet hat:

   > **Eine 0 ist ein Ergebnis, kein Loch.**

   Deshalb führt die Telemetrie je Feld `{wert, zustand}` mit **denselben** drei
   Zustandsnamen wie der Widget-Vertrag — importiert und nicht abgeschrieben, denn eine
   vierte Schreibweise von „keine Daten" ist die Bauart, die B033 heißt.

**Was diese Datei ausdrücklich NICHT tut.** Sie schätzt nichts, sie rechnet nichts hoch
und sie füllt keine Lücke mit einem Vorgabewert. Fehlt eine Eingabe, erscheint sie in
`blocker` — namentlich. Das ist Teil **a** der Naht aus `promt-team/T-0001`
(*erheben und schreiben*); die Auswertung je Rolle ist Teil **b** (`promt-team/T-0005`)
und steht bewusst nicht hier: eine Auswertung im selben Modul wie die Erhebung könnte
eine fehlende Zahl stillschweigend überbrücken, und niemand würde es sehen.
"""
from .aggregation import (ZUSTAND_ECHTE_NULL, ZUSTAND_NICHT_GELIEFERT,  # noqa: F401
                          ZUSTAND_WERT)

#: Die Telemetriefelder je Lauf, in fester Reihenfolge. ⚠ Diese Liste ist der Vertrag:
#: `pruefe()` und `zustaende()` lesen **sie** und keine eigene Aufzählung, damit ein neues
#: Feld nicht an einer von zwei Stellen vergessen werden kann.
FELDER = ["token_statisch", "token_dynamisch", "kosten_eur", "dauer_s"]

#: Die **Schlüssel**, ohne die sich eine Messung keiner Rolle, keinem Aufgaben-Typ und
#: keiner Stufe der Kette zuordnen lässt.
#:
#: ⚠⚠ **Für einen Schlüssel gilt die Drei-Zustände-Regel NICHT** — und das ist ein Befund
#: dieses Tickets, gefunden von einem eigenen Test, der rot wurde. Die Vertragsregel *„0
#: ist ein Ergebnis, kein Loch"* ist für **Messungen** geschrieben: eine leere Liste
#: Artefakte, null Kosten, null Token sind Antworten. Ein leerer `aufgaben_typ` ist keine
#: Antwort — es gibt keinen Aufgaben-Typ namens „nichts".
#:
#: > **Eine Regel über Messwerte auf einen Schlüssel anzuwenden ist eine
#: > Kategorienverwechslung, und sie macht die Lücke unsichtbar, die sie sichtbar machen
#: > soll.**
#:
#: Ohne diese Trennung wäre der Hauptbefund am Bestand — `aufgaben_typ` in **6 von 7**
#: Läufen leer — von dieser Prüfung als „echte Null" durchgewinkt worden.
PFLICHT_SCHLUESSEL = ["rolle", "aufgaben_typ", "provider"]

#: Alle Pflichteingaben, nach denen `blocker()` sucht: Messungen und Schlüssel.
PFLICHT = FELDER + PFLICHT_SCHLUESSEL


def _zustand(wert):
    """Welcher der drei Vertragszustände liegt vor? — dieselbe Regel wie im Cockpit.

    ⚠ Die Herleitung wird **nicht** kopiert: `aggregation._zustand` ist privat, aber die
    drei **Namen** kommen von dort. Eine eigene Herleitung hier wäre eine fünfte
    Formulierung derselben Regel (der Befund hinter `platform/T-0016`) — und diese eine
    ist bewusst so kurz, dass sie keine zweite Wahrheit tragen kann.

    Für Zahlen gilt der Vertragssatz wörtlich: `0` ist eine **Messung**, `None` ein Loch.
    """
    if wert is None:
        return ZUSTAND_NICHT_GELIEFERT
    if wert == 0 or wert == "" or wert == [] or wert == {}:
        return ZUSTAND_ECHTE_NULL
    return ZUSTAND_WERT


def zustaende(eintrag):
    """`{feld: {wert, zustand}}` für die Telemetriefelder eines Run-Eintrags.

    Ein Feld, das der Eintrag gar nicht führt, ist `nicht_geliefert` — **nicht** `0`.
    Genau dieser Unterschied ist der Grund für die Funktion: siebenmal `kosten_eur: 0.0`
    im Bestand bedeutet einmal „kostenlos gemessen" und zweimal „nie erhoben", und ohne
    den Zustand ist die Unterscheidung verloren.
    """
    return {f: {"wert": eintrag.get(f), "zustand": _zustand(eintrag.get(f))}
            for f in FELDER}


def blocker(eintrag):
    """Die **namentlich** fehlenden Pflichteingaben eines Run-Eintrags.

    Rückgabe ist eine Liste von Feldnamen, nie eine Zahl: der Auftrag von
    `promt-team/T-0001` verlangt den Blocker im Report, und eine Zahl ohne den Gegenstand
    ist keine Meldung (B038, wie SWR-114/SWR-120).

    ⚠ **Eine `0` ist kein Blocker.** Ein Ollama-Lauf kostet wirklich nichts; ihn als
    Lücke zu melden hieße, eine Messung für ein Loch zu erklären — die Gegenrichtung
    desselben Fehlers und die Zusicherung, an der diese Funktion hängt.

    ⚠⚠ **Schlüssel werden anders geprüft als Messungen** (siehe `PFLICHT_SCHLUESSEL`):
    bei einer Messung ist nur `None` eine Lücke, bei einem Schlüssel auch der leere
    String. Die erste Fassung dieser Funktion hat beides gleich behandelt und damit ihren
    eigenen Hauptbefund durchgewinkt.
    """
    fehlt = [f for f in FELDER
             if _zustand(eintrag.get(f)) == ZUSTAND_NICHT_GELIEFERT]
    fehlt += [f for f in PFLICHT_SCHLUESSEL if not eintrag.get(f)]
    return [f for f in PFLICHT if f in fehlt]


def ergaenze(eintrag):
    """Einen Run-Eintrag um `telemetrie` und `blocker` ergänzen — ohne zu erfinden.

    Der Eintrag wird **kopiert**; vorhandene Felder bleiben unberührt, damit die
    Run-Registry rückwärtslesbar bleibt (die 7 Altläufe müssen weiter gültig sein).
    Fehlende Werte werden **nicht** ergänzt, sondern als `nicht_geliefert` beschrieben
    und in `blocker` genannt.
    """
    neu = dict(eintrag)
    neu["telemetrie"] = zustaende(eintrag)
    neu["blocker"] = blocker(eintrag)
    return neu
