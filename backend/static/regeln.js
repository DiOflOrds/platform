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

  return { urheber: urheber, beitragKopf: beitragKopf, istWiederOffen: istWiederOffen,
           verlauf: verlauf, sortiereBriefe: sortiereBriefe,
           briefIdAusFehler: briefIdAusFehler,
           sortiereAufgaben: sortiereAufgaben, aufgabenNachRolle: aufgabenNachRolle,
           gruppenTitel: gruppenTitel, OHNE_ROLLE: OHNE_ROLLE };
})();

// Ein Modul fuer die Teststrecke, eine globale Variable fuer den Browser (ADR-002: kein
// Build, also kein Bundler, der das fuer uns entscheidet).
if (typeof module === "object" && module.exports) { module.exports = Regeln; }
else if (typeof window === "object") { window.Regeln = Regeln; }
