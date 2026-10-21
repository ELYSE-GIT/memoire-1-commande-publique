"""Tests des intervalles de confiance et de la stabilite temporelle.

Ces tests ne touchent pas la base : les formules sont pures, et les valeurs de reference se
calculent a la main. C'est ce qui permet de les verifier vraiment, et pas seulement de constater
que le code ne plante pas.

Deux d'entre eux ne verifient pas un calcul mais une **concordance entre deux fichiers** : le seuil
de detection ecrit dans le modele SQL de production et celui que le module de stabilite applique,
et le decoupage en tranches partage par deux modules de mesure. Ce sont les erreurs les plus
couteuses du projet, parce qu'elles ne font planter personne : elles produisent juste une mesure
qui ne parle pas de ce qu'on croit.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from mesures import incertitude, precision_rapprochement, stabilite

RACINE = Path(__file__).resolve().parent.parent


def test_wald_annonce_une_certitude_sur_un_resultat_parfait() -> None:
    """La formule naive ne laisse aucune marge a 40 sur 40. C'est la raison de l'avoir remplacee."""
    assert incertitude.wald(40, 40) == (100.0, 100.0)


def test_wald_peut_sortir_de_l_intervalle_possible() -> None:
    """Sur une proportion faible, la formule naive descend sous zero pour cent."""
    bas, _ = incertitude.wald(1, 100)
    assert bas < 0


def test_wilson_laisse_une_marge_sur_un_resultat_parfait() -> None:
    """Quarante sur quarante ne donne pas cent pour cent, mais un plancher autour de 91 %."""
    bas, haut = incertitude.wilson(40, 40)
    assert haut == 100.0
    assert bas == pytest.approx(91.2, abs=0.1)


def test_wilson_reste_dans_les_bornes_possibles() -> None:
    """Quelle que soit la proportion, l'intervalle reste entre 0 et 100."""
    for succes in range(0, 51):
        bas, haut = incertitude.wilson(succes, 50)
        assert 0.0 <= bas <= haut <= 100.0


def test_l_intervalle_exact_vaut_sa_valeur_de_manuel() -> None:
    """Zero succes sur dix : la borne haute exacte vaut 1 moins 0,025 puissance 1/10.

    C'est l'une des rares valeurs d'intervalle binomial qui se calcule de tete, parce que la loi
    se reduit a un seul terme. Elle sert ici de controle de la dichotomie.
    """
    _, haut = incertitude.clopper_pearson(0, 10)
    assert haut == pytest.approx(100 * (1 - 0.025 ** (1 / 10)), abs=0.05)

    bas, _ = incertitude.clopper_pearson(10, 10)
    assert bas == pytest.approx(100 * 0.025 ** (1 / 10), abs=0.05)


def test_l_intervalle_exact_contient_la_proportion_observee() -> None:
    """Un intervalle qui ne contiendrait pas la mesure dont il sort serait faux."""
    for succes, essais in ((0, 40), (1, 40), (20, 40), (39, 40), (40, 40), (448, 448)):
        bas, haut = incertitude.clopper_pearson(succes, essais)
        assert bas <= 100 * succes / essais <= haut


def test_le_bootstrap_est_reproductible() -> None:
    """Deux executions donnent exactement le meme intervalle.

    Sans graine fixe, la figure du memoire changerait a chaque `make figures` alors qu'aucune
    donnee n'aurait bouge, et git afficherait une modification a chaque fois.
    """
    assert incertitude.bootstrap_justesse() == incertitude.bootstrap_justesse()


def test_la_justesse_ponderee_refuse_de_repondre_sans_verdict() -> None:
    """Une tranche sans verdict exploitable renvoie None, et non zero.

    Zero voudrait dire « aucun rapprochement juste », ce qui est une affirmation. L'absence de
    reponse en est une autre, et c'est celle qui est vraie.
    """
    groupes: dict[str, list[str]] = {f"{bas} a {haut}": [] for bas, haut in incertitude.TRANCHES}
    effectifs = dict.fromkeys(groupes, 10)
    assert incertitude.justesse_ponderee(groupes, effectifs, 0.4) is None


def test_le_bootstrap_signale_les_cas_ou_il_ne_sait_rien_dire() -> None:
    """Quand toutes les paires relues sont justes, l'intervalle se referme : le cas est marque.

    Sans cette colonne, la table afficherait un intervalle de largeur nulle qui se lirait comme
    une certitude, alors qu'il signale l'inverse : douze paires ne suffisent pas.
    """
    table = incertitude.bootstrap_justesse()
    degeneres = [ligne for ligne in table if ligne["bootstrap_degenere"] == "oui"]
    for ligne in degeneres:
        assert ligne["largeur_points"] == 0.0
        # L'intervalle exact, lui, garde une largeur : c'est le relais annonce dans l'en-tete.
        assert ligne["exact_sans_redressement_bas"] < ligne["exact_sans_redressement_haut"]


def test_les_deux_modules_decoupent_les_memes_tranches() -> None:
    """Le bootstrap et la table de decision doivent parler du meme echantillon."""
    assert incertitude.TRANCHES == precision_rapprochement.TRANCHES
    assert incertitude.FENETRE_REFERENCE == precision_rapprochement.FENETRE_REFERENCE


def test_la_stabilite_mesure_la_regle_qui_tourne_vraiment() -> None:
    """Le seuil et la taille minimale de famille sont ceux du modele SQL de production.

    Mesurer la stabilite d'une autre regle que celle qui tourne donnerait un resultat vrai et
    sans objet. Le test lit le fichier SQL plutot qu'une constante recopiee, pour que changer la
    regle en production fasse echouer la mesure au lieu de la laisser mentir.
    """
    sql = (RACINE / "services" / "transformation" / "models" / "or" / "or_signaux.sql").read_text(
        encoding="utf-8"
    )
    seuil = re.search(r"ecart_normalise_famille > (\d+)", sql)
    taille = re.search(r"marches_dans_la_famille >= (\d+)", sql)
    assert seuil is not None and taille is not None
    assert float(seuil.group(1)) == stabilite.SEUIL
    assert int(taille.group(1)) == stabilite.TAILLE_MINIMALE_GROUPE


def test_la_periode_de_test_suit_la_periode_d_apprentissage() -> None:
    """Les deux periodes ne se chevauchent pas, et aucune annee ne tombe entre les deux."""
    assert stabilite.PREMIERE_ANNEE < stabilite.FIN_APPRENTISSAGE < stabilite.DERNIERE_ANNEE
