"""L'API publique : les routes, leurs garde-fous, et rien de plus.

Une route fait trois choses et s'arrete : elle valide ce qu'on lui donne, elle appelle une
requete ecrite dans `requetes.py`, elle renvoie un modele declare dans `modeles.py`. Aucun
calcul metier ici : il est dans la couche or du projet dbt, et le refaire a l'affichage
reviendrait a avoir deux verites.

=== Pourquoi FastAPI ==========================================================

    Option envisagee    Avantage                        Limite                       Verdict
    **FastAPI**         validation des entrees et       une dependance de plus que   **retenu**
                        documentation OpenAPI generees  Flask, et un modele
                        depuis les annotations de type  asynchrone a comprendre
                        deja presentes dans le projet
    Flask               plus petit, plus connu          ni validation ni             ecarte
                                                        documentation sans
                                                        extensions, soit le meme
                                                        poids reparti autrement
    Django REST         administration et               un cadre entier a adopter    ecarte
    Framework           authentification fournies       pour une base qui existe
                                                        deja hors de son ORM
    Litestar            tres proche de FastAPI, un      beaucoup moins d'exemples    ecarte
                        peu plus rapide sur le papier   et de reponses publiques

Ce qui a fait pencher : le projet est deja annote et verifie par mypy en mode strict. FastAPI
reutilise ces annotations pour valider les entrees et produire la documentation, donc le travail
de typage sert deux fois. A quelle echelle la reponse changerait : pour servir une seule page
HTML sans API publique, Flask suffirait et pesereait moins.

=== Ce qui n'est pas ici ======================================================

Pas de limitation de debit dans le code. Elle sera posee par Caddy en phase 9, devant le
service : un compteur en memoire dans le processus serait remis a zero a chaque redemarrage,
compterait faux des qu'il y a plus d'un processus, et devrait faire confiance a un en-tete
`X-Forwarded-For` que n'importe qui peut ecrire. Le filtrage par adresse appartient au
reverse-proxy, qui est le seul a voir la vraie adresse.

Pas d'authentification sur ces routes : les donnees servies sont publiques par nature, ce sont
les donnees essentielles de la commande publique. L'espace d'administration, lui, en aura une,
et c'est pour cette raison qu'il est un routeur separe.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout, TooManyRequests

from services.api import requetes
from services.api.base import (
    Etat,
    curseur,
    curseur_positionnel,
    fermer,
    lexiques_de,
    preparer,
)
from services.api.modeles import (
    MarcheDetaille,
    PageDeMarches,
    PageDeSignaux,
    ReponseAssistant,
    Sante,
    StatistiqueAnnuelle,
    Statistiques,
)
from services.assistant.lecture_question import Lexiques
from services.assistant.reponse_sourcee import repondre

journal = logging.getLogger("api")

# Taille de page. Dix par defaut, parce que c'est ce qu'une page affiche et ce qu'un humain
# accepte de lire. Cent au maximum : au-dela, la reponse pese plus que la requete ne coute, et
# c'est une facon simple de faire travailler le serveur pour rien.
TAILLE_PAR_DEFAUT = 10
TAILLE_MAXIMUM = 100

# Profondeur de pagination. Deux raisons, dans cet ordre.
#
# La premiere est mesuree : la recherche par texte ne classe que `PLAFOND_CANDIDATS` lignes
# (5 000), et la page la plus profonde atteignable doit rester a l'interieur de ce plafond.
# Au-dela, la page serait vide alors que des milliers de marches repondent, pour une raison
# qu'aucun visiteur ne pourrait deviner. Quarante pages de cent lignes font 4 000, soit sous le
# plafond avec de la marge. Un test verifie que les deux valeurs restent coherentes.
#
# La seconde est generale : `offset` oblige PostgreSQL a produire puis jeter les lignes sautees,
# donc la page 500 coute 500 fois la premiere. Un visiteur qui cherche vraiment affine sa
# requete ; un robot, lui, pagine.
PAGE_MAXIMUM = 40

# Longueur maximale d'une question. Les objets de marche font 86 caracteres de mediane, et
# `websearch_to_tsquery` sur un texte de plusieurs kilo-octets produit une requete enorme pour
# un resultat vide.
TEXTE_MAXIMUM = 200

# Adresse de base des routes JSON. Les pages du site sont servies par le meme processus, a
# la racine, et il faut donc que les deux jeux d'adresses ne se marchent pas dessus : une
# page HTML et une reponse JSON ne peuvent pas repondre a la meme adresse. Le raisonnement
# complet, avec les trois options envisagees, est dans `docs/adr/0012-site-public.md`.
PREFIXE_API = "/api"

# Le routeur porte les routes ; l'application les monte sous le prefixe. Ecrire
# `@application.get("/marches")` aurait fige l'adresse dans le decorateur, et un prefixe
# n'aurait plus ete possible sans reecrire les sept routes.
routeur = APIRouter()


@asynccontextmanager
async def cycle_de_vie(application: FastAPI) -> AsyncIterator[None]:
    """Ouvre la reserve de connexions et charge les lexiques au demarrage, ferme tout a l'arret.

    Tout ce qui coute cher et ne change pas est fait ici : une fois, et pas a chaque requete.
    """
    etat = Etat()
    application.state.etat = etat
    depart = time.perf_counter()
    preparer(etat)
    journal.info("demarrage en %.0f ms", (time.perf_counter() - depart) * 1000)
    try:
        yield
    finally:
        fermer(etat)


application = FastAPI(
    title="Commande publique",
    version="0.1.0",
    summary="Les marches publics francais, cherchables et verifiables.",
    description=(
        "Chaque reponse porte de quoi la verifier : le filtre applique en francais, et les "
        "numeros de marche cites. Les donnees viennent des donnees essentielles de la commande "
        "publique (DECP) et du BOAMP. Aucune valeur n'est nettoyee ici : les defauts se "
        "corrigent dans la couche de transformation, pas a l'affichage."
    ),
    lifespan=cycle_de_vie,
    # Documentation interactive laissee ouverte : l'API sert des donnees publiques, et la page
    # /docs est le moyen le plus court de montrer en soutenance ce que le service expose.
    docs_url="/docs",
    redoc_url=None,
)


@application.middleware("http")
async def en_tetes_de_securite(requete: Request, suite: Callable[[Request], Any]) -> Response:
    """Ajoute les en-tetes que le navigateur attend pour ne pas se faire abuser.

    Ils sont poses ici et non dans Caddy, pour que le service soit sain meme teste en direct,
    sans reverse-proxy devant. Caddy les reposera en phase 9 : un en-tete pose deux fois ne
    coute rien, un en-tete absent coute une faille.
    """
    reponse: Response = await suite(requete)
    # Empeche le navigateur de deviner un type de contenu, donc d'executer en JavaScript une
    # reponse JSON mal etiquetee.
    reponse.headers["X-Content-Type-Options"] = "nosniff"
    # Interdit l'affichage du site dans un cadre sur un autre domaine (clickjacking).
    reponse.headers["X-Frame-Options"] = "DENY"
    reponse.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # La politique de contenu est posee par defaut seulement : une reponse JSON ne charge rien,
    # donc tout est interdit. Les pages du site, elles, chargent leur feuille de style et htmx,
    # et declarent donc leur propre politique, plus large mais toujours limitee a elles-memes
    # (voir `services/site/pages.py`). `setdefault` et non une affectation : sans cela, ce
    # middleware ecraserait la politique de la page apres que la route l'a posee, et le
    # navigateur bloquerait la feuille de style du site. Teste.
    reponse.headers.setdefault(
        "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
    )
    return reponse


@application.exception_handler(psycopg.Error)
async def erreur_de_base(requete: Request, erreur: Exception) -> JSONResponse:
    """Transforme une erreur PostgreSQL en 503, sans rien reveler de la base.

    Un message brut de psycopg contient le texte de la requete, parfois le nom de l'hote et de
    l'utilisateur. Il part dans le journal du serveur, jamais dans la reponse.
    """
    journal.error("erreur de base sur %s : %s", requete.url.path, erreur)
    if isinstance(erreur, PoolTimeout | TooManyRequests):
        # La base va bien, c'est le service qui est sature : toutes ses connexions servent
        # quelqu'un. Le dire plutot que de laisser patienter indefiniment, et le dire
        # differemment d'une base absente, parce que la consigne n'est pas la meme pour celui
        # qui exploite le service.
        return JSONResponse(
            status_code=503,
            content={"detail": "Service sature, trop de requetes simultanees. Reessayer."},
            headers={"Retry-After": "5"},
        )
    if isinstance(erreur, psycopg.errors.QueryCanceled):
        # La requete a depasse `statement_timeout`. 504 et non 503 : le service repond, c'est
        # la requete qui etait trop longue, et l'appelant peut la preciser.
        return JSONResponse(
            status_code=504,
            content={"detail": "Requete trop longue, abandonnee. Preciser les filtres."},
        )
    return JSONResponse(status_code=503, content={"detail": "Base de donnees indisponible."})


# --- Les dependances, nommees pour que les routes restent lisibles -----------

Curseur = Annotated[psycopg.Cursor[dict[str, Any]], Depends(curseur)]
# L'assistant lit ses lignes par position : voir `curseur_positionnel`.
CurseurPositionnel = Annotated[psycopg.Cursor[Any], Depends(curseur_positionnel)]
LexiquesCharges = Annotated[Lexiques, Depends(lexiques_de)]


# --- L'etat du service -------------------------------------------------------


@routeur.get("/sante", response_model=Sante, tags=["service"])
def sante(requete: Request) -> Sante:
    """Dit si le service repond et si sa base est joignable.

    C'est cette route que lit le healthcheck du conteneur. Elle ne touche pas aux donnees : une
    base qui repond et une base remplie sont deux questions differentes, et confondre les deux
    ferait redemarrer un conteneur sain parce qu'une table est vide.
    """
    etat: Etat = requete.app.state.etat
    if etat.reserve is None:
        return Sante(etat="degrade", base_accessible=False, lexiques_charges=False)
    with etat.reserve.connection() as connexion:
        connexion.execute(requetes.VIE)
        # Le nombre de marches est lu dans la table d'une ligne, donc gratuitement. Il ne
        # decide pas de l'etat : une base joignable mais vide est un probleme de donnees, pas
        # de service, et faire redemarrer le conteneur n'y changerait rien.
        charges = connexion.execute(requetes.MARCHES_CHARGES).fetchone()
    return Sante(
        etat="pret" if etat.lexiques is not None else "degrade",
        base_accessible=True,
        marches_charges=int(charges["marches"]) if charges else None,
        lexiques_charges=etat.lexiques is not None,
    )


# --- Les marches -------------------------------------------------------------


@routeur.get("/marches", response_model=PageDeMarches, tags=["marches"])
def chercher_des_marches(
    curseur_sql: Curseur,
    q: Annotated[
        str | None,
        Query(
            max_length=TEXTE_MAXIMUM,
            description="Texte libre, tel qu'on le taperait dans une barre de recherche. "
            "Cherche dans l'objet du marche (poids fort), le nom de l'acheteur et celui du "
            "titulaire. Absent, la liste rend les marches les plus recents.",
            examples=["travaux de voirie"],
        ),
    ] = None,
    annee: Annotated[int | None, Query(ge=2014, le=2030)] = None,
    departement: Annotated[
        str | None,
        Query(min_length=2, max_length=3, pattern=r"^[0-9AB]{2,3}$", examples=["35"]),
    ] = None,
    famille: Annotated[
        str | None,
        Query(min_length=2, max_length=2, pattern=r"^[0-9]{2}$", examples=["45"]),
    ] = None,
    montant_minimum: Annotated[float | None, Query(ge=0)] = None,
    montant_maximum: Annotated[float | None, Query(ge=0)] = None,
    offre_unique: Annotated[
        bool, Query(description="Ne garder que les marches n'ayant recu qu'une seule offre")
    ] = False,
    page: Annotated[int, Query(ge=1, le=PAGE_MAXIMUM)] = 1,
    taille: Annotated[int, Query(ge=1, le=TAILLE_MAXIMUM)] = TAILLE_PAR_DEFAUT,
) -> PageDeMarches:
    """Cherche des marches, par texte et par filtres.

    Le classement par pertinence n'existe que s'il y a du texte. Sans texte, la liste est
    ordonnee par date de notification decroissante : c'est la seule reponse qui ait un sens a
    « montre-moi les marches de ce departement ».
    """
    encadrement_absurde = (
        montant_minimum is not None
        and montant_maximum is not None
        and montant_minimum > montant_maximum
    )
    if encadrement_absurde:
        raise HTTPException(
            status_code=422, detail="montant_minimum est superieur a montant_maximum."
        )

    corps, valeurs = requetes.recherche(
        q,
        {
            "annee": annee,
            "departement": departement,
            "famille": famille,
            "montant_minimum": montant_minimum,
            "montant_maximum": montant_maximum,
            "offre_unique": offre_unique,
        },
    )
    # Une ligne de plus que demande : sa seule presence repond a « y a-t-il une page suivante »,
    # sans payer un comptage. Elle n'est pas renvoyee.
    curseur_sql.execute(corps, [*valeurs, taille + 1, (page - 1) * taille])
    lignes = curseur_sql.fetchall()
    # Le nombre de candidats classes est le meme sur toutes les lignes : c'est une fonction de
    # fenetre sur l'ensemble des candidats.
    examines = lignes[0]["candidats_examines"] if lignes else None
    return PageDeMarches(
        resultats=lignes[:taille],  # type: ignore[arg-type]
        page=page,
        taille=taille,
        page_suivante=len(lignes) > taille,
        # Le plafond atteint signifie qu'il y avait au moins autant de reponses, donc que le
        # classement ne porte pas sur toutes. On ne sait pas combien il y en avait : le dire
        # demanderait le comptage que cette API refuse justement de payer.
        classement_approche=examines is not None and examines >= requetes.PLAFOND_CANDIDATS,
        candidats_examines=examines,
    )


@routeur.get("/marches/{marche_id}", response_model=MarcheDetaille, tags=["marches"])
def lire_un_marche(
    curseur_sql: Curseur,
    marche_id: Annotated[str, Path(min_length=1, max_length=64)],
) -> MarcheDetaille:
    """Toutes les lignes d'un marche, et ce qui a ete remarque dessus.

    Plusieurs lignes et non une seule : un marche attribue a un groupement d'entreprises compte
    une ligne par titulaire. C'est la raison pour laquelle cette route renvoie une liste meme
    pour un numero de marche unique, et ce fait est mesure dans le schema de la table.
    """
    curseur_sql.execute(requetes.MARCHE, (marche_id,))
    lignes = curseur_sql.fetchall()
    if not lignes:
        raise HTTPException(status_code=404, detail="Marche inconnu.")
    curseur_sql.execute(requetes.SIGNAUX_DU_MARCHE, (marche_id,))
    signaux = curseur_sql.fetchall()
    return MarcheDetaille(lignes=lignes, signaux=signaux)  # type: ignore[arg-type]


# --- Les signaux -------------------------------------------------------------


@routeur.get("/signaux", response_model=PageDeSignaux, tags=["signaux"])
def lister_les_signaux(
    curseur_sql: Curseur,
    minimum: Annotated[
        int,
        Query(
            ge=1,
            le=5,
            description="Nombre minimal de signaux portes par la ligne. Au moins un : l'index "
            "qui sert cette route ne couvre que les lignes signalees.",
        ),
    ] = 1,
    page: Annotated[int, Query(ge=1, le=PAGE_MAXIMUM)] = 1,
    taille: Annotated[int, Query(ge=1, le=TAILLE_MAXIMUM)] = TAILLE_PAR_DEFAUT,
) -> PageDeSignaux:
    """Les marches a examiner, les plus signales d'abord.

    Un signal n'est pas une accusation. Il dit qu'un marche s'ecarte de ses pairs sur un point
    mesurable, et il porte ses motifs en clair pour que le lecteur juge. La concordance de ces
    regles avec les anomalies publiees par le producteur est de 69,3 pour cent hors echantillon,
    intervalle de 67,8 a 70,8 : utile pour trier, insuffisant pour conclure.
    """
    # Une ligne de plus que demande, comme sur /marches : sa seule presence dit qu'il existe
    # une page suivante, et elle n'est pas renvoyee.
    curseur_sql.execute(requetes.SIGNAUX, (minimum, taille + 1, (page - 1) * taille))
    lignes = curseur_sql.fetchall()
    return PageDeSignaux(
        resultats=lignes[:taille],  # type: ignore[arg-type]
        page=page,
        taille=taille,
        page_suivante=len(lignes) > taille,
    )


# --- Les comptages -----------------------------------------------------------


@routeur.get("/statistiques", response_model=Statistiques, tags=["statistiques"])
def lire_les_statistiques(curseur_sql: Curseur) -> Statistiques:
    """Les comptages de la page d'accueil, lus dans une table d'une ligne.

    Ils ne sont pas calcules ici. Les calculer a la demande prenait 10,7 s sur deux millions de
    lignes, soit au-dela du delai que l'API s'impose : la page d'accueil renvoyait une erreur.
    Ils sont donc calcules au chargement, par `base/schema/009-remplir-statistiques.sql`, et la
    reponse porte la date de ce calcul pour que personne n'ait a deviner si elle est fraiche.
    """
    curseur_sql.execute(requetes.STATISTIQUES)
    ligne = curseur_sql.fetchone()
    if ligne is None:
        # La table est vide : les donnees ont ete chargees sans que `make indexer` ait suivi.
        # 503 et non un zero : afficher « zero marche » serait une affirmation fausse, alors que
        # deux millions de lignes sont peut-etre dans la table d'a cote.
        raise HTTPException(
            status_code=503,
            detail="Comptages non calcules. Lancer `make indexer` apres le chargement.",
        )
    return Statistiques(**ligne)


@routeur.get(
    "/statistiques/annees", response_model=list[StatistiqueAnnuelle], tags=["statistiques"]
)
def lire_par_annee(curseur_sql: Curseur) -> list[StatistiqueAnnuelle]:
    """Le nombre de marches, le montant total et la part de PME par annee.

    La part de PME est rapportee aux seules lignes dont le titulaire a ete resolu. Au 21 octobre
    2026, 6,8 pour cent des attributions n'ont pas de categorie d'entreprise : les compter comme
    des non-PME serait une erreur de 6,8 points, toujours dans le meme sens.
    """
    curseur_sql.execute(requetes.PAR_ANNEE)
    # Les lignes sont converties en modeles ici, et non laissees en dictionnaires.
    #
    # Elles l'etaient, avec un `# type: ignore[return-value]` pour faire taire le verificateur
    # de types : la fonction annoncait `list[StatistiqueAnnuelle]` et rendait des
    # dictionnaires. FastAPI les convertissait au moment de serialiser, donc l'API etait juste
    # et le mensonge invisible. Il a cesse de l'etre le 22 octobre 2026, quand une page du site
    # a appele cette fonction directement : `annee.annee` sur un dictionnaire, et la page
    # d'accueil repondait 500. Un `type: ignore` ne masque pas un detail de typage, il masque
    # une affirmation fausse, et elle attend le second appelant.
    return [StatistiqueAnnuelle(**ligne) for ligne in curseur_sql.fetchall()]


# --- L'assistant -------------------------------------------------------------


@routeur.get("/assistant", response_model=ReponseAssistant, tags=["assistant"])
def interroger_l_assistant(
    curseur_sql: CurseurPositionnel,
    lexiques: LexiquesCharges,
    question: Annotated[
        str,
        Query(
            min_length=3,
            max_length=TEXTE_MAXIMUM,
            description="Une question en francais.",
            examples=["combien de marches de voirie en Bretagne en 2024"],
        ),
    ],
) -> ReponseAssistant:
    """Repond a une question en francais, en citant ses sources.

    Aucun modele de langue n'intervient : la question est lue par des motifs et des lexiques,
    traduite en SQL, et la reponse est composee a partir des lignes rendues. La consequence est
    qu'elle refuse ce qu'elle ne sait pas lire, au lieu d'inventer une reponse plausible.

    Une methode `GET` et non `POST` : la requete ne modifie rien, elle est donc partageable par
    son adresse et peut etre mise en cache. C'est aussi ce qui permet de citer une reponse dans
    le memoire par un simple lien.
    """
    reponse = repondre(curseur_sql, question, lexiques)
    return ReponseAssistant(
        question=question,
        phrase=reponse.phrase,
        intention=reponse.question.intention,
        filtre=reponse.filtre,
        chiffres=reponse.chiffres,
        lignes=reponse.lignes,
        citations=reponse.citations,
        avertissement=reponse.avertissement,
        duree_ms=reponse.duree_ms,
    )


# --- Montage -----------------------------------------------------------------
#
# A la fin du fichier et non au debut : `include_router` copie les routes declarees a cet
# instant. Monte avant les decorateurs, il ne monterait rien du tout, sans erreur.
application.include_router(routeur, prefix=PREFIXE_API)
