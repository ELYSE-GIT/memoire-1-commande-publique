# ADR 0006. Detecter par des regles, avec des seuils mesures

- Date : 2026-09-28
- Statut : accepte
- Phase : 5, ingenierie des variables et detection

## Contexte

Le projet doit signaler les marches qui meritent un regard. Trois contraintes cadrent la question,
et aucune n'est negociable.

1. **Il n'existe aucune verite de reference.** Personne ne publie la liste des marches
   irreguliers. L'apprentissage supervise est donc impossible, non par choix mais par absence
   d'etiquettes.
2. **Un faux signalement coute plus cher qu'un signalement manque.** Le service s'adresse au
   public. Signaler a tort un marche regulier abime la confiance et peut nuire a une entreprise.
3. **Le resultat doit s'expliquer.** Un jury, un acheteur ou un journaliste demanderont pourquoi
   tel marche est signale. « Le modele l'a decide » n'est pas une reponse acceptable.

## Decision

**Detecter par des regles explicites, dont les seuils sont choisis par la mesure, et afficher
chaque signal comme une invitation a verifier.**

### Les variables, construites avant les regles

Une colonne est recue, une variable est fabriquee. Le fichier `or_variables.sql` construit trois
groupes de comparaison, parce qu'**un marche ne se juge pas dans l'absolu mais par rapport a ses
pairs** :

| Groupe | Ce qu'il permet de juger | Variable principale |
|---|---|---|
| la famille d'achat (code CPV) | un prix | ecart normalise a la mediane du groupe |
| l'acheteur | une habitude d'attribution | part des marches allant a un meme titulaire |
| le couple acheteur et titulaire | une relation | nombre de marches remportes ensemble |

L'ecart de prix est calcule **sur le logarithme du montant**, parce que la distribution est
log-normale, et **normalise par l'ecart interquartile** plutot que par l'ecart type. Sur des
donnees ou une ligne sur trente porte un montant fantaisiste, l'ecart type est lui-meme fausse par
ces valeurs et le score qu'il produit ne veut plus rien dire.

### Les regles, et leurs seuils

| Signal | Regle | Marches designes |
|---|---|---|
| Prix tres eleve | ecart normalise superieur a 4, dans un groupe d'au moins 30 marches | 2 661 (0,13 %) |
| Prix eleve a verifier | ecart entre 3 et 4 | 17 418 (0,87 %) |
| Prix tres bas, **non evalue** | ecart inferieur a moins 4 | 18 954 (0,95 %) |
| Offre unique sur gros marche | une seule offre, au-dessus du seuil de procedure formalisee | 53 328 (2,67 %) |
| Titulaire dominant | plus de la moitie des marches d'un acheteur qui en passe au moins dix | 1 656 (0,08 %) |
| **Au moins un signal fort** | | **57 409 (2,87 %)** |

### L'evaluation, et sa limite

Faute de verite de reference, l'evaluation utilise une **etiquette faible** : les montants que le
producteur des donnees signale lui-meme. Mesure du 28 septembre 2026, `make bench-detection` :

| Sens | Seuil | Signales | Precision | Rappel |
|---|---|---|---|---|
| trop cher | 3 | 33 600 | 55,1 % | 34,0 % |
| trop cher | **4** | 8 331 | **75,8 %** | 11,6 % |
| trop cher | 5 | 3 535 | 92,6 % | 6,0 % |
| **trop bas** | 4 | 18 208 | **0,0 %** | 0,0 % |
| les deux melanges | 4 | 26 539 | 23,8 % | 11,6 % |

**La precision affichee est un minorant.** L'etiquette est elle-meme produite par un detecteur : un
marche que nous signalons sans qu'il l'ait signale peut etre une anomalie qu'il a manquee, et non
une erreur de notre part. Ce point doit etre redit chaque fois que ce chiffre est cite.

### La decouverte qui a change le modele

La premiere version utilisait une **valeur absolue** de l'ecart, donc signalait indifferemment les
montants trop eleves et trop bas. L'evaluation a montre que les seconds ne concordent **jamais**
avec l'etiquette : zero concordance sur 18 208 marches. Melanger les deux faisait tomber la
precision de 75,8 % a 23,8 %.

Les deux directions ont donc ete separees. Cela ne signifie pas qu'un montant anormalement bas soit
anodin : un marche de travaux a un euro est tout aussi suspect. Cela signifie que **l'etiquette
faible ne dit rien sur ce cas**, donc qu'on ne peut pas le valider. Le signal existe, il est
expose, et il porte la mention « non evalue ».

C'est une lecon generale : **une mesure d'evaluation ne dit rien sur ce que son etiquette ignore**.
Confondre « non valide » et « invalide » aurait supprime un signal peut-etre utile.

## Alternatives examinees

| Option | Pour | Contre | Verdict |
|---|---|---|---|
| **Regles explicites, seuils mesures** | explicable devant un jury, un acheteur, un journaliste ; aucune dependance ; se verifie ligne a ligne | ne trouve que ce qu'on a pense a chercher | **retenu** |
| Isolation Forest, ou une autre detection non supervisee | trouve des combinaisons inattendues ; standard du domaine | explique mal ses decisions ; demande une normalisation des variables dont l'effet devrait etre mesure ; aucune etiquette pour comparer aux regles | **a mesurer en phase 5 bis**, contre les regles, avec la meme etiquette faible |
| Apprentissage supervise | le plus performant quand il est applicable | **impossible** : aucune etiquette fiable n'existe | exclu par le sujet |
| Indice composite type CRI, de la litterature | valide academiquement, comparable entre pays | demande des champs que les DECP ne portent pas, notamment les delais de procedure | partiellement applicable, a etudier |
| Grand modele de langage sur les objets de marche | lit le texte libre | cout, non determinisme, aucune explicabilite, et le probleme n'est pas textuel | non |

Le raisonnement est celui de l'escalier : la marche la plus basse d'abord. Elle donne 75,8 % de
precision sur la regle de prix. **Monter d'une marche ne se justifiera que si une mesure montre
qu'un modele fait mieux**, avec la meme etiquette et le meme protocole. C'est le travail de la
phase suivante, et le resultat sera publie meme s'il est defavorable aux regles.

## Consequences

**Positives**

- Chaque signalement porte son motif en clair, affichable a l'ecran sans traduction.
- Les seuils sont justifies par une table de mesure, pas par une intuition.
- Le cumul de signaux independants donne une priorite d'examen : 236 marches en portent deux.
- Rien a entrainer, rien a reentrainer, rien a surveiller pour derive.

**Negatives et limites, a enoncer dans le memoire**

- **Les regles ne trouvent que ce qu'on a pense a chercher.** C'est leur limite de principe, et
  c'est l'argument principal en faveur d'un modele non supervise en complement.
- Le signal de prix ne couvre que les groupes d'au moins trente marches : les familles rares sont
  hors de portee.
- La detection s'applique apres nettoyage, donc **apres retrait des montants deja signales par le
  producteur**. Elle en trouve donc moins, mais ce qu'elle trouve est nouveau.
- L'offre unique ne couvre que 44 % des marches, faute d'information. Le biais de ce sous-ensemble
  reste a mesurer.

## A mesurer ensuite

1. Un modele non supervise, evalue contre la meme etiquette faible et le meme protocole.
2. L'effet du seuil de trente marches par groupe : combien de familles, et donc de marches,
   restent hors de portee.
3. Le biais du sous-ensemble ou le nombre d'offres est renseigne.
4. La stabilite des signaux d'une collecte a l'autre : un marche signale aujourd'hui l'est-il
   encore apres la republication du lendemain.
