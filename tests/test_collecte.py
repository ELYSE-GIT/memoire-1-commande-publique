"""Tests de la collecte : tracabilite, idempotence, reprise sur erreur.

Aucun de ces tests ne touche au reseau. Un test qui appelle une API publique echoue quand l'API
est en panne, ce qui n'apprend rien sur le code, agace l'equipe, et finit par etre desactive.
Les appels reseau sont donc remplaces par des fonctions qui simulent les reponses et les pannes.

Ce qu'ils attrapent : une empreinte mal calculee, une collecte qui laisserait deux traces du meme
evenement, un fichier incomplet pris pour valide, une erreur definitive retentee en boucle.
Ce qu'ils n'attrapent pas : un changement de format de la source. Cela se voit a l'execution, et
c'est le role du manifeste de le rendre visible.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from services.collecte import appels, manifeste


@pytest.fixture(autouse=True)
def dossiers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fait ecrire le manifeste dans un dossier temporaire plutot que dans le depot."""
    monkeypatch.setattr(manifeste, "RACINE", tmp_path)
    monkeypatch.setattr(manifeste, "BRONZE", tmp_path / "bronze")
    monkeypatch.setattr(manifeste, "MANIFESTES", tmp_path / "manifestes")
    (tmp_path / "bronze").mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def sans_attente(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supprime les attentes entre tentatives : sans cela, les tests durent dix secondes."""
    # On patche les modules eux-memes, et non leur reexport par `appels` : c'est le meme objet,
    # et cela evite de dependre de ce que le module choisit d'exposer.
    monkeypatch.setattr(appels, "_attendre", lambda tentative: None)
    monkeypatch.setattr(time, "sleep", lambda duree: None)


def fichier(dossier: Path, contenu: str = "bonjour") -> Path:
    """Fabrique un fichier de test dans la couche bronze."""
    chemin = dossier / "bronze" / "source" / "fichier.txt"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(contenu, encoding="utf-8")
    return chemin


# --- Tracabilite ----------------------------------------------------------


def test_deux_contenus_differents_donnent_deux_empreintes(dossiers: Path) -> None:
    """C'est toute la raison d'etre de l'empreinte."""
    premier = fichier(dossiers, "contenu A")
    empreinte_a = manifeste.empreinte(premier)
    premier.write_text("contenu B", encoding="utf-8")
    assert manifeste.empreinte(premier) != empreinte_a


def test_le_meme_contenu_donne_toujours_la_meme_empreinte(dossiers: Path) -> None:
    """Sans cette stabilite, la verification d'integrite n'aurait aucun sens."""
    chemin = fichier(dossiers)
    assert manifeste.empreinte(chemin) == manifeste.empreinte(chemin)


def test_l_entree_decrit_le_fichier_reel(dossiers: Path) -> None:
    """Taille et chemin viennent du disque, pas de ce que le code croit avoir ecrit."""
    chemin = fichier(dossiers, "douze octets")
    entree = manifeste.decrire("essai", "https://exemple/x", chemin, lignes=3)
    assert entree.taille_octets == chemin.stat().st_size
    assert entree.lignes == 3
    assert entree.fichier == "bronze/source/fichier.txt"
    assert len(entree.empreinte_sha256) == 64


def test_la_verification_detecte_une_modification(dossiers: Path) -> None:
    """Un fichier modifie apres coup ne doit plus etre reconnu comme celui qui a ete mesure."""
    chemin = fichier(dossiers, "original")
    entree = manifeste.decrire("essai", "https://exemple/x", chemin)
    assert manifeste.verifier(entree) is True
    chemin.write_text("modifie", encoding="utf-8")
    assert manifeste.verifier(entree) is False


def test_la_verification_detecte_un_fichier_absent(dossiers: Path) -> None:
    """Une donnee brute peut avoir ete purgee : le manifeste doit le dire, pas planter."""
    chemin = fichier(dossiers)
    entree = manifeste.decrire("essai", "https://exemple/x", chemin)
    chemin.unlink()
    assert manifeste.verifier(entree) is False


# --- Idempotence ----------------------------------------------------------


def test_collecter_deux_fois_ne_laisse_qu_une_trace(dossiers: Path) -> None:
    """Relancer une collecte interrompue ne doit pas creer deux entrees contradictoires."""
    chemin = fichier(dossiers)
    manifeste.enregistrer(manifeste.decrire("decp", "https://exemple/1", chemin))
    manifeste.enregistrer(manifeste.decrire("decp", "https://exemple/2", chemin))

    entrees = manifeste.dernier_manifeste()
    assert len(entrees) == 1
    assert entrees[0].adresse == "https://exemple/2", "la derniere collecte doit gagner"


def test_deux_sources_coexistent_dans_le_manifeste(dossiers: Path) -> None:
    """Le remplacement porte sur la source, pas sur le fichier entier."""
    chemin = fichier(dossiers)
    manifeste.enregistrer(manifeste.decrire("decp", "https://exemple/1", chemin))
    manifeste.enregistrer(manifeste.decrire("boamp", "https://exemple/2", chemin))
    assert {e.source for e in manifeste.dernier_manifeste()} == {"decp", "boamp"}


def test_le_manifeste_est_du_json_lisible(dossiers: Path) -> None:
    """Il doit pouvoir etre ouvert et compris sans outil, y compris par un jury."""
    chemin = manifeste.enregistrer(manifeste.decrire("decp", "https://x", fichier(dossiers)))
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    assert contenu[0]["source"] == "decp"
    assert chemin.read_text(encoding="utf-8").endswith("\n")


def test_sans_collecte_le_manifeste_est_vide(dossiers: Path) -> None:
    """Le cas du premier lancement ne doit pas lever d'erreur."""
    assert manifeste.dernier_manifeste() == []


# --- Reprise sur erreur ---------------------------------------------------


def erreur_http(code: int) -> urllib.error.HTTPError:
    """Fabrique une erreur HTTP comparable a celle que leverait urllib."""
    return urllib.error.HTTPError("https://exemple", code, "essai", {}, None)  # type: ignore[arg-type]


def test_une_erreur_passagere_est_retentee() -> None:
    """Une erreur 500 vient du serveur et disparait souvent d'elle-meme."""
    tentatives = {"n": 0}

    def action() -> str:
        tentatives["n"] += 1
        if tentatives["n"] < 3:
            raise erreur_http(500)
        return "reussi"

    assert appels._avec_reprise(action, "essai") == "reussi"
    assert tentatives["n"] == 3


def test_une_erreur_definitive_n_est_pas_retentee() -> None:
    """Une erreur 404 ne changera pas : insister ne ferait que perdre du temps."""
    tentatives = {"n": 0}

    def action() -> str:
        tentatives["n"] += 1
        raise erreur_http(404)

    with pytest.raises(appels.EchecReseau, match="definitive"):
        appels._avec_reprise(action, "essai")
    assert tentatives["n"] == 1, "une seule tentative pour une erreur definitive"


def test_une_limitation_de_debit_est_retentee() -> None:
    """Le code 429 signale un appel trop rapide, pas une erreur de la requete."""
    tentatives = {"n": 0}

    def action() -> str:
        tentatives["n"] += 1
        if tentatives["n"] < 2:
            raise erreur_http(429)
        return "reussi"

    assert appels._avec_reprise(action, "essai") == "reussi"


def test_l_echec_persistant_est_signale_clairement() -> None:
    """Mieux vaut une erreur nommee qu'une collecte qui s'arrete sans expliquer pourquoi."""

    def action() -> str:
        raise erreur_http(503)

    with pytest.raises(appels.EchecReseau, match=f"{appels.TENTATIVES} tentatives"):
        appels._avec_reprise(action, "essai")


# --- Telechargement -------------------------------------------------------


def test_un_telechargement_interrompu_ne_laisse_pas_de_fichier_valide(
    dossiers: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C'est la condition de l'idempotence : pas de fichier tronque portant le nom attendu.

    Sans le fichier temporaire, une coupure laisserait un Parquet incomplet que la suite de la
    chaine lirait comme valide, et les mesures seraient fausses sans que rien ne le signale.
    """

    def urlopen_qui_coupe(*arguments: object, **options: object) -> object:
        raise TimeoutError("connexion interrompue")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen_qui_coupe)
    destination = dossiers / "bronze" / "decp" / "decp.parquet"

    with pytest.raises(appels.EchecReseau):
        appels.telecharger("https://exemple/decp.parquet", destination)

    assert not destination.exists(), "aucun fichier ne doit porter le nom attendu"
    assert not list(destination.parent.glob("*.partiel")), "le fichier partiel doit etre nettoye"
