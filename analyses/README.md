# analyses

Exploration des donnees. C'est le brouillon du projet, et la preuve de la demarche.

| Notebook | Sujet | Etat |
|---|---|---|
| `01-exploration-decp.ipynb` | structure, doublons, montants, dates et offres du jeu DECP consolide | fait, 2026-09-20 |

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
