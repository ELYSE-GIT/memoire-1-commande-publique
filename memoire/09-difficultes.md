# Chapitre 9. Difficultés rencontrées et solutions

> Brouillon. Les faits, les chiffres et les mesures sont vérifiés et reproductibles ; la
> formulation reste à reprendre dans la voix de l'auteur.

Un mémoire sans difficulté est un mémoire sans travail. Celui-ci en compte **soixante-quatre**,
consignées au jour le jour dans quinze journaux de bord, chacune avec son symptôme, sa cause, sa
correction et la leçon qui en a été tirée[^journaux].

Ce chapitre ne les énumère pas. Il les **classe**, parce que la répartition est elle-même un
résultat : les difficultés de ce projet ne sont pas réparties au hasard, et les familles les plus
fournies ne sont pas celles qu'on attendrait d'un projet de données.

Une règle a été tenue d'un bout à l'autre, et elle mérite d'être énoncée avant la liste : **une
leçon ne compte que si elle se voit dans le dépôt.** Une leçon qui reste dans un journal est un
regret. Une leçon devenue un test, une assertion, un commentaire à l'endroit du choix ou un critère
de révision écrit dans une décision d'architecture est une protection. Chaque entrée de ce chapitre
désigne donc le fichier où elle survit.

---

## 9.1 Six familles, et ce que la répartition apprend

| Famille | Ce qui la caractérise | Le cas le plus coûteux |
|---|---|---|
| **Deux chiffres pour une même chose** | les deux sont justes, et comptent des objets différents | 403 milliards d'euros affichés en trop sur la page d'accueil |
| **Des mesures qui se flattent** | le protocole avantage le résultat, sans que personne ne triche | une règle de détection calée sur les années qu'elle juge |
| **Des outils de qualité verts et faux** | le contrôle passe et ne contrôle rien | 195 tests verts sur une interface de programmation inutilisable |
| **Des erreurs qui réussissent en silence** | aucun message, aucune alerte, un résultat faux | un tri qui ignorait son index, 28 636 millisecondes contre 30 |
| **Chercher au mauvais endroit** | la donnée est là, pas où on la cherchait | un identifiant d'établissement jugé absent de 81 % des avis |
| **Des réputations prises pour des mesures** | une option écartée sur sa réputation, pas sur un chiffre | une méthode de détection écartée sur son coût supposé |

**Ce que cette répartition apprend, et qui n'était pas prévu** : aucune de ces six familles n'est
une famille de bogues. Pas un seul des cas les plus coûteux de ce projet n'est un programme qui
s'arrête, lève une exception ou rend un message d'erreur. Ce sont tous des programmes qui
fonctionnent et qui ont tort.

C'est une observation banale pour qui a déjà travaillé sur des données, et c'est pourtant l'inverse
de ce que l'outillage courant protège. Les tests, les vérificateurs de types, les analyseurs de
sécurité et les chaînes d'intégration attrapent le code qui échoue. Il n'existe, dans ce projet,
aucun outil qui ait attrapé un seul des six cas du tableau. Ce qui les a attrapés : un banc de
mesure, un navigateur ouvert, une relecture à la main, et une question posée à un chiffre qui
semblait trop beau.

---

## 9.2 Les cinq difficultés qui ont changé l'architecture

Les soixante-quatre entrées n'ont pas le même poids. Cinq ont modifié une décision structurante, et
elles sont développées ici parce que leur coût dépasse leur correction.

### Un tri qui ignorait son index

Le tri de la liste des marchés récents portait un `nulls last`, destiné à placer en fin de liste les
marchés sans date de notification. L'index est déclaré en ordre décroissant, et le moteur place par
convention les valeurs absentes en tête d'un tri décroissant : demander l'inverse revient à demander
un ordre que l'index ne connaît pas, donc il est abandonné et deux millions de lignes sont triées.

**28 636 millisecondes contre 30. Un facteur 965.** Et, vérifié le même jour, il existe **zéro**
ligne sans date de notification sur 1 999 474.

Ce qui en fait une difficulté structurante n'est pas le facteur 965, c'est que le défaut était une
**précaution**. Personne ne l'avait écrite par négligence, et elle serait restée invisible tant que
la table serait restée petite. La conséquence tirée est un principe de mesure plutôt qu'une
correction : chaque composant du projet a désormais son banc, parce qu'aucun test ne mesure une
durée[^api].

### Un total faux de 403 milliards d'euros

Le projet documente depuis le chapitre 1 qu'un marché attribué à un groupement d'entreprises occupe
une ligne par titulaire. Il le documente avec 273 494 cas mesurés et une figure. Mais uniquement
pour les **comptages**. Personne n'avait regardé ce que cela faisait aux **montants**, alors que le
montant publié sur chacune des lignes d'un groupement est très souvent celui du marché entier,
répété.

| Mode de calcul | Total sur onze ans |
|---|---|
| somme des lignes publiées | 1 500,9 milliards d'euros |
| une fois chaque couple (marché, montant) | **1 098,2 milliards d'euros** |
| écart | **402,7 milliards, soit 36,7 %** |

Le site affichait le premier chiffre, en gros, sur sa page d'accueil. **Il ne venait d'aucun
bogue** : une addition exacte, sur des données documentées, posée sur la mauvaise unité de comptage.

La correction est devenue une règle d'affichage : la page montre le total dédoublonné, l'addition
naïve à côté, et l'écart en pourcentage. Et une vérification de robustesse a été ajoutée : la
troisième règle défendable, garder le montant le plus élevé de chaque marché, donne 1 097,9
milliards, soit 0,03 % d'écart avec la règle retenue. **Le choix entre les règles défendables ne
change rien ; le choix de dédoublonner ou non change le total de 37 %.** C'est ce rapport entre les
deux sensibilités qui justifie la règle, pas la préférence de l'auteur[^site].

### Un contrat de données placé à la mauvaise couche

Le premier contrat écrit exigeait un identifiant d'acheteur non nul en couche argent, et faisait
échouer la chaîne sur six lignes. Les deux réflexes disponibles étaient mauvais : désactiver le
test, ou supprimer les six lignes.

La cause était ailleurs. **Le contrat contredisait la promesse de la couche** : la couche argent
s'engage à tout garder en marquant les problèmes, et y exiger un identifiant non nul revient à
exiger qu'il n'y ait aucun problème à conserver. Correction : avertissement en couche argent, règle
stricte déplacée en couche or, où elle bloque à juste titre.

**La sévérité d'un test doit correspondre à ce que sa couche promet.** Un test trop strict finit
désactivé, et un test désactivé ne protège plus rien. C'est le mécanisme exact de l'échec Louvois
décrit au annexe B, où environ deux cents contrôles de cohérence jugés bloquants ont été
neutralisés « au lieu d'améliorer la fiabilité des saisies », pour un coût connu de 358 millions
d'euros[^nettoyage].

### Un outil retenu, puis archivé par son éditeur

Un stockage objet compatible avec le protocole d'Amazon figurait dans l'architecture envisagée, et
c'était un choix banal. Son dépôt a été archivé par son éditeur le 25 avril 2026, l'offre commerciale
qui lui succède démarrant à plusieurs dizaines de milliers de dollars par an.

La réaction naturelle aurait été de chercher le remplaçant. La question posée a été différente :
**de quoi ce composant me servait-il.** La réponse était qu'il stockait des fichiers que le système
de fichiers de la machine stocke aussi bien, à une échelle où aucune des propriétés qui justifient
un stockage objet, la réplication, le partage entre machines, le versionnement d'objets, n'était
utilisée.

**L'architecture retenue ne contient donc aucun stockage objet**, et la leçon est plus générale que
l'incident : la disparition d'un composant est une occasion de vérifier qu'il servait à quelque
chose. Celui-là ne servait à rien, et il aurait été maintenu des années[^cas].

### Une graine fixe qui ne rendait pas le calcul reproductible

Deux lancements du même script d'évaluation donnaient 100 %, puis 74 %. La graine aléatoire était
pourtant fixée, ce qui est la précaution que tout le monde connaît.

Elle ne suffit pas : il faut aussi un **ordre de lignes fixe**, parce que le découpage d'un
échantillon dépend de l'ordre dans lequel les lignes arrivent, et que ce moteur de base de données
ne garantit aucun ordre sans clause explicite. La première correction, trier par l'identifiant de
marché, n'a pas suffi non plus, pour une raison qui est elle-même l'une des soixante-quatre
difficultés : **cet identifiant désigne un marché, pas une ligne.** 140 350 identifiants apparaissent
plusieurs fois.

La leçon tenue depuis : un identifiant se vérifie avant qu'on s'y appuie, et la reproductibilité se
constate en relançant, pas en lisant le code[^modele].

---

## 9.3 Les trois chiffres que ce mémoire a failli publier

Ce sont les entrées les plus inconfortables, et elles sont ici parce qu'un chapitre de difficultés
qui ne contiendrait que des problèmes techniques serait une forme de confort.

**44 % de doublons.** Mesure de la phase 2, spectaculaire, et fausse. Ce ne sont pas des doublons
mais des avenants et des groupements d'entreprises : l'historique des modifications et une ligne par
titulaire. Le chiffre aurait tenu dans une conclusion et se serait fait reprendre.

**Un rapport de coûts de 3,9 au lieu de 5,1.** La première version du résumé des coûts désignait
comme « offre gérée la moins chère » une ligne qui ne couvre que la base de données, sans la machine
qui sert les pages. Le rapport annoncé devenait 3,9, et il était faux **dans le sens défavorable à la
thèse défendue**. Une erreur de périmètre ne va pas toujours dans le sens qui arrange, et celle-là
venait de la même négligence qui le fait d'habitude.

**5 % de marchés attribués à des petites entreprises.** Premier essai de l'enrichissement, mené sur
les soixante **plus gros** titulaires. Un tirage aléatoire sur le même jeu donne 59,2 %. Le premier
chiffre n'était pas faux : il répondait à une autre question, « parmi les plus gros titulaires,
combien de petites entreprises ». **Choisir un échantillon au lieu de le tirer revient à choisir sa
réponse.**

Les trois ont été rattrapés par le même geste, et c'est le geste que ce mémoire recommande : demander
à un chiffre flatteur d'où il vient, avant de le publier plutôt qu'après.

---

## 9.4 Trois leçons de méthode qui valent au-delà de ce projet

**Un test et une mesure ne répondent pas à la même question.** Les 195 tests de l'interface de
programmation étaient verts sur un service inutilisable, et les quatre défauts qu'un banc de mesure
a trouvés en moins d'une minute rendaient tous des résultats **justes**. Il faut les deux, et il faut
savoir lequel attrape quoi. Le corollaire a coûté cher deux fois : il faut mesurer **à froid** aussi,
parce que le cas froid est celui du premier visiteur après chaque déploiement.

**Deux chiffres qui se contredisent sont souvent deux définitions.** 57 409 marchés signalés dans un
fichier de mesure, 76 309 dans une vue d'ensemble : le premier compte « au moins un signal fort », le
second tous les motifs. 1 999 474 lignes en couche or un jour, 2 053 765 le lendemain : le jeu est
republié chaque matin. Dans les deux cas, la réponse n'a pas été de choisir un chiffre, mais de
**publier les deux avec leur définition et leur date**. Un mémoire qui n'en publierait qu'un serait
plus lisible et moins vrai.

**Une leçon notée n'est pas une leçon appliquée.** Des fichiers de mesure ont été écrits deux fois
avec des fins de ligne du mauvais système, à dix jours d'intervalle, alors que la leçon du premier
incident était écrite. Elle n'était écrite **que** dans un journal. Tant qu'une leçon n'est pas dans
le code partagé, un test ou un gabarit, elle sera réapprise.

---

## 9.5 Ce qui reste ouvert

Les difficultés résolues ne sont pas plus intéressantes que celles qui ne le sont pas. Les
principales, à la date de rédaction :

| Point ouvert | Ce qu'il empêche d'affirmer |
|---|---|
| La taille minimale de famille d'achat est vérifiée sur l'historique complet, pas sur la période jugée | une famille passant de 1 556 marchés à 31 continue d'être évaluée : les chiffres de détection changeront après correction |
| La concordance tombe à 53,1 % en 2023, contre 81,7 % en 2022 et 67,8 % en 2024 | ni la pratique d'étiquetage du producteur ni le hasard ne l'expliquent, et aucune hypothèse n'est vérifiée |
| Une recherche inédite reste à environ 1,8 seconde sur une base froide, 4,8 au 95e centile | le confort d'usage n'est pas démontré, seulement la latence à chaud |
| La pertinence des résultats de recherche n'est pas mesurée | ce qui est mesuré est la vitesse et le silence, pas la qualité |
| Les quarante questions de l'assistant ont été écrites par l'auteur des motifs | le score de 40 sur 40 mesure la cohérence interne, pas la généralisation |
| Un écart de 1,6 % sur le nombre de titulaires, 213 703 mesurés contre 217 199 publiés | un écart non expliqué reste un écart |

Aucune de ces six lignes n'empêche le projet de fonctionner, et c'est précisément pourquoi elles
sont écrites : un point ouvert qui ne gêne personne est celui qui disparaît des documents.

---

[^journaux]: Les quinze journaux de bord sont dans `docs/journal/`, un par session de travail,
écrits le jour même. Chacun suit la même forme : objectif, ce qui a été fait, ce qui a résisté,
symptôme, cause, solution, leçon.

[^api]: Journal du 22 octobre 2026, `docs/journal/2026-10-22-api-publique.md`. Mesures dans
`mesures/resultats/api-latences.csv` et `api-resume.csv`, décision tracée dans l'ADR 0011.

[^site]: Journal du 22 octobre 2026, `docs/journal/2026-10-22-site-public.md`. Première migration de
schéma du projet, `base/migrations/`, et ADR 0012.

[^nettoyage]: Journal du 28 septembre 2026, `docs/journal/2026-09-28-nettoyage.md`, et ADR 0005. Le
cas Louvois est sourcé au annexe B.

[^cas]: Détail et sources au annexe C, section des outils examinés puis écartés.

[^modele]: Journal du 29 septembre 2026, `docs/journal/2026-09-29-modele-vs-regles.md`, et ADR 0007.
