-- La couche bronze ne transforme rien. Elle nomme.
--
-- Ce modele existe pour une seule raison : donner un nom stable a un fichier dont le chemin
-- contient une date. Le reste du projet interroge `bronze_decp`, pas
-- `donnees/bronze/decp/2026-09-28/decp.parquet`. Le jour ou la collecte change de convention de
-- nommage, une seule ligne change ici.
--
-- C'est une vue, pas une table : materialiser 3,28 millions de lignes une seconde fois
-- occuperait 250 Mo de plus sans rien apporter. DuckDB lit le Parquet sur place.

{{ config(materialized='view') }}

select *
from read_parquet(
    '{{ var("chemin_decp", "../../donnees/bronze/decp/*/decp.parquet") }}',
    union_by_name = true
)
