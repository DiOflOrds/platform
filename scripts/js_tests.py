#!/usr/bin/env python3
"""js_tests.py — die JS-Teststrecke der Organisation (SWR-128; ADR-008).

Bis Sprint 12 hatte die Organisation **741 Python-Tests und null JS-Tests**, waehrend
`app.js` rund 1.500 Zeilen traegt und SWR-098/099/100 Nachweise an JavaScript verlangen.
ADR-008 schliesst die Luecke mit dem **eingebauten** Testrunner von Node (`node --test`) —
kein npm, kein `package.json`, keine heruntergeladene Abhaengigkeit.

⚠ **Node ist damit ein neues externes Werkzeug, und darueber entscheidet der Mensch.**
Der Auftraggeber hat `projects/p12/T-0007` am **2026-08-17 um 11:48** mit
**`B-node-optional`** entschieden — dem Default. Node ist damit **dauerhaft keine
Voraussetzung**: fehlt es, laeuft der Preflight weiter, aber er **sagt es**. Ein still
uebersprungener Test ist der Fehler aus SWR-114/SWR-122 in seiner schlimmsten Form: eine
Zeile, die nichts meldet, ist von einer Pruefung, die nie lief, nicht zu unterscheiden.

⚠ **Die Skip-Meldung nennt seit SWR-131 die getroffene Entscheidung und keine Frist
mehr.** Vorher verwies sie auf einen *offenen* DR mit Frist 24.08. — nach der Entscheidung
haette sie den Leser auf eine Frist geschickt, die niemand mehr abwartet, und ihn eine
Handlung erwarten lassen, die es nicht gibt. Der Preis von `B-node-optional` steht in
derselben Zeile, weil er sonst nirgends steht: ein Lauf ohne Node meldet STARTKLAR,
obwohl die JS-Regeln ungepruefte Flaeche sind.

Rueckgabe von `lauf()`: `{"zustand", "meldung", "tests", "fehler"}` mit
`zustand in {"ok", "rot", "uebersprungen"}` — genau die drei Faelle, die der Aufrufer
unterscheiden muss. `"uebersprungen"` ist **kein** `"ok"`.
"""
import os
import re
import shutil
import subprocess
import sys

TESTVERZEICHNIS = os.path.join("platform", "tests", "js")
MUSTER = re.compile(r".*\.test\.(c|m)?js$")


def testdateien(root):
    """Alle JS-Testdateien, sortiert. Ohne Verzeichnis: leere Liste, kein Fehler."""
    verz = os.path.join(root, *TESTVERZEICHNIS.split("/"))
    if not os.path.isdir(verz):
        return []
    return sorted(os.path.join(verz, n) for n in os.listdir(verz) if MUSTER.match(n))


def node_vorhanden():
    """Ist ein Node-Laufzeit im PATH? — der Fakt, an dem `uebersprungen` haengt."""
    return shutil.which("node") is not None


def lauf(root=".", timeout=120):
    """Die JS-Teststrecke ausfuehren. Meldet immer, auch wenn sie nicht lief."""
    dateien = testdateien(root)
    if not dateien:
        return {"zustand": "uebersprungen", "tests": 0, "fehler": 0,
                "meldung": "JS-Teststrecke: keine Testdateien unter "
                           f"{TESTVERZEICHNIS} — nichts zu pruefen."}
    if not node_vorhanden():
        return {"zustand": "uebersprungen", "tests": 0, "fehler": 0,
                "meldung": f"JS-Teststrecke: UEBERSPRUNGEN — 'node' nicht im PATH "
                           f"({len(dateien)} Testdatei(en) ungeprueft). Entschieden am "
                           f"2026-08-17: 'B-node-optional' (p12/T-0007, ADR-008) — Node "
                           f"ist keine Voraussetzung, dieser Lauf gilt trotz ungeprueften "
                           f"JS-Regeln als startklar. 'node --version' zeigt den Stand."}
    # `node --test <datei>...` statt `<verzeichnis>`: die Dateiliste ist die Auswahl,
    # die `testdateien` getroffen hat — eine zweite Auswahlregel im Runner waere B033.
    erg = subprocess.run(["node", "--test"] + dateien, cwd=root, capture_output=True,
                         text=True, encoding="utf-8", errors="replace", timeout=timeout)
    ausgabe = (erg.stdout or "") + (erg.stderr or "")
    tests = _zahl(ausgabe, "tests")
    fehler = _zahl(ausgabe, "fail")
    if erg.returncode == 0 and not fehler:
        return {"zustand": "ok", "tests": tests, "fehler": 0,
                "meldung": f"JS-Tests: OK — {tests} Tests gruen."}
    return {"zustand": "rot", "tests": tests, "fehler": fehler or 1,
            "meldung": f"JS-Tests: ROT — {fehler or '?'} von {tests} Tests rot.\n"
                       + _ausschnitt(ausgabe)}


def _zahl(ausgabe, name):
    m = re.search(r"(?m)^# %s (\d+)\s*$" % name, ausgabe)
    return int(m.group(1)) if m else 0


def _ausschnitt(ausgabe, zeilen=25):
    rot = [z for z in ausgabe.splitlines() if z.startswith("not ok") or "AssertionError" in z]
    return "\n".join(rot[:zeilen]) if rot else "\n".join(ausgabe.splitlines()[-zeilen:])


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = argv[argv.index("--repos") + 1] if "--repos" in argv else "."
    erg = lauf(os.path.abspath(root))
    print(erg["meldung"])
    return 1 if erg["zustand"] == "rot" else 0


if __name__ == "__main__":
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import konsole
    konsole.sichere_ausgabe()  # platform/T-0009: am Melden nicht sterben
    raise SystemExit(main())
