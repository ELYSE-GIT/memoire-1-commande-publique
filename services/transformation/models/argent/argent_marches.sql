-- Couche argent : la donnee nettoyee, normalisee, et **marquee** quand elle pose probleme.
--
-- Regle tenue dans tout ce fichier : on ne supprime aucune ligne et on n'ecrase aucune valeur
-- d'origine. Chaque probleme detecte ajoute une colonne qui le dit. Une ligne supprimee ne peut
-- plus etre expliquee a un jury, ni corrigee par l'administration qui l'a publiee.
--
-- Perimetre : l'etat actuel de chaque marche (`donneesActuelles`), soit 2,11 millions de lignes
-- pour 1,83 million de marches. L'historique des avenants est conserve en bronze, et fera l'objet
-- d'une table distincte quand l'analyse des modifications sera au programme.
--
-- Les seuils utilises ne sont pas ronds par hasard : ils viennent du code de la commande publique
-- (seuils de procedure) ou de mesures faites en phase 2 (voir docs/journal/2026-09-20-phase-2.md).

{{ config(materialized='table') }}

with source as (

    select *
    from {{ ref('bronze_decp') }}
    where donneesActuelles

),

normalisation as (

    select
        *,

        -- Normalisation de la nature du marche. Mesure en phase 2 : le meme concept s'ecrit de
        -- douze facons selon la source (« Marche », « MARCHE », « MARCHE » accentue...), parce que
        -- le jeu agrege 63 sources ayant chacune ses habitudes de saisie.
        --
        -- Deux fonctions suffisent : majuscules et retrait des accents. Aucun modele, aucun
        -- rapprochement flou : c'est le premier barreau de l'escalier, et il resout l'essentiel.
        -- Reste le cas « ACCORD-CADRE » contre « ACCORD CADRE », que la ponctuation separe : on
        -- normalise donc aussi les tirets et les espaces multiples.
        nullif(
            regexp_replace(
                regexp_replace(strip_accents(upper(trim(nature))), '[-_/]', ' ', 'g'),
                '\s+', ' ', 'g'
            ),
            ''
        ) as nature_normalisee,

        -- Le code CPV designe la nature de l'achat. Ses deux premiers chiffres donnent la
        -- division, seul niveau assez stable pour comparer des marches entre eux.
        --
        -- Mesure : 244 lignes portent du texte libre a la place d'un code (« Travaux »,
        -- « lot 2000 », « X0000000 »). Un acheteur a rempli un champ de nomenclature a la main.
        -- On ne deduit donc une famille que d'un code commencant reellement par deux chiffres,
        -- et le reste est marque plus bas.
        case
            when regexp_matches(coalesce(trim(codeCPV), ''), '^[0-9]{2}')
                then substr(trim(codeCPV), 1, 2)
        end as famille_cpv

    from source

),

validation as (

    select
        *,

        -- Regle 1 : le montant doit etre renseigne et strictement positif.
        -- Mesure : 48 596 lignes sans montant, 59 588 a zero ou negatives, dont une a
        -- moins 2 676 107 euros. Un montant negatif n'a pas de sens pour un marche attribue.
        montant is not null and montant > 0 as montant_renseigne,

        -- Regle 2 : le montant doit rester plausible.
        -- Le plafond d'un milliard n'est pas arbitraire : le plus gros marche public francais reel
        -- se compte en centaines de millions. Au-dessus, on observe surtout des valeurs de
        -- remplissage, dont le maximum releve : 99 999 999 999,99 euros, soit des neuf saisis pour
        -- pouvoir valider un formulaire.
        coalesce(montant <= 1000000000, false) as montant_plausible,

        -- Regle 3 : le producteur signale lui-meme les montants douteux. On s'appuie sur son
        -- travail plutot que de le refaire, et on comparera notre propre detection a la sienne
        -- en phase 5.
        montant_anomalie is null as montant_sans_anomalie_signalee,

        -- Regle 4 : la date de notification doit exister et etre plausible.
        -- Mesure : 31 812 lignes sans date, et une date minimale au 1er janvier de l'an 1, valeur
        -- par defaut d'un champ mal rempli. La borne basse est fixee a 2015, anterieure a
        -- l'obligation de publication de 2018, donc large.
        dateNotification is not null
            and dateNotification >= date '2015-01-01'
            and dateNotification <= current_date as date_plausible,

        -- Regle 5 : la duree doit rester dans le domaine du possible.
        -- Mesure : 6 042 marches depassent dix ans et le maximum atteint 32 000 mois, soit plus de
        -- 2 600 ans. Le plafond de 240 mois, vingt ans, laisse passer les concessions longues,
        -- qui sont les contrats les plus durables de la commande publique.
        dureeMois is null or (dureeMois > 0 and dureeMois <= 240) as duree_plausible,

        -- Regle 6 : l'identifiant de l'acheteur doit etre un SIRET, c'est-a-dire quatorze chiffres.
        -- C'est la cle qui relie un marche au repertoire des entreprises et, a terme, au BOAMP.
        regexp_matches(coalesce(acheteur_id, ''), '^\d{14}$') as acheteur_siret_valide,

        -- Regle 7 : meme controle pour le titulaire. Mesure : certaines lignes portent « 00001 »
        -- en guise d'identifiant.
        titulaire_id is null
            or regexp_matches(titulaire_id, '^\d{14}$') as titulaire_siret_valide,

        -- Regle 8 bis : le code CPV, quand il existe, doit etre une suite de chiffres.
        -- La nomenclature europeenne compte huit chiffres, parfois suivis d'un tiret et d'une
        -- cle de controle. Tout le reste est une saisie libre dans un champ qui ne l'admet pas.
        codeCPV is null
            or regexp_matches(trim(codeCPV), '^[0-9]{8}') as cpv_conforme,

        -- Regle 8 : le nombre d'offres recues, quand il est renseigne, doit rester credible.
        -- Mesure : le maximum observe est de 20 300 offres pour un seul marche. Le plafond de 500
        -- est genereux : les marches les plus concurrentiels en recoivent quelques dizaines.
        offresRecues is null or (offresRecues > 0 and offresRecues <= 500) as offres_plausibles

    from normalisation

)

select
    *,

    -- La liste des regles enfreintes, en clair. Elle sert a expliquer une exclusion a un
    -- utilisateur ou a un jury, sans avoir a relire le SQL.
    array_filter(
        [
            case when not montant_renseigne then 'montant absent ou negatif' end,
            case when not montant_plausible then 'montant superieur au milliard' end,
            case when not montant_sans_anomalie_signalee then 'montant signale par le producteur' end,
            case when not date_plausible then 'date de notification absente ou impossible' end,
            case when not duree_plausible then 'duree hors du domaine du possible' end,
            case when not acheteur_siret_valide then 'identifiant acheteur non conforme' end,
            case when not titulaire_siret_valide then 'identifiant titulaire non conforme' end,
            case when not offres_plausibles then 'nombre d''offres invraisemblable' end,
            case when not cpv_conforme then 'code CPV non conforme a la nomenclature' end
        ],
        x -> x is not null
    ) as motifs_rejet,

    -- Un marche est exploitable pour l'analyse des prix quand son montant, sa date et ses
    -- identifiants tiennent. Les autres regles n'empechent pas de l'utiliser pour autre chose :
    -- c'est pourquoi ce booleen est un resume, pas un filtre applique a la table.
    montant_renseigne
        and montant_plausible
        and montant_sans_anomalie_signalee
        and date_plausible
        and acheteur_siret_valide as exploitable_pour_les_prix

from validation
