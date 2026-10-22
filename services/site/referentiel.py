"""Les libelles des familles d'achat, lus une fois au demarrage.

Sans eux, le site affiche « CPV 45 » et « CPV 71 ». Ce sont les deux divisions les plus
frequentes de la commande publique francaise, et personne hors du metier ne sait ce qu'elles
designent. Un jury encore moins.

=== Pourquoi un fichier et pas une table ====================================

    Option envisagee       Avantage                      Limite                      Verdict
    **un CSV versionne,    relisible dans une revue de   il est charge par chaque    **retenu**
    lu au demarrage**      code, diffable, et disponible processus, soit 44 lignes
                           meme base eteinte             en memoire
    une table dans         jointure SQL possible         une nomenclature officielle  ecarte
    PostgreSQL                                            n'est pas une donnee
                                                          collectee : la recharger
                                                          avec les donnees melange
                                                          deux choses differentes
    un dictionnaire ecrit  rien a lire au demarrage      c'etait deja le cas, en      ecarte
    dans le code                                          double dans `figures.py`,
                                                          avec deux formulations
                                                          differentes du meme libelle

Ce qui a fait pencher : le fichier existe en un exemplaire, et `mesures/figures.py` le lit
aussi. Avant, les memes libelles etaient recopies dans deux dictionnaires Python de ce fichier,
qui n'etaient deja plus d'accord entre eux sur la formulation de six divisions.

A quelle echelle la reponse changerait : pour les 9 454 codes CPV complets, a huit chiffres, ce
serait une table, chargee avec le reste. Quarante-quatre lignes ne justifient pas une table.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
FICHIER = RACINE / "base" / "reference" / "familles-cpv.csv"


@dataclass(frozen=True)
class Famille:
    """Une division du vocabulaire commun pour les marches publics."""

    code: str
    libelle: str
    libelle_court: str


def _charger() -> dict[str, Famille]:
    """Lit le fichier une fois, a l'import du module.

    Une absence de fichier n'est pas rattrapee : il est versionne, donc son absence signifie que
    le depot est incomplet, et il vaut mieux le savoir au demarrage qu'a l'affichage d'une page.
    """
    with FICHIER.open(encoding="utf-8") as fichier:
        return {
            ligne["code"]: Famille(
                code=ligne["code"],
                libelle=ligne["libelle"],
                libelle_court=ligne["libelle_court"],
            )
            for ligne in csv.DictReader(fichier)
        }


FAMILLES = _charger()


def libelle_famille(code: str | None, court: bool = False) -> str:
    """Le libelle d'une division CPV, ou une mention explicite si elle est inconnue.

    Une division absente du fichier rend « Division 12 » plutot qu'une chaine vide : le lecteur
    voit qu'il y a bien une famille et qu'elle n'a pas de nom ici, au lieu de voir un trou. Un
    test verifie que ce cas ne se produit sur aucune famille reellement presente dans les
    donnees.
    """
    if not code:
        return "Famille non precisee"
    famille = FAMILLES.get(code)
    if famille is None:
        return f"Division {code}"
    return famille.libelle_court if court else famille.libelle
