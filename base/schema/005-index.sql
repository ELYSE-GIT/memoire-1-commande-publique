-- Les index, appliques **apres** le chargement.
--
-- Pourquoi apres et pas avant : construire un index pendant une insertion de deux millions de
-- lignes oblige PostgreSQL a le reequilibrer a chaque ligne. Charger d'abord, indexer ensuite,
-- c'est le meme resultat en une fraction du temps. La difference est mesuree par
-- `make bench-recherche`, qui affiche la duree de chaque etape.
--
-- Chaque index coute : de l'espace disque, du temps a chaque ecriture, et de la memoire pour
-- rester efficace. Aucun n'est cree « au cas ou ». Chacun porte ici la question a laquelle il
-- repond, et `make bench-recherche` mesure sa taille reelle.

-- === La recherche plein texte =================================================
--
-- Question servie : « travaux de voirie en Ille-et-Vilaine en 2024 ».
--
--     Option envisagee   Avantage                        Limite                      Verdict
--     aucun index        rien a maintenir                parcours complet de deux    exclu
--                                                        millions de lignes
--     **GIN**            tres rapide a la lecture, fait  plus lent a construire et   **retenu**
--                        pour les listes de mots         a mettre a jour qu'un GiST
--     GiST               plus compact, ecritures plus    lectures plus lentes, et    ecarte
--                        rapides                         resultats approximatifs
--
-- Le projet ecrit par lots, une fois par collecte, et lit en permanence. Le compromis de GIN est
-- donc exactement le bon. `fastupdate = off` : la liste d'attente de GIN accelere les ecritures
-- mais ralentit les lectures de facon imprevisible, ce qui rendrait les latences mesurees
-- instables.
create index if not exists marches_recherche_idx
    on marches using gin (recherche) with (fastupdate = off);

-- === Les recherches par identifiant ==========================================
-- Question servie : « montre-moi le marche numero X », et le rapprochement avec le BOAMP.
create index if not exists marches_marche_id_idx on marches (marche_id);

-- Questions servies : « tous les marches de cette mairie », « tous les marches de cette
-- entreprise ». Ce sont les deux pages les plus probables du site apres la recherche.
create index if not exists marches_acheteur_siret_idx  on marches (acheteur_siret);
create index if not exists marches_titulaire_siret_idx on marches (titulaire_siret);

-- === Les filtres structures ==================================================
-- Beaucoup de questions reelles ne sont pas semantiques mais factuelles : un departement, une
-- annee, une famille d'achat, une tranche de montant. Les mesurer avant d'ajouter des vecteurs
-- est tout l'objet de la phase 6.
create index if not exists marches_date_idx       on marches (date_notification desc);
create index if not exists marches_famille_idx    on marches (famille_cpv);
create index if not exists marches_departement_idx on marches (acheteur_departement_code);
create index if not exists marches_montant_idx    on marches (montant desc);

-- === La tolerance aux fautes de frappe =======================================
--
-- Question servie : « mairie de Rene » pour « mairie de Rennes », ou un nom d'entreprise tape
-- de memoire. L'index plein texte ne rattrape pas une faute : il cherche des racines exactes.
--
-- Index par groupes de trois caracteres, sur les noms seulement. Pas sur l'objet du marche :
-- ce serait un index enorme pour un gain que rien ne justifie encore.
create index if not exists marches_acheteur_nom_trgm_idx
    on marches using gin (acheteur_nom gin_trgm_ops);
create index if not exists marches_titulaire_nom_trgm_idx
    on marches using gin (titulaire_nom gin_trgm_ops);

-- === Les signaux =============================================================
create index if not exists signaux_marche_id_idx on signaux (marche_id);

-- Index **partiel** : seules 2,87 % des lignes portent un signal. Un index sur la colonne
-- entiere occuperait quarante fois plus d'espace pour repondre a la meme question, « quels
-- marches faut-il examiner ». La clause `where` est ce qui fait la difference.
create index if not exists signaux_a_examiner_idx
    on signaux (signaux_forts desc)
    where signaux_forts > 0;

-- === Verification ============================================================
-- Les statistiques du planificateur sont recalculees : sans cela, PostgreSQL continue de
-- raisonner sur une table qu'il croit vide et choisit des plans absurdes.
analyze marches;
analyze signaux;

select
    relname as table_ou_index,
    pg_size_pretty(pg_relation_size(oid)) as taille
from pg_class
where relname in (
    'marches', 'signaux',
    'marches_recherche_idx', 'marches_marche_id_idx',
    'marches_acheteur_siret_idx', 'marches_titulaire_siret_idx',
    'marches_date_idx', 'marches_famille_idx', 'marches_departement_idx',
    'marches_montant_idx', 'marches_acheteur_nom_trgm_idx',
    'marches_titulaire_nom_trgm_idx', 'signaux_marche_id_idx', 'signaux_a_examiner_idx'
)
order by pg_relation_size(oid) desc;
