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

-- === Les filtres de l'assistant ==============================================
--
-- Ajoutes le 21 octobre 2026, apres une mesure embarrassante : l'assistant repondait a « combien
-- de marches en 2023 » en 54 secondes. Cause immediate, lisible dans le plan d'execution, un
-- balayage parallele des deux millions de lignes, sur une base froide. La meme requete a chaud
-- prenait encore 3 079 ms : le disque aggravait le probleme, il ne le creait pas.
--
-- Cause de fond, plus interessante : **l'assistant ne filtre pas sur les memes colonnes que la
-- recherche**. La recherche part du texte, donc de l'index GIN, et tout le reste n'est qu'un
-- affinage sur un petit nombre de lignes deja trouvees. Une question comme « combien de marches
-- en 2023 » n'a pas de texte du tout : elle demande une agregation sur une grosse tranche de la
-- table, ce qui est un autre metier. Les index suivent les requetes, et les requetes avaient
-- change sans que les index bougent.
--
-- === L'annee : un index BRIN et non un B-tree ================================
--
-- `pg_stats` donne une correlation de **-0,96** entre l'ordre physique des lignes et l'annee :
-- la table a ete chargee par date decroissante, donc les marches d'une meme annee sont
-- physiquement voisins. C'est la condition exacte ou un index BRIN, qui ne retient qu'un
-- intervalle de valeurs par groupe de pages, devient imbattable.
--
--     Option              Taille    « combien en 2023 », a chaud    Verdict
--     aucun index           0        3 079 ms (balayage parallele)   le point de depart
--     B-tree sur annee     13 Mo     non retenu : voir ci-dessous    ecarte
--     **BRIN sur annee**   **56 ko**  **156 ms**                     **retenu**
--
-- Le B-tree fonctionne aussi, mais il occupe 230 fois plus d'espace pour un gain comparable :
-- avec seulement douze annees distinctes, il ne discrimine pas plus finement que les intervalles
-- de pages du BRIN. Le choix se joue donc entierement sur la taille, ce qui compte sur un VPS.
--
-- A quelle echelle la reponse changerait : si les donnees etaient rechargees dans un ordre
-- quelconque, la correlation tomberait et le BRIN deviendrait inutile. C'est une dependance
-- reelle a la facon dont `services/publication/vers_postgres.py` ecrit les lignes, et elle est
-- verifiee par un test.
create index if not exists marches_annee_brin_idx on marches using brin (annee);

-- === Le lieu : des B-tree, parce que la correlation est nulle =================
--
-- Correlation mesuree : 0,10 pour la region, 0,03 pour le departement. Un BRIN n'y servirait a
-- rien, chaque groupe de pages contenant a peu pres toutes les regions.
--
--     Requete                              sans index     avec B-tree
--     compter une region                    10 220 ms         15,7 ms
--     compter une region et une annee        1 963 ms          295 ms
--     compter un departement                 non mesure         5,4 ms
--
-- Ces deux index coutent 27 Mo ensemble. Un index existait deja sur le **code** du departement
-- (`marches_departement_idx`), mais l'assistant recoit des **noms** : un utilisateur ecrit
-- « en Loire-Atlantique », jamais « dans le 44 ». Indexer le code ne sert donc que l'API.
create index if not exists marches_region_nom_idx on marches (acheteur_region_nom);
create index if not exists marches_departement_nom_idx on marches (acheteur_departement_nom);

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
    'marches_annee_brin_idx', 'marches_region_nom_idx', 'marches_departement_nom_idx',
    'marches_montant_idx', 'marches_acheteur_nom_trgm_idx',
    'marches_titulaire_nom_trgm_idx', 'signaux_marche_id_idx', 'signaux_a_examiner_idx'
)
order by pg_relation_size(oid) desc;
