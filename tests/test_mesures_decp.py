"""Tests des mesures DECP.

Enjeu : verifier que les requetes SQL sont correctes sans dependre du fichier de 236 Mo, qui
n'existe pas sur la machine d'integration continue et qui change tous les jours.

Methode : on construit une table minuscule portant les memes colonnes que le vrai fichier, puis on
execute chaque requete dessus. Une faute de frappe dans un nom de colonne ou une erreur de syntaxe
SQL fait echouer le test immediatement. Les valeurs, elles, ne sont pas verifiees ici : elles
dependent des donnees reelles et sont enregistrees dans `mesures/resultats/`.
"""

import duckdb
import pytest

from mesures.decp_qualite import MESURES, executer

# Les colonnes utilisees par au moins une requete, avec leur type dans le fichier reel.
COLONNES = """
    uid VARCHAR, id VARCHAR, acheteur_id VARCHAR, titulaire_id VARCHAR,
    montant DOUBLE, montant_anomalie VARCHAR, dateNotification DATE,
    offresRecues SMALLINT, modification_id SMALLINT, donneesActuelles BOOLEAN
"""


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    """Une table `decp` de deux lignes : une normale, une volontairement abimee."""
    connexion = duckdb.connect()
    connexion.execute(f"create table decp ({COLONNES})")
    connexion.execute("""
        insert into decp values
            ('M1', 'M1', 'ACH1', 'TIT1', 150000.0, null, date '2024-03-01', 3, 0, true),
            ('M2', 'M2', 'ACH2', 'TIT2', -5.0, 'aberrant', date '0001-01-01', 1, 0, true)
    """)
    return connexion


@pytest.mark.parametrize("nom,question,sql", MESURES, ids=[m[0] for m in MESURES])
def test_chaque_requete_s_execute(
    con: duckdb.DuckDBPyConnection, nom: str, question: str, sql: str
) -> None:
    """Chaque requete doit s'executer et renvoyer au moins un indicateur nomme."""
    valeurs, duree = executer(con, sql)
    assert valeurs, f"la mesure {nom} ne renvoie rien"
    assert duree >= 0
    assert question.endswith("?"), "chaque mesure repond a une question explicite"


def test_les_anomalies_sont_bien_comptees(con: duckdb.DuckDBPyConnection) -> None:
    """Verification de bout en bout sur des valeurs connues d'avance."""
    sql = next(sql for nom, _, sql in MESURES if nom == "montants")
    valeurs, _ = executer(con, sql)
    assert valeurs["negatifs_ou_nuls"] == 1
    assert valeurs["absents"] == 0


def test_les_noms_de_mesures_sont_uniques() -> None:
    """Deux mesures de meme nom s'ecraseraient dans le fichier de resultats."""
    noms = [nom for nom, _, _ in MESURES]
    assert len(noms) == len(set(noms))
