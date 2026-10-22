# Chapitre 4. Étude du marché et études de cas : qui utilise quoi, et à quel prix

> Brouillon. Les faits, les chiffres et les sources sont vérifiés ; la formulation reste à
> reprendre dans la voix de l'auteur.

Le chapitre précédent a montré le creux à combler. Celui-ci répond à une objection prévisible, et
légitime : une pile technique assemblée par un étudiant pour un mémoire, est-ce que cela ressemble
à ce que font les organisations qui ont des moyens ?

La réponse est donnée cas par cas, avec pour chaque outil retenu au moins une organisation nommée,
une source ouverte et lue, et un niveau de fiabilité explicite. Le chapitre dit aussi ce que
l'enquête **n'a pas** trouvé, car l'absence de retour d'expérience vérifiable sur un outil est une
information pour qui doit décider de l'adopter.

---

## 4.1 La méthode de l'enquête, et son échelle de fiabilité

Règle tenue d'un bout à l'autre : **aucun exemple sans source ouverte et lue.** Les cas qui n'ont
pas pu être confirmés à la source primaire ne sont pas cités comme des cas, ils sont regroupés en
fin de chapitre.

Toutes les sources ne se valent pas, et les confondre serait la principale façon de se tromper ici.
Six niveaux sont distingués, du plus solide au plus faible.

| Niveau | Ce que c'est | Ce qu'il vaut |
|---|---|---|
| Source officielle entreprise | blog d'ingénierie, dépôt de code, page officielle | solide, mais l'entreprise choisit ce qu'elle raconte |
| Publication scientifique | article évalué ou prépublication signée par ses ingénieurs | le plus solide, protocole décrit |
| Conférence | intervention publique d'un ingénieur, ou compte rendu fidèle | solide si la trace est accessible |
| Étude de cas éditeur | page rédigée par l'éditeur de l'outil avec son client | **déclaratif et commercial**, à lire comme tel |
| Page d'adoptants | liste publiée par le projet lui-même | faible, aucun détail vérifiable |
| Presse | article reprenant les propos d'une entreprise | dépend du soin du journaliste |

Cette distinction a un effet direct sur ce qui suit : les cas Dagster et Evidently, par exemple,
sont des études de cas d'éditeur. Ils sont cités, parce qu'ils décrivent des architectures précises
et nommées, mais jamais comme des preuves de performance.

Recherche documentaire menée le 19 septembre 2026. Le détail complet, avec chaque adresse et chaque
niveau de fiabilité, est dans `ressources/etudes-de-cas.md`.

---

## 4.2 Les outils retenus par ce projet, et qui les utilise déjà

| Outil du projet | Organisation | Ce qu'elle en fait | Fiabilité |
|---|---|---|---|
| **dbt** | BlaBlaCar | plus de 30 développeurs dbt, des centaines de modèles, environ 4 000 tables et 400 To | officielle |
| **dbt** | Doctolib | un graphe dbt unifié pour toutes les équipes, sur deux grappes Redshift | officielle |
| **DuckDB** | INSEE | diffusion du recensement en Parquet, DuckDB retenu « pour son efficacité ainsi que pour son universalité » | officielle |
| **DuckDB** | data.gouv.fr (DINUM) | chargement et export en Parquet dans les traitements de la plateforme | officielle, code public |
| **Parquet** | INSEE | format de diffusion des fichiers détail du recensement | officielle |
| **PostgreSQL et pgvector** | Instacart | recherche hybride lexicale et vectorielle dans un seul moteur | officielle |
| **PostgreSQL et pgvector** | Discourse | suggestions et recherche sémantique du logiciel de forum | officielle |
| **FastAPI** | Netflix | Dispatch, son outil libre de gestion d'incidents | officielle, code public |
| **FastAPI** | DINUM et INSEE | la passerelle d'IA de l'État et l'interface de codification de l'activité | officielle, code public |
| **Prometheus et Grafana** | SoundCloud, DigitalOcean | surveillance de « hundreds of services » ; remplacement d'OpenTSDB et Graphite | officielle |
| **Un serveur, pile compacte** | Stack Overflow | 209,4 millions de requêtes HTTP par jour sur 11 serveurs web et 4 bases | officielle |

Trois de ces cas méritent d'être développés, parce qu'ils ne confirment pas seulement un choix :
ils l'ont orienté.

**Instacart, ou la preuve que PostgreSQL suffit à chercher.** L'entreprise a migré sa recherche
plein texte d'Elasticsearch vers PostgreSQL, puis remplacé son service de voisinage approché FAISS
par pgvector, pour faire de la recherche hybride dans un seul moteur. Deux chiffres sont publiés :
un modèle de données normalisé qui réduit la charge d'écriture d'un facteur dix par rapport à
Elasticsearch, et un test A/B en production montrant **6 % de recherches sans résultat en
moins**[^instacart]. C'est le précédent qui autorise le chapitre 9 à ne pas installer de moteur de
recherche dédié.

**BlaBlaCar, ou le choix de dbt-core plutôt que dbt Cloud.** L'équipe a adopté la version libre et
l'orchestre elle-même, la version hébergée ayant été jugée sans valeur ajoutée suffisante en 2022 et
trop chère[^blablacar]. C'est exactement l'arbitrage que ce mémoire défend, fait par une équipe
data de cinquante personnes sur 400 To.

**Stack Overflow, ou la mesure de ce qu'une machine encaisse.** En 2016, le site servait 209,4
millions de requêtes HTTP et 66,3 millions de pages par jour, et son architecte écrivait : « We can
run the entire Q&A network off of a single application pool on a single server », la redondance
étant conservée par choix et non par nécessité[^stackoverflow]. Ce cas est l'argument de fond du
chapitre 11 : pour une charge connue et modeste, la machine unique n'est pas un pis-aller.

---

## 4.3 Le secteur public, la référence la plus proche

Ce projet traite de données publiques françaises ; les administrations qui construisent des
plateformes de données sont donc ses voisins les plus directs.

**La Fédération Wallonie-Bruxelles** a bâti sa plateforme de données sur Dagster pour
l'orchestration, dbt pour la transformation et DuckDB pour le traitement, déployés sur Docker Swarm
avec une intégration continue GitLab. L'administration compte plus de 7 000 agents et sert
4,5 millions de citoyens ; le délai de livraison des pipelines aurait été divisé par deux, et un de
ses ingénieurs résume l'intérêt de la pile ainsi : « No vendor lock-in means that 90% of our code
can be re-used anywhere »[^fwb]. **C'est le cas le plus proche de ce projet qui ait été trouvé** :
secteur public francophone, même pile, déploiement conteneurisé sans service géré. Il s'agit
toutefois d'une étude de cas publiée par l'éditeur de Dagster, donc d'un document commercial : les
chiffres de gain sont déclaratifs.

**data.gouv.fr** publie ses traitements en code ouvert. Vérification faite en clonant le dépôt le
19 septembre 2026 : 93 fichiers Python y importent Airflow, certains traitements utilisent DuckDB
pour produire des fichiers Parquet, et le stockage objet de production est un S3
d'OVHcloud[^datagouv]. Une administration française qui publie des données ouvertes les traite donc
avec les mêmes briques, et héberge chez un fournisseur européen.

**L'INSEE** diffuse le recensement en Parquet et publie un guide qui retient DuckDB « pour son
efficacité ainsi que pour son universalité » en Python, R et JavaScript[^insee]. Son Datalab SSP
Cloud, instance publique du projet libre Onyxia, stocke ses fichiers dans MinIO. Son interface de
codification automatique de l'activité principale est écrite en FastAPI et récupère ses modèles
depuis MLflow[^insee-ape].

**La DINUM** opère Albert, instance française de la passerelle libre OpenGateLLM : plus de 70
projets publics et plus de 100 000 requêtes par semaine d'après la page officielle, avec un pilote
France Services réunissant 80 conseillers dans 7 départements et plus d'un million d'euros investis
par l'État en 2024 d'après la presse[^albert]. Le code est une interface FastAPI instrumentée par
Prometheus, et une décision d'architecture du 30 janvier 2026 explique le choix d'Elasticsearch
plutôt que Qdrant pour offrir trois modes de recherche, dont une recherche hybride par fusion des
rangs réciproques. Ce document est un modèle du genre, et il a inspiré la forme des décisions
d'architecture de ce projet.

**LLaMandement** est le précédent public français le plus utile à la thèse de ce mémoire. Des
équipes de la DGFiP, du secrétariat général du Gouvernement et de la DINUM ont affiné un modèle
LLaMA de 13 milliards de paramètres sur 15 397 paires amendement et résumé, **le modèle de 70
milliards ayant été écarté pour des raisons d'efficacité et de sobriété**. Résultat : une note de
15,1 sur 20 attribuée par des rédacteurs fiscaux, contre 16,5 pour les résumés humains, et environ
5 400 amendements traités au projet de loi de finances 2024 en première lecture, dont 94 % attribués
automatiquement en moins de dix minutes[^llamandement]. Une administration française a donc choisi
publiquement le modèle le plus petit qui suffise, et l'a mesuré.

**ALICE**, enfin, montre ce que la détection automatique sur des marchés publics produit à grande
échelle. Cet outil de la Contrôlerie générale de l'Union brésilienne analyse chaque jour les
portails de marchés et le journal officiel avec une quarantaine de typologies de risque, et envoie
ses alertes à plus de 500 utilisateurs. En 2023, plus de 190 000 procédures analysées et
2,08 milliards de réais annulés ou suspendus ; d'après l'OCDE, l'audit préventif passe de plus de
400 jours à 8 jours[^alice]. Deux enseignements pour le chapitre 8 : des indicateurs de risque
automatiques produisent un effet mesurable, et **l'humain reste le décideur final**, l'outil ne
faisant qu'orienter son attention.

---

## 4.4 Les outils examinés puis écartés, et les cas qui ont pesé

Un mémoire qui ne citerait que des cas favorables à ses choix ne démontrerait rien. Quatre outils du
catalogue de départ ont été écartés, et trois l'ont été malgré des cas d'usage solides.

**LightGBM, écarté malgré deux très bons cas.** Chez OTTO, le classement des résultats de recherche
en production repose sur un modèle LightGBM LambdaMART, référence que l'entreprise a comparée à des
réseaux de neurones lors d'un test A/B en ligne de huit semaines[^otto]. Chez Airbnb, le
remplacement d'une fonction de score écrite à la main par un modèle d'arbres de gradient a produit
« one of the largest step improvements in homes bookings in Airbnb's history »[^airbnb-search]. Ces
deux cas établissent que la méthode est sérieuse. Le chapitre 8 l'écarte pourtant, et pour une
raison qui n'a rien à voir avec sa qualité : **ces deux entreprises disposent d'une étiquette**, le
clic et la réservation. Ce projet n'en a pas, et aucune mesure ne peut remplacer une étiquette
absente.

**MLflow, écarté faute de besoin.** L'enquête n'a trouvé aucun retour d'expérience d'une grande
entreprise nommée décrivant MLflow en production, ouvert et lu dans le temps de la recherche. Le
seul cas vérifié est celui de l'INSEE, dans le code de son interface de codification, sans
confirmation publique de la date ni du périmètre de mise en production. Un cas intéressant va même
dans l'autre sens : la fintech Wayflyer a d'abord adopté des fiches de modèle avec Evidently avant
des outils plus lourds comme MLflow, jugés plus coûteux en infrastructure[^wayflyer]. Comme le
chapitre 8 conclut à l'absence de modèle entraîné, la question ne se pose plus : il n'y a pas
d'expérience à suivre.

**MinIO, écarté sur un risque de gouvernance, et c'est le cas le plus instructif.** Le dépôt libre
de MinIO affiche depuis le 25 avril 2026 « THIS REPOSITORY IS NO LONGER MAINTAINED » et renvoie vers
les éditions commerciales AIStor. Le retrait s'est fait par étapes : console d'administration
réduite en février 2025, fin des binaires et images communautaires en octobre 2025, passage en mode
maintenance le 3 décembre 2025, archivage en avril 2026. AIStor est facturé au minimum 96 000
dollars par an d'après la presse spécialisée[^minio]. Un cabinet français, Datakhi, documente la
migration d'un lac de données d'un éditeur B2B de MinIO vers Garage, avec un mois de fonctionnement
en parallèle, et publie ses mesures sur une grappe de trois nœuds : lectures de petits fichiers
6,1 fois plus rapides, écritures concurrentes 9,4 fois plus rapides, 5 à 6 fois moins de
processeur[^garage].

**La leçon a été appliquée, et elle a changé l'architecture.** Ce projet n'utilise aucun stockage
objet : la couche brute est faite de fichiers Parquet sur disque, et la publication va directement
vers PostgreSQL. Le besoin ne le justifiait pas, et le cas MinIO montre le risque propre aux
logiciels dits « open core » portés par un éditeur unique. La règle retenue, écrite au chapitre 6,
est que la pérennité de la gouvernance d'une dépendance compte autant que ses performances.

**llama.cpp, écarté faute de besoin démontré.** Aucun cas vérifiable d'usage en production dans une
grande organisation n'a été trouvé ; les contenus disponibles sont des guides et des comparatifs
génériques. Le chapitre 9 explique pourquoi l'assistant de ce projet ne contient aucun modèle de
langue, ce qui rend la question théorique. L'argument en faveur d'un modèle local, si le besoin
apparaissait, est fourni par un échec : en avril 2023, des salariés de Samsung ont soumis du code
source interne à ChatGPT, et l'entreprise a interdit les outils d'IA générative sur ses appareils et
réseaux à partir du 1er mai 2023[^samsung].

---

## 4.5 Ce que l'alternative payante coûte, chiffré par ceux qui en sont sortis

La thèse de ce mémoire porte sur l'argent. Elle n'est pas isolée : plusieurs organisations ont
publié le chiffrage de leur sortie d'une offre gérée.

| Organisation | Ce qui a été remplacé | Résultat publié | Fiabilité |
|---|---|---|---|
| **37signals** | AWS, calcul puis stockage | facture AWS de 3 201 564 dollars en 2022 ; environ 700 000 dollars de serveurs Dell ; plus de 10 millions de dollars d'économies projetées sur 5 ans | officielle (son directeur technique) |
| **Checkr** | GPT-4 par un Llama-3 8B affiné | environ 12 000 dollars par mois ramenés à environ 800 ; précision de 97 % contre 88 % ; latence de 0,5 s contre 7 à 15 s, sur 1,5 million de vérifications par mois | presse, propos de l'entreprise |
| **Definite** | Snowflake par DuckDB auto-hébergé | plus de 70 % d'économie, sur l'hypothèse de 1 To et 16 vCPU | officielle, **conflit d'intérêts** |
| **Airbnb** | Hive et Tez par Spark 3 et Iceberg | plus de 50 % de ressources de calcul économisées, 40 % de temps d'exécution en moins | officielle |
| **Okta** | prétraitement avant Snowflake, par DuckDB | facture Snowflake d'environ 2 000 dollars par jour avant le prétraitement | conférence, **via sources secondaires** |

Deux de ces lignes portent une réserve, et elle doit être lue : Definite vend un produit construit
sur DuckDB, donc son chiffrage sert aussi son commerce ; le cas Okta n'a pu être vérifié que par des
comptes rendus tiers, la page de la conférence d'origine renvoyant une erreur. Les citer sans ces
réserves serait reproduire exactement le défaut que le chapitre 11 reproche aux comparateurs de
prix.

Le cas de 37signals est le plus détaillé. Le rapatriement a commencé par le calcul, annoncé en
octobre 2022 avec environ 7 millions de dollars d'économies prévues sur cinq ans, puis a touché le
stockage : une facture S3 d'environ 1,5 million de dollars par an remplacée par 18 pétaoctets de
baies Pure Storage, pour environ 1,5 million d'achat et moins de 200 000 dollars par an
d'exploitation, AWS ayant renoncé à 250 000 dollars de frais de sortie[^37signals].

**Ce que ces cas prouvent, et ce qu'ils ne prouvent pas.** Ils prouvent que le rapport de coût entre
une offre gérée et une infrastructure possédée peut être très défavorable à la première, pour une
charge stable et prévisible. Ils ne prouvent pas que ce soit toujours vrai : 37signals a une équipe
d'exploitation, et le chapitre 11 montre que le temps d'ingénierie ne figure dans aucune de ces
colonnes.

---

## 4.6 Ce que l'enquête n'a pas trouvé, et pourquoi c'est un résultat

Les éléments suivants ont été cherchés et n'ont pas été confirmés par une source primaire ouverte et
lue. Ils sont listés ici plutôt que tus, parce qu'un lecteur qui doit décider a besoin de savoir où
l'information manque.

| Ce qui manquait | Conséquence pour ce mémoire |
|---|---|
| Aucune entreprise nommée décrivant MLflow en production | l'outil est écarté sans contre-exemple à opposer |
| Aucune entreprise française nommée utilisant explicitement les termes bronze, argent et or | l'architecture en couches est décrite d'après sa définition d'origine, publiée par Databricks, et non d'après un cas |
| Aucun cas vérifiable de llama.cpp en production | pas de précédent sur lequel s'appuyer, si un modèle local devenait nécessaire |
| LightGBM chez des entreprises françaises souvent citées | les deux cas retenus sont étrangers, OTTO et Airbnb |
| Les chiffres de DOZORRO, l'IA de détection de risques ukrainienne | cas non cité, alors qu'il aurait été le plus proche d'ALICE |
| « 80 % d'économies de stockage » attribués à Instacart | le texte d'origine dit « substantial savings », sans pourcentage : le chiffre est écarté |

La dernière ligne est la plus parlante. Un pourcentage précis circulait dans des résumés de
deuxième main ; l'article d'origine ne le contient pas. **Un chiffre qui s'ajoute en circulant est le
symptôme exact du problème que ce mémoire traite sur les données publiques**, et il se traite de la
même façon : en ouvrant la source.

---

[^instacart]: Ankit Mittal et al., « How Instacart Built a Modern Search Infrastructure on
Postgres », tech-at-instacart, 28 mai 2025,
https://tech.instacart.com/how-instacart-built-a-modern-search-infrastructure-on-postgres-c528fa601d54

[^blablacar]: Tushar Bhasin, « Scaling Success: dbt at BlaBlaCar », BlaBlaCar Medium, 18 octobre
2024, https://medium.com/blablacar/scaling-success-dbt-at-blablacar-545dd9e9844a

[^stackoverflow]: Nick Craver, « Stack Overflow: The Architecture, 2016 Edition », 17 février 2016,
https://nickcraver.com/blog/2016/02/17/stack-overflow-the-architecture-2016-edition/

[^fwb]: Dagster, « Belgian Government Transforms Data Platform with Dagster », 1er juillet 2025,
https://dagster.io/customers/federation-wallonie-bruxelles-case-study Étude de cas éditeur :
les gains annoncés sont déclaratifs.

[^datagouv]: Dépôt GitHub `datagouv/datagouvfr_data_pipelines`,
https://github.com/datagouv/datagouvfr_data_pipelines Comptage propre, dépôt cloné le
19 septembre 2026.

[^insee]: Dépôt officiel InseeFrLab, https://github.com/InseeFrLab/exemples-recensement-parquet ;
guide associé sur le blog SSPHub, https://ssphub.fr/post/parquetrp/ ; INSEE, Courrier des
statistiques n° 9, juin 2023, article d'Alexis Dondon et Pierre Lamarche sur les formats de données.

[^insee-ape]: https://github.com/InseeFrLab/codif-ape-API ; documentation du SSP Cloud,
https://docs.sspcloud.fr/content/storage.html La date et le périmètre de mise en production du
modèle ne sont pas confirmés par une source publiée.

[^albert]: https://ia.numerique.gouv.fr/outils-ia/albert-api/ ;
https://github.com/etalab-ia/OpenGateLLM ; décision d'architecture du 30 janvier 2026 dans le même
dépôt ; chiffres du pilote : Journal du Net, 27 janvier 2025.

[^llamandement]: Équipes DGFiP, SGG et DINUM, « LLaMandement: Large Language Models for
Summarization of French Legislative Proposals », arXiv 2401.16182,
https://arxiv.org/abs/2401.16182

[^alice]: Contrôlerie générale de l'Union, https://www.gov.br/cgu/pt-br/assuntos/auditoria-e-fiscalizacao/alice ;
OCDS Observatory of Public Sector Innovation de l'OCDE,
https://oecd-opsi.org/innovations/robot-alice-bid-contract-and-notice-analyser/

[^otto]: Yunus Lutz, Timo Wilm, Philipp Duwe, « Industry Insights from Comparing Deep Learning and
GBDT Models for E-Commerce Learning-to-Rank », RecSys 2025, arXiv 2507.20753,
https://arxiv.org/abs/2507.20753

[^airbnb-search]: Malay Haldar et al., « Applying Deep Learning To Airbnb Search », KDD 2019,
https://arxiv.org/abs/1810.09591 La bibliothèque exacte d'arbres de gradient n'est pas précisée
par l'article.

[^wayflyer]: Evidently, « An MLOps story: how Wayflyer creates ML model cards », 3 avril 2023,
https://www.evidentlyai.com/blog/how-wayflyer-creates-ml-model-cards Étude de cas éditeur.

[^minio]: https://github.com/minio/minio ; https://github.com/minio/minio/issues/21714 ;
Blocks and Files, 19 juin 2025,
https://blocksandfiles.com/2025/06/19/minio-removes-management-features-from-basic-community-edition-object-storage-code/
Les dates exactes de l'arrêt des images sont issues de sources secondaires ; l'archivage du dépôt a
été constaté directement.

[^garage]: Datakhi, « From MinIO to Garage: Benchmark, Migration and Production Feedback »,
https://datakhi.fr/en/blog/garage-migration-production-retour-experience/ Retour d'expérience
signé par le prestataire, client anonymisé, volume modeste (environ 2 Go).

[^samsung]: TechCrunch, 2 mai 2023,
https://techcrunch.com/2023/05/02/samsung-bans-use-of-generative-ai-tools-like-chatgpt-after-april-internal-data-leak/

[^37signals]: David Heinemeier Hansson, « Why we're leaving the cloud », 19 octobre 2022 ;
« Our cloud spend in 2022 », 13 janvier 2023, https://dev.37signals.com/our-cloud-spend-in-2022/ ;
« Our cloud-exit savings will now top ten million over five years », 17 octobre 2024 ;
The Register, 9 mai 2025, pour le volet stockage.
