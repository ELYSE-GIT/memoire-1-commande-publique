# 2026-09-21. La troisieme source : API Recherche d'entreprises

## Objectif

Verifier ce que la troisieme source apporte reellement : combler les 22 % de marches sans categorie
d'acheteur, et mesurer nous-memes la part des marches attribues a des PME.

## Ce qui a ete fait

Notebook `analyses/06-api-recherche-entreprises.ipynb` : taux de resolution des SIRET, nature des
acheteurs sans categorie, part des PME sur deux echantillons, et cout d'un enrichissement complet.

## Resultats

| Mesure | Valeur |
|---|---|
| Taux de resolution des SIRET d'acheteurs | 93 sur 99, soit 94 % |
| Acheteurs sans categorie identifies comme collectivite | 0 |
| **Part des marches attribues a une PME, tirage aleatoire** | **59,2 % plus ou moins 7,4 points** |
| Chiffre officiel de l'OECP pour 2024 | 60 % |
| Meme mesure sur un echantillon biaise | 5,0 % |
| Organisations a resoudre pour un enrichissement complet | 242 745, soit 11,2 heures a six appels par seconde |

## La demonstration du biais de selection

**Ce qui a ete fait d'abord, et qui etait faux** : prendre les soixante titulaires qui remportent le
plus de marches, et compter leurs categories. Resultat : 5 % de PME, 51,7 % d'ETI, 43,3 % de grandes
entreprises.

**Pourquoi c'est faux** : en selectionnant les entreprises qui remportent le plus de marches, on a
selectionne les grandes entreprises. La mesure ne repond pas a la question posee. Aucun message
d'erreur n'apparait : le calcul est juste, c'est l'echantillon qui ment.

**La bonne facon** : la question est « quelle part des marches va a une PME », donc on tire au hasard
parmi les marches, ce qui revient a ponderer les titulaires par leur nombre de marches. Resultat :
59,2 %, a comparer aux 60 % publies par l'Etat.

**Lecon pour le memoire** : un echantillon choisi au lieu d'etre tire donne ici douze fois moins de
PME. C'est la difference entre une conclusion juste et une conclusion inverse de la realite. Cette
demonstration a sa place dans le memoire, avec les deux barres cote a cote.

## Ce que l'API n'apporte pas

**Hypothese de depart** : l'API allait remplir le champ `acheteur_categorie` manquant.

**Mesure** : sur l'echantillon d'acheteurs sans categorie, aucun n'est identifie comme collectivite
territoriale. Ce sont des bailleurs sociaux (activites immobilieres), des etablissements
d'enseignement, d'action sociale, de recherche.

**Explication** : le champ des DECP suit une nomenclature pensee pour les collectivites, dans
laquelle ces organismes n'entrent pas.

**Lecon** : enrichir n'est pas imputer. Une source externe apporte une classification differente et
complementaire, pas la meme information dans le meme vocabulaire. Le projet gardera les deux, en
identifiant clairement ce qui vient du repertoire officiel.

## Un ecart explique

Le jeu compte 29 042 acheteurs distincts a l'etat actuel, et 29 069 sur tout le fichier. Le premier
chiffre correspond exactement a celui publie par le producteur. L'ecart de 27, releve comme « a
expliquer » lors de la premiere exploration, venait donc du perimetre et non d'une faute de calcul.

**Lecon** : un ecart s'explique presque toujours par une definition avant de s'expliquer par une
erreur. Il reste l'ecart sur les titulaires, 213 703 contre 217 199, a eclaircir.

## Consequences pour l'architecture

Onze heures d'appels pour resoudre toutes les organisations, sur une API publique gratuite partagee
avec tout le monde. Trois decisions a prendre dans un ADR :

1. cache local obligatoire, une organisation resolue une fois n'est plus reinterrogee ;
2. enrichissement par ordre d'utilite, les organisations les plus frequentes d'abord, ce qui ramene
   a deux heures pour couvrir la grande majorite des marches ;
3. traitement en tache de fond, jamais pendant une requete utilisateur.

## Prochaine etape

ADR sur le rapprochement entre les trois sources, puis fin de la phase 2 : comparaison avec les jeux
officiels des DECP et redaction de la suite du memoire.
