// Renderregeln des Briefverlaufs (SWR-128; ADR-008) — **ohne DOM, ohne fetch, ohne Netz.**
//
// Warum diese Datei existiert: `app.js` ist rund 1.500 Zeilen, die jede Entscheidung
// unmittelbar in `document.createElement` verweben. Solange das so ist, laesst sich eine
// Renderregel nur mit einem Browser pruefen — und die Organisation hat 741 Python-Tests
// und **null** JS-Tests (gemessen 2026-08-17, `projects/p12/T-0004`).
//
// ADR-008 zieht deshalb die **Entscheidungen** aus der Darstellung heraus: was hier steht,
// beantwortet Fragen ("von wem ist dieser Beitrag?", "ist der Brief durch eine Nachfrage
// wieder offen?") und ruehrt kein Element an. Diese Funktionen sind ohne Browser pruefbar;
// `app.js` bleibt das duenne Stueck, das aus der Antwort ein Element macht.
//
// Kein Build, keine Paketabhaengigkeit (ADR-002 bleibt gueltig): die Datei wird von
// `index.html` als klassisches `<script>` geladen und von der Teststrecke ueber `require()`
// gelesen. Die drei Zeilen am Ende sind der ganze Preis dafuer.
"use strict";

var Regeln = (function () {

  // B054-Einstieg, woertlich wie im Backend (`briefkasten._ist_beitragskopf`): eine
  // Team-Antwort ist daran erkennbar, dass ihre Ueberschrift mit "Antwort" beginnt. Die
  // Fassung dahinter ("des Teams", "Routine-Session", Uhrzeit) variiert seit dem 15.08.
  // und darf deshalb nicht mitgeprueft werden.
  function _beginntMitAntwort(absender) {
    return String(absender || "").indexOf("Antwort") === 0;
  }

  /** Von wem ist dieser Beitrag — "mensch" oder "team"?
   *
   * Die Zuordnung wird **nicht geraten** (B038). Sie liest zwei Fakten:
   *
   * 1. Der **Erstbeitrag** ist immer vom Menschen — er ist der Brief selbst; sein
   *    Absender steht im Frontmatter und nicht in einer Ueberschrift (SWR-126).
   * 2. Jeder weitere Beitrag gehoert dem Menschen, wenn sein Absender in der
   *    **Nutzerregistry** steht (`/api/nutzer`, SWR-037) — dieselbe Liste, aus der der
   *    Absender beim Senden gewaehlt wurde. Sonst ist er vom Team.
   *
   * Die naheliegende Alternative — "Absender gleich `brief.von`" — waere falsch: der
   * Mensch darf beim Senden einen anderen registrierten Nutzer waehlen, ein zweiter
   * Beitrag desselben Menschen unter anderem Namen zaehlte dann als Team. Die Registry
   * ist ein Fakt, der Vergleich mit `von` waere eine Annahme.
   *
   * Ohne Registry (Liste leer oder nicht geliefert) bleibt der B054-Einstieg: was mit
   * "Antwort" beginnt, ist Team, alles andere Mensch. Das ist die Regel, die den Bestand
   * von 41 Briefen traegt.
   */
  function urheber(beitrag, nutzerNamen) {
    if (!beitrag) return "team";
    if (beitrag.ist_erstbeitrag) return "mensch";
    var absender = String(beitrag.absender || "");
    if (nutzerNamen && nutzerNamen.length) {
      return nutzerNamen.indexOf(absender) >= 0 ? "mensch" : "team";
    }
    return _beginntMitAntwort(absender) ? "team" : "mensch";
  }

  /** Kopfzeile eines Beitrags: `{absender, zeit, urheber}` — fertig zum Anzeigen.
   *
   * Der Erstbeitrag traegt Absender und Zeit **aus dem Brief**, nicht aus einer
   * Ueberschrift. Das Backend fuellt beides bereits (SWR-126); diese Funktion greift nur
   * dann auf den Brief zurueck, wenn die Felder leer sind — und erfindet nichts, wenn
   * auch dort nichts steht.
   */
  function beitragKopf(beitrag, brief, nutzerNamen) {
    beitrag = beitrag || {};
    brief = brief || {};
    var absender = beitrag.absender || "";
    var zeit = beitrag.zeit || "";
    if (beitrag.ist_erstbeitrag) {
      if (!absender) absender = brief.von || "";
      if (!zeit) zeit = brief.zeit || "";
    }
    return { absender: absender, zeit: zeit, urheber: urheber(beitrag, nutzerNamen) };
  }

  /** Ist dieser Brief durch eine **Nachfrage des Menschen** wieder offen? (pm/T-0060 Pkt. 3)
   *
   * Der Fall, den der Auftraggeber sehen muss: er hat an einen bereits beantworteten Brief
   * angehaengt, und SWR-126 hat den Status dabei auf `offen` zurueckgesetzt. Ohne eigene
   * Kennzeichnung sieht dieser Brief aus wie ein nie beantworteter — und der Auftraggeber
   * sieht **nicht**, dass seine Nachfrage angekommen ist.
   *
   * Erkennbar ist er daran, dass er `offen` ist und **trotzdem schon eine Team-Antwort
   * enthaelt**. Ein frischer Brief ist offen ohne Team-Beitrag; ein beantworteter ist
   * `beantwortet`. Nur die Nachfrage ist beides zugleich.
   */
  function istWiederOffen(brief, nutzerNamen) {
    if (!brief || brief.status !== "offen") return false;
    var b = brief.beitraege || [];
    for (var i = 0; i < b.length; i++) {
      if (urheber(b[i], nutzerNamen) === "team") return true;
    }
    return false;
  }

  /** Verlauf eines Briefs als fertige Kopfzeilen + Text, in Reihenfolge.
   *
   * **Faellt der Verlauf aus, bleibt der Brief lesbar.** Liefert eine (alte) Antwort kein
   * `beitraege`, wird aus `nachricht`/`antwort` ein Verlauf gebildet — dieselben zwei
   * Bloecke, die `spalte_antwort` seit SWR-050 zusagt. Eine leere Ansicht waere die
   * schlechteste aller Anzeigen: sie behauptet, es stuende nichts da.
   */
  function verlauf(brief, nutzerNamen) {
    brief = brief || {};
    var roh = brief.beitraege;
    if (!roh || !roh.length) {
      roh = [];
      if (brief.nachricht) roh.push({ absender: "", zeit: "", text: brief.nachricht,
                                      ist_erstbeitrag: true });
      if (brief.antwort) roh.push({ absender: "Antwort", zeit: brief.antwort_datum || "",
                                    text: brief.antwort, ist_erstbeitrag: false });
    }
    return roh.map(function (b) {
      var kopf = beitragKopf(b, brief, nutzerNamen);
      return { absender: kopf.absender, zeit: kopf.zeit, urheber: kopf.urheber,
               text: b.text || "" };
    });
  }

  /** Briefe fuer die Anzeige: neueste zuerst (SWR-083) — **ohne die Eingabe zu aendern.**
   *
   * `reverse()` arbeitet in-place; die API-Liste wird aber von weiteren Ansichten gelesen.
   * `slice()` davor ist deshalb keine Vorsicht, sondern die Zusage.
   */
  function sortiereBriefe(briefe) {
    return (briefe || []).slice().reverse();
  }

  /** Welchen Brief nennt diese Fehlermeldung? (SWR-130, pm/T-0058 Punkt 2)
   *
   * Schlaegt der Commit fehl, ist die Nachricht trotzdem **gespeichert** — die Datei liegt
   * auf der Platte, bevor git laeuft, und SWR-121 verlangt, dass die Meldung das zuerst
   * sagt und die Kennung nennt. Genau diese Kennung wird hier gelesen: sie ist der
   * Unterschied zwischen "gespeichert, noch nicht verbucht" und "gescheitert".
   *
   * Findet sich keine Kennung, wird **keine erfunden** (B038) — dann ist es ein echter
   * Fehler und wird als solcher gezeigt.
   */
  function briefIdAusFehler(meldung) {
    var m = String(meldung || "").match(/N-\d{4}/);
    return m ? m[0] : "";
  }

  // --------------------------------------------------------------------------
  // SWR-132 (pm/T-0064, Briefe pm/N-0038 + pm/N-0042): die projektuebergreifende
  // Aufgabenliste und ihre Gruppierung nach Rolle.
  // --------------------------------------------------------------------------

  var OHNE_ROLLE = "ohne Rolle";  // SWR-096: benannt, nicht stillschweigend fehlend

  /** Reihenfolge der Aufgaben in der Liste — **stabil und ohne die Eingabe zu aendern.**
   *
   * Sortiert nach `projekt`, dann `id`. Das ist bewusst *nicht* nach Prioritaet oder
   * Frist: die Liste existiert, damit der Auftraggeber **selbst** priorisiert
   * (`pm/N-0038`), und eine Vorsortierung nach Dringlichkeit waere eine stille erste
   * Priorisierung neben seiner — dieselbe Ueberlegung, aus der die Liste nicht gekuerzt
   * wird.
   *
   * `slice()` vor `sort()` wie bei `sortiereBriefe`: `sort` arbeitet in-place, und die
   * Antwort der API wird von mehreren Ansichten gelesen.
   */
  function sortiereAufgaben(aufgaben) {
    return (aufgaben || []).slice().sort(function (a, b) {
      var pa = String((a && a.projekt) || ""), pb = String((b && b.projekt) || "");
      if (pa !== pb) return pa < pb ? -1 : 1;
      var ia = String((a && a.id) || ""), ib = String((b && b.id) || "");
      return ia < ib ? -1 : (ia > ib ? 1 : 0);
    });
  }

  /** Aufgaben nach **Rolle** gruppiert: `[{rolle, aufgaben}]`, Rollen alphabetisch.
   *
   * Der Wunsch aus `pm/N-0042` woertlich: *"aufgaben nach rollen sehen. also
   * Team-Rolle-Aufgaben alle ausser geschlossen."*
   *
   * ⚠ **Dieselbe Liste, anders gruppiert — keine zweite Ansicht.** Zwei
   * projektuebergreifende Aufgabenlisten nebeneinander waeren zwei Antworten auf eine
   * Frage (B033), und B054 belegt den Preis: dort blieb bei zehn von dreissig Briefen die
   * Antwort unsichtbar, weil zwei Leser dieselbe Sache verschieden lasen.
   *
   * ⚠ **Jede Aufgabe erscheint in genau EINER Gruppe.** Das ist die Zusicherung, an der
   * eine Gruppierung scheitert: erscheint eine Aufgabe zweimal, zaehlt der Leser sie
   * zweimal; erscheint sie nirgends, ist sie verschwunden. Eine Aufgabe ohne `rolle`
   * bekommt deshalb die **benannte** Gruppe `"ohne Rolle"` (SWR-096) statt still zu
   * fehlen.
   *
   * ⚠ **`verantwortlich` gruppiert NICHT.** Es bleibt Feld an der Zeile. Die Fachrolle
   * und die Frage "Mensch oder Team?" sind zwei Fragen; sie zu einer Gruppierung zu
   * verschmelzen war der Fehler, der zu SWR-116 fuehrte.
   */
  function aufgabenNachRolle(aufgaben) {
    var sortiert = sortiereAufgaben(aufgaben);
    var namen = [], nach = {};
    for (var i = 0; i < sortiert.length; i++) {
      var a = sortiert[i] || {};
      var r = String(a.rolle || "").trim() || OHNE_ROLLE;
      if (!nach[r]) { nach[r] = []; namen.push(r); }
      nach[r].push(a);
    }
    namen.sort(function (x, y) {
      // `OHNE_ROLLE` zuletzt: es ist keine Rolle, sondern deren Fehlen — zwischen `pl`
      // und `test` einsortiert saehe es wie eine aus.
      if (x === OHNE_ROLLE) return 1;
      if (y === OHNE_ROLLE) return -1;
      return x < y ? -1 : (x > y ? 1 : 0);
    });
    return namen.map(function (r) { return { rolle: r, aufgaben: nach[r] }; });
  }

  /** Beschriftung einer Gruppe: `"pl (4)"` — die Zahl steht **immer** daneben.
   *
   * Kein Eintrag verschwindet ohne Zaehler: eine zugeklappte Gruppe ohne Zahl ist die
   * Anzeigeform, wegen der `pm/N-0025` und `pm/N-0038` geschrieben wurden.
   */
  function gruppenTitel(gruppe) {
    gruppe = gruppe || {};
    return String(gruppe.rolle || OHNE_ROLLE) + " (" +
           ((gruppe.aufgaben && gruppe.aufgaben.length) || 0) + ")";
  }

  // --------------------------------------------------------------------------
  // SWR-133 (pm/T-0067 aus pm/T-0066, Brief pm/N-0042): kompakt heisst **falten**.
  // --------------------------------------------------------------------------

  /** Ist diese Gruppe aufgeklappt? — `zustand` gewinnt ueber `standard`.
   *
   * Der Wunsch: *"mach das Cockpit bischen uebersichtlicher, da muss man so viel
   * scrollen -> kompakter"* (`pm/N-0042`). Der **Widerspruch** dazu steht im Brief
   * desselben Morgens: `pm/N-0038` verlangt, **alle** offenen Aufgaben zu sehen.
   *
   * > **Aufgeloest als: falten, nicht weglassen.** Zugeklappt ist nicht weg — die Zahl
   * > steht am Titel (`gruppenTitel`), und ein Griff holt es zurueck. Weggelassen waere
   * > eine zweite, stille Priorisierung; genau die hat er zweimal geruegt.
   *
   * ⚠ **`undefined` und `false` sind hier zwei verschiedene Dinge** (SWR-108: echte Null
   * vs. nicht geliefert). *Nie angefasst* heisst „nimm den Standard dieser Gruppe";
   * *zugeklappt* heisst „der Mensch hat zugeklappt" und muss einen Reiterwechsel
   * ueberleben. Wuerde `undefined` als `false` gelesen, waere jede Gruppe beim ersten
   * Aufruf zu — und der Auftraggeber saehe **weniger** als vorher, was das Gegenteil
   * beider Briefe waere.
   */
  function istGruppeOffen(zustand, name, standard) {
    var z = (zustand || {})[name];
    return z === undefined ? !!standard : !!z;
  }

  // --------------------------------------------------------------------------
  // SWR-135 (projects/p11/T-0010): Kompaktkacheln des Widget-Dashboards.
  // --------------------------------------------------------------------------

  var KEINE_DATEN = "keine Daten";

  //: Beschriftung je Kachelfeld. Kurz, weil eine Kompaktkachel schmal ist — und an
  //: EINER Stelle, weil zwei Beschriftungslisten zwei Namen fuer dasselbe Feld sind.
  var FELD_TITEL = { aufgaben_offen: "offen", briefe_offen: "Briefe",
                     unterminiert: "ohne Termin", tickets_gesamt: "Tickets",
                     letzte_baseline: "Baseline", team: "Digest" };

  /** Was zeigt die Kachel fuer dieses Feld? — die Regel aus dem Widget-Vertrag.
   *
   * Der Vertrag (`zustaende`) verlangt drei Faelle und schliesst zwei Verwechslungen
   * ausdruecklich aus:
   *
   * * `echte_null` → **als 0 anzeigen, nie als „keine Daten"**. *„0 offene Briefe ist ein
   *   Ergebnis, kein Loch."*
   * * `nicht_geliefert` → **als „keine Daten" anzeigen, nie als 0**, nie als leere Zelle.
   *   *„Ein fehlender Beitrag muss als fehlend sichtbar sein."*
   *
   * ⚠ Die Verwechslung ist nicht theoretisch: `team: null` (das Projekt fuehrt keine
   * Digests) und `briefe_offen: 0` (es gibt keine offenen Briefe) kommen aus derselben
   * Antwort und sehen ohne diese Regel gleich aus. Genau diese Gleichheit hat in SWR-128
   * fuenf Sprints lang „null JS-Tests" verborgen — dort sahen „nicht gelaufen" und
   * „gruen" gleich aus.
   *
   * Das **Fakt** (welcher Zustand) kommt aus `aggregation._zustand`; hier steht nur, wie
   * er aussieht. Zwei Orte, zwei verschiedene Fragen — kein B033.
   */
  function feldText(feld) {
    feld = feld || {};
    if (feld.zustand === "nicht_geliefert") return KEINE_DATEN;
    if (feld.zustand === "echte_null") return "0";
    // ⚠ Ein Feld OHNE bekannten Zustand gilt als `nicht_geliefert` und nicht als Wert.
    // Der erste Entwurf fiel hier durch bis `String(feld.wert)` und haette bei einem
    // unvollstaendigen Payload die Zeichenkette „undefined" auf den Schirm gebracht — eine
    // Anzeige, die aussieht wie ein Inhalt und keiner ist. „Keine Daten" ist in diesem
    // Fall die einzige wahre Aussage, die wir haben.
    if (feld.zustand !== "wert") return KEINE_DATEN;
    var w = feld.wert;
    if (w && typeof w === "object") {
      // `team` ist im Vertrag ein Objekt (`felder_innen: [letzter_digest]`) — die Kachel
      // zeigt dessen Inhalt und nicht "[object Object]".
      var d = w.letzter_digest;
      if (d === null || d === undefined) return KEINE_DATEN;
      return String(d) || "0";
    }
    return String(w);
  }

  /** Die Felder einer Kompaktkachel als `[{name, titel, text, zustand}]`, in Reihenfolge.
   *
   * Die Reihenfolge kommt aus dem **Backend** (`KACHEL_FELDER`) und wird hier nicht
   * wiederholt: `Object.keys` folgt der Einfuegereihenfolge, und eine zweite Liste im
   * Frontend waere eine zweite Aussage darueber, was eine Kachel zeigt (B033).
   */
  function kachelFelder(kachel) {
    var felder = (kachel || {}).felder || {};
    return Object.keys(felder).map(function (name) {
      return { name: name, titel: FELD_TITEL[name] || name,
               text: feldText(felder[name]), zustand: felder[name].zustand };
    });
  }

  /** Dashboard-Kacheln nach Gruppe: `[{gruppe, titel, kacheln}]` in fester Reihenfolge.
   *
   * ⚠ **Feste Reihenfolge und nicht alphabetisch**: „Feste Teams" vor „Projekt-Teams" vor
   * „Aktive Projekte" vor „Abgeschlossen" ist die Ordnung, die das Cockpit seit SWR-067
   * benutzt. Eine zweite Ordnung derselben Gruppen waere fuer den Leser eine zweite
   * Organisation.
   *
   * ⚠ **Leere Gruppen fallen weg, unbekannte nicht.** Eine Kachel mit einer Gruppe, die
   * hier nicht steht, landet in `sonstige` statt zu verschwinden (SWR-096) — sonst
   * verliert ein neuer Gruppenname stillschweigend Projekte, und niemand merkt es.
   */
  function dashboardGruppen(kacheln) {
    var ordnung = [["festes-team", "Feste Teams"], ["projekt-team", "Projekt-Teams"],
                   ["aktiv", "Aktive Projekte"], ["abgeschlossen", "Abgeschlossen"]];
    var bekannt = {}, nach = {};
    ordnung.forEach(function (g) { bekannt[g[0]] = true; nach[g[0]] = []; });
    nach.sonstige = [];
    (kacheln || []).forEach(function (k) {
      var g = (k && k.gruppe) || "";
      (bekannt[g] ? nach[g] : nach.sonstige).push(k);
    });
    var raus = ordnung.filter(function (g) { return nach[g[0]].length; })
      .map(function (g) { return { gruppe: g[0], titel: g[1], kacheln: nach[g[0]] }; });
    if (nach.sonstige.length) {
      raus.push({ gruppe: "sonstige", titel: "Ohne bekannte Gruppe",
                  kacheln: nach.sonstige });
    }
    return raus;
  }

  // SWR-138 (pm/T-0052): die zwei Abschnitte von "Fuer dich". Die Titel und die
  // Leertexte stehen HIER und nicht in `app.js`, weil ADR-008 genau diese Sorte
  // Entscheidung pruefbar machen soll — und weil die Leertexte der DoD-Punkt 4 sind.
  var FUER_DICH_LEER_ENTSCHEIDUNGEN = "Keine offenen Entscheidungen.";
  var FUER_DICH_LEER_HANDLUNGEN = "Keine offenen Handlungen.";

  /** Die beiden Abschnitte "Fuer dich", in fester Reihenfolge.
   *
   * ⚠ **Zwei Abschnitte und nicht eine Liste.** An der Entscheidungsliste haengen die
   * Knoepfe (`optionen`/`default`/`frist`, SWR-042). Ein Eintrag ohne Optionen dort
   * hiesse entweder Knoepfe, die nichts tun, oder eine Liste, in der manche Eintraege
   * Knoepfe haben und manche nicht — eine Flaeche mit zwei Bedeutungen, also B033.
   * `knoepfe` sagt es deshalb je Abschnitt ausdruecklich, statt es der Ansicht zu
   * ueberlassen.
   *
   * ⚠ **Beide Abschnitte erscheinen immer**, auch leer. Ein Abschnitt, der bei 0
   * verschwindet, ist von einem nicht gebauten nicht zu unterscheiden — dieselbe
   * Begruendung, aus der der Preflight seine Nullzeilen druckt (SWR-114/SWR-122). Der
   * Auftraggeber soll sehen, dass wir nachgesehen haben.
   */
  function fuerDichAbschnitte(entscheidungen, handlungen) {
    return [
      { schluessel: "entscheidungen", titel: "Für dich: Entscheidungen",
        eintraege: entscheidungen || [], knoepfe: true,
        leer: FUER_DICH_LEER_ENTSCHEIDUNGEN },
      { schluessel: "handlungen", titel: "Für dich: Handlungen",
        eintraege: handlungen || [], knoepfe: false,
        leer: FUER_DICH_LEER_HANDLUNGEN }
    ];
  }

  return { feldText: feldText, kachelFelder: kachelFelder,
           fuerDichAbschnitte: fuerDichAbschnitte,
           FUER_DICH_LEER_ENTSCHEIDUNGEN: FUER_DICH_LEER_ENTSCHEIDUNGEN,
           FUER_DICH_LEER_HANDLUNGEN: FUER_DICH_LEER_HANDLUNGEN,
           dashboardGruppen: dashboardGruppen, KEINE_DATEN: KEINE_DATEN,
           istGruppeOffen: istGruppeOffen,
           urheber: urheber, beitragKopf: beitragKopf, istWiederOffen: istWiederOffen,
           verlauf: verlauf, sortiereBriefe: sortiereBriefe,
           briefIdAusFehler: briefIdAusFehler,
           sortiereAufgaben: sortiereAufgaben, aufgabenNachRolle: aufgabenNachRolle,
           gruppenTitel: gruppenTitel, OHNE_ROLLE: OHNE_ROLLE };
})();

// Ein Modul fuer die Teststrecke, eine globale Variable fuer den Browser (ADR-002: kein
// Build, also kein Bundler, der das fuer uns entscheidet).
if (typeof module === "object" && module.exports) { module.exports = Regeln; }
else if (typeof window === "object") { window.Regeln = Regeln; }
