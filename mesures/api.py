"""Banc d'essai de l'API publique : latence par route, puis comportement sous charge.

=== Ce qui est mesure, et pourquoi par HTTP reel ==============================

    Option envisagee        Avantage                      Limite                     Verdict
    appeler les requetes    isole le cout de la base      ne mesure ni la validation  ecarte
    SQL directement                                        des entrees, ni la
                                                           serialisation, ni le
                                                           reseau : ce n'est pas ce
                                                           que le visiteur subit
    `TestClient` de         rapide, aucun port a ouvrir   court-circuite le serveur   ecarte
    FastAPI                                                HTTP et la reserve de fils,
                                                           donc ne peut pas mesurer la
                                                           charge
    **HTTP reel sur         mesure exactement ce que le   demarre un serveur, donc    **retenu**
    uvicorn**               visiteur subit, charge        une mesure plus lente et un
                            comprise                      port a liberer

A quelle echelle la reponse changerait : pour comparer deux formulations d'une meme requete SQL,
passer par HTTP ajoute du bruit sans rien apprendre. C'est le role de `mesures/recherche.py`.
Ici la question est « combien de temps attend un visiteur », et elle inclut tout le chemin.

=== Les deux chiffres qui comptent ===========================================

Le p50 dit ce que vit la moitie des visiteurs. Le p95 dit ce que vit le vingtieme le plus
malchanceux, et c'est lui qui fait abandonner une page. Une moyenne, elle, cache les deux : une
route qui repond en 10 ms neuf fois sur dix et en 3 s une fois sur dix a une moyenne de 310 ms,
qui ne decrit aucune visite reelle.

La premiere repetition de chaque route est jetee : elle paie le remplissage des caches de
PostgreSQL et du systeme de fichiers, ce qui ne represente pas un site ou les pages s'enchainent.
L'exception est `/statistiques`, dont le premier appel est **justement** ce qu'on veut mesurer :
c'est lui qui calcule, les suivants lisent le cache.

Sortie : `mesures/resultats/api-latences.csv`, `api-charge.csv`, `api-resume.csv`.
"""

from __future__ import annotations

import csv
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import psycopg

from services.api.requetes import PLAFOND_CANDIDATS
from services.configuration import chaine_de_connexion

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "mesures" / "resultats"

# Port distinct de celui du developpement : le banc ne doit pas tomber sur une API deja
# demarree a la main, dont l'etat des caches serait inconnu.
PORT = int(os.environ.get("PORT_BANC_API", "8099"))
RACINE_HTTP = f"http://127.0.0.1:{PORT}"

# Repetitions par route. Vingt-et-une, dont la premiere jetee : assez pour un p95 qui ne depende
# pas d'un seul appel malheureux, assez peu pour que le banc tienne en une minute.
REPETITIONS = 21

# Les paliers de concurrence. Au-dela de seize, on mesurerait surtout la file d'attente de la
# reserve de fils de Starlette, pas le service.
PALIERS = (1, 2, 4, 8, 16)
APPELS_PAR_PALIER = 60

DELAI_DEMARRAGE_S = 40.0

# Les questions qui servent a mesurer ce que le plafond de candidats change.
#
# Six viennent du jeu versionne, et quatre sont des mots seuls, choisis parce qu'ils sont tres
# frequents. C'est la difference entre les deux groupes qui fait la mesure : les questions du jeu
# comptent plusieurs mots, donc repondent peu, donc ne montraient pas le probleme. Mesurer
# seulement sur elles aurait conclu que tout allait bien.
QUESTIONS_DE_CLASSEMENT = (
    "travaux de voirie",
    "entretien des espaces verts",
    "fourniture de repas pour la restauration scolaire",
    "assurance dommages aux biens",
    "refection de la toiture d'une ecole",
    "travaux de rehabilitation de logements",
    "travaux",
    "entretien",
    "fourniture",
    "maintenance",
)

# Ce qu'une page affiche, donc ce sur quoi la comparaison porte : les dix premiers.
PROFONDEUR_COMPAREE = 10

# Delai accorde a la requete exacte, dans cette mesure seulement. L'API, elle, coupe a dix
# secondes : c'est precisement ce que cette mesure explique.
DELAI_MESURE_MS = 120_000


def centile(valeurs: list[float], part: float) -> float:
    """Centile par interpolation lineaire, sans dependance.

    `statistics.quantiles` decoupe en tranches egales et n'accepte pas un centile quelconque :
    pour le 95e, il faudrait demander vingt tranches et prendre la dix-neuvieme, ce qui est plus
    difficile a relire que le calcul lui-meme.
    """
    if not valeurs:
        return 0.0
    ordonnees = sorted(valeurs)
    if len(ordonnees) == 1:
        return ordonnees[0]
    position = part * (len(ordonnees) - 1)
    bas = int(position)
    haut = min(bas + 1, len(ordonnees) - 1)
    return ordonnees[bas] + (ordonnees[haut] - ordonnees[bas]) * (position - bas)


def appeler(chemin: str) -> tuple[float, int, Any]:
    """Appelle une route et renvoie la duree en millisecondes, le code et le corps."""
    depart = time.perf_counter()
    requete = urllib.request.Request(RACINE_HTTP + chemin)  # noqa: S310
    try:
        with urllib.request.urlopen(requete, timeout=60) as reponse:  # noqa: S310
            corps = json.loads(reponse.read())
            code = reponse.status
    except urllib.error.HTTPError as erreur:
        corps = None
        code = erreur.code
    return (time.perf_counter() - depart) * 1000, code, corps


def demarrer() -> subprocess.Popen[bytes]:
    """Demarre uvicorn dans un processus a part, et attend que /sante reponde.

    Sans rechargement automatique : le surveillant de fichiers ajoute un processus et de la
    latence, et mesurer l'outil de developpement n'a aucun interet.
    """
    serveur = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "uvicorn",
            "services.api.main:application",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
            "--log-level",
            "warning",
        ],
        cwd=RACINE,
    )
    depart = time.perf_counter()
    while time.perf_counter() - depart < DELAI_DEMARRAGE_S:
        if serveur.poll() is not None:
            raise SystemExit("L'API s'est arretee au demarrage. Lancer `make up` d'abord.")
        try:
            _, code, corps = appeler("/sante")
        except OSError:
            time.sleep(0.2)
            continue
        if code == 200 and corps and corps.get("base_accessible"):
            return serveur
        if code == 200:
            serveur.terminate()
            raise SystemExit("L'API repond mais pas sa base. Lancer `make up` puis `make charger`.")
        time.sleep(0.2)
    serveur.terminate()
    raise SystemExit(f"L'API n'a pas demarre en {DELAI_DEMARRAGE_S:.0f} s.")


def memoire_mo(serveur: subprocess.Popen[bytes]) -> float:
    """Memoire resident du processus serveur, en mega-octets.

    `ps` et non une bibliotheque : la question est posee une fois, a la fin, et ajouter une
    dependance pour lire une colonne que le systeme affiche deja serait disproportionne.
    """
    try:
        sortie = subprocess.run(  # noqa: S603
            ["/bin/ps", "-o", "rss=", "-p", str(serveur.pid)],
            capture_output=True,
            text=True,
            check=True,
        )
        return int(sortie.stdout.strip()) / 1024
    except (subprocess.CalledProcessError, ValueError):
        return 0.0


def un_marche_existant() -> str:
    """Prend un numero de marche dans les donnees chargees, pour mesurer la route de detail.

    Un numero ecrit en dur dans le banc rendrait la mesure dependante d'une collecte precise :
    le jour ou ce marche disparait des donnees, la route mesuree renvoie 404 et la latence
    mesuree devient celle d'une erreur, sans que personne ne s'en apercoive.
    """
    _, code, corps = appeler("/marches?taille=1")
    if code != 200 or not corps or not corps["resultats"]:
        raise SystemExit("Aucun marche charge : lancer `make charger`.")
    return str(corps["resultats"][0]["marche_id"])


def routes_a_mesurer(marche_id: str) -> list[tuple[str, str, str]]:
    """Les routes mesurees, avec ce que chacune represente pour un visiteur."""
    return [
        ("sante", "/sante", "le test de vie, lu par le conteneur"),
        (
            "recherche",
            "/marches?" + urllib.parse.urlencode({"q": "travaux de voirie"}),
            "la question la plus courante : du texte libre",
        ),
        (
            "recherche filtree",
            "/marches?"
            + urllib.parse.urlencode(
                {"q": "travaux de voirie", "annee": 2024, "departement": "35"}
            ),
            "du texte et deux filtres, soit la page de resultats reelle",
        ),
        (
            "recherche page 5",
            "/marches?" + urllib.parse.urlencode({"q": "travaux", "page": 5}),
            "la pagination profonde, ou offset coute",
        ),
        ("liste recente", "/marches?taille=10", "sans texte : l'index sur la date"),
        (
            "un marche",
            f"/marches/{urllib.parse.quote(marche_id)}",
            "la fiche d'un marche et ses signaux",
        ),
        ("signaux", "/signaux?taille=10", "les marches a examiner, par l'index partiel"),
        ("statistiques", "/statistiques", "les comptages de la page d'accueil"),
        ("par annee", "/statistiques/annees", "la courbe de la page d'accueil"),
        (
            "assistant",
            "/assistant?"
            + urllib.parse.urlencode(
                {"question": "combien de marches de voirie en Bretagne en 2024"}
            ),
            "une question en francais, traduite en SQL",
        ),
    ]


def mesurer_les_routes(marche_id: str) -> list[dict[str, Any]]:
    """Mesure chaque route en serie, et verifie au passage qu'elle repond bien."""
    lignes = []
    for nom, chemin, role in routes_a_mesurer(marche_id):
        # Le premier appel est mesure a part et non jete. C'est le cas froid, celui que vit le
        # premier visiteur apres un deploiement, et c'est lui qui a montre que le plafond de
        # candidats de la recherche etait trop haut : il depassait le delai du service alors que
        # la mediane a chaud etait de 57 ms. Un code autre que 200 est enregistre ici plutot que
        # de faire echouer le banc : un service lent a froid est un fait a publier.
        froid_ms, code_froid, _ = appeler(chemin)

        durees = []
        codes = set()
        for _ in range(REPETITIONS - 1):
            duree, code, _ = appeler(chemin)
            codes.add(code)
            durees.append(duree)
        if codes != {200}:
            raise SystemExit(f"La route {nom} a renvoye {sorted(codes)} au lieu de 200.")
        lignes.append(
            {
                "route": nom,
                "chemin": chemin,
                "ce_que_ca_represente": role,
                "appels": len(durees),
                "premier_appel_ms": round(froid_ms, 1),
                "premier_appel_code": code_froid,
                "p50_ms": round(statistics.median(durees), 1),
                "p95_ms": round(centile(durees, 0.95), 1),
                "minimum_ms": round(min(durees), 1),
                "maximum_ms": round(max(durees), 1),
            }
        )
        derniere = lignes[-1]
        print(
            f"  {nom:24} premier {derniere['premier_appel_ms']:8.1f} ms"
            f"   p50 {derniere['p50_ms']:7.1f} ms   p95 {derniere['p95_ms']:7.1f} ms"
        )
    return lignes


def mesurer_les_comptages() -> tuple[float, float]:
    """Compare le calcul des comptages a leur lecture dans la table d'une ligne.

    C'est la mesure qui justifie `base/schema/008-table-statistiques.sql`. Elle se fait en SQL
    direct : le calcul depasse le delai de dix secondes que l'API s'impose, donc il ne peut pas
    etre mesure a travers elle, ce qui est exactement le probleme que la table resout.
    """
    calcul = """
        select
            count(*), count(distinct marche_id), count(distinct acheteur_siret),
            count(distinct titulaire_siret), sum(montant), min(annee), max(annee)
        from marches
    """
    with (
        psycopg.connect(chaine_de_connexion("make bench-api")) as connexion,
        connexion.cursor() as curseur,
    ):
        curseur.execute(
            "select set_config(%s, %s, false)", ("statement_timeout", str(DELAI_MESURE_MS))
        )
        depart = time.perf_counter()
        curseur.execute(calcul)
        curseur.fetchone()
        duree_calcul = (time.perf_counter() - depart) * 1000

        # La lecture est mesuree plusieurs fois : a cette echelle, un seul appel mesure surtout
        # le bruit du reseau local.
        lectures = []
        for _ in range(20):
            depart = time.perf_counter()
            curseur.execute("select * from statistiques")
            curseur.fetchone()
            lectures.append((time.perf_counter() - depart) * 1000)
    return duree_calcul, statistics.median(lectures)


def mesurer_la_charge() -> list[dict[str, Any]]:
    """Fait monter la concurrence et regarde ou le service plie.

    La question posee : le choix d'un pilote synchrone dans des routes `def`, donc executees
    dans une reserve de fils, tient-il jusqu'ou. La reponse n'est pas une opinion, c'est le
    palier a partir duquel le p95 decroche alors que le debit n'augmente plus.
    """
    chemin = "/marches?" + urllib.parse.urlencode({"q": "travaux de voirie"})
    lignes = []
    for concurrence in PALIERS:
        appeler(chemin)  # un appel a vide, pour ne pas mesurer le premier
        depart = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrence) as groupe:
            resultats = list(groupe.map(lambda _: appeler(chemin), range(APPELS_PAR_PALIER)))
        total_s = time.perf_counter() - depart
        durees = [duree for duree, code, _ in resultats if code == 200]
        echecs = sum(1 for _, code, _ in resultats if code != 200)
        lignes.append(
            {
                "clients_simultanes": concurrence,
                "appels": APPELS_PAR_PALIER,
                "echecs": echecs,
                "debit_par_seconde": round(len(durees) / total_s, 1),
                "p50_ms": round(statistics.median(durees), 1) if durees else 0.0,
                "p95_ms": round(centile(durees, 0.95), 1) if durees else 0.0,
            }
        )
        derniere = lignes[-1]
        print(
            f"  {concurrence:2} clients   {derniere['debit_par_seconde']:7.1f} req/s"
            f"   p50 {derniere['p50_ms']:7.1f} ms   p95 {derniere['p95_ms']:7.1f} ms"
            f"   echecs {echecs}"
        )
    return lignes


def mesurer_le_classement() -> list[dict[str, Any]]:
    """Compare le classement exact au classement borne, en SQL direct.

    En SQL direct et non par HTTP : la requete exacte depasse le delai de dix secondes que l'API
    s'impose, donc elle ne peut pas etre mesuree a travers elle. C'est tout l'objet de la
    mesure, et c'est la raison pour laquelle cette comparaison ne passe pas par le service.

    Ce qui est compare : les dix marches affiches. Un ecart ne veut pas dire qu'une reponse est
    fausse, mais que l'ordre differe ; le dire en nombre de marches communs sur dix est la facon
    la plus honnete de l'annoncer, parce que c'est ce que le visiteur voit.
    """
    exacte = (
        "with analysee as (select websearch_to_tsquery('public.francais', %s) as requete)"
        " select marche_id, ts_rank_cd(recherche, analysee.requete) as score, montant"
        " from marches, analysee"
        " where recherche @@ analysee.requete"
        " order by score desc, montant desc nulls last"
        " limit %s"
    )
    bornee = (
        "with analysee as (select websearch_to_tsquery('public.francais', %s) as requete),"
        " candidats as («"
        "  select marche_id, recherche, montant from marches, analysee"
        "  where recherche @@ analysee.requete limit %s"
        ")"
        " select marche_id, ts_rank_cd(recherche, analysee.requete) as score, montant"
        " from candidats, analysee"
        " order by score desc, montant desc nulls last"
        " limit %s"
    ).replace("(«", "(")
    comptage = (
        "select count(*) from marches"
        " where recherche @@ websearch_to_tsquery('public.francais', %s)"
    )

    lignes = []
    with (
        psycopg.connect(chaine_de_connexion("make bench-api")) as connexion,
        connexion.cursor() as curseur,
    ):
        curseur.execute(
            "select set_config(%s, %s, false)", ("statement_timeout", str(DELAI_MESURE_MS))
        )
        for question in QUESTIONS_DE_CLASSEMENT:
            curseur.execute(comptage, (question,))
            repondent = int((curseur.fetchone() or [0])[0])

            depart = time.perf_counter()
            curseur.execute(exacte, (question, PROFONDEUR_COMPAREE))
            dix_exacts = [ligne[0] for ligne in curseur.fetchall()]
            duree_exacte = (time.perf_counter() - depart) * 1000

            depart = time.perf_counter()
            curseur.execute(bornee, (question, PLAFOND_CANDIDATS, PROFONDEUR_COMPAREE))
            dix_bornes = [ligne[0] for ligne in curseur.fetchall()]
            duree_bornee = (time.perf_counter() - depart) * 1000

            communs = len(set(dix_exacts) & set(dix_bornes))
            lignes.append(
                {
                    "question": question,
                    "mots": len(question.split()),
                    "lignes_qui_repondent": repondent,
                    "bornee_par_le_plafond": repondent > PLAFOND_CANDIDATS,
                    "exact_ms": round(duree_exacte, 1),
                    "borne_ms": round(duree_bornee, 1),
                    "acceleration": round(duree_exacte / duree_bornee, 1) if duree_bornee else 0.0,
                    "communs_sur_dix": communs,
                    "ordre_identique": dix_exacts == dix_bornes,
                }
            )
            derniere = lignes[-1]
            print(
                f"  {question[:42]:44} {repondent:>8} lignes"
                f"   exact {derniere['exact_ms']:8.1f} ms"
                f"   borne {derniere['borne_ms']:7.1f} ms"
                f"   communs {communs}/10"
            )
    return lignes


def ecrire(nom: str, lignes: list[dict[str, Any]]) -> None:
    """Ecrit un CSV dans `mesures/resultats`, avec les colonnes de la premiere ligne."""
    if not lignes:
        return
    SORTIE.mkdir(parents=True, exist_ok=True)
    chemin = SORTIE / nom
    with chemin.open("w", encoding="utf-8", newline="") as fichier:
        # `lineterminator="\n"` : sans lui, le module csv ecrit des fins de ligne Windows,
        # que git signale a chaque ajout et qui font apparaitre tout le fichier comme modifie.
        auteur = csv.DictWriter(fichier, fieldnames=list(lignes[0]), lineterminator="\n")
        auteur.writeheader()
        auteur.writerows(lignes)
    print(f"ecrit : {chemin.relative_to(RACINE)}")


def main() -> None:
    print("Demarrage de l'API...")
    depart_demarrage = time.perf_counter()
    serveur = demarrer()
    demarrage_ms = (time.perf_counter() - depart_demarrage) * 1000
    print(f"prete en {demarrage_ms:.0f} ms (dont le chargement des lexiques de l'assistant)")

    try:
        marche_id = un_marche_existant()
        print("\nLatence par route, 20 appels chacune :")
        latences = mesurer_les_routes(marche_id)
        memoire = memoire_mo(serveur)

        print("\nSous charge, sur la route de recherche :")
        charge = mesurer_la_charge()

        print("\nComptages : calcules a la demande contre lus dans la table :")
        calcul_ms, lecture_ms = mesurer_les_comptages()
        print(f"  calcul   {calcul_ms:9.0f} ms")
        print(f"  lecture  {lecture_ms:9.2f} ms")
    finally:
        if serveur is not None:
            serveur.terminate()
            serveur.wait(timeout=20)
            print("API arretee.")

    print("\nClassement exact contre classement borne, en SQL direct :")
    classement = mesurer_le_classement()

    ecrire("api-latences.csv", latences)
    ecrire("api-charge.csv", charge)
    ecrire("api-classement.csv", classement)

    recherche = next(ligne for ligne in latences if ligne["route"] == "recherche")
    plafond = max(charge, key=lambda ligne: float(ligne["debit_par_seconde"]))
    ecrire(
        "api-resume.csv",
        [
            {
                "mesure": "demarrage",
                "valeur": round(demarrage_ms, 0),
                "unite": "ms",
                "commentaire": "ouverture de la reserve et chargement des lexiques",
            },
            {
                "mesure": "recherche, p50",
                "valeur": recherche["p50_ms"],
                "unite": "ms",
                "commentaire": "texte libre, HTTP comprise",
            },
            {
                "mesure": "recherche, p95",
                "valeur": recherche["p95_ms"],
                "unite": "ms",
                "commentaire": "le vingtieme visiteur le plus malchanceux",
            },
            {
                "mesure": "pire premier appel",
                "valeur": max(float(ligne["premier_appel_ms"]) for ligne in latences),
                "unite": "ms",
                "commentaire": "base froide, juste apres le demarrage : ce que vit le premier "
                "visiteur apres un deploiement",
            },
            {
                "mesure": "comptages calcules a la demande",
                "valeur": round(calcul_ms, 0),
                "unite": "ms",
                "commentaire": "count(distinct) sur deux millions de lignes : au-dela du delai "
                "de dix secondes de l'API",
            },
            {
                "mesure": "comptages lus dans la table",
                "valeur": round(lecture_ms, 2),
                "unite": "ms",
                "commentaire": "une table d'une ligne, remplie par make indexer",
            },
            {
                "mesure": "debit maximal mesure",
                "valeur": plafond["debit_par_seconde"],
                "unite": "requetes par seconde",
                "commentaire": f"a {plafond['clients_simultanes']} clients simultanes",
            },
            {
                "mesure": "questions bornees par le plafond",
                "valeur": sum(1 for ligne in classement if ligne["bornee_par_le_plafond"]),
                "unite": f"questions sur {len(classement)}",
                "commentaire": f"au-dela de {PLAFOND_CANDIDATS} lignes qui repondent, le "
                "classement est approche",
            },
            {
                "mesure": "pire ecart du classement borne",
                "valeur": min(int(ligne["communs_sur_dix"]) for ligne in classement),
                "unite": "marches communs sur dix",
                "commentaire": "entre les dix affiches et les dix du classement exact",
            },
            {
                "mesure": "memoire du service",
                "valeur": round(memoire, 1),
                "unite": "Mo",
                "commentaire": "processus uvicorn, reserve de connexions et lexiques compris",
            },
        ],
    )


if __name__ == "__main__":
    main()
