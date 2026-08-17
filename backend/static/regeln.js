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

  // ---------- Deep-Links (SWR-150, projects/p11/T-0012) ----------
  //
  // ⚠⚠ **Der Befund, um den es hier geht, war nicht der fehlende Link, sondern der
  // zweite Bauplatz.** `app.js` hatte NEUN Stellen, die `"#/ticket/" + projekt + "/" + id`
  // zusammensetzten — und in sieben davon stand als **Beschriftung** `x.ref`, also die
  // Kennung **vom Server**. Beschriftung und Ziel kamen damit aus zwei Quellen:
  //
  //   > **Ein Link, dessen Aufschrift der Server liefert und dessen Ziel die Ansicht
  //   > zusammenbaut, ist zwei Aussagen ueber dasselbe Ticket. Solange beide gleich sind,
  //   > merkt es niemand.**
  //
  // Und sie sind nicht theoretisch verschieden: **68 Ticketnummern gibt es in mehr als
  // einem Projekt**, `T-0002` allein in **17** (gemessen 2026-08-17). Ein Ziel, das aus
  // einer Nummer und dem *gerade angezeigten* Projekt entsteht, ist in dem Moment falsch,
  // in dem beides auseinanderfaellt — also genau dann, wenn es niemand mehr erwartet.
  //
  // Deshalb: **eine** Stelle, und sie nimmt die fertige Kennung. Sie **baut keine**.
  var TICKET_ROUTE_PRAEFIX = "#/ticket/";

  // Eine Kennung ist `projekt/T-xxxx` (SWR-087, `aggregation.ref`). Das Muster ist die
  // Zusicherung, dass hier nichts anderes durchkommt — insbesondere keine nackte Nummer.
  var REF_MUSTER = /^([A-Za-z0-9_.\-]+)\/(T-\d{4})$/;

  /** Route zur Detailseite einer Aufgabe — aus der **Kennung vom Server**.
   *
   * `"pm/T-0002"` -> `"#/ticket/pm/T-0002"`.
   *
   * ⚠⚠ **Eine nackte Nummer ergibt `""` und damit KEINEN Link.** Das ist die Substanz von
   * DoD 2 des Tickets und nicht Strenge um ihrer selbst willen:
   *
   *   > **Ein Link auf das falsche Projekt ist schlimmer als kein Link. Der falsche
   *   > oeffnet ein fremdes Ticket und sieht dabei richtig aus.**
   *
   * Die Ansicht prueft deshalb `if (route)` und schreibt sonst reinen Text — sichtbar
   * unverlinkt statt unsichtbar falsch.
   */
  function ticketRoute(ref) {
    var m = REF_MUSTER.exec(String(ref || "").trim());
    return m ? TICKET_ROUTE_PRAEFIX + m[1] + "/" + m[2] : "";
  }

  /** Kennung fuer eine Nummer, die im **Fliesstext** steht — eine **ANNAHME**.
   *
   * ⚠ Diese Funktion heisst so, wie sie ist. Ein `T-0042` in einem Absatz ist **keine
   * Referenz, sondern eine Zahl**: der Text sagt nicht, aus welchem Projekt sie kommt.
   * Was hier entsteht, ist die Annahme *„gemeint ist das gerade angezeigte Projekt"* —
   * bei 68 mehrfach vergebenen Nummern ist das eine Vermutung und keine Auflösung.
   *
   * Sie steht trotzdem hier und nicht in `app.js`, und zwar aus zwei Gruenden: es bleibt
   * **eine** Stelle, an der eine Kennung entsteht, und die Annahme ist **benannt** statt
   * in einer Zeichenverkettung versteckt. Wer sie eines Tages auflösen will, findet sie.
   * Die Ansicht macht sie sichtbar (`title`-Attribut) — eine Vermutung, die aussieht wie
   * eine Auskunft, ist der Fehler, gegen den SWR-114 gebaut ist.
   */
  function textRefAnnahme(projekt, id) {
    var p = String(projekt || "").trim(), t = String(id || "").trim();
    return (p && /^T-\d{4}$/.test(t)) ? p + "/" + t : "";
  }

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

  /** SWR-144 (pm/T-0065): die **Beschriftung** des Terminierungsknopfs — nicht seine Wirkung.
   *
   * Der Knopf setzt `geplant_sprint` auf den naechsten Sprint. Die Zahl kommt aus dem
   * Payload (`naechster_sprint`, aus dem Register); gerechnet wird hier **nichts**. Ein
   * `sprint_nr + 1` an dieser Stelle waere eine zweite Antwort auf "welcher ist der
   * naechste Sprint?" (B033) — und sie waere genau dann falsch, wenn zwischen Laden und
   * Klick ein Sprint gewechselt hat.
   *
   * ⚠ **Diese Funktion entscheidet nicht, ob geschrieben wird.** Der Server entscheidet
   * das (und antwortet mit `unveraendert: true`, wenn nichts zu tun war). Hier steht nur,
   * was der Knopf **verspricht** — und im Fall "steht schon dort" verspricht er nichts
   * und sagt das:
   *
   * > **Ein Knopf, der bei jedem Klick dasselbe verspricht, sagt nicht mehr, ob er
   * > gebraucht wird.**
   *
   * Rueckgabe: `{text, titel, wirkungslos}`. `wirkungslos` ist eine **Beschriftung** und
   * keine Sperre: der Knopf bleibt klickbar, weil die Zahl im Payload alt sein kann und
   * der Server die Wahrheit hat. Ein deaktivierter Knopf auf einer veralteten Zahl waere
   * eine Sperre auf einer Vermutung.
   */
  function terminierKnopf(aufgabe, naechsterSprint) {
    var n = parseInt(naechsterSprint, 10);
    if (!(n > 0)) {
      // Ohne Nummer wird nicht geraten. ⚠ `0` und "nicht geliefert" sind hier dieselbe
      // Bauart wie im Widget-Vertrag: ein fehlender Wert bekommt einen eigenen Text.
      return { text: "Sprint unbekannt", titel: "Das Sprintregister hat keine Nummer "
               + "geliefert — ohne sie steht nicht fest, was 'der naechste Durchlauf' ist.",
               wirkungslos: true };
    }
    var ist = String(((aufgabe || {}).geplant_sprint) || "").trim();
    if (ist === String(n)) {
      return { text: "steht auf " + n, titel: "Diese Aufgabe ist bereits auf Sprint " + n
               + " terminiert. Ein Klick aendert nichts und committet nichts.",
               wirkungslos: true };
    }
    return { text: "→ Sprint " + n,
             titel: "Terminiert diese Aufgabe auf Sprint " + n
             + " (setzt geplant_sprint; prio bleibt unberuehrt).",
             wirkungslos: false };
  }

  /** SWR-146 (platform/T-0016 DoD 2/3): der Text eines Cockpit-Feldes je Zustand.
   *
   * ⚠ **Die EINE Stelle in JavaScript.** Bis Sprint 16 stand die Regel *"null heisst keine
   * Daten, 0 heisst 0"* an DREI Stellen in `cockpitKarte` inline — jede sachlich richtig,
   * und genau das war der Befund: vier Formulierungen eines Begriffs, deren
   * Auseinanderdriften niemandem auffaellt (B033, der Preis von SWR-131).
   *
   * ⚠ **Der Zustand wird hier NICHT hergeleitet, sondern gelesen.** Er kommt aus
   * `payload.zustaende[feld]` und damit aus `aggregation._zustand` — derselben Funktion,
   * aus der das Dashboard seine Zustaende nimmt. Eine zweite Herleitung in JavaScript
   * waere ein NEUER B033-Fall statt einer Reparatur; das steht so in `platform/T-0016`
   * und ist der Grund, warum DoD 1 (die Vertragsfrage) vor DoD 2 kam.
   *
   * ⚠ **Die Wortlaute sind die von Sprint 3 bis 16, Zeichen fuer Zeichen.** DoD 3 verlangt
   * die Migration OHNE Verhaltensaenderung: die drei Stellen zeigen heute das Richtige,
   * und eine Migration, die dabei eine Anzeige veraendert, hat einen Fehler gemacht. Die
   * Texte stehen deshalb als Tabelle da und sind nicht "vereinheitlicht" worden — eine
   * Vereinheitlichung waere eine Verhaltensaenderung mit gutem Gewissen.
   */
  var COCKPIT_TEXTE = {
    "letzte_baseline": {
      nicht_geliefert: KEINE_DATEN, echte_null: "noch keine" },
    "team.letzter_digest": {
      nicht_geliefert: "Digest: " + KEINE_DATEN, echte_null: "noch kein Digest" },
    "kpi": {
      nicht_geliefert: "KPI: " + KEINE_DATEN, echte_null: null }
  };

  function cockpitFeldText(feld, zustand, wert) {
    var texte = COCKPIT_TEXTE[feld];
    if (!texte) return KEINE_DATEN;   // unbekanntes Feld: nicht raten (wie `feldText`)
    if (zustand === "echte_null") return texte.echte_null;
    // ⚠⚠ **Nur `wert` liefert einen Wert — alles andere ist `nicht_geliefert`.**
    //
    // Der erste Entwurf dieser Funktion fragte `if (zustand === "nicht_geliefert" ||
    // !zustand)` und fiel bei jedem UNBEKANNTEN Zustand bis `String(wert)` durch. Bei
    // einem unvollstaendigen Payload stand damit "undefined" auf dem Schirm — genau der
    // Fehler, den der Kommentar in `feldText` seit SWR-135 beschreibt, drei Funktionen
    // weiter oben in derselben Datei.
    //
    // > **Eine Warnung, die im Nachbarcode steht, verhindert den Fehler nicht — die
    // > Zusicherung, die sie messbar macht, tut es.**
    //
    // Gefunden hat es `test_..._ein_FEHLENDER_Zustand_gilt_als_nicht_geliefert`, und zwar
    // beim ERSTEN Lauf. Die Pruefung ist deshalb wie in `feldText` formuliert: die
    // geschlossene Menge entscheidet, nicht ihre Verneinung.
    if (zustand !== "wert") return texte.nicht_geliefert;
    return String(wert);
  }

  // --------------------------------------------------------------------------
  // SWR-148 (team-mail/T-0004): Widgets — Ergebnisse, nicht Zustaende.
  // --------------------------------------------------------------------------

  //: Mindesthoehe eines Klickziels in Pixeln. 44 ist die gaengige Empfehlung fuer
  //: Fingerbedienung; der Auftraggeber hat „Touchscreen geeignet" ausdruecklich verlangt.
  //: ⚠ Die Zahl steht HIER und nicht nur im CSS, damit ein Test sie halten kann — eine
  //: Zusage „touch-geeignet" ohne pruefbare Zahl ist eine Behauptung (SWR-125).
  var TOUCH_MIN_PX = 44;

  var TAKT_TITEL = { tag: "Tag", woche: "Woche", monat: "Monat" };

  /** Was zeigt eine Widget-Zeile? — `{titel, text, zustand, grund}`.
   *
   * Dieselbe Vertragsregel wie `feldText` (SWR-135): `echte_null` ist eine `0`,
   * `nicht_geliefert` ist „keine Daten" und **nie** eine `0`. Neu ist nur der **Grund**:
   * bei einem Widget ist „warum nichts da ist" die eigentliche Nachricht.
   *
   * ⚠ Der Grund wird **angezeigt und nicht verschluckt**. „Nicht eingerichtet" kann der
   * Mensch aendern, „noch keiner erstellt" muss er abwarten — zwei verschiedene Handlungen
   * hinter demselben leeren Feld. Ohne den Grund waeren beide dasselbe Nichts.
   */
  function widgetZeile(eintrag) {
    eintrag = eintrag || {};
    var titel = TAKT_TITEL[eintrag.takt] || eintrag.takt || "";
    if (eintrag.zustand === "nicht_geliefert") {
      return { titel: titel, text: KEINE_DATEN, zustand: eintrag.zustand,
               grund: eintrag.grund || "" };
    }
    var teile = [];
    if (eintrag.datum) teile.push(eintrag.datum);
    if (eintrag.mails !== null && eintrag.mails !== undefined) {
      teile.push(eintrag.mails + " Mails");
    }
    // Die Reaktionspunkte tragen ihren EIGENEN Zustand: eine Rubrik, die fehlt, ist nicht
    // dasselbe wie eine Rubrik mit null Punkten. „0 zu tun" ist ein Ergebnis.
    if (eintrag.reaktion_zustand === "nicht_geliefert") {
      teile.push("Reaktion: " + KEINE_DATEN);
    } else if (eintrag.reaktion !== null && eintrag.reaktion !== undefined) {
      teile.push(eintrag.reaktion + "× Blick oder Reaktion");
    }
    return { titel: titel, text: teile.join(" · ") || KEINE_DATEN,
             zustand: eintrag.zustand, grund: eintrag.grund || "" };
  }

  /** Ist dieses Widget vollstaendig genug, um angezeigt zu werden?
   *
   * ⚠ **`auftrag` ist Pflicht.** Der Wunsch lautete: *„jedes widget soll eine beschreibung
   * als Auftrag erhalten"*. Ein Widget ohne Auftrag zu zeigen hiesse, den Wunsch zur Bitte
   * zu machen — und die Regel waere nach zwei Teams wieder weg. Fehlt er, erscheint das
   * Widget **nicht** und der Mangel wird gemeldet (nicht still uebergangen, SWR-114).
   */
  function widgetVollstaendig(w) {
    w = w || {};
    return !!(w.id && w.titel && String(w.auftrag || "").trim() && w.ziel);
  }

  /** Was fehlt diesem Widget? `[]`, wenn nichts fehlt — fuer eine Meldung, die den Mangel nennt. */
  function widgetMaengel(w) {
    w = w || {};
    var pflicht = [["id", w.id], ["titel", w.titel],
                   ["auftrag", String(w.auftrag || "").trim()], ["ziel", w.ziel]];
    return pflicht.filter(function (p) { return !p[1]; }).map(function (p) { return p[0]; });
  }


  // ---------- Dashboard-Konfiguration (SWR-151, projects/p11/T-0011) ----------

  /** Der Schluessel im Browser-Speicher. Eine Stelle, damit Lesen und Schreiben nicht
   *  auseinanderlaufen koennen. */
  var DASHBOARD_KONFIG_SCHLUESSEL = "mc_dashboard_widgets";

  /** Die leere Konfiguration — „nie angefasst". */
  function konfigLeer() { return { versteckt: [], reihenfolge: [] }; }

  /** Konfiguration aus dem Rohtext des Browser-Speichers — IMMER ein gueltiges Objekt.
   *
   * ⚠ **Kaputter Inhalt ergibt den Standard und keinen Fehler.** Der Speicher ist
   * ausserhalb unserer Reichweite: eine aeltere Fassung, ein halber Schreibvorgang, ein
   * Mensch mit den Entwicklerwerkzeugen. Ein Wurf hier haette das ganze Dashboard
   * angehalten — *eine Ansicht, die an ihrer eigenen Voreinstellung stirbt, ist schlimmer
   * als eine ohne Voreinstellung.*
   *
   * ⚠ Es wird **feldweise** geprueft und nicht „ist es ein Objekt". Ein `versteckt`, das
   * eine Zeichenkette ist, wuerde sonst als Liste durchgereicht und `indexOf` faende
   * Teilzeichenketten — ein Projekt `p1` waere versteckt, weil `p11` im Text steht.
   */
  function konfigLesen(roh) {
    var k = konfigLeer();
    if (!roh) return k;
    var o;
    try { o = JSON.parse(String(roh)); } catch (e) { return k; }
    if (!o || typeof o !== "object") return k;
    if (Array.isArray(o.versteckt)) {
      k.versteckt = o.versteckt.filter(function (x) { return typeof x === "string" && x; });
    }
    if (Array.isArray(o.reihenfolge)) {
      k.reihenfolge = o.reihenfolge.filter(function (x) { return typeof x === "string" && x; });
    }
    return k;
  }

  /** Konfiguration als Text fuer den Speicher. */
  function konfigSchreiben(k) {
    var s = k || konfigLeer();
    return JSON.stringify({ versteckt: s.versteckt || [], reihenfolge: s.reihenfolge || [] });
  }

  /** Widgets nach Konfiguration ordnen und trennen.
   *
   * Rueckgabe: `{ sichtbar: [...], versteckt: [...] }` — **beide** Listen, nie nur die
   * eine. Der Aufrufer soll sagen koennen, was er nicht zeigt.
   *
   * ⚠⚠ **`versteckt` ist eine Ausschlussliste und keine Auswahlliste, und das ist die
   * bestimmende Entscheidung dieser Funktion.** Bei einer Auswahlliste waere ein Widget,
   * das ein Team NEU anbietet, beim naechsten Aufruf unsichtbar — und niemand wuesste,
   * dass es existiert.
   *
   * > **Eine gespeicherte Auswahl altert gegen einen wachsenden Bestand: sie sagt „zeig
   * > diese", und was danach dazukommt, faellt lautlos aus der Ansicht.**
   *
   * ⚠ Nicht genannte Widgets behalten die **Reihenfolge des Servers** und stehen HINTER
   * den genannten. Sie ans Ende zu stellen ist eine Entscheidung: vorn stuenden sie ueber
   * einer Anordnung, die der Mensch bewusst gesetzt hat.
   */
  function widgetsOrdnen(widgets, konfig) {
    var liste = Array.isArray(widgets) ? widgets.slice() : [];
    var k = konfig || konfigLeer();
    var versteckt = k.versteckt || [], reihenfolge = k.reihenfolge || [];
    var raus = { sichtbar: [], versteckt: [] };
    var offen = [];
    liste.forEach(function (w) {
      if (versteckt.indexOf(widgetSchluessel(w)) >= 0) raus.versteckt.push(w);
      else offen.push(w);
    });
    var genannt = [];
    reihenfolge.forEach(function (name) {
      offen.forEach(function (w) {
        if (widgetSchluessel(w) === name && genannt.indexOf(w) < 0) genannt.push(w);
      });
    });
    raus.sichtbar = genannt.concat(offen.filter(function (w) { return genannt.indexOf(w) < 0; }));
    return raus;
  }

  /** Die Kennung eines Widgets — **eine** Stelle, an der sie entsteht.
   *
   * ⚠ Ein Team bietet hoechstens ein Widget an (`widget.yaml` je Team), also ist das
   * Projekt die Kennung. Stuende sie an drei Stellen, waere sie irgendwann an zweien der
   * Titel — und der Titel aendert sich, waehrend die Konfiguration bleibt.
   */
  function widgetSchluessel(w) { return String((w && w.projekt) || ""); }

  /** Ein Widget aus- oder einblenden. Gibt eine NEUE Konfiguration zurueck. */
  function konfigUmschalten(konfig, schluessel) {
    var k = konfigLesen(konfigSchreiben(konfig));
    var i = k.versteckt.indexOf(String(schluessel));
    if (i >= 0) k.versteckt.splice(i, 1); else k.versteckt.push(String(schluessel));
    return k;
  }

  /** Ein Widget um eine Stelle verschieben (`-1` hoch, `+1` runter).
   *
   * ⚠ Die Reihenfolge wird aus der **aktuell sichtbaren** Liste neu geschrieben und nicht
   * in der gespeicherten fortgeschrieben. Sonst haette eine Konfiguration von gestern
   * Namen darin, die es nicht mehr gibt, und ein Schritt „hoch" spraenge ueber ein
   * unsichtbares Loch.
   */
  function konfigVerschieben(konfig, sichtbar, schluessel, schritt) {
    var namen = (sichtbar || []).map(widgetSchluessel);
    var i = namen.indexOf(String(schluessel));
    var ziel = i + (schritt < 0 ? -1 : 1);
    if (i < 0 || ziel < 0 || ziel >= namen.length) return konfigLesen(konfigSchreiben(konfig));
    namen.splice(ziel, 0, namen.splice(i, 1)[0]);
    var k = konfigLesen(konfigSchreiben(konfig));
    k.reihenfolge = namen;
    return k;
  }

  /** Der Satz ueber das, was NICHT zu sehen ist — leer, wenn nichts versteckt ist.
   *
   * ⚠⚠ **Das ist die Antwort auf den Einwand, mit dem SWR-133 die Persistenz ABGELEHNT
   * hat:** *„Ein Zustand, der einen Neustart ueberlebt, muesste beim Wiedersehen erklaert
   * werden — sonst fehlt eine Gruppe und niemand weiss, warum."* Der Einwand ist richtig
   * und gilt hier genauso; er verbietet die Persistenz aber nicht, er verlangt die
   * **Erklaerung**. Sie steht deshalb im Kopf der Ansicht und nicht in einem Menue, das
   * man aufklappen muss.
   */
  function verstecktSatz(anzahl) {
    var n = Number(anzahl) || 0;
    if (n <= 0) return "";
    return n === 1
      ? "1 Widget ist durch deine Auswahl ausgeblendet."
      : n + " Widgets sind durch deine Auswahl ausgeblendet.";
  }

  return { widgetZeile: widgetZeile, widgetVollstaendig: widgetVollstaendig,
           widgetMaengel: widgetMaengel, TOUCH_MIN_PX: TOUCH_MIN_PX,
           feldText: feldText, kachelFelder: kachelFelder,
           terminierKnopf: terminierKnopf,
           cockpitFeldText: cockpitFeldText, COCKPIT_TEXTE: COCKPIT_TEXTE,
           fuerDichAbschnitte: fuerDichAbschnitte,
           FUER_DICH_LEER_ENTSCHEIDUNGEN: FUER_DICH_LEER_ENTSCHEIDUNGEN,
           FUER_DICH_LEER_HANDLUNGEN: FUER_DICH_LEER_HANDLUNGEN,
           dashboardGruppen: dashboardGruppen, KEINE_DATEN: KEINE_DATEN,
           istGruppeOffen: istGruppeOffen,
           urheber: urheber, beitragKopf: beitragKopf, istWiederOffen: istWiederOffen,
           verlauf: verlauf, sortiereBriefe: sortiereBriefe,
           briefIdAusFehler: briefIdAusFehler,
           sortiereAufgaben: sortiereAufgaben, aufgabenNachRolle: aufgabenNachRolle,
           gruppenTitel: gruppenTitel, OHNE_ROLLE: OHNE_ROLLE,
           DASHBOARD_KONFIG_SCHLUESSEL: DASHBOARD_KONFIG_SCHLUESSEL,
           konfigLeer: konfigLeer, konfigLesen: konfigLesen,
           konfigSchreiben: konfigSchreiben, widgetsOrdnen: widgetsOrdnen,
           widgetSchluessel: widgetSchluessel,
           konfigUmschalten: konfigUmschalten,
           konfigVerschieben: konfigVerschieben,
           verstecktSatz: verstecktSatz,
           ticketRoute: ticketRoute, textRefAnnahme: textRefAnnahme,
           TICKET_ROUTE_PRAEFIX: TICKET_ROUTE_PRAEFIX };
})();

// Ein Modul fuer die Teststrecke, eine globale Variable fuer den Browser (ADR-002: kein
// Build, also kein Bundler, der das fuer uns entscheidet).
if (typeof module === "object" && module.exports) { module.exports = Regeln; }
else if (typeof window === "object") { window.Regeln = Regeln; }
