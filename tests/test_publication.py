"""Tests de la publication vers PostgreSQL.

L'enjeu ici est une erreur silencieuse et grave : un decalage entre les colonnes declarees dans
le schema SQL et la liste utilisee par le chargeur. `COPY` ne verifie pas les noms, seulement
l'ordre et le nombre. Ajouter une colonne d'un seul cote ferait donc **glisser toutes les valeurs
d'une colonne**, sans aucune erreur, et les montants se retrouveraient dans les durees.

Ces tests comparent donc les deux sources en les lisant vraiment, plutot que de faire confiance a
une relecture humaine.

Ce qu'ils attrapent : une colonne ajoutee dans le schema et pas dans le chargeur, ou l'inverse ;
un ordre different entre les deux ; une colonne generee qu'on tenterait d'ecrire.
Ce qu'ils n'attrapent pas : une colonne correctement nommee mais mal remplie. Cela se verifie par
les tests de la couche or, dans `test_transformation.py`.
"""

import re
from pathlib import Path

from services.publication import vers_postgres

RACINE = Path(__file__).resolve().parent.parent
SCHEMA = RACINE / "base" / "schema"

# Colonnes que la base fabrique elle-meme : le chargeur ne doit jamais les ecrire.
CALCULEES_PAR_LA_BASE = {"id", "recherche"}


def colonnes_declarees(fichier: str, table: str) -> list[str]:
    """Lit les noms de colonnes d'un `create table` dans un fichier de schema.

    Volontairement simple : le schema du projet est ecrit a la main, une colonne par ligne, et
    un analyseur SQL complet serait une dependance pour rien. Si le style du schema change, ce
    test echoue bruyamment, ce qui est le comportement souhaite.
    """
    texte = (SCHEMA / fichier).read_text(encoding="utf-8")
    debut = texte.index(f"create table if not exists {table} (")
    corps = texte[debut : texte.index("\n);", debut)]

    colonnes = []
    for ligne in corps.splitlines()[1:]:
        nue = ligne.strip()
        # On ignore les commentaires, les lignes vides et les lignes de continuation.
        if not nue or nue.startswith("--"):
            continue
        trouve = re.match(r"^([a-z_][a-z0-9_]*)\s+[a-z]", nue)
        if trouve:
            colonnes.append(trouve.group(1))
    return colonnes


def test_les_colonnes_de_marches_correspondent() -> None:
    """Le chargeur ecrit exactement les colonnes du schema, dans le meme ordre."""
    declarees = [
        nom
        for nom in colonnes_declarees("003-table-marches.sql", "marches")
        if nom not in CALCULEES_PAR_LA_BASE
    ]
    assert declarees == vers_postgres.COLONNES_MARCHES, (
        "Decalage entre base/schema/003-table-marches.sql et COLONNES_MARCHES.\n"
        f"schema   : {declarees}\nchargeur : {vers_postgres.COLONNES_MARCHES}"
    )


def test_les_colonnes_de_signaux_correspondent() -> None:
    """Meme verification pour la table des signaux."""
    declarees = [
        nom
        for nom in colonnes_declarees("004-table-signaux.sql", "signaux")
        if nom not in CALCULEES_PAR_LA_BASE
    ]
    assert declarees == vers_postgres.COLONNES_SIGNAUX, (
        "Decalage entre base/schema/004-table-signaux.sql et COLONNES_SIGNAUX.\n"
        f"schema   : {declarees}\nchargeur : {vers_postgres.COLONNES_SIGNAUX}"
    )


def test_le_chargeur_n_ecrit_aucune_colonne_calculee() -> None:
    """La cle technique et la colonne de recherche sont fabriquees par la base.

    Tenter de les ecrire ferait echouer le chargement, ou pire, insererait une valeur figee qui
    ne serait plus recalculee a la mise a jour du texte.
    """
    ecrites = set(vers_postgres.COLONNES_MARCHES) | set(vers_postgres.COLONNES_SIGNAUX)
    assert not (ecrites & CALCULEES_PAR_LA_BASE)


def test_le_mot_de_passe_n_a_aucune_valeur_par_defaut() -> None:
    """Un script qui se connecte avec un mot de passe vide finit par le faire en production."""
    source = (RACINE / "services" / "publication" / "vers_postgres.py").read_text(encoding="utf-8")
    sans_guillemets = source.replace("'", '"')
    # L'acces direct leve une erreur si la variable manque. `environ.get` renverrait None, et la
    # connexion partirait avec un mot de passe vide.
    assert 'os.environ["POSTGRES_PASSWORD"]' in sans_guillemets
    assert 'environ.get("POSTGRES_PASSWORD"' not in sans_guillemets


def test_les_index_sont_dans_un_fichier_a_part() -> None:
    """Le schema cree les tables, un fichier separe cree les index.

    L'ordre compte : construire un index pendant une insertion de deux millions de lignes oblige
    PostgreSQL a le reequilibrer a chaque ligne. Si un `create index` revenait dans les fichiers
    appliques par `make base-init`, le chargement ralentirait sans que personne ne comprenne
    pourquoi.
    """
    for fichier in (
        "001-extensions.sql",
        "002-configuration-plein-texte.sql",
        "003-table-marches.sql",
        "004-table-signaux.sql",
    ):
        texte = (SCHEMA / fichier).read_text(encoding="utf-8")
        lignes_de_code = [
            ligne for ligne in texte.splitlines() if not ligne.strip().startswith("--")
        ]
        assert "create index" not in "\n".join(lignes_de_code).lower(), fichier

    index = (SCHEMA / "005-index.sql").read_text(encoding="utf-8")
    assert index.lower().count("create index") >= 10
