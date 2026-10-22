# Chapitre 5. Histoire des pratiques : d'où viennent ces outils, et pourquoi

> Brouillon. Les faits, les dates et les sources sont vérifiés ; la formulation reste à reprendre
> dans la voix de l'auteur.

Un mémoire d'ingénierie peut se passer d'histoire. Celui-ci ne le peut pas, parce que sa thèse est
un refus : refuser le cluster, refuser le service géré, refuser le grand modèle de langue. Or **on
ne peut pas refuser sérieusement un outil sans savoir quel problème il a été créé pour résoudre.**
Chaque marche de l'escalier décrit au chapitre 6 existe parce qu'une pratique antérieure avait
rencontré une limite mesurée. Connaître cette limite est la seule façon de savoir si on l'a
soi-même rencontrée.

Les quatre frises qui suivent sont volontairement resserrées sur ce qui éclaire un choix du projet.
Chaque entrée porte sa source ; celles qui n'ont pu être vérifiées que par une source secondaire
sont signalées comme telles.

---

## 5.1 Le texte : de la règle à l'attention, et ce que le projet garde de chaque étape

| Date | Étape | Le problème qu'elle résout |
|---|---|---|
| 1951 | Kleene, formalisme des événements réguliers | décrire précisément les motifs qu'un automate fini reconnaît |
| 1966 | Weizenbaum, ELIZA | aucun : il **montre** qu'une illusion de dialogue s'obtient facilement, par mots-clés et réécriture |
| 1968 | Thompson, recherche d'expression régulière | le temps exponentiel : la simulation parallèle de l'automate rend la recherche linéaire |
| 1973 | grep, Unix V4 | chercher un motif dans des fichiers trop gros pour un éditeur |
| 1965 à 1980 | systèmes experts (MYCIN, environ 600 règles) | coder une expertise. Leur déclin vient du **goulot d'acquisition** : des règles écrites à la main, coûteuses, qui généralisent mal |
| 1972 | Spärck Jones, pondération par la rareté | la spécificité d'un terme se mesure statistiquement, sans analyse du sens |
| 1994 | Robertson et al., BM25 | la fréquence brute d'un terme surévalue les longs documents : saturation et normalisation par la longueur |
| 1997 | Hochreiter et Schmidhuber, LSTM | la disparition du gradient dans les réseaux récurrents |
| 2013 | Mikolov et al., word2vec | la similarité de sens devient calculable, ce que le sac de mots interdisait |
| 2017 | Vaswani et al., Transformer | les récurrences ne se parallélisent pas et portent mal le contexte long |
| 2018 | Devlin et al., BERT | un même modèle préentraîné atteint l'état de l'art sur de nombreuses tâches |
| 2019 | Reimers et Gurevych, Sentence-BERT | comparer 10 000 phrases passait d'environ 65 heures à environ 5 secondes |
| 2019 | Martin et al., CamemBERT | un modèle français d'état de l'art, et un corpus de 4 Go suffit face à plus de 130 Go |
| 2020 | Lewis et al., génération augmentée par récupération | mettre à jour des connaissances sans réentraîner, et inventer moins |
| 2022 | Frantar et al., GPTQ | 3 ou 4 bits par poids : les grands modèles tiennent sur du matériel modeste |
| 2023 | llama.cpp, puis le format GGUF | l'inférence sur un processeur ordinaire, sans GPU ni pile Python |
| 2023 | Mistral 7B sous licence Apache 2.0, phi-1 et « Textbooks Are All You Need » | un petit modèle bien entraîné rivalise avec de plus grands |

Sources et dates exactes dans `ressources/histoire-sources-cas.md`, section 1.a. Trois entrées
reposent sur une source secondaire et sont citées avec cette réserve : la référence de Kleene, la
date de grep, et celle de la mise à disposition de ChatGPT[^reserves-texte].

**Ce que le projet garde de cette frise.** Sa recherche plein texte est une descendante directe de
1972 et de 1994 : PostgreSQL pondère les termes par leur rareté et normalise par la longueur du
document. Son racineur et sa liste de mots vides prolongent la philosophie des petits outils
d'Unix. Son assistant, lui, est un système à base de règles, et **ELIZA est la raison pour laquelle
il refuse de feindre la compréhension** : il annonce ce qu'il a compris, cite ses sources, et répond
« je ne sais pas » quand aucune règle ne s'applique (chapitre 9).

**Ce qu'il n'a pas pris, et où en est la marche suivante.** L'extension `pgvector` est installée,
et aucune colonne vectorielle n'est créée. La marche de 2013 à 2019, celle des plongements, est
donc identifiée et **non franchie**, parce qu'aucune mesure n'a montré que la recherche lexicale ne
suffisait pas. Le chapitre 9 publie le protocole qui déclenchera ce franchissement, le jour où la
mesure l'exigera.

---

## 5.2 Le data engineering : un balancier, et non une progression

| Date | Étape | Le problème qu'elle résout |
|---|---|---|
| 1992 | Inmon, l'entrepôt de données | isoler l'analyse des bases opérationnelles |
| 1996 | Kimball, modélisation dimensionnelle | rendre l'entrepôt lisible et rapide pour les métiers |
| 2004 | Dean et Ghemawat, MapReduce | paralléliser des traitements massifs sur des machines banales, avec tolérance aux pannes |
| 2006 | Hadoop 0.1.0 | le même, hors de Google |
| 2010 | Spark | MapReduce relit le disque à chaque étape, ce qui tue l'analyse interactive et le ML |
| 2012 | Redshift, puis BigQuery | l'entrepôt sans infrastructure à administrer |
| 2013 | Parquet (Cloudera et Twitter) | une requête analytique ne lit que les colonnes utiles |
| 2015 | Snowflake | séparer le stockage du calcul, et payer le calcul à la demande |
| 2015 | Airflow (Airbnb) | des workflows définis en code, planifiés et supervisés |
| 2016 | dbt | les transformations SQL deviennent du code versionné, testé, documenté |
| années 2010 | passage de l'ETL à l'ELT | le calcul devient élastique dans l'entrepôt : charger d'abord, transformer ensuite |
| 2017 à 2019 | Hudi, Iceberg, Delta Lake | mises à jour et transactions sur un lac de données, sans tout retraiter |
| 2021 | Armbrust et al., lakehouse | unifier lac et entrepôt sur des formats ouverts, moins de copies, moins de dépendance |
| 2019, puis 1.0 en 2024 | DuckDB | l'analytique colonnaire **dans le processus**, sans serveur |

**C'est la frise la plus utile à la thèse de ce mémoire, et pour une raison qui n'est pas une
opinion.** De 1992 à 2015, le mouvement va vers le toujours plus distribué, parce qu'une machine ne
suffisait plus. Depuis 2019, une partie du mouvement revient vers la machine unique, non par
nostalgie mais parce que **la machine a grossi plus vite que les jeux de données ordinaires.**

Ce projet en est un cas, et il le mesure : 3,28 millions de lignes sur 66 colonnes, agrégées par
huit mesures de qualité enchaînées en environ 1,3 seconde, sur un ordinateur portable de 16 Go, sans
aucun serveur démarré[^mesure-duckdb]. En 2010, le même travail aurait justifié une grappe de
machines ; en 2026, il justifie un fichier Parquet de 247,6 Mo et une bibliothèque chargée dans le
processus.

**Ce que le projet garde** : Parquet pour la couche brute, dbt pour les transformations, le
découpage en couches bronze, argent et or dont la définition de référence est publiée par
Databricks[^medaillon], et le principe de l'ELT. **Ce qu'il refuse** : Spark, parce qu'une grappe
pour 250 Mo coûte plus que le calcul, et un orchestrateur pour l'instant, parce que les trois
sources sont indépendantes (chapitre 6).

---

## 5.3 Le ML et le MLOps : le cadre de 1969 est encore celui du projet

| Date | Étape | Le problème qu'elle résout |
|---|---|---|
| 1969 | Fellegi et Sunter, théorie du rapprochement d'enregistrements | décider si deux enregistrements désignent la même entité : **apparié, non apparié, à revoir** |
| 2008 | Liu, Ting et Zhou, Isolation Forest | isoler les anomalies au lieu de modéliser la normalité, sans étiquettes |
| 2010 | scikit-learn, première version publique | une interface unique et documentée pour le ML en Python |
| 2015 | Sculley et al., dette technique cachée des systèmes de ML | le coût d'un système d'apprentissage est **autour** du modèle, pas dans le modèle |
| 2016 et 2017 | XGBoost, puis LightGBM | le boosting d'arbres passe à l'échelle et domine les données tabulaires |
| 2017 | Lundberg et Lee, valeurs de Shapley appliquées | justifier un score auprès d'un humain |
| 2018 | MLflow | suivre les expériences, reproduire un résultat, déployer un modèle |

**L'ancrage le plus fort de ce projet dans cette frise date de 1969.** Fellegi et Sunter n'ont pas
proposé un classement binaire mais **trois issues**, dont une « à revoir » confiée à un humain. Le
rapprochement du BOAMP et des DECP décrit au chapitre 7 reprend cette structure exactement : une
confiance haute qui s'affiche, une confiance moyenne qui s'affiche avec sa mention de doute, et une
confiance faible qui ne s'affiche jamais. Cinquante-sept ans plus tard, la bonne réponse à un
appariement incertain reste la même : ne pas trancher à la place du lecteur.

La leçon de Sculley est la deuxième que le projet applique directement. Si l'essentiel du coût d'un
système d'apprentissage se trouve autour du modèle, alors un projet qui n'a pas besoin de modèle
économise bien plus que le temps d'entraînement : il économise la surveillance de dérive, le
registre de modèles, le réentraînement et la reproductibilité des expériences. Le chapitre 8 montre
que cette économie a été **mesurée** et non supposée.

Isolation Forest, enfin, est la méthode que le chapitre 8 compare point par point à une règle
écrite en SQL. Le résultat est publié, y compris dans ce qu'il a d'inattendu.

---

## 5.4 Le déploiement : le même balancier, vingt ans plus tard

| Date | Étape | Le problème qu'elle résout |
|---|---|---|
| avant 1999 | serveurs physiques dédiés, « islands of computing capacity » | aucun : c'est le problème, des serveurs sous-utilisés et difficiles à gérer |
| 1998 à 1999 | VMware, puis Workstation 1.0 | plusieurs systèmes sur une même machine x86 |
| 2003 | Barham et al., Xen | jusqu'à 100 machines virtuelles par serveur pour quelques pour cent de surcoût |
| 2006 | Amazon EC2 en bêta | louer des serveurs à l'usage, sans acheter de matériel à l'avance |
| 2013 | Docker présenté à PyCon US | une image identique du poste au serveur : fin du « ça marche chez moi » |
| 2014 à 2015 | Kubernetes, puis 1.0 et la CNCF | ordonnancer des conteneurs sur une flotte, avec santé et réplication |
| 2022 à 2024 | sortie du cloud de 37signals | pour une charge **stable et prévisible**, le cloud coûte plus cher que des serveurs possédés |

La dernière ligne de cette frise est une facture publiée : 3 201 564 dollars d'AWS en 2022, rendus
publics en janvier 2023 pour étayer la décision[^facture-37signals]. C'est le seul cas de cette
frise où l'argument est un chiffre, et c'est pour cette raison qu'il pèse.

**Ce que le projet garde** : Docker, pour que l'image du Mac et celle du VPS soient la même.
**Ce qu'il refuse** : Kubernetes, parce qu'il ordonnance des conteneurs sur une flotte et que le
projet a une machine. Le critère qui changerait cette décision est écrit au chapitre 6, et il est
vérifiable : le jour où la charge mesurée dépasse ce qu'une machine encaisse, ou le jour où une
indisponibilité devient inacceptable pour l'usage.

---

## 5.5 Les échecs qui ont changé les pratiques, et ce que le projet en a tiré

Les frises racontent les réussites. Les pratiques d'ingénierie, elles, sont surtout faites de
cicatrices. Chaque ligne du tableau suivant est un échec documenté par une source primaire, et une
règle appliquée dans ce dépôt.

| Échec | Ce qui s'est passé | Ce que le projet en fait |
|---|---|---|
| **Public Health England, 2020** | 15 841 cas positifs perdus, l'ancien format de tableur étant limité à 65 536 lignes | **aucun tableur dans la chaîne** : Parquet, DuckDB, PostgreSQL ; tests de réconciliation du nombre de lignes source et cible |
| **GitLab.com, 2017** | base de production supprimée, et « out of five backup/replication techniques deployed none are working reliably » ; environ 6 heures de données perdues | sauvegardes copiées hors du VPS et **restauration testée**, pas seulement configurée (phase 9) |
| **Knight Capital, 2012** | code déployé à la main sur 8 serveurs, un oublié, du code mort réactivé ; plus de 460 millions de dollars perdus en 45 minutes | **déploiement entièrement automatisé**, images versionnées, aucune étape manuelle |
| **Louvois, 2011 à 2015** | environ 200 contrôles de cohérence jugés bloquants ont été neutralisés ; 358 millions d'euros de trop-versés | **ne jamais désactiver un contrôle pour faire passer des données** : les tests de données bloquent, et la sévérité correspond à la promesse de la couche (chapitre 7) |
| **SIRHEN et ONP** | 378 puis plus de 400 millions d'euros pour 2 % des personnels gérés ; 346 millions pour l'ONP | **livraisons petites et incrémentales**, une phase produit du code, une section et des mesures |
| **Zillow Offers, 2021** | fermeture de l'activité, 304 millions de dollars de dépréciation, le modèle de prix ayant surévalué les achats | **un score oriente, il ne décide pas** : « à examiner », jamais « irrégulier » (chapitre 8) |
| **Google Flu Trends, 2014** | surestimation 100 semaines sur 108, par « big data hubris » et dérive de l'outil de mesure | **validation hors échantillon et dans le temps**, publiée avec son incertitude (chapitre 11) |
| **Amazon, outil de recrutement, 2018** | le modèle pénalisait les CV contenant « women's », reproduisant un biais historique | **audit des variables servant de substitut** : taille d'entreprise, région, PME contre grands groupes |
| **Moffatt contre Air Canada, 2024** | la compagnie soutient que son agent conversationnel est « a separate legal entity responsible for its own actions » ; le tribunal répond « This is a remarkable submission » | **l'éditeur répond des réponses de son assistant** : sources citées, refus en l'absence de source, jeu d'évaluation en intégration continue |
| **NYC MyCity, 2024** | l'agent municipal affirmait que des employeurs pouvaient prélever une part des pourboires, contrairement à la loi | domaine réglementaire : **sources officielles uniquement**, et « je ne sais pas » assumé |
| **CrowdStrike, 2024** | 21 champs fournis contre 20 attendus, lecture mémoire hors limites ; 8,5 millions de machines touchées | **validation du schéma des entrées** et déploiement progressif, même sur une seule machine |
| **Log4Shell, 2021 ; Codecov, 2021 ; xz-utils, 2024** | exécution de code à distance notée 10,0 ; exfiltration de secrets d'intégration continue ; porte dérobée repérée parce que les connexions passaient de 0,3 à 0,8 seconde | inventaire des dépendances, analyse automatique en intégration, versions épinglées. Et : **l'observabilité détecte aussi des anomalies de sécurité** |
| **MinIO, 2025 à 2026** | retrait progressif de l'édition libre, dépôt archivé, édition commerciale à partir de 96 000 dollars par an | **la gouvernance d'une dépendance compte autant que ses performances** (chapitre 4) |

Sources complètes, avec les réserves de vérification, dans `ressources/histoire-sources-cas.md`,
section 4. Deux précisions : le montant de Knight Capital est celui de l'ordonnance du régulateur
américain, « over $460 million », et non celui de 440 millions souvent repris par la presse ; les
48 000 contacts non prévenus dans l'affaire anglaise viennent d'un article de presse technique et
non du communiqué officiel[^reserves-echecs].

---

## 5.6 Ce que l'histoire enseigne, et qui tient en une règle

Trois constats se dégagent, et ils fondent la méthode du reste du mémoire.

**Chaque outil répond à une limite mesurée du précédent.** MapReduce répond à ce qu'une machine ne
tenait plus. Spark répond à ce que MapReduce relisait le disque. dbt répond à ce qu'Airflow
exécutait du SQL sans le tester. Prendre la marche du haut sans avoir rencontré la limite du bas,
c'est payer le prix sans avoir le problème.

**Les deux balanciers ont tourné dans le même sens, et pour la même raison.** Le data engineering
revient vers la machine unique depuis 2019 ; le déploiement revient vers les serveurs possédés
depuis 2022. Dans les deux cas, parce que le matériel a progressé plus vite que la charge de la
plupart des organisations. Ce mémoire ne propose donc pas une position marginale : il documente un
mouvement en cours, et il le chiffre sur un cas réel.

**Les échecs coûteux ne viennent presque jamais du modèle.** Un tableur, un déploiement manuel, des
sauvegardes jamais testées, des contrôles désactivés, un agent conversationnel sans source. La
leçon de Sculley vaut pour tout un système d'information, et pas seulement pour l'apprentissage
automatique : le coût est autour.

D'où la règle unique que les chapitres suivants appliquent, et qu'ils appliquent y compris contre
les préférences de leur auteur : **on ne monte une marche que si une mesure montre que la
précédente ne suffit pas, et le résultat est publié même quand il déplaît.**

---

[^reserves-texte]: Le mémo de Kleene (RM-704, 1951) n'est confirmé que par une source
encyclopédique, le site de l'éditeur d'origine étant inaccessible. La date de grep est confirmée
pour « novembre 1973, Unix V4 », alors que plusieurs sources citent 1974. La mise à disposition de
ChatGPT au 30 novembre 2022 n'a pu être confirmée que par la même voie, le site de l'éditeur
bloquant les clients automatisés. Références complètes et URL testées dans
`ressources/histoire-sources-cas.md`, sections 1.a et 2.

[^mesure-duckdb]: Mesure propre du 20 septembre 2026, MacBook M2 Pro, Python 3.12.9, DuckDB 1.5.5.
Le comptage de 3,28 millions de lignes prend 0,009 seconde, Parquet rangeant le nombre de lignes
dans ses métadonnées ; les agrégations réelles vont de 0,01 à 0,7 seconde, et une comparaison ligne
à ligne sur les 66 colonnes prend 7,3 secondes. Ces ordres de grandeur sont cités séparément, sans
quoi la mesure paraîtrait truquée. Voir l'ADR 0002.

[^medaillon]: Databricks, « What is Medallion Architecture? »,
https://www.databricks.com/blog/what-is-medallion-architecture Le terme est proposé par cet
éditeur. Aucun retour d'expérience d'une entreprise française nommée employant explicitement ces
trois termes n'a pu être vérifié (chapitre 4, section 4.6).

[^facture-37signals]: 37signals, « Our cloud spend in 2022 », 13 janvier 2023,
https://dev.37signals.com/our-cloud-spend-in-2022/ ; David Heinemeier Hansson, « Why we're leaving
the cloud », 19 octobre 2022, https://world.hey.com/dhh/why-we-re-leaving-the-cloud-654b47e0

[^reserves-echecs]: Ordonnance SEC 34-70694 du 16 octobre 2013,
https://www.sec.gov/litigation/admin/2013/34-70694.pdf ; communiqué de Public Health England et
article de The Register du 5 octobre 2020. Le chiffre exact de 461 469 323 dollars n'a pas été
retrouvé mot pour mot dans le texte du régulateur : le mémoire s'en tient à « plus de 460 millions ».
