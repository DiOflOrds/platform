"""Unit-Verifikation DR-Benachrichtigung (P1/T-0013) + Frist-Warnung (P2/T-0007)."""
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import dr_benachrichtigung  # noqa: E402

DR = """---
id: T-0001
titel: "DR: Testfrage"
typ: decision-request
prozess: man3
rolle: pl
sprint: 1
status: open
prio: hoch
blocked_by: []
repo: p0
optionen: [A, B]
frist: {frist}
{extra}erstellt: 2026-08-07
---

Frage?
{body}"""


def _root_mit_dr(frist="2026-08-10", default=None, body=""):
    d = tempfile.mkdtemp()
    repo = os.path.join(d, "p0")
    os.makedirs(os.path.join(repo, "tickets"))
    extra = f"default: {default}\n" if default else ""
    open(os.path.join(repo, "tickets", "T-0001.md"), "w", encoding="utf-8").write(
        DR.format(frist=frist, extra=extra, body=body))
    subprocess.run(["git", "-C", repo, "init", "-q"], check=True)
    return d


class BenachrichtigungTest(unittest.TestCase):
    def test_erfolg_setzt_marker_und_verhindert_doppelversand(self):
        """Versanderfolg setzt beide Marker (Frist überschritten -> auch Warnung);
        der nächste Lauf sendet nichts mehr. Verifiziert: SWR-033, SWR-034."""
        root = _root_mit_dr()
        erg = dr_benachrichtigung.lauf(root, sende=lambda b, t: (True, "ok"))
        self.assertEqual(erg, [("p0", "T-0001", "gesendet"),
                               ("p0", "T-0001", "warnung gesendet")])
        text = open(os.path.join(root, "p0", "tickets", "T-0001.md"), encoding="utf-8").read()
        self.assertIn(dr_benachrichtigung.MARKER, text)
        self.assertIn(dr_benachrichtigung.WARN_MARKER, text)
        self.assertEqual(dr_benachrichtigung.lauf(root, sende=lambda b, t: (True, "ok")), [])

    def test_fehlschlag_ohne_marker_wird_wiederholt(self):
        """Bei Versandfehler bleiben beide Marker aus (Retry beim nächsten Lauf).
        Verifiziert: SWR-033, SWR-034."""
        root = _root_mit_dr()
        erg = dr_benachrichtigung.lauf(root, sende=lambda b, t: (False, "SMTP fehlt"))
        self.assertEqual(erg[0][2], "SMTP fehlt")
        self.assertEqual(erg[1][2], "warnung: SMTP fehlt")
        text = open(os.path.join(root, "p0", "tickets", "T-0001.md"), encoding="utf-8").read()
        self.assertNotIn(dr_benachrichtigung.MARKER, text)
        self.assertNotIn(dr_benachrichtigung.WARN_MARKER, text)
        self.assertEqual(len(dr_benachrichtigung.lauf(root, dry_run=True)), 2)

    def test_mailinhalt_traegt_projekt_und_frist(self):
        """Betreff/Text enthalten Projekt, ID, Titel, Optionen und Frist. Verifiziert: SWR-033."""
        root = _root_mit_dr()
        gesendet = []
        dr_benachrichtigung.lauf(root, sende=lambda b, t: (gesendet.append((b, t)) or (True, "ok")))
        betreff, text = gesendet[0]
        self.assertIn("[p0]", betreff)
        self.assertIn("T-0001", betreff)
        self.assertIn("2026-08-10", text)
        self.assertIn("[A, B]", text)


class FristWarnungTest(unittest.TestCase):
    """P2/T-0007: Warnmail bei Frist <= 2 Tage oder überschritten."""

    def test_schwelle_zwei_tage(self):
        """Frist > heute+2: keine Warnung; Frist = heute+2: Warnung. Verifiziert: SWR-034."""
        root = _root_mit_dr(frist="2026-08-10")
        erg = dr_benachrichtigung.lauf(root, sende=lambda b, t: (True, "ok"),
                                       heute=date(2026, 8, 7))
        self.assertEqual([e[2] for e in erg], ["gesendet"])  # 3 Tage hin: nur Neu-Mail
        root2 = _root_mit_dr(frist="2026-08-10")
        erg2 = dr_benachrichtigung.lauf(root2, sende=lambda b, t: (True, "ok"),
                                        heute=date(2026, 8, 8))
        self.assertIn("warnung gesendet", [e[2] for e in erg2])

    def test_warnung_nur_einmal(self):
        """Warn-Marker verhindert zweite Warnung; Neu-Marker bleibt unabhängig. Verifiziert: SWR-034."""
        root = _root_mit_dr()
        dr_benachrichtigung.lauf(root, sende=lambda b, t: (True, "ok"))
        erg = dr_benachrichtigung.lauf(root, sende=lambda b, t: (True, "ok"))
        self.assertEqual(erg, [])

    def test_entschiedene_drs_ohne_warnung(self):
        """Bereits entschiedene (noch offene) DRs werden nicht angemahnt. Verifiziert: SWR-034."""
        root = _root_mit_dr(body="\n**Entscheidung (D000, via Inbox, 2026-08-14):** A\n")
        erg = dr_benachrichtigung.lauf(root, sende=lambda b, t: (True, "ok"))
        self.assertEqual([e[2] for e in erg], ["gesendet"])  # keine Warnung

    def test_warntext_mit_und_ohne_default(self):
        """Warnung nennt Projekt/Ticket/Frist; Default-Option nur falls definiert. Verifiziert: SWR-035."""
        gesendet = []
        root = _root_mit_dr(default="A")
        dr_benachrichtigung.lauf(root, sende=lambda b, t: (gesendet.append((b, t)) or (True, "ok")))
        betreff, text = gesendet[-1]
        self.assertIn("FRIST-WARNUNG", betreff)
        self.assertIn("T-0001", text)
        self.assertIn("2026-08-10", text)
        self.assertIn("Default-Option: A", text)
        self.assertIn("greift", text)
        gesendet2 = []
        root2 = _root_mit_dr()
        dr_benachrichtigung.lauf(root2, sende=lambda b, t: (gesendet2.append((b, t)) or (True, "ok")))
        self.assertNotIn("Default-Option", gesendet2[-1][1])

    def test_unparsebare_frist_ohne_warnung(self):
        """DR ohne parsebare Frist erzeugt keine Warnung (nur Neu-Mail). Verifiziert: SWR-034."""
        root = _root_mit_dr(frist='"offen"')
        erg = dr_benachrichtigung.lauf(root, sende=lambda b, t: (True, "ok"))
        self.assertEqual([e[2] for e in erg], ["gesendet"])


if __name__ == "__main__":
    unittest.main()
