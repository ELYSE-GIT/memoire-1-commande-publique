# services

Un dossier par service, un conteneur par service. Chaque service a son `Dockerfile`.

| Dossier | Role | Phase |
|---|---|---|
| `collecte/` | recupere les donnees DECP, BOAMP et SIRENE, pipelines Dagster | 3 |
| `transformation/` | nettoie et modelise en SQL avec dbt (bronze, silver, gold) | 3 |
| `api/` | expose les donnees en HTTP avec FastAPI, sous le prefixe `/api` | 7 |
| `assistant/` | recherche et reponses sourcees, modele local | 5 |
| `site/` | interface publique (gabarits Jinja2 et htmx), puis espace admin | 7 |
