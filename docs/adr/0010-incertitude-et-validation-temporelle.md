# ADR 0010. Publier l'incertitude, et caler la detection sur le passe

- Date : 2026-10-21
- Statut : accepte
- Phase : 6 bis, qualite des mesures
- Decide par : Elyse, le 21 octobre 2026

## Contexte

Neuf phases ont produit des dizaines de pourcentages : 40 intentions reconnues sur 40, 85,6 % de
rapprochements justes, 75,8 % de concordance de la detection, 60 % de marches attribues a une PME.
Aucun n'etait accompagne d'une marge.

Trois d'entre eux ne sont pas des comptages mais des estimations tirees d'un echantillon : 40
questions, 300 avis du BOAMP, 60 paires relues a la main. Publier une estimation sans son
intervalle revient a affirmer davantage que la mesure n'autorise, et c'est la critique la plus
facile a formuler devant un jury.

Une seconde faiblesse, plus discrete, a ete trouvee en cherchant la premiere. La regle de detection
compare chaque marche a la mediane de sa famille d'achat, et cette mediane est calculee sur
**toutes** les annees, y compris celles que la regle doit juger. Un marche de 2026 est donc compare
a une mediane qu'il a lui-meme contribue a former. C'est une fuite de donnees.

## Decision

**Trois regles, appliquees a tout le memoire.**

1. **Tout pourcentage tire d'un echantillon est publie avec son intervalle a 95 %, calcule par la
   methode de Wilson.** La formule `p ± 1,96 racine(p(1-p)/n)` est ecartee : elle annonce 100 %
   sans marge sur un resultat parfait, et sort de l'intervalle des valeurs possibles sur une
   proportion faible. Les deux cas existent dans le projet.
2. **Un pourcentage calcule sur la population entiere ne recoit pas d'intervalle, mais la source
   d'incertitude qui le concerne est nommee.** Un intervalle de tirage sur un recensement serait un
   faux air de rigueur.
3. **La detection est desormais evaluee hors echantillon** : references calculees sur 2019-2023,
   regle appliquee a 2024-2026. Le chiffre publie est celui-la.

### Ce que la methode de Wilson change, en une ligne

| Mesure | Formule naive | Wilson |
|---|---|---|
| 40 intentions reconnues sur 40 | [100,0 ; 100,0] | **[91,2 ; 100,0]** |
| 448 citations justes sur 448 | [100,0 ; 100,0] | [99,1 ; 100,0] |
| 1 succes sur 100 | **[-1,0 ; 3,0]** | [0,2 ; 5,4] |

La premiere ligne dit que la quarante et unieme question est certaine d'etre reconnue. La troisieme
annonce une proportion negative. Ce sont deux impossibilites produites par la meme formule.

### Les options envisagees

| Option | Avantage | Limite | Verdict |
|---|---|---|---|
| **Wilson** | correct jusqu'aux bords, aucune dependance, standard en sondage | pas exact au sens strict | **retenu** |
| Wald, `p ± 1,96 racine(p(1-p)/n)` | la formule que tout le monde connait | les deux impossibilites ci-dessus | ecarte, et montre dans la figure |
| Clopper-Pearson, binomial exact | jamais en dessous du niveau annonce | conservateur, intervalle plus large | calcule en controle |
| Bayesien, loi a priori de Jeffreys | bonnes proprietes sur petits effectifs | demande de justifier une loi a priori | non retenu |

Pour la justesse du rapprochement, qui est un estimateur pondere et non une simple proportion, un
**bootstrap stratifie** remplace la formule : on retire des paires a l'interieur de chaque tranche
de similarite, on recalcule la justesse redressee, dix mille fois. La mesure montre que mille
tirages auraient suffi ; dix mille coutent moins d'une seconde et laissent une marge.

Pour le decoupage temporel, un decoupage **par date** et non un tirage au hasard : un tirage
melangeant les annees autoriserait le futur a calibrer le passe, situation qu'aucune mise en
production ne reproduit.

## Consequences

### Ce que cela coute aux chiffres du memoire

| Chiffre | Avant | Apres |
|---|---|---|
| intentions reconnues par l'assistant | 100 % | 100 %, intervalle [91,2 ; 100,0] |
| justesse du rapprochement au seuil 0,5 | 85,6 % | 85,6 %, intervalle [76,7 ; 94,0] |
| concordance de la detection, seuil 4 | 78,0 % sur la periode de calage | **69,3 % hors echantillon**, intervalle [67,8 ; 70,8] |
| part des attributions a une PME | 59,2 % estimes sur 170 titulaires | 60,8 % comptes, encadrement [56,7 ; 63,5] |

La troisieme ligne est la plus couteuse et la plus importante : **le calage sur l'historique complet
ajoutait 4 points de concordance**, et les intervalles des deux calibrages ne se chevauchent pas,
donc l'ecart n'est pas du bruit.

La quatrieme ligne illustre la regle 2. Le passage de l'echantillon au recensement a supprime le
hasard de tirage, qui valait 14,5 points de largeur, et laisse une non-reponse de 6,8 points :
6,8 % des titulaires n'ont pas ete resolus par l'API, et aucune formule ne dira ce qu'ils sont.
L'incertitude a diminue, elle n'a pas disparu, et elle a change de nature.

L'unite de comptage est l'attribution, soit un couple marche-titulaire : la table en porte
1 999 474 pour 1 738 289 marches distincts, l'ecart venant des groupements d'entreprises. A
l'echelle du marche, 56,5 % des marches ont au moins une PME parmi leurs titulaires. Les deux
chiffres sont publies, parce qu'ils ne repondent pas a la meme question.

### Ce que la mesure a ouvert, et qui n'est pas resolu

**L'annee 2023 decroche de 28 points** (53,1 % contre 81,7 % en 2022), et les intervalles interdisent
d'y voir du hasard. La part de marches que le producteur signale lui-meme baisse cette annee-la,
mais elle baisse encore en 2024 ou la concordance remonte : l'explication ne suffit pas. **La cause
n'est pas etablie, et elle est publiee comme telle.**

Consequence de methode : la variation entre annees, 28 points, depasse de sept fois l'effet de fuite
que l'on cherchait a mesurer, 4 points. Un decoupage unique en deux periodes est donc une reponse
faible. **Une validation glissante, recalant les references chaque annee, est la suite logique**, et
elle est inscrite au carnet plutot que presentee comme faite.

### Un defaut du modele de production, decouvert au passage

Trente et une familles d'achat sur cinquante-sept voient leur mediane de prix bouger de plus de
26 % entre les deux periodes. Les plus mobiles sont celles dont l'effectif s'effondre : la famille
93 passe de 1 556 marches a 31. Or le modele de production verifie la taille minimale de famille
sur **l'historique complet**, pas sur la periode jugee. Une famille devenue trop rare continue donc
d'etre evaluee avec une reference estimee sur autre chose.

Ce n'est pas corrige dans cette phase : la correction change les chiffres de la detection, et elle
merite sa propre mesure. Elle est inscrite au carnet.

### Ce qui ferait changer cette decision

- Un jeu de questions ecrit par un tiers : il mesurerait la generalisation de l'assistant, que
  l'intervalle de Wilson ne couvre pas. L'intervalle porte sur le tirage, pas sur le fait que les 40
  questions ont ete ecrites par l'auteur du systeme.
- Un echantillon de marches juge a la main : il remplacerait l'etiquette faible du producteur, et
  rendrait la concordance interpretable comme une vraie precision. Aucun intervalle ne corrige une
  etiquette approximative.
- Un historique plus long : avec dix annees exploitables plutot que huit, la validation glissante
  deviendrait la mesure de reference et ce decoupage unique passerait en annexe.

## Mesures

`make bench-incertitude` et `make bench-stabilite`. Resultats dans `mesures/resultats/incertitude-*.csv`
et `stabilite-*.csv`, figures 22 et 23, exploration dans `analyses/10-incertitude-et-stabilite.ipynb`.
