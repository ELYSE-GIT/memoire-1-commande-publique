"""Tests de l'API publique, sans PostgreSQL.

=== Pourquoi sans base de donnees =============================================

Aucun test de ce projet ne se connecte a PostgreSQL, et ce n'est pas une facilite : la chaine
d'integration continue n'a pas de base, et un test qui depend d'un service exterieur echoue pour
des raisons qui n'ont rien a voir avec le code. La dependance `curseur` de FastAPI est donc
remplacee par un faux curseur qui enregistre le SQL recu et rend des lignes decidees ici.

    Option envisagee        Avantage                      Limite                     Verdict
    PostgreSQL de test      teste le vrai SQL             un service a demarrer dans  ecarte
    (conteneur jetable)                                   la CI, des minutes de
                                                          demarrage, et des tests qui
                                                          echouent sans rapport
    SQLite en memoire       rapide, aucune dependance     ni `tsvector`, ni `filter`, ecarte
                                                          ni `lateral` : ce n'est pas
                                                          le meme dialecte, donc on
                                                          testerait autre chose
    **faux curseur +        rapide, hors ligne, et        le SQL n'est pas execute,   **retenu**
    tests de structure**    verifie ce dont depend        donc une faute de frappe
                            vraiment chaque route         dans une colonne passerait
    faux curseur seul       le plus simple a ecrire       justement : rien ne         ecarte
                                                          rattraperait une colonne
                                                          qui n'existe pas

Ce qui fait tenir le choix retenu : les tests de structure comparent les colonnes citees par
l'API aux colonnes declarees dans `base/schema/`. Une colonne mal orthographiee echoue donc ici,
alors que c'est exactement ce qu'un faux curseur ne peut pas voir.

Ce qu'ils attrapent : une colonne qui n'existe pas, un modele de reponse desynchronise du SQL,
un filtre sans garde-fou, une requete construite par concatenation, un en-tete de securite
oublie, une pagination fausse.
Ce qu'ils n'attrapent pas : une requete syntaxiquement valide mais lente, ou un plan
d'execution qui change. C'est le role de `make bench-api`, qui tourne sur la vraie base.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from services.api import main, requetes

# Les dependances sont importees depuis `base`, ou elles sont definies, et non depuis `main`
# qui ne fait que les reexporter : mypy en mode strict refuse de passer par un reexport
# implicite, et il a raison, l'identite de l'objet remplace devant etre certaine.
from services.api.base import Etat, curseur, lexiques_de
from services.api.main import application
from services.api.modeles import Marche, ReponseAssistant, Signal

RACINE = Path(__file__).resolve().parent.parent
SCHEMA = RACINE / "base" / "schema"
SOURCES_API = sorted((RACINE / "services" / "api").glob("*.py"))

# Une ligne de marche plausible, avec les champs que les modeles attendent. Les valeurs sont
# inventees ; leur forme, non : elles respectent les types du schema.
LIGNE = {
    "marche_id": "2024-ABC-001",
    "objet": "Travaux de voirie rue des Lilas",
    "acheteur_nom": "Commune de Rennes",
    "acheteur_departement_nom": "Ille-et-Vilaine",
    "acheteur_categorie": "Commune",
    "titulaire_nom": "Voirie de l'Ouest",
    "titulaire_categorie": "PME",
    "montant": 184000.00,
    "date_notification": "2024-03-11",
    "annee": 2024,
    "famille_cpv": "45",
    "procedure": "Procedure adaptee",
    "offres_recues": 3,
    "score": 0.42,
    # Le nombre de candidats reellement classes, porte par chaque ligne : c'est une fonction de
    # fenetre sur l'ensemble des candidats.
    "candidats_examines": 1200,
}

LIGNE_SIGNAL = {
    "marche_id": "2024-ABC-001",
    "famille_cpv": "45",
    "marches_dans_la_famille": 1556,
    "ecart_normalise_famille": 6.2,
    "prix_tres_eleve": True,
    "prix_eleve_a_verifier": False,
    "prix_tres_bas_non_evalue": False,
    "offre_unique_sur_gros_marche": False,
    "titulaire_dominant": False,
    "signaux_forts": 1,
    "motifs_de_signalement": ["prix 6,2 fois l'ecart interquartile au-dessus de la mediane"],
}


class FauxCurseur:
    """Un curseur qui n'execute rien, enregistre tout, et rend ce qu'on lui a donne.

    Il sert deux choses : verifier **quelle** requete une route envoie et avec quels parametres,
    et lui faire rendre un nombre de lignes choisi, ce qui est le seul moyen de tester la
    pagination sans deux millions de lignes.
    """

    def __init__(self, lots: list[list[dict[str, Any]]] | None = None) -> None:
        self.lots = list(lots or [])
        self.appels: list[tuple[str, Any]] = []

    def execute(self, requete: Any, valeurs: Any = None) -> FauxCurseur:
        # `as_string(None)` rend le SQL compose tel qu'il partirait, sans connexion.
        texte = requete.as_string(None) if hasattr(requete, "as_string") else str(requete)
        self.appels.append((texte, valeurs))
        return self

    def fetchall(self) -> list[dict[str, Any]]:
        return self.lots.pop(0) if self.lots else []

    def fetchone(self) -> dict[str, Any] | None:
        lot = self.lots.pop(0) if self.lots else []
        return lot[0] if lot else None

    @property
    def dernier_sql(self) -> str:
        return self.appels[-1][0]

    @property
    def derniers_parametres(self) -> Any:
        return self.appels[-1][1]


def client(faux: FauxCurseur | None = None, etat: Etat | None = None) -> TestClient:
    """Un client de test, avec la base remplacee par un faux curseur.

    `TestClient` est construit **sans** `with` : le cycle de vie de l'application n'est alors pas
    joue, donc aucune connexion n'est tentee. C'est ce qui rend ces tests utilisables hors ligne.
    """
    application.state.etat = etat or Etat()
    application.dependency_overrides[curseur] = lambda: faux or FauxCurseur()
    # Les routes JSON vivent sous `PREFIXE_API` depuis le 22 octobre 2026, la racine etant
    # laissee aux pages du site. Le prefixe est pose une fois dans l'adresse de base plutot que
    # recopie dans chacun des appels : les tests restent lisibles, et le prefixe reste importe
    # depuis le code au lieu d'etre ecrit en dur ici.
    return TestClient(
        application,
        base_url=f"http://testserver{main.PREFIXE_API}",
        raise_server_exceptions=False,
    )


@pytest.fixture(autouse=True)
def _nettoyer() -> Any:
    """Retire les remplacements de dependances apres chaque test.

    Sans cela, un remplacement posé par un test s'appliquerait aux suivants, et l'ordre
    d'execution changerait le resultat.
    """
    yield
    application.dependency_overrides.clear()


# --- Ce que les routes envoient a la base ------------------------------------


def test_une_recherche_sans_texte_ne_classe_pas_par_pertinence() -> None:
    """Sans texte, trier par un score constant rendrait l'ordre dependant du stockage.

    La pagination sauterait alors des lignes d'une page a l'autre, sans erreur visible.
    """
    faux = FauxCurseur([[LIGNE]])
    reponse = client(faux).get("/marches", params={"departement": "35"})
    assert reponse.status_code == 200
    assert "date_notification desc" in faux.dernier_sql
    assert "ts_rank_cd" not in faux.dernier_sql


def test_une_recherche_avec_texte_utilise_l_index_plein_texte() -> None:
    faux = FauxCurseur([[LIGNE]])
    reponse = client(faux).get("/marches", params={"q": "travaux de voirie"})
    assert reponse.status_code == 200
    assert "websearch_to_tsquery" in faux.dernier_sql
    assert "recherche @@" in faux.dernier_sql
    # Le texte passe en parametre, jamais dans le SQL.
    assert faux.derniers_parametres[0] == "travaux de voirie"
    assert "travaux" not in faux.dernier_sql


def test_les_filtres_passent_en_parametres_dans_l_ordre_du_sql() -> None:
    """Un decalage entre l'ordre des fragments et celui des valeurs est silencieux et grave.

    PostgreSQL remplacerait le premier `%s` par l'annee et le second par le departement sans
    protester, et la reponse serait fausse sans qu'aucune erreur n'apparaisse.
    """
    faux = FauxCurseur([[LIGNE]])
    reponse = client(faux).get(
        "/marches",
        params={"q": "voirie", "annee": 2024, "departement": "35", "montant_minimum": 1000},
    )
    assert reponse.status_code == 200
    # Le texte, puis les filtres dans l'ordre de leur apparition, puis le plafond de
    # candidats, puis la limite et le decalage.
    assert faux.derniers_parametres == [
        "voirie",
        2024,
        "35",
        1000.0,
        requetes.PLAFOND_CANDIDATS,
        11,
        0,
    ]
    ordre_sql = [
        faux.dernier_sql.index("annee = "),
        faux.dernier_sql.index("acheteur_departement_code = "),
        faux.dernier_sql.index("montant >= "),
    ]
    assert ordre_sql == sorted(ordre_sql)


def test_le_filtre_offre_unique_n_ajoute_aucun_parametre() -> None:
    """`offre_unique is true` porte sa condition en entier.

    Lui passer une valeur en plus decalerait tous les parametres suivants.
    """
    faux = FauxCurseur([[LIGNE]])
    client(faux).get("/marches", params={"offre_unique": True})
    # Onze et non dix : la ligne supplementaire repond a « y a-t-il une page suivante ».
    assert faux.derniers_parametres == [11, 0]
    assert "offre_unique is true" in faux.dernier_sql


def test_offre_unique_exclut_les_marches_dont_on_ignore_le_nombre_d_offres() -> None:
    """`is true` et non `= true` : la colonne accepte null.

    Un marche sans information sur les offres recues n'est pas un marche a offre unique. Le
    confondre gonflerait un signal de concentration avec des donnees manquantes.
    """
    assert "is true" in requetes.FILTRES["offre_unique"].as_string(None)


def test_la_page_suivante_est_annoncee_sans_compter_les_resultats() -> None:
    """Onze lignes demandees pour dix affichees : la onzieme ne sert qu'a repondre oui ou non."""
    faux = FauxCurseur([[LIGNE] * 11])
    reponse = client(faux).get("/marches", params={"q": "voirie"})
    corps = reponse.json()
    assert len(corps["resultats"]) == 10
    assert corps["page_suivante"] is True
    assert faux.derniers_parametres[-2] == 11
    # Le seul comptage autorise est la fonction de fenetre sur les candidats deja materialises,
    # soit 20 000 lignes au plus. Compter les lignes qui repondent est ce qui coute, et c'est
    # cela que la route ne fait jamais.
    sql_nu = faux.dernier_sql.lower().replace("count(*) over ()", "")
    assert "count(" not in sql_nu


def test_la_derniere_page_ne_promet_pas_de_suite() -> None:
    faux = FauxCurseur([[LIGNE] * 4])
    corps = client(faux).get("/marches", params={"q": "voirie"}).json()
    assert len(corps["resultats"]) == 4
    assert corps["page_suivante"] is False


def test_le_decalage_suit_la_page_demandee() -> None:
    faux = FauxCurseur([[LIGNE]])
    client(faux).get("/marches", params={"q": "voirie", "page": 3, "taille": 25})
    assert faux.derniers_parametres[-2:] == [26, 50]


# --- Les garde-fous ----------------------------------------------------------


@pytest.mark.parametrize(
    ("parametres", "raison"),
    [
        ({"taille": 500}, "une page de 500 lignes fait travailler le serveur pour rien"),
        ({"taille": 0}, "une page vide n'a pas de sens"),
        ({"page": 0}, "la premiere page est la page 1"),
        ({"page": 5000}, "offset profond : PostgreSQL produit puis jette les lignes sautees"),
        ({"page": 41}, "au-dela de la 40e page, le plafond de candidats est depasse"),
        ({"annee": 1998}, "aucune donnee avant 2014"),
        ({"departement": "trop long"}, "un code de departement fait deux ou trois caracteres"),
        ({"famille": "4"}, "une famille CPV fait deux chiffres"),
        ({"montant_minimum": -5}, "un montant negatif n'existe pas"),
        ({"q": "x" * 300}, "une requete de 300 caracteres produit un tsquery enorme"),
    ],
)
def test_les_entrees_hors_bornes_sont_refusees(parametres: dict[str, Any], raison: str) -> None:
    """Chaque borne est refusee par la validation, avant d'atteindre la base."""
    assert client().get("/marches", params=parametres).status_code == 422, raison


def test_un_encadrement_de_montant_impossible_est_refuse() -> None:
    """Minimum superieur au maximum : la requete serait valide et rendrait toujours zero ligne."""
    reponse = client().get("/marches", params={"montant_minimum": 10_000, "montant_maximum": 100})
    assert reponse.status_code == 422


def test_la_liste_des_signaux_exige_au_moins_un_signal() -> None:
    """L'index partiel ne couvre que les 2,87 pour cent de lignes signalees.

    Accepter `minimum = 0` ferait parcourir les deux millions de lignes pour une question qui
    n'interesse personne : « montre-moi les marches sans signal ».
    """
    assert client().get("/signaux", params={"minimum": 0}).status_code == 422
    faux = FauxCurseur([[LIGNE_SIGNAL]])
    assert client(faux).get("/signaux").status_code == 200
    # Onze et non dix : la route demande une ligne de plus pour savoir s'il existe une page
    # suivante, exactement comme /marches.
    assert faux.derniers_parametres == (1, 11, 0)


def test_un_marche_inconnu_rend_404_et_non_une_liste_vide() -> None:
    """Une liste vide dirait « ce marche existe et n'a aucune ligne », ce qui est impossible."""
    assert client(FauxCurseur([[]])).get("/marches/inexistant").status_code == 404


def test_un_marche_rend_toutes_ses_lignes_et_ses_signaux() -> None:
    """Un groupement d'entreprises donne plusieurs lignes pour un seul numero de marche."""
    faux = FauxCurseur([[LIGNE, LIGNE], [LIGNE_SIGNAL]])
    corps = client(faux).get("/marches/2024-ABC-001").json()
    assert len(corps["lignes"]) == 2
    assert corps["signaux"][0]["motifs_de_signalement"]


def test_les_en_tetes_de_securite_sont_poses() -> None:
    """Ils sont poses par le service, pour qu'il soit sain meme sans reverse-proxy devant."""
    entetes = client(FauxCurseur([[LIGNE]])).get("/marches").headers
    assert entetes["X-Content-Type-Options"] == "nosniff"
    assert entetes["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in entetes["Content-Security-Policy"]


def test_le_service_repond_quand_la_base_est_absente() -> None:
    """Un service qui refuse de demarrer sans sa base est intenable en demonstration.

    On ne pourrait plus ni consulter /sante ni comprendre ce qui manque.
    """
    reponse = client(etat=Etat(reserve=None)).get("/sante")
    assert reponse.status_code == 200
    assert reponse.json() == {
        "etat": "degrade",
        "base_accessible": False,
        "marches_charges": None,
        "lexiques_charges": False,
    }


def test_l_assistant_refuse_de_repondre_sans_ses_lexiques() -> None:
    """503 et non 500 : le service fonctionne, c'est ce dont il depend qui manque."""
    application.dependency_overrides.pop(lexiques_de, None)
    reponse = client(etat=Etat(lexiques=None)).get("/assistant", params={"question": "combien"})
    assert reponse.status_code == 503


# --- Les tests de structure, ceux que le faux curseur ne peut pas faire -------


def colonnes_du_schema(fichier: str, table: str) -> set[str]:
    """Lit les noms de colonnes d'un `create table` dans un fichier de schema.

    Volontairement simple, comme dans `test_publication.py` : le schema est ecrit a la main, une
    colonne par ligne. Si son style change, ce test echoue bruyamment, ce qui est voulu.
    """
    texte = (SCHEMA / fichier).read_text(encoding="utf-8")
    debut = texte.index(f"create table if not exists {table} (")
    corps = texte[debut : texte.index("\n);", debut)]
    noms = set()
    for ligne in corps.splitlines()[1:]:
        nue = ligne.strip()
        if not nue or nue.startswith("--"):
            continue
        premier = nue.split()[0]
        if re.fullmatch(r"[a-z_]+", premier):
            noms.add(premier)
    return noms


def test_chaque_colonne_servie_existe_dans_le_schema() -> None:
    """Le faux curseur accepterait `acheteur_nmo`. La base, non, et seulement en production."""
    assert set(requetes.COLONNES_MARCHE) <= colonnes_du_schema("003-table-marches.sql", "marches")
    assert set(requetes.COLONNES_SIGNAL) <= colonnes_du_schema("004-table-signaux.sql", "signaux")


def test_chaque_colonne_filtrable_existe_dans_le_schema() -> None:
    """Un filtre sur une colonne inexistante ne se verrait qu'a la premiere utilisation."""
    declarees = colonnes_du_schema("003-table-marches.sql", "marches")
    for nom, fragment in requetes.FILTRES.items():
        colonne = fragment.as_string(None).split()[0]
        assert colonne in declarees, f"le filtre {nom} porte sur une colonne inconnue"


def test_le_modele_de_reponse_et_le_sql_citent_les_memes_champs() -> None:
    """Une colonne ajoutee d'un seul cote donne un champ toujours nul, ou une donnee jetee."""
    assert set(Marche.model_fields) == set(requetes.COLONNES_MARCHE)
    assert set(Signal.model_fields) == set(requetes.COLONNES_SIGNAL)


def test_aucune_requete_n_est_construite_par_concatenation() -> None:
    """La seule defense qui tienne contre l'injection : aucune valeur dans le texte du SQL.

    Le test cherche une f-string ou un `%` de formatage sur la meme ligne qu'un mot-cle SQL.
    `psycopg.sql` compose la structure, et uniquement a partir de fragments ecrits dans le
    projet ; les valeurs passent par `%s`.
    """
    mots_cles = ("select", "where", "from", "order by", "limit", "insert", "update")
    for fichier in SOURCES_API:
        for numero, ligne in enumerate(fichier.read_text(encoding="utf-8").splitlines(), 1):
            nue = ligne.strip()
            if nue.startswith("#") or not any(mot in nue.lower() for mot in mots_cles):
                continue
            assert not re.search(r'f"|f\'', nue), f"{fichier.name}:{numero} f-string et SQL"
            assert '" %' not in nue and "' %" not in nue, f"{fichier.name}:{numero} formatage"


def test_les_connexions_sont_en_lecture_seule_et_sous_delai() -> None:
    """Aucune route de l'API n'ecrit, et aucune requete ne doit pouvoir durer indefiniment.

    Sans delai, une requete pathologique garde une connexion et un fil pour toujours : le
    service devient indisponible sans etre tombe, ce qui est le plus difficile a diagnostiquer.
    """
    source = (RACINE / "services" / "api" / "base.py").read_text(encoding="utf-8")
    assert '"default_transaction_read_only", "on"' in source
    assert '"statement_timeout"' in source
    from services.api.base import CONNEXIONS_MAXIMUM, DELAI_REQUETE_MS

    assert 0 < DELAI_REQUETE_MS <= 30_000
    # Une reserve large est un moyen de tomber en panne de memoire sur un petit VPS, pas d'aller
    # plus vite : chaque connexion est un processus serveur, et `work_mem` vaut 64 Mo.
    assert CONNEXIONS_MAXIMUM <= 8


def test_une_seule_chaine_de_connexion_dans_tout_le_projet() -> None:
    """Trois modules la construisaient, chacun avec ses variables obligatoires.

    Trois endroits qui lisent la configuration, c'est trois comportements qui divergent le jour
    ou l'on ajoute un reglage. Ce test echoue si une quatrieme copie apparait.
    """
    # Les tests sont exclus : citer le nom de la variable est precisement leur travail.
    copies = [
        chemin
        for dossier in ("services", "mesures")
        for chemin in (RACINE / dossier).glob("**/*.py")
        if "POSTGRES_PASSWORD" in chemin.read_text(encoding="utf-8")
    ]
    noms = sorted(chemin.name for chemin in copies)
    assert noms == ["configuration.py"], noms


def test_la_recherche_par_texte_classe_un_sous_ensemble_borne() -> None:
    """Classer toutes les lignes qui repondent prenait 9,8 s sur le mot « travaux ».

    348 748 lignes contiennent ce mot. Les scorer puis les trier pour n'en afficher dix etait
    l'essentiel du travail, et depassait le delai de dix secondes du service. La requete borne
    donc le nombre de candidats avant de les classer.
    """
    faux = FauxCurseur([[LIGNE]])
    client(faux).get("/marches", params={"q": "travaux"})
    assert "candidats as (" in faux.dernier_sql
    # Le plafond s'applique avant le classement, donc avant le `order by`.
    assert faux.dernier_sql.index("limit") < faux.dernier_sql.index("order by")


def test_le_plafond_de_candidats_couvre_la_page_la_plus_profonde() -> None:
    """Sinon les dernieres pages seraient vides, pour une raison indevinable.

    Avec un plafond de 1 000 candidats et une page 100 de 100 lignes, le decalage demande
    (9 900) depasserait le nombre de lignes classees : la reponse serait vide alors que des
    milliers de marches repondent a la question.
    """
    atteignable = (main.PAGE_MAXIMUM - 1) * main.TAILLE_MAXIMUM + main.TAILLE_MAXIMUM
    assert atteignable < requetes.PLAFOND_CANDIDATS


def test_l_ordre_de_la_liste_recente_est_celui_de_son_index() -> None:
    """Un tri qui ne correspond pas a l'index fait balayer deux millions de lignes.

    Mesure du 22 octobre 2026 : `order by date_notification desc nulls last, marche_id` prenait
    28 636 ms, et `order by date_notification desc, id desc` en prend 30. Le `nulls last`
    protegeait de dates absentes qui n'existent pas, et il interdisait l'index.

    Ce test lit l'index dans le schema et le tri dans la requete, pour qu'un changement d'un
    seul cote echoue ici plutot qu'en production.
    """
    index = (SCHEMA / "005-index.sql").read_text(encoding="utf-8")
    assert "on marches (date_notification desc)" in index

    corps, _ = requetes.recherche(None, {})
    tri = corps.as_string(None)
    assert "order by date_notification desc, id desc" in tri
    # `nulls last` sur cette colonne n'est pas l'ordre de l'index.
    assert "date_notification desc nulls last" not in tri


def test_la_pagination_a_un_ordre_total() -> None:
    """Sans tiebreaker unique, deux lignes a egalite changent de place d'une page a l'autre.

    Le resultat n'est pas une erreur visible : un marche saute, un autre apparait deux fois, et
    personne ne peut le reproduire. `id` est la cle primaire, donc l'ordre devient total.
    """
    for texte in (None, "voirie"):
        tri = requetes.recherche(texte, {})[0].as_string(None)
        ordre = tri[tri.index("order by") :]
        assert "id" in ordre, f"ordre sans cle unique pour texte={texte!r}"


def test_un_classement_partiel_est_annonce_et_non_cache() -> None:
    """Au-dela du plafond, les dix affiches ne sont pas les dix meilleurs.

    Mesure du 22 octobre 2026 : sur la question « travaux », 348 748 marches repondent et aucun
    des dix affiches n'appartient aux dix du classement exact. Une approximation annoncee est
    une limite ; une approximation cachee est un mensonge sur la donnee.
    """
    large = LIGNE | {"candidats_examines": requetes.PLAFOND_CANDIDATS}
    corps = client(FauxCurseur([[large]])).get("/marches", params={"q": "travaux"}).json()
    assert corps["classement_approche"] is True
    assert corps["candidats_examines"] == requetes.PLAFOND_CANDIDATS

    etroit = LIGNE | {"candidats_examines": 437}
    corps = client(FauxCurseur([[etroit]])).get("/marches", params={"q": "toiture"}).json()
    assert corps["classement_approche"] is False


def test_une_liste_sans_texte_ne_pretend_pas_avoir_classe() -> None:
    """Aucun classement n'a eu lieu : le nombre de candidats est null, pas zero."""
    sans = LIGNE | {"candidats_examines": None}
    corps = client(FauxCurseur([[sans]])).get("/marches", params={"departement": "35"}).json()
    assert corps["candidats_examines"] is None
    assert corps["classement_approche"] is False


def test_la_file_d_attente_des_connexions_est_bornee() -> None:
    """Quatre connexions et dix secondes par requete : quatre requetes lentes saturent tout.

    Sans borne sur l'attente, les visiteurs suivants patienteraient trente secondes, le defaut de
    psycopg_pool, chacun en immobilisant un fil d'execution. Le service resterait debout en
    apparence sans repondre a personne, ce qui est le mode de panne le plus difficile a
    diagnostiquer parce qu'il ne ressemble pas a une panne.
    """
    from services.api.base import ATTENTE_CONNEXION_S, CONNEXIONS_MAXIMUM, VISITEURS_EN_ATTENTE

    assert 0 < ATTENTE_CONNEXION_S <= 10, "au-dela, le visiteur a referme la page"
    assert 0 < VISITEURS_EN_ATTENTE <= 16 * CONNEXIONS_MAXIMUM
    source = (RACINE / "services" / "api" / "base.py").read_text(encoding="utf-8")
    # Les deux bornes doivent etre passees a la reserve, pas seulement declarees.
    assert "timeout=ATTENTE_CONNEXION_S" in source
    assert "max_waiting=VISITEURS_EN_ATTENTE" in source


def test_une_saturation_se_distingue_d_une_base_absente() -> None:
    """503 dans les deux cas, mais pas la meme phrase ni le meme en-tete.

    La consigne n'est pas la meme : une base absente demande d'aller la demarrer, une saturation
    demande d'attendre. Les deux erreurs de la reserve derivent de `psycopg.Error`, donc elles
    passent par le meme gestionnaire et pourraient facilement recevoir le meme message.
    """
    import psycopg
    from psycopg_pool import PoolTimeout, TooManyRequests

    source = (RACINE / "services" / "api" / "main.py").read_text(encoding="utf-8")
    assert "PoolTimeout | TooManyRequests" in source
    assert '"Retry-After": "5"' in source
    # Les deux derivent de psycopg.Error, donc le gestionnaire les attrape deja. Si cela changeait
    # dans une version future, elles deviendraient des erreurs 500 avec une trace dans le journal.
    for erreur in (PoolTimeout, TooManyRequests):
        assert issubclass(erreur, psycopg.Error)


def test_le_cache_des_mots_de_l_assistant_est_borne() -> None:
    """Un dictionnaire alimente par ce qu'un inconnu tape doit avoir une borne.

    Tant que cette fonction ne servait qu'au banc de mesure, elle voyait 40 questions ecrites a la
    main dans un processus qui s'arrete. Exposee par l'API, elle recoit un mot nouveau par appel
    si quelqu'un le decide, et un cache sans borne grandit alors indefiniment dans un service qui
    tourne des semaines.
    """
    from services.assistant.reponse_sourcee import MOTS_EN_CACHE

    assert 0 < MOTS_EN_CACHE <= 100_000
    source = (RACINE / "services" / "assistant" / "reponse_sourcee.py").read_text(encoding="utf-8")
    assert "OrderedDict" in source
    # Le plus anciennement utilise sort, et un mot qui ressert est remis en fin de file.
    assert "popitem(last=False)" in source
    assert "move_to_end" in source


def test_le_cache_des_mots_oublie_les_plus_anciens() -> None:
    """La borne doit se verifier sur le comportement, pas seulement sur le texte du fichier.

    Le test construit un faux curseur qui racinise en renvoyant le mot tel quel, demande plus de
    mots que la borne, et verifie que la memoire ne grandit pas indefiniment.
    """
    from services.assistant import reponse_sourcee

    class CurseurRacinisation:
        """Racinise en rendant le mot lui-meme, au format d'un tsvector."""

        def __init__(self) -> None:
            self.dernier = ""
            self.appels = 0

        def execute(self, requete: str, valeurs: tuple[Any, ...] = ()) -> None:
            self.appels += 1
            self.dernier = str(valeurs[0]) if valeurs else ""

        def fetchall(self) -> list[tuple[Any, ...]]:
            return []

        def fetchone(self) -> tuple[Any, ...]:
            if "to_tsvector" in self.dernier or not self.dernier:
                return (2019, 2026)
            return (f"'{self.dernier}':1",)

    faux = CurseurRacinisation()
    lexiques = reponse_sourcee.charger_lexiques(faux)  # type: ignore[arg-type]

    borne = reponse_sourcee.MOTS_EN_CACHE
    for numero in range(borne + 50):
        lexiques.frequence(f"mot{numero}")

    # Le cache vit dans la fermeture ; on l'observe par le nombre d'appels a la base. Redemander
    # les derniers mots ne doit rien couter, redemander les premiers doit couter a nouveau.
    appels_avant = faux.appels
    lexiques.frequence(f"mot{borne + 10}")
    assert faux.appels == appels_avant, "un mot recent doit encore etre en cache"
    lexiques.frequence("mot0")
    assert faux.appels == appels_avant + 1, "le plus ancien doit avoir ete oublie"


# --- Ce que la construction du site a revele ---------------------------------
#
# Les trois tests qui suivent portent sur des defauts bien reels de l'API, tous trouves le
# 22 octobre 2026 en construisant les pages, aucun par les tests existants. Ils ont un point
# commun : chacun passait inapercu tant que l'API n'avait qu'un seul appelant, celui qui l'avait
# ecrite.


def test_la_serie_par_annee_rend_des_modeles_et_non_des_dictionnaires() -> None:
    """Une annotation de type n'est pas une promesse tant que rien ne l'execute.

    Cette route rendait `curseur.fetchall()` avec un `# type: ignore[return-value]`, en
    annoncant `list[StatistiqueAnnuelle]`. FastAPI convertissait au moment de serialiser, donc
    l'API etait juste et le mensonge invisible. Le jour ou une page a appele la fonction
    directement, `annee.annee` sur un dictionnaire a fait repondre 500.
    """
    ligne = {
        "annee": 2024,
        "attributions": 307_824,
        "montant_total": 180_000_000.00,
        "attributions_resolues": 262_856,
        "attributions_pme": 163_234,
        "part_pme_pourcent": 62.1,
    }
    rendu = main.lire_par_annee(FauxCurseur([[ligne]]))  # type: ignore[arg-type]
    assert rendu[0].annee == 2024
    assert rendu[0].part_pme_pourcent == 62.1


def test_une_reponse_d_assistant_accepte_des_citations_par_ligne() -> None:
    """Les questions sur les titulaires rendent une liste de numeros dans chaque ligne.

    Le type du champ `lignes` ne l'acceptait pas, et toute question de ce genre faisait repondre
    500 a l'API. `make bench-assistant` ne le voyait pas, parce qu'il appelle la bibliotheque
    sans passer par le modele de reponse ; `make bench-api` ne le voyait pas non plus, parce
    qu'il n'envoyait qu'une question de comptage. Chaque banc couvrait ce que l'autre laissait
    de cote.
    """
    reponse = ReponseAssistant(
        question="qui a remporte les marches de voirie",
        phrase="...",
        intention="titulaires",
        filtre="contenant « voirie »",
        lignes=[{"nom": "Voirie de l'Ouest", "marches": 12, "citations": ["2024-A", "2024-B"]}],
        duree_ms=31.0,
    )
    assert reponse.lignes[0]["citations"] == ["2024-A", "2024-B"]


def test_la_liste_des_signaux_dit_s_il_existe_une_page_suivante() -> None:
    """Une liste nue ne permet pas de savoir s'il reste quelque chose derriere.

    Le deduire de « la page est pleine » propose un lien vers une page vide chaque fois que le
    dernier resultat tombe sur une fin de page.
    """
    pleine = client(FauxCurseur([[LIGNE_SIGNAL] * 11])).get("/signaux", params={"taille": 10})
    assert pleine.json()["page_suivante"] is True
    assert len(pleine.json()["resultats"]) == 10

    derniere = client(FauxCurseur([[LIGNE_SIGNAL] * 10])).get("/signaux", params={"taille": 10})
    assert derniere.json()["page_suivante"] is False


def test_le_prechauffage_lance_les_vraies_requetes_du_service() -> None:
    """Prechauffer avec une requete qui ressemble a celle du service ne prechauffe rien.

    Mesure du 22 octobre 2026 : une approximation ecrite a la main faisait bien tomber le
    premier appel de la recherche de 794 a 135 ms, mais ne changeait rien a /signaux
    (1 199 ms contre 1 379 ms). Seules les pages reellement lues entrent en memoire.
    """
    requetes_de_demarrage = {
        requete.as_string(None) if hasattr(requete, "as_string") else str(requete)
        for _, requete, _ in requetes.prechauffage()
    }
    corps, _ = requetes.recherche("travaux", {})
    assert corps.as_string(None) in requetes_de_demarrage
    assert requetes.SIGNAUX.as_string(None) in requetes_de_demarrage
