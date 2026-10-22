"""La connexion a PostgreSQL : une reserve de connexions, ouverte au demarrage, fermee a l'arret.

=== Pourquoi une reserve et non une connexion par requete ====================

Ouvrir une connexion PostgreSQL coute un aller-retour reseau, une authentification et
l'allocation d'un processus serveur. Mesure du 22 octobre 2026 sur le Mac, en local :

    ouvrir puis fermer une connexion                      environ 11 ms
    emprunter une connexion deja ouverte a la reserve     moins de 0,1 ms

Sur une requete de recherche qui repond en 18 ms, ouvrir une connexion a chaque fois ajouterait
plus de la moitie du temps de reponse pour ne rien calculer.

    Option envisagee        Avantage                     Limite                        Verdict
    une connexion par       aucun etat a gerer, aucune   environ 11 ms par requete,    ecarte
    requete                 fuite possible               et un processus serveur cree
                                                          et detruit a chaque appel
    **une reserve           le cout d'ouverture est paye  il faut la fermer a l'arret,  **retenu**
    (psycopg_pool)**        une fois                      et plafonner sa taille
    une connexion unique    le plus simple               deux visiteurs simultanes se  ecarte
    partagee                                             bloquent l'un l'autre
    un intermediaire        gere aussi plusieurs          un service de plus a          ecarte
    (PgBouncer)             applications et des milliers  exploiter et a superviser,    phase 9
                            de connexions                 pour un seul service

A quelle echelle la reponse changerait : PgBouncer devient utile le jour ou plusieurs services
se partagent la meme base, ou quand le nombre de connexions depasse ce que PostgreSQL accepte
confortablement. Pour un service unique sur un VPS, la reserve interne suffit.

=== Pourquoi les routes sont ecrites en `def` et non en `async def` ===========

Le pilote PostgreSQL utilise ici est synchrone : un appel bloque le fil d'execution jusqu'a la
reponse. Dans une route `async def`, il bloquerait la boucle d'evenements, donc **toutes** les
requetes en cours, y compris celles qui n'ont rien a voir. Ecrite en `def`, la route est
executee par Starlette dans un fil separe, et le blocage reste local a ce fil.

    Option envisagee     Avantage                        Limite                       Verdict
    **pilote synchrone   le code de l'assistant et des   le parallelisme est borne     **retenu**
    et routes `def`**    mesures est reutilise tel quel  par la reserve de fils
    pilote asynchrone    plus de requetes simultanees    il faudrait recrire           ecarte
    (psycopg async)      a memoire egale                 `services/assistant` en
                                                         asynchrone, ou le dupliquer

A quelle echelle la reponse changerait : au-dela de quelques dizaines de visiteurs simultanes,
l'asynchrone reprend l'avantage. `make bench-api` mesure le palier reel ; tant qu'il n'est pas
atteint, reecrire l'assistant serait un cout sans contrepartie.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import Any

import psycopg
from fastapi import HTTPException, Request
from psycopg.rows import dict_row, tuple_row
from psycopg_pool import ConnectionPool

from services.assistant.lecture_question import Lexiques
from services.assistant.reponse_sourcee import charger_lexiques
from services.configuration import chaine_de_connexion

journal = logging.getLogger("api")

# Taille de la reserve. Quatre connexions et non quarante : chaque connexion PostgreSQL est un
# processus serveur, et `work_mem` (64 Mo) peut etre alloue plusieurs fois par requete
# compliquee. Sur un VPS de 2 Go, une reserve large est un moyen de tomber en panne de memoire
# sous charge, pas d'aller plus vite. La valeur est mesuree par `make bench-api`.
CONNEXIONS_MINIMUM = 1
CONNEXIONS_MAXIMUM = 4

# Delai au-dela duquel une requete est abandonnee par la base elle-meme. Sans ce plafond, une
# requete pathologique garde un fil et une connexion pour toujours, et le service devient
# indisponible sans etre tombe. Dix secondes : c'est quarante fois la plus lente des requetes
# mesurees (402 ms), donc large pour un usage normal et court pour un accident.
DELAI_REQUETE_MS = 10_000


@dataclass
class Etat:
    """Ce que le service garde entre deux requetes."""

    reserve: ConnectionPool[psycopg.Connection[dict[str, Any]]] | None = None
    lexiques: Lexiques | None = None
    # Pourquoi la base n'est pas accessible, quand elle ne l'est pas. Affiche par /sante, et
    # jamais renvoye a un visiteur sur une autre route : un message d'erreur de connexion
    # contient l'hote, le port et le nom de l'utilisateur.
    raison_indisponible: str = ""


def _regler(connexion: psycopg.Connection[Any]) -> None:
    """Applique a chaque connexion de la reserve les reglages qui protegent le service.

    `statement_timeout` est pose ici et non dans la requete : pose au niveau de la connexion, il
    s'applique aussi aux requetes qu'on oublierait d'encadrer. En lecture seule, parce qu'aucune
    route de cette API n'ecrit : si une route tentait un `update`, la base refuserait, au lieu
    de modifier les donnees servies au public.
    """
    # `set_config` et non `set` : la commande `set` de PostgreSQL n'accepte pas de parametre
    # `%s`, ce qui obligerait a composer sa valeur dans le texte de la requete. Meme avec une
    # constante du module, c'est le genre de ligne qu'on finit par alimenter depuis la
    # configuration, et l'analyse statique a raison de la refuser. `set_config` est une fonction
    # ordinaire : sa valeur est un parametre, jamais du SQL.
    for reglage, valeur in (
        ("statement_timeout", str(DELAI_REQUETE_MS)),
        # Aucune route de cette API n'ecrit. Si l'une tentait un `update`, la base refuserait,
        # au lieu de modifier les donnees servies au public.
        ("default_transaction_read_only", "on"),
        # Le fuseau est fige : une date affichee doit etre la meme sur le Mac et sur le VPS.
        ("timezone", "Europe/Paris"),
    ):
        # Le troisieme argument, `is_local`, reste faux : le reglage doit survivre a la
        # transaction, sinon il ne s'appliquerait qu'a celle en cours.
        connexion.execute("select set_config(%s, %s, false)", (reglage, valeur))

    # Validation obligatoire, et c'est le banc qui l'a appris le 22 octobre 2026 : psycopg ouvre
    # une transaction au premier `select`, et la reserve refuse une connexion rendue a
    # l'interieur d'une transaction (« connection left in status INTRANS by configure function »).
    # Elle jetait donc chaque connexion configuree, et l'ouverture echouait au bout de dix
    # secondes. Avec `is_local` a faux, les reglages survivent a cette validation.
    connexion.commit()


def ouvrir(commande: str = "make api") -> ConnectionPool[psycopg.Connection[dict[str, Any]]]:
    """Ouvre la reserve de connexions. Leve une exception si la base ne repond pas."""
    reserve: ConnectionPool[psycopg.Connection[dict[str, Any]]] = ConnectionPool(
        conninfo=chaine_de_connexion(commande),
        min_size=CONNEXIONS_MINIMUM,
        max_size=CONNEXIONS_MAXIMUM,
        # Les lignes arrivent en dictionnaires, pour que le nom des colonnes soit porte par la
        # donnee et non par la position. Une colonne ajoutee au milieu d'un `select` ne decale
        # alors rien.
        kwargs={"row_factory": dict_row},
        configure=_regler,
        # Ouverture explicite : la creation silencieuse est depreciee, et surtout une erreur
        # de connexion doit se produire la ou on l'attend, pas plus tard dans une route.
        open=False,
        name="api",
    )
    reserve.open(wait=True, timeout=10.0)
    return reserve


def reserve_de(requete: Request) -> ConnectionPool[psycopg.Connection[dict[str, Any]]]:
    """La reserve de connexions, ou une erreur 503 si la base n'est pas joignable.

    503 et non 500 : l'API fonctionne, c'est sa dependance qui manque. La distinction compte
    pour la supervision, et pour le visiteur, a qui l'on dit d'attendre plutot que de signaler
    un defaut.
    """
    etat: Etat = requete.app.state.etat
    if etat.reserve is None:
        raise HTTPException(status_code=503, detail="Base de donnees indisponible.")
    return etat.reserve


def curseur(requete: Request) -> Iterator[psycopg.Cursor[dict[str, Any]]]:
    """Emprunte une connexion a la reserve pour la duree d'une requete, et la rend ensuite.

    C'est une dependance FastAPI, donc remplacable : les tests injectent un faux curseur a sa
    place et verifient les routes sans PostgreSQL. C'est ce qui permet a la chaine d'integration
    continue de tester l'API sans demarrer une base.
    """
    with reserve_de(requete).connection() as connexion, connexion.cursor() as curseur_sql:
        yield curseur_sql


def curseur_positionnel(requete: Request) -> Iterator[psycopg.Cursor[Any]]:
    """Un curseur qui rend ses lignes en tuples, pour l'assistant.

    Deux formes de ligne dans un seul service, et c'est assume. La reserve rend des
    dictionnaires, parce que les routes de l'API nomment leurs colonnes et qu'une colonne ajoutee
    au milieu d'un `select` ne doit rien decaler. Mais `services/assistant` a ete ecrit contre
    des lignes positionnelles, et c'est sous cette forme que `make bench-assistant` verifie ses
    448 citations et chacun de ses chiffres.

    Le defaut a ete trouve par le banc, le 22 octobre 2026 : avec des dictionnaires, le
    chargement des lexiques echouait sur `ligne[0]`, soit une cle absente, et le service
    demarrait en annoncant simplement « lexiques non charges : 0 ».

        Option envisagee          Avantage                   Limite                    Verdict
        reecrire l'assistant      une seule forme de ligne   ses mesures sont faites    ecarte
        pour les dictionnaires    dans tout le service       contre la forme actuelle,
                                                             donc il faudrait les
                                                             refaire pour un gain nul
        rendre l'assistant        robuste aux deux formes    deux chemins de lecture a  ecarte
        indifferent a la forme                               tester au lieu d'un
        **un curseur par         chacun lit ce qu'il        une dependance de plus a   **retenu**
        besoin**                 attend, et la raison est   nommer
                                 ecrite ici
    """
    with (
        reserve_de(requete).connection() as connexion,
        connexion.cursor(row_factory=tuple_row) as curseur_sql,
    ):
        yield curseur_sql


def lexiques_de(requete: Request) -> Lexiques:
    """Les lexiques de l'assistant, charges une seule fois au demarrage.

    Ils pesent 74 055 lexemes, 24 regions et 107 departements, et leur chargement prend 248 ms.
    Le faire a chaque question multiplierait par quatorze le temps de reponse median de
    l'assistant, qui est de 18 ms.
    """
    etat: Etat = requete.app.state.etat
    if etat.lexiques is None:
        raise HTTPException(
            status_code=503,
            detail="Assistant indisponible : les lexiques n'ont pas pu etre charges.",
        )
    return etat.lexiques


def _curseur_pour_les_mots(
    etat: Etat,
) -> Callable[[], AbstractContextManager[psycopg.Cursor[Any]]]:
    """Fabrique le fournisseur de curseurs que la fonction `frequence` des lexiques utilise.

    Un curseur par mot inconnu, emprunte puis rendu. C'est quelques dixiemes de milliseconde,
    et seulement pour un mot jamais vu : les lexiques gardent ensuite le resultat en memoire.
    """

    @contextmanager
    def fournir() -> Iterator[psycopg.Cursor[Any]]:
        reserve = etat.reserve
        if reserve is None:
            raise RuntimeError("reserve de connexions fermee")
        with (
            reserve.connection() as connexion,
            connexion.cursor(row_factory=tuple_row) as curseur_sql,
        ):
            yield curseur_sql

    return fournir


def preparer(etat: Etat, commande: str = "make api") -> None:
    """Ouvre la reserve et charge les lexiques, sans empecher le service de demarrer en cas d'echec.

    Un service qui refuse de demarrer quand sa base est absente est intenable en demonstration :
    on ne peut plus ni consulter /sante ni comprendre ce qui manque. Il demarre donc, repond 503
    sur les routes qui ont besoin de la base, et dit sur /sante ce qui ne va pas.
    """
    try:
        etat.reserve = ouvrir(commande)
    except Exception as erreur:  # noqa: BLE001
        # Le detail reste dans le journal du serveur : il contient l'hote, le port et
        # l'utilisateur, qui n'ont rien a faire dans une reponse HTTP.
        journal.error("reserve de connexions non ouverte : %s", erreur)
        etat.raison_indisponible = type(erreur).__name__
        return

    try:
        # Curseur positionnel : voir `curseur_positionnel`. Avec des dictionnaires, le
        # chargement echoue sur une cle absente et le service demarre sans assistant.
        with (
            etat.reserve.connection() as connexion,
            connexion.cursor(row_factory=tuple_row) as curseur_sql,
        ):
            # Le second argument donne a la fonction `frequence` des lexiques un curseur frais
            # a chaque mot inconnu. Sans lui, elle garderait celui du demarrage, rendu a la
            # reserve juste apres, et la premiere question echouerait sur « the cursor is
            # closed ». Le detail est dans l'en-tete de `charger_lexiques`.
            etat.lexiques = charger_lexiques(curseur_sql, _curseur_pour_les_mots(etat))
    except Exception as erreur:  # noqa: BLE001
        journal.error("lexiques non charges : %s", erreur)


def fermer(etat: Etat) -> None:
    """Ferme la reserve. Sans cela, les connexions restent ouvertes cote PostgreSQL."""
    if etat.reserve is not None:
        etat.reserve.close()
        etat.reserve = None
