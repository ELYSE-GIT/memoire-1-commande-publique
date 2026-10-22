# 22 octobre 2026. Quatre defauts qu'aucun test n'avait vus

Le depot comptait 195 tests verts et une chaine d'integration continue qui verifiait le style, les
types, les secrets et le comportement. La premiere version de l'API est passee au travers sans une
seule erreur. Elle etait inutilisable, et `make bench-api` l'a montre en moins d'une minute.

La raison tient en une phrase, et c'est la lecon de la journee : **aucun test ne mesure une duree**.
Un test verifie qu'une fonction rend le bon resultat, pas qu'elle le rend assez vite. Les quatre
defauts ci-dessous rendaient tous des resultats justes.

## Le premier : une precaution a 28 secondes

La liste des marches recents, sans texte, etait triee ainsi :

    order by date_notification desc nulls last, marche_id

Le `nulls last` servait a placer en fin de liste les marches sans date de notification. Intention
raisonnable. Deux faits la rendent absurde.

L'index est declare `on marches (date_notification desc)`, et PostgreSQL place par convention les
valeurs absentes en tete d'un tri descendant. Demander `nulls last`, c'est donc demander un ordre
que l'index ne connait pas : le moteur l'abandonne et trie deux millions de lignes.

    order by date_notification desc nulls last, marche_id    28 636 ms  (balayage parallele)
    order by date_notification desc, id desc                      30 ms  (index + tri incremental)

Et le second fait, verifie le meme jour : il y a **zero** ligne sans date de notification, sur
1 999 474. Une protection qui ne protegeait de rien a coute un facteur 965.

C'est la forme la plus commune du probleme : pas une erreur, une habitude defensive dont personne
ne mesure le prix. Elle serait restee invisible tant que la table serait restee petite.

## Le deuxieme : classer 348 748 lignes pour en afficher dix

La recherche classait toutes les lignes qui repondaient. Sur « travaux », 348 748 lignes repondent,
et leur classement prenait 9 656 ms, au-dela du delai de dix secondes que l'API s'impose : la base
abandonnait la requete et le visiteur recevait une erreur.

Le cout ne depend pas de la page demandee mais du nombre de reponses. Et le defaut ne se voyait pas
sur le jeu de mesure de la recherche, dont les 30 questions comptent toutes plusieurs mots, donc
repondent peu. Il a fallu ajouter des mots seuls et tres frequents au banc pour qu'il apparaisse.

## Le troisieme : la mesure a chaud qui valide un service casse

Premiere correction : ne classer que les 20 000 premiers candidats. Mesures excellentes, 57 ms de
mediane. Dossier clos.

Le banc l'a rouvert au lancement suivant : la toute premiere recherche apres le demarrage renvoyait
une erreur. En redemarrant PostgreSQL avant chaque essai, pour vider sa memoire partagee :

    plafond de candidats     base froide     a chaud
    20 000                      7 219 ms       57 ms
     5 000                        436 ms      116 ms
     1 000                         42 ms      101 ms

Un facteur 128. La cause est lisible : classer suppose de lire, pour chaque candidat, le vecteur de
mots du marche, que PostgreSQL stocke a part parce qu'il pese plusieurs kilo-octets.

**Mesurer seulement a chaud revient a valider un service qui echoue a chaque deploiement**,
c'est-a-dire precisement au moment d'une demonstration. Le banc mesure desormais le premier appel
separement, et ne le jette plus.

## Le quatrieme : dix secondes pour afficher quatre nombres

Les comptages de la page d'accueil, calcules a la demande : entre 10 726 ms et 61 519 ms selon
l'etat des caches. L'ecart entre les deux mesures n'est pas une erreur, c'est le fait principal : la
duree depend de ce qui reste en memoire partagee, donc de ce que le serveur a fait avant. Les deux
valeurs sont ecrites dans le schema, parce que n'en citer qu'une serait choisir celle qui arrange.

Le cout est presque entierement dans les `count(distinct)` : 9 092 ms sur 10 726. Aucun index n'y
change rien, il faut lire toutes les valeurs.

Deplace au chargement, dans une table d'une ligne : **0,5 ms** a la lecture. Meme traitement pour la
serie par annee, qui prenait 655 ms de mediane et 2 365 ms au 95e centile.

## Ce que l'optimisation a coute, et qu'il a fallu ecrire

Le plafond de 5 000 candidats n'est pas gratuit, et c'est la partie inconfortable. Le banc compare
les dix marches affiches aux dix du classement exact :

    marches qui repondent     communs sur dix
    437                                    10
    1 162                                  10
    5 489                                   8
    13 482                                  5
    20 477                                  3
    101 818 et au-dela                      0

Sous le plafond l'ordre est exact ; au-dessus il peut etre entierement different, y compris pour une
question ordinaire de trois mots. Deux sur dix, ce sont huit autres marches.

Abaisser le plafond de 20 000 a 5 000 a donc coute de la justesse : a 20 000, ces memes questions
donnaient 10, 10, 9, 9, 10, 8 et 10 sur dix. Le compromis est explicite, et il n'a pas ete choisi
contre la justesse mais contre une page qui ne s'affiche pas. Une page absente n'a pas d'ordre du
tout.

Ce qui n'etait pas negociable : le dire. La reponse porte `classement_approche` et le nombre de
candidats reellement classes. Une approximation annoncee est une limite ; une approximation cachee
est un mensonge sur la donnee.

## Trois pannes ordinaires, pour la completude

**La reserve de connexions refusait de s'ouvrir.** Message : « connection left in status INTRANS by
configure function ». La fonction qui regle chaque connexion lancait un `select set_config(...)`,
donc ouvrait une transaction, et la reserve refuse une connexion rendue a l'interieur d'une
transaction. Elle les jetait toutes. Un `commit` a la fin a suffi.

**La premiere question a l'assistant repondait « the cursor is closed ».** Les lexiques sont charges
au demarrage, et la fonction qui cherche la frequence d'un mot gardait le curseur du chargement,
rendu a la reserve juste apres. Le banc de mesure ne voyait rien, parce qu'il garde son curseur
ouvert pendant toute son execution. Corrige en laissant l'appelant fournir un curseur frais, avec
une valeur par defaut qui preserve le comportement du banc.

**Une colonne `duree_calcul_ms` a vecu une heure.** Elle valait zero. Le remplissage demandait a la
requete de se chronometrer elle-meme, par la difference entre deux `clock_timestamp()` pris dans
deux parties de la meme instruction ; PostgreSQL les a evaluees cote a cote. La colonne a ete
retiree plutot que corrigee : une duree se mesure par celui qui attend, pas par celui qui travaille.

## Ce qu'on en retient

1. **Un test et une mesure ne repondent pas a la meme question.** Les 195 tests etaient verts sur un
   service inutilisable. Il faut les deux, et il faut savoir lequel attrape quoi.
2. **Mesurer a froid, pas seulement a chaud.** Le cas froid est celui du premier visiteur apres un
   deploiement. C'est le seul qui a change une decision aujourd'hui.
3. **Un jeu de mesure herite d'une autre phase ne couvre pas la nouvelle.** Les 30 questions de la
   recherche, toutes de plusieurs mots, cachaient le defaut du classement. Il a fallu ajouter des
   mots seuls.
4. **Une optimisation se publie avec ce qu'elle coute.** Le chiffre qui compte n'est pas
   « 22 ms au lieu de 9 656 », c'est « zero marche commun sur dix au-dela du plafond ».
