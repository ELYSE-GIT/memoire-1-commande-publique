# Chapitre 1. Le vocabulaire du sujet

> Brouillon. Les faits, les chiffres et les sources sont vérifiés ; la formulation reste à
> reprendre dans la voix de l'auteur.

Ce mémoire croise deux domaines qui ont chacun leur langue : le droit de la commande publique et
l'ingénierie des données. Un lecteur venu de l'un est rarement à l'aise dans l'autre. Ce chapitre
définit donc, avant toute autre chose, les termes utilisés dans la suite. Il se lit d'une traite ou
se consulte au besoin.

Les termes introduits plus loin dans le mémoire sont définis au moment où ils apparaissent, puis
repris dans le glossaire en annexe.

---

## 1.1 Le vocabulaire de la commande publique

**Commande publique.** L'ensemble des contrats par lesquels l'État, les collectivités territoriales,
les hôpitaux et leurs établissements achètent des travaux, des fournitures ou des services. Elle
recouvre les marchés publics et les concessions. En 2024, 223 383 contrats ont été recensés, pour
233,3 milliards d'euros [^oecp].

**Acheteur.** La personne publique qui achète : une commune, un département, une région, un
ministère, un hôpital, un établissement public. Le terme juridique exact est *pouvoir adjudicateur*
ou *entité adjudicatrice* selon le régime applicable. Ce mémoire emploie « acheteur », qui est le
terme retenu par les données elles-mêmes.

**Titulaire.** L'entreprise à qui le marché est attribué. Un marché peut avoir plusieurs titulaires
lorsqu'un groupement d'entreprises répond ensemble, ce qui explique qu'une même ligne de données
puisse apparaître autant de fois qu'il y a de titulaires.

**Marché public.** Un contrat conclu à titre onéreux entre un acheteur et une entreprise pour
répondre à un besoin en travaux, fournitures ou services.

**Accord-cadre.** Un contrat qui fixe les conditions d'achats à venir sans en arrêter d'emblée le
volume. Les commandes réelles prennent ensuite la forme de **marchés subséquents** ou de **bons de
commande**. Conséquence pour les données : le montant publié pour un accord-cadre est souvent un
plafond, pas une dépense réelle. C'est l'une des sources d'incohérence mesurées au chapitre 2.

**Concession.** Un contrat par lequel un acheteur confie l'exploitation d'un service ou d'un ouvrage
à une entreprise qui se rémunère sur son exploitation, et en assume le risque. La délégation de
service public en est la forme la plus connue.

**Procédure.** La façon dont l'acheteur met en concurrence. Les principales :

| Procédure | Principe | Quand |
|---|---|---|
| Procédure adaptée (MAPA) | l'acheteur fixe lui-même les modalités | sous les seuils européens |
| Procédure ouverte | toute entreprise peut déposer une offre | au-dessus des seuils |
| Procédure restreinte | seules les entreprises sélectionnées peuvent déposer une offre | au-dessus des seuils |
| Procédure négociée | l'acheteur discute les offres | cas limitativement prévus |
| Dialogue compétitif | l'acheteur définit la solution avec les candidats | besoins complexes |

Au 21 septembre 2026, sur les quelque 8 000 avis encore ouverts au BOAMP, 7 107 relèvent de la
procédure ouverte et 522 de la procédure adaptée [^mesure-boamp].

**Seuils.** Des montants qui déclenchent des obligations. Ils changent tous les deux ans. En 2026 :
publicité obligatoire à partir de 90 000 euros hors taxes ; procédure formalisée à partir de
140 000 euros pour l'État, 216 000 pour les collectivités et 432 000 pour les entités adjudicatrices
en fournitures et services ; 5 404 000 euros pour les travaux et les concessions. En dessous de
60 000 euros pour les fournitures et services, et de 100 000 euros pour les travaux, l'acheteur est
dispensé de publicité et de mise en concurrence [^seuils].

**Offre unique.** Un marché n'ayant reçu qu'une seule offre. C'est l'indicateur de risque le plus
utilisé dans la recherche sur la commande publique, parce qu'une mise en concurrence sans
concurrence n'a pas joué son rôle. Il ne constitue pas une preuve d'irrégularité : un marché très
spécialisé attire naturellement peu de candidats.

**Indicateur de risque**, souvent appelé *red flag*. Un signal statistique qui invite à regarder un
marché de plus près. La littérature en recense une quinzaine : offre unique, délai de réponse
anormalement court, montant très au-dessus des marchés comparables, attributions répétées au même
titulaire. Un indicateur n'accuse pas, il oriente l'attention. Cette distinction est au cœur de la
responsabilité du projet et sera rappelée dans l'interface elle-même.

---

## 1.2 Les sources de données

**Données ouvertes**, ou *open data*. Des données publiées par une administration, accessibles à
tous, gratuitement, dans un format exploitable par une machine, et réutilisables y compris à des
fins commerciales. En France, la Licence Ouverte 2.0 est la licence de référence : elle n'impose que
la mention de la source.

**DECP.** Données essentielles de la commande publique. Depuis 2018, tout acheteur doit publier les
informations essentielles des marchés qu'il attribue au-dessus d'un certain seuil : acheteur,
titulaire, objet, montant, durée, date de notification, code de nomenclature. L'obligation naît du
code de la commande publique et son format est fixé par arrêté.

**BOAMP.** Bulletin officiel des annonces des marchés publics, édité par la DILA, la Direction de
l'information légale et administrative, qui dépend des services du Premier ministre. Il publie les
avis **avant** la passation, c'est-à-dire les appels à concurrence, et **après**, c'est-à-dire les
résultats. Différence essentielle avec les DECP : le BOAMP annonce ce qui est ouvert, les DECP
décrivent ce qui est conclu.

**JOUE et TED.** Le Journal officiel de l'Union européenne publie les avis dépassant les seuils
européens ; TED, *Tenders Electronic Daily*, en est la plateforme. Hors du périmètre de ce mémoire,
mais cité parce que les mêmes marchés y apparaissent sous un troisième format.

**SIRET et SIREN.** Le SIREN identifie une entreprise ou un organisme sur neuf chiffres ; le SIRET
identifie l'un de ses établissements sur quatorze chiffres, les neuf du SIREN suivis de cinq
chiffres. Ces identifiants sont la clé qui permet de relier un acheteur ou un titulaire à sa fiche
officielle, et, on le verra, le seul point d'ancrage solide entre les deux sources du projet.

**CPV.** *Common Procurement Vocabulary*, la nomenclature européenne des achats publics. Un code de
huit chiffres désigne la nature de l'achat. Les deux premiers donnent la division : 45 pour les
travaux de construction, 72 pour les services informatiques, 33 pour le matériel médical. Cette
nomenclature rend les marchés comparables entre eux, ce qui est indispensable pour juger un prix.

---

## 1.3 Le vocabulaire technique

Les termes ci-dessous sont définis ici parce qu'ils reviennent dans tout le mémoire. Les choix
techniques eux-mêmes, avec leurs alternatives, sont discutés au chapitre 6.

**Donnée brute, donnée nettoyée.** La donnée brute est celle publiée par la source, telle quelle,
défauts compris. La donnée nettoyée a été validée, corrigée quand c'est possible, et marquée quand
ce ne l'est pas. Le projet conserve toujours les deux : une donnée effacée ne peut plus être
expliquée, ni corrigée par l'administration qui l'a publiée.

**Architecture en médaillon**, ou bronze, argent, or. Une organisation des données en trois couches
successives : *bronze* pour la donnée brute conservée à l'identique, *argent* pour la donnée
nettoyée et normalisée, *or* pour les tables prêtes à être servies. Chaque couche est reconstruite à
partir de la précédente, ce qui permet de rejouer toute la chaîne après correction d'une règle.

**Pipeline de données.** L'enchaînement automatisé des étapes qui conduisent d'une source au service
final : télécharger, valider, transformer, charger, vérifier.

**Orchestrateur.** Le programme qui lance les étapes d'un pipeline dans le bon ordre, à la bonne
heure, qui relance ce qui a échoué et garde la trace de ce qui a tourné.

**Format Parquet.** Un format de fichier qui range les données par colonne plutôt que par ligne. Il
compresse mieux et permet de ne lire que les colonnes utiles à une question. Mesure sur le jeu de ce
mémoire : le même contenu pèse 247,6 mégaoctets en Parquet contre 2 595,5 en CSV, soit 10,5 fois
moins [^mesure-parquet].

**CSV.** Un fichier texte où les valeurs sont séparées par des virgules. Lisible par un humain,
universel, mais volumineux et sans types : tout y est du texte, y compris les nombres et les dates.

**Base de données relationnelle.** Un système qui stocke des données en tables liées entre elles et
répond à des questions posées en SQL. PostgreSQL en est la référence libre.

**SQL.** Le langage standard pour interroger des données tabulaires. On y décrit *ce que l'on veut*,
pas *comment le calculer*, et le moteur choisit la méthode.

**Moteur analytique embarqué.** Un moteur SQL qui s'exécute dans le programme appelant, sans serveur
à installer ni à maintenir. DuckDB en est le représentant le plus connu. Il lit un fichier Parquet
sur place, sans importer les données au préalable.

**Jointure.** L'opération qui rapproche deux tables par une valeur commune. Elle suppose un
identifiant partagé. Quand cet identifiant n'existe pas, comme entre le BOAMP et les DECP, la
jointure est impossible et il faut passer au rapprochement.

**Rapprochement d'enregistrements**, ou *record linkage*. L'ensemble des méthodes qui reconnaissent
que deux enregistrements décrivent la même chose sans identifiant commun, en comparant plusieurs
attributs avec une part d'incertitude assumée et mesurée.

**Expression régulière.** Un motif qui décrit une forme de texte, utilisé pour valider ou extraire.
Un SIRET se vérifie avec un motif de quatorze chiffres : c'est immédiat, exact et explicable. Le
projet préfère systématiquement ce type de règle quand il suffit.

**Apprentissage automatique**, ou *machine learning*. Un programme qui ajuste ses paramètres à partir
d'exemples plutôt que de suivre des règles écrites à la main. Utile quand la règle est trop
complexe à formuler, inutile et coûteux quand elle est simple.

**Détection d'anomalies.** La recherche des observations qui s'écartent du comportement habituel.
Deux familles : les règles, explicites et explicables, et les modèles statistiques, qui apprennent
la norme à partir des données.

**Plongement lexical**, ou *embedding*. La représentation d'un texte par une suite de nombres, de
telle sorte que deux textes de sens proche aient des représentations proches. C'est ce qui permet de
retrouver « entretien des ascenseurs » en cherchant « maintenance d'élévateurs ».

**Grand modèle de langage**, ou LLM. Un modèle entraîné à prédire la suite d'un texte, capable de
répondre en langue naturelle. Puissant, coûteux, non déterministe, et sujet à inventer des réponses
plausibles. Le projet ne l'emploie qu'en dernier recours, et toujours avec ses sources affichées.

**Génération augmentée par la recherche**, ou RAG. Une technique qui consiste à chercher d'abord les
documents pertinents, puis à demander au modèle de répondre **uniquement** à partir d'eux, en citant
ses sources. C'est le garde-fou contre l'invention.

**Principe de l'escalier.** Règle de conduite de ce mémoire, appliquée à chaque problème : commencer
par la marche la plus basse, règles et expressions régulières ; puis la statistique ; puis
l'apprentissage automatique ; puis les plongements lexicaux ; puis les grands modèles de langage.
**On ne monte d'une marche que si la mesure prouve que la précédente ne suffit pas.** Chaque montée
se paie en temps de calcul, en coût, en consommation d'énergie et en difficulté d'explication.

**Conteneur.** Un processus isolé avec son propre système de fichiers, qui partage le noyau de la
machine hôte. Plus léger qu'une machine virtuelle, et identique du poste de développement au
serveur de production.

**Intégration continue.** Une chaîne de vérifications rejouée automatiquement à chaque modification
du code : style, types, tests, recherche de secrets. Elle garantit que ce qui est fusionné a été
vérifié, indépendamment de la discipline de celui qui écrit.

**Reproductibilité.** La capacité à réobtenir exactement le même résultat à partir des mêmes
entrées. Elle suppose des versions verrouillées, des données datées et des scripts plutôt que des
manipulations manuelles. Dans ce projet, elle va jusqu'aux figures, dont deux exécutions successives
produisent des fichiers identiques au bit près.

---

## 1.4 Les trois unités de comptage, et pourquoi elles comptent

Une confusion suffit à fausser un pourcentage et à décrédibiliser une analyse entière. Le jeu de
données principal de ce mémoire se compte de trois façons différentes.

| Unité | Volume | Ce que c'est |
|---|---|---|
| Ligne brute | 3 283 035 | tout ce que contient le fichier, historique des modifications compris |
| Ligne à l'état actuel | 2 114 675 | la dernière version de chaque marché, une ligne par titulaire |
| Marché distinct | 1 833 468 | un contrat, quel que soit le nombre d'avenants et de titulaires |

Les trois sont justes. Elles répondent à trois questions différentes : combien le fichier contient
de lignes, combien de lignes décrivent la situation d'aujourd'hui, et combien de contrats existent.

Un même chiffre change de sens selon l'unité : 899 298 lignes portent le nombre d'offres reçues, ce
qui représente 800 782 marchés distincts. Rapporté aux lignes, cela fait 42,5 % ; rapporté aux
marchés, 43,7 %. Diviser le nombre de lignes par le nombre de marchés donnerait 49 %, un chiffre
faux que rien ne signale.

**Règle tenue dans tout le mémoire : chaque pourcentage précise son unité de comptage.**

---

[^oecp]: Observatoire économique de la commande publique, chiffres 2024 publiés le 25 novembre 2025.
Repris par Seban Avocats, « Panorama de la commande publique : les chiffres de 2024 »,
https://www.seban-associes.avocat.fr/panorama-de-la-commande-publique-les-chiffres-de-2024/ et par
achat-logistique.info, « 233,2 milliards d'euros d'achats publics en 2024 », 26 novembre 2025.

[^seuils]: Seuils applicables en 2026, sur la base des règlements délégués (UE) 2025/2150, 2025/2151,
2025/2152 du 22 octobre 2025 et 2025/2487 du 2 décembre 2025, avis NOR ECOM2600976V du 13 janvier
2026, et du décret n° 2025-1386 du 29 décembre 2025. Synthèse : marche-public.fr, « Seuils de
procédure formalisée 2026 ».

[^mesure-boamp]: Mesure propre, API BOAMP, 21 septembre 2026. Reproductible par
`analyses/04-exploration-boamp.ipynb`.

[^mesure-parquet]: Mesure propre, API data.gouv.fr, fichier du 20 septembre 2026. Reproductible par
`make donnees-decp`.
