"""Tests de la comparaison entre les regles et un modele non supervise.

L'enjeu n'est pas la performance du modele mais **la justesse du protocole**. Une comparaison a
budget d'alertes egal se trompe silencieusement : si le tri part dans le mauvais sens, ou si le
budget deborde, le resultat reste un pourcentage plausible et aucune erreur n'apparait. Le chiffre
publie dans le memoire serait alors faux sans que rien ne le signale.

Ce qu'ils attrapent : un tri inverse, un budget plus grand que le jeu, une orientation qui laisse
passer le mauvais cote, une requete de preparation qui oublie un filtre ou fabrique un ecart du
mauvais signe.
Ce qu'ils n'attrapent pas : un mauvais choix de variables ou d'etiquette. Cela ne se verifie pas
par un test, seulement par la mesure et par sa relecture.
"""

import duckdb
import numpy as np
import pytest

from mesures import modele_vs_regles as module

# --- Le protocole : precision a budget d'alertes egal ------------------------


def test_precision_prend_bien_les_mieux_classes() -> None:
    """Les trois meilleurs scores portent deux vrais positifs sur trois."""
    scores = np.array([9.0, 8.0, 7.0, 1.0, 0.0])
    etiquettes = np.array([True, False, True, True, True])
    assert module.precision_au_budget(scores, etiquettes, 3) == pytest.approx(66.7)


def test_precision_trie_du_plus_grand_au_plus_petit() -> None:
    """Un score eleve doit signifier « plus anormal ». Un tri inverse donnerait 0 %."""
    scores = np.array([5.0, 4.0, 3.0, 2.0, 1.0])
    etiquettes = np.array([True, True, False, False, False])
    assert module.precision_au_budget(scores, etiquettes, 2) == 100.0


def test_precision_nulle_si_le_budget_depasse_le_jeu() -> None:
    """Demander plus d'alertes qu'il n'y a de marches n'a pas de sens : on renvoie 0, pas une
    valeur plausible qui se glisserait dans un tableau du memoire."""
    scores = np.array([1.0, 2.0])
    etiquettes = np.array([True, True])
    assert module.precision_au_budget(scores, etiquettes, 10) == 0.0


def test_precision_du_hasard_vaut_la_frequence_de_l_etiquette() -> None:
    """Garde-fou de la mesure elle-meme : sur un score aleatoire et un grand budget, la precision
    doit retomber sur la part de positifs du jeu."""
    generateur = np.random.default_rng(module.GRAINE)
    etiquettes = generateur.random(10_000) < 0.03
    hasard = generateur.random(10_000)
    mesure = module.precision_au_budget(hasard, etiquettes, 5_000)
    assert abs(mesure - 100 * etiquettes.mean()) < 1.5


# --- L'orientation, qui est la conclusion du notebook 08 ---------------------


def test_orienter_ecarte_le_mauvais_cote() -> None:
    """Les marches hors du cote retenu ne doivent plus pouvoir etre selectionnes."""
    scores = np.array([10.0, 9.0, 1.0])
    cote = np.array([False, True, True])
    oriente = module.orienter(scores, cote)
    assert oriente[0] == -np.inf
    assert list(oriente[1:]) == [9.0, 1.0]


def test_orienter_change_le_resultat_quand_les_directions_divergent() -> None:
    """Cas d'ecole reproduisant la mesure du 28 septembre 2026 : le modele classe en tete des
    marches que l'etiquette ne marque jamais. Libre il obtient 0 %, oriente il obtient 100 %."""
    scores = np.array([9.0, 8.0, 2.0, 1.0])
    etiquettes = np.array([False, False, True, True])
    cote_utile = np.array([False, False, True, True])

    assert module.precision_au_budget(scores, etiquettes, 2) == 0.0
    assert module.precision_au_budget(module.orienter(scores, cote_utile), etiquettes, 2) == 100.0


# --- La preparation SQL, qui decide de ce que le modele voit -----------------


@pytest.fixture
def base() -> duckdb.DuckDBPyConnection:
    """Une base minuscule ou l'on connait la reponse d'avance.

    Une famille de 40 marches etales entre 1 000 et 5 000 euros, plus un marche a 1 000 000 :
    l'ecart de ce dernier doit ressortir largement positif. Les montants sont volontairement
    etales, sinon l'ecart interquartile vaut zero et la formule bascule sur son cas de repli,
    ce qui ne testerait plus rien. Une seconde famille de 5 marches seulement, qui doit etre
    ecartee faute d'effectif. Deux lignes hors bornes, qui doivent disparaitre.
    """
    con = duckdb.connect()
    # Le type est annote explicitement : sans cela, mypy deduit `None` pour la colonne
    # `montant_anomalie` a partir de la premiere ligne, et refuse la ligne suivante qui en porte
    # une valeur.
    lignes: list[tuple[str, float, str | None, int, int, str]] = [
        (f"grande-{i}", 1000.0 + 100 * i, None, 12, 3, "45000000") for i in range(40)
    ]
    lignes.append(("grande-cher", 1_000_000.0, "montant suspect", 12, 3, "45000000"))
    lignes += [(f"petite-{i}", 5000.0, None, 6, 2, "79000000") for i in range(5)]
    lignes.append(("montant-nul", 0.0, None, 12, 1, "45000000"))
    lignes.append(("montant-absurde", 1e13, None, 12, 1, "45000000"))

    con.execute(
        "create table argent_marches (uid varchar, montant double, montant_anomalie varchar,"
        " dureeMois integer, offresRecues integer, codeCPV varchar)"
    )
    con.executemany("insert into argent_marches values (?, ?, ?, ?, ?, ?)", lignes)
    con.execute(module.PREPARATION)
    return con


def test_preparation_ecarte_les_montants_hors_bornes(base: duckdb.DuckDBPyConnection) -> None:
    """Zero euro et dix mille milliards sont des erreurs de saisie, pas des marches."""
    uids = {ligne[0] for ligne in base.sql("select uid from jeu").fetchall()}
    assert "montant-nul" not in uids
    assert "montant-absurde" not in uids


def test_preparation_ecarte_les_familles_trop_petites(base: duckdb.DuckDBPyConnection) -> None:
    """Sous trente marches, la mediane d'une famille ne veut plus rien dire."""
    uids = {ligne[0] for ligne in base.sql("select uid from jeu").fetchall()}
    assert not any(uid.startswith("petite-") for uid in uids)
    assert len(uids) == 41


def test_preparation_donne_un_ecart_positif_au_marche_cher(
    base: duckdb.DuckDBPyConnection,
) -> None:
    """Le signe de l'ecart porte toute la conclusion du notebook 08 : il est teste explicitement."""
    ecart = base.sql("select ecart_normalise from jeu where uid = 'grande-cher'").fetchone()
    assert ecart is not None
    assert ecart[0] > 0


def test_preparation_lit_l_etiquette_faible(base: duckdb.DuckDBPyConnection) -> None:
    """L'etiquette vaut vrai quand le producteur a signale le montant, et seulement dans ce cas."""
    signales = base.sql("select uid from jeu where signale_par_le_producteur").fetchall()
    assert [ligne[0] for ligne in signales] == ["grande-cher"]


def test_preparation_ne_donne_aucune_variable_derivee_de_l_etiquette(
    base: duckdb.DuckDBPyConnection,
) -> None:
    """Garde-fou contre la fuite de donnees : aucune variable donnee au modele ne doit etre
    correlee a l'etiquette par construction. On verifie ici qu'aucune ne porte son nom, ce qui
    attraperait un ajout distrait."""
    colonnes = {ligne[0] for ligne in base.sql("describe jeu").fetchall()}
    assert set(module.VARIABLES) <= colonnes
    assert not any("anomalie" in v or "signale" in v for v in module.VARIABLES)
