// FRT-PWA (T-0033, SWR-021; ADR-002): Ansichten + Inbox, reine API-Aufrufe.
// T-0040: abwärtskompatibel (kein replaceChildren, kein optional chaining) + sichtbare JS-Fehler.
// P1/T-0006 (SWR-026): Projektwahl + projektübergreifende Übersicht.
// P3 Sprint 1 (ADR-005): Hash-Router #/<tab>/<projekt>[/<id>], Ticket-Detail (SWR-040),
// Jira-Board mit Filtern (SWR-041), Inbox-Buttons + Historie (SWR-042), Versions-Banner (SWR-047).
"use strict";
// P7 (SWR-054): Tab "Team" — Digest-Verlauf, Steckbrief, Konfigurator.
var TABS = [["uebersicht", "Cockpit"], ["board", "Board"], ["inbox", "Inbox"],
            ["chat", "Team-Chat"], ["team", "Team"], ["requirements", "Requirements"],
            ["trace", "Traceability"], ["architektur", "Architektur"], ["baselines", "Baselines"],
            ["reports", "Reports"], ["kpi", "Kosten/KPI"]];
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

var pinEl = document.getElementById("pin");
try { pinEl.value = sessionStorage.getItem("mc_pin") || ""; } catch (e) { /* privat-modus */ }
pinEl.addEventListener("change", function () {
  try { sessionStorage.setItem("mc_pin", pinEl.value); } catch (e) { /* ok */ }
});

function api(pfad, optionen) {
  optionen = optionen || {};
  if (pinEl.value) {  // SWR-049 + SWR-053 (P7): PIN auch für geschützte Lese-Endpunkte
    optionen.headers = optionen.headers || {};
    optionen.headers["X-MC-PIN"] = pinEl.value;
  }
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
var AMPEL_KLASSE = { rot: "rejected", gelb: "in_progress", gruen: "done", grau: "" };

function cockpitKarte(p) {  // SWR-046 + P9 SWR-067/068
      var fertig = (p.status_zahlen.done || 0) + (p.status_zahlen.rejected || 0);
      var karte = el("div", { "class": "karte" },
        el("h3", {}, p.projekt),
        el("div", { "class": "zeile" },
          pille(p.status === "abgeschlossen" ? "abgeschlossen" : (p.status || "aktiv"),
                p.status === "abgeschlossen" ? "done" : "open"),
          pille(fertig + "/" + p.tickets_gesamt + " fertig", "done")));
      if (p.beschreibung) {  // SWR-066/069: nie wieder raten, was "p3" war
        karte.appendChild(el("div", { "class": "zeile leer" }, p.beschreibung));
      }
      if (p.aufgaben && p.aufgaben.length) {  // SWR-068: laufende Aufgaben
        var az = el("div", { "class": "zeile" }, "Offen (" + p.aufgaben_offen + "): ");
        p.aufgaben.forEach(function (a) {
          az.appendChild(el("a", { "class": "tlink", href: "#/ticket/" + p.projekt + "/" + a.id,
                                   title: a.titel }, a.id));
          az.appendChild(document.createTextNode(" "));
        });
        karte.appendChild(az);
      }
      var statusZeile = el("div", { "class": "zeile" });
      Object.keys(p.status_zahlen).sort().forEach(function (s) {
        statusZeile.appendChild(pille(s + " " + p.status_zahlen[s], s));
      });
      karte.appendChild(statusZeile);
      if (p.offene_drs.length) {
        karte.appendChild(el("div", { "class": "zeile" }, "Offene Entscheidungen:"));
        p.offene_drs.forEach(function (dr) {
          karte.appendChild(el("div", { "class": "zeile" },
            pille(dr.ampel === "grau" ? "ohne Frist" : "Frist " + dr.frist, AMPEL_KLASSE[dr.ampel]),
            el("a", { "class": "tlink", href: "#/inbox/" + p.projekt }, dr.id), " " + dr.titel));
        });
      }
      if (p.briefe_offen) {  // SWR-051: unbeantwortete Briefe sichtbar
        karte.appendChild(el("div", { "class": "zeile" },
          pille(p.briefe_offen + " Brief(e) offen", "in_progress"),
          el("a", { "class": "tlink", href: "#/chat/" + p.projekt }, "zum Team-Chat")));
      }
      if (p.team) {  // SWR-055 (P7): Team-Kachel mit letztem Digest
        karte.appendChild(el("div", { "class": "zeile" },
          pille(p.team.letzter_digest ? "Digest " + p.team.letzter_digest : "noch kein Digest", "in_review"),
          el("a", { "class": "tlink", href: "#/team/" + p.projekt }, "zum Team")));
      }
      if (p.letzte_baseline) {
        karte.appendChild(el("div", { "class": "zeile" }, "Letzte Baseline: " + p.letzte_baseline));
      }
      karte.appendChild(el("div", { "class": "zeile" },
        pille(p.kpi.laeufe + " Läufe"), pille(p.kpi.kosten_eur.toFixed(2) + " € API")));
      karte.appendChild(el("button", { "class": "knopf", onclick: function () {
        gehe("board", p.projekt);
      } }, "Zum Board"));
      return karte;
}

function ladeUebersicht() {  // SWR-046 + P9 SWR-067: Org-Cockpit mit Gruppen
  return api("/api/cockpit").then(function (u) {
    document.getElementById("stand").textContent = u.projekte.length + " Projekt(e)";
    var gruppen = { "festes-team": [], "projekt-team": [], "aktiv": [], "abgeschlossen": [] };
    u.projekte.forEach(function (p) {
      (gruppen[p.gruppe || "aktiv"] || gruppen.aktiv).push(p);
    });
    var teile = [];
    [["festes-team", "Feste Teams"], ["projekt-team", "Projekt-Teams"],
     ["aktiv", "Aktive Projekte"]].forEach(function (g) {
      if (!gruppen[g[0]].length) return;
      teile.push(el("h3", {}, g[1] + " (" + gruppen[g[0]].length + ")"));
      gruppen[g[0]].forEach(function (p) { teile.push(cockpitKarte(p)); });
    });
    if (gruppen.abgeschlossen.length) {  // SWR-067: eingeklappt
      var container = el("div", { style: "display:none" });
      gruppen.abgeschlossen.forEach(function (p) { container.appendChild(cockpitKarte(p)); });
      var knopf = el("button", { "class": "knopf zweit", onclick: function () {
        var zu = container.style.display === "none";
        container.style.display = zu ? "" : "none";
        knopf.textContent = (zu ? "Ausblenden: " : "Anzeigen: ") + "abgeschlossene Projekte (" +
          gruppen.abgeschlossen.length + ")";
      } }, "Anzeigen: abgeschlossene Projekte (" + gruppen.abgeschlossen.length + ")");
      teile.push(el("h3", {}, "Abgeschlossen"));
      teile.push(el("div", { "class": "btnreihe" }, knopf));
      teile.push(container);
    }
    zeige(teile);
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

function ladeChat() {  // SWR-050/051 (P4): Briefkasten-Konversation mit dem Team
  return Promise.all([api("/api/briefkasten?projekt=" + encodeURIComponent(projekt)),
                      api("/api/nutzer")]).then(function (beide) {
    var briefe = beide[0].briefe;
    var teile = [el("div", { "class": "karte" },
      el("h3", {}, "Team-Chat (" + projekt + ") — Briefkasten"),
      el("p", { "class": "leer" }, "Nachrichten landen versioniert im Repo; die nächste " +
        "Cowork-Session antwortet in denselben Verlauf (asynchron, 0 €)."))];
    if (!briefe.length) teile.push(el("p", { "class": "leer" }, "Noch keine Nachrichten."));
    briefe.forEach(function (b) {
      var karte = el("div", { "class": "karte brief" + (b.status === "beantwortet" ? " beantwortet" : "") },
        el("div", { "class": "zeile" }, pille(b.id), pille(b.status, b.status === "offen" ? "in_progress" : "done"),
          b.von + " · " + b.zeit),
        preMitLinks(b.nachricht, projekt));
      if (b.antwort) {
        var a = el("div", { "class": "antwort" },
          el("div", { "class": "zeile" }, pille("Team", "done"), b.antwort_datum));
        a.appendChild(preMitLinks(b.antwort, projekt));
        karte.appendChild(a);
      }
      teile.push(karte);
    });
    var text = el("textarea", { rows: "3", placeholder: "Nachricht ans Team …" });
    var wer = el("select", {});
    beide[1].nutzer.forEach(function (n) {
      wer.appendChild(el("option", { value: n.name }, "Von: " + n.name));
    });
    var meldung = el("div", {});
    var knopf = el("button", { "class": "knopf" }, "Absenden");
    knopf.addEventListener("click", function () {
      knopf.disabled = true;
      api("/api/briefkasten", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ projekt: projekt, text: text.value, von: wer.value })
      }).then(function (e) {
        leeren(meldung);
        meldung.appendChild(el("div", { "class": "meldung ok" },
          "Gesendet als " + e.brief + " — die nächste Session antwortet hier."));
        text.value = ""; knopf.disabled = false;
        setTimeout(lade, 900);
      }).catch(function (fehler) {
        leeren(meldung);
        meldung.appendChild(el("div", { "class": "meldung fehler" }, String(fehler.message || fehler)));
        knopf.disabled = false;
      });
    });
    teile.push(el("div", { "class": "karte" }, text, wer, knopf, meldung));
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

function tabelle(t) {  // SWR-043/044: sortier- und filterbare Tabelle
  var sortSpalte = -1, sortAuf = true;
  var filter = el("input", { placeholder: "Filtern …", oninput: function () { baue(); } });
  var wrap = el("div", { "class": "tabellenwrap" });
  function zelleMitLinks(td, text) {
    tlinks(String(text).replace(/\*\*/g, ""), projekt).forEach(function (k) { td.appendChild(k); });
    return td;
  }
  function baue() {
    leeren(wrap);
    var tab = el("table", { "class": "tabelle" });
    var kopf = el("tr", {});
    t.spalten.forEach(function (s, i) {
      kopf.appendChild(el("th", { onclick: function () {
        if (sortSpalte === i) sortAuf = !sortAuf; else { sortSpalte = i; sortAuf = true; }
        baue();
      } }, s.replace(/\*\*/g, "") + (sortSpalte === i ? (sortAuf ? " ▲" : " ▼") : "")));
    });
    tab.appendChild(kopf);
    var zeilen = t.zeilen.filter(function (z) {
      var wort = filter.value.toLowerCase();
      return !wort || z.join(" ").toLowerCase().indexOf(wort) >= 0;
    });
    if (sortSpalte >= 0) zeilen = zeilen.slice().sort(function (a, b) {
      var x = String(a[sortSpalte] || ""), y = String(b[sortSpalte] || "");
      return (x < y ? -1 : x > y ? 1 : 0) * (sortAuf ? 1 : -1);
    });
    zeilen.forEach(function (z) {
      var tr = el("tr", {});
      z.forEach(function (zelle) { tr.appendChild(zelleMitLinks(el("td", {}), zelle)); });
      tab.appendChild(tr);
    });
    wrap.appendChild(tab);
  }
  baue();
  return el("div", {}, filter, wrap);
}

function dateiKarten(antwort, leerText) {
  return antwort.dateien.length ? antwort.dateien.map(function (d) {
    var karte = el("div", { "class": "karte" }, el("h3", {}, d.datei));
    if (d.tabellen && d.tabellen.length) {
      d.tabellen.forEach(function (t) { karte.appendChild(tabelle(t)); });
    } else {
      karte.appendChild(preMitLinks(d.text, projekt));
    }
    return karte;
  }) : [el("p", { "class": "leer" }, leerText)];
}

function ladeRequirements() {  // SWR-030 + SWR-043 (Tabellen)
  return api("/api/requirements?projekt=" + encodeURIComponent(projekt)).then(function (a) {
    zeige(dateiKarten(a, "Keine Requirements-Dokumente in diesem Projekt."));
  });
}

function ladeTrace() {  // SWR-031 + SWR-044 (Matrix als Tabelle)
  return api("/api/verifikation?projekt=" + encodeURIComponent(projekt)).then(function (a) {
    zeige(dateiKarten(a, "Keine Verifikationsreports in diesem Projekt."));
  });
}

function ladeArchitektur() {  // SWR-045: generiertes Bild aus komponenten.yaml
  var karte = el("div", { "class": "karte" },
    el("h3", {}, "Software-Architektur (generiert aus platform/architecture/komponenten.yaml)"),
    el("img", { src: "/architektur.svg", alt: "Architekturdiagramm", style: "width:100%;height:auto" }),
    el("p", { "class": "leer" }, "Änderungen an der YAML-Quelle ändern dieses Bild (arch_diagramm.py, Drift-Check im abschluss-Gate)."));
  zeige([karte]);
  return Promise.resolve();
}

// P7 SWR-059: kleiner Markdown-Renderer (DOM-basiert, keine Bibliothek — ADR-002).
// Unterstützt: #..#### Überschriften, Absätze, **fett**, *kursiv*, `code`,
// nummerierte/ungeordnete Listen, Pipe-Tabellen, --- Trennlinien.
function mdInline(text, ziel) {
  var rest = String(text || ""), m;
  // SWR-060 (Betriebs-CR aus team-mail/N-0001): [text](https://...) als Link.
  var muster = /(\[([^\]]*)\]\(([^)\s]+)\)|\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`)/;
  while ((m = rest.match(muster))) {
    if (m.index > 0) ziel.appendChild(document.createTextNode(rest.slice(0, m.index)));
    if (m[2] !== undefined) {
      if (m[3].indexOf("http") === 0) {  // nur http/https, neuer Tab (SWR-060)
        ziel.appendChild(el("a", { "class": "tlink", href: m[3], target: "_blank",
                                   rel: "noopener" }, m[2] || m[3]));
      } else ziel.appendChild(document.createTextNode(m[2]));
    }
    else if (m[4] !== undefined) ziel.appendChild(el("strong", {}, m[4]));
    else if (m[5] !== undefined) ziel.appendChild(el("em", {}, m[5]));
    else ziel.appendChild(el("code", {}, m[6]));
    rest = rest.slice(m.index + m[1].length);
  }
  if (rest) ziel.appendChild(document.createTextNode(rest));
}

function mdRender(text) {
  var wurzel = el("div", { "class": "md" });
  var zeilen = String(text || "").split("\n");
  var i = 0, liste = null;
  while (i < zeilen.length) {
    var strip = zeilen[i].trim();
    if (!strip) { i++; liste = null; continue; }
    var h = strip.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      var hEl = el("h" + Math.min(h[1].length + 1, 5), {});
      mdInline(h[2], hEl); wurzel.appendChild(hEl); i++; liste = null; continue;
    }
    if (strip.charAt(0) === "|") {  // Tabellenblock
      var tab = el("table", { "class": "tabelle" }), kopfzeile = true;
      while (i < zeilen.length && zeilen[i].trim().charAt(0) === "|") {
        var tz = zeilen[i].trim();
        i++;
        if (/^[|\s:-]+$/.test(tz)) continue;  // Trennzeile
        var tr = el("tr", {});
        tz.replace(/^\||\|$/g, "").split("|").forEach(function (zelle) {
          var td = el(kopfzeile ? "th" : "td", {});
          mdInline(zelle.trim(), td); tr.appendChild(td);
        });
        tab.appendChild(tr); kopfzeile = false;
      }
      wurzel.appendChild(el("div", { "class": "tabellenwrap" }, tab)); liste = null; continue;
    }
    var li = strip.match(/^([-*]|\d+\.)\s+(.*)$/);
    if (li) {
      var typ = /^\d/.test(li[1]) ? "ol" : "ul";
      if (!liste || liste.tagName.toLowerCase() !== typ) {
        liste = el(typ, {}); wurzel.appendChild(liste);
      }
      var punkt = el("li", {}), puffer = [li[2]];
      i++;  // Folgezeilen ohne eigenes Muster gehören zum Punkt (Umbruch im Editor)
      while (i < zeilen.length) {
        var f = zeilen[i].trim();
        if (!f || /^(#{1,4}\s|\||[-*]\s|\d+\.\s|---)/.test(f)) break;
        puffer.push(f); i++;
      }
      mdInline(puffer.join(" "), punkt); liste.appendChild(punkt); continue;
    }
    if (/^---+$/.test(strip)) { wurzel.appendChild(el("hr", {})); i++; liste = null; continue; }
    var p = el("p", {}), absatz = [strip];
    i++;
    while (i < zeilen.length) {
      var w = zeilen[i].trim();
      if (!w || /^(#{1,4}\s|\||[-*]\s|\d+\.\s|---)/.test(w)) break;
      absatz.push(w); i++;
    }
    mdInline(absatz.join(" "), p); wurzel.appendChild(p); liste = null;
  }
  return wurzel;
}

function ladeTeam() {  // P7 SWR-054/057: Team-Tab — Digest-Verlauf, Steckbrief, Konfigurator
  return api("/api/team?projekt=" + encodeURIComponent(projekt)).then(function (t) {
    var s = t.steckbrief;
    if (detailId) {  // Digest-Detail (Name steht im Hash)
      return api("/api/team/digest?projekt=" + encodeURIComponent(projekt) +
                 "&name=" + encodeURIComponent(detailId)).then(function (d) {
        zeige([el("div", { "class": "karte" },
          el("div", { "class": "btnreihe" },
            el("button", { "class": "knopf zweit", onclick: function () { gehe("team", projekt); } },
              "← Zurück zum Team")),
          mdRender(d.inhalt))]);  // SWR-059: formatiert statt Rohtext
      });
    }
    var kopf = el("div", { "class": "karte" }, el("h3", {}, s.name || t.projekt));
    var pillen = el("div", { "class": "zeile" },
      pille("Profil: " + (s.profil || "?"), "in_review"),
      pille("Datenklasse: " + s.datenklasse, s.datenklasse === "sensibel" ? "rejected" : "done"));
    (s.rollen || []).forEach(function (r) { pillen.appendChild(pille(r, "open")); });
    kopf.appendChild(pillen);
    (s.sla || []).forEach(function (z) {
      kopf.appendChild(el("div", { "class": "zeile" }, "SLA: " + z));
    });
    if (s.gegruendet) kopf.appendChild(el("div", { "class": "zeile leer" }, "Gegründet: " + s.gegruendet));

    var digestKarte = el("div", { "class": "karte" }, el("h3", {}, "Digests (" + t.digests.length + ")"));
    var jetztMeldung = el("div", {});
    var jetztKnopf = el("button", { "class": "knopf", onclick: function () {  // SWR-063 (P8)
      jetztKnopf.disabled = true;
      leeren(jetztMeldung);
      jetztMeldung.appendChild(el("div", { "class": "meldung" }, "Läuft — holen, verdichten (Ollama), ggf. senden … das kann eine Minute dauern."));
      api("/api/team/digest-jetzt", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ projekt: projekt })
      }).then(function (r) {
        jetztKnopf.disabled = false;
        leeren(jetztMeldung);
        jetztMeldung.appendChild(el("div", { "class": "meldung ok" }, r.meldung));
        lade();
      }).catch(function (f) {
        jetztKnopf.disabled = false;
        leeren(jetztMeldung);
        jetztMeldung.appendChild(el("div", { "class": "meldung fehler" }, String(f.message || f)));
      });
    } }, "Jetzt zusammenfassen (Ollama)");
    digestKarte.appendChild(el("div", { "class": "btnreihe" }, jetztKnopf));
    digestKarte.appendChild(jetztMeldung);
    if (!t.digests.length) digestKarte.appendChild(el("p", { "class": "leer" }, "Noch kein Digest."));
    t.digests.forEach(function (d) {
      digestKarte.appendChild(el("div", { "class": "karte klick brief", onclick: function () {
        gehe("team", projekt, d.name);
      } }, el("div", { "class": "zeile" }, pille(d.datum, "done"), " " + d.titel)));
    });

    var k = t.konfiguration;
    var konfigKarte = el("div", { "class": "karte" }, el("h3", {}, "Konfiguration"));
    if (!k.vorhanden) {
      konfigKarte.appendChild(el("p", { "class": "leer" }, "Dieses Team hat keine konfiguration.yaml."));
    } else {
      var taktBoxen = [];  // SWR-064 (P8): Tag/Woche/Monat gleichzeitig
      var taktZeile = el("div", { "class": "zeile" }, "Takte: ");
      [[1, "Täglich"], [7, "Wöchentlich"], [30, "Monatlich"]].forEach(function (paar) {
        var box = el("input", { type: "checkbox", style: "width:auto;margin:0" });
        box.checked = (k.takte || [k.zeitraum_tage]).indexOf(paar[0]) >= 0;
        box._tage = paar[0];
        taktBoxen.push(box);
        taktZeile.appendChild(el("label", { style: "display:flex;gap:.3rem;align-items:center" }, box, " " + paar[1]));
      });
      var rechnungenBox = el("input", { type: "checkbox", style: "width:auto;margin:0" });
      rechnungenBox.checked = !!k.abschnitt_rechnungen;
      var mailBox = el("input", { type: "checkbox", style: "width:auto;margin:0" });
      mailBox.checked = !!k.zustellung_mail;
      // SWR-071 (P8-E4): Modellwahl — Liste live vom lokalen Ollama, "automatisch" bleibt möglich
      var modellWahl = el("select", { style: "width:auto" });
      var modellHinweis = el("span", { "class": "leer" }, "");
      function modellOptionen(namen, gewaehlt) {
        leeren(modellWahl);
        modellWahl.appendChild(el("option", { value: "" }, "automatisch (erstes installiertes)"));
        var kennt = false;
        (namen || []).forEach(function (n) {
          if (n === gewaehlt) kennt = true;
          modellWahl.appendChild(el("option", { value: n }, n));
        });
        if (gewaehlt && !kennt) modellWahl.appendChild(el("option", { value: gewaehlt }, gewaehlt + " (konfiguriert, nicht installiert)"));
        modellWahl.value = gewaehlt || "";
      }
      modellOptionen([], k.ollama_modell || "");
      api("/api/team/ollama-modelle?projekt=" + encodeURIComponent(projekt)).then(function (m) {
        modellOptionen(m.modelle, k.ollama_modell || "");
        modellHinweis.textContent = m.hinweis || ("aktiv: " + (m.aktiv || "—") + (m.automatisch ? " (automatisch)" : ""));
      }).catch(function (f) {
        modellHinweis.textContent = "Modellliste nicht abrufbar: " + String(f.message || f);
      });
      // SWR-072 (P8-E4): freier Zusatz-Auftrag an die KI
      var hinweisFeld = el("input", { type: "text", maxlength: "200",
        placeholder: "z. B. achte auf Bewerbungen — eigene Kategorie anlegen" });
      hinweisFeld.value = k.ki_hinweis || "";
      var meldung = el("div", {});
      var speichern = el("button", { "class": "knopf", onclick: function () {
        speichern.disabled = true;
        leeren(meldung);
        var takte = [];
        taktBoxen.forEach(function (b) { if (b.checked) takte.push(b._tage); });
        api("/api/team/konfiguration", { method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ projekt: projekt, takte: takte,
            abschnitt_rechnungen: rechnungenBox.checked,
            zustellung_mail: mailBox.checked,
            ollama_modell: modellWahl.value,   // SWR-071
            ki_hinweis: hinweisFeld.value })   // SWR-072
        }).then(function () {
          speichern.disabled = false;
          meldung.appendChild(el("div", { "class": "meldung ok" },
            "Gespeichert und committet — gilt ab dem nächsten Digest-Lauf."));
        }).catch(function (fehler) {
          speichern.disabled = false;
          meldung.appendChild(el("div", { "class": "meldung fehler" }, String(fehler.message || fehler)));
        });
      } }, "Speichern (PIN bei Netzwerk-Zugriff)");
      konfigKarte.appendChild(taktZeile);
      konfigKarte.appendChild(el("label", { "class": "zeile" }, rechnungenBox, " Rechnungs-Abschnitt im Digest"));
      konfigKarte.appendChild(el("label", { "class": "zeile" }, mailBox, " Digest zusätzlich per Mail (SWR-058)"));
      konfigKarte.appendChild(el("div", { "class": "zeile" }, "KI-Modell: ", modellWahl, " ", modellHinweis));
      konfigKarte.appendChild(el("div", { "class": "zeile" }, "KI-Hinweis: ", hinweisFeld));
      var konten = el("div", { "class": "zeile" }, "Konten (Klasse A — Änderung per Brief/Session): ");
      (k.konten || []).forEach(function (konto) { konten.appendChild(pille(konto.name, "open")); });
      konfigKarte.appendChild(konten);
      konfigKarte.appendChild(el("div", { "class": "btnreihe" }, speichern));
      konfigKarte.appendChild(meldung);
    }

    var chartaKarte = el("div", { "class": "karte" }, el("h3", {}, "Charter"),
      t.charta ? mdRender(t.charta) : el("p", { "class": "leer" }, "Keine Charter-Datei."));  // SWR-059
    zeige([kopf, digestKarte, konfigKarte, chartaKarte]);
  }).catch(function (fehler) {
    var text = String(fehler.message || fehler);
    if (text.indexOf("kein Team-Projekt") >= 0) {
      zeige([el("div", { "class": "karte" }, el("h3", {}, "Kein Team-Projekt"),
        el("p", { "class": "leer" }, projekt + " ist ein Projekt-Repo ohne team.yaml — " +
          "Team-Ansichten gibt es für Teams aus der Registry (z. B. team-mail, pm)."))]);
      return;
    }
    throw fehler;
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
                    chat: ladeChat, team: ladeTeam, ticket: ladeTicket,
                    requirements: ladeRequirements, trace: ladeTrace,
                    architektur: ladeArchitektur, baselines: ladeBaselines,
                    reports: ladeReports, kpi: ladeKpi };
  (ansichten[aktiv] || ladeUebersicht)().catch(function (fehler) {
    zeige([el("div", { "class": "meldung fehler" }, "API nicht erreichbar: " + String(fehler.message || fehler))]);
  });
}

function serverNeustart() {  // SWR-061 (pm/N-0002): Neustart per Knopfdruck
  if (!window.confirm("Mission-Control-Server jetzt neu starten?")) return;
  api("/api/neustart", { method: "POST" }).then(function (r) {
    zeige([el("div", { "class": "meldung ok" }, r.meldung + " (Seite lädt in 3 Sekunden neu.)")]);
    setTimeout(function () { location.reload(); }, 3000);
  }).catch(function (f) {
    zeige([el("div", { "class": "meldung fehler" }, String(f.message || f))]);
  });
}
var neustartKnopf = document.getElementById("neustart");
if (neustartKnopf) neustartKnopf.addEventListener("click", serverNeustart);

function pruefeVersion() {  // SWR-047: Prozess- vs. Code-Stand
  api("/api/version").then(function (v) {
    document.getElementById("stand").textContent = "Server " + v.prozess_stand;
    if (v.prozess_stand !== v.code_stand) {
      document.body.insertBefore(el("div", { "class": "banner" },
        "Neuer Code auf der Platte (" + v.code_stand + ") — der Server läuft noch auf " +
        v.prozess_stand + ". ",
        el("button", { "class": "knopf", style: "margin-left:.4rem;padding:.3rem .8rem",
                       onclick: serverNeustart }, "Jetzt neu starten")),
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
