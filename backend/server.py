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
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import aggregation, inbox, mailer  # noqa: E402

_PLATFORM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _code_stand():
    """SWR-047 (P3): aktueller Code-Stand des platform-Repos (git, frisch je Aufruf)."""
    try:
        lauf = subprocess.run(["git", "-C", _PLATFORM_DIR, "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=5)
        return lauf.stdout.strip() or "unbekannt"
    except OSError:
        return "unbekannt"


PROZESS_STAND = _code_stand()  # beim Prozessstart eingefroren
GESTARTET = datetime.now(timezone.utc).isoformat(timespec="seconds")

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

    # ---------- Routen ----------
    def do_GET(self):
        try:
            teile = urlsplit(self.path)
            pfad = teile.path
            projekt = (parse_qs(teile.query).get("projekt") or ["p0"])[0]
            wurzel = type(self).wurzel
            if pfad == "/api/projekte":  # SWR-025
                return self._json(200, {"projekte": aggregation.projekte(wurzel)})
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
            if pfad == "/api/inbox/historie":  # SWR-042 (P3): entschiedene DRs
                return self._json(200, inbox.historie(wurzel))
            if pfad == "/api/version":  # SWR-047 (P3): Prozess- vs. Code-Stand
                return self._json(200, {"prozess_stand": PROZESS_STAND,
                                        "code_stand": _code_stand(),
                                        "gestartet": GESTARTET})
            if pfad.startswith("/api/"):
                return self._json(404, {"fehler": "unbekannter Endpunkt"})
            return self._statisch(pfad)
        except ValueError as e:  # unbekanntes Projekt (SWR-025)
            return self._json(404, {"fehler": str(e)[:400]})
        except Exception as e:  # noqa: BLE001
            return self._json(500, {"fehler": str(e)[:400]})

    def do_POST(self):
        m = re.fullmatch(r"/api/inbox/(T-\d{4})/decision", self.path)
        if not m:
            return self._json(404, {"fehler": "unbekannter Endpunkt"})
        try:
            laenge = int(self.headers.get("Content-Length", "0"))
            daten = json.loads(self.rfile.read(laenge).decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"fehler": "ungültiger JSON-Body"})
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


def start(wurzel, host="127.0.0.1", port=8080):
    """Server starten (blockierend); für Tests: Rückgabe des Serverobjekts via Thread."""
    Api.wurzel = os.path.abspath(wurzel)
    server = ThreadingHTTPServer((host, port), Api)
    return server


def main():
    p = argparse.ArgumentParser(description="Backend-MVP Mission Control v1 (T-0032)")
    p.add_argument("--repos", default=".", help="Wurzel mit process/, platform/, p0/")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    a = p.parse_args()
    server = start(a.repos, a.host, a.port)
    print(f"Mission Control v1: http://{a.host}:{a.port}/ (Wurzel {os.path.abspath(a.repos)})")
    server.serve_forever()


if __name__ == "__main__":
    main()
