"""Banc d'essai de la recherche plein texte : PostgreSQL contre DuckDB.

Le projet a introduit PostgreSQL en phase 6 pour servir le site. L'ADR 0008 assume que ce choix
a ete fait **avant** d'avoir mesure que DuckDB ne suffisait pas, ce qui est l'inverse du principe
de l'escalier applique partout ailleurs. Ce fichier est la contrepartie : les deux moteurs sont
mesures sur les memes questions, pour que la comparaison existe au lieu d'etre supposee.

=== Ce qui est compare, et pourquoi deux par deux ===========================

Un moteur de recherche fait deux choix independants : quel moteur, et quelle semantique.

    tous les mots (ET)      precis, mais renvoie souvent zero resultat
    au moins un mot (OU)    renvoie toujours quelque chose, parfois n'importe quoi

Comparer PostgreSQL en mode ET a DuckDB en mode OU ne dirait rien : on mesurerait la semantique
et non le moteur. Les quatre combinaisons sont donc mesurees.

=== Mettre les deux moteurs a egalite =======================================

DuckDB ne fournit aucune liste de mots vides francaise, seulement l'anglaise. Sans correction, il
indexerait « de », « la », « pour », ce qui change ses scores et gonfle son index. Le banc lui
donne donc **la liste de PostgreSQL**, copiee dans `mesures/mots-vides-francais.txt`. Les deux
moteurs recoivent aussi le meme racineur francais et le meme retrait des accents.

C'est la condition pour que le mot « comparaison » ait un sens.

=== Les metriques, et celle qui manque ======================================

    latence p50 et p95      ce que l'utilisateur ressent, et ce qu'il ressent au pire
    questions sans reponse  un moteur qui ne trouve rien n'a pas de latence interessante
    taille de l'index       ce que ca coute sur un VPS a 12 euros
    duree de construction   ce que coute une recollecte

La metrique qui manque est **la pertinence**, et elle ne peut pas etre calculee : elle demande un
jugement humain. Le banc prepare donc `recherche-resultats.csv`, avec une colonne `pertinent`
vide, sur le meme protocole que les soixante paires relues pour le rapprochement des sources.
Tant que ce fichier n'est pas rempli, ce banc mesure la vitesse et le silence, pas la qualite.

Lancement : `make bench-recherche`, apres `make charger` et `make indexer`.
"""

from __future__ import annotations

import csv
import os
import statistics
import time
import unicodedata
from pathlib import Path
from typing import Any

import duckdb
import psycopg

RACINE = Path(__file__).resolve().parent.parent
BASE_DUCKDB = RACINE / "donnees" / "commande_publique.duckdb"
# Index DuckDB dans un fichier a part : c'est un artefact derive, qu'on doit pouvoir supprimer
# sans toucher a la base de travail, et dont la taille se mesure a part.
INDEX_DUCKDB = RACINE / "donnees" / "recherche_duckdb.duckdb"
QUESTIONS = RACINE / "mesures" / "verification" / "questions-de-recherche.csv"
JUGEMENTS = RACINE / "mesures" / "verification" / "jugements-recherche.csv"
MOTS_VIDES = RACINE / "mesures" / "mots-vides-francais.txt"
SORTIE = RACINE / "mesures" / "resultats"

# Nombre de resultats rendus. Dix, parce que c'est ce qu'une page affiche et ce qu'un humain
# accepte de juger.
PROFONDEUR = 10

# Repetitions par question. La premiere est jetee : elle paie le remplissage des caches, et ne
# represente pas l'usage reel d'un site ou les pages s'enchainent.
REPETITIONS = 6


def chaine_de_connexion() -> str:
    """Chaine de connexion PostgreSQL, construite depuis l'environnement."""
    manquantes = [
        nom
        for nom in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
        if not os.environ.get(nom)
    ]
    if manquantes:
        raise SystemExit(
            f"Variables absentes : {', '.join(manquantes)}.\n"
            "Lancer par `make bench-recherche`, qui passe le fichier .env a uv."
        )
    return (
        f"host={os.environ.get('POSTGRES_HOST', 'localhost')}"
        f" port={os.environ.get('POSTGRES_PORT', '5432')}"
        f" dbname={os.environ['POSTGRES_DB']}"
        f" user={os.environ['POSTGRES_USER']}"
        f" password={os.environ['POSTGRES_PASSWORD']}"
    )


def lire_questions() -> list[dict[str, str]]:
    """Le jeu de questions, ecrit a la main et versionne."""
    if not QUESTIONS.exists():
        raise SystemExit(f"Jeu de questions absent : {QUESTIONS}")
    with QUESTIONS.open(encoding="utf-8") as fichier:
        return list(csv.DictReader(fichier))


# --- PostgreSQL --------------------------------------------------------------

# Deux requetes, identiques a un detail pres : la semantique.
#
# `websearch_to_tsquery` est la fonction prevue pour une barre de recherche : elle accepte le
# texte tel que l'utilisateur le tape, sans operateur, et combine les mots par ET.
#
# Pour la version OU, on remplace l'operateur dans la requete deja analysee, plutot que de
# refaire l'analyse a la main. On garde ainsi exactement la meme racinisation et les memes mots
# vides : seule la combinaison change, ce qui est le but de la comparaison.
#
# `ts_rank_cd` classe en tenant compte de la proximite des mots dans le texte, contrairement a
# `ts_rank`. Sur des objets de marche courts (86 caracteres de mediane), la proximite est le seul
# signal de structure disponible.
# La requete analysee est isolee dans un bloc `with` : une expression convertie avec `::` n'est
# pas un element valide dans un `from`, et PostgreSQL refuse la requete. L'ecrire ainsi la rend
# aussi lisible, et evite de rappeler la fonction d'analyse a chaque ligne examinee.
REQUETE_PG_ET = """
with analysee as (
    select websearch_to_tsquery('public.francais', %s) as requete
)
select marche_id, objet, acheteur_nom,
       ts_rank_cd(recherche, analysee.requete) as score
from marches, analysee
where recherche @@ analysee.requete
order by score desc, montant desc nulls last
limit %s
"""

REQUETE_PG_OU = """
with analysee as (
    select replace(
        websearch_to_tsquery('public.francais', %s)::text, '&', '|'
    )::tsquery as requete
)
select marche_id, objet, acheteur_nom,
       ts_rank_cd(recherche, analysee.requete) as score
from marches, analysee
where recherche @@ analysee.requete
order by score desc, montant desc nulls last
limit %s
"""


def sur_une_ligne(texte: str | None) -> str:
    """Remplace les retours a la ligne et les tabulations par une espace.

    Les objets de marche sont saisis par des milliers d'agents differents, et certains contiennent
    de vrais retours chariot. Ecrits tels quels dans un CSV, ils coupent la ligne en deux et le
    fichier devient illisible pour celui qui doit le juger. Constate le 11 octobre 2026, par un
    avertissement de git sur les fins de ligne.
    """
    if not texte:
        return ""
    for caractere in ("\r", "\n", "\t"):
        texte = texte.replace(caractere, " ")
    return " ".join(texte.split())


def chercher_postgres(
    curseur: psycopg.Cursor[Any], requete: str, question: str
) -> list[tuple[str, str, str]]:
    """Les `PROFONDEUR` premiers marches pour une question."""
    curseur.execute(requete, (question, PROFONDEUR))
    return [
        (ligne[0], sur_une_ligne(ligne[1]), sur_une_ligne(ligne[2])) for ligne in curseur.fetchall()
    ]


# --- DuckDB ------------------------------------------------------------------


def mots_vides() -> list[str]:
    """La liste de mots vides de PostgreSQL, pour la donner a DuckDB."""
    lignes = MOTS_VIDES.read_text(encoding="utf-8").splitlines()
    return [ligne.strip() for ligne in lignes if ligne.strip() and not ligne.startswith("#")]


def nettoyer_pour_duckdb(question: str, vides: set[str]) -> str:
    """Prepare une question pour DuckDB : minuscules, accents retires, mots vides retires.

    Pourquoi ce traitement n'existe pas pour PostgreSQL : il le fait lui-meme, **des deux cotes**.
    `websearch_to_tsquery` retire les mots vides de la question avant de construire la requete,
    exactement comme l'indexation les a retires du texte.

    DuckDB ne les retire que du texte indexe. En mode conjonctif, il exige donc un mot qu'il a
    lui-meme supprime de l'index, et ne trouve plus rien.

    Mesure du 11 octobre 2026, qui a revele le probleme :

        « travaux de voirie »           conjonctif, sans nettoyage        0 resultat
        « travaux voirie »              conjonctif, mots vides retires   20 569 resultats
        « entretien des espaces verts » conjonctif, sans nettoyage        7 resultats
        « espaces verts »               conjonctif, mots vides retires   30 263 resultats

    Sur le jeu de trente questions, la version sans nettoyage ne trouvait rien pour 29 d'entre
    elles. Conclure que DuckDB cherche mal aurait ete faux : il ne recoit pas la meme question.
    Les deux versions restent mesurees, pour que l'ecart soit lisible et non raconte.
    """
    sans_accents = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", question.lower())
        if not unicodedata.combining(caractere)
    )
    # Les apostrophes separent des mots en francais : « l'ecole » vaut « ecole ».
    for signe in ("'", "\u2019", "-", ",", ":", ";", "?", "!", "."):
        sans_accents = sans_accents.replace(signe, " ")
    mots = [mot for mot in sans_accents.split() if mot and mot not in vides]
    return " ".join(mots)


def preparer_duckdb() -> tuple[duckdb.DuckDBPyConnection, float, int]:
    """Construit l'index plein texte DuckDB s'il manque. Renvoie la connexion, la duree, la taille.

    L'index est conserve d'une execution a l'autre : le reconstruire prend plusieurs minutes et
    ne change pas. Supprimer `donnees/recherche_duckdb.duckdb` force la reconstruction, et
    `make clean-all` s'en charge.
    """
    con = duckdb.connect(str(INDEX_DUCKDB))
    con.execute("install fts; load fts;")

    # On ne se contente pas de verifier que le fichier existe : une execution interrompue en
    # laisse un, vide. Ce qui compte est la presence de la table ET de son index plein texte.
    # Constate le 11 octobre 2026, apres une interruption qui a produit un fichier inutilisable
    # que le banc a reutilise sans rien dire.
    tables = {ligne[0] for ligne in con.sql("show tables").fetchall()}
    index_present = bool(
        con.sql(
            "select 1 from duckdb_schemas() where schema_name = 'fts_main_recherche'"
        ).fetchall()
    )
    deja_la = "recherche" in tables and index_present

    duree = 0.0
    if not deja_la:
        print("  construction de l'index DuckDB (plusieurs minutes, une seule fois)")
        debut = time.perf_counter()

        # La source est ouverte par l'API Python et passee en memoire par Arrow, plutot que par
        # un `attach` construit avec le chemin du fichier : DuckDB n'accepte pas de parametre lie
        # dans un `attach`, donc la seule autre facon serait d'assembler du SQL par formatage de
        # chaine. Le projet s'y refuse partout, et l'analyse de securite du depot le bloque.
        #
        # Un identifiant de ligne est obligatoire pour un index plein texte, et la couche or n'en
        # a pas : `marche_id` designe un marche, pas une ligne. On en fabrique un, exactement
        # comme la cle technique de PostgreSQL, et pour la meme raison.
        # Le passage se fait par un tableau pandas, deja dans les dependances du projet, et non
        # par Arrow, qui demanderait d'ajouter pyarrow et ses quarante megaoctets pour un seul
        # transfert ponctuel.
        source = duckdb.connect(str(BASE_DUCKDB), read_only=True)
        colonnes = source.sql("""
            select row_number() over () as id, marche_id, objet, acheteur_nom, titulaire_nom
            from or_marches
        """).df()
        source.close()

        con.register("source_pandas", colonnes)
        con.execute("create table recherche as select * from source_pandas")
        con.unregister("source_pandas")
        del colonnes

        # Les mots vides sont fournis par une table, seule forme que DuckDB accepte en dehors de
        # l'anglais.
        con.execute("create table mots_vides (mot varchar)")
        con.executemany("insert into mots_vides values (?)", [(mot,) for mot in mots_vides()])

        con.execute("""
            pragma create_fts_index(
                'recherche', 'id', 'objet', 'acheteur_nom', 'titulaire_nom',
                stemmer = 'french', stopwords = 'mots_vides',
                strip_accents = 1, lower = 1, overwrite = 1
            )
        """)
        duree = time.perf_counter() - debut
        print(f"  index DuckDB construit en {duree:.1f} s")

    return con, duree, INDEX_DUCKDB.stat().st_size


# Deux requetes ecrites en entier plutot qu'une seule avec un trou a remplir. Assembler du SQL
# par formatage de chaine est interdit dans ce depot, meme quand la valeur inseree est un entier
# que l'on controle : la regle n'a de valeur que si elle ne souffre aucune exception.
#
# `conjunctive := 1` exige tous les mots, comme le ET de PostgreSQL. `0` accepte au moins un mot,
# comme son OU. Les deux sont mesurees.
REQUETE_DUCKDB_ET = """
select marche_id, objet, acheteur_nom
from (
    select *, fts_main_recherche.match_bm25(id, ?, conjunctive := 1) as score
    from recherche
)
where score is not null
order by score desc
limit ?
"""

REQUETE_DUCKDB_OU = """
select marche_id, objet, acheteur_nom
from (
    select *, fts_main_recherche.match_bm25(id, ?, conjunctive := 0) as score
    from recherche
)
where score is not null
order by score desc
limit ?
"""


def chercher_duckdb(
    con: duckdb.DuckDBPyConnection, question: str, *, conjonctif: bool
) -> list[tuple[str, str, str]]:
    """Les `PROFONDEUR` premiers marches pour une question, cote DuckDB."""
    requete = REQUETE_DUCKDB_ET if conjonctif else REQUETE_DUCKDB_OU
    lignes = con.execute(requete, [question, PROFONDEUR]).fetchall()
    return [(ligne[0], sur_une_ligne(ligne[1]), sur_une_ligne(ligne[2])) for ligne in lignes]


# --- Le banc -----------------------------------------------------------------


def mesurer(fonction: Any, question: str) -> tuple[list[tuple[str, str, str]], float]:
    """Execute une recherche `REPETITIONS` fois et renvoie ses resultats et la latence mediane.

    La premiere execution est jetee : elle paie le remplissage des caches. Garder la mediane
    plutot que la moyenne evite qu'une seule execution lente, due a autre chose sur la machine,
    deplace le chiffre.
    """
    durees = []
    resultats: list[tuple[str, str, str]] = []
    for tour in range(REPETITIONS):
        debut = time.perf_counter()
        resultats = fonction(question)
        ecoule = (time.perf_counter() - debut) * 1000
        if tour > 0:
            durees.append(ecoule)
    return resultats, statistics.median(durees)


def ecrire(nom: str, lignes: list[dict[str, Any]]) -> Path:
    """Ecrit un agregat CSV dans mesures/resultats/."""
    SORTIE.mkdir(parents=True, exist_ok=True)
    chemin = SORTIE / f"{nom}.csv"
    with chemin.open("w", newline="", encoding="utf-8") as sortie:
        auteur = csv.DictWriter(sortie, fieldnames=list(lignes[0].keys()), lineterminator="\n")
        auteur.writeheader()
        auteur.writerows(lignes)
    return chemin


def tailles_postgres(curseur: psycopg.Cursor[Any]) -> dict[str, int]:
    """Taille de la table servie et de son index plein texte, en octets."""
    curseur.execute("""
        select relname, pg_relation_size(oid)
        from pg_class
        where relname in ('marches', 'marches_recherche_idx')
    """)
    return {ligne[0]: ligne[1] for ligne in curseur.fetchall()}


def main() -> None:
    questions = lire_questions()
    print(f"{len(questions)} questions, {PROFONDEUR} resultats par question")

    con_duckdb, duree_index_duckdb, taille_duckdb = preparer_duckdb()

    with psycopg.connect(chaine_de_connexion()) as cx, cx.cursor() as curseur:
        tailles = tailles_postgres(curseur)

        vides = set(mots_vides())

        def postgres_et_puis_ou(question: str) -> list[tuple[str, str, str]]:
            """Tous les mots d'abord ; au moins un mot seulement si cela n'a rien donne.

            C'est le principe de l'escalier applique a la recherche. La mesure montre que le mode
            « tous les mots » repond en quelques millisecondes mais reste muet sur pres d'un tiers
            des questions, tandis que le mode « au moins un mot » repond toujours mais coute plus
            d'une seconde. Enchainer les deux donne la vitesse du premier, et ne paie le prix du
            second que quand il n'y a pas d'autre choix.
            """
            resultats = chercher_postgres(curseur, REQUETE_PG_ET, question)
            if resultats:
                return resultats
            return chercher_postgres(curseur, REQUETE_PG_OU, question)

        moteurs = {
            "postgres_et": lambda q: chercher_postgres(curseur, REQUETE_PG_ET, q),
            "postgres_ou": lambda q: chercher_postgres(curseur, REQUETE_PG_OU, q),
            "postgres_et_puis_ou": postgres_et_puis_ou,
            # La version naive : la question est passee telle quelle, mots vides compris. Gardee
            # parce que c'est ce qu'on ecrit spontanement, et que son resultat est trompeur.
            "duckdb_et_brut": lambda q: chercher_duckdb(con_duckdb, q, conjonctif=True),
            "duckdb_et": lambda q: chercher_duckdb(
                con_duckdb, nettoyer_pour_duckdb(q, vides), conjonctif=True
            ),
            "duckdb_ou": lambda q: chercher_duckdb(
                con_duckdb, nettoyer_pour_duckdb(q, vides), conjonctif=False
            ),
        }

        par_question: list[dict[str, Any]] = []
        a_juger: list[dict[str, Any]] = []

        for ligne in questions:
            question = ligne["question"]
            for nom_moteur, fonction in moteurs.items():
                resultats, latence = mesurer(fonction, question)
                par_question.append(
                    {
                        "id_question": ligne["id"],
                        "question": question,
                        "type": ligne["type"],
                        "moteur": nom_moteur,
                        "resultats": len(resultats),
                        "latence_ms": round(latence, 2),
                    }
                )
                if ligne.get("a_juger") == "oui":
                    for rang, (marche_id, objet, acheteur) in enumerate(resultats, start=1):
                        a_juger.append(
                            {
                                "id_question": ligne["id"],
                                "question": question,
                                "moteur": nom_moteur,
                                "rang": rang,
                                "marche_id": marche_id,
                                "objet": objet[:160],
                                "acheteur_nom": acheteur[:80],
                                "pertinent": "",
                            }
                        )
            print(f"  {ligne['id']} traitee", end="\r")

        # --- Le resume par moteur -------------------------------------------
        resume: list[dict[str, Any]] = []
        for nom_moteur in moteurs:
            mesures = [m for m in par_question if m["moteur"] == nom_moteur]
            latences = sorted(float(m["latence_ms"]) for m in mesures)
            rang95 = max(0, int(0.95 * len(latences)) - 1)
            resume.append(
                {
                    "moteur": nom_moteur,
                    "questions": len(mesures),
                    "sans_resultat": sum(1 for m in mesures if m["resultats"] == 0),
                    "resultats_moyens": round(
                        sum(int(m["resultats"]) for m in mesures) / len(mesures), 1
                    ),
                    "latence_p50_ms": round(statistics.median(latences), 2),
                    "latence_p95_ms": round(latences[rang95], 2),
                    "latence_max_ms": round(latences[-1], 2),
                }
            )

        print(" " * 40, end="\r")
        print("\nLatence et silence, par moteur :")
        print("  moteur                questions  sans reponse  resultats moyens   p50      p95")
        for ligne_resume in resume:
            print(
                f"  {ligne_resume['moteur']:<21} {ligne_resume['questions']:>9}"
                f" {ligne_resume['sans_resultat']:>13}"
                f" {ligne_resume['resultats_moyens']:>17}"
                f" {ligne_resume['latence_p50_ms']:>8.2f} {ligne_resume['latence_p95_ms']:>8.2f}"
            )

        # --- Le cout -------------------------------------------------------
        cout = [
            {
                "element": "table servie PostgreSQL",
                "taille_mo": round(tailles.get("marches", 0) / 1e6, 1),
                "duree_construction_s": "",
            },
            {
                "element": "index plein texte PostgreSQL (GIN)",
                "taille_mo": round(tailles.get("marches_recherche_idx", 0) / 1e6, 1),
                "duree_construction_s": "",
            },
            {
                "element": "table et index plein texte DuckDB",
                "taille_mo": round(taille_duckdb / 1e6, 1),
                "duree_construction_s": round(duree_index_duckdb, 1) or "",
            },
        ]

        chemins = [
            ecrire("recherche-par-moteur", resume),
            ecrire("recherche-par-question", par_question),
            ecrire("recherche-cout", cout),
        ]
        if a_juger:
            chemins.append(ecrire("recherche-resultats", a_juger))

        print("\nEcrit :")
        for chemin in chemins:
            print(f"  {chemin.relative_to(RACINE)}")

        if not JUGEMENTS.exists():
            print(
                "\n  La pertinence n'est pas mesuree : elle demande un jugement humain.\n"
                f"  Remplir la colonne `pertinent` de recherche-resultats.csv (oui, non, doute),\n"
                f"  enregistrer sous {JUGEMENTS.relative_to(RACINE)}, puis relancer."
            )


if __name__ == "__main__":
    main()
