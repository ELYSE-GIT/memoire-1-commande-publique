# base

Schema de la base PostgreSQL, en SQL lisible.

- `schema/` : tables, index, extensions (dont pgvector pour la recherche par similarite).
- `migrations/` : chaque changement de schema, numerote, jamais modifie apres coup.

Regle : aucun schema cree a la main dans la console. Tout passe par un fichier `.sql` versionne.
