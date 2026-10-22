# Chapitre 6. L'architecture retenue, service par service

> Brouillon. Les faits, les chiffres et les mesures sont vérifiés et reproductibles ; la
> formulation reste à reprendre dans la voix de l'auteur.

Les trois chapitres précédents ont posé le problème, l'état de l'art et l'histoire des outils.
Celui-ci décrit ce qui a été construit : six services, deux moteurs de base de données, une seule
machine en production, et une règle qui explique presque toutes les décisions.

Un parti pris de présentation, assumé : **chaque choix est donné avec ce qui a été écarté et à
quelle échelle la réponse changerait.** Une architecture sans ses alternatives n'est pas une
architecture, c'est une habitude.

---

## 6.1 Les cinq contraintes qui déterminent tout le reste

Aucune de ces contraintes n'est technique à l'origine. Toutes ont des conséquences techniques
lourdes.

| Contrainte | Origine | Conséquence sur l'architecture |
|---|---|---|
| **Reproductible** | un jury doit pouvoir faire exécuter la chaîne | versions verrouillées, image de base figée par son empreinte, aucune étape manuelle |
| **Sobre** | la machine de développement est un ordinateur portable de 16 Go, utilisé au quotidien pour autre chose | rien ne tourne en permanence, plafonds de processeur et de mémoire explicites, tout se supprime proprement |
| **Démontrable** | la soutenance peut se faire hors ligne, écran partagé | aucune dépendance à un réseau de diffusion de contenu, les pages fonctionnent sans JavaScript, un plan B hors ligne |
| **Une seule machine modeste en production** | un VPS, moins puissant que le Mac | pas de grappe, pas d'ordonnanceur de conteneurs, une empreinte mémoire qui tient |
| **Coût mesuré et défendable** | c'est la thèse du mémoire | chaque brique est libre, et son coût d'exploitation est chiffré (chapitre 11) |

La quatrième est la plus structurante, et la moins négociable : elle écarte d'emblée toute solution
dont le prix d'entrée est une grappe de machines.

---

## 6.2 Le trajet de la donnée

```
   SOURCES PUBLIQUES                COLLECTE              TRANSFORMATION            SERVICE
 ┌──────────────────┐         ┌───────────────┐       ┌──────────────────┐    ┌──────────────┐
 │ DECP             │         │               │       │  bronze  3,30 M  │    │ API          │
 │ data.gouv.fr     │────────▶│  services/    │──────▶│  la donnée brute │───▶│ FastAPI      │
 │ 250 Mo Parquet   │         │  collecte/    │       │                  │    │ 7 routes     │
 ├──────────────────┤         │               │       │  argent  2,12 M  │    ├──────────────┤
 │ BOAMP            │────────▶│  manifeste    │──────▶│  nettoyée,       │───▶│ Site public  │
 │ 1,7 M d'avis     │         │  empreinte    │       │  problèmes       │    │ 6 pages      │
 ├──────────────────┤         │  idempotence  │       │  marqués         │    │              │
 │ Recherche        │         │               │       │                  │    │              │
 │ d'entreprises    │────────▶│  reprise sur  │──────▶│  or  2,00 M      │───▶│ Assistant    │
 │ 242 745 SIRET    │         │  erreur       │       │  servie          │    │ sans modèle  │
 └──────────────────┘         └───────────────┘       └────────┬─────────┘    └──────▲───────┘
                                      │                       │                     │
                                      ▼                       ▼                     │
                              données/manifestes/     mesures/résultats/            │
                              (versionné)             (versionné, figures)          │
                                                              │                     │
                                              PUBLICATION     ▼                     │
                                            ┌─────────────────────────────┐         │
                                            │  PostgreSQL 17 + pgvector   │─────────┘
                                            │  conteneur, port 55432      │
                                            │  table servie 1 453 Mo      │
                                            │  index plein texte 120 Mo   │
                                            │  recherche en 4 ms          │
                                            └─────────────────────────────┘
```

Six stations, et une seule direction. Chaque flèche correspond à une commande du `Makefile`, et
chaque station à un dossier du dépôt. C'est volontaire : **le dépôt doit s'expliquer en le
parcourant**, sans qu'il faille lire du code Python pour découvrir où se trouve une règle de
nettoyage ou un index.

---

## 6.3 Deux moteurs de base de données, et pourquoi la publication ne transforme rien

C'est la décision qui surprend le plus, et celle qui se justifie le mieux par la mesure.

**DuckDB calcule. PostgreSQL sert.** DuckDB est une bibliothèque chargée dans le processus Python :
rien n'écoute sur un port, rien ne survit à la fin d'une commande. Il agrège deux millions de
lignes sans les charger en mémoire, et c'est exactement ce dont la chaîne de transformation a
besoin. Mais un fichier DuckDB n'est ouvert que par un seul processus lecteur, ce qui interdit de
servir plusieurs visiteurs.

Les deux moteurs ont été mesurés sur les mêmes trente questions, avec la même liste de mots vides,
le même racineur et le même retrait des accents, car les comparer sans cette précaution aurait
mesuré une différence de configuration en croyant mesurer une différence de moteur[^adr8].

| | PostgreSQL | DuckDB |
|---|---|---|
| Recherche « tous les mots », médiane | **4,0 ms** | 106 ms |
| Taille sur disque, table et index | 1 573 Mo | **312 Mo** |
| Plusieurs lecteurs simultanés | oui | non |

PostgreSQL est environ vingt-cinq fois plus rapide, DuckDB occupe cinq fois moins de place. Et il
faut dire la chose dans le bon ordre : **la décision de servir depuis PostgreSQL a été prise avant
cette mesure**, ce qui contredit le principe de l'escalier appliqué partout ailleurs. L'argument
retenu était que les latences mesurées sur PostgreSQL seraient celles de la production. La
contrepartie, posée au moment de la décision, a été de mesurer les deux moteurs quand même, pour
que la comparaison existe au lieu d'être supposée. Elle conclut qu'à faible trafic, DuckDB aurait
tenu : 106 millisecondes restent une latence acceptable. **Le choix de PostgreSQL se justifie par
la concurrence entre visiteurs, pas par la vitesse pure.**

**La règle qui encadre les deux bases** mérite d'être énoncée seule, parce qu'elle évite une classe
entière de bugs : **l'étape de publication ne nettoie rien et ne recalcule rien.** Elle copie la
couche or telle quelle. Si elle corrigeait quoi que ce soit, le projet aurait deux vérités, celle
de la chaîne de transformation et celle du site, et aucun moyen de savoir laquelle est affichée.

---

## 6.4 Les six services, et le fichier à ouvrir

| Service | Rôle | Où regarder | Ce qui a été écarté |
|---|---|---|---|
| **collecte** | récupérer les sources sans les abîmer, et tracer ce qui a été récupéré | `services/collecte/` | un orchestrateur, une bibliothèque HTTP tierce |
| **transformation** | trois couches, du brut au servi, en SQL | `services/transformation/models/` | du SQL lancé à la main, pandas, SQLMesh |
| **publication** | copier la couche or vers la base que le site interroge | `services/publication/` | que le site lise DuckDB directement |
| **api** | sept routes JSON sous `/api` | `services/api/` | GraphQL, une API non versionnée exposée sans mesure |
| **site** | six pages HTML à la racine, gabarits et fragments | `services/site/` | React ou Vue, une bibliothèque depuis un réseau de diffusion |
| **assistant** | lire une question, répondre en citant ses sources | `services/assistant/` | un modèle de langue, un cadre d'agents |

À quoi s'ajoutent deux dossiers qui ne sont pas des services mais qui portent de l'architecture :
`base/` contient neuf fichiers de schéma et deux migrations, en SQL versionné, car **aucun schéma
n'est créé à la main dans une console** ; `mesures/` contient les quinze bancs de mesure et leurs
résultats en CSV, dont les figures du mémoire sont tracées.

---

## 6.5 Un seul processus pour le site et l'API, et pourquoi c'est un choix d'architecture

Le site et l'API tournent dans le même processus, et les pages appellent les fonctions de route de
l'API **dans le processus, jamais par HTTP**. Une page ne contient ni SQL ni calcul métier.

Ce choix a quatre conséquences, toutes vérifiées par des tests ou par un banc de mesure[^adr12] :

1. **Aucune étape de construction.** Pas de Node.js sur le VPS, pas de second artefact à déployer
   et à sécuriser. Pour un site de six pages, une chaîne de construction est un coût permanent
   d'exploitation.
2. **Chaque page fonctionne sans JavaScript.** Les formulaires sont de vrais formulaires ; htmx est
   une amélioration, pas une condition. Les dix pages mesurées répondent complètement lorsqu'on les
   demande sans l'en-tête d'htmx, c'est-à-dire comme le ferait un navigateur sans JavaScript.
3. **Une adresse, deux rendus.** La même route rend la page entière ou seulement son fragment selon
   l'en-tête de la requête, et annonce cette variation dans sa réponse. Le fragment économise 51,8 %
   du poids, en médiane, sur les pages à rechargement partiel.
4. **Une politique de sécurité de contenu stricte, sans exception** : aucun domaine tiers, aucun
   script en ligne, aucune feuille de style en ligne. Cette contrainte a une conséquence inattendue
   sur les figures du site, dont la géométrie passe par des attributs et jamais par du style en
   ligne.

À quelle échelle la réponse changerait : le jour où une page devrait tenir un état complexe côté
navigateur, un cadre JavaScript reprendrait l'avantage. Afficher une liste et des filtres n'en
demande pas.

---

## 6.6 Pas d'orchestrateur, et le critère précis qui le ferait entrer

Dagster figurait dans les outils envisagés au départ, et la Fédération Wallonie-Bruxelles en fait un
usage proche du nôtre (chapitre 4). Il n'est pas retenu, et la raison est un raisonnement que l'on
peut contredire : **un orchestrateur résout un problème de dépendances entre étapes.** Les trois
sources du projet sont indépendantes et se collectent en une commande chacune. L'introduire
reviendrait à faire tourner un service de plus pour un besoin qui n'existe pas.

Le critère de révision est écrit, et il est vérifiable : le jour où la chaîne comportera des étapes
dont l'ordre et la reprise fine deviennent difficiles à tenir à la main, ou le jour où une
planification avec trace d'exécution deviendra nécessaire sur le VPS. Pour le déclenchement
périodique, un simple planificateur système suffit, et c'est ce qui est prévu en phase 9.

Le même raisonnement a écarté une bibliothèque HTTP tierce : la reprise sur erreur et la limitation
de débit tiennent en une trentaine de lignes de bibliothèque standard, commentées, qu'il faut de
toute façon comprendre pour les expliquer devant un jury.

---

## 6.7 Ce qui est versionné, et ce qui ne l'est pas

C'est la question la plus fréquemment posée sur ce dépôt, et la réponse est une règle simple : **on
versionne la preuve, pas la donnée.**

| Élément | Taille | Versionné | Pourquoi |
|---|---|---|---|
| Donnée brute | 250 Mo par collecte | non | lourde, republiée chaque matin, retéléchargeable |
| Manifeste de collecte | quelques Ko | **oui** | c'est la preuve de ce qui a été mesuré |
| Agrégats mesurés | quelques Ko | **oui** | ce sont les chiffres du mémoire |
| Figures | environ 4 Mo | **oui** | générées, mais lues par le mémoire |
| Jeu d'essai des tests | 3 Ko | **oui** | sans lui, les tests ne tournent pas sur une machine vierge |

Le manifeste est la pièce qui rend une mesure vérifiable par un tiers : il porte l'adresse exacte,
la date, la taille et l'empreinte du fichier. Il répond à la question « comment savez-vous que ce
chiffre porte bien sur ce fichier-là », qui sera posée en soutenance.

---

## 6.8 Les cinq principes tenus dans tout le dépôt

Ils reviennent partout, et les connaître dispense de lire le reste.

**1. Mesurer avant d'affirmer.** Aucun chiffre n'entre dans ce mémoire sans une commande qui le
produit. Un test compare même les chiffres cités aux mesures enregistrées : si une donnée change, la
chaîne d'intégration nomme le chiffre devenu faux.

**2. Marquer plutôt que supprimer.** Aucune ligne n'est jamais retirée. Une ligne fautive porte la
liste de ses problèmes, en clair. Une ligne effacée ne peut plus être expliquée à un jury, ni
corrigée par l'administration qui l'a publiée (chapitre 7).

**3. Le principe de l'escalier.** Règles et expressions régulières, puis statistique, puis
apprentissage automatique, puis plongements lexicaux, puis grands modèles de langue. **On ne monte
que si la mesure prouve que la marche précédente ne suffit pas.**

| Problème | Marche utilisée | Résultat |
|---|---|---|
| Douze écritures pour une nature de marché | deux fonctions SQL | six notions, quelques millisecondes |
| SIRET dans trois formats d'avis différents | une expression régulière | de 19 % à 61,3 % d'avis exploitables |
| Prix atypique | écart robuste à la médiane du groupe | 75,8 % de précision au seuil 4 |
| Relier deux sources sans identifiant commun | quatre critères empilés | de 0 % à 14,7 % de liens sûrs |
| **Monter à l'apprentissage automatique** | dix méthodes comparées à budget égal | **refusé** : aucun modèle ne dépasse la statistique |
| Chercher dans deux millions d'objets | mots clés, tous les mots puis au moins un mot | 8 ms de médiane, aucune question sans réponse |
| Afficher des comptages sur deux millions de lignes | calcul déplacé au chargement, dans une table | de 11,1 s à la demande à 0,43 ms |
| **Monter aux plongements lexicaux** | pas encore mesuré | **en attente** : l'extension est installée, aucune colonne vectorielle créée |

La dernière ligne est la plus importante du tableau, parce qu'elle montre que l'escalier n'est pas
un slogan : une marche identifiée et non franchie, avec le protocole qui déclenchera son
franchissement.

**4. Un signal n'est pas une accusation.** Tout marché signalé l'est comme une invitation à
vérifier. Un marché très spécialisé attire peu de candidats sans que personne n'ait rien à se
reprocher, et le service l'écrit à l'écran (chapitre 8).

**5. Refuser un outil demande plus d'arguments que l'adopter.** La question n'est jamais « cet outil
est-il bon » mais « qu'est-ce que je devrais écrire sans lui ».

| Outil | Verdict | Raison |
|---|---|---|
| DuckDB | **adopté** | lit le Parquet sur place, aucun serveur, agrégation en millisecondes |
| dbt | **adopté** | sans lui : un lanceur, des tests de données, une documentation, un graphe |
| Colima | **adopté** | conteneurs à la demande, sans licence d'entreprise |
| PostgreSQL et pgvector | **adopté** | plusieurs lecteurs, recherche plein texte française et vecteurs dans un seul moteur |
| Jinja2 et htmx | **adoptés** | un service, aucune compilation, des pages qui marchent sans JavaScript |
| Dagster | écarté pour l'instant | résout des dépendances entre étapes, qui n'existent pas encore |
| PySpark | écarté | une grappe pour 250 Mo coûte plus que le calcul |
| polars | écarté | une interface de plus, alors que le SQL sert déjà dans dbt |
| MinIO et le stockage objet | écarté | besoin non démontré, et gouvernance incertaine (chapitre 4) |
| Un moteur de recherche dédié | écarté | un service de plus à exploiter et à sécuriser, pour un besoin non mesuré |
| Jeux de données prêts à l'emploi | écartés | partir d'un jeu nettoyé supprimerait le problème à démontrer |

---

## 6.9 Ce que cette architecture ne sait pas faire

Une architecture se juge aussi sur ce qu'elle refuse de prétendre. Six limites sont connues et
mesurées.

**Elle ne tient pas sur plusieurs machines.** C'est volontaire, mais c'est une limite réelle :
l'écriture est faite pour un seul processus, et aucune réplication n'est prévue.

**Elle n'offre aucune garantie de disponibilité.** Une panne du VPS est une interruption de service.
Le chiffrage du chapitre 11 retient d'ailleurs, chez les fournisseurs comparés, des configurations
à une seule zone, précisément pour comparer à périmètre égal.

**Le démarrage du service prend de 11 à 27 secondes** selon l'état des caches de la base, réserve de
connexions, lexiques et préchauffage compris. C'est long, et cela a une conséquence concrète en
phase 9 : le délai de grâce du contrôle de santé du conteneur devra couvrir cette durée, sinon le
conteneur sera redémarré en boucle.

**Une recherche que personne n'a encore faite coûte environ 1,8 seconde sur une base froide**, et le
95e centile de la cascade de recherche atteint 4,8 secondes sur les neuf questions qui paient le
prix entier de la requête large. C'est sous le délai d'expiration du service, donc une attente et
non une erreur, mais c'est un point ouvert.

**La chaîne n'est pas incrémentale.** Chaque exécution reconstruit les trois couches. À environ six
secondes pour deux millions de lignes, le besoin ne s'est pas fait sentir ; il apparaîtra si le
volume croît d'un ordre de grandeur.

**L'espace d'administration n'est pas écrit.** C'est la seule pièce manquante du service, et elle
attend une décision de sécurité : comment il s'authentifie.

---

## 6.10 Les douze décisions, et où les lire

Chaque choix de ce chapitre est tracé dans une décision d'architecture datée, qui porte son
contexte, ses alternatives et ses conséquences. C'est la forme sous laquelle une architecture se
transmet.

| Décision | Ce qu'elle engage |
|---|---|
| 0001, socle technique | l'environnement, reproductible et jetable |
| 0002, DuckDB sur Parquet | pas de serveur avant le site |
| 0003, rapprochement par niveaux de confiance | un lien affiché porte toujours son degré de certitude |
| 0004, collecte traçable sans orchestrateur | manifeste versionné, donnée brute non versionnée |
| 0005, nettoyage en trois couches avec dbt | marquer plutôt que supprimer |
| 0006, détection par règles aux seuils mesurés | deux niveaux, jamais une accusation |
| 0007, rester sur les règles après comparaison à dix méthodes | la connaissance métier, pas la puissance statistique |
| 0008, PostgreSQL pour servir, DuckDB mesuré contre lui | un choix fait avant la mesure, puis confirmé par elle |
| 0009, un assistant qui cite ses sources | il refuse ce qu'il ne sait pas lire, plutôt que d'inventer |
| 0010, incertitude et validation hors échantillon | aucun pourcentage publié sans son incertitude |
| 0011, une API mesurée avant d'être jolie | quatre règles tirées de mesures, pas d'habitudes |
| 0012, un site rendu par le serveur, l'API sous un préfixe | un service, aucune compilation, des pages sans JavaScript |

Le dépôt compte par ailleurs 312 tests automatisés, dont vingt qui exécutent la vraie chaîne de
transformation sur un jeu fictif de quinze lignes dont chaque défaut est connu d'avance.

---

[^adr8]: ADR 0008, `docs/adr/0008-postgresql-pour-servir-la-recherche.md`. Mesures du 11 octobre
2026, `make bench-recherche`, agrégats dans `mesures/resultats/recherche-par-moteur.csv`. Les
latences dépendent de l'état des caches : ce qui est reproductible, et ce sur quoi la décision
repose, est l'ordre de grandeur et le classement, soit quelques millisecondes contre une centaine.

[^adr12]: ADR 0012, `docs/adr/0012-site-public.md`. Mesures du 22 octobre 2026, `make bench-site`,
agrégats dans `mesures/resultats/site-pages.csv`, `site-fragments.csv` et `site-resume.csv`.
