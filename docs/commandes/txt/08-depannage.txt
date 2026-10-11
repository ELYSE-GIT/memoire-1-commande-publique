# 08. Depannage : erreurs rencontrees et solutions

Fiche alimentee au fil de l'eau. Chaque entree suit le meme format : le symptome exact, la cause,
la solution, et la prevention mise en place pour que ca ne revienne pas.

Les entrees detaillees, avec le contexte et le temps perdu, sont dans `docs/journal/`. Cette fiche
n'en garde que la solution, pour aller vite.

## Modele d'entree

### Symptome

Le message d'erreur exact, copie tel quel.

### Cause

Ce qui se passait reellement.

### Solution

Les commandes a lancer.

### Prevention

Le test, le controle ou la ligne de documentation ajoutee pour eviter la prochaine fois.

## Bloque par la protection de la branche main

### Symptome

```
! [remote rejected] main -> main (protected branch hook declined)
```

### Cause

C'est le fonctionnement normal. La branche `main` refuse les push directs, les reecritures
d'historique et les suppressions, y compris pour le proprietaire du depot (`enforce_admins: true`).

### Solution normale

Passer par une branche et une pull request.

```bash
git switch -c fix/ma-correction
git add -p && git commit -m "fix(portee): description"
git push -u origin fix/ma-correction
gh pr create --fill
# attendre la CI verte, puis
gh pr merge --squash --delete-branch
```

### Solution d'urgence, a n'utiliser qu'en dernier recours

Lever la protection, corriger, la remettre immediatement. A noter dans le journal a chaque usage.

```bash
gh api -X DELETE repos/ELYSE-GIT/memoire-1-commande-publique/branches/main/protection
# la correction
gh api -X PUT repos/ELYSE-GIT/memoire-1-commande-publique/branches/main/protection --input infra/protection-main.json
```

### Verifier que la protection est active

```bash
gh api repos/ELYSE-GIT/memoire-1-commande-publique/branches/main/protection \
  --jq '{checks: .required_status_checks.contexts, admins: .enforce_admins.enabled}'
```

Resultat attendu : les deux controles de la CI, et `admins: true`.

---

## `role "commande_publique" does not exist` alors que la base tourne

**Symptome** : `make charger` echoue sur un role inexistant, mais `make psql` fonctionne et
`\du` montre bien le role.

**Cause** : un autre PostgreSQL occupe le port. Les connexions partent vers lui, et son message
d'erreur decrit **sa** base, pas celle du projet.

**Diagnostic** :

```bash
lsof -nP -iTCP:5432 -sTCP:LISTEN
docker compose port base 5432
```

Si la premiere commande montre un `postgres` qui n'est pas le conteneur, c'est lui. La seconde dit
sur quel port le conteneur est reellement publie.

**Correction** : le projet ecoute sur 55432, defini par `POSTGRES_PORT` dans `.env`. Si le conflit
revient sur un autre port, changer cette valeur puis `make down && make up`.

**Lecon generale** : quand un message d'erreur decrit quelque chose d'impossible, verifier d'abord
a qui l'on parle.

## Le conteneur demarre mais reste `starting`

**Symptome** : `make etat` montre `Up (health: starting)` qui ne passe jamais a `healthy`.

**Diagnostic** :

```bash
docker compose logs base | tail -30
```

**Causes vues** : une variable absente de `.env`, un volume de donnees cree par une version
differente de PostgreSQL, ou la memoire partagee insuffisante. Les trois apparaissent en clair
dans les journaux.

## Repartir d'une base vide

```bash
make down
docker volume rm commande-publique-base-donnees
make up && make base-init && make charger && make indexer
```

La deuxieme ligne **supprime definitivement** les donnees de la base. Elles se reconstruisent
entierement depuis DuckDB, donc il n'y a rien a sauvegarder, mais il faut une vingtaine de minutes.
