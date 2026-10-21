# ADR 0009. Un assistant a gabarits, sans modele de langue

- Date : 2026-10-21
- Statut : accepte
- Phase : 6, recherche et assistant
- Decide par : Elyse, le 21 octobre 2026

## Contexte

La recherche est servie et mesuree (ADR 0008) : 8 ms pour trouver les marches qui parlent de
voirie. Reste la moitie de la phase 6 : repondre a une **question**, pas a une liste de mots.

L'attente, en 2026, est qu'un assistant soit un modele de langue. C'est aussi ce que le sujet du
memoire invite a faire : comparer l'open source aux offres payantes, dont OpenAI.

La contrainte du projet est ailleurs. Le sujet porte sur l'argent public, et l'outil signale des
marches atypiques. Un chiffre faux ou une phrase mal calibree n'est pas un bogue d'affichage :
c'est une mise en cause d'un acheteur ou d'une entreprise. **L'exigence est donc la
verifiabilite avant la fluidite.**

## Decision

**Repondre par des gabarits de phrase alimentes par du SQL, avec le filtre applique rendu en
clair et les numeros de marche cites. Aucun modele de langue a cette etape.**

Six intentions couvrent les questions traitees : comptage, montant, titulaires, acheteurs,
marches signales, et a defaut la liste des extraits. Plus un refus, qui est la septieme et la
plus importante.

### Ce que « verifiable » veut dire, concretement

Une reponse rend trois choses ensemble : la phrase, le filtre applique en francais, et les
numeros de marche. Cela rend possibles trois verifications **automatiques**, ecrites dans
`mesures/assistant.py` :

1. chaque numero cite est recherche avec le filtre annonce ; s'il n'y est pas, la reponse cite
   une source qui ne la soutient pas ;
2. six regles de coherence sont verifiees sur chaque reponse (le nombre de marches a montant
   publie ne depasse pas le nombre de marches, la somme par titulaire ne depasse pas le total,
   une reponse qui annonce des marches cite au moins une source...) ;
3. le comptage est redemande apres avoir interdit les index au planificateur : meme semantique,
   autre machinerie.

Mesure du 21 octobre 2026, sur 40 questions : **448 citations verifiees, 0 fausse, 0 regle de
coherence rompue, 0 recomptage divergent.**

Aucune de ces trois verifications n'est possible sur une reponse redigee par un modele de langue,
non parce qu'un modele se tromperait plus souvent, mais parce que **rien dans sa reponse ne dit
d'ou vient le chiffre**. Il n'y a rien a verifier.

### Le refus comme fonctionnalite

Trois refus sont implementes, et c'est la partie du composant dont le projet est le plus sur.

**L'appreciation.** « Quel est le meilleur fournisseur de voirie » demande un jugement. Les
donnees essentielles de la commande publique disent qui a obtenu quel marche pour quel montant ;
elles ne contiennent aucune mesure de la qualite d'execution.

**L'accusation.** « Qui a fraude » demande une qualification penale. L'ADR 0006 a mesure que 48 %
des marches signales par la regle de prix sont des faux positifs. Repondre serait diffamatoire.
Le refus n'est pas une limite technique, c'est le comportement correct, et le message le dit avec
le chiffre.

**La question hors des donnees.** Une annee hors periode, ou un terme de recherche absent de
l'index.

Le troisieme cas a revele le defaut le plus grave trouve dans ce composant, et il n'etait pas
dans le code mais dans le raisonnement. « Combien de marches de dsfgdsfg en 2023 » : le mot
inconnu etait ecarte comme n'importe quel mot parasite, l'annee restait, et l'assistant repondait
« 272 057 marches notifies en 2023 ». Exact, et sans rapport avec la question.

Une reponse juste a une autre question est une reponse fausse, et c'est la forme d'erreur la plus
dangereuse pour cet outil, parce qu'elle est credible. La correction distingue deux categories de
mots ecartes : ceux dont le retrait ne change pas la question (« de », « marches »), et ceux dont
le retrait la change. Le second cas fait refuser, ou avertir quand une partie seulement est
perdue.

## Alternatives

| Option | Avantage | Limite | Verdict |
|---|---|---|---|
| modele distant (API payante) | phrases naturelles, aucune infrastructure | cout par question, donnees envoyees a un tiers, chiffre non verifiable automatiquement | ecarte pour l'instant |
| modele local quantifie, 3 a 7 milliards de parametres | gratuit, rien ne sort de la machine | 2 a 4 Go de RAM sur un VPS dont les specifications ne sont pas connues, latence de l'ordre de la seconde contre 20 ms | a mesurer en phase 9 |
| **gabarits de phrase alimentes par SQL** | **0 euro, 0 Go, latence de 20 ms, reponse verifiable par machine** | **phrases rigides, une tournure par intention** | **retenu** |
| le tableau brut, sans phrase | honnete, aucun risque | illisible pour qui ne connait pas le schema | ecarte |
| classifieur d'intention entraine | apprend les tournures reelles | demande un jeu de questions etiquetees qui n'existe pas | ecarte, faute de donnees |

Les gabarits ne sont pas un pis-aller. Ils rendent la reponse verifiable, ce qui est l'exigence du
sujet. Le modele de langue ameliorerait la forme **en retirant cette garantie**.

## Chemin parcouru, et les deux fausses pistes gardees

Le notebook `analyses/09-assistant-reponses-sourcees.ipynb` garde les trois versions avec leurs
mesures, parce que l'ecart entre elles est l'argument.

| version | ce qu'elle fait | trouve | envoie la bonne requete |
|---|---|---|---|
| 1 | tout le reste de la phrase part a la recherche plein texte | 0 sur 7 | 0 sur 7 |
| 2 | filtre les mots par leur frequence dans l'index | 5 sur 7 | **0 sur 7** |
| 3 | l'intention consomme ses mots declencheurs, le filtre reste en garde-fou | 7 sur 7 | 7 sur 7 |

« Trouve » veut dire : la requete rend au moins un marche. « Envoie la bonne requete » veut dire :
le texte transmis a la recherche est identique a celui de la version retenue, dont le banc verifie
par ailleurs qu'elle reconnait les 40 intentions du jeu.

La distinction est necessaire, parce que la version 2 **trouve souvent et cherche toujours autre
chose**. Le mot « marches » y reste et fait passer un resultat de 42 061 a 3 160, soit 92 % de
perdus sans que rien ne le signale ; « total », « plus » et « signales » y restent aussi ; et les
deux questions qui auraient du etre refusees recoivent une reponse.

Le cas de « marches » montre la limite de principe : ce mot apparait dans 8,7 % des marches,
souvent a bon droit (« amenagement du marche couvert »). Aucune statistique de frequence ne peut
distinguer le mot qui nomme la table du mot qui decrit un hall de marche.

La version 1 echoue entierement parce que `websearch_to_tsquery` combine les mots par ET : un seul
mot absent annule la requete. « combien » n'apparait dans aucun marche, « remporte » dans un seul.

La version 2 echoue a moitie pour une raison plus interessante : **la frequence d'un mot dans les
marches ne dit rien de son usage dans une question**. « quel », « total », « meilleur » sont assez
rares dans les marches pour passer le plancher, et assez courants dans une question pour la
detruire. Aucun seuil ne separe ces deux populations.

La version 3 pose le probleme autrement : « qui a remporte » ne decrit pas un contenu, il decrit
une operation sur les donnees. Le motif qui reconnait l'operation emporte donc les mots qui l'ont
declenchee. Le mot sert deux fois : il donne l'intention, et il quitte le texte.

## Les deux seuils du filtre ne sont pas critiques

Le balayage de 30 couples de seuils, dans le notebook, donne un ecart d'**une question sur
quarante** entre le pire couple et le meilleur. Le filtre par frequence n'est donc pas le
mecanisme principal : c'est un garde-fou, et son reglage exact a peu d'effet.

C'est un resultat et non une deception. Si le balayage avait montre une falaise, cela aurait voulu
dire que le composant tenait sur un seuil bien choisi, ce qui est fragile. Les seuils retenus
(0,05 % et 12 %) ne sont d'ailleurs pas le maximum mesure : des bornes un peu plus larges laissent
de la marge quand le vocabulaire des marches changera a la prochaine collecte.

## Un effet de bord mesure, qui vient d'un choix anterieur

La configuration `public.francais` retire les accents **avant** de consulter le dictionnaire
(ADR 0008). Consequence non prevue, mesuree le 21 octobre : la preposition « a » arrive au
dictionnaire sous la forme « a », la liste des mots vides francaise contient « a » accentue mais
pas « a » nu, et cette preposition est donc **indexee dans 23,3 % des marches**.

Le meme mecanisme, a l'envers, laisse passer « les » : la liste contient « le » et « la », pas
« les » ; le dictionnaire verifie la liste sur le mot d'origine puis racinise, et « les » ressort
sous le lexeme « le », present dans 13,3 % des marches.

Aucun des deux ne se corrige sans perdre l'insensibilite aux accents, qui est le service rendu a
l'utilisateur. Ils sont rattrapes par un plafond de frequence. Le choix de la phase 6 reste bon,
et il avait un cout qui n'apparaissait qu'a la mesure suivante.

## Consequences

### Ce que cela coute

Trois index ajoutes, parce que l'assistant filtre sur des colonnes que la recherche n'utilisait
pas : un BRIN sur l'annee (56 ko, contre 13 Mo pour un B-tree de performance comparable) et deux
B-tree sur les noms de region et de departement (27 Mo ensemble).

Une table de 74 055 lignes, `vocabulaire`, reconstruite en 8 s avec les index.

### Ce que cela rapporte

| mesure | valeur |
|---|---|
| intentions reconnues | 40 sur 40 |
| comportement attendu (repondre ou refuser) | 40 sur 40 |
| citations fausses | 0 sur 448 |
| latence mediane | 18 ms |
| latence la plus lente | de 0,3 a 0,4 s selon l'execution (402 ms au dernier passage) |
| cout | 0,0002 euro pour mille questions |
| demarrage du service | 61 ms a chaud, 534 ms sur base froide, contre 48 050 ms avant correction |

Les latences varient d'environ 30 % d'une execution a l'autre, comme celles de la recherche
(ADR 0008). C'est l'ordre de grandeur qui porte la conclusion, pas le chiffre.

### Une erreur d'attribution, corrigee par le banc

La premiere redaction de ce composant attribuait le gain du demarrage a une requete recursive qui
parcourt l'index de valeur en valeur, en opposant 4 161 ms a 15 ms. Le banc, qui remesure les deux
versions de chaque choix cote a cote, a montre que c'etait faux : une fois l'index sur la region en
place, le `select distinct` d'origine tombe a 46 ms de lui-meme, parce que PostgreSQL peut alors
parcourir l'index seul. La requete recursive ajoute un facteur 66 par-dessus, ce qui est utile mais
n'est pas ce qui sauve le demarrage.

Deux changements faits le meme jour ne se mesurent pas ensemble. C'est la raison pour laquelle les
deux versions de chaque choix restent ecrites dans `mesures/assistant.py` et remesurees a chaque
passage, plutot que racontees dans un commentaire.

### La limite a enoncer devant un jury

Les 40 questions ont ete ecrites par la meme personne que les motifs. **Un score de 40 sur 40
mesure la coherence interne, pas la capacite a comprendre une question nouvelle.** Seul un jeu
ecrit par quelqu'un d'autre le mesurerait, et ce jeu n'existe pas encore.

Ce chiffre n'est donc pas presente comme un resultat de qualite. Les resultats de qualite de ce
composant sont les trois verifications automatiques, qui ne dependent pas de qui a ecrit les
questions.

### Le defaut connu, non corrige, et pourquoi

« travaux » apparait dans 17,3 % des marches, « les » dans 13,3 %. La frequence ne peut donc pas
garder l'un et ecarter l'autre, et le plafond a 12 % ecarte les deux. « travaux de voirie » cherche
« voirie » seul : la recherche reste large, elle ne devient pas fausse.

La correction propre est connue et tient en une dizaine de lignes : ne plus **filtrer** avec les
mots trop frequents mais s'en servir pour **classer**. Un mot frequent ne decide pas quels marches
sortent, il decide dans quel ordre.

Elle n'est pas ecrite, et c'est delibere. Son benefice porte sur l'ordre des resultats, qui ne se
mesure que par un jugement humain de pertinence, et ces jugements n'existent pas encore. Monter
cette marche sans pouvoir la mesurer contredirait le principe qui a guide tout le reste du projet.

## Ce qui ferait reviser cette decision

| marche suivante | declencheur chiffre |
|---|---|
| mots frequents utilises pour classer | les jugements de pertinence relus montrent un defaut d'ordre |
| classifieur d'intention entraine | plus d'une intention sur cinq mal reconnue sur un jeu ecrit par un tiers |
| modele de langue local pour rediger | des questions reelles hors des six intentions, demandant une synthese en prose, et un VPS dont la RAM le permet |
| modele distant | jamais pour les chiffres ; eventuellement pour reformuler une phrase deja verifiee, le chiffre restant produit par le SQL |

La derniere ligne est la position de repli si un jury insiste sur l'usage d'un modele de langue :
le modele peut habiller une reponse, il ne doit pas la produire.
