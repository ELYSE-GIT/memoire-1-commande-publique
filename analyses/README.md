# analyses

Exploration des donnees. C'est le brouillon du projet, et la preuve de la demarche.

| Notebook | Sujet | Etat |
|---|---|---|
| `01-exploration-decp.ipynb` | structure, doublons, montants, dates et offres du jeu DECP consolide | fait, 2026-09-20 |
| `02-statistiques-descriptives.ipynb` | distributions, saisonnalite, acheteurs, familles CPV, normalisation | fait, 2026-09-20 |
| `03-lecture-visuelle.ipynb` | les 15 figures commentees : ce qu'elles disent, ce qu'elles ne disent pas | fait, 2026-09-21 |
| `04-exploration-boamp.ipynb` | BOAMP : volumetrie, avis ouverts, delais, rapprochement avec les DECP | fait, 2026-09-21 |
| `05-comment-le-projet-se-verifie.ipynb` | les tests, ce qu'ils attrapent, ce qu'ils ratent, et un echec en direct | fait, 2026-09-21 |
| `06-api-recherche-entreprises.ipynb` | resolution des SIRET, part des PME, demonstration du biais de selection | fait, 2026-09-21 |
| `07-rapprochement-des-sources.ipynb` | relier le BOAMP aux DECP : entonnoir, reglage des parametres, justesse mesuree | fait, 2026-09-27 |
| `08-modelisation-detection.ipynb` | dix methodes de detection comparees a budget d'alertes egal, hyperparametres manipulables | fait, 2026-09-29 |

Un script accompagne ces notebooks : `verifier_notebooks.py`, lance par `make verif-notebooks`. Il
controle que chaque cellule est du Python valide, qu'aucune ne porte de sortie d'erreur et que
toutes ont ete jouees. Il existe parce que `jupyter execute` **rend un code de sortie 0 meme quand
une cellule leve une exception**.

## Methode

On explore ici, on industrialise ailleurs. Un notebook sert a poser une question, regarder, et
laisser la reponse orienter la question suivante. Quand une mesure est stabilisee, elle part dans
`mesures/` sous forme de script rejouable, et le traitement part dans `services/`.

`ruff format` reecrit aussi les cellules de code des notebooks. Il faut donc formater **avant**
de rejouer, sinon le depot contient des sorties enregistrees pour un code qui a change depuis.
`make notebooks` le fait dans le bon ordre.

Les notebooks sont versionnes **avec leurs resultats**, pour qu'ils se lisent sans etre executes.
Ils restent rejouables d'un bout a l'autre : `make notebooks`, puis `make verif-notebooks`.

Les cellules de reglage sont marquees d'un commentaire `A MODIFIER` : budgets d'alertes,
hyperparametres, grilles de comparaison. Elles sont regroupees pour pouvoir etre changees en
direct, pendant une demonstration, sans avoir a relire tout le notebook.

## Ce qu'on a appris ici

- 3 283 035 lignes pour 1 833 468 marches reels : la difference vient de l'historique des
  modifications et des groupements d'entreprises, pas de doublons.
- Environ 7 800 doublons residuels seulement, et aucune ligne strictement identique a une autre.
- 58 % des lignes n'indiquent pas le nombre d'offres recues, alors que c'est l'indicateur de risque
  principal de la litterature. Decision a prendre avant la phase 5.
- Le total annuel brut est faux d'un facteur dix a vingt : 3 030 milliards d'euros annonces pour
  2020, contre environ 230 milliards reels. Ecarter les montants deja signales par le producteur
  suffit a revenir dans le bon ordre de grandeur.
- La commande publique suit le calendrier budgetaire : pics en decembre et en juillet, creux en aout.
- 59,2 % des marches sont attribues a une PME, mesure independante qui retrouve les 60 % publies par
  l'Etat. La meme mesure sur un echantillon mal construit donne 5 %.
- La construction (division CPV 45) represente a elle seule plus du triple de la famille suivante.
- Sur dix methodes de detection comparees a budget d'alertes egal, **aucun modele ne depasse une
  statistique descriptive**. Un modele non supervise laisse libre tombe meme sous le hasard, parce
  qu'il cherche les montants anormalement bas, que l'etiquette disponible ne marque jamais.
- `uid` identifie un marche, pas une ligne : 140 350 uid sont partages par plusieurs lignes, et 619
  portent des montants contradictoires. Cela a rendu une mesure non reproductible avant d'etre vu.
- Une graine fixe ne suffit pas a rendre un calcul reproductible : il faut aussi un ordre de lignes
  fixe, parce que DuckDB n'en garantit aucun sans `order by`.
