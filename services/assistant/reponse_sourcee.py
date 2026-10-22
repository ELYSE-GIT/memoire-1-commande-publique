"""Repondre a une question en citant les marches d'ou vient la reponse.

=== Ce que « sourcee » veut dire ici ========================================

Une reponse sourcee n'est pas une reponse accompagnee de liens. C'est une reponse dont **chaque
chiffre est reproductible** : le filtre applique est rendu avec la reponse, en clair, et les
numeros de marche cites permettent de retrouver les lignes comptees.

La consequence est mesurable, et c'est tout l'interet : `mesures/assistant.py` recalcule chaque
chiffre par une requete ecrite autrement, et verifie que chaque numero cite existe et passe bien
le filtre annonce. Une reponse fausse est donc detectee par une machine, sans relecture humaine.

C'est ce qu'une reponse generee par un modele de langue ne permet pas. Non parce qu'un modele se
tromperait plus souvent, mais parce que **rien dans sa reponse ne dit d'ou vient le chiffre**, et
qu'il n'y a donc rien a verifier automatiquement.

=== Pourquoi aucun modele de langue a cette etape ===========================

    Option envisagee           Avantage                    Limite                       Verdict
    modele distant             phrases naturelles,         cout par question, donnees   ecarte
    (API payante)              tournures variees           envoyees a un tiers,         pour
                                                           chiffre non verifiable       l'instant
    modele local quantifie     gratuit, rien ne sort       2 a 4 Go de RAM sur un VPS   a mesurer
    (3 a 7 milliards de        de la machine               a 12 euros ; latence de      en phase 9
    parametres)                                            l'ordre de la seconde
    **gabarits de phrase**     0 euro, 0 Go, reponse       phrases rigides, une         **retenu**
                               verifiable par machine,     tournure par intention
                               latence de la requete SQL
    reponse brute (le tableau  honnete                     illisible pour qui ne        ecarte
    sans phrase)                                           connait pas le schema

A quelle echelle la reponse changerait : des que les questions cessent d'etre couvertes par six
intentions, ou qu'un utilisateur veut une synthese de plusieurs marches en prose. La marche
suivante est alors le modele local, **avec les extraits en entree et l'interdiction de sortir du
texte fourni**. Ce qui la declencherait est chiffre dans l'ADR 0009.

Les gabarits ne sont pas un pis-aller : ils rendent la reponse verifiable, ce qui est l'exigence
du sujet. Le modele de langue, lui, ameliorerait la forme en retirant cette garantie.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Any

import psycopg
from psycopg import sql

from services.assistant.lecture_question import (
    MOT_VIDE,
    PROFONDEUR,
    Lexiques,
    Question,
    lire,
)

# === Les fragments de filtre =================================================
#
# Une question donne un filtre different a chaque fois : parfois une annee, parfois une region et
# un texte, parfois rien que l'annee. La requete est donc assemblee, et c'est exactement la
# situation ou l'on ecrit une injection SQL sans le vouloir.
#
#     Option envisagee            Avantage                   Limite                     Verdict
#     f-string ou `.format`       immediat                   **refuse par Semgrep**,    exclu
#     sur la requete                                         et a juste titre : rien
#                                                            ne distingue un fragment
#                                                            litteral d'une valeur
#                                                            venue de l'utilisateur
#     ecrire les 16 combinaisons  aucune composition          16 requetes par intention, ecarte
#     de filtres a la main                                    soit 96 a maintenir
#     `coalesce` sur un filtre    une seule requete           le planificateur ne peut   ecarte
#     toujours present            (`%s is null or annee = %s`) plus utiliser l'index :
#                                                             mesure a 1,9 s au lieu
#                                                             de 8 ms
#     **composition psycopg**     les fragments sont des      une classe de plus a       **retenu**
#     **(`psycopg.sql`)**         objets `SQL`, les valeurs   connaitre
#                                 restent des parametres ;
#                                 melanger les deux est
#                                 impossible par typage
#
# Les valeurs ne traversent jamais la composition : elles sont liees en parametres, dans le meme
# ordre que les fragments. Seuls des litteraux ecrits dans ce fichier deviennent du SQL.

# Nombre de mots dont la frequence est gardee en memoire. La justification complete est a
# l'endroit ou le cache est cree, dans `charger_lexiques`.
MOTS_EN_CACHE = 20_000

FILTRE_TEXTE = "{p}recherche @@ websearch_to_tsquery('public.francais', %s)"
FILTRE_ANNEE = "{p}annee = %s"
FILTRE_REGION = "{p}acheteur_region_nom = %s"
FILTRE_DEPARTEMENT = "{p}acheteur_departement_nom = %s"

# Les six requetes. Chacune rend, en plus de ses chiffres, les numeros de marche qui les portent :
# c'est ce qui rend la reponse verifiable. `array_agg ... order by montant` prend les plus gros,
# parce que ce sont ceux qu'un relecteur veut voir en premier.

# Le comptage, demande par toutes les intentions : il dit si la question a une reponse.
#
# Trois colonnes et pas une de plus. La premiere version en demandait cinq, dont la mediane et un
# `array_agg` sur l'ensemble filtre, et c'est elle qui a rendu « combien de marches en 2023 »
# insupportable : 54 179 ms.
#
# Ce chiffre merite sa precision, sinon il se raconte mieux qu'il ne se mesure. Il a ete releve
# **sur une base froide et sans index sur l'annee**, donc il cumule trois causes : les pages lues
# depuis le disque, le balayage de deux millions de lignes, et les deux tris. Les index ajoutes le
# meme jour dans `005-index.sql` traitent les deux premieres.
#
# Reste la troisieme, qui est celle que ce fichier corrige. Mesure a chaud et index en place, sur
# les 272 057 marches de 2023, remesuree a chaque passage de `make bench-assistant` :
#
#     une requete, cinq colonnes (premiere version)      590 ms
#     retenu : trois colonnes seulement                  104 ms
#     array_agg trie sur l'ensemble filtre               330 ms
#     retenu : order by avec limit 3                     103 ms
#
# La lecon est generale : une agregation qui trie coute le prix du tri, et on ne trie pas 272 057
# lignes pour afficher trois numeros de marche. Les deux colonnes retirees sont redevenues deux
# requetes separees, chacune demandee seulement quand elle sert.
COMPTAGE = """
select count(*) as marches,
       count(montant) as avec_montant,
       coalesce(sum(montant), 0) as total
from marches
where {filtres}
"""

# La mediane, demandee par la seule intention qui l'affiche. Un tri reste un tri : cette requete
# coute des secondes sur une grosse tranche, et c'est assume parce qu'une question sur un montant
# total porte presque toujours un filtre de texte, qui ramene l'ensemble a quelques milliers de
# lignes.
MEDIANE = """
select percentile_cont(0.5) within group (order by montant) as mediane
from marches
where {filtres}
"""

# Les trois marches cites. `limit 3` apres un `order by` indexe, au lieu d'un `array_agg` sur
# l'ensemble : PostgreSQL s'arrete apres trois lignes au lieu de trier tout l'ensemble.
CITATIONS = """
select marche_id
from marches
where {filtres}
order by montant desc nulls last
limit 3
"""

TITULAIRES = """
select titulaire_nom as nom,
       count(*) as marches,
       coalesce(sum(montant), 0) as total,
       (array_agg(marche_id order by montant desc nulls last))[1:3] as citations
from marches
where {filtres} and titulaire_nom is not null
group by titulaire_nom
order by marches desc, total desc
limit %s
"""

ACHETEURS = """
select acheteur_nom as nom,
       count(*) as marches,
       count(distinct titulaire_siret) as titulaires,
       coalesce(sum(montant), 0) as total,
       (array_agg(marche_id order by montant desc nulls last))[1:3] as citations
from marches
where {filtres} and acheteur_nom is not null
group by acheteur_nom
order by marches desc, total desc
limit %s
"""

EXTRAITS = """
select marche_id, objet, acheteur_nom, titulaire_nom, montant, annee
from marches
where {filtres}
order by montant desc nulls last
limit %s
"""

# Les marches signales. La jointure se fait sur `marche_id`, qui n'est pas unique : un marche a
# autant de lignes que de titulaires. `distinct on` garde donc une ligne par marche, et le
# commentaire est necessaire parce que le lecteur se demandera pourquoi.
SIGNALES = """
select distinct on (m.marche_id)
       m.marche_id, m.objet, m.acheteur_nom, m.montant,
       s.signaux_forts, s.motifs_de_signalement
from marches m
join signaux s on s.marche_id = m.marche_id
where {filtres} and s.signaux_forts > 0
order by m.marche_id, s.signaux_forts desc, m.montant desc nulls last
limit %s
"""


@dataclass
class Reponse:
    """Une reponse, et tout ce qu'il faut pour la verifier sans faire confiance."""

    question: Question
    phrase: str
    # Les chiffres annonces, nommes. `mesures/assistant.py` les recalcule un par un.
    chiffres: dict[str, Any] = field(default_factory=dict)
    # Le tableau affiche sous la phrase.
    lignes: list[dict[str, Any]] = field(default_factory=list)
    # Les numeros de marche cites. Verifies un par un pendant les mesures.
    citations: list[str] = field(default_factory=list)
    # Le filtre applique, en francais. Sans lui, un chiffre ne veut rien dire.
    filtre: str = ""
    # Ce que la reponse ne couvre pas, quand la question demandait davantage.
    avertissement: str = ""
    duree_ms: float = 0.0


# Les valeurs distinctes d'une colonne indexee, par saut de valeur en valeur dans l'index.
#
# `select distinct acheteur_region_nom from marches` demande vingt-quatre valeurs. PostgreSQL ne
# sait pas sauter dans un index (il n'a pas de « skip scan »), mais on peut l'ecrire a la main :
# partir de la plus petite valeur, puis demander repetitivement la plus petite valeur strictement
# superieure a la precedente. Vingt-cinq descentes d'index au lieu d'un parcours. Le procede est
# connu sous le nom de « loose index scan », et il suppose un index sur la colonne.
#
# Les mesures, dans l'ordre ou elles ont ete faites le 21 octobre 2026, parce que l'ordre change
# la conclusion :
#
#     select distinct, avant l'index sur la region      4 161 ms
#     select distinct, apres l'index sur la region         46 ms   (parcours d'index seul)
#     cette requete, apres l'index                        0,7 ms
#
# La premiere version de ce commentaire opposait 4 161 ms a 15 ms et attribuait tout le gain a la
# requete recursive. C'etait faux, et c'est le banc qui l'a montre en remesurant les deux versions
# cote a cote une fois les index en place : **l'index fait l'essentiel du travail**, en permettant
# un parcours d'index seul au lieu d'un balayage de la table. La requete recursive ajoute un
# facteur 66 par-dessus, ce qui reste utile et n'est pas ce qui sauve le demarrage.
#
# Deux changements faits le meme jour ne se mesurent pas ensemble. C'est la raison pour laquelle
# les deux versions restent ecrites dans `mesures/assistant.py` plutot que racontees ici.
VALEURS_DISTINCTES_REGION = """
with recursive valeurs as (
    select min(acheteur_region_nom) as valeur from marches
    union all
    select (select min(acheteur_region_nom) from marches
            where acheteur_region_nom > valeurs.valeur)
    from valeurs where valeurs.valeur is not null
)
select valeur from valeurs where valeur is not null
"""

VALEURS_DISTINCTES_DEPARTEMENT = """
with recursive valeurs as (
    select min(acheteur_departement_nom) as valeur from marches
    union all
    select (select min(acheteur_departement_nom) from marches
            where acheteur_departement_nom > valeurs.valeur)
    from valeurs where valeurs.valeur is not null
)
select valeur from valeurs where valeur is not null
"""


def charger_lexiques(
    curseur: psycopg.Cursor[Any],
    curseur_pour_les_mots: Callable[[], AbstractContextManager[psycopg.Cursor[Any]]] | None = None,
) -> Lexiques:
    """Lire dans la base ce dont l'analyseur a besoin.

    Appele une fois au demarrage du service, pas a chaque question : ce sont 131 noms de lieux et
    73 722 lexemes, qui ne changent qu'a la recollecte. La frequence est servie depuis un
    dictionnaire en memoire, soit environ 3 Mo, ce qui evite une lecture par mot.

    === Pourquoi un second argument ============================================

    La fonction `frequence` rendue dans les lexiques a besoin de la base : elle demande a
    PostgreSQL de raciniser un mot inconnu, pour le chercher sous la meme forme que l'index.
    Tant que l'appelant est un banc de mesure, le curseur de chargement reste ouvert pendant
    toute l'execution et peut servir.

    Dans un service, non : le curseur du demarrage est rendu a la reserve des que les lexiques
    sont charges, et la premiere question recoit « the cursor is closed ». Le defaut a ete
    trouve par `make bench-api` le 22 octobre 2026, apres vingt-et-un appels en erreur 503.

        Option envisagee          Avantage                   Limite                    Verdict
        garder le curseur du      aucun changement           une connexion monopolisee  ecarte
        demarrage ouvert                                      pour toute la duree du
                                                              service, et un seul
                                                              curseur partage entre
                                                              tous les visiteurs
        raciniser en Python       aucune base a interroger   ce ne serait plus la meme  ecarte
                                                              racinisation que l'index,
                                                              donc des mots introuvables
        precharger la             tout en memoire            on ne connait pas a        ecarte
        racinisation de tous                                  l'avance les mots que les
        les mots possibles                                    visiteurs taperont
        **laisser l'appelant      le banc garde son          un argument de plus, avec  **retenu**
        fournir un curseur**      comportement, le service   une valeur par defaut

    Sans ce second argument, le comportement est exactement celui d'avant : le curseur de
    chargement est reutilise.
    """
    from services.assistant.lecture_question import plier

    curseur.execute(VALEURS_DISTINCTES_REGION)
    regions = {plier(ligne[0]): ligne[0] for ligne in curseur.fetchall()}

    curseur.execute(VALEURS_DISTINCTES_DEPARTEMENT)
    departements = {plier(ligne[0]): ligne[0] for ligne in curseur.fetchall()}

    # La periode couverte, demandee a `date_notification` et non a `annee`.
    #
    # Les deux colonnes disent la meme chose : verifie le 21 octobre 2026 sur les 1 999 474
    # lignes, zero desaccord, zero valeur absente, et un test le reverifie. Mais une seule des
    # deux porte un index B-tree, et un `min` ou un `max` sur une colonne indexee est une
    # descente d'index au lieu d'un balayage.
    #
    #     min et max sur annee                   347 ms (balayage, meme index BRIN en place)
    #     min et max sur date_notification         0,6 ms (index marches_date_idx)
    #
    # L'index BRIN de l'annee ne sert a rien ici : il donne un intervalle par groupe de pages,
    # ce qui permet de filtrer mais pas de trouver un extremum sans lire les pages.
    curseur.execute(
        "select extract(year from min(date_notification))::int,"
        "       extract(year from max(date_notification))::int"
        " from marches"
    )
    premiere, derniere = curseur.fetchone()  # type: ignore[misc]

    curseur.execute("select lexeme, marches, echantillon from vocabulaire")
    frequences: dict[str, float] = {}
    for lexeme, marches, echantillon in curseur.fetchall():
        frequences[lexeme] = marches / echantillon if echantillon else 0.0

    # Le mot de la question doit etre racinise avant d'etre cherche dans le vocabulaire, qui ne
    # contient que des lexemes. On demande la racinisation a PostgreSQL plutot que de la
    # reimplementer : c'est la meme que celle de l'index, par construction.
    # Cache **borne**, et la borne n'est pas decorative.
    #
    # Tant que cette fonction ne servait qu'a `make bench-assistant`, elle voyait 40 questions
    # ecrites a la main : quelques centaines de mots, dans un processus qui s'arrete. Depuis que
    # l'API l'expose, elle voit ce qu'un inconnu tape. Un dictionnaire sans borne grandit alors
    # d'une entree par mot jamais vu, indefiniment, dans un service qui tourne des semaines.
    # C'est une facon simple de faire consommer de la memoire a un serveur, et elle ne demande
    # aucun privilege : il suffit d'envoyer des mots differents.
    #
    #     Option envisagee        Avantage                   Limite                    Verdict
    #     aucun cache             rien a borner              une requete a la base par  ecarte
    #                                                        mot, a chaque question
    #     cache sans borne        le plus simple             grandit avec ce qu'on lui  exclu
    #                                                        envoie : c'est le defaut
    #     **cache borne, le       memoire plafonnee, et les  les mots rares sont        **retenu**
    #     plus ancien sort**      mots courants restent      recalcules s'ils reviennent
    #     cache avec expiration   suit l'evolution du        une date par entree pour   ecarte
    #     par duree               vocabulaire                un vocabulaire qui ne
    #                                                        change qu'a la recollecte
    #
    # 20 000 entrees : largement au-dessus du vocabulaire reel des questions, et tres en dessous
    # des 74 055 lexemes de la table. Une entree est un mot court et un flottant, donc quelques
    # mega-octets au pire.
    #
    # Ce que cette borne ne protege pas : chaque mot inconnu coute une requete a la base, cache
    # ou non. Limiter le **nombre d'appels** appartient au reverse-proxy, qui est le seul a voir
    # la vraie adresse de l'appelant. Voir l'ADR 0011.
    cache: OrderedDict[str, float] = OrderedDict()

    def raciniser(mot: str) -> str | None:
        """Demande la racinisation a PostgreSQL, sur un curseur encore valide."""
        requete = "select to_tsvector('public.francais', %s)::text"
        if curseur_pour_les_mots is None:
            curseur.execute(requete, (mot,))
            return str(curseur.fetchone()[0])  # type: ignore[index]
        with curseur_pour_les_mots() as frais:
            frais.execute(requete, (mot,))
            return str(frais.fetchone()[0])  # type: ignore[index]

    def frequence(mot: str) -> float:
        if mot in cache:
            # Remis en fin de file : un mot qui ressert ne doit pas etre le prochain a sortir.
            cache.move_to_end(mot)
            return cache[mot]

        vecteur = raciniser(mot)
        if not vecteur:
            # Mot vide pour PostgreSQL : il n'entrerait pas dans la requete de toute facon,
            # et la raison affichee a l'utilisateur doit le dire ainsi.
            valeur = MOT_VIDE
        else:
            lexeme = vecteur.split("'")[1]
            valeur = frequences.get(lexeme, 0.0)

        cache[mot] = valeur
        if len(cache) > MOTS_EN_CACHE:
            # Le plus anciennement utilise sort. `last=False` prend le debut de la file.
            cache.popitem(last=False)
        return valeur

    return Lexiques(
        regions=regions,
        departements=departements,
        frequence=frequence,
        annees=(int(premiere), int(derniere)),
    )


def construire_filtre(question: Question, prefixe: str = "") -> tuple[sql.Composed, list[Any], str]:
    """Assembler le filtre SQL, ses parametres, et sa version lisible par un humain.

    La troisieme valeur n'est pas un luxe : c'est elle qui rend le chiffre interpretable. « 221
    marches » ne veut rien dire ; « 221 marches contenant voirie, en Ile-de-France, en 2023 »
    veut dire quelque chose, et se verifie.
    """
    fragments: list[sql.SQL] = []
    valeurs: list[Any] = []
    en_clair: list[str] = []

    # `prefixe` qualifie les colonnes quand la requete joint deux tables (« m. »). Il ne vient
    # jamais de l'utilisateur : seuls les appels de ce fichier le fournissent.
    def fragment(gabarit: str) -> sql.SQL:
        return sql.SQL(gabarit.replace("{p}", prefixe))

    if question.texte:
        fragments.append(fragment(FILTRE_TEXTE))
        valeurs.append(question.texte)
        en_clair.append(f"contenant « {question.texte} »")
    if question.annee is not None:
        fragments.append(fragment(FILTRE_ANNEE))
        valeurs.append(question.annee)
        en_clair.append(f"notifies en {question.annee}")
    if question.region is not None:
        fragments.append(fragment(FILTRE_REGION))
        valeurs.append(question.region)
        en_clair.append(f"dont l'acheteur est en {question.region}")
    if question.departement is not None:
        fragments.append(fragment(FILTRE_DEPARTEMENT))
        valeurs.append(question.departement)
        en_clair.append(f"dont l'acheteur est dans le departement {question.departement}")

    if not fragments:
        # Ne doit pas arriver : `lire` refuse une question sans aucun critere. La garde est la
        # pour que ce fichier ne puisse pas, par une evolution future, compter la base entiere
        # et l'annoncer comme une reponse.
        raise ValueError("filtre vide : la question aurait du etre refusee en amont")

    return sql.SQL(" and ").join(fragments), valeurs, ", ".join(en_clair)


def _euros(montant: float | None) -> str:
    """Un montant en euros, lisible. Les espaces sont insecables, pour l'affichage."""
    if montant is None:
        return "montant inconnu"
    if montant >= 1_000_000_000:
        milliards = montant / 1_000_000_000
        return f"{milliards:.1f} milliard{'s' if milliards >= 2 else ''} d'euros".replace(".", ",")
    if montant >= 1_000_000:
        # Le pluriel se decide sur le nombre affiche et non sur le montant : 1,9 million reste
        # au singulier, 2,0 millions passe au pluriel. Vu a l'ecran, ou l'assistant annoncait
        # « 29,9 million d'euros ».
        millions = montant / 1_000_000
        return f"{millions:.1f} million{'s' if millions >= 2 else ''} d'euros".replace(".", ",")
    return f"{montant:,.0f} euros".replace(",", " ")


def repondre(curseur: psycopg.Cursor[Any], question_posee: str, lexiques: Lexiques) -> Reponse:
    """Lire la question, la traduire en SQL, composer la reponse et ses citations."""
    depart = time.perf_counter()
    question = lire(question_posee, lexiques)

    if question.intention == "refus":
        return Reponse(
            question=question,
            phrase=question.refus or "Question non traitee.",
            duree_ms=(time.perf_counter() - depart) * 1000,
        )

    filtres, valeurs, en_clair = construire_filtre(question)
    reponse = Reponse(question=question, phrase="", filtre=en_clair)

    # Un mot perdu qui ne fait pas refuser doit au moins etre annonce : la reponse porte alors
    # sur moins que ce qui a ete demande, et l'utilisateur est le seul a pouvoir juger si cela
    # lui convient.
    if question.perdus:
        reponse.avertissement = (
            "Termes ignores, absents des marches charges : "
            + ", ".join(f"« {mot} »" for mot in question.perdus)
            + ". La reponse porte sur le reste de la question."
        )

    # Le comptage sert deux intentions et sert aussi de garde pour les autres : si le filtre ne
    # rend aucun marche, aucune liste n'a de sens et il faut le dire.
    curseur.execute(sql.SQL(COMPTAGE).format(filtres=filtres), valeurs)
    marches, avec_montant, total = curseur.fetchone()  # type: ignore[misc]

    if marches == 0:
        reponse.phrase = (
            f"Aucun marche ne correspond : {en_clair}. "
            "Soit ces marches n'existent pas dans les donnees chargees, soit les mots employes "
            "ne sont pas ceux des acheteurs."
        )
        reponse.chiffres = {"marches": 0}
        reponse.duree_ms = (time.perf_counter() - depart) * 1000
        return reponse

    curseur.execute(sql.SQL(CITATIONS).format(filtres=filtres), valeurs)
    reponse.citations = [ligne[0] for ligne in curseur.fetchall()]
    reponse.chiffres = {
        "marches": marches,
        "avec_montant": avec_montant,
        "total": float(total),
    }

    if question.intention == "comptage":
        manquants = marches - avec_montant
        reponse.phrase = f"{marches} marches correspondent : {en_clair}."
        if manquants:
            # Ne jamais annoncer une somme en taisant ce qu'elle ne couvre pas. La completude
            # des montants est mesuree dans le chapitre sur la qualite des donnees.
            reponse.phrase += (
                f" {manquants} d'entre eux n'ont pas de montant publie, "
                f"soit {manquants / marches:.0%}."
            )

    elif question.intention == "montant":
        curseur.execute(
            sql.SQL(MEDIANE).format(filtres=filtres),
            valeurs,
        )
        mediane = curseur.fetchone()[0]  # type: ignore[index]
        reponse.chiffres["mediane"] = float(mediane) if mediane is not None else None
        reponse.phrase = (
            f"Les {avec_montant} marches a montant publie totalisent {_euros(float(total))}, "
            f"pour une mediane de {_euros(float(mediane) if mediane else None)} : {en_clair}."
        )
        if marches != avec_montant:
            reponse.phrase += (
                f" {marches - avec_montant} marches sont exclus de ce total, faute de montant."
            )

    elif question.intention in ("titulaires", "acheteurs"):
        requete = TITULAIRES if question.intention == "titulaires" else ACHETEURS
        curseur.execute(
            sql.SQL(requete).format(filtres=filtres),
            [*valeurs, PROFONDEUR],
        )
        colonnes = [description[0] for description in curseur.description or []]
        reponse.lignes = [dict(zip(colonnes, ligne, strict=True)) for ligne in curseur.fetchall()]
        for ligne in reponse.lignes:
            reponse.citations.extend(ligne.get("citations") or [])
        if not reponse.lignes:
            quoi = "titulaire" if question.intention == "titulaires" else "acheteur"
            reponse.phrase = (
                f"{marches} marches correspondent ({en_clair}), mais aucun ne porte de nom de "
                f"{quoi} exploitable."
            )
        else:
            premier = reponse.lignes[0]
            role = "titulaire" if question.intention == "titulaires" else "acheteur"
            reponse.phrase = (
                f"Sur {marches} marches ({en_clair}), le premier {role} est "
                f"{premier['nom']}, avec {premier['marches']} marches pour "
                f"{_euros(float(premier['total']))}."
            )
            reponse.chiffres["premier"] = premier["nom"]
            reponse.chiffres["premier_marches"] = premier["marches"]

    elif question.intention == "signales":
        # La requete joint deux tables : le filtre doit nommer la sienne. Le prefixe est
        # passe a la construction, et non applique apres coup par un remplacement de chaine,
        # qui toucherait aussi les noms de colonnes contenus dans d'autres mots.
        filtres_m, valeurs_m, _ = construire_filtre(question, prefixe="m.")
        curseur.execute(
            sql.SQL(SIGNALES).format(filtres=filtres_m),
            [*valeurs_m, PROFONDEUR],
        )
        colonnes = [description[0] for description in curseur.description or []]
        reponse.lignes = [dict(zip(colonnes, ligne, strict=True)) for ligne in curseur.fetchall()]
        reponse.citations = [ligne["marche_id"] for ligne in reponse.lignes]
        if not reponse.lignes:
            reponse.phrase = (
                f"Aucun des {marches} marches correspondants n'est signale ({en_clair}). "
                "Les regles de signalement sont decrites dans l'ADR 0006."
            )
        else:
            reponse.phrase = (
                f"{len(reponse.lignes)} marches signales parmi ceux qui correspondent "
                f"({en_clair}). Un signalement veut dire « eloigne de ses pairs », pas "
                "« irregulier » : 48 % des signalements de prix sont des faux positifs."
            )

    else:  # extraits
        curseur.execute(
            sql.SQL(EXTRAITS).format(filtres=filtres),
            [*valeurs, PROFONDEUR],
        )
        colonnes = [description[0] for description in curseur.description or []]
        reponse.lignes = [dict(zip(colonnes, ligne, strict=True)) for ligne in curseur.fetchall()]
        reponse.citations = [ligne["marche_id"] for ligne in reponse.lignes]
        reponse.phrase = (
            f"{marches} marches correspondent ({en_clair}). Voici les "
            f"{len(reponse.lignes)} plus gros montants."
        )

    reponse.duree_ms = (time.perf_counter() - depart) * 1000
    return reponse
