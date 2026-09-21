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
    (
        "montants-histogramme",
        "Comment les montants se distribuent-ils, en echelle logarithmique ?",
        """
        select
            floor(log10(montant) * 4) / 4 as puissance_de_dix,
            count(*)                      as marches
        from marches
        where montant > 0
        group by 1
        having count(*) > 20
        order by 1
        """,
    ),
    (
        "concentration-titulaires",
        "Quelle part des montants revient aux plus gros titulaires ?",
        """
        with par_titulaire as (
            select titulaire_id, sum(montant) as total
            from marches
            where montant > 0
              and montant_anomalie is null
              and titulaire_id is not null
            group by 1
        ),
        classe as (
            select
                total,
                row_number() over (order by total desc) as rang,
                count(*) over ()                        as titulaires,
                sum(total) over ()                      as montant_total,
                sum(total) over (order by total desc rows between unbounded preceding
                                 and current row)       as cumul
            from par_titulaire
        )
        select
            round(100.0 * rang / titulaires, 2)       as part_titulaires,
            round(100.0 * cumul / montant_total, 2)   as part_montants
        from classe
        where rang % 500 = 0 or rang <= 10
        order by rang
        """,
    ),
    (
        "saisonnalite-annee-mois",
        "La saisonnalite est-elle stable d'une annee a l'autre ?",
        """
        select
            year(dateNotification)  as annee,
            month(dateNotification) as mois,
            count(*)                as marches
        from marches
        where dateNotification between date '2019-01-01' and date '2025-12-31'
        group by 1, 2
        order by 1, 2
        """,
    ),
    (
        "offre-unique-par-cpv",
        "Quelles familles d'achat recoivent le plus souvent une seule offre ?",
        """
        select
            substr(codeCPV, 1, 2) as famille_cpv,
            count(*)              as marches_renseignes,
            round(
                100.0 * sum(case when offresRecues = 1 then 1 else 0 end) / count(*), 1
            )                     as part_offre_unique
        from marches
        where offresRecues is not null and codeCPV is not null
        group by 1
        having count(*) > 10000
        order by part_offre_unique desc
        """,
    ),
    (
        "completude-champs",
        "Quels champs sont reellement exploitables ?",
        """
        select champ, round(100.0 * renseignes / total, 1) as part_renseigne
        from (
            select 'Montant' as champ, count(montant) as renseignes, count(*) as total from marches
            union all select 'Date de notification', count(dateNotification), count(*) from marches
            union all select 'Code CPV', count(codeCPV), count(*) from marches
            union all select 'Acheteur (identifiant)', count(acheteur_id), count(*) from marches
            union all select 'Titulaire (identifiant)', count(titulaire_id), count(*) from marches
            union all select 'Categorie d''acheteur', count(acheteur_categorie), count(*)
                from marches
            union all select 'Duree en mois', count(dureeMois), count(*) from marches
            union all select 'Procedure', count(procedure), count(*) from marches
            union all select 'Forme de prix', count(formePrix), count(*) from marches
            union all select 'Offres recues', count(offresRecues), count(*) from marches
            union all select 'Sous-traitance declaree', count(sousTraitanceDeclaree), count(*)
                from marches
            union all select 'Considerations sociales', count(considerationsSociales), count(*)
                from marches
        )
        order by part_renseigne desc
        """,
    ),
    (
        "acheteurs-quartiles",
        "Les distributions de montants different-elles selon le type d'acheteur ?",
        """
        select
            acheteur_categorie                      as categorie,
            count(*)                                as marches,
            round(quantile_cont(montant, 0.25), 0)  as quartile_1,
            round(median(montant), 0)               as mediane,
            round(quantile_cont(montant, 0.75), 0)  as quartile_3,
            round(quantile_cont(montant, 0.05), 0)  as bas,
            round(quantile_cont(montant, 0.95), 0)  as haut
        from marches
        where montant > 0 and acheteur_categorie is not null and montant_anomalie is null
        group by 1
        having count(*) > 20000
        order by mediane desc
        """,
    ),
    (
        "geographie-acheteurs",
        "Ou sont les acheteurs, vus par leurs coordonnees ?",
        """
        select
            round(acheteur_latitude, 1)  as latitude,
            round(acheteur_longitude, 1) as longitude,
            count(*)                     as marches
        from marches
        where acheteur_latitude between 41 and 52
          and acheteur_longitude between -5.5 and 9.8
        group by 1, 2
        having count(*) > 30
        order by marches desc
        """,
    ),
    (
        "evolution-mensuelle",
        "Comment le nombre de marches publies evolue-t-il dans le temps ?",
        """
        select
            date_trunc('month', dateNotification) as mois,
            count(*)                              as marches
        from marches
        where dateNotification between date '2019-01-01' and date '2026-06-30'
        group by 1
        order by 1
        """,
    ),
    (
        "distance-titulaires",
        "Les acheteurs travaillent-ils avec des entreprises proches ?",
        """
        select
            case
                when titulaire_distance < 10  then '1. moins de 10 km'
                when titulaire_distance < 50  then '2. 10 a 50 km'
                when titulaire_distance < 150 then '3. 50 a 150 km'
                when titulaire_distance < 500 then '4. 150 a 500 km'
                else                               '5. plus de 500 km'
            end      as tranche,
            count(*) as marches
        from marches
        where titulaire_distance is not null
        group by 1
        order by 1
        """,
    ),
    (
        "offre-unique-par-tranche",
        "La concurrence depend-elle du montant du marche ?",
        """
        select
            case
                when montant < 25000    then '1. moins de 25 k'
                when montant < 90000    then '2. 25 a 90 k'
                when montant < 214000   then '3. 90 a 214 k'
                when montant < 1000000  then '4. 214 k a 1 M'
                when montant < 10000000 then '5. 1 a 10 M'
                else                         '6. plus de 10 M'
            end                                    as tranche,
            count(*)                               as marches,
            round(
                100.0 * sum(case when offresRecues = 1 then 1 else 0 end) / count(*), 1
            )                                      as part_offre_unique,
            round(median(offresRecues), 1)         as mediane_offres
        from marches
        where montant > 0 and offresRecues is not null and montant_anomalie is null
        group by 1
        order by 1
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
