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

## Justesse mesuree, et ce qu'elle change

Un taux de rapprochement ne dit rien de sa justesse. Soixante paires ont donc ete relues une par
une, douze par tranche de similarite, avec un verdict ecrit dans
`mesures/verification/2026-09-27-verdicts-rapprochement.csv`.

| Tranche de similarite | Paires relues | Justes | Fausses | Doutes | Justesse |
|---|---|---|---|---|---|
| 0,4 a 0,5 | 12 | 0 | 12 | 0 | 0 % |
| 0,5 a 0,6 | 12 | 6 | 4 | 2 | 60 % |
| 0,6 a 0,7 | 12 | 8 | 3 | 1 | 72,7 % |
| 0,7 a 0,8 | 12 | 10 | 1 | 1 | 90,9 % |
| 0,8 et plus | 12 | 12 | 0 | 0 | 100 % |

**Les 19 paires ou le SIRET du titulaire concorde sont toutes justes.** Le niveau 4 merite donc bien
son nom de confiance haute, et cette fois la mesure le prouve au lieu de le supposer.

En croisant ces verdicts avec le balayage des seuils, et en ponderant chaque tranche par son
effectif reel (l'echantillon relu est stratifie, une moyenne simple serait fausse) :

| Seuil | Rapproches | Couverture | Justesse estimee | Rapprochements justes |
|---|---|---|---|---|
| 0,4 | 83 | 27,7 % | 66,0 % | **54,8** |
| 0,5 | 64 | 21,3 % | 85,6 % | **54,8** |
| 0,6 | 48 | 16,0 % | 94,1 % | 45,2 |
| 0,7 | 41 | 13,7 % | 97,8 % | 40,1 |
| 0,8 | 31 | 10,3 % | 100 % | 31,0 |

**Resultat decisif** : les seuils 0,4 et 0,5 produisent le meme nombre de rapprochements justes.
Descendre sous 0,5 n'apporte donc aucune information utile, seulement 19 erreurs supplementaires.
Ce constat etait impossible a deviner, et il justifie a lui seul le temps passe a relire les paires.

**Effet de la fenetre de dates** : de 6 a 36 mois, le nombre d'avis avec candidats passe de 137 a
147, soit quelques points. La fenetre laisse en mediane une centaine de marches candidats : elle ne
trie presque rien. C'est le seuil de similarite qui discrimine, et c'est donc lui qu'il faut regler.

**Reglage retenu** : fenetre de 18 mois, seuil de 0,6, ce qui donne 94,1 % de justesse pour 16 % de
couverture. Le seuil de 0,5 reste disponible si la couverture devient prioritaire, au prix de
8 points de justesse. Le plancher de 0,5 est une limite dure : en dessous, on n'ajoute que du faux.

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

## Ce qui a ete mesure depuis, et ce qui reste

| Point | Statut |
|---|---|
| Effet de la fenetre de dates, de 6 a 36 mois | **mesure** : gain de quelques points seulement |
| Effet du seuil de similarite, de 0,4 a 0,9 | **mesure** : c'est le vrai levier |
| Taux de faux rapprochements | **mesure** sur 60 paires relues a la main |
| Gain apporte par RapidFuzz puis par des plongements lexicaux | a mesurer en phase 3 |
| Second relecteur sur les memes 60 paires | souhaitable, non fait |

**Limite a enoncer dans le memoire** : les soixante verdicts ont ete poses par une seule personne,
sur lecture des libelles. Deux libelles proches peuvent designer deux lots d'un meme marche, ce qui
est un rapprochement acceptable, ou deux marches distincts, ce qui ne l'est pas. Un second
relecteur changerait probablement quelques verdicts, sans modifier la tendance.
