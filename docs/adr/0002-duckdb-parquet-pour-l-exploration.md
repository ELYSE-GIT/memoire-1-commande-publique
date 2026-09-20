# ADR 0002. DuckDB et Parquet pour l'exploration des donnees

- Date : 2026-09-20
- Statut : accepte
- Phase : 2, regarder les vraies donnees

## Contexte

Le jeu principal du projet fait 3,28 millions de lignes et 66 colonnes. Avant d'ecrire le moindre
pipeline, il faut pouvoir poser des questions dessus : combien de doublons, quels montants
aberrants, quels champs manquants. La machine de developpement est un MacBook de 16 Go utilise au
quotidien pour autre chose, et la regle de sobriete interdit qu'un service tourne en permanence.

Le producteur publie le meme jeu dans deux formats : Parquet (247,6 Mo) et CSV (2 595,5 Mo).

## Decision

Explorer avec **DuckDB**, en lisant directement le fichier **Parquet**, sans base de donnees
demarree et sans import prealable.

| Option | Pour | Contre | Retenu |
|---|---|---|---|
| **DuckDB sur Parquet** | aucun serveur, aucun import, lit le fichier sur place, SQL complet, quelques dizaines de millisecondes par requete | moteur mono-machine, pas fait pour servir des utilisateurs simultanes | **oui, pour l'exploration** |
| pandas sur CSV | connu de tous, ecosysteme immense | 2,6 Go a charger en memoire, plusieurs minutes, risque de saturer les 16 Go | non |
| polars | tres rapide, API moderne, lit aussi le Parquet | il faudrait apprendre une API de plus, alors que le SQL est deja exige par le memoire et par dbt | non a ce stade |
| PostgreSQL | la base de l'application finale | installer, creer un schema, importer 3,3 M de lignes avant la premiere question | oui plus tard, pour servir le site |
| Spark | passe a l'echelle sur un cluster | complexite et consommation sans rapport avec 3,3 M de lignes sur un portable | non |

Le stockage reste en Parquet pour la couche brute. Le CSV n'est pas telecharge.

## Consequences

**Positives**

- Le fichier se telecharge en environ 5 secondes et s'interroge sans rien installer de plus.
- Le comptage des lignes prend 0,009 s : Parquet range le nombre de lignes dans ses metadonnees.
  Les agregations reelles prennent de 0,01 a 0,7 seconde, une comparaison ligne a ligne sur les
  66 colonnes prend 7,3 secondes. Ces ordres de grandeur sont a citer separement, sans quoi la
  mesure paraitrait truquee.
- Le SQL ecrit ici se reutilisera presque tel quel dans les modeles dbt de la phase 4.
- Cout : 0 euro, contre un entrepot gere facture a l'heure de calcul.

**Negatives et limites**

- DuckDB est mono-machine. Il ne remplacera pas PostgreSQL pour servir le site.
- Les donnees brutes ne sont pas versionnees, donc une mesure n'est reproductible que si l'on note
  la date de publication du fichier. C'est le role du bloc de contexte ecrit par `make bench-decp`.
- Le jeu est republie chaque matin : deux mesures prises a deux jours d'ecart ne portent pas
  exactement sur les memes donnees.

## Mesures qui justifient ce choix

Relevees le 2026-09-20 sur MacBook M2 Pro, Python 3.12.9, DuckDB 1.5.5.

| Mesure | Valeur |
|---|---|
| Taille Parquet contre CSV | 247,6 Mo contre 2 595,5 Mo, soit 10,5 fois moins |
| Telechargement du Parquet | environ 5 s |
| Comptage de 3,28 M de lignes | 0,009 s |
| Huit mesures de qualite enchainees | environ 1,3 s au total |
| Execution complete du notebook | environ 4 s |
| Memoire vive utilisee | tient largement dans les 16 Go, sans reglage particulier |

## A decider plus tard

Le nombre d'offres recues manque dans 58 % des lignes, alors que c'est l'indicateur de risque
principal de la litterature. Trois pistes : se restreindre au sous-ensemble renseigne en mesurant le
biais, croiser avec le BOAMP, ou changer d'indicateur. Un ADR distinct tranchera avant la phase 5.
