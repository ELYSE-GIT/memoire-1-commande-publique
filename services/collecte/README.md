# services/collecte

Recupere les trois sources du projet et les depose dans la couche bronze, sans les modifier.

## Les commandes

| Commande | Ce qu'elle fait | Duree |
|---|---|---|
| `make collecte-decp` | telecharge le jeu DECP consolide en Parquet | environ 5 s |
| `make collecte-boamp` | recupere les avis du BOAMP par l'API, page par page | quelques minutes |
| `make collecte` | les deux, puis ecrit le manifeste | |

## Ce qui est garanti

**Idempotence.** Relancer une collecte interrompue ne cree ni doublon ni fichier incomplet. Le
telechargement passe par un fichier temporaire renomme a la fin ; le manifeste remplace l'entree
du jour au lieu d'en ajouter une seconde.

**Tracabilite.** Chaque collecte ecrit une entree dans `donnees/manifestes/AAAA-MM-JJ.json` :
la source, l'adresse exacte, la date, la taille et l'empreinte SHA-256 du fichier. Le manifeste
est versionne, la donnee ne l'est pas.

**Menagement des sources.** Six appels par seconde au maximum, la ou les API publiques en
annoncent sept. Reprise sur erreur avec attente croissante, et distinction entre les erreurs
passageres, que l'on retente, et les erreurs definitives, que l'on ne retente pas.

## Ou vont les fichiers

```
donnees/
  bronze/
    decp/2026-09-28/decp.parquet        la donnee brute, jamais modifiee, jamais versionnee
    boamp/2026-09-28/avis.jsonl
  manifestes/
    2026-09-28.json                     la trace de ce qui a ete collecte, versionnee
```

## Pourquoi pas d'orchestrateur pour l'instant

Voir `docs/adr/0004-collecte-et-couche-bronze.md`. En resume : trois sources, aucune dependance
entre elles, une execution par jour au plus. Un orchestrateur se justifie quand les dependances
se multiplient, et la decision sera reprise a ce moment-la, avec la mesure qui la motive.
