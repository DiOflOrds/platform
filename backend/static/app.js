// FRT-PWA (T-0033, SWR-021; ADR-002): Ansichten + Inbox-Formular, reine API-Aufrufe.
// T-0040: abwärtskompatibel (kein replaceChildren, kein optional chaining) + sichtbare JS-Fehler.
// P1/T-0006 (SWR-026): Projektwahl + projektübergreifende Übersicht.
"use strict";
var TABS = [["uebersicht", "Übersicht"], ["board", "Board"], ["inbox", "Inbox"],
            ["requirements", "Requirements"], ["trace", "Traceability"],
            ["baselines", "Baselines"], ["reports", "Reports"], ["kpi", "Kosten/KPI"]];
var inhalt = document.getElementById("inhalt");
var tabsEl = document.getElementById("tabs");
var projektEl = document.getElementById("projekt");
var aktiv = location.hash.replace("#", "") || "uebersicht";
var projekt = "p0";

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

function zeigeTabs() {
  leeren(tabsEl);
  TABS.forEach(function (paar) {
    tabsEl.appendChild(el("button", {
      "class": paar[0] === aktiv ? "aktiv" : "",
      onclick: function () { aktiv = paar[0]; location.hash = paar[0]; lade(); }
    }, paar[1]));
  });
}

function zeige(elemente) {
  leeren(inhalt);
  elemente.forEach(function (e) { inhalt.appendChild(e); });
}

function ladeUebersicht() {
  return api("/api/uebersicht").then(function (u) {
    document.getElementById("stand").textContent = u.projekte.length + " Projekt(e)";
    zeige(u.projekte.map(function (p) {
      var karte = el("div", { "class": "karte" },
        el("h3", {}, p.projekt),
        el("div", { "class": "zeile" },
          el("span", { "class": "pille open" }, p.tickets_offen + " offen"),
          el("span", { "class": "pille" }, p.tickets_gesamt + " gesamt")));
      if (p.offene_drs.length) {
        karte.appendChild(el("div", { "class": "zeile" }, "Offene Entscheidungen:"));
        p.offene_drs.forEach(function (dr) {
          karte.appendChild(el("div", { "class": "zeile" },
            el("span", { "class": "pille in_review" }, dr.id), " " + dr.titel));
        });
      }
      karte.appendChild(el("button", { "class": "knopf", onclick: function () {
        projekt = p.projekt; projektEl.value = projekt; aktiv = "board";
        location.hash = "board"; lade();
      } }, "Zum Board"));
      return karte;
    }));
  });
}

function ladeBoard() {
  return api("/api/board?projekt=" + encodeURIComponent(projekt)).then(function (b) {
    document.getElementById("stand").textContent = b.anzahl + " Tickets";
    var reihenfolge = ["open", "in_analysis", "in_progress", "in_review", "blocked", "done", "rejected"];
    var karten = [];
    reihenfolge.forEach(function (status) {
      var gruppe = b.gruppen[status];
      if (!gruppe || !gruppe.length) return;
      var karte = el("div", { "class": "karte" }, el("h3", {}, status + " (" + gruppe.length + ")"));
      gruppe.forEach(function (t) {
        karte.appendChild(el("div", { "class": "zeile" },
          el("span", { "class": "pille " + status }, t.id), " " + t.titel + " ",
          el("span", { "class": "pille" }, t.rolle + " · S" + t.sprint + " · " + t.prio)));
      });
      karten.push(karte);
    });
    zeige(karten);
  });
}

function ladeInbox() {
  return Promise.all([api("/api/inbox"), api("/api/nutzer")]).then(function (beide) {
    var antwort = beide[0];
    var entscheider = beide[1].nutzer.filter(function (n) { return n.rolle === "entscheider"; });
    if (!antwort.inbox.length) {
      zeige([el("p", { "class": "leer" }, "Keine offenen Entscheidungen.")]);
      return;
    }
    zeige(antwort.inbox.map(function (dr) {
      var opt = el("input", { placeholder: "Gewählte Option (z. B. A1 — oder Freitext)" });
      var grund = el("textarea", { rows: "2", placeholder: "Begründung (optional)" });
      var wer = el("select", {});  // SWR-038: Entscheider-Auswahl
      entscheider.forEach(function (n) {
        wer.appendChild(el("option", { value: n.name }, "Entscheider: " + n.name));
      });
      var knopf = el("button", { "class": "knopf" }, "Entscheiden");
      var meldung = el("div", {});
      knopf.addEventListener("click", function () {
        knopf.disabled = true;
        api("/api/inbox/" + dr.id + "/decision", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ option: opt.value, begruendung: grund.value,
                                 projekt: dr.projekt || "p0",
                                 entscheider: wer.value })
        }).then(function (e) {
          leeren(meldung);
          meldung.appendChild(el("div", { "class": "meldung ok" },
            "Angenommen als " + e.entscheidung + " (Mail: " + (e.mail ? "gesendet" : "nicht konfiguriert") + ")."));
        }).catch(function (fehler) {
          leeren(meldung);
          meldung.appendChild(el("div", { "class": "meldung fehler" }, String(fehler.message || fehler)));
          knopf.disabled = false;
        });
      });
      return el("div", { "class": "karte" },
        el("h3", {}, "[" + (dr.projekt || "p0") + "] " + dr.id + " — " + dr.titel),
        el("div", { "class": "zeile" }, el("span", { "class": "pille " + dr.status }, dr.status),
          el("span", { "class": "pille" }, dr.prio + " · Sprint " + dr.sprint)),
        el("pre", {}, dr.body), opt, grund, wer, knopf, meldung);
    }));
  });
}

function ladeReports() {
  return api("/api/reports?projekt=" + encodeURIComponent(projekt)).then(function (antwort) {
    zeige(antwort.reports.length ? antwort.reports.map(function (r) {
      return el("div", { "class": "karte" }, el("h3", {}, r.sprint), el("pre", {}, r.text));
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
    return el("div", { "class": "karte" }, el("h3", {}, d.datei), el("pre", {}, d.text));
  }) : [el("p", { "class": "leer" }, leerText)];
}

function ladeRequirements() {  // SWR-030
  return api("/api/requirements?projekt=" + encodeURIComponent(projekt)).then(function (a) {
    zeige(dateiKarten(a, "Keine Requirements-Dokumente in diesem Projekt."));
  });
}

function ladeTrace() {  // SWR-031
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
                    requirements: ladeRequirements, trace: ladeTrace,
                    baselines: ladeBaselines, reports: ladeReports, kpi: ladeKpi };
  (ansichten[aktiv] || ladeUebersicht)().catch(function (fehler) {
    zeige([el("div", { "class": "meldung fehler" }, "API nicht erreichbar: " + String(fehler.message || fehler))]);
  });
}

projektEl.addEventListener("change", function () { projekt = projektEl.value; lade(); });
api("/api/projekte").then(function (antwort) {
  leeren(projektEl);
  antwort.projekte.forEach(function (name) {
    projektEl.appendChild(el("option", { value: name }, name));
  });
  if (antwort.projekte.indexOf(projekt) < 0 && antwort.projekte.length) projekt = antwort.projekte[0];
  projektEl.value = projekt;
  lade();
}).catch(function () { lade(); });
