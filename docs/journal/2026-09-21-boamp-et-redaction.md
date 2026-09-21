# 2026-09-21. BOAMP et premiere redaction

## Objectif du jour

Explorer la deuxieme source, le BOAMP, et ecrire les deux premiers chapitres du memoire, en
definissant tout le vocabulaire avant de l'employer.

## Ce qui a ete fait

- Notebook `analyses/04-exploration-boamp.ipynb` : volumetrie, nature des avis, avis ouverts,
  delais de reponse, et test de rapprochement avec les DECP. Le code de chaque graphique est ecrit
  et execute dans le notebook.
- `memoire/00-plan.md` : plan des 13 chapitres, pagination cible, principes de redaction.
- `memoire/01-vocabulaire.md` : chapitre 1, tous les termes du domaine et de la technique.
- `memoire/02-etat-des-lieux.md` : chapitre 2, le probleme en chiffres mesures, avec six figures.
- `tests/test_chiffres_memoire.py` : 17 tests qui comparent les chiffres cites dans le memoire aux
  mesures enregistrees.

## Ce que le BOAMP apporte

| Mesure | Valeur |
|---|---|
| Avis publies | 1 707 999, du 2 mars 2015 a aujourd'hui |
| Avis de marche | 1 160 935 |
| Resultats de marche | 465 999 |
| **Appels d'offres ouverts au moment de la mesure** | **8 014** |
| Delai median laisse aux entreprises | 31 jours |
| Volume annuel | environ 145 000 avis, stable depuis 2016 |

Contrairement aux DECP consolidees, dont la hausse apparente vient en partie de l'elargissement de
la collecte, le BOAMP est une source unique et homogene depuis dix ans. C'est une meilleure base
pour toute analyse d'evolution dans le temps.

## La difficulte principale : les deux sources ne se joignent pas

**Symptome** : sur 600 avis recents portant un identifiant de dossier, aucun ne correspond a un
identifiant des DECP. Ni sur `id`, ni sur `uid`, ni par inclusion.

**Cause** : le BOAMP porte un identifiant technique produit par la plateforme de dematerialisation
de l'acheteur, sous forme d'UUID. Les DECP portent un identifiant choisi par l'acheteur lui-meme,
souvent un numero de dossier interne, combine a son SIRET. Les deux designent le meme marche sans
jamais se rencontrer.

**Consequence** : relier les deux sources sera un rapprochement d'enregistrements, pas une jointure.
Le point d'ancrage existe : le SIRET de l'acheteur, present des deux cotes, le BOAMP le portant dans
son champ detaille et non dans ses colonnes de premier niveau.

**Statut** : non tranche. Un ADR decidera de la methode, et le taux de rapprochement obtenu sera
publie, y compris s'il est decevant.

**Lecon pour le memoire** : deux sources publiques d'une meme administration, sur un meme objet, sans
identifiant commun. C'est le probleme d'interoperabilite le plus banal et le plus couteux du monde
de la donnee publique, et il merite une section entiere.

## Autres enseignements

**Une metadonnee qui ment.** Le catalogue annonce une derniere modification au 25 aout 2025, soit
plus d'un an. La donnee, elle, va jusqu'a aujourd'hui. Une metadonnee decrit une intention, la
donnee decrit un fait : on verifie la fraicheur d'une source en regardant la donnee.

**Les limites d'une API d'agregation.** L'API sait compter et grouper, mais refuse `date_diff` et ne
renvoie pas l'alias d'une expression de date dans un groupement. Deux reponses : poser douze
questions simples plutot qu'une requete illisible, et rapatrier un echantillon quand le serveur ne
sait pas calculer. Regle retenue : agreger cote serveur quand on le peut, calculer localement quand
le serveur ne sait pas faire.

**Les chiffres du memoire sont desormais testes.** Le fichier `tests/test_chiffres_memoire.py`
compare chaque chiffre cite aux mesures enregistrees, et verifie que toute figure appelee dans le
texte existe. Si le jeu de donnees est retelecharge et qu'une valeur change, la chaine d'integration
nomme le chiffre devenu faux. La regle « aucun chiffre sans mesure » devient executable.

## Prochaine etape

L'API Recherche d'entreprises, troisieme source, pour enrichir les 22 % de marches sans categorie
d'acheteur et donner un nom lisible aux SIRET des deux cotes. Puis l'ADR sur le rapprochement
BOAMP et DECP.
