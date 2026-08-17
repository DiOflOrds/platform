#!/usr/bin/env python3
"""Die Auswertung der Lauftelemetrie je Rolle (SWR-140, promt-team/T-0005).

**Warum es diese Datei gibt und warum sie nicht `telemetrie.py` ist.** `SWR-137` hat den
Feldvertrag gebaut (Teil a) und in seinen eigenen Docstring geschrieben, warum die
Auswertung **woanders** wohnen muss: *eine Auswertung im selben Modul wie die Erhebung
könnte eine fehlende Zahl stillschweigend überbrücken, und niemand würde es sehen.*

**Der Befund, der die Bauart bestimmt.** Der Bestand ist leer — 7 Läufe, **0** mit
Token-Feldern, **6** ohne `aufgaben_typ`. Die naheliegende Auswertung wäre ein Mittelwert
je Rolle. Genau der ist hier falsch:

> **Ein Mittel über die Läufe, die zufällig gemeldet haben, ist kein Mittel über die
> Läufe. Ohne seinen Nenner gedruckt ist es von einer vollständigen Messung nicht zu
> unterscheiden.**

Das ist derselbe Fehler wie `kosten_eur: 0.0` aus SWR-137, eine Etage höher: dort im
**Feld**, hier im **Aggregat**. Deshalb trägt jede Zahl hier `n_gemessen` **und**
`n_gesamt`, und ein Aggregat ohne eine einzige Messung ist `nicht_geliefert` und **nicht**
`0`.

**Was diese Datei ausdrücklich NICHT tut.** Sie leitet keinen Blocker neu her (die stehen
in `telemetrie.blocker`, B033), sie kennt keine zweite Quelle neben der Run-Registry, und
sie lässt keinen Lauf weg: ein Lauf ohne `aufgaben_typ` erscheint **namentlich** unter
`nicht_zuordenbar`. Ihn wegzulassen würde den Nenner verkleinern und die Abdeckung besser
aussehen lassen, als sie ist — also genau die Lücke verstecken, um deren Sichtbarkeit es
geht.

⚠ **Ein Provider, der in der geplanten Kette steht, aber nicht an erster Stelle, ist kein
Verstoß.** Die Kette ist eine **Rückfallleiter** (`on_unavailable: next_in_chain`): wer
`[ollama, claude]` plant und auf `claude` landet, hat die Leiter benutzt, wie sie gemeint
ist. Beides zusammenzuwerfen ergäbe einen roten Report über richtiges Verhalten — und ein
Dauerbefund trainiert das Wegsehen an (die Falle aus SWR-131).
"""
import json
import os
import re

from .aggregation import (ZUSTAND_ECHTE_NULL, ZUSTAND_NICHT_GELIEFERT,  # noqa: F401
                          ZUSTAND_WERT)
from . import telemetrie

#: Die auswertbaren Messfelder — **gelesen** aus dem Vertrag, nicht neu aufgezählt.
#: Ein Feld, das dort dazukommt, ist hier ohne Änderung dabei (SWR-137).
FELDER = telemetrie.FELDER

#: Ergebnis der Zuordnung eines Laufs zu seinem geplanten Provider (SWR-140).
SOLL_IST_PASST = "passt"                        # genutzter Provider = erste Stufe
SOLL_IST_ABWEICHEND_MIT_GRUND = "abweichend_mit_grund"  # in der Kette, nicht an 1. Stelle
SOLL_IST_ABWEICHUNG = "abweichung"              # gar nicht in der Kette
SOLL_IST_UNBEKANNT = "unbekannt"                # kein Eintrag in der Registry


def lies_registry(pfad):
    """Run-Registry (JSONL) als Liste von Einträgen. Unlesbare Zeilen werden **gezählt**.

    Rückgabe: `(eintraege, kaputte_zeilen)`. Eine kaputte Zeile still zu überspringen
    hieße, den Nenner zu verkleinern — dieselbe Regel wie bei `nicht_zuordenbar`.
    """
    eintraege, kaputt = [], 0
    if not os.path.exists(pfad):
        return eintraege, kaputt
    with open(pfad, encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                eintraege.append(json.loads(zeile))
            except ValueError:
                kaputt += 1
    return eintraege, kaputt


def _mess_wert(eintrag, feld):
    """Der Wert dieses Feldes, wenn er **gemessen** ist — sonst `None`.

    ⚠ Eine `0` ist gemessen. Sie hier als „nichts" zu behandeln wäre die Gegenrichtung
    des Fehlers aus SWR-137 und ebenso falsch.
    """
    z = telemetrie.zustaende(eintrag).get(feld) or {}
    if z.get("zustand") == ZUSTAND_NICHT_GELIEFERT:
        return None
    return z.get("wert")


def aggregat(eintraege, feld):
    """Summe/Mittel eines Messfeldes **mit seiner Abdeckung** (SWR-140).

    Rückgabe::

        {"summe": …, "mittel": …, "zustand": …, "n_gemessen": …, "n_gesamt": …}

    ⚠ `zustand` ist `nicht_geliefert`, solange **kein** Lauf gemessen hat — und dann sind
    `summe` und `mittel` `None` und nicht `0`. Ein Aggregat ohne Messung als `0` zu
    drucken ist die teuerste Form der Schätzung, weil es wie ein Ergebnis aussieht.

    ⚠⚠ `n_gemessen < n_gesamt` ist der **Regelfall** und keine Ausnahme. Wer nur `mittel`
    liest, liest ein Mittel über eine unbekannte Teilmenge.
    """
    werte = []
    for e in eintraege:
        w = _mess_wert(e, feld)
        if w is not None:
            werte.append(w)
    n_gesamt = len(eintraege)
    if not werte:
        return {"summe": None, "mittel": None, "zustand": ZUSTAND_NICHT_GELIEFERT,
                "n_gemessen": 0, "n_gesamt": n_gesamt}
    summe = sum(werte)
    return {"summe": summe, "mittel": summe / len(werte),
            "zustand": ZUSTAND_ECHTE_NULL if summe == 0 else ZUSTAND_WERT,
            "n_gemessen": len(werte), "n_gesamt": n_gesamt}


def je_rolle(eintraege):
    """`{ROLLE: {feld: aggregat, "n_laeufe": …, "blocker": {feld: anzahl}}}` (SWR-140).

    Die Blocker werden aus :func:`telemetrie.blocker` **gelesen** und nicht neu
    hergeleitet — zwei Herleitungen derselben Frage sind B033, und die zweite wäre die,
    die niemand pflegt.
    """
    gruppen = {}
    for e in eintraege:
        gruppen.setdefault((e.get("rolle") or "").upper() or "(ohne Rolle)", []).append(e)
    ergebnis = {}
    for rolle, es in sorted(gruppen.items()):
        blocker_zaehler = {}
        for e in es:
            for feld in (e.get("blocker") if isinstance(e.get("blocker"), list)
                         else telemetrie.blocker(e)):
                blocker_zaehler[feld] = blocker_zaehler.get(feld, 0) + 1
        ergebnis[rolle] = {f: aggregat(es, f) for f in FELDER}
        ergebnis[rolle]["n_laeufe"] = len(es)
        ergebnis[rolle]["blocker"] = dict(sorted(blocker_zaehler.items()))
    return ergebnis


# --- Soll/Ist gegen process/roles/registry.yaml --------------------------------

_ROLLE_RE = re.compile(r"^  ([A-Z][A-Z0-9_]*):\s*$")
_TYP_RE = re.compile(r"^      ([a-zA-Z0-9_\-]+):\s*\{(.*)\}\s*$")
_CHAIN_RE = re.compile(r"chain:\s*\[([^\]]*)\]")


def lies_rollen_registry(pfad):
    """Geplante Ketten je Rolle und Aufgaben-Typ aus `process/roles/registry.yaml`.

    Bewusst ein **kleiner** Leser statt einer YAML-Abhängigkeit: die Organisation hat
    keine, und eine neue einzuführen wäre eine Entscheidung für alle Repos (Klasse A für
    die Werkzeugfrage, vgl. `p12/T-0007`) und nicht für dieses Ticket.

    Rückgabe::

        {ROLLE: {"chain": [...], "script_tasks": [...], "typen": {typ: [chain]}}}
    """
    rollen, rolle = {}, None
    if not os.path.exists(pfad):
        return rollen
    with open(pfad, encoding="utf-8") as f:
        for zeile in f.read().replace("\r\n", "\n").split("\n"):
            ohne = zeile.split("#", 1)[0].rstrip()
            m = _ROLLE_RE.match(ohne)
            if m:
                rolle = m.group(1)
                rollen[rolle] = {"chain": [], "script_tasks": [], "typen": {}}
                continue
            if rolle is None:
                continue
            if ohne.strip().startswith("provider_chain:"):
                rollen[rolle]["chain"] = _liste(ohne)
            elif ohne.strip().startswith("script_tasks:"):
                rollen[rolle]["script_tasks"] = _liste(ohne)
            else:
                mt = _TYP_RE.match(ohne)
                if mt:
                    mc = _CHAIN_RE.search(mt.group(2))
                    rollen[rolle]["typen"][mt.group(1)] = (
                        [s.strip() for s in mc.group(1).split(",") if s.strip()]
                        if mc else [])
    return rollen


def _liste(zeile):
    inhalt = zeile.split(":", 1)[1].strip()
    if inhalt.startswith("[") and inhalt.endswith("]"):
        return [s.strip() for s in inhalt[1:-1].split(",") if s.strip()]
    return []


def geplante_kette(rollen, rolle, aufgaben_typ):
    """Die geplante Kette — Auflösung **in der Reihenfolge, die die Datei selbst nennt**.

    1. Aufgaben-Typ in `script_tasks`? → `["script"]`, kein LLM.
    2. `aufgaben_typen.<typ>` vorhanden? → dessen `chain`.
    3. sonst → `provider_chain` der Rolle.

    Diese Reihenfolge steht im Kopf von `registry.yaml`; sie hier **anders** zu
    beantworten hieße, zwei Wahrheiten über dieselbe Frage zu führen.
    """
    r = rollen.get((rolle or "").upper())
    if not r:
        return []
    if aufgaben_typ and aufgaben_typ in r["script_tasks"]:
        return ["script"]
    if aufgaben_typ and aufgaben_typ in r["typen"]:
        return list(r["typen"][aufgaben_typ])
    return list(r["chain"])


def soll_ist(eintraege, rollen):
    """Soll/Ist je Lauf **und** die namentlich nicht zuordenbaren (SWR-140).

    Rückgabe::

        {"zuordnungen": [ {rolle, aufgaben_typ, ticket, soll, ist, urteil}, … ],
         "nicht_zuordenbar": [ {rolle, ticket, ist, grund}, … ],
         "n_gesamt": …}

    ⚠ `n_gesamt` zählt **alle** Läufe, auch die nicht zuordenbaren. Ein Nenner, aus dem
    die unbequemen Fälle herausfallen, macht jede Quote besser, als sie ist.
    """
    zuordnungen, offen = [], []
    for e in eintraege:
        typ = e.get("aufgaben_typ") or ""
        ist = e.get("provider") or ""
        if not typ:
            offen.append({"rolle": e.get("rolle", ""), "ticket": e.get("ticket", ""),
                          "ist": ist, "grund": "aufgaben_typ fehlt"})
            continue
        soll = geplante_kette(rollen, e.get("rolle"), typ)
        if not soll:
            urteil = SOLL_IST_UNBEKANNT
        elif ist and ist == soll[0]:
            urteil = SOLL_IST_PASST
        elif ist and ist in soll:
            urteil = SOLL_IST_ABWEICHEND_MIT_GRUND
        else:
            urteil = SOLL_IST_ABWEICHUNG
        zuordnungen.append({"rolle": e.get("rolle", ""), "aufgaben_typ": typ,
                            "ticket": e.get("ticket", ""), "soll": soll, "ist": ist,
                            "urteil": urteil})
    return {"zuordnungen": zuordnungen, "nicht_zuordenbar": offen,
            "n_gesamt": len(eintraege)}


def bericht(registry_pfad, rollen_pfad):
    """Der ganze Report als Text — die Antwort auf `promt-team/N-0001`.

    ⚠ Er liefert womöglich **keine Zahl**. Das ist kein Mangel des Berichts, sondern
    sein Ergebnis: solange kein Lauf Token meldet, ist die richtige Antwort auf *„welche
    Rollen über Claude, welche über Ollama?"* die **benannte Lücke** und nicht eine
    siebenfache Null, die wie eine Messung aussieht.
    """
    eintraege, kaputt = lies_registry(registry_pfad)
    rollen = lies_rollen_registry(rollen_pfad)
    rollen_stat = je_rolle(eintraege)
    si = soll_ist(eintraege, rollen)
    z = []
    z.append(f"# Telemetrie je Rolle — {len(eintraege)} Lauf/Läufe "
             f"({kaputt} unlesbare Zeile(n))")
    z.append("")
    if not eintraege:
        z.append("KEINE Läufe in der Registry — es gibt nichts auszuwerten, und das ist")
        z.append("die Aussage, nicht eine Null.")
        return "\n".join(z) + "\n"
    for rolle, werte in rollen_stat.items():
        z.append(f"## {rolle} — {werte['n_laeufe']} Lauf/Läufe")
        for feld in FELDER:
            a = werte[feld]
            if a["zustand"] == ZUSTAND_NICHT_GELIEFERT:
                z.append(f"  {feld}: NICHT GELIEFERT "
                         f"(0 von {a['n_gesamt']} Läufen gemessen)")
            else:
                z.append(f"  {feld}: Summe {a['summe']}, Mittel "
                         f"{a['mittel']:.4g} — GEMESSEN AN {a['n_gemessen']} VON "
                         f"{a['n_gesamt']} Läufen")
        if werte["blocker"]:
            fehlend = ", ".join(f"{f} ({n}x)" for f, n in werte["blocker"].items())
            z.append(f"  BLOCKER: {fehlend}")
        z.append("")
    z.append(f"## Soll/Ist der Provider-Kette — {si['n_gesamt']} Lauf/Läufe")
    for zu in si["zuordnungen"]:
        z.append(f"  [{zu['urteil']}] {zu['rolle']}/{zu['aufgaben_typ']} "
                 f"({zu['ticket']}): geplant {zu['soll']}, gelaufen '{zu['ist']}'")
    if si["nicht_zuordenbar"]:
        z.append(f"  ⚠ NICHT ZUORDENBAR: {len(si['nicht_zuordenbar'])} von "
                 f"{si['n_gesamt']} Läufen — namentlich:")
        for o in si["nicht_zuordenbar"]:
            z.append(f"     {o['rolle']}/{o['ticket']} (gelaufen '{o['ist']}') "
                     f"— {o['grund']}")
        z.append("  Solange dieser Anteil nicht null ist, ist jede Quote unten eine")
        z.append("  Quote über die zuordenbaren Läufe und nicht über die Läufe.")
    return "\n".join(z) + "\n"
