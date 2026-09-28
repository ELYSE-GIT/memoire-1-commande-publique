-- Couche or : la table que le site et les analyses interrogent.
--
-- Difference de nature avec la couche argent, et c'est tout l'interet d'avoir deux couches :
--
--   argent  garde tout, marque les problemes. Sert a expliquer, a auditer, a corriger.
--   or      ne garde que ce qui est exploitable, et le dit clairement. Sert a repondre.
--
-- Le filtre applique ici n'est donc pas une perte d'information : la ligne ecartee existe
-- toujours en argent, avec le motif de son exclusion. Ce qui disparait ici se retrouve en une
-- requete.
--
-- Les colonnes sont choisies, pas heritees : une table de service expose ce dont on a besoin,
-- pas les 76 colonnes de la source. Un site qui lit 76 colonnes pour en afficher 12 paie la
-- lecture des 64 autres a chaque requete.

{{ config(materialized='table') }}

select
    -- Identification
    uid                                                as marche_id,
    id                                                 as reference_acheteur,

    -- L'acheteur
    acheteur_id                                        as acheteur_siret,
    acheteur_nom,
    acheteur_categorie,
    acheteur_departement_code,
    acheteur_departement_nom,
    acheteur_region_nom,
    acheteur_commune_nom,
    acheteur_latitude,
    acheteur_longitude,

    -- Le titulaire
    titulaire_id                                       as titulaire_siret,
    titulaire_nom,
    titulaire_categorie,
    titulaire_distance                                 as distance_km,

    -- Le marche
    objet,
    nature_normalisee                                  as nature,
    famille_cpv,
    codeCPV                                            as code_cpv,
    procedure,
    montant,
    -- Le logarithme est calcule ici plutot qu'a chaque interrogation : la distribution des
    -- montants est log-normale (mesure en phase 2), donc toute comparaison de prix se fera sur
    -- cette echelle. La calculer une fois evite de la recalculer des millions de fois.
    log10(montant)                                     as montant_log10,
    dureeMois                                          as duree_mois,
    offresRecues                                       as offres_recues,
    -- Indicateur de risque le plus utilise dans la litterature. Il vaut null, et non false,
    -- quand l'information manque : confondre « pas d'offre unique » et « on ne sait pas »
    -- fausserait toute statistique. L'information manque dans 56 % des marches.
    case when offresRecues is not null then offresRecues = 1 end as offre_unique,

    -- Le temps
    dateNotification                                   as date_notification,
    year(dateNotification)                             as annee,
    month(dateNotification)                            as mois,

    -- La provenance, conservee jusqu'ici : elle permet de rattacher une anomalie a la plateforme
    -- qui l'a publiee, et donc de la signaler a qui peut la corriger.
    sourceDataset                                      as source

from {{ ref('argent_marches') }}
where exploitable_pour_les_prix
