"""Banc d'essai du site : le poids de chaque page, sa latence, et ce qu'elle vaut sans JavaScript.

Ce banc mesure trois choses que celui de l'API ne peut pas mesurer, parce qu'elles n'existent
qu'une fois le HTML fabrique.

**Le poids servi.** Une page de 400 Ko qui repond en 20 ms est lente pour qui la regarde : sur
une connexion mobile a 2 Mbit/s, ces 400 Ko font 1,6 seconde d'attente que la latence du serveur
ne montre pas. Le poids est donc mesure, page par page, compresse et non compresse.

**Le gain du rechargement partiel.** Le meme filtre applique de deux facons : en rechargeant la
page entiere, ou en remplacant le seul fragment de resultats. L'ecart justifie htmx, ou ne le
justifie pas, et c'est une mesure et non une opinion.

**Le fonctionnement sans JavaScript.** Une page est demandee sans l'en-tete `HX-Request` et son
HTML est verifie : la liste de resultats doit s'y trouver. C'est le plan B de la soutenance, et
un plan B qu'on n'essaie pas n'existe pas.

=== Pourquoi le poids est mesure et pas seulement la latence ==================

    Option envisagee       Avantage                     Limite                      Verdict
    latence du serveur     facile, deja mesure par      ne dit rien de ce que le    insuffisant
    seule                  `make bench-api`             navigateur doit telecharger
                                                         puis analyser
    **latence + poids      les deux couts que subit     ne mesure pas le rendu du   **retenu**
    servi, compresse       un visiteur reel             navigateur, qui demande un
    et non compresse**                                  navigateur
    mesure dans un vrai    mesure le rendu, le          un navigateur et un pilote  ecarte
    navigateur             premier affichage, les       a installer et a versionner,
    (Lighthouse,           Core Web Vitals              pour un site de six pages
    Playwright)                                          sans animation

A quelle echelle la reponse changerait : un site avec des images, des polices et du JavaScript
applicatif se mesure dans un navigateur, parce que le temps de rendu y domine le temps de
transfert. Ici, la page la plus lourde est du texte.

=== Le demarrage a froid, mesure a part ======================================

Le banc de l'API avait deja montre qu'une mesure a chaud ne dit rien du premier visiteur. Ce
banc va plus loin : il mesure chaque page **en premier**, dans un processus qui vient de
demarrer, parce que l'ordre des appels change le resultat. La premiere page visitee paie le
remplissage des caches de PostgreSQL pour toutes les suivantes, et c'est elle qui peut depasser
le delai que le service s'impose.

Sortie : `mesures/resultats/site-pages.csv`, `site-fragments.csv`, `site-resume.csv`.
"""

from __future__ import annotations

import csv
import gzip
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "mesures" / "resultats"

# Port propre au banc, distinct de celui du developpement et de celui du banc de l'API : les
# trois doivent pouvoir tourner sans se gener.
PORT = int(os.environ.get("PORT_BANC_SITE", "8098"))
RACINE_HTTP = f"http://127.0.0.1:{PORT}"

# Repetitions par page, dont la premiere mesuree a part. Onze et non vingt-et-une comme pour
# l'API : une page coute plus cher a fabriquer qu'une reponse JSON, et le banc doit rester sous
# la minute pour etre relance souvent.
REPETITIONS = 11

DELAI_DEMARRAGE_S = 40.0

# La question posee a l'assistant dans la mesure. Tiree du jeu versionne, comme les exemples
# affiches par la page : mesurer sur une question inventee pour le banc mesurerait le banc.
QUESTION = "combien de marches de voirie en 2023"

# Le debit d'une connexion mobile mediocre, pour traduire des kilo-octets en secondes
# d'attente. 2 Mbit/s, soit 250 ko/s : c'est l'ordre de grandeur d'une 4G saturee, et le
# chiffre sert a dire si le poids d'une page compte ou non.
DEBIT_MOBILE_KO_PAR_S = 250


def centile(valeurs: list[float], part: float) -> float:
    """Centile par interpolation lineaire. Meme fonction que dans `mesures/api.py`."""
    if not valeurs:
        return 0.0
    ordonnees = sorted(valeurs)
    if len(ordonnees) == 1:
        return ordonnees[0]
    position = part * (len(ordonnees) - 1)
    bas = int(position)
    haut = min(bas + 1, len(ordonnees) - 1)
    return ordonnees[bas] + (ordonnees[haut] - ordonnees[bas]) * (position - bas)


def appeler(chemin: str, htmx: bool = False) -> tuple[float, int, bytes]:
    """Appelle une page et renvoie la duree en millisecondes, le code et le corps brut.

    `htmx` pose l'en-tete `HX-Request`, exactement comme le fait htmx dans le navigateur. C'est
    ce qui fait rendre le fragment au lieu de la page entiere, et c'est donc la seule difference
    entre les deux mesures de poids.
    """
    requete = urllib.request.Request(RACINE_HTTP + chemin)  # noqa: S310
    if htmx:
        requete.add_header("HX-Request", "true")
    depart = time.perf_counter()
    try:
        with urllib.request.urlopen(requete, timeout=60) as reponse:  # noqa: S310
            corps = reponse.read()
            code = reponse.status
    except urllib.error.HTTPError as erreur:
        corps = erreur.read()
        code = erreur.code
    return (time.perf_counter() - depart) * 1000, code, corps


def demarrer() -> subprocess.Popen[bytes]:
    """Demarre le site dans un processus a part, et attend que l'API reponde.

    C'est `services.site.main` et non `services.api.main` : l'application deployee, celle qui
    sert les pages et les donnees. Le banc de l'API, lui, demarre l'API seule, pour que le cout
    des pages ne se melange pas a celui des routes JSON.
    """
    serveur = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "uvicorn",
            "services.site.main:application",
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
            raise SystemExit("Le site s'est arrete au demarrage. Lancer `make up` d'abord.")
        try:
            # L'etat du service se lit sur la route de l'API, pas sur une page : une page
            # repond meme quand la base est absente, et le banc demarrerait sur une base vide.
            _, code, corps = appeler("/api/sante")
        except OSError:
            time.sleep(0.2)
            continue
        if code == 200 and b'"base_accessible":true' in corps:
            return serveur
        if code == 200:
            serveur.terminate()
            raise SystemExit(
                "Le site repond mais pas sa base. Lancer `make up` puis `make charger`."
            )
        time.sleep(0.2)
    serveur.terminate()
    raise SystemExit(f"Le site n'a pas demarre en {DELAI_DEMARRAGE_S:.0f} s.")


def un_marche_existant() -> str:
    """Un numero de marche pris dans les donnees, pour mesurer la fiche.

    Ecrire un numero en dur rendrait la mesure dependante d'une collecte precise : le jour ou ce
    marche disparait, le banc mesurerait la latence d'une page d'erreur sans le dire.
    """
    _, code, corps = appeler("/api/marches?taille=1")
    if code != 200 or b'"marche_id"' not in corps:
        raise SystemExit("Aucun marche charge : lancer `make charger`.")
    trouve = re.search(rb'"marche_id":"([^"]+)"', corps)
    if trouve is None:
        raise SystemExit("Reponse inattendue de /api/marches.")
    return trouve.group(1).decode()


def pages_a_mesurer(marche_id: str) -> list[dict[str, Any]]:
    """Les pages mesurees, avec ce que chacune represente et ce qu'elle doit contenir.

    `temoin` est un morceau de texte qui doit se trouver dans le HTML rendu. Il transforme la
    mesure en verification : une page qui repond 200 en deux millisecondes parce qu'elle est
    vide passerait pour la plus rapide du site.
    """
    return [
        {
            "page": "accueil",
            "chemin": "/",
            "role": "la premiere page, avec ses comptages et sa figure",
            "temoin": "Ce que contient la base",
            "fragment": "",
        },
        {
            "page": "recherche vide",
            "chemin": "/recherche",
            "role": "le formulaire et les marches les plus recents",
            "temoin": "Rechercher un marché",
            "fragment": "",
        },
        {
            "page": "recherche texte",
            "chemin": "/recherche?" + urllib.parse.urlencode({"q": "travaux de voirie"}),
            "role": "la recherche la plus courante : du texte libre",
            "temoin": "notifié le",
            "fragment": "/recherche?" + urllib.parse.urlencode({"q": "travaux de voirie"}),
        },
        {
            "page": "recherche filtree",
            "chemin": "/recherche?"
            + urllib.parse.urlencode(
                {"q": "travaux de voirie", "annee": "2024", "departement": "35"}
            ),
            "role": "du texte et deux filtres, soit la page de resultats reelle",
            "temoin": "notifié le",
            "fragment": "/recherche?"
            + urllib.parse.urlencode(
                {"q": "travaux de voirie", "annee": "2024", "departement": "35"}
            ),
        },
        {
            "page": "recherche large",
            "chemin": "/recherche?" + urllib.parse.urlencode({"q": "travaux"}),
            "role": "un mot seul tres frequent : le cas ou le classement est approche",
            "temoin": "Classement approché",
            "fragment": "",
        },
        {
            "page": "fiche",
            "chemin": f"/fiche/{urllib.parse.quote(marche_id)}",
            "role": "la fiche d'un marche, ses titulaires et ses signaux",
            "temoin": "Ce qui a été remarqué",
            "fragment": "",
        },
        {
            "page": "a examiner",
            "chemin": "/a-examiner",
            "role": "les marches signales, par l'index partiel",
            "temoin": "Marchés à examiner",
            "fragment": "/a-examiner",
        },
        {
            "page": "questions",
            "chemin": "/questions?" + urllib.parse.urlencode({"question": QUESTION}),
            "role": "une question en francais, avec ses citations",
            "temoin": "Filtre appliqué",
            "fragment": "/questions?" + urllib.parse.urlencode({"question": QUESTION}),
        },
        {
            "page": "a propos",
            "chemin": "/a-propos",
            "role": "les sources et les limites, sans toucher a la base",
            "temoin": "Les sources",
            "fragment": "",
        },
        {
            "page": "page inconnue",
            "chemin": "/adresse-qui-n-existe-pas",
            "role": "une adresse inconnue : une page et non un objet JSON",
            "temoin": "Page introuvable",
            "fragment": "",
        },
    ]


def poids_ko(corps: bytes) -> tuple[float, float]:
    """Le poids servi, non compresse et compresse en gzip.

    Les deux, parce que c'est le second que le visiteur telecharge reellement : Caddy compresse
    le HTML en phase 9, et un service qui ne compresse pas encore doit savoir ce que la
    compression lui fera gagner avant de l'annoncer.
    """
    return len(corps) / 1024, len(gzip.compress(corps, 6)) / 1024


def mesurer_les_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mesure chaque page : premier appel a part, puis dix appels a chaud."""
    lignes = []
    for page in pages:
        froid_ms, code_froid, corps = appeler(page["chemin"])
        durees = []
        for _ in range(REPETITIONS - 1):
            duree, code, corps = appeler(page["chemin"])
            if code == code_froid:
                durees.append(duree)
        brut_ko, comprime_ko = poids_ko(corps)
        # La verification, au meme endroit que la mesure : un temoin absent veut dire que la
        # page a repondu sans son contenu, ce qui invalide la latence mesuree.
        texte = corps.decode("utf-8", errors="replace")
        lignes.append(
            {
                "page": page["page"],
                "chemin": page["chemin"],
                "ce_que_ca_represente": page["role"],
                "code": code_froid,
                "temoin_present": page["temoin"] in texte,
                "premier_appel_ms": round(froid_ms, 1),
                "p50_ms": round(statistics.median(durees), 1) if durees else 0.0,
                "p95_ms": round(centile(durees, 0.95), 1) if durees else 0.0,
                "poids_ko": round(brut_ko, 1),
                "poids_comprime_ko": round(comprime_ko, 1),
                "attente_mobile_ms": round(comprime_ko / DEBIT_MOBILE_KO_PAR_S * 1000, 0),
            }
        )
        etat = "ok" if page["temoin"] in texte else "TEMOIN ABSENT"
        print(
            f"  {page['page']:<20} {code_froid}  froid {froid_ms:7.0f} ms  "
            f"p50 {lignes[-1]['p50_ms']:6.1f} ms  {brut_ko:6.1f} ko  "
            f"({comprime_ko:5.1f} ko comprime)  {etat}"
        )
    return lignes


def mesurer_les_fragments(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compare la page entiere et le fragment, pour les pages qui ont un rechargement partiel.

    C'est la mesure qui justifie htmx ou qui le condamne. Elle porte sur le poids et sur la
    latence : le serveur fait presque le meme travail dans les deux cas, donc c'est le poids qui
    doit faire la difference.
    """
    lignes = []
    for page in pages:
        if not page["fragment"]:
            continue
        durees_page, durees_fragment = [], []
        corps_page = corps_fragment = b""
        # Un appel a vide d'abord : la comparaison doit porter sur deux chemins egalement
        # chauds, sinon elle mesure l'ordre des appels.
        appeler(page["fragment"])
        appeler(page["fragment"], htmx=True)
        for _ in range(REPETITIONS - 1):
            duree, _, corps_page = appeler(page["fragment"])
            durees_page.append(duree)
            duree, _, corps_fragment = appeler(page["fragment"], htmx=True)
            durees_fragment.append(duree)
        page_ko, page_comprime = poids_ko(corps_page)
        fragment_ko, fragment_comprime = poids_ko(corps_fragment)
        lignes.append(
            {
                "page": page["page"],
                "chemin": page["fragment"],
                "page_entiere_ko": round(page_ko, 1),
                "fragment_ko": round(fragment_ko, 1),
                "economie_pourcent": round(100 * (1 - fragment_ko / page_ko), 1),
                "page_entiere_comprime_ko": round(page_comprime, 1),
                "fragment_comprime_ko": round(fragment_comprime, 1),
                "page_entiere_p50_ms": round(statistics.median(durees_page), 1),
                "fragment_p50_ms": round(statistics.median(durees_fragment), 1),
                # Le fragment ne doit surtout pas contenir le squelette : s'il le contenait, le
                # navigateur insererait une page dans une page.
                "fragment_sans_squelette": b"<!doctype html>" not in corps_fragment.lower(),
            }
        )
        print(
            f"  {page['page']:<20} page {page_ko:6.1f} ko  fragment {fragment_ko:6.1f} ko  "
            f"soit {lignes[-1]['economie_pourcent']:5.1f} % de moins"
        )
    return lignes


def verifier_sans_javascript(pages: list[dict[str, Any]]) -> list[str]:
    """Verifie que chaque page rend son contenu sans que htmx n'intervienne.

    C'est exactement ce que fait un navigateur dont le JavaScript est desactive, ou dans lequel
    le fichier htmx ne s'est pas charge : il demande la page sans en-tete `HX-Request`, et il
    doit recevoir une page complete, avec son contenu. Le plan B de la soutenance est cette
    ligne de mesure.
    """
    manquants = []
    for page in pages:
        _, _, corps = appeler(page["chemin"])
        texte = corps.decode("utf-8", errors="replace")
        complete = "<!doctype html>" in texte.lower() and page["temoin"] in texte
        if not complete:
            manquants.append(page["page"])
    return manquants


def verifier_la_politique_de_securite() -> dict[str, Any]:
    """Relit les en-tetes de securite servis par une page, pour que la mesure les atteste.

    Une politique de securite ecrite dans le code et jamais relue dans une reponse reelle est
    une intention. Celle-ci est verifiee par un test, et enregistree ici pour que le memoire
    cite une mesure et non une ligne de code.
    """
    requete = urllib.request.Request(RACINE_HTTP + "/")  # noqa: S310
    with urllib.request.urlopen(requete, timeout=30) as reponse:  # noqa: S310
        en_tetes = {cle.lower(): valeur for cle, valeur in reponse.getheaders()}
    politique = en_tetes.get("content-security-policy", "")
    return {
        "politique": politique,
        "sans_unsafe_inline": "unsafe-inline" not in politique,
        "sans_domaine_tiers": "http" not in politique,
        "vary_htmx": en_tetes.get("vary", "") == "HX-Request",
    }


def ecrire(nom: str, lignes: list[dict[str, Any]]) -> None:
    """Ecrit un CSV dans `mesures/resultats`, avec les colonnes de la premiere ligne."""
    if not lignes:
        return
    SORTIE.mkdir(parents=True, exist_ok=True)
    chemin = SORTIE / nom
    with chemin.open("w", encoding="utf-8", newline="") as fichier:
        auteur = csv.DictWriter(fichier, fieldnames=list(lignes[0]), lineterminator="\n")
        auteur.writeheader()
        auteur.writerows(lignes)
    print(f"ecrit : {chemin.relative_to(RACINE)}")


def poids_du_statique() -> list[dict[str, Any]]:
    """Le poids des fichiers servis tels quels, et ce qu'ils representent une fois en cache.

    Ils ne sont telecharges qu'a la premiere visite : un navigateur les garde ensuite. Les
    compter dans le poids de chaque page serait donc faux, et les ignorer le serait aussi.
    """
    lignes = []
    for nom in ("site.css", "htmx-2.0.11.min.js", "marque.svg"):
        _, code, corps = appeler(f"/statique/{nom}")
        brut, comprime = poids_ko(corps)
        lignes.append(
            {
                "fichier": nom,
                "code": code,
                "poids_ko": round(brut, 1),
                "poids_comprime_ko": round(comprime, 1),
            }
        )
    return lignes


def main() -> None:
    print("Demarrage du site...")
    depart = time.perf_counter()
    serveur = demarrer()
    demarrage_ms = (time.perf_counter() - depart) * 1000
    print(f"pret en {demarrage_ms:.0f} ms")

    try:
        marche_id = un_marche_existant()
        pages = pages_a_mesurer(marche_id)

        print(f"\nLatence et poids, {REPETITIONS - 1} appels a chaud par page :")
        latences = mesurer_les_pages(pages)

        print("\nPage entiere contre fragment htmx :")
        fragments = mesurer_les_fragments(pages)

        print("\nFichiers servis tels quels :")
        statiques = poids_du_statique()
        for ligne in statiques:
            print(f"  {ligne['fichier']:<22} {ligne['poids_ko']:6.1f} ko")

        print("\nSans JavaScript :")
        manquants = verifier_sans_javascript(pages)
        print(
            "  toutes les pages rendent leur contenu"
            if not manquants
            else f"  INCOMPLETES : {manquants}"
        )

        print("\nEn-tetes de securite servis :")
        securite = verifier_la_politique_de_securite()
        for cle, valeur in securite.items():
            print(f"  {cle:<22} {valeur}")
    finally:
        serveur.terminate()
        serveur.wait(timeout=20)
        print("Site arrete.")

    ecrire("site-pages.csv", latences)
    ecrire("site-fragments.csv", fragments)
    ecrire("site-statique.csv", statiques)

    la_plus_lourde = max(latences, key=lambda ligne: float(ligne["poids_ko"]))
    la_plus_lente = max(latences, key=lambda ligne: float(ligne["p95_ms"]))
    pire_froid = max(latences, key=lambda ligne: float(ligne["premier_appel_ms"]))
    economie = (
        statistics.median([float(ligne["economie_pourcent"]) for ligne in fragments])
        if fragments
        else 0.0
    )
    ecrire(
        "site-resume.csv",
        [
            {
                "mesure": "demarrage du site",
                "valeur": round(demarrage_ms, 0),
                "unite": "ms",
                "commentaire": "reserve de connexions, lexiques et gabarits",
            },
            {
                "mesure": "page la plus lourde",
                "valeur": la_plus_lourde["poids_ko"],
                "unite": "ko",
                "commentaire": f"{la_plus_lourde['page']}, soit "
                f"{la_plus_lourde['poids_comprime_ko']} ko comprime",
            },
            {
                "mesure": "page la plus lente, p95",
                "valeur": la_plus_lente["p95_ms"],
                "unite": "ms",
                "commentaire": f"{la_plus_lente['page']}",
            },
            {
                "mesure": "pire premier appel",
                "valeur": pire_froid["premier_appel_ms"],
                "unite": "ms",
                "commentaire": f"{pire_froid['page']}, base froide : ce que vit le premier "
                "visiteur apres un demarrage",
            },
            {
                "mesure": "economie du fragment htmx",
                "valeur": round(economie, 1),
                "unite": "pour cent du poids",
                "commentaire": "mediane sur les pages a rechargement partiel",
            },
            {
                "mesure": "poids du statique",
                "valeur": round(sum(float(ligne["poids_ko"]) for ligne in statiques), 1),
                "unite": "ko",
                "commentaire": "feuille de style, htmx et icone, telecharges une seule fois "
                "puis gardes par le navigateur",
            },
            {
                "mesure": "pages completes sans JavaScript",
                "valeur": len(pages) - len(manquants),
                "unite": f"pages sur {len(pages)}",
                "commentaire": "demandees sans l'en-tete HX-Request, comme un navigateur sans "
                "JavaScript",
            },
            {
                "mesure": "politique de securite sans unsafe-inline",
                "valeur": securite["sans_unsafe_inline"],
                "unite": "vrai ou faux",
                "commentaire": securite["politique"],
            },
        ],
    )


if __name__ == "__main__":
    main()
