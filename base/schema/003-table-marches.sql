-- La table servie : un marche attribue, tel que le site l'affichera.
--
-- Elle reproduit la couche or du projet dbt (`or_marches`), parce que c'est cette couche qui
-- porte la promesse « exploitable ». Aucun nettoyage n'est refait ici : si une valeur est
-- fausse, le defaut se corrige dans le modele dbt, pas dans la base de service. Deux endroits
-- qui nettoient, c'est deux verites qui divergent.
--
-- === Pourquoi une cle technique et non le numero de marche =====================
--
-- Mesure du 11 octobre 2026, sur 1 999 474 lignes de la couche or :
--
--     marche_id distincts                      1 738 289
--     couples (marche_id, titulaire_siret)     1 992 358
--     lignes strictement identiques            136
--
-- Donc **aucune colonne, ni aucune combinaison de colonnes, n'identifie une ligne**. Le numero
-- de marche designe un marche, qui a autant de lignes que de titulaires dans un groupement ; et
-- meme le couple avec le titulaire se repete, quand un marche fait l'objet de plusieurs
-- notifications ou corrections.
--
--     Option envisagee            Avantage                   Limite                     Verdict
--     marche_id en cle primaire   la cle a un sens metier    **impossible** : 261 185    exclu
--                                                            lignes la partagent         par les
--                                                                                        donnees
--     couple marche_id et         plus proche du metier      impossible aussi :          exclu
--     titulaire                                              7 116 lignes en double
--     deduire une cle en          une cle stable d'une       une collision silencieuse   ecarte
--     hachant toutes les          collecte a l'autre         sur les 136 lignes
--     colonnes                                               identiques
--     **cle technique            toujours unique, pas de     ne veut rien dire pour un   **retenu**
--     croissante**               supposition a verifier      humain, donc `marche_id`
--                                                            reste expose et indexe
--
-- Consequence a enoncer dans le memoire : les donnees publiques de la commande publique ne
-- fournissent pas d'identifiant de ligne. C'est un fait sur la donnee, pas un choix technique,
-- et c'est pour cette raison qu'aucune contrainte de cle etrangere n'est posee vers cette table.

create table if not exists marches (

    -- Cle technique. `generated always` empeche de l'ecrire a la main, donc d'introduire un
    -- doublon par erreur lors d'un chargement.
    id                          bigint generated always as identity primary key,

    -- === Identification ======================================================
    -- Non unique, et c'est mesure plus haut. Indexe quand meme : c'est par ce numero qu'un
    -- utilisateur ou une source externe designera un marche.
    marche_id                   text not null,
    reference_acheteur          text,

    -- === L'acheteur ==========================================================
    acheteur_siret              text,
    acheteur_nom                text,
    acheteur_categorie          text,
    acheteur_departement_code   text,
    acheteur_departement_nom    text,
    acheteur_region_nom         text,
    acheteur_commune_nom        text,
    -- Coordonnees du siege de l'acheteur, pour la carte et pour la distance au titulaire.
    -- `double precision` et non `numeric` : ce sont des mesures, pas des montants, et la
    -- precision decimale exacte n'a aucun interet ici.
    acheteur_latitude           double precision,
    acheteur_longitude          double precision,

    -- === Le titulaire ========================================================
    titulaire_siret             text,
    titulaire_nom               text,
    titulaire_categorie         text,
    -- Distance a vol d'oiseau entre acheteur et titulaire. `smallint` suffit : la plus grande
    -- distance possible entre deux points francais tient largement sous 32 767 km.
    distance_km                 smallint,

    -- === L'objet du marche ===================================================
    objet                       text,
    nature                      text,
    famille_cpv                 text,
    code_cpv                    text,
    procedure                   text,

    -- === Les montants ========================================================
    -- `numeric` et non `double precision` : c'est de l'argent. Un flottant binaire ne peut pas
    -- representer exactement 0,01 euro, et les erreurs s'accumulent sur une somme de deux
    -- millions de lignes. Le mode de stockage est un choix, pas un detail.
    montant                     numeric(18, 2),
    -- Le logarithme, lui, est une mesure : flottant.
    montant_log10               double precision,
    duree_mois                  smallint,
    offres_recues               smallint,
    offre_unique                boolean,

    -- === Le calendrier =======================================================
    date_notification           date,
    annee                       smallint,
    mois                        smallint,

    -- === La provenance =======================================================
    -- Quelle source a publie cette ligne. Garde pour la tracabilite : un chiffre du memoire doit
    -- pouvoir etre remonte jusqu'a son producteur.
    source                      text,

    -- === La colonne de recherche =============================================
    --
    -- Colonne **generee** : PostgreSQL la recalcule lui-meme a chaque ecriture. Elle ne peut
    -- donc jamais etre en retard sur le texte, contrairement a une colonne remplie par un
    -- declencheur ou par un script, qu'on oublie de relancer.
    --
    -- Trois champs y entrent, et le choix se defend : l'objet du marche, le nom de l'acheteur et
    -- le nom du titulaire. Une question reelle melange les trois (« qui fournit des logiciels a
    -- la mairie de Rennes »), et les separer obligerait l'utilisateur a savoir dans quelle case
    -- taper quoi.
    --
    -- Les poids `A` et `B` servent au classement : un mot trouve dans l'objet compte plus qu'un
    -- mot trouve dans un nom d'entreprise. Sans eux, une societe appelee « Toiture et Voirie »
    -- sortirait devant les marches de toiture.
    --
    -- La configuration est nommee en entier (`public.francais`), parce qu'une colonne generee
    -- doit etre deterministe : avec un nom court, sa valeur dependrait du `search_path`.
    recherche tsvector generated always as (
        setweight(to_tsvector('public.francais', coalesce(objet, '')), 'A')
        || setweight(to_tsvector('public.francais', coalesce(acheteur_nom, '')), 'B')
        || setweight(to_tsvector('public.francais', coalesce(titulaire_nom, '')), 'B')
    ) stored
);

comment on table marches is
    'Marches attribues, couche servie. Copie fidele de or_marches : aucun nettoyage ici.';
comment on column marches.id is
    'Cle technique. Les donnees publiques ne fournissent aucun identifiant de ligne unique.';
comment on column marches.marche_id is
    'Numero du marche. NON UNIQUE : un marche a autant de lignes que de titulaires.';
comment on column marches.recherche is
    'Index plein texte francais, accents retires. Objet en poids A, noms en poids B.';
