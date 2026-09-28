"""Les trois sources du projet, et comment les collecter.

Chaque source a sa fonction de collecte. Toutes suivent la meme forme : elles deposent un fichier
dans la couche bronze, ecrivent une entree au manifeste, et renvoient cette entree.

Ce que la couche bronze garantit : la donnee y est **telle que la source l'a publiee**. Aucun
filtre, aucun renommage, aucune correction. C'est le seul endroit ou l'on peut encore comparer ce
que l'on a recu a ce que l'on a produit, et c'est ce qui rend la chaine rejouable apres correction
d'une regle de nettoyage.

Pourquoi un fichier par jour plutot qu'un fichier unique ecrase :

    Option                 Avantage                       Limite                    Verdict
    Un instantane date     rejouable, comparable dans     236 Mo par collecte       retenu, avec
    par collecte           le temps, incident tracable                              purge manuelle
    Un fichier ecrase      un seul fichier a gerer        une mesure d'hier ne      ecarte
                                                          peut plus etre refaite
    Tout l'historique      analyse des corrections        des dizaines de Go pour   hors sujet ici
    conserve indefiniment  apportees par les acheteurs    un gain non demontre
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from services.collecte import appels, manifeste
from services.collecte.manifeste import BRONZE, Entree

# Le jeu DECP consolide est republie chaque matin, et son adresse contient la date de publication.
# On passe donc par l'API du catalogue pour obtenir l'adresse du jour, plutot que de figer une
# adresse qui serait perimee des le lendemain.
CATALOGUE_DECP = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "donnees-essentielles-de-la-commande-publique-consolidees-format-tabulaire/"
)
FICHIER_DECP = "decp.parquet"

API_BOAMP = (
    "https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records"
)
# L'API limite chaque reponse a cent enregistrements, et refuse de depasser dix mille au total
# par requete. La collecte complete se fera donc par tranches de dates, en phase 3.
TAILLE_PAGE = 100


def _dossier_du_jour(source: str) -> Path:
    """Le dossier bronze de cette source pour aujourd'hui."""
    jour = datetime.now(UTC).date().isoformat()
    return BRONZE / source / jour


def adresse_decp() -> str:
    """Resout l'adresse du fichier Parquet publie aujourd'hui."""
    catalogue = appels.lire_json(CATALOGUE_DECP)
    for ressource in catalogue.get("resources", []):
        if ressource.get("title") == FICHIER_DECP:
            adresse: str = ressource["url"]
            return adresse
    message = f"{FICHIER_DECP} absent du catalogue : la source a peut-etre change de format"
    raise appels.EchecReseau(message)


def collecter_decp() -> Entree:
    """Telecharge le jeu DECP consolide et l'enregistre au manifeste."""
    adresse = adresse_decp()
    destination = _dossier_du_jour("decp") / FICHIER_DECP

    if destination.exists():
        # Idempotence : le fichier du jour existe deja, on ne le retelecharge pas. Son empreinte
        # est recalculee, ce qui verifie au passage qu'il n'a pas ete tronque.
        print(f"  deja present : {destination.relative_to(manifeste.RACINE)}")
    else:
        print(f"  telechargement depuis {adresse[:70]}...")
        appels.telecharger(adresse, destination)

    entree = manifeste.decrire(
        source="decp",
        adresse=adresse,
        chemin=destination,
        commentaire="jeu consolide, 63 sources agregees, republie quotidiennement",
    )
    manifeste.enregistrer(entree)
    return entree


def collecter_boamp(debut: str, fin: str, maximum: int = 2000) -> Entree:
    """Recupere les avis du BOAMP parus entre deux dates, en JSON ligne par ligne.

    Le format retenu est le JSON Lines : un avis par ligne. Il se lit en flux, sans charger tout
    le fichier, se concatene sans retraitement, et DuckDB le lit directement. Un JSON unique
    contenant un tableau obligerait a tout charger en memoire pour lire le premier avis.
    """
    destination = _dossier_du_jour("boamp") / f"avis-{debut}-{fin}.jsonl"
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists():
        print(f"  deja present : {destination.relative_to(manifeste.RACINE)}")
        lignes = sum(1 for _ in destination.open(encoding="utf-8"))
    else:
        temporaire = destination.with_suffix(".jsonl.partiel")
        lignes = 0
        with temporaire.open("w", encoding="utf-8") as sortie:
            for depart in range(0, maximum, TAILLE_PAGE):
                reponse = appels.lire_json(
                    API_BOAMP,
                    where=f"dateparution >= date'{debut}' and dateparution < date'{fin}'",
                    order_by="dateparution",
                    limit=TAILLE_PAGE,
                    offset=depart,
                )
                avis = reponse.get("results", [])
                if not avis:
                    break
                for un_avis in avis:
                    sortie.write(json.dumps(un_avis, ensure_ascii=False) + "\n")
                    lignes += 1
                print(f"    {lignes} avis collectes", end="\r")
        temporaire.replace(destination)
        print(f"    {lignes} avis collectes")

    entree = manifeste.decrire(
        source="boamp",
        adresse=f"{API_BOAMP} du {debut} au {fin}",
        chemin=destination,
        lignes=lignes,
        commentaire="avis de marche et resultats, format JSON Lines",
    )
    manifeste.enregistrer(entree)
    return entree
