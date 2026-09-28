-- Les signaux de detection : les marches qui meritent un regard.
--
-- **Un signal n'est pas une accusation.** C'est une invitation a verifier, et le service le dira
-- a l'ecran. Un marche tres specialise attire peu de candidats sans que personne n'ait rien a se
-- reprocher, et un prix eleve peut tenir a une contrainte technique que la donnee ne porte pas.
--
-- Trois regles, aucune n'est un modele. C'est le premier barreau de l'escalier, et il ne sera
-- franchi que si la mesure prouve qu'il ne suffit pas.
--
-- Les seuils viennent d'une evaluation, pas d'une intuition. En utilisant comme etiquette faible
-- les anomalies que le producteur signale lui-meme, la regle de prix donne :
--
--     sens du signal   seuil   signales   precision   rappel
--     trop cher          3      33 600      55,1 %      34,0 %
--     trop cher          4       8 331      75,8 %      11,6 %
--     trop cher          5       3 535      92,6 %       6,0 %
--     trop bas           4      18 208       0,0 %       0,0 %
--
-- D'ou deux niveaux plutot qu'un seul seuil : un signal **fort** au-dela de 4, affichable en
-- confiance, et un signal **a verifier** entre 3 et 4, utile a un analyste mais pas a un visiteur.
--
-- Precaution de lecture, a redire dans le memoire : la precision mesuree est un **minorant**.
-- L'etiquette faible est elle-meme un detecteur, et un marche que nous signalons sans qu'il l'ait
-- signale peut etre une anomalie qu'il a manquee, pas une erreur de notre part.

{{ config(materialized='table') }}

with variables as (

    select * from {{ ref('or_variables') }}

),

signaux as (

    select
        *,

        -- === Signal 1 : prix atypique dans sa famille d'achat ==============
        --
        -- La condition sur la taille du groupe n'est pas un detail. Dans une famille de trois
        -- marches, la mediane est calculee sur le marche examine lui-meme : le comparer a elle
        -- revient a le comparer a lui-meme. Trente marches est le seuil retenu, et son effet
        -- sera mesure.
        -- **Les deux directions sont separees, et ce n'est pas un detail.** La premiere version
        -- de ce modele utilisait une valeur absolue, qui melangeait les montants trop eleves et
        -- les montants trop bas. L'evaluation a montre que les seconds ne concordent **jamais**
        -- avec les anomalies signalees par le producteur : 0 % sur 18 208 marches. La precision
        -- du signal tombait de 75,8 % a 23,8 % du seul fait de ce melange.
        --
        -- Cela ne veut pas dire qu'un montant anormalement bas soit normal : un marche de travaux
        -- a un euro est tout aussi suspect. Cela veut dire que **l'etiquette faible ne dit rien
        -- sur ce cas**, donc qu'on ne peut pas le valider. Il est expose a part, et signale comme
        -- non evalue.
        coalesce(
            marches_dans_la_famille >= 30 and ecart_normalise_famille > 4, false
        )                                            as prix_tres_eleve,

        coalesce(
            marches_dans_la_famille >= 30
            and ecart_normalise_famille between 3 and 4, false
        )                                            as prix_eleve_a_verifier,

        -- Non evalue faute d'etiquette : a afficher avec cette mention, ou pas du tout.
        coalesce(
            marches_dans_la_famille >= 30 and ecart_normalise_famille < -4, false
        )                                            as prix_tres_bas_non_evalue,

        -- === Signal 2 : concurrence absente ================================
        --
        -- L'offre unique est l'indicateur le plus utilise de la litterature. Il n'est renseigne
        -- que dans 44 % des marches, et la mesure de phase 2 a montre qu'il est banal sur les
        -- petits marches (27,1 % sous 25 000 euros) et rare sur les gros (16,2 % au-dessus de
        -- 10 millions). Le signal ne se declenche donc qu'au-dessus du seuil de procedure
        -- formalisee, la ou une offre unique est reellement inhabituelle.
        coalesce(offre_unique and montant >= 214000, false) as offre_unique_sur_gros_marche,

        -- === Signal 3 : concentration des attributions =====================
        --
        -- L'indicateur de repli identifie en phase 2 : contrairement au nombre d'offres, il est
        -- calculable sur 100 % des marches. Mesure : 1 656 couples ou un titulaire remporte plus
        -- de la moitie des marches d'un acheteur qui en passe au moins dix, dont 58 ou il les
        -- remporte tous.
        --
        -- La condition sur le nombre de marches de l'acheteur est indispensable : un acheteur qui
        -- passe deux marches et les confie au meme prestataire n'a rien d'anormal.
        coalesce(
            marches_de_l_acheteur >= 10 and part_du_titulaire > 0.5, false
        )                                            as titulaire_dominant

    from variables

)

select
    *,

    -- Le nombre de signaux distincts. Trois signaux independants qui pointent le meme marche
    -- valent mieux qu'un seul, et c'est ce cumul qui orientera la priorite d'examen.
    (
        case when prix_tres_eleve then 1 else 0 end
        + case when offre_unique_sur_gros_marche then 1 else 0 end
        + case when titulaire_dominant then 1 else 0 end
    )                                                as signaux_forts,

    -- La liste en clair, pour l'affichage. Un utilisateur doit comprendre pourquoi un marche lui
    -- est presente, sans avoir a lire ce fichier.
    array_filter(
        [
            case when prix_tres_eleve
                then 'prix tres superieur aux marches comparables' end,
            case when prix_eleve_a_verifier
                then 'prix superieur aux marches comparables' end,
            case when prix_tres_bas_non_evalue
                then 'prix tres inferieur aux marches comparables, signal non evalue' end,
            case when offre_unique_sur_gros_marche
                then 'une seule offre recue sur un marche au-dessus des seuils' end,
            case when titulaire_dominant
                then 'ce titulaire remporte plus de la moitie des marches de cet acheteur' end
        ],
        x -> x is not null
    )                                                as motifs_de_signalement

from signaux
