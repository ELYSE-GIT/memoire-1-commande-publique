# 21 octobre 2026. L'assistant : zero reponse sur sept questions, puis 40 sur 40

Phase 6, seconde moitie. La recherche etait servie et mesuree depuis le 11 octobre. Restait a
repondre a une question posee en francais, pas a une liste de mots.

## Ce qui etait prevu, et ce qui s'est passe

Prevu : extraire l'annee et le lieu de la phrase, envoyer le reste a la recherche plein texte,
composer une reponse. Une demi-journee.

Resultat du premier essai, sur sept questions ecrites a l'avance : **zero marche trouve, sept fois
sur sept**. L'extraction de l'annee et du lieu fonctionnait. C'est la requete envoyee qui etait
fausse.

## Le mot qui annule la requete

`websearch_to_tsquery` combine les mots par ET, ce qui est le bon choix pour une barre de
recherche. Appliquee a une phrase entiere, la requete demande des marches contenant a la fois
« voirie » et « combien ».

Comptage, mot par mot, sur les 1 999 474 marches :

    combien       0 marche
    remporte      1 marche
    quel        513 marches
    voirie   42 061 marches

Un seul mot absent annule tout. Et le mot qui detruit la requete est precisement celui qui dit ce
que l'utilisateur veut faire.

## Premiere correction, et ce qu'elle a appris en echouant

Idee : ecarter les mots trop rares pour etre du vocabulaire de marche. Le critere est mesurable,
donc preferable a une liste ecrite a la main. `ts_stat` sur un echantillon de 5 % des pages donne
la frequence de 74 055 lexemes en 8 secondes.

La table des frequences a sorti deux surprises, toutes les deux des mots vides, tous les deux tres
frequents :

    a      23,3 % des marches
    le     13,3 % des marches

Deux mecanismes, decouverts en comparant `french` et `public.francais` mot a mot.

La configuration du projet retire les accents **avant** de consulter le dictionnaire. La
preposition « à » arrive donc sous la forme « a », et la liste des mots vides francaise contient
« à » mais pas « a ». Le jour ou la recherche est devenue insensible aux accents, cette
preposition est entree dans l'index.

Le meme mecanisme a l'envers laisse passer « les » : la liste contient « le » et « la », pas
« les ». Le dictionnaire verifie la liste sur le mot d'origine, puis racinise, et « les » ressort
sous le lexeme « le ».

Un choix de la phase 6, defendable et documente, avait un cout qui n'apparaissait qu'a la mesure
suivante. Le filtre a donc deux bornes et non une.

**Et il ne suffit pas.** Cinq questions sur sept trouvent maintenant des marches, contre zero.
J'ai failli m'arreter la. En comparant les requetes reellement envoyees a celles de la version qui
a fini par marcher, le vrai chiffre apparait : la version 2 n'envoie **jamais** la bonne requete,
zero fois sur sept.

Le mot « marches » y restait et faisait passer un resultat de 42 061 a 3 160, soit 92 % de perdus
en silence. « total », « plus », « signales » y restaient aussi. Et les deux questions qui
auraient du etre refusees recevaient une reponse.

Lecon de methode, plus que de technique : un chiffre flatteur obtenu sur un critere commode
(« trouve-t-on quelque chose ? ») a failli clore la question. Il s'est effondre des que le critere
est devenu calcule.

« quel », « total », « meilleur », « achete » sont assez rares dans les marches pour passer le
plancher, et assez courants dans une question pour la detruire. Aucun seuil ne separe ces deux
populations, parce que la frequence d'un mot dans les marches ne dit rien de son usage dans une
question. Le balayage de trente couples de seuils le confirme a l'envers : une fois l'intention
corrigee, l'ecart entre le pire et le meilleur couple n'est plus que d'une question sur quarante.

## La correction qui marche

Le probleme etait mal pose. « qui a remporte » ne decrit pas un contenu : il decrit une operation
sur les donnees. Le motif qui reconnait l'operation doit donc **emporter avec lui les mots qui
l'ont declenchee**. Le mot sert deux fois : il donne l'intention, et il quitte le texte.

Six intentions, plus un refus. Sept questions sur sept.

## Trois choses mesurees que je n'avais pas vues venir

**Une question a 54 secondes.** « Combien de marches en 2023 ». Deux causes : des agregats qui
trient (une mediane et un `array_agg` sur 272 057 lignes, demandes pour toutes les intentions
alors qu'une seule les affiche), et surtout **l'assistant ne filtre pas sur les memes colonnes que
la recherche**. La recherche part du texte, donc de l'index GIN. Une question sans texte demande
une agregation sur une grosse tranche de la table, ce qui est un autre metier. Les index avaient
ete poses pour la recherche et n'avaient pas suivi.

La correlation entre l'ordre physique des lignes et l'annee vaut -0,96 : la table a ete chargee
par date decroissante. C'est la condition exacte ou un index BRIN bat un B-tree sur le seul critere
qui compte sur un VPS, la taille. **56 ko contre 13 Mo**, pour un gain comparable.

**Le demarrage du service a 48 secondes.** Lire les lexiques demandait `select distinct` sur deux
millions de lignes, et un `min`/`max` sur une colonne non indexee. Un service qui met 48 s a
repondre a sa premiere question est casse, meme si toutes les suivantes sont rapides. 48 050 ms
devenus 61 ms.

**Une reponse juste a une autre question.** La plus grave des trois, et elle n'etait pas dans le
code mais dans le raisonnement. « Combien de marches de dsfgdsfg en 2023 » : le mot inconnu etait
ecarte comme n'importe quel parasite, l'annee restait, et l'assistant repondait « 272 057 marches
notifies en 2023 ». Exact, et sans rapport avec la question posee.

Retirer « de » ou « marches » ne change pas la question. Retirer le mot que l'utilisateur a choisi
pour decrire ce qu'il cherche la change. La distinction est maintenant dans le code, et elle
decide entre repondre, avertir et refuser.

## Une erreur d'attribution, corrigee par le banc

J'ai d'abord ecrit que remplacer `select distinct` par un parcours d'index de valeur en valeur
faisait passer la lecture des regions de 4 161 ms a 15 ms. Le banc, qui remesure les deux versions
de chaque choix cote a cote, a montre que c'etait faux : une fois l'index sur la region en place,
le `select distinct` d'origine tombe a 46 ms de lui-meme, parce que PostgreSQL peut alors
parcourir l'index seul au lieu de la table.

Deux changements faits le meme jour ne se mesurent pas ensemble. C'est pour cette raison que les
deux versions de chaque decision restent ecrites dans `mesures/assistant.py` et rejouees a chaque
passage, au lieu d'etre racontees dans un commentaire.

## Le refus comme fonctionnalite

Trois refus, et c'est la partie du composant dont je suis le plus sur.

« Quel est le meilleur fournisseur » demande une appreciation : aucune mesure de la qualite
d'execution n'existe dans ces donnees.

« Qui a fraude » demande une qualification penale. L'ADR 0006 a mesure que 48 % des marches
signales par la regle de prix sont des faux positifs. Repondre serait diffamatoire, et le message
de refus donne ce chiffre.

Une annee hors periode, ou un terme de recherche absent de l'index, font refuser aussi.

## Ce que le banc mesure, et ce qu'il ne mesure pas

Sept mesures, dont aucune ne demande d'avis. C'est la propriete cherchee : une reponse qui porte
son filtre et ses sources se verifie par une machine. 448 citations recherchees avec le filtre
annonce, zero fausse. Six regles de coherence par reponse, zero rompue. Chaque comptage refait en
interdisant les index au planificateur, zero divergence.

Ce qu'il ne mesure pas, et qu'il faut dire : **les 40 questions ont ete ecrites par la meme
personne que les motifs**. Un score de 40 sur 40 mesure la coherence interne, pas la capacite a
comprendre une question nouvelle. Seul un jeu ecrit par quelqu'un d'autre le mesurerait.

## Le defaut connu, laisse en place

« travaux » apparait dans 17,3 % des marches, « les » dans 13,3 %. La frequence ne peut pas garder
l'un et ecarter l'autre, et le plafond a 12 % ecarte les deux. « travaux de voirie » cherche donc
« voirie » seul : large, pas faux.

La correction tient en une dizaine de lignes : se servir des mots trop frequents pour **classer**
au lieu de **filtrer**. Elle n'est pas ecrite, parce que son benefice porte sur l'ordre des
resultats, qui ne se mesure que par un jugement humain de pertinence, et que ces jugements
n'existent pas encore. Monter une marche sans pouvoir la mesurer aurait contredit le principe
suivi partout ailleurs.

## Ce que je retiens

Le premier essai a echoue a 100 %, et c'est la meilleure chose qui pouvait arriver : un echec
total se diagnostique, un echec partiel se rationalise. La premiere correction, mesurable et
elegante, paraissait en rattraper cinq sur sept et n'en rattrapait aucune, ce que seul un critere
calcule a montre. Ce
sont les deux qui ont donne la troisieme.

Et le banc m'a contredit une fois sur un chiffre que j'avais deja ecrit. C'est exactement ce qu'on
lui demande.
