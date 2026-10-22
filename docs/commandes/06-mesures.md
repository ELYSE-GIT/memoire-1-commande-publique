# 06. Les mesures et les bancs d'essai

Chaque choix technique du projet est mesure, pas affirme. Ce fichier liste les commandes qui
produisent ces mesures, dans l'ordre ou on les lance.

Toutes tournent **sur le Mac**. Aucune ne demande le VPS, aucune n'a besoin d'Internet sauf
`bench-rapprochement`, qui interroge l'API du BOAMP.

Les resultats vont dans `mesures/resultats/` en CSV. Les figures du memoire sont tracees **a partir
de ces fichiers**, jamais saisies a la main : c'est ce qui garantit qu'un chiffre affiche dans le
memoire existe dans un fichier que l'on peut ouvrir.

## Avant tout : avoir les donnees

```bash
make donnees-decp        # telecharge les DECP consolidees, environ 250 Mo
make transformer         # construit les couches argent et or, et les variables de detection
```

**Duree** : quelques minutes pour le telechargement, environ 6 secondes pour la transformation.

---

## La carte des bancs d'essai

| Commande | Ce qu'elle mesure | Duree | Sortie |
|---|---|---|---|
| `make bench-decp` | qualite et performance de lecture du jeu DECP | environ 30 s | `decp-qualite.csv` |
| `make bench-decp-distributions` | agregats descriptifs : montants, dates, familles, acheteurs | environ 40 s | une dizaine de CSV |
| `make bench-nettoyage` | effet de chaque regle de nettoyage, couche par couche | environ 10 s | `nettoyage-couches.csv`, `nettoyage-regles.csv` |
| `make bench-detection` | precision et rappel de la regle de prix, par seuil | environ 15 s | `detection-seuils.csv` |
| `make bench-modele` | les regles contre un modele, a budget d'alertes egal | environ 30 s | `modele-vs-regles.csv`, `-cout.csv` |
| `make bench-rapprochement` | part des avis du BOAMP reliables aux DECP | environ 3 min | `*-rapprochement-boamp-decp.csv` |
| `make bench-precision` | justesse du rapprochement, par relecture de 60 paires | environ 5 s | `rapprochement-precision.csv` |
| `make bench-incertitude` | intervalle de confiance de chaque pourcentage tire d'un echantillon | environ 1 s | `incertitude-*.csv` |
| `make bench-stabilite` | la regle de detection calee sur 2019-2023, appliquee a 2024-2026 | environ 2 s | `stabilite-*.csv` |
| `make bench-api` | l'API publique, route par route, puis sous charge | environ 4 min | `api-latences.csv`, `api-charge.csv`, `api-classement.csv`, `api-resume.csv` |
| `make bench-site` | le site : poids de chaque page, gain du fragment, rendu sans JavaScript | environ 1 min | `site-pages.csv`, `site-fragments.csv`, `site-statique.csv`, `site-resume.csv` |
| `make figures` | trace les 25 figures du memoire depuis les CSV | environ 5 s | `memoire/figures/` |

---

## `make bench-decp`

**Ce que ca fait** : lit le jeu DECP et mesure ce qu'il coute et ce qu'il vaut. Taille sur disque
en Parquet contre CSV, duree de lecture, memoire utilisee, taux de remplissage de chaque colonne.

**Resultat attendu** : 247,6 Mo en Parquet contre 2 595,5 Mo en CSV, soit dix fois moins.

---

## `make bench-decp-distributions`

**Ce que ca fait** : calcule tous les agregats descriptifs qui alimentent les figures 1 a 15.
Montants par tranche, saisonnalite, familles CPV, concentration des titulaires, completude des
champs, distances geographiques.

**Resultat attendu** : une dizaine de CSV dans `mesures/resultats/`. Le plus parlant :
`total-annuel.csv`, qui montre 3 030 Md€ en brut contre 233 Md€ apres nettoyage.

---

## `make bench-nettoyage`

**Ce que ca fait** : mesure l'effet de chacune des neuf regles de nettoyage, et ce que chaque
couche retient. Aucune ligne n'est supprimee : les problemes sont **marques**, et cette commande
compte les marques.

**Resultat attendu** : 3 296 811 lignes brutes, 2 121 908 a l'etat actuel, 1 999 474 exploitables,
soit 94,2 %.

---

## `make bench-detection`

**Ce que ca fait** : evalue la regle de prix contre les montants que le producteur des donnees
signale lui-meme, pour plusieurs seuils et dans les deux directions.

**Resultat attendu** : 75,8 % de precision au seuil 4 dans la direction « trop cher », et **0,0 %**
dans la direction « trop bas ». Ce zero n'est pas un echec : il dit que l'etiquette ne sait rien de
ce cas, donc qu'on ne peut pas le valider. Le signal existe quand meme, avec la mention
« non evalue ».

**La precision affichee est un minorant**, parce que l'etiquette est elle-meme produite par un
detecteur : un marche que nous signalons sans qu'il l'ait signale peut etre une anomalie qu'il a
manquee.

---

## `make bench-modele`

**Ce que ca fait** : compare quatre methodes de detection a budget d'alertes egal. La regle, un
Isolation Forest laisse libre, le meme oriente vers les montants eleves, et un tirage aleatoire qui
sert de garde-fou.

**Resultat attendu** :

```
  budget    regle    modele    oriente    hasard
     100    96.0 %     0.0 %     73.0 %     2.0 %
    1000    96.1 %     0.0 %     65.7 %     3.1 %
   10000    73.3 %     1.7 %     70.9 %     2.7 %
```

**Comment le lire** : le modele laisse libre est **sous le hasard**, parce qu'il cherche les
montants anormalement bas, que l'etiquette ne marque jamais. Oriente du meme cote que la regle,
sans rien reapprendre, il remonte a 73 %. Et il ne depasse jamais la regle.

Le detail des dix methodes comparees, les metriques et les fausses pistes sont dans
`analyses/08-modelisation-detection.ipynb`. La decision est tracee dans l'ADR 0007.

**Attention a la reproductibilite** : ce script trie ses lignes avant de calculer. Sans ce tri,
deux lancements donnent deux resultats, parce que DuckDB ne garantit aucun ordre et que le modele
echantillonne par position. Le commentaire de la constante `GRAINE` dans le script raconte
comment le probleme a ete trouve.

---

## `make bench-rapprochement`

**Ce que ca fait** : mesure quelle part des avis du BOAMP peut etre reliee a un marche des DECP,
alors que les deux sources **ne partagent aucun identifiant**. Quatre criteres empiles : le SIRET
de l'acheteur, une fenetre de dates, la similarite des objets, le titulaire retrouve.

**Duree** : environ 3 minutes, parce que la commande interroge l'API du BOAMP en respectant une
limite de six appels par seconde.

**Resultat attendu** : 14,7 % des avis relies en confiance haute, contre 0 % par identifiant.

---

## `make bench-precision`

**Ce que ca fait** : croise les 60 verdicts relus a la main, versionnes dans
`mesures/verification/`, avec le balayage des seuils, en redressant chaque tranche par son effectif
reel.

**Resultat attendu** : les seuils 0,4 et 0,5 donnent le meme nombre de rapprochements justes, mais
0,4 y ajoute 19 erreurs. D'ou le plancher a 0,5.

---

## `make figures`

**Ce que ca fait** : trace les 19 figures du memoire en SVG et en PNG, depuis les CSV de
`mesures/resultats/`.

**Resultat attendu** : 38 fichiers dans `memoire/figures/`. Les SVG sont **identiques au bit** d'une
execution a l'autre, sinon chaque regeneration produirait un enorme diff dans git.

---

## Enchainer tout

```bash
make donnees-decp && make transformer \
  && make bench-decp && make bench-decp-distributions \
  && make bench-nettoyage && make bench-detection && make bench-modele \
  && make figures
```

**Duree totale** : environ 3 minutes, hors telechargement et hors `bench-rapprochement`.

Puis verifier que les chiffres du memoire correspondent toujours aux mesures :

```bash
make test        # dont tests/test_chiffres_memoire.py, qui relit les CSV
```

---

## `make bench-recherche`

**Ce que ca fait** : compare six facons de chercher dans les deux millions de marches, sur trente
questions de test versionnees. Trois cote PostgreSQL, trois cote DuckDB.

**Prerequis** : `make up`, `make charger` et `make indexer`.

**Duree** : environ 7 minutes, dont l'essentiel passe dans le mode « au moins un mot », qui coute
plus d'une seconde par requete. La premiere execution construit en plus l'index plein texte de
DuckDB, 21 secondes, conserve ensuite.

**Resultat attendu** :

```
  moteur                questions  sans reponse  resultats moyens   p50      p95
  postgres_et                  30             9               6.0     3.95    24.84
  postgres_ou                  30             0              10.0  1920.32  6315.27
  postgres_et_puis_ou          30             0               9.0     8.03  4807.95
  duckdb_et_brut               30            29               0.2   105.25   161.06
  duckdb_et                    30            10               5.7   105.67   150.51
  duckdb_ou                    30             0              10.0   131.23   224.80
```

**Les latences varient d'une execution a l'autre**, d'environ 30 %. C'est normal : elles dependent
de l'etat des caches et de ce qui tourne par ailleurs sur la machine. Ce qui est stable, et ce
qu'il faut lire, est l'ordre de grandeur et le classement. Le nombre de questions sans reponse,
lui, ne bouge pas.

**Comment le lire** :

- `postgres_et` repond en 4 millisecondes mais reste **muet sur 9 questions sur 30**.
- `postgres_ou` repond toujours mais coute pres de deux secondes.
- `postgres_et_puis_ou` enchaine les deux : 8 millisecondes et aucun silence. C'est la strategie
  retenue, et c'est le principe de l'escalier applique a la recherche.
- `duckdb_et_brut` est muet sur 29 questions sur 30. **Ce n'est pas un defaut de DuckDB** : il
  retire les mots vides du texte indexe mais pas de la question posee. La ligne est conservee
  parce que c'est l'erreur qu'on commet spontanement, et que son resultat est trompeur.

La decision et son raisonnement complet sont dans l'ADR 0008.

### Ce que cette commande ne mesure pas

**La pertinence.** Elle demande un jugement humain. La commande ecrit
`mesures/resultats/recherche-resultats.csv` : pour les dix questions marquees `a_juger`, les dix
premiers marches trouves par chaque moteur, avec une colonne `pertinent` vide.

Il faut la remplir par `oui`, `non` ou `doute`, enregistrer le fichier sous
`mesures/verification/jugements-recherche.csv`, puis relancer. Meme protocole que les soixante
paires relues pour le rapprochement des sources, et pour la meme raison.

---

## `make bench-incertitude`

**Ce qu'elle fait** : calcule l'intervalle de confiance a 95 % de chaque pourcentage du projet
tire d'un echantillon, par trois methodes comparees, et un bootstrap stratifie pour la justesse du
rapprochement, qui est un estimateur pondere sans formule simple.

**Ou** : sur le Mac. **Duree** : environ 1 seconde. **Prerequis** : `make transformer`, plus les
CSV produits par `make bench-assistant` et `make bench-rapprochement`.

```bash
make bench-incertitude
```

**Comment le lire** :

- la colonne `wilson_bas` est la seule que le memoire cite. Les colonnes `wald_*` et `exact_*`
  servent a montrer pourquoi, et ne sont pas des resultats ;
- sur les mesures parfaites, `wald_bas` vaut 100 : la formule la plus repandue annonce une
  certitude. C'est la raison de l'avoir ecartee, et elle est publiee dans la figure 22 ;
- `bootstrap_degenere` a `oui` signale une tranche ou toutes les paires relues sont justes. Le
  rééchantillonnage y rend un intervalle de largeur nulle, qui se lit comme une certitude et
  signale l'inverse. Dans ce cas, lire les colonnes `exact_sans_redressement_*` ;
- `incertitude-sources.csv` est la table la plus utile : pour chaque chiffre annonce, elle nomme
  la source d'incertitude qui domine. Un intervalle de confiance ne couvre que le hasard du
  tirage, jamais une non-reponse ni une etiquette approximative.

---

## `make bench-stabilite`

**Ce qu'elle fait** : recalcule les references de la regle de prix sur les seules annees 2019 a
2023, applique la regle a 2024-2026, et compare au calibrage actuel, qui utilise toutes les
annees y compris celles qu'il juge.

**Ou** : sur le Mac. **Duree** : environ 2 secondes. **Prerequis** : `make transformer`.

```bash
make bench-stabilite
```

**Comment le lire** :

- la ligne a lire est `apprentissage seul` evaluee sur `test`, la seule dont la colonne `fuite`
  vaut `non`. C'est le chiffre que le memoire publie : **69,3 %** ;
- l'ecart avec la ligne `global` evaluee sur `test`, 73,3 %, est ce que la fuite ajoutait :
  4 points, et les deux intervalles ne se chevauchent pas ;
- `stabilite-par-annee.csv` montre que la regle ne vieillit pas, mais que 2023 decroche de 28
  points sans explication etablie ;
- `stabilite-familles.csv` liste les familles d'achat dont la mediane bouge entre les deux
  periodes. Trente et une sur cinquante-sept bougent de plus de 26 %.

### Ce que cette commande ne mesure pas

**Elle ne separe pas la fuite de l'effet de taille.** Le calibrage global dispose de plus de
lignes pour estimer une mediane, ce qui aide reellement. Une partie des 4 points vient de la, et
un decoupage unique ne sait pas dire laquelle. Une validation glissante, qui recalerait les
references chaque annee, est la suite inscrite au carnet.

---

## `make bench-api`

**Ou** : sur le Mac, apres `make up` et avec les donnees chargees. Le banc demarre l'API
lui-meme, sur le port 8099 pour ne pas tomber sur une API deja lancee a la main, puis l'arrete.

**Ce que ca fait** : mesure la latence de chaque route, par HTTP reel et non par un client de
test, parce que la question posee est « combien de temps attend un visiteur » et qu'elle inclut
la validation des entrees, la serialisation et le reseau. Puis fait monter la concurrence de 1 a
16 clients. Puis compare, en SQL direct, le classement borne de la recherche au classement exact.

```bash
make up
make bench-api
```

**Duree** : environ 4 minutes, dont une bonne partie pour la requete de comptage exacte, gardee
pour montrer ce qu'elle coute.

**Resultat attendu**, mesures du 22 octobre 2026 :

| Route | Premier appel, base froide | p50 | p95 |
|---|---|---|---|
| `/api/sante` | 9 ms | 3 ms | 4 ms |
| `/api/marches?q=...` | 1 281 a 7 302 ms | 20 ms | 96 ms |
| `/api/marches/{id}` | 8 ms | 2 ms | 4 ms |
| `/api/signaux` | 1 314 a 1 443 ms | 84 ms | 172 ms |
| `/api/statistiques` | 9 ms | 2 ms | 3 ms |
| `/api/statistiques/annees` | 5 ms | 2 ms | 3 ms |
| `/api/assistant` | 304 a 8 766 ms | 31 ms | 37 ms |

Le service tient entre 87 et 111 requetes par seconde selon l'execution, sans aucun echec sur
300 appels, et sa memoire est de 37 Mo.

**Deux chiffres au lieu d'un dans la colonne froide**, et c'est volontaire : le premier appel
varie d'un facteur six d'une execution a l'autre, selon ce que le Mac garde du disque de la
machine virtuelle. Publier une seule valeur laisserait croire a une mesure stable. Ce qui est
stable, lui, c'est l'ordre de grandeur : la premiere visite coute des centaines de
millisecondes a plusieurs secondes, et une fois sur un demarrage reellement froid elle a
depasse les dix secondes du service.

C'est pour cette raison que le service se **prechauffe** au demarrage depuis le 22 octobre 2026.
`make bench-api` coupe ce prechauffage (`PRECHAUFFAGE=0`), justement pour continuer a mesurer le
cas froid ; `make bench-site` mesure le service tel qu'il est deploye, prechauffage compris, et
le pire premier appel y tombe a 166 ms.

**Les trois colonnes a savoir lire** :

- **Le premier appel** est mesure a part et non jete. C'est ce que vit le premier visiteur apres
  un deploiement, et c'est lui qui a fait abaisser le plafond de candidats de la recherche de
  20 000 a 5 000 : la mediane a chaud etait de 57 ms, mais le premier appel depassait les dix
  secondes du service et renvoyait une erreur. Mesurer seulement a chaud aurait valide un
  service qui echoue a chaque deploiement.
- **Le p50** dit ce que vit la moitie des visiteurs.
- **Le p95** dit ce que vit le vingtieme le plus malchanceux, et c'est lui qui fait abandonner
  une page. Une moyenne cacherait les deux.

**Ce que le banc a trouve et qu'aucun test n'aurait pu trouver** : quatre defauts, parce
qu'aucun test ne mesure une duree. Le tri de la liste recente qui renoncait a son index
(28 636 ms contre 30 ms), les comptages de la page d'accueil abandonnes par la base, le
classement de la recherche trop large a froid, et la serie par annee a 2,4 secondes au 95e
centile. Le detail est dans l'ADR 0011.

**Ce que le banc mesure aussi depuis le 22 octobre 2026** : une question par intention de
l'assistant, et non une seule. Chaque intention rend une forme de reponse differente, et avec
une seule question de comptage, les questions sur les titulaires repondaient 500 depuis la mise
en service de l'API sans qu'aucun test ni aucun banc ne le voie.

**Ce que `api-classement.csv` contient** : pour dix questions, le nombre de marches qui
repondent, la duree du classement exact, celle du classement borne, et combien des dix marches
affiches sont les memes dans les deux cas. C'est la contrepartie du plafond, chiffree : exacte
sous 5 000 reponses, et jusqu'a zero sur dix au-dela.

---

## `make bench-site` : le poids des pages et le gain du rechargement partiel

Mesure ce que la latence seule ne dit pas : combien pese chaque page, ce que le fragment htmx
economise, et si les pages se rendent sans JavaScript.

```bash
make up
make bench-site
```

**Duree** : environ une minute. Le banc demarre le site lui-meme, mesure, et l'arrete.

**Resultat attendu**, mesures du 22 octobre 2026, base froide :

| Page | Premier appel | p50 | Poids | Comprime |
|---|---|---|---|---|
| `/` | 22 ms | 6 ms | 17,0 ko | 4,3 ko |
| `/recherche?q=...` | 83 ms | 25 ms | 15,5 ko | 4,4 ko |
| `/recherche?q=travaux` | 53 ms | 55 ms | 17,0 ko | 5,5 ko |
| `/fiche/{id}` | 16 ms | 4 ms | 6,5 ko | 2,6 ko |
| `/a-examiner` | 277 ms | 67 ms | 8,4 ko | 1,9 ko |
| `/questions?question=...` | 108 ms | 55 ms | 5,5 ko | 2,1 ko |
| `/a-propos` | 5 ms | 1 ms | 9,5 ko | 3,9 ko |

**Ce qu'il faut savoir en lire** :

- **Le poids.** La page la plus lourde fait 17,0 ko, soit 5,5 ko une fois compressee : 22
  millisecondes d'attente sur une connexion mobile a 2 Mbit/s. Aucune optimisation de poids
  n'est justifiee, et le dire en chiffres evite d'en faire une par reflexe. Les fichiers
  charges une fois puis gardes par le navigateur (feuille de style, htmx, icone) pesent 67,0 ko
  au total.
- **Le gain du fragment.** Le meme filtre applique de deux facons : en rechargeant la page
  entiere, ou en remplacant la seule liste de resultats. Le fragment pese 32 a 71 pour cent de
  moins, mediane 52. C'est ce qui justifie htmx, et c'est une mesure, pas une preference.
- **Sans JavaScript.** Chaque page est demandee sans l'en-tete `HX-Request`, exactement comme
  un navigateur dont le JavaScript est coupe, et son contenu doit etre present. Dix pages sur
  dix. C'est le plan B de la soutenance, et un plan B qu'on n'essaie pas n'existe pas.
- **Les en-tetes servis.** Le banc relit la politique de securite reellement envoyee et verifie
  qu'elle n'autorise ni `unsafe-inline` ni aucun domaine tiers. Une politique ecrite dans le
  code et jamais relue dans une reponse reelle est une intention, pas une mesure.
