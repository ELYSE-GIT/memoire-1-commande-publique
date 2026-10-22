# base/reference

Les nomenclatures officielles dont le projet a besoin pour afficher ses donnees en francais.

Elles ne sont pas des donnees collectees : elles ne changent pas d'une collecte a l'autre, elles
sont courtes, et elles doivent etre relisibles dans une revue de code. Elles sont donc
versionnees ici, en CSV, plutot que recuperees par un script ou ecrites en dur dans le code.

| Fichier | Contenu | Source |
|---|---|---|
| `familles-cpv.csv` | les 45 divisions du vocabulaire commun pour les marches publics (CPV), plus une heritee de la version 2003 | reglement (CE) n° 213/2008, nomenclature CPV 2008 |

## `familles-cpv.csv`

La colonne `famille_cpv` de la table `marches` contient les **deux premiers chiffres** d'un code
CPV, soit sa division. Sans ce fichier, le site afficherait « CPV 45 » et « CPV 71 », ce qui ne
veut rien dire pour qui ne connait pas la nomenclature, et un jury n'a aucune raison de la
connaitre.

Trois colonnes :

- `code` : la division, sur deux caracteres, le zero initial compris (`03` et non `3`).
- `libelle` : le libelle, **abrege**. Les libelles officiels font jusqu'a deux cents caracteres
  (« Meubles (y compris les meubles de bureau), amenagements, appareils electromenagers (a
  l'exclusion de l'eclairage) et produits de nettoyage ») et sont illisibles dans un tableau.
  L'abregement est assume et declare ici, plutot que silencieux.
- `libelle_court` : deux a trois mots, pour les axes de graphique et les etiquettes.

Un test verifie que **chaque division presente dans les donnees chargees a son libelle**. Une
division qui apparaitrait sans entree ici s'afficherait « Division 12 », ce qui est honnete mais
signale un fichier a completer.

### La division 74, et ce qu'elle apprend sur les donnees

Elle ne fait pas partie de la nomenclature 2008 : c'est l'ancien code des services
d'architecture et d'ingenierie, remplace par le 71 le 15 septembre 2008. Elle est pourtant
presente sur **4 539 marches** des donnees chargees, notifies bien apres cette date. Elle figure
donc ici, avec un libelle qui dit d'ou elle vient, plutot que d'etre affichee « Division 74 » ou
silencieusement rangee avec le 71 : fusionner deux codes parce qu'ils designent la meme chose
serait une decision de nettoyage, et le nettoyage se fait dans la couche de transformation, pas
dans un fichier de libelles.

### Les codes qui ne sont pas des divisions

La colonne `famille_cpv` contient **91 valeurs distinctes**, alors que ce fichier en nomme 46.
Les 45 autres (`00`, `01`, `11`, `99`...) ne correspondent a aucune division, ni de 2008 ni de
2003 : ce sont des codes CPV mal saisis a la source. Elles portent **9 898 attributions, soit
0,50 %** des donnees chargees, mesure du 22 octobre 2026.

Elles ne sont pas supprimees et ne sont pas renommees. Le site les laisse hors du menu de
recherche, qui ne propose que des familles ayant un sens, et la page « a propos » dit combien
elles representent. Une donnee fausse qu'on cache est une donnee fausse qu'on ne corrigera
jamais.

### Ce qui n'est pas ici, et pourquoi

Les codes CPV complets, a huit chiffres : il y en a environ 9 500, la colonne `code_cpv` de la
table les conserve, et le projet n'affiche jamais ce niveau de detail. Le jour ou il le ferait,
ce serait un fichier a part, charge dans la base plutot que lu a chaque demarrage.
