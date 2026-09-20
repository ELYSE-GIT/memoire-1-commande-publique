"""Agregats descriptifs du jeu DECP, pour les figures du memoire.

Complement de `decp_qualite.py` : celui-ci mesure la qualite (ce qui manque, ce qui est faux),
celui-la decrit la forme des donnees (combien, quand, ou, pour quel montant).

Chaque agregat est ecrit en CSV dans `mesures/resultats/`. Les figures sont ensuite tracees a
partir de ces CSV par `mesures/figures.py`, jamais a partir du fichier Parquet directement. La
separation est volontaire : une figure du memoire doit etre reproductible sans retelecharger
240 Mo, et un chiffre affiche doit exister dans un fichier que l'on peut ouvrir et verifier.

Perimetre : toutes les mesures portent sur `donneesActuelles`, c'est-a-dire l'etat actuel de chaque
marche, soit 1 833 468 marches. Inclure l'historique des avenants compterait plusieurs fois le meme
marche.

Pourquoi ce format et pas un autre :

    Option        Avantage                          Limite                       Verdict
    CSV           lisible, ouvrable partout,        pas de types                 retenu
                  diffable dans git
    JSON          types conserves, imbrication      moins direct a tracer        retenu pour
                                                                                 la qualite
    Parquet       compact, types                    illisible sans outil         non : ces
                                                                                 agregats font
                                                                                 quelques Ko
    base de       requetable                        disproportionne pour         non
    donnees                                         quelques dizaines de lignes

Lancement : `make bench-decp-distributions`.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any

import duckdb

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "donnees" / "brut" / "decp.parquet"
SORTIE = RACINE / "mesures" / "resultats"

# Nom du fichier de sortie, question posee, requete.
AGREGATS: list[tuple[str, str, str]] = [
    (
        "montants-tranches",
        "Comment les marches se repartissent-ils par tranche de montant ?",
        """
        select
            case
                when montant < 25000    then '1. moins de 25 k'
                when montant < 90000    then '2. 25 a 90 k'
                when montant < 214000   then '3. 90 a 214 k'
                when montant < 1000000  then '4. 214 k a 1 M'
                when montant < 10000000 then '5. 1 a 10 M'
                else                         '6. plus de 10 M'
            end as tranche,
            count(*) as marches,
            round(100.0 * count(*) / sum(count(*)) over (), 1) as part_pourcent
        from marches
        where montant > 0
        group by 1
        order by 1
        """,
    ),
    (
        "montants-total-annuel",
        "Que devient le total annuel quand on ecarte les montants signales comme aberrants ?",
        """
        select
            year(dateNotification) as annee,
            count(*)               as marches,
            round(sum(montant) / 1e9, 1) as total_brut_milliards,
            round(
                sum(case when montant_anomalie is null then montant else 0 end) / 1e9, 1
            ) as total_nettoye_milliards
        from marches
        where dateNotification between date '2019-01-01' and date '2025-12-31'
        group by 1
        order by 1
        """,
    ),
    (
        "saisonnalite-mensuelle",
        "La commande publique a-t-elle une saisonnalite ?",
        """
        select
            month(dateNotification) as mois,
            count(*)                as marches
        from marches
        where dateNotification between date '2019-01-01' and date '2025-12-31'
        group by 1
        order by 1
        """,
    ),
    (
        "acheteurs-categories",
        "Qui achete ?",
        """
        select
            coalesce(acheteur_categorie, '(non renseigne)') as categorie,
            count(*)                                        as marches,
            round(median(montant), 0)                       as montant_median
        from marches
        group by 1
        order by marches desc
        """,
    ),
    (
        "familles-cpv",
        "Qu'achete-t-on ? Les deux premiers chiffres du code CPV donnent la famille.",
        """
        select
            substr(codeCPV, 1, 2)     as famille_cpv,
            count(*)                  as marches,
            round(median(montant), 0) as montant_median
        from marches
        where codeCPV is not null
        group by 1
        having count(*) > 5000
        order by marches desc
        """,
    ),
    (
        "offres-recues",
        "Combien d'offres par marche, sur le sous-ensemble ou l'information existe ?",
        """
        select
            case
                when offresRecues = 1              then '1 offre'
                when offresRecues between 2 and 3  then '2 a 3 offres'
                when offresRecues between 4 and 9  then '4 a 9 offres'
                when offresRecues between 10 and 99 then '10 a 99 offres'
                else                                    '100 offres et plus'
            end as tranche,
            count(*) as marches
        from marches
        where offresRecues is not null
        group by 1
        order by min(offresRecues)
        """,
    ),
    (
        "normalisation-nature",
        "Combien d'ecritures differentes pour une meme nature de marche ?",
        """
        select
            nature            as ecriture,
            count(*)          as marches
        from marches
        where nature is not null
        group by 1
        order by marches desc
        """,
    ),
]


def ecrire_csv(chemin: Path, lignes: list[tuple[Any, ...]], colonnes: list[str]) -> None:
    """Ecrit un agregat en CSV, fins de ligne Unix et retour a la ligne final."""
    with chemin.open("w", newline="", encoding="utf-8") as sortie:
        auteur = csv.writer(sortie, lineterminator="\n")
        auteur.writerow(colonnes)
        auteur.writerows(lignes)


def main() -> None:
    if not FICHIER.exists():
        raise SystemExit(f"Fichier absent : {FICHIER}. Lancer d'abord `make donnees-decp`.")

    con = duckdb.connect()
    con.register("decp", con.read_parquet(str(FICHIER)))
    # Une vue plutot qu'un filtre repete dans chaque requete : le perimetre est defini une fois.
    con.execute("create view marches as select * from decp where donneesActuelles")

    SORTIE.mkdir(parents=True, exist_ok=True)
    for nom, question, sql in AGREGATS:
        debut = time.perf_counter()
        resultat = con.sql(sql)
        lignes = resultat.fetchall()
        duree = time.perf_counter() - debut
        chemin = SORTIE / f"{nom}.csv"
        ecrire_csv(chemin, lignes, list(resultat.columns))
        print(f"{nom:<28} {len(lignes):>3} lignes  {duree:>6.2f} s   {question}")

    print(f"\nEcrit dans {SORTIE.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
