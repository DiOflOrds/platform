// FRT-PWA (T-0033, SWR-021; ADR-002): vier Ansichten + Inbox-Formular, reine API-Aufrufe.
"use strict";
const TABS = [["board", "Board"], ["inbox", "Inbox"], ["reports", "Reports"], ["kpi", "Kosten/KPI"]];
const inhalt = document.getElementById("inhalt");
const tabsEl = document.getElementById("tabs");
let aktiv = location.hash.replace("#", "") || "board";

async function api(pfad, optionen) {
  const r = await fetch(pfad, optionen);
  const daten = await r.json();
  if (!r.ok) throw new Error(daten.fehler || r.status);
  return daten;
}
const el = (tag, attrs = {}, ...kinder) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) (k === "class") ? e.className = v : (k.startsWith("on") ? e.addEventListener(k.slice(2), v) : e.setAttribute(k, v));
  e.append(...kinder);
  return e;
};

function zeigeTabs() {
  tabsEl.replaceChildren(...TABS.map(([id, name]) =>
    el("button", { class: id === aktiv ? "aktiv" : "", onclick: () => { aktiv = id; location.hash = id; lade(); } }, name)));
}

async function ladeBoard() {
  const b = await api("/api/board");
  document.getElementById("stand").textContent = `${b.anzahl} Tickets`;
  const reihenfolge = ["open", "in_analysis", "in_progress", "in_review", "blocked", "done", "rejected"];
  inhalt.replaceChildren(...reihenfolge.filter(s => b.gruppen[s]?.length).map(status =>
    el("div", { class: "karte" },
      el("h3", {}, `${status} (${b.gruppen[status].length})`),
      ...b.gruppen[status].map(t => el("div", { class: "zeile" },
        el("span", { class: `pille ${status}` }, t.id),
        document.createTextNode(` ${t.titel} `),
        el("span", { class: "pille" }, `${t.rolle} · S${t.sprint} · ${t.prio}`))))));
}

async function ladeInbox() {
  const { inbox } = await api("/api/inbox");
  if (!inbox.length) { inhalt.replaceChildren(el("p", { class: "leer" }, "Keine offenen Entscheidungen. 🎉")); return; }
  inhalt.replaceChildren(...inbox.map(dr => {
    const opt = el("input", { placeholder: "Gewählte Option (z. B. „A" oder Freitext)" });
    const grund = el("textarea", { rows: "2", placeholder: "Begründung (optional)" });
    const knopf = el("button", { class: "knopf" }, "Entscheiden");
    const meldung = el("div");
    knopf.addEventListener("click", async () => {
      knopf.disabled = true;
      try {
        const e = await api(`/api/inbox/${dr.id}/decision`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ option: opt.value, begruendung: grund.value }) });
        meldung.replaceChildren(el("div", { class: "meldung ok" },
          `Angenommen als ${e.entscheidung} (Mail: ${e.mail ? "gesendet" : "nicht konfiguriert"}).`));
      } catch (fehler) {
        meldung.replaceChildren(el("div", { class: "meldung fehler" }, String(fehler.message || fehler)));
        knopf.disabled = false;
      }
    });
    return el("div", { class: "karte" },
      el("h3", {}, `${dr.id} — ${dr.titel}`),
      el("div", { class: "zeile" }, el("span", { class: `pille ${dr.status}` }, dr.status),
        el("span", { class: "pille" }, `${dr.prio} · Sprint ${dr.sprint}`)),
      el("pre", {}, dr.body), opt, grund, knopf, meldung);
  }));
}

async function ladeReports() {
  const { reports } = await api("/api/reports");
  inhalt.replaceChildren(...(reports.length ? reports.map(r =>
    el("div", { class: "karte" }, el("h3", {}, r.sprint), el("pre", {}, r.text)))
    : [el("p", { class: "leer" }, "Noch keine Sprint-Reports.")]));
}

async function ladeKpi() {
  const k = await api("/api/kpi");
  inhalt.replaceChildren(
    el("div", { class: "karte kpiraster" },
      el("div", { class: "kpi" }, el("b", {}, String(k.laeufe)), "Läufe"),
      el("div", { class: "kpi" }, el("b", {}, `${k.kosten_eur_gesamt.toFixed(2)} €`), "Kosten gesamt"),
      ...Object.entries(k.laeufe_je_provider).map(([p, n]) => el("div", { class: "kpi" }, el("b", {}, String(n)), p))),
    el("div", { class: "karte" }, el("h3", {}, "Kosten je Monat"),
      ...Object.entries(k.kosten_eur_je_monat).map(([m, eur]) => el("div", { class: "zeile" }, `${m}: ${eur.toFixed(2)} €`)),
      el("h3", {}, "Letzte Läufe"), el("pre", {}, JSON.stringify(k.letzte, null, 1))));
}

async function lade() {
  zeigeTabs();
  inhalt.replaceChildren(el("p", { class: "leer" }, "Lade …"));
  try {
    await ({ board: ladeBoard, inbox: ladeInbox, reports: ladeReports, kpi: ladeKpi })[aktiv]();
  } catch (fehler) {
    inhalt.replaceChildren(el("div", { class: "meldung fehler" }, `API nicht erreichbar: ${fehler.message || fehler}`));
  }
}
lade();
