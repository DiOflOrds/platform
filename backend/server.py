#!/usr/bin/env python3
"""BCK-Server (SWR-020/022/024; ADR-001): HTTP-API + statisches Frontend.
Standardbibliothek, kein eigener Zustand — jede Anfrage liest frisch aus der
Git-Arbeitskopie. Start: python platform/backend/server.py --repos <wurzel>
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import (aggregation, briefkasten, inbox, mailer, pool,  # noqa: E402
                     session, sprint, teams, tickets, widgets)


def schreibschutz_pruefen(client_ip, pin_header):
    """SWR-048 (P4, ADR-006): None = erlaubt, sonst deutsche Fehlermeldung (403).
    localhost braucht keine PIN; remote nur mit korrekter MC_PIN; ohne gesetzte
    MC_PIN sind Remote-Schreibzugriffe komplett gesperrt (sicherer Default)."""
    import hmac
    if client_ip in ("127.0.0.1", "::1", "localhost"):
        return None
    konfiguriert = os.environ.get("MC_PIN", "")
    if not konfiguriert:
        return ("Remote-Schreibzugriffe sind gesperrt: auf dem Server ist keine "
                "MC_PIN gesetzt (setx MC_PIN <PIN>, Server neu starten — Runbook Kap. 10).")
    if not pin_header or not hmac.compare_digest(str(pin_header), konfiguriert):
        return "PIN fehlt oder ist falsch — bitte die PIN im Kopfbereich eingeben (SWR-049)."
    return None

_PLATFORM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _code_stand():
    """SWR-047 (P3): aktueller Code-Stand des platform-Repos (git, frisch je Aufruf)."""
    try:
        lauf = subprocess.run(["git", "-C", _PLATFORM_DIR, "rev-parse", "--short", "HEAD"],
                              capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", timeout=5)
        return lauf.stdout.strip() or "unbekannt"
    except OSError:
        return "unbekannt"


PROZESS_STAND = _code_stand()  # beim Prozessstart eingefroren
GESTARTET = datetime.now(timezone.utc).isoformat(timespec="seconds")
NEUSTART_CODE = 42  # SWR-061: Startskripte starten bei diesem Code neu
SCHLEIFEN_MARKER = "MC_NEUSTART_SCHLEIFE"  # SWR-073: von mission-control[-lan].cmd gesetzt


class _Zaehler:
    """Zählt gerade bediente Anfragen (SWR-073: nie mitten im Request neu starten)."""

    def __init__(self):
        self.wert = 0
        self.sperre = threading.Lock()

    def __enter__(self):
        with self.sperre:
            self.wert += 1

    def __exit__(self, *_):
        with self.sperre:
            self.wert -= 1

    def leer(self):
        with self.sperre:
            return self.wert == 0


_laufende = _Zaehler()

# platform/N-0002: Abbrüche der Gegenseite sind Normalbetrieb, kein Serverfehler.
_ABBRUCH = (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)


def verbindungsabbruch(fehler):
    """platform/N-0002: True, wenn der Fehler nur ein Verbindungsabbruch der
    Gegenseite ist (reine Prüffunktion, ohne Seiteneffekte — testbar)."""
    return isinstance(fehler, _ABBRUCH)


def selbst_neustart_noetig(prozess_stand, aktueller_stand, vorheriger_fund,
                           schleife_aktiv, ruhig):
    """SWR-073: reine Entscheidungsfunktion (testbar, ohne Seiteneffekte).

    Neu gestartet wird nur, wenn ein Startskript den Neustart auffängt
    (`schleife_aktiv`), der Code auf der Platte von diesem Prozess abweicht,
    derselbe neue Stand schon beim vorigen Durchlauf gesehen wurde (Entprellen —
    ein Sprint schreibt viele Dateien) und gerade keine Anfrage läuft (`ruhig`).
    """
    if not schleife_aktiv or not aktueller_stand or aktueller_stand == "unbekannt":
        return False
    if aktueller_stand == prozess_stand:
        return False
    return aktueller_stand == vorheriger_fund and ruhig


def _neustart_wache(intervall=20, austritt=None, stand=_code_stand, ruhig=None):
    """SWR-073: Hintergrundwache — beendet den Prozess mit 42, sobald neuer Code
    auf der Platte liegt. Alles injizierbar, damit Tests ohne echten Exit laufen."""
    austritt = austritt or (lambda: os._exit(NEUSTART_CODE))
    ruhig = ruhig or _laufende.leer
    vorher = ""
    schleife = os.environ.get(SCHLEIFEN_MARKER) == "1"
    while True:
        jetzt = stand()
        if selbst_neustart_noetig(PROZESS_STAND, jetzt, vorher, schleife, ruhig()):
            print(f"[backend] Neuer Code auf der Platte ({jetzt}) — Server startet "
                  f"selbstständig neu (SWR-073).", flush=True)
            return austritt()
        vorher = jetzt
        time.sleep(intervall)

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml", ".webmanifest": "application/manifest+json"}


class Api(BaseHTTPRequestHandler):
    wurzel = "."          # wird von start()/main() gesetzt
    protokoll = print     # testbar

    # ---------- Hilfen ----------
    def _json(self, status, daten):
        body = json.dumps(daten, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _statisch(self, pfad):
        pfad = "index.html" if pfad in ("", "/") else pfad.lstrip("/")
        voll = os.path.normpath(os.path.join(STATIC, pfad))
        if not voll.startswith(STATIC) or not os.path.isfile(voll):
            return self._json(404, {"fehler": "nicht gefunden"})
        daten = open(voll, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(os.path.splitext(voll)[1],
                                                  "application/octet-stream"))
        self.send_header("Content-Length", str(len(daten)))
        self.end_headers()
        self.wfile.write(daten)

    def log_message(self, fmt, *args):  # Ruhe im Testlauf; Betrieb loggt über protokoll
        type(self).protokoll("[backend] " + fmt % args)

    def handle_one_request(self):
        """SWR-073: laufende Anfragen zählen — die Neustart-Wache wartet, bis Ruhe ist.

        platform/N-0002: Legt die Gegenseite auf (Handy sperrt den Bildschirm, Tab
        zu, WLAN weg), wirft der Socket ConnectionResetError o. ä. Das ist
        Normalbetrieb und kein Serverfehler — eine Logzeile statt Traceback.
        """
        with _laufende:
            try:
                return BaseHTTPRequestHandler.handle_one_request(self)
            except _ABBRUCH as fehler:
                self.close_connection = True
                type(self).protokoll(
                    "[backend] Verbindung zu %s vorzeitig beendet (%s) — "
                    "kein Fehler, Anfrage verworfen."
                    % (self.client_address[0], type(fehler).__name__))
                return None

    # ---------- Routen ----------
    def do_GET(self):
        try:
            teile = urlsplit(self.path)
            pfad = teile.path
            projekt = (parse_qs(teile.query).get("projekt") or ["p0"])[0]
            wurzel = type(self).wurzel
            if pfad == "/api/projekte":  # SWR-025
                return self._json(200, {"projekte": aggregation.projekte(wurzel)})
            if pfad == "/api/navigation":  # SWR-082 (pm/T-0012): Gruppen für den Kopfbereich
                return self._json(200, aggregation.navigation(wurzel))
            if pfad == "/api/uebersicht":  # SWR-026
                return self._json(200, aggregation.uebersicht(wurzel))
            if pfad == "/api/board":
                return self._json(200, aggregation.lade_board(wurzel, projekt))
            if pfad == "/api/reports":
                return self._json(200, aggregation.lade_reports(wurzel, projekt))
            if pfad == "/api/kpi":
                return self._json(200, aggregation.lade_kpi(wurzel, projekt))
            if pfad == "/api/requirements":  # SWR-030
                return self._json(200, aggregation.lade_requirements(wurzel, projekt))
            if pfad == "/api/pool":  # SWR-086 (pm/N-0020): Projekt-Pool read-only
                return self._json(200, aggregation.lade_pool(wurzel))
            if pfad == "/api/verifikation":  # SWR-031
                return self._json(200, aggregation.lade_verifikation(wurzel, projekt))
            if pfad == "/api/baselines":  # SWR-032
                return self._json(200, aggregation.lade_baselines(wurzel))
            if pfad == "/api/inbox":  # SWR-027: alle Projekte
                return self._json(200, inbox.liste(wurzel))
            if pfad == "/api/nutzer":  # SWR-037: Registry (read-only)
                return self._json(200, {"nutzer": inbox.lade_nutzer(wurzel)})
            if pfad == "/api/ticket":  # SWR-040 (P3): Einzelticket für die Detailansicht
                tid = (parse_qs(teile.query).get("id") or [""])[0]
                return self._json(200, aggregation.lade_ticket(wurzel, projekt, tid))
            if pfad == "/api/ticket/editor":  # SWR-077/081 (P10): Formularzustand, PIN-frei
                tid = (parse_qs(teile.query).get("id") or [""])[0]
                try:
                    return self._json(200, tickets.editor_daten(wurzel, projekt, tid))
                except tickets.TicketFehler as e:
                    return self._json(e.code, {"fehler": str(e)})
            # SWR-138 (pm/T-0052, Teil e aus pm/T-0038 / Brief pm/N-0031): der zweite
            # Abschnitt neben der Inbox — Tickets, bei denen der Mensch **handeln** statt
            # entscheiden soll. ⚠ Eigene Route und **keine** Erweiterung von `/api/inbox`:
            # an der Inbox-Liste hängen die Entscheidungsknöpfe (SWR-042), und eine Liste,
            # in der manche Einträge Knöpfe haben und manche nicht, wäre eine Fläche mit
            # zwei Bedeutungen (B033). Die Daten sind trotzdem **eine** Quelle: die Route
            # liefert die Teilmenge von `wartet_auf_mensch` ohne die DRs.
            if pfad == "/api/fuer-dich":
                return self._json(200, {"handlungen":
                                        aggregation.fuer_dich_handlungen(wurzel)})
            if pfad == "/api/inbox/historie":  # SWR-042 (P3): entschiedene DRs
                return self._json(200, inbox.historie(wurzel))
            if pfad == "/api/version":  # SWR-047 (P3): Prozess- vs. Code-Stand
                return self._json(200, {"prozess_stand": PROZESS_STAND,
                                        "code_stand": _code_stand(),
                                        "gestartet": GESTARTET})
            if pfad == "/api/cockpit":  # SWR-046 (P3): alle Projekte auf einen Blick
                return self._json(200, aggregation.cockpit_alle(wurzel))
            # SWR-135 (projects/p11/T-0010): Kompaktkacheln fürs Widget-Dashboard.
            # ⚠ Eigene Route und **keine** Erweiterung von `/api/cockpit`: der Widget-
            # Vertrag prüft seit B066 die Feldliste von `cockpit`, und ein zusätzlicher
            # Schlüssel dort wäre ein Vertragsbruch. Die Route ist eine andere **Form**
            # derselben Daten, kein zweiter Erhebungsweg — `dashboard` ruft `cockpit_alle`.
            if pfad == "/api/dashboard":
                return self._json(200, aggregation.dashboard(wurzel))
            # SWR-148 (team-mail/T-0004): die Widgets des Dashboards — Ergebnisse der
            # Teams, nicht Zustaende der Projekte.
            #
            # ⚠ Diese Route liefert bewusst KEINE Mailinhalte: Datum, Zahlen und den
            # Auftrag, aber keinen Betreff, keinen Absender, keinen Link. Der Inhalt liegt
            # hinter dem PIN-Leser (`/api/team/...`, SWR-053) und bleibt dort — Mission
            # Control ist per `mission-control-lan.cmd` auch im LAN erreichbar, und eine
            # ungeschuetzte Route mit Mailbetreffs waere genau der Fall, den das PIN-Gate
            # verhindern soll.
            if pfad == "/api/widgets":
                return self._json(200, widgets.widgets(wurzel))
            if pfad == "/api/session":  # SWR-102 (pm/T-0040): was die letzte Session tat
                return self._json(200, session.stand(wurzel))
            if pfad == "/api/sprint":  # SWR-103 (pm/T-0016, pm/D006): Sprint-Workflow
                return self._json(200, sprint.plan(wurzel))
            if pfad == "/api/briefkasten":  # SWR-050 (P4): Konversation lesen
                return self._json(200, briefkasten.liste(wurzel, projekt))
            if pfad.startswith("/api/team"):  # SWR-053 (P7): PIN-Lesegate für
                # sensible Team-Inhalte — remote nur mit PIN, localhost frei
                sperre = schreibschutz_pruefen(self.client_address[0],
                                               self.headers.get("X-MC-PIN"))
                if sperre:
                    return self._json(403, {"fehler": sperre})
                try:
                    if pfad == "/api/team":
                        return self._json(200, teams.team_daten(wurzel, projekt))
                    if pfad == "/api/team/digest":
                        name = (parse_qs(teile.query).get("name") or [""])[0]
                        return self._json(200, teams.digest_inhalt(wurzel, projekt, name))
                    if pfad == "/api/team/ollama-modelle":  # SWR-071 (P8-E4)
                        return self._json(200, teams.ollama_modelle(wurzel, projekt))
                    if pfad == "/api/team/digest-vorschau":  # SWR-090 (pm/T-0025)
                        return self._json(200, teams.digest_vorschau(wurzel, projekt))
                    # SWR-160 (projects/p11/T-0013): der INHALT eines Widgets.
                    #
                    # ⚠⚠ Die Route steht INNERHALB des `/api/team`-Zweigs und damit hinter
                    # dem PIN-Leser — nicht daneben mit eigener Pruefung. Ein zweites Gate
                    # neben dem vorhandenen waere B033 an der empfindlichsten Stelle: zwei
                    # Zugriffsregeln, die auseinanderlaufen koennen, ohne dass etwas rot
                    # wird. Ein Test haelt ueber den Syntaxbaum fest, dass
                    # `widgets.widget_inhalt` NUR hier aufgerufen wird.
                    if pfad == "/api/team/widget-inhalt":
                        q = parse_qs(teile.query)
                        name = (q.get("name") or [projekt])[0]
                        takt = (q.get("takt") or [""])[0]
                        inhalt = widgets.widget_inhalt(wurzel, name, takt)
                        if inhalt is None:
                            return self._json(404, {"fehler": f"Team '{name}' bietet kein "
                                                              f"Widget an (kein widget.yaml)."})
                        return self._json(200, inhalt)
                except teams.TeamFehler as e:
                    return self._json(e.code, {"fehler": str(e)})
            if pfad == "/architektur.svg":  # SWR-045 (P3): generiertes Architekturbild
                svg = os.path.join(_PLATFORM_DIR, "architecture", "architektur.svg")
                if not os.path.isfile(svg):
                    return self._json(404, {"fehler": "architektur.svg fehlt — Generator ausführen"})
                daten = open(svg, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml")
                self.send_header("Content-Length", str(len(daten)))
                self.end_headers()
                self.wfile.write(daten)
                return None
            if pfad.startswith("/api/"):
                return self._json(404, {"fehler": "unbekannter Endpunkt"})
            return self._statisch(pfad)
        except ValueError as e:  # unbekanntes Projekt (SWR-025)
            return self._json(404, {"fehler": str(e)[:400]})
        except Exception as e:  # noqa: BLE001
            return self._json(500, {"fehler": str(e)[:400]})

    def do_POST(self):
        # SWR-048 (P4): Schreibschutz für alle POST-Endpunkte
        sperre = schreibschutz_pruefen(self.client_address[0], self.headers.get("X-MC-PIN"))
        if sperre:
            return self._json(403, {"fehler": sperre})
        try:
            laenge = int(self.headers.get("Content-Length", "0"))
            daten = json.loads(self.rfile.read(laenge).decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"fehler": "ungültiger JSON-Body"})
        if self.path == "/api/neustart":  # SWR-061 (T-0015, pm/N-0002): Neustart per Knopf
            self._json(200, {"ok": True, "meldung": "Server startet neu — die Seite lädt gleich neu."})
            def _ende():
                os._exit(42)  # Startskript-Schleife (mission-control[-lan].cmd) startet neu
            threading.Timer(0.5, _ende).start()
            return None
        if self.path == "/api/team/digest-jetzt":  # SWR-063 (P8): Sofort-Zusammenfassung
            try:
                erg = teams.digest_jetzt(type(self).wurzel, daten.get("projekt", ""))
            except teams.TeamFehler as e:
                return self._json(e.code, {"fehler": str(e)})
            return self._json(200, erg)
        if self.path == "/api/team/konfiguration":  # SWR-056 (P7): Eckparameter ändern
            try:
                erg = teams.konfiguration_schreiben(type(self).wurzel,
                                                    daten.get("projekt", ""), daten)
            except teams.TeamFehler as e:
                return self._json(e.code, {"fehler": str(e)})
            return self._json(200, erg)
        if self.path == "/api/ticket":  # SWR-077/078/081 (P10): Ticket ändern (PIN oben geprüft)
            try:
                erg = tickets.speichere(type(self).wurzel, daten.get("projekt", ""),
                                        daten.get("id", ""), daten)
            except tickets.TicketFehler as e:
                return self._json(e.code, {"fehler": str(e)})
            return self._json(200, erg)
        # SWR-144 (pm/T-0065): der Knopf je Zeile der Aufgabenliste. PIN oben geprüft wie
        # jeder Schreibweg. ⚠ Eigene Route und **kein** Sonderfall in `/api/ticket`: dort
        # bringt der Client die Werte mit, hier bringt er **keine** — das ist der ganze
        # Unterschied, an dem die Fingerprint-Begründung von SWR-144 hängt. Ein
        # Feld-Parameter an `/api/ticket` hätte beide Fälle in einen Aufruf gelegt und die
        # Begründung damit unprüfbar gemacht.
        if self.path == "/api/ticket/terminieren":
            try:
                erg = tickets.terminiere(type(self).wurzel, daten.get("projekt", ""),
                                         daten.get("id", ""))
            except tickets.TicketFehler as e:
                return self._json(e.code, {"fehler": str(e)})
            return self._json(200, erg)
        if self.path == "/api/pool":  # SWR-088 (pm/T-0022, Teil "Anlegen"; PIN oben geprüft)
            try:
                erg = pool.kandidat_anlegen(type(self).wurzel, daten.get("kategorie", ""),
                                            daten.get("kandidat", ""),
                                            daten.get("kurzbeschreibung", ""),
                                            daten.get("felder") or {})
            except pool.PoolFehler as e:
                return self._json(e.code, {"fehler": str(e)})
            return self._json(200, erg)
        if self.path == "/api/pool/start":  # SWR-089 (pm/T-0022, Teil "Starten"; PIN oben geprüft)
            try:
                erg = pool.kandidat_starten(type(self).wurzel, daten.get("kandidat", ""))
            except pool.PoolFehler as e:
                return self._json(e.code, {"fehler": str(e)})
            return self._json(200, erg)
        # SWR-147 (pm/T-0063): Gründung VORLEGEN. ⚠ Die Route existiert, weil eine Funktion
        # ohne Aufrufer der Fehlermodus von SWR-122 ist — berechnet und von niemandem
        # gelesen. Sie heißt bewusst nicht `/api/pool/gruenden`: sie gründet nicht.
        if self.path == "/api/pool/gruendung-vorlegen":
            try:
                erg = pool.gruendung_vorlegen(type(self).wurzel, daten.get("team", ""),
                                              daten.get("steckbrief") or {})
            except pool.PoolFehler as e:
                return self._json(e.code, {"fehler": str(e)})
            return self._json(200, erg)
        if self.path == "/api/briefkasten":  # SWR-050 (P4): Nachricht ans Team
            # SWR-126 (pm/T-0059): optionales `brief` hängt an einen bestehenden Brief an.
            # Fehlt es, ist der Aufruf byte-identisch zu vorher — `None` heißt „neu".
            # Die Kennung wird in `briefkasten` geprüft, nicht hier: eine zweite Prüfung
            # daneben wäre B033, und die tiefere ist die, die den Pfad baut.
            try:
                erg = briefkasten.sende(type(self).wurzel, daten.get("projekt", "p0"),
                                        daten.get("text", ""), daten.get("von", "E. John"),
                                        brief=daten.get("brief") or None)
            except briefkasten.BriefkastenFehler as e:
                return self._json(e.code, {"fehler": str(e)})
            return self._json(200, erg)
        m = re.fullmatch(r"/api/inbox/(T-\d{4})/decision", self.path)
        if not m:
            return self._json(404, {"fehler": "unbekannter Endpunkt"})
        projekt = daten.get("projekt", "p0")  # SWR-027
        try:
            ergebnis = inbox.entscheide(type(self).wurzel, m.group(1),
                                        daten.get("option", ""),
                                        daten.get("begruendung", ""),
                                        projekt=projekt,
                                        entscheider=daten.get("entscheider", ""))  # SWR-038
        except inbox.InboxFehler as e:
            return self._json(e.code, {"fehler": str(e)})
        except Exception as e:  # noqa: BLE001
            return self._json(500, {"fehler": str(e)[:400]})
        ergebnis["projekt"] = projekt
        ok, meldung = mailer.sende(
            f"[{projekt}] Entscheidung {ergebnis['entscheidung']} zu {ergebnis['ticket']}",
            f"Option: {ergebnis['option']}\nEntscheider: {ergebnis['entscheider']}\n"
            f"Begründung: {daten.get('begruendung', '—')}\n")
        type(self).protokoll(f"[backend] Mail: {meldung}")
        ergebnis["mail"] = ok
        return self._json(200, ergebnis)


class RuhigerServer(ThreadingHTTPServer):
    """platform/N-0002: Zweite Sicherung — was doch am Handler vorbeikommt (z. B.
    Abbruch beim Aufräumen der Verbindung), wird für Verbindungsabbrüche still
    verworfen. Echte Fehler behalten ihren Traceback."""

    def handle_error(self, request, client_address):
        if verbindungsabbruch(sys.exc_info()[1]):
            return
        ThreadingHTTPServer.handle_error(self, request, client_address)


def start(wurzel, host="127.0.0.1", port=8080):
    """Server starten (blockierend); für Tests: Rückgabe des Serverobjekts via Thread."""
    Api.wurzel = os.path.abspath(wurzel)
    server = RuhigerServer((host, port), Api)
    return server


def main():
    p = argparse.ArgumentParser(description="Backend-MVP Mission Control v1 (T-0032)")
    p.add_argument("--repos", default=".", help="Wurzel mit process/, platform/, p0/")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    a = p.parse_args()
    server = start(a.repos, a.host, a.port)
    print(f"Mission Control v1: http://{a.host}:{a.port}/ (Wurzel {os.path.abspath(a.repos)})")
    if os.environ.get(SCHLEIFEN_MARKER) == "1":  # SWR-073 (pm/N-0010)
        threading.Thread(target=_neustart_wache, daemon=True).start()
        print("[backend] Selbst-Neustart aktiv: neuer Code auf der Platte startet den "
              "Server automatisch neu (SWR-073).")
    server.serve_forever()


if __name__ == "__main__":
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                      "..", "scripts"))
    import konsole
    konsole.sichere_ausgabe()  # platform/T-0009: am Melden nicht sterben
    main()
