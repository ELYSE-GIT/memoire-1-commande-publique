# services/api

L'API publique : ce que le site interroge, et ce qu'un tiers peut interroger directement.

Lancement : `make up` puis `make site` (les pages **et** l'API) ou `make api` (l'API seule, ce
que mesure `make bench-api`). Documentation interactive sur <http://localhost:8000/docs>,
generee depuis le code, donc toujours a jour. Mesures : `make bench-api`.

**Toutes les routes sont sous le prefixe `/api`** depuis le 22 octobre 2026 : la racine est
celle des pages du site, et une page HTML ne peut pas repondre a la meme adresse qu'un objet
JSON. Le raisonnement et son cout sont dans l'ADR 0012.

| Fichier | Role |
|---|---|
| `main.py` | les routes, leurs garde-fous, les en-tetes de securite. Aucun calcul metier |
| `requetes.py` | tout le SQL, au meme endroit, pour etre relu sans lire le Python |
| `modeles.py` | la forme de chaque reponse, verifiee a chaque appel |
| `base.py` | la reserve de connexions, ouverte au demarrage et fermee a l'arret |

## Les routes

| Route | Ce qu'elle rend | p50 mesure |
|---|---|---|
| `GET /api/sante` | etat du service et de sa base | 3 ms |
| `GET /api/marches` | recherche par texte et par filtres | 20 ms |
| `GET /api/marches/{marche_id}` | toutes les lignes d'un marche et ses signaux | 2 ms |
| `GET /api/signaux` | les marches a examiner, les plus signales d'abord | 84 ms |
| `GET /api/statistiques` | les comptages de la page d'accueil | 2 ms |
| `GET /api/statistiques/annees` | la serie par annee, avec la part de PME | 2 ms |
| `GET /api/assistant` | une question en francais, avec ses citations | 31 ms |

Mesures du 22 octobre 2026, sur le Mac, base chargee de 1 999 474 lignes, a chaud. Le detail,
premier appel a froid compris, est dans `mesures/resultats/api-latences.csv`.

## Ce que la construction du site a corrige ici

Trois defauts de cette API, publiee la veille avec 239 tests verts, ont ete trouves le
22 octobre 2026 en ecrivant les pages qui l'utilisent. Aucun n'aurait ete trouve autrement : une
API dont le seul appelant est son auteur n'est pas vraiment appelee.

- **`/api/statistiques/annees` rendait des dictionnaires en annoncant des modeles**, sous un
  `# type: ignore[return-value]`. FastAPI convertissait au moment de serialiser, donc la reponse
  HTTP etait juste et le mensonge invisible. Un `type: ignore` ne masque pas un detail de
  typage, il masque une affirmation fausse, et elle attend le second appelant.
- **`/api/assistant` repondait 500 a toute question sur les titulaires ou les acheteurs**, soit
  neuf des quarante questions du jeu : le type du champ `lignes` n'acceptait pas la liste de
  citations que ces reponses portent. `make bench-assistant` ne passe pas par le modele,
  `make bench-api` n'envoyait qu'une question de comptage ; chaque banc couvrait ce que l'autre
  laissait de cote. Le banc envoie desormais une question par intention.
- **`/api/signaux` rendait une liste nue**, sans dire s'il existait une page suivante. Elle rend
  maintenant une page, comme `/api/marches`.

## Le prechauffage au demarrage

Le service lance lui-meme, au demarrage, les requetes les plus couteuses : la recherche plein
texte, la liste des signaux, les deux tables de comptage, et une question par forme de reponse
de l'assistant. Environ dix secondes, pendant lesquelles personne n'attend.

Sans lui, la premiere question posee a l'assistant sur une base qui vient de demarrer depassait
les dix secondes du service et repondait 504. Le mecanisme est circulaire : le delai maximal tue
la requete avant qu'elle n'aboutisse, donc rien n'est mis en cache, donc la suivante repart de
zero.

| Page | Sans prechauffage | Avec |
|---|---|---|
| `/a-examiner` | 1 199 a 2 812 ms | 166 ms |
| `/questions` | 1 107 a 4 000 ms | 120 ms |
| `/recherche?q=...` | 794 a 1 766 ms | 95 ms |

Deux approches ont ete mesurees puis ecartees : des requetes ecrites a la main qui *ressemblent*
a celles du service (elles ne prechauffent que ce qu'elles lisent, donc pas `/signaux`), et
`pg_prewarm` sur toute la table (22 secondes de demarrage pour un gain partiel). Le detail est
dans `requetes.py`, a cote de `prechauffage()`.

`PRECHAUFFAGE=0` le coupe, et c'est ce que fait `make bench-api` : mesurer un service prechauffe
ne dirait plus rien du cas froid.

## Les quatre decisions, et ce qui les a tranchees

Chacune vient d'une mesure, pas d'un avis. Le detail est dans le fichier concerne.

**Aucun nombre total de resultats.** Compter les lignes qui repondent oblige PostgreSQL a toutes
les visiter. Le service rend une ligne de plus que demande : sa presence suffit a afficher
« page suivante ». Voir l'en-tete de `requetes.py`.

**Le classement porte sur 5 000 candidats au plus.** Classer les 348 748 lignes qui contiennent
« travaux » prenait 9 656 ms a chaud et 7 219 ms a froid au plafond de 20 000, contre 436 ms a
froid et 24 ms a chaud au plafond retenu. La contrepartie est mesuree et annoncee : au-dela du
plafond, les dix marches affiches ne sont pas les dix du classement exact, et la reponse porte
`classement_approche` pour que le site l'ecrive. Voir `PLAFOND_CANDIDATS` dans `requetes.py`.

**Les comptages ne sont pas calcules a la demande.** Entre 10,7 s et 61,5 s selon l'etat des
caches, contre moins de 3 ms une fois lus dans une table d'une ligne remplie au chargement. Voir
`base/schema/008-table-statistiques.sql`.

**Les routes sont ecrites en `def` et non en `async def`.** Le pilote PostgreSQL utilise ici est
synchrone ; dans une route asynchrone il bloquerait toutes les requetes en cours. Ecrite en
`def`, la route tourne dans un fil separe. Ce choix permet surtout de reutiliser
`services/assistant` tel quel, avec ses 448 citations deja verifiees. Voir l'en-tete de
`base.py`.

## Ce que la charge donne

| Clients simultanes | Debit | p50 | p95 | Echecs |
|---|---|---|---|---|
| 1 | 46 req/s | 21 ms | 25 ms | 0 |
| 2 | 78 req/s | 24 ms | 32 ms | 0 |
| 4 | 81 req/s | 52 ms | 72 ms | 0 |
| 8 | 89 req/s | 92 ms | 107 ms | 0 |
| 16 | 88 req/s | 165 ms | 252 ms | 0 |

Le debit plafonne entre 87 et 111 requetes par seconde selon l'execution, des huit clients, et
au-dela la latence croit proportionnellement au nombre de clients. L'ecart entre deux executions
du banc est reel et vaut d'etre note : il depend de ce que la base garde en memoire. Le banc
chauffe desormais le service par cent appels avant de monter en charge, parce qu'une mesure
faite sur une base froide donnait 13,4 requetes par seconde a un client : ce n'etait pas une
mesure du service, c'etait une mesure du disque. C'est le comportement attendu d'une file
d'attente : le service ne s'effondre pas, il fait patienter. Le plafond vient de la reserve de connexions,
volontairement limitee a quatre pour un VPS de petite taille, et des deux processeurs alloues a
la VM des conteneurs.

Aucun echec sur 300 appels. A remesurer sur le VPS, qui est moins puissant : c'est la mesure qui
dira s'il faut elargir la reserve ou ajouter un processus.

## Securite

- Aucune valeur fournie par un visiteur n'entre dans le texte d'une requete. Seule la structure
  est composee, avec `psycopg.sql`, et uniquement a partir de fragments ecrits dans
  `requetes.py`. Un test verifie qu'aucune ligne du dossier ne melange f-string et mot-cle SQL.
- Les connexions sont en lecture seule (`default_transaction_read_only`) : une route qui
  tenterait une ecriture serait refusee par la base.
- Chaque requete est abandonnee au-dela de dix secondes. Sans ce plafond, une requete
  pathologique garde une connexion et un fil pour toujours, et le service devient indisponible
  sans etre tombe.
- Toutes les entrees sont bornees : longueur du texte, annee, format du departement, taille de
  page, profondeur de pagination. Les bornes sont testees une par une.
- **L'attente d'une connexion est bornee** a cinq secondes, et la file a trente-deux visiteurs.
  Avec quatre connexions et dix secondes par requete, quatre requetes lentes saturent la reserve ;
  sans ces bornes, les visiteurs suivants patienteraient trente secondes chacun en immobilisant un
  fil, et le service resterait debout sans repondre a personne. Il repond « service sature »
  plutot que de ne plus repondre.
- **Le cache des mots de l'assistant est borne** a 20 000 entrees, le plus anciennement utilise
  sortant en premier. Tant que cette fonction ne servait qu'au banc de mesure, elle voyait
  40 questions ecrites a la main dans un processus qui s'arrete ; exposee au public, elle recoit
  un mot nouveau par appel si quelqu'un le decide.
- Un message d'erreur de PostgreSQL ne part jamais dans une reponse HTTP : il contient le texte
  de la requete, parfois l'hote et l'utilisateur. Il va dans le journal du serveur, et le
  visiteur recoit 503 ou 504.
- En-tetes poses par le service lui-meme, pour qu'il soit sain meme sans reverse-proxy devant :
  `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Content-Security-Policy`.
- Pas d'authentification sur ces routes : les donnees servies sont publiques par nature. L'espace
  d'administration en aura une, et c'est pour cela qu'il sera un routeur separe.
- Pas de limitation de debit dans le code : elle appartient a Caddy, en phase 9. Un compteur en
  memoire serait remis a zero a chaque redemarrage, compterait faux des qu'il y a plus d'un
  processus, et devrait faire confiance a un en-tete que n'importe qui peut ecrire.

## Ce qui n'est pas encore la

- **Pas de `Dockerfile`.** Il appartient a la phase 9, avec Caddy et le deploiement, et sera
  ecrit en meme temps qu'il sera construit et teste. Un Dockerfile jamais construit donne
  l'illusion d'un service deployable.
- ~~Pas d'interface.~~ Faite : voir `services/site/README.md`.
- **Pas de cache HTTP.** Aucune route ne pose `Cache-Control`. A mesurer quand le site existera :
  mettre en cache ce qui repond en 2 ms n'apporterait rien.
