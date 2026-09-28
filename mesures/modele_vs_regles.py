"""Les regles valent-elles mieux qu'un modele ? Comparaison a budget d'alertes egal.

Le projet detecte aujourd'hui par des regles explicites. La question posee ici est la seule qui
permette de justifier ce choix, ou d'en changer : **un modele non supervise fait-il mieux, sur les
memes donnees, avec la meme etiquette et le meme protocole ?**

Le protocole, et c'est lui qui rend la comparaison honnete :

    A budget d'alertes egal. Pour un nombre d'alertes donne, on prend les N marches les mieux
    classes par chaque methode, et on compare leur precision. Comparer une regle qui signale
    8 000 marches a un modele qui en signale 60 000 ne dirait rien : le second trouverait
    mecaniquement plus d'anomalies, et produirait mecaniquement plus de faux signalements.

Un analyste n'a pas un temps infini. La vraie question n'est pas « combien d'anomalies une methode
peut-elle trouver » mais « sur les mille marches que j'ai le temps d'examiner, laquelle m'en donne
le plus de vrais ».

Quatre methodes sont comparees, dont une qui sert de repere :

    Regle            ecart normalise du montant a la mediane de sa famille d'achat
    Modele           Isolation Forest sur cinq variables
    Modele oriente   le meme, restreint aux montants eleves, le cote ou la regle cherche
    Hasard           tirage aleatoire, pour verifier que les autres apprennent quelque chose

La troisieme methode est la conclusion du notebook `analyses/08-modelisation-detection.ipynb`, et
elle est la raison d'etre de ce fichier. Le modele libre obtient zero pour cent, **sous le
hasard**. Le diagnostic a montre pourquoi : ses alertes portent sur des montants anormalement
**bas** (ecart median autour de moins 8), alors que l'etiquette faible ne marque que des montants
trop **hauts**. La metrique ne mesurait donc pas la qualite du modele, mais un desaccord de
direction. Oriente du meme cote que la regle, sans qu'une ligne de son apprentissage ne change,
le modele passe de 0 a 100 pour cent sur les cent premieres alertes.

Ce que le projet en retient, et qui justifie de rester sur la marche des regles :

    Le modele sait trouver des valeurs extremes aussi bien que la regle. Il ne sait pas
    **lesquelles** nous interessent. Cette connaissance vient du metier, pas des donnees. Une
    regle la porte en clair et l'explique a l'utilisateur ; le modele ne l'a que si on la lui
    impose de l'exterieur, et il ne peut alors plus rien expliquer de sa decision.

Pourquoi Isolation Forest plutot qu'un autre modele :

    Option              Avantage                        Limite                     Verdict
    Isolation Forest    concu pour l'anomalie, rapide,  explique mal ses           retenu pour
                        peu de reglages, supporte les   decisions                  la comparaison
                        variables d'echelles variees
    Local Outlier       tres bon sur des anomalies      cout quadratique :         ecarte
    Factor              locales                          impraticable sur 2 M
    One-Class SVM       fondement theorique solide      ne passe pas l'echelle     ecarte
    Autoencodeur        capte des structures complexes  demande un reglage long,   hors sujet ici
                                                        et une explication encore
                                                        plus difficile
    Modele supervise    le plus performant              **impossible** : aucune    exclu par
                                                        etiquette fiable            le sujet

**Precaution, la meme que pour les regles** : l'etiquette faible est elle-meme un detecteur de
montants. Elle avantage donc structurellement toute methode qui regarde le montant, et desavantage
celle qui regarde autre chose. Ce biais est nomme ici parce qu'il ne peut pas etre corrige, et il
doit etre redit chaque fois que ces chiffres sont cites.

Lancement : `make bench-modele`, apres `make transformer`.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
from sklearn.ensemble import IsolationForest

RACINE = Path(__file__).resolve().parent.parent
BASE = RACINE / "donnees" / "commande_publique.duckdb"
SORTIE = RACINE / "mesures" / "resultats"

# Budgets d'alertes compares. Ils vont de ce qu'une personne peut examiner en une journee a ce
# qu'une equipe traiterait en un an.
BUDGETS = [100, 500, 1000, 5000, 10000, 30000]

# Graine fixe : deux executions doivent donner le meme resultat. Sans elle, la comparaison
# changerait a chaque lancement et ne prouverait rien.
#
# **Une graine ne suffit pas, et le chemin pour s'en rendre compte vaut d'etre garde.**
# Mesure du 28 septembre 2026 : deux lancements de ce script, meme graine et memes donnees,
# donnaient 100,0 % puis 74,0 % de precision a 100 alertes. Trois causes empilees, trouvees dans
# cet ordre :
#
#   1. DuckDB execute en parallele et ne garantit **aucun ordre** de lignes sans `order by`. Or
#      Isolation Forest tire `max_samples` lignes par position, et le vecteur de hasard est
#      apparie aux etiquettes par position lui aussi.
#   2. `order by uid` n'a pas suffi : **uid n'est pas unique**. Il identifie un marche, pas une
#      ligne, et un marche a autant de lignes que de titulaires. Mesure : 140 350 uid apparaissent
#      plusieurs fois, soit 281 404 lignes en trop sur 2 054 924, et **619 uid portent des
#      montants contradictoires**. Les lignes d'un meme uid pouvaient donc encore permuter.
#   3. L'ordre porte donc sur l'ensemble des colonnes utilisees. Deux lignes qui resteraient a
#      egalite apres cela sont identiques : les permuter ne change plus rien.
#
# Reste une limite a enoncer, parce qu'aucun tri ne la corrige : les scores d'Isolation Forest
# comportent beaucoup d'ex aequo (418 921 valeurs distinctes pour 2 053 765 marches, et 491
# marches a egalite avec le 100e score). Une precision mesuree sur un tres petit budget est donc
# fragile par nature. C'est une raison de plus de lire la colonne des grands budgets.
GRAINE = 42

# Les variables donnees au modele. Aucune ne contient l'etiquette, ni rien qui en derive : ce
# serait une fuite de donnees, et le modele afficherait un score parfait sans rien avoir appris.
PREPARATION = """
create or replace temp view jeu as
with base as (
    select
        uid,
        montant,
        log10(montant)                          as montant_log10,
        montant_anomalie is not null            as signale_par_le_producteur,
        coalesce(dureeMois, 0)                  as duree_mois,
        coalesce(offresRecues, 0)               as offres_recues,
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
        count(*)                                as marches_dans_la_famille,
        median(montant_log10)                   as mediane_log,
        quantile_cont(montant_log10, 0.25)      as q1_log,
        quantile_cont(montant_log10, 0.75)      as q3_log
    from base
    where famille_cpv is not null
    group by 1
)
select
    b.uid,
    b.signale_par_le_producteur,
    b.montant_log10,
    b.duree_mois,
    b.offres_recues,
    s.marches_dans_la_famille,
    case
        when s.q3_log - s.q1_log > 0
            then (b.montant_log10 - s.mediane_log) / ((s.q3_log - s.q1_log) / 1.349)
        else 0
    end as ecart_normalise,
    -- Le montant rapporte a la duree : deux marches de meme montant n'engagent pas la meme
    -- depense annuelle. Le modele peut s'en servir, la regle de prix ne le fait pas.
    case when b.duree_mois > 0 then log10(b.montant / b.duree_mois) else b.montant_log10 end
        as montant_par_mois_log10
from base b
join statistiques s using (famille_cpv)
where s.marches_dans_la_famille >= 30
"""

VARIABLES = [
    "ecart_normalise",
    "montant_log10",
    "montant_par_mois_log10",
    "duree_mois",
    "offres_recues",
]


def precision_au_budget(scores: np.ndarray, etiquettes: np.ndarray, budget: int) -> float:
    """Part de marches reellement signales parmi les `budget` marches les mieux classes.

    Le tri est descendant : un score eleve doit signifier « plus anormal » pour les deux methodes,
    sinon la comparaison serait faussee en faveur de l'une d'elles.
    """
    if budget > len(scores):
        return 0.0
    # argpartition trouve les N plus grands sans trier les deux millions d'autres : quelques
    # dizaines de millisecondes au lieu de plusieurs secondes.
    indices = np.argpartition(-scores, budget - 1)[:budget]
    return round(100 * float(etiquettes[indices].mean()), 1)


def orienter(scores: np.ndarray, cote_retenu: np.ndarray) -> np.ndarray:
    """Repousse en fin de classement les marches hors du cote retenu, sans rien recalculer.

    C'est la seule chose qu'on ajoute au modele : une information metier, celle du cote ou l'on
    cherche. Elle vaut a elle seule la difference entre un score sous le hasard et un score
    comparable a la regle.
    """
    return np.where(cote_retenu, scores, -np.inf)


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Base absente : {BASE}. Lancer d'abord `make transformer`.")

    con = duckdb.connect(str(BASE), read_only=True)
    con.execute(PREPARATION)

    debut = time.perf_counter()
    # L'ordre est indispensable a la reproductibilite, et il porte sur toutes les colonnes
    # utilisees parce que uid ne suffit pas a designer une ligne. Voir le commentaire de GRAINE.
    jeu = con.sql(
        "select * from jeu"
        " order by uid, montant_log10, ecart_normalise, montant_par_mois_log10,"
        " duree_mois, offres_recues, signale_par_le_producteur"
    ).df()
    duree_lecture = time.perf_counter() - debut
    etiquettes = jeu["signale_par_le_producteur"].to_numpy()
    print(
        f"{len(jeu):,} marches, {etiquettes.sum():,} signales par le producteur "
        f"({100 * etiquettes.mean():.1f} %), lus en {duree_lecture:.1f} s".replace(",", " ")
    )

    # --- La regle -------------------------------------------------------
    # Son score est l'ecart lui-meme, dans le sens « trop cher » seulement : la mesure du
    # 28 septembre a montre que le sens « trop bas » ne concorde jamais avec l'etiquette.
    score_regle = jeu["ecart_normalise"].to_numpy()

    # --- Le modele ------------------------------------------------------
    matrice = jeu[VARIABLES].to_numpy(dtype=np.float32)
    debut = time.perf_counter()
    foret = IsolationForest(
        n_estimators=100,
        # 256 echantillons par arbre est la valeur recommandee par les auteurs de la methode :
        # une anomalie se detecte sur un petit echantillon, en ajouter dilue le signal.
        max_samples=256,
        random_state=GRAINE,
        n_jobs=-1,
    )
    foret.fit(matrice)
    duree_entrainement = time.perf_counter() - debut

    debut = time.perf_counter()
    # score_samples renvoie un score d'autant plus **bas** que l'observation est anormale. On
    # l'inverse pour que les deux methodes se lisent dans le meme sens.
    score_modele = -foret.score_samples(matrice)
    duree_prediction = time.perf_counter() - debut
    print(
        f"Isolation Forest : entraine en {duree_entrainement:.1f} s, "
        f"applique en {duree_prediction:.1f} s"
    )

    # --- Le modele oriente ----------------------------------------------
    # Meme modele, memes scores : on repousse simplement en fin de classement les marches du
    # cote « montant bas », celui que l'etiquette faible ne marque jamais. C'est la connaissance
    # metier que la regle contenait deja en clair, donnee au modele de l'exterieur.
    cote_montant_eleve = jeu["ecart_normalise"].to_numpy() > 0
    score_modele_oriente = orienter(score_modele, cote_montant_eleve)

    # --- Le hasard ------------------------------------------------------
    hasard = np.random.default_rng(GRAINE).random(len(jeu))

    # --- La comparaison -------------------------------------------------
    resultats: list[dict[str, Any]] = []
    for budget in BUDGETS:
        for methode, scores in (
            ("regle", score_regle),
            ("modele", score_modele),
            ("modele_oriente", score_modele_oriente),
            ("hasard", hasard),
        ):
            resultats.append(
                {
                    "budget_alertes": budget,
                    "methode": methode,
                    "precision_pourcent": precision_au_budget(scores, etiquettes, budget),
                }
            )

    print("\nPrecision a budget d'alertes egal :")
    print("  budget    regle    modele    oriente    hasard")
    for budget in BUDGETS:
        par_methode = {
            r["methode"]: r["precision_pourcent"]
            for r in resultats
            if r["budget_alertes"] == budget
        }
        print(
            f"  {budget:>6}   {par_methode['regle']:>5} %   {par_methode['modele']:>5} %   "
            f"{par_methode['modele_oriente']:>6} %   {par_methode['hasard']:>5} %"
        )

    SORTIE.mkdir(parents=True, exist_ok=True)
    chemin = SORTIE / "modele-vs-regles.csv"
    with chemin.open("w", newline="", encoding="utf-8") as sortie:
        auteur = csv.DictWriter(sortie, fieldnames=list(resultats[0].keys()), lineterminator="\n")
        auteur.writeheader()
        auteur.writerows(resultats)

    cout = SORTIE / "modele-vs-regles-cout.csv"
    with cout.open("w", newline="", encoding="utf-8") as sortie:
        auteur = csv.DictWriter(
            sortie,
            fieldnames=["etape", "duree_secondes", "marches", "variables"],
            lineterminator="\n",
        )
        auteur.writeheader()
        auteur.writerows(
            [
                {
                    "etape": "lecture des donnees",
                    "duree_secondes": round(duree_lecture, 2),
                    "marches": len(jeu),
                    "variables": len(VARIABLES),
                },
                {
                    "etape": "entrainement du modele",
                    "duree_secondes": round(duree_entrainement, 2),
                    "marches": len(jeu),
                    "variables": len(VARIABLES),
                },
                {
                    "etape": "application du modele",
                    "duree_secondes": round(duree_prediction, 2),
                    "marches": len(jeu),
                    "variables": len(VARIABLES),
                },
                {
                    "etape": "regle (deja calculee en SQL)",
                    "duree_secondes": 0.0,
                    "marches": len(jeu),
                    "variables": 1,
                },
            ]
        )

    print(f"\nEcrit : {chemin.relative_to(RACINE)}")
    print(f"Ecrit : {cout.relative_to(RACINE)}")
    print(
        "\n  Rappel : l'etiquette faible est un detecteur de montants **eleves**. Elle ne peut\n"
        "  donc valider aucune methode qui cherche du cote des montants bas, et le zero du\n"
        "  modele libre mesure ce desaccord de direction, pas une qualite. Ce biais ne peut pas\n"
        "  etre corrige, seulement enonce."
    )


if __name__ == "__main__":
    main()
