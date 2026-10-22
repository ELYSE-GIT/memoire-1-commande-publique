# mesures

Chaque affirmation du memoire est prouvee par une mesure reproductible.

- Les scripts de mesure se lancent par `make bench-<composant>`.
- Les resultats sont ecrits en CSV ou JSON, avec la date, la machine (Mac ou VPS),
  les versions des outils et le jeu de donnees utilise.
- Les figures du memoire sont generees a partir de ces fichiers, jamais saisies a la main.

Metriques suivies : latence p50 et p95, debit, duree, RAM et CPU maximum, taille disque,
qualite (metriques ML, taux d'erreurs dans les donnees), cout en euros par mois.

## Mesures disponibles

| Commande | Ce qu'elle mesure | Duree |
|---|---|---|
| `make bench-decp` | qualite et performance sur le jeu DECP consolide | environ 30 s |
| `make bench-decp-distributions` | agregats descriptifs : tranches, total annuel, saisonnalite, acheteurs, CPV, offres | environ 40 s |
| `make bench-nettoyage` | effet de chaque regle de nettoyage, couche par couche | environ 10 s |
| `make bench-detection` | precision et rappel de la regle de prix, par seuil | environ 15 s |
| `make bench-modele` | les regles contre un modele non supervise, a budget d'alertes egal | environ 30 s |
| `make bench-rapprochement` | part des avis du BOAMP reliables aux DECP | environ 3 min |
| `make bench-precision` | justesse du rapprochement, par relecture de 60 paires | environ 5 s |
| `make bench-recherche` | recherche plein texte, PostgreSQL contre DuckDB, sur 30 questions | environ 7 min |
| `make bench-assistant` | l'assistant sur 40 questions : intentions, citations, coherence, latence | environ 1 min |
| `make bench-incertitude` | intervalle a 95 % de chaque pourcentage tire d'un echantillon | environ 1 s |
| `make bench-stabilite` | la regle de detection calee sur 2019-2023, appliquee a 2024-2026 | environ 2 s |
| `make bench-api` | l'API publique : latence par route, montee en charge, cout du classement | environ 4 min |
| `make bench-site` | le site : poids de chaque page, gain du fragment htmx, rendu sans JavaScript | environ 1 min |
| `make figures` | trace les 25 figures du memoire depuis ces agregats | environ 5 s |

Les resultats sont dans `resultats/`. Les figures du memoire sont tracees **depuis ces fichiers**,
jamais saisies a la main : c'est ce qui garantit qu'un chiffre affiche dans le memoire existe dans
un fichier qu'on peut ouvrir et verifier.

Deux fichiers ne sont pas des mesures mais des **entrees** du protocole, ecrites a la main et
versionnees pour pouvoir etre relues :

| Fichier | Role |
|---|---|
| `verification/2026-09-27-verdicts-rapprochement.csv` | 60 paires jugees a la main |
| `verification/questions-de-recherche.csv` | 30 questions de test de la recherche |
| `verification/questions-assistant.csv` | 40 questions de test de l'assistant, avec le comportement attendu |
| `mots-vides-francais.txt` | liste de PostgreSQL, donnee a DuckDB pour que la comparaison soit valide |

## Comment une figure du memoire est produite

```
donnees/brut/decp.parquet          le fichier public, jamais versionne
        |
        |  make bench-decp-distributions
        v
mesures/resultats/*.csv            les agregats, versionnes, quelques Ko
        |
        |  make figures
        v
memoire/figures/*.svg et *.png     les figures du memoire
```

Aucune figure ne lit le fichier Parquet, et aucun chiffre du memoire n'est saisi a la main.
Consequence : reproduire une figure ne demande pas de retelecharger 240 Mo, et chaque valeur
affichee existe dans un fichier que l'on peut ouvrir et verifier.
