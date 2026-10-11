# services/publication

Copie la couche or, calculee par dbt dans DuckDB, vers la base PostgreSQL que le site
interrogera.

C'est une etape de **publication**, pas de transformation : rien n'est nettoye ni recalcule ici.
Si une valeur est fausse, le defaut se corrige dans `services/transformation/`, jamais ici. Deux
endroits qui nettoient, c'est deux verites qui divergent.

| Fichier | Role |
|---|---|
| `vers_postgres.py` | lit `or_marches` et `or_signaux`, les copie dans PostgreSQL, mesure chaque etape |

Lancement : `make charger`, apres `make up` et `make base-init`.

Pourquoi deux bases et non une seule : DuckDB calcule vite sur des colonnes, mais ne sert qu'un
seul processus lecteur a la fois. PostgreSQL sert plusieurs visiteurs en meme temps, et c'est lui
qui tournera sur le VPS. Le raisonnement complet, avec sa contrepartie mesuree, est dans
l'ADR 0008.
