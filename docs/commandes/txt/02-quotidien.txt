# 02. Le quotidien : demarrer, arreter, verifier

Les commandes d'une session de travail normale. Toutes se lancent a la racine du projet, sur le Mac.

## Ouvrir une session

| Commande | Ce que ca fait | Duree |
|---|---|---|
| `make install` | remet le `.venv` a jour si les dependances ont change | 5 s a 2 min |
| `make vm-up` | demarre la VM des conteneurs (4 CPU, 6 Go) | 30 s |
| `make up` | demarre les services du projet | 10 s |
| `make api` | demarre l'API publique (necessite `make up`) | 1 s |
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

## L'API publique

Depuis la phase 7, le projet a un second service : l'API, qui sert les marches, les signaux, les
comptages et l'assistant. Elle a besoin de PostgreSQL, donc de `make up` avant.

### Demarrer

```bash
make up        # PostgreSQL d'abord, sinon l'API demarre en mode degrade
make api       # l'API, rechargee a chaque modification du code
```

**Duree** : moins d'une seconde pour le demarrage, dont le chargement des lexiques de
l'assistant (74 055 lexemes, 24 regions, 107 departements).

**Resultat attendu** : `Uvicorn running on http://127.0.0.1:8000`. Ouvrir
<http://localhost:8000/docs> : la documentation interactive est generee depuis le code, donc
toujours a jour. Chaque route y est essayable directement dans le navigateur, ce qui est le plus
court chemin pour montrer l'API en soutenance.

**Arreter** : Ctrl-C dans le terminal. L'API ne redemarre pas toute seule, comme le reste.

### Verifier qu'elle va bien

```bash
curl -s http://localhost:8000/sante
```

**Resultat attendu** :

```json
{"etat":"pret","base_accessible":true,"marches_charges":1999474,"lexiques_charges":true}
```

Les deux cas a savoir lire :

- `"etat":"degrade"` avec `"base_accessible":false` : PostgreSQL n'est pas demarre. L'API
  fonctionne quand meme et le dit, plutot que de refuser de demarrer. C'est voulu : en
  demonstration, un service qui refuse de demarrer ne permet meme plus de comprendre ce qui
  manque.
- `"marches_charges":null` : la base est joignable mais la table des comptages est vide. Il
  manque `make indexer` apres le chargement.

### Trois appels pour la demonstration

```bash
curl -s "http://localhost:8000/marches?q=travaux+de+voirie&annee=2024" | head -40
curl -s "http://localhost:8000/signaux?taille=3"
curl -s "http://localhost:8000/assistant?question=combien+de+marches+de+voirie+en+Bretagne+en+2024"
```

Le troisieme est celui a montrer : la reponse porte la phrase, les chiffres, le filtre applique
en francais et les numeros de marche cites, verifiables un par un sur `/marches/{marche_id}`.

### `classement_approche`, et pourquoi il faut savoir l'expliquer

La reponse d'une recherche contient deux champs qu'il faut pouvoir justifier devant un jury :

```json
{"classement_approche": true, "candidats_examines": 5000}
```

Le service ne classe que 5 000 marches au plus. Classer les 348 748 qui contiennent « travaux »
prenait 9,7 secondes a chaud, et 7,2 secondes a froid au plafond precedent de 20 000, ce qui
depassait le delai que l'API s'impose. Quand `classement_approche` vaut `true`, les marches
affiches sont les mieux classes **parmi les 5 000 plus recents qui contiennent les mots**, et non
parmi tous.

Le raisonnement complet, avec le tableau de ce que l'approximation change vraiment, est dans
`services/api/requetes.py` et dans l'ADR 0011.
