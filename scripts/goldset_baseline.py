#!/usr/bin/env python3
"""goldset_baseline.py — die gemessene Baseline des Goldsets (SWR-149, promt-team/T-0007).

**Was hier gemessen wird, und was ausdrücklich nicht.** `promt-team/T-0007` DoD 4 verlangt:
*„Die Erfolgsquote der heutigen Fassung ist gemessen — ohne sie ist dieses Ticket eine
Sammlung und keine Messgrundlage."* Messbar ist genau eine Sache, und sie ist nicht die,
die man beim ersten Lesen erwartet:

> **Gemessen wird, ob die Prüfung eines Falls gegen den BESTAND aufgeht — also gegen das,
> was die Rolle damals hervorgebracht hat und was heute im Repo liegt. NICHT gemessen wird
> ein frischer Lauf der Rolle.**

Ein frischer Lauf braucht einen Provider. Diese Umgebung hat keinen (nachgesehen, nicht
vermutet), und ein Provider-Lauf kostet Geld — das ist Klasse A und liegt beim Menschen.
Die Zahl aus einem nicht gelaufenen Lauf zu schätzen wäre B027/B038, und zwar an der
Stelle, an der die ganze Messgrundlage hängt.

⚠ **Deshalb drei Zustände und nicht zwei** (die Lehre von SWR-137, hier am Nachbarfall
angewandt): `erfuellt`, `nicht_erfuellt` und `nicht_entscheidbar`. Ein Fall ohne
`ergebnis_heute` ist **nicht** durchgefallen — er ist unentschieden, und er wird
**namentlich** geführt. Ihn als Fehlschlag zu zählen machte die Quote schlechter, ihn
wegzulassen machte sie besser; beides wäre eine erfundene Zahl.

⚠⚠ **Die Trennschärfe ist die zweite Messung, und sie ist die unbequemere.** Eine Prüfung,
deren Suchtext auch in den Artefakten *anderer* Fälle steht, geht auf, ohne etwas zu
unterscheiden. Eine Quote von 100 % über Prüfungen, die überall aufgehen, ist kein
Ergebnis, sondern ein Maß für die Beliebigkeit der Suchtexte. Der Bericht nennt sie
deshalb neben der Quote und nicht in einer Fußnote.

Nutzung:
    python goldset_baseline.py --repos <wurzel> [--schreibe]
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend import goldset  # noqa: E402
import konsole  # noqa: E402

GOLDSET = "promt-team/management/goldset.jsonl"
BERICHT = "promt-team/management/goldset-baseline.md"

#: Die drei Zustände einer Fallmessung. ⚠ Sie stehen **hier** und werden gelesen, nicht
#: wiederholt — dieselbe Entscheidung wie bei `goldset.PRUEF_ARTEN` (SWR-131).
ZUSTAENDE = ("erfuellt", "nicht_erfuellt", "nicht_entscheidbar")


def _lies_text(wurzel, pfad):
    voll = os.path.join(wurzel, *pfad.split("/"))
    if not os.path.isfile(voll):
        return None
    try:
        with open(voll, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def _json_pfad(text, pfad):
    """Punktpfad in einem JSON- oder JSONL-Dokument auflösen -> `(gefunden, wert)`.

    JSONL wird als Liste gelesen; `0.nr` ist damit „Feld `nr` der ersten Zeile".
    """
    try:
        daten = json.loads(text)
    except ValueError:
        daten = []
        for zeile in text.splitlines():
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                daten.append(json.loads(zeile))
            except ValueError:
                return False, None
    knoten = daten
    for teil in pfad.split("."):
        if isinstance(knoten, dict) and teil in knoten:
            knoten = knoten[teil]
        elif isinstance(knoten, list) and teil.isdigit() and int(teil) < len(knoten):
            knoten = knoten[int(teil)]
        else:
            return False, None
    return True, knoten


def messe_fall(fall, wurzel):
    """Ein Fall gegen den Bestand -> `(zustand, begruendung)`.

    ⚠ `nicht_entscheidbar` ist ein **eigener** Ausgang und keine Verlegenheit: die Prüfung
    braucht ein Artefakt, und wenn keines benannt ist, sagt der Fall nichts über die Rolle
    aus — weder gut noch schlecht.
    """
    pruefung = fall.get("fehlschlag_erkannt_an") or {}
    art, wert = pruefung.get("art"), str(pruefung.get("wert") or "")
    if art == "datei_existiert":
        # ⚠ Diese Art braucht KEIN `ergebnis_heute`: ihr `wert` IST der Pfad. Sie hier mit
        # dem gleichen Vorbehalt zu behandeln wie die Textarten hiesse, eine ausfuehrbare
        # Pruefung als unentscheidbar zu fuehren.
        voll = os.path.join(wurzel, *wert.split("/"))
        if os.path.exists(voll):
            return "erfuellt", f"{wert} liegt im Bestand"
        return "nicht_erfuellt", f"{wert} fehlt im Bestand"
    ziel = fall.get("ergebnis_heute")
    if not ziel:
        return ("nicht_entscheidbar",
                "kein 'ergebnis_heute' benannt — der Fall sagt ueber den Bestand nichts, "
                "und eine Zahl daraus waere erfunden")
    text = _lies_text(wurzel, ziel)
    if text is None:
        return "nicht_entscheidbar", f"{ziel} ist nicht lesbar"
    if art == "enthaelt":
        return (("erfuellt", f"'{wert}' steht in {ziel}") if wert in text
                else ("nicht_erfuellt", f"'{wert}' fehlt in {ziel}"))
    if art == "enthaelt_nicht":
        return (("erfuellt", f"'{wert}' steht nicht in {ziel}") if wert not in text
                else ("nicht_erfuellt", f"'{wert}' steht in {ziel}, soll aber nicht"))
    if art == "regex":
        try:
            treffer = re.search(wert, text) is not None
        except re.error as e:
            return "nicht_entscheidbar", f"regex laeuft nicht: {e}"
        return (("erfuellt", f"Muster trifft in {ziel}") if treffer
                else ("nicht_erfuellt", f"Muster trifft nicht in {ziel}"))
    if art == "json_pfad":
        gefunden, w = _json_pfad(text, wert)
        return (("erfuellt", f"{wert} = {w!r} in {ziel}") if gefunden
                else ("nicht_erfuellt", f"{wert} gibt es in {ziel} nicht"))
    return "nicht_entscheidbar", f"unbekannte Pruefart '{art}'"


def trennschaerfe(faelle, wurzel):
    """Je Fall: in wie vielen **fremden** Artefakten des Sets geht seine Prüfung auch auf?

    ⚠ Das ist die Messung gegen die bequemste Art, ein Goldset grün zu bekommen: einen
    Suchtext zu wählen, der überall steht. Nur Textarten sind betroffen — `datei_existiert`
    hat kein fremdes Artefakt, in dem es aufgehen könnte.
    """
    artefakte = {}
    for fall in faelle:
        ziel = fall.get("ergebnis_heute")
        if ziel and ziel not in artefakte:
            artefakte[ziel] = _lies_text(wurzel, ziel) or ""
    ergebnis = []
    for fall in faelle:
        pruefung = fall.get("fehlschlag_erkannt_an") or {}
        art, wert = pruefung.get("art"), str(pruefung.get("wert") or "")
        eigen = fall.get("ergebnis_heute")
        if art not in ("enthaelt", "regex") or not eigen:
            ergebnis.append(None)
            continue
        fremd = 0
        for pfad, text in artefakte.items():
            if pfad == eigen:
                continue
            if art == "enthaelt" and wert in text:
                fremd += 1
            elif art == "regex":
                try:
                    if re.search(wert, text):
                        fremd += 1
                except re.error:
                    pass
        ergebnis.append(fremd)
    return ergebnis


def messe(wurzel):
    """Der ganze Lauf -> Kennzahlen-Wörterbuch. Keine Formatierung, keine Datei."""
    pfad = os.path.join(wurzel, *GOLDSET.split("/"))
    faelle, kaputt = goldset.lies(pfad)
    maengel = goldset.pruefe_set(faelle, wurzel=wurzel) if faelle else []
    messungen = [messe_fall(f, wurzel) for f in faelle]
    fremd = trennschaerfe(faelle, wurzel)
    return {"faelle": faelle, "kaputte_zeilen": kaputt, "maengel": maengel,
            "messungen": messungen, "fremdtreffer": fremd,
            "goldset_pfad": GOLDSET}


def _quote(erfuellt, entscheidbar):
    """⚠ Immer **mit** Nenner. Eine Quote ohne ihn ist von einer vollständigen Messung
    nicht zu unterscheiden — der Befund von SWR-140, hier eingehalten statt zitiert."""
    if not entscheidbar:
        return "NICHT MESSBAR (0 entscheidbare Faelle)"
    return f"{100.0 * erfuellt / entscheidbar:.1f} % ({erfuellt} von {entscheidbar})"


def bericht(daten):
    """Der Bericht als Text. Er nennt zuerst, was **nicht** gemessen ist."""
    faelle, messungen = daten["faelle"], daten["messungen"]
    fremd = daten["fremdtreffer"]
    z = []
    z.append("# Goldset-Baseline (SWR-149, `promt-team/T-0007` DoD 4)")
    z.append("")
    z.append(f"**{len(faelle)} Faelle**, {daten['kaputte_zeilen']} unlesbare Zeile(n), "
             f"Quelle `{daten['goldset_pfad']}`.")
    z.append("")
    z.append("## ⚠⚠ Was hier NICHT gemessen ist")
    z.append("")
    z.append("Gemessen ist, ob die Pruefung eines Falls **gegen den Bestand** aufgeht — "
             "gegen das, was die Rolle damals hervorgebracht hat und was heute im Repo "
             "liegt. **Nicht** gemessen ist ein **frischer Lauf** der Rolle: dafuer "
             "braucht es einen Provider, diese Umgebung hat keinen, und ein Provider-Lauf "
             "kostet Geld (Klasse A, liegt beim Menschen).")
    z.append("")
    z.append("> **Diese Baseline sagt, dass die Faelle ausfuehrbar sind und gegen welchen "
             "Stand sie aufgehen. Sie sagt NICHT, wie gut eine Rolle heute arbeitet.**")
    z.append("")
    z.append("⚠⚠ **Und deshalb ist eine hohe Bestandsquote hier KEIN gutes Zeugnis.** Die "
             "Pruefausdruecke sind aus den Artefakten **abgeleitet**, die im Bestand "
             "liegen — dass sie dort aufgehen, ist zu einem grossen Teil **Bauart und "
             "nicht Befund**. Wer die Spalte 'Quote' unten als Aussage ueber die Qualitaet "
             "der Rollen liest, liest sie falsch, und das steht hier, weil eine Zahl ohne "
             "diesen Satz genau so gelesen wuerde.")
    z.append("")
    z.append("> **Der Wert dieser Messung liegt in den drei anderen Spalten: dass jeder "
             "Fall AUSFUEHRBAR ist, dass jeder Fall BELEGT ist, und dass genannt wird, "
             "welche Faelle sich gegen den Bestand gar nicht entscheiden lassen.**")
    z.append("")
    z.append("Fuer das Eval-Gate (`promt-team/T-0003`) ist damit **eine** Eingabe offen, "
             "und sie ist benannt: die Erfolgsquote eines frischen Laufs je Rolle.")
    z.append("")
    if daten["maengel"]:
        z.append("## ⚠ Maengel des Sets")
        z.append("")
        for m in daten["maengel"]:
            z.append(f"- {m}")
        z.append("")
    else:
        z.append("**Set geprueft:** Form, Herkunft **gegen den Bestand aufgeloest** und "
                 "`rolle`/`aufgaben_typ` gegen `process/roles/registry.yaml` — 0 Maengel.")
        z.append("")
    rollen = {}
    for fall, (zustand, _) in zip(faelle, messungen):
        r = rollen.setdefault(fall.get("rolle") or "(ohne Rolle)", {})
        t = r.setdefault(fall.get("aufgaben_typ") or "(ohne Typ)",
                         {k: 0 for k in ZUSTAENDE})
        t[zustand] += 1
    z.append("## Bestandsquote je Rolle und Aufgaben-Typ")
    z.append("")
    z.append("| Rolle | Aufgaben-Typ | Faelle | erfuellt | nicht erfuellt | "
             "nicht entscheidbar | Quote (mit Nenner) |")
    z.append("|---|---|---|---|---|---|---|")
    for r in sorted(rollen):
        for t in sorted(rollen[r]):
            c = rollen[r][t]
            n = sum(c.values())
            entscheidbar = c["erfuellt"] + c["nicht_erfuellt"]
            z.append(f"| {r} | {t} | {n} | {c['erfuellt']} | {c['nicht_erfuellt']} | "
                     f"{c['nicht_entscheidbar']} | {_quote(c['erfuellt'], entscheidbar)} |")
    z.append("")
    for r in sorted(rollen):
        e = sum(c["erfuellt"] for c in rollen[r].values())
        n = sum(c["nicht_erfuellt"] for c in rollen[r].values())
        u = sum(c["nicht_entscheidbar"] for c in rollen[r].values())
        z.append(f"- **{r.upper()}**: {e + n + u} Faelle, Bestandsquote "
                 f"{_quote(e, e + n)}, **{u} nicht entscheidbar**.")
    z.append("")
    offen = [(f, g) for f, (zu, g) in zip(faelle, messungen)
             if zu == "nicht_entscheidbar"]
    z.append("## Nicht entscheidbare Faelle — namentlich")
    z.append("")
    if not offen:
        z.append("Keine. Jeder Fall benennt ein Artefakt, gegen das seine Pruefung laeuft.")
    else:
        z.append("⚠ Sie sind **nicht** durchgefallen. Ein Fall als Fehlschlag zu zaehlen, "
                 "der nie gelaufen ist, waere eine erfundene Zahl (B038).")
        z.append("")
        for fall, grund in offen:
            # ⚠ „namentlich" heisst: mit der Belegstelle. Vier Zeilen `dev/bugfix` sind
            # eine Zaehlung und keine Nennung — der Fehler, den SWR-140 an den nicht
            # zuordenbaren Laeufen benannt hat, hier am eigenen Bericht vermieden.
            beleg = (fall.get("herkunft") or ["(ohne Beleg)"])[0]
            z.append(f"- `{fall.get('rolle')}/{fall.get('aufgaben_typ')}` "
                     f"— Beleg `{beleg}` — {grund}")
    z.append("")
    gemessen = [x for x in fremd if x is not None]
    stumpf = [(f, x) for f, x in zip(faelle, fremd) if x]
    z.append("## ⚠ Trennschaerfe der Pruefungen")
    z.append("")
    z.append(f"Von {len(gemessen)} textbasierten Pruefungen gehen **{len(stumpf)}** auch in "
             f"mindestens einem **fremden** Artefakt des Sets auf.")
    z.append("")
    z.append("> **Eine Pruefung, deren Suchtext ueberall steht, geht auf, ohne etwas zu "
             "unterscheiden. Eine Quote ueber solche Pruefungen misst die Beliebigkeit der "
             "Suchtexte und nicht die Arbeit der Rolle.**")
    z.append("")
    if stumpf:
        for fall, n in sorted(stumpf, key=lambda p: -p[1])[:12]:
            wert = (fall.get("fehlschlag_erkannt_an") or {}).get("wert")
            z.append(f"- `{fall.get('rolle')}/{fall.get('aufgaben_typ')}`: "
                     f"`{wert}` trifft in {n} fremden Artefakt(en)")
        z.append("")
        z.append("Diese Faelle sind **nicht falsch** — sie sind **schwach**. Sie zu "
                 "schaerfen ist Arbeit am Goldset und kein Fehlerbericht ueber die Rolle; "
                 "sie stillschweigend mitzuzaehlen waere der Fehler.")
        z.append("")
        z.append("⚠ **Und diese Messung kann eine Sache nicht unterscheiden:** einen "
                 "beliebigen Suchtext von einem Suchtext ueber eine **Konvention**. Wenn "
                 "eine Regel absichtlich an vielen Stellen gilt (etwa: *jeder "
                 "Subprozess-Aufruf legt seine Kodierung fest*), dann **soll** ihre "
                 "Pruefung ueberall aufgehen — ein hoher Wert ist dort das erwartete "
                 "Ergebnis und kein Mangel. Die Zahl wird deshalb **berichtet und nicht "
                 "erzwungen**; sie zu einem Gate zu machen hiesse, richtige Faelle zu "
                 "verbieten (SWR-131).")
    z.append("")
    belegt_mit_stelle = sum(1 for f in faelle
                            if any(goldset.HERKUNFT_TRENNER in h
                                   for h in (f.get("herkunft") or [])))
    z.append("## Beleglage")
    z.append("")
    z.append(f"- **{belegt_mit_stelle} von {len(faelle)}** Faellen belegen sich mit einer "
             f"**Stelle** in einer Datei, nicht nur mit einem Dateinamen.")
    z.append(f"- Faelle mit `soll_scheitern_auf`: "
             f"{sum(1 for f in faelle if f.get('soll_scheitern_auf'))}.")
    z.append(f"- Faelle mit benannter Auslassung (`sensibel_ausgelassen`): "
             f"{sum(1 for f in faelle if f.get('sensibel_ausgelassen'))}.")
    z.append("")
    return "\n".join(z) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description="Goldset-Baseline (SWR-149)")
    p.add_argument("--repos", default=".")
    p.add_argument("--schreibe", action="store_true",
                   help=f"Bericht nach {BERICHT} schreiben")
    a = p.parse_args(argv)
    wurzel = os.path.abspath(a.repos)
    daten = messe(wurzel)
    if not daten["faelle"]:
        print(f"KEIN GOLDSET: {GOLDSET} ist leer oder fehlt — es wird NICHTS geschrieben "
              "(ein leerer Bericht an der Stelle des echten ist der Fehler aus SWR-145).")
        return 1
    text = bericht(daten)
    if a.schreibe:
        ziel = os.path.join(wurzel, *BERICHT.split("/"))
        os.makedirs(os.path.dirname(ziel), exist_ok=True)
        with open(ziel, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"Bericht geschrieben: {BERICHT}")
    else:
        print(text)
    return 1 if daten["maengel"] else 0


if __name__ == "__main__":  # pragma: no cover
    konsole.sichere_ausgabe()
    sys.exit(main())
