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
)
insert into statistiques (
    ligne_unique, marches, marches_distincts, acheteurs, titulaires,
    montant_total, premiere_annee, derniere_annee, marches_signales,
    calcule_a
)
select
    true,
    compte.marches, compte.marches_distincts, compte.acheteurs, compte.titulaires,
    compte.montant_total, compte.premiere_annee, compte.derniere_annee,
    signales.marches_signales,
    clock_timestamp()
from compte, signales
on conflict (ligne_unique) do update set
    marches           = excluded.marches,
    marches_distincts = excluded.marches_distincts,
    acheteurs         = excluded.acheteurs,
    titulaires        = excluded.titulaires,
    montant_total     = excluded.montant_total,
    premiere_annee    = excluded.premiere_annee,
    derniere_annee    = excluded.derniere_annee,
    marches_signales  = excluded.marches_signales,
    calcule_a         = excluded.calcule_a;

-- Verification affichee, pour que celui qui lance la commande voie ce qui a ete ecrit.
select
    marches, marches_distincts, acheteurs, titulaires, marches_signales, calcule_a
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
