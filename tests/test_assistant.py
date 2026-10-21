"""Tests de l'assistant a reponses sourcees.

L'enjeu n'est pas que l'assistant reponde, mais **qu'il refuse quand il le doit** et qu'il ne
reponde jamais a une question differente de celle qui est posee. C'est la forme d'erreur
dangereuse pour cet outil : une reponse exacte sur un filtre que l'utilisateur n'a pas demande
est credible, donc elle ne se remarque pas.

Ce qu'ils attrapent : un motif d'intention qui ne consomme pas ses mots, un refus qui cesse de
fonctionner, un mot inconnu avale en silence, du SQL assemble par formatage de chaine, un jeu de
questions mal forme, une ligne du jeu dont l'intention attendue n'existe pas.

Ce qu'ils n'attrapent pas : la pertinence d'une reponse. Et surtout pas la **generalisation** :
les quarante questions du jeu ont ete ecrites par la meme personne que les motifs, donc un score
de 100 % mesure la coherence interne, pas la capacite a comprendre une question nouvelle. Seul un
jeu ecrit par quelqu'un d'autre le mesurerait. C'est note dans l'ADR 0009 comme une limite, et
c'est la raison pour laquelle ce chiffre n'est pas presente comme un resultat de qualite.

Aucun de ces tests n'a besoin de PostgreSQL : `lire` recoit ses lexiques en parametre, et c'est
precisement pour cela qu'il les recoit.
"""

import csv
from pathlib import Path

import pytest

from services.assistant import lecture_question
from services.assistant.lecture_question import (
    INTENTIONS,
    MOT_VIDE,
    Lexiques,
    lire,
    plier,
)

RACINE = Path(__file__).resolve().parent.parent
JEU = RACINE / "mesures" / "verification" / "questions-assistant.csv"

# Les intentions que le jeu de questions peut nommer. Le refus n'est pas dans `INTENTIONS` :
# c'est un comportement, pas une operation sur les donnees.
INTENTIONS_CONNUES = {nom for nom, _ in INTENTIONS} | {"extraits", "refus"}

# Un vocabulaire minuscule, ecrit a la main, avec les frequences reellement mesurees le
# 21 octobre 2026 sur l'echantillon de 5 %. Les tests portent donc sur les memes ordres de
# grandeur que la production, sans conteneur.
FREQUENCES = {
    "voir": 0.0205,  # voirie
    "scolair": 0.0289,
    "restaur": 0.0271,
    "toitur": 0.0036,
    "logiciel": 0.0074,
    "a": 0.2329,  # la preposition accentuee, qui a cesse d'etre un mot vide
    "le": 0.1331,  # entre par la porte de son pluriel
    "travau": 0.1730,  # vrai vocabulaire du domaine, et pourtant au-dessus du plafond
    "quel": 0.00015,  # trop rare : un mot de question, pas de domaine
}

# Les mots que PostgreSQL ne met pas dans l'index. La liste reproduit fidelement la liste
# francaise, **y compris ses deux trous mesures** : « a » et « les » n'y figurent pas, parce
# qu'ils ne sont pas des mots vides pour la configuration `public.francais`. Les mettre ici
# rendrait les tests plus verts et moins vrais, et ferait disparaitre le defaut que le plafond de
# frequence existe pour rattraper.
MOTS_VIDES = {
    "de",
    "la",
    "en",
    "pour",
    "dans",
    "sont",
    "est",
    "du",
    "des",
    "au",
    "aux",
    "et",
    "ou",
    "le",
    "qui",
    "me",
    "vous",
}


def frequence(mot: str) -> float:
    """La fonction que `charger_lexiques` fabrique a partir de la base, ici ecrite a la main."""
    if mot in MOTS_VIDES:
        return MOT_VIDE
    # Racinisation grossiere, suffisante pour les mots de ces tests. La vraie vient de
    # PostgreSQL, et c'est tout l'interet de passer les lexiques en parametre.
    #
    # Le prefixe doit faire au moins trois lettres, sinon « assurance » serait rapproche de la
    # racine « a » et heriterait de sa frequence de 23 %.
    for racine, part in FREQUENCES.items():
        if mot == racine or (len(racine) >= 3 and mot.startswith(racine)):
            return part
    return 0.0


@pytest.fixture
def lexiques() -> Lexiques:
    return Lexiques(
        regions={"ile de france": "Île-de-France", "bretagne": "Bretagne"},
        departements={"rhone": "Rhône", "loire atlantique": "Loire-Atlantique"},
        frequence=frequence,
        annees=(2015, 2026),
    )


# --- Le pliage ---------------------------------------------------------------


def test_le_pliage_retire_les_accents_et_la_ponctuation() -> None:
    assert plier("Rénovation de l'école, 2023 !") == "renovation de l ecole 2023"


def test_le_pliage_rend_les_deux_orthographes_identiques() -> None:
    # C'est la condition pour qu'un motif ecrit sans accents reconnaisse la question accentuee.
    assert plier("Île-de-France") == plier("ile de france")


# --- Les intentions ---------------------------------------------------------


@pytest.mark.parametrize(
    ("question", "attendue"),
    [
        ("combien de marches de voirie", "comptage"),
        ("nombre de marches de voirie", "comptage"),
        ("quel montant total pour la restauration scolaire", "montant"),
        ("combien coute la restauration scolaire", "montant"),
        ("qui a remporte les marches de voirie", "titulaires"),
        ("quelles entreprises fournissent des logiciels", "titulaires"),
        ("qui achete des logiciels", "acheteurs"),
        ("quelles collectivites achetent des logiciels", "acheteurs"),
        ("quels marches de voirie sont signales", "signales"),
        ("marches atypiques de voirie", "signales"),
        ("restauration scolaire", "extraits"),
    ],
)
def test_les_intentions_sont_reconnues(question: str, attendue: str, lexiques: Lexiques) -> None:
    assert lire(question, lexiques).intention == attendue


def test_combien_coute_est_une_somme_et_non_un_comptage(lexiques: Lexiques) -> None:
    """L'ordre des motifs compte, et ce test le fige.

    « combien coute » contient « combien ». Si le motif du comptage etait teste avant celui du
    montant, la question serait comprise comme un denombrement.
    """
    assert lire("combien coutent les marches de voirie", lexiques).intention == "montant"


# --- La consommation des mots declencheurs ----------------------------------


def test_l_intention_retire_ses_mots_du_texte_cherche(lexiques: Lexiques) -> None:
    question = lire("qui a remporte les marches de voirie", lexiques)
    assert question.texte == "voirie"


def test_l_intention_retire_toutes_les_occurrences(lexiques: Lexiques) -> None:
    """Le defaut du 21 octobre 2026 : `re.search` ne retirait que la premiere occurrence.

    « quel montant total » declenche l'intention sur « montant », et « total » restait. La
    requete cherchait alors des marches contenant le mot « total » : zero resultat.
    """
    question = lire("quel montant total pour la restauration scolaire", lexiques)
    assert "total" not in question.texte
    assert question.texte == "restauration scolaire"


def test_le_superlatif_ne_part_pas_dans_le_texte(lexiques: Lexiques) -> None:
    question = lire("qui achete le plus de logiciels", lexiques)
    assert question.texte == "logiciels"


def test_les_mots_de_schema_ne_partent_pas_dans_le_texte(lexiques: Lexiques) -> None:
    question = lire("liste des marches de voirie", lexiques)
    assert question.texte == "voirie"


# --- Le filtre par frequence -------------------------------------------------


def test_un_mot_vide_est_ecarte_avec_la_bonne_raison(lexiques: Lexiques) -> None:
    """Dire a l'utilisateur que « de » est « trop frequent » serait faux.

    Il n'est pas indexe du tout. Les deux cas meritent deux messages, et la distinction est la
    raison d'etre de la sentinelle `MOT_VIDE`.
    """
    question = lire("marches de voirie", lexiques)
    raisons = dict(question.ecartes)
    assert "mot vide" in raisons["de"]


def test_un_mot_trop_frequent_est_ecarte(lexiques: Lexiques) -> None:
    question = lire("travaux de voirie", lexiques)
    raisons = dict(question.ecartes)
    assert "trop frequent" in raisons["travaux"]
    assert question.texte == "voirie"


def test_un_mot_trop_frequent_ne_compte_pas_comme_perdu(lexiques: Lexiques) -> None:
    """« travaux » est ecarte, mais la question reste la meme : on cherche toujours de la voirie.

    Seul un mot absent de l'index change la question posee.
    """
    assert lire("travaux de voirie", lexiques).perdus == []


def test_un_mot_inconnu_est_compte_comme_perdu(lexiques: Lexiques) -> None:
    assert lire("marches de dsfgdsfg et de voirie", lexiques).perdus == ["dsfgdsfg"]


# --- Les refus ---------------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "quel est le meilleur fournisseur de voirie",
        "quelle entreprise est la plus fiable",
        "qui a fraude sur les marches de voirie",
        "quels titulaires sont corrompus",
        "quelle entreprise me recommandez-vous",
    ],
)
def test_une_demande_d_appreciation_ou_d_accusation_est_refusee(
    question: str, lexiques: Lexiques
) -> None:
    analysee = lire(question, lexiques)
    assert analysee.intention == "refus"
    assert analysee.refus


def test_le_refus_d_accusation_explique_le_taux_de_faux_positifs(lexiques: Lexiques) -> None:
    """Le refus doit dire pourquoi, sinon il passe pour une limite technique.

    48 % des signalements de prix sont des faux positifs (ADR 0006). C'est le fait qui rend la
    reponse impossible, et il doit figurer dans le message.
    """
    refus = lire("qui a fraude", lexiques).refus or ""
    assert "48" in refus


@pytest.mark.parametrize("annee", [2030, 1998, 2099])
def test_une_annee_hors_periode_est_refusee(annee: int, lexiques: Lexiques) -> None:
    analysee = lire(f"combien de marches de voirie en {annee}", lexiques)
    assert analysee.intention == "refus"
    assert "2015" in (analysee.refus or "")


def test_une_annee_dans_la_periode_est_acceptee(lexiques: Lexiques) -> None:
    assert lire("combien de marches de voirie en 2023", lexiques).annee == 2023


def test_une_question_sans_aucun_critere_est_refusee(lexiques: Lexiques) -> None:
    assert lire("combien", lexiques).intention == "refus"


def test_un_mot_inconnu_seul_fait_refuser_meme_avec_une_annee(lexiques: Lexiques) -> None:
    """Le defaut A40, et sa correction.

    Repondre « 272 057 marches notifies en 2023 » a la question « combien de marches de dsfgdsfg
    en 2023 » est exact et sans rapport. Une reponse juste a une autre question est une reponse
    fausse.
    """
    analysee = lire("combien de marches de dsfgdsfg en 2023", lexiques)
    assert analysee.intention == "refus"
    assert "dsfgdsfg" in (analysee.refus or "")


# --- Les entites ------------------------------------------------------------


def test_la_region_est_reconnue_et_retiree_du_texte(lexiques: Lexiques) -> None:
    analysee = lire("marches de voirie en Ile-de-France", lexiques)
    assert analysee.region == "Île-de-France"
    assert "france" not in analysee.texte


def test_le_departement_est_reconnu(lexiques: Lexiques) -> None:
    assert lire("marches de voirie dans le Rhone", lexiques).departement == "Rhône"


def test_le_nom_le_plus_long_est_reconnu_en_premier(lexiques: Lexiques) -> None:
    """« Loire-Atlantique » ne doit pas etre lu comme « Loire ».

    Le lexique est trie par longueur decroissante pour cette raison. Sans ce tri, le resultat
    depend de l'ordre de parcours d'un dictionnaire, donc de l'ordre d'insertion : un defaut qui
    apparait et disparait au rechargement des donnees.
    """
    lexiques_pieges = Lexiques(
        regions={},
        departements={"loire": "Loire", "loire atlantique": "Loire-Atlantique"},
        frequence=frequence,
        annees=(2015, 2026),
    )
    assert (
        lire("marches de voirie en Loire-Atlantique", lexiques_pieges).departement
        == "Loire-Atlantique"
    )


# --- Le jeu de questions -----------------------------------------------------


def test_le_jeu_de_questions_est_bien_forme() -> None:
    with JEU.open(encoding="utf-8") as fichier:
        lignes = list(csv.DictReader(fichier))

    assert len(lignes) >= 40, "le jeu doit couvrir au moins quarante questions"

    identifiants = [ligne["id"] for ligne in lignes]
    assert len(identifiants) == len(set(identifiants)), "identifiants en double"

    for ligne in lignes:
        assert ligne["intention_attendue"] in INTENTIONS_CONNUES, (
            f"{ligne['id']} : intention inconnue {ligne['intention_attendue']!r}"
        )
        assert ligne["comportement_attendu"] in {"repond", "refuse"}, (
            f"{ligne['id']} : comportement inconnu"
        )
        assert ligne["commentaire"].strip(), f"{ligne['id']} : commentaire vide"


def test_le_jeu_contient_assez_de_refus() -> None:
    """Un jeu sans refus mesurerait seulement la capacite a repondre.

    Le refus est la moitie du sujet : un assistant qui repond toujours invente. Au moins un
    cinquieme des questions doivent attendre un refus.
    """
    with JEU.open(encoding="utf-8") as fichier:
        lignes = list(csv.DictReader(fichier))
    refus = sum(1 for ligne in lignes if ligne["comportement_attendu"] == "refuse")
    assert refus >= len(lignes) // 5, f"seulement {refus} refus attendus sur {len(lignes)}"


def test_chaque_intention_est_couverte_par_le_jeu() -> None:
    with JEU.open(encoding="utf-8") as fichier:
        attendues = {ligne["intention_attendue"] for ligne in csv.DictReader(fichier)}
    manquantes = INTENTIONS_CONNUES - attendues
    assert not manquantes, f"intentions jamais testees : {sorted(manquantes)}"


# --- Le SQL ------------------------------------------------------------------


def test_aucune_requete_n_est_assemblee_par_formatage_de_chaine() -> None:
    """Le filtre varie d'une question a l'autre : c'est exactement la ou l'on ecrit une injection.

    Les valeurs doivent rester des parametres, et seuls des litteraux de ce fichier devenir du
    SQL. Le test lit le source plutot que de faire confiance a la relecture.
    """
    source = (RACINE / "services" / "assistant" / "reponse_sourcee.py").read_text(encoding="utf-8")
    for interdit in ('f"select', "f'select", 'f"""select', "% (question", ".format(question"):
        assert interdit not in source.lower(), f"SQL assemble par chaine : {interdit!r}"
    assert "from psycopg import sql" in source, "la composition sure de psycopg doit etre utilisee"


def test_les_seuils_du_filtre_restent_dans_un_ordre_coherent() -> None:
    assert 0 < lecture_question.PLANCHER < lecture_question.PLAFOND < 1
