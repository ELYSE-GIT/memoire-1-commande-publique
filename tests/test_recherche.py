"""Tests du banc d'essai de la recherche.

L'enjeu n'est pas la vitesse des moteurs mais **la validite de la comparaison**. Un banc qui
donne a un moteur une question nettoyee et a l'autre la question brute produit des chiffres
plausibles et une conclusion fausse. C'est arrive le 11 octobre 2026 : DuckDB paraissait muet sur
29 questions sur 30 alors qu'il ne recevait simplement pas la meme question.

Ce qu'ils attrapent : un nettoyage de question casse, un jeu de questions mal forme, du SQL
assemble par formatage de chaine, une liste de mots vides vide ou illisible.
Ce qu'ils n'attrapent pas : une question mal choisie. Cela se corrige en relisant le jeu, et
c'est pourquoi il est versionne plutot que genere.
"""

import csv
from pathlib import Path

from mesures import recherche

RACINE = Path(__file__).resolve().parent.parent

TYPES_CONNUS = {
    "mots_cles",
    "mots_cles_et_lieu",
    "mots_cles_et_annee",
    "mots_cles_et_acheteur",
    "mots_cles_et_montant",
    "mots_cles_et_categorie",
    "acheteur",
    "acheteur_et_annee",
    "titulaire",
    "lieu_et_annee",
    "question_naturelle",
    "paraphrase",
    "faute_de_frappe",
    "sans_accent",
    "marque",
    "probablement_sans_reponse",
}


# --- Le nettoyage des questions ----------------------------------------------


def test_le_nettoyage_retire_les_mots_vides() -> None:
    """« travaux de voirie » doit devenir « travaux voirie ».

    C'est exactement le cas qui faisait echouer DuckDB : « de » a ete retire du texte indexe,
    donc l'exiger dans la question ne peut rien trouver.
    """
    assert recherche.nettoyer_pour_duckdb("travaux de voirie", {"de"}) == "travaux voirie"


def test_le_nettoyage_retire_les_accents() -> None:
    """Un utilisateur ne tape pas les accents dans une barre de recherche."""
    assert recherche.nettoyer_pour_duckdb("rénovation énergétique", set()) == (
        "renovation energetique"
    )


def test_le_nettoyage_coupe_sur_les_apostrophes() -> None:
    """En francais l'apostrophe separe deux mots : « l'ecole » vaut « ecole »."""
    nettoye = recherche.nettoyer_pour_duckdb("l'ecole et l’hopital", {"et", "l"})
    assert nettoye == "ecole hopital"


def test_le_nettoyage_ne_rend_pas_une_chaine_vide_inattendue() -> None:
    """Une question faite uniquement de mots vides doit donner une chaine vide, pas une erreur."""
    assert recherche.nettoyer_pour_duckdb("de la pour", {"de", "la", "pour"}) == ""


def test_la_liste_de_mots_vides_est_lisible_et_fournie() -> None:
    """La liste vient de PostgreSQL. Si elle disparait, la comparaison perd sa validite."""
    vides = recherche.mots_vides()
    assert len(vides) > 100
    # Les commentaires d'entete ne doivent pas se retrouver parmi les mots.
    assert not any(mot.startswith("#") for mot in vides)
    for attendu in ("de", "la", "pour", "des"):
        assert attendu in vides


# --- Le jeu de questions -----------------------------------------------------


def lire_questions() -> list[dict[str, str]]:
    chemin = RACINE / "mesures" / "verification" / "questions-de-recherche.csv"
    with chemin.open(encoding="utf-8") as fichier:
        return list(csv.DictReader(fichier))


def test_les_identifiants_de_questions_sont_uniques() -> None:
    """Deux questions avec le meme identifiant rendraient les resultats impossibles a relier."""
    identifiants = [ligne["id"] for ligne in lire_questions()]
    assert len(identifiants) == len(set(identifiants))


def test_chaque_question_porte_un_type_connu() -> None:
    """Le type sert a analyser ou la recherche echoue. Une faute de frappe le rendrait muet."""
    for ligne in lire_questions():
        assert ligne["type"] in TYPES_CONNUS, f"{ligne['id']} : type inconnu {ligne['type']!r}"


def test_le_jeu_couvre_les_cas_difficiles() -> None:
    """Un jeu fait uniquement de mots cles bien choisis ne mesurerait rien d'utile.

    Quatre types doivent etre presents : la paraphrase, la faute de frappe, l'absence d'accents,
    et au moins une question qui ne doit rien trouver.
    """
    types = {ligne["type"] for ligne in lire_questions()}
    for indispensable in (
        "paraphrase",
        "faute_de_frappe",
        "sans_accent",
        "probablement_sans_reponse",
    ):
        assert indispensable in types


def test_une_dizaine_de_questions_est_marquee_pour_le_jugement() -> None:
    """La pertinence se juge a la main : trop peu de questions et la mesure ne vaut rien, trop et
    personne ne le fera."""
    a_juger = [ligne for ligne in lire_questions() if ligne["a_juger"] == "oui"]
    assert 8 <= len(a_juger) <= 14


# --- Le SQL ------------------------------------------------------------------


def test_aucune_requete_n_est_assemblee_par_formatage() -> None:
    """Regle du depot : tout parametre passe par une liaison, jamais par une chaine.

    Le controle porte sur le fichier lui-meme, parce qu'une relecture humaine laisse passer ce
    genre de chose, et que l'analyse de securite du depot ne couvre pas toutes les formes.
    """
    source = (RACINE / "mesures" / "recherche.py").read_text(encoding="utf-8")
    for requete in ("REQUETE_PG_ET", "REQUETE_PG_OU", "REQUETE_DUCKDB_ET", "REQUETE_DUCKDB_OU"):
        assert f'{requete} = """' in source
    assert ".format(" not in source


def test_les_deux_requetes_duckdb_ne_different_que_par_la_conjonction() -> None:
    """Si elles differaient par autre chose, on comparerait deux requetes, pas deux semantiques."""
    et = recherche.REQUETE_DUCKDB_ET.replace("conjunctive := 1", "X")
    ou = recherche.REQUETE_DUCKDB_OU.replace("conjunctive := 0", "X")
    assert et == ou


def test_les_deux_requetes_postgres_ne_different_que_par_la_conjonction() -> None:
    """Meme exigence cote PostgreSQL : seule la combinaison des mots change."""
    assert "replace(" in recherche.REQUETE_PG_OU
    assert "replace(" not in recherche.REQUETE_PG_ET
    # Le reste de la requete, apres le bloc d'analyse, doit etre identique.
    corps_et = recherche.REQUETE_PG_ET.split(")\n", 1)[1]
    corps_ou = recherche.REQUETE_PG_OU.split(")\n", 1)[1]
    assert corps_et == corps_ou


# --- L'ecriture des resultats a juger ----------------------------------------


def test_les_objets_sont_ramenes_sur_une_seule_ligne() -> None:
    """Un objet de marche contenant un retour chariot couperait la ligne du CSV a juger.

    Constate le 11 octobre 2026 : git signalait des fins de ligne Windows dans le fichier des
    resultats, parce que certains objets, saisis par des agents differents, en contiennent.
    """
    assert recherche.sur_une_ligne("Travaux\r\nde voirie") == "Travaux de voirie"
    assert recherche.sur_une_ligne("Lot 1\tToiture") == "Lot 1 Toiture"
    assert recherche.sur_une_ligne("  espaces   multiples  ") == "espaces multiples"
    assert recherche.sur_une_ligne(None) == ""
    assert recherche.sur_une_ligne("") == ""
