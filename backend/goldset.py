#!/usr/bin/env python3
"""Das Format eines Goldset-Falls (SWR-142, promt-team/T-0006).

**Warum es diese Datei gibt.** `promt-team/T-0002` verlangt ein Goldset je KI-Rolle — den
Maßstab, gegen den ein Eval-Gate prüft. Die Naht, an der das Ticket bei seiner fünften
Berührung zerlegt wurde, trägt mehr als Bequemlichkeit:

> **Ohne Format sind zwanzig Fälle zwanzig Einzelmeinungen — und ein Eval-Gate, das Formen
> vergleicht statt Ergebnisse, misst die Sorgfalt des Schreibers.**

**Die zwei Felder, an denen alles hängt.**

`fehlschlag_erkannt_an` ist **Pflicht** und **keine Prosa**. Ein Fall, dessen Fehlschlag
nur „sieht man doch" erkennt, ist kein Prüffall, sondern eine Meinung mit Termin. Und er
wird **abgelehnt** statt vorbelegt: ein Vorgabewert an dieser Stelle machte jede
ungeschriebene Prüfung stillschweigend zu einer bestandenen.

`soll_scheitern_auf` nennt die Provider-Stufe, auf der ein Fall **scheitern soll**. Ohne
ihn belegt ein grünes Eval nur, dass die Aufgabe leicht war. ⚠ Das Feld allein genügt
nicht — geprüft wird, dass **je Aufgaben-Typ mindestens einer** gesetzt ist. Ein Feld ohne
Prüfung ist ein Wunsch (SWR-125, hier angewandt statt zitiert).

**Sensible Daten werden benannt und ausgelassen, nicht anonymisiert erfunden.** Ein
erfundener Fall misst den Erfinder. Die Auslassung trägt ihren **Grund**, sonst ist die
Lücke im Set von Vollständigkeit nicht zu unterscheiden.

**Warum alle Mängel eines Falls auf einmal gemeldet werden.** Ein Fall, der über fünf
Läufe fünfmal korrigiert wird, ist der Preis eines Prüfers, der beim ersten Mangel
aufhört.

Diese Datei enthält **keine Fälle** — die sind `promt-team/T-0007`.
"""
import json
import os
import re

#: Die geschlossene Menge der Prüfarten. ⚠ Sie steht **hier** und nirgends sonst; der
#: Prüfer liest sie, statt sie zu wiederholen. Eine zweite Schreibweise derselben Liste
#: ist die Bauart, die SWR-131 gekostet hat.
PRUEF_ARTEN = ("enthaelt", "enthaelt_nicht", "regex", "json_pfad", "datei_existiert")

#: Pflichtfelder eines Falls. `soll_scheitern_auf` steht bewusst **nicht** hier: es ist je
#: Aufgaben-Typ Pflicht, nicht je Fall — die Prüfung dafür ist `pruefe_set`.
#:
#: ⚠ **`herkunft` ist ab v2 (SWR-149) Pflicht.** `promt-team/T-0007` DoD 2 verlangt
#: *„real heißt: aus dem Bestand belegt, nicht ausgedacht"* — und das stand bis hierher
#: **nur als Satz im Ticket**. Ein Satz, den keine Prüfung liest, altert lautlos
#: (`L-2026-08-17ag`, an derselben Stelle zweimal an einem Tag aufgelaufen). Der Beleg ist
#: deshalb ein **Feld**, und zwar ein auflösbares: `pruefe_herkunft` hält es gegen den
#: Bestand.
PFLICHT = ("rolle", "aufgaben_typ", "eingabe", "erwartetes_ergebnis",
           "fehlschlag_erkannt_an", "herkunft")

#: Trenner zwischen Datei und Belegstelle in einem `herkunft`-Eintrag: `pfad::suchtext`.
#: ⚠ Der Suchtext ist der Unterschied zwischen „die Datei gibt es" und „der Fall steht
#: darin". Eine Datei existiert auch für einen erfundenen Fall.
HERKUNFT_TRENNER = "::"

#: Die Aussage, die `pruefe_set` **ohne** Bestand über sich selbst macht. ⚠ Sie steht als
#: Konstante da, damit der Test sie **liest** statt sie zu wiederholen — eine zweite
#: Schreibweise desselben Satzes ist die Bauart aus SWR-131.
HINWEIS_OHNE_WURZEL = ("HERKUNFT UND ROLLEN-REGISTRY NICHT GEPRUEFT (keine Wurzel "
                       "uebergeben) — diese Liste sagt nichts darueber, ob die Faelle "
                       "belegt sind")


def pruefe_fall(fall):
    """**Alle** Mängel eines Falls — Liste von Meldungen, leer = in Ordnung (SWR-142).

    Bewusst alle und nicht der erste: ein Fall, der über fünf Läufe fünfmal korrigiert
    wird, ist der Preis eines Prüfers, der beim ersten Mangel aufhört.
    """
    m = []
    if not isinstance(fall, dict):
        return ["Fall ist kein Objekt"]
    for feld in PFLICHT:
        wert = fall.get(feld)
        if wert is None or (isinstance(wert, str) and not wert.strip()):
            m.append(f"Pflichtfeld fehlt: {feld}")
    pruefung = fall.get("fehlschlag_erkannt_an")
    if pruefung is not None:
        if isinstance(pruefung, str):
            m.append("fehlschlag_erkannt_an ist Prosa — ein Fall, dessen Fehlschlag nur "
                     "'sieht man doch' erkennt, ist kein Prueffall")
        elif not isinstance(pruefung, dict):
            m.append("fehlschlag_erkannt_an muss {art, wert} sein")
        else:
            art = pruefung.get("art")
            if art not in PRUEF_ARTEN:
                m.append(f"unbekannte Pruefart '{art}' — erlaubt: "
                         f"{', '.join(PRUEF_ARTEN)}")
            if not str(pruefung.get("wert") or "").strip():
                m.append("fehlschlag_erkannt_an ohne 'wert'")
            if art == "regex":
                try:
                    re.compile(str(pruefung.get("wert") or ""))
                except re.error as e:
                    m.append(f"regex nicht uebersetzbar: {e}")
    if "sensibel_ausgelassen" in fall:
        if not str(fall.get("sensibel_ausgelassen") or "").strip():
            m.append("sensibel_ausgelassen ohne Grund — eine unerklaerte Luecke ist von "
                     "Vollstaendigkeit nicht zu unterscheiden")
    m += _maengel_herkunft_form(fall)
    return m


def _maengel_herkunft_form(fall):
    """Die **Form** von `herkunft` — ohne Bestand, also ohne Auflösung (SWR-149).

    ⚠ Eine Zeichenkette wird **abgelehnt**, obwohl ein einzelner Pfad als Zeichenkette
    bequemer wäre: ein Satz und ein Pfad sehen als Zeichenkette gleich aus, und nur einer
    von beiden lässt sich auflösen. Genau diese Verwechselbarkeit ist der Grund, aus dem
    `fehlschlag_erkannt_an` keine Prosa sein darf — hier dieselbe Entscheidung am
    Nachbarfeld, statt sie ein zweites Mal zu lernen.
    """
    if "herkunft" not in fall:
        return []  # das Fehlen meldet die PFLICHT-Schleife, nicht diese Stelle
    h = fall.get("herkunft")
    if isinstance(h, str):
        return ["herkunft ist eine Zeichenkette — ein Satz und ein Pfad sind so nicht zu "
                "unterscheiden; erwartet wird eine Liste von Belegstellen"]
    if not isinstance(h, (list, tuple)):
        return ["herkunft muss eine Liste von Belegstellen sein (pfad oder "
                f"pfad{HERKUNFT_TRENNER}suchtext)"]
    if not h:
        return ["herkunft ist leer — ein Fall ohne Beleg ist ausgedacht, bis das "
                "Gegenteil dasteht"]
    m = []
    for i, eintrag in enumerate(h, 1):
        if not isinstance(eintrag, str) or not eintrag.strip():
            m.append(f"herkunft[{i}] ist keine Belegstelle")
            continue
        pfad = eintrag.split(HERKUNFT_TRENNER, 1)[0].strip()
        if not pfad:
            m.append(f"herkunft[{i}] nennt keine Datei")
        # ⚠ Nicht nur os.path.isabs: seit Python 3.13 sagt es unter Windows fuer
        # "/etc/passwd" False (kein Laufwerk = nicht absolut). Die Zusicherung
        # test_absoluter_pfad_und_aufstieg_werden_abgelehnt war auf dem Host genau
        # dadurch blind (Befund Host-Lauf 2026-08-22). Deshalb zusaetzlich: fuehrender
        # Schraegstrich (beide Richtungen), Laufwerksbuchstabe, und ".." auch in
        # Backslash-Schreibweise.
        elif (os.path.isabs(pfad) or pfad.startswith(("/", "\\"))
              or re.match(r"^[A-Za-z]:", pfad)
              or ".." in pfad.replace("\\", "/").split("/")):
            m.append(f"herkunft[{i}] ist kein repo-relativer Pfad: {pfad}")
    return m


def zerlege_herkunft(eintrag):
    """`pfad::suchtext` -> `(pfad, suchtext_oder_None)`."""
    if HERKUNFT_TRENNER in eintrag:
        pfad, text = eintrag.split(HERKUNFT_TRENNER, 1)
        return pfad.strip(), text.strip() or None
    return eintrag.strip(), None


def pruefe_herkunft(fall, wurzel):
    """Der Beleg **gegen den Bestand**: existiert die Datei, steht der Fall darin?

    ⚠ Der Suchtext ist die eigentliche Prüfung. *Eine Datei existiert auch für einen
    erfundenen Fall* — erst die Belegstelle darin unterscheidet „aus dem Bestand" von
    „plausibel formuliert". Ein Eintrag **ohne** Suchtext wird nicht abgelehnt (ein ganzes
    Artefakt kann der Beleg sein), aber `bericht` **zählt** ihn: ein Set, dessen Belege
    alle nur Dateinamen sind, ist schwächer belegt, als es aussieht.
    """
    m = []
    for eintrag in (fall.get("herkunft") or []):
        if not isinstance(eintrag, str):
            continue  # Form meldet `pruefe_fall`
        pfad, suchtext = zerlege_herkunft(eintrag)
        voll = os.path.join(wurzel, *pfad.split("/"))
        if not os.path.isfile(voll):
            m.append(f"herkunft nicht auflösbar: {pfad} gibt es nicht")
            continue
        if suchtext is None:
            continue
        try:
            with open(voll, encoding="utf-8", errors="replace") as f:
                inhalt = f.read()
        except OSError as e:
            m.append(f"herkunft {pfad} nicht lesbar: {e}")
            continue
        if suchtext not in inhalt:
            m.append(f"Belegstelle steht nicht in {pfad}: {suchtext[:60]!r}")
    return m


def pruefe_registry(fall, wurzel, registry="process/roles/registry.yaml"):
    """`rolle` und `aufgaben_typ` gegen die Rollen-Registry (SWR-149).

    ⚠ Das Format sagt seit v1 *„KI-Rolle laut `process/roles/registry.yaml`"* und
    *„Aufgaben-Typ derselben Registry"* — **geprüft** wurde es nicht. Ein Aufgaben-Typ,
    den die Registry nicht kennt, kann der Orchestrator nicht auflösen: der Fall kann
    niemals laufen und sieht im Set aus wie jeder andere. Das ist SWR-125 (*Regel ohne
    Prüfung*) am eigenen Format — die fünfte Gestalt derselben Familie.

    Fehlt die Registry, ist das **ein Mangel und keine bestandene Prüfung**: eine
    Prüfung, deren Grundlage fehlt, darf nicht grün melden (SWR-114).
    """
    pfad = os.path.join(wurzel, *registry.split("/"))
    rollen = _lade_registry(pfad)
    if rollen is None:
        return [f"Rollen-Registry nicht lesbar ({registry}) — die Pruefung von rolle und "
                f"aufgaben_typ hat keine Grundlage und meldet deshalb nicht gruen"]
    rolle = str(fall.get("rolle") or "").strip()
    typ = str(fall.get("aufgaben_typ") or "").strip()
    schluessel = rolle.upper()
    if schluessel not in rollen:
        return [f"rolle '{rolle}' steht nicht in der Rollen-Registry — "
                f"bekannt: {', '.join(sorted(rollen))}"]
    erlaubt = rollen[schluessel]
    if typ and typ not in erlaubt:
        return [f"aufgaben_typ '{typ}' ist fuer Rolle '{rolle}' nicht in der Registry — "
                f"der Orchestrator koennte den Fall nicht aufloesen; bekannt: "
                f"{', '.join(sorted(erlaubt)) or '(keiner)'}"]
    return []


def _lade_registry(pfad):
    """`{ROLLE: set(aufgaben_typen | script_tasks)}` oder `None`, wenn nicht lesbar.

    `script_tasks` zählen mit: ein Aufgaben-Typ mit Skript-Route ist ein gültiger Typ —
    er läuft nur ohne LLM. Ein Goldset-Fall darauf ist der billigste, den es gibt, und
    deshalb ausdrücklich erlaubt.
    """
    try:
        import yaml
    except ImportError:
        return None
    try:
        with open(pfad, encoding="utf-8") as f:
            daten = yaml.safe_load(f) or {}
    except (OSError, ValueError):
        return None
    try:
        rollen = daten["roles"]
    except (KeyError, TypeError):
        return None
    if not isinstance(rollen, dict):
        return None
    ergebnis = {}
    for name, v in rollen.items():
        v = v or {}
        typen = set(v.get("script_tasks") or [])
        typen |= set((v.get("aufgaben_typen") or {}).keys())
        ergebnis[str(name).upper()] = typen
    return ergebnis


def pruefe_set(faelle, wurzel=None):
    """Mängel des **ganzen** Sets: je Fall und die Regel über die Fälle (SWR-142/149).

    ⚠ Die Regel über die Fälle ist der Punkt, an dem `soll_scheitern_auf` mehr wird als
    ein Feld: **je Aufgaben-Typ muss mindestens ein Fall** ihn setzen, sonst belegt ein
    grünes Eval nur, dass die Aufgaben leicht waren. Der fehlende Typ wird **genannt**.

    ⚠⚠ **`wurzel=None` prüft die Form und den Bestand NICHT — und sagt es.** Ohne Wurzel
    lässt sich `herkunft` nicht auflösen und die Registry nicht lesen. Das stillschweigend
    zu überspringen wäre wörtlich SWR-145: *ein unvollständiger Modus, dessen Ergebnis von
    dem des vollständigen nicht zu unterscheiden ist.* Deshalb steht die Auslassung als
    Zeile **in der Mängelliste** — nicht als Fehler des Sets, sondern als Aussage über die
    Prüfung. Wer nur die Form prüfen will, ruft `pruefe_fall` je Fall.
    """
    m = []
    typen = {}
    for i, fall in enumerate(faelle, 1):
        for mangel in pruefe_fall(fall):
            m.append(f"Fall {i}: {mangel}")
        if isinstance(fall, dict) and wurzel is not None:
            for mangel in pruefe_herkunft(fall, wurzel):
                m.append(f"Fall {i}: {mangel}")
            for mangel in pruefe_registry(fall, wurzel):
                m.append(f"Fall {i}: {mangel}")
        if isinstance(fall, dict):
            typ = fall.get("aufgaben_typ") or "(ohne Typ)"
            typen.setdefault(typ, False)
            if str(fall.get("soll_scheitern_auf") or "").strip():
                typen[typ] = True
    for typ, hat in sorted(typen.items()):
        if not hat:
            m.append(f"Aufgaben-Typ '{typ}': kein Fall mit 'soll_scheitern_auf' — ein "
                     f"gruenes Eval belegt sonst nur, dass die Aufgabe leicht war")
    if wurzel is None:
        m.append(HINWEIS_OHNE_WURZEL)
    return m


def lies(pfad):
    """Goldset (JSONL) als `(faelle, kaputte_zeilen)`. Kaputte Zeilen werden gezählt."""
    faelle, kaputt = [], 0
    if not os.path.exists(pfad):
        return faelle, kaputt
    with open(pfad, encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                faelle.append(json.loads(zeile))
            except ValueError:
                kaputt += 1
    return faelle, kaputt


#: Untergrenze aus `promt-team/T-0008` DoD 1: eine Rolle mit Läufen braucht ≥ 20 belegte
#: Fälle. ⚠ Die Zahl steht **hier** und nicht im Test, damit Regel und Prüfung nicht zwei
#: Schreibweisen derselben Aussage sind (die Bauart aus SWR-131).
MINDESTFAELLE_JE_ROLLE = 20


def rollen_mit_laeufen(wurzel):
    """`{rolle: anzahl}` über **alle** Run-Registries der Organisation.

    ⚠⚠ **Die Grundmenge ist hier der eigentliche Gegenstand** (`SWR-128`-Familie, in
    Sprint 26 *und* 27 *und* 28 dieselbe Stelle): `promt-team/T-0008` hat drei Sprints lang
    auf *„einen Lauf"* gewartet und dabei an **einem Abend** gemessen, während die Frage
    über den **Bestand** gestellt war. Diese Funktion liest deshalb jede Registry, die die
    Discovery findet, und nicht die eine, die gerade im Ticket zitiert wird.

    > *Eine Bedingung über einen Bestand, gemessen an einem Ereignis, ist grün oder rot je
    > nachdem, wann man hinsieht.*
    """
    zaehler = {}
    for repo in sorted(os.listdir(wurzel)):
        pfad = os.path.join(wurzel, repo, "management", "runs", "run-registry.jsonl")
        if not os.path.isfile(pfad):
            continue
        with open(pfad, encoding="utf-8") as f:
            for zeile in f:
                zeile = zeile.strip()
                if not zeile:
                    continue
                try:
                    rolle = (json.loads(zeile).get("rolle") or "").strip()
                except ValueError:
                    continue          # eine kaputte Zeile ist kein Lauf, aber auch kein Grund
                if rolle:
                    zaehler[rolle] = zaehler.get(rolle, 0) + 1
    return zaehler


def abdeckung(wurzel, goldset_pfad="promt-team/management/goldset.jsonl"):
    """Wer hat Läufe, wer hat ein Goldset? — `promt-team/T-0008` als **Prüfung**.

    Rückgabe `{"mit_laeufen", "faelle_je_rolle", "unterdeckt", "ohne_laeufe"}`:

    * ``unterdeckt`` — Rollen **mit** Läufen und **weniger** als
      `MINDESTFAELLE_JE_ROLLE` Fällen. Das ist der **Befund**; jede andere Zeile ist Auskunft.
    * ``ohne_laeufe`` — Rollen im Goldset ohne einen einzigen aufgezeichneten Lauf.
      ⚠ **Kein Befund**, sondern DoD 2 des Tickets: *die Lücke bleibt sichtbar* statt mit
      abgeleiteten Fällen gefüllt zu werden.

    ⚠ Was hier **nicht** gemessen wird: ob ein Lauf `status: ok` hatte. Ein Fehlschlag ist
    ein Lauf — er zeigt, dass die Rolle im Betrieb angefasst wird, und genau darauf zielt
    *„das Goldset folgt dem Betrieb"*. Die Verwechslung von „gelaufen" mit „gelungen" hat
    dieses Haus in Sprint 26 schon einmal einen Sprint gekostet.
    """
    laeufe = rollen_mit_laeufen(wurzel)
    faelle, _ = lies(os.path.join(wurzel, *goldset_pfad.split("/")))
    je_rolle = {}
    for f in faelle:
        r = (f.get("rolle") or "").strip()
        if r:
            je_rolle[r] = je_rolle.get(r, 0) + 1
    unterdeckt = sorted((r, je_rolle.get(r, 0)) for r in laeufe
                        if je_rolle.get(r, 0) < MINDESTFAELLE_JE_ROLLE)
    return {"mit_laeufen": laeufe,
            "faelle_je_rolle": je_rolle,
            "unterdeckt": unterdeckt,
            "ohne_laeufe": sorted(r for r in je_rolle if r not in laeufe)}


def haenge_an(pfad, fall):
    """Einen **geprüften** Fall anhängen — append-only wie die Run-Registry.

    Wirft `ValueError` mit **allen** Mängeln, wenn der Fall sie hat. Ein ungeprüfter
    Schreibweg neben diesem wäre die Lage aus SWR-134: eine Prüfung, die der Aufrufer
    anwenden muss.
    """
    m = pruefe_fall(fall)
    if m:
        raise ValueError("Goldset-Fall abgelehnt: " + "; ".join(m))
    os.makedirs(os.path.dirname(os.path.abspath(pfad)), exist_ok=True)
    with open(pfad, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(fall, ensure_ascii=False) + "\n")
    return fall
