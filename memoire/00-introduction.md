# Introduction

> Brouillon. Les faits, les chiffres et les mesures sont vérifiés et reproductibles ; la
> formulation reste à reprendre dans la voix de l'auteur.

La commande publique française représente environ 230 000 marchés par an et plus de
230 milliards d'euros en 2024. Depuis 2018, les acheteurs publics ont l'obligation de publier les
données essentielles de ces marchés, et ils le font : le jeu consolidé est republié chaque matin,
librement réutilisable.

Il est inexploitable en l'état, et cela se mesure. Additionner les montants publiés tels quels
donne un total annuel **faux d'un facteur dix à vingt**. Des dates de notification tombent au
1er janvier de l'an 1. La nature d'un marché s'écrit de douze façons différentes pour six notions.
Et les deux grandes sources publiques, les données essentielles et le bulletin officiel des
annonces, désignent les mêmes marchés sans jamais se rencontrer : sur six cents avis récents
portant un identifiant de dossier, **aucun** ne correspond à un identifiant des données
essentielles.

La conséquence pratique est qu'une petite entreprise qui voudrait savoir qui achète quoi, à quel
prix et auprès de qui, n'a pas les moyens de le découvrir. L'ouverture des données a eu lieu ; leur
lisibilité, non.

## La question posée

Ce mémoire part d'une question d'ingénieur plutôt que d'une question de recherche :

> **Peut-on rendre ces données lisibles, signaler les marchés atypiques et répondre à une question
> en langue naturelle, avec une qualité professionnelle, pour un coût qu'une petite structure peut
> payer, et en démontrant chacun de ces trois mots ?**

Trois mots sont à démontrer, et ils ne se démontrent pas de la même manière. « Lisible » se mesure
en qualité de données. « Atypique » se mesure en précision, et demande de dire ce qu'on appelle un
signal. « Payable » se mesure en euros par mois, face à ce que coûteraient les offres gérées des
grands fournisseurs à charge égale.

## La thèse défendue

**À cette échelle et pour cet usage, des outils libres déployés sur une machine modeste atteignent
une qualité professionnelle pour environ cinq fois moins cher qu'une offre gérée équivalente, et le
chiffre survit à une comparaison faite dans les règles.**

Le résultat central est **23,50 euros hors taxes par mois**, contre 119,44 chez AWS et 121,64 chez
Azure pour la même charge, à partir de tarifs officiels relevés le même jour et reverifiables un par
un. Soit un rapport de **5,1**.

Ce que la thèse ne dit pas mérite d'être énoncé tout de suite, parce que c'est la première objection
qu'un jury formulera : elle ne dit pas que les offres gérées sont chères. Les 96 euros d'écart
mensuel achètent des sauvegardes automatiques, une bascule en cas de panne, des correctifs
appliqués, un engagement de disponibilité et un interlocuteur. La thèse dit qu'à cette échelle, pour
cet usage, **ces garanties ne sont pas nécessaires**, et elle chiffre de combien.

## La méthode, en quatre principes

**Mesurer plutôt qu'affirmer.** Chaque composant a son banc de mesure, chaque résultat son fichier
daté dans `mesures/`, et les seize figures du document sont tracées depuis ces fichiers, jamais
saisies à la main. Un test échoue si un chiffre du texte ne correspond plus à sa mesure.

**L'escalier de complexité.** Règles et expressions régulières, puis statistique, puis apprentissage
automatique, puis vecteurs de sens, puis modèle de langue. **On ne monte une marche que si une
mesure montre que la précédente ne suffit pas.** Ce projet s'est arrêté à la statistique : dix
méthodes de détection comparées à budget d'alertes égal donnent la main à une règle écrite à la main,
et l'extension vectorielle de la base est installée sans qu'aucune colonne de vecteurs existe. Ce
sont des refus mesurés, pas des renoncements.

**Marquer plutôt que supprimer.** Aucune ligne de données n'est jamais supprimée. Une ligne fautive
reste consultable avec, écrit en clair à côté d'elle, le motif qui la disqualifie. C'est ce qui
permet de répondre à « lesquelles, et pourquoi », et de changer une règle sans avoir à recollecter.

**Publier ce qui déplaît.** Les résultats défavorables, les mesures non concluantes, les chiffres
que l'enquête n'a pas trouvés et les erreurs commises figurent dans le document au même titre que
les réussites. Soixante-quatre difficultés sont consignées, et le chapitre 9 leur est consacré. Une
approximation annoncée est une limite ; une approximation cachée est un mensonge sur la donnée.

## Le plan

Le **chapitre 1** mesure le problème sur les données réelles. Le **chapitre 2** examine ce qui
existe déjà, outils publics, projets associatifs et plateformes commerciales, à partir d'une grille
de fonctions posée avant la comparaison. Le **chapitre 3** expose l'architecture retenue et les
options écartées.

Les **chapitres 4, 5 et 6** sont le coeur technique : rendre les données exploitables et relier les
deux sources, détecter les marchés atypiques, puis répondre à une question en citant ses sources. Le
**chapitre 7** traite de la mise en service et de la sécurité, le **chapitre 8** rassemble les
mesures, l'incertitude et la comparaison de coûts, et le **chapitre 9** les difficultés.

Trois annexes complètent le document sans alourdir le corps : le glossaire (annexe A), l'histoire
des pratiques qui explique d'où viennent ces outils et pourquoi ils ont remplacé les précédents
(annexe B), et les études de cas d'organisations qui les utilisent, chacune avec son niveau de
fiabilité (annexe C).

## Le matériel et les outils

Le développement s'est fait sur un ordinateur portable à dix coeurs et 16 gigaoctets de mémoire,
sans carte graphique dédiée. Aucun entraînement de modèle, aucun calcul distribué, aucun appel à un
service payant n'a été nécessaire. Le code, les mesures, les décisions d'architecture et les journaux
de bord sont publics.

> **À écrire par l'auteur** : la phrase sur l'assistance par modèles de langue pour les étapes
> techniques. C'est à toi de la formuler, et elle doit rester factuelle.
