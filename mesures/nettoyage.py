"""Effet mesure de chaque regle de nettoyage.

Une regle de nettoyage qui n'est pas mesuree est une affirmation. Ce script repond a trois
questions, pour chaque regle de la couche argent :

  - combien de lignes elle marque ;
  - ce que cela represente en part du total ;
  - ce qu'il reste une fois toutes les regles appliquees.

Il mesure aussi le passage d'une couche a l'autre, qui est la vraie mesure du nettoyage : 3,3
millions de lignes brutes deviennent 2,1 millions de lignes a l'etat actuel, puis 2,0 millions de
lignes exploitables pour une analyse de prix.

Pourquoi lire la base plutot que recalculer :

    Option                    Avantage                    Limite                  Verdict
    Interroger le fichier     la mesure porte sur ce      demande que la chaine   retenu
    DuckDB produit par dbt    que la chaine a vraiment    ait tourne avant
                              produit
    Refaire les regles en     autonome                    deux definitions des    ecarte
    Python dans ce script                                 memes regles, qui
                                                          divergeront
    Lire le Parquet brut      pas de dependance a dbt     ne mesure pas le        ecarte
                                                          nettoyage, seulement
                                                          la donnee brute

La deuxieme option est la plus tentante et la plus dangereuse : deux ecritures d'une meme regle
finissent toujours par diverger, et c'est alors la mesure qui ment, pas la chaine.

**Toutes les requetes de ce fichier sont ecrites en entier.** Fabriquer le nom d'une colonne ou
d'une table par interpolation de chaine ferait gagner quelques lignes, mais produirait du SQL
construit par concatenation, forme que l'analyse de securite refuse a juste titre. Ecrire les neuf
regles en une seule requete est au passage plus rapide : un seul passage sur la table au lieu de
neuf.

Lancement : `make bench-nettoyage`, apres `make transformer`.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

RACINE = Path(__file__).resolve().parent.parent
BASE = RACINE / "donnees" / "commande_publique.duckdb"
SORTIE = RACINE / "mesures" / "resultats"

# Un seul passage sur la table compte les lignes marquees par chacune des neuf regles. Les
# colonnes valent true quand la regle est respectee : on compte donc les false.
REQUETE_REGLES = """
select
    count(*)                                                        as lignes_totales,
    sum(case when not montant_renseigne then 1 else 0 end)          as montant_renseigne,
    sum(case when not montant_plausible then 1 else 0 end)          as montant_plausible,
    sum(case when not montant_sans_anomalie_signalee then 1 else 0 end)
        as montant_sans_anomalie_signalee,
    sum(case when not date_plausible then 1 else 0 end)             as date_plausible,
    sum(case when not duree_plausible then 1 else 0 end)            as duree_plausible,
    sum(case when not acheteur_siret_valide then 1 else 0 end)      as acheteur_siret_valide,
    sum(case when not titulaire_siret_valide then 1 else 0 end)     as titulaire_siret_valide,
    sum(case when not offres_plausibles then 1 else 0 end)          as offres_plausibles,
    sum(case when not cpv_conforme then 1 else 0 end)               as cpv_conforme,
    sum(case when exploitable_pour_les_prix then 1 else 0 end)      as exploitables
from argent_marches
"""

# Ce que chaque regle verifie, en francais. L'ordre suit celui du modele SQL, pour qu'on puisse
# lire les deux cote a cote.
#
# Ces libelles sont du texte destine a etre lu : ils portent donc leurs accents, contrairement aux
# noms de colonnes et de fichiers, qui restent en ASCII pour se comporter pareil sur tout systeme.
# Ils sont volontairement courts : ils servent d'etiquettes dans une figure.
DESCRIPTIONS: dict[str, str] = {
    "montant_renseigne": "Montant présent et positif",
    "montant_plausible": "Montant sous le milliard d'euros",
    "montant_sans_anomalie_signalee": "Montant non signalé par le producteur",
    "date_plausible": "Date de notification possible",
    "duree_plausible": "Durée inférieure à vingt ans",
    "acheteur_siret_valide": "SIRET de l'acheteur conforme",
    "titulaire_siret_valide": "SIRET du titulaire conforme",
    "offres_plausibles": "Nombre d'offres crédible",
    "cpv_conforme": "Code CPV conforme à la nomenclature",
}

# Les trois couches, avec une requete ecrite en entier pour chacune.
REQUETES_COUCHES: list[tuple[str, str, str, str]] = [
    (
        "bronze",
        "bronze_decp",
        "la donnee telle que la source l'a publiee",
        "select count(*) as lignes from bronze_decp",
    ),
    (
        "argent",
        "argent_marches",
        "l'etat actuel de chaque marche, problemes marques",
        "select count(*) as lignes from argent_marches",
    ),
    (
        "or",
        "or_marches",
        "les marches exploitables pour une analyse de prix",
        "select count(*) as lignes from or_marches",
    ),
]

REQUETE_COLONNES = """
select table_name, count(*) as colonnes
from information_schema.columns
where table_name in ('bronze_decp', 'argent_marches', 'or_marches')
group by 1
"""

REQUETE_NORMALISATION = """
select
    nature_normalisee      as notion,
    count(*)               as lignes,
    count(distinct nature) as ecritures_regroupees
from argent_marches
where nature_normalisee is not null
group by 1
order by lignes desc
"""


def mesurer_regles(con: duckdb.DuckDBPyConnection) -> tuple[list[dict[str, Any]], int, int]:
    """Pour chaque regle : combien de lignes elle marque, et quelle part cela represente."""
    resultat = con.sql(REQUETE_REGLES)
    valeurs = dict(zip(resultat.columns, resultat.fetchone() or (), strict=True))
    lignes_totales = int(valeurs["lignes_totales"])

    mesures = [
        {
            "regle": regle,
            "verifie": description,
            "lignes_marquees": int(valeurs[regle]),
            "part_pourcent": round(100 * int(valeurs[regle]) / lignes_totales, 3),
        }
        for regle, description in DESCRIPTIONS.items()
    ]
    return mesures, lignes_totales, int(valeurs["exploitables"])


def mesurer_couches(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Le passage d'une couche a l'autre : ce qui entre, ce qui sort, et pourquoi."""
    colonnes = dict(con.sql(REQUETE_COLONNES).fetchall())
    mesures: list[dict[str, Any]] = []
    for couche, table, contenu, requete in REQUETES_COUCHES:
        lignes = con.sql(requete).fetchone()
        mesures.append(
            {
                "couche": couche,
                "table": table,
                "contenu": contenu,
                "lignes": int(lignes[0]) if lignes else 0,
                "colonnes": int(colonnes.get(table, 0)),
            }
        )
    return mesures


def mesurer_normalisation(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Combien d'ecritures differentes chaque notion regroupe, apres normalisation."""
    return [
        {"notion": notion, "lignes": int(lignes), "ecritures_regroupees": int(ecritures)}
        for notion, lignes, ecritures in con.sql(REQUETE_NORMALISATION).fetchall()
    ]


def ecrire(nom: str, lignes: list[dict[str, Any]]) -> Path:
    """Ecrit une mesure en CSV, fins de ligne Unix et retour a la ligne final."""
    SORTIE.mkdir(parents=True, exist_ok=True)
    chemin = SORTIE / f"{nom}.csv"
    with chemin.open("w", newline="", encoding="utf-8") as sortie:
        auteur = csv.DictWriter(sortie, fieldnames=list(lignes[0].keys()), lineterminator="\n")
        auteur.writeheader()
        auteur.writerows(lignes)
    return chemin


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Base absente : {BASE}. Lancer d'abord `make transformer`.")

    con = duckdb.connect(str(BASE), read_only=True)

    couches = mesurer_couches(con)
    print("Les trois couches :")
    for couche in couches:
        lignes = f"{couche['lignes']:,}".replace(",", " ")
        print(
            f"  {couche['couche']:<8} {lignes:>12} lignes  "
            f"{couche['colonnes']:>3} colonnes   {couche['contenu']}"
        )

    regles, total, exploitables = mesurer_regles(con)
    print("\nEffet de chaque regle de nettoyage, sur la couche argent :")
    for regle in sorted(regles, key=lambda r: int(r["lignes_marquees"]), reverse=True):
        marquees = f"{regle['lignes_marquees']:,}".replace(",", " ")
        print(f"  {marquees:>9} lignes ({regle['part_pourcent']:>6.3f} %)   {regle['verifie']}")
    print(
        f"\n  {exploitables:,} lignes exploitables pour une analyse de prix, "
        f"soit {100 * exploitables / total:.1f} %".replace(",", " ")
    )

    normalisation = mesurer_normalisation(con)
    regroupees = sum(int(n["ecritures_regroupees"]) for n in normalisation)
    print(
        f"\nNormalisation de la nature : {regroupees} ecritures ramenees a "
        f"{len(normalisation)} notions"
    )

    for nom, lignes_mesurees in (
        ("nettoyage-couches", couches),
        ("nettoyage-regles", regles),
        ("nettoyage-normalisation", normalisation),
    ):
        chemin = ecrire(nom, lignes_mesurees)
        print(f"Ecrit : {chemin.relative_to(RACINE)}")

    print(f"\nMesure du {datetime.now(UTC).date().isoformat()}")


if __name__ == "__main__":
    main()
