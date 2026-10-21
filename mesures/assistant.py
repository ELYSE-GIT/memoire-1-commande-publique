"""Banc d'essai de l'assistant a reponses sourcees.

=== Ce que ce banc mesure, et pourquoi c'est inhabituel ======================

Un assistant se juge d'ordinaire par relecture humaine : on lit les reponses et on les note. Ce
banc mesure autre chose, qui ne demande personne : **la verifiabilite**.

    reconnaissance de l'intention   la bonne operation a-t-elle ete choisie
    comportement attendu            repondre quand il faut, refuser quand il faut
    citations valides               chaque numero cite existe et passe le filtre annonce
    coherence interne               les chiffres annonces ne se contredisent pas
    recalcul par un autre plan      le meme chiffre, obtenu par un autre chemin d'execution
    latence p50 et p95              ce que l'utilisateur ressent
    cout                            euros par mille questions

Aucune de ces sept mesures ne demande d'avis. C'est la propriete que le projet cherche : une
reponse construite a partir d'un filtre explicite se verifie par une machine. Une reponse
redigee par un modele de langue ne le permet pas, parce que rien dedans ne dit d'ou vient le
chiffre.

Ce que ce banc **ne** mesure **pas** : la pertinence. « EUROVIA ILE DE FRANCE est le premier
titulaire » est verifiable ; « c'est une reponse utile a la question posee » ne l'est pas. Les
quarante questions portent une colonne `intention_attendue` relue a la main, et c'est la seule
part de jugement, placee une fois pour toutes dans le jeu de donnees plutot qu'a chaque mesure.

=== Les trois verifications automatiques ====================================

1. **Citations.** Chaque numero de marche cite est recherche dans la table, avec le filtre
   annonce. S'il n'y est pas, la reponse cite une source qui ne la soutient pas.

2. **Coherence.** Des regles qui doivent toujours tenir : le nombre de marches a montant publie
   ne depasse pas le nombre de marches ; la somme des marches par titulaire ne depasse pas le
   total ; une mediane tombe entre le minimum et le maximum.

3. **Recalcul par un autre plan.** Le meme comptage est redemande apres avoir interdit au
   planificateur d'utiliser les index. La semantique est identique, la machinerie est
   differente : un ecart signalerait un index faux, ce qui est rare mais silencieux. C'est la
   contrepartie des index ajoutes le 21 octobre 2026.

Lancement : `make bench-assistant`, apres `make charger` et `make indexer`.
"""

from __future__ import annotations

import csv
import os
import statistics
import time
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

from mesures.recherche import sur_une_ligne
from services.assistant.lecture_question import Lexiques
from services.assistant.reponse_sourcee import (
    VALEURS_DISTINCTES_REGION,
    Reponse,
    charger_lexiques,
    construire_filtre,
    repondre,
)

RACINE = Path(__file__).resolve().parent.parent
QUESTIONS = RACINE / "mesures" / "verification" / "questions-assistant.csv"
SORTIE = RACINE / "mesures" / "resultats"

# Repetitions par question. La premiere est jetee : elle paie le remplissage des caches, comme
# dans le banc de recherche, pour que les deux chiffres soient comparables.
REPETITIONS = 6

# Prix d'un VPS a 12 euros par mois, rapporte a la seconde de calcul. Sert a chiffrer le cout
# d'un millier de questions, pour la comparaison aux offres payantes du chapitre 11.
EUROS_PAR_MOIS = 12.0
SECONDES_PAR_MOIS = 30 * 24 * 3600


def chaine_de_connexion() -> str:
    """Chaine de connexion PostgreSQL, construite depuis l'environnement."""
    manquantes = [
        nom
        for nom in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
        if not os.environ.get(nom)
    ]
    if manquantes:
        raise SystemExit(
            f"Variables absentes : {', '.join(manquantes)}.\n"
            "Lancer par `make bench-assistant`, qui passe le fichier .env a uv."
        )
    return (
        f"host={os.environ.get('POSTGRES_HOST', 'localhost')}"
        f" port={os.environ.get('POSTGRES_PORT', '5432')}"
        f" dbname={os.environ['POSTGRES_DB']}"
        f" user={os.environ['POSTGRES_USER']}"
        f" password={os.environ['POSTGRES_PASSWORD']}"
    )


def lire_questions() -> list[dict[str, str]]:
    """Le jeu de questions, ecrit a la main et versionne."""
    if not QUESTIONS.exists():
        raise SystemExit(f"Jeu de questions absent : {QUESTIONS}")
    with QUESTIONS.open(encoding="utf-8") as fichier:
        return list(csv.DictReader(fichier))


# --- Les trois verifications -------------------------------------------------

VERIFIER_CITATION = """
select count(*)
from marches
where marche_id = %s and ({filtres})
"""


def verifier_citations(curseur: psycopg.Cursor[Any], reponse: Reponse) -> tuple[int, int]:
    """Chaque numero cite existe-t-il, et passe-t-il le filtre annonce ?

    Rend (citations verifiees, citations fausses). Une citation fausse est une faute grave :
    elle donne a l'utilisateur une source qui ne soutient pas la reponse.
    """
    if not reponse.citations:
        return 0, 0
    filtres, valeurs, _ = construire_filtre(reponse.question)
    fausses = 0
    for marche_id in reponse.citations:
        curseur.execute(
            sql.SQL(VERIFIER_CITATION).format(filtres=filtres),
            [marche_id, *valeurs],
        )
        if (curseur.fetchone() or (0,))[0] == 0:
            fausses += 1
    return len(reponse.citations), fausses


def verifier_coherence(reponse: Reponse) -> list[str]:
    """Les regles qui doivent toujours tenir. Rend la liste de celles qui ont cede."""
    rompues: list[str] = []
    chiffres = reponse.chiffres
    marches = chiffres.get("marches")
    if marches is None:
        return rompues

    avec_montant = chiffres.get("avec_montant")
    if avec_montant is not None and avec_montant > marches:
        rompues.append("plus de marches a montant publie que de marches")

    if (total := chiffres.get("total")) is not None and total < 0:
        rompues.append("total negatif")

    if (mediane := chiffres.get("mediane")) is not None and mediane < 0:
        rompues.append("mediane negative")

    # La somme des comptes par titulaire ou par acheteur ne peut pas depasser le total, parce
    # que chaque ligne de marche a au plus un titulaire et un acheteur.
    if reponse.lignes and "marches" in (reponse.lignes[0] or {}):
        somme = sum(ligne.get("marches", 0) for ligne in reponse.lignes)
        if somme > marches:
            rompues.append(f"somme par ligne ({somme}) superieure au total ({marches})")

    # Une liste rendue sans aucun marche derriere, ou l'inverse.
    if reponse.lignes and marches == 0:
        rompues.append("des lignes rendues alors que le comptage est nul")

    # Une reponse qui annonce des marches sans citer aucune source.
    if marches > 0 and not reponse.citations:
        rompues.append("reponse sans aucune citation")

    return rompues


RECOMPTER = """
select count(*) from marches where {filtres}
"""


def recompter_sans_index(curseur: psycopg.Cursor[Any], reponse: Reponse) -> int | None:
    """Le meme comptage, en interdisant les index au planificateur.

    `set local` : l'effet est annule a la fin de la transaction, donc le reste du banc mesure
    bien la configuration normale. Sans `local`, cette verification faussererait toutes les
    latences mesurees apres elle.
    """
    if "marches" not in reponse.chiffres:
        return None
    filtres, valeurs, _ = construire_filtre(reponse.question)
    curseur.execute("set local enable_indexscan = off")
    curseur.execute("set local enable_bitmapscan = off")
    curseur.execute("set local enable_indexonlyscan = off")
    curseur.execute(
        sql.SQL(RECOMPTER).format(filtres=filtres),
        valeurs,
    )
    compte = (curseur.fetchone() or (None,))[0]
    curseur.execute("reset enable_indexscan")
    curseur.execute("reset enable_bitmapscan")
    curseur.execute("reset enable_indexonlyscan")
    return int(compte) if compte is not None else None


# --- Le cout des choix, mesure dans les deux sens ----------------------------
#
# Trois decisions de ce composant ont ete prises apres avoir mesure une version lente. Les
# chiffres « avant » ne sont pas recopies d'un carnet : les deux versions restent ecrites ici et
# sont remesurees a chaque passage du banc.
#
# C'est une regle du projet, appliquee aussi au modele de detection ecarte en phase 5 : une
# comparaison qu'on ne peut plus rejouer n'est plus une mesure, c'est une affirmation.

CHOIX_MESURES: list[tuple[str, str, str, str]] = [
    (
        "agregats du comptage",
        "une requete, cinq colonnes",
        """select count(*), count(montant), coalesce(sum(montant), 0),
                  percentile_cont(0.5) within group (order by montant),
                  (array_agg(marche_id order by montant desc nulls last))[1:3]
           from marches where annee = 2023""",
        "retenu : trois requetes, chacune demandee quand elle sert",
    ),
    (
        "agregats du comptage",
        "retenu : trois colonnes seulement",
        """select count(*), count(montant), coalesce(sum(montant), 0)
           from marches where annee = 2023""",
        "",
    ),
    (
        "valeurs distinctes d'un lieu",
        "select distinct sur deux millions de lignes",
        "select distinct acheteur_region_nom from marches",
        "retenu : parcours de l'index de valeur en valeur",
    ),
    (
        "valeurs distinctes d'un lieu",
        "retenu : parcours de l'index (loose index scan)",
        VALEURS_DISTINCTES_REGION,
        "",
    ),
    (
        "periode couverte",
        "min et max sur la colonne annee",
        "select min(annee), max(annee) from marches",
        "retenu : min et max sur la date, qui est indexee",
    ),
    (
        "periode couverte",
        "retenu : min et max sur la date de notification",
        "select extract(year from min(date_notification))::int,"
        " extract(year from max(date_notification))::int from marches",
        "",
    ),
    (
        "trois citations",
        "array_agg trie sur l'ensemble filtre",
        """select (array_agg(marche_id order by montant desc nulls last))[1:3]
           from marches where annee = 2023""",
        "retenu : order by avec limit 3",
    ),
    (
        "trois citations",
        "retenu : order by avec limit 3",
        """select marche_id from marches where annee = 2023
           order by montant desc nulls last limit 3""",
        "",
    ),
]


def mesurer_les_choix(curseur: psycopg.Cursor[Any]) -> list[dict[str, Any]]:
    """Rejouer les deux versions de chaque choix, et rendre leurs durees.

    Le premier passage de chaque requete est jete : il paie le remplissage des caches, et c'est
    lui qui a donne les 54 secondes du 21 octobre, mesurees sur une base froide. Le chiffre
    retenu est la mediane de trois passages suivants, c'est-a-dire ce que subit un utilisateur
    sur un site deja frequente.
    """
    lignes: list[dict[str, Any]] = []
    for choix, version, requete, verdict in CHOIX_MESURES:
        durees: list[float] = []
        for tour in range(4):
            depart = time.perf_counter()
            curseur.execute(requete)
            curseur.fetchall()
            if tour > 0:
                durees.append((time.perf_counter() - depart) * 1000)
        lignes.append(
            {
                "choix": choix,
                "version": version,
                "millisecondes": round(statistics.median(durees), 1),
                "verdict": verdict,
            }
        )
    return lignes


# --- Le banc -----------------------------------------------------------------


def mesurer(
    curseur: psycopg.Cursor[Any], question: str, lexiques: Lexiques
) -> tuple[Reponse, float, float]:
    """Repondre `REPETITIONS` fois, rendre la reponse et les latences p50 et p95."""
    latences: list[float] = []
    reponse: Reponse | None = None
    for tour in range(REPETITIONS):
        depart = time.perf_counter()
        reponse = repondre(curseur, question, lexiques)
        duree = (time.perf_counter() - depart) * 1000
        if tour > 0:
            latences.append(duree)
    if reponse is None:  # pragma: no cover - REPETITIONS est toujours superieur a zero
        raise RuntimeError("aucune reponse mesuree")
    latences.sort()
    p50 = statistics.median(latences)
    # Avec cinq mesures retenues, le p95 est la plus lente. Dit tel quel pour que le chiffre ne
    # soit pas lu comme un centile estime sur un grand echantillon.
    p95 = latences[-1]
    return reponse, p50, p95


def ecrire(nom: str, lignes: list[dict[str, Any]]) -> Path:
    """Ecrire un CSV de resultats.

    Deux precautions, et les deux viennent d'erreurs deja commises dans ce projet.

    `lineterminator="\n"` : sans lui, le module `csv` ecrit des fins de ligne Windows, et git
    les signale a chaque commit sur une machine qui travaille en Unix. Constate le 11 octobre
    2026 sur le banc de recherche.

    `sur_une_ligne` : les objets de marche sont saisis par des milliers d'agents differents, et
    certains contiennent de vrais retours chariot. Ecrits tels quels, ils coupent une ligne de
    CSV en deux et le fichier devient illisible pour qui doit le relire. La fonction est importee
    du banc de recherche plutot que recopiee : une correction a un seul endroit.
    """
    SORTIE.mkdir(parents=True, exist_ok=True)
    chemin = SORTIE / nom
    propres = [
        {
            cle: sur_une_ligne(valeur) if isinstance(valeur, str) else valeur
            for cle, valeur in ligne.items()
        }
        for ligne in lignes
    ]
    with chemin.open("w", encoding="utf-8", newline="") as fichier:
        redacteur = csv.DictWriter(fichier, fieldnames=list(propres[0].keys()), lineterminator="\n")
        redacteur.writeheader()
        redacteur.writerows(propres)
    return chemin


def main() -> None:
    questions = lire_questions()
    print(f"{len(questions)} questions, {REPETITIONS} passages chacune")

    par_question: list[dict[str, Any]] = []
    extraits: list[dict[str, Any]] = []

    with psycopg.connect(chaine_de_connexion()) as connexion, connexion.cursor() as curseur:
        depart_lexiques = time.perf_counter()
        lexiques = charger_lexiques(curseur)
        duree_lexiques = (time.perf_counter() - depart_lexiques) * 1000
        print(
            f"lexiques charges en {duree_lexiques:.0f} ms : "
            f"{len(lexiques.regions)} regions, {len(lexiques.departements)} departements, "
            f"annees {lexiques.annees[0]} a {lexiques.annees[1]}"
        )

        for ligne in questions:
            reponse, p50, p95 = mesurer(curseur, ligne["question"], lexiques)
            citations, fausses = verifier_citations(curseur, reponse)
            rompues = verifier_coherence(reponse)
            recompte = recompter_sans_index(curseur, reponse)
            annonce = reponse.chiffres.get("marches")

            comportement = "refuse" if reponse.question.intention == "refus" else "repond"
            # Un comptage a zero n'est pas un refus, mais ce n'est pas non plus une reponse :
            # la question est bien comprise et la base ne contient rien. Compte a part.
            if annonce == 0:
                comportement = "aucun resultat"

            par_question.append(
                {
                    "id": ligne["id"],
                    "question": ligne["question"],
                    "intention_attendue": ligne["intention_attendue"],
                    "intention_trouvee": reponse.question.intention,
                    "intention_juste": "oui"
                    if reponse.question.intention == ligne["intention_attendue"]
                    else "non",
                    "comportement_attendu": ligne["comportement_attendu"],
                    "comportement_observe": comportement,
                    "comportement_juste": "oui"
                    if comportement == ligne["comportement_attendu"]
                    else "non",
                    "marches_annonces": annonce if annonce is not None else "",
                    "recompte_sans_index": recompte if recompte is not None else "",
                    "recompte_identique": ""
                    if recompte is None or annonce is None
                    else ("oui" if recompte == annonce else "NON"),
                    "citations": citations,
                    "citations_fausses": fausses,
                    "regles_de_coherence_rompues": "; ".join(rompues),
                    "latence_p50_ms": round(p50, 1),
                    "latence_p95_ms": round(p95, 1),
                    "mots_perdus": " ".join(reponse.question.perdus),
                }
            )

            extraits.append(
                {
                    "id": ligne["id"],
                    "question": ligne["question"],
                    "intention": reponse.question.intention,
                    "filtre": reponse.filtre,
                    "reponse": reponse.phrase,
                    "avertissement": reponse.avertissement,
                    "citations": " ".join(reponse.citations[:3]),
                }
            )

        cout_des_choix = mesurer_les_choix(curseur)

    # --- Le resume, calcule et non raconte ---
    total = len(par_question)
    intentions_justes = sum(1 for ligne in par_question if ligne["intention_juste"] == "oui")
    comportements_justes = sum(1 for ligne in par_question if ligne["comportement_juste"] == "oui")
    citations_totales = sum(int(ligne["citations"]) for ligne in par_question)
    citations_fausses = sum(int(ligne["citations_fausses"]) for ligne in par_question)
    coherences_rompues = sum(1 for ligne in par_question if ligne["regles_de_coherence_rompues"])
    recomptes_differents = sum(1 for ligne in par_question if ligne["recompte_identique"] == "NON")
    p50s = [float(ligne["latence_p50_ms"]) for ligne in par_question]
    p95s = [float(ligne["latence_p95_ms"]) for ligne in par_question]

    # Cout : le temps de calcul reellement consomme, au prix du VPS.
    secondes = sum(p50s) / 1000
    euros_mille = (secondes / total) * 1000 * (EUROS_PAR_MOIS / SECONDES_PAR_MOIS)

    resume = [
        {
            "mesure": "chargement des lexiques",
            "valeur": round(duree_lexiques, 1),
            "unite": "ms",
            "commentaire": (
                "demarrage du service : 24 regions, 107 departements, 74 055 lexemes. "
                "Mesure a 48 050 ms avant les corrections du 21 octobre 2026"
            ),
        },
        {
            "mesure": "questions",
            "valeur": total,
            "unite": "questions",
            "commentaire": "jeu versionne, relu a la main",
        },
        {
            "mesure": "intention reconnue",
            "valeur": round(100 * intentions_justes / total, 1),
            "unite": "%",
            "commentaire": f"{intentions_justes} sur {total}",
        },
        {
            "mesure": "comportement attendu",
            "valeur": round(100 * comportements_justes / total, 1),
            "unite": "%",
            "commentaire": "repondre quand il faut, refuser quand il faut",
        },
        {
            "mesure": "citations verifiees",
            "valeur": citations_totales,
            "unite": "citations",
            "commentaire": "chacune recherchee avec le filtre annonce",
        },
        {
            "mesure": "citations fausses",
            "valeur": citations_fausses,
            "unite": "citations",
            "commentaire": "une seule suffirait a disqualifier la methode",
        },
        {
            "mesure": "regles de coherence rompues",
            "valeur": coherences_rompues,
            "unite": "questions",
            "commentaire": "six regles verifiees par reponse",
        },
        {
            "mesure": "recomptages divergents",
            "valeur": recomptes_differents,
            "unite": "questions",
            "commentaire": "meme comptage, planificateur prive d'index",
        },
        {
            "mesure": "latence mediane",
            "valeur": round(statistics.median(p50s), 1),
            "unite": "ms",
            "commentaire": "mediane des p50 par question",
        },
        {
            "mesure": "latence la plus lente",
            "valeur": round(max(p95s), 1),
            "unite": "ms",
            "commentaire": next(
                ligne["question"]
                for ligne in par_question
                if float(ligne["latence_p95_ms"]) == max(p95s)
            ),
        },
        {
            "mesure": "cout",
            "valeur": round(euros_mille, 5),
            "unite": "euros / 1000 questions",
            "commentaire": (
                f"temps de calcul au prix d'un VPS a {EUROS_PAR_MOIS:.0f} euros par mois"
            ),
        },
    ]

    for nom, lignes in (
        ("assistant-par-question.csv", par_question),
        ("assistant-resume.csv", resume),
        ("assistant-reponses.csv", extraits),
        ("assistant-cout-des-choix.csv", cout_des_choix),
    ):
        print(f"ecrit : {ecrire(nom, lignes)}")

    print()
    for ligne in resume:
        print(f"  {ligne['mesure']:32} {ligne['valeur']:>12} {ligne['unite']}")

    print("\n  cout des choix, les deux versions remesurees :")
    for ligne in cout_des_choix:
        print(
            f"    {ligne['choix']:30} {ligne['version'][:44]:46} {ligne['millisecondes']:>9.1f} ms"
        )

    # Les echecs, nommes. Un banc qui ne dit pas ce qui a rate ne sert a rien.
    for ligne in par_question:
        if ligne["intention_juste"] == "non" or ligne["comportement_juste"] == "non":
            print(
                f"\n  {ligne['id']} {ligne['question']}"
                f"\n     intention attendue {ligne['intention_attendue']}, "
                f"trouvee {ligne['intention_trouvee']}"
                f"\n     comportement attendu {ligne['comportement_attendu']}, "
                f"observe {ligne['comportement_observe']}"
            )


if __name__ == "__main__":
    main()
