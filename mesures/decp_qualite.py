"""Mesure de la qualite du jeu DECP consolide.

Ce script rejoue, de facon reproductible, les mesures explorees dans
`analyses/01-exploration-decp.ipynb`. Le notebook sert a comprendre, ce script sert a produire
des chiffres datees, comparables d'une execution a l'autre.

Il ecrit deux fichiers dans `mesures/resultats/` :
  - un JSON complet, avec le contexte d'execution (machine, versions, taille du fichier) ;
  - un CSV a plat, directement utilisable pour tracer les figures du memoire.

Lancement : `make bench-decp` (ou `uv run python mesures/decp_qualite.py`).

Principe retenu : DuckDB lit le fichier Parquet sur place. Aucune base n'est demarree, aucune
donnee n'est copiee. Chaque requete est chronometree separement, car les durees varient de
plusieurs ordres de grandeur selon que DuckDB lit les metadonnees du fichier ou son contenu.

Pourquoi ce moteur plutot qu'un autre, a l'echelle de ce jeu (3,28 M de lignes, 66 colonnes,
236 Mo en Parquet, sur un portable de 16 Go) :

    Option       Avantage                         Limite ici                    Verdict
    DuckDB       lit le Parquet sur place, SQL    mono-machine                  retenu
                 complet, agregation en ms
    pandas       ecosysteme, souplesse            charge tout en RAM avant      pour afficher
                                                  d'agreger                     les resultats
    polars       tres rapide, API typee           une API de plus, alors que    ecarte ici
                                                  le SQL sert deja dans dbt
    PySpark      passe a l'echelle sur cluster    demarrer une JVM coute plus   ecarte
                                                  que le calcul lui-meme
    PostgreSQL   transactionnel, sert le site     import prealable de 3,3 M     plus tard
                                                  de lignes

A quelle echelle la reponse changerait : au-dela d'une centaine de Go, ou si le traitement devait
etre reparti sur plusieurs machines, un moteur distribue redeviendrait pertinent. En dessous, il
ajoute du cout et de la complexite sans gain mesurable.

Le format de sortie suit la meme logique : JSON pour le detail et le contexte (structure imbriquee,
lisible tel quel), CSV pour les figures (une ligne par indicateur, directement tracable). Une base
de donnees pour stocker huit mesures serait disproportionnee.
"""

from __future__ import annotations

import csv
import json
import platform
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "donnees" / "brut" / "decp.parquet"
SORTIE = RACINE / "mesures" / "resultats"

# Chaque mesure : un nom, une question en francais, une requete SQL.
# L'ordre suit celui de l'exploration : volume, doublons, montants, dates, offres.
MESURES: list[tuple[str, str, str]] = [
    (
        "volume",
        "Combien de lignes, de marches, d'acheteurs et de titulaires ?",
        """
        select
            count(*)                        as lignes,
            count(distinct uid)             as uid_distincts,
            count(distinct acheteur_id)     as acheteurs,
            count(distinct titulaire_id)    as titulaires
        from decp
        """,
    ),
    (
        "lignes_par_uid",
        "Un identifiant de marche porte-t-il une ou plusieurs lignes ?",
        """
        with par_uid as (select uid, count(*) as n from decp group by 1)
        select
            sum(case when n = 1 then 1 else 0 end) as uid_une_seule_ligne,
            sum(case when n > 1 then 1 else 0 end) as uid_plusieurs_lignes,
            max(n)                                 as maximum_lignes_pour_un_uid
        from par_uid
        """,
    ),
    (
        "origine_des_lignes_multiples",
        "Historique des modifications, groupements d'entreprises, ou vrais doublons ?",
        """
        with par_couple as (
            select
                uid,
                modification_id,
                count(*)                     as n,
                count(distinct titulaire_id) as titulaires
            from decp
            group by 1, 2
        )
        select
            sum(case when n > 1 and n = titulaires then 1 else 0 end) as multi_titulaires,
            sum(case when n > 1 and n > titulaires then 1 else 0 end) as doublons_residuels
        from par_couple
        """,
    ),
    (
        "lignes_actuelles",
        "En ne gardant que l'etat actuel de chaque marche, combien reste-t-il ?",
        """
        select
            count(*)            as lignes,
            count(distinct uid) as marches
        from decp
        where donneesActuelles
        """,
    ),
    (
        "montants",
        "Les montants sont-ils exploitables ?",
        """
        select
            sum(case when montant is null then 1 else 0 end)   as absents,
            sum(case when montant <= 0 then 1 else 0 end)      as negatifs_ou_nuls,
            sum(case when montant > 1e9 then 1 else 0 end)     as superieurs_au_milliard,
            round(min(montant), 2)                             as minimum,
            round(median(montant), 2)                          as mediane,
            round(max(montant), 2)                             as maximum
        from decp
        """,
    ),
    (
        "anomalies_du_producteur",
        "Combien d'anomalies le producteur signale-t-il lui-meme ?",
        """
        select
            sum(case when montant_anomalie = 'suspect' then 1 else 0 end)  as suspects,
            sum(case when montant_anomalie = 'aberrant' then 1 else 0 end) as aberrants
        from decp
        """,
    ),
    (
        "dates",
        "Les dates de notification sont-elles plausibles ?",
        """
        select
            sum(case when dateNotification is null then 1 else 0 end)         as absentes,
            min(dateNotification)                                             as plus_ancienne,
            max(dateNotification)                                             as plus_recente,
            sum(case when dateNotification < date '2015-01-01' then 1 else 0 end) as avant_2015,
            sum(case when dateNotification > current_date then 1 else 0 end)  as dans_le_futur
        from decp
        """,
    ),
    (
        "offres_recues",
        "L'indicateur de risque principal, le nombre d'offres, est-il renseigne ?",
        """
        select
            sum(case when offresRecues is null then 1 else 0 end) as absentes,
            sum(case when offresRecues = 1 then 1 else 0 end)     as une_seule_offre,
            max(offresRecues)                                     as maximum
        from decp
        """,
    ),
]


def contexte(fichier: Path) -> dict[str, Any]:
    """Tout ce qu'il faut pour qu'une mesure reste comparable dans six mois."""
    return {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "machine": f"{platform.system()} {platform.machine()}",
        "processeurs": platform.processor() or "inconnu",
        "python": platform.python_version(),
        "duckdb": duckdb.__version__,
        "fichier": str(fichier.relative_to(RACINE)),
        "taille_octets": fichier.stat().st_size,
        "taille_mo": round(fichier.stat().st_size / 1e6, 1),
    }


def executer(con: duckdb.DuckDBPyConnection, sql: str) -> tuple[dict[str, Any], float]:
    """Execute une requete et renvoie son resultat nomme plus sa duree en secondes."""
    debut = time.perf_counter()
    resultat = con.sql(sql)
    colonnes = resultat.columns
    valeurs = resultat.fetchone()
    duree = time.perf_counter() - debut
    if valeurs is None:
        return {}, duree
    return dict(zip(colonnes, valeurs, strict=True)), duree


def main() -> None:
    if not FICHIER.exists():
        message = f"Fichier absent : {FICHIER}. Lancer d'abord `make donnees-decp`."
        raise SystemExit(message)

    con = duckdb.connect()
    # Le fichier est enregistre comme table nommee `decp`. On passe par l'API Python plutot que
    # par une requete construite avec le chemin en clair : aucune chaine n'est interpolee dans du
    # SQL, donc aucune injection possible, meme si le chemin venait un jour d'un argument.
    con.register("decp", con.read_parquet(str(FICHIER)))

    rapport: dict[str, Any] = {"contexte": contexte(FICHIER), "mesures": {}}
    lignes_csv: list[dict[str, Any]] = []

    for nom, question, sql in MESURES:
        valeurs, duree = executer(con, sql)
        rapport["mesures"][nom] = {
            "question": question,
            "duree_secondes": round(duree, 4),
            "valeurs": {c: str(v) for c, v in valeurs.items()},
        }
        print(f"{nom:<30} {duree:>7.3f} s   {valeurs}")
        for colonne, valeur in valeurs.items():
            lignes_csv.append(
                {
                    "mesure": nom,
                    "indicateur": colonne,
                    "valeur": valeur,
                    "duree_secondes": round(duree, 4),
                    "date": rapport["contexte"]["date"],
                }
            )

    SORTIE.mkdir(parents=True, exist_ok=True)
    jour = datetime.now(UTC).date().isoformat()
    chemin_json = SORTIE / f"{jour}-decp-qualite.json"
    chemin_csv = SORTIE / f"{jour}-decp-qualite.csv"

    # Le retour a la ligne final est exige par la verification pre-commit, et c'est la convention
    # POSIX pour un fichier texte.
    chemin_json.write_text(
        json.dumps(rapport, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with chemin_csv.open("w", newline="", encoding="utf-8") as sortie:
        # lineterminator force les fins de ligne Unix : par defaut, le module csv ecrit en CRLF,
        # ce qui produit des differences inutiles dans git sur une machine Unix.
        auteur = csv.DictWriter(sortie, fieldnames=list(lignes_csv[0].keys()), lineterminator="\n")
        auteur.writeheader()
        auteur.writerows(lignes_csv)

    print(f"\nEcrit : {chemin_json.relative_to(RACINE)}")
    print(f"Ecrit : {chemin_csv.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
