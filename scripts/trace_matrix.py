#!/usr/bin/env python3
"""SWR↔Test-Traceability-Matrix (T-0026, Retro-CR 3/3 aus Sprint 2).

Liest SWR-IDs aus den Docstrings der Unit-Tests (Auflösung: Methode vor
Klasse vor Modul — der nächstgelegene Docstring mit SWR-IDs gewinnt) und den
Anforderungsstatus aus `p0/requirements/software/software-requirements.md`,
und generiert die Matrix nach `p0/verification/reports/swr-test-matrix.md`.

Lücken-Regel (G1-Punkt 1, g1-vorlage.md): Jede SWR mit Status `reviewed`
ohne Unit-Test-Abdeckung wird als Lücke ausgewiesen — außer ihr
Verification-Eintrag nennt ausdrücklich einen CI-/Workflow-Nachweis.
`--check`: Exit 1 bei Lücken (CI-Gate-Vorstufe, Playbook Kap. 3).
"""
import argparse
import ast
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import board  # noqa: E402  — gemeinsame Projekt-Discovery (SWR-070, p9/T-0007)

SWR_RE = re.compile(r"SWR-\d{3}")
PRODUKTE_CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                            "orchestrator", "config", "produkte.yaml")


def swr_quellen_alle_projekte(wurzel):
    """T-0010(p1): SWR-Dokumente aller Projekte per Discovery (tickets/ + requirements).

    SWR-070/p9-T-0007: nutzt dieselbe Discovery wie Board und Cockpit — damit zählen
    auch Projektordner im Sammel-Repo `projects/` (pm/D003, ab P10) zur Matrix."""
    quellen = []
    for _name, basis in board.projekt_pfade(wurzel):
        pfad = os.path.join(basis, "requirements", "software",
                            "software-requirements.md")
        if os.path.exists(pfad):
            quellen.append(pfad)
    return quellen


def lade_produkt_cfg(name, wurzel, cfg_pfad=None):
    """T-0064: Matrix-Parameter eines Produkts aus produkte.yaml (Pfade absolut)."""
    try:
        import yaml
    except ImportError:
        raise RuntimeError("PyYAML fehlt für --produkt (pip install pyyaml).")
    daten = yaml.safe_load(open(cfg_pfad or PRODUKTE_CFG, encoding="utf-8"))
    if name not in (daten.get("produkte") or {}):
        raise RuntimeError(f"Produkt '{name}' nicht in produkte.yaml "
                           f"(bekannt: {', '.join(daten.get('produkte', {}))}).")
    cfg = daten["produkte"][name]
    # p2/T-0002: normpath — produkte.yaml nutzt '/'-Pfade; unter Windows sonst
    # gemischte Trenner (erster realer Suite-Lauf auf dem Team-Node deckte das auf).
    return {"tests": os.path.normpath(os.path.join(wurzel, cfg["tests"])),
            "swr": os.path.normpath(os.path.join(wurzel, cfg["swr"])),
            "ziel": os.path.normpath(os.path.join(wurzel, cfg["ziel"])),
            "id_muster": cfg.get("id_muster", SWR_RE.pattern)}


def _ids(node, muster=SWR_RE):
    return set(muster.findall(ast.get_docstring(node) or ""))


def tests_scannen(tests_dir, muster=SWR_RE):
    """(abdeckung: swr -> [test-id], ohne_bezug: [test-id]) aus allen test_*.py.

    muster: Anforderungs-ID-Regex (T-0048 — Produkt-Repos mit eigenem Schema)."""
    abdeckung, ohne_bezug = {}, []
    for datei in sorted(os.listdir(tests_dir)):
        if not (datei.startswith("test_") and datei.endswith(".py")):
            continue
        baum = ast.parse(open(os.path.join(tests_dir, datei), encoding="utf-8").read())
        modul_ids = _ids(baum, muster)
        for kl in [n for n in baum.body if isinstance(n, ast.ClassDef)]:
            klassen_ids = _ids(kl, muster) or modul_ids
            for fn in [n for n in kl.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and n.name.startswith("test_")]:
                ids = _ids(fn, muster) or klassen_ids
                test_id = f"{datei}::{kl.name}::{fn.name}"
                if ids:
                    for i in sorted(ids):
                        abdeckung.setdefault(i, []).append(test_id)
                else:
                    ohne_bezug.append(test_id)
    return abdeckung, ohne_bezug


def swr_lesen(pfad, muster=SWR_RE):
    """SWR-Tabellenzeilen parsen: id -> {requirement, verification, status}."""
    eintraege = {}
    for zeile in open(pfad, encoding="utf-8"):
        m = re.match(rf"\|\s*({muster.pattern})\s*\|", zeile)
        if m:
            teile = [t.strip() for t in zeile.strip().strip("|").split("|")]
            if len(teile) >= 6:
                eintraege[teile[0]] = {"requirement": teile[1],
                                       "verification": teile[3], "status": teile[5]}
    return eintraege


def bestand_ids(ziel, muster=SWR_RE):
    """SWR-158: IDs der **vorhandenen** Zielmatrix — `None`, wenn es sie noch nicht gibt.

    ⚠ `None` und `set()` sind ausdrücklich zweierlei. Eine Matrix, die es noch nie gab,
    kann nicht schrumpfen; eine, die es gibt und leer ist, sehr wohl. Beides auf `set()`
    abzubilden hiesse, den ersten Schreibvorgang wie einen Totalverlust aussehen zu
    lassen — und das waere ein Dauerbefund am Tag der Einfuehrung (SWR-109/110/112).

    Gelesen werden **nur Tabellenzeilen**, und dort nur die **erste Spalte**. Die Datei
    nennt dieselben IDs weiter unten noch einmal (Lueckenliste, „in Tests referenziert,
    aber nicht im Anforderungsdokument"); wer sie mitzaehlt, vergleicht den Bestand mit
    einer anderen Menge als der, die `generiere()` als Tabelle schreibt.
    """
    if not os.path.isfile(ziel):
        return None
    ids = set()
    with open(ziel, encoding="utf-8") as f:
        for zeile in f:
            if not zeile.lstrip().startswith("|"):
                continue
            erste = zeile.strip().strip("|").split("|")[0].strip()
            if muster.fullmatch(erste):
                ids.add(erste)
    return ids


def generiere(swrs, abdeckung, ohne_bezug):
    """(markdown, luecken) — Matrix + Lückenliste."""
    zeilen = ["# SWR ↔ Test-Matrix (generiert von platform/scripts/trace_matrix.py — "
              "nicht von Hand editieren)", ""]
    n_rev = sum(1 for e in swrs.values() if e["status"] == "reviewed")
    zeilen.append(f"Stand: {date.today().isoformat()} · SWRs: {len(swrs)} "
                  f"(reviewed: {n_rev}) · Tests mit SWR-Bezug: "
                  f"{sum(len(v) for v in abdeckung.values())} · ohne Bezug: {len(ohne_bezug)}")
    zeilen += ["", "| SWR | Status | Unit-Tests | Abdeckung |", "|---|---|---|---|"]
    luecken = []
    for swr in sorted(swrs):
        e, tests = swrs[swr], abdeckung.get(swr, [])
        if tests:
            deckung = f"{len(tests)} Test(s)"
        elif e["status"] == "reviewed" and re.search(r"workflow|CI-Lauf", e["verification"], re.I):
            deckung = "über CI-Workflow verifiziert (kein Unit-Test)"
        elif e["status"] == "reviewed" and re.search(r"checklist|Checkliste", e["verification"]):
            deckung = "manuelle Abnahme dokumentiert (p0/verification/reports/) — kein Unit-Test"
        elif e["status"] == "reviewed":
            deckung = "**LÜCKE**"
            luecken.append(swr)
        else:
            deckung = f"offen (Status {e['status']})"
        zeilen.append(f"| {swr} | {e['status']} | {'<br>'.join(tests) or '—'} | {deckung} |")
    unbekannt = sorted(set(abdeckung) - set(swrs))
    if unbekannt:
        zeilen += ["", "## In Tests referenziert, aber nicht im Anforderungsdokument", ""]
        zeilen += [f"- {s}: {', '.join(abdeckung[s])}" for s in unbekannt]
        luecken += unbekannt
    zeilen += ["", "## Lücken (reviewed ohne Testabdeckung)", ""]
    zeilen.append("Keine." if not luecken else "\n".join(f"- {s}" for s in sorted(set(luecken))))
    zeilen += ["", "## Tests ohne SWR-Bezug (informativ — Prozess-Tooling mit CR-Bezug erlaubt, T-0025)", ""]
    zeilen.append("Keine." if not ohne_bezug else "\n".join(f"- {t}" for t in ohne_bezug))
    return "\n".join(zeilen) + "\n", sorted(set(luecken))


def main():
    p = argparse.ArgumentParser(description="SWR↔Test-Matrix generieren (T-0026, T-0048)")
    p.add_argument("--repos", default=".", help="Wurzel mit platform/ und p0/")
    p.add_argument("--check", action="store_true", help="Exit 1 bei Lücken (CI-Gate)")
    p.add_argument("--tests", help="Tests-Verzeichnis (Default: <repos>/platform/tests)")
    p.add_argument("--swr", action="append",
                   help="SWR-Markdown, mehrfach möglich — Quellen werden zu EINER "
                        "Matrix zusammengeführt (SWR-029; Default: p0-Dokument)")
    p.add_argument("--ziel", help="Ziel-Matrix (Default: <repos>/p0/verification/"
                                  "reports/swr-test-matrix.md)")
    p.add_argument("--id-muster", default=SWR_RE.pattern,
                   help="Regex für Anforderungs-IDs (T-0048, z.B. 'SWR-D\\d{2}')")
    p.add_argument("--produkt", help="Produktname aus config/produkte.yaml (T-0064) — "
                                     "ersetzt --tests/--swr/--ziel/--id-muster")
    p.add_argument("--alle-projekte", action="store_true",
                   help="T-0010(p1): SWR-Quellen per Discovery — seit SWR-145 der "
                        "Standardfall; das Flag bleibt für bestehende Aufrufer wirksam")
    a = p.parse_args()
    wurzel = os.path.abspath(a.repos)
    # SWR-145 (platform/T-0019): **Discovery ist der Normalfall, nicht die Zuschaltung.**
    #
    # Bis Sprint 17 war `--alle-projekte` aus und das Ziel trotzdem die kanonische Matrix.
    # Beide Voreinstellungen sind für sich vertretbar; zusammen schreiben sie den
    # unvollständigen Modus an den Ort des vollständigen. Ein Aufruf ohne Flag hat in
    # Sprint 17 die Matrix mit 24 von 143 Anforderungen überschrieben, „Matrix geschrieben"
    # gemeldet und Exit 0 gegeben.
    #
    # ⚠ Ein ausdrückliches `--swr` gewinnt weiter: es ist die einzige Stelle, an der der
    # Aufrufer nachweislich etwas anderes gemeint hat (und `--produkt` setzt es eine Zeile
    # tiefer selbst). Ohne diese Bedingung wäre der Produktmodus still kaputt — seine
    # Matrix ist absichtlich klein.
    #
    # ⚠ `--alle-projekte` bleibt wirksam und wird nicht entfernt: `abschluss.cmd` und die
    # CI übergeben es. Eine Reparatur, die den korrekten Aufrufer zerbricht, ist keine.
    if not a.swr:
        a.swr = swr_quellen_alle_projekte(wurzel)
    if a.produkt:
        cfg = lade_produkt_cfg(a.produkt, wurzel)
        a.tests, a.swr, a.ziel, a.id_muster = (cfg["tests"], [cfg["swr"]],
                                               cfg["ziel"], cfg["id_muster"])
    muster = re.compile(a.id_muster)
    # SWR-145: Der alte Rückfall auf **p0 allein** ist weg. Er war der Ort, an dem der
    # unvollständige Modus entstand — und er sah wie ein harmloser Default aus, weil `p0`
    # tatsächlich die meisten Anforderungen führt. Findet die Discovery nichts, ist das
    # ein Befund und keine Gelegenheit für eine Ersatzquelle.
    #
    # ⚠ Die Prüfung steht **vor** `tests_scannen` und nicht dahinter: sie soll den Grund
    # nennen, aus dem nichts geschrieben wird. Stand sie dahinter, gewann bei einer
    # fehlenden Testverzeichnis-Angabe deren `FileNotFoundError` — eine Meldung über das
    # zweite Problem, während das erste die Ursache war.
    swr_dateien = a.swr or []
    if not swr_dateien:
        print("KEINE SWR-QUELLE gefunden — weder per --swr noch per Discovery unter "
              f"{wurzel}. Es wird NICHTS geschrieben (SWR-145: eine leere Matrix an den "
              f"Ort der echten zu schreiben wäre der Fehler, den dieses Werkzeug hatte).")
        sys.exit(1)
    abdeckung, ohne = tests_scannen(
        a.tests or os.path.join(wurzel, "platform", "tests"), muster)
    swrs = {}
    for pfad in swr_dateien:  # SWR-029: mehrere Anforderungsquellen, eine Matrix
        swrs.update(swr_lesen(pfad, muster))
    text, luecken = generiere(swrs, abdeckung, ohne)
    ziel = a.ziel or os.path.join(wurzel, "p0", "verification", "reports",
                                  "swr-test-matrix.md")
    # SWR-158 (platform/T-0020): **Der Generator liest seinen eigenen Vorgänger, bevor
    # er ihn ersetzt.** Sprint 17: die Matrix verlor 121 Zeilen, die Anzahl fiel von 143
    # auf 24, die Meldung lautete „Matrix geschrieben" und der Exit-Code war 0.
    #
    # ⚠ Die drei Fragen, die diesen Bau vier Sprints lang zurückgehalten haben, sind in
    # Sprint 22 **gemessen** beantwortet worden — über alle 95 Commits der Datei, ID-Menge
    # je Fassung, 94 Übergänge, **kein einziger** mit einer verschwundenen ID:
    #
    #   Frage 1 — Anzahl oder IDs? **IDs.** Nicht aus Prinzip: die ID-Prüfung hätte über
    #   die gesamte Historie **null** Fehlalarme erzeugt, eine Anzahl-Prüfung wäre bei
    #   gleichbleibendem Umfang blind gewesen.
    #
    #   Frage 2 — wann ist Schrumpfen legitim, und wer sagt es? **Vorerst: nie.** Die drei
    #   gedachten Ausnahmen (`rejected`, eigene Produktmatrix, archiviertes Projekt) sind
    #   an der kanonischen Matrix **noch nie eingetreten**; eine `rejected` Anforderung
    #   bleibt ohnehin als Zeile stehen. *Ein Flag, das jeder Aufrufer setzt, ist keine
    #   Regel — und eine Ausnahme, die es noch nie gab, ist keine Ausnahme, sondern eine
    #   Vermutung über die Zukunft.* Deshalb **kein** `--darf-schrumpfen`.
    #
    #   Frage 3 — gilt sie auch für `--produkt`? **Ja, aber je Ziel.** Verglichen wird
    #   gegen die **Zieldatei**, die der Aufruf ohnehin kennt. Eine Produktmatrix misst
    #   sich an ihrer eigenen Vorgängerin und nie an der kanonischen; damit scheitert die
    #   Prüfung nicht an ihrer eigenen Ausnahme, weil sie keine braucht.
    #
    # ⚠ Es wird **nichts geschrieben**. Dieselbe Bauform wie SWR-145 eine Ebene höher:
    # der Schaden von Sprint 17 lebte und starb in einer Arbeitskopie und hat die Commits
    # nie erreicht — eine Warnung nach dem Schreiben hätte ihn nicht verhindert.
    alt = bestand_ids(ziel, muster)
    if alt is not None:
        verschwunden = sorted(alt - set(swrs))
        if verschwunden:
            print(f"BESTAND SCHRUMPFT — {len(verschwunden)} Anforderungs-ID(s) der "
                  f"vorhandenen Matrix fehlen im neuen Stand: {', '.join(verschwunden)}. "
                  f"Bestand {len(alt)}, neu {len(swrs)}. Es wird NICHTS geschrieben "
                  f"(SWR-158). Ziel: {os.path.relpath(ziel, wurzel)}")
            sys.exit(1)
    os.makedirs(os.path.dirname(ziel), exist_ok=True)
    open(ziel, "w", encoding="utf-8", newline="\n").write(text)
    print(f"Matrix geschrieben: {os.path.relpath(ziel, wurzel)} — "
          f"{len(swrs)} SWRs, {len(luecken)} Lücke(n).")
    sys.exit(1 if (a.check and luecken) else 0)


if __name__ == "__main__":
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import konsole
    konsole.sichere_ausgabe()  # platform/T-0009: am Melden nicht sterben
    main()
