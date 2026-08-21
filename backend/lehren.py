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
