-- Les variables de detection : ce qui sert a reperer un marche atypique.
--
-- Une colonne est recue, une variable est fabriquee. Ce fichier ne lit que des colonnes deja
-- nettoyees et en tire des grandeurs comparables entre marches qui ne le sont pas en euros.
--
-- Le principe qui guide toutes ces variables : **un marche ne se juge pas dans l'absolu, mais par
-- rapport a ses pairs**. Un marche de voirie a 500 000 euros n'est ni cher ni bon marche ; il
-- l'est par rapport aux autres marches de voirie, du meme type d'acheteur, de la meme annee.
--
-- Trois groupes de comparaison sont construits ici :
--   par famille d'achat   pour juger un prix
--   par acheteur          pour juger une habitude d'attribution
--   par couple acheteur et titulaire   pour juger une relation
--
-- Sur la fuite de donnees : les medianes sont calculees sur l'ensemble des marches, y compris
-- celui que l'on examine. Sur une famille de mille marches, l'effet est negligeable ; sur une
-- famille de trois, il ne l'est pas. La colonne `marches_dans_la_famille` permet de le mesurer
-- plutot que de le supposer, et la detection ecartera les groupes trop petits.

{{ config(materialized='table') }}

with marches as (

    select * from {{ ref('or_marches') }}

),

-- Groupe de comparaison n°1 : la famille d'achat.
-- Les statistiques portent sur le logarithme du montant, parce que la distribution est
-- log-normale (mesure en phase 2). Comparer des montants bruts donnerait un poids demesure aux
-- gros marches et rendrait tout petit marche « normal » par construction.
statistiques_famille as (

    select
        famille_cpv,
        count(*)                                     as marches_dans_la_famille,
        median(montant_log10)                        as mediane_log_famille,
        quantile_cont(montant_log10, 0.25)           as q1_log_famille,
        quantile_cont(montant_log10, 0.75)           as q3_log_famille
    from marches
    where famille_cpv is not null
    group by 1

),

-- Groupe de comparaison n°2 : l'acheteur.
statistiques_acheteur as (

    select
        acheteur_siret,
        count(*)                                     as marches_de_l_acheteur,
        count(distinct titulaire_siret)              as titulaires_de_l_acheteur,
        median(montant)                              as montant_median_acheteur
    from marches
    group by 1

),

-- Groupe de comparaison n°3 : la relation entre un acheteur et un titulaire.
statistiques_relation as (

    select
        acheteur_siret,
        titulaire_siret,
        count(*)                                     as marches_ensemble,
        sum(montant)                                 as montant_ensemble
    from marches
    where titulaire_siret is not null
    group by 1, 2

)

select
    m.marche_id,
    m.acheteur_siret,
    m.titulaire_siret,
    m.famille_cpv,
    m.annee,
    m.mois,
    m.montant,
    m.montant_log10,

    -- === Variables de prix ===============================================

    f.marches_dans_la_famille,
    round(f.mediane_log_famille, 4)                  as mediane_log_famille,

    -- Ecart brut au centre de la famille, en ordres de grandeur. Une valeur de 1 signifie
    -- « dix fois plus cher que la mediane de sa famille ».
    round(m.montant_log10 - f.mediane_log_famille, 4) as ecart_log_famille,

    -- Ecart normalise, version robuste. On divise par l'ecart interquartile plutot que par
    -- l'ecart type : sur des donnees ou une ligne sur trente porte un montant fantaisiste,
    -- l'ecart type est lui-meme fausse par ces valeurs, et le score qu'il produit ne veut
    -- plus rien dire.
    --
    -- Le facteur 1,349 convertit un ecart interquartile en equivalent d'ecart type pour une
    -- distribution normale. Il rend le score comparable a un score z classique, ce qui permet
    -- d'utiliser les reperes habituels : au-dela de 3, l'observation est rare.
    case
        when f.q3_log_famille - f.q1_log_famille > 0
            then round(
                (m.montant_log10 - f.mediane_log_famille)
                / ((f.q3_log_famille - f.q1_log_famille) / 1.349),
                4
            )
    end                                              as ecart_normalise_famille,

    -- === Variables de concurrence ========================================

    m.offres_recues,
    m.offre_unique,

    -- === Variables de concentration ======================================

    a.marches_de_l_acheteur,
    a.titulaires_de_l_acheteur,

    -- Part des marches de cet acheteur qui vont a ce titulaire. C'est l'indicateur de repli
    -- identifie en phase 2 : contrairement au nombre d'offres, il est calculable sur 100 % des
    -- marches, puisqu'il ne demande que l'identite des parties.
    round(r.marches_ensemble * 1.0 / a.marches_de_l_acheteur, 4) as part_du_titulaire,
    r.marches_ensemble,

    -- Un acheteur qui ne travaille qu'avec une poignee d'entreprises n'est pas suspect en soi :
    -- une petite commune a peu de fournisseurs. La variable brute est donc exposee, et son
    -- interpretation reste a la charge de l'analyse, jamais du calcul.
    round(a.titulaires_de_l_acheteur * 1.0 / a.marches_de_l_acheteur, 4) as diversite_acheteur,

    -- === Variables de calendrier =========================================

    -- Decembre et juillet sont les pics de notification, mesure en phase 2. Un marche notifie en
    -- decembre n'a rien d'anormal ; c'est un marche **inhabituel pour son acheteur** qui merite
    -- un regard, et cela se juge par rapport au mois, pas dans l'absolu.
    m.mois = 12                                      as notifie_en_decembre,
    m.mois in (7, 12)                                as notifie_en_pic,

    -- === Variables de territoire =========================================

    m.distance_km,
    m.distance_km <= 50                              as titulaire_local,

    -- === Variables de contrat ============================================

    m.duree_mois,
    -- Montant rapporte a la duree : deux marches de meme montant n'engagent pas la meme depense
    -- annuelle si l'un dure six mois et l'autre dix ans.
    case
        when m.duree_mois > 0 then round(m.montant / m.duree_mois, 2)
    end                                              as montant_par_mois

from marches m
left join statistiques_famille  f on f.famille_cpv = m.famille_cpv
left join statistiques_acheteur a on a.acheteur_siret = m.acheteur_siret
left join statistiques_relation r
    on r.acheteur_siret = m.acheteur_siret
   and r.titulaire_siret = m.titulaire_siret
