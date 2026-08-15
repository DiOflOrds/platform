// FRT-PWA (T-0033, SWR-021; ADR-002): Ansichten + Inbox, reine API-Aufrufe.
// T-0040: abwärtskompatibel (kein replaceChildren, kein optional chaining) + sichtbare JS-Fehler.
// P1/T-0006 (SWR-026): Projektwahl + projektübergreifende Übersicht.
// P3 Sprint 1 (ADR-005): Hash-Router #/<tab>/<projekt>[/<id>], Ticket-Detail (SWR-040),
// Jira-Board mit Filtern (SWR-041), Inbox-Buttons + Historie (SWR-042), Versions-Banner (SWR-047).
"use strict";
var TABS = [["uebersicht", "Übersicht"], ["board", "Board"], ["inbox", "Inbox"],
            ["requirements", "Requirements"], ["trace", "Traceability"],
            ["baselines", "Baselines"], ["reports", "Reports"], ["kpi", "Kosten/KPI"]];
var inhalt = document.getElementById("inhalt");
var tabsEl = document.getElementById("tabs");
var projektEl = document.getElementById("projekt");
var aktiv = "uebersicht";
var projekt = "p0";
var detailId = "";
var boardFilter = { sprint: "", rolle: "", typ: "" };

window.onerror = function (meldung, quelle, zeile) {
  var kasten = document.createElement("div");
  kasten.className = "meldung fehler";
  kasten.textContent = "JS-Fehler: " + meldung + " (" + (quelle || "?") + ":" + zeile + ")";
  (inhalt || document.body).appendChild(kasten);
};

function leeren(knoten) { while (knoten.firstChild) knoten.removeChild(knoten.firstChild); }

function el(tag, attrs) {
  var e = document.createElement(tag);
  attrs = attrs || {};
  Object.keys(attrs).forEach(function (k) {
    if (k === "class") e.className = attrs[k];
    else if (k.indexOf("on") === 0) e.addEventListener(k.slice(2), attrs[k]);
    else e.setAttribute(k, attrs[k]);
  });
  for (var i = 2; i < arguments.length; i++) {
    var kind = arguments[i];
    e.appendChild(typeof kind === "string" ? document.createTextNode(kind) : kind);
  }
  return e;
}

function api(pfad, optionen) {
  return fetch(pfad, optionen).then(function (r) {
    return r.json().then(function (daten) {
      if (!r.ok) throw new Error(daten.fehler || r.status);
      return daten;
    });
  });
}

// ---------- Router (ADR-005): #/<tab>/<projekt>[/<id>], alt "#board" bleibt gültig ----------
function gehe(tab, proj, id) {
  location.hash = "#/" + tab + "/" + (proj || projekt) + (id ? "/" + id : "");
}

function parseHash() {
  var h = location.hash.replace(/^#\/?/, "");
  var teile = h.split("/");
  aktiv = teile[0] || "uebersicht";
  if (teile[1]) { projekt = teile[1]; if (projektEl.value !== projekt) projektEl.value = projekt; }
  detailId = teile[2] || "";
}

window.addEventListener("hashchange", function () { parseHash(); lade(); });

// ---------- Bausteine ----------
function pille(text, klasse) { return el("span", { "class": "pille " + (klasse || "") }, String(text)); }

function tlinks(text, proj) {
  // T-xxxx im Text als Links auf die Detailansicht (SWR-040)
  var knoten = [], rest = String(text || ""), m;
  while ((m = rest.match(/T-\d{4}/))) {
    if (m.index > 0) knoten.push(document.createTextNode(rest.slice(0, m.index)));
    (function (id) {
      knoten.push(el("a", { "class": "tlink", href: "#/ticket/" + proj + "/" + id }, id));
    })(m[0]);
    rest = rest.slice(m.index + 6);
  }
  if (rest) knoten.push(document.createTextNode(rest));
  return knoten;
}

function preMitLinks(text, proj) {
  var p = el("pre", {});
  tlinks(text, proj).forEach(function (k) { p.appendChild(k); });
  return p;
}

function zeigeTabs() {
  leeren(tabsEl);
  TABS.forEach(function (paar) {
    tabsEl.appendChild(el("button", {
      "class": paar[0] === aktiv ? "aktiv" : "",
      onclick: function () { gehe(paar[0], projekt); }
    }, paar[1]));
  });
}

function zeige(elemente) {
  leeren(inhalt);
  elemente.forEach(function (e) { inhalt.appendChild(e); });
}

// ---------- Ansichten ----------
function ladeUebersicht() {
  return api("/api/uebersicht").then(function (u) {
    document.getElementById("stand").textContent = u.projekte.length + " Projekt(e)";
    zeige(u.projekte.map(function (p) {
      var karte = el("div", { "class": "karte" },
        el("h3", {}, p.projekt),
        el("div", { "class": "zeile" },
          pille(p.tickets_offen + " offen", "open"), pille(p.tickets_gesamt + " gesamt")));
      if (p.offene_drs.length) {
        karte.appendChild(el("div", { "class": "zeile" }, "Offene Entscheidungen:"));
        p.offene_drs.forEach(function (dr) {
          karte.appendChild(el("div", { "class": "zeile" },
            el("a", { "class": "tlink", href: "#/inbox/" + p.projekt }, dr.id), " " + dr.titel));
        });
      }
      karte.appendChild(el("button", { "class": "knopf", onclick: function () {
        gehe("board", p.projekt);
      } }, "Zum Board"));
      return karte;
    }));
  });
}

function filterSelect(name, werte, beschriftung) {
  var s = el("select", { style: "width:auto;margin:0", onchange: function () {
    boardFilter[name] = s.value; lade();
  } }, el("option", { value: "" }, beschriftung + ": alle"));
  werte.forEach(function (w) {
    var o = el("option", { value: w }, beschriftung + ": " + w);
    if (boardFilter[name] === w) o.setAttribute("selected", "selected");
    s.appendChild(o);
  });
  return s;
}

function ladeBoard() {  // SWR-041: Jira-like — Statusspalten, Filter, Karte -> Detail
  return api("/api/board?projekt=" + encodeURIComponent(projekt)).then(function (b) {
    document.getElementById("stand").textContent = b.anzahl + " Tickets";
    var reihenfolge = ["open", "in_analysis", "in_progress", "in_review", "blocked", "done", "rejected"];
    var alle = [], werte = { sprint: [], rolle: [], typ: [] };
    reihenfolge.forEach(function (status) {
      (b.gruppen[status] || []).forEach(function (t) { t._status = status; alle.push(t); });
    });
    alle.forEach(function (t) {
      ["sprint", "rolle", "typ"].forEach(function (k) {
        var v = String(t[k] || "");
        if (v && werte[k].indexOf(v) < 0) werte[k].push(v);
      });
    });
    var filterzeile = el("div", { "class": "karte filterzeile" },
      filterSelect("sprint", werte.sprint.sort(), "Sprint"),
      filterSelect("rolle", werte.rolle.sort(), "Rolle"),
      filterSelect("typ", werte.typ.sort(), "Typ"));
    var spalten = el("div", { "class": "spalten" });
    reihenfolge.forEach(function (status) {
      var gruppe = (b.gruppen[status] || []).filter(function (t) {
        return (!boardFilter.sprint || String(t.sprint) === boardFilter.sprint) &&
               (!boardFilter.rolle || t.rolle === boardFilter.rolle) &&
               (!boardFilter.typ || String(t.typ || "") === boardFilter.typ);
      });
      if (!gruppe.length) return;
      var spalte = el("div", { "class": "spalte" },
        el("h3", {}, status + " (" + gruppe.length + ")"));
      gruppe.forEach(function (t) {
        spalte.appendChild(el("div", { "class": "karte klick", onclick: function () {
          gehe("ticket", projekt, t.id);
        } },
          el("div", { "class": "zeile" }, pille(t.id, t._status), String(t.titel).slice(0, 90)),
          el("div", { "class": "zeile" }, pille(t.rolle + " · S" + t.sprint + " · " + t.prio))));
      });
      spalten.appendChild(spalte);
    });
    zeige([filterzeile, spalten]);
  });
}

function ladeTicket() {  // SWR-040: Detailansicht
  return api("/api/ticket?projekt=" + encodeURIComponent(projekt) +
             "&id=" + encodeURIComponent(detailId)).then(function (t) {
    var kopf = el("div", { "class": "karte" },
      el("h3", {}, t.id + " — " + (t.titel || "")),
      el("div", { "class": "zeile" }, pille(t.status, t.status), pille(t.typ || "task"),
        pille(t.prozess || "-"), pille("Rolle " + (t.rolle || "-")),
        pille("Sprint " + (t.sprint || "-")), pille(t.prio || "-")));
    if (t.reviewer) kopf.appendChild(el("div", { "class": "zeile" }, "Reviewer: " + t.reviewer));
    if (t.frist) kopf.appendChild(el("div", { "class": "zeile" }, "Frist: " + t.frist +
      (t.default ? " · Default: " + t.default : "")));
    var bb = t.blocked_by;
    if (bb && bb.length && String(bb) !== "[]") {
      var z = el("div", { "class": "zeile" }, "Blockiert durch: ");
      tlinks(String(bb), projekt).forEach(function (k) { z.appendChild(k); });
      kopf.appendChild(z);
    }
    kopf.appendChild(el("button", { "class": "knopf", onclick: function () {
      gehe("board", projekt);
    } }, "Zurück zum Board"));
    zeige([kopf, el("div", { "class": "karte" }, preMitLinks(t.body, projekt))]);
  });
}

function drKarte(dr, entscheider) {  // SWR-042: Buttons statt Freitext, wo Optionen definiert sind
  var grund = el("textarea", { rows: "2", placeholder: "Begründung (optional)" });
  var wer = el("select", {});  // SWR-038
  entscheider.forEach(function (n) {
    wer.appendChild(el("option", { value: n.name }, "Entscheider: " + n.name));
  });
  var meldung = el("div", {});
  var karte = el("div", { "class": "karte" },
    el("h3", {}, "[" + dr.projekt + "] " + dr.id + " — " + dr.titel),
    el("div", { "class": "zeile" }, pille(dr.status, dr.status),
      pille(dr.prio + " · Sprint " + dr.sprint),
      dr.frist ? pille("Frist " + dr.frist + (dr.default ? " · Default " + dr.default : ""), "in_review") : el("span", {})),
    preMitLinks(dr.body, dr.projekt));

  function sende(option, ausloeser) {
    ausloeser.disabled = true;
    api("/api/inbox/" + dr.id + "/decision", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ option: option, begruendung: grund.value,
                             projekt: dr.projekt || "p0", entscheider: wer.value })
    }).then(function (e) {
      leeren(meldung);
      meldung.appendChild(el("div", { "class": "meldung ok" },
        "Angenommen als " + e.entscheidung + " durch " + e.entscheider +
        " (Mail: " + (e.mail ? "gesendet" : "nicht konfiguriert") + ")."));
    }).catch(function (fehler) {
      leeren(meldung);
      meldung.appendChild(el("div", { "class": "meldung fehler" }, String(fehler.message || fehler)));
      ausloeser.disabled = false;
    });
  }

  karte.appendChild(grund);
  karte.appendChild(wer);
  if (dr.optionen && dr.optionen.length) {
    var reihe = el("div", { "class": "btnreihe" });
    dr.optionen.forEach(function (o) {
      var b = el("button", { "class": "knopf" + (o === dr.default ? "" : " zweit") },
        o + (o === dr.default ? " (Default)" : ""));
      b.addEventListener("click", function () { sende(o, b); });
      reihe.appendChild(b);
    });
    karte.appendChild(reihe);
  } else {
    var opt = el("input", { placeholder: "Gewählte Option (Alt-DR ohne Optionen: Freitext)" });
    var knopf = el("button", { "class": "knopf" }, "Entscheiden");
    knopf.addEventListener("click", function () { sende(opt.value, knopf); });
    karte.appendChild(opt); karte.appendChild(knopf);
  }
  karte.appendChild(meldung);
  return karte;
}

function ladeInbox() {
  return Promise.all([api("/api/inbox"), api("/api/nutzer"), api("/api/inbox/historie")])
    .then(function (drei) {
      var offen = drei[0].inbox, historie = drei[2].historie;
      var entscheider = drei[1].nutzer.filter(function (n) { return n.rolle === "entscheider"; });
      var teile = [];
      if (!offen.length) teile.push(el("p", { "class": "leer" }, "Keine offenen Entscheidungen."));
      offen.forEach(function (dr) { teile.push(drKarte(dr, entscheider)); });
      if (historie.length) {
        var h = el("div", { "class": "karte" }, el("h3", {}, "Historie (" + historie.length + " entschieden)"));
        historie.forEach(function (e) {
          var z = el("div", { "class": "zeile" },
            el("a", { "class": "tlink", href: "#/ticket/" + e.projekt + "/" + e.id },
              "[" + e.projekt + "] " + e.id), " ", pille(e.status, e.status), " ");
          tlinks(e.entscheidung, e.projekt).forEach(function (k) { z.appendChild(k); });
          h.appendChild(z);
        });
        teile.push(h);
      }
      zeige(teile);
    });
}

function ladeReports() {
  return api("/api/reports?projekt=" + encodeURIComponent(projekt)).then(function (antwort) {
    zeige(antwort.reports.length ? antwort.reports.map(function (r) {
      return el("div", { "class": "karte" }, el("h3", {}, r.sprint), preMitLinks(r.text, projekt));
    }) : [el("p", { "class": "leer" }, "Noch keine Sprint-Reports.")]);
  });
}

function ladeKpi() {
  return api("/api/kpi?projekt=" + encodeURIComponent(projekt)).then(function (k) {
    var kacheln = el("div", { "class": "karte kpiraster" },
      el("div", { "class": "kpi" }, el("b", {}, String(k.laeufe)), "Läufe"),
      el("div", { "class": "kpi" }, el("b", {}, k.kosten_eur_gesamt.toFixed(2) + " €"), "Kosten gesamt"));
    Object.keys(k.laeufe_je_provider).forEach(function (p) {
      kacheln.appendChild(el("div", { "class": "kpi" }, el("b", {}, String(k.laeufe_je_provider[p])), p));
    });
    var detail = el("div", { "class": "karte" }, el("h3", {}, "Kosten je Monat"));
    Object.keys(k.kosten_eur_je_monat).forEach(function (m) {
      detail.appendChild(el("div", { "class": "zeile" }, m + ": " + k.kosten_eur_je_monat[m].toFixed(2) + " €"));
    });
    detail.appendChild(el("h3", {}, "Letzte Läufe"));
    detail.appendChild(el("pre", {}, JSON.stringify(k.letzte, null, 1)));
    zeige([kacheln, detail]);
  });
}

function dateiKarten(antwort, leerText) {
  return antwort.dateien.length ? antwort.dateien.map(function (d) {
    return el("div", { "class": "karte" }, el("h3", {}, d.datei), preMitLinks(d.text, projekt));
  }) : [el("p", { "class": "leer" }, leerText)];
}

function ladeRequirements() {  // SWR-030 (Tabellen: P3 Sprint 2, SWR-043)
  return api("/api/requirements?projekt=" + encodeURIComponent(projekt)).then(function (a) {
    zeige(dateiKarten(a, "Keine Requirements-Dokumente in diesem Projekt."));
  });
}

function ladeTrace() {  // SWR-031 (Tabellen: P3 Sprint 2, SWR-044)
  return api("/api/verifikation?projekt=" + encodeURIComponent(projekt)).then(function (a) {
    zeige(dateiKarten(a, "Keine Verifikationsreports in diesem Projekt."));
  });
}

function ladeBaselines() {  // SWR-032
  return api("/api/baselines").then(function (a) {
    zeige(a.repos.map(function (r) {
      var karte = el("div", { "class": "karte" }, el("h3", {}, r.repo));
      if (!r.tags.length) karte.appendChild(el("p", { "class": "leer" }, "Keine Baselines."));
      r.tags.forEach(function (t) { karte.appendChild(el("div", { "class": "zeile" }, t)); });
      return karte;
    }));
  });
}

function lade() {
  zeigeTabs();
  zeige([el("p", { "class": "leer" }, "Lade …")]);
  var ansichten = { uebersicht: ladeUebersicht, board: ladeBoard, inbox: ladeInbox,
                    ticket: ladeTicket, requirements: ladeRequirements, trace: ladeTrace,
                    baselines: ladeBaselines, reports: ladeReports, kpi: ladeKpi };
  (ansichten[aktiv] || ladeUebersicht)().catch(function (fehler) {
    zeige([el("div", { "class": "meldung fehler" }, "API nicht erreichbar: " + String(fehler.message || fehler))]);
  });
}

function pruefeVersion() {  // SWR-047: Prozess- vs. Code-Stand
  api("/api/version").then(function (v) {
    document.getElementById("stand").textContent = "Server " + v.prozess_stand;
    if (v.prozess_stand !== v.code_stand) {
      document.body.insertBefore(el("div", { "class": "banner" },
        "Neuer Code auf der Platte (" + v.code_stand + ") — der Server läuft noch auf " +
        v.prozess_stand + ". Bitte Server neu starten (Strg+C, dann neu ausführen) und die Seite hart neu laden."),
        document.body.firstChild);
    }
  }).catch(function () { /* Altserver ohne /api/version: kein Banner möglich */ });
}

projektEl.addEventListener("change", function () { gehe(aktiv === "ticket" ? "board" : aktiv, projektEl.value); });
api("/api/projekte").then(function (antwort) {
  leeren(projektEl);
  antwort.projekte.forEach(function (name) {
    projektEl.appendChild(el("option", { value: name }, name));
  });
  parseHash();
  if (antwort.projekte.indexOf(projekt) < 0 && antwort.projekte.length) projekt = antwort.projekte[0];
  projektEl.value = projekt;
  pruefeVersion();
  lade();
}).catch(function () { parseHash(); lade(); });
