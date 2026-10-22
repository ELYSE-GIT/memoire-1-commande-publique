"""Copie la couche or de DuckDB vers PostgreSQL.

DuckDB calcule, PostgreSQL sert. Ce script fait le pont entre les deux, et ne fait rien d'autre :
aucun nettoyage, aucun calcul, aucune correction. La couche or porte deja la promesse
« exploitable », et la refaire ici creerait deux verites.

Comment transferer deux millions de lignes :

    Option envisagee          Avantage                     Limite                      Verdict
    INSERT ligne a ligne      le plus simple a ecrire      un aller-retour reseau par  exclu
                                                           ligne : des heures
    executemany par lots      correct, et portable         PostgreSQL analyse la       ecarte
                                                           requete a chaque lot
    **COPY depuis un flux**   le chemin le plus court      il faut respecter l'ordre   **retenu**
                              dans PostgreSQL, pas         exact des colonnes
                              d'analyse de requete
    COPY binaire              encore un peu plus rapide    chaque type doit etre       ecarte
                                                           encode a la main, pour un
                                                           gain non mesure
    fichier CSV intermediaire tres rapide aussi            un fichier temporaire de    ecarte
                                                           plusieurs Go, et les
                                                           guillemets a gerer

Le choix de COPY depuis un flux garde tout en memoire par lots de 50 000 lignes : rien n'est
ecrit sur le disque, et la memoire reste plate quelle que soit la taille de la table.

Ordre des operations, qui n'est pas negociable :

    1. `make base-init`  cree les tables, **sans index**
    2. `make charger`    ce script
    3. `make indexer`    cree les index

Construire les index avant le chargement obligerait PostgreSQL a les reequilibrer a chaque ligne.
La duree de chaque etape est affichee, pour que l'ecart soit mesure et non suppose.

Lancement : `make charger`.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import duckdb
import psycopg

from services.configuration import chaine_de_connexion

RACINE = Path(__file__).resolve().parent.parent.parent
BASE_DUCKDB = RACINE / "donnees" / "commande_publique.duckdb"

# Taille des lots lus dans DuckDB. 50 000 lignes tiennent dans quelques dizaines de megaoctets,
# et amortissent le cout fixe de chaque aller-retour. Mesure : au-dela, le gain devient nul.
TAILLE_LOT = 50_000

# Les colonnes copiees, dans l'ordre exact de la table PostgreSQL. La colonne `id` est generee
# par la base et la colonne `recherche` est calculee par elle : aucune des deux n'est ecrite ici.
#
# Cette liste est volontairement ecrite en entier plutot que deduite du schema. Un `select *`
# marcherait jusqu'au jour ou une colonne serait ajoutee d'un seul cote : le chargement
# continuerait en decalant silencieusement les valeurs d'une colonne.
COLONNES_MARCHES = [
    "marche_id",
    "reference_acheteur",
    "acheteur_siret",
    "acheteur_nom",
    "acheteur_categorie",
    "acheteur_departement_code",
    "acheteur_departement_nom",
    "acheteur_region_nom",
    "acheteur_commune_nom",
    "acheteur_latitude",
    "acheteur_longitude",
    "titulaire_siret",
    "titulaire_nom",
    "titulaire_categorie",
    "distance_km",
    "objet",
    "nature",
    "famille_cpv",
    "code_cpv",
    "procedure",
    "montant",
    "montant_log10",
    "duree_mois",
    "offres_recues",
    "offre_unique",
    "date_notification",
    "annee",
    "mois",
    "source",
]

COLONNES_SIGNAUX = [
    "marche_id",
    "famille_cpv",
    "marches_dans_la_famille",
    "mediane_log_famille",
    "ecart_log_famille",
    "ecart_normalise_famille",
    "marches_de_l_acheteur",
    "titulaires_de_l_acheteur",
    "part_du_titulaire",
    "marches_ensemble",
    "diversite_acheteur",
    "prix_tres_eleve",
    "prix_eleve_a_verifier",
    "prix_tres_bas_non_evalue",
    "offre_unique_sur_gros_marche",
    "titulaire_dominant",
    "signaux_forts",
    "motifs_de_signalement",
]


def copier(
    source: duckdb.DuckDBPyConnection,
    cible: psycopg.Connection[Any],
    table: str,
    vue_duckdb: str,
    colonnes: list[str],
) -> tuple[int, float]:
    """Copie une table de DuckDB vers PostgreSQL. Renvoie le nombre de lignes et la duree."""
    liste = ", ".join(colonnes)
    source.execute(f"select {liste} from {vue_duckdb}")  # noqa: S608 - liste fermee, voir plus haut

    debut = time.perf_counter()
    lignes = 0
    with (
        cible.cursor() as curseur,
        curseur.copy(f"copy {table} ({liste}) from stdin") as flux,  # noqa: S608
    ):
        while True:
            lot = source.fetchmany(TAILLE_LOT)
            if not lot:
                break
            for ligne in lot:
                flux.write_row(ligne)
            lignes += len(lot)
            # Avancement affiche seulement dans un vrai terminal : le retour chariot n'efface
            # rien quand la sortie part dans un fichier ou un tube, et le journal devient
            # illisible.
            if sys.stdout.isatty():
                print(f"  {table} : {lignes:,} lignes".replace(",", " "), end="\r")
    duree = time.perf_counter() - debut
    if sys.stdout.isatty():
        print(" " * 60, end="\r")
    return lignes, duree


def main() -> None:
    if not BASE_DUCKDB.exists():
        raise SystemExit(f"Base absente : {BASE_DUCKDB}. Lancer d'abord `make transformer`.")

    source = duckdb.connect(str(BASE_DUCKDB), read_only=True)

    with psycopg.connect(chaine_de_connexion("make charger")) as cible:
        with cible.cursor() as curseur:
            # Refus de charger par-dessus des donnees existantes. Un second chargement
            # doublerait tout en silence, et la cle technique ne l'empecherait pas : elle est
            # generee, donc chaque ligne reinseree recevrait un nouvel identifiant.
            curseur.execute("select count(*) from marches")
            resultat = curseur.fetchone()
            deja = resultat[0] if resultat else 0
            if deja:
                raise SystemExit(
                    f"La table `marches` contient deja {deja:,} lignes.\n".replace(",", " ")
                    + "Lancer `make base-vider` pour recharger proprement."
                )

        print("Publication de la couche or vers PostgreSQL")
        total = 0.0
        for table, vue, colonnes in (
            ("marches", "or_marches", COLONNES_MARCHES),
            ("signaux", "or_signaux", COLONNES_SIGNAUX),
        ):
            lignes, duree = copier(source, cible, table, vue, colonnes)
            total += duree
            debit = lignes / duree if duree else 0
            print(
                f"  {table:<9} {lignes:>9,} lignes en {duree:>6.1f} s"
                f"   ({debit:>8,.0f} lignes par seconde)".replace(",", " ")
            )

        cible.commit()
        print(f"\nTermine en {total:.1f} s. Index non construits : lancer `make indexer`.")


if __name__ == "__main__":
    main()
