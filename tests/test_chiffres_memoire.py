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
