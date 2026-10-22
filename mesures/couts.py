"""Ce que le projet coute a faire tourner, et ce qu'il couterait ailleurs.

=== Ce qui est compare, et ce qui ne l'est pas =================================

La these du memoire est qu'une plateforme de qualite professionnelle tient pour une fraction du
cout des offres gerees. Une these pareille se verifie ou s'effondre sur la facon dont la
comparaison est posee. Trois pieges, et ce que ce script fait pour les eviter.

**Comparer la meme charge.** Pas « AWS contre un VPS » dans l'absolu, mais « faire tourner
exactement ce service, avec son empreinte mesuree ». L'empreinte vient des mesures du projet :
la taille reelle de la base PostgreSQL, la memoire reelle du service, les plafonds reellement
poses dans `compose.yaml`. Elle n'est pas estimee, elle est lue.

**Comparer des prix verifiables.** Chaque tarif vient d'une source officielle et
machine-lisible, avec sa region, sa devise et sa date : `mesures/reference/prix-cloud.csv`. Un
prix de comparateur tiers ou de blog n'entre pas dans ce fichier.

**Dire ce que l'argent achete en plus.** Une base geree n'est pas un VPS plus cher : elle
apporte des sauvegardes automatiques, un basculement, des correctifs appliques, un engagement de
disponibilite et un interlocuteur. Le tableau de ce script chiffre le prix ; la section du
memoire dit ce que ce prix couvre, parce qu'un chiffre seul mentirait par omission.

    Option envisagee          Avantage                     Limite                    Verdict
    comparer les prix         simple, et c'est ce que       compare une facture a     ecarte
    affiches en vitrine       font la plupart des           une autre sans dire ce
                              comparatifs                   qu'il y a dedans
    **dimensionner depuis     la comparaison porte sur      il faut mesurer avant de  **retenu**
    l'empreinte mesuree**     la meme charge reelle         chiffrer, et le dire
    appeler les calculateurs  le chiffre officiel du        aucun des quatre n'offre  ecarte
    de chaque fournisseur     fournisseur                   d'acces sans compte

A quelle echelle la reponse changerait : ce calcul porte sur **un** service, deux millions de
lignes et une centaine de requetes par seconde. Au-dela de quelques teraoctets ou de plusieurs
milliers de requetes par seconde, l'elasticite d'une offre geree cesse d'etre un confort et
devient la seule reponse praticable. Le memoire le dit a cet endroit.

=== Ce que ce script ne sait pas chiffrer =====================================

Databricks, Snowflake et OpenAI ne publient pas de tarif sous une forme verifiable sans compte :
leurs pages de tarification construisent leurs tableaux dans le navigateur, et aucune des trois
n'expose de liste de prix publique comparable a celle d'AWS ou d'Azure. Verifie le 22 octobre
2026. Le projet ne publie donc **aucun** chiffre pour ces trois offres, plutot qu'un chiffre
invente : c'est une absence, elle est declaree, et c'est en soi une difference entre les
fournisseurs qui vaut d'etre notee.

Sortie : `mesures/resultats/couts-empreinte.csv`, `couts-scenarios.csv`, `couts-resume.csv`.
"""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "mesures" / "resultats"
PRIX = RACINE / "mesures" / "reference" / "prix-cloud.csv"

# Heures facturees dans un mois. 730 : c'est la convention des trois fournisseurs (8 760 heures
# par an divisees par douze), et non 720. Un mois de 24 x 30 sous-estimerait de 1,4 pour cent.
HEURES_PAR_MOIS = 730

# Marge gardee au-dessus de l'empreinte mesuree pour dimensionner le disque. Les donnees de la
# commande publique grossissent d'environ 300 000 attributions par an, soit 15 pour cent, et une
# base qui atteint son disque s'arrete d'ecrire sans prevenir.
MARGE_DISQUE = 1.6


def lire_prix() -> list[dict[str, str]]:
    """Le referentiel de prix, tel qu'il a ete releve aux sources officielles."""
    with PRIX.open(encoding="utf-8") as fichier:
        return list(csv.DictReader(fichier))


def prix_de(tarifs: list[dict[str, str]], fournisseur: str, reference: str) -> float:
    """Un tarif, par son fournisseur et sa reference exacte.

    Leve si la reference n'existe pas : un tarif absent doit arreter le calcul, jamais valoir
    zero. Un zero silencieux ferait apparaitre un concurrent gratuit.
    """
    for ligne in tarifs:
        if ligne["fournisseur"] == fournisseur and ligne["reference"] == reference:
            return float(ligne["prix"])
    raise SystemExit(f"tarif absent du referentiel : {fournisseur} / {reference}")


def taux_usd_en_eur(tarifs: list[dict[str, str]]) -> float:
    """Le taux de change releve le meme jour que les tarifs, a la source de la BCE."""
    return prix_de(tarifs, "Banque centrale europeenne", "1 USD en EUR")


def taille_mo(chemin: Path) -> float:
    """Taille d'un fichier ou d'un dossier, en mega-octets. Zero s'il est absent."""
    if not chemin.exists():
        return 0.0
    if chemin.is_file():
        return chemin.stat().st_size / 1024 / 1024
    total = sum(f.stat().st_size for f in chemin.rglob("*") if f.is_file())
    return total / 1024 / 1024


def taille_de_la_base_mo() -> float:
    """Taille reelle de la base PostgreSQL, demandee a PostgreSQL lui-meme.

    `pg_database_size` et non la taille du volume Docker : le volume contient aussi les journaux
    de transactions et l'espace non encore rendu au systeme, qui ne sont pas ce qu'on
    provisionne. Zero si la base n'est pas demarree, et le script le dit.
    """
    requete = "select pg_database_size(current_database());"
    try:
        # Chemin resolu par `shutil.which` plutot qu'ecrit en dur : `docker` s'installe a des
        # endroits differents selon la machine (Homebrew, Colima, Docker Desktop), et un
        # chemin fige rendrait la mesure impossible a relancer ailleurs. L'analyse statique a
        # raison de refuser un nom de commande nu, qui dependrait du PATH de celui qui lance.
        docker = shutil.which("docker")
        if docker is None:
            return 0.0
        sortie = subprocess.run(  # noqa: S603
            [
                docker,
                "compose",
                "exec",
                "-T",
                "base",
                "sh",
                "-c",
                f'psql -q -t -A -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "{requete}"',
            ],
            cwd=RACINE,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        return int(sortie.stdout.strip()) / 1024 / 1024
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, OSError):
        return 0.0


def lire_mesure(nom: str, colonne: str, cle: str, valeur: str) -> float:
    """Va chercher un chiffre deja mesure dans un CSV de resultats.

    Les empreintes memoire et les latences ne sont pas remesurees ici : elles le sont par
    `make bench-api` et `make bench-site`, avec leur protocole. Les recalculer autrement
    donnerait deux chiffres pour la meme chose.
    """
    chemin = SORTIE / f"{nom}.csv"
    if not chemin.exists():
        return 0.0
    with chemin.open(encoding="utf-8") as fichier:
        for ligne in csv.DictReader(fichier):
            if ligne.get(cle) == valeur:
                try:
                    return float(ligne[colonne])
                except (TypeError, ValueError):
                    return 0.0
    return 0.0


def empreinte() -> list[dict[str, Any]]:
    """Ce que le service occupe reellement, mesure et non estime."""
    base_mo = taille_de_la_base_mo()
    lignes = [
        {
            "poste": "base PostgreSQL",
            "valeur": round(base_mo, 1),
            "unite": "Mo",
            "mesure_par": "pg_database_size, base chargee",
            "commentaire": "ce qu'il faut provisionner en disque pour la base",
        },
        {
            "poste": "donnees sources conservees",
            "valeur": round(
                taille_mo(RACINE / "donnees" / "brut") + taille_mo(RACINE / "donnees" / "bronze"), 1
            ),
            "unite": "Mo",
            "mesure_par": "taille des dossiers brut et bronze",
            "commentaire": "gardees pour pouvoir tout recharger sans recollecter",
        },
        {
            "poste": "memoire du service",
            "valeur": lire_mesure("api-resume", "valeur", "mesure", "memoire du service"),
            "unite": "Mo",
            "mesure_par": "make bench-api",
            "commentaire": "processus uvicorn, reserve de connexions et lexiques compris",
        },
        {
            "poste": "memoire plafonnee de PostgreSQL",
            "valeur": 3072.0,
            "unite": "Mo",
            "mesure_par": "compose.yaml, limite explicite",
            "commentaire": "plafond pose, pas consommation observee",
        },
        {
            "poste": "processeurs plafonnes de PostgreSQL",
            "valeur": 2.0,
            "unite": "vCPU",
            "mesure_par": "compose.yaml, limite explicite",
            "commentaire": "le service applicatif se contente du reste",
        },
        {
            "poste": "debit maximal mesure",
            "valeur": lire_mesure("api-resume", "valeur", "mesure", "debit maximal mesure"),
            "unite": "requetes par seconde",
            "mesure_par": "make bench-api",
            "commentaire": "sur la route de recherche, aucun echec sur 300 appels",
        },
    ]
    return [ligne for ligne in lignes if ligne["valeur"]]


def scenarios(tarifs: list[dict[str, str]], disque_go: float) -> list[dict[str, Any]]:
    """Le cout mensuel de la meme charge chez chacun, en euros hors taxes.

    Tous les montants sont ramenes en euros au taux du jour, et tous sont hors taxes : les
    tarifs publics d'AWS, d'Azure et d'OVHcloud le sont. Aucun engagement, aucune reservation,
    aucune remise de volume : ce sont les tarifs qu'un particulier ou une petite structure paie
    reellement, et c'est le cas qui interesse ce memoire.
    """
    taux = taux_usd_en_eur(tarifs)
    lignes: list[dict[str, Any]] = []

    # --- Ce que le projet fait reellement : un VPS, tout dessus -------------
    vps = prix_de(tarifs, "OVHcloud", "vps-comfort-4-8-160 : 4 vCPU, 8 Go, 160 Go SSD")
    lignes.append(
        {
            "scenario": "VPS, tout sur une machine",
            "fournisseur": "OVHcloud",
            "detail": "vps-comfort-4-8-160, PostgreSQL et le service sur la meme machine",
            "calcul": round(vps, 2),
            "stockage": 0.0,
            "total_eur_mois": round(vps, 2),
            "ce_qui_n_est_pas_inclus": "sauvegardes, supervision et mises a jour a notre charge",
        }
    )
    vps_petit = prix_de(tarifs, "OVHcloud", "vps-essential-2-8-80 : 2 vCPU, 8 Go, 80 Go SSD")
    lignes.append(
        {
            "scenario": "VPS minimal, tout sur une machine",
            "fournisseur": "OVHcloud",
            "detail": "vps-essential-2-8-80, au plus juste de l'empreinte mesuree",
            "calcul": round(vps_petit, 2),
            "stockage": 0.0,
            "total_eur_mois": round(vps_petit, 2),
            "ce_qui_n_est_pas_inclus": "idem, et aucune marge de croissance du disque",
        }
    )

    # --- AWS : une instance pour le service, une base geree ----------------
    ec2 = prix_de(tarifs, "AWS", "t4g.medium : 2 vCPU, 4 Gio") * HEURES_PAR_MOIS
    rds = prix_de(tarifs, "AWS", "db.t4g.large Single-AZ : 2 vCPU, 8 Gio") * HEURES_PAR_MOIS
    disque_aws = prix_de(tarifs, "AWS", "General Purpose GP3") * disque_go
    total_aws = (ec2 + rds + disque_aws) * taux
    lignes.append(
        {
            "scenario": "service gere, base geree",
            "fournisseur": "AWS",
            "detail": f"EC2 t4g.medium + RDS db.t4g.large Single-AZ + {disque_go:.0f} Go GP3",
            "calcul": round((ec2 + rds) * taux, 2),
            "stockage": round(disque_aws * taux, 2),
            "total_eur_mois": round(total_aws, 2),
            "ce_qui_n_est_pas_inclus": "Multi-AZ, transfert sortant, sauvegardes au-dela du "
            "volume de la base, supervision",
        }
    )

    # --- Azure : meme forme -------------------------------------------------
    vm = prix_de(tarifs, "Azure", "Standard_D2_v5 Linux : 2 vCPU, 8 Gio") * HEURES_PAR_MOIS
    pg = prix_de(tarifs, "Azure", "B2S burstable : 2 vCore") * HEURES_PAR_MOIS
    disque_azure = prix_de(tarifs, "Azure", "Flex Server Storage Data Stored") * disque_go
    sauvegarde = prix_de(tarifs, "Azure", "Backup Storage LRS") * disque_go
    total_azure = vm + pg + disque_azure + sauvegarde
    lignes.append(
        {
            "scenario": "service gere, base geree",
            "fournisseur": "Azure",
            "detail": f"VM D2_v5 + PostgreSQL Flexible B2S + {disque_go:.0f} Go + sauvegarde",
            "calcul": round(vm + pg, 2),
            "stockage": round(disque_azure + sauvegarde, 2),
            "total_eur_mois": round(total_azure, 2),
            "ce_qui_n_est_pas_inclus": "haute disponibilite, transfert sortant, supervision",
        }
    )

    # --- Google Cloud : seulement la base, et en fourchette -----------------
    #
    # La page de tarification publie plusieurs jeux de prix sans que sa source permette de
    # dire lequel correspond a quelle region. Le projet publie donc une fourchette, du tarif
    # le plus bas au plus haut, et la borne basse est celle qui avantage Google.
    for borne, suffixe in (("basse", "le plus bas publie"), ("haute", "le plus haut publie")):
        cpu = prix_de(tarifs, "Google Cloud", f"vCPU : tarif {suffixe}") * 2 * HEURES_PAR_MOIS
        ram = prix_de(tarifs, "Google Cloud", f"RAM : tarif {suffixe}") * 8 * HEURES_PAR_MOIS
        ssd = (
            prix_de(tarifs, "Google Cloud", f"SSD : tarif {suffixe}") * disque_go * HEURES_PAR_MOIS
        )
        lignes.append(
            {
                "scenario": f"base geree seule, borne {borne}",
                "fournisseur": "Google Cloud",
                "detail": f"Cloud SQL PostgreSQL 2 vCPU, 8 Gio, {disque_go:.0f} Go SSD",
                "calcul": round((cpu + ram) * taux, 2),
                "stockage": round(ssd * taux, 2),
                "total_eur_mois": round((cpu + ram + ssd) * taux, 2),
                "ce_qui_n_est_pas_inclus": "la machine qui sert les pages, la haute "
                "disponibilite, et la region n'est pas identifiable dans la source",
            }
        )
    return lignes


def ecrire(nom: str, lignes: list[dict[str, Any]]) -> None:
    """Ecrit un CSV dans `mesures/resultats`, avec les colonnes de la premiere ligne."""
    if not lignes:
        return
    SORTIE.mkdir(parents=True, exist_ok=True)
    chemin = SORTIE / nom
    with chemin.open("w", encoding="utf-8", newline="") as fichier:
        auteur = csv.DictWriter(fichier, fieldnames=list(lignes[0]), lineterminator="\n")
        auteur.writeheader()
        auteur.writerows(lignes)
    print(f"ecrit : {chemin.relative_to(RACINE)}")


def main() -> None:
    tarifs = lire_prix()
    releve = {ligne["consulte_le"] for ligne in tarifs}
    print(f"Tarifs releves le {', '.join(sorted(releve))}, aux sources officielles.")
    print(f"Taux de change du meme jour : 1 USD = {taux_usd_en_eur(tarifs)} EUR (BCE).\n")

    print("Empreinte reellement mesuree :")
    postes = empreinte()
    for poste in postes:
        print(f"  {poste['poste']:<36} {poste['valeur']:>10} {poste['unite']}")
    base_mo = next((p["valeur"] for p in postes if p["poste"] == "base PostgreSQL"), 0.0)
    if not base_mo:
        raise SystemExit(
            "\nLa base n'a pas repondu : lancer `make up` avant, sinon le dimensionnement "
            "serait invente."
        )

    disque_go = round(base_mo / 1024 * MARGE_DISQUE, 0)
    print(
        f"\nDisque provisionne : {disque_go:.0f} Go, soit l'empreinte mesuree "
        f"({base_mo / 1024:.1f} Go) avec {MARGE_DISQUE:.1f} fois de marge."
    )

    print("\nCout mensuel de la meme charge, hors taxes, sans engagement :")
    lignes = scenarios(tarifs, disque_go)
    for ligne in sorted(lignes, key=lambda x: float(x["total_eur_mois"])):
        print(
            f"  {ligne['fournisseur']:<14} {ligne['scenario']:<34} "
            f"{ligne['total_eur_mois']:>8.2f} EUR"
        )

    ecrire("couts-empreinte.csv", postes)
    ecrire("couts-scenarios.csv", lignes)

    retenu = next(x for x in lignes if x["scenario"] == "VPS, tout sur une machine")
    # Le rapport annonce ne compare que des scenarios comparables : ceux qui couvrent a la fois
    # le service et sa base. Ceux de Google Cloud ne couvrent que la base, parce que la region
    # de ses tarifs n'est pas identifiable et qu'il aurait fallu l'inventer pour la machine ;
    # les mettre dans le meme classement ferait passer une offre partielle pour la moins chere.
    compares = [x for x in lignes if x["scenario"] == "service gere, base geree"]
    moins_cher = min(compares, key=lambda x: float(x["total_eur_mois"]))
    plus_cher = max(compares, key=lambda x: float(x["total_eur_mois"]))
    ecrire(
        "couts-resume.csv",
        [
            {
                "mesure": "solution retenue",
                "valeur": retenu["total_eur_mois"],
                "unite": "EUR par mois hors taxes",
                "commentaire": retenu["detail"],
            },
            {
                "mesure": "offre geree complete la moins chere",
                "valeur": moins_cher["total_eur_mois"],
                "unite": "EUR par mois hors taxes",
                "commentaire": f"{moins_cher['fournisseur']} : {moins_cher['detail']}",
            },
            {
                "mesure": "offre geree complete la plus chere",
                "valeur": plus_cher["total_eur_mois"],
                "unite": "EUR par mois hors taxes",
                "commentaire": f"{plus_cher['fournisseur']} : {plus_cher['detail']}",
            },
            {
                "mesure": "rapport au moins cher des geres complets",
                "valeur": round(
                    float(moins_cher["total_eur_mois"]) / float(retenu["total_eur_mois"]), 1
                ),
                "unite": "fois",
                "commentaire": "a charge egale, hors ce que l'offre geree apporte en plus",
            },
            {
                "mesure": "base geree seule chez Google Cloud",
                "valeur": min(
                    float(x["total_eur_mois"]) for x in lignes if x["fournisseur"] == "Google Cloud"
                ),
                "unite": "EUR par mois hors taxes",
                "commentaire": "borne basse, et elle ne couvre que la base : la machine qui "
                "sert les pages n'est pas comprise",
            },
            {
                "mesure": "cout annuel de la solution retenue",
                "valeur": round(float(retenu["total_eur_mois"]) * 12, 2),
                "unite": "EUR par an hors taxes",
                "commentaire": "sans compter le nom de domaine ni le temps d'exploitation",
            },
            {
                "mesure": "offres non chiffrees",
                "valeur": 3,
                "unite": "fournisseurs",
                "commentaire": "Databricks, Snowflake et OpenAI ne publient pas de tarif "
                "verifiable sans compte : aucun chiffre plutot qu'un chiffre invente",
            },
        ],
    )


if __name__ == "__main__":
    os.environ.setdefault("COMPOSE_PROJECT_NAME", "memoire-1-commande-publique")
    main()
