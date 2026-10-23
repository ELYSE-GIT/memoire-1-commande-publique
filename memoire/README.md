# memoire

Sources du memoire ecrit, et figures generees.

Les sources sont en Markdown, et elles restent l'unique verite : une correction se fait ici, jamais
dans le PDF. Le rendu final passe par **Quarto**, qui lit ces fichiers tels quels. La comparaison
qui a conduit a ce choix est dans l'en-tete de la cible `memoire` du Makefile.

```bash
make memoire          # verifie les chiffres cites, puis rend sortie/memoire.pdf
make memoire-pages    # compte les pages du PDF rendu
```

## Le corps du memoire

| Fichier | Contenu | Etat |
|---|---|---|
| `memoire.qmd` | le document assemble : page de titre, sommaire, puis les fichiers dans l'ordre | a jour |
| `00-plan.md` | plan, cible de pagination, principes de redaction. **Ne fait pas partie du rendu** | a jour |
| `00-introduction.md` | le sujet, la these, la methode, le plan | brouillon redige |
| `01-etat-des-lieux.md` | chapitre 1 : le probleme, en chiffres mesures | brouillon redige |
| `02-etat-de-l-art.md` | chapitre 2 : ce qui existe deja, outils publics, libres et commerciaux | brouillon redige |
| `03-architecture.md` | chapitre 3 : l'architecture retenue, service par service | brouillon redige |
| `04-ingenierie-des-donnees.md` | chapitre 4 : collecter, nettoyer, relier les sources | brouillon redige |
| `05-detection.md` | chapitre 5 : detecter les marches atypiques, et refuser un modele par la mesure | brouillon redige |
| `06-recherche-et-assistant.md` | chapitre 6 : du mot-cle a la reponse sourcee | brouillon redige |
| `07-mise-en-production.md` | chapitre 7 : l'API, le site, la securite et le deploiement | brouillon redige |
| `08-mesures-et-incertitude.md` | chapitre 8 : ce que vaut un pourcentage, la validation hors echantillon, les couts compares | brouillon redige |
| `09-difficultes.md` | chapitre 9 : les soixante-quatre difficultes, classees, et leurs lecons | brouillon redige |
| `10-conclusion.md` | ce qui est demontre, ce qui ne l'est pas, ce qui reste a faire | brouillon redige |

## Les annexes

Elles sont hors du compte de pages du corps. Aucune ne porte un resultat du projet : la premiere
definit, les deux autres situent. Les placer en annexe les garde entierement lisibles tout en
ramenant le corps a ce qui demontre quelque chose.

| Fichier | Contenu | Etat |
|---|---|---|
| `annexe-a-glossaire.md` | tous les termes du domaine et de la technique, definis avant usage | brouillon redige |
| `annexe-b-histoire-des-pratiques.md` | d'ou viennent ces outils, et les echecs qui ont change les pratiques | brouillon redige |
| `annexe-c-etudes-de-cas.md` | qui utilise ces outils, avec le niveau de fiabilite de chaque source | brouillon redige |
| `figures/` | les figures, produites par `make figures` depuis `mesures/resultats/` | 26 figures, 16 citees |

## Regles tenues dans ces textes

1. Aucun terme n'est employe avant d'avoir ete defini. L'annexe A sert de glossaire.
2. Aucun chiffre n'est affirme sans source externe citee ou sans mesure reproductible, avec la
   commande qui la produit. Un test echoue en nommant tout chiffre devenu faux.
3. Aucune figure n'est dessinee a la main : toutes viennent de `mesures/`. Un test verifie que
   chaque figure citee existe, pour que le document ne sorte pas troue.
4. Chaque pourcentage precise son unite de comptage. Le jeu principal se compte de trois facons :
   3 283 035 lignes brutes, 2 114 675 lignes a l'etat actuel, 1 833 468 marches distincts.
5. Les brouillons portent une note en tete : les faits sont verifies, la formulation reste a
   reprendre par l'auteur, dans sa voix.
6. Tout pourcentage tire d'un echantillon est publie avec son intervalle a 95 %, calcule par la
   methode de Wilson. Un pourcentage calcule sur la population entiere n'en recoit pas, mais la
   source d'incertitude qui le concerne est nommee. Voir l'ADR 0010.
7. Les etiquettes de notes de bas de page sont uniques d'un fichier a l'autre : le rendu assemble
   tous les chapitres en un seul document, et deux notes de meme nom s'y confondraient.
