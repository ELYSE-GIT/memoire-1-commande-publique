# ADR 0008. PostgreSQL pour servir la recherche, et DuckDB mesure contre lui

- Date : 2026-10-11
- Statut : accepte
- Phase : 6, recherche et assistant
- Decide par : Elyse, le 2 octobre 2026

## Contexte

Jusqu'a la phase 6, le projet n'avait **aucun service**. DuckDB est une bibliotheque chargee dans
le processus Python : rien n'ecoute sur un port, rien ne tourne apres la fin d'une commande, et la
reproductibilite etait deja assuree par `uv.lock` et `.python-version`. C'est pour cette raison
qu'il n'y avait ni `compose.yaml`, ni conteneur, ni Dockerfile.

La phase 6 change cela : le site devra repondre a plusieurs visiteurs en meme temps, ce qu'un
fichier DuckDB ouvert par un seul processus ne sait pas faire.

## Decision

**Servir la recherche depuis PostgreSQL, en conteneur, des la phase 6.**

### La tension, enoncee plutot que cachee

Cette decision a ete prise **avant** d'avoir mesure que DuckDB ne suffisait pas. C'est l'inverse
du principe de l'escalier applique partout ailleurs dans le projet, et un jury attentif peut le
relever.

L'argument retenu, celui d'Elyse : les latences mesurees sur PostgreSQL seront les vraies, celles
du VPS. Mesurer DuckDB pour deployer PostgreSQL aurait produit des chiffres sans rapport avec la
production.

La contrepartie, posee en meme temps que la decision : **`make bench-recherche` mesure les deux
moteurs sur les memes questions**, pour que la comparaison existe. Les resultats sont plus bas, et
ils sont publies quel que soit leur verdict.

## Le protocole

Trente questions de test, versionnees dans `mesures/verification/questions-de-recherche.csv`,
ecrites a partir du vocabulaire reellement present dans les donnees, avec des types varies :
mots cles, nom d'acheteur, nom d'entreprise, lieu, annee, montant, paraphrase, faute de frappe,
absence d'accents, et une question qui ne doit **rien** trouver.

Six repetitions par question, la premiere jetee parce qu'elle paie le remplissage des caches, et
mediane retenue plutot que moyenne.

Deux choix independants sont mesures separement, parce que les melanger n'aurait rien dit :

| | Ce que ca fait |
|---|---|
| tous les mots | precis, mais reste muet quand un seul mot manque |
| au moins un mot | repond toujours, parfois n'importe quoi |

### Mettre les deux moteurs a egalite

DuckDB ne fournit aucune liste de mots vides francaise. Sans correction il indexerait « de »,
« la », « pour », ce qui changerait ses scores. Le banc lui donne donc **la liste de PostgreSQL**,
copiee du conteneur dans `mesures/mots-vides-francais.txt`, plus le meme racineur francais et le
meme retrait des accents.

Sans cette precaution, on mesurerait une difference de configuration en croyant mesurer une
difference de moteur.

## Les mesures

Le 11 octobre 2026, sur 1 999 474 marches, `make bench-recherche` :

| Moteur | Questions sans reponse | Resultats moyens | Latence mediane | 95e centile |
|---|---|---|---|---|
| PostgreSQL, tous les mots | 9 sur 30 | 6,0 | **4,0 ms** | 24,8 ms |
| PostgreSQL, au moins un mot | 0 | 10,0 | 1 920 ms | 6 315 ms |
| **PostgreSQL, les deux en cascade** | **0** | 9,0 | **8,0 ms** | 4 808 ms |
| DuckDB, question non nettoyee | 29 sur 30 | 0,2 | 105 ms | 161 ms |
| DuckDB, tous les mots | 10 sur 30 | 5,7 | 106 ms | 151 ms |
| DuckDB, au moins un mot | 0 | 10,0 | 131 ms | 225 ms |

**Ces latences ne sont pas reproductibles au chiffre pres**, contrairement aux mesures de
precision du projet. Deux executions du meme banc donnent 1 461 ms puis 1 920 ms pour la requete
large : une latence depend de l'etat des caches, du disque et de ce qui tourne par ailleurs sur la
machine. Ce qui est reproductible, et ce sur quoi la decision repose, est **l'ordre de grandeur et
le classement** : quelques millisecondes contre une centaine, contre plus d'une seconde.
Le nombre de questions sans reponse, lui, est stable.

### Le cout

| Element | Taille | Duree de construction |
|---|---|---|
| Table servie PostgreSQL | 1 453 Mo | 77 s de chargement |
| Index plein texte PostgreSQL (GIN) | 120 Mo | 62 s pour les 12 index |
| Table et index plein texte DuckDB | **312 Mo** | 21 s |

## Ce que la mesure a appris

### 1. PostgreSQL est vingt-cinq fois plus rapide, et la decision se trouve justifiee apres coup

4,0 millisecondes contre 106. L'ecart ne vient pas d'un reglage mais de la nature des deux
moteurs : PostgreSQL consulte un index inverse et ne lit que les lignes candidates, tandis que la
recherche plein texte de DuckDB evalue sa fonction de score sur les deux millions de lignes.

La decision prise avant la mesure se trouve donc confirmee par elle. Il faut le dire dans cet
ordre, et pas l'inverse.

### 2. DuckDB occupe cinq fois moins de place

312 Mo contre 1 573 Mo. Pour un site a faible trafic, DuckDB aurait tenu : 106 millisecondes est
une latence acceptable pour une recherche. Le choix de PostgreSQL se justifie par la concurrence
entre visiteurs, pas par la vitesse pure.

### 3. La cascade est la bonne strategie, et c'est l'escalier applique a la recherche

« Tous les mots » repond en 4 millisecondes mais laisse 9 questions sur 30 sans reponse, soit
presque un tiers. « Au moins un mot » repond toujours mais coute plus d'une seconde, parce qu'il
designe des centaines de milliers de lignes qu'il faut ensuite toutes classer.

Les enchainer donne **8 millisecondes de mediane et aucun silence** : on paie le prix du second
seulement quand le premier n'a rien trouve.

**Limite a enoncer** : le 95e centile de la cascade reste a 4,8 secondes, parce que les neuf
questions concernees paient le prix entier. C'est inacceptable en production et cela sera traite
en phase 7, en bornant la requete large par un filtre structure avant le classement.

### 4. Une erreur de protocole qui aurait produit une conclusion fausse

La premiere version du banc donnait a DuckDB la question telle que l'utilisateur la tape. Resultat
« mesure » : **muet sur 29 questions sur 30**, contre 9 pour PostgreSQL. La conclusion facile
etait ecrite : DuckDB cherche mal.

Diagnostic : DuckDB retire les mots vides du **texte indexe**, mais pas de la **question posee**.
En mode conjonctif il exige donc un mot qu'il a lui-meme supprime de l'index.

| Question | Sans nettoyage | Mots vides retires |
|---|---|---|
| « travaux de voirie » | 0 resultat | 20 569 resultats |
| « entretien des espaces verts » | 7 resultats | 30 263 resultats |

Une fois la question nettoyee comme PostgreSQL le fait lui-meme, DuckDB reste muet sur 10
questions contre 9 : les deux moteurs sont alors **equivalents sur ce critere**. La difference
observee ne venait pas du moteur mais du protocole.

Les deux versions restent mesurees dans `recherche-par-moteur.csv`, pour que l'ecart soit lisible
plutot que raconte. C'est la troisieme fois dans ce projet qu'un resultat spectaculaire se revele
etre une erreur de mesure, apres le modele a 0 % de l'ADR 0007 et l'echantillon des 150 plus gros
titulaires de la phase 2.

### 5. Deux PostgreSQL sur le meme port

Au premier demarrage, la connexion echouait avec « role commande_publique does not exist », alors
que le conteneur fonctionnait parfaitement. Un PostgreSQL deja installe sur le Mac occupait le
port 5432 : les connexions du projet tombaient sur lui.

La base du projet ecoute donc sur **55432** cote machine, et toujours 5432 a l'interieur du
conteneur. Decaler le port du projet evite de toucher a une installation qui sert peut-etre a
autre chose.

### 6. Les donnees publiques ne fournissent aucune cle de ligne

Mesure sur la couche or, avant d'ecrire le schema :

| | |
|---|---|
| lignes | 1 999 474 |
| `marche_id` distincts | 1 738 289 |
| couples `marche_id` et titulaire distincts | 1 992 358 |
| lignes strictement identiques | 136 |

Aucune colonne, ni aucune combinaison, n'identifie une ligne. Le schema fabrique donc une cle
technique, et **aucune contrainte de cle etrangere** ne peut etre posee entre `marches` et
`signaux`. C'est un fait sur la donnee, pas un choix technique.

## Alternatives examinees

| Option | Pour | Contre | Verdict |
|---|---|---|---|
| **PostgreSQL en conteneur** | ce qui tournera sur le VPS, plusieurs lecteurs, recherche plein texte et pgvector dans le meme moteur | une VM Linux a demarrer, 1 573 Mo sur disque | **retenu** |
| Rester sur DuckDB | zero service, 312 Mo, deja en place | un seul processus lecteur, donc inutilisable par un site ; 100 ms contre 4 ms | ecarte, mais **mesure** : il aurait tenu pour un site a faible trafic |
| PostgreSQL installe a la main sur le Mac | pas de conteneur | ne ressemble en rien au VPS, rien de reproductible, et le port etait deja pris | ecarte |
| Elasticsearch, Meilisearch ou Qdrant | concus pour la recherche | un service de plus a exploiter, a securiser et a sauvegarder, pour un besoin que PostgreSQL couvre a 4 ms | ecarte, a reconsiderer si la mesure le reclame |
| SQLite avec FTS5 | un fichier, pas de serveur, FTS5 est excellent | ecriture concurrente limitee, et pas de type vectoriel natif pour la suite | ecarte |

## Consequences

**Positives**

- La latence de recherche est connue et basse : 8 ms de mediane avec la cascade.
- pgvector est deja installe, donc la montee vers la recherche par similarite ne demandera aucun
  service supplementaire. **Aucune colonne vectorielle n'est creee tant que la mesure n'a pas
  montre que les mots cles ne suffisent pas.**
- L'infrastructure du VPS est en place et versionnee : image figee par empreinte, secrets hors du
  depot, port sur la boucle locale seulement, plafonds de memoire et de processeur.
- Le choix contesté est desormais adosse a une mesure publiee.

**Negatives et limites, a enoncer dans le memoire**

- **Le 95e centile de la cascade est a 4,8 secondes.** A corriger en phase 7.
- Le projet a maintenant un service a demarrer et a arreter. La regle de sobriete devient une
  discipline : `make down` et `make vm-down` en fin de session.
- 1 573 Mo sur disque contre 312 Mo pour DuckDB, soit cinq fois plus pour le meme contenu.
- La pertinence de la recherche **n'est pas encore mesuree**. Le banc prepare
  `recherche-resultats.csv` avec une colonne a remplir a la main, sur le meme protocole que les
  soixante paires du rapprochement. Tant qu'il n'est pas rempli, on mesure la vitesse et le
  silence, pas la qualite.

## A mesurer ensuite

1. **La pertinence**, par jugement humain des dix premiers resultats sur dix questions.
2. L'effet des index trigrammes sur les fautes de frappe : combien de questions ils rattrapent,
   pour 209 Mo d'index.
3. Le plafonnement de la requete large, pour ramener le 95e centile sous la seconde.
4. Les embeddings, **seulement si** les mesures 1 et 2 laissent des questions sans reponse
   correcte. Le corpus fait 1 236 294 objets distincts, et l'index vectoriel demanderait 2 a 4 Go
   selon le modele : le choix dependra de la RAM du VPS, encore inconnue.
