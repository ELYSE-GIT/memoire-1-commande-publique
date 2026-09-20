# ADR 0001. Le socle technique de developpement

- Date : 2026-09-20
- Statut : accepte
- Phase : 1, environnement et reflexes

## Contexte

Le projet doit tenir trois promesses qui pesent sur le choix des outils de base.

1. Il doit etre **reproductible** : une autre machine, ou le VPS, doit obtenir exactement le meme
   environnement, sans surprise de version.
2. Il doit etre **sobre** : la machine de developpement est un MacBook M2 Pro de 16 Go, utilise au
   quotidien pour autre chose. Rien ne doit tourner en permanence.
3. Il doit etre **demontrable** : le depot doit s'expliquer en le parcourant, et chaque commande
   doit etre rejouable par son auteur seul, devant un jury.

## Decision

| Besoin | Choix | Alternatives ecartees | Pourquoi |
|---|---|---|---|
| Python et dependances | **uv** | pip et venv, Poetry, conda | uv installe la version de Python, resout et verrouille les dependances, le tout en une seule commande et en quelques secondes. Le fichier `uv.lock` est versionne, donc l'environnement est identique partout. Poetry fait presque autant mais reste nettement plus lent. conda tire un ecosysteme parallele dont le projet n'a pas besoin. |
| Conteneurs sur le Mac | **Colima** | Docker Desktop, Podman, OrbStack | Colima se demarre et s'arrete a la demande, avec des ressources plafonnees explicitement. Docker Desktop tourne en permanence et impose une licence payante au dela de 250 salaries, ce qui affaiblirait la these du cout. OrbStack est plus rapide mais n'est pas libre. Podman est libre, mais Colima colle mieux a une demo qui utilise `docker compose`. |
| Style et erreurs | **Ruff** | Flake8 plus Black plus isort | Ruff remplace les trois, avec un seul fichier de configuration et un temps d'execution de l'ordre de la centaine de millisecondes. |
| Types | **mypy** en mode strict | pyright, aucun typage | Le typage strict attrape en amont les erreurs de forme des donnees, frequentes sur des sources publiques irregulieres. mypy est la reference de l'ecosysteme Python. |
| Tests | **pytest** avec couverture | unittest | Syntaxe plus legere, fixtures, et un ecosysteme de greffons large. |
| Avant commit | **pre-commit** avec **gitleaks** | verification manuelle, hook maison | Un secret publie sur un depot public est considere comme compromis, meme efface ensuite. La verification doit etre automatique et bloquante. |
| Integration continue | **GitHub Actions** | GitLab CI, Jenkins | Le depot est sur GitHub, l'integration est native, et le service est gratuit pour un depot public. |

## Consequences

**Positives**

- Un nouvel arrivant installe tout avec deux commandes : `brew install ...` puis `make install`.
- Les versions sont verrouillees dans `uv.lock`, donc la CI, le Mac et le VPS executent la meme chose.
- Aucun service ne tourne en arriere-plan entre deux sessions de travail.
- Le cout de cette couche est de zero euro, un point a mesurer et a comparer dans le memoire.

**Negatives et limites**

- Colima ajoute une etape (`make vm-up`) que Docker Desktop evite. C'est le prix de la sobriete, et
  cette etape est documentee dans la fiche du quotidien.
- mypy en mode strict ralentit l'ecriture des premieres lignes de chaque module.
- uv est un outil jeune. En cas de blocage, la solution de repli reste `pip` avec un
  `requirements.txt` exporte depuis `uv.lock`.

## A mesurer

Ces chiffres serviront le chapitre sur les couts et la performance du poste de developpement.

- Duree de `make install` a froid et a chaud.
- RAM consommee par Colima au repos et en charge, comparee a Docker Desktop.
- Duree complete de `make verif` en local, puis de la CI sur GitHub Actions.
