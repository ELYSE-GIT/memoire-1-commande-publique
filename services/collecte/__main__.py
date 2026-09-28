"""Point d'entree de la collecte, en ligne de commande.

Usage :
    uv run python -m services.collecte decp
    uv run python -m services.collecte boamp --debut 2025-01-01 --fin 2025-07-01
    uv run python -m services.collecte etat

Ou, plus simplement, par le Makefile : `make collecte-decp`, `make collecte-boamp`, `make collecte`.

Pourquoi un module executable plutot qu'un script par source :

    Option                Avantage                        Limite                  Verdict
    Un module avec        une seule facon de lancer,      un fichier de plus      retenu
    sous-commandes        les options sont documentees
                          par `--help`
    Un script par source  immediat a ecrire               la logique commune se   ecarte
                                                          duplique
    Une fonction appelee  souple                          rien n'est executable   ecarte
    depuis un notebook                                    sans ouvrir un notebook
"""

from __future__ import annotations

import argparse
import sys

from services.collecte import manifeste, sources


def afficher(entree: manifeste.Entree) -> None:
    """Resume d'une collecte, pour la sortie terminal."""
    print(f"  source     : {entree.source}")
    print(f"  fichier    : {entree.fichier}")
    print(f"  taille     : {entree.taille_mo} Mo")
    if entree.lignes is not None:
        print(f"  lignes     : {entree.lignes}")
    print(f"  empreinte  : {entree.empreinte_sha256[:16]}...")


def commande_etat() -> int:
    """Affiche le dernier manifeste et verifie que les fichiers sont intacts."""
    entrees = manifeste.dernier_manifeste()
    if not entrees:
        print("Aucune collecte enregistree. Lancer `make collecte-decp`.")
        return 1

    print(f"Derniere collecte : {entrees[0].date_collecte[:10]}\n")
    tout_va_bien = True
    for entree in entrees:
        intact = manifeste.verifier(entree)
        tout_va_bien = tout_va_bien and intact
        etat = "intact" if intact else "MANQUANT OU MODIFIE"
        lignes = f", {entree.lignes} lignes" if entree.lignes is not None else ""
        print(f"  {entree.source:<8} {entree.taille_mo:>7} Mo{lignes:<18} {etat}")
        print(f"           {entree.fichier}")
    return 0 if tout_va_bien else 1


def main(arguments: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        prog="services.collecte",
        description="Collecte les sources du projet vers la couche bronze.",
    )
    sous = analyseur.add_subparsers(dest="commande", required=True)

    sous.add_parser("decp", help="telecharge le jeu DECP consolide (environ 240 Mo)")

    boamp = sous.add_parser("boamp", help="recupere les avis du BOAMP sur une periode")
    boamp.add_argument("--debut", default="2025-01-01", help="date de debut, incluse")
    boamp.add_argument("--fin", default="2025-07-01", help="date de fin, exclue")
    boamp.add_argument("--maximum", type=int, default=2000, help="nombre maximal d'avis")

    sous.add_parser("etat", help="affiche le dernier manifeste et verifie les fichiers")

    options = analyseur.parse_args(arguments)

    if options.commande == "decp":
        print("Collecte des DECP consolidees")
        afficher(sources.collecter_decp())
        return 0

    if options.commande == "boamp":
        print(f"Collecte du BOAMP, du {options.debut} au {options.fin}")
        afficher(sources.collecter_boamp(options.debut, options.fin, options.maximum))
        return 0

    return commande_etat()


if __name__ == "__main__":
    sys.exit(main())
