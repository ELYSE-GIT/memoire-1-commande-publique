"""Evaluation de la detection par regles.

Une regle de detection qui n'est pas evaluee ne vaut rien : elle signale des marches, et personne
ne sait si elle a raison. Le probleme, sur ce sujet, est qu'**il n'existe aucune verite de
reference**. Personne ne publie la liste des marches irreguliers.

Ce script utilise donc une **etiquette faible** : les montants que le producteur des donnees
signale lui-meme comme suspects ou aberrants. Elle est imparfaite, et sa limite doit etre dite
clairement.

    Ce que l'etiquette faible permet         Ce qu'elle ne permet pas
    comparer plusieurs seuils entre eux      affirmer un taux d'erreur absolu
    voir le compromis precision et rappel    conclure qu'un marche est irregulier
    justifier un choix par un chiffre        remplacer un controle humain

**La precision mesuree est un minorant.** L'etiquette est elle-meme produite par un detecteur : un
marche que nous signalons sans qu'il l'ait signale peut etre une anomalie qu'il a manquee, et non
une erreur de notre part. Annoncer « 75,8 % de precision » sans cette precaution serait malhonnete.

Pourquoi evaluer sur la couche argent et non sur la couche or :

    Option              Avantage                        Limite                    Verdict
    Couche argent       contient encore les lignes      il faut recalculer la     retenu
                        signalees, donc l'etiquette     variable de prix
    Couche or           la variable existe deja         les lignes signalees en   impossible
                                                        ont ete retirees : plus
                                                        d'etiquette a comparer

C'est une consequence logique du nettoyage : ce qui a ete ecarte ne peut plus servir a evaluer ce
qui l'a ecarte. L'evaluation remonte donc d'une couche.

Lancement : `make bench-detection`, apres `make transformer`.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import duckdb

RACINE = Path(__file__).resolve().parent.parent
BASE = RACINE / "donnees" / "commande_publique.duckdb"
SORTIE = RACINE / "mesures" / "resultats"

# Seuils evalues. Ils encadrent largement le choix retenu, pour que la table montre le compromis
# et pas seulement le point d'arrivee.
SEUILS = [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]

# Taille minimale d'un groupe de comparaison. En dessous, la mediane est calculee sur trop peu de
# marches, dont celui que l'on examine : on le compare en partie a lui-meme.
TAILLE_MINIMALE_GROUPE = 30

# La variable de prix, recalculee sur la couche argent. Le calcul reproduit exactement celui de
# `or_variables.sql` : ecart au logarithme median de la famille, normalise par l'ecart
# interquartile. Les deux definitions doivent rester identiques, et le test le verifie.
PREPARATION = """
create or replace temp view evaluation as
with base as (
    select
        uid,
        montant,
        log10(montant) as montant_log10,
        montant_anomalie,
        case
            when regexp_matches(coalesce(trim(codeCPV), ''), '^[0-9]{2}')
                then substr(trim(codeCPV), 1, 2)
        end as famille_cpv
    from argent_marches
    where montant > 0 and montant <= 1e12
),
statistiques as (
    select
        famille_cpv,
        count(*)                            as marches_dans_la_famille,
        median(montant_log10)               as mediane_log,
        quantile_cont(montant_log10, 0.25)  as q1_log,
        quantile_cont(montant_log10, 0.75)  as q3_log
    from base
    where famille_cpv is not null
    group by 1
)
select
    b.uid,
    b.montant,
    b.montant_anomalie is not null as signale_par_le_producteur,
    s.marches_dans_la_famille,
    case
        when s.q3_log - s.q1_log > 0
            then (b.montant_log10 - s.mediane_log) / ((s.q3_log - s.q1_log) / 1.349)
    end as ecart_normalise
from base b
join statistiques s using (famille_cpv)
"""

# Trois directions, evaluees separement. Les melanger dans une valeur absolue a ete la premiere
# erreur de ce module : la direction « trop bas » ne concorde jamais avec l'etiquette, et noyait
# la direction « trop cher », qui elle concorde. Chaque requete est ecrite en entier, le seuil
# reste un parametre.
EVALUATIONS: dict[str, str] = {
    "trop cher": """
        select
            count(*)                                                   as marches_evalues,
            sum(case when ecart_normalise > ? then 1 else 0 end)       as signales,
            sum(case when ecart_normalise > ? and signale_par_le_producteur then 1 else 0 end)
                                                                       as concordants,
            sum(case when signale_par_le_producteur then 1 else 0 end) as etiquetes
        from evaluation
        where marches_dans_la_famille >= ?
    """,
    "trop bas": """
        select
            count(*)                                                   as marches_evalues,
            sum(case when ecart_normalise < -? then 1 else 0 end)      as signales,
            sum(case when ecart_normalise < -? and signale_par_le_producteur then 1 else 0 end)
                                                                       as concordants,
            sum(case when signale_par_le_producteur then 1 else 0 end) as etiquetes
        from evaluation
        where marches_dans_la_famille >= ?
    """,
    "les deux": """
        select
            count(*)                                                   as marches_evalues,
            sum(case when abs(ecart_normalise) > ? then 1 else 0 end)  as signales,
            sum(case when abs(ecart_normalise) > ? and signale_par_le_producteur then 1 else 0 end)
                                                                       as concordants,
            sum(case when signale_par_le_producteur then 1 else 0 end) as etiquetes
        from evaluation
        where marches_dans_la_famille >= ?
    """,
}


def evaluer(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Pour chaque seuil : combien de marches signales, et quelle part concorde."""
    con.execute(PREPARATION)
    resultats: list[dict[str, Any]] = []
    for sens, requete in EVALUATIONS.items():
        for seuil in SEUILS:
            ligne = con.execute(requete, [seuil, seuil, TAILLE_MINIMALE_GROUPE]).fetchone()
            if ligne is None:
                # `assert` serait plus court, mais il disparait quand Python tourne optimise :
                # le controle ne protegerait plus rien en production.
                message = f"la requete « {sens} » n'a rien renvoye"
                raise RuntimeError(message)
            evalues, signales, concordants, etiquetes = ligne
            resultats.append(
                {
                    "sens": sens,
                    "seuil": seuil,
                    "marches_evalues": evalues,
                    "signales": signales,
                    "concordants": concordants,
                    "precision_pourcent": (
                        round(100 * concordants / signales, 1) if signales else 0.0
                    ),
                    "rappel_pourcent": (
                        round(100 * concordants / etiquetes, 1) if etiquetes else 0.0
                    ),
                    "part_signalee_pourcent": (
                        round(100 * signales / evalues, 2) if evalues else 0.0
                    ),
                }
            )
    return resultats


def compter_signaux(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Combien de marches chaque signal designe, et combien en cumulent plusieurs."""
    ligne = con.execute("""
        select
            count(*)                                                     as marches,
            sum(case when prix_tres_eleve then 1 else 0 end)             as prix_tres_eleve,
            sum(case when prix_eleve_a_verifier then 1 else 0 end)        as prix_eleve_a_verifier,
            sum(case when prix_tres_bas_non_evalue then 1 else 0 end)     as prix_tres_bas,
            sum(case when offre_unique_sur_gros_marche then 1 else 0 end) as offre_unique,
            sum(case when titulaire_dominant then 1 else 0 end)          as titulaire_dominant,
            sum(case when signaux_forts >= 1 then 1 else 0 end)          as au_moins_un,
            sum(case when signaux_forts >= 2 then 1 else 0 end)          as au_moins_deux
        from or_signaux
    """).fetchone()
    if ligne is None:
        message = "le comptage des signaux n'a rien renvoye : la table or_signaux est-elle vide ?"
        raise RuntimeError(message)
    noms = [
        "marches",
        "prix_tres_eleve",
        "prix_eleve_a_verifier",
        "prix_tres_bas",
        "offre_unique",
        "titulaire_dominant",
        "au_moins_un",
        "au_moins_deux",
    ]
    total = ligne[0]
    return [
        {"signal": nom, "marches": valeur, "part_pourcent": round(100 * valeur / total, 2)}
        for nom, valeur in zip(noms, ligne, strict=True)
        if nom != "marches"
    ]


def ecrire(nom: str, lignes: list[dict[str, Any]]) -> Path:
    """Ecrit une mesure en CSV, fins de ligne Unix et retour a la ligne final."""
    SORTIE.mkdir(parents=True, exist_ok=True)
    chemin = SORTIE / f"{nom}.csv"
    with chemin.open("w", newline="", encoding="utf-8") as sortie:
        auteur = csv.DictWriter(sortie, fieldnames=list(lignes[0].keys()), lineterminator="\n")
        auteur.writeheader()
        auteur.writerows(lignes)
    return chemin


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Base absente : {BASE}. Lancer d'abord `make transformer`.")

    con = duckdb.connect(str(BASE), read_only=True)

    evaluation = evaluer(con)
    print("Regle de prix, evaluee contre les anomalies signalees par le producteur :")
    print("  sens        seuil   signales   concordants   precision   rappel")
    for ligne in evaluation:
        signales = f"{ligne['signales']:,}".replace(",", " ")
        concordants = f"{ligne['concordants']:,}".replace(",", " ")
        print(
            f"  {ligne['sens']:<10}  {ligne['seuil']:>5}   {signales:>8}   {concordants:>11}   "
            f"{ligne['precision_pourcent']:>8} %   {ligne['rappel_pourcent']:>5} %"
        )
    print(
        "\n  Rappel : la precision est un minorant. L'etiquette est elle-meme un detecteur,\n"
        "  et un marche signale sans qu'il l'ait signale peut etre une anomalie qu'il a manquee."
    )

    signaux = compter_signaux(con)
    print("\nMarches designes par chaque signal :")
    for signal in signaux:
        marches = f"{signal['marches']:,}".replace(",", " ")
        print(f"  {marches:>9} ({signal['part_pourcent']:>5} %)   {signal['signal']}")

    for nom, lignes in (("detection-seuils", evaluation), ("detection-signaux", signaux)):
        print(f"Ecrit : {ecrire(nom, lignes).relative_to(RACINE)}")


if __name__ == "__main__":
    main()
