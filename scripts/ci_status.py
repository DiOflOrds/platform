#!/usr/bin/env python3
"""ci_status.py — CI-Läufe nach dem Push prüfen (SWR-105, platform/T-0003).

Beantwortet die Frage, für die bisher ein Mensch fünf Browser-Tabs öffnen musste:
**Sind die Actions-Läufe für die Commits, die gerade gepusht wurden, grün?**

Die Repos unter `DiOflOrds` sind öffentlich — die Actions-API antwortet ohne
Anmeldung. Es braucht **kein Token und keine Rechtevergabe**. Werden Repos später
privat, genügt eine Fine-grained PAT mit `Actions: Read` + `Metadata: Read` in der
Umgebungsvariablen `GITHUB_TOKEN`; gespeichert wird sie hier nie.

Die Regel, an der alles hängt (DoD 2 des Tickets):
**Ein grüner Lauf für einen ANDEREN Commit ist kein grüner Lauf.** Verglichen wird
der `head_sha` gegen den lokalen Commit. Ohne Treffer heißt das Ergebnis „noch kein
Lauf" — nie „grün". Dieselbe Vorsicht wie `session.stille` und `zuletzt_erledigt`.

**SWR-107 (platform/T-0004, Sprint 2):** Bei einem roten Repo nennt der Bericht Job
und Schritt. Anlass war der erste Hostlauf — er fand drei rote Repos und konnte für
zwei davon die Ursache nicht nennen. Ein `ROT` ohne Schritt ist eine Farbe und kein
Befund; es lässt genau die Lücke offen, die dieses Skript schließen sollte. Scheitert
die Nachfrage, bleibt das Repo **rot** und der Bericht sagt „Schritt unbekannt" —
eine Diagnose, die einen Befund verschluckt, wäre schlimmer als keine (B038).

Läuft auf dem HOST, nicht in der Cowork-Sandbox (die hat keinen GitHub-Zugang,
Guardrail 2). Aufgerufen aus `abschluss.cmd`, Schritt [5/5].

Nutzung:
    python ci_status.py --repos <wurzel> [--warten SEK] [--budget N]
                        [--json PFAD] [--md PFAD] [--leise]

Exit-Codes: 0 = alle geprüften Repos grün für ihren Commit, 1 = sonst, 2 = Aufrufsfehler.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import board  # noqa: E402  — gemeinsame Projekt-Discovery (SWR-070)

API = "https://api.github.com/repos/{slug}/actions/runs?branch={branch}&per_page=30"
# SWR-107: dieselbe API-Familie, dieselbe Anmeldefreiheit — die Diagnose eines roten
# Laufs. Ein `ROT` ohne Schritt ist eine Farbe und kein Befund; es lässt genau die
# Lücke offen, die SWR-105 schließen sollte (ein Mensch öffnet eine Seite).
JOBS_API = "https://api.github.com/repos/{slug}/actions/runs/{lauf}/jobs?per_page=50"
# Unangemeldet erlaubt GitHub 60 Abfragen je Stunde und IP. Das Budget ist deshalb
# keine Vorsichtsmaßnahme, sondern eine harte Grenze: 13 Repos je Runde sind vier
# Runden, mehr nicht. Wird es aufgebraucht, sagt der Bericht das — eine Grenze, die
# sich als Befund tarnt („kein Lauf"), wäre die stille Falschaussage aus B038.
BUDGET_STANDARD = 50
WARTEN_STANDARD = 120
RUNDE_SEK = 40

# Endzustände: hier wird nicht mehr nachgefragt. `kein_lauf` gehört bewusst NICHT
# dazu — nach einem Push ist es der Normalfall und wird zum Befund erst, wenn die
# Wartezeit abgelaufen ist.
FERTIG = ("gruen", "rot", "kein_ci", "fehler")

# SWR-107: Ergebnisse, die KEIN Fehlschlag sind. `skipped` und `neutral` sind Folgen
# eines Fehlers oder ausdrücklich folgenlos — wer sie als Befund liest, meldet den
# falschen Schritt und liest sich trotzdem wie eine Antwort (B063).
OHNE_BEFUND = (None, "success", "skipped", "neutral")

KLARTEXT = {
    "gruen": "grün für diesen Commit",
    "rot": "ROT",
    "laeuft": "läuft noch",
    "kein_lauf": "noch kein Lauf für diesen Commit",
    "kein_ci": "kein CI zu erwarten (Workflow ohne Remote)",
    "fehler": "FEHLER beim Abruf",
}


def remote_slug(url):
    """`https://github.com/DiOflOrds/p0.git` / `git@github.com:DiOflOrds/p0.git` -> `DiOflOrds/p0`.

    Gibt None zurück, wenn die URL nicht auf GitHub zeigt — ein Repo mit fremdem
    Remote ist kein Fehler, es ist nur nichts, was diese Prüfung beantworten kann.
    """
    m = re.search(r"github\.com[:/]+([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", str(url or "").strip())
    return f"{m.group(1)}/{m.group(2)}" if m else None


def _git(repo, *args):
    try:
        out = subprocess.run(["git", "-C", repo, *args],
                             capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=15)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def hat_workflow(pfad):
    """Trägt dieses Repo mindestens eine Workflow-Datei?"""
    verz = os.path.join(pfad, ".github", "workflows")
    if not os.path.isdir(verz):
        return False
    return any(n.endswith((".yml", ".yaml")) for n in os.listdir(verz))


def zu_pruefen(wurzel):
    """SWR-105: Welche Repos haben überhaupt einen CI-Lauf zu erwarten?

    Ein Repo zählt nur mit **Remote UND Workflow**. Die beiden Gegenfälle sind
    verschieden und werden verschieden gemeldet:

    * Workflow ohne Remote (`team-dashboard`) -> `kein_ci`. Ein Gate, das nur als
      Datei existiert, soll als solches sichtbar sein statt stillschweigend zu
      fehlen — sonst liest sich „alles grün" als Aussage über ein Repo, das nie
      geprüft wurde.
    * Remote ohne Workflow (`process`) -> gar nicht gelistet. Dort ist nichts
      versprochen, also fehlt auch nichts.
    """
    pruefen, ohne_remote = [], []
    for name in sorted({n for n, _ in board.projekt_pfade(wurzel)} |
                       {d for d in os.listdir(wurzel)
                        if os.path.isdir(os.path.join(wurzel, d, ".git"))}):
        pfad = os.path.join(wurzel, name)
        if not os.path.isdir(pfad) or not hat_workflow(pfad):
            continue
        slug = remote_slug(_git(pfad, "remote", "get-url", "origin"))
        if slug:
            pruefen.append({"repo": name, "slug": slug,
                            "commit": _git(pfad, "rev-parse", "HEAD"),
                            "branch": _git(pfad, "rev-parse", "--abbrev-ref", "HEAD") or "main"})
        else:
            ohne_remote.append({"repo": name, "slug": "", "commit": "", "branch": ""})
    return pruefen, ohne_remote


def hole_json(url, token=None):
    """Ein GET gegen die Actions-API. Wirft nichts — gibt (daten, fehlertext) zurück."""
    kopf = {"Accept": "application/vnd.github+json", "User-Agent": "aspice-ci-status"}
    if token:
        kopf["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=kopf), timeout=20) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        # 403/429 mit erschöpftem Kontingent ist die Grenze, nicht der Befund.
        rest = e.headers.get("x-ratelimit-remaining") if e.headers else None
        if e.code in (403, 429) and rest == "0":
            return None, ("Rate-Limit erschöpft (unangemeldet 60 Abfragen/Stunde). "
                          "Später erneut laufen lassen.")
        return None, f"HTTP {e.code} {e.reason}"
    except (urllib.error.URLError, OSError, ValueError) as e:
        return None, f"Abruf fehlgeschlagen: {e}"


def bewerte(commit, daten):
    """SWR-105: Läufe eines Repos -> Zustand für GENAU diesen Commit.

    Der Kern der Anforderung. Gesucht wird der Lauf mit passendem `head_sha`;
    ohne Treffer ist die Antwort `kein_lauf` — **nie** `gruen`, auch wenn ganz
    oben ein grüner Lauf eines anderen Commits steht. Genau dieser Fall ist der
    Grund für das Ticket: der Blick auf die Actions-Seite sieht zuerst die Farbe
    und erst danach (wenn überhaupt) den Commit.
    """
    laeufe = (daten or {}).get("workflow_runs") or []
    treffer = [r for r in laeufe if str(r.get("head_sha", "")).lower() == str(commit or "").lower()]
    if not commit or not treffer:
        return {"zustand": "kein_lauf"}
    if any(r.get("status") != "completed" for r in treffer):
        offen = [r for r in treffer if r.get("status") != "completed"][0]
        return {"zustand": "laeuft", "workflow": offen.get("name", ""),
                "url": offen.get("html_url", "")}
    schlecht = [r for r in treffer if r.get("conclusion") != "success"]
    if schlecht:
        # SWR-107: die Lauf-ID GENAU dieses roten Laufs merken. Sie ist der Schlüssel
        # zur Diagnose; die ID des ersten Laufs der Liste wäre die eines anderen.
        return {"zustand": "rot", "workflow": schlecht[0].get("name", ""),
                "fazit": schlecht[0].get("conclusion", ""),
                "lauf_id": schlecht[0].get("id"),
                "url": schlecht[0].get("html_url", "")}
    return {"zustand": "gruen", "workflow": treffer[0].get("name", ""),
            "url": treffer[0].get("html_url", "")}


def fehlerschritt(daten):
    """SWR-107: Jobs-Antwort eines roten Laufs -> welcher Job, welcher Schritt.

    Reine Auswertung, kein Abruf — dieselbe Trennung wie `bewerte()`, damit die
    Regel ohne Netz prüfbar bleibt.

    **Es gibt keine Antwort „unauffällig".** Findet sich kein fehlgeschlagener
    Schritt, aber ein fehlgeschlagener Job, ist die Antwort der **Jobname**; findet
    sich auch der nicht, ist sie `None` und der Bericht sagt „Schritt unbekannt".
    Ein roter Lauf, dessen Diagnose leer ausgeht, bleibt rot — eine Diagnose, die
    einen Befund verschluckt, wäre schlimmer als keine (B038).
    """
    # B063: eine unerwartete Nutzlast ist ein Fall der Anforderung („unexpected
    # payload"), kein Absturz. Eine Liste statt eines Objekts, ein Objekt statt einer
    # Liste, ein Eintrag, der kein Objekt ist — alles davon führt zu `None` und damit
    # zu „Schritt unbekannt". Eine Diagnose, die den ganzen Bericht mitreißt, wäre
    # schlimmer als das Fehlen der Diagnose (B038): der rote Befund war zu diesem
    # Zeitpunkt bereits vollständig ermittelt.
    jobs = daten.get("jobs") if isinstance(daten, dict) else None
    jobs = [j for j in jobs if isinstance(j, dict)] if isinstance(jobs, list) else []
    schlecht = [j for j in jobs if j.get("conclusion") not in OHNE_BEFUND]
    if not schlecht:
        return None
    job = schlecht[0]
    # B063: mehrere gescheiterte Jobs werden gezählt, nicht verschwiegen. Eine Zeile,
    # die den ersten nennt, liest sich sonst als DIE Ursache.
    weitere = len(schlecht) - 1
    schritte = job.get("steps")
    for s in schritte if isinstance(schritte, list) else []:
        if isinstance(s, dict) and s.get("conclusion") not in OHNE_BEFUND:
            return {"job": job.get("name") or "", "schritt": s.get("name") or "",
                    "schritt_fazit": s.get("conclusion") or "", "weitere_jobs": weitere}
    return {"job": job.get("name") or "", "schritt": "",
            "schritt_fazit": job.get("conclusion") or "", "weitere_jobs": weitere}


def diagnose(stand, holen, budget_rest, token=None):
    """SWR-107: für jedes rote Repo **einmal** nachfragen, welcher Schritt fiel.

    Läuft **nach** der Warteschleife: rot ist ein Endzustand, eine Wiederholung je
    Runde wäre verschenktes Budget. Grüne, laufende und ungelaufene Repos lösen
    **keine** Abfrage aus.

    Gibt `(verbrauchte Abfragen, Budget war zu knapp)` zurück. Der Zustand eines
    Repos wird hier **nie** geändert — nur `diagnose_*` kommt hinzu.

    B063: dass das Budget eine Diagnose verhindert hat, wird **auch nach oben**
    gemeldet und nicht nur in die Zeile des betroffenen Repos geschrieben. Sonst
    beantwortet das maschinenlesbare `budget_erschoepft` dieselbe Frage mit *nein*,
    die der Fließtext daneben mit *ja* beantwortet — zwei Quellen für eine Aussage,
    also B033.
    """
    verbraucht, zu_knapp = 0, False
    for r in [z for z in stand.values() if z.get("zustand") == "rot"]:
        if not r.get("lauf_id"):
            r["diagnose_fehler"] = "keine Lauf-Adresse in der Antwort"
            continue
        if verbraucht >= budget_rest:
            r["diagnose_fehler"] = "Abfragebudget aufgebraucht"
            zu_knapp = True
            continue
        daten, fehler = holen(JOBS_API.format(slug=r["slug"], lauf=r["lauf_id"]), token)
        verbraucht += 1
        if fehler:
            r["diagnose_fehler"] = fehler
            continue
        treffer = fehlerschritt(daten)
        if not treffer:
            r["diagnose_fehler"] = "kein fehlgeschlagener Job in der Antwort"
            continue
        if not treffer["job"] and not treffer["schritt"]:
            # B063: die Antwort kam an und war leer. Das ist etwas anderes, als gar
            # nicht gefragt zu haben — sonst ist eine verbrauchte Abfrage unsichtbar.
            r["diagnose_fehler"] = "fehlgeschlagener Job ohne Namen in der Antwort"
            continue
        r.update({"job": treffer["job"], "schritt": treffer["schritt"],
                  "schritt_fazit": treffer["schritt_fazit"],
                  "weitere_jobs": treffer["weitere_jobs"]})
    return verbraucht, zu_knapp


def schritt_klartext(r):
    """Eine Zeile für den Menschen — Schritt, sonst Job, sonst ehrlich „unbekannt"."""
    if not isinstance(r, dict):
        return "Schritt unbekannt"
    weitere = r.get("weitere_jobs") or 0
    dazu = f" · {weitere} weitere(r) Job(s) ebenfalls fehlgeschlagen" if weitere else ""
    if r.get("schritt"):
        return f"Schritt „{r['schritt']}“ ({r.get('schritt_fazit') or 'failure'}){dazu}"
    if r.get("job"):
        return f"Job „{r['job']}“ ({r.get('schritt_fazit') or 'failure'}){dazu}"
    grund = r.get("diagnose_fehler")
    return f"Schritt unbekannt — {grund}" if grund else "Schritt unbekannt"


def pruefe(wurzel, holen=hole_json, warten=WARTEN_STANDARD, budget=BUDGET_STANDARD,
           schlafen=time.sleep, jetzt=None, token=None):
    """SWR-105: Alle Repos prüfen, mit Warteschleife und Abfragebudget.

    Nachgefragt wird nur bei Repos, die noch keinen Endzustand haben — ein Repo,
    das grün ist, wird nicht erneut abgefragt. Das ist nicht Sparsamkeit, sondern
    die Bedingung dafür, dass die 60 Abfragen je Stunde für einen ganzen Lauf
    reichen.
    """
    pruefen, ohne_remote = zu_pruefen(wurzel)
    stand = {r["repo"]: dict(r, zustand="kein_lauf") for r in pruefen}
    for r in ohne_remote:
        stand[r["repo"]] = dict(r, zustand="kein_ci")
    verbraucht, budget_alle = 0, False
    frist = (warten or 0)
    while True:
        offen = [r for r in pruefen if stand[r["repo"]]["zustand"] not in FERTIG]
        if not offen:
            break
        if verbraucht + len(offen) > budget:
            budget_alle = True
            break
        for r in offen:
            daten, fehler = holen(API.format(slug=r["slug"], branch=r["branch"]), token)
            verbraucht += 1
            stand[r["repo"]].update({"zustand": "fehler", "meldung": fehler} if fehler
                                    else bewerte(r["commit"], daten))
        if all(stand[r["repo"]]["zustand"] in FERTIG for r in pruefen) or frist <= 0:
            break
        schlafen(min(RUNDE_SEK, frist))
        frist -= RUNDE_SEK
    # SWR-107: erst jetzt diagnostizieren. Die Schleife klärt, OB ein Repo fertig ist;
    # die Diagnose gilt einem Zustand, der sich nicht mehr ändert. Beides zu vermischen
    # hieße, in jeder Runde erneut zu fragen — bei 60 Abfragen je Stunde die sicherste
    # Art, das Budget an eine Antwort zu verlieren, die schon vorliegt.
    diag_abfragen, diag_knapp = diagnose(stand, holen, max(0, budget - verbraucht), token)
    verbraucht += diag_abfragen
    budget_alle = budget_alle or diag_knapp
    zeilen = [stand[n] for n in sorted(stand)]
    relevant = [z for z in zeilen if z["zustand"] != "kein_ci"]
    return {
        "stand": (jetzt or datetime.now()).strftime("%Y-%m-%d %H:%M"),
        "abfragen": verbraucht,
        "budget_erschoepft": budget_alle,
        "repos": zeilen,
        "alles_gruen": bool(relevant) and all(z["zustand"] == "gruen" for z in relevant),
    }


def bericht(e):
    """Klartext für den Menschen — dieselben Zustände, keine zweite Bewertung (B033)."""
    z = [f"# CI-Status nach dem Push", "",
         f"Stand: {e['stand']} · {e['abfragen']} Abfrage(n) · "
         f"{'ALLES GRÜN' if e['alles_gruen'] else 'NICHT vollständig grün'}", ""]
    if e["budget_erschoepft"]:
        z += ["**Abfragebudget aufgebraucht** — nicht jedes Repo wurde bis zum Endzustand "
              "verfolgt. Die unten als „läuft noch\" oder „noch kein Lauf\" geführten Repos "
              "sind damit **ungeprüft**, nicht in Ordnung.", ""]
    z += ["| Repo | Zustand | Commit | Workflow | Lauf |", "|---|---|---|---|---|"]
    for r in e["repos"]:
        z.append(f"| {r['repo']} | {KLARTEXT.get(r['zustand'], r['zustand'])} "
                 f"| {(r.get('commit') or '')[:8]} | {r.get('workflow', '')} "
                 f"| {r.get('url') or r.get('meldung', '')} |")
    offen = [r["repo"] for r in e["repos"] if r["zustand"] in ("kein_lauf", "laeuft")]
    if offen:
        z += ["", "**Noch offen:** " + ", ".join(offen) + ". „Noch kein Lauf\" heißt **nicht** "
              "in Ordnung — es heißt, dass für diesen Commit noch nichts vorliegt."]
    rot = [r for r in e["repos"] if r["zustand"] == "rot"]
    if rot:
        # SWR-107: nicht nur welches Repo rot ist, sondern woran es liegt. Ohne diese
        # Zeile muss doch wieder ein Mensch die Actions-Seite öffnen.
        z += ["", "**Rot — und woran es liegt:**", ""]
        z += [f"* **{r['repo']}** ({r.get('fazit', '')}): {schritt_klartext(r)}" for r in rot]
    return "\n".join(z) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description="CI-Läufe nach dem Push prüfen (SWR-105)")
    p.add_argument("--repos", default=".", help="Wurzel mit den Repo-Ordnern")
    p.add_argument("--warten", type=int, default=WARTEN_STANDARD,
                   help=f"Sekunden auf laufende Prüfungen warten (Default {WARTEN_STANDARD})")
    p.add_argument("--budget", type=int, default=BUDGET_STANDARD,
                   help=f"Höchstzahl API-Abfragen (Default {BUDGET_STANDARD})")
    p.add_argument("--json", dest="ziel_json", help="Ergebnis als JSON schreiben")
    p.add_argument("--md", dest="ziel_md", help="Ergebnis als Klartext schreiben")
    p.add_argument("--leise", action="store_true", help="nur die Zusammenfassung ausgeben")
    a = p.parse_args(argv)
    wurzel = os.path.abspath(a.repos)
    if not os.path.isdir(wurzel):
        print(f"Wurzel nicht gefunden: {wurzel}")
        return 2
    e = pruefe(wurzel, warten=a.warten, budget=a.budget,
               token=os.environ.get("GITHUB_TOKEN") or None)
    text = bericht(e)
    if not a.leise:
        print(text)
    for ziel, inhalt in ((a.ziel_json, json.dumps(e, ensure_ascii=False, indent=2)),
                         (a.ziel_md, text)):
        if ziel:
            with open(ziel, "w", encoding="utf-8", newline="\n") as f:
                f.write(inhalt)
    print(f"CI-STATUS: {'ALLES GRUEN' if e['alles_gruen'] else 'NICHT VOLLSTAENDIG GRUEN'} "
          f"({e['abfragen']} Abfragen)")
    return 0 if e["alles_gruen"] else 1


if __name__ == "__main__":
    sys.exit(main())
