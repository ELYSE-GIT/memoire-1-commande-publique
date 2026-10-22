"""Verifie que les chiffres cites dans le memoire correspondent aux mesures enregistrees.

Regle du projet : aucun chiffre n'est affirme sans mesure reproductible. Ce test rend la regle
executable. Si le jeu de donnees est retelecharge et qu'une valeur change, la chaine d'integration
echoue en nommant le chiffre devenu faux, et le texte du memoire doit etre mis a jour.

Ce test ne lit pas le fichier de 236 Mo : il compare le texte aux agregats deja versionnes dans
`mesures/resultats/`. Il tourne donc aussi en integration continue.

Ce qu'il attrape : un chiffre du memoire qui ne correspond plus aux donnees, une mesure supprimee,
un fichier d'agregat renomme.
Ce qu'il n'attrape pas : une phrase juste sur les chiffres et fausse sur le fond. Cela reste du
travail de relecture.
"""

import csv
import json
from collections.abc import Callable
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
RESULTATS = RACINE / "mesures" / "resultats"
MEMOIRE = RACINE / "memoire"


def qualite() -> dict[str, dict[str, str]]:
    """Le dernier rapport de qualite produit par `make bench-decp`."""
    rapports = sorted(RESULTATS.glob("*-decp-qualite.json"))
    assert rapports, "aucun rapport de qualite : lancer `make bench-decp`"
    mesures = json.loads(rapports[-1].read_text(encoding="utf-8"))["mesures"]
    return {nom: bloc["valeurs"] for nom, bloc in mesures.items()}


def agregat(nom: str) -> list[dict[str, str]]:
    """Un agregat descriptif produit par `make bench-decp-distributions`."""
    chemin = RESULTATS / f"{nom}.csv"
    assert chemin.exists(), f"agregat manquant : {nom}. Lancer `make bench-decp-distributions`"
    with chemin.open(encoding="utf-8") as fichier:
        return list(csv.DictReader(fichier))


# Chaque entree : le chiffre tel qu'il est ecrit dans le memoire, et la mesure qui le confirme.
CHIFFRES_DU_MEMOIRE = [
    ("3 283 035 lignes brutes", lambda: qualite()["volume"]["lignes"], "3283035"),
    ("1 833 468 marches distincts", lambda: qualite()["lignes_actuelles"]["marches"], "1833468"),
    (
        "2 114 675 lignes a l'etat actuel",
        lambda: qualite()["lignes_actuelles"]["lignes"],
        "2114675",
    ),
    (
        "environ 7 800 doublons residuels",
        lambda: qualite()["origine_des_lignes_multiples"]["doublons_residuels"],
        "7764",
    ),
    (
        "273 494 groupements d'entreprises",
        lambda: qualite()["origine_des_lignes_multiples"]["multi_titulaires"],
        "273494",
    ),
    ("48 596 montants absents", lambda: qualite()["montants"]["absents"], "48596"),
    (
        "59 588 montants negatifs ou nuls",
        lambda: qualite()["montants"]["negatifs_ou_nuls"],
        "59588",
    ),
    (
        "2 197 montants au-dessus du milliard",
        lambda: qualite()["montants"]["superieurs_au_milliard"],
        "2197",
    ),
    ("31 812 dates de notification absentes", lambda: qualite()["dates"]["absentes"], "31812"),
    ("1 441 dates anterieures a 2015", lambda: qualite()["dates"]["avant_2015"], "1441"),
    (
        "1 903 309 lignes sans le nombre d'offres",
        lambda: qualite()["offres_recues"]["absentes"],
        "1903309",
    ),
    (
        "290 752 lignes a offre unique",
        lambda: qualite()["offres_recues"]["une_seule_offre"],
        "290752",
    ),
]


@pytest.mark.parametrize(
    "libelle,mesure,attendu", CHIFFRES_DU_MEMOIRE, ids=[c[0] for c in CHIFFRES_DU_MEMOIRE]
)
def test_chiffre_cite_dans_le_memoire(
    libelle: str, mesure: Callable[[], str], attendu: str
) -> None:
    """Le chiffre ecrit dans le memoire doit correspondre a la mesure enregistree."""
    obtenu = mesure()
    assert obtenu == attendu, (
        f"Le memoire annonce « {libelle} » mais la mesure donne {obtenu}. "
        "Mettre le texte a jour, ou verifier que la mesure est bien celle attendue."
    )


def test_part_des_marches_sous_le_seuil_europeen() -> None:
    """Le memoire affirme que 63 % des marches sont sous 214 000 euros."""
    tranches = agregat("montants-tranches")
    sous_seuil = sum(float(t["part_pourcent"]) for t in tranches[:3])
    assert round(sous_seuil) == 63


def test_concentration_des_titulaires() -> None:
    """Le memoire affirme que 1 % des titulaires captent 53 % des montants, 10 % en captent 88."""
    courbe = agregat("concentration-titulaires")

    def part_au_seuil(seuil: float) -> int:
        point = min(courbe, key=lambda ligne: abs(float(ligne["part_titulaires"]) - seuil))
        return round(float(point["part_montants"]))

    assert part_au_seuil(1) == 53
    assert part_au_seuil(10) == 88


def test_completude_des_champs_faibles() -> None:
    """Le memoire cite trois champs sous la barre de la moitie."""
    parts = {
        ligne["champ"]: float(ligne["part_renseigne"]) for ligne in agregat("completude-champs")
    }
    assert parts["Offres recues"] == 42.5
    assert parts["Sous-traitance declaree"] == 39.1
    assert parts["Considerations sociales"] == 49.4


def test_intervalle_annonce_pour_quarante_sur_quarante() -> None:
    """Le chapitre 11 annonce [91,2 ; 100,0] pour les 40 intentions reconnues sur 40.

    C'est le chiffre le plus souvent repris du chapitre, et le plus facile a recopier de travers :
    il est verifie contre la mesure, comme les autres.
    """
    lignes = {ligne["mesure"]: ligne for ligne in agregat("incertitude-proportions")}
    intention = lignes["assistant : intention reconnue"]
    assert intention["succes"] == intention["essais"]
    assert float(intention["wilson_bas"]) == 91.2
    assert float(intention["wilson_haut"]) == 100.0
    # Et la formule ecartee, qui ne laisse aucune marge : c'est l'argument du chapitre.
    assert float(intention["wald_bas"]) == 100.0


def test_ce_que_la_fuite_ajoutait_a_la_detection() -> None:
    """Le chapitre 11 annonce 69,3 % hors echantillon, contre 73,3 % avec la fuite."""
    sur_le_test = {
        ligne["calibrage"]: ligne
        for ligne in agregat("stabilite-calibrage")
        if ligne["periode_evaluee"] == "test"
    }
    avec_fuite = float(sur_le_test["global (production actuelle)"]["precision_pourcent"])
    sans_fuite = float(sur_le_test["apprentissage seul"]["precision_pourcent"])
    assert avec_fuite == 73.3
    assert sans_fuite == 69.3
    assert round(avec_fuite - sans_fuite, 1) == 4.0
    # Les deux intervalles ne se chevauchent pas : c'est ce qui autorise a parler d'un ecart reel.
    assert float(sur_le_test["apprentissage seul"]["precision_haut"]) < float(
        sur_le_test["global (production actuelle)"]["precision_bas"]
    )


def test_encadrement_de_la_part_des_pme() -> None:
    """Le chapitre 11 annonce 60,8 % comptes, et un encadrement de 56,7 a 63,5."""
    pme = agregat("incertitude-recensement-pme")[0]
    assert float(pme["part_pme_sur_resolus_pourcent"]) == 60.8
    assert float(pme["borne_basse_pourcent"]) == 56.7
    assert float(pme["borne_haute_pourcent"]) == 63.5
    # La non-reponse est plus etroite que le hasard de tirage de l'ancien echantillon : c'est la
    # comparaison que la section fait, et elle doit rester vraie.
    assert float(pme["etendue_non_reponse_points"]) < float(
        pme["largeur_tirage_echantillon_points"]
    )


def test_le_decrochage_de_2023() -> None:
    """Le chapitre 11 annonce 53,1 % en 2023, sans chevauchement avec 2022."""
    par_annee = {ligne["annee"]: ligne for ligne in agregat("stabilite-par-annee")}
    assert float(par_annee["2023"]["precision_pourcent"]) == 53.1
    assert float(par_annee["2023"]["precision_haut"]) < float(par_annee["2022"]["precision_bas"])


def test_chaque_figure_citee_existe() -> None:
    """Une image appelee dans le memoire doit exister, sinon le document sort troue."""
    manquantes = []
    for texte in MEMOIRE.glob("*.md"):
        for ligne in texte.read_text(encoding="utf-8").splitlines():
            if ligne.startswith("![") and "](figures/" in ligne:
                nom = ligne.split("](", 1)[1].rstrip(")")
                if not (MEMOIRE / nom).exists():
                    manquantes.append(f"{texte.name} : {nom}")
    assert manquantes == [], f"figures citees mais absentes : {manquantes}"


def test_le_debit_annonce_pour_l_api() -> None:
    """Le memoire annonce 94 requetes par seconde et aucun echec sur 300 appels.

    Les deux vont ensemble : un debit sans son taux d'echec ne veut rien dire, puisqu'un service
    qui refuse la moitie des appels repond tres vite aux autres.
    """
    charge = agregat("api-charge")
    debit = max(float(ligne["debit_par_seconde"]) for ligne in charge)
    assert 90 <= debit <= 100, f"le memoire annonce environ 94 req/s, mesure : {debit}"
    assert sum(int(ligne["echecs"]) for ligne in charge) == 0
    assert sum(int(ligne["appels"]) for ligne in charge) == 300


def test_ce_que_le_plafond_de_candidats_change_vraiment() -> None:
    """Le memoire affirme que l'ordre est exact sous le plafond et peut differer au-dessus.

    C'est l'affirmation la plus genante de la section 10.1, donc celle qu'il faut tenir. Si une
    remesure la contredisait, le texte devrait changer, pas la mesure.
    """
    from services.api.requetes import PLAFOND_CANDIDATS

    classement = agregat("api-classement")
    sous = [ligne for ligne in classement if int(ligne["lignes_qui_repondent"]) < PLAFOND_CANDIDATS]
    au_dessus = [
        ligne for ligne in classement if int(ligne["lignes_qui_repondent"]) > PLAFOND_CANDIDATS
    ]
    assert sous and au_dessus, "la mesure doit couvrir les deux cotes du plafond"

    for ligne in sous:
        assert int(ligne["communs_sur_dix"]) == 10, (
            f"sous le plafond, l'ordre doit etre exact : {ligne['question']}"
        )
    # Au-dessus, le memoire ne promet rien, et c'est le point : il annonce que l'ordre peut etre
    # entierement different. Au moins une question doit le montrer, sinon la mise en garde serait
    # excessive et il faudrait la nuancer.
    assert min(int(ligne["communs_sur_dix"]) for ligne in au_dessus) == 0


def test_le_gain_du_tri_aligne_sur_l_index() -> None:
    """Le memoire cite un facteur 965 entre les deux ordres de tri de la liste recente.

    Les deux durees sont dans le commentaire de `requetes.py`, pas dans un CSV : elles viennent
    d'un `explain analyze` et non d'un banc. Ce test verifie au moins que le texte du memoire et
    celui du code racontent la meme chose, pour qu'une correction d'un cote n'oublie pas l'autre.
    """
    memoire = (MEMOIRE / "10-mise-en-production.md").read_text(encoding="utf-8")
    code = (RACINE / "services" / "api" / "requetes.py").read_text(encoding="utf-8")
    for duree in ("28 636", "965"):
        assert duree in memoire, f"{duree} absent du memoire"
        assert duree in code, f"{duree} absent de requetes.py"
