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


#: Die Rubrik der Rechnungs-Kachel. ⚠ Wortgleich zur Überschrift im Digest — dieselbe
#: Bauform wie `RUBRIK_REAKTION` und **keine** zweite Auswahlregel (`SWR-210`).
RUBRIK_RECHNUNG = "Rechnungen/Zahlungen"
#: ⚠⚠ **Für `SPAM` gibt es im Digest KEINE Rubrik — und das steht hier als benannte
#: Abwesenheit statt als stille Null** (`SWR-210`, `team-dashboard/T-0005`).
#:
#: Die Design-Vorlage des Auftraggebers (`projects/p11/design/widget_design_mail.png`)
#: verlangt vier Kacheln: `IN`, `Reaktion`, `Rechnung`, `SPAM`. Gemessen am Bestand liefert
#: `team-mail` die ersten drei; eine SPAM-Rubrik erzeugt es nicht.
#:
#: > **Die Vorlage fragt nach einer Zahl, die die Quelle nicht herstellt. `0` anzuzeigen
#: > hieße „kein Spam" behaupten — die Verwechslung von „echte Null" und „nicht erhoben",
#: > gegen die `SWR-108` gebaut wurde. Die Kachel steht deshalb da und sagt, dass sie
#: > nichts weiß.**
#:
#: Der Weg dahin ist ein CR an `team-mail` (`team-mail/T-0007`), nicht eine Zahl hier.
RUBRIK_SPAM = None
#: Die vier Kacheln der Vorlage, in ihrer Reihenfolge: (Schlüssel, Beschriftung, Rubrik).
#: `None` als Rubrik heißt „diese Kachel hat heute keine Quelle" — siehe `RUBRIK_SPAM`.
#: ⚠ `in` kommt nicht aus einer Rubrik, sondern aus der Mailzahl der Digest-Überschrift;
#: es steht deshalb nicht in dieser Tabelle, sondern wird in `post_widget` gesetzt.
KACHEL_RUBRIKEN = (("reaktion", "Reaktion", RUBRIK_REAKTION),
                   ("rechnung", "Rechnung", RUBRIK_RECHNUNG),
                   ("spam", "SPAM", RUBRIK_SPAM))
#: ⚠ **Entscheidung des Auftraggebers, nicht Vorschlag des Teams.** Die Vorlage trug einen
#: Platzhalter („max. zwei Zeilen und x Zeichen"); auf die Rückfrage in
#: `team-dashboard/N-0004` hat er am 2026-08-21 geantwortet: *„1. 180 Zeichen ok.
#: 2. Aufklappen 3. die eine Reaktion verlangen"*. Die Zahl steht hier als benannte
#: Konstante, damit sie eine Festlegung bleibt und keine Gewohnheit wird.
ZUSAMMENFASSUNG_ZEICHEN = 180
ZUSAMMENFASSUNG_ZEILEN = 2


def _rubrikpunkte(text, rubrik):
    """Die Listenpunkte unter einer Rubrik im **Wortlaut** — `None`, wenn sie fehlt.

    ⚠⚠ **Die eine Auswahlregel dieses Moduls.** `reaktionspunkte` (zählt) und
    `reaktionspunkte_text` (zitiert) hatten bis `SWR-210` je einen eigenen, wortgleichen
    Rumpf; die Doppelung war im Docstring von `reaktionspunkte_text` sogar ausdrücklich
    als Risiko benannt (*„Zwei Auswahlregeln über dieselbe Rubrik wären B033"*). Mit der
    dritten und vierten Kachel wären es vier Kopien geworden.

    `rubrik is None` heißt **„für diese Kachel gibt es keine Quelle"** und ist etwas
    anderes als „Rubrik fehlt in diesem Digest" — beide antworten `None`, aber der Grund
    unterscheidet sich, und den trägt der Aufrufer.
    """
    if not rubrik or not text or rubrik not in text:
        return None
    zeilen = text.splitlines()
    start = next(i for i, z in enumerate(zeilen) if rubrik in z)
    punkte = []
    for z in zeilen[start + 1:]:
        if z.lstrip().startswith("#"):
            break
        if _ZAHLPUNKT.match(z):
            punkte.append(z.strip())
    return punkte


def zusammenfassung(punkte, zeichen=ZUSAMMENFASSUNG_ZEICHEN, zeilen=ZUSAMMENFASSUNG_ZEILEN):
    """Die Reaktions-Punkte als kurze Zusammenfassung — `None`, wenn es keine gibt.

    ⚠⚠ **Diese Funktion gehört hinter das PIN-Lesegate** und wird ausschließlich aus
    `widget_inhalt` aufgerufen. Die Design-Vorlage zeigt die Zusammenfassung in der
    Kachel; ihr **Wortlaut** sind aber Betreffzeilen, Absender und Mail-Links — genau das,
    was `SWR-160` hinter das Gate gestellt hat.

    > **Der Wunsch und die Schranke widersprechen sich nur scheinbar: der Auftraggeber hat
    > „wenn man auf Reaktion klickt" geschrieben. Ein Klick ist genau die Stelle, an der
    > ein Lesegate hingehört. Die Kachel zeigt die ZAHL, das Aufklappen den WORTLAUT.**

    `None` bleibt `None`: fehlt die Rubrik, gibt es keine Zusammenfassung — `""` wäre die
    Behauptung, es sei nichts zu berichten.
    """
    if punkte is None:
        return None
    text = " · ".join(re.sub(r"^\s*(?:\d+[.)]|[-*+])\s+", "", p) for p in punkte[:zeilen])
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # Mail-Links raus, Text bleibt
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= zeichen else text[:zeichen - 1].rstrip() + "…"


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
    punkte = _rubrikpunkte(text, RUBRIK_REAKTION)
    return None if punkte is None else len(punkte)


def reaktionspunkte_text(text):
    """SWR-160: die Punkte unter „Braucht Blick oder Reaktion" im **Wortlaut**.

    ⚠ **Das ist der sensible Zwilling von `reaktionspunkte`.** Dort wird gezählt, hier
    wird zitiert — dieselbe Rubrik, zwei völlig verschiedene Auskünfte:

    > **Die ANZAHL offener Punkte ist eine Kennzahl. Ihr WORTLAUT sind Betreffzeilen,
    > Absender und Links.** Deshalb steht die Zahl in der ungeschützten Kachel und der
    > Wortlaut hinter dem PIN-Lesegate.

    `None`, wenn die Rubrik fehlt — nie `[]`. Eine leere Liste hiesse „nichts zu tun",
    und das ist eine andere Aussage als „nicht erhoben" (SWR-108/135).

    ⚠ Ausgeschnitten wird an **derselben** Stelle wie in `reaktionspunkte`: dieselbe
    Rubrik, dieselbe Abbruchbedingung, dasselbe Zeilenmuster. Zwei Auswahlregeln über
    dieselbe Rubrik wären B033, und dann zählte die Kachel andere Punkte, als der Leser
    hinter dem Gate zu sehen bekäme.
    """
    return _rubrikpunkte(text, RUBRIK_REAKTION)


def widget_inhalt(root, projekt, takt=""):
    """SWR-160: der INHALT eines Widgets — nur hinter dem PIN-Lesegate aufzurufen.

    ⚠⚠ **Diese Funktion darf von keiner ungeschützten Route erreichbar sein.** Der
    Aufrufer ist `server.py` innerhalb des `\/api\/team`-Zweigs, und ein Test hält das
    über den Syntaxbaum fest — *ein Gate, das erst in der Anzeige greift, ist keines*
    (DoD 3 von `projects/p11/T-0013`).

    Ohne `takt`: der jüngste Digest überhaupt. Mit `takt`: der jüngste dieses Takts.
    Gibt es keinen, ist `punkte` `None` **mit Grund** und nicht `[]` — dieselbe
    Unterscheidung, die die Kachel führt.

    ⚠ Gelesen wird über `teams.digest_liste`/`teams.digest_inhalt` und nicht über einen
    eigenen Verzeichnis-Scan (SWR-092): ein zweiter Erhebungsweg hinter einem Gate wäre
    der gefährlichste von allen, weil er die Regeln des ersten nicht erbt.
    """
    zusage = widget_zusage(root, projekt)
    if zusage is None:
        return None
    liste = teams.digest_liste(root, projekt)
    eintrag = None
    for e in liste:
        if not takt or takt_aus_dateiname(e["name"]) == takt:
            eintrag = e
            break
    if eintrag is None:
        return {"id": zusage["id"], "projekt": projekt, "takt": takt, "datum": None,
                "punkte": None, "grund": "noch keiner erstellt"}
    inhalt = teams.digest_inhalt(root, projekt, eintrag["name"])["inhalt"]
    punkte = reaktionspunkte_text(inhalt)
    return {"id": zusage["id"], "projekt": projekt,
            "takt": takt or takt_aus_dateiname(eintrag["name"]),
            "datum": eintrag["datum"], "punkte": punkte,
            # SWR-210: die kurze Fassung für das Aufklappen der Reaktions-Kachel.
            # ⚠ Sie steht HIER und nicht im Payload der Kachel — ihr Wortlaut ist
            # derselbe geschützte Inhalt wie `punkte`, nur kürzer. Eine Kürzung macht
            # aus einer Betreffzeile keine Kennzahl.
            "zusammenfassung": zusammenfassung(punkte),
            "zusammenfassung_grenze": {"zeichen": ZUSAMMENFASSUNG_ZEICHEN,
                                       "zeilen": ZUSAMMENFASSUNG_ZEILEN},
            "grund": "" if punkte is not None else
                     f"Rubrik '{RUBRIK_REAKTION}' fehlt in diesem Digest"}


def _mailzahl(titel):
    """`… (89 Mail(s))` → `89`; ohne Angabe `None` — **nicht** `0` (B038)."""
    m = _MAILZAHL.search(titel or "")
    return int(m.group(1)) if m else None


def _zustand(wert):
    """Ein Wert → sein Vertragszustand. Die **eine** Stelle, die das entscheidet.

    ⚠ Kein vierter Zustand (`SWR-096`/`SWR-108`): `None` ist `nicht_geliefert`, `0` ist
    `echte_null`, alles andere `wert`. Diese drei Zeilen standen vor `SWR-210` inline im
    Payload und wären mit vier Kacheln viermal dagestanden.
    """
    return (ZUSTAND_NICHT_GELIEFERT if wert is None
            else ZUSTAND_ECHTE_NULL if wert == 0 else ZUSTAND_WERT)


def _kacheln(inhalt, mails):
    """Das 2×2-Raster der Design-Vorlage: `IN` / `Reaktion` / `Rechnung` / `SPAM`.

    ⚠⚠ **Jede Kachel trägt ihren eigenen Zustand — und `SPAM` trägt einen GRUND.** Die
    Vorlage des Auftraggebers verlangt vier Zahlen; `team-mail` erzeugt drei. Für die
    vierte gibt es keine Rubrik, und `0` wäre die Behauptung „kein Spam".

    > **Eine Kachel, die nichts weiß, sagt das. Eine Kachel, die stattdessen `0` zeigt,
    > lügt in einer Zahl — und niemand sieht einer `0` an, dass sie erfunden ist.**
    """
    raus = [{"schluessel": "in", "beschriftung": "IN", "wert": mails,
             "zustand": _zustand(mails),
             "grund": "" if mails is not None
                      else "Mailzahl fehlt in der Digest-Überschrift"}]
    for schluessel, beschriftung, rubrik in KACHEL_RUBRIKEN:
        punkte = _rubrikpunkte(inhalt, rubrik)
        wert = None if punkte is None else len(punkte)
        if rubrik is None:
            grund = ("keine Quelle: der Digest führt keine SPAM-Rubrik "
                     "(CR an team-mail, team-mail/T-0007)")
        elif punkte is None:
            grund = f"Rubrik '{rubrik}' fehlt in diesem Digest"
        else:
            grund = ""
        raus.append({"schluessel": schluessel, "beschriftung": beschriftung,
                     "wert": wert, "zustand": _zustand(wert), "grund": grund})
    return raus


def _sicht_takt(eintraege):
    """Der EINE Takt, den das Widget zeigt — Vertrag v2.9, `team-dashboard/T-0001`.

    Vorgabe ist der **kleinste** versprochene Takt (`tag` vor `woche` vor `monat`): der
    jüngste Stand zuerst, wörtlich der Wunsch aus `p0/N-0002`. Die übrigen Einträge
    bleiben im Payload und sind umschaltbar — sie werden nur nicht gleichzeitig gezeigt.

    ⚠ Der Rückgabewert kommt **aus** `eintraege` und ist nie ein Takt, den es dort nicht
    gibt: eine Anweisung, etwas zu zeigen, das nicht geliefert wird, zwänge den Renderer
    zu einer eigenen Entscheidung — also genau zu der zweiten Stelle, gegen die dieser
    Vertrag geschrieben ist.

    ⚠ Sortiert wird über `_TAKT_ZAHL` und nicht über die Reihenfolge der Liste: die
    Reihenfolge stammt aus der Zusage des Teams und ist keine Aussage über das Alter.
    """
    if not eintraege:
        return ""
    return min(eintraege,
               key=lambda e: _TAKT_ZAHL.get(e.get("takt"), 10**6))["takt"]


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
            # ⚠ SWR-210: dieselben Schlüssel wie im Wert-Fall. Ein Eintrag, dem Felder
            # FEHLEN, zwingt jeden Leser zu `.get()` mit Vorgabewert — und ein
            # Vorgabewert ist genau die erfundene Auskunft, gegen die der Vertrag
            # `nicht_geliefert` führt. Die vier Kacheln stehen also da und sagen, dass
            # es diesen Digest nicht gibt.
            eintraege.append({"takt": takt, "zustand": ZUSTAND_NICHT_GELIEFERT,
                              "grund": grund, "datum": None, "mails": None,
                              "reaktion": None,
                              "reaktion_zustand": ZUSTAND_NICHT_GELIEFERT,
                              "kacheln": _kacheln("", None),
                              "zusammenfassung_verfuegbar": False})
            continue
        inhalt = teams.digest_inhalt(root, projekt, eintrag["name"])["inhalt"]
        punkte = reaktionspunkte(inhalt)
        mails = _mailzahl(eintrag["titel"])
        eintraege.append({
            "takt": takt,
            "zustand": ZUSTAND_WERT,
            "grund": "",
            "datum": eintrag["datum"],
            "mails": mails,
            # `None` bleibt `None`: fehlt die Rubrik, wissen wir es nicht.
            "reaktion": punkte,
            "reaktion_zustand": (ZUSTAND_NICHT_GELIEFERT if punkte is None
                                 else ZUSTAND_ECHTE_NULL if punkte == 0
                                 else ZUSTAND_WERT),
            # SWR-210 (team-dashboard/T-0005, Brief N-0004): das 2×2-Raster der
            # Design-Vorlage. ⚠ `mails`/`reaktion` bleiben unverändert daneben stehen —
            # wer sie heute liest, liest sie weiter (Unterversion des Vertrags, keine 3).
            "kacheln": _kacheln(inhalt, mails),
            # ⚠ NUR die Auskunft, DASS es eine Zusammenfassung gibt. Ihr Wortlaut sind
            # Betreffzeilen und Absender und liegt hinter dem PIN-Lesegate (SWR-160).
            "zusammenfassung_verfuegbar": punkte is not None and punkte > 0,
        })
    return {"id": zusage["id"], "projekt": projekt, "titel": zusage["titel"],
            "auftrag": zusage["auftrag"], "ziel": zusage["ziel"],
            "eintraege": eintraege,
            # ⚠⚠ Vertrag v2.9 (team-dashboard/T-0001, Brief p0/N-0002 „viel zu groß"):
            # die Liste darf jeden versprochenen Takt tragen — SICHTBAR ist genau EINER.
            # Gemessen am 2026-08-22 lieferte dieses Widget 3 Einträge mit 12 Kacheln in
            # ein Raster, das für EINE Zeitreihe gebaut ist.
            #
            #   Das Widget rendert nicht zu viel, weil jemand zu viel gebaut hat, sondern
            #   weil der Vertrag nie gesagt hat, wie viel genug ist.
            #
            # Die Auswahl steht HIER und nicht im Renderer: eine zweite Stelle, die
            # entscheidet, welcher Takt der jüngste ist, ist die Familie aus B033.
            "sicht_takt": _sicht_takt(eintraege),
            # SWR-160 (projects/p11/T-0013): die Kachel sagt, DASS es einen Inhalt gibt
            # und WO er liegt — sie liefert ihn nicht.
            #
            # ⚠⚠ Kein vierter Zustand. `inhalt_gesperrt` ist ein eigener Schluessel neben
            # `eintraege` und faerbt keinen der drei Werte ein: eine Sperre ist kein
            # Datenzustand, sondern eine Zugriffsregel, und die beiden in EIN Vokabular zu
            # werfen hiesse „keine Daten" und „nicht fuer dich" zu verwechseln.
            #
            # ⚠ Und die Kachel VERSCHWINDET nicht. Eine Kachel, die ohne PIN weg ist,
            # verraet nichts und behauptet dabei, es gaebe hier nichts — dieselbe
            # Verwechslung wie „keine Daten" gegen „0" (SWR-108/135), eine Etage weiter.
            "inhalt_gesperrt": True,
            "inhalt_route": "/api/team/widget-inhalt",
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
