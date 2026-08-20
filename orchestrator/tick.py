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
from backend import git_schreiben  # noqa: E402  — SWR-134: der eine Schreibweg nach Git
from backend import organisation  # noqa: E402  — SWR-169: der eine Leser von besetzungen.yaml
from gateway import core as gateway  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None

PRIO_RANG = board.PRIO_RANG


# ---------- Git-Helfer ----------

def git(repo, *args, fehler_ok=False):
    """Ein Git-Aufruf des Ticks — seit SWR-134 über den **einen** Schreibweg.

    ⚠ Vorher lief der Orchestrator ohne Sperren-Räumung. Auf dem Cowork-Mount hinterlässt
    **jeder** Git-Aufruf eine `.git/index.lock`, die Git selbst nicht entfernen darf; der
    nächste schreibende Aufruf im selben Repo scheitert daran. Ein Tick macht in Folge
    `add`, `commit`, `checkout`, `add`, `commit` — er lief also in genau diesen Fehler,
    für den die Reparatur seit Sprint 5 im Haus lag und die nur der Briefkasten benutzte.
    """
    v = git_schreiben.ruf(repo, args)
    if not v.ok and not fehler_ok:
        raise RuntimeError(f"git {' '.join(args)} in {repo}: {v.stderr.strip()}")
    return v.stdout.strip()


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


def waehle_ticket(tickets, registry, nur_ticket=None, nur_rolle=None):
    """Nächstes bearbeitbares Ticket: open, Blocker done, Rolle aktiv+ki, nach Prio/ID.

    ⚠ SWR-172: `nur_rolle` schränkt die Auswahl auf **eine** Rolle ein. `pm/D010` hat den
    Schnelltakt je **Besetzung** entschieden (`platform/PROB`, `team-mail/MAIL-RED`) —
    ausdrückbar war bisher nur die Einheit, und deshalb ist die Rolle auf dem Weg von der
    Entscheidung zum Aufruf verloren gegangen (`platform/T-0033`).

    ⚠ Der Schalter ist gebaut und **nicht umgelegt**: `ollama-schnelltakt.cmd` bleibt
    unverändert, bis der Auftraggeber entschieden hat (`platform/T-0035`). Gemessen am
    Bestand vom 2026-08-20 trägt **kein einziges** der 14 offenen Tickets eine Rolle mit
    ollama-Besetzung — die Einschränkung wäre heute eine Abschaltung, und das ist eine
    Aussage über seine Automatik, nicht über unseren Code.
    """
    nach_id = {t["id"]: t for t in tickets if t.get("id")}
    kandidaten = []
    for t in tickets:
        if t.get("status") != "open":
            continue
        if nur_ticket and t.get("id") != nur_ticket:
            continue
        if nur_rolle and (t.get("rolle") or "").upper() != nur_rolle.upper():
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


def schlusszeile(erg, erfolgreich, branch):
    """SWR-167: Das Ergebniswort folgt dem Ergebnis des Gateways.

    Die alte Fassung war ein unbedingtes `print("Tick abgeschlossen. …")` vor `return 0`
    — nach Erfolg, nach `wartet` und nach `fehler` gleichlautend. Am 2026-08-20 standen
    dadurch in allen drei durchgelaufenen Ticks zwei Zeilen übereinander, die einander
    widersprachen:

        Gateway: status=fehler provider= kosten=0.00 € artefakte=[]
        Tick abgeschlossen. Review/PR: Branch feature/t-0001-…

    ⚠ „Abgeschlossen" war dabei kein falsches Wort für einen Fehler — es war gar kein Wort
    über das Ergebnis, sondern eines über das Ende der Funktion. Diese Fassung nennt den
    Status, den auch die Run-Registry trägt, damit Log und Registry nicht auseinanderlaufen.
    """
    if erfolgreich:
        return f"Tick abgeschlossen. Review/PR: Branch {branch}"
    if erg.status == "wartet":
        return f"Tick wartet (status={erg.status}): {erg.meldung or 'ohne Meldung'}"
    return (f"Tick OHNE ERGEBNIS (status={erg.status}, artefakte=0): "
            f"{erg.meldung or 'keine Artefakte erzeugt'}")


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

def besetzungsbefund(repos, rolle, einheit, provider):
    """SWR-171: passt die gezogene Rolle zum erzwungenen Provider? '' = ja, sonst der Befund.

    ⚠⚠ Gemessen am Lauf vom 2026-08-20 um 21:30: `SWR-169` war richtig gebaut und in vier
    Gegenproben belegt — **alle vier prüften die Auflösungsfunktion, keine ihren Aufrufer.**
    Im Betrieb bekam sie `CM@platform` und `DEV@team-mail` statt `PROB@platform` und
    `MAIL-RED@team-mail`, lieferte korrekt `''` und fiel auf den Guardrails-Default zurück.
    Die Anforderung war grün, die Wirkung war null.

    > **Eine Gegenprobe, die die Funktion prüft und nicht ihren Aufrufer, misst die Hälfte,
    > die man selbst geschrieben hat.**

    ⚠ Geprüft wird die **Besetzung**, nicht der Modellname: `DEV@team-mail` gibt es im
    Register überhaupt nicht. Ein Tick, der dieser Instanz Arbeit gibt, ist auch mit
    richtigem Modell falsch.

    ⚠ Ohne `--provider` greift die Prüfung nicht — dann gilt die Provider-Kette der Rolle
    aus `registry.yaml`, und über die hat das Besetzungsregister nichts zu sagen.
    """
    motor = organisation.MOTOR_JE_PROVIDER.get(provider or "")
    if not motor:
        return ""
    if organisation.besetzung_mit_motor(repos, rolle, einheit, motor):
        return ""
    besetzt = organisation.besetzungen_mit_motor(repos, motor)
    return (f"Rolle {rolle} hat in Einheit '{einheit}' keine Besetzung mit motor "
            f"'{motor}' (process/roles/besetzungen.yaml). Mit motor '{motor}' besetzt: "
            f"{', '.join(besetzt) or 'keine'}.")


def tick(repos, projekt="p0", dry_run=False, nur_ticket=None, provider=None, nur_rolle=None):
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

    t = waehle_ticket(tickets, registry, nur_ticket, nur_rolle)
    if not t:
        zusatz = f", Rolle {nur_rolle.upper()}" if nur_rolle else ""
        print(f"Kein bearbeitbares Ticket (open, Blocker erledigt, Rolle aktiv{zusatz}). "
              f"Tick beendet.")
        return 0

    rolle = t["rolle"].upper()
    route, kette_oder_typ, stufe = aufloese_route(t, registry[rolle])
    if provider and route == "llm":
        kette_oder_typ = [provider]  # CLI-Override, z.B. --provider session
    print(f"Gewählt: {t['id']} '{t['titel']}' — Rolle {rolle}, Route: {route} ({kette_oder_typ})")

    # SWR-171: VOR dem Gateway-Aufruf, vor dem Branch und vor jedem Statuswechsel.
    # ⚠ Rückgabe 0 und nicht 1: der Lauf ist nicht kaputt, es gibt für diese Besetzung
    # nichts zu tun — dieselbe Kategorie wie „Kein bearbeitbares Ticket" darüber. Das
    # Ergebniswort trägt den Grund, wie SWR-167 es für den Fehlerfall verlangt.
    befund = besetzungsbefund(repos, rolle, projekt, provider)
    if befund:
        print(f"Tick OHNE ERGEBNIS (Besetzung): {befund} Kein Gateway-Aufruf, kein Branch, "
              f"kein Statuswechsel — {t['id']} bleibt unangetastet.")
        return 0

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

    # SWR-168: Der Branchname ist aus Ticket-ID und Titel gebildet und damit bei JEDEM
    # Tick derselbe. Bei einem Dauerauftrag (takt: je-session) ist der zweite Tick nicht
    # der Sonderfall, sondern der Regelfall — im 15-Minuten-Takt nach 15 Minuten. Der alte
    # Fallback `checkout <branch>` setzte HEAD dann auf die ALTE Spitze dieses Branches und
    # damit rückwärts (gemessen am reflog vom 2026-08-20: zwei Commits zurück, main und
    # Branch divergiert). Deshalb: einen bestehenden Branch auf den aktuellen Stand
    # nachziehen, statt HEAD auf seinen alten zu ziehen.
    try:
        git(ziel_repo, "checkout", "-b", branch)
    except RuntimeError:
        # Branch existiert (früherer Tick desselben Tickets, 2. Lauf Session-Austausch).
        git(ziel_repo, "checkout", "-B", branch)
    try:
        erg = gateway.execute(rolle.lower(), baue_auftrag(t, t.get("repo", projekt)), {
            "arbeitsverzeichnis": ziel_repo,
            "systemprompt": baue_systemprompt(prozess_repo, rolle),
            "provider_kette": kette_oder_typ,
            "modell_stufe": stufe,
            "aufgaben_typ": t.get("aufgaben_typ", ""),
            # SWR-169: Das Modell kommt aus dem Besetzungsregister der Rolle — der Stelle,
            # die der Auftraggeber im HMI pflegt. Leer heißt „nichts gesetzt", nicht „kein
            # Modell": dann greift der Guardrails-Wert.
            "modell_name": organisation.modell_der_besetzung(repos, rolle, projekt),
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
        # SWR-168: Die Rückkehr wird NACHGEPRÜFT statt mit fehler_ok=True verschluckt.
        # Am 2026-08-20 um 20:15 ist sie stillschweigend misslungen; die Folge war ein
        # Ergebnis-Commit auf dem Feature-Branch, ein 'in_progress' das auf main stehen
        # blieb, und ein Preflight, der den Arbeitsbaum las und deshalb 0 meldete.
        # Was ein Lauf hinterlässt, prüft ab hier der Lauf selbst.
        # ⚠ Kein `return` in diesem finally: ein return hier würde eine noch fliegende
        # Ausnahme aus dem try verschlucken. Der Befund wird gemerkt und danach gewertet.
        git(ziel_repo, "checkout", basis_branch, fehler_ok=True)
        steht_auf = git(ziel_repo, "rev-parse", "--abbrev-ref", "HEAD",
                        fehler_ok=True).strip()

    if steht_auf != basis_branch:
        print(f"ABBRUCH — Rückkehr auf '{basis_branch}' misslungen, HEAD steht auf "
              f"'{steht_auf or 'unbekannt'}'. Ticket und Board werden NICHT "
              f"fortgeschrieben, damit nichts auf dem Feature-Branch landet (SWR-168).")
        return 1

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
    print(schlusszeile(erg, erfolgreich, branch))
    return 0


def main():
    p = argparse.ArgumentParser(description="Orchestrator-MVP: ein Tick")
    p.add_argument("--repos", default=".", help="Wurzel mit process/, platform/, p0/")
    p.add_argument("--projekt", default="p0")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--ticket", help="nur dieses Ticket betrachten")
    p.add_argument("--rolle", help="SWR-172: nur Tickets dieser Rolle ziehen — die Besetzung, "
                                   "die pm/D010 entschieden hat (z.B. PROB)")
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
    sys.exit(tick(wurzel, a.projekt, a.dry_run, a.ticket, a.provider, a.rolle))


if __name__ == "__main__":
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                      "..", "scripts"))
    import konsole
    konsole.sichere_ausgabe()  # platform/T-0009: am Melden nicht sterben
    main()
