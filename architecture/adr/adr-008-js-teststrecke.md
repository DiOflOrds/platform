# ADR-008: Teststrecke für die Renderregeln des Frontends

*Status: entschieden (PL/ARCH, 2026-08-17, `projects/p12/T-0004`, Sprint 12). Gate: G2-Vorlage.
Teilfrage „darf Node Voraussetzung werden?" **nicht** hier entschieden — Klasse A, DR
`projects/p12/T-0007`.*

## Kontext — und die Messung, die ihn hart macht

`projects/p12/T-0004` verlangt die Teststrecken-Entscheidung **vor** jeder Umstellung, und
sie verbietet ausdrücklich, den Nachweis durch das Wort „Tests" zu ersetzen (B027/B038).

Gemessen am Bestand vom 2026-08-17:

| | |
|---|---|
| Python-Tests | **741** |
| JS-Tests | **0** |
| Zeilen in `platform/backend/static/app.js` | **1.524** |
| Anforderungen, die Nachweise an JavaScript verlangen | SWR-098, SWR-099, SWR-100 |
| bisherige Abnahmeform (ADR-002) | „UI-Checkliste statt automatisierter UI-Tests im MVP" |

ADR-002 hat diesen Verzicht **bewusst** getroffen — für ein MVP mit „vier Ansichten und
einem Formular" — und im selben Satz die Bedingung genannt, unter der er endet: *„bei
wachsendem Frontend-Scope (nach P0) neu bewerten."* Der Scope ist gewachsen; die
Neubewertung ist dieses ADR. **ADR-002 wird damit nicht widerrufen, sondern eingelöst.**

⚠ Der Anlass ist konkret: `pm/T-0058` und `pm/T-0060` fordern in ihrer DoD wörtlich einen
„JS-Test, der nachweislich gegen den Vorstand scheitert". Ohne Strecke gibt es diesen
Nachweis nicht — und der HMI-Sprint hätte seine eigene Abnahme nicht erfüllen können.

## Optionen — einzeln bewertet, wie das Ticket es verlangt

**(1) Pool-Kandidat #8 („JS-Frontend-Tests") vorziehen.** Ein vollständiges Frontend-
Testwerkzeug (Jest/Vitest + jsdom, oder Playwright) prüft auch das DOM. Preis: ein
`package.json`, ein `node_modules`, eine Toolchain auf jedem Gerät — genau die
Build-Pipeline, gegen die ADR-002 entschieden hat, und ein Paketbaum aus dem Netz in einem
Bestand, der „Artefakt = Evidenz" als Prinzip führt. **Verworfen** für diesen Schnitt; als
Pool-Kandidat bleibt er bestehen, falls DOM-Prüfungen später wirklich gebraucht werden.

**(2) Die Renderregeln in eine ohne Browser prüfbare Form bringen.** Die Entscheidungen
werden von der Darstellung getrennt: `static/regeln.js` beantwortet Fragen („von wem ist
dieser Beitrag?", „ist der Brief durch eine Nachfrage wieder offen?") und rührt kein
Element an; `app.js` bleibt das dünne Stück, das aus der Antwort ein Element macht. Geprüft
wird mit dem **eingebauten** Testrunner von Node (`node --test`, `node:test`) — **kein
npm, kein package.json, keine heruntergeladene Abhängigkeit.** **Gewählt.**

**(3) Begründet auf dokumentierte manuelle Stichproben zurückfallen.** Das ist der Status
quo aus ADR-002, und `p12/T-0004` nennt ihn für diesen Fall ausdrücklich **nicht erfüllt**.
Er bliebe die ehrliche Wahl, wenn (2) an der Laufzeitfrage scheitert — dann aber als
*benannter Rückfall* mit Namen im Preflight, nicht als Schweigen. **Verworfen als Ziel,
behalten als Rückfallebene** (siehe „Konsequenzen").

## Entscheidung

Option 2, in drei Teilen:

1. **Regeln ohne DOM.** Jede Renderentscheidung, die eine Frage beantwortet, wandert nach
   `platform/backend/static/regeln.js`. Die Datei kennt weder `document` noch `fetch`.
   Sie wird von `index.html` als klassisches `<script>` geladen und von der Teststrecke
   über `require()` gelesen — drei Zeilen am Dateiende, kein Bundler. **ADR-002 bleibt
   gültig: es gibt weiterhin keinen Build.**
2. **Runner ohne Paket.** `node --test` über `platform/tests/js/*.test.cjs`, gestartet aus
   `platform/scripts/js_tests.py`. Node bringt Runner und Assertions seit v18 mit; die
   Strecke lädt nichts nach und braucht kein Netz.
3. **Der Zustand wird immer gemeldet.** `js_tests.lauf()` kennt drei Zustände — `ok`,
   `rot`, `uebersprungen` — und der Preflight druckt seine Zeile in **allen dreien**.
   `rot` zählt als Befund.

## ⚠ Was hier NICHT entschieden wird — und warum

**Ob Node eine Voraussetzung des Projekts werden darf, ist Klasse A** („neues externes
Werkzeug", harte Regel; `p12/T-0004` nennt genau diesen Fall). Diese Frage geht als
Decision Request **an den Menschen**: `projects/p12/T-0007`, mit Frist und Default.

Bis dahin gilt: **`uebersprungen` zählt nicht als Befund.** Fehlt Node auf dem Gerät des
Auftraggebers, läuft sein Preflight weiter — er bekommt eine Zeile, keine Sperre. Ein
Werkzeug, über das noch niemand entschieden hat, darf den Lauf nicht blockieren.

⚠ Und `uebersprungen` ist **nicht** `ok`. Das ist die Lehre aus SWR-114 und SWR-122,
wörtlich: eine Prüfung, die nicht lief, ist von einer grünen nicht zu unterscheiden, sobald
beide dasselbe melden. Der Test dazu (`test_ohne_node_ist_der_zustand_uebersprungen_und_NICHT_ok`)
ist die teuerste Zusicherung dieser Strecke, weil sie die Strecke selbst betrifft.

## Konsequenzen

* **Das DOM bleibt ungeprüft.** Diese Strecke sagt nichts darüber, ob ein `<div>` an der
  richtigen Stelle steht. Sie sagt, ob die *Entscheidung* dahinter stimmt. Wer mehr will,
  zieht Option 1 — und braucht dafür einen eigenen Beschluss.
* **Die Trennung muss gehalten werden.** Eine Regel, die in `app.js` zurückwandert, ist
  wieder ungeprüft. Das ist kein Mechanismus, sondern eine Gewohnheit — und Sprint 11 hat
  dreimal gezeigt, was eine aufgeschriebene Regel ohne Prüfung wert ist. Kandidat für eine
  spätere Prüfung: `regeln.js` darf die Zeichenfolgen `document`/`window.` nicht enthalten.
* **Rückfallebene, benannt:** entscheidet der Mensch gegen Node, bleibt Option 3 — und die
  Zeile im Preflight sagt dann dauerhaft, dass hier von Hand geprüft wird. Der Zustand ist
  dann schlechter, aber **sichtbar**; das ist der ganze Unterschied zu vorher.
* `SWR-128` trägt diese Entscheidung als Anforderung; `SWR-129` ist die erste Regel, die
  darauf gebaut wurde.
