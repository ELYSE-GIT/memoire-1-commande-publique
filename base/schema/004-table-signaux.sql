-- Les signaux de detection, un par ligne de marche.
--
-- Table separee de `marches`, et ce n'est pas une question de normalisation : les deux ont des
-- **cycles de vie differents**. Les faits d'un marche ne changent plus une fois publies ; les
-- signaux, eux, sont recalcules chaque fois qu'un seuil bouge ou qu'une regle est ajoutee.
-- Pouvoir vider et reconstruire les signaux sans toucher aux faits evite de republier deux
-- millions de lignes pour un changement de seuil.
--
-- Aucune contrainte de cle etrangere vers `marches` : `marche_id` n'y est pas unique, donc une
-- cle etrangere est impossible. C'est mesure dans `003-table-marches.sql`.
--
-- Le detail des regles et de leurs seuils est dans l'ADR 0006, et leur comparaison a dix
-- methodes de detection dans l'ADR 0007.

create table if not exists signaux (

    id                          bigint generated always as identity primary key,
    marche_id                   text not null,

    -- === Le groupe de comparaison ============================================
    -- Un marche ne se juge pas dans l'absolu mais par rapport a ses pairs. Ces colonnes disent
    -- a quoi il a ete compare, pour que l'affichage puisse l'expliquer a l'utilisateur.
    famille_cpv                 text,
    marches_dans_la_famille     integer,
    mediane_log_famille         double precision,
    ecart_log_famille           double precision,
    -- L'ecart normalise robuste : (montant moins la mediane du groupe) divise par l'ecart
    -- interquartile. C'est le score qui porte le signal de prix.
    ecart_normalise_famille     double precision,

    -- === La concentration ====================================================
    marches_de_l_acheteur       integer,
    titulaires_de_l_acheteur    integer,
    part_du_titulaire           double precision,
    marches_ensemble            integer,
    diversite_acheteur          double precision,

    -- === Les signaux, un booleen par regle ===================================
    prix_tres_eleve                 boolean not null default false,
    prix_eleve_a_verifier           boolean not null default false,
    -- Ce signal existe mais **aucune etiquette ne permet de l'evaluer** : zero concordance sur
    -- 18 208 marches. Il doit etre affiche avec la mention « non evalue », ou pas du tout.
    -- « Non valide » n'est pas « invalide », et supprimer ce signal aurait ecarte un cas reel :
    -- un marche de travaux a un euro merite un regard.
    prix_tres_bas_non_evalue        boolean not null default false,
    offre_unique_sur_gros_marche    boolean not null default false,
    titulaire_dominant              boolean not null default false,

    -- Nombre de signaux portes par la ligne, pour trier les marches a examiner en priorite.
    signaux_forts               smallint not null default 0,

    -- Les motifs en clair, affichables tels quels a l'ecran. Un signalement doit porter sa
    -- raison : « le modele l'a decide » n'est pas une reponse acceptable devant un acheteur.
    motifs_de_signalement       text[]
);

comment on table signaux is
    'Resultat des regles de detection. Reconstruit a chaque changement de seuil, sans toucher aux faits.';
comment on column signaux.prix_tres_bas_non_evalue is
    'Signal expose mais NON EVALUE : aucune etiquette disponible ne le confirme ni ne l''infirme.';
