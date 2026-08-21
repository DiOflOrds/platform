// Der Kommentar-Kasten an der Aufgabe (SWR-192, platform/T-0030, Brief platform/N-0007).
//
// ⚠⚠ **Die teuerste Zusicherung hier ist die an der ERLEDIGTEN Aufgabe.** DoD 6 des
// Tickets sagt: die Archivsperre gilt dem FORMULAR, nicht dem GESPRAECH. Ein Kasten, der
// an `done` verschwindet, waere genau der Kanal, der dort schweigt, wo am haeufigsten
// gefragt wird — und er waere in einem Test ueber ein offenes Ticket **gruen**.
//
// ⚠ Geprueft wird der KNOTEN und nicht das Muster im Quelltext. Ein Muster ist eine
// Absicht; erst der Knoten, der dasteht, ist ein Befund (dieselbe Trennung wie in
// `renderweg_p12.test.cjs`).
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const { ladeKontext } = require("./_app_laden.cjs");

/** Alle Knoten des Baums, flach — der Mini-DOM kann kein `querySelectorAll`. */
function alle(k, aus) {
  aus = aus || [];
  if (!k || !k.kinder) return aus;
  k.kinder.forEach((kind) => { aus.push(kind); alle(kind, aus); });
  return aus;
}

const tags = (baum, t) => alle(baum).filter((k) => k.tagName === t);

function ticket(extra) {
  return Object.assign({
    id: "T-0001", ref: "platform/T-0001", titel: "Ein Ticket", status: "open",
    fingerprint: "abc123", kommentare: [],
  }, extra || {});
}

function verlauf(t) {
  const kontext = ladeKontext();
  assert.strictEqual(typeof kontext.verlaufsKarte, "function",
                     "verlaufsKarte nicht gefunden — der Nachweis prueft sonst nichts");
  return kontext.verlaufsKarte(t);
}

test("SWR-192: ohne Beitrag steht da, dass noch keiner da ist — und trotzdem ein Feld", () => {
  const karte = verlauf(ticket());
  assert.match(karte.textContent, /Noch kein Beitrag/,
               "die leere Lage sagt nichts — der Kasten sieht dann aus wie ein Fehler");
  assert.strictEqual(tags(karte, "textarea").length, 1, "kein Eingabefeld");
  assert.strictEqual(tags(karte, "button").length, 1, "kein Sendeknopf");
});

test("SWR-192: die Beitraege stehen im Kasten, mit Absender und Zeit", () => {
  const karte = verlauf(ticket({ kommentare: [
    { von: "Mensch via HMI", zeit: "2026-08-21 11:00", text: "zweiter" },
    { von: "Mensch via HMI", zeit: "2026-08-21 10:00", text: "erster" },
  ] }));
  const text = karte.textContent;
  assert.match(text, /zweiter/);
  assert.match(text, /erster/);
  assert.match(text, /2026-08-21 11:00/);
  assert.match(text, /Mensch via HMI/);
});

test("SWR-192, DoD 5: neuester zuerst — und die Reihenfolge kommt aus dem Backend", () => {
  const karte = verlauf(ticket({ kommentare: [
    { von: "x", zeit: "2026-08-21 11:00", text: "NEUER" },
    { von: "x", zeit: "2026-08-21 10:00", text: "AELTER" },
  ] }));
  const text = karte.textContent;
  assert.ok(text.indexOf("NEUER") < text.indexOf("AELTER"),
            "der neueste Beitrag steht nicht oben");
});

test("SWR-192: die Karte sortiert NICHT selbst nach — zwei Sortierungen sind zwei Meinungen", () => {
  // ⚠ Die Liste kommt hier ABSICHTLICH in der falschen Reihenfolge. Wuerde die Karte
  // selbst sortieren, stuende sie danach richtig — und die Zusicherung im Backend
  // (`test_ticket_kommentar.test_neueste_zuerst`) waere ab da unwirksam, ohne dass es
  // jemand merkt.
  const karte = verlauf(ticket({ kommentare: [
    { von: "x", zeit: "2026-08-21 10:00", text: "AELTER" },
    { von: "x", zeit: "2026-08-21 11:00", text: "NEUER" },
  ] }));
  const text = karte.textContent;
  assert.ok(text.indexOf("AELTER") < text.indexOf("NEUER"),
            "die Karte sortiert nach — damit gibt es zwei Stellen, die 'neu' definieren");
});

test("SWR-192, DoD 6: der Kasten steht AUCH an erledigten und abgelehnten Aufgaben", () => {
  ["done", "rejected"].forEach((status) => {
    const karte = verlauf(ticket({ status }));
    assert.strictEqual(tags(karte, "textarea").length, 1,
                       `kein Eingabefeld bei status=${status} — die Archivsperre gilt `
                       + "dem Formular, nicht dem Gespraech (DoD 6)");
    assert.strictEqual(tags(karte, "button").length, 1,
                       `kein Sendeknopf bei status=${status}`);
  });
});

test("SWR-192: der Beitragstext laeuft durch denselben Renderer wie der Rumpf", () => {
  // ⚠ Sonst haette ein Ticketverweis im Kommentar keinen Link — und der Verlauf waere
  // eine zweite Textsorte in derselben Ansicht.
  const karte = verlauf(ticket({ kommentare: [
    { von: "x", zeit: "2026-08-21 11:00", text: "siehe T-0042" },
  ] }));
  const links = tags(karte, "a");
  assert.strictEqual(links.length, 1, "kein Link im Beitragstext");
  assert.strictEqual(links[0].textContent, "T-0042");
});
