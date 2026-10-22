-- Les comptages de la page d'accueil, calcules une fois et lus en permanence.
--
-- === Pourquoi une table et non une requete ===================================
--
-- Mesure du 22 octobre 2026, sur les 1 999 474 lignes chargees, chaque morceau isole :
--
--     count(*)                                              657 ms
--     trois count(distinct) ensemble                       9 092 ms
--     sum(montant), min et max de l'annee                    974 ms
--     count(*) des signaux, par l'index partiel                3 ms
--     ------------------------------------------------------------
--     total                                               10 726 ms
--
-- Et la meme requete, remesuree le meme jour juste apres un essai de charge : **41 719 ms**.
-- L'ecart n'est pas une erreur de mesure, c'est le fait principal : la duree depend de ce qui
-- reste en memoire partagee, donc de ce que le serveur a fait avant. Les deux valeurs sont
-- citees parce que n'en citer qu'une serait choisir celle qui arrange, et parce qu'elles
-- mettent d'accord sur la seule chose qui compte : la requete depasse, dans les deux cas, le
-- delai de dix secondes que l'API s'impose.
--
-- Soit dix secondes et sept dixiemes pour afficher quatre nombres sur une page d'accueil. Le
-- delai que l'API s'impose etant de dix secondes, la requete etait **abandonnee par la base**,
-- et la page d'accueil renvoyait une erreur 504. Le defaut a ete trouve par `make bench-api`,
-- pas par un test : aucun test ne mesure une duree.
--
-- Le cout est presque entierement dans les `count(distinct)` : PostgreSQL doit trier ou hacher
-- la colonne entiere pour savoir combien de valeurs differentes elle contient. Aucun index n'y
-- change rien, parce qu'il faut lire toutes les valeurs de toute facon.
--
--     Option envisagee          Avantage                   Limite                     Verdict
--     la requete a chaque       toujours a jour            10,7 s, donc abandonnee    exclu par
--     visite                                                par la base               la mesure
--     la requete, gardee en     payee une fois par heure   la premiere visite apres   ecarte
--     memoire dans le service                               chaque redemarrage attend
--                                                           dix secondes, et il y a
--                                                           autant de caches que de
--                                                           processus
--     estimer depuis            quelques microsecondes     `reltuples` est une        ecarte
--     `pg_class.reltuples`                                  estimation du planificateur,
--                                                           et ne sait rien des
--                                                           valeurs distinctes
--     **une table remplie au    lue en moins d'une         un etat de plus a          **retenu**
--     chargement**              milliseconde, et le        reconstruire au bon moment
--                               chiffre est exact
--     une vue materialisee      le meme resultat, gere     il faudrait quand meme
--                               par PostgreSQL             decider quand la rafraichir, ecarte
--                                                          et elle cache le cout dans
--                                                          un objet qu'on oublie
--
-- Ce qui a fait pencher : ces comptages ne changent **qu'au chargement**. Les calculer au
-- moment ou l'on charge, c'est payer dix secondes une fois par collecte au lieu de les faire
-- attendre a un visiteur. La vue materialisee donnerait le meme resultat, mais la table rend le
-- moment du calcul visible dans le Makefile, ce qui est le point du projet.
--
-- A quelle echelle la reponse changerait : si les donnees arrivaient en continu plutot que par
-- lots, il faudrait des compteurs tenus a l'ecriture, ou accepter un chiffre approche.
--
-- La table ne contient qu'une ligne. La contrainte le garantit : sans elle, un remplissage
-- lance deux fois en empilerait deux, et l'API lirait la premiere venue.

create table if not exists statistiques (

    -- Toujours vrai, donc toujours la meme valeur, donc une seule ligne possible.
    ligne_unique                boolean primary key default true
                                check (ligne_unique),

    marches                     bigint not null,
    marches_distincts           bigint not null,
    acheteurs                   bigint not null,
    titulaires                  bigint not null,
    -- Somme des montants portes par les lignes. ATTENTION : elle surcompte.
    montant_total               numeric(20, 2),

    -- Somme des montants en ne comptant qu'une fois chaque couple (marche, montant).
    --
    -- C'est le chiffre a afficher, et l'ecart avec le precedent est le resultat de mesure le
    -- plus genant de la journee du 22 octobre 2026 :
    --
    --     somme sur les lignes                     1 500,9 milliards d'euros
    --     somme par couple (marche, montant)       1 098,2 milliards d'euros
    --     ecart                                      402,7 milliards, soit 36,7 %
    --
    -- La raison : un marche attribue a un groupement d'entreprises occupe une ligne par
    -- titulaire, et le montant publie sur chacune de ces lignes est tres souvent celui du
    -- marche entier, repete, et non la part du titulaire. Additionner les lignes compte donc
    -- ce marche autant de fois qu'il a de titulaires. Le projet documentait deja ce piege
    -- pour les COMPTAGES (273 494 cas de groupements, voir memoire/02-etat-des-lieux.md) ;
    -- personne n'avait regarde ce qu'il faisait aux MONTANTS avant que le site n'ait a en
    -- afficher un.
    --
    -- Pourquoi `distinct (marche_id, montant)` et non une autre regle :
    --
    --     Option envisagee        Ce qu'elle donne   Cout     Limite               Verdict
    --     somme des lignes        1 500,9 Md         2 s      surcompte de 36,7 %  ecarte
    --     **distinct (marche,     1 098,2 Md         13 s     deux lots d'un meme  **retenu**
    --     montant)**                                          marche au meme
    --                                                          montant fusionnes
    --     max(montant) par        1 097,9 Md         25 s     ecrase les montants  ecarte
    --     marche                                               differents d'un
    --                                                          meme marche
    --                                                          (avenants, lots)
    --     part reelle de chaque   le vrai chiffre    --       la source ne publie  impossible
    --     titulaire                                            pas la repartition
    --
    -- Mesures du 22 octobre 2026 sur les 1 999 474 lignes chargees. Les deux regles
    -- defendables ne different que de 0,3 milliard sur 1 098, soit 0,03 pour cent : le choix
    -- entre elles ne change pas le chiffre affiche, alors que le choix de ne pas dedoublonner
    -- le change de 37 pour cent. C'est la seule decision qui compte ici.
    --
    -- Ce qui a fait pencher : la regle retenue ne suppose rien que la source ne dise. Sa limite
    -- est bornee et mesuree, et elle va dans le sens de la prudence. Le site affiche les deux
    -- chiffres et l'ecart, parce qu'un total d'argent public est exactement le genre de nombre
    -- qu'on reprend sans le verifier.
    montant_total_marches       numeric(20, 2),

    premiere_annee              smallint,
    derniere_annee              smallint,
    marches_signales            bigint not null default 0,

    -- Quand ces nombres ont ete calcules. Affiche par l'API : un comptage sans sa date est une
    -- affirmation dont on ne peut pas dire si elle est perimee.
    calcule_a                   timestamptz not null default now()
);

-- Une colonne `duree_calcul_ms` a existe ici pendant une heure, le 22 octobre 2026, et a ete
-- retiree : elle valait **zero**. La raison est instructive. Le remplissage demandait a la
-- requete de se chronometrer elle-meme, par la difference entre deux `clock_timestamp()` pris
-- dans deux parties de la meme instruction. PostgreSQL est libre d'evaluer ces parties dans
-- l'ordre qu'il veut, et les a evaluees cote a cote : la difference mesurait la duree du calcul
-- de la difference, pas celle du comptage.
--
-- La duree reelle, mesuree de l'exterieur le meme jour : 11,5 s pour le remplissage complet.
-- Une duree se mesure par celui qui attend, pas par celui qui travaille. Elle appartient donc
-- a `make bench-api` et a `\timing` de psql, et elle n'a rien a faire dans cette table.

comment on table statistiques is
    'Comptages de la page d''accueil. Une seule ligne. Remplie par 009-remplir-statistiques.sql.';
comment on column statistiques.marches is
    'Lignes chargees, soit un couple marche et titulaire. PAS le nombre de marches.';
comment on column statistiques.calcule_a is
    'Date du calcul. Un comptage sans sa date ne dit pas s''il est perime.';


-- La meme decision, pour la serie par annee.
--
-- Mesure du 22 octobre 2026, a travers l'API : 655 ms de mediane, 2 365 ms au 95e centile. La
-- requete groupe les 1 999 474 lignes par annee et calcule une part de PME au passage. C'est
-- moins grave que les dix secondes des comptages, mais c'est la courbe de la page d'accueil :
-- deux secondes avant le premier dessin, a chaque visite, pour douze nombres qui ne changent
-- qu'au chargement.
--
-- Le denominateur est stocke avec le pourcentage, et ce n'est pas un ornement. La part de PME
-- est calculee parmi les seules lignes dont le titulaire a ete resolu : au 21 octobre 2026,
-- 6,8 % des attributions n'ont aucune categorie d'entreprise. Publier le pourcentage sans son
-- denominateur laisserait croire qu'il porte sur tout, et transformerait une non-reponse en
-- non-PME.
--
-- L'unite de comptage est l'**attribution** et non le marche : un marche attribue a un
-- groupement compte une fois par titulaire. C'est l'unite qui a un sens pour une part de PME, et
-- elle est nommee dans le nom des colonnes.

create table if not exists statistiques_annuelles (

    annee                       smallint primary key,
    attributions                bigint not null,
    montant_total               numeric(20, 2),
    -- Lignes dont la categorie d'entreprise du titulaire est connue. C'est le denominateur de
    -- la part de PME, et il est publie avec elle.
    attributions_resolues       bigint not null,
    attributions_pme            bigint not null,
    part_pme_pourcent           double precision
);

comment on table statistiques_annuelles is
    'Serie par annee, calculee au chargement. Unite de comptage : l''attribution.';
comment on column statistiques_annuelles.part_pme_pourcent is
    'Part des attributions revenant a une PME, parmi les attributions_resolues seulement.';
