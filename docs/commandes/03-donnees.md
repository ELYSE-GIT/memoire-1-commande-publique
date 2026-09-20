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

## Rejouer le notebook d'exploration

```bash
make notebook-decp
```

**Ce que ca fait** : execute `analyses/01-exploration-decp.ipynb` du debut a la fin et enregistre
les resultats dans le notebook lui-meme.

**Duree** : environ 5 secondes. **A quoi ca sert** : garantir que le notebook publie n'est pas
casse, et que ses resultats correspondent bien au code qu'il affiche.

Pour travailler dedans plutot que le rejouer : ouvrir le fichier dans VS Code et choisir
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
