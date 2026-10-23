# Plan du mémoire

Document de travail. Il ne fait pas partie du document rendu.

**Format de rendu** : Quarto, qui lit directement les sources Markdown de ce dossier et produit le
PDF. Les sources restent l'unique vérité : une correction se fait dans le `.md`, jamais dans le PDF.

**Cible** : 40 à 60 pages pour le corps, annexes non comptées.

---

## Le corps

| # | Chapitre | Fichier | Mots | État |
|---|---|---|---|---|
| | Introduction | `00-introduction.md` | | **à écrire** |
| 1 | État des lieux : le problème | `01-etat-des-lieux.md` | 2 190 | rédigé |
| 2 | État de l'art : les solutions existantes | `02-etat-de-l-art.md` | 2 501 | rédigé |
| 3 | L'architecture retenue | `03-architecture.md` | 3 068 | rédigé |
| 4 | Ingénierie des données | `04-ingenierie-des-donnees.md` | 3 608 | rédigé |
| 5 | Détection des marchés atypiques | `05-detection.md` | 3 915 | rédigé |
| 6 | Recherche et assistant | `06-recherche-et-assistant.md` | 4 489 | rédigé |
| 7 | Mise en production et sécurité | `07-mise-en-production.md` | 5 509 | rédigé |
| 8 | Mesures, coûts et comparaison au marché | `08-mesures-et-incertitude.md` | 3 907 | rédigé |
| 9 | Difficultés rencontrées et solutions | `09-difficultes.md` | 2 343 | rédigé |
| | Conclusion et limites | `10-conclusion.md` | | **à écrire** |

## Les annexes, hors du compte de pages

| | Annexe | Fichier | Mots | État |
|---|---|---|---|---|
| A | Glossaire : le vocabulaire du sujet | `annexe-a-glossaire.md` | 3 824 | rédigé |
| B | Histoire des pratiques | `annexe-b-histoire-des-pratiques.md` | 3 153 | rédigé |
| C | Étude du marché et études de cas | `annexe-c-etudes-de-cas.md` | 3 287 | rédigé |
| D | Décisions d'architecture, protocole de mesure, sources | depuis `docs/adr/` | | à assembler |

**Pourquoi ces trois chapitres sont en annexe plutôt que supprimés.** Le glossaire, l'histoire des
pratiques et les études de cas sont demandés par le cahier des charges et ils ont été écrits. Mais
aucun des trois ne porte un résultat du projet : le premier définit, les deux autres situent. Les
placer en annexe les garde intégralement lisibles tout en ramenant le corps à ce qui démontre
quelque chose. Le lecteur pressé lit le corps, le jury qui veut vérifier lit les annexes.

**Le nombre de pages réel se mesure au premier rendu**, pas en comptant les mots : les tableaux et
les seize figures occupent plus de place que leur nombre de mots ne le suggère. Si le corps dépasse
la cible, le prochain levier est le chapitre 7, le plus long, dont la partie « mesures de l'API et
du site » peut rejoindre l'annexe D sans rien perdre.

---

## Principes de rédaction

1. **Aucun terme n'est utilisé avant d'être défini.** L'annexe A sert de glossaire ; chaque terme
   technique est défini au moment où il apparaît, et repris dans l'annexe.
2. **Aucun chiffre n'est affirmé sans source ou sans mesure.** Une source externe est citée avec son
   auteur, son titre, sa date et son adresse. Une mesure propre indique la commande qui la produit
   et la date d'exécution.
3. **Aucune figure n'est dessinée à la main.** Toutes viennent de `mesures/`, par `make figures`.
   Un test vérifie que chaque figure citée existe.
4. **Chaque choix technique présente ses alternatives**, avec ce qui a fait pencher et l'échelle à
   laquelle la réponse changerait.
5. **Les échecs sont racontés**, y compris ceux du projet. Un mémoire sans difficulté est un mémoire
   sans travail : c'est l'objet du chapitre 9.
6. **Chaque pourcentage précise son unité de comptage.** Trois coexistent et se confondent
   facilement : 3,30 millions de lignes brutes, 2,12 millions de lignes à l'état actuel,
   1,83 million de marchés distincts.

## Fabriquer le PDF

```bash
make memoire        # rend le PDF dans memoire/sortie/
```

Les chiffres cités sont vérifiés par la suite de tests avant le rendu : `uv run pytest
tests/test_chiffres_memoire.py tests/test_couts.py`. Un chiffre du texte qui ne correspond plus à
une mesure fait échouer un test en le nommant.
