# Chapitre 2. État de l'art : ce qui existe déjà, et ce qui manque

> Brouillon. Les faits, les chiffres et les sources sont vérifiés ; la formulation reste à
> reprendre dans la voix de l'auteur.

Le chapitre précédent a mesuré un problème : des données publiées en abondance, mais inexploitables
en l'état. Avant de construire quoi que ce soit, il faut savoir ce qui existe. Ce chapitre recense
les outils qui s'adressent aujourd'hui à la commande publique française, qu'ils soient publics,
libres ou commerciaux, et il cherche précisément ce qu'aucun d'eux ne fait.

**Une précaution de méthode, énoncée d'emblée.** Cette comparaison porte sur ce que ces outils
annoncent publiquement, sur ce que leur documentation décrit et, quand le code est ouvert, sur ce
qu'il contient. Elle ne repose pas sur un usage prolongé de chacun d'eux : un abonnement à huit
plateformes commerciales dépasse les moyens d'un mémoire, et plusieurs d'entre elles ne donnent
accès à leur produit qu'après une démonstration commerciale. C'est une limite réelle de ce
chapitre, et elle vaut mieux qu'un jugement présenté comme un essai.

---

## 2.1 Une grille de lecture, posée avant de comparer

Comparer des outils sans grille revient à préférer celui dont on a lu la page d'accueil en
dernier. Les six fonctions ci-dessous découlent directement des trois usages empêchés identifiés à
la fin du chapitre 1.

| # | Fonction | La question de l'utilisateur |
|---|---|---|
| F1 | Trouver un marché ouvert | « qu'est-ce qui est à prendre, dans mon métier et près de chez moi ? » |
| F2 | Analyser les attributions passées | « à quel prix ce type de prestation s'achète-t-il, et par qui ? » |
| F3 | Mesurer et corriger la qualité des données | « ce chiffre est-il exploitable, et sinon pourquoi ? » |
| F4 | Relier l'amont et l'aval | « cet appel d'offres, qu'est-il devenu, et pour quel montant ? » |
| F5 | Signaler les marchés atypiques | « lesquels méritent un regard ? » |
| F6 | Répondre à une question, avec ses sources | « qui a remporté les marchés de voirie en 2023 ? » |

F1 est le marché historique de la veille commerciale. F2 et F3 sont le terrain des acteurs libres.
F4, F5 et F6 sont, comme la suite le montre, très peu couvertes.

---

## 2.2 Les outils publics : publier et mettre en concurrence

L'État français a construit un ensemble d'outils cohérent, et il faut le dire avant d'en montrer
les angles morts : la France publie beaucoup, gratuitement, sous licence ouverte, et depuis
longtemps.

**data.gouv.fr et data.economie.gouv.fr** diffusent les données essentielles. Le ministère publie
un jeu des marchés conformes et laisse en accès libre les non conformes, explicitement « afin de
permettre à leurs émetteurs de procéder à leur correction et à leur republication »[^exclus]. Au
19 septembre 2026, le jeu conforme compte 704 853 lignes pour 472 873 identifiants distincts, et le
jeu des exclus 26 780 lignes[^mesure-jeux]. Publier ses propres rejets est un choix inhabituel et
honnête ; c'est aussi l'aveu, par le producteur, que la qualité n'est pas acquise.

**PLACE**, la plateforme des achats de l'État opérée par l'AIFE, est l'outil de passation. Fin
2025, elle réunit 4 759 entités d'achat, 20 642 agents publics et 344 000 entreprises inscrites ;
36 101 consultations y ont été publiées et 163 000 offres électroniques déposées en 2025, en hausse
de 5,1 %[^place]. L'AIFE a par ailleurs ouvert en 2025 une nouvelle interface de programmation pour
les données essentielles, conforme à l'arrêté de décembre 2022.

**APProch** publie en amont les *projets* d'achat, avant même la consultation, avec des alertes par
secteur et par lieu[^approch]. C'est le seul outil public qui adresse franchement F1.

**Le BOAMP**, édité par la DILA, publie les avis et les expose par une interface de programmation
sous Licence Ouverte 2.0[^boamp]. Le volume annuel des avis parus décroît lentement : 144 480 en
2015, 158 839 en 2019, 149 300 en 2023, 137 423 en 2025[^mesure-boamp-art].

**TED et les eForms** jouent le même rôle au niveau européen, au-dessus des seuils communautaires.
Le format eForms, établi par le règlement d'exécution (UE) 2019/1780, est obligatoire depuis
octobre 2023[^eforms]. C'est la direction que prendra, à terme, la normalisation française.

**Le constat.** Ces outils publient, mettent en concurrence et notifient. Aucun d'eux n'analyse :
il n'existe pas de service public qui réponde à « à quel prix ce type de prestation s'achète-t-il
habituellement », ni qui relie un avis du BOAMP au montant finalement attribué, ni qui signale un
marché atypique. F2 à F6 restent ouvertes.

---

## 2.3 Les projets libres et associatifs : analyser et mesurer la transparence

C'est là que se trouve l'essentiel du travail d'analyse, et c'est un fait notable en soi.

**decp.info, devenu colibre** (Colin Maudry) est l'outil le plus proche de ce projet. Créé en 2021,
passé en version 3 le 29 juillet 2026, il consolide les DECP et permet de les explorer. Le jeu
consolidé est republié chaque jour sur data.gouv.fr, en Parquet de 236 Mo et en CSV de 2,4 Go, sous
Licence Ouverte 2.0[^colibre]. Les fonctions de base sont gratuites, un abonnement à 20 euros hors
taxes par mois ajoute les alertes et les vues partagées, et l'accès programmatique est payant.

C'est aussi ce projet qui documente le mieux les défauts de la source : son auteur indique
supprimer environ un million de doublons à chaque traitement[^doublons]. Cette affirmation n'a pas
été auditée, et le chapitre 1 a montré sur nos propres mesures que le mot « doublon » recouvre
trois phénomènes très différents, dont deux ne sont pas des doublons. Elle est citée ici pour ce
qu'elle est : le constat d'un praticien, convergent avec le nôtre sur le diagnostic, pas sur le
chiffre.

**Éclaireur public** (Anticor avec Data for Good, lancé en février 2026) ne mesure pas les marchés
mais la transparence de ceux qui les passent, par un indice noté de A à E sur le modèle du
Nutri-Score. Résultat : sur 4 626 collectivités soumises à l'obligation, 86,0 % publient leurs
marchés, mais seules 26,8 % obtiennent une note de qualité A ou B, 98 % des collectivités ont un
indice global E, et 126 seulement obtiennent A[^eclaireur]. Ces chiffres confirment de l'extérieur
ce que le chapitre 1 a mesuré de l'intérieur : l'obligation de publier est largement respectée, la
qualité de ce qui est publié ne l'est pas.

**opentender.eu**, issu du projet européen DIGIWHIST mené par l'Université de Cambridge avec la
Hertie School, le Government Transparency Institute et d'autres partenaires, couvre 35 juridictions
européennes et calcule des indicateurs d'intégrité, passés de 9 en 2024 à 11 dans la mise à jour de
mars 2026[^opentender]. C'est le plus avancé des outils sur F5. Sa limite pour notre sujet est son
périmètre : il s'appuie sur TED, donc sur les seuls marchés au-dessus des seuils européens. Or le
chapitre 1 a mesuré que 63 % des marchés français sont sous le seuil de 214 000 euros applicable
aux collectivités. L'essentiel de la commande publique française échappe donc à cet outil.

**L'Open Contracting Partnership** fournit la matière conceptuelle : le standard de données OCDS,
un guide de 2024 recensant 73 signaux de risque avec leurs formules, et une bibliothèque libre,
Cardinal, lancée le 12 juin 2024 avec 10 indicateurs[^ocp]. Le chapitre 5 reprend explicitement
plusieurs de ces définitions, et dit lesquelles les DECP ne permettent pas de calculer.

---

## 2.4 Les plateformes commerciales : vendre de la veille, et parfois une IA

Le marché privé existe, il est ancien, et il est concentré sur F1.

| Acteur | Positionnement | Tarif public |
|---|---|---|
| Marchés Publics France | veille d'appels d'offres et d'attributions | 1 200 à 5 000 euros HT par an selon la zone |
| Marchés Online (Groupe Moniteur) | veille intégrale, base d'attributaires sur trois ans | grille publique côté acheteurs seulement : 399 à 26 040 euros HT par an |
| Vecteur Plus (Infopro Digital) | veille marchés publics et projets privés | non publié |
| DoubleTrade | détection et anticipation des appels d'offres | non publié |
| France Marchés | agrégateur d'avis, alertes gratuites | gratuit pour les alertes, le reste non vérifié |
| Deepbloo | veille par IA, plus de 4 millions d'avis dans plus de 190 pays (déclaratif) | non publié |
| Tengo | IA pour cibler et rédiger les réponses | non publié |
| Tenderbolt | IA de réponse aux appels d'offres, hébergement UE | non publié, « we do not offer a generic pricing grid » |

Relevé du 19 septembre 2026[^commerciaux].

Deux observations, dont la seconde est un résultat.

**Le positionnement est homogène.** Ces huit acteurs vendent de la veille en amont et, pour les plus
récents, de l'aide à la rédaction des réponses. Aucun ne met en avant l'analyse des attributions
passées, le contrôle de la qualité des données publiées, ni le signalement de marchés atypiques.
C'est cohérent avec leur modèle économique : leur client est l'entreprise qui veut gagner un
marché, pas le citoyen qui veut comprendre une dépense.

**Sur huit acteurs, deux publient un tarif vérifiable** pour une entreprise cliente. Cette opacité
n'est pas anecdotique pour un mémoire dont la thèse porte sur les coûts : elle interdit la
comparaison chiffrée que le sujet appelle. Le même phénomène se reproduira au chapitre 8 avec
Databricks, Snowflake et OpenAI, qui ne publient pas davantage de tarif vérifiable sans ouverture
de compte. Sur l'ensemble des fournisseurs examinés dans ce mémoire, qu'il s'agisse de veille ou
d'infrastructure, **la minorité qui publie ses prix sous une forme qu'un tiers peut vérifier est
une donnée de marché, et pas seulement une gêne de méthode.**

Une illustration pour finir : Vecteur Plus annonce « plus de 180 000 marchés publics » en 2025 pour
188 milliards d'euros[^vecteur]. L'Observatoire économique de la commande publique recensait
223 383 contrats pour 233,3 milliards en 2024. Les deux chiffres ne sont pas comparables, les
périmètres diffèrent, et rien dans la communication de l'acteur privé ne permet de savoir lequel.
C'est exactement le problème que ce mémoire traite.

---

## 2.5 La grille, remplie

| Fonction | Outils publics | Libres et associatifs | Commerciaux | Ce projet |
|---|---|---|---|---|
| F1 trouver un marché ouvert | oui (APProch, BOAMP, PLACE) | partiellement (colibre à terme) | **c'est leur métier** | non, hors sujet |
| F2 analyser les attributions | non | oui (colibre) | marginal | oui |
| F3 qualité des données | publication des rejets | oui (colibre, Éclaireur) | non | oui, et mesurée |
| F4 relier l'amont et l'aval | non | non | non | oui, avec un degré de confiance |
| F5 signaler les atypiques | non | oui hors de France (opentender, Cardinal) | non | oui, règles mesurées |
| F6 répondre avec ses sources | non | non | assistants de rédaction, sans sources vérifiables | oui |

---

## 2.6 Le creux, et ce que ce mémoire prétend y mettre

Trois fonctions sont vides ou presque, et ce sont les trois qui demandent le plus de travail
d'ingénierie : relier deux sources sans identifiant commun, signaler sans accuser, et répondre à
une question en citant ses sources.

**Ce que ce mémoire ne prétend pas.** Il n'est pas le premier à consolider les DECP : colibre le
fait, quotidiennement, et mieux sur le volume. Il n'invente pas les indicateurs de risque : ils
viennent de Fazekas et Kocsis et du guide de l'Open Contracting Partnership. Il ne découvre pas la
mauvaise qualité des données : le Sénat, la Cour des comptes et Anticor l'ont écrit avant.

**Ce qu'il apporte**, et ce sont les quatre points sur lesquels le jury est invité à le juger :

1. **Une chaîne complète, de la source publique à l'écran, dont chaque étape est mesurée** et
   rejouable par une commande. Les outils existants publient un résultat ; celui-ci publie aussi
   le coût, la latence, la précision et l'incertitude de chaque étape.
2. **Le rapprochement du BOAMP et des DECP**, que personne ne propose, avec son taux de réussite et
   sa justesse publiés plutôt que supposés (chapitre 4).
3. **Une détection justifiée par la mesure plutôt que par la mode**, y compris quand la mesure
   conclut contre l'apprentissage automatique (chapitre 5).
4. **Un coût d'exploitation mesuré et comparé aux offres gérées du marché**, soit 23,50 euros hors
   taxes par mois contre 119,44 pour l'offre gérée complète la moins chère (chapitre 8).

Autrement dit, l'apport n'est pas une idée neuve, c'est une démonstration : **que la chaîne
complète tient, pour le prix d'un abonnement de veille d'entrée de gamme, avec des outils libres,
et que chacune de ses affirmations est vérifiable.**

---

[^exclus]: Description du jeu « decp-2022-marches-exclus », data.economie.gouv.fr,
https://data.economie.gouv.fr/explore/dataset/decp-2022-marches-exclus/information/

[^mesure-jeux]: Calcul propre, interface de programmation Opendatasoft de data.economie.gouv.fr,
19 septembre 2026. Détail dans `ressources/etat-des-lieux-commande-publique.md`, section 3.2. Les
comptages portent sur des lignes, et une ligne ne correspond pas forcément à un contrat unique.

[^place]: AIFE, page PLACE, chiffres de fin 2025, https://aife.economie.gouv.fr/nos-applications/place/

[^approch]: economie.gouv.fr, « APProch, portail unique des projets d'achats publics »,
https://www.economie.gouv.fr/APProch-portail-unique-projets-achats-publics

[^boamp]: Interface de programmation du BOAMP, plateforme Opendatasoft de la DILA,
https://boamp-datadila.opendatasoft.com/api/explore/v2.0 ; fiche data.gouv.fr du service de données.

[^mesure-boamp-art]: Calcul propre, interface BOAMP, comptage par année de parution, 19 septembre 2026.

[^eforms]: Office des publications de l'Union européenne, https://ted.europa.eu/en/simap/eforms ;
règlement d'exécution (UE) 2019/1780, modifié en novembre 2022 et en décembre 2023. La date exacte
d'entrée en obligation (octobre 2023) est celle de la page officielle ; le jour précis cité par
plusieurs sources secondaires n'a pas été confirmé.

[^colibre]: Colin Maudry, « decp.info devient colibre », 29 juillet 2026,
https://colin.maudry.com/posts/decp.info-devient-colibre/ ; jeu consolidé publié sur
https://www.data.gouv.fr/datasets/donnees-essentielles-de-la-commande-publique-consolidees-format-tabulaire

[^doublons]: Colin Maudry, « Journée de l'OECP », 25 novembre 2025,
https://colin.maudry.com/posts/2025-11-25-oecp/

[^eclaireur]: Éclaireur public (Anticor et Data for Good), https://eclaireurpublic.fr/perspectives ;
reprise par achatpublic.info, février 2026.

[^opentender]: Hertie School, annonce du lancement de la plateforme DIGIWHIST ; cadre mis à jour de
11 indicateurs, Government Transparency Institute, 12 mars 2026,
https://imonitor.govtransparency.eu/2026/03/12/corruption-risk-indicators-in-public-procurement-an-updated-opentender-eu-framework/
La page « about » du site n'a pas pu être ouverte (erreur 403) : ni la couverture ni la fraîcheur
des données françaises n'ont été vérifiées directement.

[^ocp]: Open Contracting Partnership, « Red flags in public procurement : a guide to using data to
detect and mitigate risks », 2024,
https://www.open-contracting.org/wp-content/uploads/2024/12/OCP2024-RedFlagProcurement-1.pdf ;
annonce de Cardinal, 12 juin 2024.

[^commerciaux]: Relevé du 19 septembre 2026 sur les pages publiques de tarification de chaque
acteur. Détail et adresses dans `ressources/etat-des-lieux-commande-publique.md`, section 4.3. La
grille de Marchés Online est celle des acheteurs qui publient des avis, applicable au 1er janvier
2019 ; aucun tarif de veille pour les entreprises n'a été trouvé. La page tarifs de France Marchés
n'a pas pu être ouverte (erreur 403).

[^vecteur]: Vecteur Plus, chiffres 2025 repris par achatpublic.info, « Statistiques commande
publique 2025 », 30 janvier 2026. Estimation privée, pas un chiffre officiel.
