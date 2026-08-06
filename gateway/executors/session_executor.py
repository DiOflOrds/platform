"""Session-Austausch-Executor (T-0012): Prompt-Austausch über Markdown-Dateien.

Für den Betrieb ohne API-Key und ohne lokales LLM: Der Orchestrator erzeugt eine
Prompt-Datei; eine Claude-/Cowork-Session (oder ein Mensch) beantwortet sie in der
Datei-Block-Konvention; der nächste Tick liest die Antwort ein und pflegt die
Dateien ins Arbeitsverzeichnis ein. Kosten: 0 € (läuft im Session-Abo).

Ablage (im Git, kein Zustand außerhalb): <projekt>/management/runs/session-austausch/
    <ticket>-prompt.md    (vom Executor erzeugt)
    <ticket>-antwort.md   (von der Session/dem Menschen erzeugt)

1. Lauf: Antwortdatei fehlt -> Prompt schreiben, Rückgabe {"wartet": True}.
2. Lauf: Antwortdatei da    -> Datei-Blöcke einpflegen, normales Ergebnis.
"""
import os

from ..dateiblock import AUSGABE_ANWEISUNG, schreibe_dateibloecke


def austausch_verzeichnis(kontext):
    basis = os.path.dirname(kontext["registry_pfad"])
    return os.path.join(basis, "session-austausch")


def fuehre_aus(rolle, aufgabe, kontext, cfg):
    verzeichnis = austausch_verzeichnis(kontext)
    ticket = kontext.get("ticket") or "aufgabe"
    prompt_pfad = os.path.join(verzeichnis, f"{ticket}-prompt.md")
    antwort_pfad = os.path.join(verzeichnis, f"{ticket}-antwort.md")

    if os.path.exists(antwort_pfad):
        text = open(antwort_pfad, encoding="utf-8").read()
        dateien = schreibe_dateibloecke(text, kontext["arbeitsverzeichnis"])
        if not dateien:
            return {"modell": "session-austausch", "kosten_eur": 0.0,
                    "log": f"Antwortdatei {antwort_pfad} enthält keine Datei-Blöcke."}
        return {"modell": "session-austausch", "kosten_eur": 0.0,
                "log": f"Antwort eingelesen ({antwort_pfad}), "
                       f"{len(dateien)} Datei(en) eingepflegt: {', '.join(dateien)}"}

    os.makedirs(verzeichnis, exist_ok=True)
    with open(prompt_pfad, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"""# Session-Austausch: Prompt für Ticket {ticket} (Rolle {rolle.upper()})

*Erzeugt vom Orchestrator. Diese Datei in eine Claude-/Cowork-Session geben
(oder dort einfach sagen: „Beantworte den Session-Austausch").
Die Antwort als `{ticket}-antwort.md` im selben Verzeichnis speichern,
dann den Tick erneut starten.*

## Systemprompt (Rollenkarte, Skill, Wissensbasis)

{kontext.get('systemprompt', '')}

## Auftrag

{aufgabe}

{AUSGABE_ANWEISUNG}
""")
    return {"wartet": True, "modell": "session-austausch", "kosten_eur": 0.0,
            "log": f"Prompt erzeugt: {prompt_pfad} — warte auf {os.path.basename(antwort_pfad)}."}
