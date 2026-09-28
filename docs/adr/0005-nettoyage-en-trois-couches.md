# ADR 0005. Le nettoyage en trois couches, avec dbt

- Date : 2026-09-28
- Statut : accepte
- Phase : 4, nettoyage

## Contexte

La phase 2 a mesure ce que contiennent reellement les donnees : le total annuel brut est faux d'un
facteur dix a vingt, 59 588 montants sont negatifs ou nuls, la date la plus ancienne remonte au
1er janvier de l'an 1, et le meme concept s'ecrit de douze facons selon la source.

Il faut donc nettoyer. Trois questions se posent avant d'ecrire la premiere regle :

1. **Ou nettoyer ?** Dans le code de l'application, ou dans une couche de donnees dediee ?
2. **Avec quoi ?** Du SQL ecrit a la main, ou un outil de transformation ?
3. **Que faire des lignes fautives ?** Les supprimer, ou les conserver en les marquant ?

## Decision

**Trois couches, construites par dbt, et aucune ligne supprimee.**

| Couche | Promesse | Materialisation | Volume mesure |
|---|---|---|---|
| **bronze** | la donnee telle que la source l'a publiee. Aucune correction, aucun filtre | vue | 3 296 811 lignes, 66 colonnes |
| **argent** | nettoyee et normalisee, problemes **marques** et non retires | table | 2 121 908 lignes, 79 colonnes |
| **or** | prete a servir, ne contient que l'exploitable | table | 1 999 474 lignes, 29 colonnes |

Le passage de bronze a argent retire 1,17 million de lignes, qui sont l'historique des avenants :
la couche argent ne porte que l'etat actuel de chaque marche. Le passage d'argent a or en retire
122 434 de plus, qui sont les lignes inexploitables pour une analyse de prix, **et qui restent
consultables en argent avec le motif de leur exclusion**.

### Marquer plutot que supprimer

C'est la decision la plus structurante de cet ADR.

Chaque ligne de la couche argent conserve ses valeurs d'origine et recoit neuf colonnes de
qualite, plus une colonne `motifs_rejet` qui liste en clair les regles enfreintes.

| Regle | Lignes marquees | Part |
|---|---|---|
| Montant present et positif | 66 984 | 3,157 % |
| Montant non signale par le producteur | 54 926 | 2,589 % |
| Montant sous le milliard d'euros | 33 328 | 1,571 % |
| SIRET du titulaire conforme | 27 115 | 1,278 % |
| Nombre d'offres credible | 5 573 | 0,263 % |
| Duree inferieure a vingt ans | 2 029 | 0,096 % |
| Date de notification possible | 515 | 0,024 % |
| Code CPV conforme a la nomenclature | 508 | 0,024 % |
| SIRET de l'acheteur conforme | 337 | 0,016 % |

**Trois raisons de marquer plutot que de supprimer :**

1. Une ligne effacee ne peut plus etre expliquee. Devant un jury, « nous avons retire 122 434
   lignes » appelle immediatement « lesquelles, et pourquoi », et la reponse doit exister.
2. Une ligne effacee ne peut plus etre corrigee par l'administration qui l'a publiee. Le projet
   peut, a terme, signaler a un acheteur que ses donnees sont fautives : encore faut-il les avoir.
3. Une regle peut etre mauvaise. Le seuil d'un milliard est un choix, discutable : le conserver
   comme un marquage permet de le changer et de tout rejouer, ce qu'une suppression interdit.

### Les seuils ne sont pas ronds par hasard

| Seuil | Valeur | Origine |
|---|---|---|
| Montant maximal | 1 milliard d'euros | le plus gros marche public francais reel se compte en centaines de millions |
| Date minimale | 2015 | anterieure a l'obligation de publication de 2018, donc large |
| Duree maximale | 240 mois | vingt ans, ce qui laisse passer les concessions longues |
| Offres maximales | 500 | les marches les plus concurrentiels en recoivent quelques dizaines |

Chacun est un parametre du modele SQL, commente a l'endroit ou il s'applique, et non une valeur
enfouie dans du code.

## Alternatives examinees

### Ou nettoyer

| Option | Pour | Contre | Verdict |
|---|---|---|---|
| **Une couche de donnees dediee** | une seule definition des regles, verifiable et mesurable | une etape de plus dans la chaine | **retenu** |
| Dans le code de l'API | immediat, rien a construire | chaque service refait le nettoyage a sa facon, les chiffres divergent | non |
| Dans les notebooks d'analyse | souple | rien n'est reutilisable, et le site ne beneficie de rien | non |

### Avec quel outil

| Option | Pour | Contre | Verdict |
|---|---|---|---|
| **dbt** | SQL pur, tests de donnees integres, documentation et graphe de dependances automatiques, change de moteur sans reecrire | une dependance, et un vocabulaire a apprendre | **retenu** |
| SQL et un lanceur maison | aucune dependance, controle total | il faudrait reecrire les tests de donnees, la documentation et le graphe : c'est exactement ce que dbt fournit | ecarte |
| SQLMesh | plus moderne, gere mieux l'incrementiel | communaute plus petite, moins de documentation, et le besoin d'incrementiel n'est pas demontre | a reconsiderer |
| pandas ou polars en Python | familier | la transformation quitte le SQL, donc le moteur ne peut plus l'optimiser, et on perd la lisibilite pour un relecteur non developpeur | non |

**Le raisonnement** : la question n'est pas « dbt est-il bon » mais « qu'est-ce que je devrais
ecrire sans lui ». La reponse est : un lanceur, un systeme de tests de donnees, une generation de
documentation et un graphe de dependances. C'est plusieurs semaines de travail pour refaire moins
bien. **C'est la premiere fois dans ce projet qu'un outil est adopte plutot qu'ecarte**, et c'est
parce que le calcul penche nettement de son cote.

Ce choix a une consequence qui vaut d'etre dite : dbt sait executer les memes modeles sur DuckDB
et sur PostgreSQL. La phase 7 pourra donc servir le site depuis PostgreSQL sans reecrire une seule
regle de nettoyage, et le portage sera mesure.

## Consequences

**Positives**

- Les neuf regles sont ecrites en SQL commente, lisibles par un relecteur qui n'est pas developpeur.
- L'effet de chaque regle est mesure et publie : `make bench-nettoyage`, figure 18.
- Vingt tests d'integration executent la vraie chaine sur un jeu fictif de quinze lignes dont
  chaque defaut est connu d'avance. Ils ont attrape deux erreurs pendant l'ecriture.
- Les tests de donnees de dbt tournent sur le vrai jeu et ont trouve deux defauts reels : six
  lignes sans SIRET ni nom d'acheteur, et 244 codes CPV remplis en texte libre.

**Negatives et limites**

- La couche argent occupe 79 colonnes contre 66 en bronze : le marquage a un cout en place.
- La chaine complete prend environ six secondes sur ce Mac. Ce sera a remesurer sur le VPS.
- **La severite d'un test doit correspondre a la promesse de sa couche.** Le premier contrat
  ecrit exigeait un SIRET non nul en couche argent, ce qui contredisait la promesse de tout
  conserver. Corrige en avertissement, et la regle stricte a ete placee en couche or.

## A mesurer ensuite

1. La duree de la chaine sur le VPS, comparee au Mac.
2. Le cout du portage vers PostgreSQL en phase 7 : combien de modeles demandent une adaptation.
3. L'effet du seuil d'un milliard : combien de marches reels se situent entre 100 millions et
   1 milliard, et sont donc conserves a juste titre.
