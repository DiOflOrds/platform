// Verhalten des EINEN Renderwegs (projects/p12/T-0006, ADR-P12-001).
//
// ⚠⚠ **Was diese Datei prueft und `test_renderweg_zaehlung.py` nicht.** Der Zaehltest liest
// den Quelltext: er sieht, dass es einen Renderer gibt und dass der Inline-Pass ein Muster
// mit `T-\d{4}` traegt. Er sieht **nicht**, was dabei herauskommt.
//
// > **Ein Muster im Quelltext ist eine Absicht. Erst der Knoten, der danach dasteht, ist
// > ein Befund.**
//
// SWR-098 verlangt den Nachweis woertlich an drei Orten — Fliesstext, Listenpunkt,
// Tabellenzelle —, weil genau das der Unterschied zum alten Weg ist: `tlinks` bekam immer
// nur eine fertige Zeichenkette und wusste nie, wo sie stand.
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const { ladeRenderer } = require("./_app_laden.cjs");

const PROJEKT = "p11";

/** Alle Knoten des Baums, flach — der Mini-DOM kann kein `querySelectorAll`. */
function alle(k, aus) {
  aus = aus || [];
  if (!k || !k.kinder) return aus;
  k.kinder.forEach((kind) => { aus.push(kind); alle(kind, aus); });
  return aus;
}

const links = (baum) => alle(baum).filter((k) => k.tagName === "a");
const tags = (baum, t) => alle(baum).filter((k) => k.tagName === t);

// ---------------------------------------------------------------- SWR-098

test("SWR-098: T-nnnn im FLIESSTEXT wird ein Link", () => {
  const baum = ladeRenderer()("Wir haben T-0042 geschlossen.", PROJEKT);
  const a = links(baum);
  assert.strictEqual(a.length, 1, "kein Link im Fliesstext");
  assert.strictEqual(a[0].textContent, "T-0042");
  assert.strictEqual(a[0].attrs.href, "#/ticket/p11/T-0042");
  // ⚠ Die Annahme ist SICHTBAR und nicht stillschweigend (SWR-114/SWR-150): der Text sagt
  // nicht, aus welchem Projekt die Nummer kommt.
  assert.match(a[0].attrs.title, /^angenommen: p11\/T-0042$/);
});

test("SWR-098: T-nnnn im LISTENPUNKT wird ein Link", () => {
  // ⚠ Genau das konnte der alte Weg nicht: `mdRender` machte das `<li>`, und `tlinks` sah
  // den Text nie. Ein `T-0042` in einer Liste war bis heute kein Link.
  const baum = ladeRenderer()("- offen: T-0042\n- erledigt: T-0043", PROJEKT);
  const a = links(baum);
  assert.strictEqual(tags(baum, "li").length, 2);
  assert.deepStrictEqual(a.map((x) => x.textContent), ["T-0042", "T-0043"]);
});

test("SWR-098: T-nnnn in der TABELLENZELLE wird ein Link", () => {
  const baum = ladeRenderer()("| Ticket | Stand |\n|---|---|\n| T-0042 | offen |", PROJEKT);
  const a = links(baum);
  assert.strictEqual(a.length, 1, "kein Link in der Tabellenzelle");
  assert.strictEqual(a[0].attrs.href, "#/ticket/p11/T-0042");
});

test("SWR-098: `T-0042` in BACKTICKS bleibt ein Zitat und wird KEIN Link", () => {
  // ⚠ Die Reihenfolge im Muster als Verhalten gemessen, nicht als Stellung im Quelltext.
  // Verlinkte man es, verlinkte die Dokumentation ueber den Renderer ihre eigenen Beispiele.
  const baum = ladeRenderer()("Ein Beispiel ist `T-0042` im Text.", PROJEKT);
  assert.strictEqual(links(baum).length, 0, "das Zitat wurde verlinkt");
  assert.strictEqual(tags(baum, "code").length, 1);
  assert.strictEqual(tags(baum, "code")[0].textContent, "T-0042");
});

test("SWR-098/150: OHNE Projekt entsteht Text und kein Link", () => {
  // ⚠ Ein Link auf das falsche Projekt ist schlimmer als kein Link — er oeffnet ein
  // fremdes Ticket und sieht dabei richtig aus. 68 Nummern gibt es mehrfach.
  const baum = ladeRenderer()("Siehe T-0042.", "");
  assert.strictEqual(links(baum).length, 0, "eine nackte Nummer wurde verlinkt");
  assert.match(baum.textContent, /T-0042/, "die Nummer ist beim Nichtverlinken verschwunden");
});

test("SWR-098: FETTDRUCK und Ticketlink stehen in DERSELBEN Zelle", () => {
  // ⚠⚠ Der Beleg von ADR-P12-001, umgedreht: der alte Aufrufer warf `**` weg, damit der
  // Link-Weg nicht daran scheitert. Beides zugleich zu koennen ist der ganze Punkt der
  // Zusammenfuehrung — und es ist die Stelle, an der zwei Wege eine Luecke hatten.
  const baum = ladeRenderer()("| Was | Wer |\n|---|---|\n| **wichtig** T-0042 | pl |", PROJEKT);
  assert.strictEqual(tags(baum, "strong").length, 1, "kein Fettdruck in der Zelle");
  assert.strictEqual(links(baum).length, 1, "kein Link in derselben Zelle");
  assert.ok(!baum.textContent.includes("*"), "die Sternchen stehen als Zeichen da");
});

// ---------------------------------------------------------------- SWR-099

test("SWR-099: ein Code-Zaun bleibt VERBATIM und behaelt seine Zeilenumbrueche", () => {
  const quelle = "Vorher\n```\nzeile eins\n  eingerueckt\nzeile drei\n```\nNachher";
  const baum = ladeRenderer()(quelle, PROJEKT);
  const pre = tags(baum, "pre");
  assert.strictEqual(pre.length, 1, "kein <pre> fuer den Zaun");
  assert.strictEqual(pre[0].textContent, "zeile eins\n  eingerueckt\nzeile drei");
  assert.strictEqual(tags(baum, "code").length, 1, "kein <code> im <pre>");
});

test("SWR-099: im Zaun ist ** ein Sternchenpaar und T-0042 eine Zeichenfolge", () => {
  // ⚠ Ein Link im Codebeispiel ist ein Fehler, der wie eine Verbesserung aussieht.
  const baum = ladeRenderer()("```\nvar x = **fett** T-0042;\n```", PROJEKT);
  assert.strictEqual(links(baum).length, 0, "der Zaun wurde inline interpretiert");
  assert.strictEqual(tags(baum, "strong").length, 0);
  assert.strictEqual(tags(baum, "pre")[0].textContent, "var x = **fett** T-0042;");
});

test("SWR-099: ein NICHT geschlossener Zaun endet am Textende und verschluckt nichts", () => {
  const baum = ladeRenderer()("Text davor\n```\nrest ohne ende\nnoch eine zeile", PROJEKT);
  assert.match(baum.textContent, /Text davor/);
  assert.match(baum.textContent, /rest ohne ende/);
  assert.match(baum.textContent, /noch eine zeile/);
});

test("SWR-099: der ABSATZ bleibt beim Zusammenfuegen mit Leerzeichen", () => {
  // Gegenprobe zum Zaun: die Reparatur durfte den Absatzpfad nicht mit umbauen.
  const baum = ladeRenderer()("erste zeile\nzweite zeile", PROJEKT);
  assert.strictEqual(tags(baum, "p").length, 1);
  assert.strictEqual(tags(baum, "p")[0].textContent, "erste zeile zweite zeile");
});

// ---------------------------------------------------------------- SWR-100

test("SWR-100: Markup in einem Brief erscheint als TEXT, nicht als Element", () => {
  // ⚠ Briefe sind freier Text eines Menschen durch das Chat-Formular. Diese Zusicherung
  // misst das ERGEBNIS; die Statikpruefung misst, dass kein `innerHTML` im Quelltext steht.
  // Beides zusammen, weil eine Ausfuehrungsstelle auch ohne `innerHTML` entstehen kann.
  const boese = '<script>alert(1)</script> und <img src=x onerror=alert(2)>';
  const baum = ladeRenderer()(boese, PROJEKT);
  assert.strictEqual(tags(baum, "script").length, 0, "ein <script>-Knoten ist entstanden");
  assert.strictEqual(tags(baum, "img").length, 0, "ein <img>-Knoten ist entstanden");
  assert.ok(baum.textContent.includes("<script>alert(1)</script>"),
            "das Markup steht nicht als Text da");
});

test("GEGENPROBE: der Baumleser wuerde einen Link ueberhaupt finden", () => {
  // ⚠ Ohne diese Zusicherung belegen die Negativpruefungen oben nur, dass `links()` immer
  // leer ist. Eine Messung, die nie etwas findet, ist von einer gruenen nicht zu
  // unterscheiden — der Befund aus der Trennschaerfe von SWR-149.
  const baum = ladeRenderer()("[Anthropic](https://www.anthropic.com)", PROJEKT);
  assert.strictEqual(links(baum).length, 1, "der Baumleser findet nicht einmal einen Link");
});
