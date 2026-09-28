"""Fabrique le jeu de donnees fictif qui sert aux tests de la transformation.

Pourquoi un fichier fabrique plutot que le vrai jeu :

    Option                Avantage                      Limite                    Verdict
    Jeu fictif de 12      chaque defaut est connu        ne reflete pas toute la   retenu
    lignes, commite       d'avance, le test tourne       variete du reel
                          en une seconde
    Extrait du vrai jeu   realiste                       les defauts changent a    ecarte
                                                         chaque republication,
                                                         le test devient instable
    Le jeu complet        verite terrain                 250 Mo, dix secondes      ecarte
                                                         par test

Chaque ligne du jeu fictif porte **un defaut et un seul**, nomme dans son identifiant. Quand un
test echoue, le nom de la ligne dit immediatement quelle regle a lache.

Lancement : `uv run python tests/fixtures/construire_bronze_fictif.py`
Le fichier produit est versionne : il fait quelques kilooctets, et le regenerer a chaque test
serait du temps perdu.
"""

from datetime import date
from pathlib import Path

import duckdb

SORTIE = Path(__file__).resolve().parent / "bronze_fictif.parquet"

# Une ligne par cas a couvrir. L'identifiant dit ce que la ligne teste.
# Colonnes : uid, id, nature, acheteur_id, acheteur_nom, titulaire_id, objet, montant,
#            montant_anomalie, codeCPV, dureeMois, offresRecues, dateNotification,
#            donneesActuelles, sourceDataset
LIGNES = [
    # Le cas normal : toutes les regles passent.
    (
        "normal",
        "M1",
        "Marché",
        "21130108000019",
        "Ville d'essai",
        "35009850500026",
        "entretien des ascenseurs",
        150000.0,
        None,
        "50750000",
        24,
        3,
        date(2025, 2, 10),
        True,
        "essai",
    ),
    # Une deuxieme ligne normale, ecrite autrement : la normalisation doit les regrouper.
    (
        "normal-casse",
        "M2",
        "MARCHÉ",
        "21130108000019",
        "Ville d'essai",
        "35009850500026",
        "travaux de voirie",
        90000.0,
        None,
        "45233000",
        12,
        5,
        date(2025, 3, 1),
        True,
        "essai",
    ),
    # Une troisieme graphie, avec un tiret : la ponctuation aussi doit etre normalisee.
    (
        "normal-tiret",
        "M3",
        "Accord-cadre",
        "21130108000019",
        "Ville d'essai",
        "35009850500026",
        "fournitures de bureau",
        40000.0,
        None,
        "30190000",
        36,
        2,
        date(2025, 4, 1),
        True,
        "essai",
    ),
    (
        "normal-espace",
        "M4",
        "ACCORD CADRE",
        "21130108000019",
        "Ville d'essai",
        "35009850500026",
        "fournitures scolaires",
        25000.0,
        None,
        "39160000",
        36,
        4,
        date(2025, 5, 1),
        True,
        "essai",
    ),
    # Un defaut par ligne, a partir d'ici.
    (
        "montant-absent",
        "M5",
        "Marché",
        "21130108000019",
        "Ville",
        "35009850500026",
        "sans montant",
        None,
        None,
        "50750000",
        12,
        3,
        date(2025, 2, 10),
        True,
        "essai",
    ),
    (
        "montant-negatif",
        "M6",
        "Marché",
        "21130108000019",
        "Ville",
        "35009850500026",
        "montant negatif",
        -5000.0,
        None,
        "50750000",
        12,
        3,
        date(2025, 2, 10),
        True,
        "essai",
    ),
    (
        "montant-enorme",
        "M7",
        "Marché",
        "21130108000019",
        "Ville",
        "35009850500026",
        "valeur de remplissage",
        99999999999.99,
        None,
        "50750000",
        12,
        3,
        date(2025, 2, 10),
        True,
        "essai",
    ),
    (
        "montant-signale",
        "M8",
        "Marché",
        "21130108000019",
        "Ville",
        "35009850500026",
        "signale par le producteur",
        500000.0,
        "aberrant",
        "50750000",
        12,
        3,
        date(2025, 2, 10),
        True,
        "essai",
    ),
    (
        "date-an-1",
        "M9",
        "Marché",
        "21130108000019",
        "Ville",
        "35009850500026",
        "date par defaut",
        150000.0,
        None,
        "50750000",
        12,
        3,
        date(1, 1, 1),
        True,
        "essai",
    ),
    (
        "duree-absurde",
        "M10",
        "Marché",
        "21130108000019",
        "Ville",
        "35009850500026",
        "duree de 2600 ans",
        150000.0,
        None,
        "50750000",
        32000,
        3,
        date(2025, 2, 10),
        True,
        "essai",
    ),
    (
        "siret-acheteur-faux",
        "M11",
        "Marché",
        "00001",
        "Ville",
        "35009850500026",
        "identifiant acheteur tronque",
        150000.0,
        None,
        "50750000",
        12,
        3,
        date(2025, 2, 10),
        True,
        "essai",
    ),
    (
        "siret-titulaire-faux",
        "M12",
        "Marché",
        "21130108000019",
        "Ville",
        "00001",
        "identifiant titulaire tronque",
        150000.0,
        None,
        "50750000",
        12,
        3,
        date(2025, 2, 10),
        True,
        "essai",
    ),
    (
        "offres-absurdes",
        "M13",
        "Marché",
        "21130108000019",
        "Ville",
        "35009850500026",
        "vingt mille offres",
        150000.0,
        None,
        "50750000",
        12,
        20300,
        date(2025, 2, 10),
        True,
        "essai",
    ),
    (
        "cpv-texte-libre",
        "M14",
        "Marché",
        "21130108000019",
        "Ville",
        "35009850500026",
        "code CPV rempli a la main",
        150000.0,
        None,
        "Travaux",
        12,
        3,
        date(2025, 2, 10),
        True,
        "essai",
    ),
    # Une ligne d'historique : elle ne doit jamais apparaitre en couche argent.
    (
        "historique",
        "M15",
        "Marché",
        "21130108000019",
        "Ville",
        "35009850500026",
        "version anterieure d'un marche",
        100000.0,
        None,
        "50750000",
        12,
        3,
        date(2024, 1, 1),
        False,
        "essai",
    ),
]


def main() -> None:
    con = duckdb.connect()
    con.execute("""
        create table cas (
            uid varchar, id varchar, nature varchar,
            acheteur_id varchar, acheteur_nom varchar, titulaire_id varchar,
            objet varchar, montant double, montant_anomalie varchar,
            codeCPV varchar, dureeMois smallint, offresRecues smallint,
            dateNotification date, donneesActuelles boolean, sourceDataset varchar
        )
    """)
    con.executemany("insert into cas values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", LIGNES)

    # Les colonnes ci-dessous ne discriminent aucun cas de test : elles servent seulement a ce que
    # la couche or, qui les expose, puisse se construire. Les ecrire dans chaque ligne de LIGNES
    # rendrait les cas illisibles, alors qu'ils doivent se lire d'un coup d'oeil.
    con.execute("""
        create table bronze_fictif as
        select
            *,
            'Commune'          as acheteur_categorie,
            '13'               as acheteur_departement_code,
            'Bouches-du-Rhone' as acheteur_departement_nom,
            'Provence'         as acheteur_region_nom,
            'Ville d''essai'   as acheteur_commune_nom,
            43.3               as acheteur_latitude,
            5.4                as acheteur_longitude,
            'Entreprise d''essai' as titulaire_nom,
            'PME'              as titulaire_categorie,
            12                 as titulaire_distance,
            'Procedure adaptee' as procedure
        from cas
    """)
    con.execute("copy bronze_fictif to ? (format parquet)", [str(SORTIE)])
    colonnes = len(con.execute("describe bronze_fictif").fetchall())
    print(f"{len(LIGNES)} lignes et {colonnes} colonnes ecrites dans {SORTIE.name}")


if __name__ == "__main__":
    main()
