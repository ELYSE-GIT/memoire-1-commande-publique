# 2026-10-11. Servir la recherche : PostgreSQL arrive dans le projet

## Objectif

Rendre les deux millions de marches cherchables, et tenir la contrepartie posee avec la decision :
mesurer DuckBD contre PostgreSQL sur les memes questions, puisque le choix de PostgreSQL a ete
fait avant d'avoir mesure qu'il etait necessaire.

## Ce qui a ete fait

- `compose.yaml`, le premier du projet : PostgreSQL 17 avec pgvector, image figee par empreinte,
  secrets hors du depot, port sur la boucle locale seulement, plafonds de 2 processeurs et 3 Go.
- `base/schema/` en cinq fichiers : extensions, configuration plein texte francaise, deux tables,
  index a part.
- `services/publication/vers_postgres.py` et `make charger`.
- `mesures/recherche.py` et `make bench-recherche` : six moteurs compares.
- Trente questions de test versionnees, et le fichier de jugement a remplir a la main.
- Figure 20, ADR 0008, 17 tests de plus, 133 au total.

## Le resultat

| Moteur | Sans reponse | Latence mediane | 95e centile |
|---|---|---|---|
| PostgreSQL, tous les mots | 9 sur 30 | **4,0 ms** | 24,8 ms |
| PostgreSQL, au moins un mot | 0 | 1 920 ms | 6 315 ms |
| **PostgreSQL, en cascade** | **0** | **8,0 ms** | 4 808 ms |
| DuckDB, tous les mots | 10 sur 30 | 106 ms | 151 ms |
| DuckDB, au moins un mot | 0 | 131 ms | 225 ms |

PostgreSQL est vingt-cinq fois plus rapide. DuckDB occupe cinq fois moins de place : 312 Mo contre
1 573 Mo. Pour un site a faible trafic, DuckDB aurait tenu.

## Difficultes rencontrees

### 1. Deux PostgreSQL sur le meme port, et une erreur qui accuse le mauvais coupable

Le chargement echouait sur `role "commande_publique" does not exist`, alors que la meme commande
lancee **dans** le conteneur fonctionnait parfaitement et que le role existait.

Un `lsof -nP -iTCP:5432 -sTCP:LISTEN` a tranche en une ligne : un PostgreSQL installe sur le Mac
occupait deja le port. Les connexions du projet tombaient sur lui, et son message d'erreur
decrivait **sa** base, pas la notre.

Correction : la base du projet ecoute sur 55432 cote machine, toujours 5432 a l'interieur du
conteneur. Je n'ai pas touche a l'installation existante, qui sert peut-etre a autre chose.

**Lecon** : quand un message d'erreur decrit quelque chose d'impossible, verifier d'abord a qui
l'on parle. Et un service installe sur une machine de developpement est un piege tant qu'on ne
sait pas qu'il est la.

### 2. Les donnees publiques ne fournissent aucune cle de ligne

Avant d'ecrire `create table`, j'ai verifie l'unicite plutot que de la supposer. C'etait la lecon
de la session precedente, ou `uid` avait rendu une mesure non reproductible.

| | |
|---|---|
| lignes de la couche or | 1 999 474 |
| `marche_id` distincts | 1 738 289 |
| couples `marche_id` et titulaire | 1 992 358 |
| lignes strictement identiques | 136 |

Aucune colonne n'identifie une ligne, et aucune combinaison non plus. Le schema fabrique donc une
cle technique, et **aucune contrainte de cle etrangere n'est possible** entre les deux tables.

**Lecon** : la verification coute une requete et evite de batir un schema sur une supposition.

### 3. Une erreur de protocole qui donnait une conclusion fausse

Premiere version du banc : DuckDB paraissait muet sur **29 questions sur 30**, contre 9 pour
PostgreSQL. La conclusion s'ecrivait d'elle-meme, et elle etait fausse.

Diagnostic, en comparant question par question : DuckDB retire les mots vides du **texte indexe**
mais pas de la **question posee**. En mode conjonctif il exige donc un mot qu'il a lui-meme
supprime. PostgreSQL, lui, les retire des deux cotes.

| Question | Sans nettoyage | Mots vides retires |
|---|---|---|
| « travaux de voirie » | 0 resultat | 20 569 resultats |
| « entretien des espaces verts » | 7 resultats | 30 263 resultats |

Une fois la question nettoyee comme PostgreSQL le fait, DuckDB reste muet sur 10 questions contre
9 : les deux moteurs sont **equivalents sur ce critere**. L'ecart venait du protocole.

Les deux versions restent dans les mesures publiees, pour que l'ecart se lise.

**Lecon** : comparer deux outils exige de leur donner la meme chose. C'est la troisieme fois dans
ce projet qu'un resultat spectaculaire se revele etre une erreur de mesure.

### 4. Le mode « au moins un mot » coute plus d'une seconde

1 920 ms de mediane, 6 315 ms au 95e centile. La cause est mecanique : une requete large designe
des centaines de milliers de lignes, et il faut les classer toutes avant d'en rendre dix.

Correction, et c'est l'escalier applique a la recherche : **enchainer les deux**. « Tous les
mots » d'abord, « au moins un mot » seulement si le premier n'a rien trouve. Resultat, 8 ms de
mediane et plus aucun silence.

Limite qui reste, et qu'il faut dire : le 95e centile de la cascade est a 4,8 secondes, parce que
les neuf questions concernees paient le prix entier. A corriger en phase 7 en bornant la requete
large par un filtre structure.

### 5. Trois outils, trois syntaxes, et une dependance evitee

- `attach` de DuckDB n'accepte pas de parametre lie, donc la seule facon de designer un fichier
  serait d'assembler du SQL par formatage de chaine. Le depot l'interdit et son analyse de
  securite le bloque. Contourne en passant par l'API Python et un tableau pandas enregistre.
- `pyarrow` aurait ete plus direct : quarante megaoctets de dependance pour un transfert ponctuel,
  ecarte au profit de pandas, deja present.
- `create_fts_index` de DuckDB veut `stemmer = 'french'` avec un signe egal, mais `match_bm25`
  veut `conjunctive := 1` avec deux points. Trouve en essayant les deux.

### 6. Une latence ne se mesure pas comme une precision

Deux executions du meme banc, sur les memes donnees, donnent 1 461 puis 1 920 millisecondes pour
la requete large. Rien n'a change : une latence depend de l'etat des caches, du disque et de ce
qui tourne par ailleurs sur la machine.

C'est a dire franchement, parce que le projet s'est battu la session precedente pour obtenir une
mesure **reproductible au bit pres** sur la detection. Les deux exigences ne sont pas les memes :

| Type de mesure | Reproductible ? | Ce sur quoi on s'appuie |
|---|---|---|
| precision, nombre de signaux, taille d'index | oui, a l'identique | le chiffre lui-meme |
| latence | non, variation de 30 % constatee | l'ordre de grandeur et le classement |

La decision ne repose donc pas sur « 4,0 contre 106 » mais sur « quelques millisecondes contre une
centaine ». Le nombre de questions restees sans reponse, lui, est stable d'une execution a l'autre.

## A savoir expliquer devant le jury

- Pourquoi le projet n'avait aucun conteneur avant la phase 6, et pourquoi il en a un maintenant.
- Pourquoi une colonne generee plutot qu'un declencheur pour l'index plein texte.
- Pourquoi la configuration plein texte francaise de PostgreSQL ne suffit pas, et ce qu'ajoute
  `unaccent` : la preuve est affichee par `make base-init`, les deux formes donnent le meme index.
- Pourquoi les index sont construits apres le chargement et non avant.
- Pourquoi l'index partiel sur les signaux fait 408 ko la ou un index complet en ferait quarante
  fois plus.
- Pourquoi la pertinence de la recherche n'est pas encore mesuree, et ce qu'il faut pour la
  mesurer.
- Pourquoi une latence ne se cite pas au chiffre pres, alors qu'une precision si.

## Prochaine etape

Juger a la main les dix premiers resultats de dix questions, pour obtenir la premiere mesure de
pertinence. Puis decider, sur mesure, s'il faut monter aux embeddings.
