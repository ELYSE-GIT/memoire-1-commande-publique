-- Remplit la table des comptages. A lancer APRES le chargement et APRES les index.
--
-- Apres le chargement, evidemment. Apres les index, parce que `count(*) from signaux where
-- signaux_forts > 0` passe par l'index partiel : 3 ms avec, un balayage complet sans.
--
-- Le remplissage est un `insert ... on conflict`, et non un `delete` suivi d'un `insert` : la
-- table ne doit jamais etre vide, meme une fraction de seconde. Un visiteur qui arrive pendant
-- un rechargement doit voir les anciens chiffres, pas une page d'accueil sans chiffres.

-- `clock_timestamp()` et non `now()` pour la date d'ecriture : `now()` renvoie l'heure du
-- debut de la transaction, qui precede le comptage de plusieurs secondes.
with compte as (
    select
        count(*)                            as marches,
        count(distinct marche_id)            as marches_distincts,
        count(distinct acheteur_siret)       as acheteurs,
        count(distinct titulaire_siret)      as titulaires,
        sum(montant)                         as montant_total,
        min(annee)                           as premiere_annee,
        max(annee)                           as derniere_annee
    from marches
),
signales as (
    select count(*) as marches_signales from signaux where signaux_forts > 0
),
-- Le montant sans le surcompte des groupements. 13 secondes de calcul sur les 1 999 474
-- lignes, soit impossible a la demande, et c'est pour cela qu'il est ecrit ici. Le pourquoi
-- de la regle est dans le fichier 008, a cote de la colonne.
sans_doublons as (
    select sum(montant) as montant_total_marches
    from (select distinct marche_id, montant from marches) as couples
)
insert into statistiques (
    ligne_unique, marches, marches_distincts, acheteurs, titulaires,
    montant_total, montant_total_marches, premiere_annee, derniere_annee, marches_signales,
    calcule_a
)
select
    true,
    compte.marches, compte.marches_distincts, compte.acheteurs, compte.titulaires,
    compte.montant_total, sans_doublons.montant_total_marches,
    compte.premiere_annee, compte.derniere_annee,
    signales.marches_signales,
    clock_timestamp()
from compte, signales, sans_doublons
on conflict (ligne_unique) do update set
    marches           = excluded.marches,
    marches_distincts = excluded.marches_distincts,
    acheteurs         = excluded.acheteurs,
    titulaires        = excluded.titulaires,
    montant_total     = excluded.montant_total,
    montant_total_marches = excluded.montant_total_marches,
    premiere_annee    = excluded.premiere_annee,
    derniere_annee    = excluded.derniere_annee,
    marches_signales  = excluded.marches_signales,
    calcule_a         = excluded.calcule_a;

-- Verification affichee, pour que celui qui lance la commande voie ce qui a ete ecrit.
select
    marches, marches_distincts, acheteurs, titulaires, marches_signales,
    round(montant_total / 1e9, 1)         as montant_milliards_lignes,
    round(montant_total_marches / 1e9, 1) as montant_milliards_marches,
    calcule_a
from statistiques;


-- La serie par annee. Reconstruite entierement : les annees ne disparaissent pas, mais leurs
-- chiffres changent a chaque collecte, et un `delete` suivi d'un `insert` dans la meme
-- transaction ne laisse jamais la table vide pour un lecteur.
begin;

delete from statistiques_annuelles;

insert into statistiques_annuelles (
    annee, attributions, montant_total,
    attributions_resolues, attributions_pme, part_pme_pourcent
)
select
    annee,
    count(*)                                                        as attributions,
    sum(montant)                                                    as montant_total,
    count(*) filter (where titulaire_categorie is not null)         as attributions_resolues,
    count(*) filter (where titulaire_categorie = 'PME')             as attributions_pme,
    -- `nullif` au denominateur : une annee dont aucun titulaire n'est resolu rend null, pas une
    -- division par zero. Null se lit « on ne sait pas » ; un zero se lirait « aucune PME ».
    100.0 * count(*) filter (where titulaire_categorie = 'PME')
          / nullif(count(*) filter (where titulaire_categorie is not null), 0)
                                                                    as part_pme_pourcent
from marches
where annee is not null
group by annee;

commit;

select annee, attributions, attributions_resolues, round(part_pme_pourcent::numeric, 1) as part_pme
from statistiques_annuelles
order by annee;


-- La table par famille d'achat. Reconstruite entierement, comme la serie annuelle : les familles
-- ne disparaissent pas, mais leurs quartiles bougent a chaque collecte.
--
-- La jointure avec `signaux` est a gauche : une famille sans aucun marche signale doit rester
-- dans la table avec un zero, et non disparaitre. C'est la difference entre « aucun signal » et
-- « famille inconnue », et la page d'accueil affiche les deux differemment.
begin;

delete from statistiques_familles;

insert into statistiques_familles (
    famille_cpv, marches, montant_total,
    marches_avec_montant, montant_q1, montant_median, montant_q3,
    attributions_resolues, attributions_pme, part_pme_pourcent,
    marches_signales
)
with comptes as (
    select
        famille_cpv,
        count(*)                                                    as marches,
        sum(montant)                                                as montant_total,
        count(montant)                                              as marches_avec_montant,
        -- `percentile_cont` interpole entre deux valeurs encadrantes, `percentile_disc` rendrait
        -- une valeur reellement presente. L'interpolation est le bon choix ici : c'est la meme
        -- definition que celle utilisee par la detection, donc les deux chiffres se comparent.
        percentile_cont(0.25) within group (order by montant)       as montant_q1,
        percentile_cont(0.50) within group (order by montant)       as montant_median,
        percentile_cont(0.75) within group (order by montant)       as montant_q3,
        count(*) filter (where titulaire_categorie is not null)     as attributions_resolues,
        count(*) filter (where titulaire_categorie = 'PME')         as attributions_pme,
        100.0 * count(*) filter (where titulaire_categorie = 'PME')
              / nullif(count(*) filter (where titulaire_categorie is not null), 0)
                                                                    as part_pme_pourcent
    from marches
    where famille_cpv is not null
    group by famille_cpv
),
signales as (
    select m.famille_cpv, count(*) as marches_signales
    from signaux as s
    join marches as m on m.marche_id = s.marche_id
    where s.signaux_forts > 0 and m.famille_cpv is not null
    group by m.famille_cpv
)
select
    comptes.famille_cpv, comptes.marches, comptes.montant_total,
    comptes.marches_avec_montant, comptes.montant_q1, comptes.montant_median, comptes.montant_q3,
    comptes.attributions_resolues, comptes.attributions_pme, comptes.part_pme_pourcent,
    coalesce(signales.marches_signales, 0)
from comptes
left join signales on signales.famille_cpv = comptes.famille_cpv;

commit;

select
    famille_cpv, marches,
    round(montant_median) as montant_median,
    round(part_pme_pourcent::numeric, 1) as part_pme,
    marches_signales
from statistiques_familles
order by marches desc
limit 10;
