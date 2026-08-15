"""Unit-Verifikation Produktkatalog v0 (T-0056) + Check (SWR-036, P2/T-0008)."""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import catalog  # noqa: E402

GIT_ID = ["-c", "user.name=Test", "-c", "user.email=test@example.invalid"]


def _produkt_repo(root, name, version="1.0.0", tag=True):
    repo = os.path.join(root, name)
    os.makedirs(repo)
    open(os.path.join(repo, "pyproject.toml"), "w", encoding="utf-8").write(
        f'[project]\nname = "{name}"\nversion = "{version}"\n')
    subprocess.run(["git", "-C", repo, "init", "-q"], check=True)
    subprocess.run(["git", "-C", repo, "add", "-A"], check=True)
    subprocess.run(["git", "-C", repo] + GIT_ID + ["commit", "-q", "-m", "init"], check=True)
    if tag:
        subprocess.run(["git", "-C", repo] + GIT_ID + ["tag", "-a", f"v{version}",
                                                       "-m", "release"], check=True)
    return repo

EINTRAG = {"name": "datakonv", "version": "1.0.0", "released": "2026-08-06",
           "interface": "CLI", "repo": "produkt-datakonv", "project": "p0",
           "capabilities": "CSV<->JSON", "limitations": "flat only", "doc": "README.md"}


class KatalogTest(unittest.TestCase):
    def test_neuer_eintrag_erzeugt_yaml_und_seite(self):
        """Registrierung erzeugt products.yaml und Detailseite. Bezug: T-0056."""
        with tempfile.TemporaryDirectory() as d:
            yaml_pfad, seite = catalog.registriere(d, dict(EINTRAG))
            import yaml as y
            daten = y.safe_load(open(yaml_pfad, encoding="utf-8"))
            self.assertEqual(daten["products"]["datakonv"]["version"], "1.0.0")
            self.assertIn("CSV<->JSON", open(seite, encoding="utf-8").read())

    def test_update_ersetzt_version(self):
        """Erneute Registrierung aktualisiert den Eintrag statt zu duplizieren. Bezug: T-0056."""
        with tempfile.TemporaryDirectory() as d:
            catalog.registriere(d, dict(EINTRAG))
            neu = dict(EINTRAG, version="1.1.0")
            yaml_pfad, _ = catalog.registriere(d, neu)
            import yaml as y
            daten = y.safe_load(open(yaml_pfad, encoding="utf-8"))
            self.assertEqual(len(daten["products"]), 1)
            self.assertEqual(daten["products"]["datakonv"]["version"], "1.1.0")


class KatalogCheckTest(unittest.TestCase):
    """P2/T-0008: --check gleicht Katalog und Produkt-Repos ab."""

    def _root(self):
        d = tempfile.mkdtemp()
        katalog_dir = os.path.join(d, "process", "catalog")
        _produkt_repo(d, "produkt-demo")
        catalog.registriere(katalog_dir, dict(EINTRAG, name="demo", repo="produkt-demo"))
        return d, katalog_dir

    def test_konsistenter_katalog_ohne_befund(self):
        """Eintrag mit Repo, Tag v<version>, passender pyproject-Version und Seite: leer. Verifiziert: SWR-036."""
        d, katalog_dir = self._root()
        self.assertEqual(catalog.pruefe(d, katalog_dir), [])

    def test_versionskonflikt_und_fehlender_tag(self):
        """Katalog-Version ohne Tag und abweichende pyproject-Version werden gemeldet. Verifiziert: SWR-036."""
        d, katalog_dir = self._root()
        catalog.registriere(katalog_dir, dict(EINTRAG, name="demo", repo="produkt-demo",
                                              version="2.0.0"))
        befunde = catalog.pruefe(d, katalog_dir)
        texte = " | ".join(b for _, b in befunde)
        self.assertIn("Release-Tag v2.0.0 fehlt", texte)
        self.assertIn("Versionskonflikt", texte)

    def test_release_repo_ohne_eintrag(self):
        """produkt-*-Repo mit Release-Tag ohne Katalog-Eintrag wird gemeldet; ohne Tag nicht. Verifiziert: SWR-036."""
        d, katalog_dir = self._root()
        _produkt_repo(d, "produkt-neu", version="0.1.0")
        _produkt_repo(d, "produkt-inarbeit", tag=False)
        befunde = catalog.pruefe(d, katalog_dir)
        produkte = [p for p, _ in befunde]
        self.assertIn("produkt-neu", produkte)
        self.assertNotIn("produkt-inarbeit", produkte)


if __name__ == "__main__":
    unittest.main()
