# 10. Mise en production et sécurité

> État : la section 10.1 est rédigée (phase 7). Les sections 10.2 à 10.5, qui portent sur le VPS,
> les conteneurs, la supervision et les sauvegardes, seront écrites en phase 9.

## 10.1 Servir les données : l'API

Jusqu'ici, tout ce que ce mémoire décrit n'existait que sous la forme de scripts lancés à la main
sur un ordinateur portable. Deux millions de marchés nettoyés, une recherche en texte intégral,
des règles de détection et un assistant qui cite ses sources : rien de tout cela n'était
accessible à qui que ce soit d'autre. Cette section décrit le passage d'un traitement à un
service, et surtout ce que ce passage a appris.

### 10.1.1 Ce qu'un service change par rapport à un script

Un script a le droit d'être lent. Il tourne une fois, on attend, on obtient un fichier. Un service
n'a pas ce droit : quelqu'un attend devant un écran, et il n'a aucune idée de ce qui se passe.
Cette différence n'est pas une question de degré, elle change les critères de conception.

Trois contraintes apparaissent d'un coup. D'abord, **le temps devient une exigence** et non une
observation : une requête qui prend dix secondes n'est pas une requête lente, c'est une page qui
ne s'affiche pas. Ensuite, **les entrées viennent de l'extérieur** : un script reçoit ses
paramètres de celui qui l'écrit, un service reçoit ce qu'un inconnu a tapé, y compris ce qu'il a
tapé pour voir ce qui casserait. Enfin, **les erreurs doivent être racontées à quelqu'un** : un
script peut s'arrêter avec une trace d'exécution, un service doit répondre quelque chose, et ce
quelque chose ne doit révéler ni le texte de ses requêtes ni le nom de son serveur.

L'API construite ici expose sept routes : l'état du service, la recherche de marchés, le détail
d'un marché, les signaux de détection, deux jeux de comptages et l'assistant. Le choix du cadre
technique, FastAPI plutôt que Flask, Django REST Framework ou Litestar, est détaillé dans
l'ADR 0011 ; il tient en une phrase : le projet était déjà entièrement annoté et vérifié par un
analyseur de types en mode strict, et FastAPI réutilise ces annotations pour valider les entrées
et produire sa documentation, de sorte que le travail de typage sert deux fois.

Ce choix n'est pas le sujet intéressant. Le sujet intéressant est ce qui s'est passé quand on a
mesuré.

### 10.1.2 Quatre défauts qu'aucun test ne pouvait trouver

À la fin de la phase 6, le dépôt comptait 195 tests, tous verts, et une chaîne d'intégration
continue qui vérifiait le style, les types, les secrets et le comportement. La première version de
l'API passait l'ensemble sans une seule erreur. Elle était pourtant inutilisable, et le banc de
mesure `make bench-api` l'a montré en moins d'une minute.

La raison est simple et vaut d'être énoncée : **aucun test ne mesure une durée**. Un test vérifie
qu'une fonction rend le bon résultat, pas qu'elle le rend assez vite. Les quatre défauts ci-dessous
produisaient tous des résultats justes.

| Ce qui était écrit | Ce que la mesure a donné | Ce qui a changé |
|---|---|---|
| trier la liste récente par `date_notification desc nulls last` | **28 636 ms** : PostgreSQL renonce à l'index et parcourt les deux millions de lignes | `order by date_notification desc, id desc`, soit **30 ms** |
| classer tous les marchés qui répondent à la recherche | **9 656 ms** sur le mot « travaux », abandonnée par la base | classement limité à un nombre fixe de candidats |
| calculer les comptages de la page d'accueil à chaque visite | entre **10 726 ms** et **61 519 ms** selon l'état des caches | table remplie au chargement, lue en **0,5 ms** |
| calculer la série par année à chaque visite | **655 ms** de médiane, **2 365 ms** au 95e centile | seconde table remplie au chargement, **2 ms** |

Le premier cas mérite d'être regardé de près, parce que le défaut était une **précaution**. La
mention `nulls last` servait à placer en fin de liste les marchés dont la date de notification
serait absente. L'intention est raisonnable. Deux faits la rendent absurde. Le premier est qu'un
index déclaré sur `date_notification desc` place par convention les valeurs absentes en tête, de
sorte que demander l'ordre inverse revient à demander un ordre que l'index ne connaît pas : le
moteur abandonne l'index et trie deux millions de lignes. Le second est qu'il n'existe **aucune**
ligne sans date de notification, sur 1 999 474. Une protection qui ne protégeait de rien a coûté
un facteur 965.

C'est la forme la plus commune du problème : non pas une erreur, mais une habitude défensive dont
personne ne mesure le prix. Elle serait restée invisible aussi longtemps que la table serait
restée petite, et elle n'aurait jamais fait échouer un test.

### 10.1.3 Mesurer à froid, et pourquoi cela a changé une décision

Le troisième défaut a eu une suite instructive. Après avoir limité le classement de la recherche à
20 000 candidats, les mesures étaient excellentes : 57 millisecondes de médiane. La décision
semblait close.

Le banc l'a rouverte au lancement suivant. La toute première recherche après le démarrage du
service renvoyait une erreur. En remesurant, en redémarrant la base avant chaque essai pour vider
sa mémoire partagée :

| Candidats classés | Base froide | À chaud |
|---|---|---|
| 20 000 | **7 219 ms** | 57 ms |
| 5 000 | 436 ms | 116 ms |
| 1 000 | 42 ms | 101 ms |

Un facteur 128 entre froid et chaud. La cause est lisible : classer suppose de lire, pour chaque
candidat, le vecteur de mots du marché, que PostgreSQL stocke à part parce qu'il pèse plusieurs
kilo-octets. Aller chercher 20 000 de ces vecteurs sur un disque dont rien n'est en mémoire coûte
exactement ce que la mesure dit.

Ce qui compte ici n'est pas le chiffre mais la leçon de méthode : **mesurer seulement à chaud
revient à valider un service qui échoue à chaque déploiement**, c'est-à-dire précisément au moment
d'une démonstration. Le banc mesure donc désormais le premier appel séparément, et ne le jette
pas. C'est la barre rouge de la figure 24.

![Latence par route et comportement sous charge](figures/24-api-latence-et-charge.svg)

Le panneau de droite dit l'autre moitié de l'histoire. Le débit plafonne vers 94 requêtes par
seconde dès deux clients simultanés, et au-delà la latence croît proportionnellement au nombre de
clients, sans aucun échec sur 300 appels. C'est le comportement attendu d'une file d'attente : le
service ne s'effondre pas, il fait patienter. La limite vient de la réserve de connexions, fixée à
quatre volontairement, parce que chaque connexion PostgreSQL est un processus serveur et que la
machine de production sera petite.

### 10.1.4 Ce que l'optimisation a coûté, et pourquoi il faut l'écrire

Limiter le classement à 5 000 candidats n'est pas gratuit, et c'est le point le plus important de
cette section. Au-delà de ce plafond, les dix marchés affichés ne sont plus les dix meilleurs : ce
sont les mieux classés **parmi les 5 000 premiers que l'index rend**. Le banc compare les deux
listes :

| Marchés qui répondent | Marchés communs sur dix |
|---|---|
| 437 | 10 |
| 1 162 | 10 |
| 5 489 | 8 |
| 13 482 | 5 |
| 20 477 | 3 |
| 101 818 et au-delà | 0 |

Sous le plafond, l'ordre est exact. Au-dessus, il peut être entièrement différent, y compris pour
une question ordinaire de trois mots. Deux sur dix n'est pas une nuance d'ordre : ce sont huit
autres marchés.

Trois choses doivent être dites franchement à ce sujet.

La première est que l'alternative mesurée n'était pas « un classement exact un peu plus lent »,
mais une page qui ne s'affiche pas. Une page absente n'a pas d'ordre du tout.

La deuxième est que les marchés rendus ne sont pas quelconques. La table étant écrite par date
décroissante, les 5 000 premiers candidats sont en pratique les plus récents. Pour une question
d'un seul mot très courant, « les plus récents qui contiennent ce mot » est même une réponse plus
utile que « les mieux classés », le score de proximité ne distinguant presque rien quand il n'y a
qu'un mot à situer. Mais il faut noter que cette propriété repose sur la façon dont le chargeur
écrit les lignes, et non sur une garantie du modèle relationnel : c'est une dépendance réelle,
mesurée par la corrélation de -0,96 entre l'ordre physique et l'année, et vérifiée par un test.

La troisième n'est pas négociable : **il faut le dire**. Chaque réponse de recherche porte un
champ `classement_approche` et le nombre de candidats réellement classés, et l'interface l'écrit à
l'écran. Une approximation annoncée est une limite connue ; une approximation silencieuse est un
mensonge sur la donnée. C'est la même exigence que celle qui gouverne l'assistant au chapitre 9 :
un résultat doit porter de quoi le vérifier.

### 10.1.5 Sécurité : ce qui est refusé par construction

Les mesures occupent l'essentiel de cette section parce que ce sont elles qui ont changé le code.
La sécurité, elle, n'a rien changé après coup : elle est posée dès l'écriture, et c'est précisément
ce qu'on attend d'elle.

Quatre défenses méritent d'être décrites, parce qu'elles ne relèvent pas de la bonne volonté mais
de la structure.

**Aucune valeur fournie par un visiteur n'entre dans le texte d'une requête.** Seule la structure
de la requête est composée, à partir de fragments écrits dans le projet, et les valeurs restent des
paramètres. Ce n'est pas une discipline mais une propriété vérifiable : un test parcourt les
fichiers de l'API et échoue si une ligne mêle un mot-clé SQL et une chaîne formatée.

**Les connexions sont ouvertes en lecture seule.** Une route qui tenterait une écriture, par erreur
ou par détournement, serait refusée par la base elle-même. L'API ne peut pas modifier les données
qu'elle sert, quelle que soit la requête reçue.

**Chaque requête est abandonnée au-delà de dix secondes.** Sans ce plafond, une requête
pathologique garde indéfiniment une connexion et un fil d'exécution : le service devient
indisponible sans être tombé, ce qui est le mode de panne le plus difficile à diagnostiquer. Ce
même plafond est ce qui a révélé trois des quatre défauts de la section 10.1.2, en transformant une
lenteur en erreur visible.

**Les messages d'erreur de la base ne sortent jamais.** Un message de l'interface PostgreSQL
contient le texte de la requête, parfois l'hôte et le nom de l'utilisateur. Il part dans le journal
du serveur, et le visiteur reçoit un code et une phrase.

S'y ajoutent les bornes sur chaque entrée, toutes testées une par une, et les en-têtes de sécurité
posés par le service lui-même plutôt que par le serveur placé devant lui, pour qu'il reste sain même
testé en direct.

Deux absences sont volontaires et seront traitées en phase 9. Il n'y a **pas de limitation de
débit** dans le code : un compteur en mémoire serait remis à zéro à chaque redémarrage, compterait
faux dès qu'il y a plus d'un processus, et devrait faire confiance à un en-tête que n'importe qui
peut écrire. Le filtrage par adresse appartient à celui qui voit la vraie adresse, c'est-à-dire au
serveur frontal. Et il n'y a **pas d'authentification** sur ces routes, parce que les données
servies sont publiques par nature ; l'espace d'administration, lui, en aura une, et c'est la raison
pour laquelle il est construit comme un ensemble de routes séparées.
