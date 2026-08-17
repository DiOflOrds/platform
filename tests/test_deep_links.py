"""Deep-Links auf die Detailseite (SWR-150, projects/p11/T-0012).

⚠⚠ **Der Befund war nicht der fehlende Link, sondern der zweite Bauplatz.** `app.js` hatte
**neun** Stellen, die `"#/ticket/" + projekt + "/" + id` zusammensetzten — und in sieben
davon stand als Beschriftung `x.ref`, also die Kennung **vom Server**.

> **Ein Link, dessen Aufschrift der Server liefert und dessen Ziel die Ansicht
> zusammenbaut, ist zwei Aussagen über dasselbe Ticket. Solange beide gleich sind, merkt es
> niemand.**

Die Gegenprobe steht deshalb **am wirklichen Bestand** und nicht an einer Attrappe: es wird
gemessen, dass Ticketnummern hier tatsächlich mehrfach vorkommen. Eine Gegenprobe, die sich
ihren eigenen Kollisionsfall hinlegt, prüft die Testdatei (`L-2026-08-17ai`).

Ausführung: python -m unittest discover platform/tests
"""
import glob
import os
import re
import sys
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
from backend import aggregation  # noqa: E402
import board  # noqa: E402

_WURZEL = os.path.dirname(os.path.dirname(_HIER))
_APP_JS = os.path.join(_HIER, "..", "backend", "static", "app.js")
_REGELN_JS = os.path.join(_HIER, "..", "backend", "static", "regeln.js")


def _text(pfad):
    with open(pfad, encoding="utf-8") as f:
        return f.read()


class EinBauplatzTest(unittest.TestCase):
    """Verifiziert: SWR-150."""

    def test_app_js_baut_keine_ticketroute_mehr_zusammen(self):
        """⚠⚠ DER Zähltest: 9 Stellen -> 0. Er ist bewusst auf **app.js** begrenzt; eine
        dateiübergreifende Textsuche wäre am Präfix in `regeln.js` rot geworden — der
        Fehlalarm, der am 17.08. viermal aufgelaufen ist. Verifiziert: SWR-150."""
        treffer = re.findall(r'"#/ticket/"', _text(_APP_JS))
        self.assertEqual(len(treffer), 0,
                         f"{len(treffer)} Stelle(n) in app.js setzen die Route noch selbst "
                         f"zusammen — die Kennung kommt vom Server (SWR-087)")

    def test_das_praefix_steht_genau_einmal_und_zwar_in_regeln_js(self):
        """Eine zweite Schreibweise derselben Zeichenkette ist die Bauart aus SWR-131.

        ⚠ **Diese Zusicherung hat ihren eigenen ersten Wurf widerlegt.** Sie zählte das
        Vorkommen der Zeichenkette in der ganzen Datei und wurde `2 != 1` — der zweite
        Treffer war das **Beispiel im Kommentar** darüber (`"pm/T-0002" -> "#/ticket/…"`).
        Ein richtiges Beispiel ist keine zweite Schreibweise.

        > **Eine Textsuche kann eine Erklärung nicht von ihrem Gegenstand unterscheiden —
        > und die Erklärung steht nun einmal genau dort, wo der Gegenstand ist.**

        Das ist derselbe Fehlalarm, der am 17.08. viermal aufgelaufen ist (SWR-141,
        SWR-148). Gemessen wird deshalb die **Zuweisung** im Code und nicht das Wort im
        Text. Verifiziert: SWR-150."""
        code = re.sub(r"(?s)/\*.*?\*/", "", _text(_REGELN_JS))
        code = "\n".join(re.sub(r"//.*$", "", z) for z in code.splitlines())
        self.assertEqual(code.count('"#/ticket/"'), 1,
                         "das Routenpräfix steht mehr als einmal im CODE")
        self.assertRegex(code, r'var\s+TICKET_ROUTE_PRAEFIX\s*=\s*"#/ticket/";')

    def test_app_js_geht_ueber_den_einen_baustein(self):
        """Gegenprobe zum Zähltest: dass die Zusammensetzungen **weg** sind, heißt nicht,
        dass die Links da sind. Verifiziert: SWR-150."""
        app = _text(_APP_JS)
        self.assertIn("function ticketLink(", app)
        self.assertGreaterEqual(app.count("ticketLink("), 7,
                                "die ersetzten Stellen benutzen den Baustein nicht")
        self.assertIn("Regeln.ticketRoute(", app)


class BestandTest(unittest.TestCase):
    """Verifiziert: SWR-150 — die Kollision ist gemessen, nicht angenommen."""

    def _ids_je_projekt(self):
        tr = {}
        for pfad in glob.glob(os.path.join(_WURZEL, "**", "tickets"), recursive=True):
            if ".git" in pfad or "templates" in pfad:
                continue
            repo = os.path.dirname(pfad)
            tickets, _ = board.lade_tickets(repo)
            for t in tickets:
                tr.setdefault(t.get("id"), set()).add(os.path.basename(repo))
        return tr

    def test_ticketnummern_kommen_im_bestand_wirklich_mehrfach_vor(self):
        """⚠ Ohne diese Messung wäre DoD 2 eine Sorge und keine Anforderung.
        Verifiziert: SWR-150."""
        mehrfach = {k: v for k, v in self._ids_je_projekt().items() if len(v) > 1}
        self.assertGreater(len(mehrfach), 1,
                           "keine mehrfach vergebene Nummer im Bestand — dann müsste die "
                           "Begründung von SWR-087 neu geschrieben werden")
        self.assertGreaterEqual(max(len(v) for v in mehrfach.values()), 3)

    def test_ref_vom_server_ist_immer_projekt_und_nummer(self):
        """Die Route hängt an dieser Form; sie hier zu messen ist der Vertrag zwischen
        `aggregation.ref` und `Regeln.ticketRoute`. Verifiziert: SWR-087, SWR-150."""
        muster = re.compile(r"^[A-Za-z0-9_.\-]+/T-\d{4}$")
        for projekt in aggregation.projekte(_WURZEL) or []:
            with self.subTest(projekt=projekt):
                self.assertRegex(aggregation.ref(projekt, "T-0001"), muster)

    def test_ref_ohne_projekt_ergibt_keine_verlinkbare_kennung(self):
        """⚠ Die Gegenprobe an der Quelle: `ref("", id)` gibt die nackte Nummer zurück, und
        genau die darf im Ziel nicht landen. Verifiziert: SWR-150."""
        self.assertEqual(aggregation.ref("", "T-0002"), "T-0002")
        # ... und die Route lehnt sie ab. Geprüft wird die Regel in regeln.js über ihren
        # Quelltext, weil hier kein JS läuft — die ausführende Zusicherung steht in
        # `regeln.test.cjs` ("eine NACKTE Nummer ergibt KEINEN Link").
        self.assertIn("REF_MUSTER", _text(_REGELN_JS))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
