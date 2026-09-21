"""Tests du rapprochement entre le BOAMP et les DECP.

Comme les autres tests de mesure, ceux-ci ne touchent ni au fichier de 236 Mo ni au reseau : ils
fabriquent une table `marches` de quelques lignes et des avis en memoire. Une mesure qui depend
d'une API externe n'est pas un test, c'est une surveillance.

Ce qu'ils attrapent : une expression reguliere qui ne reconnait plus un SIRET, une requete cassee,
une regle de niveau inversee, une fenetre de dates qui ne filtre plus.
Ce qu'ils n'attrapent pas : un seuil de similarite mal choisi. Cela se regle par la mesure sur
donnees reelles, pas par un test.
"""

from datetime import date

import duckdb
import pytest

from mesures.rapprochement_boamp_decp import (
    SEUIL_OBJET,
    Avis,
    extraire_sirets,
    niveaux_de_rapprochement,
)

ACHETEUR = "21130108000019"
TITULAIRE = "35009850500026"


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    """Une table `marches` avec trois marches d'un meme acheteur, a des dates differentes."""
    connexion = duckdb.connect()
    connexion.execute("""
        create table marches (
            acheteur_id varchar, titulaire_id varchar, objet varchar, dateNotification date
        )
    """)
    connexion.execute(
        """
        insert into marches values
            (?, ?, 'fourniture de pieces detachees et maintenance des equipements',
             date '2025-02-10'),
            (?, '99999999999999', 'travaux de voirie rue des lilas', date '2025-01-15'),
            (?, '88888888888888', 'objet sans rapport', date '2019-01-01')
        """,
        [ACHETEUR, TITULAIRE, ACHETEUR, ACHETEUR],
    )
    return connexion


def test_extraction_des_sirets_dans_un_document_json() -> None:
    """Le SIRET se trouve quel que soit l'emplacement, et l'ordre d'apparition est conserve."""
    document = {
        "EFORMS": {"organisation": {"id": ACHETEUR}, "attributaire": {"id": TITULAIRE}},
        "texte": f"contrat notifie a l'entreprise {TITULAIRE}",
    }
    assert extraire_sirets(document) == [ACHETEUR, TITULAIRE]


def test_extraction_ignore_les_nombres_de_mauvaise_longueur() -> None:
    """Un numero de marche a seize chiffres ne doit pas etre pris pour un SIRET."""
    assert extraire_sirets({"reference": "1234567890123456", "code": "123"}) == []


def test_extraction_accepte_un_document_deja_en_texte() -> None:
    """Le BOAMP renvoie tantot un objet JSON, tantot une chaine. Les deux doivent marcher."""
    assert extraire_sirets(f'{{"siret": "{ACHETEUR}"}}') == [ACHETEUR]


def test_niveau_0_sans_siret(con: duckdb.DuckDBPyConnection) -> None:
    """Un avis sans SIRET ne peut pas etre rapproche."""
    avis = Avis(idweb="1", objet="peu importe", date="2025-03-01", sirets=[])
    assert niveaux_de_rapprochement(con, avis)[0] == 0


def test_niveau_0_si_l_acheteur_est_inconnu(con: duckdb.DuckDBPyConnection) -> None:
    """Un SIRET qui n'achete rien dans les DECP ne permet aucun rapprochement."""
    avis = Avis(idweb="1", objet="peu importe", date="2025-03-01", sirets=["11111111111111"])
    assert niveaux_de_rapprochement(con, avis)[0] == 0


def test_niveau_1_acheteur_connu_mais_hors_fenetre(con: duckdb.DuckDBPyConnection) -> None:
    """L'acheteur existe, mais aucun de ses marches n'est dans la fenetre de dates."""
    avis = Avis(idweb="1", objet="objet sans rapport", date="2023-06-01", sirets=[ACHETEUR])
    niveau, candidats, _ = niveaux_de_rapprochement(con, avis)
    assert niveau == 1
    assert candidats == 0


def test_niveau_2_candidats_mais_objet_trop_different(con: duckdb.DuckDBPyConnection) -> None:
    """Des marches existent dans la fenetre, mais aucun objet ne ressemble a celui de l'avis."""
    avis = Avis(
        idweb="1", objet="prestation de nettoyage des vitres", date="2025-03-01", sirets=[ACHETEUR]
    )
    niveau, candidats, similarite = niveaux_de_rapprochement(con, avis)
    assert niveau == 2
    assert candidats >= 1
    assert similarite <= SEUIL_OBJET


def test_niveau_3_objet_proche(con: duckdb.DuckDBPyConnection) -> None:
    """Un objet presque identique suffit a atteindre le niveau 3."""
    avis = Avis(
        idweb="1",
        objet="fourniture de pieces detachees et maintenance des equipements",
        date="2025-03-01",
        sirets=[ACHETEUR],
    )
    niveau, _, similarite = niveaux_de_rapprochement(con, avis)
    assert niveau == 3
    assert similarite > SEUIL_OBJET


def test_niveau_4_titulaire_retrouve(con: duckdb.DuckDBPyConnection) -> None:
    """Le SIRET du titulaire present dans l'avis emporte la decision, meme si l'objet differe."""
    avis = Avis(
        idweb="1",
        objet="libelle totalement different",
        date="2025-03-01",
        sirets=[ACHETEUR, TITULAIRE],
    )
    assert niveaux_de_rapprochement(con, avis)[0] == 4


def test_la_fenetre_de_dates_filtre_vraiment(con: duckdb.DuckDBPyConnection) -> None:
    """Le marche de 2019 ne doit jamais remonter pour un avis de 2025."""
    avis = Avis(idweb="1", objet="objet sans rapport", date="2025-03-01", sirets=[ACHETEUR])
    _, candidats, _ = niveaux_de_rapprochement(con, avis)
    total = con.execute("select count(*) from marches where acheteur_id = ?", [ACHETEUR]).fetchone()
    assert total is not None
    assert candidats < total[0], "la fenetre de dates doit ecarter le marche de 2019"


def test_une_date_de_parution_invalide_echoue_clairement(con: duckdb.DuckDBPyConnection) -> None:
    """Mieux vaut une erreur explicite qu'un rapprochement silencieusement faux."""
    avis = Avis(idweb="1", objet="peu importe", date="pas une date", sirets=[ACHETEUR])
    with pytest.raises(ValueError, match="Invalid isoformat string"):
        niveaux_de_rapprochement(con, avis)


def test_le_seuil_reste_dans_une_plage_raisonnable() -> None:
    """Un seuil hors de cette plage signalerait une modification accidentelle."""
    assert 0.4 <= SEUIL_OBJET <= 0.9


def test_date_du_jour_non_utilisee_dans_la_fenetre(con: duckdb.DuckDBPyConnection) -> None:
    """La fenetre se calcule autour de la parution de l'avis, jamais autour d'aujourd'hui."""
    ancien = Avis(
        idweb="1", objet="travaux de voirie rue des lilas", date="2025-03-01", sirets=[ACHETEUR]
    )
    recent = Avis(
        idweb="2",
        objet="travaux de voirie rue des lilas",
        date=date.today().isoformat(),
        sirets=[ACHETEUR],
    )
    assert niveaux_de_rapprochement(con, ancien)[1] > niveaux_de_rapprochement(con, recent)[1]
