# services/site/statique

Les fichiers servis tels quels, a la racine `/statique`. Ils sont telecharges une seule fois par
visiteur, puis gardes par son navigateur.

| Fichier | Poids | Origine |
|---|---|---|
| `site.css` | 15,4 ko | ecrit pour ce projet |
| `htmx-2.0.11.min.js` | 51,0 ko | **tiers**, recopie tel quel |
| `marque.svg` | 0,6 ko | ecrit pour ce projet |

## Le seul fichier tiers du depot

htmx est la seule bibliotheque exterieure que ce projet embarque. Elle est recopiee ici plutot
que chargee depuis un reseau de diffusion de contenu, pour deux raisons :

- **La demonstration ne doit dependre d'aucun reseau.** Un fichier charge depuis un domaine
  tiers est un ecran blanc possible le jour de la soutenance.
- **Personne d'autre ne doit pouvoir remplacer le JavaScript de la page.** Un CDN compromis, ou
  simplement un paquet republie sous le meme numero de version, executerait son code chez chaque
  visiteur. La politique de securite du site n'autorise donc aucun domaine exterieur.

En echange, c'est a nous de dire d'ou vient ce fichier et comment le verifier.

| | |
|---|---|
| Version | htmx 2.0.11 |
| Telecharge depuis | <https://unpkg.com/htmx.org@2.0.11/dist/htmx.min.js> |
| Le 22 octobre 2026 | |
| Taille | 52 182 octets |
| Empreinte SHA-256 | `d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717` |
| Licence | BSD 2-Clause (Big Sky Software) |

Verifier qu'il n'a pas ete modifie :

```bash
shasum -a 256 services/site/statique/htmx-2.0.11.min.js
```

Un test du projet fait la meme verification a chaque execution de `make test`, et les hooks de
pre-commit qui reformatent les fichiers excluent explicitement celui-ci : **un fichier tiers se
verifie, il ne se reformate pas.** Ajouter une fin de ligne manquante suffirait a rendre son
empreinte differente de celle publiee, donc invalide la seule chose qui permet de dire qu'il
n'a pas ete touche.

## Mettre a jour htmx

1. Telecharger la nouvelle version sous son nouveau nom : le numero est dans le nom du fichier,
   donc deux versions ne peuvent pas se confondre et le cache d'un navigateur ne sert jamais
   l'ancienne.
2. Mettre a jour ce tableau : version, adresse, date, taille, empreinte.
3. Changer le nom cite dans `services/site/gabarits/base.html`.
4. Supprimer l'ancien fichier. Un test verifie qu'il n'y a qu'une seule version versionnee.
5. Relancer `make test` puis `make bench-site`, et ouvrir une page dans un navigateur en
   regardant la console : c'est la seule facon de voir une violation de la politique de
   securite, et c'est ainsi qu'a ete trouvee celle de la feuille de style que htmx insere
   lui-meme.
