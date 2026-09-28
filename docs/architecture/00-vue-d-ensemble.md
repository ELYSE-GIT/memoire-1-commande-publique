# Vue d'ensemble de l'architecture

Le document a ouvrir en premier. Il explique **ce que fait le projet, comment, pourquoi ainsi**, et
ce qu'il ne faut pas refaire.

Tout ce qui est affirme ici est mesure. Chaque chiffre renvoie a la commande qui le produit.

---

## 1. Le trajet de la donnee

```
   SOURCES PUBLIQUES                COLLECTE              TRANSFORMATION            SERVICE
 ┌──────────────────┐         ┌───────────────┐       ┌──────────────────┐    ┌──────────────┐
 │ DECP             │         │               │       │  bronze  3,30 M  │    │ API          │
 │ data.gouv.fr     │────────▶│  services/    │──────▶│  la donnee brute │───▶│ FastAPI      │
 │ 250 Mo Parquet   │         │  collecte/    │       │                  │    │ (phase 7)    │
 ├──────────────────┤         │               │       │  argent  2,12 M  │    ├──────────────┤
 │ BOAMP            │────────▶│  manifeste    │──────▶│  nettoyee,       │───▶│ Site public  │
 │ 1,7 M d'avis     │         │  empreinte    │       │  problemes       │    │ + admin      │
 ├──────────────────┤         │  idempotence  │       │  marques         │    │ (phase 7)    │
 │ Recherche        │         │               │       │                  │    │              │
 │ d'entreprises    │────────▶│  reprise sur  │──────▶│  or  2,00 M      │───▶│ Assistant    │
 │ 242 745 SIRET    │         │  erreur       │       │  servie          │    │ (phase 6)    │
 └──────────────────┘         └───────────────┘       └──────────────────┘    └──────────────┘
                                      │                        │
                                      ▼                        ▼
                              donnees/manifestes/     mesures/resultats/
                              (versionne)             (versionne, source des figures)
```

**Ce qui est versionne et ce qui ne l'est pas**, parce que c'est la question la plus frequente :

| Element | Taille | Versionne | Pourquoi |
|---|---|---|---|
| Donnee brute | 250 Mo par collecte | non | lourde, republiee chaque matin, retelechargeable |
| Manifeste | quelques Ko | **oui** | c'est la preuve de ce qui a ete mesure |
| Agregats mesures | quelques Ko | **oui** | ce sont les chiffres du memoire |
| Figures | environ 4 Mo | **oui** | generees, mais lues par le memoire |
| Jeu d'essai des tests | 3 Ko | **oui** | sans lui, les tests ne tournent pas sur une machine vierge |

---

## 2. Les composants, et le fichier a ouvrir

| Composant | Role | Ou regarder |
|---|---|---|
| **Collecte** | recuperer les sources sans les abimer, et tracer ce qui a ete recupere | `services/collecte/` |
| **Transformation** | trois couches, du brut au servi, en SQL | `services/transformation/models/` |
| **Mesures** | tout chiffrer, et ecrire les resultats en CSV | `mesures/` |
| **Figures** | tracer depuis les CSV, jamais depuis les donnees | `mesures/figures.py` |
| **Exploration** | montrer la demarche, code visible et execute | `analyses/*.ipynb` |
| **Tests** | 105 tests, dont 20 qui executent la vraie chaine | `tests/` |
| **Decisions** | pourquoi tel choix, et ce qui a ete ecarte | `docs/adr/` |
| **Journal** | ce qui a mal tourne, et la lecon | `docs/journal/` |

---

## 3. Les cinq principes tenus

Ils reviennent partout. Les connaitre dispense de lire le reste.

### 3.1 Mesurer avant d'affirmer

Aucun chiffre n'entre dans le memoire sans une commande qui le produit. Un test compare meme les
chiffres cites aux mesures enregistrees : si une donnee change, la chaine d'integration nomme le
chiffre devenu faux.

### 3.2 Marquer plutot que supprimer

Aucune ligne n'est jamais retiree. Une ligne fautive porte la liste de ses problemes, en clair.
Une ligne effacee ne peut plus etre expliquee a un jury, ni corrigee par l'administration qui l'a
publiee.

### 3.3 Le principe de l'escalier

Regles et expressions regulieres, puis statistique, puis apprentissage automatique, puis
plongements lexicaux, puis grands modeles de langage. **On ne monte que si la mesure prouve que la
marche precedente ne suffit pas.**

Ou il s'applique deja :

| Probleme | Marche utilisee | Resultat |
|---|---|---|
| Douze ecritures pour une nature de marche | deux fonctions SQL | six notions, quelques millisecondes |
| SIRET dans trois formats d'avis differents | une expression reguliere | 19 % d'avis exploitables devient 61 % |
| Prix atypique | ecart robuste a la mediane du groupe | 75,8 % de precision au seuil 4 |
| Relier deux sources sans identifiant commun | quatre criteres empiles | de 0 % a 14,7 % de liens surs |
| **Monter a l'apprentissage automatique** | dix methodes comparees a budget egal | **refuse** : aucun modele ne depasse la statistique |

La derniere ligne est la plus importante du tableau, parce qu'elle montre que l'escalier sert dans
les deux sens. Voir l'ADR 0007 : les modeles ne trouvent des valeurs extremes qu'une fois qu'on leur
a dit de quel cote regarder, et cette connaissance vient du metier, pas des donnees.

### 3.4 Un signal n'est pas une accusation

Tout marche signale l'est comme une invitation a verifier. Un marche tres specialise attire peu de
candidats sans que personne n'ait rien a se reprocher. Le service devra l'ecrire a l'ecran.

### 3.5 Refuser un outil demande plus d'arguments que l'adopter

La question n'est jamais « cet outil est-il bon » mais « qu'est-ce que je devrais ecrire sans
lui ».

| Outil | Verdict | Raison |
|---|---|---|
| DuckDB | **adopte** | lit le Parquet sur place, aucun serveur, agregation en millisecondes |
| dbt | **adopte** | sans lui : un lanceur, des tests de donnees, une documentation, un graphe |
| Colima | **adopte** | conteneurs a la demande, sans licence d'entreprise |
| Dagster | ecarte pour l'instant | resout des dependances entre etapes, qui n'existent pas encore |
| PySpark | ecarte | un cluster pour 250 Mo coute plus que le calcul |
| polars | ecarte | une API de plus, alors que le SQL sert deja dans dbt |
| requests, httpx | ecartes pour l'instant | trente lignes de bibliotheque standard suffisent |
| Jeux Kaggle ou Hugging Face | ecartes | partir d'un jeu nettoye supprimerait le probleme a demontrer |

---

## 4. Les decisions, et ou les lire

| ADR | Decision | Ce qu'elle engage |
|---|---|---|
| [0001](../adr/0001-socle-technique.md) | uv, Colima, Ruff, mypy, pytest | l'environnement, reproductible et jetable |
| [0002](../adr/0002-duckdb-parquet-pour-l-exploration.md) | DuckDB sur Parquet | pas de serveur avant le site |
| [0003](../adr/0003-rapprochement-des-sources.md) | rapprochement par niveaux de confiance | un lien affiche porte toujours son degre de certitude |
| [0004](../adr/0004-collecte-et-couche-bronze.md) | collecte tracable, sans orchestrateur | manifeste versionne, donnee brute non versionnee |
| [0005](../adr/0005-nettoyage-en-trois-couches.md) | bronze, argent, or, avec dbt | marquer plutot que supprimer |
| [0006](../adr/0006-detection-par-regles.md) | detection par regles, seuils mesures | deux niveaux, jamais une accusation |
| [0007](../adr/0007-regles-plutot-qu-un-modele.md) | rester sur les regles, apres comparaison a dix methodes | la connaissance metier, pas la puissance statistique |

---

## 5. Les erreurs commises, et ce qu'il ne faut pas refaire

C'est la section la plus utile du document. Chaque ligne est une erreur reellement commise sur ce
projet, avec ce qu'elle a coute et ce qui l'evite.

### Sur les donnees

| Erreur | Ce qui s'est passe | A faire a la place |
|---|---|---|
| **Confondre les unites de comptage** | 899 298 lignes divisees par 1 833 468 marches, soit 49 % au lieu de 44 % | preciser l'unite a chaque pourcentage. Trois coexistent : 3,30 M de lignes brutes, 2,12 M a l'etat actuel, 1,83 M de marches |
| **Annoncer un chiffre spectaculaire sans l'expliquer** | « 44 % de doublons », qui etaient des avenants et des groupements | decomposer avant de publier. Les vrais doublons sont 7 800, soit 0,4 % |
| **Chercher une donnee au mauvais endroit** | le SIRET semblait manquer dans 81 % des avis du BOAMP : il etait ailleurs, trois formats coexistent | verifier ou l'on cherche avant de conclure a une absence |
| **Croire une metadonnee** | le catalogue annoncait une source abandonnee depuis un an, la donnee allait jusqu'au jour meme | une metadonnee decrit une intention, la donnee decrit un fait |
| **Ecrire le commentaire avant de lire la sortie** | trois legendes affirmaient des tendances non verifiees, dont une fausse | lire la sortie, puis ecrire |
| **Prendre un identifiant pour une cle unique** | `uid` identifie un marche, pas une ligne : 140 350 uid repetes, 281 404 lignes en trop, 619 montants contradictoires | verifier l'unicite avant de s'appuyer dessus, par un `count(*) - count(distinct ...)` |

### Sur la methode

| Erreur | Ce qui s'est passe | A faire a la place |
|---|---|---|
| **Choisir un echantillon au lieu de le tirer** | les 60 plus gros titulaires donnaient 5 % de PME, contre 59,2 % sur un tirage aleatoire | tirer au hasard, en ponderant par ce que la question mesure |
| **Mesurer la couverture sans la justesse** | un seuil plus bas rapprochait davantage, et davantage a tort | la question n'est pas « combien de liens » mais « combien de liens justes » |
| **Oublier de redresser un echantillon stratifie** | la moyenne naive donnait 33 % la ou la bonne reponse etait 6,7 % | ponderer chaque strate par son effectif reel |
| **Choisir une palette a l'oeil** | elle echouait a trois controles, dont la lisibilite pour un daltonien | faire valider les couleurs par un outil |
| **Lire un score sous le hasard comme un mauvais score** | le modele obtenait 0 % : il cherchait du cote que l'etiquette ne marque jamais, et passait a 73 % une fois oriente | ouvrir les observations designees avant de conclure |
| **Ecarter une option sur sa reputation** | Local Outlier Factor, ecarte pour cout quadratique, traite le jeu complet en 15,8 secondes | mesurer le cout avant de l'invoquer |
| **Annoncer qu'une methode robuste gagnera** | les versions naives font un peu mieux, parce que l'etiquette est elle-meme un detecteur de montants | verifier ce que l'etiquette est capable de departager |

### Sur la reproductibilite

| Erreur | Ce qui s'est passe | A faire a la place |
|---|---|---|
| **Croire qu'une graine fixe suffit** | deux lancements identiques donnaient 100,0 % puis 74,0 % : DuckDB ne garantit aucun ordre de lignes, et le modele echantillonne par position | fixer l'ordre au chargement, sur toutes les colonnes utilisees, et le verifier en relancant |
| **Se fier au code de sortie** | `jupyter execute` rend 0 meme quand une cellule leve une exception | relire le fichier produit, `make verif-notebooks` |
| **Laisser un scanner lire les donnees** | gitleaks parcourait 3 Go de Parquet en 7 min 40, pour deux fausses alertes | reduire son perimetre a ce qui peut fuir, jamais sa sensibilite, et le verifier avec un secret factice |

### Sur l'ingenierie

| Erreur | Ce qui s'est passe | A faire a la place |
|---|---|---|
| **Configurer un garde-fou sans le tester** | la protection de la branche principale laissait passer le proprietaire | tester tout garde-fou par un essai reel qui doit echouer |
| **Committer sur la branche principale en local** | une pull request melangeant deux sujets, et un historique a reecrire | `git switch -c` avant la premiere modification, toujours |
| **Placer un contrat de donnees a la mauvaise couche** | un test bloquant sur une couche dont la promesse est de tout conserver | la severite d'un test doit correspondre a ce que sa couche promet |
| **Installer un outil de qualite a deux versions** | Ruff 0.6.9 en pre-commit contre 0.16.8 dans le projet : les deux se contredisaient | epingler la meme version aux deux endroits |
| **Supposer que la machine d'integration a ce qu'on a en local** | paquets dbt absents, jeu d'essai exclu par `.gitignore` | une chaine d'integration verifie l'hypothese implicite que tout est installe |
| **Publier un notebook sans l'executer** | du code non teste presente comme un resultat | `make notebooks` rejoue tout, et les sorties sont versionnees |
| **Versionner un artefact non reproductible** | 6 500 lignes de difference pour des figures identiques | sel fixe et date retiree : deux executions donnent le meme fichier au bit pres |
| **Un chemin relatif dans un artefact partage** | une vue interrogeable depuis dbt et nulle part ailleurs | un artefact partage ne depend pas de l'endroit d'ou on l'appelle |

---

## 6. Les chiffres cles, tous mesures

| Mesure | Valeur | Commande |
|---|---|---|
| Lignes brutes / etat actuel / marches | 3 296 811 / 2 121 908 / 1 833 468 | `make bench-nettoyage` |
| Lignes exploitables apres nettoyage | 94,2 % | `make bench-nettoyage` |
| Total annuel brut contre reel | 3 030 Md€ contre 233 Md€ | `make bench-decp-distributions` |
| Part des marches attribues a une PME | 59,2 % (officiel : 60 %) | notebook 06 |
| Marches portant au moins un signal | 76 309, soit 3,8 % | `make transformer` |
| Precision de la regle de prix, seuil 4 | 75,8 % (minorant) | `make bench-detection` |
| Precision de la regle a 1 000 alertes | 96,1 % contre 65,7 % pour le meilleur modele | `make bench-modele` |
| Methodes de detection comparees | 10, dont 7 apprises | notebook 08 |
| Lignes dont l'uid est partage | 281 404 sur 2 054 924 | notebook 08 |
| Avis du BOAMP relies aux DECP | 14,7 % en confiance haute | `make bench-rapprochement` |
| Parquet contre CSV | 247,6 Mo contre 2 595,5 Mo | `make collecte-decp` |
| Duree de la chaine complete | environ 6 secondes | `make transformer` |
| Cout de l'ensemble | 0 euro | |

---

## 7. Par ou commencer, selon ce que l'on cherche

| Question | Fichier |
|---|---|
| Comment lancer le projet ? | [`docs/commandes/00-sommaire.md`](../commandes/00-sommaire.md) |
| Que font les donnees ? | `analyses/01` a `analyses/03` |
| Comment sont-elles nettoyees ? | `services/transformation/models/argent/argent_marches.sql` |
| Pourquoi ce choix technique ? | `docs/adr/` |
| Qu'est-ce qui a mal tourne ? | `docs/journal/`, ou la section 5 ci-dessus |
| Comment le projet se verifie-t-il ? | `analyses/05-comment-le-projet-se-verifie.ipynb` |
