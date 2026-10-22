# services/site

L'interface publique : six pages HTML, fabriquees par le meme processus que l'API.

Lancement : `make up` puis `make site`, et <http://localhost:8000/>.
Mesures : `make bench-site`.

| Fichier | Role |
|---|---|
| `main.py` | l'application deployee : l'API, les pages, les fichiers statiques, les erreurs |
| `pages.py` | une fonction par page. Aucun SQL : chaque page appelle la route de l'API |
| `gabarits/` | les gabarits Jinja2. `fragments/` contient ce que htmx remplace |
| `statique/` | la feuille de style, htmx versionne, l'icone. Voir son `README.md` : c'est le seul fichier tiers du depot, et son empreinte est verifiee par un test |

## Les pages

| Adresse | Ce qu'elle montre | p50 mesure | Poids |
|---|---|---|---|
| `/` | les comptages, deux diagrammes, par ou commencer | 6 ms | 17,0 ko |
| `/recherche` | le formulaire et les resultats | 25 ms | 15,5 ko |
| `/fiche/{marche_id}` | un marche, sa position dans sa famille, ses signaux | 4 ms | 6,5 ko |
| `/a-examiner` | les marches atypiques, motifs en clair | 67 ms | 8,4 ko |
| `/questions` | l'assistant, avec ses citations | 55 ms | 5,5 ko |
| `/a-propos` | les sources, les limites, la methode | 1 ms | 9,5 ko |

Mesures du 22 octobre 2026, sur le Mac, base chargee de 1 999 474 lignes. Le detail, premier
appel a froid et poids compresse compris, est dans `mesures/resultats/site-pages.csv`.

## Les trois figures, et ce qu'elles remplacent

Aucune bibliotheque de graphiques : les trois sont des SVG dont la geometrie est calculee en
Python et passe par des attributs. Une bibliotheque JavaScript pese de 90 ko a 3 Mo, demande
presque toujours `'unsafe-eval'` ou du script en ligne, et affiche une page vide si elle ne se
charge pas.

**Les attributions par annee, et la part des PME.** Repond a « la base couvre-t-elle vraiment
onze ans ? », que le seul chiffre « 1 999 474 » ne repond pas.

**Ce que l'Etat et les collectivites achetent.** Les dix premieres familles d'achat, libelles a
gauche et cliquables. Une page d'accueil qui annonce deux millions de marches sans dire de quoi
il s'agit ne dit presque rien.

**Ou se situe ce marche dans sa famille.** C'est la figure la plus utile du site. La fiche d'un
marche signale affichait « ecart normalise 6,53 » : c'est la bonne mesure, et personne ne sait
la lire. La reglette montre la moitie centrale de la famille, sa mediane, et la position du
marche, sur une echelle logarithmique, avec le rapport ecrit en toutes lettres a cote : « ce
marche coute 7 547 fois le montant median de sa famille ». L'echelle logarithmique n'est pas un
choix de presentation : les montants vont de quelques centaines d'euros a plusieurs centaines de
millions, et une echelle ordinaire tasserait toute la moitie centrale contre le bord gauche.

Les libelles des familles viennent de `base/reference/familles-cpv.csv`, pas de la base : une
nomenclature officielle n'est pas une donnee collectee. Le menu de recherche est devenu un menu
deroulant pour la meme raison : saisir « 45 » demandait de connaitre la nomenclature europeenne
pour se servir du site.

## Les cinq decisions

**Les pages appellent les fonctions de l'API, pas l'API par HTTP.** Une page de ce site ne
contient ni SQL ni calcul : elle appelle la fonction de route qui sert la meme chose en JSON, et
la met en forme. Elle ne peut donc pas afficher un chiffre que l'API ne servirait pas, ni
oublier un avertissement que l'API porte. Et il n'y a ni aller-retour reseau ni serialisation
payes pour rien. Voir l'en-tete de `pages.py`.

**Jinja2 et htmx, pas une application JavaScript.** Un seul service a deployer, aucune chaine
de compilation sur le VPS, et le HTML arrive deja rempli. htmx est versionne dans `statique/`
(51 ko), donc le site fonctionne sans reseau : c'est le plan B de la soutenance.

**Chaque page fonctionne sans JavaScript.** Les formulaires sont de vrais formulaires, avec une
`action` qui mene a une page complete. htmx ne fait que remplacer le rechargement complet par le
remplacement d'un fragment. `make bench-site` demande chaque page sans l'en-tete `HX-Request`
et verifie que son contenu est la : dix pages sur dix.

**Une adresse, deux rendus.** La meme route rend la page entiere ou son seul fragment, selon
l'en-tete `HX-Request` que htmx envoie. Une adresse reste donc partageable et citable
(`/recherche?q=voirie&annee=2024`), le bouton « retour » fonctionne, et le fragment pese 32 a
72 pour cent de moins que la page. L'en-tete `Vary: HX-Request` est pose en consequence : sans
lui, un cache rendrait un fragment a qui demande la page.

**L'API a pris le prefixe `/api`.** Une page HTML et une reponse JSON ne peuvent pas repondre a
la meme adresse. Le prefixe a ete pose le jour ou le site a ete ecrit, quand l'API n'avait aucun
consommateur exterieur ; plus tard, il aurait fallu maintenir des redirections. Un test verifie
qu'aucune adresse n'est revendiquee des deux cotes, parce que la premiere route declaree gagne,
en silence.

## Ce que le site affiche et que beaucoup cachent

- **« Classement approche »**, des que plus de marches repondent que le service n'en classe. Sur
  une recherche large, les dix marches affiches peuvent etre entierement differents des dix du
  classement exact. La page le dit et explique quoi faire.
- **Le total des montants dedoublonne**, 1 098,2 milliards d'euros, avec a cote l'addition naive
  qui donne 1 500,9 milliards. L'ecart de 36,7 pour cent vient des groupements d'entreprises, qui
  repetent le montant du marche entier sur chaque titulaire.
- **Le denominateur de chaque pourcentage.** La part de PME est rapportee aux seules attributions
  dont la categorie du titulaire est connue, et la page dit combien manquent.
- **« A examiner » et non « anomalies ».** La concordance des regles avec les anomalies publiees
  par le producteur est de 69,3 pour cent hors echantillon.
- **La date de calcul des comptages**, parce qu'un chiffre sans sa date ne dit pas s'il est
  perime.
- **L'adresse de l'API qui produit chaque page**, en pied de page. « Verifiable » veut dire
  qu'on peut obtenir la meme chose sans ce site.

## Securite

- **Politique de contenu stricte, sans exception** : `default-src 'none'` puis `'self'` pour ce
  qui est necessaire. Aucun domaine tiers, aucun `unsafe-inline`, aucun `unsafe-eval`. La figure
  de la page d'accueil est donc un SVG dont la geometrie passe par des attributs, et non une
  barre `style="width: 62%"` qui aurait oblige a autoriser le style en ligne.
- htmx est configure par une balise `<meta>` et non en JavaScript, pour la meme raison. Sans
  cela, il insere sa propre feuille de style en ligne, que le navigateur bloque : une violation
  par page, constatee dans un vrai navigateur.
- Tout texte venu des donnees est echappe par Jinja2, et un test le verifie sur un objet de
  marche contenant une balise `<script>`.
- Les en-tetes de l'API s'appliquent aussi aux pages : `X-Content-Type-Options`,
  `X-Frame-Options`, `Referrer-Policy`.
- Une erreur rend une page, pas un objet JSON, et ne revele rien de la base. L'API, elle, garde
  ses erreurs en JSON : le choix se fait sur le chemin demande et non sur l'en-tete `Accept`,
  qu'un navigateur remplit de facon inutilisable.
- **Aucune authentification ici** : les donnees servies sont publiques. L'espace
  d'administration, lui, en aura une, et c'est pour cela qu'il sera un routeur separe.

## Ce qui n'est pas encore la

- **L'espace d'administration.** C'est la suite immediate, et la facon dont il s'authentifie
  reste a decider avec Elyse.
- **Pas de `Dockerfile`.** Phase 9, en meme temps que Caddy, et ecrit le jour ou il sera
  construit et teste. Un Dockerfile jamais construit donne l'illusion d'un service deployable.
  Note pour ce jour-la : le service met de onze a vingt-sept secondes a demarrer selon l'etat
  des caches, prechauffage compris, donc le `start_period` du healthcheck doit etre genereux.
- **Pas de compression.** Les pages sont servies telles quelles ; Caddy compressera en phase 9.
  `make bench-site` mesure deja les deux poids, pour que le gain soit connu avant d'etre annonce.
- **Pas de page par acheteur ni par titulaire.** La recherche les trouve, mais il n'y a pas de
  fiche dediee. A faire si les jugements de pertinence montrent que c'est ce qu'on cherche.
