# services/api

L'API publique : ce que le site interroge, et ce qu'un tiers peut interroger directement.

Lancement : `make up` puis `make api`. Documentation interactive sur
<http://localhost:8000/docs>, generee depuis le code, donc toujours a jour.
Mesures : `make bench-api`.

| Fichier | Role |
|---|---|
| `main.py` | les routes, leurs garde-fous, les en-tetes de securite. Aucun calcul metier |
| `requetes.py` | tout le SQL, au meme endroit, pour etre relu sans lire le Python |
| `modeles.py` | la forme de chaque reponse, verifiee a chaque appel |
| `base.py` | la reserve de connexions, ouverte au demarrage et fermee a l'arret |

## Les routes

| Route | Ce qu'elle rend | p50 mesure |
|---|---|---|
| `GET /sante` | etat du service et de sa base | 2 ms |
| `GET /marches` | recherche par texte et par filtres | 22 ms |
| `GET /marches/{marche_id}` | toutes les lignes d'un marche et ses signaux | 2 ms |
| `GET /signaux` | les marches a examiner, les plus signales d'abord | 62 ms |
| `GET /statistiques` | les comptages de la page d'accueil | 2 ms |
| `GET /statistiques/annees` | la serie par annee, avec la part de PME | 2 ms |
| `GET /assistant` | une question en francais, avec ses citations | 36 ms |

Mesures du 22 octobre 2026, sur le Mac, base chargee de 1 999 474 lignes, a chaud. Le detail,
premier appel a froid compris, est dans `mesures/resultats/api-latences.csv`.

## Les quatre decisions, et ce qui les a tranchees

Chacune vient d'une mesure, pas d'un avis. Le detail est dans le fichier concerne.

**Aucun nombre total de resultats.** Compter les lignes qui repondent oblige PostgreSQL a toutes
les visiter. Le service rend une ligne de plus que demande : sa presence suffit a afficher
« page suivante ». Voir l'en-tete de `requetes.py`.

**Le classement porte sur 5 000 candidats au plus.** Classer les 348 748 lignes qui contiennent
« travaux » prenait 9 656 ms a chaud et 7 219 ms a froid au plafond de 20 000, contre 436 ms a
froid et 22 ms a chaud au plafond retenu. La contrepartie est mesuree et annoncee : au-dela du
plafond, les dix marches affiches ne sont pas les dix du classement exact, et la reponse porte
`classement_approche` pour que le site l'ecrive. Voir `PLAFOND_CANDIDATS` dans `requetes.py`.

**Les comptages ne sont pas calcules a la demande.** Entre 10,7 s et 61,5 s selon l'etat des
caches, contre 0,5 ms une fois lus dans une table d'une ligne remplie au chargement. Voir
`base/schema/008-table-statistiques.sql`.

**Les routes sont ecrites en `def` et non en `async def`.** Le pilote PostgreSQL utilise ici est
synchrone ; dans une route asynchrone il bloquerait toutes les requetes en cours. Ecrite en
`def`, la route tourne dans un fil separe. Ce choix permet surtout de reutiliser
`services/assistant` tel quel, avec ses 448 citations deja verifiees. Voir l'en-tete de
`base.py`.

## Ce que la charge donne

| Clients simultanes | Debit | p50 | p95 | Echecs |
|---|---|---|---|---|
| 1 | 46 req/s | 21 ms | 26 ms | 0 |
| 2 | 94 req/s | 21 ms | 25 ms | 0 |
| 4 | 93 req/s | 30 ms | 71 ms | 0 |
| 8 | 83 req/s | 92 ms | 161 ms | 0 |
| 16 | 92 req/s | 152 ms | 210 ms | 0 |

Le debit plafonne vers 90 requetes par seconde des deux clients, et au-dela la latence croit
proportionnellement au nombre de clients. C'est le comportement attendu d'une file d'attente :
le service ne s'effondre pas, il fait patienter. Le plafond vient de la reserve de connexions,
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
- **Pas d'interface.** Les gabarits Jinja2 et htmx viennent juste apres, dans `services/site`.
- **Pas de cache HTTP.** Aucune route ne pose `Cache-Control`. A mesurer quand le site existera :
  mettre en cache ce qui repond en 2 ms n'apporterait rien.
