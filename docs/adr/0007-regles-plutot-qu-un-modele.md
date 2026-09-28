# ADR 0007. Rester sur les regles, apres les avoir comparees a dix methodes

- Date : 2026-09-29
- Statut : accepte
- Phase : 5 bis, comparaison mesuree
- Prolonge : [ADR 0006](0006-detection-par-regles.md), qui s'etait engage a faire cette mesure

## Contexte

L'ADR 0006 a choisi de detecter par des regles explicites et a pris un engagement precis :

> Monter d'une marche ne se justifiera que si une mesure montre qu'un modele fait mieux, avec la
> meme etiquette et le meme protocole. C'est le travail de la phase suivante, et le resultat sera
> publie meme s'il est defavorable aux regles.

Cet ADR rend cette mesure. Elle est faite dans `analyses/08-modelisation-detection.ipynb`, et sa
partie stabilisee est rejouable par `make bench-modele`.

## Le protocole

**A budget d'alertes egal.** Pour un nombre d'alertes donne, on prend les N marches les mieux
classes par chaque methode et on compare leur precision. Comparer une regle qui signale 8 331
marches a un modele qui en signale 60 000 ne dirait rien : le second trouverait mecaniquement plus
d'anomalies, et mecaniquement plus de faux.

Quatre metriques, et deux volontairement ecartees :

| Metrique | Pourquoi elle est la |
|---|---|
| precision a budget | c'est la contrainte reelle de l'analyste, qui n'a pas un temps infini |
| precision moyenne (AP) | resume le classement entier, adaptee aux classes rares |
| ROC AUC | montree **pour etre critiquee** : elle reste flatteuse quand les positifs sont rares |
| duree | un modele qui demande des heures ne tient pas sur un VPS a 12 euros |
| ~~taux de bonnes reponses~~ | repondre « rien a signaler » partout donne 97,3 % |
| ~~rappel seul~~ | signaler les deux millions de marches donne 100 % de rappel |

Etiquette : la meme que l'ADR 0006, faible et assumee comme telle, les montants que le producteur
des donnees signale lui-meme.

## La decision

**Les regles restent la methode de detection du projet.**

La justification a change deux fois pendant la mesure, et c'est la derniere qui compte.

> Sur dix methodes, aucune n'a depasse une statistique descriptive tenant en une ligne de SQL. Les
> modeles ne trouvent des valeurs extremes qu'une fois qu'on leur a dit **de quel cote** regarder,
> et cette connaissance vient du metier, pas des donnees. Une regle la porte en clair et l'explique
> a l'utilisateur ; un modele ne l'a que si on la lui impose de l'exterieur, et il ne peut alors
> plus rien expliquer de sa decision.

## Les mesures

### Precision a budget d'alertes egal, sur 2 053 765 marches

| Budget | Regle | Modele libre | Modele oriente | Hasard |
|---|---|---|---|---|
| 100 | **96,0 %** | 0,0 % | 73,0 % | 2,0 % |
| 500 | **98,0 %** | 0,0 % | 73,6 % | 2,8 % |
| 1 000 | **96,1 %** | 0,0 % | 65,7 % | 3,1 % |
| 5 000 | **87,5 %** | 1,1 % | 74,8 % | 2,8 % |
| 10 000 | **73,3 %** | 1,7 % | 70,9 % | 2,7 % |
| 30 000 | **56,4 %** | 25,6 % | 52,9 % | 2,6 % |

### Le banc complet, precision moyenne (AP)

| Methode | AP libre | AP orientee | Duree |
|---|---|---|---|
| 1. z-score global | 49,66 % | 49,64 % | instantane |
| 2. z-score par famille | **50,22 %** | **50,20 %** | instantane |
| 3. ecart robuste, **la regle** | 47,12 % | 47,11 % | instantane |
| 4. k-moyennes, normalisation standard | 9,44 % | 24,36 % | 0,6 s |
| 5. k-moyennes, normalisation robuste | 7,01 % | 16,05 % | 0,5 s |
| 6. ACP, erreur de reconstruction | 19,86 % | 50,04 % | 0,1 s |
| 7. enveloppe elliptique | 6,33 % | 12,79 % | 1,9 s |
| 8. SVM a une classe | 4,27 % | 6,79 % | 1,0 s |
| 9. Isolation Forest | 17,46 % | 41,32 % | 4,7 s |
| 10. Local Outlier Factor | 3,96 % | 6,83 % | 15,8 s |

## Ce que la mesure a appris, et qui n'etait pas prevu

### 1. Le modele libre est sous le hasard, et ce n'est pas un defaut du modele

Isolation Forest obtient **0 %** de precision sur les petits budgets, contre 2 a 3 % pour un
tirage aleatoire. Le diagnostic a montre pourquoi : ses mille premieres alertes ont un ecart median
de **moins 8,2**, un montant median de **0,20 euro** et 468 offres recues. Ce sont des montants
anormalement **bas**. L'etiquette, elle, ne marque que des montants trop **hauts**.

La metrique ne mesurait donc pas la qualite du modele, mais un desaccord de direction. Oriente du
meme cote que la regle, sans qu'une ligne de son apprentissage ne change, le modele passe de 0 a
73 % sur les cent premieres alertes.

C'est la meme lecon que l'ADR 0006, appliquee cette fois au modele : **une evaluation ne dit rien
sur ce que son etiquette ignore.**

### 2. Les versions naives battent legerement la version robuste

Attendu : la mediane et l'ecart interquartile devaient l'emporter sur la moyenne et l'ecart type,
puisqu'une valeur extreme gonfle l'ecart type et se masque elle-meme.

Mesure : les deux versions naives font un peu **mieux** (AP 49,7 et 50,2 contre 47,1).

L'explication est la limite centrale de cette evaluation : l'etiquette est un detecteur de gros
montants, et l'ecart a la famille est correle a **0,98** au montant brut. Classer par montant donne
donc presque raison d'avance.

**Consequence a enoncer dans le memoire : cette etiquette ne sait pas departager ces trois
variantes.** Elle valide une direction de recherche, pas la finesse d'un calcul. Le choix de la
version robuste repose donc aujourd'hui sur un argument de methode, non sur une mesure. Le
departage demande un echantillon juge a la main, et c'est le premier point de la suite.

### 3. Local Outlier Factor avait ete ecarte sur une idee recue

L'ADR 0006 l'ecartait pour « cout quadratique, impraticable sur 2 millions de lignes ». Mesure :
la duree **par ligne** n'augmente que de 60 % quand la taille passe de 25 000 a 400 000 lignes, la ou un cout quadratique l'aurait multipliee par 16, et la methode traite le jeu
complet en **15,8 secondes** (mesure separee de la memoire : environ 1,7 Go). En cinq dimensions, scikit-learn indexe les
points dans un arbre et la recherche de voisins devient quasi lineaire ; la reputation de LOF vient
de son comportement en grande dimension.

La methode est donc praticable. Elle est simplement mauvaise ici (AP 3,96 %). L'ecarter reste
justifie, mais pour la bonne raison.

### 4. Une graine fixe ne suffit pas a rendre un calcul reproductible

Deux lancements du meme script, meme graine et memes donnees, donnaient **100,0 % puis 74,0 %**.
Trois causes empilees :

1. DuckDB execute en parallele et ne garantit aucun ordre de lignes sans `order by`. Isolation
   Forest tire ses echantillons **par position**.
2. `order by uid` n'a pas suffi : **uid identifie un marche, pas une ligne**. Mesure : 140 350 uid
   apparaissent plusieurs fois, soit 281 404 lignes en trop sur 2 054 924, et **619 uid portent des
   montants contradictoires** d'une ligne a l'autre.
3. Le tri porte donc sur toutes les colonnes utilisees.

Effet de bord utile : le point 2 est un defaut de qualite des donnees qui n'avait pas ete vu, et
qui est maintenant mesure.

### 5. ROC AUC aurait conduit a un mauvais choix

Les k-moyennes affichent **71,5 %** d'AUC pour **2,0 %** de precision a mille alertes. Le SVM
affiche une AUC **sous 50 %**, donc un classement globalement pire que le hasard, tout en placant
des vrais positifs dans ses premiers rangs. Avec 3 % de positifs, bien ordonner la masse des
marches ordinaires suffit a gonfler l'AUC. Elle est conservee dans les tableaux uniquement comme
contre-exemple.

## Alternatives examinees

| Option | Pour | Contre | Verdict |
|---|---|---|---|
| **Regles explicites** | explicables, sans dependance, instantanees, verifiables ligne a ligne | ne trouvent que ce qu'on a pense a chercher | **retenu** |
| Isolation Forest en remplacement | trouve des combinaisons inattendues | AP 41 % orientee contre 47 % pour la regle, et n'explique rien | ecarte par la mesure |
| Isolation Forest **en complement**, sur le cote « montant bas » | couvre une zone que la regle laisse de cote | aucune etiquette ne permet de l'evaluer | **garde comme signal non evalue** |
| ACP orientee | la meilleure des methodes apprises, AP 50,0 % | egale la meilleure statistique sans rien expliquer de plus, et demande une normalisation a maintenir | ecarte, a reconsiderer si le jury le demande |
| Local Outlier Factor | standard du domaine | AP 3,96 %, et 15,8 s contre un calcul SQL instantane | ecarte par la mesure |
| Apprentissage supervise | le plus performant quand il s'applique | aucune etiquette fiable | exclu par le sujet |

## Consequences

**Positives**

- Le choix des regles ne repose plus sur un raisonnement mais sur dix mesures comparables.
- Le protocole a budget egal est reutilisable tel quel pour le prochain signal.
- Trois defauts ont ete trouves en chemin : la non-reproductibilite, la non-unicite de `uid`, et
  une alternative ecartee sur une idee recue.

**Negatives et limites, a enoncer dans le memoire**

- **L'etiquette ne departage pas les variantes de la regle.** C'est la limite principale, et elle
  n'est pas corrigeable sans travail humain.
- Les scores d'Isolation Forest comportent beaucoup d'ex aequo : 419 008 valeurs distinctes pour
  2 053 765 marches, et 491 marches a egalite avec le centieme score. Les precisions sur petit
  budget sont donc a lire comme des ordres de grandeur.
- Le modele oriente depend fortement de `max_samples` : 57,3 % a 64 echantillons, 90,2 % a 1024,
  alors que la valeur recommandee par les auteurs est 256. Un defaut de bibliotheque n'est pas une
  verite.
- La comparaison porte sur le seul signal de prix. Les signaux d'offre unique et de titulaire
  dominant n'ont pas encore ete compares a un modele.

## A mesurer ensuite

1. **Un echantillon juge a la main**, pour obtenir une etiquette qui ne vienne pas d'un detecteur
   de montants, et departager enfin la regle robuste de ses versions naives.
2. L'apport reel des quatre variables autres que l'ecart : le modele oriente fait-il mieux que
   l'ecart seul, ou seulement aussi bien ?
3. La meme comparaison sur le signal d'offre unique, qui ne depend pas du montant et n'entretient
   donc pas cette parente genante avec l'etiquette.
