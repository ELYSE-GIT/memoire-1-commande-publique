# services/transformation

De la donnee brute aux tables pretes a servir, en SQL, avec dbt.

## Les trois couches, et la regle de chacune

| Couche | Regle | Materialisation |
|---|---|---|
| **bronze** | la donnee telle que la source l'a publiee. Aucune correction, aucun filtre | vue |
| **argent** | nettoyee et normalisee. **On marque les problemes, on ne supprime rien** | table |
| **or** | prete a etre servie au site et aux analyses | table |

Les modeles de la couche or :

| Modele | Contenu |
|---|---|
| `or_marches` | les marches exploitables, 29 colonnes choisies |
| `or_variables` | les variables de detection : ecarts de prix, concentration, calendrier |
| `or_signaux` | les cinq signaux, avec leurs motifs en clair |

## Les commandes

| Commande | Ce qu'elle fait |
|---|---|
| `make transformer` | construit les trois couches |
| `make transformer-tester` | lance les tests de donnees |
| `make transformer-doc` | genere la documentation et le graphe des dependances |

## Pourquoi marquer plutot que supprimer

Une ligne supprimee ne peut plus etre expliquee a un jury, ni corrigee par l'administration qui l'a
publiee. Chaque ligne de la couche argent conserve donc ses valeurs d'origine, et recoit des
colonnes de qualite qui disent ce qui ne va pas :

- `montant_valide`, `date_valide`, `duree_valide` : des booleens ;
- `motifs_rejet` : la liste des regles enfreintes, lisible telle quelle.

Une analyse filtre ensuite sur ce qui l'interesse, et **le nombre de lignes ecartees par chaque
regle est mesure et publie**. C'est la difference entre un nettoyage et une disparition.
