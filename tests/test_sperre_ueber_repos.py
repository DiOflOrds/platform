"""Eine Sperre darf ein fremdes Repo nennen (SWR-193, platform/T-0045).

⚠⚠ **Der Befund, aus dem diese Datei entstanden ist, lag nicht im Werkzeug, sondern in
vier Terminierungen.** `promt-team/T-0003` trug viermal den Vermerk *„kein `blocked` — es
fehlt kein Beschluss"*. Das las sich wie eine **Beurteilung der Lage**; gemessen war es
der **einzige Status, den das Werkzeug hergab**: `blocked_by: [pm/T-0077]` wurde als
unbekanntes Ticket abgelehnt, `blocked_by: []` als fehlender Verweis.

> **Eine Begründung, die mit der einzigen möglichen Handlung zusammenfällt, ist von einer
> Rationalisierung nicht zu unterscheiden.** (`L-2026-08-21cc`)

⚠ Die **wichtigste** Zusicherung hier ist die über die dritte Lage: „unbekannt" und
„unerreichbar" sind zwei Antworten, und nur eine darf blockieren. Ohne sie würde
`board.py --check` in einem einzeln ausgecheckten Repo aus einem nicht daliegenden
Nachbarn einen Fehler machen — die Bauart, die `SWR-166` 83 abgebrochene Läufe gekostet
hat.

Ausführung: python -m unittest discover platform/tests
"""
import os
import shutil
import sys
import tempfile
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
import board  # noqa: E402

TICKET = """---
id: {tid}
titel: "Ticket {tid}"
typ: task
prozess: swe3
rolle: dev
sprint: 1
status: {status}
prio: mittel
erstellt: 2026-08-01
{extra}---

## Auftrag

Etwas.
"""


def lege(pfad, tid, status="open", **fm):
    os.makedirs(os.path.join(pfad, "tickets"), exist_ok=True)
    extra = "".join(f"{k}: {v}\n" for k, v in fm.items())
    with open(os.path.join(pfad, "tickets", f"{tid}.md"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write(TICKET.format(tid=tid, status=status, extra=extra))


class QualifizierteSperreTest(unittest.TestCase):
    """Verifiziert: SWR-193."""

    def setUp(self):
        self.wurzel = tempfile.mkdtemp(prefix="swr193-")
        self.pm = os.path.join(self.wurzel, "pm")
        self.team = os.path.join(self.wurzel, "promt-team")
        lege(self.pm, "T-0077")
        lege(self.team, "T-0001")

    def tearDown(self):
        shutil.rmtree(self.wurzel, ignore_errors=True)

    def _fehler(self, tid="T-0002", **fm):
        lege(self.team, tid, **fm)
        tickets, probleme = board.lade_tickets(self.team)
        return probleme + board.validiere_alle(tickets, self.team, git_pruefen=False)

    # --- die Lage, um die es geht ---------------------------------------------

    def test_blocked_mit_fremder_kennung_wird_angenommen(self):
        """⚠⚠ Genau das ging vier Sprints lang nicht."""
        self.assertEqual(self._fehler(status="blocked",
                                      blocked_by="[pm/T-0077]"), [])

    def test_fremde_kennung_neben_lokaler(self):
        self.assertEqual(self._fehler(status="blocked",
                                      blocked_by="[T-0001, pm/T-0077]"), [])

    # --- drei Lagen, und nur EINE ist ein Befund -------------------------------

    def test_einheit_da_ticket_nicht_ist_ein_befund(self):
        fehler = self._fehler(status="blocked", blocked_by="[pm/T-9999]")
        self.assertTrue(any("pm/T-9999" in f for f in fehler), fehler)
        self.assertTrue(any("Einheit pm gefunden" in f for f in fehler), fehler)

    def test_unbekannte_einheit_ist_KEIN_befund(self):
        """⚠ Das Fehlen eines Nachbarn ist eine Aussage ueber die UMGEBUNG."""
        self.assertEqual(self._fehler(status="blocked",
                                      blocked_by="[gibtsnicht/T-0001]"), [])

    def test_ohne_auffindbare_wurzel_KEIN_befund(self):
        """⚠⚠ Der Fall `board.py --check` im einzeln ausgecheckten Repo / in CI.

        Gemessen wird an einem Repo, ueber dem keine zweite Einheit liegt — genau die
        Lage, in der ein Befund eine Aussage ueber die Umgebung waere.
        """
        allein = os.path.join(tempfile.mkdtemp(prefix="swr193-allein-"), "solo")
        try:
            lege(allein, "T-0001", status="blocked", blocked_by="[pm/T-0077]")
            self.assertIsNone(board._org_wurzel(allein),
                              "Vorbedingung verfehlt: hier duerfte keine Wurzel sein")
            tickets, probleme = board.lade_tickets(allein)
            self.assertEqual(
                probleme + board.validiere_alle(tickets, allein, git_pruefen=False), [])
        finally:
            shutil.rmtree(os.path.dirname(allein), ignore_errors=True)

    # --- was sich NICHT aendern darf ------------------------------------------

    def test_nackte_id_bleibt_repo_lokal(self):
        """⚠ Es kommt eine Form DAZU, es wird keine ersetzt — sonst faesst der Bestand an."""
        fehler = self._fehler(status="blocked", blocked_by="[T-0077]")
        self.assertTrue(any("T-0077" in f for f in fehler),
                        f"die nackte ID wird nicht mehr repo-lokal aufgeloest: {fehler}")

    def test_blocked_ohne_verweis_bleibt_abgelehnt(self):
        fehler = self._fehler(status="blocked", blocked_by="[]")
        self.assertTrue(any("blocked erfordert" in f for f in fehler), fehler)

    def test_selbstverweis_bleibt_abgelehnt(self):
        fehler = self._fehler(tid="T-0003", status="blocked", blocked_by="[T-0003]")
        self.assertTrue(any("sich selbst" in f for f in fehler), fehler)

    # --- die Kennungsform ------------------------------------------------------

    def test_muster_trifft_die_form_aus_SWR_087_und_keine_andere(self):
        for gut in ("pm/T-0077", "promt-team/T-0001", "p11/T-0016", "team-mail/T-0003"):
            self.assertTrue(board.QUALIFIZIERTE_REF.match(gut), gut)
        for schlecht in ("T-0077", "pm/T-77", "pm/", "/T-0077", "pm/T-0077/x",
                         "../pm/T-0077", "pm/t-0077"):
            self.assertIsNone(board.QUALIFIZIERTE_REF.match(schlecht), schlecht)

    def test_ein_pfadausbruch_wird_nicht_zur_verzeichnisreise(self):
        """⚠⚠ Ein `..` in einer Kennung darf nie ein Verzeichnis verlassen.

        Der Schutz ist **die Form selbst** und keine zusätzliche Prüfung: `..` trifft
        `QUALIFIZIERTE_REF` nicht, also wird die Kennung gar nicht erst als Repo-Pfad
        gelesen, sondern fällt auf die repo-lokale Auflösung zurück — und dort ist sie
        eine unbekannte ID. **Aus keinem dieser Zeichen wird jemals ein `os.path.join`.**
        """
        for boese in ("../../etc/T-0001", "../pm/T-0077", "/etc/T-0001"):
            with self.subTest(boese=boese):
                self.assertIsNone(board.QUALIFIZIERTE_REF.match(boese),
                                  f"{boese!r} wuerde als Repo-Kennung gelesen")
        fehler = self._fehler(tid="T-0004", status="blocked",
                              blocked_by="[../pm/T-0077]")
        self.assertTrue(any("unbekanntes Ticket" in f for f in fehler), fehler)


class WurzelSucheTest(unittest.TestCase):
    """Verifiziert: SWR-193 — die OBERSTE Ebene, nicht die erste."""

    def setUp(self):
        self.wurzel = tempfile.mkdtemp(prefix="swr193-tiefe-")
        lege(os.path.join(self.wurzel, "pm"), "T-0077")
        lege(os.path.join(self.wurzel, "platform"), "T-0001")
        self.sammel = os.path.join(self.wurzel, board.SAMMEL_REPO)
        for p in ("p10", "p11", "p12"):
            lege(os.path.join(self.sammel, p), "T-0001")

    def tearDown(self):
        shutil.rmtree(self.wurzel, ignore_errors=True)

    def test_aus_dem_sammelrepo_wird_die_org_wurzel_gefunden(self):
        """⚠⚠ Ueber `projects/p11` liegt `projects` mit DREI Einheiten — die erste
        Ebene, die passt, und die falsche: sie kennt `pm` nicht."""
        p11 = os.path.join(self.sammel, "p11")
        self.assertEqual(board._org_wurzel(p11), os.path.abspath(self.wurzel))

    def test_und_deshalb_loest_eine_sperre_aus_p11_auf_pm_auf(self):
        p11 = os.path.join(self.sammel, "p11")
        self.assertEqual(board._pruefe_fremde_sperre("pm/T-0077", p11), [])
        self.assertTrue(board._pruefe_fremde_sperre("pm/T-9999", p11))


if __name__ == "__main__":
    unittest.main()
