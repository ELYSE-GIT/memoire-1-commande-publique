# 22 octobre 2026, deuxieme partie. Ecrire l'interface a casse l'API

L'API avait ete fusionnee le matin meme : sept routes, 239 tests verts, un banc de mesure qui
avait deja trouve quatre defauts et les avait corriges. Le travail de l'apres-midi devait etre
de la mise en page.

Il a fallu trois heures pour s'apercevoir que **l'API avait trois defauts de plus**, et qu'ils
etaient tous invisibles tant que son seul appelant etait celui qui l'avait ecrite.

## Le premier : un `# type: ignore` qui mentait

La page d'accueil a repondu 500 au premier essai.

    AttributeError: 'dict' object has no attribute 'annee'

La route `/statistiques/annees` etait ecrite ainsi :

    curseur_sql.execute(requetes.PAR_ANNEE)
    return curseur_sql.fetchall()  # type: ignore[return-value]

Elle annonce `list[StatistiqueAnnuelle]` et rend des dictionnaires. Le commentaire etait la pour
faire taire mypy, et mypy avait raison. Mais rien n'echouait : FastAPI convertit les
dictionnaires en modeles au moment de serialiser la reponse, donc l'API etait juste, la
documentation etait juste, et le mensonge etait invisible.

Il a cesse de l'etre le jour ou une page a appele la fonction **directement**, sans passer par
la couche HTTP.

La lecon tient en une ligne, et je la trouve plus utile que la correction : **un `type: ignore`
ne masque pas un detail de typage, il masque une affirmation fausse, et elle attend le second
appelant.**

## Le deuxieme : une question sur quatre faisait tomber l'API

En cliquant sur l'exemple « qui a remporte les marches de voirie en Ile-de-France en 2023 », la
page a repondu 500, avec vingt lignes d'erreur de validation Pydantic.

Le champ `lignes` d'une reponse d'assistant etait type
`list[dict[str, str | float | int | None]]`. Pour une question sur les titulaires, chaque ligne
contient une cle `citations` qui vaut une **liste** de numeros de marche. Le modele la refusait.

Donc : toute question sur les titulaires ou sur les acheteurs, soit neuf des quarante questions
du jeu versionne, faisait repondre 500 a l'API depuis sa mise en service.

Ce qui m'interesse ici, c'est pourquoi personne ne l'avait vu, parce que les deux bancs de
mesure existaient deja :

- `make bench-assistant` verifie les quarante questions, leurs chiffres et leurs 448 citations.
  Mais il appelle la bibliotheque directement, sans passer par le modele de reponse de l'API.
- `make bench-api` passe par le modele. Mais il n'envoyait **qu'une seule question**, un
  comptage.

Chaque banc couvrait exactement ce que l'autre laissait de cote. Le banc de l'API envoie
desormais une question par intention, sept au lieu d'une : c'est la seule facon de faire passer
chaque forme de reponse dans le modele au moins une fois.

## Le troisieme : une liste sans page suivante

Pour construire le lien « page suivante » de la liste des marches a examiner, il fallait savoir
s'il restait quelque chose derriere. `/signaux` rendait une liste nue : impossible de le savoir.

J'ai d'abord ecrit la deduction evidente, « la page est pleine donc il y en a une autre ». Elle
est fausse une fois sur dix, exactement quand le dernier resultat tombe sur une fin de page, et
elle propose alors un lien vers une page vide. La route rend maintenant une page, comme
`/marches`, avec une ligne demandee en plus dont la seule presence repond a la question.

Trois defauts, trois formes du meme fait : **une API dont le seul appelant est son auteur n'est
pas vraiment appelee.**

## Le quatrieme defaut etait a moi, et il etait dans la console

La politique de securite du site est stricte : `default-src 'none'`, puis `'self'` pour ce qui
est necessaire, et surtout **pas** de `'unsafe-inline'`. C'est pour cela que la figure de la
page d'accueil est un SVG dont la geometrie passe par des attributs, et non une barre
`style="width: 62%"`.

J'ai ouvert la page dans un vrai navigateur. Zero erreur a l'ecran, et une dans la console :

    Applying inline style violates the following Content Security Policy
    directive 'style-src 'self''.

C'etait htmx, qui insere sa propre feuille de style au chargement, pour ses indicateurs
d'attente. Des styles dont je n'avais pas besoin, puisque les miens sont dans `site.css`. La
correction est une balise `<meta name="htmx-config">`, parce que configurer htmx en JavaScript
aurait demande exactement ce que la politique interdit.

Ce qui vaut d'etre note : **tout etait vert sans navigateur**. Les tests passaient, le banc
passait, la page s'affichait. Une politique de securite ne se verifie pas en la lisant, elle se
verifie en la faisant appliquer par un navigateur. `make bench-site` relit maintenant les
en-tetes reellement servis, mais c'est l'ouverture d'un onglet qui a trouve celui-la.

## Le total de 403 milliards d'euros en trop

La page d'accueil devait afficher un montant total. Le calcul existait deja, dans la table des
comptages : `sum(montant)`, soit 1 500,9 milliards d'euros sur onze ans.

Le projet documente depuis la phase 2 qu'un marche attribue a un groupement d'entreprises occupe
une ligne par titulaire, et il le documente tres bien : 273 494 cas, mesures, expliques, avec
une figure. Mais uniquement pour les **comptages**. Personne, moi compris, n'avait regarde ce
que cela faisait aux **montants**.

Or le montant publie sur chacune des lignes d'un groupement est tres souvent celui du marche
entier, repete. Mesure :

    somme des lignes                                1 500,9 milliards d'euros
    une fois chaque couple (marche, montant)        1 098,2 milliards d'euros
    ecart                                             402,7 milliards, soit 36,7 %

Le site affichait un chiffre faux de 403 milliards d'euros, et il l'affichait en gros, sur sa
page d'accueil. C'est exactement le genre de nombre qu'un lecteur reprend sans verifier.

La page affiche desormais le total dedoublonne, l'addition naive a cote, et l'ecart en
pourcentage. La troisieme regle envisageable, garder le montant le plus eleve de chaque marche,
donne 1 097,9 milliards : 0,03 pour cent d'ecart avec la regle retenue. Le choix **entre** les
regles defendables ne change rien ; le choix de dedoublonner ou non change le total de 37 pour
cent.

Au passage, c'est la premiere migration du projet. `base/migrations/` etait vide, parce que
jusqu'ici un changement de schema se reglait en rechargeant une base vide. Celui-la arrive sur
une base de deux millions de lignes dont le rechargement prend plus d'une heure, et tous les
fichiers de `schema/` sont ecrits en `create table if not exists` : les relancer n'ajoute aucune
colonne.

## Le premier visiteur paie pour tous les autres

Le banc de l'API mesurait deja le premier appel a froid. Il donnait des centaines de
millisecondes, parfois une seconde. Acceptable.

Puis j'ai ouvert `/questions` sur un Mac qui venait de demarrer, conteneurs lances a l'instant.
Dix secondes, puis une erreur 504. La meme question, juste apres : 86 millisecondes.

Rien n'etait casse. La base n'avait aucune de ses pages en memoire, et le premier visiteur
payait le remplissage des caches pour tous les suivants. Ce qui rend la chose vicieuse, c'est
que le delai de dix secondes que le service s'impose **tue la requete avant qu'elle ait fini**,
donc rien n'est mis en cache, donc la requete suivante repart de zero.

Le service se prechauffe donc au demarrage. Trois etapes, et les deux premieres se sont trompees.

**Premiere tentative** : des requetes ecrites a la main, ressemblant a celles du service. Un
`select` avec l'index plein texte, un autre sur l'index des signaux. Resultat mesure : la
recherche tombe de 794 a 135 ms, `/signaux` ne bouge pas (1 199 ms contre 1 379 ms), l'assistant
ne bouge pas non plus. Prechauffer ne charge en memoire que les pages qu'on lit **vraiment** :
il faut lire ce que le service lira, pas quelque chose qui y ressemble.

**Deuxieme tentative** : charger toute la table en memoire avec `pg_prewarm`. Mesure :
22 secondes de demarrage, et la premiere recherche passe seulement de 1 766 a 647 ms, parce que
`shared_buffers` vaut 768 Mo pour une table de 1 386 Mo et que la seconde moitie chargee evince
la premiere. Extension installee, mesuree, desinstallee.

**Troisieme** : les vraies requetes du service, construites a partir du meme code, et une
question par forme de reponse de l'assistant.

    page                     sans prechauffage       avec
    /a-examiner              1 199 a 2 812 ms       166 ms
    /questions               1 107 a 4 000 ms       120 ms
    /recherche?q=...           794 a 1 766 ms        95 ms

Le demarrage passe de 0,9 a 10,9 secondes. Le cout n'a pas disparu, il a change de place : au
demarrage, personne n'attend. Il faudra s'en souvenir en phase 9, pour le `start_period` du
healthcheck du conteneur.

Et une derniere honnetete, parce qu'elle m'a coute une demi-heure : la mesure du cas froid est
**tres** variable. Entre deux executions, le meme premier appel va de 1 281 ms a 7 302 ms, selon
ce que le Mac garde du disque de la machine virtuelle. Redemarrer la machine virtuelle ne suffit
pas a refroidir vraiment, parce que l'hote garde l'image disque en cache. Les chiffres publies
donnent donc un intervalle et non une valeur, et je prefere ecrire un intervalle honnete qu'une
precision inventee.

## Ce que le banc du site mesure, et pourquoi la latence ne suffisait pas

`make bench-site` mesure trois choses que `make bench-api` ne peut pas mesurer, parce qu'elles
n'existent qu'une fois le HTML fabrique.

**Le poids.** Une page de 400 ko qui repond en 20 ms est lente pour qui la regarde. Les pages du
site font 4,4 a 16,2 ko, soit 1,9 a 5,5 ko compressees : 22 millisecondes d'attente sur une
connexion mobile mediocre. Aucune optimisation de poids n'est justifiee, et c'est une conclusion
mesuree, pas une impression.

**Le gain du rechargement partiel.** La meme adresse appelee avec et sans l'en-tete
`HX-Request` : le fragment pese 32 a 71 pour cent de moins que la page. C'est ce qui justifie
htmx, et sans la mesure ce serait une preference.

**Le fonctionnement sans JavaScript.** Chaque page est demandee comme le ferait un navigateur
dont le JavaScript est coupe, et son contenu doit etre present. Dix sur dix. C'est le plan B de
la soutenance, et un plan B qu'on n'essaie pas n'existe pas.

## Le prefixe de l'API, pose a temps

Une page HTML et une reponse JSON ne peuvent pas repondre a la meme adresse. L'API prenait
`/marches`, et le site en avait besoin.

Trois options : renommer les pages pour eviter les collisions, negocier sur l'en-tete `Accept`,
ou donner a l'API un prefixe. La negociation est elegante et fausse : un navigateur declare
accepter a peu pres tout, et le visiteur recevrait du JSON une fois sur deux. Renommer les pages
donnerait deux jeux de noms qui se ressemblent, et une collision a la premiere page ajoutee.

L'API passe donc sous `/api`. Les adresses publiees la veille changent, ce qui n'est jamais
agreable, mais l'API n'avait aucun consommateur exterieur : le prefixe a coute une heure de mise
a jour de la documentation et des mesures. Pose dans six mois, il aurait demande des
redirections a maintenir indefiniment. Un test verifie maintenant qu'aucune adresse n'est
revendiquee des deux cotes, parce qu'en cas de collision la premiere route declaree gagne, en
silence.

## Ce que je retiens

Le matin, le banc de mesure avait trouve ce que les tests ne voyaient pas, parce qu'aucun test
ne mesure une duree. L'apres-midi a ajoute deux cousins a cette lecon.

**Ecrire le second appelant est une forme de test.** Trois defauts reels, trouves en utilisant
l'API plutot qu'en la testant. Aucun n'etait subtil ; tous etaient invisibles depuis l'interieur.

**Ouvrir un navigateur est une forme de test.** La violation de politique de securite ne se
voyait ni dans les tests, ni dans le banc, ni a l'ecran. Elle se voyait dans la console, et il
fallait ouvrir la console.

Et un fait qui n'est pas une lecon mais qui compte : le chiffre le plus faux de la journee,
403 milliards d'euros, ne venait d'aucun bogue. Il venait d'une addition parfaitement correcte,
sur des donnees parfaitement documentees, posee sur la mauvaise unite de comptage. Le code
n'avait rien a se reprocher.
