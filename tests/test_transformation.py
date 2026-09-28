"""Tests des regles de nettoyage, sur un jeu dont les defauts sont connus d'avance.

Ces tests executent **la vraie chaine dbt** sur un fichier fictif de quinze lignes, puis verifient
que chaque ligne a bien ete marquee comme prevu. C'est un test d'integration, plus lent que les
autres (quelques secondes), mais c'est le seul qui prouve que le SQL fait ce que ses commentaires
annoncent.

Pourquoi ne pas reecrire les regles en Python pour les tester :

    Option                    Avantage               Limite                        Verdict
    Executer la vraie chaine  teste ce qui tourne    plus lent, demande dbt        retenu
    Reecrire les regles       rapide, isole          deux definitions qui vont     ecarte
    en Python                                        diverger : le test finirait
                                                     par valider du code mort

Chaque ligne du jeu fictif porte un defaut et un seul, nomme dans son identifiant. Quand un test
echoue, le nom de la ligne dit immediatement quelle regle a lache.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import duckdb
import pytest

RACINE = Path(__file__).resolve().parent.parent
TRANSFORMATION = RACINE / "services" / "transformation"
FIXTURE = RACINE / "tests" / "fixtures" / "bronze_fictif.parquet"


@pytest.fixture(scope="module")
def base(tmp_path_factory: pytest.TempPathFactory) -> duckdb.DuckDBPyConnection:
    """Execute la chaine dbt sur le jeu fictif, et renvoie une connexion au resultat.

    La portee est `module` : dbt demarre en quelques secondes, et le refaire pour chacun des
    quinze tests couterait une minute pour rien.
    """
    chemin_base = tmp_path_factory.mktemp("transformation") / "essai.duckdb"

    environnement = os.environ | {"CHEMIN_BASE": str(chemin_base)}
    # Chemin complet de l'executable : lancer « uv » sans le resoudre laisserait le PATH decider
    # quel programme s'execute. C'est une precaution de securite, et elle donne aussi un message
    # clair quand l'outil n'est pas installe.
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv est introuvable : ces tests demandent l'environnement du projet")

    def lancer_dbt(*arguments: str) -> subprocess.CompletedProcess[str]:
        """Lance une commande dbt dans le projet de transformation."""
        return subprocess.run(  # noqa: S603
            [uv, "run", "dbt", *arguments],
            cwd=TRANSFORMATION,
            env=environnement,
            capture_output=True,
            text=True,
            check=False,
        )

    # Les paquets dbt ne sont pas versionnes : ils se reinstallent. Sur cette machine ils sont
    # deja la et la commande prend une seconde ; sur la machine d'integration continue, qui part
    # d'un depot vierge, elle est indispensable. Le test doit tourner dans les deux cas sans
    # qu'on ait a s'en souvenir.
    dependances = lancer_dbt("deps")
    if dependances.returncode != 0:
        pytest.fail(f"dbt deps a echoue :\n{dependances.stdout[-2000:]}")

    resultat = lancer_dbt("build", "--vars", f'{{"chemin_decp": "{FIXTURE}"}}', "--target", "local")
    if resultat.returncode != 0:
        pytest.fail(f"dbt a echoue :\n{resultat.stdout[-3000:]}")

    return duckdb.connect(str(chemin_base), read_only=True)


def marquee(base: duckdb.DuckDBPyConnection, identifiant: str, colonne: str) -> bool:
    """La ligne nommee respecte-t-elle la regle portee par cette colonne ?"""
    # Les noms de colonnes viennent des tests eux-memes, pas d'une entree exterieure, mais la
    # requete reste ecrite en entier : on lit toute la ligne et on choisit la colonne en Python.
    resultat = base.execute("select * from argent_marches where uid = ?", [identifiant]).fetchdf()
    assert not resultat.empty, f"la ligne {identifiant} est absente de la couche argent"
    return bool(resultat.iloc[0][colonne])


# --- Perimetre ------------------------------------------------------------


def test_l_historique_est_ecarte_de_la_couche_argent(base: duckdb.DuckDBPyConnection) -> None:
    """La couche argent ne porte que l'etat actuel : les versions anterieures restent en bronze."""
    presente = base.execute(
        "select count(*) from argent_marches where uid = 'historique'"
    ).fetchone()
    assert presente is not None
    assert presente[0] == 0


def test_aucune_ligne_n_est_supprimee_par_le_nettoyage(base: duckdb.DuckDBPyConnection) -> None:
    """Quatorze lignes entrent, quatorze ressortent : on marque, on ne supprime pas."""
    compte = base.execute("select count(*) from argent_marches").fetchone()
    assert compte is not None
    assert compte[0] == 14, "les lignes defectueuses doivent etre conservees et marquees"


# --- Normalisation --------------------------------------------------------


def test_quatre_graphies_sont_ramenees_a_deux_notions(base: duckdb.DuckDBPyConnection) -> None:
    """« Marché », « MARCHÉ », « Accord-cadre » et « ACCORD CADRE » : deux notions, pas quatre."""
    notions = base.execute("""
        select nature_normalisee, count(*) as lignes
        from argent_marches
        where uid like 'normal%'
        group by 1 order by 1
    """).fetchall()
    assert dict(notions) == {"ACCORD CADRE": 2, "MARCHE": 2}


def test_la_famille_cpv_est_deduite_des_deux_premiers_chiffres(
    base: duckdb.DuckDBPyConnection,
) -> None:
    """Le code 50750000 doit donner la famille 50."""
    resultat = base.execute(
        "select famille_cpv from argent_marches where uid = 'normal'"
    ).fetchone()
    assert resultat is not None
    assert resultat[0] == "50"


def test_un_cpv_en_texte_libre_ne_produit_aucune_famille(
    base: duckdb.DuckDBPyConnection,
) -> None:
    """« Travaux » n'est pas un code : mieux vaut aucune famille qu'une famille inventee."""
    resultat = base.execute(
        "select famille_cpv from argent_marches where uid = 'cpv-texte-libre'"
    ).fetchone()
    assert resultat is not None
    assert resultat[0] is None


# --- Les neuf regles, une par une -----------------------------------------


@pytest.mark.parametrize(
    "identifiant,colonne",
    [
        ("montant-absent", "montant_renseigne"),
        ("montant-negatif", "montant_renseigne"),
        ("montant-enorme", "montant_plausible"),
        ("montant-signale", "montant_sans_anomalie_signalee"),
        ("date-an-1", "date_plausible"),
        ("duree-absurde", "duree_plausible"),
        ("siret-acheteur-faux", "acheteur_siret_valide"),
        ("siret-titulaire-faux", "titulaire_siret_valide"),
        ("offres-absurdes", "offres_plausibles"),
        ("cpv-texte-libre", "cpv_conforme"),
    ],
)
def test_chaque_defaut_est_detecte(
    base: duckdb.DuckDBPyConnection, identifiant: str, colonne: str
) -> None:
    """La ligne fabriquee avec ce defaut doit etre marquee par la regle correspondante."""
    assert marquee(base, identifiant, colonne) is False


def test_une_ligne_saine_ne_declenche_aucune_regle(base: duckdb.DuckDBPyConnection) -> None:
    """Le cas normal doit passer toutes les regles : sans cela, le nettoyage serait trop strict."""
    resultat = base.execute(
        "select motifs_rejet, exploitable_pour_les_prix from argent_marches where uid = 'normal'"
    ).fetchone()
    assert resultat is not None
    assert list(resultat[0]) == []
    assert resultat[1] is True


def test_les_motifs_sont_ecrits_en_clair(base: duckdb.DuckDBPyConnection) -> None:
    """Un motif doit pouvoir etre montre a un utilisateur sans relire le SQL."""
    resultat = base.execute(
        "select motifs_rejet from argent_marches where uid = 'montant-enorme'"
    ).fetchone()
    assert resultat is not None
    assert "montant superieur au milliard" in list(resultat[0])


# --- Couche or ------------------------------------------------------------


def test_la_couche_or_ne_garde_que_l_exploitable(base: duckdb.DuckDBPyConnection) -> None:
    """Les lignes marquees sur une regle de prix ne doivent pas atteindre la table de service."""
    identifiants = [
        ligne[0] for ligne in base.execute("select marche_id from or_marches").fetchall()
    ]
    assert "normal" in identifiants
    for ecarte in ("montant-absent", "montant-enorme", "montant-signale", "date-an-1"):
        assert ecarte not in identifiants


def test_la_couche_or_garde_ce_qui_reste_utilisable(base: duckdb.DuckDBPyConnection) -> None:
    """Un titulaire mal identifie n'empeche pas d'analyser le prix du marche."""
    identifiants = [
        ligne[0] for ligne in base.execute("select marche_id from or_marches").fetchall()
    ]
    assert "siret-titulaire-faux" in identifiants, (
        "cette regle ne conditionne pas l'analyse des prix : la ligne doit rester"
    )


def test_offre_unique_distingue_l_absence_d_information(
    base: duckdb.DuckDBPyConnection,
) -> None:
    """Trois offres donnent false, aucune information donne null : la nuance change les moyennes."""
    resultat = base.execute(
        "select offre_unique from or_marches where marche_id = 'normal'"
    ).fetchone()
    assert resultat is not None
    assert resultat[0] is False
