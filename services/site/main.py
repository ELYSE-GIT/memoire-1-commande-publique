"""L'application deployee : l'API et les pages du site, dans un seul processus.

C'est ce module que `uvicorn` sert en production (`make site`), et c'est le seul endroit du
projet ou les deux moities sont assemblees.

=== Pourquoi un seul processus et non deux services =========================

    Option envisagee       Avantage                      Limite                     Verdict
    **un processus qui     une seule reserve de           le site et l'API ne       **retenu**
    sert les pages et      connexions, un seul            peuvent pas etre
    les donnees**          conteneur, aucun appel         redimensionnes
                           reseau entre les deux          separement
    deux services, le      chaque moitie se deploie et    chaque page paie un aller  ecarte
    site appelant l'API    se redimensionne seule         et retour HTTP, et le site
    par HTTP                                              tombe si l'API bouge
    deux services, le      le site est purement           deux conteneurs, deux      ecarte
    site en Node.js        statique                       chaines de construction,
                                                          deux choses a securiser

Ce qui a fait pencher : le VPS. Un processus Python de 37 Mo qui sert les deux est ce qui tient
dans une machine a 2 Go sans se demander quoi arreter. A quelle echelle la reponse changerait :
le jour ou la recherche demanderait plus de puissance que l'affichage, ou l'inverse, separer
permettrait de ne payer que pour ce qui sature. Aucune mesure ne le justifie aujourd'hui.

Les pages appellent les fonctions de route de l'API **dans le processus**, pas par HTTP : voir
l'en-tete de `pages.py`. Elles ne peuvent donc pas afficher un chiffre que l'API ne servirait
pas, et il n'y a pas de serialisation JSON payee pour rien.

=== Pourquoi les erreurs sont traitees ici ==================================

L'API repond en JSON, le site en HTML. Les deux partagent la meme application, donc les memes
gestionnaires d'erreur : poses dans `services/api/main.py`, ils renverraient un objet JSON a un
visiteur qui a tape une mauvaise adresse dans son navigateur. Les gestionnaires sont donc
redefinis ici, et ils regardent le chemin demande pour savoir en quelle langue repondre. Celui
de l'API est reutilise tel quel pour les chemins de l'API, plutot que recopie.
"""

from __future__ import annotations

import psycopg
from fastapi import Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as ErreurHTTP

from services.api.main import PREFIXE_API, application, erreur_de_base
from services.site.pages import CHEMIN_STATIQUE, STATIQUE, page, routeur

# `application` vient de `services.api.main` et ressort d'ici : c'est ce module que `uvicorn`
# sert, parce que c'est ici que l'application est complete. L'export est declare, parce qu'un
# nom simplement importe n'est pas considere comme exporte, et qu'il vaut mieux le dire que
# d'affaiblir la verification de types.
__all__ = ["application"]

# Les pages, a la racine. Montees apres les routes JSON, qui vivent sous `PREFIXE_API` : aucune
# adresse n'est donc revendiquee deux fois, et un test le verifie.
application.include_router(routeur)

# Les fichiers servis tels quels : la feuille de style, htmx, l'icone. `StaticFiles` refuse de
# sortir du dossier indique, y compris par un chemin contenant `..`.
application.mount(CHEMIN_STATIQUE, StaticFiles(directory=str(STATIQUE)), name="statique")


def sur_le_site(requete: Request) -> bool:
    """Vrai quand l'adresse demandee est une page et non une route de l'API.

    Le test porte sur le chemin et non sur l'en-tete `Accept` : un navigateur envoie un
    `Accept` qui accepte a peu pres tout, et s'y fier donnerait du JSON a un visiteur une fois
    sur deux. Le chemin, lui, est sans ambiguite.
    """
    chemin = requete.url.path
    return not (chemin == PREFIXE_API or chemin.startswith(f"{PREFIXE_API}/"))


# Les messages affiches selon le code. Ecrits en francais et sans jargon : la personne qui les
# lit n'a pas demande a savoir ce qu'est un code de statut.
MESSAGES = {
    404: (
        "Page introuvable",
        "Cette adresse ne correspond à aucune page du site.",
    ),
    422: (
        "Demande incomprise",
        "Un des filtres envoyés n'a pas pu être lu.",
    ),
    503: (
        "Service momentanément indisponible",
        "Les données ne sont pas joignables en ce moment. Rien n'est perdu : il suffit de "
        "réessayer dans un instant.",
    ),
    504: (
        "Recherche trop longue",
        "La recherche a dépassé le temps que le service s'accorde, et a été abandonnée. "
        "Ajouter un filtre, une année ou un département la rend beaucoup plus rapide.",
    ),
}


def page_d_erreur(requete: Request, code: int, detail: str = "") -> HTMLResponse:
    """Rend une page d'erreur HTML, avec la navigation du site."""
    titre, message = MESSAGES.get(
        code, ("Une erreur est survenue", "Le service n'a pas pu répondre à cette demande.")
    )
    return page(
        requete,
        "erreur.html",
        {"titre": titre, "message": message, "detail": detail},
        code=code,
    )


@application.exception_handler(ErreurHTTP)
async def erreur_http(requete: Request, erreur: Exception) -> Response:
    """Une page pour le site, un objet JSON pour l'API."""
    assert isinstance(erreur, ErreurHTTP)  # noqa: S101
    if sur_le_site(requete):
        return page_d_erreur(requete, erreur.status_code)
    return await http_exception_handler(requete, erreur)


@application.exception_handler(psycopg.Error)
async def erreur_de_base_ou_page(requete: Request, erreur: Exception) -> Response:
    """Delegue a l'API pour ses routes, rend une page pour le site.

    Le gestionnaire de l'API est appele, et non recopie : c'est lui qui sait distinguer une
    reserve saturee d'une base absente, qui pose `Retry-After` et qui garde le message brut de
    PostgreSQL dans le journal plutot que dans la reponse. Le site reprend le code de statut
    qu'il a choisi et l'habille.
    """
    reponse = await erreur_de_base(requete, erreur)
    if not sur_le_site(requete):
        return reponse
    assert isinstance(reponse, JSONResponse)  # noqa: S101
    return page_d_erreur(requete, reponse.status_code)
