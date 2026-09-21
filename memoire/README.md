# memoire

Sources du memoire ecrit et figures generees.

Les sources sont en Markdown : c'est le format qui se convertit le plus facilement vers Typst,
Quarto ou Word, et la decision sur le rendu final n'est pas encore prise. Aucun contenu n'est
enferme dans un format proprietaire tant que ce choix n'est pas arrete.

| Fichier | Contenu | Etat |
|---|---|---|
| `00-plan.md` | plan des 13 chapitres, pagination cible, principes de redaction | a jour |
| `01-vocabulaire.md` | chapitre 1 : tous les termes du domaine et de la technique | brouillon redige |
| `02-etat-des-lieux.md` | chapitre 2 : le probleme, en chiffres mesures | brouillon redige |
| `figures/` | les figures, produites par `make figures` depuis `mesures/resultats/` | 15 figures |

## Regles tenues dans ces textes

1. Aucun terme n'est employe avant d'avoir ete defini.
2. Aucun chiffre n'est affirme sans source externe citee ou sans mesure reproductible, avec la
   commande qui la produit.
3. Aucune figure n'est dessinee a la main : toutes viennent de `mesures/`.
4. Chaque pourcentage precise son unite de comptage. Le jeu principal se compte de trois facons :
   3 283 035 lignes brutes, 2 114 675 lignes a l'etat actuel, 1 833 468 marches distincts.
5. Les brouillons portent une note en tete : les faits sont verifies, la formulation reste a
   reprendre par l'auteur, dans sa voix.
