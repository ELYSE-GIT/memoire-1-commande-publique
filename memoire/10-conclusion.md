# Conclusion et limites

> Brouillon. Les faits, les chiffres et les mesures sont vérifiés et reproductibles ; la
> formulation reste à reprendre dans la voix de l'auteur.

## Ce qui est démontré

Six résultats sont mesurés, reproductibles par une commande, et chacun porte sa date et son fichier.

**Les données publiques deviennent exploitables sans qu'une seule ligne soit supprimée.** 94,2 % des
lignes à l'état actuel sont utilisables pour une analyse de prix, et les 5,8 % restantes sont
consultables avec, écrit en clair, le motif qui les disqualifie. Douze écritures sont ramenées à six
notions par trois fonctions SQL, sans aucun modèle.

**Les deux sources publiques qui ne se joignent pas peuvent être rapprochées, avec une confiance
publiée.** Réglage retenu : 94,1 % de justesse pour 16 % de couverture, le plafond étant imposé par
les données elles-mêmes puisque seuls 61,3 % des avis portent un identifiant exploitable. Le résultat
le plus utile de cette partie est négatif : deux seuils différents produisent le même nombre de liens
**justes**, donc abaisser le seuil n'apporte aucune information, seulement des erreurs. Il a fallu
relire soixante paires à la main pour le savoir.

**Une règle écrite à la main bat le meilleur modèle appris, à budget d'alertes égal.** Pour mille
alertes à examiner, la règle atteint 96,1 % de concordance contre 65,7 % pour le modèle orienté par
les mêmes variables, et 0,0 % pour le modèle brut, le hasard donnant 3,1 %. Dix méthodes ont été
comparées, et le protocole à budget égal est ce qui rend la comparaison honnête : comparer des seuils
revient à comparer des échelles.

**Un assistant peut répondre à une question en langue naturelle sans modèle de langue, et ses
réponses sont vérifiables par une machine.** Sur quarante questions versionnées : 448 citations
vérifiées, **zéro fausse**, aucune des six règles de cohérence rompue, 18 millisecondes de latence
médiane. Chaque réponse porte son filtre en clair et les numéros des marchés d'où vient son chiffre,
ce qui permet de la revérifier automatiquement. Aucune de ces vérifications n'est possible sur une
réponse générée.

**Deux millions de marchés se servent depuis une machine modeste.** Recherche plein texte à
19,7 millisecondes de médiane, 89,3 requêtes par seconde sans aucun échec, 37,3 mégaoctets de mémoire
pour le service, des pages de 17 kilooctets au maximum, et dix pages sur dix qui fonctionnent sans
JavaScript.

**Et le coût tient.** 23,50 euros hors taxes par mois contre 119,44 chez AWS et 121,64 chez Azure
pour la même charge, soit **5,1 fois**, sur des tarifs officiels relevés le même jour et
reverifiables ligne par ligne. À chaque hypothèse discutable, celle qui désavantage la thèse a été
retenue : une seule zone de disponibilité plutôt que la haute disponibilité, la borne basse pour le
fournisseur dont les prix ne sont pas identifiables, et la machine à 23,50 euros plutôt que celle à
17,50.

## Ce qui n'est pas démontré

Ces limites ne sont pas des précautions de style. Chacune désigne une affirmation que ce mémoire
**ne** fait pas.

**La disponibilité.** Il y a une machine, donc aucune garantie de service. Si elle tombe, le site
tombe. La chaîne est rejouable depuis la donnée brute conservée, donc le pire scénario est une
reconstruction de quelques heures, pas une perte ; ce n'est pas la même chose qu'une bascule
automatique.

**Le déploiement en production.** Le projet tourne sur la machine de développement. Le chapitre 7 dit
précisément ce qui est prêt à déployer, ce qui reste à écrire et ce que la machine coûterait, mais un
service non déployé n'est pas un service en production, et les latences publiées sont celles d'un
ordinateur portable, pas d'un serveur à 23,50 euros.

**La pertinence de la recherche.** Ce qui est mesuré est la vitesse et l'absence de silence. La
qualité des résultats demande des jugements humains qui n'existent pas encore. De même, au-delà de
cinq mille marchés qui répondent, les dix affichés peuvent être dix autres que les dix du classement
exact : c'est annoncé dans chaque réponse, et son effet réel sur un utilisateur n'est pas mesuré.

**La généralisation de l'assistant.** Les quarante questions ont été écrites par l'auteur des motifs
qui les reconnaissent. Quarante sur quarante mesure donc la cohérence interne, pas la capacité à
comprendre une question nouvelle.

**La précision de la détection est un minorant, pas une précision.** L'étiquette utilisée est le
signalement d'anomalie du producteur lui-même, qui est une étiquette faible : un marché anormal non
signalé par son producteur compte comme une erreur de la règle alors qu'il peut être un vrai
signalement. Le chiffre annoncé est donc une borne basse, et seul un jugement humain sur un
échantillon permettrait de le mesurer vraiment.

**Le temps d'ingénierie n'est dans aucune colonne, et c'est la limite qui compte le plus.** Les
heures passées à écrire la collecte, le nettoyage, la détection, la recherche et l'interface ne
disparaissent pas parce qu'elles ne sont pas facturées : elles sont payées en temps. Dès que ce temps
est valorisé au prix d'un ingénieur, les 96 euros d'écart mensuel représentent **moins d'une heure de
travail**. Ce qui sauve le raisonnement n'est pas une pirouette comptable : ce temps a produit le
nettoyage, le rapprochement des sources et la détection, qu'aucune offre gérée ne fournit. Les
offres gérées remplacent de l'exploitation, pas de la conception.

## Ce que je ferais ensuite, dans cet ordre

1. **Faire juger à la main un échantillon de marchés signalés**, pour obtenir une étiquette qui ne
   vienne pas du producteur. C'est ce qui manque pour transformer un minorant en mesure, et c'est le
   seul point qui change la valeur scientifique du chapitre 5.
2. **Corriger la taille minimale de famille d'achat**, vérifiée sur l'historique complet au lieu de
   la période jugée. La correction changera des chiffres publiés, donc elle mérite sa propre mesure.
3. **Comprendre le décrochage de 2023**, où la concordance tombe à 53,1 % contre 81,7 % en 2022.
   Aucune hypothèse n'est aujourd'hui vérifiée.
4. **Déployer, puis remesurer sur la machine réelle**, qui est moins puissante que celle du
   développement.
5. **Faire écrire les questions par quelqu'un d'autre**, et faire relire les paires rapprochées par
   un second relecteur. Deux limites qui tiennent au même fait : un seul auteur a tout écrit et tout
   jugé.

## Le résultat qui résume les autres

S'il faut retenir une seule chose de ce travail, ce n'est pas un chiffre, c'est un refus répété et
chaque fois justifié par une mesure : **aucun orchestrateur, aucun stockage objet, aucun entrepôt de
données, aucun moteur distribué, aucun modèle appris en production, aucun modèle de langue, et aucune
ligne de JavaScript écrite.** Sept outils reconnus, utiles ailleurs, écartés ici avec à chaque fois
le chiffre qui le justifie et le critère écrit qui ferait changer d'avis.

Un seul outil a été adopté sans réserve dans la couche de données, et le raisonnement est l'inverse
du précédent : la question n'a jamais été « cet outil est-il bon » mais « qu'est-ce que je devrais
écrire sans lui ».

C'est la seule méthode que ce mémoire propose de généraliser. Elle tient en une phrase : **on ne
monte une marche que si une mesure montre que la précédente ne suffit pas, et le résultat est publié
même quand il déplaît.**
