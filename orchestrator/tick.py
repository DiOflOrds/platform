#!/usr/bin/env python3
"""Orchestrator-MVP (Sprint 1, T-0005): ein Tick.

Ablauf: Board lesen -> Aufgabe wählen (Prio, blocked_by, Rolle aktiv)
-> Skript-Route prüfen -> sonst via Gateway an Rollen-Agent
-> Ergebnis als Commit auf Branch + Ticket-Update + Run-Registry (JSONL).

Nutzung (vom Repos-Wurzelverzeichnis, das process/, platform/, p0/ enthält):
    python platform/orchestrator/tick.py --repos . [--projekt p0] [--dry-run] [--ticket T-xxxx]

Manuell startbar; Scheduler später (Sprint 3). Läuft auf dem Team-Node (D007).
Ticket-Frontmatter-Erweiterungen (optional): aufgaben_typ, repo (Ziel-Repo, Default: Projekt).
"""
import argparse
import os
import re
import subprocess
import sys

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PLATFORM)
sys.path.insert(0, os.path.join(_PLATFORM, "scripts"))

import board  # noqa: E402
import preflight as preflight_mod  # noqa: E402  (T-0024: Precondition je Tick)
from gateway import core as gateway  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None

PRIO_RANG = board.PRIO_RANG


# ---------- Git-Helfer ----------

def git(repo, *args, fehler_ok=False):
    out = subprocess.run(["git", "-C", repo, *args], capture_output=True,
        text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0 and not fehler_ok:
        raise RuntimeError(f"git {' '.join(args)} in {repo}: {out.stderr.strip()}")
    return out.stdout.strip()


def slug(text, laenge=30):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:laenge].rstrip("-") or "aufgabe"


def arbeitskopie_sauber(repo, ignoriere_praefix=None):
    """True, wenn die Arbeitskopie keine uncommitteten Änderungen hat (T-0014).

    ignoriere_praefix: Pfad-Präfix, das nicht zählt (z.B. session-austausch/,
    damit die Antwortdatei des 2. Session-Laufs den Tick nicht blockiert).
    """
    for zeile in git(repo, "status", "--porcelain", "-uall").splitlines():
        pfad = zeile[3:].strip().replace("\\", "/")
        if ignoriere_praefix and pfad.startswith(ignoriere_praefix):
            continue
        return False
    return True


# ---------- Auswahl ----------

def lade_registry(prozess_repo):
    if yaml is None:
        raise RuntimeError("PyYAML fehlt (pip install -r platform/requirements.txt).")
    with open(os.path.join(prozess_repo, "roles", "registry.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)["roles"]


def waehle_ticket(tickets, registry, nur_ticket=None):
    """Nächstes bearbeitbares Ticket: open, Blocker done, Rolle aktiv+ki, nach Prio/ID."""
    nach_id = {t["id"]: t for t in tickets if t.get("id")}
    kandidaten = []
    for t in tickets:
        if t.get("status") != "open":
            continue
        if nur_ticket and t.get("id") != nur_ticket:
            continue
        rolle = (t.get("rolle") or "").upper()
        r = registry.get(rolle)
        if not r or r.get("besetzung") != "ki" or r.get("status") != "active":
            continue
        if board.offene_blocker(t, nach_id):
            continue
        kandidaten.append(t)
    kandidaten.sort(key=lambda t: (PRIO_RANG.get(t.get("prio"), 99), t["id"]))
    return kandidaten[0] if kandidaten else None


def warte_lauf_phase1(t, route, kette, projekt_repo):
    """T-0038: Phase-1-Erkennung VOR dem Statuswechsel.

    Ein Session-Lauf, der auf die Antwortdatei warten wird (session in der Kette,
    Antwortdatei fehlt), soll das Ticket nicht open->in_progress->open zyklieren
    (Erwartungswert: 0 Statuswechsel-Commits je Warte-Lauf; SWR-017).
    Falls ein früherer Ketten-Provider (z.B. ollama) doch antwortet, entfällt nur
    der in_progress-Zwischenstand — der Ergebnis-Status wird normal gesetzt.
    """
    if route != "llm" or "session" not in (kette if isinstance(kette, (list, tuple)) else []):
        return False
    antwort = os.path.join(projekt_repo, "management", "runs", "session-austausch",
                           f"{t['id']}-antwort.md")
    return not os.path.exists(antwort)


def aufloese_route(t, rollen_eintrag):
    """Registry-Auflösung: script | (chain, tier). Siehe registry.yaml-Kopf."""
    typ = t.get("aufgaben_typ", "")
    if typ and typ in (rollen_eintrag.get("script_tasks") or []):
        return "script", typ, None
    at = (rollen_eintrag.get("aufgaben_typen") or {}).get(typ)
    if at:
        return "llm", at.get("chain", rollen_eintrag.get("provider_chain", ["claude"])), at.get("tier", rollen_eintrag.get("model_tier", "standard"))
    return "llm", rollen_eintrag.get("provider_chain", ["claude"]), rollen_eintrag.get("model_tier", "standard")


# ---------- Kontextaufbau ----------

def lese(pfad):
    try:
        return open(pfad, encoding="utf-8").read()
    except OSError:
        return ""


def baue_systemprompt(prozess_repo, rolle):
    """Rollenkarte + Skills (laut Rollenkarte referenziert) + Wissensbasis."""
    teile = [lese(os.path.join(prozess_repo, "roles", f"{rolle.lower()}.md"))]
    skills_dir = os.path.join(prozess_repo, "skills")
    if os.path.isdir(skills_dir):
        for sk in sorted(os.listdir(skills_dir)):
            pfad = os.path.join(skills_dir, sk, "SKILL.md")
            if os.path.exists(pfad) and rolle.lower() in teile[0].lower() and sk in teile[0]:
                teile.append(lese(pfad))
    wb = os.path.join(prozess_repo, "knowledge", rolle.lower())
    for name in ("lessons.md", "heuristiken.md"):
        inhalt = lese(os.path.join(wb, name))
        if inhalt:
            teile.append(inhalt)
    teile.append("Regeln: Arbeite nur im Arbeitsverzeichnis. Erzeuge die geforderten Dateien "
                 "vollständig. Keine Aktionen außerhalb des Auftrags. Antworte auf Deutsch.")
    return "\n\n---\n\n".join(x for x in teile if x)


def baue_auftrag(t, ziel_repo_name):
    return (f"Ticket {t['id']}: {t['titel']}\n\n{t.get('_body', '')}\n\n"
            f"Erledige dieses Ticket jetzt durch Anlegen/Ändern der nötigen Dateien "
            f"im Arbeitsverzeichnis. WICHTIG: Das Arbeitsverzeichnis ist bereits die "
            f"Wurzel des Repos '{ziel_repo_name}' — alle Pfade relativ dazu angeben, "
            f"OHNE '{ziel_repo_name}/' als Präfix (T-0013). "
            f"Das Ticket selbst und Git übernimmt der Orchestrator.")


# ---------- Ticket-/Board-Fortschreibung ----------

def setze_status(projekt_repo, ticket_id, neu, extra_felder=None, notiz=None):
    pfad = os.path.join(projekt_repo, "tickets", f"{ticket_id}.md")
    text = lese(pfad).replace("\r\n", "\n")
    text = re.sub(r"(?m)^status:.*$", f"status: {neu}", text, count=1)
    for k, v in (extra_felder or {}).items():
        if re.search(rf"(?m)^{k}:", text):
            text = re.sub(rf"(?m)^{k}:.*$", f"{k}: {v}", text, count=1)
        else:
            text = re.sub(r"(?m)^erstellt:", f"{k}: {v}\nerstellt:", text, count=1)
    if notiz:
        text = text.rstrip() + f"\n\n{notiz}\n"
    open(pfad, "w", encoding="utf-8", newline="\n").write(text)
    tickets, probleme = board.lade_tickets(projekt_repo)
    probleme += board.validiere_alle(tickets, projekt_repo, git_pruefen=False)
    if probleme:
        raise RuntimeError("Ticket-Update invalide: " + "; ".join(probleme))
    open(os.path.join(projekt_repo, "BOARD.md"), "w", encoding="utf-8", newline="\n").write(
        board.generiere_board(tickets))


# ---------- Tick ----------

def tick(repos, projekt="p0", dry_run=False, nur_ticket=None, provider=None):
    prozess_repo = os.path.join(repos, "process")
    projekt_repo = os.path.join(repos, projekt)
    # SWR-028/ADR-004: Projekt gegen die Discovery-Konvention validieren.
    if not os.path.isdir(os.path.join(projekt_repo, "tickets")):
        print(f"ABBRUCH — unbekanntes Projekt '{projekt}': {projekt_repo} hat kein "
              f"tickets/-Verzeichnis (Discovery-Konvention, ADR-004).")
        return 1
    registry = lade_registry(prozess_repo)
    guardrails_pfad = os.path.join(repos, "platform", "orchestrator", "config", "guardrails.yaml")
    registry_pfad = os.path.join(projekt_repo, "management", "runs", "run-registry.jsonl")

    tickets, probleme = board.lade_tickets(projekt_repo)
    probleme += board.validiere_alle(tickets, projekt_repo, git_pruefen=False)
    if probleme:
        print("ABBRUCH — Board invalide:", *probleme, sep="\n  ")
        return 1

    t = waehle_ticket(tickets, registry, nur_ticket)
    if not t:
        print("Kein bearbeitbares Ticket (open, Blocker erledigt, Rolle aktiv). Tick beendet.")
        return 0

    rolle = t["rolle"].upper()
    route, kette_oder_typ, stufe = aufloese_route(t, registry[rolle])
    if provider and route == "llm":
        kette_oder_typ = [provider]  # CLI-Override, z.B. --provider session
    print(f"Gewählt: {t['id']} '{t['titel']}' — Rolle {rolle}, Route: {route} ({kette_oder_typ})")

    if dry_run:
        print("Dry-Run: keine Ausführung, keine Änderungen.")
        return 0

    if route == "script":
        if kette_oder_typ in ("board-generierung", "board-hygiene"):
            rc = board.main([projekt_repo])
            print(f"Skript-Route board.py: rc={rc}")
            return rc
        print(f"Skript-Route '{kette_oder_typ}' noch nicht implementiert — Ticket bleibt open.")
        return 0

    ziel_repo = os.path.join(repos, t.get("repo", projekt))
    branch = f"feature/{t['id'].lower()}-{slug(t['titel'])}"
    basis_branch = git(ziel_repo, "rev-parse", "--abbrev-ref", "HEAD")

    # Precondition (T-0014): saubere Arbeitskopien, damit der Ergebnis-Commit
    # keine unbeteiligten Änderungen einsammelt. Ausnahme: session-austausch/
    # (Antwortdatei des 2. Laufs) im Projekt-Repo.
    pruefungen = [(ziel_repo, t.get("repo", projekt), None),
                  (projekt_repo, projekt, "management/runs/session-austausch/")]
    if os.path.abspath(ziel_repo) == os.path.abspath(projekt_repo):
        pruefungen = pruefungen[1:]
    for pruef_repo, name, ausnahme in pruefungen:
        if not arbeitskopie_sauber(pruef_repo, ausnahme):
            print(f"ABBRUCH — Arbeitskopie '{name}' hat uncommittete Änderungen. "
                  f"Erst committen/stashen (z.B. sprint1-abschluss.cmd), dann Tick erneut starten.")
            return 1

    # T-0038: Warte-Läufe (Session-Phase 1) lösen keinen Statuswechsel aus.
    phase1 = warte_lauf_phase1(t, route, kette_oder_typ, projekt_repo)
    if not phase1:
        setze_status(projekt_repo, t["id"], "in_progress")
        git(projekt_repo, "add", "-A")
        git(projekt_repo, "commit", "-m", f"{t['id']}: Status in_progress (Orchestrator-Tick)")

    try:
        git(ziel_repo, "checkout", "-b", branch)
    except RuntimeError:
        git(ziel_repo, "checkout", branch)  # Branch existiert (z.B. 2. Lauf Session-Austausch)
    try:
        erg = gateway.execute(rolle.lower(), baue_auftrag(t, t.get("repo", projekt)), {
            "arbeitsverzeichnis": ziel_repo,
            "systemprompt": baue_systemprompt(prozess_repo, rolle),
            "provider_kette": kette_oder_typ,
            "modell_stufe": stufe,
            "aufgaben_typ": t.get("aufgaben_typ", ""),
            "ticket": t["id"],
            "guardrails_pfad": guardrails_pfad,
            "registry_pfad": registry_pfad,
        })
        print(f"Gateway: status={erg.status} provider={erg.provider} kosten={erg.kosten_eur:.2f} € "
              f"artefakte={erg.artefakte}")
        erfolgreich = erg.status == "ok" and erg.artefakte
        if erfolgreich:
            # Nur die erzeugten Artefakte committen — kein add -A (T-0014).
            git(ziel_repo, "add", "--", *erg.artefakte)
            git(ziel_repo, "commit", "-m", f"{t['id']}: {t['titel']} ({rolle}, {erg.provider}, "
                f"{erg.kosten_eur:.2f} EUR)")
    finally:
        git(ziel_repo, "checkout", basis_branch, fehler_ok=True)

    # Ticket-/Board-Fortschreibung erst nach Rückkehr auf den Basis-Branch
    # (wichtig, falls Ziel-Repo == Projekt-Repo).
    if erfolgreich:
        reviewer = "pl" if rolle.lower() != "pl" else "cm"
        setze_status(projekt_repo, t["id"], "in_review", {"reviewer": reviewer},
                     notiz=f"**Orchestrator {erg.provider}:** Branch `{branch}` in `{t.get('repo', projekt)}`, "
                           f"Artefakte: {', '.join(erg.artefakte)}, Kosten {erg.kosten_eur:.2f} €.")
    elif erg.status == "wartet":
        if not phase1:
            # Sicherheitsnetz: falls in_progress gesetzt wurde, zurück auf open (wie bisher).
            setze_status(projekt_repo, t["id"], "open",
                         notiz=f"**Session-Austausch:** {erg.meldung}")
        # T-0038: im Phase-1-Fall bleibt das Ticket unangetastet (Status open);
        # Evidenz sind Prompt-Datei + Run-Registry.
        print(f"WARTET: {erg.meldung}")
        print("Antwortdatei erstellen (z.B. durch die Cowork-Session), dann Tick erneut starten.")
    else:
        meldung = erg.meldung or "keine Artefakte erzeugt"
        setze_status(projekt_repo, t["id"], "open", notiz=f"**Tick fehlgeschlagen:** {meldung}")
        if erg.status == "abgebrochen":
            notfall = os.path.join(projekt_repo, "management", "runs", "NOTFALL-MELDUNG.md")
            os.makedirs(os.path.dirname(notfall), exist_ok=True)
            open(notfall, "a", encoding="utf-8", newline="\n").write(f"- {t['id']}: {meldung}\n")
            print(f"GUARDRAIL: {meldung} — Meldung in {notfall}, keine weiteren Ticks starten!")

    git(projekt_repo, "add", "-A")
    if erg.status == "wartet" and phase1:
        git(projekt_repo, "commit", "-m",
            f"{t['id']}: Warte-Lauf Phase 1 — Prompt + Run-Registry, kein Statuswechsel (T-0038)")
    else:
        git(projekt_repo, "commit", "-m", f"{t['id']}: Tick-Ergebnis (Status, Board, Run-Registry)")
    print("Tick abgeschlossen. Review/PR: Branch", branch)
    return 0


def main():
    p = argparse.ArgumentParser(description="Orchestrator-MVP: ein Tick")
    p.add_argument("--repos", default=".", help="Wurzel mit process/, platform/, p0/")
    p.add_argument("--projekt", default="p0")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--ticket", help="nur dieses Ticket betrachten")
    p.add_argument("--provider", choices=["claude", "copilot", "ollama", "session"],
                   help="Provider-Kette übersteuern (z.B. session für Prompt-Austausch)")
    p.add_argument("--no-preflight", action="store_true",
                   help="Preflight (T-0024) überspringen — nur für Diagnosezwecke")
    a = p.parse_args()
    wurzel = os.path.abspath(a.repos)
    if not a.no_preflight:
        # T-0024: Precondition je Tick — Locks/Status/Board; Tests laufen in CI.
        if preflight_mod.preflight(wurzel, skip_tests=True) and not a.dry_run:
            print("Tick abgebrochen: Preflight hat Befunde (T-0024). "
                  "--no-preflight nur für Diagnose.")
            sys.exit(1)
    sys.exit(tick(wurzel, a.projekt, a.dry_run, a.ticket, a.provider))


if __name__ == "__main__":
    main()
