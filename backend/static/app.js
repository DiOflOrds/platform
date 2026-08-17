// FRT-PWA (T-0033, SWR-021; ADR-002): Ansichten + Inbox, reine API-Aufrufe.
// T-0040: abwärtskompatibel (kein replaceChildren, kein optional chaining) + sichtbare JS-Fehler.
// P1/T-0006 (SWR-026): Projektwahl + projektübergreifende Übersicht.
// P3 Sprint 1 (ADR-005): Hash-Router #/<tab>/<projekt>[/<id>], Ticket-Detail (SWR-040),
// Jira-Board mit Filtern (SWR-041), Inbox-Buttons + Historie (SWR-042), Versions-Banner (SWR-047).
"use strict";
// P7 (SWR-054): Tab "Team" — Digest-Verlauf, Steckbrief, Konfigurator.
// SWR-086 (pm/N-0020): "Projekt-Pool" als eigener Backlog-Reiter neben dem Cockpit.
var TABS = [["uebersicht", "Cockpit"], ["pool", "Projekt-Pool"], ["board", "Board"], ["inbox", "Inbox"],
            ["chat", "Team-Chat"], ["team", "Team"], ["requirements", "Requirements"],
            ["trace", "Traceability"], ["architektur", "Architektur"], ["baselines", "Baselines"],
            ["reports", "Reports"], ["kpi", "Kosten/KPI"]];
var inhalt = document.getElementById("inhalt");
var tabsEl = document.getElementById("tabs");
var projektEl = document.getElementById("projektwahl");
var aktiv = "uebersicht";
var projekt = "p0";
var detailId = "";
var boardFilter = { sprint: "", rolle: "", typ: "", label: "" };  // SWR-079 (P10): Label-Filter
var editorOffen = false;  // SWR-077 (P10): Ticket-Detail zeigt Formular statt Ansicht

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
  if (teile[1]) { projekt = teile[1]; }
  // SWR-077 (P10): Der Editor gehört zu genau einem Ticket — wer wegnavigiert oder
  // ein anderes Ticket öffnet, bekommt wieder die Ansicht (kein Formular mit
  // Werten des Vorgängers, kein versehentliches Speichern am falschen Ticket).
  if (aktiv !== "ticket" || (teile[2] || "") !== detailId) editorOffen = false;
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

var offeneDrs = null;  // SWR-076 (pm/N-0016): Anzahl wartender Entscheidungen, null = ungeprüft
function zeigeTabs() {
  leeren(tabsEl);
  TABS.forEach(function (paar) {
    // SWR-076: Die Inbox trägt die Zahl der auf dich wartenden Entscheidungen im Reiter
    var text = paar[1];
    if (paar[0] === "inbox" && offeneDrs) text = paar[1] + " (" + offeneDrs + ")";
    tabsEl.appendChild(el("button", {
      "class": (paar[0] === aktiv ? "aktiv" : "") +
               (paar[0] === "inbox" && offeneDrs ? " wartet" : ""),
      title: paar[0] === "inbox" && offeneDrs
        ? offeneDrs + " Entscheidung(en) warten auf dich" : "",
      onclick: function () { gehe(paar[0], projekt); }
    }, text));
  });
}

// SWR-082 (pm/N-0015, T-0012): Kopfbereich zeigt genau das, was auch im Cockpit steht.
// Die Gruppen kommen fertig vom Server (aggregation.navigation) — Kopf und Cockpit
// können damit nicht auseinanderlaufen. Abgeschlossenes bleibt erreichbar, aber weg.
var navDaten = null;
var navWeitereOffen = false;

function projektKnopf(e) {
  return el("button", {
    "class": e.projekt === projekt ? "aktiv" : "",
    title: e.beschreibung || e.projekt,
    onclick: function () { gehe(aktiv === "ticket" ? "board" : aktiv, e.projekt); }
  }, e.projekt);
}

function zeichneProjektwahl() {
  if (!projektEl || !navDaten) return;
  leeren(projektEl);
  (navDaten.gruppen || []).forEach(function (g) {
    projektEl.appendChild(el("span", { "class": "gruppe" }, g.name));
    g.eintraege.forEach(function (e) { projektEl.appendChild(projektKnopf(e)); });
  });
  var weitere = navDaten.weitere || [];
  if (!weitere.length) return;
  // Deep-Link auf ein abgeschlossenes Projekt: dann aufklappen, sonst bliebe der
  // aktuelle Eintrag unsichtbar (Boards und Berichte von p0–p9 bleiben gebraucht).
  var drin = weitere.some(function (e) { return e.projekt === projekt; });
  if (drin) navWeitereOffen = true;
  var knopf = el("button", { "class": "weitere", onclick: function () {
    navWeitereOffen = !navWeitereOffen; zeichneProjektwahl();
  } }, (navWeitereOffen ? "weniger" : "weitere (" + weitere.length + ")"));
  projektEl.appendChild(knopf);
  if (navWeitereOffen) {
    weitere.forEach(function (e) { projektEl.appendChild(projektKnopf(e)); });
  }
}

function ladeNavigation() {  // SWR-082: Gruppen holen und Kopfbereich zeichnen
  return api("/api/navigation").then(function (n) {
    navDaten = n;
    zeichneProjektwahl();
    return n;
  });
}

function navProjekte() {  // alle bekannten Namen, aktive zuerst
  var namen = [];
  (navDaten && navDaten.gruppen || []).forEach(function (g) {
    g.eintraege.forEach(function (e) { namen.push(e.projekt); });
  });
  (navDaten && navDaten.weitere || []).forEach(function (e) { namen.push(e.projekt); });
  return namen;
}

function pruefeInbox() {  // SWR-076 (pm/N-0016): Zähler frisch holen und Reiter neu zeichnen
  return api("/api/inbox").then(function (d) {
    var neu = (d.inbox || []).length;
    if (neu !== offeneDrs) { offeneDrs = neu; zeigeTabs(); }
  }).catch(function () { /* Zähler ist Komfort, nie ein Grund für eine Fehlermeldung */ });
}

function zeige(elemente) {
  leeren(inhalt);
  elemente.forEach(function (e) { inhalt.appendChild(e); });
}

// ---------- Ansichten ----------
// SWR-103 (pm/T-0016): `sprint` und `mensch` sind benannte Zustände und KEINE Fristen —
// sie bekommen deshalb eine eigene Farbe und nie das Grün, das „Termin liegt komfortabel
// in der Zukunft" bedeutet (B038: eine Farbe, die sich wie eine Terminzusage liest).
var AMPEL_KLASSE = { rot: "rejected", gelb: "in_progress", gruen: "done", grau: "",
                     sprint: "open", mensch: "in_review" };
// SWR-074 (pm/N-0012): Takt-Aufgaben bleiben absichtlich offen — Klartext statt Rätselraten.
var TAKT_NAMEN = { "je-session": "je Session", taeglich: "täglich", woechentlich: "wöchentlich",
                   monatlich: "monatlich", quartalsweise: "quartalsweise", jaehrlich: "jährlich" };
// SWR-104 (pm/T-0032): Takte dürfen eine Uhrzeit tragen (`taeglich@14:00`,
// `woechentlich@Mo-14:00`). Ohne diese Zerlegung fiele der Klartext auf den Rohwert
// zurück — lesbar, aber deutschsprachig falsch („taeglich@14:00" statt „täglich 14:00").
function TAKT_TEXT(t) {
  var teile = String(t || "").split("@");
  if (teile.length !== 2) { return TAKT_NAMEN[t] || t; }
  return (TAKT_NAMEN[teile[0]] || teile[0]) + " " + teile[1].replace("-", " ");
}

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
        var offenText = "Offen (" + p.aufgaben_offen +
          (p.aufgaben_wiederkehrend ? ", davon " + p.aufgaben_wiederkehrend +
            " wiederkehrend" : "") + "): ";  // SWR-074
        var az = el("div", { "class": "zeile" }, offenText);
        p.aufgaben.forEach(function (a) {
          az.appendChild(el("a", { "class": "tlink", href: "#/ticket/" + p.projekt + "/" + a.id,
                                   title: a.titel + (a.takt ? " (wiederkehrend: " +
                                     TAKT_TEXT(a.takt) + ")" : "") }, a.ref || a.id));  // SWR-087
          // SWR-074 (pm/N-0017): dieselbe Klartext-Pille wie im Board statt eines Symbols —
          // ein "↻" war zwar da, hat aber niemandem gesagt, was es bedeutet.
          if (a.takt) {
            az.appendChild(document.createTextNode(" "));
            az.appendChild(pille("wiederkehrend: " + TAKT_TEXT(a.takt), "in_progress"));
          }
          az.appendChild(document.createTextNode(" "));
        });
        karte.appendChild(az);
      }
      // SWR-091 (pm/T-0030, Brief pm/N-0025): überfällige Aufgaben stehen VOR den
      // Statuszahlen und ungekürzt — sie sind der Grund, warum es dieses Feld gibt.
      if (p.ueberfaellig && p.ueberfaellig.length) {
        karte.appendChild(el("div", { "class": "zeile" },
          pille(p.ueberfaellig.length + " überfällig", AMPEL_KLASSE.rot)));
        p.ueberfaellig.forEach(function (u) {
          karte.appendChild(el("div", { "class": "zeile" },
            pille("Frist " + u.frist + " (" + u.tage + " Tag" + (u.tage === 1 ? "" : "e") +
                  " über)", AMPEL_KLASSE.rot),
            el("a", { "class": "tlink", href: "#/ticket/" + p.projekt + "/" + u.id },
               u.ref || u.id),
            " " + u.titel));
        });
      }
      // SWR-104 (pm/T-0032, Brief pm/N-0025): fällige Uhrzeit-Takte stehen neben den
      // überfälligen Fristen — sie tragen keine `frist` und wären dort sonst unsichtbar.
      // „überfällig seit HH:MM" statt „erledigt": läuft keine Session, feuert nichts,
      // und die Anzeige sagt das (B038) statt so zu tun, als sei es getan.
      if (p.takt_faellig && p.takt_faellig.length) {
        karte.appendChild(el("div", { "class": "zeile" },
          pille(p.takt_faellig.length + " Takt fällig", AMPEL_KLASSE.rot)));
        p.takt_faellig.forEach(function (u) {
          karte.appendChild(el("div", { "class": "zeile" },
            pille("überfällig seit " + u.seit, AMPEL_KLASSE[u.ampel] || AMPEL_KLASSE.rot),
            pille(u.takt_klartext, "in_progress"),
            el("a", { "class": "tlink", href: "#/ticket/" + p.projekt + "/" + u.id },
               u.ref || u.id),
            " " + u.titel));
        });
      }
      var statusZeile = el("div", { "class": "zeile" });
      Object.keys(p.status_zahlen).sort().forEach(function (s) {
        statusZeile.appendChild(pille(s + " " + p.status_zahlen[s], s));
      });
      // SWR-091: unterminierte offene Backlog-Tickets ehrlich benennen statt sie als
      // „einfach offen" mitlaufen zu lassen — genau das war der Befund aus pm/N-0025.
      if (p.unterminiert) {
        statusZeile.appendChild(pille(p.unterminiert + " ohne Frist", "in_progress"));
      }
      karte.appendChild(statusZeile);
      if (p.offene_drs.length) {
        karte.appendChild(el("div", { "class": "zeile" }, "Offene Entscheidungen:"));
        p.offene_drs.forEach(function (dr) {
          karte.appendChild(el("div", { "class": "zeile" },
            pille(dr.ampel === "grau" ? "ohne Frist" : "Frist " + dr.frist, AMPEL_KLASSE[dr.ampel]),
            el("a", { "class": "tlink", href: "#/inbox/" + p.projekt }, dr.ref || dr.id),  // SWR-087
            " " + dr.titel));
        });
      }
      if (p.briefe_offen) {  // SWR-051: unbeantwortete Briefe sichtbar
        karte.appendChild(el("div", { "class": "zeile" },
          pille(p.briefe_offen + " Brief(e) offen", "in_progress"),
          el("a", { "class": "tlink", href: "#/chat/" + p.projekt }, "zum Team-Chat")));
      }
      if (p.team) {  // SWR-055 (P7): Team-Kachel mit letztem Digest
        // SWR-108: `null` heisst "fuehrt keine Digests" und wird als "keine Daten"
        // beschriftet; "" heisst "fuehrt Digests, hatte noch keinen" — eine echte Null,
        // die weiterhin "noch kein Digest" sagt. Vorher waren beide Faelle derselbe Satz.
        karte.appendChild(el("div", { "class": "zeile" },
          pille(p.team.letzter_digest === null ? "Digest: keine Daten"
                : p.team.letzter_digest ? "Digest " + p.team.letzter_digest
                : "noch kein Digest", "in_review"),
          el("a", { "class": "tlink", href: "#/team/" + p.projekt }, "zum Team")));
      }
      // SWR-108: `null` = fuer diesen Eintrag ist keine Baseline vorgesehen (Profil ohne
      // G4) -> "keine Daten". "" = vorgesehen, aber noch keine -> "noch keine Baseline".
      // Ein leerer Wert wurde vorher stillschweigend weggelassen; genau das verbietet
      // SWR-096, weil ein fehlender Beitrag als fehlend sichtbar sein muss.
      // SWR-111 (team-dashboard/T-0002): die Kachel zeigt NUR den Tag. Die Annotation
      // steht in `letzte_baseline_text` (bei p1 284 Zeichen — mehr als eine Reihe fasst)
      // und gehoert auf die Detailseite, wie die volle Aufgabenliste bei SWR-094.
      // Nicht im Widget kuerzen: die Regel gehoert in die Quelle, nicht ins JavaScript.
      karte.appendChild(el("div", { "class": "zeile" }, "Letzte Baseline: " + (
        p.letzte_baseline === null ? "keine Daten"
          : p.letzte_baseline || "noch keine")));
      // SWR-108: ohne Run-Registry gibt es keine Messung — die 0 zu zeigen hiesse, eine
      // Messung zu behaupten (B038). `p.kpi` ist dann `null`, und `.toFixed` darauf waere
      // ein Absturz der ganzen Kachel: der Leser wird mitgezogen, nicht nur die Quelle.
      var kpiZeile = el("div", { "class": "zeile" });
      if (p.kpi === null) {
        kpiZeile.appendChild(pille("KPI: keine Daten"));
      } else {
        kpiZeile.appendChild(pille(p.kpi.laeufe + " Läufe"));
        kpiZeile.appendChild(pille(p.kpi.kosten_eur.toFixed(2) + " € API"));
      }
      karte.appendChild(kpiZeile);
      karte.appendChild(el("button", { "class": "knopf", onclick: function () {
        gehe("board", p.projekt);
      } }, "Zum Board"));
      return karte;
}

// SWR-102 (pm/T-0040, Briefe pm/N-0032+N-0033): "2026-08-16T20:55:38+02:00" -> "2026-08-16 20:55".
function sessionZeit(iso) {
  var m = String(iso || "").match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  return m ? m[1] + " " + m[2] : "";
}

// SWR-102: Kachel "Letzte Session" — zeigt den Block "Das Wichtigste" aus
// pm/management/session-agenda.md. Kein zweiter Text: dieselbe Datei, die die
// Session ohnehin schreibt. Der Zeitstempel kommt aus dem Git-Commit, nicht aus
// dem Text — sonst sähe ein alter Stand nach einem ausgefallenen Lauf frisch aus
// (T-0040 Befund c, B038).
function sessionKachel(s) {
  var karte = el("div", { "class": "karte" });
  var kopf = el("div", { "class": "zeile" }, el("h3", { style: "margin:0" }, "Letzte Session"),
    pille(sessionZeit(s.stand) || "Zeitpunkt unbekannt", s.veraltet ? "in_progress" : "done"));
  if (s.fortschreibungen_heute) {
    kopf.appendChild(pille(s.fortschreibungen_heute + "× heute fortgeschrieben"));
  }
  karte.appendChild(kopf);
  if (s.veraltet && s.hinweis) {
    karte.appendChild(el("div", { "class": "meldung fehler" },
      s.hinweis + " — der geplante Lauf ist ausgefallen oder Cowork ist zu."));
  }
  karte.appendChild(s.text ? mdRender(s.text)
    : el("p", { "class": "leer" }, "Kein Block „Das Wichtigste“ in " + s.quelle + "."));
  karte.appendChild(el("div", { "class": "zeile" },
    "Quelle: " + s.quelle + " · Zeitstempel aus dem Git-Commit, nicht aus dem Text."));
  return karte;
}

// SWR-103 (pm/T-0016, pm/D006): Kachel "Sprint aktuell" — die Workflow-Sicht des PM.
// Quelle ist pm/management/sprint-aktuell.md, dieselbe Datei, die die Routine-Session
// ohnehin schreibt (kein zweiter Plan, B033). Zeitstempel aus dem Git-Commit.
// SWR-117 (pm/T-0047): der Kopfblock der ORGANISATION — Aussagen, die keiner Kachel
// gehören. B049: die „ohne Frist"-Zahl war nur je Kachel lesbar, und drei Sessions in
// Folge erklärten sie für abgearbeitet, während in einer anderen Kachel Tickets offen
// standen.
//
// Der Block liest AUSSCHLIESSLICH `organisation` aus dem Cockpit-Payload und zählt
// nichts selbst nach (ADR-P11-001: keine Logik im Rand — sonst sagten Kopfblock und
// Preflight verschiedene Dinge über dieselbe Frage).
//
// Er wird auch bei 0 gerendert. Die Alternative — bei 0 schweigen — macht einen
// geprüften Bestand von einem ungeprüften ununterscheidbar; dieselbe Entscheidung hat
// SWR-114 für die Preflight-Zeile bereits getroffen.
//
// Die Referenzen stehen NEBEN der Zahl und nicht hinter einem Aufklappen: ein Gate,
// das „82" sagt, nennt nicht, welche fünf fehlen (B038).
function orgKopfblock(o) {
  var karte = el("div", { "class": "karte" });
  var n = o.unterminiert_gesamt || 0;
  var kopf = el("div", { "class": "zeile" },
    el("h3", { style: "margin:0" }, "Organisation"));
  kopf.appendChild(pille(n + " ohne Frist", n ? "in_progress" : "done"));
  // SWR-120 (pm/T-0051): die zweite Zahl im SELBEN Kopfblock. Sie kommt als weiterer
  // Schluessel neben die erste — genau die Erweiterbarkeit, wegen der T-0047 den Block
  // als Schwesterschluessel gebaut hat. Kein Leser aendert sich dafuer.
  var m = o.wartet_auf_mensch_gesamt || 0;
  kopf.appendChild(pille(m + "× wartet auf dich", m ? "in_review" : "done"));
  karte.appendChild(kopf);
  var refs = o.unterminiert_refs || [];
  if (refs.length) {
    karte.appendChild(el("div", { "class": "meldung fehler" },
      "Offene Tickets ohne Frist: " + refs.join(", ")));
  } else {
    karte.appendChild(el("div", { "class": "hinweis" },
      "Kein offenes Ticket ohne Frist."));
  }
  var mrefs = o.wartet_auf_mensch_refs || [];
  karte.appendChild(el("div", { "class": mrefs.length ? "meldung" : "hinweis" },
    mrefs.length ? "Wartet auf dich: " + mrefs.join(", ")
                 : "Nichts wartet auf dich."));
  return karte;
}

function sprintKachel(s) {
  var karte = el("div", { "class": "karte" });
  var z = s.zaehler || {};
  // SWR-106: Die Planeinheit ist der Sprint. Die laufende Nummer steht als erstes im
  // Kopf — ohne sie sind „Sprint 4" in der Tabelle und „in drei Läufen" im Kopf des
  // Lesers zwei verschiedene Dinge.
  var kopf = el("div", { "class": "zeile" }, el("h3", { style: "margin:0" }, "Sprint aktuell"));
  if (s.sprint_nr) {
    kopf.appendChild(pille("Sprint " + s.sprint_nr +
      (s.takt_min ? " · Takt " + s.takt_min + " Min" : ""), "done"));
  }
  kopf.appendChild(
    pille(sprintZeit(s.stand) || "Zeitpunkt unbekannt", s.veraltet ? "in_progress" : "done"));
  if (z.dieser_sprint) kopf.appendChild(pille(z.dieser_sprint + "× dieser Sprint", "open"));
  if (z.wartet_auf_mensch) {
    kopf.appendChild(pille(z.wartet_auf_mensch + "× wartet auf dich", "in_review"));
  }
  // SWR-106: fest geplant und Warteschlange sind dieselbe Zahl mit verschiedener
  // Verbindlichkeit — deshalb zwei Pillen und nicht eine Summe (B053).
  if (z.fest_geplant) kopf.appendChild(pille(z.fest_geplant + "× fest geplant", "in_progress"));
  if (z.warteschlange) kopf.appendChild(pille(z.warteschlange + "× Warteschlange"));
  if (z.terminiert) kopf.appendChild(pille(z.terminiert + "× mit Datum", "in_progress"));
  karte.appendChild(kopf);
  // Widerspruch zwischen Frist und geplantem Sprint: die bekannte Schwachstelle daran,
  // beide Felder zu führen (B033). Sie steht oben, weil sie sonst niemand sucht.
  var wid = s.widersprueche || [];
  if (wid.length) {
    var wliste = el("div", { "class": "meldung fehler" },
      wid.length + "× Frist und geplanter Sprint widersprechen sich:");
    wid.forEach(function (w) {
      wliste.appendChild(el("div", {}, w.ref + " — " + w.meldung));
    });
    karte.appendChild(wliste);
  }
  if (s.veraltet && s.hinweis) {
    karte.appendChild(el("div", { "class": "meldung fehler" },
      s.hinweis + " — der Plan ist nicht fortgeschrieben worden."));
  }
  // Der Bestandsabgleich steht VOR dem Plan: ein Ticket, das in keiner Planzeile
  // vorkommt, ist genau der Vorgang, den sonst niemand sieht (B049/B044) — er darf
  // nicht unter einer 18-zeiligen Tabelle stehen.
  var fehlend = s.nicht_geplant || [];
  if (fehlend.length) {
    var liste = el("div", { "class": "meldung fehler" },
      fehlend.length + " offene(s) Ticket(s) stehen in KEINER Planzeile:");
    fehlend.forEach(function (t) {
      liste.appendChild(el("div", {}, el("a", { href: "#/ticket/" + t.projekt + "/" + t.id },
        t.ref), " — " + (t.titel || "")));
    });
    karte.appendChild(liste);
  } else if (s.offen_gesamt) {
    karte.appendChild(el("div", { "class": "zeile" },
      "Alle " + s.offen_gesamt + " offenen Aufgaben der Organisation sind im Plan."));
  }
  if (!(s.zeilen || []).length) {
    karte.appendChild(el("p", { "class": "leer" }, "Kein Sprint-Plan in " + s.quelle + "."));
    return karte;
  }
  var tab = el("table", { "class": "tab" });
  tab.appendChild(el("tr", {}, el("th", {}, "Aufgabe"), el("th", {}, "Rolle"),
    el("th", {}, "Fällig"), el("th", {}, "Status"), el("th", {}, "Grund")));
  s.zeilen.forEach(function (r) {
    var erste = (r.refs || []).filter(function (x) { return x.indexOf("/") > 0; })[0] || "";
    var teile = erste.split("/");
    var name = el("td", {});
    if (teile.length === 2) {
      name.appendChild(el("a", { href: "#/ticket/" + teile[0] + "/" + teile[1] }, r.aufgabe));
    } else { name.appendChild(document.createTextNode(r.aufgabe)); }
    tab.appendChild(el("tr", {}, name, el("td", {}, r.rolle || ""),
      el("td", {}, pille(r.faellig || "—", AMPEL_KLASSE[r.ampel]),
        r.horizont === "warteschlange" ? pille("Warteschlange") : ""),
      el("td", {}, r.status || ""), el("td", {}, r.grund || "")));
  });
  karte.appendChild(tab);
  karte.appendChild(el("div", { "class": "zeile" },
    "Quelle: " + s.quelle + " · Zeitstempel aus dem Git-Commit, nicht aus dem Text."));
  return karte;
}

function sprintZeit(iso) { return sessionZeit(iso); }

function ladeUebersicht() {  // SWR-046 + P9 SWR-067: Org-Cockpit mit Gruppen
  // SWR-102: Die Session-Kachel darf das Cockpit nicht mitreissen — faellt ihr
  // Endpunkt aus, fehlt die Kachel, nicht die Uebersicht.
  return Promise.all([api("/api/cockpit"),
                      api("/api/session").catch(function () { return null; }),
                      api("/api/sprint").catch(function () { return null; })
                     ]).then(function (beide) {
    var u = beide[0], sitzung = beide[1], sprintplan = beide[2];
    document.getElementById("stand").textContent = u.projekte.length + " Projekt(e)";
    var gruppen = { "festes-team": [], "projekt-team": [], "aktiv": [], "abgeschlossen": [] };
    u.projekte.forEach(function (p) {
      (gruppen[p.gruppe || "aktiv"] || gruppen.aktiv).push(p);
    });
    var teile = [];
    // SWR-102: ganz oben, ohne Scrollen sichtbar (T-0040 DoD 2).
    if (sitzung) teile.push(sessionKachel(sitzung));
    // SWR-103: direkt darunter — was die Session getan hat, dann was ansteht (T-0016 DoD 6).
    if (sprintplan) teile.push(sprintKachel(sprintplan));
    // SWR-117 (pm/T-0047): der Org-Kopfblock ÜBER den Kacheln — die Zahl gilt der
    // Organisation, nicht einem Projekt, und ist je Kachel grundsätzlich nicht lesbar
    // (B049). Er erscheint AUCH bei 0: ein stiller Check ist von einem nicht gelaufenen
    // nicht zu unterscheiden (dieselbe Begründung wie die Preflight-Zeile aus SWR-114).
    if (u.organisation) teile.push(orgKopfblock(u.organisation));
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
    // SWR-079 (P10): Filter über die tatsächlich vergebenen Labels — die Liste kommt
    // aus den Tickets, nicht aus einer gepflegten Aufzählung (Labels sind frei).
    var labels = [];
    alle.forEach(function (t) {
      (t.labels || []).forEach(function (l) { if (labels.indexOf(l) < 0) labels.push(l); });
    });
    // SWR-075 (pm/N-0013): länger erledigte Aufgaben verstopfen das Board nicht mehr
    var veraltet = alle.filter(function (t) { return t.veraltet; }).length;
    var filterzeile = el("div", { "class": "karte filterzeile" },
      filterSelect("sprint", werte.sprint.sort(), "Sprint"),
      filterSelect("rolle", werte.rolle.sort(), "Rolle"),
      filterSelect("typ", werte.typ.sort(), "Typ"));
    if (labels.length) filterzeile.appendChild(filterSelect("label", labels.sort(), "Label"));
    if (veraltet) {
      var altBox = el("input", { type: "checkbox", style: "width:auto;margin:0" });
      altBox.checked = boardFilter.alteZeigen === true;
      altBox.addEventListener("change", function () {
        boardFilter.alteZeigen = altBox.checked;
        ladeBoard();
      });
      filterzeile.appendChild(el("label", { style: "display:flex;gap:.3rem;align-items:center" },
        altBox, " älter als 1 Tag erledigt anzeigen (" + veraltet + ")"));
    }
    var spalten = el("div", { "class": "spalten" });
    reihenfolge.forEach(function (status) {
      var gruppe = (b.gruppen[status] || []).filter(function (t) {
        return (!boardFilter.sprint || String(t.sprint) === boardFilter.sprint) &&
               (!boardFilter.rolle || t.rolle === boardFilter.rolle) &&
               (!boardFilter.typ || String(t.typ || "") === boardFilter.typ) &&
               (!boardFilter.label || (t.labels || []).indexOf(boardFilter.label) >= 0) &&
               (boardFilter.alteZeigen === true || !t.veraltet);  // SWR-075/079
      });
      if (!gruppe.length) return;
      var spalte = el("div", { "class": "spalte" },
        el("h3", {}, status + " (" + gruppe.length + ")"));
      gruppe.forEach(function (t) {
        var karte = el("div", { "class": "karte klick", onclick: function () {
          gehe("ticket", projekt, t.id);
        } },
          // SWR-087 (platform/N-0003): eindeutige Kennung <projekt>/T-xxxx statt bloßer Nummer
          el("div", { "class": "zeile" }, pille(t.ref || t.id, t._status), String(t.titel).slice(0, 90)),
          // SWR-074 (pm/N-0012): Takt-Aufgaben sind absichtlich dauerhaft offen
          el("div", { "class": "zeile" }, pille(t.rolle + " · S" + t.sprint + " · " + t.prio),
             t.takt ? pille("wiederkehrend: " + TAKT_TEXT(t.takt), "in_progress") : ""));
        if (t.labels && t.labels.length) {  // SWR-079 (P10, pm/N-0013)
          var lz = el("div", { "class": "zeile" });
          t.labels.forEach(function (l) { lz.appendChild(pille(l, "in_review")); });
          karte.appendChild(lz);
        }
        spalte.appendChild(karte);
      });
      spalten.appendChild(spalte);
    });
    zeige([filterzeile, spalten]);
  });
}

// ---------- P10 (ADR-007): Ticket-Editor — zweiter Schreibpfad neben der Skript-Route ----------
function feldZeile(beschriftung, eingabe) {
  return el("div", { "class": "zeile" }, el("label", { style: "min-width:8rem" }, beschriftung),
            eingabe);
}

function auswahlFeld(werte, wert) {
  var s = el("select", { style: "width:auto" });
  werte.forEach(function (w) {
    var o = el("option", { value: w }, w);
    if (String(wert) === String(w)) o.selected = true;
    s.appendChild(o);
  });
  return s;
}

function ladeEditor() {  // SWR-077/079/080/081 (P10)
  return api("/api/ticket/editor?projekt=" + encodeURIComponent(projekt) +
             "&id=" + encodeURIComponent(detailId)).then(function (e) {
    var f = e.felder, v = e.vokabular;
    var meldung = el("div", {});
    var kopf = el("div", { "class": "karte" },
      el("h3", {}, "Bearbeiten: " + (e.ref || e.id)),
      el("div", { "class": "zeile leer" },
        "Geprüft wird mit denselben Regeln wie in der Skript-Route (board.py); " +
        "jede Änderung wird sofort committet (Herkunft „Mensch via HMI\") und " +
        "gegen eine parallel laufende Routine-Session abgesichert."));

    if (!e.bearbeitbar) {  // Archiv: nur die Wiedereröffnung, nichts sonst
      var wiederKnopf = el("button", { "class": "knopf" }, "Wiedereröffnen");
      kopf.appendChild(el("div", { "class": "zeile" }, pille(f.status, f.status), e.grund));
      wiederKnopf.addEventListener("click", function () {
        wiederKnopf.disabled = true;
        speichern({ status: (v.status_moeglich[1] || "in_progress") }, null, meldung, wiederKnopf);
      });
      kopf.appendChild(el("div", { "class": "btnreihe" }, wiederKnopf,
        el("button", { "class": "knopf zweit", onclick: function () {
          editorOffen = false; lade();
        } }, "Abbrechen")));
      kopf.appendChild(meldung);
      zeige([kopf]);
      return;
    }

    var titel = el("input", { type: "text", maxlength: "160" });
    titel.value = f.titel || "";
    var typ = auswahlFeld(v.typen, f.typ);
    var prio = auswahlFeld(v.prios, f.prio);
    var status = auswahlFeld(v.status_moeglich, f.status);
    var rolle = el("input", { type: "text", style: "width:auto" });
    rolle.value = f.rolle || "";
    var sprint = el("input", { type: "text", style: "width:auto" });
    sprint.value = f.sprint || "";
    var taktWerte = [""], taktNamen = { "": "einmalig" };
    Object.keys(v.takte).forEach(function (k) { taktWerte.push(k); taktNamen[k] = v.takte[k]; });
    var takt = el("select", { style: "width:auto" });
    taktWerte.forEach(function (w) {
      var o = el("option", { value: w }, taktNamen[w]);
      if (String(f.takt || "") === w) o.selected = true;
      takt.appendChild(o);
    });
    var reviewer = el("input", { type: "text", style: "width:auto" });
    reviewer.value = f.reviewer || "";
    // SWR-079: freie Mehrfach-Labels — Komma trennt, der Server validiert den Zeichensatz.
    var labels = el("input", { type: "text",
      placeholder: "z. B. team-pm, neues-projekt, bug (Komma trennt, max. " + v.label_max + ")" });
    labels.value = (f.labels || []).join(", ");
    var body = el("textarea", { rows: "12" });
    body.value = e.body || "";

    var speichernKnopf = el("button", { "class": "knopf" }, "Speichern (PIN bei Netzwerk-Zugriff)");
    speichernKnopf.addEventListener("click", function () {
      speichernKnopf.disabled = true;
      speichern({ titel: titel.value, typ: typ.value, prio: prio.value, status: status.value,
                  rolle: rolle.value, sprint: sprint.value, takt: takt.value,
                  reviewer: reviewer.value,
                  labels: labels.value.split(",").map(function (x) { return x.trim(); })
                    .filter(function (x) { return x; }) },
                body.value, meldung, speichernKnopf);
    });

    function speichern(felder, text, ziel, ausloeser) {
      leeren(ziel);
      var last = { projekt: projekt, id: e.id, fingerprint: e.fingerprint, felder: felder };
      if (text !== null && text !== undefined) last.body = text;
      api("/api/ticket", { method: "POST", headers: { "Content-Type": "application/json" },
                           body: JSON.stringify(last) })
        .then(function (r) {
          ziel.appendChild(el("div", { "class": "meldung ok" },
            r.meldung + " Commit " + r.commit + "."));
          editorOffen = false;
          setTimeout(lade, 800);
        }).catch(function (fehler) {
          if (ausloeser) ausloeser.disabled = false;
          var grund = String(fehler.message || fehler);
          ziel.appendChild(el("div", { "class": "meldung fehler" }, grund));
          // SWR-080: Ein Konflikt ist kein Tippfehler — statt „nochmal versuchen"
          // gibt es genau den Weg, der hilft: neu laden und erneut eintragen.
          if (grund.indexOf("Routine-Session") >= 0) {
            ziel.appendChild(el("div", { "class": "btnreihe" },
              el("button", { "class": "knopf", onclick: function () { lade(); } },
                 "Ticket neu laden")));
          }
        });
    }

    kopf.appendChild(feldZeile("Titel", titel));
    kopf.appendChild(feldZeile("Typ", typ));
    kopf.appendChild(feldZeile("Priorität", prio));
    kopf.appendChild(feldZeile("Status", status));
    kopf.appendChild(feldZeile("Rolle", rolle));
    kopf.appendChild(feldZeile("Sprint", sprint));
    kopf.appendChild(feldZeile("Takt", takt));
    kopf.appendChild(feldZeile("Reviewer", reviewer));
    kopf.appendChild(feldZeile("Labels", labels));
    kopf.appendChild(el("div", { "class": "zeile" }, "Fließtext:"));
    kopf.appendChild(body);
    kopf.appendChild(el("div", { "class": "btnreihe" }, speichernKnopf,
      el("button", { "class": "knopf zweit", onclick: function () {
        editorOffen = false; lade();
      } }, "Abbrechen")));
    kopf.appendChild(meldung);
    zeige([kopf]);
  });
}

function ladeTicket() {  // SWR-040: Detailansicht
  if (editorOffen) return ladeEditor();  // SWR-077 (P10)
  return api("/api/ticket?projekt=" + encodeURIComponent(projekt) +
             "&id=" + encodeURIComponent(detailId)).then(function (t) {
    var kopf = el("div", { "class": "karte" },
      // SWR-087 (platform/N-0003): Ticketnummern sind nur je Repo eindeutig
      el("h3", {}, (t.ref || t.id) + " — " + (t.titel || "")),
      el("div", { "class": "zeile" }, pille(t.status, t.status), pille(t.typ || "task"),
        pille(t.prozess || "-"), pille("Rolle " + (t.rolle || "-")),
        pille("Sprint " + (t.sprint || "-")), pille(t.prio || "-")));
    if (t.takt) {  // SWR-074 (pm/N-0012): erklärt, warum das Ticket dauerhaft offen bleibt
      kopf.appendChild(el("div", { "class": "zeile" },
        pille("wiederkehrend: " + TAKT_TEXT(t.takt), "in_progress"),
        " Daueraufgabe — wird " + TAKT_TEXT(t.takt) + " erledigt und bleibt danach offen."));
    }
    if (t.labels && t.labels.length) {  // SWR-079 (P10, pm/N-0013)
      var lz = el("div", { "class": "zeile" }, "Labels: ");
      t.labels.forEach(function (l) { lz.appendChild(pille(l, "in_review")); });
      kopf.appendChild(lz);
    }
    if (t.reviewer) kopf.appendChild(el("div", { "class": "zeile" }, "Reviewer: " + t.reviewer));
    if (t.frist) kopf.appendChild(el("div", { "class": "zeile" }, "Frist: " + t.frist +
      (t.default ? " · Default: " + t.default : "")));
    var bb = t.blocked_by;
    if (bb && bb.length && String(bb) !== "[]") {
      var z = el("div", { "class": "zeile" }, "Blockiert durch: ");
      tlinks(String(bb), projekt).forEach(function (k) { z.appendChild(k); });
      kopf.appendChild(z);
    }
    // SWR-077 (P10, pm/N-0014): offene Aufgaben sind hier nicht mehr nur lesbar.
    var geschlossen = t.status === "done" || t.status === "rejected";
    kopf.appendChild(el("div", { "class": "btnreihe" },
      el("button", { "class": "knopf", onclick: function () {
        editorOffen = true; lade();
      } }, geschlossen ? "Wiedereröffnen" : "Bearbeiten"),
      el("button", { "class": "knopf zweit", onclick: function () {
        gehe("board", projekt);
      } }, "Zurück zum Board")));
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
    el("h3", {}, (dr.ref || dr.projekt + "/" + dr.id) + " — " + dr.titel),  // SWR-087
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
              e.ref || (e.projekt + "/" + e.id)), " ", pille(e.status, e.status), " ");  // SWR-087
          tlinks(e.entscheidung, e.projekt).forEach(function (k) { z.appendChild(k); });
          h.appendChild(z);
        });
        teile.push(h);
      }
      zeige(teile);
    });
}

// SWR-130 (pm/T-0058): Briefe, deren Beitrag gespeichert, aber nicht verbucht ist.
// ⚠ Das ist KEIN zweiter Inhaltszustand (B033): der Text kommt weiter ausschliesslich aus
// GET /api/briefkasten — die Datei liegt auf der Platte, bevor git laeuft (SWR-121), also
// zeigt das Nachladen sie ohnehin. Gemerkt wird hier nur, was die API NICHT sagen kann:
// dass der Commit dazu fehlschlug. Ein Set von Brief-IDs, nichts weiter.
var unverbuchteBriefe = {};

function ladeChat() {  // SWR-050/051 (P4): Briefkasten-Konversation mit dem Team
  return Promise.all([api("/api/briefkasten?projekt=" + encodeURIComponent(projekt)),
                      api("/api/nutzer")]).then(function (beide) {
    var briefe = beide[0].briefe;
    var nutzer = beide[1].nutzer || [];
    var nutzerNamen = nutzer.map(function (n) { return n.name; });
    var teile = [el("div", { "class": "karte" },
      el("h3", {}, "Team-Chat (" + projekt + ") — Briefkasten"),
      el("p", { "class": "leer" }, "Nachrichten landen versioniert im Repo; die nächste " +
        "Cowork-Session antwortet in denselben Verlauf (asynchron, 0 €)."))];
    if (!briefe.length) teile.push(el("p", { "class": "leer" }, "Noch keine Nachrichten."));

    // SWR-083 (pm/N-0018): neueste zuerst — die Regel steht in `regeln.js` und laesst
    // die API-Liste unangetastet (andere Ansichten lesen dieselben Daten).
    Regeln.sortiereBriefe(briefe).forEach(function (b) {
      var wiederOffen = Regeln.istWiederOffen(b, nutzerNamen);
      var karte = el("div", { "class": "karte brief"
        + (b.status === "beantwortet" ? " beantwortet" : "")
        + (wiederOffen ? " wiederoffen" : "") });
      var kopf = el("div", { "class": "zeile" }, pille(b.id),
        pille(b.status, b.status === "offen" ? "in_progress" : "done"));
      // SWR-129 (pm/T-0060 Punkt 3): Der Brief, den eine Nachfrage wieder geoeffnet hat,
      // ist als solcher erkennbar. Ohne dieses Schild sieht er aus wie ein nie
      // beantworteter — und der Auftraggeber sieht nicht, dass seine Nachfrage ankam.
      if (wiederOffen) {
        kopf.appendChild(pille("Nachfrage — wartet auf Antwort", "in_progress"));
      }
      if (unverbuchteBriefe[b.id]) {
        kopf.appendChild(pille("gespeichert, noch nicht verbucht", "blocked"));
      }
      karte.appendChild(kopf);

      // SWR-129: der Verlauf statt eines Frage/Antwort-Paars.
      Regeln.verlauf(b, nutzerNamen).forEach(function (beitrag) {
        var kasten = el("div", { "class": "beitrag " + beitrag.urheber });
        kasten.appendChild(el("div", { "class": "wer" },
          (beitrag.absender || "(ohne Absender)")
          + (beitrag.zeit ? " · " + beitrag.zeit : "")));
        kasten.appendChild(preMitLinks(beitrag.text, projekt));
        karte.appendChild(kasten);
      });

      // SWR-129 (pm/T-0060 Punkt 1): je Brief ein Antwortfeld. Das grosse Feld oben
      // bleibt fuer einen NEUEN Brief — zwei Wege mit einer Bedeutung waeren B033.
      karte.appendChild(antwortfeld(b.id, nutzer));
      teile.push(karte);
    });

    teile.splice(1, 0, neuerBriefKarte(nutzer));
    zeige(teile);
  });
}

/** Ein Sendefeld — fuer einen neuen Brief (`briefId` leer) oder als Antwort an einen
 *  bestehenden. Ein Bauweg, zwei Ziele: der Unterschied ist genau das Feld `brief`
 *  im Aufruf (SWR-126), und alles andere waere ein zweiter Schreibpfad (B033).
 */
function _sendekasten(briefId, nutzer, knopfText, platzhalter) {
  var text = el("textarea", { rows: briefId ? "2" : "3", placeholder: platzhalter });
  var wer = el("select", {});
  nutzer.forEach(function (n) {
    wer.appendChild(el("option", { value: n.name }, "Von: " + n.name));
  });
  var meldung = el("div", {});
  var knopf = el("button", { "class": "knopf" }, knopfText);
  knopf.addEventListener("click", function () {
    knopf.disabled = true;
    var nutzlast = { projekt: projekt, text: text.value, von: wer.value };
    if (briefId) nutzlast.brief = briefId;
    api("/api/briefkasten", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(nutzlast)
    }).then(function (e) {
      text.value = "";
      // SWR-130 (pm/T-0058): sofort neu laden statt nach 900 ms. Gezeigt wird, was
      // GET /api/briefkasten liefert — kein lokal zusammengebauter Beitrag (B033).
      // Der Knopf bleibt gesperrt, bis das Neuzeichnen ihn ersetzt (SWR-102/B055:
      // ein zweiter Klick in dieses Fenster erzeugte frueher einen zweiten Brief).
      lade();
    }).catch(function (fehler) {
      var meldungstext = String(fehler.message || fehler);
      leeren(meldung);
      // ⚠ SWR-130 Punkt 2: Ein fehlgeschlagener Commit heisst NICHT, dass die Nachricht
      // weg ist — sie liegt auf der Platte, bevor git laeuft (SWR-121). Eine Liste, die
      // sie jetzt nicht zeigt, behauptet das Gegenteil. Also wird auch hier neu geladen,
      // und der Brief traegt „gespeichert, noch nicht verbucht" statt „gescheitert".
      var id = Regeln.briefIdAusFehler(meldungstext);
      if (id) {
        unverbuchteBriefe[id] = true;
        text.value = "";
        lade();
        return;
      }
      meldung.appendChild(el("div", { "class": "meldung fehler" }, meldungstext));
      knopf.disabled = false;
    });
  });
  return { text: text, wer: wer, knopf: knopf, meldung: meldung };
}

function antwortfeld(briefId, nutzer) {
  var k = _sendekasten(briefId, nutzer, "Antworten",
                       "Antwort oder Nachfrage zu " + briefId + " …");
  return el("div", { "class": "antwortfeld" }, k.text, k.wer, k.knopf, k.meldung);
}

function neuerBriefKarte(nutzer) {
  // SWR-083: Das Schreibfeld fuer einen NEUEN Brief steht oben — bei neueste-zuerst
  // laege es sonst hinter dem gesamten Verlauf.
  var k = _sendekasten("", nutzer, "Absenden", "Neue Nachricht ans Team …");
  return el("div", { "class": "karte" },
    el("p", { "class": "leer" }, "Neuer Brief — für eine Nachfrage zu einem bestehenden " +
      "Brief das Feld unter dem Brief benutzen."),
    k.text, k.wer, k.knopf, k.meldung);
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

// SWR-085 (pm/N-0019): Requirements standardmäßig über ALLE Projekte/Teams, mit
// Filter nach Projekt und Gruppe. Vorher zeigte die Ansicht nur das oben gewählte
// Projekt — wer nicht wusste, in welchem Repo eine Anforderung liegt, fand sie nicht.
var reqFilter = { projekt: "", gruppe: "", wort: "" };

function ladeRequirements() {  // SWR-030 + SWR-043 (Tabellen) + SWR-085 (Filter)
  return api("/api/requirements?projekt=alle").then(function (a) {
    var dateien = a.dateien || [];
    var projekte = [], gruppen = [];
    dateien.forEach(function (d) {
      if (d.projekt && projekte.indexOf(d.projekt) < 0) projekte.push(d.projekt);
      if (d.gruppe && gruppen.indexOf(d.gruppe) < 0) gruppen.push(d.gruppe);
    });
    var zeile = el("div", { "class": "karte filterzeile" });
    var wortFeld = el("input", { type: "text", placeholder: "Volltext (z. B. SWR-085, Label, Digest)" });
    wortFeld.value = reqFilter.wort;

    function auswahl(schluessel, werte, beschriftung) {
      var s = el("select", {});
      s.appendChild(el("option", { value: "" }, beschriftung + ": alle"));
      werte.sort().forEach(function (w) {
        var o = el("option", { value: w }, w);
        if (reqFilter[schluessel] === w) o.selected = true;
        s.appendChild(o);
      });
      s.addEventListener("change", function () { reqFilter[schluessel] = s.value; baue(); });
      return s;
    }
    zeile.appendChild(auswahl("projekt", projekte, "Projekt/Team"));
    zeile.appendChild(auswahl("gruppe", gruppen, "Gruppe"));
    wortFeld.addEventListener("input", function () { reqFilter.wort = wortFeld.value; baue(); });
    zeile.appendChild(wortFeld);
    var zaehler = el("div", { "class": "zeile leer" });
    zeile.appendChild(zaehler);

    function baue() {
      var wort = reqFilter.wort.toLowerCase();
      var treffer = dateien.filter(function (d) {
        return (!reqFilter.projekt || d.projekt === reqFilter.projekt) &&
               (!reqFilter.gruppe || d.gruppe === reqFilter.gruppe) &&
               (!wort || (d.datei + " " + d.text).toLowerCase().indexOf(wort) >= 0);
      });
      zaehler.textContent = treffer.length + " von " + dateien.length +
        " Dokument(en) aus " + projekte.length + " Projekten/Teams";
      var karten = treffer.map(function (d) {
        var karte = el("div", { "class": "karte" },
          el("h3", {}, (d.projekt ? d.projekt + " · " : "") + d.datei),
          el("div", { "class": "zeile" }, pille(d.projekt || "?"), pille(d.gruppe || "—")));
        if (d.tabellen && d.tabellen.length) {
          d.tabellen.forEach(function (t) { karte.appendChild(tabelle(t)); });
        } else {
          karte.appendChild(preMitLinks(d.text, d.projekt || projekt));
        }
        return karte;
      });
      if (!karten.length) {
        karten = [el("p", { "class": "leer" }, "Kein Requirements-Dokument passt zum Filter.")];
      }
      zeige([zeile].concat(karten));
    }
    baue();
  });
}

function poolFormular() {  // SWR-088 (pm/T-0022, Teil "Anlegen")
  var kategorie = el("select", {},
    el("option", { value: "team" }, "Team-Kandidat"),
    el("option", { value: "technik" }, "Technik-Kandidat"));
  // pm/N-0023: Technik-Kandidaten tragen die ganze Aufgabe im Kandidat-Feld
  // (keine eigene Kurzbeschreibung) — dafür ein echtes Textfeld statt einer
  // einzeiligen Eingabe, damit lange (auch KI-formulierte) Texte lesbar
  // bleiben. Team-Kandidaten behalten das einzeilige Feld (kurzer Name, wie
  // ein künftiger Team-Ordner) — beide Felder teilen sich `.value`, es wird
  // beim Kategoriewechsel synchronisiert, nicht dupliziert gepflegt.
  var kandidatInput = el("input", { type: "text",
    placeholder: "Kandidat, z. B. team-urlaub (Kleinbuchstaben/Ziffern/Bindestrich)" });
  var kandidatText = el("textarea", { rows: "3",
    placeholder: "Kandidat, z. B. 'CSV-Export für Reports' — auch lange Texte möglich" });
  kandidatText.style.display = "none";
  var kandidatZeile = el("div", { "class": "zeile" }, kandidatInput, kandidatText);
  var kurzZeile = el("div", { "class": "zeile" },
    el("textarea", { rows: "3",
      placeholder: "Kurzbeschreibung (nur Team-Kandidaten) — auch lange Texte möglich" }));
  var kurz = kurzZeile.firstChild;
  // pm/N-0024: "Quelle" (Technik) läuft durch dieselbe Prüfung wie Kandidat-Text
  // und Kurzbeschreibung (siehe FELD_MAX in pool.py) — also auch dieselbe
  // Textfläche statt einer einzeiligen Eingabe, sonst wiederholt sich der Befund
  // nur an der nächsten Zusatzspalte (Nutzen/Voraussetzung laufen durch dieselbe
  // Funktion und bekommen die Fläche deshalb gleich mit).
  var extra1 = el("textarea", { rows: "2", placeholder: "Nutzen" });
  var extra2 = el("textarea", { rows: "2", placeholder: "Voraussetzung" });
  var extra2Zeile = el("div", { "class": "zeile" }, extra2);
  function kandidatFeld() { return kategorie.value === "technik" ? kandidatText : kandidatInput; }
  kategorie.addEventListener("change", function () {
    var technik = kategorie.value === "technik";
    kandidatText.value = kandidatInput.value = technik ? kandidatInput.value : kandidatText.value;
    kandidatInput.style.display = technik ? "none" : "";
    kandidatText.style.display = technik ? "" : "none";
    kurzZeile.style.display = technik ? "none" : "";
    extra1.placeholder = technik ? "Quelle" : "Nutzen";
    extra2Zeile.style.display = technik ? "none" : "";
  });
  var meldung = el("div", {});
  var knopf = el("button", { "class": "knopf" }, "Kandidat anlegen");
  knopf.addEventListener("click", function () {
    knopf.disabled = true;
    var technik = kategorie.value === "technik";
    var felder = technik ? { "Quelle": extra1.value } : { "Nutzen": extra1.value, "Voraussetzung": extra2.value };
    api("/api/pool", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kategorie: kategorie.value, kandidat: kandidatFeld().value,
                             kurzbeschreibung: kurz.value, felder: felder })
    }).then(function (e) {
      leeren(meldung);
      meldung.appendChild(el("div", { "class": "meldung ok" }, e.meldung));
      kandidatInput.value = ""; kandidatText.value = ""; kurz.value = ""; extra1.value = ""; extra2.value = "";
      knopf.disabled = false;
      setTimeout(lade, 900);
    }).catch(function (fehler) {
      leeren(meldung);
      meldung.appendChild(el("div", { "class": "meldung fehler" }, String(fehler.message || fehler)));
      knopf.disabled = false;
    });
  });
  return el("div", { "class": "karte" },
    el("h3", {}, "Neuen Kandidaten anlegen"),
    el("div", { "class": "zeile" }, kategorie),
    kandidatZeile,
    kurzZeile,
    el("div", { "class": "zeile" }, extra1),
    extra2Zeile,
    knopf, meldung);
}

function poolStartFormular(technikNamen) {  // SWR-089 (pm/T-0022, Teil "Starten")
  if (!technikNamen.length) {
    return el("div", { "class": "karte" }, el("h3", {}, "Projekt starten"),
      el("p", { "class": "leer" }, "Keine Technik-Kandidaten im Pool."));
  }
  var auswahl = el.apply(null, ["select", {}].concat(technikNamen.map(function (n) {
    return el("option", { value: n }, n);
  })));
  var meldung = el("div", {});
  var knopf = el("button", { "class": "knopf" }, "G0-Antrag anlegen (Starten)");
  knopf.addEventListener("click", function () {
    knopf.disabled = true;
    api("/api/pool/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kandidat: auswahl.value })
    }).then(function (e) {
      leeren(meldung);
      meldung.appendChild(el("div", { "class": "meldung ok" }, e.meldung));
      knopf.disabled = false;
      setTimeout(lade, 900);
    }).catch(function (fehler) {
      leeren(meldung);
      meldung.appendChild(el("div", { "class": "meldung fehler" }, String(fehler.message || fehler)));
      knopf.disabled = false;
    });
  });
  return el("div", { "class": "karte" },
    el("h3", {}, "Projekt starten (nur Technik-Kandidaten)"),
    el("p", { "class": "leer" },
      "Legt den Ordner projects/<neu> an und stellt einen G0-Antrag in die Inbox — " +
      "entscheidet nichts, die Freigabe bleibt bei dir (Playbook Kap. 16). Team-Kandidaten " +
      "laufen weiterhin über den Briefkasten (volle Team-Gründung, intake.md)."),
    el("div", { "class": "zeile" }, auswahl),
    knopf, meldung);
}

function ladePool() {  // SWR-086 (pm/N-0020): Projekt-Pool als Backlog-Bereich
  return api("/api/pool").then(function (p) {
    if (!p.vorhanden) {
      zeige([el("div", { "class": "karte" }, el("h3", {}, "Projekt-Pool"),
        el("p", { "class": "leer" }, "Keine Pool-Datei gefunden (" + p.quelle + ")."))]);
      return;
    }
    var technikNamen = [];
    (p.abschnitte || []).forEach(function (a) {
      if ((a.titel || "").indexOf("Technik-Kandidaten") !== -1 && a.tabellen[0]) {
        var idx = a.tabellen[0].spalten.indexOf("Kandidat");
        if (idx === -1) idx = 1;
        a.tabellen[0].zeilen.forEach(function (z) { if (z[idx]) technikNamen.push(z[idx]); });
      }
    });
    var kopf = el("div", { "class": "karte" },
      el("h3", {}, "Projekt-Pool — Kandidaten für neue Projekte und Teams"),
      el("div", { "class": "zeile leer" },
        "Quelle: " + p.quelle + " (gepflegt vom PM-Team, pm/D005). " +
        "Technik-Kandidaten lassen sich unten per Knopf starten (G0-Antrag, entscheidet " +
        "nichts). Team-Kandidaten starten weiterhin per Zuruf im Briefkasten (volle " +
        "Team-Gründung, intake.md)."),
      el("div", { "class": "zeile" },
        pille("Anzeigen: da", "done"),
        pille("Anlegen: da", "done"),
        pille("Starten (Technik) per Knopf: da", "done")));
    var karten = [kopf, poolFormular(), poolStartFormular(technikNamen)];
    (p.abschnitte || []).forEach(function (a) {
      var karte = el("div", { "class": "karte" }, el("h3", {}, a.titel || "Kandidaten"));
      a.tabellen.forEach(function (t) { karte.appendChild(tabelle(t)); });
      karten.push(karte);
    });
    zeige(karten);
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
    // SWR-090 (pm/T-0025): Der Knopf sagt im Klartext, womit er läuft. Die Angaben kommen
    // vom Werkzeug selbst (`--was-laeuft` -> jetzt_takte), NICHT aus k.takte im Formular —
    // sonst wäre es die zweite Kopie derselben Regel und ein Auseinanderlaufen wie in
    // team-mail/N-0002 wieder unsichtbar.
    var laeuftZeile = el("div", { "class": "zeile leer" }, "Ein Klick startet: wird geprüft …");
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
        var dateien = r.dateien || [];  // SWR-090: was ist tatsächlich entstanden?
        jetztMeldung.appendChild(el("div", { "class": "meldung ok" },
          dateien.length ? "Fertig — geschrieben: " + dateien.join(" · ")
                         : "Fertig — kein neuer Digest geschrieben (Details unten)."));
        jetztMeldung.appendChild(el("pre", { "class": "leer" }, r.meldung));
        lade();
      }).catch(function (f) {
        jetztKnopf.disabled = false;
        leeren(jetztMeldung);
        jetztMeldung.appendChild(el("div", { "class": "meldung fehler" }, String(f.message || f)));
      });
    } }, "Jetzt zusammenfassen (Ollama)");
    digestKarte.appendChild(el("div", { "class": "btnreihe" }, jetztKnopf));
    digestKarte.appendChild(laeuftZeile);
    digestKarte.appendChild(jetztMeldung);
    api("/api/team/digest-vorschau?projekt=" + encodeURIComponent(projekt)).then(function (v) {
      laeuftZeile.textContent = "Ein Klick startet: " + (v.takt_text || "—") +
        " · Modell: " + (v.automatisch ? "automatisch (erstes installiertes)" : v.modell) +
        " · KI-Hinweis: " + (v.ki_hinweis ? "„" + v.ki_hinweis + "“" : "kein Zusatz") +
        (v.zustellung_mail ? " · Versand: zusätzlich per Mail" : " · Versand: nur ablegen");
    }).catch(function (f) {
      laeuftZeile.textContent = "Ein Klick startet: nicht abrufbar — " + String(f.message || f);
    });
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
  zeichneProjektwahl();  // SWR-082: aktueller Eintrag bleibt hervorgehoben
  zeige([el("p", { "class": "leer" }, "Lade …")]);
  var ansichten = { uebersicht: ladeUebersicht, board: ladeBoard, inbox: ladeInbox,
                    chat: ladeChat, team: ladeTeam, ticket: ladeTicket,
                    pool: ladePool,  // SWR-086 (pm/N-0020)
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

var _gestartet = "";  // SWR-073: Startzeitpunkt des Servers, an dem die Seite hängt
function pruefeVersion() {  // SWR-047: Prozess- vs. Code-Stand
  api("/api/version").then(function (v) {
    document.getElementById("stand").textContent = "Server " + v.prozess_stand;
    // SWR-073 (pm/N-0010): Der Server startet sich bei neuem Code selbst neu.
    // Kommt er mit neuem Startzeitpunkt zurück, lädt die Seite von allein nach.
    if (!_gestartet) _gestartet = v.gestartet;
    else if (v.gestartet !== _gestartet) { location.reload(); return; }
    if (v.prozess_stand !== v.code_stand && !document.querySelector(".banner")) {
      document.body.insertBefore(el("div", { "class": "banner" },
        "Neuer Code auf der Platte (" + v.code_stand + ") — der Server läuft noch auf " +
        v.prozess_stand + ". ",
        el("button", { "class": "knopf", style: "margin-left:.4rem;padding:.3rem .8rem",
                       onclick: serverNeustart }, "Jetzt neu starten")),
        document.body.firstChild);
    }
  }).catch(function () { /* Altserver ohne /api/version oder Neustart läuft gerade */ });
}
setInterval(pruefeVersion, 30000);  // SWR-073: merkt den Selbst-Neustart

ladeNavigation().then(function () {  // SWR-082 (pm/T-0012), löst die alte Auswahlliste ab
  parseHash();
  var namen = navProjekte();
  if (namen.indexOf(projekt) < 0 && namen.length) projekt = namen[0];
  pruefeVersion();
  pruefeInbox();  // SWR-076 (pm/N-0016)
  lade();
}).catch(function () { parseHash(); lade(); });
setInterval(pruefeInbox, 60000);  // SWR-076: Zähler bleibt aktuell, auch ohne Neuladen
