# 22 octobre 2026, troisieme partie. 23,50 euros contre 119, et ce que l'ecart achete

La these du memoire est une affirmation sur de l'argent : une plateforme de qualite
professionnelle pour une fraction du cout des offres gerees. C'est le genre d'affirmation qu'un
jury verifie, et le genre qu'on peut gonfler sans mentir franchement. Cette session l'a chiffree.

## Le resultat

| Scenario | Fournisseur | EUR/mois HT |
|---|---|---|
| VPS minimal, tout sur une machine | OVHcloud | 17,50 |
| **VPS retenu**, tout sur une machine | OVHcloud | **23,50** |
| Base geree seule, borne basse | Google Cloud | 90,90 |
| Service gere et base geree | AWS | 119,44 |
| Service gere et base geree | Azure | 121,64 |
| Base geree seule, borne haute | Google Cloud | 176,34 |

**5,1 fois.** Pas cent fois, pas deux fois : cinq. C'est un rapport defendable, et c'est
precisement parce qu'il est modeste qu'il tient.

## Les trois facons de tricher, et ce qu'il a fallu faire pour les eviter

**Comparer deux choses differentes.** « AWS contre un VPS » ne veut rien dire dans l'absolu :
tout depend de ce qu'on y met. La comparaison porte donc sur une charge precise, et chacun de
ses chiffres est **lu** et non estime : la taille de la base est demandee a PostgreSQL
(`pg_database_size`, 2 481 Mo), la memoire du service vient de `make bench-api` (37,3 Mo), les
plafonds de processeur et de memoire sont ceux reellement declares dans `compose.yaml`.

**Comparer des prix invérifiables.** C'est la partie qui a pris le plus de temps, et de loin.
Les tarifs du nuage changent plusieurs fois par an, varient du simple au double selon la region,
et la plupart des chiffres qui circulent viennent de comparateurs qui recopient et datent mal.
Chaque tarif utilise ici vient d'une source officielle et lisible par une machine :

    AWS         liste de prix publique, CSV par service et par region   eu-west-3
    Azure       interface de tarification au detail, JSON, sans compte  francecentral
    OVHcloud    catalogue public, JSON, en euros                        FR
    BCE         taux de reference du jour, pour la conversion

Un test verifie le domaine de chaque source : un comparateur ne peut pas entrer dans le fichier.

**Oublier ce que l'argent achete.** C'est la tricherie la plus grave, et la plus courante. Les
96 euros d'ecart mensuel achetent des sauvegardes automatiques, une bascule, des correctifs
appliques, un engagement de disponibilite et un interlocuteur. Un test verifie que le memoire
nomme ces contreparties ; sans elles, le chiffre serait un argument de vente.

Et le chiffrage retient volontairement des configurations a **une seule zone**, qui n'offrent
aucune garantie de bascule. En haute disponibilite, la facture geree double a peu pres. L'ecart
se creuserait donc, et c'est la raison pour laquelle la comparaison est faite ainsi : elle
choisit systematiquement l'hypothese qui desavantage la these defendue.

## Google Cloud, ou l'honnetete coute une fourchette

Les trois autres fournisseurs publient leurs prix sous une forme qu'un programme peut lire.
Google Cloud, non : sa page de tarification construit ses tableaux dans le navigateur, et la
source contient **plusieurs jeux de prix sans que rien ne dise a quelle region chacun
correspond**. Les ecarts vont de 0,0413 a 0,07 dollar par vCPU-heure, soit 70 pour cent.

Deux solutions : choisir le jeu qui arrange, ou publier une fourchette. Le projet publie une
fourchette, et la borne basse est celle qui avantage Google. Les deux lignes correspondantes
sont marquees a part et hachurees sur la figure, parce qu'elles ne couvrent **que la base** : la
machine qui sert les pages n'y est pas.

Ce detail a failli produire une erreur. La premiere version du resume prenait « l'offre geree la
moins chere » toutes offres confondues, et designait donc Google Cloud a 90,90 euros, qui ne
couvre pas la meme chose. Le rapport annonce serait passe a 3,9, et il aurait ete faux dans le
sens defavorable. Corrige, et un test le verrouille.

## Trois offres que je n'ai pas chiffrees

Databricks, Snowflake et OpenAI font partie des offres auxquelles le cahier des charges demande
de comparer. Je ne les ai pas chiffrees, et je prefere le dire que le contourner : **aucune des
trois ne publie de tarif sous une forme verifiable sans ouvrir un compte.** Leurs pages de
tarification construisent leurs tableaux dans le navigateur, et j'ai verifie le code source des
trois.

J'aurais pu reprendre des chiffres de comparateurs. J'ai prefere publier zero chiffre. Et en
l'ecrivant je me suis apercu que cette absence est elle-meme un resultat : sur six fournisseurs
examines, trois rendent leurs prix verifiables par un tiers et trois non. Pour quelqu'un qui
compare avant d'acheter, c'est une donnee.

## Ce qui ne figure dans aucune colonne

**Le temps d'ingenierie.** Les heures passees a ecrire la collecte, le nettoyage, la detection,
la recherche et l'interface ne disparaissent pas parce qu'elles ne sont pas facturees : elles
sont payees en temps au lieu d'etre payees en euros. Des que ce temps est valorise au prix d'un
ingenieur, les 96 euros d'ecart mensuel representent moins d'une heure de travail.

C'est la limite honnete de la these, et elle est ecrite dans la section 11.3.3 plutot que
laissee au lecteur a deviner. Le resultat ne dit pas que les offres gerees sont cheres. Il dit
qu'**a cette echelle, pour cet usage, elles ne sont pas necessaires**, et il chiffre de combien.

## Ce que je retiens

La difficulte de cette phase n'etait pas le calcul : trois multiplications et une conversion.
Elle etait d'obtenir des prix qu'un lecteur puisse reverifier un par un. Les listes de prix
publiques d'AWS et d'Azure sont une excellente surprise ; celle d'AWS fait 170 Mo pour EC2 dans
une seule region, et il a fallu la lire en flux pour en extraire cinq lignes.

Et une regle qui ressort : **a chaque hypothese, choisir celle qui desavantage sa propre
these**. Une seule zone plutot que la haute disponibilite, la borne basse pour Google, le
scenario a 23,50 euros plutot que celui a 17,50. Un resultat qui survit a ce traitement se
defend ; un resultat obtenu dans l'autre sens ne survit pas a la premiere question du jury.
