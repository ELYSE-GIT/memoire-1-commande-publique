# Plateforme open source d'intelligence sur la commande publique francaise

Chaque annee, l'Etat et les collectivites passent environ 230 000 marches publics, pour plus de
230 milliards d'euros. Ces donnees sont publiques, mais dispersees, incompletes et pleines de
doublons. Ce projet les rassemble, les nettoie, signale les marches atypiques et aide une PME a
trouver les appels d'offres faits pour elle.

Memoire de fin d'etudes, EFREI Paris. Auteur : Elyse Rasoloarivony ([ELYSE-GIT](https://github.com/ELYSE-GIT)).

## La these defendue

Une plateforme de qualite professionnelle, securisee et maintenable, pour une fraction du cout des
offres d'AWS, Azure, Google Cloud, Databricks, Snowflake ou OpenAI. Chaque affirmation est prouvee
par une mesure : qualite, performance, cout. Les protocoles et les resultats sont dans `mesures/`.

## Les sources de donnees

| Source | Contenu | Acces |
|---|---|---|
| DECP v3 | les marches publics attribues | data.economie.gouv.fr |
| BOAMP | les avis d'appels d'offres | boamp.fr |
| API Recherche d'entreprises | l'identite des entreprises (SIRENE) | recherche-entreprises.api.gouv.fr |

## Demarrer

Prerequis : macOS, Homebrew, git. Le detail est dans
[docs/commandes/01-installation-mac.md](docs/commandes/01-installation-mac.md).

```bash
brew install uv colima docker docker-compose pre-commit gitleaks
make install          # cree le .venv et installe les dependances verrouillees
make verif            # style, types, tests, recherche de secrets
```

`make help` affiche toutes les commandes disponibles, avec une ligne d'explication chacune.

## Voir le site

```bash
make up            # PostgreSQL
make site          # les pages et l'API, dans un seul processus
```

Puis <http://localhost:8000/> pour le site, et <http://localhost:8000/docs> pour la
documentation interactive de l'API, generee depuis le code.

| Adresse | Ce qu'elle rend |
|---|---|
| `/` | les comptages, la courbe par annee, par ou commencer |
| `/recherche` | la recherche par texte et par filtres |
| `/fiche/{marche_id}` | un marche, ses titulaires, ce qui a ete remarque dessus |
| `/a-examiner` | les marches atypiques, avec leurs motifs en clair |
| `/questions` | une question en francais, avec ses citations |
| `/a-propos` | les sources, les limites, la methode |
| `/api/...` | les memes donnees en JSON |

Le site est fabrique par le serveur, avec des gabarits et htmx : aucune compilation, aucun
Node.js, et chaque page fonctionne sans JavaScript. Le demarrage prend une dizaine de secondes,
dont le prechauffage de la base, pour que le premier visiteur n'attende pas.

## Sobriete

Rien ne tourne en permanence sur la machine de developpement. On demarre la VM des conteneurs pour
une tache (`make vm-up`), on l'arrete apres (`make vm-down`). Les ressources sont plafonnees a
4 CPU et 6 Go de RAM. `make clean-all` supprime tout ce que le projet a cree sur la machine.

## Organisation du depot

```
services/         un dossier et un conteneur par service
base/             schema SQL et migrations
infra/            Caddy, Prometheus, Grafana, Ansible
analyses/         exploration des donnees
mesures/          protocoles de mesure et resultats
docs/             commandes, decisions, journal, runbook, demo
memoire/          sources du memoire et figures
tests/            tests automatises
```

Chaque dossier a son propre `README.md` qui explique son role.

## Qualite

Ruff pour le style, mypy pour les types, pytest pour les tests, pre-commit avant chaque commit,
gitleaks contre les secrets. La chaine d'integration continue rejoue tout a chaque push et a chaque
pull request. La branche `main` n'accepte que des pull requests avec une CI verte.

## Licence

A definir avant la publication finale.
