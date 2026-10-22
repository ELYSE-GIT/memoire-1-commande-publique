# ADR 0012 : un site rendu par le serveur, et une API qui prend un prefixe

- Date : 2026-10-22
- Statut : accepte
- Complete l'ADR 0011 (API publique), dont il est l'interface. Ne remplace rien.

## Contexte

L'ADR 0011 a produit une API qui sert les marches, les signaux, les comptages et l'assistant.
Elle est utilisable par un programme, pas par un visiteur : la demonstration attendue en
soutenance est une interface, avec un espace d'administration, sur un VPS Ubuntu de petite
taille.

Deux contraintes pesent sur le choix, et aucune n'est une question de gout.

**Le deploiement.** Le VPS heberge un service, pas une chaine de construction. Tout ce qui
demande Node.js, un build, un second artefact ou un second conteneur est un cout permanent
d'exploitation, pour un site de six pages.

**La demonstration.** Elle peut se faire hors ligne, depuis ce Mac, ecran partage. Un site qui
charge une bibliotheque depuis un reseau de diffusion de contenu est un site qui peut etre blanc
le jour de la soutenance, et un site qui n'affiche rien sans JavaScript l'est aussi.

## Decision

Les pages sont **fabriquees par le serveur**, avec des gabarits Jinja2, et **htmx** remplace le
rechargement complet par le remplacement d'un fragment. Le tout dans `services/site`, servi par
le meme processus uvicorn que l'API.

Cinq regles en decoulent, toutes verifiees par des tests ou par `make bench-site` :

1. **Les pages appellent les fonctions de route de l'API dans le processus**, jamais par HTTP.
   Une page ne contient ni SQL ni calcul metier.
2. **Chaque page fonctionne sans JavaScript.** Les formulaires sont de vrais formulaires ; htmx
   est une amelioration, pas une condition.
3. **Une adresse, deux rendus** : la meme route rend la page ou son fragment selon l'en-tete
   `HX-Request`, et pose `Vary: HX-Request`.
4. **Politique de contenu stricte, sans exception** : aucun domaine tiers, aucun
   `unsafe-inline`, aucun script en ligne.
5. **L'API passe sous le prefixe `/api`**, la racine revenant aux pages.

## Les options, pour le cadre

| Option | Avantage | Limite | Verdict |
|---|---|---|---|
| **Jinja2 rendu par FastAPI + htmx** | un service, aucune compilation, aucun Node.js sur le VPS, HTML deja rempli | un gabarit de plus par fragment | **retenu** |
| React ou Vue, application separee | l'etat du formulaire est tenu par le navigateur | Node.js, une compilation, un second artefact a deployer et a securiser, une API publique a versionner pour soi-meme | ecarte |
| Gabarits seuls, sans htmx | le plus simple possible | chaque filtre recharge toute la page : 11,7 ko au lieu de 7,9 ko mesures, et le formulaire se reconstruit a chaque clic | ecarte |
| htmx depuis un CDN | rien a versionner | la demonstration depend du reseau de la salle, et la politique de securite doit ouvrir un domaine tiers | ecarte |

A quelle echelle la reponse changerait : le jour ou une page garderait un etat complexe cote
navigateur, un cadre JavaScript reprendrait l'avantage. Afficher une liste et des filtres n'en
demande pas.

### Le prefixe `/api`, et pourquoi maintenant

| Option | Avantage | Limite | Verdict |
|---|---|---|---|
| **l'API sous `/api`, les pages a la racine** | des adresses humaines et lisibles pour les pages, et une separation nette | les adresses publiees la veille changent | **retenu** |
| les pages sous des noms sans collision (`/fiche/...` pour une fiche, `/marches` restant JSON) | aucune adresse ne change | deux jeux de noms qui se ressemblent, et une collision a la premiere page ajoutee | ecarte |
| negocier sur l'en-tete `Accept` | une seule adresse pour les deux | un navigateur declare accepter a peu pres tout : le visiteur recevrait du JSON une fois sur deux | ecarte |

Ce qui a fait trancher : le cout du changement. L'API avait ete publiee la veille et n'avait
aucun consommateur exterieur ; le prefixe a coute une heure de mise a jour de la documentation
et des mesures. Pose plus tard, il aurait demande des redirections a maintenir indefiniment.

## Ce que la construction de l'interface a revele dans l'API

C'est le resultat le plus utile de la journee, et il n'etait pas prevu. **Trois defauts de
l'API, publiee la veille avec 239 tests verts, sont apparus en ecrivant des pages qui
l'utilisent.** Aucun n'aurait ete trouve autrement, parce qu'une API dont le seul appelant est
celui qui l'a ecrite n'est pas vraiment appelee.

| Defaut | Ce qui le cachait | Ce qui l'a revele |
|---|---|---|
| `/statistiques/annees` rendait des dictionnaires en annoncant des modeles, avec un `# type: ignore` | FastAPI convertissait au moment de serialiser : la reponse HTTP etait juste | une page appelant la fonction directement, et un `AttributeError` |
| `/assistant` repondait 500 a toute question sur les titulaires ou les acheteurs | le type du champ `lignes` n'acceptait pas de liste ; `make bench-assistant` n'appelle pas le modele, `make bench-api` n'envoyait qu'une question de comptage | une page posant une autre question |
| `/signaux` ne disait pas s'il existait une page suivante | personne n'avait eu a paginer | un lien « page suivante » a construire |

La lecon generale, et elle vaut au-dela de ce projet : **un `# type: ignore` ne masque pas un
detail de typage, il masque une affirmation fausse, et elle attend le second appelant.** Et deux
bancs de mesure peuvent chacun couvrir ce que l'autre laisse de cote : `make bench-api` mesure
desormais une question par intention, ce qui est la seule facon de faire passer chaque forme de
reponse dans le modele.

## Le prechauffage, et le cout qui change de place

Le banc de l'API mesurait deja le premier appel a froid, et donnait des centaines de
millisecondes. En utilisant le site sur un Mac qui venait de demarrer, la premiere question
posee a l'assistant a depasse les dix secondes du service et renvoye une erreur. La meme
question, ensuite, repond en 86 ms. Rien n'etait casse : la base n'avait aucune de ses pages en
memoire, et le premier visiteur payait le remplissage des caches pour tous les suivants.

Le service lance donc au demarrage les requetes les plus couteuses, dont une question par forme
de reponse de l'assistant.

| Option | Avantage | Limite | Verdict |
|---|---|---|---|
| ne rien faire | aucun code | le premier visiteur apres chaque demarrage recoit une erreur, donc le jury le premier | ecarte |
| **prechauffer avec les vraies requetes** | le cout est paye au demarrage, ou personne n'attend | le demarrage passe de 0,9 a 10,9 s | **retenu** |
| augmenter le delai de la requete | une ligne | un service qui met dix secondes a repondre est un service casse | ecarte |
| charger toute la table en memoire (`pg_prewarm`) | toute recherche serait rapide, pas seulement celles prechauffees | **22 s** de demarrage mesurees, et un gain partiel : `shared_buffers` vaut 768 Mo pour une table de 1 386 Mo | ecarte, mesure |

Effet mesure sur le premier appel de chaque page, base froide :

| Page | Sans prechauffage | Avec |
|---|---|---|
| `/a-examiner` | 1 199 a 2 812 ms | **166 ms** |
| `/questions` | 1 107 a 4 000 ms | **120 ms** |
| `/recherche?q=...` | 794 a 1 766 ms | **95 ms** |

Une tentative intermediaire merite d'etre notee, parce qu'elle a failli etre gardee : des
requetes **ressemblant** a celles du service, ecrites a la main a cote. Elles faisaient tomber
le premier appel de la recherche de 794 a 135 ms et ne changeaient rien a `/signaux` (1 199 ms
contre 1 379 ms). Prechauffer ne charge en memoire que les pages qu'on lit vraiment : il faut
lire ce que le service lira, pas quelque chose qui y ressemble. Le prechauffage est donc
construit a partir des requetes du service, et l'assistant est prechauffe en lui posant
reellement les questions que le site propose en exemple. Un test verifie que les deux listes ne
divergent pas.

Limite assumee : une recherche que personne n'a encore faite reste a environ 1,8 seconde sur une
base froide. C'est lent, mais c'est sous le delai du service, donc c'est une attente et non une
erreur.

## Le total des montants, surcompte de 36,7 pour cent

Le site devait afficher un montant total. Le projet documentait depuis la phase 2 que les
groupements d'entreprises produisent plusieurs lignes par marche, mais seulement pour les
**comptages** ; personne n'avait regarde ce que cela faisait aux **montants**. Mesure :

| Facon de compter | Total | Cout |
|---|---|---|
| somme des lignes | 1 500,9 milliards d'euros | 2 s |
| **une fois chaque couple (marche, montant)** | **1 098,2 milliards** | 13 s |
| montant le plus eleve de chaque marche | 1 097,9 milliards | 25 s |

L'ecart entre les deux regles defendables est de 0,03 pour cent ; l'ecart avec l'addition naive
est de **403 milliards d'euros**. Le total dedoublonne est calcule au chargement, comme les
autres comptages, et la page d'accueil affiche les deux avec l'ecart.

C'est aussi la premiere migration du projet : `base/migrations/` etait vide jusqu'ici, parce que
chaque changement de schema se faisait en rechargeant une base vide. Celui-ci arrive sur une
base chargee dont le rechargement complet prend plus d'une heure, et tous les fichiers de
`schema/` sont ecrits en `create table if not exists`.

## Consequences

**Ce que cela apporte.** Un seul service a deployer et a superviser. Des pages de 4 a 16
kilo-octets. Un site qui fonctionne sans JavaScript et sans reseau. Une politique de securite
sans exception. Des adresses partageables et citables dans le memoire. Et une API dont trois
defauts reels ont ete corriges parce qu'elle a enfin un appelant qui n'est pas son auteur.

**Ce que cela coute.** Un demarrage de onze secondes, a prendre en compte dans le healthcheck du
conteneur en phase 9. Un gabarit de plus par fragment. Et l'impossibilite de redimensionner les
pages et les donnees separement, ce qu'aucune mesure ne justifie aujourd'hui.

**Ce qui ferait revenir sur cette decision.** Une page a etat complexe cote navigateur. Ou une
charge telle que l'affichage et la recherche ne puissent plus partager le meme processus : le
banc dit que le plafond est entre 87 et 111 requetes par seconde sur ce Mac, et il faudra le
remesurer sur le VPS, qui est moins puissant.
