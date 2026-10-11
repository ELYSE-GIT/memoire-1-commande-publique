"""Tests du socle du projet.

Ils verifient que l'environnement et la configuration de base sont corrects.
Ils servent aussi de premier test vert pour la chaine d'integration continue.
"""

import shutil
import subprocess
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


def test_le_fichier_env_ne_peut_pas_etre_versionne() -> None:
    """Le fichier `.env` porte de vrais secrets : il ne doit jamais etre suivi par git.

    Ce test remplace une regle du scanner de secrets, qui signalait `.env` a chaque execution et
    rendait `make verif` rouge en permanence. Une alerte qui crie toujours finit par etre ignoree ;
    un test qui verifie exactement le risque reel, non.

    Deux verifications distinctes, parce qu'elles attrapent deux fautes differentes : un `.env`
    retire de `.gitignore`, et un `.env` ajoute a l'index avant que la regle n'existe.
    """
    racine = Path(__file__).resolve().parent.parent

    # Chemin complet de git plutot que son nom : un nom seul se resout par la variable PATH, que
    # l'appelant controle. L'analyse de securite du depot le refuse, et elle a raison.
    git = shutil.which("git")
    assert git, "git introuvable"

    # noqa S603 : la commande est entierement ecrite ici, aucun argument ne vient de
    # l'exterieur. Meme convention que tests/test_transformation.py, qui lance dbt.
    ignore = subprocess.run(  # noqa: S603
        [git, "check-ignore", "-q", ".env"], cwd=racine, check=False
    )
    assert ignore.returncode == 0, ".env n'est pas ignore par git"

    suivi = subprocess.run(  # noqa: S603
        [git, "ls-files", ".env"], cwd=racine, capture_output=True, text=True, check=True
    )
    assert not suivi.stdout.strip(), ".env est suivi par git"


def test_un_exemple_de_configuration_est_versionne() -> None:
    """`.env.example` doit exister et ne contenir aucune valeur reelle.

    Sans lui, personne ne sait quelles variables renseigner pour faire tourner le projet. Avec un
    vrai mot de passe dedans, il deviendrait la fuite qu'on cherche a eviter.
    """
    exemple = (Path(__file__).resolve().parent.parent / ".env.example").read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD" in exemple
    assert "POSTGRES_PASSWORD=a_changer" in exemple


def test_ruff_est_epingle_a_la_meme_version_partout() -> None:
    """La version de ruff du projet et celle du hook pre-commit doivent etre identiques.

    Incident du 2026-09-28 : deux versions differentes formatent differemment. Le hook reformatait
    le fichier, l'integration continue exigeait l'inverse, et le commit ne passait jamais. La
    panne est invisible tant qu'on ne compare pas les deux fichiers, et elle revient a chaque
    montee de version automatique.

    Ce test encode la lecon. La section `pre-commit` du fichier Dependabot evite d'avoir a la
    corriger a la main.
    """
    racine = Path(__file__).resolve().parent.parent

    projet = tomllib.loads((racine / "pyproject.toml").read_text(encoding="utf-8"))
    dependances = projet["dependency-groups"]["dev"]
    epingle = next(ligne for ligne in dependances if ligne.startswith("ruff=="))
    version_projet = epingle.split("==")[1]

    hooks = (racine / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    debut = hooks.index("astral-sh/ruff-pre-commit")
    ligne_revision = hooks[debut : hooks.index("hooks:", debut)]
    version_hook = ligne_revision.split("rev:")[1].strip().lstrip("v")

    assert version_projet == version_hook, (
        f"ruff est epingle a {version_projet} dans pyproject.toml "
        f"et a {version_hook} dans .pre-commit-config.yaml"
    )
