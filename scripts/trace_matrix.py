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

SWR_RE = re.compile(r"SWR-\d{3}")


def _ids(node):
    return set(SWR_RE.findall(ast.get_docstring(node) or ""))


def tests_scannen(tests_dir):
    """(abdeckung: swr -> [test-id], ohne_bezug: [test-id]) aus allen test_*.py."""
    abdeckung, ohne_bezug = {}, []
    for datei in sorted(os.listdir(tests_dir)):
        if not (datei.startswith("test_") and datei.endswith(".py")):
            continue
        baum = ast.parse(open(os.path.join(tests_dir, datei), encoding="utf-8").read())
        modul_ids = _ids(baum)
        for kl in [n for n in baum.body if isinstance(n, ast.ClassDef)]:
            klassen_ids = _ids(kl) or modul_ids
            for fn in [n for n in kl.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and n.name.startswith("test_")]:
                ids = _ids(fn) or klassen_ids
                test_id = f"{datei}::{kl.name}::{fn.name}"
                if ids:
                    for i in sorted(ids):
                        abdeckung.setdefault(i, []).append(test_id)
                else:
                    ohne_bezug.append(test_id)
    return abdeckung, ohne_bezug


def swr_lesen(pfad):
    """SWR-Tabellenzeilen parsen: id -> {requirement, verification, status}."""
    eintraege = {}
    for zeile in open(pfad, encoding="utf-8"):
        m = re.match(r"\|\s*(SWR-\d{3})\s*\|", zeile)
        if m:
            teile = [t.strip() for t in zeile.strip().strip("|").split("|")]
            if len(teile) >= 6:
                eintraege[teile[0]] = {"requirement": teile[1],
                                       "verification": teile[3], "status": teile[5]}
    return eintraege


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
    p = argparse.ArgumentParser(description="SWR↔Test-Matrix generieren (T-0026)")
    p.add_argument("--repos", default=".", help="Wurzel mit platform/ und p0/")
    p.add_argument("--check", action="store_true", help="Exit 1 bei Lücken (CI-Gate)")
    a = p.parse_args()
    wurzel = os.path.abspath(a.repos)
    abdeckung, ohne = tests_scannen(os.path.join(wurzel, "platform", "tests"))
    swrs = swr_lesen(os.path.join(wurzel, "p0", "requirements", "software",
                                  "software-requirements.md"))
    text, luecken = generiere(swrs, abdeckung, ohne)
    ziel = os.path.join(wurzel, "p0", "verification", "reports", "swr-test-matrix.md")
    os.makedirs(os.path.dirname(ziel), exist_ok=True)
    open(ziel, "w", encoding="utf-8", newline="\n").write(text)
    print(f"Matrix geschrieben: {os.path.relpath(ziel, wurzel)} — "
          f"{len(swrs)} SWRs, {len(luecken)} Lücke(n).")
    sys.exit(1 if (a.check and luecken) else 0)


if __name__ == "__main__":
    main()
