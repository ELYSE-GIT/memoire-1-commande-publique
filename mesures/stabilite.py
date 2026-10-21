"""Stabilite temporelle de la detection : une regle calee sur le passe tient-elle sur la suite ?

La regle de prix du projet compare un marche a la mediane de sa famille d'achat. Cette mediane,
cet ecart interquartile et le seuil sont des **parametres**, et ils sont aujourd'hui estimes sur
l'ensemble des annees, y compris celles que la regle doit juger. Un marche de 2026 est donc compare
a une mediane qu'il a lui-meme contribue a former.

C'est une fuite de donnees, legere mais reelle, et c'est la premiere chose qu'un statisticien
cherche dans un modele. Le probleme n'est pas qu'elle fausse enormement le resultat ici : c'est
qu'on ne le savait pas, faute de l'avoir mesure. Ce module repond a deux questions distinctes :

  1. **La fuite change-t-elle la mesure ?** On recalcule les references sur les seules annees
     d'apprentissage, on applique la regle aux annees suivantes, et on compare a la version
     actuelle. Si la precision s'effondre, la mesure publiee est surevaluee.
  2. **Les references bougent-elles dans le temps ?** Si la mediane de prix d'une famille d'achat
     se deplace entre deux periodes, une regle calee une fois pour toutes se desaccorde
     silencieusement. On mesure le deplacement, famille par famille.

Pourquoi un decoupage par date plutot qu'un tirage au hasard :

    Option              Avantage                        Limite                    Verdict
    Decoupage par       reproduit la seule situation    les periodes n'ont pas    retenu
    date                reelle : on juge des marches    le meme volume ni la
                        posterieurs au calage           meme inflation
    Tirage au hasard    periodes equilibrees,           **autorise le futur a     exclu
    (train/test)        variance plus faible            calibrer le passe** :
                                                        mesure impossible a
                                                        reproduire en production
    Validation croisee  utilise toute la donnee         meme defaut que le        exclu
    par blocs melanges                                  tirage au hasard
    Validation croisee  correcte, et plus stable        plusieurs recalculs       ecartee pour
    glissante dans le   qu'un decoupage unique          complets sur deux         l'instant, notee
    temps                                               millions de lignes        comme suite

Le decoupage glissant est la suite logique de ce module. Il est ecarte maintenant pour une raison
mesurable, pas par principe : un decoupage unique suffit a repondre oui ou non a la question
« la fuite change-t-elle la mesure », et c'est cette question qui bloque la redaction du
chapitre 8.

Pourquoi evaluer sur la couche argent : meme raison que `detection.py`. La couche or a retire les
lignes signalees par le producteur, donc l'etiquette faible n'y existe plus. Ce qui a ete ecarte
ne peut pas servir a evaluer ce qui l'a ecarte.

Lancement : `make bench-stabilite`, apres `make transformer`. Aucun conteneur, aucun reseau :
le module lit la base DuckDB locale en lecture seule.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import duckdb

# L'intervalle vient du module d'incertitude, il n'est pas recopie ici. Une precision de
# 53,1 % sur 1 423 marches signales et une de 81,7 % sur 1 597 ne se comparent pas a l'oeil :
# il faut savoir si leurs intervalles se chevauchent. Les deux mesures du jour se repondent
# donc l'une a l'autre.
from mesures.incertitude import wilson

RACINE = Path(__file__).resolve().parent.parent
BASE = RACINE / "donnees" / "commande_publique.duckdb"
RESULTATS = RACINE / "mesures" / "resultats"

# Periode d'apprentissage et periode de test. La coupure est posee a la fin de 2023 pour deux
# raisons : elle laisse cinq annees completes pour estimer les references, et les trois annees
# suivantes representent presque la moitie des marches, donc le test n'est pas anecdotique.
# Les annees anterieures a 2019 sont ecartees : moins de 23 000 marches en tout, contre 141 903
# pour la seule annee 2019. Les y inclure melangerait un regime de collecte different.
PREMIERE_ANNEE = 2019
FIN_APPRENTISSAGE = 2023
DERNIERE_ANNEE = 2026

# Seuil et taille minimale de famille, repris **a l'identique** du modele de production
# `or_signaux.sql`. Mesurer la stabilite d'une autre regle que celle qui tourne n'aurait aucun
# interet ; un test verifie que les deux valeurs concordent avec le fichier SQL.
SEUIL = 4.0
TAILLE_MINIMALE_GROUPE = 30

# Deplacement de mediane juge notable, en log decimal. 0,1 en log10 vaut un facteur 1,26, soit
# 26 % de prix : en dessous, le deplacement se confond avec le bruit d'echantillonnage d'une
# famille de quelques centaines de marches.
DEPLACEMENT_NOTABLE = 0.1

SOCLE = """
create or replace temp view socle as
select
    uid,
    montant,
    log10(montant)                          as montant_log10,
    montant_anomalie is not null            as signale_par_le_producteur,
    year(try_cast(dateNotification as date)) as annee,
    case
        when regexp_matches(coalesce(trim(codeCPV), ''), '^[0-9]{2}')
            then substr(trim(codeCPV), 1, 2)
    end                                     as famille_cpv
from argent_marches
where montant > 0 and montant <= 1e12
"""

# Deux jeux de references, construits par la meme requete a une clause de date pres. Ecrire la
# requete deux fois inviterait les deux definitions a diverger ; elle est donc parametree par les
# bornes d'annees, et appelee avec les bornes completes pour la version globale.
#
# Les bornes sont inserees dans le texte de la requete, et non passees comme parametres : DuckDB
# refuse de preparer un `create view`. Elles passent donc par `int()` juste avant, ce qui garantit
# que seule une annee entiere peut y entrer. Aucune de ces valeurs ne vient d'une saisie
# exterieure, ce sont des constantes du module, mais la conversion reste ecrite pour que la
# garantie soit dans le code et pas seulement dans ce commentaire.
REFERENCES = """
create or replace temp view {nom} as
select
    famille_cpv,
    count(*)                           as marches,
    median(montant_log10)              as mediane_log,
    quantile_cont(montant_log10, 0.25) as q1_log,
    quantile_cont(montant_log10, 0.75) as q3_log
from socle
where famille_cpv is not null and annee between {debut:d} and {fin:d}
group by 1
"""

# L'ecart normalise, calcule contre un jeu de references donne. Le facteur 1,349 convertit un
# ecart interquartile en equivalent d'ecart type, comme dans `or_variables.sql`.
EVALUATION = """
create or replace temp view {nom} as
select
    s.uid,
    s.annee,
    s.signale_par_le_producteur,
    r.marches as marches_dans_la_famille,
    case
        when r.q3_log - r.q1_log > 0
            then (s.montant_log10 - r.mediane_log) / ((r.q3_log - r.q1_log) / 1.349)
    end as ecart_normalise
from socle s
join {references} r using (famille_cpv)
"""

RESUME = """
select
    count(*)                                                   as marches_evalues,
    sum(case when ecart_normalise > ? then 1 else 0 end)       as signales,
    sum(case when ecart_normalise > ? and signale_par_le_producteur then 1 else 0 end)
                                                               as concordants,
    sum(case when signale_par_le_producteur then 1 else 0 end) as etiquetes
from {vue}
where marches_dans_la_famille >= ? and annee between ? and ?
"""

PAR_ANNEE = """
select
    annee,
    count(*)                                                   as marches_evalues,
    sum(case when ecart_normalise > ? then 1 else 0 end)       as signales,
    sum(case when ecart_normalise > ? and signale_par_le_producteur then 1 else 0 end)
                                                               as concordants,
    sum(case when signale_par_le_producteur then 1 else 0 end) as etiquetes
from evaluation_apprentissage
where marches_dans_la_famille >= ? and annee between ? and ?
group by 1
order by 1
"""

# Desaccords de decision entre les deux calibrages, sur la periode de test. C'est le chiffre le
# plus concret du module : combien de marches changent d'avis, et dans quel sens.
DESACCORDS = """
select
    sum(case when g.ecart_normalise > ? and a.ecart_normalise <= ? then 1 else 0 end)
        as signales_seulement_par_le_calibrage_global,
    sum(case when g.ecart_normalise <= ? and a.ecart_normalise > ? then 1 else 0 end)
        as signales_seulement_par_le_calibrage_apprentissage,
    sum(case when g.ecart_normalise > ? and a.ecart_normalise > ? then 1 else 0 end)
        as signales_par_les_deux,
    count(*) as marches_compares
from evaluation_globale g
join evaluation_apprentissage a using (uid)
where g.marches_dans_la_famille >= ?
  and a.marches_dans_la_famille >= ?
  and g.annee between ? and ?
"""

DERIVE_DES_FAMILLES = """
select
    a.famille_cpv,
    a.marches                                    as marches_apprentissage,
    t.marches                                    as marches_test,
    round(a.mediane_log, 4)                      as mediane_log_apprentissage,
    round(t.mediane_log, 4)                      as mediane_log_test,
    round(t.mediane_log - a.mediane_log, 4)      as deplacement_log,
    round(100 * (pow(10, t.mediane_log - a.mediane_log) - 1), 1) as deplacement_prix_pourcent,
    round(a.q3_log - a.q1_log, 4)                as ecart_interquartile_apprentissage,
    round(t.q3_log - t.q1_log, 4)                as ecart_interquartile_test
from references_apprentissage a
join references_test t using (famille_cpv)
where a.marches >= ? and t.marches >= ?
order by abs(t.mediane_log - a.mediane_log) desc
"""


def preparer(con: duckdb.DuckDBPyConnection) -> None:
    """Construit le socle, les trois jeux de references et les deux evaluations."""
    con.execute(SOCLE)
    for nom, debut, fin in (
        ("references_globales", PREMIERE_ANNEE, DERNIERE_ANNEE),
        ("references_apprentissage", PREMIERE_ANNEE, FIN_APPRENTISSAGE),
        ("references_test", FIN_APPRENTISSAGE + 1, DERNIERE_ANNEE),
    ):
        con.execute(REFERENCES.format(nom=nom, debut=int(debut), fin=int(fin)))
    con.execute(EVALUATION.format(nom="evaluation_globale", references="references_globales"))
    con.execute(
        EVALUATION.format(nom="evaluation_apprentissage", references="references_apprentissage")
    )


def mesurer(con: duckdb.DuckDBPyConnection, vue: str, debut: int, fin: int) -> dict[str, Any]:
    """Precision et rappel d'un calibrage sur une periode donnee."""
    ligne = con.execute(
        RESUME.format(vue=vue), [SEUIL, SEUIL, TAILLE_MINIMALE_GROUPE, debut, fin]
    ).fetchone()
    if ligne is None:
        message = f"la mesure de « {vue} » sur {debut}-{fin} n'a rien renvoye"
        raise RuntimeError(message)
    evalues, signales, concordants, etiquetes = ligne
    return {
        "marches_evalues": evalues,
        "signales": signales,
        "concordants": concordants,
        "etiquetes": etiquetes,
        "precision_pourcent": round(100 * concordants / signales, 1) if signales else 0.0,
        "precision_bas": round(wilson(concordants, signales)[0], 1),
        "precision_haut": round(wilson(concordants, signales)[1], 1),
        "rappel_pourcent": round(100 * concordants / etiquetes, 1) if etiquetes else 0.0,
        "part_signalee_pourcent": round(100 * signales / evalues, 3) if evalues else 0.0,
    }


def comparer_les_calibrages(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Les deux calibrages, chacun evalue sur la periode d'apprentissage puis sur celle de test.

    Les quatre lignes se lisent en croix. La diagonale « calage et evaluation sur la meme
    periode » est la mesure optimiste, celle que le projet publiait sans le savoir. La ligne
    « apprentissage calibre, test evalue » est la seule qui reproduise la situation reelle d'une
    regle en production : juger des marches posterieurs a son calage.
    """
    periodes = {
        "apprentissage": (PREMIERE_ANNEE, FIN_APPRENTISSAGE),
        "test": (FIN_APPRENTISSAGE + 1, DERNIERE_ANNEE),
    }
    calibrages = {
        "global (production actuelle)": "evaluation_globale",
        "apprentissage seul": "evaluation_apprentissage",
    }
    table: list[dict[str, Any]] = []
    for nom_calibrage, vue in calibrages.items():
        for nom_periode, (debut, fin) in periodes.items():
            mesure = mesurer(con, vue, debut, fin)
            table.append(
                {
                    "calibrage": nom_calibrage,
                    "periode_evaluee": nom_periode,
                    "annees": f"{debut}-{fin}",
                    "fuite": (
                        "oui"
                        if nom_calibrage.startswith("global") or nom_periode == "apprentissage"
                        else "non"
                    ),
                    **mesure,
                }
            )
    return table


def compter_les_desaccords(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Combien de marches les deux calibrages ne signalent pas de la meme facon."""
    ligne = con.execute(
        DESACCORDS,
        [
            SEUIL,
            SEUIL,
            SEUIL,
            SEUIL,
            SEUIL,
            SEUIL,
            TAILLE_MINIMALE_GROUPE,
            TAILLE_MINIMALE_GROUPE,
            FIN_APPRENTISSAGE + 1,
            DERNIERE_ANNEE,
        ],
    ).fetchone()
    if ligne is None:
        message = "le comptage des desaccords n'a rien renvoye"
        raise RuntimeError(message)
    global_seul, apprentissage_seul, les_deux, compares = ligne
    union = global_seul + apprentissage_seul + les_deux
    return {
        "marches_compares": compares,
        "signales_par_les_deux": les_deux,
        "signales_seulement_par_le_calibrage_global": global_seul,
        "signales_seulement_par_le_calibrage_apprentissage": apprentissage_seul,
        "desaccords": global_seul + apprentissage_seul,
        "part_de_desaccord_dans_l_union_pourcent": (
            round(100 * (global_seul + apprentissage_seul) / union, 1) if union else 0.0
        ),
    }


def derive_annuelle(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Precision annee par annee, avec les references calees sur l'apprentissage seul.

    Si la regle se degradait en vieillissant, la precision baisserait annee apres annee apres la
    coupure. C'est exactement ce qu'il faut regarder avant de laisser une regle tourner sans la
    recalibrer.
    """
    lignes = con.execute(
        PAR_ANNEE, [SEUIL, SEUIL, TAILLE_MINIMALE_GROUPE, PREMIERE_ANNEE, DERNIERE_ANNEE]
    ).fetchall()
    table: list[dict[str, Any]] = []
    for annee, evalues, signales, concordants, etiquetes in lignes:
        table.append(
            {
                "annee": annee,
                "periode": "apprentissage" if annee <= FIN_APPRENTISSAGE else "test",
                "marches_evalues": evalues,
                "signales": signales,
                "concordants": concordants,
                "etiquetes": etiquetes,
                "precision_pourcent": round(100 * concordants / signales, 1) if signales else 0.0,
                "precision_bas": round(wilson(concordants, signales)[0], 1),
                "precision_haut": round(wilson(concordants, signales)[1], 1),
                "rappel_pourcent": round(100 * concordants / etiquetes, 1) if etiquetes else 0.0,
                "part_signalee_pourcent": round(100 * signales / evalues, 3) if evalues else 0.0,
                # Part des marches que le producteur a lui-meme signales. Elle est publiee annee
                # par annee parce que la precision mesuree en depend directement : si le
                # producteur etiquette moins, nos signalements concordent moins, sans qu'aucune
                # regle ni aucun prix n'ait change. Separer les deux explications demande cette
                # colonne.
                "part_etiquetee_pourcent": round(100 * etiquetes / evalues, 2) if evalues else 0.0,
            }
        )
    return table


def derive_des_familles(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """De combien la mediane de prix de chaque famille se deplace entre les deux periodes."""
    colonnes = [
        "famille_cpv",
        "marches_apprentissage",
        "marches_test",
        "mediane_log_apprentissage",
        "mediane_log_test",
        "deplacement_log",
        "deplacement_prix_pourcent",
        "ecart_interquartile_apprentissage",
        "ecart_interquartile_test",
    ]
    lignes = con.execute(
        DERIVE_DES_FAMILLES, [TAILLE_MINIMALE_GROUPE, TAILLE_MINIMALE_GROUPE]
    ).fetchall()
    return [dict(zip(colonnes, ligne, strict=True)) for ligne in lignes]


def ecrire(nom: str, lignes: list[dict[str, Any]]) -> Path:
    """Ecrit une mesure en CSV, fins de ligne Unix."""
    RESULTATS.mkdir(parents=True, exist_ok=True)
    chemin = RESULTATS / f"{nom}.csv"
    with chemin.open("w", newline="", encoding="utf-8") as sortie:
        auteur = csv.DictWriter(sortie, fieldnames=list(lignes[0].keys()), lineterminator="\n")
        auteur.writeheader()
        auteur.writerows(lignes)
    return chemin


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Base absente : {BASE}. Lancer d'abord `make transformer`.")

    con = duckdb.connect(str(BASE), read_only=True)
    preparer(con)

    calibrages = comparer_les_calibrages(con)
    print(
        f"Regle de prix, seuil {SEUIL}, familles de {TAILLE_MINIMALE_GROUPE} marches minimum.\n"
        f"Apprentissage {PREMIERE_ANNEE}-{FIN_APPRENTISSAGE}, "
        f"test {FIN_APPRENTISSAGE + 1}-{DERNIERE_ANNEE}.\n"
    )
    print(
        "  calibrage                      periode          signales   precision   "
        "intervalle a 95 %   rappel   fuite"
    )
    for ligne in calibrages:
        signales = f"{ligne['signales']:,}".replace(",", " ")
        intervalle = f"[{ligne['precision_bas']:>5} ; {ligne['precision_haut']:>5}]"
        print(
            f"  {ligne['calibrage']:<30} {ligne['periode_evaluee']:<15}  {signales:>8}   "
            f"{ligne['precision_pourcent']:>8} %   {intervalle:>17}   "
            f"{ligne['rappel_pourcent']:>5} %   {ligne['fuite']:>5}"
        )

    desaccords = compter_les_desaccords(con)
    print("\nDesaccords entre les deux calibrages, sur la periode de test :")
    for cle, valeur in desaccords.items():
        affiche = f"{valeur:,}".replace(",", " ") if isinstance(valeur, int) else valeur
        print(f"  {affiche:>12}   {cle.replace('_', ' ')}")

    annees = derive_annuelle(con)
    print("\nPrecision annee par annee, references calees sur l'apprentissage seul :")
    print(
        "  annee   periode         signales   precision   intervalle a 95 %   rappel   "
        "etiquetes par le producteur"
    )
    for ligne in annees:
        signales = f"{ligne['signales']:,}".replace(",", " ")
        intervalle = f"[{ligne['precision_bas']:>5} ; {ligne['precision_haut']:>5}]"
        print(
            f"  {ligne['annee']:>5}   {ligne['periode']:<14}  {signales:>8}   "
            f"{ligne['precision_pourcent']:>8} %   {intervalle:>17}   "
            f"{ligne['rappel_pourcent']:>5} %   {ligne['part_etiquetee_pourcent']:>25} %"
        )

    familles = derive_des_familles(con)
    notables = [
        ligne for ligne in familles if abs(float(ligne["deplacement_log"])) >= DEPLACEMENT_NOTABLE
    ]
    print(
        f"\nDeplacement de la mediane de prix entre les deux periodes, "
        f"sur {len(familles)} familles d'achat :"
    )
    print(
        f"  {len(notables)} familles bougent de plus de {DEPLACEMENT_NOTABLE} en log decimal, "
        f"soit plus de {round(100 * (10**DEPLACEMENT_NOTABLE - 1))} % de prix"
    )
    print("  Les cinq plus mobiles :")
    for ligne in familles[:5]:
        print(
            f"    CPV {ligne['famille_cpv']}   {ligne['deplacement_prix_pourcent']:>7} % de prix   "
            f"({ligne['marches_apprentissage']} puis {ligne['marches_test']} marches)"
        )

    for nom, lignes in (
        ("stabilite-calibrage", calibrages),
        ("stabilite-desaccords", [desaccords]),
        ("stabilite-par-annee", annees),
        ("stabilite-familles", familles),
    ):
        print(f"\nEcrit : {ecrire(nom, lignes).relative_to(RACINE)}")


if __name__ == "__main__":
    main()
