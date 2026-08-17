#!/usr/bin/env python3
"""Dashboard-Widgets (SWR-148, team-mail/T-0004) — Ergebnisse, nicht Zustände.

**Warum diese Datei existiert.** SWR-135 hat für das Dashboard dieselben Projektkacheln
gebaut, die das Cockpit zeigt. Der Auftraggeber hat das am 2026-08-17 benannt: *„ist an sich
das gleiche wie das cockpit, aber dashbaord ist dafür gedacht, dass man bestimmte ergebnisse
vom Projekten"*. Nach den eigenen Regeln dieser Organisation ist das ein **Befund** und kein
Geschmacksurteil — zwei Anzeigen derselben Daten sind B033.

> **Eine Kachel zeigt den Zustand eines Projekts. Ein Widget zeigt das Ergebnis einer
> Arbeit.**

Der Unterschied ist nicht die Darstellung, sondern die Quelle: Kacheln kommen für alle
Projekte aus derselben Aggregation, ein Widget kommt **aus dem Team** und ist je Team
verschieden.

**Ein Team ohne `widget.yaml` hat kein Widget** — kein leeres. Ein leeres Widget behauptet,
es gäbe dort etwas zu sehen. Heute bietet genau ein Team eines an; das ist der Stand und
keine Lücke.

**Der Auftrag liegt beim Team, nicht hier.** `widget.yaml` ist die Zusage des Teams, was
sein Widget zeigt. Läge sie in der Plattform, wäre es eine Zusage der Plattform über fremde
Arbeit — und ein neues Team bräuchte eine Codeänderung, um ein Widget zu bekommen.

⚠ **Der Auftrag wird gegen die Wirklichkeit gehalten.** `widget.yaml` verspricht Takte,
`konfiguration.yaml` liefert sie. Wo beides auseinandergeht, sagt das Widget es — mit
**Grund**. *Ein Dashboard, das nur zeigt, was zufällig da ist, kann nicht sagen, was fehlt.*

⚠ **Keine Mailinhalte.** Datum, Zahlen, Auftrag ja; Betreff, Absender, Links **nein** — die
stehen hinter dem PIN-Leser (SWR-053), und Mission Control ist per
`mission-control-lan.cmd` auch im LAN erreichbar. Diese Datei liest Digest-Text nur, um
**Punkte zu zählen**, und gibt keinen davon weiter.
"""
import os
import re

from . import teams

#: Die drei Zustände des Widget-Vertrags (SWR-096/108). ⚠ Kein vierter: „nicht
#: eingerichtet" und „noch keiner erstellt" sind **Gründe** für `nicht_geliefert`, keine
#: eigenen Zustände. Ein vierter Wert hätte das Vokabular des Vertrags erweitert, ohne dass
#: irgendein Leser ihn kennt.
ZUSTAND_WERT = "wert"
ZUSTAND_ECHTE_NULL = "echte_null"
ZUSTAND_NICHT_GELIEFERT = "nicht_geliefert"

#: Die Rubrik, die in **allen** heute vorhandenen Digests steht (gemessen am Bestand
#: 2026-08-17: `2026-08-15-digest.md`, `2026-08-16-tag-digest.md`,
#: `2026-08-16-woche-digest.md`). Sie ist die Antwort auf *„offene aufgaben aus den mails"*.
RUBRIK_REAKTION = "Braucht Blick oder Reaktion"

_ZAHLPUNKT = re.compile(r"^\s{0,3}(?:\d+[.)]|[-*+])\s+\S")
#: `… (Tag) — 89 Mail(s)` und `… (57 Mails, letzte ~24 h)`. ⚠ Die Zahl steht **nicht**
#: zuverlässig in Klammern — der erste Entwurf verlangte `\((\d+)\s*Mail` und lieferte am
#: echten Bestand für **jeden** Digest `None`. Am Modell wäre das nie aufgefallen; gemessen
#: wurde es an den drei vorhandenen Dateien.
_MAILZAHL = re.compile(r"(\d+)\s*Mail")


def _wert(roh):
    """Wert einer `schluessel: wert`-Zeile — mit Anführungszeichen, ohne Kommentar.

    ⚠ **Ein `#` ist nicht immer ein Kommentar.** Das Klickziel eines Widgets ist eine
    Hash-Route (`#/team/team-mail`, ADR-005). Der erste Entwurf schnitt am ersten `#` ab und
    machte daraus einen **leeren** String — ein Widget, das aussieht wie eines und nirgendwo
    hinführt. Gefunden am echten `widget.yaml`, nicht an einem Modell.

    Regel: ist der Wert **gequotet**, gilt der Inhalt der Anführungszeichen; sonst wird nur
    an einem `#` abgeschnitten, dem **Leerraum** vorausgeht.
    """
    v = roh.strip()
    if v[:1] in ('"', "'"):
        ende = v.find(v[0], 1)
        return v[1:ende] if ende > 0 else v[1:]
    return re.split(r"\s+#", v, 1)[0].strip()


def widget_zusage(root, projekt):
    """`widget.yaml` eines Teams — oder `None`, wenn es keins anbietet.

    ⚠ **`None` und „leer" sind hier verschiedene Dinge.** Kein `widget.yaml` heißt: dieses
    Team bietet kein Widget an, es erscheint **nicht** im Dashboard. Ein leeres Widget wäre
    die schlechtere Anzeige — es behauptet einen Ort, an dem etwas stehen sollte.

    Bewusst ein winziger Zeilenparser und **kein** YAML-Import: ADR-002 („kein Build, keine
    Abhängigkeit") gilt unverändert, und `teams.lade_konfiguration` liest die Nachbardatei
    seit Sprint 7 genauso. Ein zweiter Parser-Stil im selben Verzeichnis wäre die Sorte
    Uneinheitlichkeit, die niemand als Fehler meldet und jeder Leser einmal nachschlägt.
    """
    pfad = os.path.join(_teampfad(root, projekt), "widget.yaml")
    if not os.path.isfile(pfad):
        return None
    zusage = {"id": "", "titel": "", "auftrag": "", "ziel": "", "takte": []}
    schluessel = None
    with open(pfad, encoding="utf-8") as f:
        for zeile in f:
            roh = zeile.rstrip("\n")
            if roh.lstrip().startswith("#") or not roh.strip():
                continue
            if roh.startswith((" ", "\t")) and schluessel in ("auftrag",):
                # Fortsetzungszeile eines `>-`-Blocks: anhängen, einfach getrennt.
                zusage["auftrag"] = (zusage["auftrag"] + " " + roh.strip()).strip()
                continue
            if ":" not in roh:
                continue
            k, v = roh.split(":", 1)
            k, v = k.strip(), _wert(v)
            schluessel = k
            if k == "takte":
                zusage["takte"] = [t.strip() for t in v.strip("[]").split(",") if t.strip()]
            elif k in zusage:
                zusage[k] = "" if v in (">-", ">", "|") else v.strip('"\'')
    if not zusage["id"]:
        return None
    return zusage


def _teampfad(root, projekt):
    """Der Ordner des Teams. Eine Zeile, damit `os.path.join` nicht dreimal dasteht."""
    return os.path.join(root, projekt)


def takt_aus_dateiname(name):
    """`2026-08-16-tag-digest.md` → `"tag"`. Ohne Taktangabe: `""`.

    ⚠ **Der Bestand hat einen Fall ohne Takt:** `2026-08-15-digest.md` (Altformat vor
    SWR-064). Er darf **nicht** stillschweigend als Tagesdigest gelten — das wäre eine
    Annahme über eine Datei, die selbst nichts dazu sagt (B038). Sie zählt als Digest, aber
    für **keinen** Takt. Die Gegenprobe dazu steht in den Tests.
    """
    m = re.match(r"^\d{4}-\d{2}-\d{2}-([a-zä-ü]+)-digest\.md$", name or "")
    return m.group(1) if m else ""


def reaktionspunkte(text):
    """Wie viele Punkte stehen unter „Braucht Blick oder Reaktion"? — `None`, wenn die
    Rubrik fehlt.

    ⚠ **Die Unterscheidung ist der ganze Wert dieser Funktion:**

    * Rubrik fehlt → `None` (`nicht_geliefert`). Ein Digest ohne diese Rubrik sagt nichts
      über offene Punkte; `0` zu melden hieße „nichts zu tun" behaupten.
    * Rubrik da, keine Punkte → `0` (`echte_null`). *„Keine direkten Rechnungen"* ist ein
      Ergebnis. Genau dieser Fall steht im Digest vom 16.08. unter „Rechnungen/Zahlungen".

    Gezählt werden Listenpunkte bis zur nächsten Überschrift — nicht Zeilen, nicht Wörter.
    Der Digest vom 16.08. (Tag) hat vier numerierte Punkte, der Wochendigest mehr.
    """
    if not text or RUBRIK_REAKTION not in text:
        return None
    zeilen = text.splitlines()
    start = next(i for i, z in enumerate(zeilen) if RUBRIK_REAKTION in z)
    punkte = 0
    for z in zeilen[start + 1:]:
        if z.lstrip().startswith("#"):
            break
        if _ZAHLPUNKT.match(z):
            punkte += 1
    return punkte


def _mailzahl(titel):
    """`… (89 Mail(s))` → `89`; ohne Angabe `None` — **nicht** `0` (B038)."""
    m = _MAILZAHL.search(titel or "")
    return int(m.group(1)) if m else None


def post_widget(root, projekt):
    """Das Widget eines Teams: Auftrag + je versprochenem Takt der jüngste Digest.

    Liest die Digestliste über **`teams.digest_liste`** — die Stelle, die es seit SWR-053
    gibt. Ein eigener Verzeichnis-Scan wäre ein zweiter Erhebungsweg (SWR-092) und würde
    beim nächsten Namensschema auseinanderlaufen.
    """
    zusage = widget_zusage(root, projekt)
    if zusage is None:
        return None
    cfg = teams.lade_konfiguration(root, projekt)
    eingerichtet = set(cfg.get("takte") or [])
    liste = teams.digest_liste(root, projekt)

    # Jüngster Digest je Takt. `digest_liste` liefert neueste zuerst — das erste Vorkommen
    # ist damit das jüngste, und es wird hier nicht ein zweites Mal sortiert.
    juengster = {}
    ohne_takt = 0
    for eintrag in liste:
        takt = takt_aus_dateiname(eintrag["name"])
        if not takt:
            ohne_takt += 1
            continue
        juengster.setdefault(takt, eintrag)

    eintraege = []
    for takt in zusage["takte"]:
        zahl = _TAKT_ZAHL.get(takt)
        eintrag = juengster.get(takt)
        if eintrag is None:
            # ⚠ Zwei Gründe, ein Zustand. Der Unterschied ist die Information, die der
            # Auftraggeber braucht: „nicht eingerichtet" kann er ändern, „noch keiner" muss
            # er abwarten.
            if zahl is not None and zahl not in eingerichtet:
                grund = "nicht eingerichtet — Takt fehlt in konfiguration.yaml"
            else:
                grund = "noch keiner erstellt"
            eintraege.append({"takt": takt, "zustand": ZUSTAND_NICHT_GELIEFERT,
                              "grund": grund, "datum": None, "mails": None,
                              "reaktion": None})
            continue
        inhalt = teams.digest_inhalt(root, projekt, eintrag["name"])["inhalt"]
        punkte = reaktionspunkte(inhalt)
        eintraege.append({
            "takt": takt,
            "zustand": ZUSTAND_WERT,
            "grund": "",
            "datum": eintrag["datum"],
            "mails": _mailzahl(eintrag["titel"]),
            # `None` bleibt `None`: fehlt die Rubrik, wissen wir es nicht.
            "reaktion": punkte,
            "reaktion_zustand": (ZUSTAND_NICHT_GELIEFERT if punkte is None
                                 else ZUSTAND_ECHTE_NULL if punkte == 0
                                 else ZUSTAND_WERT),
        })
    return {"id": zusage["id"], "projekt": projekt, "titel": zusage["titel"],
            "auftrag": zusage["auftrag"], "ziel": zusage["ziel"],
            "eintraege": eintraege,
            # Digests ohne Taktangabe im Namen: gezählt und **genannt**, nicht verschwiegen
            # und nicht einem Takt zugeschlagen (SWR-114).
            "digests_ohne_takt": ohne_takt}


#: Name → Zahl in `konfiguration.yaml`. ⚠ **Die Quelle ist `team-mail/tools/mail_digest.py`
#: (`TAKTE`).** Sie liegt beim Team und ist von der Plattform nicht importierbar (das
#: Werkzeug ist team-lokal und darf fehlen, siehe `teams._werkzeug`). Diese Zeile ist
#: deshalb eine **zweite Fassung** — und weil das genau die Bauart ist, die SWR-131
#: gekostet hat, hält ein Test sie gegen das Original, sobald das Werkzeug vorhanden ist.
_TAKT_ZAHL = {"tag": 1, "woche": 7, "monat": 30}


def widgets(root):
    """Alle angebotenen Widgets — über die entdeckten Teams, in stabiler Reihenfolge.

    ⚠ **Nur Teams**, nicht alle Projekte: ein Widget ist das Ergebnis einer laufenden
    Arbeit. `teams.ist_team` ist die vorhandene Antwort auf „ist das ein Team?" und wird
    hier nicht nachgebaut.
    """
    from . import aggregation
    raus = []
    for name in aggregation.projekte(root):
        if not teams.ist_team(root, name):
            continue
        w = post_widget(root, name)
        if w is not None:
            raus.append(w)
    return {"widgets": raus, "vertrag": aggregation.vertrag_version(root)}
