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
| `make bench-decp` | qualite et performance sur le jeu DECP consolide | environ 2 s |

Les resultats sont dans `resultats/`, un fichier JSON et un CSV par execution, nommes par la date.
Le JSON contient le contexte complet : machine, versions de Python et de DuckDB, taille du fichier
mesure. Sans ce contexte, une mesure n'est pas comparable a une autre.
