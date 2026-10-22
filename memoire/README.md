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
| `03-etat-de-l-art.md` | chapitre 3 : ce qui existe deja, outils publics, libres et commerciaux | brouillon redige |
| `04-marche-et-etudes-de-cas.md` | chapitre 4 : qui utilise ces outils, et ce que l'alternative payante coute | brouillon redige |
| `05-histoire-des-pratiques.md` | chapitre 5 : d'ou viennent ces outils, et les echecs qui ont change les pratiques | brouillon redige |
| `06-architecture.md` | chapitre 6 : l'architecture retenue, service par service | brouillon redige |
| `07-ingenierie-des-donnees.md` | chapitre 7 : collecter, nettoyer, relier les sources | brouillon redige |
| `08-detection.md` | chapitre 8 : detecter les marches atypiques, et refuser un modele par la mesure | brouillon redige |
| `09-recherche-et-assistant.md` | chapitre 9 : du mot-cle a la reponse sourcee | brouillon redige |
| `11-mesures-et-incertitude.md` | chapitre 11 : ce que vaut un pourcentage, la validation hors echantillon, les couts compares | brouillon redige |
| `figures/` | les figures, produites par `make figures` depuis `mesures/resultats/` | 26 figures |

## Regles tenues dans ces textes

1. Aucun terme n'est employe avant d'avoir ete defini.
2. Aucun chiffre n'est affirme sans source externe citee ou sans mesure reproductible, avec la
   commande qui la produit.
3. Aucune figure n'est dessinee a la main : toutes viennent de `mesures/`.
4. Chaque pourcentage precise son unite de comptage. Le jeu principal se compte de trois facons :
   3 283 035 lignes brutes, 2 114 675 lignes a l'etat actuel, 1 833 468 marches distincts.
5. Les brouillons portent une note en tete : les faits sont verifies, la formulation reste a
   reprendre par l'auteur, dans sa voix.
6. Tout pourcentage tire d'un echantillon est publie avec son intervalle a 95 %, calcule par la
   methode de Wilson. Un pourcentage calcule sur la population entiere n'en recoit pas, mais la
   source d'incertitude qui le concerne est nommee. Voir l'ADR 0010.
