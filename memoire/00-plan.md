# Plan du mémoire

Document de travail. Le format de rendu final (Typst, Quarto ou Word) reste à décider ; les sources
sont écrites en Markdown, qui se convertit vers les trois.

Cible : 40 à 60 pages, hors annexes.

| # | Chapitre | Contenu | Pages | État |
|---|---|---|---|---|
| 0 | Introduction | le sujet, la thèse, la méthode, le plan | 2 | à écrire |
| 1 | Le vocabulaire du sujet | tous les termes du domaine et de la technique, définis avant usage | 4 | **rédigé** |
| 2 | État des lieux : le problème | la commande publique, ses données, leurs défauts mesurés | 8 | **rédigé** |
| 3 | État de l'art : les solutions existantes | outils publics, projets associatifs, plateformes commerciales | 5 | à écrire |
| 4 | Étude du marché et études de cas | qui utilise quoi, avec sources vérifiables | 4 | matière réunie |
| 5 | Histoire des pratiques | d'où viennent ces outils, et pourquoi ils ont remplacé les précédents | 4 | matière réunie |
| 6 | Architecture retenue | le trajet de la donnée, service par service, avec les alternatives écartées | 6 | à écrire |
| 7 | Ingénierie des données | collecte, stockage, transformation, qualité | 6 | phase 3 et 4 |
| 8 | Détection des marchés atypiques | de la règle au modèle, et ce que la mesure justifie | 6 | phase 5 |
| 9 | Recherche et assistant | du mot-clé à la réponse sourcée, l'escalier de complexité | 5 | phase 6 |
| 10 | Mise en production et sécurité | VPS, conteneurs, supervision, sauvegardes | 4 | phase 9 |
| 11 | Mesures, coûts et comparaison au marché | performance, qualité, euros par mois, face aux offres payantes | 5 | phase 8 |
| 12 | Difficultés rencontrées et solutions | le journal de bord, transformé en enseignements | 4 | alimenté en continu |
| 13 | Conclusion et limites | ce qui est démontré, ce qui ne l'est pas, ce qui reste à faire | 2 | à écrire |

Annexes : glossaire complet, décisions d'architecture (ADR), protocole de mesure, sources.

## Principes de rédaction

1. **Aucun terme n'est utilisé avant d'être défini.** Le chapitre 1 sert de prérequis ; chaque terme
   technique introduit plus loin est défini au moment où il apparaît, et repris dans le glossaire.
2. **Aucun chiffre n'est affirmé sans source ou sans mesure.** Une source externe est citée avec son
   auteur, son titre, sa date et son adresse. Une mesure propre indique la commande qui la produit
   et la date d'exécution.
3. **Aucune figure n'est dessinée à la main.** Toutes viennent de `mesures/`, par `make figures`.
4. **Chaque choix technique présente ses alternatives**, avec ce qui a fait pencher et l'échelle à
   laquelle la réponse changerait.
5. **Les échecs sont racontés**, y compris ceux du projet. Un mémoire sans difficulté est un mémoire
   sans travail.
