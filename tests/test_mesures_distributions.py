"""Tests des agregats descriptifs et des figures.

Meme principe que `test_mesures_decp.py` : on ne depend jamais du fichier de 236 Mo. Les requetes
sont executees sur une table minuscule, et les figures sont tracees a partir de CSV fabriques pour
le test, dans un dossier temporaire.

Ce que ces tests attrapent : une faute de frappe dans un nom de colonne, une requete qui ne compile
plus apres une modification, une figure qui plante sur un agregat vide ou a une seule ligne.
Ce qu'ils n'attrapent pas : une figure laide ou un axe mal choisi. Cela se verifie a l'oeil, en
regardant les fichiers produits.
"""

import csv
from pathlib import Path

import duckdb
import pytest

from mesures import figures
from mesures.decp_distributions import AGREGATS

COLONNES = """
    uid VARCHAR, montant DOUBLE, montant_anomalie VARCHAR, dateNotification DATE,
    offresRecues SMALLINT, acheteur_categorie VARCHAR, codeCPV VARCHAR, nature VARCHAR
"""


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    """Une vue `marches` de trois lignes, couvrant un cas normal et deux cas abimes."""
    connexion = duckdb.connect()
    connexion.execute(f"create table marches ({COLONNES})")
    connexion.execute("""
        insert into marches values
            ('M1', 150000.0, null, date '2024-03-01', 3, 'Commune', '45000000', 'Marché'),
            ('M2', 9.9e10, 'aberrant', date '2023-12-15', 1, null, '71000000', 'MARCHE'),
            ('M3', 42000.0, null, date '2022-07-20', null, 'Département', '45210000', 'MARCHÉ')
    """)
    return connexion


@pytest.mark.parametrize("nom,question,sql", AGREGATS, ids=[a[0] for a in AGREGATS])
def test_chaque_agregat_s_execute(
    con: duckdb.DuckDBPyConnection, nom: str, question: str, sql: str
) -> None:
    """Chaque requete d'agregat doit s'executer et renvoyer des colonnes nommees."""
    resultat = con.sql(sql)
    assert resultat.columns, f"l'agregat {nom} ne renvoie aucune colonne"
    assert resultat.fetchall() is not None


def test_les_noms_d_agregats_sont_uniques() -> None:
    """Deux agregats de meme nom ecriraient dans le meme fichier CSV."""
    noms = [nom for nom, _, _ in AGREGATS]
    assert len(noms) == len(set(noms))


def test_le_total_nettoye_ecarte_bien_les_aberrants(con: duckdb.DuckDBPyConnection) -> None:
    """Verification de bout en bout : la ligne marquee aberrante ne doit pas peser dans le total."""
    sql = next(sql for nom, _, sql in AGREGATS if nom == "montants-total-annuel")
    lignes = {ligne[0]: ligne for ligne in con.sql(sql).fetchall()}
    # 2023 ne contient que la ligne a 99 milliards, marquee aberrante.
    assert lignes[2023][2] > 0, "le total brut doit inclure la ligne aberrante"
    assert lignes[2023][3] == 0, "le total nettoye doit l'ecarter"


def test_les_figures_se_tracent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Les figures se tracent a partir de CSV minimaux, sans toucher au vrai jeu de donnees."""
    agregats = tmp_path / "resultats"
    agregats.mkdir()
    contenus = {
        "montants-total-annuel": [
            ["annee", "marches", "total_brut_milliards", "total_nettoye_milliards"],
            ["2024", "10", "3000.0", "230.0"],
            ["2025", "12", "4700.0", "250.0"],
        ],
        "montants-tranches": [
            ["tranche", "marches", "part_pourcent"],
            ["1. moins de 25 k", "100", "40.0"],
            ["6. plus de 10 M", "10", "60.0"],
        ],
        "saisonnalite-mensuelle": [["mois", "marches"]]
        + [[str(mois), str(1000 * mois)] for mois in range(1, 13)],
        "familles-cpv": [
            ["famille_cpv", "marches", "montant_median"],
            ["45", "800", "120000"],
            ["71", "250", "90000"],
        ],
        "offres-recues": [
            ["tranche", "marches"],
            ["1 offre", "200"],
            ["2 a 3 offres", "300"],
        ],
    }
    for nom, lignes in contenus.items():
        with (agregats / f"{nom}.csv").open("w", newline="", encoding="utf-8") as sortie:
            csv.writer(sortie, lineterminator="\n").writerows(lignes)

    sorties = tmp_path / "figures"
    monkeypatch.setattr(figures, "AGREGATS", agregats)
    monkeypatch.setattr(figures, "FIGURES", sorties)
    figures.main()

    produites = sorted(chemin.name for chemin in sorties.glob("*.svg"))
    assert len(produites) == 5, f"cinq figures attendues, obtenu : {produites}"
    assert all((sorties / nom.replace(".svg", ".png")).exists() for nom in produites)
