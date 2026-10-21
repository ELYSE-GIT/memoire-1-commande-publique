# 21 octobre 2026, soir. Quarante sur quarante, et ce que ca ne prouve pas

Meme journee que l'assistant. La phase 6 etait close, les 40 questions reconnues, les 448 citations
verifiees. Une question posee a froid a rouvert le dossier : est-ce que tout ce qui compte dans un
travail de donnees a ete fait ?

Reponse apres inventaire du depot : l'exploration oui, la modelisation statistique non. Trois
manques, dont deux se comblaient sans etiquette supplementaire et sans calcul lourd. Voici ce que
leur comblement a trouve.

## Le point de depart : un inventaire, pas une intuition

Avant d'ecrire une ligne, recherche de `bootstrap`, `intervalle de confiance`, `p-value`,
`train_test`, `cross_val` dans tout le depot. **Une seule occurrence**, dans le notebook 06 : une
marge calculee a la main avec la formule `p ± 1,96 racine(p(1-p)/n)`.

Elle y etait inoffensive, parce que la proportion mesuree valait 58,9 %, loin des bords. Appliquee
aux mesures de l'assistant, elle ne l'est plus du tout.

## Ce que la formule connue annonce sur 40 sur 40

    mesure                  observe          formule naive            Wilson
    intentions reconnues    100,0 %      [100,0 ; 100,0]      [ 91,2 ; 100,0]
    citations justes        100,0 %      [100,0 ; 100,0]      [ 99,1 ; 100,0]
    1 succes sur 100          1,0 %      [ -1,0 ;   3,0]      [  0,2 ;   5,4]

La premiere ligne affirme que la quarante et unieme question sera reconnue, c'est certain. La
troisieme annonce qu'une proportion peut etre negative. Deux impossibilites, produites par la meme
formule, pour la meme raison : quand `p` vaut 0 ou 1, le produit `p(1-p)` vaut zero, et la marge
aussi ; la formule suppose que la proportion observee est la vraie proportion, et a la frontiere
cette hypothese s'effondre sans prevenir.

Wilson a remplace Wald partout. Clopper-Pearson, le binomial exact, est calcule en controle, par
dichotomie sur la loi binomiale plutot qu'avec scipy : cinquante iterations, quelques
millisecondes, aucune dependance ajoutee. Deux valeurs de manuel servent de test, celles ou la loi
se reduit a un seul terme.

## Le bootstrap qui s'est referme sur un point

La justesse du rapprochement n'est pas une proportion simple : c'est une moyenne ponderee sur cinq
tranches de similarite, dont le denominateur varie parce que les paires marquees « doute » en
sortent. Pas de formule de variance simple, donc rééchantillonnage : tirer des paires a l'interieur
de chaque tranche, recalculer, dix mille fois.

    seuil   relues   justesse   intervalle a 95 %   largeur
      0.4       60     66,0 %     [ 59,3 ;  72,3]   13,0 pts
      0.5       48     85,6 %     [ 76,7 ;  94,0]   17,3 pts
      0.8       12    100,0 %     [100,0 ; 100,0]    0,0 pts

La derniere ligne a arrete la session. Un intervalle de largeur nulle se lit comme une certitude
absolue. Il dit ici exactement l'inverse : **les douze paires relues dans cette tranche sont toutes
justes, donc le rééchantillonnage ne peut tirer que des « oui » et repete la meme valeur**. La
methode n'a plus de prise, et sans controle elle l'annonce comme un resultat parfait.

Le cas est detecte, marque dans le CSV, et l'intervalle exact prend le relais : [73,5 ; 100,0]. La
lecon tient en une phrase : *une methode qui ne sait rien dire doit le dire, pas produire un
chiffre rassurant*.

Au passage, un chiffre faux corrige : j'ecrivais « 64 paires relues » dans trois fichiers. Le
fichier de verdicts en contient 60, dont 56 exploitables. Verifie en comptant, pas en se souvenant.

## Le vrai sujet : 85,6 % valait plus ou moins neuf points

Le seuil 0,5 du rapprochement a ete choisi sur une justesse estimee a 85,6 %. L'intervalle couvre
de 76,7 a 94,0. **La decision reste la bonne**, parce que l'intervalle du seuil 0,5 ne chevauche pas
celui du seuil 0,4 ; mais la precision affichee etait illusoire, et personne ne l'avait dit.

## La fuite que je ne cherchais pas

En montant la mesure de stabilite, une evidence qui n'avait jamais ete ecrite : la regle de prix
compare chaque marche a la mediane de sa famille d'achat, et cette mediane est calculee sur toutes
les annees, **y compris celle du marche juge**. Un marche de 2026 est compare a une mediane qu'il a
contribue a former.

    calibrage                      periode evaluee   precision   intervalle
    global (production actuelle)   apprentissage        78,0 %   [76,8 ; 79,1]
    global (production actuelle)   test                 73,3 %   [71,8 ; 74,8]
    apprentissage seul             apprentissage        70,8 %   [69,6 ; 72,0]
    apprentissage seul             test                 69,3 %   [67,8 ; 70,8]

A periode d'evaluation identique, la fuite ajoute **4 points**, et les deux intervalles ne se
chevauchent pas. Le chiffre publie passe de 73,3 a 69,3 %.

Lecture complete, et elle nuance la premiere : le calibrage global fait mieux sur les **deux**
periodes, pas seulement sur celle qu'il a vue. Disposer de deux millions de lignes pour estimer une
mediane aide reellement. Une partie des 4 points vient de la, l'autre de la fuite, et un decoupage
unique ne sait pas les separer. C'est ecrit comme tel plutot que simplifie.

## L'annee 2023, et ce qu'on ne sait pas

    annee   concordance   intervalle        etiquetes par le producteur
     2022       81,7 %    [79,7 ; 83,5]      3,35 %
     2023       53,1 %    [50,5 ; 55,6]      2,71 %
     2024       67,8 %    [65,1 ; 70,3]      2,46 %

Vingt-huit points de chute, et des intervalles separes de plus de vingt points : ce n'est pas du
bruit. Premiere explication venue : le producteur a change sa pratique d'etiquetage cette annee-la.
Elle ne tient pas. La part de marches qu'il signale baisse encore en 2024, ou la concordance
remonte a 67,8 %.

**La cause n'est pas etablie.** Elle est publiee comme telle. Le projet a deja paye cinq fois
l'erreur d'ecrire la conclusion avant de regarder la mesure, et une explication inventee apres coup
serait la sixieme.

Consequence de methode, plus genante que la fuite elle-meme : la variation entre annees, 28 points,
est **sept fois plus grande** que l'effet qu'on cherchait a mesurer, 4 points. Un decoupage unique
en deux periodes est donc une reponse faible a la question posee. La validation glissante, ecartee
en debut de session pour aller plus vite, redevient necessaire, et elle est inscrite au carnet.

## Un defaut de production trouve en chemin

Trente et une familles d'achat sur cinquante-sept voient leur mediane bouger de plus de 26 % entre
les deux periodes. Les plus mobiles sont celles dont l'effectif s'effondre : la famille 93 passe de
1 556 marches a 31. Or le modele de production verifie la taille minimale de famille sur
l'historique complet, pas sur la periode jugee. Une famille devenue rare continue d'etre evaluee
avec une reference estimee sur autre chose.

Pas corrige aujourd'hui : la correction change les chiffres de la detection et merite sa propre
mesure. Inscrit au carnet.

## Celle que je n'attendais pas : compter n'a pas supprime l'incertitude

Le notebook 06 estimait la part de PME sur 170 titulaires interroges par l'API. Depuis,
l'enrichissement a ete applique a toute la table : la part est **comptee**, 60,8 % des
attributions.

Reflexe naturel : l'incertitude a disparu. Faux.

    hasard de tirage de l'echantillon de 170   14,5 points de largeur
    non-reponse du recensement                  6,8 points d'etendue

Une verification d'unite faite avant de livrer, et qui a corrige le chiffre : `or_marches` porte
1 999 474 lignes pour 1 738 289 marches distincts, parce qu'un groupement d'entreprises donne une
ligne par titulaire. Le pourcentage porte donc sur des **attributions**, pas sur des marches. A
l'echelle du marche, 56,5 % ont au moins une PME. Les deux sont publies.

6,8 % des titulaires n'ont pas ete resolus par l'API. Leur categorie est inconnue, et aucune
formule ne la dira : on peut seulement encadrer, entre 56,7 et 63,5 %. L'incertitude a diminue de
moitie, elle n'a pas disparu, et surtout **elle a change de nature** : d'un hasard qui se calcule a
une non-reponse qui ne se corrige pas.

C'est ce qui a donne la troisieme table du module, celle qui nomme pour chaque chiffre la source
d'incertitude dominante plutot que de coller un intervalle partout. Un intervalle au mauvais
endroit rassure a tort.

## Ce qui est en place ce soir

`make bench-incertitude`, `make bench-stabilite`, figures 22 et 23, notebook 10, ADR 0010,
12 tests de plus dont deux qui verifient une **concordance entre fichiers** : le seuil de detection
lu directement dans le modele SQL de production, et le decoupage en tranches partage par deux
modules. Ce sont les erreurs les plus couteuses du projet, parce qu'elles ne font planter personne :
elles produisent une mesure qui ne parle pas de ce qu'on croit.

## Les trois lecons

1. **Un chiffre d'echantillon sans intervalle affirme plus que la mesure n'autorise**, et la formule
   la plus connue est celle qui echoue exactement la ou le projet mesure : aux bords.
2. **Un intervalle ne couvre que le hasard du tirage.** Pas une non-reponse, pas une etiquette
   approximative, pas un jeu de questions ecrit par l'auteur du systeme. Nommer la source qui domine
   vaut mieux que calculer celle qui se calcule.
3. **Chercher une faiblesse en revele d'autres.** Je cherchais des intervalles de confiance ; j'ai
   trouve une fuite de donnees de 4 points, un decrochage annuel inexplique de 28 points, et un
   defaut du modele de production. Aucun des trois n'etait visible sans la mesure.
