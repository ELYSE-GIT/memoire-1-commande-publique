"""Tests du calcul de justesse du rapprochement.

L'enjeu ici n'est pas la performance mais **la justesse du calcul lui-meme**. Un redressement
d'echantillon stratifie se trompe silencieusement : le resultat reste un nombre plausible, aucune
erreur n'apparait. Ces tests verifient donc le calcul sur des cas dont on connait la reponse a
l'avance.

Ce qu'ils attrapent : une ponderation oubliee, un doute compte comme une reussite, une tranche
mal bornee, un fichier de verdicts mal lu.
Ce qu'ils n'attrapent pas : un verdict humain errone. Cela se corrige en relisant les paires, et
c'est pourquoi le fichier de verdicts est versionne plutot que calcule.
"""

import csv
from pathlib import Path

import pytest

from mesures import precision_rapprochement as module

VERDICTS = [
    # tranche, verdict : deux tranches, des verdicts connus d'avance.
    ("0.4 a 0.5", "non"),
    ("0.4 a 0.5", "non"),
    ("0.4 a 0.5", "doute"),
    ("0.8 a 1.01", "oui"),
    ("0.8 a 1.01", "oui"),
    ("0.8 a 1.01", "non"),
]

BALAYAGE = [
    # fenetre, seuil, confiance moyenne : 100 rapprochements a 0,4 dont 10 seulement a 0,8.
    (18, 0.4, 100),
    (18, 0.5, 10),
    (18, 0.6, 10),
    (18, 0.7, 10),
    (18, 0.8, 10),
    (12, 0.4, 999),  # une autre fenetre, qui ne doit jamais etre prise en compte
]


@pytest.fixture(autouse=True)
def fichiers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fabrique les deux fichiers d'entree et fait pointer le module dessus."""
    verification = tmp_path / "verification"
    resultats = tmp_path / "resultats"
    verification.mkdir()
    resultats.mkdir()

    with (verification / "2026-01-01-verdicts-rapprochement.csv").open(
        "w", newline="", encoding="utf-8"
    ) as sortie:
        auteur = csv.writer(sortie, lineterminator="\n")
        auteur.writerow(["tranche", "verdict_humain"])
        auteur.writerows(VERDICTS)

    with (resultats / "2026-01-01-rapprochement-balayage.csv").open(
        "w", newline="", encoding="utf-8"
    ) as sortie:
        auteur = csv.writer(sortie, lineterminator="\n")
        auteur.writerow(["fenetre_mois", "seuil_objet", "confiance_moyenne"])
        auteur.writerows(BALAYAGE)

    monkeypatch.setattr(module, "VERIFICATION", verification)
    monkeypatch.setattr(module, "RESULTATS", resultats)


def test_le_doute_est_exclu_du_calcul() -> None:
    """Deux non et un doute donnent une justesse de 0 sur 2, pas de 0 sur 3."""
    justesse = module.justesse_par_tranche()["0.4 a 0.5"]
    assert justesse["relues"] == 3
    assert justesse["doutes"] == 1
    assert justesse["justesse"] == 0.0


def test_la_justesse_se_calcule_sur_les_verdicts_surs() -> None:
    """Deux oui et un non donnent deux tiers, et non la moitie des trois lignes."""
    justesse = module.justesse_par_tranche()["0.8 a 1.01"]["justesse"]
    assert justesse == pytest.approx(0.667, abs=0.001)


def test_une_tranche_sans_verdict_ne_fait_pas_echouer() -> None:
    """Les tranches absentes du fichier valent zero, elles ne levent pas d'erreur."""
    assert module.justesse_par_tranche()["0.6 a 0.7"]["relues"] == 0


def test_seule_la_fenetre_de_reference_est_lue() -> None:
    """La ligne de la fenetre de 12 mois ne doit pas polluer la table."""
    par_seuil = module.rapprochements_par_seuil()
    assert par_seuil[0.4] == 100
    assert 999 not in par_seuil.values()


def test_la_ponderation_corrige_bien_l_echantillon() -> None:
    """Le calcul doit ponderer par les effectifs reels, pas faire la moyenne des tranches.

    Cas construit : 90 rapprochements dans la tranche 0,4 a 0,5, dont la justesse est nulle, et
    10 dans la tranche 0,8 et plus, dont la justesse est de deux tiers. La moyenne naive des deux
    tranches donnerait 33 %. La moyenne ponderee donne 6,7 %, ce qui est la bonne reponse.
    """
    table = {ligne["seuil_objet"]: ligne for ligne in module.table_de_decision()}
    au_seuil_bas = table[0.4]
    assert au_seuil_bas["rapproches_par_objet"] == 100
    assert au_seuil_bas["justesse_estimee_pourcent"] == pytest.approx(6.7, abs=0.1)


def test_un_seuil_eleve_ne_retient_que_sa_tranche() -> None:
    """Au seuil de 0,8, seuls les dix rapprochements de la derniere tranche comptent."""
    table = {ligne["seuil_objet"]: ligne for ligne in module.table_de_decision()}
    assert table[0.8]["rapproches_par_objet"] == 10
    assert table[0.8]["justesse_estimee_pourcent"] == pytest.approx(66.7, abs=0.1)


def test_le_nombre_de_justes_attendus_est_coherent() -> None:
    """Le produit de la couverture par la justesse doit correspondre a la colonne publiee."""
    for ligne in module.table_de_decision():
        attendu = ligne["rapproches_par_objet"] * ligne["justesse_estimee_pourcent"] / 100
        assert ligne["rapprochements_justes_attendus"] == pytest.approx(attendu, abs=0.2)


def test_un_fichier_manquant_est_signale_clairement(tmp_path: Path) -> None:
    """Mieux vaut une erreur nommant le fichier qu'un resultat calcule sur du vide."""
    with pytest.raises(FileNotFoundError, match="aucun fichier"):
        module.dernier(tmp_path, "*-inexistant.csv")
