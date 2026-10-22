# ADR 0011 : une API publique mesuree avant d'etre jolie

- Date : 2026-10-22
- Statut : accepte
- Remplace : rien. Complete l'ADR 0008 (PostgreSQL pour servir) et l'ADR 0009 (assistant sans
  modele de langue), dont elle expose le travail.

## Contexte

Les phases 1 a 6 ont produit une base chargee de 1 999 474 lignes, une recherche plein texte,
des regles de detection et un assistant a reponses sourcees. Rien de tout cela n'etait
accessible autrement qu'en lancant un script Python sur le Mac. Le livrable attendu est une
demonstration en direct sur un VPS, avec un espace d'administration : il faut donc un service
qui repond a des requetes, et une interface.

Cette decision porte sur l'API. L'interface fait l'objet d'une decision separee, parce que son
choix (gabarits rendus par le serveur plutot qu'une application JavaScript) ne depend pas des
memes mesures.

## Decision

Une API FastAPI dans `services/api`, sept routes, un pilote PostgreSQL synchrone dans des
routes `def`, et **quatre regles tirees de mesures, pas d'habitudes** :

1. Aucune route ne renvoie de nombre total de resultats.
2. Le classement d'une recherche porte sur 5 000 candidats au plus, et la reponse dit quand elle
   a atteint ce plafond.
3. Les comptages de la page d'accueil sont calcules au chargement, dans une table, jamais a la
   demande.
4. Tout ordre de tri est ecrit pour un index existant, et tout tri se termine par une colonne
   unique.

## Les options, pour le cadre

| Option | Avantage | Limite | Verdict |
|---|---|---|---|
| **FastAPI** | validation des entrees et documentation OpenAPI generees depuis les annotations de type deja presentes | une dependance de plus que Flask | **retenu** |
| Flask | plus petit, plus connu | ni validation ni documentation sans extensions : le meme poids reparti autrement | ecarte |
| Django REST Framework | administration et authentification fournies | un cadre entier a adopter pour une base qui existe deja hors de son ORM | ecarte |
| Litestar | tres proche, un peu plus rapide sur le papier | beaucoup moins d'exemples publics | ecarte |

Ce qui a fait pencher : le projet est deja annote et verifie par mypy en mode strict. FastAPI
reutilise ces annotations, donc le travail de typage sert deux fois.

## Ce que les mesures ont change

C'est la partie qui compte. Les quatre regles ci-dessus ne sont pas des principes : trois sur
quatre corrigent un defaut que le banc a trouve, et qu'aucun test n'aurait pu trouver, parce
qu'aucun test ne mesure une duree.

| Ce qui etait ecrit | Ce que la mesure a donne | Ce qui a change |
|---|---|---|
| classer toutes les lignes qui repondent | 9 656 ms a chaud sur « travaux » (348 748 lignes), abandonnee par la base | plafond de candidats, d'abord 20 000 |
| plafond a 20 000, valide a chaud | 7 219 ms **a froid** : premiere recherche apres demarrage en erreur 504 | plafond abaisse a 5 000 |
| comptages calcules a chaque visite | de 10 726 ms a 61 519 ms selon l'etat des caches | table remplie au chargement, lue en 0,5 ms |
| `order by date_notification desc nulls last` | 28 636 ms : PostgreSQL renonce a l'index et balaye deux millions de lignes | `order by date_notification desc, id desc`, 30 ms |
| serie par annee calculee a la demande | 655 ms de mediane, 2 365 ms au 95e centile | seconde table remplie au chargement, 2 ms |

Le quatrieme cas est le plus instructif, parce que le defaut etait une **precaution**. Le
`nulls last` servait a placer les marches sans date en fin de liste. Il y en a zero sur
1 999 474 lignes. Une protection qui ne protegeait de rien a coute un facteur 965.

## La contrepartie, mesuree et annoncee

Le plafond de candidats n'est pas gratuit. `make bench-api` compare les dix marches affiches aux
dix du classement exact :

| Lignes qui repondent | Marches communs sur dix |
|---|---|
| 437 | 10 |
| 1 162 | 10 |
| 5 489 | 8 |
| 13 482 | 5 |
| 20 477 | 3 |
| 6 432 | 2 |
| 101 818 et au-dela | 0 |

Sous le plafond, l'ordre est exact. Au-dessus, il peut etre entierement different, y compris
pour une question ordinaire de trois mots. Ce n'est pas un detail d'ordre : a 2 sur 10, ce sont
huit autres marches.

Trois consequences assumees :

- Les dix marches rendus ne sont pas quelconques : ce sont les mieux classes parmi les 5 000
  premiers que l'index rend, donc en pratique les plus recents, la table etant ecrite par date
  decroissante. Cette correspondance est une dependance a la facon dont le chargeur ecrit, pas
  une garantie du modele relationnel. Elle est mesuree (correlation de -0,96) et verifiee par un
  test.
- La reponse porte `classement_approche` et `candidats_examines`. Le site l'ecrira a l'ecran.
  Une approximation annoncee est une limite ; une approximation cachee est un mensonge sur la
  donnee.
- Ce compromis n'a pas ete choisi contre la justesse mais contre une page qui ne s'affiche pas.
  Une page absente n'a pas d'ordre du tout.

## Ce qui n'est pas dans cette decision

- **Pas de limitation de debit dans le code.** Elle appartient a Caddy, en phase 9 : un compteur
  en memoire serait remis a zero a chaque redemarrage, compterait faux des qu'il y a plus d'un
  processus, et devrait faire confiance a un en-tete que n'importe qui peut ecrire. Le filtrage
  par adresse appartient a celui qui voit la vraie adresse.
- **Pas d'authentification.** Les donnees servies sont publiques par nature. L'espace
  d'administration en aura une, et sera un routeur separe pour cette raison.
- **Pas de `Dockerfile`.** Phase 9, avec le deploiement, pour qu'il soit ecrit en meme temps
  qu'il est construit et teste.
- **Pas de cache HTTP.** Mettre en cache une route qui repond en 2 ms n'apporterait rien. A
  remesurer quand le site existera et que les pages assembleront plusieurs appels.

## Deux bornes ajoutees apres relecture de securite

Elles ne changent pas la decision, mais elles manquaient, et toutes deux decoulent du fait
nouveau que ce code est desormais expose au public.

**L'attente d'une connexion et la taille de la file.** Avec quatre connexions et dix secondes par
requete, quatre requetes lentes occupent toute la reserve. Le defaut de psycopg_pool fait alors
patienter trente secondes chaque visiteur suivant, chacun immobilisant un fil d'execution : le
service reste debout en apparence et ne repond plus a personne. C'est le mode de panne le plus
difficile a diagnostiquer, parce qu'il ne ressemble pas a une panne. L'attente est bornee a cinq
secondes et la file a trente-deux visiteurs, ce qui absorbe une pointe et refuse tot une charge
soutenue. Elargir la reserve aurait ete la mauvaise reponse : sur un petit VPS, cela remplace une
file d'attente par une panne de memoire.

**Le cache des mots de l'assistant.** La fonction qui cherche la frequence d'un mot garde ses
resultats dans un dictionnaire. Tant qu'elle ne servait qu'a `make bench-assistant`, elle voyait
40 questions ecrites a la main dans un processus qui s'arrete. Exposee par l'API, elle recoit ce
qu'un inconnu tape, et un dictionnaire sans borne grandit d'une entree par mot jamais vu, dans un
service qui tourne des semaines. Il est desormais borne a 20 000 entrees, le plus anciennement
utilise sortant en premier.

Ce que cette seconde borne ne protege pas, et qu'il faut dire : chaque mot inconnu coute une
requete a la base, en cache ou non. Limiter le nombre d'appels appartient au reverse-proxy, seul
a voir la vraie adresse de l'appelant, et c'est la meme raison que pour la limitation de debit.

La lecon generale est que du code sur, parce qu'il ne voyait que des entrees connues, cesse de
l'etre le jour ou on l'expose, sans qu'une seule de ses lignes ait change.

## Consequences

- Les comptages sont desormais un **etat a reconstruire** : `make indexer` doit suivre tout
  chargement, sinon `/statistiques` renvoie 503 plutot qu'un zero trompeur.
- `services/assistant.charger_lexiques` accepte un second argument facultatif, qui lui permet
  d'obtenir un curseur frais pour raciniser un mot inconnu. Sans lui, il gardait le curseur du
  demarrage, rendu a la reserve juste apres : la premiere question echouait sur « the cursor is
  closed ». Le comportement du banc de mesure est inchange.
- La chaine de connexion PostgreSQL est sortie dans `services/configuration.py`. Trois modules
  en tenaient une copie, chacune avec sa liste de variables obligatoires. Un test echoue si une
  quatrieme apparait.
- La profondeur de pagination est liee au plafond de candidats : 40 pages de 100 lignes au
  maximum. Un test verifie que les deux valeurs restent coherentes, parce que les desaccorder
  rendrait les dernieres pages vides sans erreur visible.

## Ce qui ferait changer cette decision

- **Un besoin d'afficher « page 12 sur 47 »** rendrait le comptage exact obligatoire, et il
  faudrait alors le mettre en cache par requete.
- **Dix fois plus de donnees** rendraient 5 000 candidats negligeables devant le nombre de
  reponses. Il faudrait un classement precalcule a l'ecriture, ou un moteur dedie (Meilisearch,
  Qdrant). Ni l'un ni l'autre n'est justifie avant d'avoir mesure ce que l'approximation gene
  reellement, ce qui demande les jugements de pertinence encore a rendre.
- **Plusieurs dizaines de visiteurs simultanes** rendraient l'avantage a un pilote asynchrone.
  `make bench-api` mesure le palier : de 95 a 111 requetes par seconde selon l'execution,
  sans aucun echec sur 300 appels.
  Tant qu'il n'est pas atteint, reecrire l'assistant en asynchrone serait un cout sans
  contrepartie.
- **Des donnees arrivant en continu** plutot que par lots rendraient les tables de comptages
  fausses entre deux chargements. Il faudrait alors des compteurs tenus a l'ecriture, ou accepter
  un chiffre approche et le dire.
