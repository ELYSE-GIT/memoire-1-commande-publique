# 2026-09-28. Variables et detection

## Objectif

Fabriquer les variables qui servent a reperer un marche atypique, puis poser les premieres regles
de detection. Avec une exigence : **aucun seuil choisi a l'intuition**.

## Ce qui a ete fait

- 16 termes ajoutes au chapitre de vocabulaire : variable, quantile, robuste, ecart normalise,
  groupe de comparaison, precision, rappel, etiquette faible, fuite de donnees.
- `or_variables.sql` : trois groupes de comparaison, quinze variables.
- `or_signaux.sql` : cinq signaux, seuils issus d'une evaluation.
- `mesures/detection.py` et `make bench-detection` : l'evaluation, reproductible.
- ADR 0006 et vue d'ensemble de l'architecture.

## L'erreur la plus instructive du projet jusqu'ici

**Symptome** : une mesure d'essai donnait 75,8 % de precision. Le script ecrit ensuite, cense
faire la meme chose, en donnait 23,8 %. Trois fois moins, sur la meme donnee et le meme seuil.

**Cause** : la mesure d'essai testait `ecart > 4`, le script testait `abs(ecart) > 4`. Une valeur
absolue, ajoutee sans y penser, parce qu'elle semblait plus complete.

**Ce que la mesure a revele** : les montants **trop bas** ne concordent **jamais** avec les
anomalies signalees par le producteur. Zero concordance sur 18 208 marches. En melangeant les deux
directions, on noyait un signal valide dans un signal non evaluable.

**Solution** : deux signaux distincts. Le prix trop eleve, valide a 75,8 %. Le prix trop bas,
expose separement et marque « non evalue ».

**Lecon pour le memoire, et elle est generale** : une evaluation ne dit rien sur ce que son
etiquette ignore. Le reflexe aurait ete de conclure que la detection des montants bas est mauvaise.
La conclusion juste est qu'**elle n'est pas evaluable avec cette etiquette**. Confondre « non
valide » et « invalide » aurait supprime un signal peut-etre utile : un marche de travaux a un euro
est tout aussi anormal qu'un marche a cent millions.

Cette erreur est aussi un rappel de la precedente : une mesure d'essai jetee dans un terminal et
une mesure ecrite dans un script doivent donner le meme chiffre. Quand elles different, c'est une
information, pas un detail a corriger en silence.

## Ce que la detection trouve

| Signal | Marches | Part |
|---|---|---|
| Prix tres eleve | 2 661 | 0,13 % |
| Prix eleve a verifier | 17 418 | 0,87 % |
| Prix tres bas, non evalue | 18 954 | 0,95 % |
| Offre unique sur un marche au-dessus des seuils | 53 328 | 2,67 % |
| Titulaire dominant chez son acheteur | 1 656 | 0,08 % |
| **Au moins un signal fort** | **57 409** | **2,87 %** |
| Deux signaux independants | 236 | 0,01 % |

Le prix tres eleve ne designe que 2 661 marches, quand l'evaluation en signalait 8 331. L'ecart
s'explique : la detection s'applique **apres** nettoyage, donc apres retrait des montants deja
signales par le producteur. Elle en trouve moins, mais ce qu'elle trouve est nouveau.

## Deux precautions ecrites dans le code

**La taille du groupe de comparaison.** Dans une famille de trois marches, la mediane est calculee
sur le marche examine lui-meme : le comparer a elle revient a le comparer a lui-meme. C'est une
fuite de donnees, discrete et reelle. Le seuil de trente marches l'evite, et son effet sera mesure.

**La precision est un minorant.** L'etiquette faible est elle-meme un detecteur. Un marche que nous
signalons sans qu'il l'ait signale peut etre une anomalie qu'il a manquee. Annoncer « 75,8 % » sans
cette precaution serait malhonnete, et un jury attentif le releverait.

## Prochaine etape

Comparer ces regles a un modele non supervise, avec la meme etiquette et le meme protocole. Le
resultat sera publie meme s'il est defavorable aux regles. C'est la seule facon de justifier de
monter, ou de rester, sur la marche actuelle de l'escalier.
