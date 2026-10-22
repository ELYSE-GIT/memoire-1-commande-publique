"""Configuration partagee des services : la chaine de connexion, et rien d'autre.

Ce fichier existe pour une raison mesurable : au 22 octobre 2026, **trois** modules
construisaient la meme chaine de connexion PostgreSQL a partir des memes variables, chacun avec
sa propre liste de variables obligatoires et son propre message d'erreur. Trois endroits qui
lisent la configuration, c'est trois comportements qui divergent le jour ou l'on ajoute un
reglage : le chargeur exige un mot de passe, l'API s'en passe, et personne ne s'en apercoit
avant la production.

    Option envisagee          Avantage                      Limite                      Verdict
    une fonction par module   aucun import a ecrire         trois listes de variables   ecarte,
                                                            obligatoires a maintenir,   c'etait
                                                            trois messages d'erreur     l'etat
                                                            differents                  precedent
    **un module partage**     une seule verite, un seul     un import de plus, et un    **retenu**
                              message d'erreur, un seul     dossier `services` qui
                              test a ecrire                 devient un paquet
    pydantic-settings         validation declarative,       une dependance de plus pour
                              types verifies, documente     cinq variables, et un
                              les valeurs par defaut        comportement implicite sur  ecarte
                                                            les valeurs manquantes
    un fichier de config      lisible sans lire le code     deux sources de verite avec
    (toml, yaml)                                            `.env`, et un secret qui    ecarte
                                                            finit par etre commite

A quelle echelle la reponse changerait : au-dela d'une quinzaine de reglages, ou le jour ou
plusieurs environnements auront besoin de valeurs par defaut differentes, pydantic-settings
devient le bon outil. Pour cinq variables dont une est un secret, il ajoute une dependance sans
rien retirer.
"""

import os

# Les variables sans valeur par defaut possible. Le mot de passe en fait partie, et c'est le
# point important : un service qui se connecte avec un mot de passe vide finit par le faire en
# production. `os.environ[...]` leve une erreur ; `os.environ.get(...)` renverrait None et la
# connexion partirait quand meme.
OBLIGATOIRES = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")

# L'hote et le port, eux, ont une valeur par defaut raisonnable en local. Le port du projet est
# 55432 et non 5432 : un PostgreSQL deja installe sur le Mac occupait le port standard. Le
# defaut reste 5432, qui est la valeur juste sur le VPS ; c'est `.env` qui decale le port en
# local.
HOTE_PAR_DEFAUT = "localhost"
PORT_PAR_DEFAUT = "5432"


def chaine_de_connexion(commande: str = "une commande make") -> str:
    """Fabrique la chaine de connexion PostgreSQL depuis l'environnement.

    `commande` sert uniquement au message d'erreur : il indique quelle cible du Makefile passe
    le fichier `.env` a uv. Sans cette precision, l'erreur dit quoi manque mais pas quoi taper.
    """
    manquantes = [nom for nom in OBLIGATOIRES if not os.environ.get(nom)]
    if manquantes:
        raise SystemExit(
            f"Variables absentes : {', '.join(manquantes)}.\n"
            f"Lancer par `{commande}`, qui passe le fichier .env a uv."
        )
    hote = os.environ.get("POSTGRES_HOST", HOTE_PAR_DEFAUT)
    port = os.environ.get("POSTGRES_PORT", PORT_PAR_DEFAUT)
    return (
        f"host={hote} port={port}"
        f" dbname={os.environ['POSTGRES_DB']}"
        f" user={os.environ['POSTGRES_USER']}"
        f" password={os.environ['POSTGRES_PASSWORD']}"
    )
