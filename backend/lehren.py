# -*- coding: utf-8 -*-
"""lehren.py (SWR-194, platform/T-0034): hat eine Lehre einen Vertreter?

⚠⚠ **Der Befund, gegen den dieses Modul gebaut ist, war kein Sorgfaltsfehler.** `L-003`
(2026-08-06) war vorbildlich formuliert, **dreifach** abgelegt und trug einen
Erwartungswert (*„Wiederholungsquote in Sprint 2 = 0"*). Gemessen in Sprint 26:
**3 von 3**, nach **14 Tagen** und 25 Sprints.

> **Es fehlte nicht das Aufschreiben. Es fehlte der VERTRETER: der Satz, der ihren
> Vollzug trug, ist nie ein Ticket und nie eine Prüfung geworden.**

⚠ **Was dieses Modul ausdrücklich NICHT tut:** es fordert nicht für jede Lehre einen
Vertreter ein. Das wären am gemessenen Bestand **29 Dauerbefunde**, und ein Dauerbefund
trainiert genau das Wegsehen, gegen das `SWR-166` gebaut ist (83 abgebrochene Läufe).
Der Bestand ist **benannt**, nicht rot.

Die Bauform ist die von `SWR-190`: eine Prüfung, die **von allein rot wird**, wenn etwas
Neues passiert — hier: wenn eine **neue** Lehre mit ausformulierter Regel ohne Vertreter
dazukommt.
"""
import os
import re

#: Wo die Lehren dieses Hauses liegen. ⚠ Über die Rollenordner **entdeckt** und nicht
#: aufgezählt: eine feste Liste wäre an dem Tag falsch, an dem eine elfte Rolle eine
#: `lessons.md` bekommt — dieselbe Stelle, die `SWR-128` dreimal gekostet hat.
LEHREN_GLOB = os.path.join("process", "knowledge", "*", "lessons.md")
#: Der Kopf eines Lehr-Abschnitts. Beide Formen des Bestands: `L-JJJJ-MM-TTxx` und `L-nnn`.
#:
#: ⚠⚠ Die Formen stehen hier **als Muster und nicht als Beispiel**, und das ist an einem
#: echten Fehlschlag gelernt: der erste Entwurf nannte eine **existierende** Lehr-ID zur
#: Veranschaulichung — und hat ihr damit einen Vertreter verschafft. Die Zählung fiel von
#: 29 auf 28, ohne dass sich an der Sache irgendetwas geändert hätte.
#:
#: > **Eine Prüfung, die ihre eigene Frage beantworten kann, prüft nicht mehr.**
LEHRE_KOPF = re.compile(r"^## (L-\d{4}-\d{2}-\d{2}[a-z]*|L-\d{3})\b", re.M)
#: ⚠⚠ **Die ehrliche Untermenge** (Vorabfrage 3 von `platform/T-0034`), und sie ist am
#: Bestand **gemessen** statt gesetzt: von **108** Lehren tragen **34** eine
#: ausformulierte `**Regel:**`. Nicht jede Lehre braucht einen Vertreter — manche sind
#: Beobachtungen. Die Regel-Zeile ist die Konvention, mit der dieses Haus selbst schon
#: unterscheidet; sie ist damit gefunden und nicht erfunden.
REGEL_ZEILE = re.compile(r"^\*\*Regel:?\*\*", re.M)
#: ⚠⚠ **SWR-199 (platform/T-0050, Sprint 31): die „ehrliche Untermenge" war eine
#: SCHREIBWEISE, und die Messung hat das entschieden — nicht eine Meinung.**
#:
#: Anlass: drei Lehren aus Sprint 30 (`cj`, `ck`, `cl`) waren für `REGEL_ZEILE`
#: unsichtbar, weil sie `**Regel.**` statt `**Regel:**` trugen. Die Zählung blieb stehen,
#: **und die Prüfung blieb grün** — eine Sperrklinke, die man mit einem anders gesetzten
#: Doppelpunkt umgeht, ist keine.
#:
#: Gemessen am 2026-08-21 über `process/knowledge/*/lessons.md`:
#:
#: | | Zahl |
#: |---|---|
#: | Lehren gesamt | **112** |
#: | mit `**Regel:**` (die alte Grundmenge) | **38** |
#: | mit **irgendeiner** Regel-Schreibweise | **111** |
#: | `ohne_vertreter` über die alte Grundmenge (38) | **29** |
#: | `ohne_vertreter` über *irgendeine* Regel-Schreibweise (111) | **91** |
#: | `ohne_vertreter` über **alle** Lehren (112) | **91** |
#:
#: **Drei Aussagen, sauber getrennt — die erste Fassung dieses Textes hat sie
#: zusammengezogen und wurde von der eigenen Zusicherung widerlegt:**
#:
#: 1. **Die Konvention „hat eine Regel" trennt praktisch nichts:** 111 von 112 Lehren
#:    tragen eine. Als Auswahlkriterium ist sie keine Auswahl.
#: 2. **`**Regel:**` trennt sehr wohl — aber nach Zeichensetzung, nicht nach Substanz.**
#:    Trefferquote der Vertreter: **24 %** innerhalb der 38 „Erkannten" (9 von 38),
#:    **15 %** unter den 73 „Übersehenen" (11 von 73). Nahezu dasselbe. Die Menge, die
#:    einen Vertreter *braucht*, sieht auf beiden Seiten gleich aus.
#: 3. **Zwischen „irgendeine Regel-Schreibweise" und „gar kein Filter" liegt NULL:**
#:    beide ergeben 91. Die eine Lehre ohne Regel-Zeile hat ohnehin einen Vertreter.
#:
#: > **⚠⚠ Deshalb fällt der Filter, statt erweitert zu werden. Erweitern und Weglassen
#: > sind am gemessenen Bestand dasselbe Ergebnis — und von zwei gleichwertigen Bauformen
#: > ist die mit einem Begriff weniger die richtige.**
#:
#: Der Preis ist in beiden Fällen derselbe und ist der Grund, warum `T-0050` nicht
#: nebenbei repariert wurde: `ohne_vertreter` springt von **29** auf **91** — rund
#: hundert Dauerbefunde und damit `SWR-166` ein viertes Mal. Bezahlt wird er nicht mit
#: einem roten Bestand, sondern mit derselben Bauform, die `SWR-195` und `SWR-197` für
#: ihren Altbestand schon zweimal benutzt haben: die Unterscheidung wandert von der
#: **Schreibweise** auf die **Zeit**. Der gemessene Bestand ist eine **benannte** Menge
#: und bleibt still; rot wird eine **neue** Lehre ohne Vertreter — und ab jetzt in
#: **jeder** Schreibweise, was der eigentliche Ertrag ist: die drei Lehren aus Sprint 30
#: wären auch heute noch unsichtbar.
#:
#: ⚠ **Der Ausstieg wird eine HANDLUNG statt eines Nebeneffekts.** Bisher führte man
#: eine Lehre als bloße Beobachtung, indem man den Doppelpunkt wegließ — unsichtbar und
#: versehentlich. Ab jetzt wird sie ausdrücklich als `**Beobachtung:**` gekennzeichnet.
#: Das Ticket verlangt genau diese Wahl: *„Entweder eine Zusicherung bauen — oder die
#: Lehre bewusst als Beobachtung führen. Beides ist eine Entscheidung."*
#: Am 2026-08-21 trägt **0** Lehre den Marker; er ist ein Ausgang, kein Schlupfloch.
BEOBACHTUNG_ZEILE = re.compile(r"^\*\*Beobachtung:?\*\*", re.M)
#: Dateiendungen, in denen ein Vertreter zählt. ⚠ **Ticketdateien zählen bewusst nicht.**
#: Ein Ticket ist ein Vorsatz mit Datum; eine Zusicherung ist der Vollzug. Genau dieser
#: Unterschied ist der Gegenstand des Tickets — ein Ticket als Vertreter zu zählen hieße,
#: den Befund mit dem zu beantworten, was ihn erzeugt hat.
VERTRETER_ENDUNGEN = (".py", ".cjs", ".js")
#: ⚠⚠ **Dateien, die NICHT als Vertreter zählen dürfen — die Prüfung selbst und ihr Test.**
#:
#: Der Grund ist gemessen und nicht vorsorglich: der erste Entwurf dieses Moduls nannte
#: eine echte Lehr-ID in einem erklärenden Kommentar und hat ihr damit einen Vertreter
#: verschafft. **Die Zählung sank von 29 auf 28, ohne dass sich an der Sache etwas
#: geändert hatte.** Das Muster ist danach neutralisiert worden — aber die Möglichkeit
#: bleibt, solange die Prüfung in ihrem eigenen Korpus liegt.
#:
#: > **Eine Prüfung, die sich selbst liest, kann ihre eigene Frage beantworten. Das ist
#: > dieselbe Tautologie, gegen die `SWR-189` das Literal NEBEN die Zusicherung gestellt
#: > hat — hier gelöst, indem der Prüfer aus der geprüften Menge herausgenommen wird.**
NICHT_VERTRETER = ("lehren.py", "test_lehren_vertreter.py")


def _wurzel(start=None):
    """Die Organisationswurzel — der Ordner, unter dem `process/knowledge/` liegt."""
    pfad = os.path.abspath(start or os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    return pfad


def lehren(wurzel=None):
    """{lehr_id: text} über alle Rollen-Lehrbücher."""
    import glob as _glob
    wurzel = _wurzel(wurzel)
    gefunden = {}
    for datei in sorted(_glob.glob(os.path.join(wurzel, LEHREN_GLOB))):
        with open(datei, encoding="utf-8", errors="replace") as f:
            txt = f.read()
        teile = LEHRE_KOPF.split(txt)
        for i in range(1, len(teile), 2):
            gefunden[teile[i]] = teile[i + 1]
    return gefunden


def mit_regel(wurzel=None):
    """Lehren mit ausformulierter `**Regel:**`, sortiert.

    ⚠ **Ab SWR-199 nicht mehr die Grundmenge**, sondern nur noch die Auskunft, wie viele
    Lehren diese eine Schreibweise tragen. Sie bleibt stehen, weil die Messung aus
    `platform/T-0050` sie zitiert und weil ihr Verhältnis zu `grundmenge()` der Beleg
    ist, dass der Filter nichts ausgewählt hat. Sie zu löschen hieße, die Zahl zu
    verlieren, an der die Entscheidung hängt.
    """
    return sorted(k for k, t in lehren(wurzel).items() if REGEL_ZEILE.search(t))


def beobachtungen(wurzel=None):
    """SWR-199: Lehren, die **ausdrücklich** als Beobachtung geführt werden, sortiert."""
    return sorted(k for k, t in lehren(wurzel).items() if BEOBACHTUNG_ZEILE.search(t))


def grundmenge(wurzel=None):
    """SWR-199: **alle** Lehren außer den ausdrücklich als Beobachtung geführten.

    Die Ablösung von `mit_regel` als Grundmenge. Die Begründung steht bei
    `BEOBACHTUNG_ZEILE` — hier nur die Anwendung: der Regel-Filter entfernte am
    gemessenen Bestand in **jeder** Schreibweise null Lehren aus der Befundmenge, also
    ist er keine Auswahl, sondern Zeremonie.
    """
    aus = set(beobachtungen(wurzel))
    return sorted(k for k in lehren(wurzel) if k not in aus)


def _vertreter_korpus(wurzel):
    """Der Text aller Dateien, in denen ein Vertreter stehen kann.

    ⚠ `.git`, `node_modules` und der Lock-Parkplatz sind ausgenommen — der Parkplatz
    trägt Kopien alter Stände (**11000+** Dateien), und ein Treffer dort wäre ein
    Vertreter, den es heute nicht mehr gibt.
    """
    stuecke = []
    for basis, verzeichnisse, dateien in os.walk(wurzel):
        verzeichnisse[:] = [d for d in verzeichnisse
                            if d not in (".git", "node_modules", "verwaiste-locks")]
        for d in dateien:
            if not d.endswith(VERTRETER_ENDUNGEN) or d in NICHT_VERTRETER:
                continue
            try:
                with open(os.path.join(basis, d), encoding="utf-8", errors="replace") as f:
                    stuecke.append(f.read())
            except OSError:
                continue
    return stuecke


def ohne_vertreter(wurzel=None):
    """Lehren der Grundmenge, die **keine** Zusicherung zitiert. Sortiert.

    ⚠ SWR-199: die Grundmenge ist ab Sprint 31 `grundmenge()` (alle Lehren außer den
    ausdrücklich als Beobachtung geführten) und nicht mehr `mit_regel()`. Der Wechsel
    ist **gemessen** und nicht gewählt: der Regel-Filter entfernte null Lehren aus dem
    Ergebnis dieser Funktion — 91 vor wie nach dem Filter.

    ⚠ Erkannt daran, dass die Lehr-ID im Quelltext einer Prüfung **vorkommt**. Das ist
    eine Textkonvention, und eine Prüfung auf Text prüft den Text und nicht die Sache —
    das ist die Warnung aus Vorabfrage 2 des Tickets, und sie bleibt richtig.

    > **Sie wird trotzdem gebaut, weil die Alternative keine Prüfung ist. Eine Zitierung
    > kann lügen; ein Schweigen kann es nicht. Diese Prüfung findet nicht die schlechte
    > Zusicherung — sie findet die FEHLENDE, und genau die hat vierzehn Tage gekostet.**
    """
    wurzel = _wurzel(wurzel)
    korpus = _vertreter_korpus(wurzel)
    return [k for k in grundmenge(wurzel) if not any(k in t for t in korpus)]

#: ⚠⚠ **Die Lehren, die dieses Haus VERANKERT hat — als benannte Menge und nicht als
#: Zahl** (`SWR-209`, `platform/T-0061`, Sprint 34).
#:
#: **Der Anlass ist ein Datenverlust, den fünf Sprints lang niemand bemerkt hat.** Der
#: Abschluss-Commit von Sprint 32 (`process@a82f207`, Betreff *„Lehren cq-cv
#: verankert"*) hat `knowledge/cm/lessons.md` von **1931 auf 26 Zeilen** und
#: `knowledge/pl/lessons.md` von **871 auf 26** gekürzt: **91 Lehr-Abschnitte gelöscht**,
#: **2 hinzugefügt**. Geschrieben wurde die Datei, statt an sie anzuhängen.
#:
#: > **⚠⚠ Ein Commit, der „verankert" im Betreff trägt, hat 91 Lehren entfernt. Und die
#: > Prüfung, die das hätte finden müssen, hat es als FORTSCHRITT gemeldet: „Diese
#: > Lehre(n) haben einen Vertreter bekommen — bitte die Basis nachziehen."**
#:
#: Die Menge `OHNE_VERTRETER_BASIS` (Stand Sprint 31, **91** IDs) hatte die ganze Zeit
#: recht; die 71 vermeintlich „gewonnenen Vertreter" waren **verschwundene
#: Gegenstände**. `platform/T-0061` hat daraus in Sprint 33 gefolgert, die Lehren hätten
#: *„nie in einem Lehrbuch gelebt"* — auch das war falsch. Sie haben dort gelebt, bis ein
#: Commit sie überschrieb.
#:
#: > **Eine Prüfung, die Schrumpfen nicht von Fortschritt unterscheiden kann, meldet
#: > beides beim Namen des angenehmeren Falls — und ein Bestand kann verschwinden,
#: > während sein Wächter Erfolg meldet.**
#:
#: ⚠ Wiederhergestellt aus `process@386627d` (Sprint-32-Abschluss vor dem Verlust); die
#: beiden danach hinzugekommenen Lehren (`cu`, `cv`) sind **angehängt** und nicht
#: ersetzt. Das ist **kein** Umschreiben von Historie (Playbook Kap. 16), sondern die
#: Rücknahme einer unbeabsichtigten Löschung: die Git-Historie bleibt unangetastet,
#: wiederhergestellt wird der Arbeitsstand.
#:
#: ⚠ Als **Menge** geführt und nicht als Zahl (`L-2026-08-20by`): eine Zahl sagt nicht,
#: WELCHE Lehre verschwunden ist. Neue Lehren kommen hinzu — die Menge ist eine
#: Untergrenze und keine Obergrenze.
VERANKERTE_LEHREN = frozenset({
    "L-2026-08-16", "L-2026-08-16b", "L-2026-08-16c", "L-2026-08-16d",
    "L-2026-08-16e", "L-2026-08-16f", "L-2026-08-16g", "L-2026-08-16h",
    "L-2026-08-16i", "L-2026-08-16j", "L-2026-08-16k", "L-2026-08-16l",
    "L-2026-08-16m", "L-2026-08-17a", "L-2026-08-17aa", "L-2026-08-17ab",
    "L-2026-08-17ac", "L-2026-08-17ad", "L-2026-08-17ae", "L-2026-08-17af",
    "L-2026-08-17ag", "L-2026-08-17ah", "L-2026-08-17ai", "L-2026-08-17aj",
    "L-2026-08-17ak", "L-2026-08-17al", "L-2026-08-17am", "L-2026-08-17an",
    "L-2026-08-17ao", "L-2026-08-17ap", "L-2026-08-17aq", "L-2026-08-17ar",
    "L-2026-08-17as", "L-2026-08-17at", "L-2026-08-17au", "L-2026-08-17av",
    "L-2026-08-17aw", "L-2026-08-17ax", "L-2026-08-17ay", "L-2026-08-17az",
    "L-2026-08-17b", "L-2026-08-17ba", "L-2026-08-17bb", "L-2026-08-17bc",
    "L-2026-08-17bd", "L-2026-08-17be", "L-2026-08-17bf", "L-2026-08-17bg",
    "L-2026-08-17c", "L-2026-08-17d", "L-2026-08-17e", "L-2026-08-17f",
    "L-2026-08-17g", "L-2026-08-17h", "L-2026-08-17i", "L-2026-08-17j",
    "L-2026-08-17k", "L-2026-08-17l", "L-2026-08-17m", "L-2026-08-17n",
    "L-2026-08-17o", "L-2026-08-17p", "L-2026-08-17q", "L-2026-08-17r",
    "L-2026-08-17s", "L-2026-08-17t", "L-2026-08-17u", "L-2026-08-17v",
    "L-2026-08-17w", "L-2026-08-17x", "L-2026-08-17y", "L-2026-08-17z",
    "L-2026-08-20bh", "L-2026-08-20bi", "L-2026-08-20bj", "L-2026-08-20bk",
    "L-2026-08-20bl", "L-2026-08-20bm", "L-2026-08-20bn", "L-2026-08-20bo",
    "L-2026-08-20bp", "L-2026-08-20bq", "L-2026-08-20br", "L-2026-08-20bs",
    "L-2026-08-20bt", "L-2026-08-20bu", "L-2026-08-20bv", "L-2026-08-20bw",
    "L-2026-08-20bx", "L-2026-08-20by", "L-2026-08-20bz", "L-2026-08-20ca",
    "L-2026-08-20cb", "L-2026-08-20cc", "L-2026-08-20cd", "L-2026-08-20ce",
    "L-2026-08-20cf", "L-2026-08-20cg", "L-2026-08-20ch", "L-2026-08-20ci",
    "L-2026-08-20cj", "L-2026-08-20ck", "L-2026-08-20cl", "L-2026-08-20cm",
    "L-2026-08-20cn", "L-2026-08-20co", "L-2026-08-20cp", "L-2026-08-20cq",
    "L-2026-08-21cj", "L-2026-08-21ck", "L-2026-08-21cl", "L-2026-08-21cm",
    "L-2026-08-21cn", "L-2026-08-21co", "L-2026-08-21cp", "L-2026-08-21cq",
    "L-2026-08-21cr", "L-2026-08-21cs", "L-2026-08-21ct", "L-2026-08-21cu",
    "L-2026-08-21cv", "L-2026-08-21cw", "L-2026-08-21cx", "L-2026-08-21cy",
    "L-2026-08-21cz", "L-2026-08-21da",
})


def verschwundene(wurzel=None):
    """Verankerte Lehren, die heute **keinen Kopf mehr** in einem Lehrbuch haben. Sortiert.

    ⚠ Die Antwort ist eine Liste von **Namen** und keine Differenz zweier Zahlen — genau
    daran ist der Verlust aus Sprint 32 fünf Sprints lang vorbeigelaufen.
    """
    vorhanden = set(lehren(wurzel))
    return sorted(VERANKERTE_LEHREN - vorhanden)
