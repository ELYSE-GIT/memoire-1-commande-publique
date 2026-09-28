"""Mesure du rapprochement entre les avis du BOAMP et les marches des DECP.

Question posee : les deux sources ne partagent aucun identifiant commun (mesure du 21 septembre
2026, aucune correspondance sur 600 avis). Peut-on quand meme les relier, et a quel taux ?

Le principe suivi est celui de l'escalier, applique au rapprochement d'enregistrements. On monte
d'un niveau seulement quand le precedent ne suffit pas, et on mesure chaque niveau separement pour
savoir ce que chacun apporte.

    Niveau 1  SIRET de l'acheteur, extrait de l'avis, reconnu dans les DECP
    Niveau 2  plus une fenetre de dates autour de la parution de l'avis
    Niveau 3  plus une similarite entre les objets de marche
    Niveau 4  plus le SIRET du titulaire, present dans le meme avis

Pourquoi extraire les SIRET par expression reguliere plutot que par un analyseur de schema :

    Option                      Avantage                      Limite                 Verdict
    Motif de 14 chiffres        un seul code pour les trois   peut capter un autre   retenu
    sur tout le document        formats rencontres            nombre de 14 chiffres
    Analyseur par schema        precis, sait quel SIRET est   trois analyseurs a     ecarte
    (FNSimple, EFORMS, MAPA)    l'acheteur                    ecrire et a maintenir
    Schema XML officiel eForms  exhaustif et normalise        lourd, et le BOAMP     plus tard
                                                              republie en JSON

Le risque du motif est reel mais mesurable : un nombre de 14 chiffres qui ne serait pas un SIRET ne
correspondra a aucun acheteur des DECP, et sera donc ecarte au niveau 1. C'est la verification qui
rattrape l'imprecision de l'extraction.

Pourquoi `difflib` pour comparer les objets :

    Option        Avantage                          Limite                        Verdict
    difflib       bibliotheque standard, aucune     lent sur de gros volumes      retenu pour
    (stdlib)      dependance                                                      la mesure
    RapidFuzz     dix a cent fois plus rapide       une dependance de plus        en phase 3
    Splink        rapprochement probabiliste        demande des donnees           si la mesure
                  complet, tourne sur DuckDB        d'entrainement                le justifie
    Plongements   comprend les reformulations       cout de calcul, modele a      dernier recours
    lexicaux                                        charger, moins explicable

Lancement : `make bench-rapprochement`.
"""

from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import duckdb

RACINE = Path(__file__).resolve().parent.parent
FICHIER_DECP = RACINE / "donnees" / "brut" / "decp.parquet"
SORTIE = RACINE / "mesures" / "resultats"

API_BOAMP = (
    "https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records"
)

# Un SIRET fait quatorze chiffres. Le motif exige des bornes de mot pour ne pas decouper un
# nombre plus long, comme un numero de marche a seize chiffres.
MOTIF_SIRET = re.compile(r"\b(\d{14})\b")

# Fenetre de dates : un avis de resultat parait apres la notification du marche, avec un delai
# variable. Dix-huit mois avant couvre les publications tardives, trois mois apres couvre les
# marches notifies juste apres la parution de l'avis. Les bornes sont calculees en Python plutot
# qu'en SQL : DuckDB n'accepte pas de parametre dans un `interval`, et un intervalle ecrit en dur
# dans la requete empecherait de faire varier la fenetre pour la mesurer.
JOURS_AVANT = 18 * 30
JOURS_APRES = 3 * 30

# Seuil de similarite des objets. Mesure sur un echantillon : en dessous de 0,6, les
# rapprochements deviennent douteux ; au-dessus de 0,8, on perd les reformulations legitimes.
SEUIL_OBJET = 0.6


@dataclass
class Avis:
    """Un avis de resultat du BOAMP, reduit a ce qui sert au rapprochement."""

    idweb: str
    objet: str
    date: str
    sirets: list[str]


def interroger_boamp(**parametres: object) -> dict[str, Any]:
    """Appelle l'API du BOAMP et renvoie la reponse JSON."""
    url = f"{API_BOAMP}?{urllib.parse.urlencode(parametres)}"
    # L'en-tete identity evite une reponse compressee que urllib ne decompresse pas seul.
    requete = urllib.request.Request(  # noqa: S310
        url, headers={"Accept-Encoding": "identity"}
    )
    with urllib.request.urlopen(requete, timeout=60) as reponse:  # noqa: S310
        resultat: dict[str, Any] = json.loads(reponse.read())
    return resultat


def extraire_sirets(document: object) -> list[str]:
    """Renvoie les SIRET trouves dans un avis, dans l'ordre d'apparition, sans doublon.

    L'ordre compte : dans les trois formats rencontres, l'acheteur apparait avant les titulaires.
    """
    texte = document if isinstance(document, str) else json.dumps(document, ensure_ascii=False)
    return list(dict.fromkeys(MOTIF_SIRET.findall(texte)))


def charger_avis(debut: str, fin: str, nombre: int) -> list[Avis]:
    """Recupere des avis de resultat de marche sur une periode donnee."""
    avis: list[Avis] = []
    for page in range((nombre + 99) // 100):
        reponse = interroger_boamp(
            select="idweb,objet,dateparution,donnees",
            where=f"nature_libelle='Résultat de marché' and dateparution >= date'{debut}'"
            f" and dateparution < date'{fin}'",
            order_by="dateparution",
            limit=100,
            offset=page * 100,
        )
        for ligne in reponse["results"]:
            avis.append(
                Avis(
                    idweb=ligne["idweb"],
                    objet=(ligne.get("objet") or "").lower(),
                    date=ligne["dateparution"][:10],
                    sirets=extraire_sirets(ligne["donnees"]),
                )
            )
    return avis


def niveaux_de_rapprochement(
    con: duckdb.DuckDBPyConnection,
    avis: Avis,
    jours_avant: int = JOURS_AVANT,
    seuil_objet: float = SEUIL_OBJET,
) -> tuple[int, int, float]:
    """Renvoie le niveau atteint, le nombre de candidats, et la meilleure similarite d'objet.

    Niveau 0 : aucun SIRET de l'avis n'est un acheteur connu des DECP.
    Niveau 1 : acheteur reconnu.
    Niveau 2 : au moins un marche de cet acheteur dans la fenetre de dates.
    Niveau 3 : un de ces marches a un objet suffisamment proche.
    Niveau 4 : un de ces marches a pour titulaire un autre SIRET du meme avis.
    """
    if not avis.sirets:
        return 0, 0, 0.0

    # La liste de SIRET est passee comme un seul parametre, converti en tableau par DuckDB.
    # Fabriquer la liste de points d'interrogation par concatenation marcherait aussi, mais
    # produirait une requete construite par chaine, forme que l'analyse de securite refuse a
    # juste titre : elle reste dangereuse le jour ou le contenu concatene change de nature.
    acheteurs = con.execute(
        "select distinct acheteur_id from marches "
        "where acheteur_id in (select unnest(?::varchar[]))",
        [avis.sirets],
    ).fetchall()
    if not acheteurs:
        return 0, 0, 0.0

    acheteur = acheteurs[0][0]
    autres_sirets = [s for s in avis.sirets if s != acheteur]

    parution = date.fromisoformat(avis.date)
    candidats = con.execute(
        """
        select objet, titulaire_id
        from marches
        where acheteur_id = ?
          and dateNotification between ? and ?
        """,
        [acheteur, parution - timedelta(days=jours_avant), parution + timedelta(days=JOURS_APRES)],
    ).fetchall()
    if not candidats:
        return 1, 0, 0.0

    meilleure = max(
        (
            SequenceMatcher(None, avis.objet, (objet or "").lower()).ratio()
            for objet, _ in candidats
        ),
        default=0.0,
    )
    par_titulaire = [c for c in candidats if c[1] and c[1] in autres_sirets]

    if par_titulaire:
        return 4, len(candidats), meilleure
    if meilleure > seuil_objet:
        return 3, len(candidats), meilleure
    return 2, len(candidats), meilleure


# Valeurs explorees pour le balayage. Elles encadrent le choix actuel, dans les deux sens, pour
# pouvoir dire non seulement « nous avons choisi 18 mois et 0,6 » mais « voici ce que donnent les
# autres valeurs, et voici pourquoi celles-ci ».
FENETRES_MOIS = [6, 12, 18, 24, 36]
SEUILS = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def balayer(con: duckdb.DuckDBPyConnection, avis: list[Avis]) -> list[dict[str, float | int | str]]:
    """Mesure le taux de rapprochement pour chaque fenetre et chaque seuil.

    Le calcul est organise pour ne pas refaire le travail inutilement : pour une fenetre donnee,
    on calcule une seule fois la meilleure similarite de chaque avis, puis on applique les six
    seuils dessus. Sans cette precaution, il faudrait trente passages au lieu de cinq.
    """
    lignes: list[dict[str, float | int | str]] = []
    for mois in FENETRES_MOIS:
        debut = time.perf_counter()
        # Le seuil est mis a 1.1 pour que le niveau 3 ne se declenche jamais : on veut la
        # similarite brute de chaque avis, pas un niveau deja filtre.
        mesures = [
            niveaux_de_rapprochement(con, un_avis, jours_avant=mois * 30, seuil_objet=1.1)
            for un_avis in avis
        ]
        duree = time.perf_counter() - debut
        avec_candidats = [m for m in mesures if m[1] > 0]
        for seuil in SEUILS:
            # Niveau 4 : le titulaire concorde, quel que soit le seuil sur l'objet.
            niveau_4 = sum(1 for m in mesures if m[0] == 4)
            # Niveau 3 : l'objet depasse le seuil, sans que le titulaire ne concorde.
            niveau_3 = sum(1 for m in mesures if m[0] != 4 and m[2] > seuil)
            lignes.append(
                {
                    "fenetre_mois": mois,
                    "seuil_objet": seuil,
                    "avis": len(avis),
                    "avec_candidats": len(avec_candidats),
                    "confiance_haute": niveau_4,
                    "confiance_moyenne": niveau_3,
                    "part_rapproches": round(100 * (niveau_3 + niveau_4) / len(avis), 1),
                    "duree_secondes": round(duree, 1),
                }
            )
        print(
            f"  fenetre {mois:>2} mois : {len(avec_candidats):>3} avis avec candidats, "
            f"{duree:>5.1f} s"
        )
    return lignes


def echantillon_a_verifier(
    con: duckdb.DuckDBPyConnection, avis: list[Avis], par_tranche: int = 12
) -> list[dict[str, str | float]]:
    """Constitue un echantillon de rapprochements a relire a la main.

    Un taux de rapprochement ne dit rien de sa justesse : un seuil bas rapproche davantage, et
    rapproche davantage a tort. La seule facon de le savoir est de lire les paires.

    L'echantillon est stratifie par tranche de similarite plutot que tire uniformement : on veut
    autant d'exemples a 0,45 qu'a 0,85, precisement pour voir ou la methode commence a se tromper.
    Un tirage uniforme donnerait surtout des cas faciles.
    """
    tranches = [(0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01)]
    retenus: list[dict[str, str | float]] = []

    for un_avis in avis:
        if not un_avis.sirets:
            continue
        acheteurs = con.execute(
            "select distinct acheteur_id from marches "
            "where acheteur_id in (select unnest(?::varchar[]))",
            [un_avis.sirets],
        ).fetchall()
        if not acheteurs:
            continue
        acheteur = acheteurs[0][0]
        autres = [s for s in un_avis.sirets if s != acheteur]
        parution = date.fromisoformat(un_avis.date)
        candidats = con.execute(
            """
            select objet, titulaire_id from marches
            where acheteur_id = ? and dateNotification between ? and ?
            """,
            [
                acheteur,
                parution - timedelta(days=JOURS_AVANT),
                parution + timedelta(days=JOURS_APRES),
            ],
        ).fetchall()
        if not candidats:
            continue

        meilleur_objet, meilleur_titulaire, meilleur_score = "", None, 0.0
        for objet, titulaire in candidats:
            score = SequenceMatcher(None, un_avis.objet, (objet or "").lower()).ratio()
            if score > meilleur_score:
                meilleur_objet, meilleur_titulaire, meilleur_score = objet or "", titulaire, score

        for bas, haut in tranches:
            if bas <= meilleur_score < haut:
                deja = sum(1 for r in retenus if r["tranche"] == f"{bas} a {haut}")
                if deja < par_tranche:
                    retenus.append(
                        {
                            "tranche": f"{bas} a {haut}",
                            "similarite": round(meilleur_score, 3),
                            "idweb": un_avis.idweb,
                            "objet_boamp": un_avis.objet[:180],
                            "objet_decp": meilleur_objet[:180],
                            "titulaire_concorde": "oui"
                            if meilleur_titulaire and meilleur_titulaire in autres
                            else "non",
                            "verdict_humain": "",
                        }
                    )
                break

    return sorted(retenus, key=lambda r: float(r["similarite"]))


def main() -> None:
    if not FICHIER_DECP.exists():
        raise SystemExit(f"Fichier absent : {FICHIER_DECP}. Lancer d'abord `make donnees-decp`.")

    debut = time.perf_counter()
    avis = charger_avis("2025-01-01", "2025-07-01", 300)
    duree_collecte = time.perf_counter() - debut
    print(f"{len(avis)} avis de resultat charges en {duree_collecte:.0f} s")

    con = duckdb.connect()
    con.register("decp", con.read_parquet(str(FICHIER_DECP)))
    con.execute("create view marches as select * from decp where donneesActuelles")

    debut = time.perf_counter()
    atteints: dict[int, int] = dict.fromkeys(range(5), 0)
    candidats_par_avis: list[int] = []
    for un_avis in avis:
        niveau, candidats, _ = niveaux_de_rapprochement(con, un_avis)
        atteints[niveau] += 1
        if candidats:
            candidats_par_avis.append(candidats)
    duree_mesure = time.perf_counter() - debut

    total = len(avis)
    avec_siret = sum(1 for a in avis if a.sirets)
    # Un avis compte pour tous les niveaux jusqu'au sien : le niveau 4 a aussi franchi le 1.
    cumul = {n: sum(atteints[m] for m in range(n, 5)) for n in range(1, 5)}

    libelles = {
        1: "SIRET d'acheteur reconnu dans les DECP",
        2: "plus au moins un marche dans la fenetre de dates",
        3: "plus un objet de marche suffisamment proche",
        4: "plus le SIRET du titulaire retrouve dans l'avis",
    }
    print(f"\n{avec_siret} avis portent au moins un SIRET ({100 * avec_siret / total:.0f} %)")
    for niveau in range(1, 5):
        part = 100 * cumul[niveau] / total
        print(f"  niveau {niveau} : {cumul[niveau]:>3} avis ({part:>5.1f} %)  {libelles[niveau]}")

    candidats_par_avis.sort()
    median = candidats_par_avis[len(candidats_par_avis) // 2] if candidats_par_avis else 0
    maximum = max(candidats_par_avis, default=0)
    print(f"\n  candidats par avis apres la fenetre : median {median}, max {maximum}")
    print(f"  duree de la mesure : {duree_mesure:.0f} s pour {total} avis")

    SORTIE.mkdir(parents=True, exist_ok=True)
    jour = datetime.now(UTC).date().isoformat()
    chemin = SORTIE / f"{jour}-rapprochement-boamp-decp.csv"
    with chemin.open("w", newline="", encoding="utf-8") as sortie:
        auteur = csv.writer(sortie, lineterminator="\n")
        auteur.writerow(["niveau", "libelle", "avis", "part_pourcent"])
        auteur.writerow([0, "avis analyses", total, 100.0])
        auteur.writerow(
            [0, "avis portant au moins un SIRET", avec_siret, round(100 * avec_siret / total, 1)]
        )
        for niveau in range(1, 5):
            auteur.writerow(
                [niveau, libelles[niveau], cumul[niveau], round(100 * cumul[niveau] / total, 1)]
            )
    print(f"\nEcrit : {chemin.relative_to(RACINE)}")

    print("\nBalayage des parametres :")
    lignes_balayage = balayer(con, avis)
    chemin_balayage = SORTIE / f"{jour}-rapprochement-balayage.csv"
    with chemin_balayage.open("w", newline="", encoding="utf-8") as sortie:
        ecrivain = csv.DictWriter(
            sortie, fieldnames=list(lignes_balayage[0].keys()), lineterminator="\n"
        )
        ecrivain.writeheader()
        ecrivain.writerows(lignes_balayage)

    # Ce que le balayage apprend, affiche directement : le meilleur taux, et le choix retenu.
    meilleur = max(lignes_balayage, key=lambda ligne: ligne["part_rapproches"])
    retenu = next(
        ligne
        for ligne in lignes_balayage
        if ligne["fenetre_mois"] == JOURS_AVANT // 30 and ligne["seuil_objet"] == SEUIL_OBJET
    )
    print(
        f"\n  meilleur taux : {meilleur['part_rapproches']} % "
        f"(fenetre {meilleur['fenetre_mois']} mois, seuil {meilleur['seuil_objet']})"
    )
    print(
        f"  choix retenu  : {retenu['part_rapproches']} % "
        f"(fenetre {retenu['fenetre_mois']} mois, seuil {retenu['seuil_objet']})"
    )
    print(f"\nEcrit : {chemin_balayage.relative_to(RACINE)}")

    # Echantillon a relire : la colonne verdict_humain reste vide, elle se remplit a la main.
    echantillon = echantillon_a_verifier(con, avis)
    chemin_echantillon = SORTIE / f"{jour}-rapprochement-echantillon.csv"
    with chemin_echantillon.open("w", newline="", encoding="utf-8") as sortie:
        relecture = csv.DictWriter(
            sortie, fieldnames=list(echantillon[0].keys()), lineterminator="\n"
        )
        relecture.writeheader()
        relecture.writerows(echantillon)
    print(f"\n{len(echantillon)} rapprochements a relire, repartis par tranche de similarite")
    print(f"Ecrit : {chemin_echantillon.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
