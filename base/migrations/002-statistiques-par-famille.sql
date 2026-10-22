-- Migration 002 : la table des agregats par famille d'achat.
--
-- Meme raison que la migration 001 : `base/schema/008-table-statistiques.sql` cree ses tables
-- en `create table if not exists`, donc le relancer sur une base chargee n'ajoute rien si la
-- table existe deja, mais il ne la cree pas non plus si l'on ne relance pas le fichier. Ce
-- fichier-ci est relancable sans effet et se contente de garantir que la table existe.
--
-- A lancer par `make migrer`, puis `make indexer` pour la remplir.
--
-- Ce que la table contient et pourquoi elle existe : voir l'en-tete de sa declaration dans
-- `base/schema/008-table-statistiques.sql`. En resume, les quartiles par famille coutent
-- 9,4 secondes a calculer et 1 milliseconde a lire, et ils sont ce qui permet d'afficher
-- « ce marche coute 5 460 fois la mediane de sa famille » plutot que « ecart normalise 6,53 ».

create table if not exists statistiques_familles (
    famille_cpv                 text primary key,
    marches                     bigint not null,
    montant_total               numeric(20, 2),
    marches_avec_montant        bigint not null,
    montant_q1                  numeric(18, 2),
    montant_median              numeric(18, 2),
    montant_q3                  numeric(18, 2),
    attributions_resolues       bigint not null,
    attributions_pme            bigint not null,
    part_pme_pourcent           double precision,
    marches_signales            bigint not null default 0
);

select
    case
        when not exists (select 1 from statistiques_familles)
            then 'table prete, vide : lancer `make indexer` pour la remplir'
        else 'table deja remplie'
    end as etat;
