"""Les pages du site : des gabarits HTML remplis par les memes fonctions que l'API sert en JSON.

Le site n'a pas de code metier, et il n'a pas non plus de requetes SQL. Chaque page appelle la
fonction de route de l'API, celle-la meme qui repond en JSON, et se contente de la mettre en
page. Une page ne peut donc pas afficher un chiffre que l'API ne servirait pas, ni oublier un
avertissement que l'API porte.

=== Pourquoi Jinja2 et htmx, et pas une application JavaScript =================

    Option envisagee     Avantage                        Limite                       Verdict
    **Jinja2 rendu par   un seul service a deployer,     le rechargement partiel      **retenu**
    FastAPI + htmx**     aucune compilation, aucun       demande un gabarit de plus
                         Node.js sur le VPS, le HTML     par fragment
                         arrive deja rempli
    React ou Vue         l'etat du formulaire est tenu   Node.js, une compilation, un  ecarte
    (application         par le navigateur               second artefact a deployer,
    separee)                                             et une API publique a
                                                          versionner pour soi-meme
    gabarits seuls,      le plus simple possible         chaque filtre recharge la     ecarte
    sans htmx                                            page entiere, soit 18 Ko au
                                                          lieu de 4 Ko mesures
    htmx depuis un CDN   rien a versionner               la demonstration depend du    ecarte
                                                         reseau de la salle, et la
                                                         politique de securite doit
                                                         ouvrir un domaine tiers

Ce qui a fait pencher : la contrainte de deploiement. Le VPS heberge un service, pas une chaine
de compilation ; `uvicorn` sert les pages et les donnees depuis le meme processus. htmx est
versionne dans `statique/`, donc le site fonctionne sans reseau, ce qui est le plan B de la
soutenance.

A quelle echelle la reponse changerait : le jour ou une page garderait un etat complexe cote
navigateur (un formulaire a plusieurs etapes, une carte interactive), un cadre JavaScript
reprendrait l'avantage. Afficher une liste et des filtres n'en demande pas.

=== Pourquoi chaque page fonctionne aussi sans JavaScript =====================

Les formulaires sont de vrais formulaires : `method="get"` et une `action` qui mene a une page
complete. htmx ne fait que remplacer le rechargement complet par le remplacement d'un fragment.
Si htmx ne se charge pas (reseau coupe, extension de navigateur, lecteur d'ecran ancien), le
site continue de fonctionner, plus lentement. L'inverse (une page vide sans JavaScript) est le
mode de panne le plus courant des sites modernes, et c'est celui qu'on verrait en soutenance.

Une consequence a tenir : une adresse doit suffire a reproduire ce qui est affiche. Chaque
recherche vit donc dans sa propre adresse (`/recherche?q=voirie&annee=2024`), partageable et
citable dans le memoire.

=== Pourquoi la meme route rend une page ou un fragment ======================

htmx envoie l'en-tete `HX-Request` sur ses appels. La route lit cet en-tete et rend soit la page
entiere, soit le seul fragment qui change. Deux adresses pour la meme information auraient
double la surface a tester et rendu les adresses non partageables.

    Option envisagee       Avantage                     Limite                      Verdict
    **une route, deux      une seule adresse, donc      il faut penser a `Vary`     **retenu**
    rendus selon           partageable, et seul le
    `HX-Request`**         fragment transite
    une route `/fragments` separation visible dans       l'adresse poussee dans      ecarte
    par fragment           l'arborescence                l'historique serait celle
                                                          du fragment, donc une page
                                                          blanche si on la partage
    renvoyer la page       aucune logique                tout le HTML transite pour  ecarte
    entiere et laisser     conditionnelle                remplacer un dixieme de la
    htmx y decouper                                      page

L'en-tete `Vary: HX-Request` est pose en consequence : sans lui, un cache (celui du navigateur,
celui de Caddy en phase 9) pourrait rendre un fragment a quelqu'un qui demande la page.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path as CheminFichier
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from jinja2 import StrictUndefined

from services.api.base import Etat, curseur, curseur_positionnel
from services.api.main import (
    PAGE_MAXIMUM,
    PREFIXE_API,
    TEXTE_MAXIMUM,
    chercher_des_marches,
    interroger_l_assistant,
    lire_les_statistiques,
    lire_par_annee,
    lire_un_marche,
    lister_les_signaux,
)
from services.api.modeles import PageDeMarches
from services.assistant.lecture_question import Lexiques

DOSSIER = CheminFichier(__file__).parent
GABARITS = DOSSIER / "gabarits"
STATIQUE = DOSSIER / "statique"

# Adresse publique des fichiers statiques. Montee par `services/site/main.py`, et citee ici
# parce que c'est la politique de securite qui doit la connaitre.
CHEMIN_STATIQUE = "/statique"

# La documentation interactive de l'API, posee a la racine par
# `services/api/main.py`. Citee en pied de chaque page : un site de donnees
# publiques doit dire par quelle adresse on obtient les memes donnees sans lui.
CHEMIN_DOCS = "/docs"

# Combien de resultats par page sur le site. Dix comme l'API : c'est ce qu'un ecran affiche sans
# defilement, et le plafond de candidats classes a ete dimensionne pour cette taille.
PAR_PAGE = 10

# La politique de contenu des pages. Elle est stricte et nommee ici, en un seul endroit.
#
# `default-src 'none'` d'abord : tout est interdit, puis on ouvre ce qui est necessaire, et
# uniquement vers soi-meme (`'self'`). Aucun domaine tiers n'apparait, parce qu'aucun fichier
# n'est charge depuis un tiers : htmx est versionne dans `statique/`.
#
# Ce qui n'est PAS autorise, et ce que cela a coute :
#
#   `'unsafe-inline'` sur les styles. Une barre de proportion ecrite
#   `<div style="width: 62%">` aurait demande d'autoriser le style en ligne, donc d'ouvrir la
#   porte a tout attribut `style` injecte dans la page. La figure de la page d'accueil est donc
#   un SVG, dont la geometrie passe par des attributs (`x`, `y`, `height`) et non par du CSS.
#   C'est quelques lignes de calcul dans le gabarit, contre une politique de securite qui tient.
#
#   `'unsafe-eval'` et le JavaScript en ligne. htmx n'en a pas besoin : il lit des attributs
#   `hx-*`. Le site ne contient aucune balise `<script>` avec du code dedans.
POLITIQUE_DE_CONTENU = "; ".join(
    (
        "default-src 'none'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        # Les appels htmx vont vers le site lui-meme, jamais ailleurs.
        "connect-src 'self'",
        "form-action 'self'",
        "base-uri 'none'",
        "frame-ancestors 'none'",
    )
)

routeur = APIRouter(include_in_schema=False)

# --- Les dependances, les memes que celles de l'API --------------------------

Curseur = Annotated[psycopg.Cursor[dict[str, Any]], Depends(curseur)]
CurseurPositionnel = Annotated[psycopg.Cursor[Any], Depends(curseur_positionnel)]


def lexiques_ou_rien(requete: Request) -> Lexiques | None:
    """Les lexiques de l'assistant, ou `None` s'ils n'ont pas pu etre charges.

    L'API a une dependance pour cela, `lexiques_de`, mais elle leve une erreur 503 avant
    meme que la route ne commence, donc avant qu'une page HTML ait pu etre rendue : le
    visiteur recevrait un objet JSON a la place d'une page. Ici, l'absence est une valeur, et
    la page affiche en francais que l'assistant est indisponible, sans cesser d'etre une page.
    """
    etat: Etat = requete.app.state.etat
    return etat.lexiques


LexiquesEventuels = Annotated["Lexiques | None", Depends(lexiques_ou_rien)]


# --- Mise en forme ----------------------------------------------------------
#
# Ces fonctions sont declarees comme filtres Jinja2 plus bas. Elles sont ici et non dans le
# gabarit parce qu'un nombre mal formate est un defaut qui se teste, et qu'un test ne peut pas
# appeler une expression ecrite au milieu du HTML.

# Espace fine insecable : le separateur de milliers du francais. Un espace ordinaire laisserait
# « 1 999 474 » se couper en fin de ligne, et un point en ferait un nombre anglais.
FINE = " "


def nombre(valeur: int | float | Decimal | None) -> str:
    """Un entier, groupe par milliers. `None` devient un tiret, jamais zero."""
    if valeur is None:
        return "–"
    return f"{int(valeur):,}".replace(",", FINE)


def euros(valeur: int | float | Decimal | None) -> str:
    """Un montant, arrondi a l'euro.

    Les centimes sont conserves dans la base (`numeric(18, 2)`) parce que c'est de l'argent,
    mais les afficher sur un marche de 12 millions d'euros donnerait une precision qui n'existe
    pas dans la source.
    """
    if valeur is None:
        return "montant non publié"
    return f"{nombre(round(Decimal(valeur)))}{FINE}€"


def jour(valeur: dt.date | None) -> str:
    """Une date au format francais. Les dates de l'API sont en ISO, pour etre triables."""
    if valeur is None:
        return "–"
    return valeur.strftime("%d/%m/%Y")


def pourcentage(valeur: float | None) -> str:
    """Un pourcentage a une decimale, avec la virgule francaise."""
    if valeur is None:
        return "–"
    return f"{valeur:.1f}".replace(".", ",") + f"{FINE}%"


FILTRES_DE_FORMAT = {
    "nombre": nombre,
    "euros": euros,
    "jour": jour,
    "pourcentage": pourcentage,
}

# `StrictUndefined` : une variable absente du contexte leve une erreur au lieu de s'afficher
# comme une chaine vide. C'est le defaut de Jinja2 qui est dangereux ici : renommer une cle du
# contexte ferait disparaitre un chiffre de la page sans qu'aucun test ni aucun journal ne le
# signale, et c'est precisement le genre de panne qu'un relecteur de memoire remarque avant son
# auteur. Mieux vaut une page en erreur qu'une page fausse.
gabarits = Jinja2Templates(directory=str(GABARITS))
gabarits.env.undefined = StrictUndefined
gabarits.env.filters.update(FILTRES_DE_FORMAT)
# Rendu disponible a tous les gabarits : l'adresse de l'API, pour que chaque page puisse offrir
# le lien vers la reponse JSON qui l'a produite. C'est la forme la plus courte de « verifiable ».
gabarits.env.globals["prefixe_api"] = PREFIXE_API
gabarits.env.globals["chemin_statique"] = CHEMIN_STATIQUE
gabarits.env.globals["chemin_docs"] = CHEMIN_DOCS


def page(
    requete: Request,
    gabarit: str,
    contexte: dict[str, Any],
    fragment: str | None = None,
    code: int = 200,
) -> HTMLResponse:
    """Rend un gabarit, ou son seul fragment quand l'appel vient de htmx.

    Le choix du rendu se lit dans l'en-tete `HX-Request`, pose par htmx et par personne
    d'autre. Un visiteur qui le poserait a la main recevrait un fragment de HTML : c'est sans
    consequence, le fragment ne contient rien de plus que la page.
    """
    depuis_htmx = requete.headers.get("HX-Request") == "true"
    choisi = fragment if (depuis_htmx and fragment) else gabarit
    reponse = gabarits.TemplateResponse(requete, choisi, contexte, status_code=code)
    reponse.headers["Content-Security-Policy"] = POLITIQUE_DE_CONTENU
    # Sans cela, un cache qui a garde le fragment le rendrait a la requete suivante, qui
    # demande la page entiere : le visiteur verrait une liste de resultats sans entete ni
    # feuille de style.
    reponse.headers["Vary"] = "HX-Request"
    return reponse


def entier_ou_rien(texte: str | None, minimum: int, maximum: int) -> int | None:
    """Lit un entier venu d'un champ de formulaire, ou rend `None` si le champ est vide.

    L'API est stricte : `annee=` sans valeur vaut 422, et c'est correct pour une API, dont
    l'appelant est un programme. Le site, lui, recoit les champs d'un formulaire HTML, qui
    envoie **tous** ses champs, y compris ceux que le visiteur a laisses vides. Refuser la
    recherche parce qu'une case est vide serait un defaut, pas une validation.

    Hors bornes, la valeur est ignoree plutot que refusee : une annee 1800 tapee a la main ne
    merite pas une page d'erreur, elle merite d'etre traitee comme une annee non precisee.
    """
    if texte is None or not texte.strip():
        return None
    try:
        valeur = int(texte)
    except ValueError:
        return None
    return valeur if minimum <= valeur <= maximum else None


def decimal_ou_rien(texte: str | None) -> float | None:
    """Meme chose pour un montant. La virgule francaise est acceptee, et les espaces retires."""
    if texte is None or not texte.strip():
        return None
    try:
        valeur = float(texte.replace(FINE, "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None
    return valeur if valeur >= 0 else None


def texte_ou_rien(texte: str | None) -> str | None:
    """Un champ de texte vide vaut « pas de filtre », et non « cherche la chaine vide »."""
    if texte is None or not texte.strip():
        return None
    return texte.strip()


# --- Les pages ---------------------------------------------------------------


def part(partie: int, total: int) -> float | None:
    """Un pourcentage, ou `None` quand le denominateur est nul.

    `None` et non zero : sur une base vide, « 0 % de marches signales » est une affirmation
    fausse, alors que « on ne sait pas » est exact. Le gabarit affiche un tiret.
    """
    return None if not total else 100 * partie / total


def figure_par_annee(annees: list[Any]) -> dict[str, Any]:
    """Prepare la geometrie du SVG de la page d'accueil, en coordonnees entieres.

    Pourquoi un SVG calcule ici plutot qu'une bibliotheque de graphiques : une bibliotheque
    JavaScript (Chart.js, Plotly) pese entre 90 Ko et 3 Mo, demande `'unsafe-eval'` ou du script
    en ligne pour la plupart, et affiche une page vide si elle ne se charge pas. Le SVG arrive
    rempli dans la reponse, se lit sans JavaScript, et s'imprime.

    Les figures du memoire, elles, restent produites par `mesures/figures.py` : celle-ci montre
    l'etat de la base a l'instant de la visite, ce qui n'est pas la meme chose.
    """
    if not annees:
        return {"barres": [], "largeur": 0, "hauteur": 0}
    hauteur, largeur_barre, espace, marge_basse = 180, 34, 10, 28
    maximum = max(annee.attributions for annee in annees) or 1
    barres = []
    for rang, annee in enumerate(annees):
        # Hauteur proportionnelle au nombre d'attributions, arrondie au pixel. Au moins un
        # pixel : une annee a 300 attributions doit rester visible a cote d'une annee a 300 000,
        # sinon la figure laisse croire qu'il n'y a rien.
        haut = max(1, round(hauteur * annee.attributions / maximum))
        barres.append(
            {
                "annee": annee.annee,
                "x": rang * (largeur_barre + espace),
                "y": hauteur - haut,
                "hauteur": haut,
                "largeur": largeur_barre,
                "attributions": annee.attributions,
                "part_pme": annee.part_pme_pourcent,
                # La part de PME, dessinee en plein dans la barre. Rapportee aux seules
                # attributions dont la categorie du titulaire est connue : le gabarit l'ecrit.
                "hauteur_pme": (
                    0
                    if annee.part_pme_pourcent is None
                    else max(1, round(haut * annee.part_pme_pourcent / 100))
                ),
            }
        )
    return {
        "barres": barres,
        "largeur": len(annees) * (largeur_barre + espace) - espace,
        "hauteur": hauteur,
        "hauteur_totale": hauteur + marge_basse,
        "base": hauteur,
    }


@routeur.get("/", response_class=HTMLResponse)
def accueil(requete: Request, curseur_sql: Curseur) -> HTMLResponse:
    """La page d'accueil : ce que contient la base, et par quoi commencer.

    Elle affiche des comptages lus dans une table d'une ligne, et la date de leur calcul. Un
    chiffre sans sa date ne dit pas s'il est perime, et c'est la premiere question qu'un jury
    posera devant une page d'accueil.
    """
    comptages = lire_les_statistiques(curseur_sql)
    annees = [annee for annee in lire_par_annee(curseur_sql) if annee.annee is not None]
    return page(
        requete,
        "accueil.html",
        {
            "titre": "Les marchés publics français, cherchables et vérifiables",
            "comptages": comptages,
            "annees": annees,
            "part_signalee": part(comptages.marches_signales, comptages.marches),
            # De combien l'addition naive depasse le total dedoublonne. Calcule et non ecrit en
            # dur : c'est un chiffre qui depend des donnees chargees.
            "surcompte_pourcent": (
                None
                if not comptages.montant_total_marches
                else part(
                    int(comptages.montant_total or 0) - int(comptages.montant_total_marches),
                    int(comptages.montant_total_marches),
                )
            ),
            # La part d'attributions sans categorie d'entreprise est calculee et non ecrite en
            # dur dans le gabarit : c'est le denominateur de la part de PME affichee juste a
            # cote, et un chiffre ecrit a la main cesse d'etre vrai au chargement suivant.
            "part_sans_categorie": part(
                sum(a.attributions for a in annees) - sum(a.attributions_resolues for a in annees),
                sum(a.attributions for a in annees),
            ),
            # Les hauteurs de la figure sont calculees ici, pas dans le gabarit : une regle de
            # trois au milieu du HTML est illisible et intestable.
            "figure": figure_par_annee(annees),
        },
    )


@routeur.get("/recherche", response_class=HTMLResponse)
def recherche(
    requete: Request,
    curseur_sql: Curseur,
    q: Annotated[str | None, Query(max_length=TEXTE_MAXIMUM)] = None,
    # Quarante caracteres, et non la longueur exacte attendue : ces champs sont remplis a la
    # main, et une annee tapee « deux mille vingt-quatre » doit etre ignoree, pas refusee par
    # une page d'erreur. La borne reste la pour que personne n'envoie un kilo-octet par champ.
    annee: Annotated[str | None, Query(max_length=40)] = None,
    departement: Annotated[str | None, Query(max_length=40)] = None,
    famille: Annotated[str | None, Query(max_length=40)] = None,
    montant_minimum: Annotated[str | None, Query(max_length=40)] = None,
    montant_maximum: Annotated[str | None, Query(max_length=40)] = None,
    offre_unique: Annotated[bool, Query()] = False,
    page_demandee: Annotated[int, Query(alias="page", ge=1, le=PAGE_MAXIMUM)] = 1,
) -> HTMLResponse:
    """La recherche : un formulaire, une liste, et ce que la liste ne dit pas.

    Les filtres arrivent en texte et sont lus avec indulgence (voir `entier_ou_rien`). Ils sont
    ensuite passes a la fonction de route de l'API, qui applique ses propres bornes : le site ne
    duplique aucune regle de validation, il traduit un formulaire en appel.
    """
    # Chaque critere dans sa propre variable, et non dans un dictionnaire : un dictionnaire
    # melangeant chaines, entiers et booleens perd son type des qu'on le relit, et l'erreur se
    # verrait a l'execution au lieu de la verification.
    mots = texte_ou_rien(q)
    an = entier_ou_rien(annee, 2014, 2030)
    dep = texte_ou_rien(departement)
    fam = texte_ou_rien(famille)
    plancher = decimal_ou_rien(montant_minimum)
    plafond = decimal_ou_rien(montant_maximum)

    resultats: PageDeMarches | None = None
    erreur = ""
    if plancher is not None and plafond is not None and plancher > plafond:
        # Dit en francais plutot que renvoye en 422 : le visiteur a inverse deux cases, il n'a
        # pas besoin d'un code de statut.
        erreur = "Le montant minimum est supérieur au montant maximum."
    else:
        resultats = chercher_des_marches(
            curseur_sql,
            q=mots,
            annee=an,
            departement=dep,
            famille=fam,
            montant_minimum=plancher,
            montant_maximum=plafond,
            offre_unique=offre_unique,
            page=page_demandee,
            taille=PAR_PAGE,
        )
    return page(
        requete,
        "recherche.html",
        {
            "titre": "Rechercher un marché",
            # Ce que le service a retenu, pour que la page puisse le dire.
            "criteres": {"q": mots, "offre_unique": offre_unique},
            # Ce que le visiteur a tape, pour le reafficher tel quel dans le formulaire. Les
            # deux different quand une valeur a ete ignoree, et reafficher la valeur nettoyee
            # effacerait la frappe sans explication.
            "brut": {
                "q": q or "",
                "annee": annee or "",
                "departement": departement or "",
                "famille": famille or "",
                "montant_minimum": montant_minimum or "",
                "montant_maximum": montant_maximum or "",
            },
            "resultats": resultats,
            "erreur": erreur,
            "page_courante": page_demandee,
            "page_maximum": PAGE_MAXIMUM,
            "parametres": parametres_sans_page(requete),
        },
        fragment="fragments/resultats.html",
    )


def parametres_sans_page(requete: Request) -> str:
    """Les parametres de la requete courante, sans `page`, pour fabriquer les liens de pagination.

    Reconstruits depuis la requete plutot qu'assembles depuis les criteres : ce qui est dans
    l'adresse est ce que le visiteur a demande, et le lien « page suivante » doit le conserver
    exactement, y compris un filtre que le site ignorerait.
    """
    gardes = [
        f"{cle}={valeur}"
        for cle, valeur in requete.query_params.multi_items()
        if cle != "page" and valeur
    ]
    return "&".join(gardes)


@routeur.get("/fiche/{marche_id}", response_class=HTMLResponse)
def fiche(
    requete: Request,
    curseur_sql: Curseur,
    marche_id: Annotated[str, Path(min_length=1, max_length=64)],
) -> HTMLResponse:
    """La fiche d'un marche : toutes ses lignes, et ce qui a ete remarque dessus.

    Plusieurs lignes et non une : un marche attribue a un groupement d'entreprises compte une
    ligne par titulaire. La page le dit, parce que voir deux fois le meme numero de marche sans
    explication ressemble a un doublon.
    """
    try:
        detaille = lire_un_marche(curseur_sql, marche_id)
    except HTTPException as refus:
        if refus.status_code != 404:
            raise
        return page(
            requete,
            "erreur.html",
            {
                "titre": "Marché introuvable",
                "message": f"Aucun marché ne porte le numéro « {marche_id} ».",
                "detail": "Le numéro est celui publié par l'acheteur. Il n'est pas unique "
                "entre acheteurs, et certains marchés anciens n'en portent pas.",
            },
            code=404,
        )
    return page(
        requete,
        "fiche.html",
        {
            "titre": f"Marché {marche_id}",
            "marche_id": marche_id,
            "lignes": detaille.lignes,
            "signaux": detaille.signaux,
            "montant_total": somme_des_montants(detaille.lignes),
        },
    )


def somme_des_montants(lignes: list[Any]) -> Decimal | None:
    """Le montant d'un marche a plusieurs titulaires.

    Attention a ce que ce chiffre veut dire : dans les DECP, le montant publie sur chaque ligne
    d'un groupement est tres souvent le montant **du marche entier**, repete, et non la part du
    titulaire. Les additionner donnerait alors un total faux, multiplie par le nombre de
    titulaires. La page affiche donc le montant quand il est identique sur toutes les lignes, et
    refuse de totaliser quand il differe, en le disant.
    """
    montants = {ligne.montant for ligne in lignes if ligne.montant is not None}
    return montants.pop() if len(montants) == 1 else None


@routeur.get("/a-examiner", response_class=HTMLResponse)
def a_examiner(
    requete: Request,
    curseur_sql: Curseur,
    minimum: Annotated[int, Query(ge=1, le=5)] = 1,
    page_demandee: Annotated[int, Query(alias="page", ge=1, le=PAGE_MAXIMUM)] = 1,
) -> HTMLResponse:
    """Les marches qui s'ecartent de leurs pairs, avec leurs motifs en clair.

    Le titre de la page est « a examiner » et non « anomalies », et ce n'est pas de la prudence
    de facade : la concordance de ces regles avec les anomalies publiees par le producteur est
    de 69,3 pour cent hors echantillon, intervalle de 67,8 a 70,8. Un marche signale est un
    marche a regarder, pas un marche fautif, et la page le repete a cote de la liste.
    """
    page_de_signaux = lister_les_signaux(
        curseur_sql, minimum=minimum, page=page_demandee, taille=PAR_PAGE
    )
    return page(
        requete,
        "a-examiner.html",
        {
            "titre": "Marchés à examiner",
            "signaux": page_de_signaux.resultats,
            "minimum": minimum,
            "page_courante": page_demandee,
            "page_suivante": page_de_signaux.page_suivante,
            "parametres": parametres_sans_page(requete),
        },
        fragment="fragments/signaux.html",
    )


# Des questions que l'assistant sait lire, proposees comme point de depart.
#
# Elles sont recopiees telles quelles du jeu versionne `mesures/verification/
# questions-assistant.csv`, et un test verifie que chacune y figure encore. Ce ne sont donc pas
# des exemples choisis pour bien paraitre : ce sont ceux dont la reponse, les chiffres et les
# citations sont reverifies a chaque `make bench-assistant`.
#
# La derniere est un refus, et elle est affichee comme telle. Montrer ce que l'assistant refuse
# de repondre est plus informatif que de montrer quatre reussites : c'est la difference entre un
# outil qui s'arrete et un outil qui invente.
EXEMPLES_DE_QUESTIONS = (
    ("combien de marches de voirie en 2023", "un comptage"),
    ("qui a remporte les marches de voirie en Ile-de-France en 2023", "des titulaires"),
    ("marches atypiques de voirie", "des marches signales"),
    ("entretien des espaces verts a Rennes", "des extraits"),
    ("quel est le meilleur fournisseur de voirie", "un refus : la question demande un avis"),
)


@routeur.get("/questions", response_class=HTMLResponse)
def questions(
    requete: Request,
    curseur_sql: CurseurPositionnel,
    lexiques: LexiquesEventuels,
    question: Annotated[str | None, Query(max_length=TEXTE_MAXIMUM)] = None,
) -> HTMLResponse:
    """Poser une question en francais, et obtenir une reponse qui cite ses sources.

    Aucun modele de langue n'intervient. La page affiche donc, a cote de la phrase, le filtre
    que l'assistant a compris et les numeros de marche cites : c'est ce qui permet au lecteur de
    verifier au lieu de croire. Quand l'assistant ne sait pas lire la question, il le dit, et la
    page affiche ce refus tel quel plutot qu'une reponse approchante.
    """
    pose = texte_ou_rien(question)
    reponse = None
    # Trois caracteres au moins, comme l'API : en dessous, `websearch_to_tsquery` ne rend rien
    # d'exploitable et la reponse serait un refus deguise en resultat.
    if lexiques is not None and pose is not None and len(pose) >= 3:
        reponse = interroger_l_assistant(curseur_sql, lexiques, question=pose)
    return page(
        requete,
        "questions.html",
        {
            "titre": "Poser une question",
            "question": pose or "",
            "reponse": reponse,
            "assistant_disponible": lexiques is not None,
            "exemples": EXEMPLES_DE_QUESTIONS,
        },
        fragment="fragments/reponse.html",
    )


@routeur.get("/a-propos", response_class=HTMLResponse)
def a_propos(requete: Request) -> HTMLResponse:
    """D'ou viennent les donnees, ce qu'elles valent, et ce que ce site ne peut pas dire.

    Cette page n'interroge pas la base, volontairement : elle doit rester consultable quand la
    base ne repond pas, parce que c'est exactement le moment ou l'on veut savoir ce que le site
    affiche d'habitude.
    """
    return page(requete, "a-propos.html", {"titre": "À propos des données"})
