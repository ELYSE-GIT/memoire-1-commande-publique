# 2026-09-29. Les regles valent-elles mieux qu'un modele ?

## Objectif

Tenir l'engagement pris dans l'ADR 0006 : comparer les regles de detection a un modele non
supervise, avec la meme etiquette et le meme protocole, et publier le resultat **meme s'il est
defavorable aux regles**.

## Ce qui a ete fait

- `analyses/08-modelisation-detection.ipynb` : le notebook de modelisation, 28 cellules de code,
  dix methodes comparees, les hyperparametres regroupes dans des cellules marquees `A MODIFIER`
  pour pouvoir etre manipules pendant la soutenance.
- `mesures/modele_vs_regles.py` et `make bench-modele` : la partie stabilisee, quatre methodes.
- Figure 19, tracee depuis ces mesures.
- `analyses/verifier_notebooks.py` et `make verif-notebooks` : controle de syntaxe, d'erreur et
  d'execution complete des notebooks.
- 11 tests sur le protocole de comparaison et sur la preparation SQL.
- ADR 0007.

## Le resultat

Les regles restent la methode de detection. Mais la raison n'est pas celle que j'avais ecrite au
depart, et le chemin compte autant que la conclusion.

| Budget d'alertes | Regle | Modele libre | Modele oriente | Hasard |
|---|---|---|---|---|
| 100 | 96,0 % | 0,0 % | 73,0 % | 2,0 % |
| 1 000 | 96,1 % | 0,0 % | 65,7 % | 3,1 % |
| 10 000 | 73,3 % | 1,7 % | 70,9 % | 2,7 % |

## Difficultes rencontrees

### 1. Un modele sous le hasard, et la tentation de conclure trop vite

Isolation Forest obtenait **0 %** de precision la ou un tirage aleatoire obtenait 2 a 3 %. La
conclusion facile etait ecrite d'avance : « les regles gagnent ». Avant de la garder, j'ai regarde
les marches que le modele designait : ecart median de **moins 8,2**, montant median de **0,20 euro**,
468 offres recues. Ce sont des montants anormalement **bas**, que l'etiquette ne marque jamais.

La metrique ne mesurait pas le modele, elle mesurait un desaccord de direction. Oriente du meme
cote que la regle, le modele passe de 0 a 73 % sans qu'une ligne de son apprentissage ne change.

**Lecon** : un resultat sous le hasard n'est pas un mauvais resultat, c'est un signe qu'on ne
mesure pas ce qu'on croit mesurer.

### 2. Une graine fixe ne suffit pas a rendre un calcul reproductible

Deux lancements du meme script, meme graine, memes donnees : **100,0 % puis 74,0 %**. Trois causes
empilees, trouvees l'une apres l'autre.

1. DuckDB execute en parallele et ne garantit **aucun ordre** de lignes sans `order by`. Isolation
   Forest tire ses echantillons par position, et le vecteur de hasard est apparie aux etiquettes
   par position.
2. `order by uid` n'a pas suffi. J'ai compare les empreintes des matrices : environ 700 lignes sur
   deux millions portaient des valeurs **completement** differentes, pas des arrondis. Donc des
   lignes permutees, donc **uid n'est pas unique**.
3. Verification : 140 350 uid apparaissent plusieurs fois, soit 281 404 lignes en trop sur
   2 054 924, et **619 uid portent des montants contradictoires** d'une ligne a l'autre. `uid`
   identifie un marche, pas une ligne ; un marche a autant de lignes que de titulaires.

Correction : le tri porte sur toutes les colonnes utilisees. Trois executions donnent maintenant
le meme fichier, et c'est verifie plutot qu'affirme.

**Lecon** : la reproductibilite ne se decrete pas avec une graine, elle se verifie en relancant.
Effet de bord utile : les 619 montants contradictoires sont un defaut de qualite qui n'avait pas
ete vu.

### 3. `jupyter execute` sort en code 0 quand une cellule echoue

Une erreur SQL a interrompu le notebook a la troisieme cellule. La commande a rendu **0**, et rien
ne l'a signale. Une cible Makefile ou une etape de CI qui se fierait a ce code de sortie laisserait
passer un notebook casse, et le depot afficherait une trace d'erreur au lieu d'un resultat.

Correction : `analyses/verifier_notebooks.py`, sans dependance supplementaire, qui relit le fichier
produit. Il verifie aussi la syntaxe de chaque cellule, parce que j'ai attendu quatre minutes
d'execution pour decouvrir une apostrophe mal echappee dans la derniere cellule.

### 4. La mesure a donne tort a deux de mes convictions

**Le robuste ne bat pas le naif.** J'avais annonce que la mediane et l'ecart interquartile
l'emporteraient sur la moyenne et l'ecart type. Mesure : les versions naives font un peu
**mieux** (AP 49,7 et 50,2 contre 47,1). Raison : l'etiquette est un detecteur de gros montants,
et l'ecart a la famille est correle a **0,98** au montant brut. Classer par montant donne presque
raison d'avance.

Consequence honnete : **cette etiquette ne sait pas departager ces trois variantes**. Le choix du
robuste repose sur un argument de methode, pas sur une mesure, jusqu'a ce qu'un echantillon soit
juge a la main.

**Local Outlier Factor n'est pas quadratique ici.** Je l'avais ecarte dans l'ADR 0006 sur sa
reputation. Mesure : la duree par ligne n'augmente que de 60 % quand la taille passe de 25 000 a 400 000 lignes, la ou un cout quadratique l'aurait multipliee par 16, et la methode
traite le jeu complet en **15,8 secondes**, pour environ 1,7 Go de memoire. En cinq dimensions, scikit-learn indexe les
points dans un arbre. La reputation vient du comportement en grande dimension. La methode reste
ecartee, mais parce qu'elle est mauvaise ici (AP 3,96 %), pas parce qu'elle serait impraticable.

**Lecon** : ne jamais ecarter une option sans l'avoir mesuree, meme quand la litterature semble
trancher.

### 5. La valeur par defaut n'est pas la meilleure valeur

`max_samples=256` est la valeur recommandee par les auteurs d'Isolation Forest. Sur ce jeu, 1024
fait nettement mieux pour le modele oriente : **90,2 % contre 65,7 %** a mille alertes. Cela ne
change pas la decision, puisque la regle reste au-dessus, mais cela change ce qu'on peut en dire :
un modele demanderait un reglage sur mesure, a refaire a chaque changement de donnees. Une regle
n'a rien a regler.

### 6. Gitleaks lisait trois gigaoctets de donnees, pour deux fausses alertes

`gitleaks dir .` parcourt le systeme de fichiers et **ignore le `.gitignore`**. Il lisait donc
`donnees/`, 3 Go de Parquet et de base DuckDB, en **7 minutes 40**, pour deux fausses alertes : une
suite d'octets binaires ressemblant a une cle AWS, et l'objet d'un marche public qui declenchait la
regle generique.

Correction : un `.gitleaks.toml` qui part des regles par defaut et exclut `donnees/`. Ces fichiers
ne sont pas versionnes, donc ils ne peuvent pas fuir par un push, et le scan de l'historique n'est
pas concerne. Le scan passe de **7 min 40 a 1,15 s**.

Puis la verification, parce qu'un garde-fou desactive par erreur est pire que pas de garde-fou :
un faux jeton `ghp_...` pose dans `services/` est bien detecte, le meme pose dans `donnees/` est
bien ignore, et le depot est propre apres nettoyage.

**Lecon** : baisser la sensibilite d'un scanner est dangereux, reduire son perimetre a ce qui peut
reellement fuir ne l'est pas. Mais il faut le prouver en plantant un secret factice.

## A savoir expliquer devant le jury

- Pourquoi comparer a budget d'alertes egal, et pourquoi le taux de bonnes reponses est
  inutilisable quand 3 % des lignes sont positives.
- Pourquoi ROC AUC est affichee dans les tableaux alors qu'elle est jugee trompeuse : les
  k-moyennes affichent 71,5 % d'AUC pour 2,0 % de precision a mille alertes.
- Pourquoi un modele peut passer de 0 a 73 % sans reapprendre.
- Pourquoi `uid` n'identifie pas une ligne, et ce que cela a casse.
- Ce qui manque pour departager la regle robuste de ses versions naives, et pourquoi c'est une
  limite de l'etiquette, pas du calcul.
- Pourquoi exclure `donnees/` du scan de secrets ne retire aucune protection, et comment on l'a
  verifie.

## Prochaine etape

Juger a la main un echantillon de marches designes par chacune des trois statistiques, pour obtenir
une etiquette qui ne vienne pas d'un detecteur de montants.
