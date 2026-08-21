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
    """Die Grundmenge: Lehren mit ausformulierter `**Regel:**`, sortiert."""
    return sorted(k for k, t in lehren(wurzel).items() if REGEL_ZEILE.search(t))


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
    """Lehren mit Regel, die **keine** Zusicherung zitiert. Sortiert.

    ⚠ Erkannt daran, dass die Lehr-ID im Quelltext einer Prüfung **vorkommt**. Das ist
    eine Textkonvention, und eine Prüfung auf Text prüft den Text und nicht die Sache —
    das ist die Warnung aus Vorabfrage 2 des Tickets, und sie bleibt richtig.

    > **Sie wird trotzdem gebaut, weil die Alternative keine Prüfung ist. Eine Zitierung
    > kann lügen; ein Schweigen kann es nicht. Diese Prüfung findet nicht die schlechte
    > Zusicherung — sie findet die FEHLENDE, und genau die hat vierzehn Tage gekostet.**
    """
    wurzel = _wurzel(wurzel)
    korpus = _vertreter_korpus(wurzel)
    return [k for k in mit_regel(wurzel) if not any(k in t for t in korpus)]
