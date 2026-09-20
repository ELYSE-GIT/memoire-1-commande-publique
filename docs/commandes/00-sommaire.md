# Sommaire des commandes

Carte de toutes les commandes du projet, classees par besoin. Chaque fiche precise, pour chaque
commande : ce qu'elle fait, ou la lancer (Mac ou VPS), le resultat attendu et la duree approximative.

La source est en Markdown. La version `.txt` du dossier `txt/` est generee par `make docs-txt`.
Ne jamais modifier un fichier `.txt` a la main : il serait ecrase.

| Fiche | Quand l'ouvrir | Etat |
|---|---|---|
| [01-installation-mac.md](01-installation-mac.md) | premiere installation, ou reinstallation complete | fait |
| [02-quotidien.md](02-quotidien.md) | chaque session de travail | fait |
| [03-donnees.md](03-donnees.md) | collecte, transformation, qualite des donnees | phase 3 |
| [04-modeles.md](04-modeles.md) | entrainement, evaluation, registre des modeles | phase 4 |
| [05-ia.md](05-ia.md) | indexation, recherche, assistant | phase 5 |
| [06-mesures.md](06-mesures.md) | toutes les commandes `make bench-*` | phase 7 |
| [07-vps.md](07-vps.md) | acces SSH, deploiement, sauvegarde, mise a jour | phase 8 |
| [08-depannage.md](08-depannage.md) | quand quelque chose casse | au fil de l'eau |
| [09-demo-soutenance.md](09-demo-soutenance.md) | repetitions et jour de la soutenance | phase 12 |

## Les trois commandes a retenir

```bash
make help     # la liste complete, avec une ligne d'explication par commande
make verif    # style, types, tests, secrets : exactement ce que verifie la CI
make vm-down  # en fin de session, plus rien ne tourne sur le Mac
```
