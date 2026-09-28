# 2026-09-28. Le nettoyage en trois couches

## Objectif

Passer de la donnee brute, mesuree en phase 2, a une table exploitable. Avec une contrainte tenue
d'un bout a l'autre : **ne supprimer aucune ligne**.

## Ce qui a ete fait

- Projet dbt dans `services/transformation/`, trois couches, neuf regles de nettoyage commentees.
- Contrats de donnees ecrits pour les couches argent et or, avec 18 tests de donnees.
- `mesures/nettoyage.py` et `make bench-nettoyage` : l'effet de chaque regle, mesure.
- Figure 18, tracee depuis ces mesures.
- 20 tests d'integration qui executent la vraie chaine sur un jeu fictif de quinze lignes.
- ADR 0005.

## Le resultat

| Couche | Lignes | Colonnes | Contenu |
|---|---|---|---|
| bronze | 3 296 811 | 66 | la donnee telle que la source l'a publiee |
| argent | 2 121 908 | 79 | l'etat actuel de chaque marche, problemes marques |
| or | 1 999 474 | 29 | les marches exploitables pour une analyse de prix |

**94,2 % des lignes de la couche argent sont exploitables** pour une analyse de prix. Les 5,8 %
restants ne disparaissent pas : ils portent le motif de leur exclusion.

La normalisation de la nature du marche ramene **douze ecritures a six notions**. Le cas
« ACCORD-CADRE » contre « ACCORD CADRE », qui resistait en phase 2, est resolu en normalisant
aussi la ponctuation. Toujours aucun modele, toujours deux fonctions SQL.

## Ce que les tests de donnees ont trouve

**Six lignes sans SIRET ni nom d'acheteur**, toutes de la meme source. Des marches dont on ne sait
pas qui les a passes.

**244 codes CPV qui ne sont pas des codes** : « Travaux », « lot 2000 », « X0000000 ». Des
acheteurs ont ecrit du texte libre dans un champ de nomenclature. La regle ne deduit desormais une
famille que d'un code commencant reellement par deux chiffres, et marque le reste.

Ces deux defauts n'etaient pas connus avant. Ils ont ete trouves parce qu'un contrat de donnees
avait ete ecrit, pas parce qu'on les cherchait.

## Difficultes rencontrees

### Un contrat place a la mauvaise couche

**Symptome** : le test `not_null` sur le SIRET de l'acheteur faisait echouer la chaine, en couche
argent, avec six lignes fautives.

**Cause** : le contrat contredisait la promesse de la couche. La couche argent s'engage a **tout
garder en marquant les problemes** ; y exiger un identifiant non nul revenait a exiger qu'il n'y
ait aucun probleme a conserver.

**Solution** : avertissement en couche argent, regle stricte en couche or, ou elle bloque a juste
titre puisque la couche or ne contient que l'exploitable.

**Lecon pour le memoire** : la severite d'un test doit correspondre a ce que sa couche promet. Un
test trop strict finit desactive, et un test desactive ne protege plus rien. C'est le mecanisme
exact de l'echec Louvois.

### Une vue avec un chemin relatif

**Symptome** : la couche bronze etait interrogeable depuis dbt, mais pas depuis un notebook ni un
script lance a la racine : `No files found that match the pattern`.

**Cause** : la vue portait un chemin relatif, resolu depuis le dossier de travail du processus.

**Solution** : le chemin est passe en absolu par le Makefile. La vue est desormais interrogeable
de partout.

**Lecon** : un artefact partage ne doit pas dependre de l'endroit d'ou on l'appelle.

### Deux refus de l'analyse de securite, encore

Le script de mesure construisait ses requetes en inserant des noms de colonnes. Corrige en ecrivant
les neuf regles dans une seule requete complete, ce qui est au passage plus rapide : un seul
passage sur la table au lieu de neuf.

Et le test d'integration lancait `uv` sans chemin complet, laissant le PATH decider quel programme
s'execute. Corrige par `shutil.which`, avec en prime un message clair quand l'outil manque.

## Un outil adopte, pour la premiere fois

Jusqu'ici, ce projet a surtout ecarte des outils : pas d'orchestrateur, pas de bibliotheque HTTP,
pas de moteur distribue. dbt est le premier a etre retenu, et l'ADR 0005 explique pourquoi : sans
lui, il faudrait ecrire un lanceur, un systeme de tests de donnees, une generation de documentation
et un graphe de dependances. Plusieurs semaines pour refaire moins bien.

**Lecon** : la question n'est jamais « cet outil est-il bon » mais « qu'est-ce que je devrais
ecrire sans lui ». La reponse penche parfois du cote de l'outil, et il faut alors savoir le dire.

## Prochaine etape

L'ingenierie des variables : fabriquer, a partir des colonnes nettoyees, les grandeurs qui
serviront a detecter les marches atypiques. Ecart du montant a la mediane de sa famille CPV,
concentration des attributions par acheteur, position dans le calendrier budgetaire.

### Deux versions de Ruff qui se contredisaient

**Symptome** : la chaine d'integration refusait un fichier que le hook pre-commit venait
d'accepter, et reciproquement. Le commit passait en local, echouait sur le serveur.

**Cause** : le hook pre-commit etait fige a Ruff 0.6.9, quand le projet utilisait 0.16.8. Les deux
formatent differemment un `assert` accompagne d'un message. Le hook reformatait dans un sens, la
chaine exigeait l'autre.

**Solution** : la meme version aux deux endroits, epinglee a l'exact, avec un commentaire qui
explique pourquoi dans chacun des deux fichiers. `pre-commit autoupdate` a d'ailleurs propose une
version encore plus recente, ce qui aurait recree l'ecart : l'alignement se fait a la main, ou par
Dependabot qui met les deux a jour ensemble.

**Lecon pour le memoire** : un outil de qualite installe deux fois a deux versions differentes ne
protege plus, il bloque. C'est une forme discrete de la meme erreur que l'environnement non
reproductible, et elle se voit seulement quand les deux copies divergent.

### La chaine d'integration ne voyait ni les paquets ni le jeu d'essai

**Symptome** : les vingt tests d'integration passaient sur le Mac et echouaient tous sur le
serveur, avec deux erreurs successives : `dbt expects 1 package(s)` puis `No files found that
match the pattern .../bronze_fictif.parquet`.

**Causes**, deux fois la meme : ce qui marche en local parce qu'il est deja la.

1. Les paquets dbt sont installes une fois sur cette machine et ignores par git, a juste titre.
   La machine d'integration part d'un depot vierge et ne les avait pas.
2. Le jeu d'essai est un fichier Parquet, et `.gitignore` exclut tous les `.parquet` depuis la
   phase 1. La regle protege des donnees de 250 Mo ; elle excluait aussi un fichier de test de
   3 Ko, qui doit au contraire etre versionne.

**Solutions** : le test lance lui-meme `dbt deps` avant de construire, et `.gitignore` porte une
exception nommee pour `tests/fixtures/*.parquet`, avec le commentaire qui explique pourquoi.

**Lecon pour le memoire** : une chaine d'integration ne verifie pas seulement le code, elle
verifie **l'hypothese implicite que tout est deja installe**. Trois echecs consecutifs ont revele
trois dependances invisibles depuis le poste de developpement : une version d'outil, des paquets,
un fichier. Aucune n'aurait ete vue autrement.
