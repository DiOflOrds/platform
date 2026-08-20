"""SWR-164 (platform/T-0021, Frage 3): der Parkplatz wird gemessen und gemeldet.

⚠⚠ **Die Frage lautete, ob `.git/verwaiste-locks` unbegrenzt waechst — und die Antwort ist
ja, aus einem Grund, der im Raeummechanismus selbst steht.** `entferne_artefakte` ist
zweistufig: erst `os.remove`, bei `OSError` **umbenennen**. Auf einem Mount ohne
`unlink`-Recht scheitert die erste Stufe **immer**; jede geraeumte Sperre wird also geparkt
und nie geloescht.

| Sprint | `pm/.git/verwaiste-locks` |
|---|---|
| 21 | 1975 |
| 24 | 2099 |

> **Reparierbar ist das von hier aus nicht — was fehlt, ist das Loeschrecht und nicht eine
> Idee. Was fehlte, war die MESSUNG: eine ungemessene Groesse ist von einer, die nicht
> waechst, nicht zu unterscheiden.**

Die Zeile ist deshalb ausdruecklich **kein Befund**. Sie meldet und blockiert nicht — eine
Dauerwarnung ueber einen Zustand, den niemand abstellen kann, traeniert das Wegsehen
(dieselbe Begruendung wie beim Altbestand der 42 DRs in SWR-131).
"""
import os
import shutil
import sys
import tempfile
import unittest

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HIER, ".."))
sys.path.insert(0, os.path.join(_HIER, "..", "scripts"))
import preflight  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(_HIER))


class ParkplatzStandTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _repo(self, name, geparkt=0):
        g = os.path.join(self.tmp, name, ".git")
        os.makedirs(g)
        if geparkt:
            p = os.path.join(g, preflight.PARKPLATZ)
            os.makedirs(p)
            for i in range(geparkt):
                open(os.path.join(p, f"index.lock.{i}"), "w").close()

    def test_ohne_jedes_repo_ist_die_antwort_None_und_keine_Null(self):
        """⚠ Die Gegenprobe, ohne die die Zahl wertlos waere.

        „Nicht gemessen" und „gemessen: 0" sehen als Zahl gleich aus und sind zwei
        verschiedene Tatsachen — genau die Verwechslung, die SWR-114 benannt hat und die in
        SWR-128 fuenf Sprints lang „null JS-Tests" verborgen hat.
        """
        self.assertIsNone(preflight.parkplatz_stand(self.tmp))

    def test_ein_repo_OHNE_parkplatz_zaehlt_als_null_und_nicht_als_unbekannt(self):
        """Ein Repo, in dem noch nie eine Sperre geparkt wurde, hat den Parkplatz nicht —
        das ist eine echte Null und kein Loch."""
        self._repo("p0", geparkt=0)
        stand = preflight.parkplatz_stand(self.tmp)
        self.assertIsNone(stand,
                          "ohne angelegten Parkplatz gibt es nichts zu lesen; die Aussage "
                          "'0' duerfte erst fallen, wenn mindestens ein Verzeichnis da ist")

    def test_gezaehlt_wird_ueber_alle_repos(self):
        self._repo("p0", geparkt=3)
        self._repo("p1", geparkt=4)
        gesamt, groesster = preflight.parkplatz_stand(self.tmp)
        self.assertEqual(gesamt, 7)
        self.assertEqual(groesster, ("p1", 4))

    def test_der_groesste_einzelbestand_wird_NAMENTLICH_genannt(self):
        """⚠ Eine Summe allein sagt nicht, wo man aufraeumen muesste.

        Dieselbe Regel wie in SWR-110: Dateien **nennen** statt zaehlen. Ein Mensch, der
        den Parkplatz auf dem Host leeren will, braucht das Repo und nicht die Summe.
        """
        self._repo("klein", geparkt=1)
        self._repo("gross", geparkt=99)
        _gesamt, groesster = preflight.parkplatz_stand(self.tmp)
        self.assertEqual(groesster[0], "gross")

    def test_die_messung_raeumt_NICHTS_weg(self):
        """⚠⚠ Eine Messung, die ihren Gegenstand veraendert, misst sich selbst.

        Der Parkplatz ist das Archiv der geraeumten Sperren; ihn beim Zaehlen zu leeren
        haette die Zahl beim naechsten Lauf auf 0 gebracht und die Frage, ob er waechst,
        dauerhaft unbeantwortbar gemacht.
        """
        self._repo("p0", geparkt=5)
        preflight.parkplatz_stand(self.tmp)
        p = os.path.join(self.tmp, "p0", ".git", preflight.PARKPLATZ)
        self.assertEqual(len(os.listdir(p)), 5)

    def test_am_ECHTEN_bestand_ist_die_zahl_dreistellig_oder_groesser(self):
        """Die Lehre aus SWR-128: konstruierte Faelle genuegen nicht.

        ⚠ Geprueft wird eine **Groessenordnung** und keine feste Zahl: der Bestand waechst
        mit jedem Lauf, und ein Test, der die heutige Zahl festnagelt, ist morgen rot und
        sagt nichts (der Fehler aus SWR-157).
        """
        if not os.path.isdir(os.path.join(WURZEL, "pm", ".git")):
            self.skipTest("Bestand nicht vorhanden (isolierte Testumgebung)")
        stand = preflight.parkplatz_stand(WURZEL)
        self.assertIsNotNone(stand)
        gesamt, groesster = stand
        self.assertGreater(gesamt, 100,
                           "der gemessene Bestand war in Sprint 21 vierstellig in einem "
                           "einzigen Repo — faellt er unter 100, ist entweder aufgeraeumt "
                           "worden oder die Messung sieht die Repos nicht mehr")
        self.assertGreater(groesster[1], 0)


if __name__ == "__main__":
    unittest.main()
