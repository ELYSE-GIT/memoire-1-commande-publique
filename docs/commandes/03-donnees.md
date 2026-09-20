# 03. Les donnees : telecharger, explorer, mesurer

Toutes ces commandes se lancent a la racine du projet, sur le Mac.

## Telecharger le jeu DECP consolide

```bash
make donnees-decp
```

**Ce que ca fait** : interroge l'API de data.gouv.fr pour obtenir l'adresse du fichier du jour, puis
telecharge `decp.parquet` dans `donnees/brut/`.

**Pourquoi passer par l'API** : le jeu est republie chaque matin et l'adresse contient la date de
publication. Une adresse copiee a la main serait perime des le lendemain.

**Resultat attendu** : un fichier d'environ 240 Mo. **Duree** : environ 5 secondes en fibre.

Le dossier `donnees/` est ignore par git. Les donnees brutes ne se versionnent pas : elles sont
lourdes, elles changent tous les jours, et elles se retelechargent en une commande.

## Mesurer la qualite et les performances

```bash
make bench-decp
```

**Ce que ca fait** : execute huit mesures sur le fichier (volume, doublons, montants, dates, offres
recues), chronometre chacune, et ecrit deux fichiers dans `mesures/resultats/` :

- `AAAA-MM-JJ-decp-qualite.json` : le detail, avec le contexte d'execution (machine, versions,
  taille du fichier) ;
- `AAAA-MM-JJ-decp-qualite.csv` : les memes chiffres a plat, pour tracer les figures du memoire.

**Duree** : environ 2 secondes. **Resultat attendu** : huit lignes de mesures, puis les deux
chemins de fichiers ecrits.

Ces fichiers sont versionnes : ce sont les preuves des chiffres du memoire.

## Calculer les agregats descriptifs

```bash
make bench-decp-distributions
```

**Ce que ca fait** : calcule sept agregats (tranches de montant, total annuel brut et nettoye,
saisonnalite, categories d'acheteur, familles CPV, offres recues, ecritures de la nature) et ecrit
un CSV par agregat dans `mesures/resultats/`.

**Duree** : moins d'une seconde. **Perimetre** : l'etat actuel de chaque marche, soit 1 833 468
marches, et non les 3,28 millions de lignes d'historique.

## Tracer les figures du memoire

```bash
make figures
```

**Ce que ca fait** : trace cinq figures dans `memoire/figures/`, en SVG pour le memoire imprime et
en PNG pour l'apercu. Le script lit **uniquement** les CSV de `mesures/resultats/`, jamais le
fichier Parquet.

**Pourquoi cette separation** : une figure doit etre reproductible sans retelecharger 240 Mo, et
chaque valeur affichee doit exister dans un fichier que l'on peut ouvrir et verifier. Aucun chiffre
du memoire n'est saisi a la main.

**Duree** : environ 3 secondes.

## Rejouer les notebooks d'exploration

```bash
make notebooks
```

**Ce que ca fait** : execute les notebooks de `analyses/` du debut a la fin et enregistre les
resultats dans les fichiers eux-memes.

**Duree** : environ 15 secondes. **A quoi ca sert** : garantir qu'un notebook publie n'est pas
casse, et que ses resultats correspondent bien au code qu'il affiche. Un notebook publie sans avoir
ete execute est du code non teste.

Pour travailler dedans plutot que les rejouer : ouvrir le fichier dans VS Code et choisir
l'interpreteur `.venv` du projet.

## Les sources de donnees du projet

| Source | Contenu | Acces | Licence |
|---|---|---|---|
| DECP consolidees | marches attribues, 63 sources agregees, 2018 a 2026 | data.gouv.fr, Parquet et CSV | Licence Ouverte 2.0 |
| DECP officielles | jeux `decp-2022-marches-valides` et `-exclus` | API Opendatasoft de data.economie.gouv.fr | Licence Ouverte 2.0 |
| BOAMP | avis d'appel a la concurrence et d'attribution | API Opendatasoft de la DILA | Licence Ouverte 2.0 |
| Recherche d'entreprises | identite des entreprises (base SIRENE) | API publique de l'Etat | Licence Ouverte 2.0 |

## Verifier ce qu'on a telecharge

```bash
ls -lh donnees/brut/
uv run python -c "import duckdb; print(duckdb.sql(\"describe select * from 'donnees/brut/decp.parquet'\"))"
```

## Liberer la place

```bash
rm -rf donnees/
```

Aucune perte : tout se retelecharge avec `make donnees-decp`.
