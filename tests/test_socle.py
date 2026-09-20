"""Tests du socle du projet.

Ils verifient que l'environnement et la configuration de base sont corrects.
Ils servent aussi de premier test vert pour la chaine d'integration continue.
"""

import sys
import tomllib
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def test_version_python_attendue() -> None:
    """Le projet tourne sur Python 3.12, la version declaree dans .python-version."""
    attendue = (RACINE / ".python-version").read_text().strip()
    reelle = f"{sys.version_info.major}.{sys.version_info.minor}"
    assert reelle == attendue


def test_exemple_env_present_et_sans_secret() -> None:
    """Le modele de configuration est versionne, mais le vrai .env ne l'est jamais."""
    exemple = RACINE / ".env.example"
    assert exemple.exists()
    contenu = exemple.read_text()
    assert "POSTGRES_PASSWORD=a_changer" in contenu
    assert (RACINE / ".gitignore").read_text().count(".env") >= 1


def test_chaque_dossier_important_a_son_readme() -> None:
    """Le depot doit s'expliquer tout seul quand on le parcourt."""
    dossiers = ["services", "base", "infra", "analyses", "mesures", "docs", "memoire"]
    manquants = [d for d in dossiers if not (RACINE / d / "README.md").exists()]
    assert manquants == []


def test_pyproject_declare_les_groupes_de_dependances() -> None:
    """Les outils de developpement restent separes des dependances de production."""
    with (RACINE / "pyproject.toml").open("rb") as fichier:
        config = tomllib.load(fichier)
    assert config["project"]["name"] == "commande-publique"
    assert "dev" in config["dependency-groups"]
