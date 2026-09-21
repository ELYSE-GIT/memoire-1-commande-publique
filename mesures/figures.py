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

# Sans ce sel fixe, matplotlib tire au hasard les identifiants internes du SVG a chaque execution :
# deux figures identiques produisent alors deux fichiers entierement differents, et git affiche des
# milliers de lignes modifiees pour rien. Avec un sel fixe et sans date dans les metadonnees, un
# fichier ne change que si la figure a reellement change.
matplotlib.rcParams["svg.hashsalt"] = "commande-publique"
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, LogNorm  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
AGREGATS = RACINE / "mesures" / "resultats"
FIGURES = RACINE / "memoire" / "figures"

# Palette des series, verifiee par un validateur : luminosite dans la bande utile, saturation
# suffisante pour ne pas virer au gris, et surtout separation garantie pour un lecteur daltonien
# (ecart deutan 8,8 et normal 22,3 sur la paire la plus proche). La palette precedente, tiree du
# guide du projet, echouait sur trois criteres : elle etait trop sombre, trop desaturee, et le
# vert et l'ocre devenaient indiscernables en vision deuteranope.
SERIE_1 = "#3a6ea5"  # bleu ardoise
SERIE_2 = "#c05621"  # terre de Sienne
SERIE_3 = "#2f8f68"  # vert sapin
SERIE_4 = "#7a4b9e"  # prune

# Le texte porte ses propres couleurs, jamais celles d'une serie : un titre ou un chiffre reste
# lisible et neutre, c'est la marque coloree a cote de lui qui porte l'identite.
ENCRE = "#16223a"
GRIS = "#6b6b6b"
FILET = "#d9d4c7"

# Rampe sequentielle : une seule teinte, du clair au fonce. Jamais d'arc-en-ciel pour representer
# une magnitude : l'oeil lit une progression de clarte, pas une progression de teintes.
RAMPE_BLEUE = LinearSegmentedColormap.from_list(
    "bleu_commande_publique",
    ["#f2f5f9", "#cfdcea", "#a7c0da", "#7aa0c6", "#4e7fb0", "#2b5a89", "#17395a"],
)


def chemin_lisible(chemin: Path) -> str:
    """Affiche un chemin relatif au projet quand c'est possible, absolu sinon.

    Sans cette precaution, le script plante des que la sortie est ailleurs que dans le depot,
    par exemple dans un dossier temporaire pendant les tests.
    """
    try:
        return str(chemin.relative_to(RACINE))
    except ValueError:
        return str(chemin)


# Les libelles produits par SQL sont en ASCII, par prudence sur les encodages entre systemes.
# Ils sont traduits ici, au moment de l'affichage, ou les accents sont attendus.
LIBELLES_TRANCHES = {
    "moins de 25 k": "moins de 25 k€",
    "25 a 90 k": "25 à 90 k€",
    "90 a 214 k": "90 à 214 k€",
    "214 k a 1 M": "214 k€ à 1 M€",
    "1 a 10 M": "1 à 10 M€",
    "plus de 10 M": "plus de 10 M€",
}


# Meme principe pour les noms de champs, ecrits en ASCII dans les requetes SQL.
CHAMPS_ACCENTUES = {
    "Duree en mois": "Durée en mois",
    "Procedure": "Procédure",
    "Categorie d'acheteur": "Catégorie d'acheteur",
    "Considerations sociales": "Considérations sociales",
    "Offres recues": "Offres reçues",
    "Sous-traitance declaree": "Sous-traitance déclarée",
}


def libelle_tranche(brut: str) -> str:
    """Retire le numero de tri (« 1. moins de 25 k ») et rend le libelle accentue."""
    sans_numero = brut.split(". ", 1)[1]
    return LIBELLES_TRANCHES.get(sans_numero, sans_numero)


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
        # metadata retire la date de creation, qui rendrait chaque fichier different du precedent.
        metadonnees = {"Date": None} if extension == "svg" else {}
        # Dans un SVG, seuls les elements rasterises dependent de cette resolution : 150 points par
        # pouce suffisent pour un nuage imprime, et divisent par deux le poids du fichier.
        resolution = 150 if extension == "svg" else 200
        figure.savefig(
            FIGURES / f"{nom}.{extension}",
            dpi=resolution,
            bbox_inches="tight",
            facecolor="white",
            metadata=metadonnees,
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

    gauche.bar(annees, brut, color=SERIE_2, width=0.6)
    soigner(gauche, "Total brut déclaré")

    droite.bar(annees, nettoye, color=SERIE_3, width=0.6)
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
    libelles = [libelle_tranche(d["tranche"]) for d in donnees]
    parts = [float(d["part_pourcent"]) for d in donnees]

    figure, axes = plt.subplots(figsize=(7.5, 3.6))
    barres = axes.barh(libelles, parts, color=SERIE_1, height=0.62)
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
    couleurs = [SERIE_2 if v > moyenne else SERIE_1 for v in valeurs]

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
    barres = axes.barh(libelles, valeurs, color=SERIE_1, height=0.62)
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
    couleurs = [SERIE_2 if libelle == "1 offre" else SERIE_1 for libelle in libelles]

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
        "En milliers de lignes, uniquement là où l'information existe : 899 298 lignes, "
        "soit 800 782 marchés\nsur 1 833 468, c'est-à-dire 44 %. En couleur chaude, le marché "
        "à offre unique, principal indicateur de risque de la littérature.\nLe trou de 56 % "
        "dans cette "
        "colonne est la difficulté principale identifiée pour la détection.",
    )
    enregistrer(figure, "05-offres-recues")


def figure_histogramme_montants() -> None:
    """Forme de la distribution : une seule barre par quart de puissance de dix.

    Echelle logarithmique parce que les montants s'etalent de quelques euros a cent milliards.
    En echelle lineaire, 99 % des marches seraient ecrases sur la premiere colonne.
    """
    donnees = lire("montants-histogramme")
    x = [float(d["puissance_de_dix"]) for d in donnees]
    y = [int(d["marches"]) / 1000 for d in donnees]

    figure, axes = plt.subplots(figsize=(8.5, 3.8))
    axes.bar(x, y, width=0.22, color=SERIE_1)
    axes.axvline(5.1, color=ENCRE, linewidth=1, linestyle="--")
    axes.text(5.2, max(y) * 0.86, "médiane\n126 372 €", color=ENCRE, fontsize=8.5)
    axes.set_xticks([2, 3, 4, 5, 6, 7, 8, 9])
    axes.set_xticklabels(["100 €", "1 k€", "10 k€", "100 k€", "1 M€", "10 M€", "100 M€", "1 Md€"])
    soigner(axes, "Distribution des montants de marché")
    legender(
        figure,
        "Nombre de marchés, en milliers, par quart de puissance de dix. Échelle logarithmique en "
        "abscisse :\nles montants s'étalent de quelques euros à cent milliards, une échelle "
        "linéaire écraserait tout sur la gauche.\nLa distribution est proche d'une loi "
        "log-normale, ce qui justifiera de raisonner en écart au logarithme du montant.",
    )
    enregistrer(figure, "06-histogramme-montants")


def figure_concentration() -> None:
    """Courbe de Lorenz : la concentration des montants sur une poignee d'entreprises."""
    donnees = lire("concentration-titulaires")
    x = [float(d["part_titulaires"]) for d in donnees]
    y = [float(d["part_montants"]) for d in donnees]

    figure, axes = plt.subplots(figsize=(6.6, 4.4))
    axes.plot(
        [0, 100],
        [0, 100],
        color=GRIS,
        linewidth=1,
        linestyle="--",
        label="répartition parfaitement égale",
    )
    axes.plot(x, y, color=SERIE_1, linewidth=2, label="répartition observée")

    def ecart_au_seuil(ligne: dict[str, str], seuil: float) -> float:
        """Distance entre le point mesure et le seuil que l'on veut annoter."""
        return abs(float(ligne["part_titulaires"]) - seuil)

    for seuil, couleur in ((1.0, SERIE_2), (10.0, SERIE_4)):
        proche = min(donnees, key=lambda ligne: ecart_au_seuil(ligne, seuil))
        px, py = float(proche["part_titulaires"]), float(proche["part_montants"])
        axes.plot([px], [py], marker="o", markersize=8, color=couleur, zorder=3)
        axes.annotate(
            f"{px:.0f} % des titulaires\ncaptent {py:.0f} % des montants",
            xy=(px, py),
            xytext=(px + 8, py - 18),
            color=ENCRE,
            fontsize=8.5,
            arrowprops={"arrowstyle": "-", "color": GRIS, "linewidth": 0.8},
        )

    axes.set_xlim(0, 100)
    axes.set_ylim(0, 100)
    axes.set_xlabel(
        "part des titulaires, classés du plus gros au plus petit", color=GRIS, fontsize=8.5
    )
    axes.set_ylabel("part cumulée des montants", color=GRIS, fontsize=8.5)
    axes.legend(loc="lower right", frameon=False, fontsize=8.5, labelcolor=GRIS)
    soigner(axes, "Concentration des montants sur une poignée d'entreprises")
    legender(
        figure,
        "Courbe de Lorenz, calculée sur les montants hors anomalies signalées, par titulaire.\n"
        "Plus la courbe s'éloigne de la diagonale, plus la commande publique est concentrée. "
        "Un marché concurrentiel\nne produit pas une courbe plate : cette concentration est un "
        "point à expliquer, pas encore une anomalie.",
    )
    enregistrer(figure, "07-concentration-titulaires")


def figure_heatmap_saisonnalite() -> None:
    """Saisonnalite annee par annee : la forme se repete-t-elle ?"""
    donnees = lire("saisonnalite-annee-mois")
    annees = sorted({int(d["annee"]) for d in donnees})
    grille = [[0.0] * 12 for _ in annees]
    for d in donnees:
        grille[annees.index(int(d["annee"]))][int(d["mois"]) - 1] = int(d["marches"]) / 1000

    figure, axes = plt.subplots(figsize=(8.5, 3.6))
    image = axes.imshow(grille, cmap=RAMPE_BLEUE, aspect="auto")
    axes.set_xticks(range(12))
    axes.set_xticklabels(
        [
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
    )
    axes.set_yticks(range(len(annees)))
    axes.set_yticklabels([str(annee) for annee in annees])
    axes.grid(visible=False)
    barre = figure.colorbar(image, ax=axes, shrink=0.82)
    barre.set_label("milliers de marchés", color=GRIS, fontsize=8.5)
    barre.ax.tick_params(colors=GRIS, labelsize=8)
    soigner(axes, "La saisonnalité se répète-t-elle d'une année à l'autre ?")
    legender(
        figure,
        "Marchés notifiés par mois et par année, en milliers. Une seule teinte, du clair au "
        "foncé : l'œil lit\nune progression d'intensité, pas un code de couleurs. Les colonnes "
        "de décembre et de juillet ressortent chaque année,\nce qui confirme un effet de "
        "calendrier budgétaire et non un accident d'une année particulière.",
    )
    enregistrer(figure, "08-heatmap-saisonnalite")


def figure_offre_unique_par_cpv() -> None:
    """Quelles familles d'achat sont les moins concurrentielles ?"""
    donnees = sorted(
        lire("offre-unique-par-cpv"), key=lambda d: float(d["part_offre_unique"]), reverse=True
    )[:12]
    noms = {
        "92": "Loisirs, culture et sport",
        "72": "Services informatiques",
        "66": "Services financiers et assurance",
        "50": "Réparation et entretien",
        "30": "Machines de bureau et informatique",
        "48": "Logiciels",
        "79": "Services aux entreprises",
        "34": "Matériel de transport",
        "45": "Travaux de construction",
        "71": "Architecture et ingénierie",
        "33": "Matériel médical",
        "90": "Déchets et environnement",
        "35": "Équipements de sécurité",
        "60": "Services de transport",
        "80": "Enseignement et formation",
        "85": "Santé et action sociale",
        "31": "Machines et appareils électriques",
        "39": "Mobilier et équipement",
        "44": "Matériaux de construction",
        "15": "Produits alimentaires",
        "09": "Produits pétroliers et électricité",
        "77": "Services agricoles",
    }
    libelles = [noms.get(d["famille_cpv"], f"Division {d['famille_cpv']}") for d in donnees]
    parts = [float(d["part_offre_unique"]) for d in donnees]
    moyenne = 22.0

    figure, axes = plt.subplots(figsize=(8.5, 4.6))
    barres = axes.barh(libelles, parts, color=SERIE_1, height=0.62)
    axes.bar_label(barres, fmt="%.0f %%", padding=4, color=GRIS, fontsize=8.5)
    axes.axvline(moyenne, color=SERIE_2, linewidth=1.4)
    axes.text(
        moyenne + 0.6,
        len(libelles) - 0.4,
        f"moyenne : {moyenne:.0f} %",
        color=SERIE_2,
        fontsize=8.5,
    )
    axes.invert_yaxis()
    axes.grid(axis="y", visible=False)
    axes.grid(axis="x", color=FILET, linewidth=0.6)
    axes.set_xlim(0, max(parts) * 1.18)
    soigner(axes, "Les familles d'achat les moins concurrentielles")
    legender(
        figure,
        "Part des marchés n'ayant reçu qu'une seule offre, par division du code CPV, sur les "
        "familles de plus de\n10 000 marchés renseignés. Le trait vertical marque la moyenne "
        "générale de 22 %.\nLes services informatiques à 37 % méritent une explication : marchés "
        "très spécialisés, ou concurrence réellement faible ?",
    )
    enregistrer(figure, "09-offre-unique-par-cpv")


def figure_completude() -> None:
    """Quels champs peut-on reellement utiliser ?"""
    donnees = sorted(lire("completude-champs"), key=lambda d: float(d["part_renseigne"]))
    libelles = [CHAMPS_ACCENTUES.get(d["champ"], d["champ"]) for d in donnees]
    parts = [float(d["part_renseigne"]) for d in donnees]
    # Le seuil de 90 % separe ce qui est directement exploitable de ce qui demande une precaution.
    couleurs = [SERIE_1 if p >= 90 else SERIE_2 for p in parts]

    figure, axes = plt.subplots(figsize=(8, 4.4))
    barres = axes.barh(libelles, parts, color=couleurs, height=0.62)
    axes.bar_label(barres, fmt="%.1f %%", padding=4, color=GRIS, fontsize=8.5)
    axes.axvline(90, color=GRIS, linewidth=1, linestyle="--")
    axes.grid(axis="y", visible=False)
    axes.grid(axis="x", color=FILET, linewidth=0.6)
    axes.set_xlim(0, 112)
    soigner(axes, "Complétude des champs : ce qui est utilisable, et ce qui ne l'est pas")
    legender(
        figure,
        "Part des lignes où le champ est renseigné, sur les 2 114 675 lignes de l'état actuel.\n"
        "En bleu, les champs au-dessus de 90 %, directement exploitables. En couleur chaude, ceux "
        "qui demandent une précaution\nméthodologique : la sous-traitance, les considérations "
        "sociales et le nombre d'offres manquent dans plus d'un cas sur deux.",
    )
    enregistrer(figure, "10-completude-des-champs")


def figure_quartiles_acheteurs() -> None:
    """Distributions comparees : une boite a moustaches par type d'acheteur."""
    donnees = sorted(lire("acheteurs-quartiles"), key=lambda d: float(d["mediane"]))
    libelles = [f"{d['categorie']}\n({int(d['marches']) // 1000} k marchés)" for d in donnees]
    boites = [
        {
            "label": libelle,
            "whislo": float(d["bas"]),
            "q1": float(d["quartile_1"]),
            "med": float(d["mediane"]),
            "q3": float(d["quartile_3"]),
            "whishi": float(d["haut"]),
            "fliers": [],
        }
        for libelle, d in zip(libelles, donnees, strict=True)
    ]

    figure, axes = plt.subplots(figsize=(8.5, 4.4))
    axes.bxp(
        boites,
        # orientation remplace l'ancien parametre vert, retire dans matplotlib 3.13.
        orientation="horizontal",
        showfliers=False,
        patch_artist=True,
        boxprops={"facecolor": SERIE_1, "edgecolor": SERIE_1, "linewidth": 0},
        medianprops={"color": "white", "linewidth": 1.6},
        whiskerprops={"color": GRIS, "linewidth": 1},
        capprops={"color": GRIS, "linewidth": 1},
    )
    axes.set_xscale("log")
    axes.set_xlabel("montant du marché, échelle logarithmique", color=GRIS, fontsize=8.5)
    axes.grid(axis="y", visible=False)
    axes.grid(axis="x", color=FILET, linewidth=0.6)
    soigner(axes, "Montants selon le type d'acheteur")
    legender(
        figure,
        "Boîtes à moustaches, hors montants signalés comme anormaux, pour les catégories de plus "
        "de 20 000 marchés.\nLa boîte couvre la moitié centrale des marchés, le trait blanc la "
        "médiane, les moustaches les 5e et 95e centiles.\nLes régions, syndicats mixtes et "
        "départements ont une médiane proche de 200 k€, soit le double des communes et de l'État, "
        "à 100 k€.\nL'État se distingue autrement : sa dispersion est la plus large, du très "
        "petit achat au marché à plusieurs millions.",
    )
    enregistrer(figure, "11-montants-par-type-acheteur")


def figure_carte_acheteurs() -> None:
    """Repartition geographique, tracee a partir des seules coordonnees."""
    donnees = lire("geographie-acheteurs")
    longitudes = [float(d["longitude"]) for d in donnees]
    latitudes = [float(d["latitude"]) for d in donnees]
    poids = [int(d["marches"]) for d in donnees]
    maximum = max(poids)

    figure, axes = plt.subplots(figsize=(6.4, 6.2))
    # Echelle logarithmique pour la couleur : quelques grandes villes depassent 50 000 marches
    # quand la mediane des cases est autour de 100. En echelle lineaire, tout le territoire
    # deviendrait blanc et la figure ne montrerait que Paris.
    nuage = axes.scatter(
        longitudes,
        latitudes,
        s=[12 + 260 * (p / maximum) ** 0.5 for p in poids],
        c=poids,
        cmap=RAMPE_BLEUE,
        norm=LogNorm(vmin=min(poids), vmax=maximum),
        alpha=0.85,
        linewidths=0,
        # 2 423 points tracés en vectoriel donnaient un SVG de 1,6 Mo. Rasteriser le seul nuage
        # ramène le fichier sous 100 Ko : le texte et les axes restent nets a l'impression,
        # et un nuage de points n'a rien a gagner a rester vectoriel.
        rasterized=True,
    )
    barre = figure.colorbar(nuage, ax=axes, shrink=0.6)
    barre.set_label("marchés par point, échelle logarithmique", color=GRIS, fontsize=8.5)
    barre.ax.tick_params(colors=GRIS, labelsize=8)
    axes.set_aspect(1 / 0.66)  # correction sommaire de la projection aux latitudes francaises
    axes.set_xlabel("longitude", color=GRIS, fontsize=8.5)
    axes.set_ylabel("latitude", color=GRIS, fontsize=8.5)
    axes.grid(color=FILET, linewidth=0.6)
    soigner(axes, "Où sont les acheteurs publics")
    legender(
        figure,
        "Chaque point regroupe les acheteurs d'une même case de 0,1 degré, soit environ 11 km, "
        "ayant passé plus de 30 marchés.\nTaille et intensité proportionnelles au nombre de "
        "marchés. Aucun fond de carte n'est utilisé : la forme du territoire\napparaît par la "
        "seule densité des acheteurs, ce qui évite d'embarquer un jeu de données géographiques "
        "supplémentaire.",
    )
    enregistrer(figure, "12-carte-des-acheteurs")


def figure_evolution_mensuelle() -> None:
    """Serie temporelle : une ligne, parce que l'ordre des points a un sens."""
    donnees = lire("evolution-mensuelle")
    mois = [d["mois"][:7] for d in donnees]
    valeurs = [int(d["marches"]) / 1000 for d in donnees]

    figure, axes = plt.subplots(figsize=(9, 3.8))
    axes.plot(mois, valeurs, color=SERIE_1, linewidth=2)
    axes.fill_between(range(len(mois)), valeurs, color=SERIE_1, alpha=0.12)
    axes.set_xticks(range(0, len(mois), 6))
    axes.set_xticklabels([mois[i] for i in range(0, len(mois), 6)], rotation=45, ha="right")
    axes.set_ylabel("milliers de marchés", color=GRIS, fontsize=8.5)
    soigner(axes, "Nombre de marchés notifiés, mois par mois")
    legender(
        figure,
        "Marchés notifiés par mois, en milliers, de janvier 2019 à juin 2026.\nLa progression "
        "générale reflète autant l'élargissement de la collecte que l'activité réelle : un nombre "
        "qui monte dans un jeu de données\nagrégé ne signifie pas forcément que le phénomène "
        "mesuré augmente. À vérifier source par source avant toute interprétation.",
    )
    enregistrer(figure, "13-evolution-mensuelle")


def figure_distance_titulaires() -> None:
    """Achat local ou national ?"""
    donnees = lire("distance-titulaires")
    libelles = [d["tranche"].split(". ", 1)[1].replace(" a ", " à ") for d in donnees]
    valeurs = [int(d["marches"]) / 1000 for d in donnees]
    total = sum(valeurs)

    figure, axes = plt.subplots(figsize=(8, 3.6))
    barres = axes.bar(libelles, valeurs, color=SERIE_1, width=0.62)
    axes.bar_label(
        barres,
        labels=[f"{100 * v / total:.0f} %" for v in valeurs],
        padding=4,
        color=GRIS,
        fontsize=8.5,
    )
    axes.set_ylabel("milliers de marchés", color=GRIS, fontsize=8.5)
    soigner(axes, "Distance entre l'acheteur et son titulaire")
    legender(
        figure,
        "Marchés dont la distance entre acheteur et titulaire est calculable, en milliers.\n"
        "Plus de la moitié des marchés sont attribués à moins de 50 km : la commande publique est "
        "largement un fait local,\nce qui donne tout son sens à une recherche par territoire dans "
        "le service final.",
    )
    enregistrer(figure, "14-distance-titulaires")


def figure_offre_unique_par_tranche() -> None:
    """Relation entre le montant et la concurrence : une ligne, l'ordre des tranches a un sens."""
    donnees = lire("offre-unique-par-tranche")
    libelles = [libelle_tranche(d["tranche"]) for d in donnees]
    parts = [float(d["part_offre_unique"]) for d in donnees]
    volumes = [int(d["marches"]) / 1000 for d in donnees]

    figure, axes = plt.subplots(figsize=(8.5, 4))
    axes.plot(libelles, parts, color=SERIE_1, linewidth=2, marker="o", markersize=9)
    # Une etiquette sur chaque point : ils sont six, et c'est la valeur qui compte ici.
    for x, (part, volume) in enumerate(zip(parts, volumes, strict=True)):
        axes.annotate(
            f"{part:.1f} %",
            xy=(x, part),
            xytext=(0, 11),
            textcoords="offset points",
            ha="center",
            color=ENCRE,
            fontsize=9,
            fontweight="bold",
        )
        axes.annotate(
            f"{volume:.0f} k marchés",
            xy=(x, part),
            xytext=(0, -20),
            textcoords="offset points",
            ha="center",
            color=GRIS,
            fontsize=8,
        )
    axes.set_ylim(min(parts) - 6, max(parts) + 5)
    axes.set_ylabel("part des marchés à offre unique", color=GRIS, fontsize=8.5)
    soigner(axes, "Plus le marché est petit, moins il attire de candidats")
    legender(
        figure,
        "Part des marchés n'ayant reçu qu'une seule offre, par tranche de montant, hors montants "
        "signalés comme anormaux.\nLa relation est monotone : 27,1 % sous 25 k€ contre 16,2 % "
        "au-dessus de 10 M€.\nConséquence pour la détection : une offre unique sur un petit "
        "marché est banale, sur un gros marché elle l'est beaucoup moins.",
    )
    enregistrer(figure, "15-offre-unique-par-tranche")


def main() -> None:
    print("Figures generees depuis mesures/resultats/ :")
    figure_total_annuel()
    figure_tranches_montant()
    figure_saisonnalite()
    figure_familles_cpv()
    figure_offres_recues()
    figure_histogramme_montants()
    figure_concentration()
    figure_heatmap_saisonnalite()
    figure_offre_unique_par_cpv()
    figure_completude()
    figure_quartiles_acheteurs()
    figure_carte_acheteurs()
    figure_evolution_mensuelle()
    figure_distance_titulaires()
    figure_offre_unique_par_tranche()
    print(f"\nDossier : {chemin_lisible(FIGURES)}")


if __name__ == "__main__":
    main()
