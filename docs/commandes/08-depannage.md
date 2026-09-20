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
