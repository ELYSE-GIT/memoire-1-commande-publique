# ADR 0003. Relier le BOAMP, les DECP et le repertoire des entreprises

- Date : 2026-09-21
- Statut : accepte
- Phase : 2, fin de l'exploration des sources

## Contexte

Le projet exploite trois sources publiques :

| Source | Ce qu'elle decrit | Volume |
|---|---|---|
| DECP consolidees | les marches attribues | 1 833 468 marches |
| BOAMP | les avis avant et apres la passation | 1 707 999 avis |
| API Recherche d'entreprises | les organisations, par leur SIRET | 242 745 a resoudre |

Relier les deux premieres donnerait la chaine complete : l'appel d'offres, les conditions de mise
en concurrence, puis le montant reellement attribue. C'est ce qui manque aujourd'hui a quiconque
veut analyser la commande publique.

**Le probleme mesure** : les deux sources ne partagent aucun identifiant. Sur 600 avis recents
portant un `contractfolderid`, **aucun** ne correspond a un identifiant des DECP. Le BOAMP porte un
identifiant technique produit par la plateforme de dematerialisation de l'acheteur, sous forme
d'UUID ; les DECP portent un numero de dossier choisi par l'acheteur, combine a son SIRET.

## Decision

**Ne pas tenter une jointure. Construire un rapprochement par niveaux, mesure, et publier son
taux de reussite avec le resultat.**

Le rapprochement suit le principe de l'escalier deja applique au reste du projet. Chaque niveau
ajoute un critere, et chaque niveau est mesure separement pour savoir ce qu'il apporte.

| Niveau | Critere ajoute | Avis rapproches | Part |
|---|---|---|---|
| 0 | avis portant au moins un SIRET | 184 sur 300 | 61,3 % |
| 1 | ce SIRET est un acheteur connu des DECP | 159 | 53,0 % |
| 2 | plus au moins un marche dans une fenetre de 18 mois | 142 | 47,3 % |
| 3 | plus un objet de marche suffisamment proche | 93 | 31,0 % |
| 4 | plus le SIRET du titulaire retrouve dans le meme avis | 44 | 14,7 % |

Mesure du 21 septembre 2026, sur 300 avis de resultat parus au premier semestre 2025. Reproductible
par `make bench-rapprochement`, resultats dans `mesures/resultats/`.

**Les niveaux 3 et 4 ne sont pas concurrents mais complementaires** : le niveau 4 donne une quasi
certitude quand il aboutit, le niveau 3 couvre davantage de cas avec une confiance moindre. Le
rapprochement produira donc un **degre de confiance** et non un booleen :

| Confiance | Regle | Usage prevu |
|---|---|---|
| Haute | acheteur, fenetre de dates et SIRET du titulaire concordent | affichage du lien a l'utilisateur |
| Moyenne | acheteur, fenetre de dates, objet proche, un seul candidat | affichage avec mention explicite du doute |
| Faible | acheteur et fenetre de dates seulement, plusieurs candidats | usage interne, jamais affiche |

## Alternatives examinees

| Option | Pour | Contre | Verdict |
|---|---|---|---|
| **Rapprochement par niveaux, avec degre de confiance** | explicable, mesurable, degradable proprement | ne relie qu'une partie des avis | **retenu** |
| Jointure sur un identifiant commun | gratuite, exacte | mesure : zero correspondance sur 600 avis | impossible |
| Splink, rapprochement probabiliste sur DuckDB | etat de l'art, gere l'incertitude, tourne sur notre moteur | demande un jeu d'entrainement etiquete que nous n'avons pas | a reconsiderer en phase 5, si le taux du niveau 3 plafonne |
| Comparaison des objets par plongements lexicaux | comprend les reformulations, « entretien » et « maintenance » | cout de calcul, modele a charger, resultat moins explicable devant un jury | seulement si la mesure montre que la similarite textuelle plafonne |
| Demander l'identifiant aux acheteurs | reglerait le probleme a la racine | hors de portee d'un memoire | non |
| Renoncer a relier les sources | simple | prive le projet de son apport principal | non |

## Choix techniques associes

**Extraction des SIRET par expression reguliere, sur tout le document.** Les avis du BOAMP
existent en trois formats : eForms (233 sur 300 dans l'echantillon), FNSimple (60) et MAPA (7).
Ecrire trois analyseurs serait plus precis mais trois fois plus couteux a maintenir. Chercher le
motif de quatorze chiffres partout dans le document fonctionne sur les trois, et l'imprecision est
rattrapee par la verification : un nombre qui n'est pas un SIRET ne correspondra a aucun acheteur.

**Comparaison des objets par `difflib`, de la bibliotheque standard.** RapidFuzz serait dix a cent
fois plus rapide, mais la mesure porte sur 300 avis et prend douze secondes. La dependance sera
prise en phase 3, quand le traitement portera sur des centaines de milliers d'avis.

**Seuil de similarite a 0,6.** En dessous, les rapprochements deviennent douteux ; au-dessus de 0,8,
les reformulations legitimes sont perdues. Ce seuil est un parametre du script, pas une valeur
enfouie dans le code, precisement pour pouvoir le faire varier et mesurer son effet.

## Consequences

**Positives**

- Le lien entre un appel d'offres et son montant attribue devient possible pour une part mesurable
  des avis, avec un degre de confiance affiche.
- La methode est explicable en une phrase : meme acheteur, dates compatibles, objet proche, et si
  possible meme titulaire.
- Chaque niveau etant mesure separement, l'effet d'une amelioration future se lit immediatement.

**Negatives et limites, a enoncer dans le memoire**

- **Seuls 61 % des avis portent un SIRET exploitable.** C'est le plafond du dispositif, et il ne
  depend pas de nous.
- La mediane est de 107 marches candidats par avis apres la fenetre de dates : cette fenetre trie
  peu, c'est l'objet et le titulaire qui discriminent.
- Un rapprochement de confiance moyenne peut etre faux. Le site devra le dire, jamais le masquer.
- La mesure porte sur des avis de resultat du premier semestre 2025. Les avis recents sont moins
  susceptibles d'etre deja dans les DECP, en raison du delai de publication.

## A mesurer ensuite

1. L'effet de la fenetre de dates : 6, 12, 18, 24 mois, et le taux obtenu pour chacune.
2. L'effet du seuil de similarite, de 0,4 a 0,9.
3. Le taux de faux rapprochements, par verification manuelle d'un echantillon de cinquante liens.
4. Le gain apporte par RapidFuzz, puis eventuellement par des plongements lexicaux, en qualite et
   en temps de calcul.
