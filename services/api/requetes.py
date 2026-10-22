"""Les requetes SQL de l'API, ecrites en SQL et au meme endroit.

Elles ne sont pas disseminees dans les routes : une route decrit ce que l'API promet, une
requete decrit comment la base y repond. Les separer permet de relire le SQL sans lire le
Python, et de verifier par un test que chaque colonne citee existe vraiment dans le schema.

=== Pourquoi aucune route ne renvoie de nombre total de resultats =============

C'est la decision la plus visible de ce fichier, et elle vient d'une mesure. Compter les lignes
qui repondent a une recherche oblige PostgreSQL a toutes les visiter, meme pour n'afficher que
les dix premieres. L'index GIN donne les dix premieres en quelques millisecondes ; le comptage
paie le parcours complet des lignes trouvees.

    Option envisagee           Avantage                    Limite                      Verdict
    `count(*)` exact a chaque  « 57 312 resultats »        la latence depend du nombre  ecarte
    page                       rassure l'utilisateur       de resultats, donc la page
                                                            la plus lente est celle qui
                                                            interesse le moins
    estimation par             constante et tres rapide    un chiffre faux affiche      ecarte
    `explain`                                               comme un chiffre vrai
    **une ligne de plus que    constante, honnete, et      on ne sait pas combien de    **retenu**
    demande**                  suffit a afficher « page    pages il y a au total
                               suivante »
    comptage exact seulement   le meilleur des deux        deux chemins de code, et un
    sous un seuil                                          seuil arbitraire a            ecarte
                                                           justifier                     pour
                                                                                          l'instant

A quelle echelle la reponse changerait : si le site avait besoin d'afficher « page 12 sur 47 »,
le comptage exact redeviendrait obligatoire, et il faudrait alors le mettre en cache par requete.
Tant que la navigation est « suivant » et « precedent », la ligne supplementaire suffit.

=== Pourquoi les filtres sont composes et non concatenes =====================

Chaque valeur fournie par un visiteur passe par un parametre `%s`, jamais par une f-string.
Seule la **structure** de la requete est composee, avec `psycopg.sql`, et uniquement a partir de
fragments ecrits dans ce fichier. Un nom de colonne ne vient donc jamais de l'exterieur. C'est
la seule defense qui tienne contre l'injection SQL : echapper a la main finit toujours par
oublier un cas.
"""

from typing import Any

from psycopg import sql

# Les colonnes servies dans une liste de resultats. Elles sont enumerees et non prises par `*` :
# `select *` renverrait aussi la colonne `recherche`, un vecteur de plusieurs kilo-octets par
# ligne, pour rien.
COLONNES_MARCHE = (
    "marche_id",
    "objet",
    "acheteur_nom",
    "acheteur_departement_nom",
    "acheteur_categorie",
    "titulaire_nom",
    "titulaire_categorie",
    "montant",
    "date_notification",
    "annee",
    "famille_cpv",
    "procedure",
    "offres_recues",
)

COLONNES_SIGNAL = (
    "marche_id",
    "famille_cpv",
    "marches_dans_la_famille",
    "ecart_normalise_famille",
    "prix_tres_eleve",
    "prix_eleve_a_verifier",
    "prix_tres_bas_non_evalue",
    "offre_unique_sur_gros_marche",
    "titulaire_dominant",
    "signaux_forts",
    "motifs_de_signalement",
)

_LISTE_MARCHE = sql.SQL(", ").join(sql.Identifier(nom) for nom in COLONNES_MARCHE)
_LISTE_SIGNAL = sql.SQL(", ").join(sql.Identifier("s", nom) for nom in COLONNES_SIGNAL)

# Nombre de lignes classees, au maximum.
#
# === Le resultat le plus important de `make bench-api` ========================
#
# Mesure du 22 octobre 2026, sur les 1 999 474 lignes chargees, question « travaux » :
#
#     lignes contenant le mot                                  348 748
#     classement exact de toutes ces lignes                    9 815 ms
#     classement des 1 000 premieres                             101 ms
#     classement des 5 000 premieres                             116 ms
#     classement des 20 000 premieres                            177 ms
#
# Le cout ne depend pas de la page demandee mais du **nombre de lignes qui repondent**. Trier
# 348 748 scores pour n'en afficher dix est l'essentiel du travail, et c'est ce qui faisait
# depasser le delai de dix secondes de l'API sur un mot courant. Une question plus precise
# (« travaux de voirie », 20 477 lignes) repondait en 57 ms : le defaut ne se voyait donc pas
# sur les questions du jeu de mesure, toutes composees de plusieurs mots.
#
#     Option envisagee         Avantage                    Limite                      Verdict
#     classer toutes les       l'ordre est exact           9,8 s sur un mot courant,   ecarte
#     lignes qui repondent                                 soit un service inutilisable
#     **classer les N          constante, et moins de      l'ordre n'est exact que si  **retenu**
#     premieres lignes que     200 ms dans le pire cas     moins de N lignes repondent
#     l'index rend**           mesure
#     refuser les questions    simple                      c'est refuser « travaux »,  ecarte
#     trop larges                                          une question legitime
#     garder un cache des      tres rapide a la deuxieme   ne resout rien a la         ecarte
#     questions frequentes     visite                      premiere, et il faut
#                                                          l'invalider
#
# === Ce que l'approximation change vraiment, mesure ===========================
#
# Il ne suffit pas de dire que le classement est « approche ». `make bench-api` compare les dix
# marches affiches aux dix du classement exact, sur dix questions, au plafond retenu de 5 000 :
#
#     question                              lignes qui repondent   exact     borne   communs
#     refection de la toiture d'une ecole                    437      5 ms      3 ms    10/10
#     fourniture de repas (restauration scolaire)          1 162      9 ms      7 ms    10/10
#     assurance dommages aux biens                         5 489     17 ms     14 ms     8/10
#     entretien des espaces verts                         13 482    114 ms     25 ms     5/10
#     travaux de voirie                                   20 477    139 ms     19 ms     3/10
#     maintenance                                        108 650    169 ms     28 ms     3/10
#     travaux de rehabilitation de logements               6 432     27 ms     25 ms     2/10
#     entretien                                          101 818    154 ms     22 ms     0/10
#     fourniture                                         233 730  3 223 ms    133 ms     0/10
#     travaux                                            348 748  5 184 ms     66 ms     0/10
#
# La lecture honnete de ce tableau, et elle n'est pas confortable : **sous le plafond l'ordre est
# exact** (les deux premieres lignes), et des qu'il est depasse l'ordre peut etre entierement
# different, y compris pour une question ordinaire de trois mots comme « travaux de
# rehabilitation de logements ». Deux sur dix n'est pas un detail d'ordre : ce sont huit autres
# marches.
#
# Abaisser le plafond de 20 000 a 5 000 a donc coute de la justesse : a 20 000, les memes
# questions donnaient 10/10, 10/10, 9/10, 9/10, 10/10, 8/10 et 10/10, et seuls les trois mots
# seuls tres courants tombaient a 0/10. Le compromis est explicite : un service qui repond en
# 22 ms et se trompe d'ordre sur les questions larges, contre un service juste qui depasse son
# delai a froid et renvoie une erreur.
#
# Ce qui a fait trancher : une page qui ne s'affiche pas n'a pas d'ordre du tout. Et les dix
# marches rendus ne sont pas quelconques, ce sont les mieux classes **parmi les 5 000 premiers
# que l'index rend**, c'est-a-dire en pratique les plus recents, la table etant ecrite par date
# decroissante. Cette correspondance entre ordre physique et date est une dependance reelle a la
# facon dont `services/publication/vers_postgres.py` ecrit les lignes, pas une garantie du
# modele relationnel : elle est mesuree (correlation de -0,96, voir `base/schema/005-index.sql`)
# et verifiee par un test. Si le chargement changeait d'ordre, les candidats deviendraient
# quelconques et ce compromis s'effondrerait.
#
# Ce qui n'est pas negociable : le dire. La reponse porte `candidats_examines`, et l'API en
# deduit `classement_approche`. Le site l'ecrit a l'ecran. Une approximation annoncee est une
# limite ; une approximation cachee est un mensonge sur la donnee.
#
# Ce qui ferait changer cette decision : un classement precalcule a l'ecriture, ou un moteur
# dedie (Meilisearch, Qdrant) qui tient l'index en memoire. Les deux sont du travail de phase
# ulterieure, et ni l'un ni l'autre n'est justifie avant d'avoir mesure ce que cette
# approximation gene reellement, ce qui demande les jugements de pertinence qu'Elyse doit rendre.
PLAFOND_CANDIDATS = 5_000

# Les filtres structures, un fragment par critere. La cle est le nom du parametre de la route,
# ce qui garantit qu'un filtre ajoute a l'API sans son fragment SQL echoue a l'import plutot
# qu'en silence.
FILTRES = {
    "annee": sql.SQL("annee = %s"),
    "departement": sql.SQL("acheteur_departement_code = %s"),
    "famille": sql.SQL("famille_cpv = %s"),
    "montant_minimum": sql.SQL("montant >= %s"),
    "montant_maximum": sql.SQL("montant <= %s"),
    # Le `is true` et non `= true` : la colonne accepte null, et un marche dont on ignore le
    # nombre d'offres ne doit pas etre compte comme ayant recu une offre unique.
    "offre_unique": sql.SQL("offre_unique is true"),
}


def _conditions(filtres: dict[str, Any]) -> tuple[list[sql.SQL | sql.Composed], list[Any]]:
    """Traduit les filtres fournis en fragments SQL et en valeurs, dans le meme ordre."""
    fragments: list[sql.SQL | sql.Composed] = []
    valeurs: list[Any] = []
    for nom, valeur in filtres.items():
        if valeur is None or valeur is False:
            continue
        fragments.append(FILTRES[nom])
        # Le filtre booleen n'a pas de valeur a passer : sa condition est entiere dans le
        # fragment. Les autres en ont exactement une.
        if valeur is not True:
            valeurs.append(valeur)
    return fragments, valeurs


def recherche(texte: str | None, filtres: dict[str, Any]) -> tuple[sql.Composed, list[Any]]:
    """Construit la requete de recherche, avec ou sans texte.

    Deux formes, parce que ce ne sont pas les memes requetes. Avec du texte, l'index GIN donne
    les lignes qui contiennent les mots et le classement se fait par pertinence. Sans texte,
    aucun classement par pertinence n'a de sens : la question devient « les marches les plus
    recents qui remplissent ces criteres », et c'est l'index sur la date qui repond.

    Trier sans texte par un score constant serait pire qu'inutile : l'ordre deviendrait celui
    du stockage, donc instable d'un chargement a l'autre, et la pagination sauterait des lignes.
    """
    fragments, valeurs = _conditions(filtres)

    if texte:
        # La requete analysee est isolee dans un `with` : une expression convertie avec `::`
        # n'est pas un element valide dans un `from`, et PostgreSQL refuse la requete.
        # `websearch_to_tsquery` accepte le texte tel que l'utilisateur le tape, sans operateur.
        # `ts_rank_cd` tient compte de la proximite des mots, seul signal de structure
        # disponible sur des objets de marche courts (86 caracteres de mediane).
        # En deux temps : l'index rend des candidats, puis on ne classe que ceux-la. Le
        # pourquoi, avec ses mesures, est en tete de ce fichier.
        corps = sql.SQL(
            "with analysee as ("
            "  select websearch_to_tsquery('public.francais', %s) as requete"
            "),"
            " candidats as ("
            "  select {colonnes}, recherche, id"
            "  from marches, analysee"
            "  where recherche @@ analysee.requete{filtres}"
            "  limit %s"
            ")"
            # `count(*) over ()` compte les candidats, pas les resultats : une fonction de
            # fenetre est evaluee avant `limit`. Il porte donc sur les 20 000 lignes au plus de
            # `candidats`, ce qui est gratuit, et il permet de dire au visiteur que son
            # classement est approche au lieu de le lui cacher.
            " select {colonnes}, ts_rank_cd(recherche, analysee.requete) as score,"
            "        count(*) over () as candidats_examines"
            " from candidats, analysee"
            # `id` en dernier : le score et le montant peuvent etre a egalite, et sans
            # tiebreaker unique l'ordre dependrait du hasard, donc changerait d'une page a
            # l'autre.
            " order by score desc, montant desc nulls last, id"
            " limit %s offset %s"
        ).format(
            colonnes=_LISTE_MARCHE,
            filtres=sql.SQL("").join([sql.SQL(" and ") + fragment for fragment in fragments]),
        )
        return corps, [texte, *valeurs, PLAFOND_CANDIDATS]

    ou = sql.SQL(" where ") + sql.SQL(" and ").join(fragments) if fragments else sql.SQL("")
    # L'ordre est ecrit pour l'index, et c'est mesure. `marches_date_idx` est declare
    # `(date_notification desc)`, donc avec les valeurs absentes en premier, qui est la
    # convention de PostgreSQL pour un tri descendant.
    #
    #     order by date_notification desc nulls last, marche_id    28 636 ms
    #     order by date_notification desc, id desc                      30 ms
    #
    # Mesure du 22 octobre 2026. Le premier ordre n'est pas celui de l'index : PostgreSQL
    # renonce a l'index, balaye les 1 999 474 lignes en parallele et trie. Le second est le
    # prefixe de l'index, suivi d'un tri incremental a l'interieur de chaque date : 175 lignes
    # lues au lieu de deux millions, pour le meme resultat.
    #
    # Le plus embarrassant est la raison du `nulls last` : se proteger de dates absentes. Il y
    # en a **zero** sur 1 999 474 lignes, verifie le meme jour. Une precaution qui ne protege de
    # rien a coute un facteur 965.
    #
    # `id desc` en second et non `marche_id` : `id` est la cle primaire, donc unique, donc
    # l'ordre est total. `marche_id` se repete (261 185 lignes partagent un numero), et deux
    # lignes a egalite peuvent changer de place d'une page a l'autre, ce qui fait sauter ou
    # repeter des resultats pendant la pagination.
    corps = sql.SQL(
        # `null` et non zero : aucun classement n'a eu lieu, donc aucun candidat n'a ete
        # examine. Zero se lirait « aucun resultat », ce qui est faux.
        " select {colonnes}, 0.0 as score, null::bigint as candidats_examines"
        " from marches{ou}"
        " order by date_notification desc, id desc"
        " limit %s offset %s"
    ).format(colonnes=_LISTE_MARCHE, ou=ou)
    return corps, valeurs


# Toutes les lignes d'un marche. La limite n'est pas decorative : le plus gros groupement
# observe dans les donnees compte 103 titulaires, et une ligne de marche se repete aussi quand
# le marche fait l'objet de plusieurs notifications.
MARCHE = sql.SQL(
    "select {colonnes} from marches where marche_id = %s order by titulaire_nom limit 200"
).format(colonnes=_LISTE_MARCHE)

SIGNAUX_DU_MARCHE = sql.SQL("select {colonnes} from signaux as s where s.marche_id = %s").format(
    colonnes=_LISTE_SIGNAL
)

# Les marches a examiner.
#
# Pourquoi une jointure laterale limitee a une ligne, et non une jointure ordinaire :
# `marche_id` n'est unique ni dans `marches` ni dans `signaux`. Une jointure classique sur cette
# colonne multiplierait les lignes (trois titulaires et trois signaux donnent neuf lignes), et
# la pagination deviendrait fausse. La laterale rapporte **un exemplaire** des faits pour
# illustrer le signal ; le detail complet reste sur /marches/{marche_id}.
#
# L'index partiel `signaux_a_examiner_idx` ne couvre que les 2,87 % de lignes qui portent un
# signal : la clause `where s.signaux_forts >= %s` doit donc rester superieure a zero pour que
# l'index serve.
SIGNAUX = sql.SQL(
    "select {colonnes}, m.objet, m.acheteur_nom, m.montant, m.annee"
    " from signaux as s"
    " left join lateral ("
    "   select objet, acheteur_nom, montant, annee"
    "   from marches as m where m.marche_id = s.marche_id limit 1"
    " ) as m on true"
    " where s.signaux_forts >= %s"
    " order by s.signaux_forts desc, s.ecart_normalise_famille desc nulls last, s.id"
    " limit %s offset %s"
).format(colonnes=_LISTE_SIGNAL)

# Les comptages de la page d'accueil : une ligne, lue telle quelle.
#
# Le calcul n'est pas ici, et c'est le resultat d'une mesure. Le faire a la demande prenait
# 10,7 s sur 1 999 474 lignes, dont 9,1 s pour les seuls `count(distinct)`, soit au-dela du
# delai de dix secondes que l'API s'impose : la page d'accueil renvoyait une erreur 504. Le
# raisonnement complet, avec les cinq options envisagees, est dans
# `base/schema/008-table-statistiques.sql`, et le remplissage dans le fichier 009.
#
# Ce qui reste a la charge de l'API : rien. Un `select` sur une table d'une ligne.
STATISTIQUES = """
select
    marches, marches_distincts, acheteurs, titulaires,
    montant_total, premiere_annee, derniere_annee, marches_signales, calcule_a
from statistiques
"""

# Le nombre de marches seul, pour /sante. Sur une table d'une ligne, c'est gratuit, et cela
# permet au test de vie de dire si la base est non seulement joignable mais remplie.
MARCHES_CHARGES = "select marches from statistiques"

# La serie par annee, lue dans sa table.
#
# Calculee a la demande, elle prenait 655 ms de mediane et 2 365 ms au 95e centile, mesure du
# 22 octobre 2026 : le groupement des 1 999 474 lignes par annee, avec une part de PME au
# passage. C'est la courbe de la page d'accueil, donc la premiere chose qu'un visiteur attend.
# Elle est desormais calculee au chargement, comme les comptages, par le fichier 009.
#
# Le denominateur de la part de PME est renvoye avec elle : 6,8 % des attributions n'ont aucune
# categorie d'entreprise, et un pourcentage sans son denominateur ferait passer cette
# non-reponse pour des non-PME.
PAR_ANNEE = """
select
    annee, attributions, montant_total,
    attributions_resolues, attributions_pme, part_pme_pourcent
from statistiques_annuelles
order by annee
"""

# Les valeurs proposees dans les menus de filtre. Elles viennent de la base et non d'une liste
# ecrite a la main : une famille d'achat qui disparait des donnees doit disparaitre du menu.
FAMILLES = """
select famille_cpv, count(*) as marches
from marches
where famille_cpv is not null
group by famille_cpv
order by marches desc
"""

# Le test de vie. `select 1` et non une requete sur `marches` : le healthcheck doit dire si la
# base repond, pas si elle est remplie. Les deux questions sont distinctes, et la seconde est
# deja repondue par les statistiques en cache.
VIE = "select 1"
