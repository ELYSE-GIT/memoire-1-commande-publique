"""Incertitude des mesures : ce que chaque pourcentage vaut vraiment.

Tout le projet annonce des pourcentages. Aucun, jusqu'ici, ne disait **plus ou moins combien**.
Or trois de ces chiffres ne sont pas des comptages exhaustifs mais des estimations tirees d'un
echantillon : 40 questions pour l'assistant, 300 avis pour le rapprochement, 60 paires relues a la
main, dont 56 exploitables. Un chiffre tire d'un echantillon sans son intervalle est une
affirmation plus forte que la mesure ne l'autorise.

Ce module repare cela, et fait surtout une distinction que le projet confondait :

    Nature du chiffre        Exemple du projet                    Incertitude dominante
    recensement              60,8 % de PME sur 1 999 474 marches  aucune au tirage, mais
                                                                   6,8 % de titulaires non
                                                                   resolus : c'est la vraie
                                                                   incertitude
    echantillon             40 intentions sur 40 questions        tirage : intervalle de
                                                                   Wilson
    etiquette indirecte     75,8 % de concordance avec les         ni tirage ni non-reponse :
                            anomalies du producteur                l'etiquette elle-meme est
                                                                   un detecteur. Aucun
                                                                   intervalle ne corrige ca.

**La lecon est la troisieme ligne.** Un intervalle de confiance ne mesure que le hasard du tirage.
Il ne dit rien d'un echantillon mal construit, d'une non-reponse, ni d'une etiquette approximative.
Mettre un intervalle sur la concordance de la detection donnerait un faux air de rigueur a une
mesure dont le defaut est ailleurs. Le troisieme tableau produit par ce module nomme donc, pour
chaque chiffre du memoire, la source d'incertitude qui domine.

Quelle formule pour une proportion :

    Option              Avantage                        Limite                      Verdict
    Wilson              correct jusqu'aux bords 0 et 1, pas tout a fait exact       retenu
                        pas de dependance externe,
                        standard en sondage
    Wald (p +- 1,96     la formule que tout le monde    **donne 0 d'incertitude a   ecarte, et le
    racine(p(1-p)/n))   connait                         40 sur 40**, et sort de     module le
                                                        [0, 1] quand p est petit    montre
    Clopper-Pearson     exact, jamais en dessous du     conservateur : intervalle   calcule pour
    (binomial exact)    niveau annonce                  plus large que necessaire   comparaison
    Bayesien (Jeffreys) bonnes proprietes, naturel      demande d'assumer une       non retenu
                        sur les petits effectifs        loi a priori a justifier

Le cas « 40 sur 40 » tranche a lui seul : Wald annonce 100 % sans marge, ce qui voudrait dire que
la 41e question est certaine d'etre juste. Wilson annonce un plancher autour de 91 %. C'est la
difference entre un resultat et une publicite.

Pourquoi un reechantillonnage pour la justesse du rapprochement, et pas une formule :

    Option              Avantage                        Limite                      Verdict
    Bootstrap           suit l'estimateur reellement    demande de tirer des        retenu
    stratifie           utilise, y compris sa           milliers de fois, et de
                        ponderation par tranche         fixer une graine
    Formule de          exacte si l'estimateur est      l'estimateur ici est un     ecarte
    variance d'un       une simple moyenne ponderee     rapport, et les doutes
    sondage stratifie                                   exclus changent le
                                                        denominateur au tirage
    Ignorer et donner   simple                          60 paires relues, cinq      exclu
    le point                                            tranches : l'intervalle
                                                        depasse dix points, le
                                                        taire serait mentir

Rien n'est appele qui sorte du Mac : ce module ne lit que des CSV deja produits et la base DuckDB
locale. Aucun appel reseau, aucun conteneur a demarrer.

Lancement : `make bench-incertitude`.
"""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path
from typing import Any

import duckdb

RACINE = Path(__file__).resolve().parent.parent
BASE = RACINE / "donnees" / "commande_publique.duckdb"
RESULTATS = RACINE / "mesures" / "resultats"
VERIFICATION = RACINE / "mesures" / "verification"

# Niveau de confiance de tous les intervalles du projet. 95 % est la convention en sciences
# sociales et en sondage ; l'annoncer une fois ici evite de melanger des niveaux differents d'une
# table a l'autre.
CONFIANCE = 0.95

# Quantile de la loi normale pour 95 % bilateral. Ecrit en clair plutot que calcule : la valeur est
# une constante connue, et la faire dependre de scipy ajouterait une dependance pour un nombre.
Z = 1.959963984540054

# Nombre de reechantillonnages. 10 000 suffit pour stabiliser les bornes au dixieme de point ;
# la section « combien de tirages » du notebook 10 le verifie en comparant 100, 1 000 et 100 000.
TIRAGES = 10_000

# Graine fixee. Sans elle, deux executions donnent deux intervalles legerement differents et la
# figure du memoire change a chaque `make figures` sans qu'aucune donnee ait bouge. Le projet a
# deja paye cette erreur une fois, sur la detection : voir le journal du 28 septembre.
GRAINE = 20261021

# Bornes des tranches relues, identiques a celles de `precision_rapprochement.py`. Les deux
# modules doivent decouper pareil, sinon ils ne parlent pas du meme echantillon ; un test le
# verifie en important les deux constantes.
TRANCHES = [(0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01)]

# Fenetre de reference du rapprochement, reprise du meme module, pour la meme raison.
FENETRE_REFERENCE = 18

# Taille de l'echantillon d'avis du balayage de rapprochement.
AVIS_ECHANTILLONNES = 300

# Taille de l'echantillon de titulaires interroges par le notebook 06, avant que
# l'enrichissement soit applique a toute la table. Elle sert a repondre a une question
# precise : maintenant que la part de PME est comptee et plus estimee, l'incertitude a-t-elle
# vraiment diminue ? La reponse demande de comparer l'ancienne largeur de tirage a la nouvelle
# etendue de non-reponse, et donc de recalculer la premiere.
TITULAIRES_ECHANTILLONNES = 170


def wilson(succes: int, essais: int) -> tuple[float, float]:
    """Intervalle de Wilson a 95 %, en pourcentage.

    La formule corrige le defaut de Wald en recentrant la proportion observee vers 0,5 d'une
    quantite qui depend de la taille de l'echantillon. Consequence utile : l'intervalle reste
    dans [0, 1] et ne se referme jamais completement, meme sur un resultat parfait.
    """
    if essais == 0:
        return (0.0, 100.0)
    proportion = succes / essais
    denominateur = 1 + Z**2 / essais
    centre = (proportion + Z**2 / (2 * essais)) / denominateur
    demi_largeur = (
        Z
        / denominateur
        * math.sqrt(proportion * (1 - proportion) / essais + Z**2 / (4 * essais**2))
    )
    return (100 * max(0.0, centre - demi_largeur), 100 * min(1.0, centre + demi_largeur))


def wald(succes: int, essais: int) -> tuple[float, float]:
    """Intervalle de Wald, calcule uniquement pour montrer ou il echoue.

    Il n'est utilise dans aucune conclusion du projet. Il figure dans la table de comparaison
    parce que c'est la formule que le notebook 06 appliquait, et qu'il faut pouvoir montrer
    pourquoi elle a ete remplacee.
    """
    if essais == 0:
        return (0.0, 100.0)
    proportion = succes / essais
    marge = Z * math.sqrt(proportion * (1 - proportion) / essais)
    return (100 * (proportion - marge), 100 * (proportion + marge))


def _log_binomiale(k: int, n: int, p: float) -> float:
    """Logarithme de la probabilite d'exactement k succes sur n tirages.

    Passer par les logarithmes evite le depassement de capacite : pour n = 448, le coefficient
    binomial du milieu vaut environ 10 puissance 133, et le produit direct perd toute precision.
    """
    if p <= 0.0:
        return 0.0 if k == 0 else -math.inf
    if p >= 1.0:
        return 0.0 if k == n else -math.inf
    return (
        math.lgamma(n + 1)
        - math.lgamma(k + 1)
        - math.lgamma(n - k + 1)
        + k * math.log(p)
        + (n - k) * math.log1p(-p)
    )


def _queue_haute(k: int, n: int, p: float) -> float:
    """Probabilite d'observer au moins k succes sur n, si la vraie proportion est p."""
    return sum(math.exp(_log_binomiale(i, n, p)) for i in range(k, n + 1))


def _queue_basse(k: int, n: int, p: float) -> float:
    """Probabilite d'observer au plus k succes sur n, si la vraie proportion est p."""
    return sum(math.exp(_log_binomiale(i, n, p)) for i in range(0, k + 1))


def clopper_pearson(succes: int, essais: int) -> tuple[float, float]:
    """Intervalle binomial exact, obtenu par dichotomie sur la loi binomiale.

    Les bornes sont les proportions pour lesquelles le resultat observe devient tout juste
    improbable. La dichotomie remplace la fonction beta inverse de scipy : cinquante iterations
    donnent une precision tres superieure au dixieme de point affiche, pour quelques
    millisecondes et zero dependance en plus.
    """
    if essais == 0:
        return (0.0, 100.0)
    alpha = 1 - CONFIANCE

    bas = 0.0
    if succes > 0:
        gauche, droite = 0.0, succes / essais
        for _ in range(50):
            milieu = (gauche + droite) / 2
            if _queue_haute(succes, essais, milieu) < alpha / 2:
                gauche = milieu
            else:
                droite = milieu
        bas = (gauche + droite) / 2

    haut = 1.0
    if succes < essais:
        gauche, droite = succes / essais, 1.0
        for _ in range(50):
            milieu = (gauche + droite) / 2
            if _queue_basse(succes, essais, milieu) < alpha / 2:
                droite = milieu
            else:
                gauche = milieu
        haut = (gauche + droite) / 2

    return (100 * bas, 100 * haut)


def lire(dossier: Path, nom: str) -> list[dict[str, str]]:
    """Lit un CSV du projet."""
    with (dossier / nom).open(encoding="utf-8") as fichier:
        return list(csv.DictReader(fichier))


def dernier(dossier: Path, motif: str) -> Path:
    """Le fichier le plus recent correspondant au motif."""
    fichiers = sorted(dossier.glob(motif))
    if not fichiers:
        message = f"aucun fichier {motif} dans {dossier}"
        raise FileNotFoundError(message)
    return fichiers[-1]


def proportions_mesurees() -> list[dict[str, Any]]:
    """Chaque proportion du projet tiree d'un echantillon, avec ses trois intervalles."""
    assistant = lire(RESULTATS, "assistant-par-question.csv")
    questions = len(assistant)
    intentions_justes = sum(1 for ligne in assistant if ligne["intention_juste"] == "oui")
    comportements_justes = sum(1 for ligne in assistant if ligne["comportement_juste"] == "oui")
    citations = sum(int(ligne["citations"] or 0) for ligne in assistant)
    citations_fausses = sum(int(ligne["citations_fausses"] or 0) for ligne in assistant)

    balayage = [
        ligne
        for ligne in csv.DictReader(
            dernier(RESULTATS, "*-rapprochement-balayage.csv").open(encoding="utf-8")
        )
        if int(ligne["fenetre_mois"]) == FENETRE_REFERENCE
    ]
    rapproches_05 = next(
        int(ligne["confiance_haute"]) + int(ligne["confiance_moyenne"])
        for ligne in balayage
        if float(ligne["seuil_objet"]) == 0.5
    )
    avec_candidats = int(balayage[0]["avec_candidats"])

    verdicts = list(
        csv.DictReader(dernier(VERIFICATION, "*-verdicts-rapprochement.csv").open(encoding="utf-8"))
    )
    relues_sures = [ligne for ligne in verdicts if ligne["verdict_humain"] in {"oui", "non"}]
    justes_relues = sum(1 for ligne in relues_sures if ligne["verdict_humain"] == "oui")

    mesures = [
        (
            "assistant : intention reconnue",
            intentions_justes,
            questions,
            "40 questions versionnees",
        ),
        (
            "assistant : comportement attendu",
            comportements_justes,
            questions,
            "repondre ou refuser a bon escient",
        ),
        (
            "assistant : citation juste",
            citations - citations_fausses,
            citations,
            "chaque citation recherchee avec le filtre annonce",
        ),
        (
            "rapprochement : avis avec un candidat",
            avec_candidats,
            AVIS_ECHANTILLONNES,
            "tirage de 300 avis du BOAMP",
        ),
        (
            "rapprochement : avis rapproches au seuil 0,5",
            rapproches_05,
            AVIS_ECHANTILLONNES,
            "fenetre de 18 mois",
        ),
        (
            "rapprochement : justesse brute des paires relues",
            justes_relues,
            len(relues_sures),
            "sans redressement, echantillon stratifie : voir la table dediee",
        ),
    ]

    table: list[dict[str, Any]] = []
    for nom, succes, essais, commentaire in mesures:
        wilson_bas, wilson_haut = wilson(succes, essais)
        wald_bas, wald_haut = wald(succes, essais)
        exact_bas, exact_haut = clopper_pearson(succes, essais)
        table.append(
            {
                "mesure": nom,
                "succes": succes,
                "essais": essais,
                "taux_pourcent": round(100 * succes / essais, 1) if essais else 0.0,
                "wilson_bas": round(wilson_bas, 1),
                "wilson_haut": round(wilson_haut, 1),
                "largeur_points": round(wilson_haut - wilson_bas, 1),
                "wald_bas": round(wald_bas, 1),
                "wald_haut": round(wald_haut, 1),
                "exact_bas": round(exact_bas, 1),
                "exact_haut": round(exact_haut, 1),
                "commentaire": commentaire,
            }
        )
    return table


def justesse_par_tranche(verdicts: list[dict[str, str]]) -> dict[str, list[str]]:
    """Les verdicts humains, regroupes par tranche de similarite."""
    groupes: dict[str, list[str]] = {}
    for bas, haut in TRANCHES:
        nom = f"{bas} a {haut}"
        groupes[nom] = [ligne["verdict_humain"] for ligne in verdicts if ligne["tranche"] == nom]
    return groupes


def effectifs_par_tranche() -> dict[str, int]:
    """Nombre reel de rapprochements dans chaque tranche, lu dans le balayage.

    Ces effectifs servent de poids : l'echantillon relu compte douze paires par tranche, alors
    que les tranches n'ont pas du tout le meme effectif reel. Sans ce redressement, une tranche
    rare peserait autant qu'une tranche frequente.
    """
    lignes = [
        ligne
        for ligne in csv.DictReader(
            dernier(RESULTATS, "*-rapprochement-balayage.csv").open(encoding="utf-8")
        )
        if int(ligne["fenetre_mois"]) == FENETRE_REFERENCE
    ]
    par_seuil = {float(ligne["seuil_objet"]): int(ligne["confiance_moyenne"]) for ligne in lignes}
    effectifs: dict[str, int] = {}
    for indice, (bas, haut) in enumerate(TRANCHES):
        au_dessus_du_haut = par_seuil.get(haut, 0) if indice + 1 < len(TRANCHES) else 0
        effectifs[f"{bas} a {haut}"] = par_seuil.get(bas, 0) - au_dessus_du_haut
    return effectifs


def justesse_ponderee(
    groupes: dict[str, list[str]], effectifs: dict[str, int], seuil: float
) -> float | None:
    """Justesse redressee pour un seuil : moyenne des tranches retenues, ponderee par l'effectif.

    Renvoie None quand aucune des tranches retenues n'a de verdict exploitable, cas qui doit
    rester visible plutot que d'etre remplace par un zero trompeur.
    """
    retenues = [f"{bas} a {haut}" for bas, haut in TRANCHES if bas >= seuil]
    poids_total = sum(effectifs[nom] for nom in retenues)
    if poids_total == 0:
        return None
    somme = 0.0
    for nom in retenues:
        surs = [verdict for verdict in groupes[nom] if verdict in {"oui", "non"}]
        if not surs:
            return None
        somme += effectifs[nom] * surs.count("oui") / len(surs)
    return somme / poids_total


def bootstrap_justesse() -> list[dict[str, Any]]:
    """Intervalle de la justesse redressee, par reechantillonnage dans chaque tranche.

    Le tirage se fait **a l'interieur de chaque tranche**, en conservant le nombre de paires
    relues : c'est ce que reproduit un bootstrap stratifie. Les effectifs reels, eux, sont
    traites comme fixes. C'est un choix, et il doit etre dit : l'intervalle publie couvre le
    hasard des verdicts relus, pas celui du tirage des 300 avis qui a fixe les poids. Il est
    donc un minorant de l'incertitude totale.
    """
    verdicts = list(
        csv.DictReader(dernier(VERIFICATION, "*-verdicts-rapprochement.csv").open(encoding="utf-8"))
    )
    groupes = justesse_par_tranche(verdicts)
    effectifs = effectifs_par_tranche()
    # `random` et non `secrets` : un bootstrap doit etre **reproductible**, donc tirer d'une
    # suite determinee par une graine. Un generateur cryptographique, qui refuse par
    # construction d'etre reproductible, rendrait l'intervalle different a chaque execution.
    # L'avertissement de securite ne s'applique donc pas ici, et il est ecarte ligne a ligne
    # plutot que desactive pour tout le fichier.
    alea = random.Random(GRAINE)  # noqa: S311

    table: list[dict[str, Any]] = []
    for bas, _ in TRANCHES:
        observee = justesse_ponderee(groupes, effectifs, bas)
        if observee is None:
            continue
        simulations: list[float] = []
        for _ in range(TIRAGES):
            tires = {
                nom: [alea.choice(valeurs) for _ in valeurs] if valeurs else []
                for nom, valeurs in groupes.items()
            }
            simulee = justesse_ponderee(tires, effectifs, bas)
            if simulee is not None:
                simulations.append(simulee)
        simulations.sort()
        indice_bas = int(0.025 * len(simulations))
        indice_haut = min(len(simulations) - 1, int(0.975 * len(simulations)))
        retenues = [f"{b} a {h}" for b, h in TRANCHES if b >= bas]

        # Verdicts mis en commun, sans redressement, pour pouvoir calculer un intervalle exact
        # de secours. Il ignore la ponderation par tranche, donc il ne remplace pas le bootstrap :
        # il sert de garde-fou la ou le bootstrap ne sait rien dire.
        surs = [
            verdict for nom in retenues for verdict in groupes[nom] if verdict in {"oui", "non"}
        ]
        exact_bas, exact_haut = clopper_pearson(surs.count("oui"), len(surs))

        # **Le bootstrap degenere quand l'echantillon ne contient aucune variation.** Au seuil le
        # plus haut, les douze paires relues sont toutes justes : chaque reechantillonnage redonne
        # exactement 100 %, et l'intervalle se referme sur un point. Ce n'est pas une certitude,
        # c'est l'aveu que la methode n'a plus de prise. Le reechantillonnage ne peut produire que
        # des valeurs deja presentes dans l'echantillon ; si celui-ci n'en contient qu'une, il la
        # repete. Le cas est detecte, signale, et l'intervalle exact prend le relais.
        degenere = simulations[0] == simulations[-1]
        table.append(
            {
                "seuil_objet": bas,
                "rapproches_par_objet": sum(effectifs[nom] for nom in retenues),
                "paires_relues": sum(len(groupes[nom]) for nom in retenues),
                "paires_justes": surs.count("oui"),
                "justesse_pourcent": round(100 * observee, 1),
                "bootstrap_bas": round(100 * simulations[indice_bas], 1),
                "bootstrap_haut": round(100 * simulations[indice_haut], 1),
                "largeur_points": round(
                    100 * (simulations[indice_haut] - simulations[indice_bas]), 1
                ),
                "bootstrap_degenere": "oui" if degenere else "non",
                "exact_sans_redressement_bas": round(exact_bas, 1),
                "exact_sans_redressement_haut": round(exact_haut, 1),
                "tirages_exploitables": len(simulations),
            }
        )
    return table


def recensement_des_pme(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """La part d'attributions a une PME, comptee, et l'etendue due a la non-reponse.

    Le notebook 06 estimait cette part sur un echantillon de titulaires interroges par l'API, et
    l'annoncait avec une marge de tirage. Or l'enrichissement a ensuite ete applique a toute la
    table : la part n'est plus une estimation, c'est un comptage. Son incertitude a change de
    nature. Elle ne vient plus du tirage, mais des titulaires que l'API n'a pas resolus, dont la
    categorie reste inconnue. On ne peut pas l'estimer, on peut l'encadrer : en supposant que ces
    titulaires sont tous des PME, puis qu'aucun ne l'est.

    **L'unite de comptage est l'attribution, pas le marche.** `or_marches` porte une ligne par
    couple marche-titulaire : 1 999 474 lignes pour 1 738 289 marches distincts, l'ecart venant
    des groupements d'entreprises, ou plusieurs societes se partagent un meme marche. Compter les
    lignes repond donc a « quelle part des attributions va a une PME », et non a « quelle part des
    marches ». Les deux sont publies : confondre les deux est l'erreur la plus facile a commettre
    sur ce jeu, et le memoire impose a chaque pourcentage de nommer son unite de comptage.
    """
    ligne = con.execute("""
        select
            count(*)                                                     as attributions,
            count(distinct marche_id)                                    as marches,
            sum(case when titulaire_categorie = 'PME' then 1 else 0 end) as pme,
            sum(case when titulaire_categorie is null then 1 else 0 end) as non_resolus
        from or_marches
    """).fetchone()
    if ligne is None:
        message = (
            "le comptage des categories n'a rien renvoye : la table or_marches est-elle vide ?"
        )
        raise RuntimeError(message)
    attributions, marches, pme, non_resolus = ligne

    # Le meme chiffre a l'echelle du marche : un marche est compte des qu'au moins un de ses
    # titulaires est une PME. C'est la convention la plus lisible pour un groupement, et elle est
    # ecrite ici plutot que laissee a la supposition du lecteur.
    par_marche = con.execute("""
        select count(*)
        from (
            select marche_id
            from or_marches
            group by 1
            having sum(case when titulaire_categorie = 'PME' then 1 else 0 end) > 0
        )
    """).fetchone()
    if par_marche is None:
        message = "le comptage par marche n'a rien renvoye"
        raise RuntimeError(message)

    resolus = attributions - non_resolus
    part = pme / resolus

    # Largeur qu'un echantillon de la taille de celui du notebook 06 aurait donnee, a la meme
    # proportion. Ce n'est pas une mesure, c'est un calcul de largeur, et il sert a comparer deux
    # incertitudes de nature differente sur la meme echelle. Sans lui, on croirait que passer de
    # l'echantillon au recensement a supprime l'incertitude ; il montre qu'elle a surtout change
    # de nature, et qu'elle n'a pas disparu.
    tirage_bas, tirage_haut = wilson(
        round(part * TITULAIRES_ECHANTILLONNES), TITULAIRES_ECHANTILLONNES
    )

    return {
        "attributions": attributions,
        "marches": marches,
        "resolus": resolus,
        "non_resolus": non_resolus,
        "part_non_resolus_pourcent": round(100 * non_resolus / attributions, 1),
        "part_pme_sur_resolus_pourcent": round(100 * part, 1),
        "borne_basse_pourcent": round(100 * pme / attributions, 1),
        "borne_haute_pourcent": round(100 * (pme + non_resolus) / attributions, 1),
        "marches_avec_au_moins_une_pme": par_marche[0],
        "part_marches_avec_au_moins_une_pme_pourcent": round(100 * par_marche[0] / marches, 1),
        # Largeur de l'encadrement, donc rapportee aux attributions comme ses deux bornes.
        # L'avoir rapportee aux marches distincts a produit une etendue de 7,8 points pour un
        # encadrement large de 6,8 : deux denominateurs differents dans la meme phrase.
        "etendue_non_reponse_points": round(100 * non_resolus / attributions, 1),
        "largeur_tirage_echantillon_points": round(tirage_haut - tirage_bas, 1),
        "titulaires_echantillonnes": TITULAIRES_ECHANTILLONNES,
    }


def sources_d_incertitude(
    pme: dict[str, Any], proportions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Pour chaque chiffre du memoire : d'ou vient son incertitude, et combien elle vaut.

    C'est la table la plus utile des trois. Elle empeche l'erreur que ce module aurait pu
    introduire : coller un intervalle de confiance sur tout, y compris la ou le tirage n'est pas
    le probleme. Un intervalle au mauvais endroit rassure a tort.
    """
    par_nom = {ligne["mesure"]: ligne for ligne in proportions}
    intention = par_nom["assistant : intention reconnue"]
    rapproches = par_nom["rapprochement : avis rapproches au seuil 0,5"]

    return [
        {
            "chiffre": "part des attributions a une PME",
            "valeur_pourcent": pme["part_pme_sur_resolus_pourcent"],
            "nature": "recensement",
            "incertitude_dominante": "non-reponse",
            "etendue_points": round(pme["borne_haute_pourcent"] - pme["borne_basse_pourcent"], 1),
            "detail": (
                f"compte sur {pme['attributions']} attributions, donc aucun hasard de "
                "tirage. "
                f"{pme['part_non_resolus_pourcent']} % des titulaires n'ont pas ete resolus : "
                f"la part reelle est entre {pme['borne_basse_pourcent']} et "
                f"{pme['borne_haute_pourcent']} %"
            ),
        },
        {
            "chiffre": "intentions reconnues par l'assistant",
            "valeur_pourcent": intention["taux_pourcent"],
            "nature": "echantillon",
            "incertitude_dominante": "tirage, et surtout provenance des questions",
            "etendue_points": intention["largeur_points"],
            "detail": (
                f"intervalle de Wilson [{intention['wilson_bas']} ; {intention['wilson_haut']}] %. "
                "Les 40 questions ont ete ecrites par l'auteur du systeme : l'intervalle couvre "
                "le tirage, pas ce biais. Un jeu ecrit par un tiers reste a mesurer"
            ),
        },
        {
            "chiffre": "avis du BOAMP rapproches d'un marche",
            "valeur_pourcent": rapproches["taux_pourcent"],
            "nature": "echantillon",
            "incertitude_dominante": "tirage",
            "etendue_points": rapproches["largeur_points"],
            "detail": (
                f"300 avis tires, intervalle de Wilson "
                f"[{rapproches['wilson_bas']} ; {rapproches['wilson_haut']}] %"
            ),
        },
        {
            "chiffre": "justesse du rapprochement",
            "valeur_pourcent": None,
            "nature": "echantillon stratifie, redresse",
            "incertitude_dominante": "tirage, sur 60 paires relues seulement",
            "etendue_points": None,
            "detail": (
                "bootstrap stratifie, voir incertitude-justesse-rapprochement.csv. "
                "Les poids viennent du balayage et sont traites comme fixes : "
                "l'intervalle est un minorant"
            ),
        },
        {
            "chiffre": "concordance de la detection avec les anomalies signalees",
            "valeur_pourcent": None,
            "nature": "recensement",
            "incertitude_dominante": "etiquette approximative",
            "etendue_points": None,
            "detail": (
                "calculee sur tous les marches evalues : aucun intervalle de tirage a produire. "
                "L'etiquette est elle-meme un detecteur de montants, donc la mesure est un "
                "minorant de la precision reelle. Aucun calcul ne corrige cela, seul un "
                "echantillon juge a la main le peut"
            ),
        },
        {
            "chiffre": "pertinence des resultats de recherche",
            "valeur_pourcent": None,
            "nature": "non mesure",
            "incertitude_dominante": "absence de jugement humain",
            "etendue_points": None,
            "detail": (
                "les 30 questions de recherche n'ont pas encore de verdict de pertinence. "
                "Tant qu'il manque, aucun taux ne peut etre annonce, avec ou sans intervalle"
            ),
        },
        {
            "chiffre": "latences mesurees",
            "valeur_pourcent": None,
            "nature": "repetitions sur une machine",
            "incertitude_dominante": "variabilite d'execution",
            "etendue_points": None,
            "detail": (
                "une latence n'est pas une proportion : elle se publie en mediane et en p95, "
                "jamais avec un intervalle de Wilson. La variabilite entre executions a deja ete "
                "observee sur la question la plus lente, de 291 a 403 ms"
            ),
        },
    ]


def ecrire(nom: str, lignes: list[dict[str, Any]]) -> Path:
    """Ecrit une mesure en CSV, fins de ligne Unix.

    Les CSV du projet ont deja ete committes une fois en CRLF, ce qui rendait chaque execution
    differente de la precedente dans git. Le terminateur est donc impose ici.
    """
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

    proportions = proportions_mesurees()
    print("Proportions tirees d'un echantillon, intervalle a 95 % :")
    print(f"  {'mesure':<44} {'taux':>7}   {'Wilson':>16}   {'Wald':>16}   {'exact':>16}")
    for ligne in proportions:
        wilson_affiche = f"[{ligne['wilson_bas']:>5} ; {ligne['wilson_haut']:>5}]"
        wald_affiche = f"[{ligne['wald_bas']:>5} ; {ligne['wald_haut']:>5}]"
        exact_affiche = f"[{ligne['exact_bas']:>5} ; {ligne['exact_haut']:>5}]"
        print(
            f"  {ligne['mesure']:<44} {ligne['taux_pourcent']:>6} %   "
            f"{wilson_affiche:>16}   {wald_affiche:>16}   {exact_affiche:>16}"
        )
    print(
        "\n  A lire sur la premiere ligne : Wald annonce 100 % sans marge, donc la certitude que\n"
        "  la question suivante sera juste. Wilson refuse de le dire. C'est tout l'ecart entre\n"
        "  une mesure et une affirmation."
    )

    justesse = bootstrap_justesse()
    print(f"\nJustesse du rapprochement, bootstrap stratifie sur {TIRAGES} tirages :")
    print("  seuil   rapproches   relues   justesse   intervalle a 95 %   largeur   exact")
    for ligne in justesse:
        intervalle = f"[{ligne['bootstrap_bas']:>5} ; {ligne['bootstrap_haut']:>5}]"
        exact = (
            f"[{ligne['exact_sans_redressement_bas']:>5} ; "
            f"{ligne['exact_sans_redressement_haut']:>5}]"
        )
        print(
            f"  {ligne['seuil_objet']:>5}   {ligne['rapproches_par_objet']:>10}   "
            f"{ligne['paires_relues']:>6}   {ligne['justesse_pourcent']:>7} %   "
            f"{intervalle:>17}   {ligne['largeur_points']:>5} pts   {exact:>16}"
        )
    degeneres = [ligne["seuil_objet"] for ligne in justesse if ligne["bootstrap_degenere"] == "oui"]
    if degeneres:
        print(
            f"\n  Le bootstrap degenere au seuil {degeneres[0]} : toutes les paires relues y sont\n"
            "  justes, donc chaque tirage redonne 100 % et l'intervalle se referme sur un point.\n"
            "  Ce n'est pas une certitude, c'est l'aveu que douze paires ne suffisent pas. La\n"
            "  colonne « exact », qui ne depend pas du reechantillonnage, prend le relais."
        )

    con = duckdb.connect(str(BASE), read_only=True)
    pme = recensement_des_pme(con)
    print("\nPart de PME : un comptage, pas une estimation.")
    print(
        f"  unite : l'attribution. {pme['attributions']} attributions pour "
        f"{pme['marches']} marches distincts, l'ecart venant des groupements d'entreprises."
    )
    print(
        f"  {pme['part_pme_sur_resolus_pourcent']} % des attributions dont le titulaire est "
        f"resolu, sur {pme['resolus']} attributions"
    )
    print(
        f"  a l'echelle du marche : "
        f"{pme['part_marches_avec_au_moins_une_pme_pourcent']} % des marches ont au moins "
        f"une PME parmi leurs titulaires"
    )
    print(
        f"  {pme['part_non_resolus_pourcent']} % de titulaires non resolus : la part reelle est "
        f"entre {pme['borne_basse_pourcent']} % et {pme['borne_haute_pourcent']} %"
    )
    print(
        f"  Soit une etendue de {pme['etendue_non_reponse_points']} points, contre "
        f"{pme['largeur_tirage_echantillon_points']} points de hasard de tirage pour "
        f"l'echantillon de {pme['titulaires_echantillonnes']} titulaires du notebook 06.\n"
        "  Le recensement a donc reduit l'incertitude, pas supprime : il a remplace un hasard\n"
        "  qui se calcule par une non-reponse qui ne se corrige pas."
    )

    sources = sources_d_incertitude(pme, proportions)
    print("\nSource d'incertitude dominante, chiffre par chiffre :")
    for ligne in sources:
        print(f"  {ligne['chiffre']:<52} {ligne['nature']:<32} {ligne['incertitude_dominante']}")

    for nom, lignes in (
        ("incertitude-proportions", proportions),
        ("incertitude-justesse-rapprochement", justesse),
        ("incertitude-recensement-pme", [pme]),
        ("incertitude-sources", sources),
    ):
        print(f"\nEcrit : {ecrire(nom, lignes).relative_to(RACINE)}")


if __name__ == "__main__":
    main()
