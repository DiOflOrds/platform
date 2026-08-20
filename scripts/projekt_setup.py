#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Projekt-Setup (Projektmodell, process/docs/04-projektmodell-orga-rework-2.md Kap. 4).

Erzeugt ein neues Projekt unter projects/<kennung> mit kompletter Struktur und den
Pflicht-Tickets des Setup-Prozesses:

  T-0001            PL: Projektplanung (Projektplan nach PM-Methoden) — zuerst, kritisch
  T-0002..T-0010    je Core-Rolle EIN Initialisierungs-Ticket, blocked_by T-0001
  T-0011/T-0012     wiederkehrende Takt-Tickets (PL-Monitoring, QM-Stichprobe, je-session)

Das Core Team gilt implizit über roles/besetzungen.yaml (core_team) — hier wird NICHTS
in Registries geschrieben. ⚠ Das Skript erzeugt Struktur, nie Freigaben: G0 bleibt
Klasse A beim Menschen (Lehre p12/T-0001: der Knopf darf gründen, aber nie entscheiden);
der Projektauftrag entsteht als Stub mit dem Vermerk „G0 OFFEN".

Nutzung:
    python projekt_setup.py --repos <wurzel> --kennung p16 --name "Mein Projekt" \
        --beschreibung "Ein Satz, was das Projekt tut" [--profil entwicklung] \
        [--datenklasse intern]
"""
import argparse
import datetime
import io
import os
import sys

_HIER = os.path.dirname(os.path.abspath(__file__))
if _HIER not in sys.path:
    sys.path.insert(0, _HIER)
import board  # noqa: E402

PROFILE = ["entwicklung", "dienstleistung", "wiederkehrend"]
DATENKLASSEN = ["intern", "sensibel"]

# Rollen-Initialisierung (Konzept 04, Kap. 4.2): Rolle -> (prozess, reviewer, titel, ziel)
INIT_TICKETS = [
    ("cm", "sup8", "qm", "CM: Konfigurationsmanagement-Plan erstellen (docs/cm-plan.md)",
     "Work Products, Tools, Repos/Storage und Baseline-Regeln dieses Projekts festlegen; "
     "Ablage docs/cm-plan.md. Wiederkehrende CM-Aufgaben (Baseline-Pflege, Backup-Check) "
     "als eigene Tickets einplanen."),
    ("coach", "sup10", "qm", "COACH: Workflows + projektspezifische Rollenbeschreibungen anlegen",
     "Workflows des Projekts dokumentieren (Abweichungen vom Playbook explizit); "
     "roles/<rolle>.md für die hier zentralen Rollen aus dem Template "
     "process/templates/rollenkarte-projekt.md anlegen; docs/historie.md fuehren."),
    ("rm", "swe1", "qm", "RM: Anforderungen aus den Projektplan-Zielen ableiten",
     "Ziele aus docs/projektplan.md Kap. 1 als STK erfassen, erste SWRs ableiten "
     "(draft bis G1 — B027); Traceability anlegen."),
    ("arch", "swe2", "qm", "ARCH: System-/SW-Architektur (Erstentwurf + ADRs)",
     "Architektur-Erstentwurf zu den reviewten Anforderungen; Entscheidungen als ADRs; "
     "Entwurf vor Bau als eigenes Artefakt (Lehre p11/T-0001)."),
    ("qm", "sup1", "pl", "QM: Review-/Audit-Plan erstellen (docs/qm-plan.md)",
     "Was wird wann von wem geprueft (Reviews, Stichproben, Gate-Checks); "
     "Ablage docs/qm-plan.md; wiederkehrende Stichprobe siehe Takt-Ticket."),
    ("test", "swe4", "qm", "TEST: Verifikationsstrategie erstellen",
     "Testebenen, Abdeckungsanspruch, Automatisierungsgrad fuer dieses Projekt; "
     "Ablage verification/strategie.md."),
    ("dev", "swe3", "qm", "DEV: Entwicklungsumgebung und CI-Anbindung dokumentieren",
     "Wie wird hier gebaut/getestet (Plattform-Werkzeuge, Skript-Routen); "
     "Luecken als CR ans Plattform-Projekt."),
    ("prob", "sup9", "qm", "PROB: Problem-Management anbinden",
     "feedback_route/Problem-Tickets fuer dieses Projekt verifizieren; "
     "Trend-Report als wiederkehrende Aufgabe einplanen."),
    ("chg", "sup10", "qm", "CHG: Change-Management anbinden",
     "CR-Workflow fuer dieses Projekt verifizieren (Anlass-Links, Impact-Weg); "
     "offene-CR-Review als wiederkehrende Aufgabe einplanen."),
]


def _schreib(pfad, text):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with io.open(pfad, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _ticket(nr, kennung, rolle, prozess, reviewer, titel, ziel, heute,
            prio="hoch", blocked_by="[]", takt=""):
    tid = "T-%04d" % nr
    takt_zeile = f"takt: {takt}\n" if takt else ""
    return tid, (f"---\n"
                 f"id: {tid}\n"
                 f'titel: "{titel}"\n'
                 f"typ: task\n"
                 f"prozess: {prozess}\n"
                 f"rolle: {rolle}\n"
                 f"sprint: 0\n"
                 f"status: open\n"
                 f"prio: {prio}\n"
                 f"blocked_by: {blocked_by}\n"
                 f"{takt_zeile}"
                 f"repo: {kennung}\n"
                 f"reviewer: {reviewer}\n"
                 f"geändert: {heute}\n"
                 f"erstellt: {heute}\n"
                 f"---\n\n## Ziel\n\n{ziel}\n\n"
                 f"*Erzeugt von projekt_setup.py (Projekt-Setup, Konzept 04 Kap. 4). "
                 f"Herkunft und Ablauf: docs/01-projektauftrag.md, docs/projektplan.md.*\n")


def erzeuge(root, kennung, name, beschreibung, profil="entwicklung",
            datenklasse="intern", heute=None):
    """Legt projects/<kennung> vollstaendig an. Liefert den Projektpfad."""
    if not kennung or not kennung.replace("-", "").isalnum() or not kennung.islower():
        raise ValueError(f"Ungueltige Kennung: {kennung!r} (klein, alphanumerisch, z. B. p16)")
    if profil not in PROFILE:
        raise ValueError(f"Ungueltiges Profil: {profil} (erlaubt: {', '.join(PROFILE)})")
    if datenklasse not in DATENKLASSEN:
        raise ValueError(f"Ungueltige Datenklasse: {datenklasse}")
    pfad = os.path.join(root, "projects", kennung)
    if os.path.exists(pfad):
        raise ValueError(f"{pfad} existiert bereits — Setup bricht ab, nichts geschrieben.")
    heute = heute or datetime.date.today().isoformat()

    # Steckbrief (SWR-175: name = Beschriftung, Ordner = Identitaet)
    _schreib(os.path.join(pfad, "steckbrief.yaml"),
             f'beschreibung: "{beschreibung}"\nstatus: aktiv\nname: "{kennung.upper()} {name}"\n'
             f'# profil: {profil} · datenklasse: {datenklasse} — Governance-Eintrag in\n'
             f'# process/teams/registry.yaml nur noetig, wenn von den Defaults abgewichen wird.\n')
    _schreib(os.path.join(pfad, "README.md"),
             f"# {kennung.upper()} {name}\n\n{beschreibung}\n\n"
             f"Setup nach Projektmodell (process/docs/04-projektmodell-orga-rework-2.md):\n"
             f"Planung zuerst (docs/projektplan.md), dann Rollen-Initialisierung (Tickets), "
             f"dann Betrieb. Historie: docs/historie.md.\n")
    _schreib(os.path.join(pfad, "docs", "01-projektauftrag.md"),
             f"# Projektauftrag {kennung.upper()} — „{name}“ (STUB — **G0 OFFEN**)\n\n"
             f"*Erzeugt von projekt_setup.py am {heute}. ⚠ Dieses Skript erzeugt Struktur, "
             f"nie Freigaben: Der Auftrag gilt erst mit G0-Entscheid des Auftraggebers "
             f"(Klasse A, via Inbox-DR). Bis dahin arbeitet hier nur der PL an der Planung.*\n\n"
             f"## Kurzfassung\n\n{beschreibung}\n\n## Offen bis G0\n\n"
             f"Scope, Randbedingungen, Abnahmekriterien — vom PL im Projektplan praezisiert, "
             f"vom Menschen mit G0 bestaetigt.\n")
    vorlage = os.path.join(root, "process", "templates", "projektplan.md")
    plan = io.open(vorlage, encoding="utf-8").read() if os.path.isfile(vorlage) else "# Projektplan <Pxx>\n"
    plan = plan.replace("<Pxx>", kennung.upper()).replace("<Name>", name)
    _schreib(os.path.join(pfad, "docs", "projektplan.md"), plan)
    _schreib(os.path.join(pfad, "docs", "historie.md"),
             f"# Historie: {kennung.upper()} „{name}“ — Chronik und Lessons Learned\n\n"
             f"*Projektgedaechtnis (Konzept 03 Kap. 5, Template projekt-historie.md). "
             f"Pflicht-Lektuere jeder Rollen-Instanz. Chronik: PL; LeLe: COACH.*\n\n"
             f"## Steckbrief\n\n- **Auftrag:** {beschreibung}\n"
             f"- **Angelegt:** {heute} (projekt_setup.py; G0 offen)\n"
             f"- **Profil / Datenklasse:** {profil} / {datenklasse}\n- **Status:** aktiv\n\n"
             f"## Chronik\n\n| Datum | Ereignis | Beleg |\n|---|---|---|\n"
             f"| {heute} | Projekt angelegt (Setup-Skript); G0 offen | T-0001 |\n\n"
             f"## Lessons Learned (projektbezogen)\n\n"
             f"| # | Lehre (ein Satz) | Quelle | Uebernommen nach |\n|---|---|---|---|\n\n"
             f"## Offene Faeden\n\n- G0-Entscheid des Auftraggebers\n")
    _schreib(os.path.join(pfad, "roles", "README.md"),
             "# Projektspezifische Rollenkarten\n\nJe Rolle eine Datei `<rolle>.md` nach "
             "`process/templates/rollenkarte-projekt.md` — legt der COACH bei der "
             "Initialisierung an (Konzept 04, Kap. 4.2).\n")

    # Tickets: Planung zuerst, Initialisierung blocked_by, Takt-Tickets
    tickets = []
    tickets.append(_ticket(1, kennung, "pl", "man3", "qm",
                           "PL: Projektplanung nach PM-Methoden (docs/projektplan.md)",
                           "Projektplan vollstaendig ausfuellen (Ziele, Phasen, Aufgaben, "
                           "Workflows, Team/Rollen, Infrastruktur, Timeline, Risiken) und "
                           "G0-DR fuer den Menschen vorbereiten. Reviewer: QM + PM.",
                           heute, prio="kritisch"))
    nr = 2
    for rolle, prozess, reviewer, titel, ziel in INIT_TICKETS:
        tickets.append(_ticket(nr, kennung, rolle, prozess, reviewer, titel, ziel, heute,
                               blocked_by="[T-0001]"))
        nr += 1
    tickets.append(_ticket(nr, kennung, "pl", "man3", "qm",
                           "Takt: PL-Monitoring — Board, Ampeln, Chronikzeile, Bericht an PM",
                           "Je Sprint: Board-Hygiene, Ueberfaelligkeits-Ampeln, Chronikzeile "
                           "in docs/historie.md, Statusbericht an das PM-Team.",
                           heute, blocked_by="[T-0001]", takt="je-session"))
    nr += 1
    tickets.append(_ticket(nr, kennung, "qm", "sup1", "pl",
                           "Takt: QM-Stichprobe auf Lieferungen und Prozesskonformitaet",
                           "Je Sprint eine Stichprobe gemaess docs/qm-plan.md (sobald "
                           "vorhanden); Findings als Tickets.",
                           heute, blocked_by="[T-0006]", takt="je-session"))
    for tid, text in tickets:
        _schreib(os.path.join(pfad, "tickets", tid + ".md"), text)

    # SWR-188: Standard-Workflows, an die SOEBEN erzeugten Takt-Tickets gebunden —
    # ein neues Projekt startet mit null unabgedeckten Takten (Konzept 04 Kap. 9).
    takt_pl = "T-%04d" % (len(INIT_TICKETS) + 2)   # PL-Monitoring
    takt_qm = "T-%04d" % (len(INIT_TICKETS) + 3)   # QM-Stichprobe
    _schreib(os.path.join(pfad, "docs", "workflows.yaml"), f"""\
# Workflows {kennung.upper()} (SWR-187/188, erzeugt von projekt_setup.py am {heute}).
# Schema: process/templates/workflows.yaml — Governance-Marken werden beim Review gesetzt.

workflows:
  - id: WF-{kennung.upper()}-MONITORING
    name: PL-Monitoring (Board, Ampeln, Chronik, Bericht an PM)
    takt: je-session
    geplant_von: pl
    ticket: {takt_pl}
    arch_review: ""
    cm_verankert: ""
    schritte:
      - rolle: script
        werkzeug: board.py --check
        aktion: Board lesen, Ampeln/Ueberfaelligkeit pruefen
        input: tickets/ + BOARD.md
        output: Lagebild (fluechtig)
      - rolle: pl
        aktion: bewerten, koordinieren, eskalieren; Chronikzeile schreiben
        input: Lagebild
        output: docs/historie.md (Chronik) + Statusbericht an PM
  - id: WF-{kennung.upper()}-QM
    name: QM-Stichprobe auf Lieferungen und Prozesskonformitaet
    takt: je-session
    geplant_von: qm
    ticket: {takt_qm}
    arch_review: ""
    cm_verankert: ""
    schritte:
      - rolle: qm
        aktion: Stichprobe gemaess docs/qm-plan.md (sobald vorhanden)
        input: Lieferungen des Laufs + DoD-Checklisten
        output: Findings als Tickets oder Freigabe-Vermerk am Ticket
""")

    # Board erzeugen + validieren (dieselbe Skript-Route wie ueberall)
    geladen, probleme = board.lade_tickets(pfad)
    probleme += board.validiere_alle(geladen, pfad, git_pruefen=False)
    if probleme:
        raise RuntimeError("Setup-Tickets invalide (Bug im Setup-Skript): " + "; ".join(probleme))
    _schreib(os.path.join(pfad, "BOARD.md"), board.generiere_board(geladen))
    return pfad


def main(argv=None):
    ap = argparse.ArgumentParser(description="Neues Projekt nach Projektmodell anlegen")
    ap.add_argument("--repos", default=".", help="Wurzel der Arbeitskopien")
    ap.add_argument("--kennung", required=True, help="Discovery-Kennung, z. B. p16")
    ap.add_argument("--name", required=True, help="Anzeigename")
    ap.add_argument("--beschreibung", required=True, help="Ein Satz Auftrag")
    ap.add_argument("--profil", default="entwicklung", choices=PROFILE)
    ap.add_argument("--datenklasse", default="intern", choices=DATENKLASSEN)
    a = ap.parse_args(argv)
    try:
        pfad = erzeuge(os.path.abspath(a.repos), a.kennung, a.name, a.beschreibung,
                       a.profil, a.datenklasse)
    except (ValueError, RuntimeError) as e:
        print(f"FEHLER: {e}")
        return 1
    print(f"OK: {pfad} angelegt — 12 Tickets (Planung, 9x Rollen-Initialisierung, 2x Takt).")
    print("Naechste Schritte:")
    print("  1. G0-DR an den Menschen (Klasse A) — das Skript hat NICHTS freigegeben.")
    print("  2. organigramm.py laufen lassen (Core Team erscheint automatisch).")
    print("  3. Abweichungen/spezifische Rollen: PM pflegt roles/besetzungen.yaml.")
    return 0


if __name__ == "__main__":
    # platform/T-0009: am Melden nicht sterben. ⚠ Sprint 28 nachgezogen — dieses Skript
    # ist im Projektmodell-Rework ohne die Regel entstanden, die für JEDEN Einstiegspunkt
    # dieses Hauses gilt; gefunden hat es test_konsole, nicht der Rework-Bericht.
    import konsole
    konsole.sichere_ausgabe()
    sys.exit(main())
