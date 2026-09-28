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
