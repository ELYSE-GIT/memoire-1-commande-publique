"""Verifie la comparaison de couts : ses tarifs, sa methode et les chiffres qu'elle publie.

La these du memoire est une affirmation sur de l'argent. C'est le genre d'affirmation qu'un jury
verifie, et le genre qu'on peut gonfler sans mentir franchement : en comparant deux charges
differentes, en citant un prix introuvable, ou en oubliant ce que l'offre la plus chere apporte
en plus. Ces tests rendent ces trois tricheries difficiles.

Ce qu'ils attrapent : un tarif sans source ou sans date, un prix venu d'un comparateur plutot que
du fournisseur, un chiffre du memoire qui ne correspond plus aux mesures, un rapport annonce qui
compare une offre partielle a une offre complete, une devise melangee.
Ce qu'ils n'attrapent pas : un tarif officiel releve de travers, et un dimensionnement discutable.
La premiere protection contre cela est que chaque ligne porte l'adresse de sa source, donc est
reverifiable une par une.
"""

import csv
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
RESULTATS = RACINE / "mesures" / "resultats"
PRIX = RACINE / "mesures" / "reference" / "prix-cloud.csv"
MEMOIRE = RACINE / "memoire" / "08-mesures-et-incertitude.md"

# Les domaines dont un tarif a le droit de venir : celui du fournisseur lui-meme, ou celui de la
# banque centrale pour le taux de change. Un comparateur, un blog ou un article de presse n'est
# pas une source de prix : il recopie, il date mal, et il se trompe de region.
DOMAINES_AUTORISES = (
    "amazonaws.com",
    "prices.azure.com",
    "cloud.google.com",
    "api.ovh.com",
    "frankfurter.dev",
)


def tarifs() -> list[dict[str, str]]:
    with PRIX.open(encoding="utf-8") as fichier:
        return list(csv.DictReader(fichier))


def resume() -> dict[str, dict[str, str]]:
    with (RESULTATS / "couts-resume.csv").open(encoding="utf-8") as fichier:
        return {ligne["mesure"]: ligne for ligne in csv.DictReader(fichier)}


def scenarios() -> list[dict[str, str]]:
    with (RESULTATS / "couts-scenarios.csv").open(encoding="utf-8") as fichier:
        return list(csv.DictReader(fichier))


# --- Les tarifs ---------------------------------------------------------------


def test_chaque_tarif_porte_sa_source_sa_region_et_sa_date() -> None:
    """Un prix de nuage sans sa date est perime avant d'etre lu, et sans sa region il est faux.

    Les tarifs varient du simple au double entre regions chez le meme fournisseur, et ils
    changent plusieurs fois par an. Une comparaison qui ne dit ni l'un ni l'autre n'est pas
    verifiable, donc ne vaut rien.
    """
    for ligne in tarifs():
        reference = f"{ligne['fournisseur']} / {ligne['reference']}"
        assert ligne["source"].startswith("https://"), reference
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", ligne["consulte_le"]), reference
        assert ligne["region"], reference
        assert ligne["devise"] in ("EUR", "USD"), reference
        assert float(ligne["prix"]) > 0, reference


def test_aucun_tarif_ne_vient_d_un_comparateur() -> None:
    """Un comparateur recopie, date mal et se trompe de region.

    Les prix de ce projet viennent du fournisseur lui-meme, par une liste publique et lisible
    par une machine, ou de la banque centrale pour le change.
    """
    for ligne in tarifs():
        domaine = ligne["source"].split("/")[2]
        assert any(domaine.endswith(autorise) for autorise in DOMAINES_AUTORISES), (
            f"{ligne['fournisseur']} : source non officielle, {domaine}"
        )


def test_les_quatre_fournisseurs_sont_couverts() -> None:
    """Comparer a un seul concurrent serait choisir son adversaire."""
    presents = {ligne["fournisseur"] for ligne in tarifs()}
    for attendu in ("OVHcloud", "AWS", "Azure", "Google Cloud"):
        assert attendu in presents


def test_les_tarifs_sont_releves_le_meme_jour() -> None:
    """Melanger des releves de dates differentes compare des prix qui n'ont pas coexiste."""
    dates = {ligne["consulte_le"] for ligne in tarifs()}
    assert len(dates) == 1, f"releves a des dates differentes : {sorted(dates)}"


# --- La methode de comparaison -------------------------------------------------


def test_le_rapport_annonce_compare_des_offres_completes() -> None:
    """Une offre qui ne couvre que la base ne se compare pas a une offre complete.

    Les deux lignes de Google Cloud ne comprennent pas la machine qui sert les pages. Les
    classer avec les autres ferait passer une offre partielle pour la moins chere, et gonflerait
    le rapport annonce.
    """
    resultats = resume()
    retenu = float(resultats["solution retenue"]["valeur"])
    reference = float(resultats["offre geree complete la moins chere"]["valeur"])
    annonce = float(resultats["rapport au moins cher des geres complets"]["valeur"])
    assert abs(reference / retenu - annonce) < 0.1

    completes = [x for x in scenarios() if x["scenario"] == "service gere, base geree"]
    assert {x["fournisseur"] for x in completes} == {"AWS", "Azure"}
    # Et la ligne partielle la moins chere est bien moins chere que les completes : c'est
    # precisement pourquoi elle ne doit pas servir de reference.
    partielles = [x for x in scenarios() if "base geree seule" in x["scenario"]]
    assert min(float(x["total_eur_mois"]) for x in partielles) < reference


def test_le_scenario_retenu_est_celui_qui_tourne_vraiment() -> None:
    """Annoncer le rapport depuis la machine la moins chere gonflerait l'ecart.

    Le projet tourne sur le VPS a quatre processeurs, pas sur le minimal. La difference sur le
    rapport annonce est de 6,8 contre 5,1.
    """
    retenu = next(x for x in scenarios() if x["scenario"] == "VPS, tout sur une machine")
    minimal = next(x for x in scenarios() if x["scenario"] == "VPS minimal, tout sur une machine")
    assert float(minimal["total_eur_mois"]) < float(retenu["total_eur_mois"])
    assert float(resume()["solution retenue"]["valeur"]) == float(retenu["total_eur_mois"])


def test_chaque_offre_geree_dit_ce_qu_elle_n_inclut_pas() -> None:
    """Un prix sans son perimetre est un argument, pas une mesure.

    Le chiffrage retient des configurations a une seule zone : sans cette precision, un lecteur
    croirait comparer a de la haute disponibilite, qui coute a peu pres le double.
    """
    for ligne in scenarios():
        assert ligne["ce_qui_n_est_pas_inclus"].strip(), ligne["fournisseur"]


def test_l_empreinte_est_mesuree_et_non_estimee() -> None:
    """Le dimensionnement part de la taille reelle de la base, pas d'un ordre de grandeur."""
    with (RESULTATS / "couts-empreinte.csv").open(encoding="utf-8") as fichier:
        postes = {ligne["poste"]: ligne for ligne in csv.DictReader(fichier)}
    base = postes["base PostgreSQL"]
    assert "pg_database_size" in base["mesure_par"]
    assert float(base["valeur"]) > 1000
    assert "make bench-api" in postes["memoire du service"]["mesure_par"]


# --- Les chiffres cites dans le memoire ----------------------------------------


def test_les_montants_cites_dans_le_memoire_viennent_des_mesures() -> None:
    """Regle du projet : aucun chiffre affirme sans mesure reproductible."""
    texte = MEMOIRE.read_text(encoding="utf-8")
    resultats = resume()
    attendus = {
        "solution retenue": "23,50",
        "offre geree complete la moins chere": "119,44",
        "offre geree complete la plus chere": "121,64",
        "rapport au moins cher des geres complets": "5,1",
    }
    for mesure, ecrit in attendus.items():
        valeur = float(resultats[mesure]["valeur"])
        assert abs(valeur - float(ecrit.replace(",", "."))) < 0.01, mesure
        assert ecrit in texte, f"« {ecrit} » absent du memoire pour {mesure}"


def test_le_memoire_dit_ce_que_l_ecart_achete() -> None:
    """Un ecart de prix annonce sans sa contrepartie est un argument de vente, pas une mesure."""
    texte = MEMOIRE.read_text(encoding="utf-8")
    for contrepartie in ("sauvegardes", "basculement", "correctifs", "temps d'ingénierie"):
        assert contrepartie.lower() in texte.lower(), contrepartie


def test_le_memoire_dit_a_quelle_echelle_la_conclusion_s_inverse() -> None:
    """Une comparaison sans son domaine de validite se fait citer hors contexte."""
    texte = MEMOIRE.read_text(encoding="utf-8")
    assert "s'inverse" in texte or "renverseraient" in texte
    assert "téraoctets" in texte


def test_les_offres_non_chiffrees_sont_declarees() -> None:
    """Ne pas chiffrer trois offres demandees est acceptable ; le taire ne l'est pas."""
    texte = MEMOIRE.read_text(encoding="utf-8")
    for offre in ("Databricks", "Snowflake", "OpenAI"):
        assert offre in texte
    assert float(resume()["offres non chiffrees"]["valeur"]) == 3
