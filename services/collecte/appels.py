"""Appels reseau de la collecte : telechargement de fichiers et interrogation d'API.

Ce module regroupe tout ce qui touche au reseau, pour une raison simple : c'est la seule partie du
projet qui peut echouer sans qu'on y soit pour rien. Un serveur public tombe, une connexion coupe,
une limite de debit se declenche. Isoler ces appels permet de leur appliquer un traitement uniforme
(reprise sur erreur, limitation de debit, journalisation) et de tester le reste sans reseau.

Pourquoi la bibliotheque standard plutot qu'une dependance :

    Option      Avantage                              Limite                        Verdict
    urllib      aucune dependance, presente meme      code verbeux, ni reprise      retenu
    (stdlib)    sur un VPS minimal                    ni session
    requests    la plus connue, API agreable          synchrone, projet en          non
                                                      maintenance douce
    httpx       meme API, plus l'asynchrone et des    une dependance de plus pour   a reconsiderer
                delais fins                           un gain non mesure ici        si parallele

La reprise sur erreur et la limitation de debit sont ecrites ici, en une trentaine de lignes. Les
prendre d'une bibliotheque tierce economiserait ces lignes, mais ajouterait une dependance a
surveiller pour un comportement qu'il faut de toute facon comprendre et savoir expliquer.

A quelle echelle la reponse changerait : si la collecte devait paralleliser des centaines d'appels
simultanes, ou gerer des sessions authentifiees, `httpx` deviendrait justifie.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Un service public interroge sans menagement finit par bloquer l'appelant, et degrade le service
# pour tout le monde. Ces valeurs sont volontairement en dessous des limites annoncees.
DELAI_ENTRE_APPELS = 1 / 6  # l'API Recherche d'entreprises annonce sept appels par seconde
DELAI_ATTENTE = 60  # secondes avant d'abandonner un appel
TENTATIVES = 4

# L'en-tete identity evite une reponse compressee : urllib ne la decompresse pas seul, contrairement
# a requests ou httpx. C'est exactement le genre de detail qu'une bibliotheque tierce absorbe.
ENTETES = {"Accept-Encoding": "identity", "User-Agent": "memoire-commande-publique/0.1"}


class EchecReseau(RuntimeError):
    """Un appel a echoue apres toutes les tentatives."""


def _attendre(tentative: int) -> None:
    """Attente croissante entre deux tentatives : 1 s, 2 s, 4 s, 8 s.

    Une attente fixe repeterait l'appel pendant que le serveur est encore en difficulte. Le
    doublement laisse le temps a un incident passager de se resoudre, sans bloquer trop longtemps.
    """
    time.sleep(2**tentative)


def _avec_reprise(action: Callable[[], Any], description: str) -> Any:
    """Execute une action reseau, en reessayant apres une erreur passagere.

    Distinction importante : une erreur 404 ne se retente pas, elle ne changera pas. Une erreur 500
    ou une coupure reseau, si.
    """
    for tentative in range(TENTATIVES):
        try:
            return action()
        except urllib.error.HTTPError as erreur:
            if erreur.code < 500 and erreur.code != 429:
                message = f"{description} : erreur {erreur.code}, definitive"
                raise EchecReseau(message) from erreur
            if tentative == TENTATIVES - 1:
                message = f"{description} : erreur {erreur.code} apres {TENTATIVES} tentatives"
                raise EchecReseau(message) from erreur
            print(f"    {description} : erreur {erreur.code}, nouvelle tentative")
            _attendre(tentative)
        except (urllib.error.URLError, TimeoutError) as erreur:
            if tentative == TENTATIVES - 1:
                message = f"{description} : reseau indisponible apres {TENTATIVES} tentatives"
                raise EchecReseau(message) from erreur
            print(f"    {description} : {erreur}, nouvelle tentative")
            _attendre(tentative)
    message = f"{description} : echec inattendu"
    raise EchecReseau(message)


def lire_json(adresse: str, **parametres: object) -> dict[str, Any]:
    """Interroge une API et renvoie sa reponse JSON."""
    url = f"{adresse}?{urllib.parse.urlencode(parametres)}" if parametres else adresse

    def appeler() -> dict[str, Any]:
        requete = urllib.request.Request(url, headers=ENTETES)  # noqa: S310
        with urllib.request.urlopen(requete, timeout=DELAI_ATTENTE) as reponse:  # noqa: S310
            contenu: dict[str, Any] = json.loads(reponse.read())
        return contenu

    resultat = _avec_reprise(appeler, f"appel a {adresse}")
    time.sleep(DELAI_ENTRE_APPELS)
    return dict(resultat)


def telecharger(adresse: str, destination: Path) -> Path:
    """Telecharge un fichier, par blocs, et renvoie son chemin.

    L'ecriture passe par un fichier temporaire renomme a la fin. Sans cette precaution, une
    coupure en cours de telechargement laisserait un fichier incomplet portant le nom attendu,
    que la suite de la chaine traiterait comme valide. C'est une condition de l'idempotence.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporaire = destination.with_suffix(destination.suffix + ".partiel")

    def recuperer() -> Path:
        requete = urllib.request.Request(adresse, headers=ENTETES)  # noqa: S310
        with (
            urllib.request.urlopen(requete, timeout=DELAI_ATTENTE) as reponse,  # noqa: S310
            temporaire.open("wb") as sortie,
        ):
            while bloc := reponse.read(1024 * 1024):
                sortie.write(bloc)
        temporaire.replace(destination)
        return destination

    try:
        return Path(_avec_reprise(recuperer, f"telechargement de {adresse}"))
    finally:
        temporaire.unlink(missing_ok=True)
