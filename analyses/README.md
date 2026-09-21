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

## Methode

On explore ici, on industrialise ailleurs. Un notebook sert a poser une question, regarder, et
laisser la reponse orienter la question suivante. Quand une mesure est stabilisee, elle part dans
`mesures/` sous forme de script rejouable, et le traitement part dans `services/`.

Les notebooks sont versionnes **avec leurs resultats**, pour qu'ils se lisent sans etre executes.
Ils restent rejouables d'un bout a l'autre : `make notebook-decp`.

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
