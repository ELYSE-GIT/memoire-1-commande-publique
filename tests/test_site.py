"""Tests du site, sans PostgreSQL et sans navigateur.

Memes principes que `tests/test_api.py` : la dependance `curseur` est remplacee par un faux
curseur, le cycle de vie n'est pas joue, et rien ne sort de la machine. Ce qui change, c'est ce
qui est verifie : une page n'est pas une reponse JSON, et ses defauts ne sont pas les memes.

    Ce que ces tests attrapent                       Ce qu'ils n'attrapent pas
    une page qui ne se rend plus                     une page laide
    un fragment qui emporte le squelette de la page  un contraste insuffisant
    un en-tete de securite absent ou trop permissif  une page lente
    une variable de gabarit renommee d'un cote       un enchainement de clics casse
    une adresse revendiquee par le site et par l'API
    un exemple affiche qui n'est plus dans le jeu
    un formulaire qui refuse ses propres champs vides

Ce qui manque est couvert ailleurs : `make bench-site` mesure le poids et la latence de chaque
page sur la vraie base, verifie qu'elles se rendent sans JavaScript et relit les en-tetes
servis ; la verification a l'oeil, elle, se fait dans un navigateur et se raconte dans le
journal.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from services.api import requetes
from services.api.base import (
    QUESTIONS_DE_PRECHAUFFAGE,
    Etat,
    curseur,
    curseur_positionnel,
)
from services.api.main import PREFIXE_API, application
from services.site import pages
from services.site.main import application as application_du_site
from tests.test_api import LIGNE, LIGNE_SIGNAL, FauxCurseur

RACINE = Path(__file__).resolve().parent.parent
GABARITS = RACINE / "services" / "site" / "gabarits"
QUESTIONS = RACINE / "mesures" / "verification" / "questions-assistant.csv"

# Une ligne de la table des comptages, telle que la page d'accueil la lit.
COMPTAGES = {
    "marches": 1_999_474,
    "marches_distincts": 1_738_289,
    "acheteurs": 28_879,
    "titulaires": 208_468,
    "montant_total": 1_500_944_336_475.13,
    "montant_total_marches": 1_098_205_917_601.62,
    "premiere_annee": 2015,
    "derniere_annee": 2026,
    "marches_signales": 57_409,
    "calcule_a": "2026-10-22T15:26:06",
}

ANNEE = {
    "annee": 2024,
    "attributions": 307_824,
    "montant_total": 180_000_000.00,
    "attributions_resolues": 262_856,
    "attributions_pme": 163_234,
    "part_pme_pourcent": 62.1,
}


def client(lots: list[list[dict[str, Any]]] | None = None) -> TestClient:
    """Un client de test sur l'application deployee, pages comprises.

    C'est `services.site.main` et non `services.api.main` : les gestionnaires d'erreur qui
    rendent du HTML y sont poses, et les tester sur l'autre application testerait l'inverse de
    ce qui est deploye.
    """
    application_du_site.state.etat = Etat()
    faux = FauxCurseur(lots)
    application_du_site.dependency_overrides[curseur] = lambda: faux
    application_du_site.dependency_overrides[curseur_positionnel] = lambda: faux
    return TestClient(application_du_site, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _nettoyer() -> Any:
    yield
    application_du_site.dependency_overrides.clear()
    application.dependency_overrides.clear()


# --- Les pages se rendent ----------------------------------------------------


def test_la_page_d_accueil_affiche_les_comptages_et_leur_date() -> None:
    """Un comptage sans sa date ne dit pas s'il est perime.

    C'est la premiere question qu'un jury pose devant une page d'accueil chiffree.
    """
    reponse = client([[COMPTAGES], [ANNEE]]).get("/")
    assert reponse.status_code == 200
    assert "1 999 474" in reponse.text
    assert "22/10/2026" in reponse.text


def test_la_page_d_accueil_affiche_le_total_dedoublonne_et_l_ecart() -> None:
    """Additionner les montants ligne par ligne surcompte de 36,7 pour cent.

    Afficher le total brut sans le dire ferait circuler un chiffre faux de 403 milliards
    d'euros, et un total d'argent public est exactement ce qu'on reprend sans verifier.
    """
    texte = client([[COMPTAGES], [ANNEE]]).get("/").text
    assert "1 098 205 917 602" in texte
    assert "1 500 944 336 475" in texte
    assert "36,7" in texte


def test_la_figure_de_l_accueil_est_un_svg_sans_style_en_ligne() -> None:
    """La geometrie passe par des attributs SVG, jamais par un attribut `style`.

    Autoriser le style en ligne obligerait a ouvrir `'unsafe-inline'` dans la politique de
    securite, donc a accepter n'importe quel attribut `style` injecte dans une page.
    """
    texte = client([[COMPTAGES], [ANNEE]]).get("/").text
    svg = texte[texte.index("<svg") : texte.index("</svg>")]
    assert "<rect" in svg
    assert "style=" not in svg


def test_une_recherche_affiche_ses_resultats_et_le_lien_vers_la_fiche() -> None:
    reponse = client([[LIGNE]]).get("/recherche", params={"q": "travaux de voirie"})
    assert reponse.status_code == 200
    assert LIGNE["objet"] in reponse.text
    assert f'href="/fiche/{LIGNE["marche_id"]}"' in reponse.text


def test_la_fiche_dit_pourquoi_un_marche_a_plusieurs_lignes() -> None:
    """Voir deux fois le meme numero sans explication ressemble a un doublon."""
    deux = [dict(LIGNE), {**LIGNE, "titulaire_nom": "Autre entreprise"}]
    reponse = client([deux, [LIGNE_SIGNAL]]).get(f"/fiche/{LIGNE['marche_id']}")
    assert reponse.status_code == 200
    assert "groupement" in reponse.text
    assert "Autre entreprise" in reponse.text


def test_un_marche_inconnu_rend_une_page_et_non_un_objet_json() -> None:
    """404 est une reponse normale pour un visiteur : il doit pouvoir repartir d'ici."""
    reponse = client([[]]).get("/fiche/inexistant")
    assert reponse.status_code == 404
    assert reponse.headers["content-type"].startswith("text/html")
    assert "Retour à l'accueil" in reponse.text


def test_une_adresse_inconnue_rend_une_page_et_non_un_objet_json() -> None:
    reponse = client().get("/une-adresse-qui-n-existe-pas")
    assert reponse.status_code == 404
    assert reponse.headers["content-type"].startswith("text/html")
    assert "<!doctype html>" in reponse.text.lower()


def test_l_api_garde_ses_erreurs_en_json() -> None:
    """Le site rend du HTML, l'API rend du JSON, et c'est le chemin qui decide.

    Se fier a l'en-tete `Accept` donnerait du JSON a un navigateur une fois sur deux : un
    navigateur declare accepter a peu pres tout.
    """
    reponse = client().get(f"{PREFIXE_API}/marches", params={"page": 0})
    assert reponse.status_code == 422
    assert reponse.headers["content-type"].startswith("application/json")


def test_la_page_a_propos_ne_touche_pas_a_la_base() -> None:
    """Elle doit rester lisible quand la base ne repond pas.

    C'est exactement le moment ou l'on veut savoir ce que le site affiche d'habitude.
    """
    faux = FauxCurseur()
    application_du_site.state.etat = Etat()
    application_du_site.dependency_overrides[curseur] = lambda: faux
    reponse = TestClient(application_du_site).get("/a-propos")
    assert reponse.status_code == 200
    assert faux.appels == []


# --- Le rechargement partiel -------------------------------------------------


def test_une_requete_htmx_rend_le_fragment_seul() -> None:
    """Un fragment qui emporterait le squelette insererait une page dans une page."""
    entiere = client([[LIGNE]]).get("/recherche", params={"q": "voirie"})
    fragment = client([[LIGNE]]).get(
        "/recherche", params={"q": "voirie"}, headers={"HX-Request": "true"}
    )
    assert fragment.status_code == 200
    assert "<!doctype html>" not in fragment.text.lower()
    assert "<form" not in fragment.text
    assert LIGNE["objet"] in fragment.text
    # Le fragment est bien plus leger que la page : c'est la raison d'etre de htmx, et
    # `make bench-site` en publie le chiffre exact.
    assert len(fragment.content) < len(entiere.content)


def test_une_reponse_de_page_declare_varier_selon_l_en_tete_htmx() -> None:
    """Sans `Vary`, un cache rendrait un fragment a qui demande la page entiere.

    Le visiteur verrait une liste de resultats sans entete ni feuille de style, et seulement
    parfois, ce qui est la pire forme de defaut.
    """
    reponse = client([[LIGNE]]).get("/recherche")
    assert reponse.headers["vary"] == "HX-Request"


# --- La securite -------------------------------------------------------------


def test_la_politique_de_contenu_du_site_n_autorise_aucun_tiers() -> None:
    """htmx est versionne dans le depot, donc aucun domaine externe n'a a etre autorise."""
    politique = client([[COMPTAGES], [ANNEE]]).get("/").headers["content-security-policy"]
    assert "default-src 'none'" in politique
    assert "script-src 'self'" in politique
    assert "frame-ancestors 'none'" in politique
    assert "unsafe-inline" not in politique
    assert "unsafe-eval" not in politique
    assert "http" not in politique


def test_la_politique_du_site_ne_remplace_pas_celle_de_l_api() -> None:
    """Une reponse JSON ne charge rien : tout doit rester interdit pour elle."""
    politique = client([[LIGNE]]).get(f"{PREFIXE_API}/marches").headers["content-security-policy"]
    assert politique == "default-src 'none'; frame-ancestors 'none'"


def test_les_en_tetes_de_securite_sont_poses_aussi_sur_les_pages() -> None:
    en_tetes = client([[COMPTAGES], [ANNEE]]).get("/").headers
    assert en_tetes["x-content-type-options"] == "nosniff"
    assert en_tetes["x-frame-options"] == "DENY"
    assert "referrer-policy" in en_tetes


def test_le_texte_d_un_marche_est_echappe_dans_la_page() -> None:
    """Un objet de marche vient des donnees publiees, donc de l'exterieur.

    Jinja2 echappe par defaut, et ce test est la pour que personne ne desactive cet
    echappement « pour afficher un peu de mise en forme ».
    """
    piege = {**LIGNE, "objet": "<script>alert('x')</script> travaux"}
    texte = client([[piege]]).get("/recherche", params={"q": "travaux"}).text
    assert "<script>alert" not in texte
    assert "&lt;script&gt;" in texte


def test_aucun_script_ni_style_en_ligne_dans_les_pages_rendues() -> None:
    """La politique de securite interdit le script et le style en ligne : les pages s'y tiennent.

    La verification porte sur le HTML **rendu** et non sur le gabarit : c'est ce que le
    navigateur recoit, et c'est la seule version ou une boucle ou une condition a produit son
    resultat. La premiere ecriture de ce test lisait les gabarits, et elle se trompait de cible :
    elle voyait le mot « script » dans un commentaire Jinja2.
    """
    rendues = {
        "/": client([[COMPTAGES], [ANNEE]]).get("/").text,
        "/recherche": client([[LIGNE]]).get("/recherche", params={"q": "voirie"}).text,
        "/a-examiner": client([[LIGNE_SIGNAL]]).get("/a-examiner").text,
        "/a-propos": client().get("/a-propos").text,
    }
    for adresse, texte in rendues.items():
        for balise in re.findall(r"<script\b[^>]*>(.*?)</script>", texte, re.S):
            assert not balise.strip(), f"script en ligne sur {adresse}"
        assert " style=" not in texte, f"style en ligne sur {adresse}"


def test_htmx_est_servi_depuis_le_depot_et_non_depuis_un_cdn() -> None:
    """La demonstration ne doit dependre d'aucun reseau, et aucun tiers ne doit pouvoir
    remplacer le JavaScript de la page."""
    base = (GABARITS / "base.html").read_text(encoding="utf-8")
    assert "{{ chemin_statique }}/htmx-" in base
    assert "cdn." not in base
    fichiers = list((RACINE / "services" / "site" / "statique").glob("htmx-*.min.js"))
    assert len(fichiers) == 1, "une seule version de htmx versionnee"
    assert fichiers[0].name in base


def test_le_fichier_tiers_est_celui_qui_a_ete_publie() -> None:
    """htmx est la seule bibliotheque exterieure du depot : son empreinte est verifiee.

    Recopier un fichier tiers sans pouvoir dire d'ou il vient ni s'il a ete modifie ne vaut pas
    mieux que de le charger depuis un domaine inconnu. L'empreinte attendue est publiee dans
    `services/site/statique/README.md`, avec l'adresse et la date du telechargement.

    C'est aussi pour ce test que les hooks de pre-commit qui reformatent les fichiers excluent
    celui-ci : une simple fin de ligne ajoutee rendrait l'empreinte differente de celle publiee,
    donc invalide la seule chose qui permet de dire que le fichier n'a pas ete touche.
    """
    statique = RACINE / "services" / "site" / "statique"
    fichier = statique / "htmx-2.0.11.min.js"
    empreinte = hashlib.sha256(fichier.read_bytes()).hexdigest()
    documentation = (statique / "README.md").read_text(encoding="utf-8")
    assert empreinte in documentation, "empreinte differente de celle publiee dans le README"
    assert str(fichier.stat().st_size) in documentation.replace("\u202f", "").replace(" ", "")


def test_htmx_n_insere_pas_sa_propre_feuille_de_style() -> None:
    """Sans cette configuration, htmx ajoute un `<style>` en ligne que la politique bloque.

    Mesure dans un navigateur le 22 octobre 2026 : une violation signalee par page, et des
    styles d'attente qui existent deja dans site.css.
    """
    base = (GABARITS / "base.html").read_text(encoding="utf-8")
    configuration = re.search(r'name="htmx-config" content=\'([^\']+)\'', base)
    assert configuration is not None
    assert json.loads(configuration.group(1))["includeIndicatorStyles"] is False


# --- Les adresses ------------------------------------------------------------


def test_aucune_adresse_n_est_revendiquee_par_le_site_et_par_l_api() -> None:
    """Une page HTML et une reponse JSON ne peuvent pas repondre a la meme adresse.

    C'est la raison du prefixe de l'API, et ce test est ce qui empeche une page ajoutee plus
    tard de masquer une route sans que personne ne s'en apercoive : la premiere route declaree
    gagne, en silence.
    """
    du_site = {route.path for route in pages.routeur.routes}  # type: ignore[attr-defined]
    de_l_api = {
        route.path  # type: ignore[attr-defined]
        for route in application.routes
        if getattr(route, "path", "").startswith(PREFIXE_API)
    }
    assert du_site & de_l_api == set()
    assert all(not chemin.startswith(PREFIXE_API) for chemin in du_site)


def test_chaque_gabarit_cite_par_le_code_existe() -> None:
    """Un nom de gabarit est une chaine de caracteres : rien ne le verifie avant l'execution.

    Une page qui n'est visitee qu'en demonstration echouerait alors devant le jury.
    """
    sources = (RACINE / "services" / "site").rglob("*.py")
    cites = set()
    for source in sources:
        cites |= set(re.findall(r'"([a-z0-9/_-]+\.html)"', source.read_text(encoding="utf-8")))
    assert cites, "aucun gabarit cite : le motif de recherche est faux"
    for nom in cites:
        assert (GABARITS / nom).exists(), f"gabarit absent : {nom}"


def test_chaque_gabarit_present_est_utilise() -> None:
    """Un gabarit que plus rien n'appelle est du code mort qu'on croit relire."""
    sources = "\n".join(
        source.read_text(encoding="utf-8")
        for source in (RACINE / "services" / "site").rglob("*")
        if source.suffix in (".py", ".html")
    )
    for gabarit in GABARITS.rglob("*.html"):
        relatif = gabarit.relative_to(GABARITS).as_posix()
        assert relatif in sources, f"gabarit jamais appele : {relatif}"


# --- Le formulaire -----------------------------------------------------------


@pytest.mark.parametrize(
    "champs",
    [
        {"q": "", "annee": "", "departement": "", "montant_minimum": ""},
        {"q": "voirie", "annee": "pas une annee"},
        {"q": "voirie", "annee": "1800"},
        {"q": "voirie", "montant_minimum": "100 000,50"},
        {"q": "voirie", "montant_maximum": "n'importe quoi"},
    ],
)
def test_un_formulaire_mal_rempli_ne_renvoie_pas_une_erreur(champs: dict[str, str]) -> None:
    """Un formulaire HTML envoie tous ses champs, y compris ceux laisses vides.

    Refuser la recherche parce qu'une case est vide serait un defaut, pas une validation.
    L'API, elle, reste stricte : son appelant est un programme.
    """
    reponse = client([[LIGNE]]).get("/recherche", params=champs)
    assert reponse.status_code == 200


def test_un_encadrement_de_montant_absurde_est_dit_en_francais() -> None:
    """Le visiteur a inverse deux cases : il n'a pas besoin d'un code de statut."""
    reponse = client().get(
        "/recherche", params={"montant_minimum": "1000000", "montant_maximum": "10"}
    )
    assert reponse.status_code == 200
    assert "supérieur au montant maximum" in reponse.text


def test_le_lien_de_page_suivante_conserve_les_filtres() -> None:
    """Perdre les filtres a la page deux est un defaut classique et silencieux.

    Les parametres sont repris de l'adresse courante, et non reconstruits depuis les criteres :
    ce que le visiteur a demande doit etre conserve, y compris ce que le site ignore.
    """
    page_de_resultats = client([[LIGNE] * 11]).get(
        "/recherche", params={"q": "voirie", "annee": "2024", "departement": "35"}
    )
    suivante = re.search(r'href="(/recherche\?[^"]*page=2)"', page_de_resultats.text)
    assert suivante is not None
    adresse = suivante.group(1)
    assert "annee=2024" in adresse
    assert "departement=35" in adresse


# --- Ce que la page promet au lecteur ----------------------------------------


def test_un_classement_approche_est_annonce_a_l_ecran() -> None:
    """Une approximation annoncee est une limite ; une approximation cachee est un mensonge.

    Au-dela du plafond de candidats, les dix marches affiches peuvent etre entierement
    differents des dix du classement exact : mesure, et donc ecrit sur la page.
    """
    bornee = {**LIGNE, "score": 0.1, "candidats_examines": requetes.PLAFOND_CANDIDATS}
    texte = client([[bornee]]).get("/recherche", params={"q": "travaux"}).text
    assert "Classement approché" in texte

    exacte = {**LIGNE, "score": 0.1, "candidats_examines": 12}
    texte = client([[exacte]]).get("/recherche", params={"q": "travaux de voirie"}).text
    assert "Classement approché" not in texte


def test_la_page_des_signaux_rappelle_ce_qu_un_signal_ne_dit_pas() -> None:
    """« A examiner » et non « anomalies » : la concordance mesuree est de 69,3 pour cent."""
    texte = client([[LIGNE_SIGNAL]]).get("/a-examiner").text
    assert "69,3" in texte
    assert "examiner" in texte


def test_chaque_page_renvoie_vers_l_adresse_de_l_api_qui_la_produit() -> None:
    """« Verifiable » veut dire qu'on peut obtenir la meme chose sans ce site."""
    texte = client([[COMPTAGES], [ANNEE]]).get("/").text
    assert f"{PREFIXE_API}/statistiques" in texte


# --- Les exemples affiches ---------------------------------------------------


def questions_du_jeu() -> set[str]:
    with QUESTIONS.open(encoding="utf-8") as fichier:
        return {ligne["question"] for ligne in csv.DictReader(fichier)}


def test_les_exemples_proposes_viennent_du_jeu_de_questions_versionne() -> None:
    """Sinon ce sont des exemples choisis pour bien paraitre.

    Ceux-la sont reverifies a chaque `make bench-assistant`, chiffres et citations compris.
    """
    jeu = questions_du_jeu()
    for exemple, _ in pages.EXEMPLES_DE_QUESTIONS:
        assert exemple in jeu, f"exemple absent du jeu versionne : {exemple}"


def test_chaque_exemple_propose_est_prechauffe_au_demarrage() -> None:
    """Un exemple sur lequel on clique en demonstration ne doit pas etre le cas froid.

    Mesure du 22 octobre 2026 : la premiere question sur des marches signales depassait les dix
    secondes du service sur une base qui vient de demarrer, et repondait 504.
    """
    for exemple, _ in pages.EXEMPLES_DE_QUESTIONS:
        assert exemple in QUESTIONS_DE_PRECHAUFFAGE, f"exemple non prechauffe : {exemple}"


def test_les_questions_de_prechauffage_viennent_du_jeu_versionne() -> None:
    jeu = questions_du_jeu()
    for question in QUESTIONS_DE_PRECHAUFFAGE:
        assert question in jeu, f"question de prechauffage inventee : {question}"


# --- La mise en forme --------------------------------------------------------


@pytest.mark.parametrize(
    ("valeur", "attendu"),
    [
        (1_999_474, "1 999 474"),
        (0, "0"),
        (None, "–"),
    ],
)
def test_les_nombres_sont_groupes_par_milliers(valeur: int | None, attendu: str) -> None:
    """Une espace fine insecable, et non un espace ordinaire : un nombre ne se coupe pas."""
    assert pages.nombre(valeur) == attendu


def test_un_montant_absent_ne_devient_pas_zero() -> None:
    """« 0 euro » est une affirmation ; « montant non publie » est un fait."""
    assert pages.euros(None) == "montant non publié"
    assert "184 000" in pages.euros(184_000)


def test_un_marche_a_montants_differents_n_est_pas_totalise() -> None:
    """Le montant d'une ligne de groupement est souvent celui du marche entier, repete.

    Les additionner donnerait un total multiplie par le nombre de titulaires.
    """

    class Ligne:
        def __init__(self, montant: float | None) -> None:
            self.montant = montant

    assert pages.somme_des_montants([Ligne(100.0), Ligne(100.0)]) == 100
    assert pages.somme_des_montants([Ligne(100.0), Ligne(50.0)]) is None
    assert pages.somme_des_montants([]) is None


def test_une_part_sans_denominateur_ne_vaut_pas_zero() -> None:
    """Sur une base vide, « 0 % de marches signales » est faux ; « on ne sait pas » est exact."""
    assert pages.part(0, 0) is None
    assert pages.part(1, 4) == 25.0
