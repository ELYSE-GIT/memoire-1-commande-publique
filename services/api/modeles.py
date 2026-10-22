"""Les formes de reponse de l'API, declarees une fois et verifiees par FastAPI.

Pourquoi des modeles et pas des dictionnaires. Un `dict` renvoye tel quel par une route marche
tres bien jusqu'au jour ou une requete SQL change de colonne : la reponse change de forme sans
que rien n'echoue, et c'est le site qui casse en silence. Un modele declare la forme une fois, la
verifie a chaque reponse, et la publie dans la documentation OpenAPI sans travail
supplementaire.

    Option envisagee        Avantage                    Limite                       Verdict
    renvoyer les lignes     zero code a ecrire          la forme de la reponse suit   ecarte
    SQL telles quelles                                  le SQL sans prevenir, et la
                                                        documentation est fausse
    **modeles Pydantic**    la forme est verifiee a     il faut tenir deux listes de  **retenu**
                            chaque reponse, et la       champs a jour, le SQL et le
                            documentation est generee   modele, et un test verifie
                            depuis le code              qu'elles concordent
    dataclasses + json      pas de dependance en plus   aucune validation, et pas de  ecarte
                                                        documentation generee         (Pydantic
                                                                                       vient deja
                                                                                       avec
                                                                                       FastAPI)

A quelle echelle la reponse changerait : pour une API interne a un seul consommateur ecrit par
la meme personne, le dictionnaire suffirait. Ici l'API est publique, donc sa forme est un
engagement.

Tous les montants sont en euros, toutes les dates au format ISO (AAAA-MM-JJ), et un champ absent
dans la source reste `null` plutot que d'etre comble par une valeur inventee.
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class Marche(BaseModel):
    """Un marche attribue, tel qu'une liste de resultats l'affiche."""

    marche_id: str = Field(
        description="Numero du marche. NON UNIQUE : un marche a autant de "
        "lignes que de titulaires dans un groupement"
    )
    objet: str | None = Field(default=None, description="Objet du marche, tel que publie")
    acheteur_nom: str | None = None
    acheteur_departement_nom: str | None = None
    acheteur_categorie: str | None = None
    titulaire_nom: str | None = None
    titulaire_categorie: str | None = Field(
        default=None, description="PME, ETI, GE ou null quand le SIRET n'a pas ete resolu"
    )
    # `Decimal` et non `float` : c'est de l'argent, et la colonne est en `numeric(18, 2)`.
    # Un flottant binaire ne represente pas exactement 0,01 euro.
    montant: Decimal | None = None
    date_notification: date | None = None
    annee: int | None = None
    famille_cpv: str | None = None
    procedure: str | None = None
    offres_recues: int | None = None


class ResultatRecherche(Marche):
    """Un marche trouve par la recherche, avec son score de pertinence."""

    score: float = Field(
        description="Score de proximite des mots, calcule par PostgreSQL. "
        "Comparable entre les resultats d'une meme requete, "
        "pas d'une requete a l'autre"
    )


class Signal(BaseModel):
    """Ce qui a ete remarque sur un marche, et a quoi il a ete compare.

    Un signalement sans sa raison n'est pas exploitable : un acheteur a qui l'on dit « ce marche
    est anormal » demandera legitimement pourquoi, et « le calcul l'a decide » n'est pas une
    reponse. Les colonnes de comparaison sont donc exposees avec le verdict.
    """

    marche_id: str
    famille_cpv: str | None = None
    marches_dans_la_famille: int | None = Field(
        default=None,
        description="Taille du groupe de comparaison. En dessous de 30, la "
        "mediane du groupe n'est pas fiable et aucun signal de prix "
        "n'est emis",
    )
    ecart_normalise_famille: float | None = Field(
        default=None,
        description="(montant moins la mediane du groupe) divise par l'ecart "
        "interquartile, en log10. Au-dela de 4, le prix est signale",
    )
    prix_tres_eleve: bool = False
    prix_eleve_a_verifier: bool = False
    prix_tres_bas_non_evalue: bool = Field(
        default=False,
        description="Signal expose mais NON EVALUE : aucune etiquette disponible "
        "ne le confirme ni ne l'infirme",
    )
    offre_unique_sur_gros_marche: bool = False
    titulaire_dominant: bool = False
    signaux_forts: int = 0
    motifs_de_signalement: list[str] = Field(default_factory=list)


class PageDeMarches(BaseModel):
    """Une page de resultats.

    Pas de nombre total de resultats, et c'est un choix mesure, pas un oubli. Voir l'en-tete de
    `services/api/requetes.py` : compter les lignes qui repondent a « travaux » obligerait
    PostgreSQL a parcourir les 57 000 lignes concernees avant de pouvoir afficher les dix
    premieres. Le site affiche donc « page suivante » ou rien, ce qui est la seule information
    dont un lecteur se serve reellement.
    """

    resultats: list[ResultatRecherche]
    page: int
    taille: int
    page_suivante: bool
    classement_approche: bool = Field(
        default=False,
        description="Vrai quand plus de resultats repondent que le service n'en classe "
        "(20 000). Les marches affiches sont alors les mieux classes parmi les 20 000 plus "
        "recents qui contiennent les mots, et non parmi tous. Mesure : sur la question "
        "« travaux », 348 748 marches repondent et aucun des dix affiches n'est dans les dix "
        "du classement exact. A afficher a l'ecran",
    )
    candidats_examines: int | None = Field(
        default=None,
        description="Nombre de marches reellement classes. Null quand la requete ne comporte "
        "aucun texte, donc aucun classement",
    )


class MarcheDetaille(BaseModel):
    """Un marche et tout ce que le projet en sait."""

    lignes: list[Marche] = Field(
        description="Une ligne par titulaire. Un marche attribue a un groupement d'entreprises "
        "en a plusieurs : 1 999 474 lignes pour 1 738 289 marches distincts"
    )
    signaux: list[Signal] = Field(default_factory=list)


class Statistiques(BaseModel):
    """Les comptages de la page d'accueil."""

    marches: int = Field(description="Lignes chargees, soit un couple marche et titulaire")
    marches_distincts: int
    acheteurs: int
    titulaires: int
    montant_total: Decimal | None = None
    premiere_annee: int | None = None
    derniere_annee: int | None = None
    marches_signales: int = Field(description="Lignes portant au moins un signal")
    calcule_a: datetime = Field(
        description="Date du calcul de ces comptages, au chargement des donnees. Un comptage "
        "sans sa date ne dit pas s'il est perime"
    )


class StatistiqueAnnuelle(BaseModel):
    """Une annee, pour la courbe de la page d'accueil.

    L'unite de comptage est l'attribution, pas le marche : un marche attribue a un groupement
    d'entreprises compte une fois par titulaire. C'est l'unite qui a un sens pour une part de
    PME, et le nom des champs le dit plutot que de laisser deviner.
    """

    annee: int
    attributions: int
    montant_total: Decimal | None = None
    attributions_resolues: int = Field(
        description="Attributions dont la categorie d'entreprise du titulaire est connue. "
        "C'est le denominateur de part_pme_pourcent, et il est publie avec elle : "
        "6,8 pour cent des attributions n'ont aucune categorie"
    )
    attributions_pme: int
    part_pme_pourcent: float | None = Field(
        default=None,
        description="Part des attributions revenant a une PME, rapportee aux seules "
        "attributions_resolues. Null quand aucune n'est resolue, ce qui se lit "
        "« on ne sait pas » et non « aucune PME »",
    )


class ReponseAssistant(BaseModel):
    """Une reponse en francais, et tout ce qu'il faut pour la verifier sans faire confiance."""

    question: str
    phrase: str
    intention: str = Field(
        description="Ce que l'assistant a cru comprendre : comptage, "
        "mediane, liste, extraits, refus..."
    )
    filtre: str = Field(
        description="Le filtre applique, en francais. Sans lui, un chiffre ne veut rien dire"
    )
    chiffres: dict[str, float | int | str | None] = Field(default_factory=dict)
    lignes: list[dict[str, str | float | int | None]] = Field(default_factory=list)
    citations: list[str] = Field(
        default_factory=list,
        description="Numeros de marche cites, verifiables un par un sur /marches/{marche_id}",
    )
    avertissement: str = Field(
        default="",
        description="Ce que la reponse ne couvre pas, quand la question demandait davantage",
    )
    duree_ms: float


class Sante(BaseModel):
    """L'etat du service, pour la supervision et pour le healthcheck du conteneur."""

    etat: str
    base_accessible: bool
    marches_charges: int | None = None
    lexiques_charges: bool = False
