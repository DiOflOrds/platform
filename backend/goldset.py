#!/usr/bin/env python3
"""Das Format eines Goldset-Falls (SWR-142, promt-team/T-0006).

**Warum es diese Datei gibt.** `promt-team/T-0002` verlangt ein Goldset je KI-Rolle — den
Maßstab, gegen den ein Eval-Gate prüft. Die Naht, an der das Ticket bei seiner fünften
Berührung zerlegt wurde, trägt mehr als Bequemlichkeit:

> **Ohne Format sind zwanzig Fälle zwanzig Einzelmeinungen — und ein Eval-Gate, das Formen
> vergleicht statt Ergebnisse, misst die Sorgfalt des Schreibers.**

**Die zwei Felder, an denen alles hängt.**

`fehlschlag_erkannt_an` ist **Pflicht** und **keine Prosa**. Ein Fall, dessen Fehlschlag
nur „sieht man doch" erkennt, ist kein Prüffall, sondern eine Meinung mit Termin. Und er
wird **abgelehnt** statt vorbelegt: ein Vorgabewert an dieser Stelle machte jede
ungeschriebene Prüfung stillschweigend zu einer bestandenen.

`soll_scheitern_auf` nennt die Provider-Stufe, auf der ein Fall **scheitern soll**. Ohne
ihn belegt ein grünes Eval nur, dass die Aufgabe leicht war. ⚠ Das Feld allein genügt
nicht — geprüft wird, dass **je Aufgaben-Typ mindestens einer** gesetzt ist. Ein Feld ohne
Prüfung ist ein Wunsch (SWR-125, hier angewandt statt zitiert).

**Sensible Daten werden benannt und ausgelassen, nicht anonymisiert erfunden.** Ein
erfundener Fall misst den Erfinder. Die Auslassung trägt ihren **Grund**, sonst ist die
Lücke im Set von Vollständigkeit nicht zu unterscheiden.

**Warum alle Mängel eines Falls auf einmal gemeldet werden.** Ein Fall, der über fünf
Läufe fünfmal korrigiert wird, ist der Preis eines Prüfers, der beim ersten Mangel
aufhört.

Diese Datei enthält **keine Fälle** — die sind `promt-team/T-0007`.
"""
import json
import os
import re

#: Die geschlossene Menge der Prüfarten. ⚠ Sie steht **hier** und nirgends sonst; der
#: Prüfer liest sie, statt sie zu wiederholen. Eine zweite Schreibweise derselben Liste
#: ist die Bauart, die SWR-131 gekostet hat.
PRUEF_ARTEN = ("enthaelt", "enthaelt_nicht", "regex", "json_pfad", "datei_existiert")

#: Pflichtfelder eines Falls. `soll_scheitern_auf` steht bewusst **nicht** hier: es ist je
#: Aufgaben-Typ Pflicht, nicht je Fall — die Prüfung dafür ist `pruefe_set`.
PFLICHT = ("rolle", "aufgaben_typ", "eingabe", "erwartetes_ergebnis",
           "fehlschlag_erkannt_an")


def pruefe_fall(fall):
    """**Alle** Mängel eines Falls — Liste von Meldungen, leer = in Ordnung (SWR-142).

    Bewusst alle und nicht der erste: ein Fall, der über fünf Läufe fünfmal korrigiert
    wird, ist der Preis eines Prüfers, der beim ersten Mangel aufhört.
    """
    m = []
    if not isinstance(fall, dict):
        return ["Fall ist kein Objekt"]
    for feld in PFLICHT:
        wert = fall.get(feld)
        if wert is None or (isinstance(wert, str) and not wert.strip()):
            m.append(f"Pflichtfeld fehlt: {feld}")
    pruefung = fall.get("fehlschlag_erkannt_an")
    if pruefung is not None:
        if isinstance(pruefung, str):
            m.append("fehlschlag_erkannt_an ist Prosa — ein Fall, dessen Fehlschlag nur "
                     "'sieht man doch' erkennt, ist kein Prueffall")
        elif not isinstance(pruefung, dict):
            m.append("fehlschlag_erkannt_an muss {art, wert} sein")
        else:
            art = pruefung.get("art")
            if art not in PRUEF_ARTEN:
                m.append(f"unbekannte Pruefart '{art}' — erlaubt: "
                         f"{', '.join(PRUEF_ARTEN)}")
            if not str(pruefung.get("wert") or "").strip():
                m.append("fehlschlag_erkannt_an ohne 'wert'")
            if art == "regex":
                try:
                    re.compile(str(pruefung.get("wert") or ""))
                except re.error as e:
                    m.append(f"regex nicht uebersetzbar: {e}")
    if "sensibel_ausgelassen" in fall:
        if not str(fall.get("sensibel_ausgelassen") or "").strip():
            m.append("sensibel_ausgelassen ohne Grund — eine unerklaerte Luecke ist von "
                     "Vollstaendigkeit nicht zu unterscheiden")
    return m


def pruefe_set(faelle):
    """Mängel des **ganzen** Sets: je Fall und die Regel über die Fälle (SWR-142).

    ⚠ Die Regel über die Fälle ist der Punkt, an dem `soll_scheitern_auf` mehr wird als
    ein Feld: **je Aufgaben-Typ muss mindestens ein Fall** ihn setzen, sonst belegt ein
    grünes Eval nur, dass die Aufgaben leicht waren. Der fehlende Typ wird **genannt**.
    """
    m = []
    typen = {}
    for i, fall in enumerate(faelle, 1):
        for mangel in pruefe_fall(fall):
            m.append(f"Fall {i}: {mangel}")
        if isinstance(fall, dict):
            typ = fall.get("aufgaben_typ") or "(ohne Typ)"
            typen.setdefault(typ, False)
            if str(fall.get("soll_scheitern_auf") or "").strip():
                typen[typ] = True
    for typ, hat in sorted(typen.items()):
        if not hat:
            m.append(f"Aufgaben-Typ '{typ}': kein Fall mit 'soll_scheitern_auf' — ein "
                     f"gruenes Eval belegt sonst nur, dass die Aufgabe leicht war")
    return m


def lies(pfad):
    """Goldset (JSONL) als `(faelle, kaputte_zeilen)`. Kaputte Zeilen werden gezählt."""
    faelle, kaputt = [], 0
    if not os.path.exists(pfad):
        return faelle, kaputt
    with open(pfad, encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                faelle.append(json.loads(zeile))
            except ValueError:
                kaputt += 1
    return faelle, kaputt


def haenge_an(pfad, fall):
    """Einen **geprüften** Fall anhängen — append-only wie die Run-Registry.

    Wirft `ValueError` mit **allen** Mängeln, wenn der Fall sie hat. Ein ungeprüfter
    Schreibweg neben diesem wäre die Lage aus SWR-134: eine Prüfung, die der Aufrufer
    anwenden muss.
    """
    m = pruefe_fall(fall)
    if m:
        raise ValueError("Goldset-Fall abgelehnt: " + "; ".join(m))
    os.makedirs(os.path.dirname(os.path.abspath(pfad)), exist_ok=True)
    with open(pfad, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(fall, ensure_ascii=False) + "\n")
    return fall
