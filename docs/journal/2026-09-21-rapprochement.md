# 2026-09-21. Relier les sources : mesure et decision

## Objectif

Trancher la question laissee ouverte par l'exploration du BOAMP : les deux sources n'ayant aucun
identifiant commun, peut-on quand meme les relier, et a quel taux ? Une decision d'architecture ne
se prend pas a l'intuition, donc on mesure d'abord.

## Ce qui a ete fait

- `mesures/rapprochement_boamp_decp.py` : quatre niveaux de rapprochement, chacun mesure separement,
  resultats dates en CSV. Lancement par `make bench-rapprochement`.
- Figure 16, l'entonnoir du rapprochement, tracee depuis ce CSV.
- 13 tests, sans reseau ni fichier de 236 Mo.
- ADR 0003 : la decision, ses alternatives et ses limites.

## Le resultat

Sur 300 avis de resultat parus au premier semestre 2025 :

| Niveau | Critere | Avis | Part |
|---|---|---|---|
| 0 | portant au moins un SIRET | 184 | 61,3 % |
| 1 | SIRET d'acheteur reconnu dans les DECP | 159 | 53,0 % |
| 2 | plus une fenetre de 18 mois | 142 | 47,3 % |
| 3 | plus un objet de marche proche | 93 | 31,0 % |
| 4 | plus le SIRET du titulaire retrouve | 44 | 14,7 % |

La mediane est de 107 marches candidats par avis apres la fenetre de dates. La fenetre trie donc
tres peu : ce sont l'objet et le titulaire qui discriminent reellement.

## Une erreur de depart, et ce qu'elle a couté

**Symptome** : la premiere mesure donnait 56 avis sur 300 portant un SIRET, soit 19 %. Un chiffre
qui rendait le rapprochement presque inutile.

**Cause** : l'extraction ne lisait qu'un seul format. Les avis du BOAMP existent en trois schemas :
eForms, le standard europeen, pour 233 avis sur 300 ; FNSimple, l'ancien format francais, pour 60 ;
et MAPA pour 7. Mon code cherchait le SIRET a l'emplacement prevu par FNSimple uniquement.

**Solution** : ne pas ecrire trois analyseurs, mais chercher le motif de quatorze chiffres partout
dans le document. Le taux passe de 19 % a 61 %.

**Lecon pour le memoire** : avant de conclure qu'une donnee manque, verifier qu'on la cherche au bon
endroit. Et quand plusieurs formats coexistent, une regle simple appliquee a tout le document bat
souvent trois analyseurs precis. L'imprecision est rattrapee par la verification en aval : un nombre
de quatorze chiffres qui n'est pas un SIRET ne correspondra a aucun acheteur.

## Deux refus de l'analyse de securite, tous deux justifies

**Premier** : la liste de points d'interrogation d'une clause `in`, fabriquee par concatenation.
Remplacee par un parametre unique converti en tableau par DuckDB. La forme dangereuse disparait,
meme si le contenu, lui, etait sur.

**Second** : un intervalle SQL ne peut pas etre parametre. Les bornes de la fenetre sont desormais
calculees en Python, ce qui a un avantage inattendu : la fenetre devient un parametre du script,
donc mesurable. On pourra publier le taux obtenu pour 6, 12, 18 et 24 mois.

**Lecon** : une contrainte de securite ou d'outil oblige souvent a une meilleure conception.

## Ce que la decision retient

Un rapprochement par niveaux, produisant un **degre de confiance** et non un booleen : haute quand
le titulaire concorde, moyenne quand l'objet concorde et qu'un seul candidat subsiste, faible
sinon. Un lien de confiance moyenne sera affiche avec la mention du doute, jamais masque.

Le plafond du dispositif est connu et il ne depend pas de nous : **39 % des avis ne portent aucun
SIRET exploitable**.

## Prochaine etape

Faire varier la fenetre de dates et le seuil de similarite, puis verifier manuellement cinquante
liens pour estimer le taux de faux rapprochements. Ensuite, fin de la phase 2.

---

## Suite, le 2026-09-27 : regler les parametres et mesurer la justesse

### Le balayage

Les deux parametres du rapprochement, la fenetre de dates et le seuil de similarite, etaient
choisis sans preuve. Le balayage les fait varier et mesure le taux obtenu pour chaque combinaison.

**Resultat** : la fenetre ne change presque rien, de 137 a 147 avis avec candidats entre 6 et
36 mois. Le seuil change tout, de 42,3 % a 20 % de rapprochements entre 0,4 et 0,9. La fenetre
laisse en mediane une centaine de candidats par avis : elle ne trie pas, elle delimite.

### La justesse, qui ne se calcule pas

Un taux de rapprochement ne dit rien de sa justesse, et aucune verite de reference n'existe. Il a
fallu relire soixante paires, une par une, et poser un verdict. Les verdicts sont versionnes dans
`mesures/verification/`, pour etre recontrolables.

| Tranche | Justes | Fausses | Doutes | Justesse |
|---|---|---|---|---|
| 0,4 a 0,5 | 0 | 12 | 0 | 0 % |
| 0,5 a 0,6 | 6 | 4 | 2 | 60 % |
| 0,6 a 0,7 | 8 | 3 | 1 | 72,7 % |
| 0,7 a 0,8 | 10 | 1 | 1 | 90,9 % |
| 0,8 et plus | 12 | 0 | 0 | 100 % |

**Les 19 paires ou le SIRET du titulaire concorde sont toutes justes.** La conception en niveaux de
confiance est donc validee par la mesure, et non plus seulement par le raisonnement.

### Le piege de calcul, evite de justesse

L'echantillon relu est stratifie : douze paires par tranche, alors que les tranches n'ont pas du
tout le meme poids reel. Faire la moyenne des verdicts aurait donne un chiffre faux, et personne ne
s'en serait apercu : le resultat aurait ete un nombre plausible. La justesse est donc ponderee par
l'effectif reel de chaque tranche.

Un test verifie ce redressement sur un cas construit ou la moyenne naive donnerait 33 % et la
moyenne ponderee 6,7 %.

### Le resultat qui decide

| Seuil | Couverture | Justesse | Rapprochements justes |
|---|---|---|---|
| 0,4 | 27,7 % | 66,0 % | **54,8** |
| 0,5 | 21,3 % | 85,6 % | **54,8** |
| 0,6 | 16,0 % | 94,1 % | 45,2 |

**Les seuils 0,4 et 0,5 donnent le meme nombre de rapprochements justes.** Descendre sous 0,5
n'ajoute que des erreurs. C'etait impossible a deviner, et cela justifie a soi seul le temps passe
a relire les paires.

**Lecon pour le memoire** : mesurer une couverture sans mesurer sa justesse conduit a optimiser le
mauvais chiffre. La question n'est jamais « combien de liens trouve-t-on » mais « combien de liens
justes trouve-t-on ».
