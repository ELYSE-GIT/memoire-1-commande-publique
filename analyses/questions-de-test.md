# Les trente questions de test de la recherche

Ce fichier explique a quoi sert `mesures/verification/questions-de-recherche.csv`, et comment le
corriger.

## Pourquoi ce fichier existe

« La recherche marche bien » n'est pas une mesure. Pour en faire une, il faut un jeu de questions
fixe et, pour une partie d'entre elles, savoir a l'avance quels marches devraient sortir.

C'est exactement la demarche suivie pour le rapprochement des sources : soixante paires relues a
la main, versionnees dans ce meme dossier, qui ont permis de mesurer une justesse plutot que de
l'affirmer. Sans elles, le seuil de rapprochement aurait ete choisi au hasard.

## Comment il a ete construit, et la limite que cela cree

Les trente questions ont ete **ecrites a partir des donnees** : vocabulaire reellement present
dans les objets de marche, acheteurs reellement presents, departements les plus representes.

Cela cree un biais qu'il faut enoncer plutot que cacher : **des questions tirees des donnees sont
plus faciles que des questions posees par un inconnu.** Une PME qui cherche un marche n'emploie
pas forcement le vocabulaire administratif des avis.

C'est pour cela que le jeu contient volontairement des questions qui ne suivent pas ce
vocabulaire :

| Type | Ce qu'il teste | Exemple |
|---|---|---|
| `paraphrase` | l'utilisateur dit autrement | « tonte des pelouses » pour « entretien des espaces verts » |
| `faute_de_frappe` | la tolerance aux erreurs | « mairie de Rene » pour Rennes |
| `sans_accent` | ce que tout le monde tape vraiment | « renovation energetique » |
| `question_naturelle` | une phrase, pas des mots cles | « qui fournit l'electricite aux hopitaux » |
| `probablement_sans_reponse` | la capacite a **ne pas** repondre | « un pont a peage en Corse » |

La derniere ligne est la plus importante. Un moteur qui renvoie toujours dix resultats, meme
quand il n'y a rien, est un moteur qui mentira a l'utilisateur.

## Ce que tu as a faire

**Environ trente minutes.** Ouvre `mesures/verification/questions-de-recherche.csv` et :

1. **supprime** les questions qui sonnent faux, ou que personne ne poserait ;
2. **reformule** dans tes mots celles qui sentent le vocabulaire administratif ;
3. **ajoute** les questions que tu poserais toi, surtout si elles n'emploient pas le vocabulaire
   des avis. Ce sont les plus utiles ;
4. laisse la colonne `type` telle quelle, ou mets `mots_cles` si tu ne sais pas.

Les dix questions marquees `a_juger = oui` sont celles pour lesquelles tu jugeras les resultats
un par un, a l'etape suivante. Tu peux changer lesquelles, garde juste le compte a dix environ.

## L'etape d'apres, une fois le fichier corrige

```bash
make bench-recherche
```

La commande ecrit `mesures/resultats/recherche-resultats.csv` : pour chaque question marquee
`a_juger`, les dix premiers marches trouves, avec une colonne `pertinent` vide.

Tu la remplis par `oui`, `non` ou `doute`, et la commande suivante calcule la precision reelle de
la recherche. Meme protocole que les soixante paires du rapprochement, et pour la meme raison :
**une mesure de pertinence ne peut venir que d'un jugement humain.**
