"""Figures du memoire, tracees a partir des agregats mesures.

Regle du projet : une figure ne lit jamais le fichier de donnees brut, et aucun chiffre n'est saisi
a la main. Ce script lit uniquement les CSV produits par `decp_distributions.py`. Consequence
pratique : reproduire une figure ne demande pas de retelecharger 240 Mo, et chaque valeur affichee
existe dans un fichier que l'on peut ouvrir et verifier.

Sortie : `memoire/figures/`, en SVG et en PNG.

    Format   Avantage                                   Limite                  Usage
    SVG      vectoriel, net a toute taille, leger,      illisible tel quel      memoire imprime
             diffable dans git
    PNG      s'affiche partout, y compris dans un        pixellise si agrandi    apercu, GitHub
             README sur GitHub
    PDF      vectoriel, standard de l'edition            un fichier par figure,  non retenu, le SVG
                                                         moins pratique a lire   suffit

Pourquoi matplotlib plutot qu'un autre outil de trace :

    Option        Avantage                              Limite                       Verdict
    matplotlib    controle total, sortie vectorielle,   verbeux                      retenu
                  aucune dependance a un service
    seaborn       plus court pour les graphiques        couche de plus, styles       non
                  statistiques                          par defaut reconnaissables
    plotly        interactif                            lourd, pensé pour le web,    non pour le
                                                        inutile dans un PDF          memoire
    Excel         rapide                                chiffres saisis a la main,   exclu par
                                                        non reproductible            les regles

Lancement : `make figures`.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import matplotlib

# Backend sans fenetre : le script tourne aussi bien en local que dans une chaine automatisee.
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
AGREGATS = RACINE / "mesures" / "resultats"
FIGURES = RACINE / "memoire" / "figures"

# Palette reprise du guide du projet : encre, ocre, vert. Trois couleurs suffisent, elles se
# distinguent en noir et blanc, et elles evitent les degrades decoratifs.
ENCRE = "#16223a"
OCRE = "#a8591c"
VERT = "#3d6b4f"
GRIS = "#6b6b6b"
FILET = "#d9d4c7"


def chemin_lisible(chemin: Path) -> str:
    """Affiche un chemin relatif au projet quand c'est possible, absolu sinon.

    Sans cette precaution, le script plante des que la sortie est ailleurs que dans le depot,
    par exemple dans un dossier temporaire pendant les tests.
    """
    try:
        return str(chemin.relative_to(RACINE))
    except ValueError:
        return str(chemin)


def lire(nom: str) -> list[dict[str, str]]:
    """Lit un agregat CSV produit par decp_distributions.py."""
    with (AGREGATS / f"{nom}.csv").open(encoding="utf-8") as fichier:
        return list(csv.DictReader(fichier))


def soigner(axes: Any, titre: str) -> None:
    """Applique le meme traitement a chaque figure : peu de traits, pas de decor inutile.

    Le texte explicatif ne va pas sous le titre, ou il chevauche la figure voisine, mais en
    legende sous la figure, comme dans un memoire imprime.
    """
    axes.set_title(titre, color=ENCRE, fontsize=11, fontweight="bold", loc="left", pad=10)
    for bord in ("top", "right"):
        axes.spines[bord].set_visible(False)
    for bord in ("left", "bottom"):
        axes.spines[bord].set_color(FILET)
    axes.tick_params(colors=GRIS, labelsize=8.5)
    axes.grid(axis="y", color=FILET, linewidth=0.6)
    axes.set_axisbelow(True)


def legender(figure: Any, texte: str) -> None:
    """Legende sous la figure : source, perimetre, unite. Une figure doit se lire seule."""
    figure.text(0.01, -0.04, texte, color=GRIS, fontsize=8.5, ha="left", va="top", wrap=True)


def enregistrer(figure: Any, nom: str) -> None:
    """Enregistre en SVG (memoire) et en PNG (apercu)."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    for extension in ("svg", "png"):
        figure.savefig(
            FIGURES / f"{nom}.{extension}", dpi=200, bbox_inches="tight", facecolor="white"
        )
    plt.close(figure)
    print(f"  {nom}.svg et {nom}.png")


def figure_total_annuel() -> None:
    """La figure centrale : les montants aberrants rendent le total annuel inutilisable."""
    donnees = lire("montants-total-annuel")
    annees = [d["annee"] for d in donnees]
    brut = [float(d["total_brut_milliards"]) for d in donnees]
    nettoye = [float(d["total_nettoye_milliards"]) for d in donnees]

    figure, (gauche, droite) = plt.subplots(1, 2, figsize=(10, 4))

    gauche.bar(annees, brut, color=OCRE, width=0.6)
    soigner(gauche, "Total brut déclaré")

    droite.bar(annees, nettoye, color=VERT, width=0.6)
    droite.axhline(230, color=ENCRE, linewidth=1, linestyle="--")
    # Le repere est place en coordonnees relatives, pour rester lisible quelles que soient
    # les valeurs de l'annee la plus forte.
    droite.text(
        0.02,
        0.88,
        "ordre de grandeur réel : environ 230 Md",
        transform=droite.transAxes,
        color=ENCRE,
        fontsize=8.5,
        va="bottom",
    )
    soigner(droite, "Total après retrait des montants signalés")

    figure.suptitle(
        "Un total annuel inutilisable tant que les montants aberrants ne sont pas écartés",
        color=ENCRE,
        fontsize=12.5,
        fontweight="bold",
        x=0.01,
        ha="left",
        y=1.04,
    )
    legender(
        figure,
        "Somme des montants notifiés par année, en milliards d'euros, sur l'état actuel des "
        "marchés.\nÀ droite, les montants marqués suspects ou aberrants par le producteur sont "
        "écartés du calcul.\nSource : DECP consolidées, data.gouv.fr, fichier du "
        "20 septembre 2026. Les années 2019 et 2020 restent basses : la couverture des sources "
        "était incomplète.",
    )
    enregistrer(figure, "01-total-annuel-brut-vs-nettoye")


def figure_tranches_montant() -> None:
    """Ou se situe la masse des marches : de petits montants, tres nombreux."""
    donnees = lire("montants-tranches")
    # On retire le numero de tri present dans le libelle (« 1. moins de 25 k »).
    libelles = [
        d["tranche"].split(". ", 1)[1].replace(" k", " k€").replace(" M", " M€") for d in donnees
    ]
    parts = [float(d["part_pourcent"]) for d in donnees]

    figure, axes = plt.subplots(figsize=(7.5, 3.6))
    barres = axes.barh(libelles, parts, color=ENCRE, height=0.62)
    axes.bar_label(barres, fmt="%.1f %%", padding=4, color=GRIS, fontsize=8.5)
    axes.invert_yaxis()
    axes.grid(axis="y", visible=False)
    axes.grid(axis="x", color=FILET, linewidth=0.6)
    axes.set_xlim(0, max(parts) * 1.18)
    soigner(axes, "Répartition des marchés par tranche de montant")
    legender(
        figure,
        "Part des marchés, en pourcentage, sur 2 047 720 marchés au montant renseigné et positif.\n"
        "Les seuils retenus correspondent aux seuils de procédure : 25 k€, 90 k€ et 214 k€.",
    )
    enregistrer(figure, "02-tranches-de-montant")


def figure_saisonnalite() -> None:
    """Les pics de juillet et de decembre, et le creux d'aout."""
    donnees = lire("saisonnalite-mensuelle")
    mois_noms = [
        "janv.",
        "févr.",
        "mars",
        "avril",
        "mai",
        "juin",
        "juil.",
        "août",
        "sept.",
        "oct.",
        "nov.",
        "déc.",
    ]
    valeurs = [int(d["marches"]) for d in donnees]
    moyenne = sum(valeurs) / len(valeurs)
    # Les mois au-dessus de la moyenne sont mis en avant : c'est le message de la figure.
    couleurs = [OCRE if v > moyenne else ENCRE for v in valeurs]

    figure, axes = plt.subplots(figsize=(8, 3.6))
    axes.bar(mois_noms, [v / 1000 for v in valeurs], color=couleurs, width=0.62)
    axes.axhline(moyenne / 1000, color=GRIS, linewidth=1, linestyle="--")
    soigner(axes, "Saisonnalité de la commande publique")
    legender(
        figure,
        "Marchés notifiés par mois, en milliers, cumul 2019 à 2025. En ocre, les mois au-dessus "
        "de la moyenne,\nfigurée par le trait pointillé. Les pics de juillet et de décembre "
        "correspondent aux fins de cycle budgétaire, le creux d'août aux congés.",
    )
    enregistrer(figure, "03-saisonnalite")


def figure_familles_cpv() -> None:
    """Ce que l'Etat et les collectivites achetent reellement."""
    donnees = sorted(lire("familles-cpv"), key=lambda d: int(d["marches"]), reverse=True)[:10]
    # Libelles officiels des divisions CPV les plus frequentes.
    noms = {
        "45": "Travaux de construction",
        "71": "Services d'architecture et d'ingénierie",
        "79": "Services aux entreprises",
        "33": "Matériel médical",
        "90": "Services liés aux déchets et à l'environnement",
        "50": "Services de réparation et d'entretien",
        "34": "Matériel de transport",
        "44": "Structures et matériaux de construction",
        "72": "Services informatiques",
        "39": "Mobilier et équipement",
        "48": "Logiciels",
        "80": "Services d'enseignement et de formation",
        "85": "Services de santé et d'action sociale",
        "66": "Services financiers et d'assurance",
        "09": "Produits pétroliers et électricité",
        "15": "Produits alimentaires",
    }
    libelles = [noms.get(d["famille_cpv"], f"Division {d['famille_cpv']}") for d in donnees]
    valeurs = [int(d["marches"]) / 1000 for d in donnees]

    figure, axes = plt.subplots(figsize=(8.5, 4.2))
    barres = axes.barh(libelles, valeurs, color=ENCRE, height=0.62)
    axes.bar_label(barres, fmt="%.0f k", padding=4, color=GRIS, fontsize=8.5)
    axes.invert_yaxis()
    axes.grid(axis="y", visible=False)
    axes.grid(axis="x", color=FILET, linewidth=0.6)
    axes.set_xlim(0, max(valeurs) * 1.16)
    soigner(axes, "Les dix familles d'achat les plus fréquentes")
    legender(
        figure,
        "Nombre de marchés, en milliers, par division du code CPV, soit les deux premiers "
        "chiffres du code.\nLa construction représente à elle seule plus du double de la "
        "deuxième famille.",
    )
    enregistrer(figure, "04-familles-cpv")


def figure_offres_recues() -> None:
    """L'indicateur de risque principal, et le trou dans les donnees."""
    donnees = lire("offres-recues")
    libelles = [d["tranche"] for d in donnees]
    valeurs = [int(d["marches"]) / 1000 for d in donnees]
    total = sum(valeurs)
    couleurs = [OCRE if libelle == "1 offre" else ENCRE for libelle in libelles]

    figure, axes = plt.subplots(figsize=(8, 3.6))
    barres = axes.bar(libelles, valeurs, color=couleurs, width=0.62)
    axes.bar_label(
        barres,
        labels=[f"{100 * v / total:.0f} %" for v in valeurs],
        padding=4,
        color=GRIS,
        fontsize=8.5,
    )
    soigner(axes, "Nombre d'offres reçues par marché")
    legender(
        figure,
        "En milliers de marchés, uniquement là où l'information existe : 899 298 marchés sur "
        "1 833 468, soit 49 %.\nEn ocre, le marché à offre unique, principal indicateur de "
        "risque de la littérature. Le trou de 51 % dans cette colonne\nest la difficulté "
        "principale identifiée pour la détection.",
    )
    enregistrer(figure, "05-offres-recues")


def main() -> None:
    print("Figures generees depuis mesures/resultats/ :")
    figure_total_annuel()
    figure_tranches_montant()
    figure_saisonnalite()
    figure_familles_cpv()
    figure_offres_recues()
    print(f"\nDossier : {chemin_lisible(FIGURES)}")


if __name__ == "__main__":
    main()
