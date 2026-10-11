# 02. Le quotidien : demarrer, arreter, verifier

Les commandes d'une session de travail normale. Toutes se lancent a la racine du projet, sur le Mac.

## Ouvrir une session

| Commande | Ce que ca fait | Duree |
|---|---|---|
| `make install` | remet le `.venv` a jour si les dependances ont change | 5 s a 2 min |
| `make vm-up` | demarre la VM des conteneurs (4 CPU, 6 Go) | 30 s |
| `make up` | demarre les services du projet | 10 s |
| `make etat` | montre la VM et les conteneurs en cours | 2 s |

Tant qu'on ne travaille pas sur les services, `make vm-up` est inutile. Le code Python, les tests et
le style tournent sans conteneur.

## Pendant le travail

| Commande | Ce que ca fait |
|---|---|
| `make lint` | signale les erreurs de style et les pieges courants |
| `make format` | reformate le code automatiquement |
| `make types` | verifie la coherence des types |
| `make test` | lance les tests avec le taux de couverture |
| `make verif` | les quatre d'un coup, comme la CI |

Reflexe : lancer `make verif` avant de committer. Si c'est vert en local, la CI sera verte.

## Fermer la session

| Commande | Ce que ca fait |
|---|---|
| `make down` | arrete les services |
| `make vm-down` | arrete la VM des conteneurs |
| `make etat` | verifie qu'il ne reste rien qui tourne |

Regle de sobriete : le Mac est une machine personnelle. En fin de session, plus rien ne tourne, pas
de demarrage automatique au login, pas de serveur oublie.

## Git au quotidien

```bash
git switch -c feat/collecte-decp     # une branche par fonctionnalite
git add -p                            # relire chaque morceau avant de l'ajouter
git commit -m "feat(collecte): ajoute le telechargement des DECP"
git push -u origin feat/collecte-decp
gh pr create --fill                   # ouvre la pull request
```

Les messages suivent la convention `type(portee): description` :
`feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`.

La branche `main` est protegee : aucun push direct, une pull request avec une CI verte.

## Nettoyer

| Commande | Ce que ca fait |
|---|---|
| `make clean` | supprime les caches Python et les rapports de tests |
| `make clean-all` | supprime en plus le `.venv`, les donnees locales, les conteneurs, les volumes et les images du projet |
| `colima delete` | supprime la VM entierement, y compris son disque de 40 Go |

---

## La base de service PostgreSQL

Depuis la phase 6, le projet a un **service** : une base PostgreSQL, qui tourne dans un conteneur.
Elle ne doit tourner que pendant une session de travail.

### Demarrer

```bash
make vm-up    # la machine Linux qui fait tourner les conteneurs, une fois par session
make up       # PostgreSQL lui-meme
make etat     # verifier : la VM et le conteneur doivent apparaitre
```

**Duree** : 1 a 2 minutes pour `make vm-up` la premiere fois, 20 secondes ensuite. `make up` prend
quelques secondes.

**Resultat attendu** : `make etat` affiche `colima is running` et une ligne
`commande-publique-base   Up (healthy)`. Le mot **healthy** compte : il veut dire que la base
repond vraiment, pas seulement que le conteneur est lance.

### Arreter, et ce n'est pas optionnel

```bash
make down       # arrete PostgreSQL, garde les donnees
make vm-down    # eteint la machine Linux
```

C'est la machine personnelle d'Elyse : rien ne doit rester allume apres une session. Aucun service
du projet ne redemarre tout seul, c'est voulu.

### Ouvrir une console SQL

```bash
make psql
```

**Resultat attendu** : une invite `commande_publique=#`. Quitter avec `\q`.

Quelques commandes utiles dans cette console : `\dt` liste les tables, `\d marches` decrit une
table, `\di+` liste les index avec leur taille.

### Le port, et pourquoi il n'est pas 5432

La base du projet ecoute sur **55432** et non sur le port standard. Un PostgreSQL installe
directement sur le Mac occupait deja 5432, et les connexions du projet tombaient sur lui, avec un
message trompeur (`role "commande_publique" does not exist`) alors que le conteneur fonctionnait.

Le conteneur, lui, ecoute toujours sur 5432 a l'interieur. Seul le port cote machine change, et il
est defini par `POSTGRES_PORT` dans `.env`.
