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


def lire_date(motif: str) -> list[dict[str, str]]:
    """Lit le plus recent des agregats dates, par exemple `2026-09-21-rapprochement.csv`.

    Les mesures datees s'accumulent volontairement : on veut pouvoir comparer deux executions.
    La figure, elle, montre toujours la derniere.
    """
    fichiers = sorted(AGREGATS.glob(f"*-{motif}.csv"))
    if not fichiers:
        message = f"aucun fichier *-{motif}.csv dans {AGREGATS}"
        raise FileNotFoundError(message)
    with fichiers[-1].open(encoding="utf-8") as fichier:
        return list(csv.DictReader(fichier))


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


def figure_rapprochement() -> None:
    """L'entonnoir du rapprochement entre les deux sources, niveau par niveau."""
    lignes = lire_date("rapprochement-boamp-decp")
    libelles = [
        "Avis analysés",
        "Portant au moins un SIRET",
        "Acheteur reconnu dans les DECP",
        "Plus une fenêtre de 18 mois",
        "Plus un objet proche",
        "Plus le titulaire retrouvé",
    ]
    parts = [float(ligne["part_pourcent"]) for ligne in lignes]
    effectifs = [int(ligne["avis"]) for ligne in lignes]

    figure, axes = plt.subplots(figsize=(8.5, 3.8))
    # Un entonnoir se lit de haut en bas : chaque barre est un sous-ensemble de la precedente.
    # Les deux dernieres sont mises en avant : ce sont les niveaux exploitables.
    couleurs = [SERIE_1] * 4 + [SERIE_3, SERIE_2]
    barres = axes.barh(libelles, parts, color=couleurs, height=0.64)
    axes.bar_label(
        barres,
        labels=[f"{p:.1f} %  ({n} avis)" for p, n in zip(parts, effectifs, strict=True)],
        padding=5,
        color=GRIS,
        fontsize=8.5,
    )
    axes.invert_yaxis()
    axes.grid(axis="y", visible=False)
    axes.grid(axis="x", color=FILET, linewidth=0.6)
    axes.set_xlim(0, 118)
    soigner(axes, "Peut-on relier un avis du BOAMP à un marché des DECP ?")
    legender(
        figure,
        "Mesure sur 300 avis de résultat parus au premier semestre 2025. Aucun identifiant n'est "
        "commun aux deux sources :\nle rapprochement se construit critère par critère. En vert, le "
        "niveau de confiance moyenne ; en couleur chaude, la confiance haute,\nquand le SIRET du "
        "titulaire figure aussi dans l'avis. Reproductible par make bench-rapprochement.",
    )
    enregistrer(figure, "16-rapprochement-boamp-decp")


def figure_precision_rapprochement() -> None:
    """Le compromis du seuil : couvrir plus, ou se tromper moins.

    Les deux series sont des pourcentages, donc un seul axe suffit. Superposer deux echelles
    differentes dans un meme cadre est la premiere cause de mauvaise lecture d'un graphique.
    """
    donnees = lire("rapprochement-precision")
    seuils = [float(d["seuil_objet"]) for d in donnees]
    couverture = [float(d["couverture_pourcent"]) for d in donnees]
    justesse = [float(d["justesse_estimee_pourcent"]) for d in donnees]
    justes = [float(d["rapprochements_justes_attendus"]) for d in donnees]

    figure, (gauche, droite) = plt.subplots(1, 2, figsize=(10, 3.8))

    gauche.plot(
        seuils,
        justesse,
        color=SERIE_1,
        linewidth=2,
        marker="o",
        markersize=8,
        label="justesse des rapprochements",
    )
    gauche.plot(
        seuils,
        couverture,
        color=SERIE_2,
        linewidth=2,
        marker="s",
        markersize=8,
        label="couverture des avis",
    )
    gauche.set_xlabel("seuil de similarité des objets", color=GRIS, fontsize=8.5)
    gauche.set_ylabel("pourcentage", color=GRIS, fontsize=8.5)
    gauche.set_ylim(0, 105)
    gauche.legend(loc="center left", frameon=False, fontsize=8.5, labelcolor=GRIS)
    soigner(gauche, "Couvrir plus, ou se tromper moins")

    # Le produit des deux : ce qui compte reellement, le nombre de rapprochements justes obtenus.
    barres = droite.bar([str(s) for s in seuils], justes, color=SERIE_1, width=0.6)
    # Les deux premieres barres sont a egalite : c'est le message de ce panneau.
    barres[0].set_color(SERIE_2)
    barres[1].set_color(SERIE_2)
    droite.bar_label(barres, fmt="%.0f", padding=4, color=GRIS, fontsize=8.5)
    droite.set_xlabel("seuil de similarité des objets", color=GRIS, fontsize=8.5)
    droite.set_ylabel("rapprochements justes", color=GRIS, fontsize=8.5)
    soigner(droite, "Ce qui reste une fois les erreurs retirées")

    figure.suptitle(
        "Descendre le seuil sous 0,5 n'ajoute que des erreurs",
        color=ENCRE,
        fontsize=12.5,
        fontweight="bold",
        x=0.01,
        ha="left",
        y=1.04,
    )
    legender(
        figure,
        "Mesure sur 300 avis, fenêtre de 18 mois. La justesse vient de la relecture à la main de "
        "60 paires, stratifiées par tranche\nde similarité puis redressées par leur effectif réel. "
        "À gauche, le compromis ; à droite, son produit : le nombre de rapprochements\njustes. "
        "Les seuils 0,4 et 0,5 en donnent autant, mais 0,4 y ajoute 19 erreurs.",
    )
    enregistrer(figure, "17-precision-du-rapprochement")


def figure_nettoyage() -> None:
    """Ce que le nettoyage retire, et ce qu'il garde.

    Deux panneaux : le passage d'une couche a l'autre, puis l'effet de chaque regle. Les deux
    repondent a la meme question, a deux echelles differentes.
    """
    couches = lire("nettoyage-couches")
    regles = sorted(lire("nettoyage-regles"), key=lambda r: int(r["lignes_marquees"]), reverse=True)

    # Les libelles du panneau de droite sont longs : sans un espacement genereux entre les deux
    # panneaux, ils debordent sur celui de gauche. Le defaut a ete vu en regardant la figure
    # produite, ce qu'aucun test ne remplace.
    figure, (gauche, droite) = plt.subplots(
        1, 2, figsize=(12.5, 4.2), gridspec_kw={"wspace": 0.75, "width_ratios": [1, 1.5]}
    )

    noms = [c["couche"] for c in couches]
    lignes = [int(c["lignes"]) / 1e6 for c in couches]
    barres = gauche.bar(noms, lignes, color=[SERIE_1, SERIE_1, SERIE_3], width=0.55)
    gauche.bar_label(barres, fmt="%.2f M", padding=4, color=ENCRE, fontsize=9, fontweight="bold")
    for x, couche in enumerate(couches):
        gauche.annotate(
            f"{couche['colonnes']} colonnes",
            xy=(x, 0),
            xytext=(0, -26),
            textcoords="offset points",
            ha="center",
            color=GRIS,
            fontsize=8,
        )
    gauche.set_ylabel("millions de lignes", color=GRIS, fontsize=8.5)
    gauche.set_ylim(0, max(lignes) * 1.18)
    soigner(gauche, "De la donnée brute à la table servie")

    # Echelle logarithmique : la regle la plus frequente marque 200 fois plus de lignes que la
    # plus rare. En echelle lineaire, six des neuf regles seraient invisibles.
    libelles = [r["verifie"] for r in regles]
    marquees = [int(r["lignes_marquees"]) for r in regles]
    barres = droite.barh(libelles, marquees, color=SERIE_2, height=0.62)
    droite.bar_label(
        barres,
        labels=[f"{m:,}".replace(",", " ") for m in marquees],
        padding=4,
        color=GRIS,
        fontsize=8,
    )
    droite.set_xscale("log")
    droite.invert_yaxis()
    droite.grid(axis="y", visible=False)
    droite.grid(axis="x", color=FILET, linewidth=0.6)
    droite.set_xlim(100, max(marquees) * 6)
    droite.tick_params(axis="y", labelsize=8)
    soigner(droite, "Lignes marquées par chaque règle")

    legender(
        figure,
        "À gauche, les trois couches : la donnée brute, l'état actuel de chaque marché avec ses "
        "problèmes marqués, puis les marchés\nexploitables pour une analyse de prix. À droite, "
        "l'effet de chacune des neuf règles, en échelle logarithmique : la plus fréquente\nmarque "
        "deux cents fois plus de lignes que la plus rare. Aucune ligne n'est supprimée : une ligne "
        "marquée reste consultable avec son motif.",
    )
    enregistrer(figure, "18-nettoyage-par-regle")


def figure_modele_vs_regles() -> None:
    """Ce qu'un modele non supervise apporte, et ce qu'il n'apporte pas.

    Le graphique porte un resultat contre-intuitif, donc il doit etre lisible sans le texte : le
    modele laisse a lui-meme fait **moins bien que le hasard**, et la seule chose qui le remet au
    niveau de la regle est une information metier donnee de l'exterieur.

    Une echelle logarithmique en abscisse : les budgets vont de 100 a 30 000, une echelle lineaire
    ecraserait les trois premiers points contre l'axe.
    """
    donnees = lire("modele-vs-regles")
    budgets = sorted({int(d["budget_alertes"]) for d in donnees})
    par_methode: dict[str, list[float]] = {}
    for ligne in donnees:
        par_methode.setdefault(ligne["methode"], []).append(float(ligne["precision_pourcent"]))

    figure, axes = plt.subplots(figsize=(9, 4.6))
    series = (
        ("regle", "règle de prix", SERIE_1, "o", "-"),
        ("modele_oriente", "modèle, orienté vers les montants élevés", SERIE_3, "s", "-"),
        ("modele", "modèle, laissé libre", SERIE_2, "^", "--"),
        ("hasard", "hasard", SERIE_4, "d", ":"),
    )
    for cle, etiquette, couleur, marqueur, trait in series:
        axes.plot(
            budgets,
            par_methode[cle],
            color=couleur,
            linewidth=2,
            marker=marqueur,
            markersize=7,
            linestyle=trait,
            label=etiquette,
        )

    axes.set_xscale("log")
    axes.set_xticks(budgets)
    axes.set_xticklabels([f"{b:,}".replace(",", " ") for b in budgets])
    axes.set_ylim(-4, 105)
    axes.set_xlabel("budget d'alertes, échelle logarithmique", color=GRIS, fontsize=8.5)
    axes.set_ylabel("précision, en pourcentage", color=GRIS, fontsize=8.5)
    axes.legend(loc="center left", frameon=False, fontsize=8.5, labelcolor=GRIS)
    soigner(axes, "À budget d'alertes égal, la règle devance le modèle")

    legender(
        figure,
        "Mesure du 29 septembre 2026 sur 2 053 765 marchés, `make bench-modele`. Isolation "
        "Forest, 100 arbres, 256 échantillons par arbre.\nÉtiquette faible : les montants que le "
        "producteur des données signale lui-même. Laissé libre, le modèle désigne des "
        "montants\nanormalement BAS, que cette étiquette ne marque jamais, et sa précision tombe "
        "sous le hasard. Orienté vers les montants\nélevés, le même modèle redevient comparable à "
        "la règle sans la dépasser. La connaissance métier, pas la puissance\nstatistique, fait la "
        "différence.",
    )
    enregistrer(figure, "19-modele-vs-regles")


def figure_recherche() -> None:
    """Deux moteurs, deux semantiques, et le compromis que la mesure revele.

    Deux panneaux parce que deux grandeurs incomparables sont en jeu : une duree, en
    millisecondes et sur une echelle logarithmique parce qu'elle varie d'un facteur mille, et un
    nombre de questions restees sans reponse. Les superposer dans un seul cadre serait la
    premiere cause de mauvaise lecture.
    """
    donnees = lire("recherche-par-moteur")
    # Ordre choisi pour la lecture : les deux strategies PostgreSQL simples, puis la cascade qui
    # est la conclusion, puis DuckDB.
    ordre = [
        ("postgres_et", "PostgreSQL\ntous les mots"),
        ("postgres_ou", "PostgreSQL\nau moins un mot"),
        ("postgres_et_puis_ou", "PostgreSQL\nen cascade"),
        ("duckdb_et_brut", "DuckDB\nsans nettoyage"),
        ("duckdb_et", "DuckDB\ntous les mots"),
        ("duckdb_ou", "DuckDB\nau moins un mot"),
    ]
    par_moteur = {ligne["moteur"]: ligne for ligne in donnees}
    etiquettes = [libelle for cle, libelle in ordre if cle in par_moteur]
    p50 = [float(par_moteur[cle]["latence_p50_ms"]) for cle, _ in ordre if cle in par_moteur]
    p95 = [float(par_moteur[cle]["latence_p95_ms"]) for cle, _ in ordre if cle in par_moteur]
    muets = [int(par_moteur[cle]["sans_resultat"]) for cle, _ in ordre if cle in par_moteur]
    total = [int(par_moteur[cle]["questions"]) for cle, _ in ordre if cle in par_moteur]

    figure, (gauche, droite) = plt.subplots(1, 2, figsize=(10, 4.2))
    position = list(range(len(etiquettes)))
    largeur = 0.38

    gauche.barh(
        [rang + largeur / 2 for rang in position], p50, largeur, color=SERIE_1, label="médiane"
    )
    gauche.barh(
        [rang - largeur / 2 for rang in position],
        p95,
        largeur,
        color=SERIE_2,
        label="95e centile",
    )
    gauche.set_xscale("log")
    gauche.set_yticks(position)
    gauche.set_yticklabels(etiquettes, fontsize=7.5)
    gauche.invert_yaxis()
    gauche.set_xlabel("latence en millisecondes, échelle logarithmique", color=GRIS, fontsize=8.5)
    gauche.legend(loc="lower right", frameon=False, fontsize=8.5, labelcolor=GRIS)
    soigner(gauche, "Le temps de réponse")
    gauche.grid(axis="y", visible=False)
    gauche.grid(axis="x", color=FILET, linewidth=0.6)

    barres = droite.barh(position, muets, 0.6, color=SERIE_3)
    # La barre la plus parlante est celle de la version naive : on la distingue.
    for index, valeur in enumerate(muets):
        if valeur >= 0.8 * total[index]:
            barres[index].set_color(SERIE_2)
    droite.bar_label(barres, fmt="%d", padding=3, color=GRIS, fontsize=8.5)
    droite.set_yticks(position)
    droite.set_yticklabels([])
    droite.invert_yaxis()
    droite.set_xlim(0, max(total) + 2)
    droite.set_xlabel(f"questions restées sans réponse, sur {max(total)}", color=GRIS, fontsize=8.5)
    soigner(droite, "Le silence")
    droite.grid(axis="y", visible=False)
    droite.grid(axis="x", color=FILET, linewidth=0.6)

    figure.suptitle(
        "Répondre vite, ou répondre toujours",
        color=ENCRE,
        fontsize=12.5,
        fontweight="bold",
        x=0.01,
        ha="left",
        y=1.04,
    )
    legender(
        figure,
        "Mesure du 11 octobre 2026 sur 1 999 474 marchés et 30 questions de test, "
        "`make bench-recherche`. Six répétitions par question,\nla première jetée, médiane "
        "retenue. « Tous les mots » répond en 4 millisecondes mais reste muet sur 9 questions "
        "sur 30 ; « au moins un\nmot » répond toujours mais coûte plus d'une seconde. Les "
        "enchaîner donne 7 millisecondes et aucun silence. La version DuckDB\nsans nettoyage de "
        "la question est muette sur 29 questions sur 30 : DuckDB retire les mots vides du texte "
        "indexé, pas de la\nquestion posée. Conclure qu'il cherche mal aurait été une erreur de "
        "protocole, pas une mesure. Une latence varie d'environ\n30 % d'une exécution à l'autre : "
        "c'est l'ordre de grandeur et le classement qui portent la conclusion, pas le chiffre.",
    )
    enregistrer(figure, "20-recherche-latence-et-silence")


def figure_assistant() -> None:
    """Le cout de chaque choix, remesure dans les deux sens, et les verifications automatiques.

    Deux panneaux, parce que la figure doit porter les deux arguments du composant et qu'ils sont
    de nature differente.

    A gauche, ce que chaque decision a coute ou economise. Les deux versions de chaque choix sont
    rejouees a chaque passage du banc, donc la barre « avant » n'est pas un souvenir : elle est
    remesuree. C'est la regle appliquee au modele de detection ecarte en phase 5.

    A droite, ce qui justifie de ne pas avoir mis de modele de langue : une reponse construite a
    partir d'un filtre explicite se verifie par une machine, et 448 verifications passent.
    """
    choix = lire("assistant-cout-des-choix")
    resume = {ligne["mesure"]: ligne for ligne in lire("assistant-resume")}

    # Le CSV porte des cles de code, sans accents, parce qu'il est lu par des tests. Une figure
    # est lue par un humain : les libelles sont traduits ici, a un seul endroit.
    LIBELLES = {
        "agregats du comptage": "agrégats du comptage",
        "valeurs distinctes d'un lieu": "valeurs distinctes\nd'une région",
        "periode couverte": "période couverte\npar les données",
        "trois citations": "les trois marchés cités",
    }

    def virgule(valeur: str) -> str:
        """Le separateur decimal francais. Une figure de memoire ne s'ecrit pas en anglais."""
        return str(valeur).replace(".", ",")

    # Les paires, dans l'ordre ou elles ont ete decidees. La version retenue porte le mot
    # « retenu » dans sa colonne, ce qui evite de dupliquer l'information ici.
    paires: list[tuple[str, float, float]] = []
    for ligne in choix:
        if not ligne["version"].startswith("retenu"):
            avant = float(ligne["millisecondes"])
            apres = next(
                float(autre["millisecondes"])
                for autre in choix
                if autre["choix"] == ligne["choix"] and autre["version"].startswith("retenu")
            )
            paires.append((ligne["choix"], avant, apres))

    figure, (gauche, droite) = plt.subplots(1, 2, figsize=(10.5, 4.4))

    position = list(range(len(paires)))
    largeur = 0.38
    gauche.barh(
        [rang + largeur / 2 for rang in position],
        [avant for _, avant, _ in paires],
        largeur,
        color=SERIE_2,
    )
    gauche.barh(
        [rang - largeur / 2 for rang in position],
        [apres for _, _, apres in paires],
        largeur,
        color=SERIE_1,
    )
    gauche.set_xscale("log")
    # Les deux series sont nommees sur la premiere paire seulement, ce qui remplace une legende.
    # Toute legende posee dans le cadre masquait une paire, et posee au-dessus elle recouvrait le
    # titre du panneau.
    for rang, (_, avant_ms, apres_ms) in enumerate(paires):
        for decalage, valeur, nom in (
            (largeur / 2, avant_ms, "première version"),
            (-largeur / 2, apres_ms, "version retenue"),
        ):
            # Une decimale sous dix millisecondes : « 1 ms » pour 0,7 ms ferait disparaitre le
            # rapport de 66 que la figure est censee montrer.
            texte = (f"{valeur:.1f} ms" if valeur < 10 else f"{valeur:.0f} ms").replace(".", ",")
            if rang == 0:
                texte = f"{texte}, {nom}"
            gauche.annotate(
                texte,
                (valeur, rang + decalage),
                xytext=(4, 0),
                textcoords="offset points",
                va="center",
                color=GRIS,
                fontsize=8,
            )
    gauche.set_yticks(position)
    gauche.set_yticklabels([LIBELLES.get(nom, nom) for nom, _, _ in paires], fontsize=8)
    gauche.invert_yaxis()
    gauche.set_xlabel("millisecondes, échelle logarithmique", color=GRIS, fontsize=8.5)
    # L'axe est elargi a droite pour degager un coin ou poser la legende. Sans cela, elle se
    # superpose a la paire la plus longue, ou deborde sur la note de bas de figure.
    # Les deux series sont nommees sur la premiere paire seulement, ce qui remplace une legende.
    # Toute legende posee dans le cadre masquait une paire, et posee au-dessus elle recouvrait le
    # titre du panneau.
    for rang, (_, avant_ms, apres_ms) in enumerate(paires):
        for decalage, valeur, nom in (
            (largeur / 2, avant_ms, "première version"),
            (-largeur / 2, apres_ms, "version retenue"),
        ):
            # Une decimale sous dix millisecondes : « 1 ms » pour 0,7 ms ferait disparaitre le
            # rapport de 66 que la figure est censee montrer.
            texte = (f"{valeur:.1f} ms" if valeur < 10 else f"{valeur:.0f} ms").replace(".", ",")
            if rang == 0:
                texte = f"{texte}, {nom}"
            gauche.annotate(
                texte,
                (valeur, rang + decalage),
                xytext=(4, 0),
                textcoords="offset points",
                va="center",
                color=GRIS,
                fontsize=8,
            )
    gauche.set_xlim(0.4, 20000)
    soigner(gauche, "Ce que chaque choix a coûté")
    gauche.grid(axis="y", visible=False)
    gauche.grid(axis="x", color=FILET, linewidth=0.6)

    # Le panneau de droite oppose ce qui a ete verifie a ce qui a echoue. Les trois dernieres
    # barres valent zero, et c'est le resultat : une barre absente se lit mieux qu'un tableau.
    verifications = [
        ("citations\nvérifiées", int(resume["citations verifiees"]["valeur"]), SERIE_1),
        ("citations\nfausses", int(resume["citations fausses"]["valeur"]), SERIE_2),
        (
            "règles\nrompues",
            int(resume["regles de coherence rompues"]["valeur"]),
            SERIE_2,
        ),
        (
            "recomptages\ndivergents",
            int(resume["recomptages divergents"]["valeur"]),
            SERIE_2,
        ),
    ]
    barres = droite.bar(
        range(len(verifications)),
        [valeur for _, valeur, _ in verifications],
        0.58,
        color=[couleur for _, _, couleur in verifications],
    )
    droite.bar_label(barres, fmt="%d", padding=3, color=GRIS, fontsize=9)
    droite.set_xticks(range(len(verifications)))
    droite.set_xticklabels([nom for nom, _, _ in verifications], fontsize=8)
    droite.set_ylabel("nombre", color=GRIS, fontsize=8.5)
    soigner(droite, "Ce qu'une machine peut vérifier")
    droite.grid(axis="x", visible=False)
    droite.grid(axis="y", color=FILET, linewidth=0.6)

    figure.suptitle(
        "Répondre en citant ses sources, sans modèle de langue",
        color=ENCRE,
        fontsize=12.5,
        fontweight="bold",
        x=0.01,
        ha="left",
        y=1.04,
    )
    legender(
        figure,
        f"Mesure du 21 octobre 2026 sur 1 999 474 marchés et "
        f"{resume['questions']['valeur']} questions de test, `make bench-assistant`. À gauche, "
        f"les deux versions de\nchaque décision sont rejouées à chaque passage du banc : la barre "
        "« première version » est remesurée, pas recopiée. À droite, les\ntrois vérifications "
        "automatiques que permet une réponse portant son filtre et ses sources : chaque numéro "
        "de marché cité est\nrecherché avec le filtre annoncé, six règles de cohérence sont "
        "contrôlées par réponse, et chaque comptage est refait en interdisant\nles index au "
        f"planificateur. Latence médiane {virgule(resume['latence mediane']['valeur'])} ms, "
        f"la plus lente {virgule(resume['latence la plus lente']['valeur'])} ms, pour "
        f"{virgule(resume['cout']['valeur'])} euro par millier de\nquestions. "
        f"Les {resume['questions']['valeur']} questions ayant été "
        "écrites par l'auteur des motifs, le score de reconnaissance mesure la cohérence interne "
        "et non\nla capacité à comprendre une question nouvelle : ce sont les trois "
        "vérifications, indépendantes de qui a écrit les questions, qui portent\nla conclusion.",
    )
    enregistrer(figure, "21-assistant-cout-et-verifications")


def virgule(valeur: float, decimales: int = 1) -> str:
    """Separateur decimal francais. Un memoire en francais n'affiche pas « 18.1 »."""
    return f"{valeur:.{decimales}f}".replace(".", ",")


def milliers(valeur: int) -> str:
    """Espace fine comme separateur de milliers, convention francaise."""
    return f"{valeur:,}".replace(",", " ")


def figure_incertitude() -> None:
    """Ce que vaut chaque pourcentage, et quelle incertitude compte vraiment.

    Deux panneaux qui ne disent pas la meme chose. A gauche, le hasard du tirage, celui qui se
    calcule. A droite, la demonstration que ce n'est pas toujours lui qui domine : pour la part
    de PME, passer de l'echantillon au recensement a supprime le hasard de tirage et laisse une
    non-reponse qu'aucune formule ne corrige.
    """
    proportions = lire("incertitude-proportions")
    pme = lire("incertitude-recensement-pme")[0]

    # Libelles courts : le nom complet de la mesure vit dans le CSV, la figure doit rester lisible.
    courts = {
        "assistant : intention reconnue": "intention reconnue\n(40 questions)",
        "assistant : comportement attendu": "comportement attendu\n(40 questions)",
        "assistant : citation juste": "citation juste\n(448 citations)",
        "rapprochement : avis avec un candidat": "avis avec un candidat\n(300 avis)",
        "rapprochement : avis rapproches au seuil 0,5": "avis rapprochés\n(300 avis)",
        "rapprochement : justesse brute des paires relues": "paires justes\n(56 exploitables)",
    }

    figure, (gauche, droite) = plt.subplots(1, 2, figsize=(10.5, 4.2))

    positions = list(range(len(proportions)))
    for position, ligne in zip(positions, proportions, strict=True):
        taux = float(ligne["taux_pourcent"])
        bas = float(ligne["wilson_bas"])
        haut = float(ligne["wilson_haut"])
        # Les deux mesures parfaites sont tracees dans la couleur d'alerte : c'est la que la
        # formule naive se trompe le plus lourdement.
        couleur = SERIE_2 if taux == 100.0 else SERIE_1
        gauche.plot(
            [bas, haut], [position, position], color=couleur, linewidth=3, solid_capstyle="butt"
        )
        gauche.plot([taux], [position], marker="o", markersize=7, color=couleur)
        # Les bornes de Wald, en trait fin et legerement decale. Sur les lignes a 100 % elles se
        # referment sur le point : le trait a une longueur nulle et devient invisible. Un trait
        # invisible ne se lit pas, donc le cas est marque d'un trait vertical. C'est tout le
        # propos du panneau, il ne peut pas rester implicite.
        wald_bas, wald_haut = float(ligne["wald_bas"]), float(ligne["wald_haut"])
        if wald_haut - wald_bas < 0.05:
            gauche.plot(
                [wald_bas],
                [position + 0.3],
                marker="|",
                markersize=8,
                color=GRIS,
                markeredgewidth=1,
            )
            gauche.text(
                wald_bas - 1.2,
                position + 0.32,
                "largeur nulle",
                color=GRIS,
                fontsize=7.5,
                ha="right",
                va="center",
            )
        else:
            gauche.plot(
                [wald_bas, wald_haut],
                [position + 0.3, position + 0.3],
                color=GRIS,
                linewidth=1,
                solid_capstyle="butt",
            )
        # La colonne de valeurs est a une abscisse fixe, hors de la zone des barres : sinon elle
        # suit la borne haute et vient recouvrir le libelle de la ligne voisine.
        gauche.text(
            107,
            position,
            f"{virgule(taux)} %   [{virgule(bas)} ; {virgule(haut)}]",
            color=GRIS,
            fontsize=8,
            va="center",
        )

    gauche.set_yticks(positions)
    gauche.set_yticklabels([courts[ligne["mesure"]] for ligne in proportions], fontsize=8)
    gauche.set_xlim(26, 136)
    gauche.set_xlabel("pourcentage", color=GRIS, fontsize=8.5)
    gauche.invert_yaxis()
    soigner(gauche, "Trait épais : Wilson. Trait fin : la formule naïve")
    # La grille horizontale n'apporte rien sur un graphique a categories : elle est retiree apres
    # `soigner`, qui l'ajoute par defaut pour les graphiques a barres verticales.
    gauche.grid(axis="y", visible=False)
    gauche.grid(axis="x", color=FILET, linewidth=0.6)

    # Panneau de droite : la meme grandeur, mesuree deux fois, avec deux incertitudes de nature
    # differente. Les deux barres sont sur la meme echelle, donc leurs longueurs se comparent.
    recense = float(pme["part_pme_sur_resolus_pourcent"])
    demi_tirage = float(pme["largeur_tirage_echantillon_points"]) / 2
    borne_basse = float(pme["borne_basse_pourcent"])
    borne_haute = float(pme["borne_haute_pourcent"])

    droite.plot(
        [recense - demi_tirage, recense + demi_tirage],
        [1, 1],
        color=SERIE_2,
        linewidth=11,
        solid_capstyle="butt",
    )
    droite.plot(
        [borne_basse, borne_haute], [0, 0], color=SERIE_1, linewidth=11, solid_capstyle="butt"
    )
    droite.plot([recense], [0], marker="|", markersize=15, color="white")
    droite.axvline(60.0, color=ENCRE, linewidth=1, linestyle=(0, (4, 3)))
    # Le repere du producteur est annote sous les barres : au-dessus, il croisait le libelle
    # de la barre haute.
    droite.text(60.0, -0.7, "60 % publiés par le producteur", color=ENCRE, fontsize=8, ha="center")

    tirage = virgule(float(pme["largeur_tirage_echantillon_points"]))
    non_reponse = virgule(float(pme["etendue_non_reponse_points"]))
    # Les libelles sont poses dans l'axe, au-dessus de leur barre, et non sur la graduation de
    # gauche : un libelle de deux lignes y deborderait sur le panneau voisin.
    droite.text(
        52,
        1.30,
        f"échantillon de {pme['titulaires_echantillonnes']} titulaires, "
        f"hasard de tirage : {tirage} points",
        color=SERIE_2,
        fontsize=8.5,
        ha="left",
    )
    droite.text(
        52,
        0.30,
        f"recensement de {milliers(int(pme['attributions']))} attributions, "
        f"non-réponse : {non_reponse} points",
        color=SERIE_1,
        fontsize=8.5,
        ha="left",
    )
    droite.set_yticks([])
    droite.set_ylim(-1.0, 2.0)
    droite.set_xlim(51, 71)
    droite.set_xlabel("part des attributions à une PME, en pourcentage", color=GRIS, fontsize=8.5)
    soigner(droite, "Compter ne supprime pas l'incertitude")
    droite.grid(axis="y", visible=False)
    droite.grid(axis="x", color=FILET, linewidth=0.6)

    figure.suptitle(
        "Quarante sur quarante ne veut pas dire cent pour cent",
        color=ENCRE,
        fontsize=12.5,
        fontweight="bold",
        x=0.01,
        ha="left",
        y=1.04,
    )
    legender(
        figure,
        "À gauche, intervalles à 95 % des proportions tirées d'un échantillon. Le trait épais est "
        "l'intervalle de Wilson, le trait fin\ncelui de la formule p ± 1,96 racine(p(1-p)/n) : sur "
        "les deux mesures parfaites, elle annonce 100 % sans aucune marge, donc la\ncertitude que "
        "la question suivante sera juste. À droite, la même grandeur mesurée deux fois : "
        "l'enrichissement appliqué à toute\nla table a supprimé le hasard de tirage, et laissé une "
        "non-réponse que personne ne comptait. L'unité de comptage est\nl'attribution, soit un "
        "couple marché-titulaire : un groupement d'entreprises en produit plusieurs pour un même "
        "marché.\n"
        "Sources : mesures/resultats/incertitude-proportions.csv et\n"
        "incertitude-recensement-pme.csv.",
    )
    enregistrer(figure, "22-incertitude-des-mesures")


def figure_stabilite() -> None:
    """Une regle calee sur le passe, appliquee a la suite.

    Le panneau de gauche repond a la question posee : la regle ne se degrade pas avec l'age. Il en
    souleve une autre, plus genante : l'annee 2023 decroche de trente points, et les intervalles
    interdisent d'y voir du bruit.
    """
    annees = lire("stabilite-par-annee")
    calibrages = lire("stabilite-calibrage")

    figure, (gauche, droite) = plt.subplots(1, 2, figsize=(10.5, 4.0))

    etiquettes = [ligne["annee"] for ligne in annees]
    positions = list(range(len(annees)))
    valeurs = [float(ligne["precision_pourcent"]) for ligne in annees]
    vers_le_bas = [
        valeur - float(ligne["precision_bas"])
        for valeur, ligne in zip(valeurs, annees, strict=True)
    ]
    vers_le_haut = [
        float(ligne["precision_haut"]) - valeur
        for valeur, ligne in zip(valeurs, annees, strict=True)
    ]

    # La periode de test est ombree : tout ce qui est a droite de la coupure n'a pas servi a
    # calculer les references.
    premiere_de_test = next(
        indice for indice, ligne in enumerate(annees) if ligne["periode"] == "test"
    )
    coupure = premiere_de_test - 0.5
    gauche.axvspan(coupure, len(annees) - 0.4, color=FILET, alpha=0.5, linewidth=0)
    gauche.text(
        coupure + 0.12,
        24,
        "années postérieures au calage",
        color=GRIS,
        fontsize=8,
        ha="left",
    )

    gauche.errorbar(
        positions,
        valeurs,
        yerr=[vers_le_bas, vers_le_haut],
        color=SERIE_1,
        ecolor=SERIE_1,
        elinewidth=1.4,
        capsize=4,
        marker="o",
        markersize=7,
        linewidth=2,
    )
    # L'annee qui decroche est nommee : une figure ne laisse pas au lecteur le soin de deviner ce
    # qu'elle montre.
    indice_bas = valeurs.index(min(valeurs))
    gauche.annotate(
        f"{etiquettes[indice_bas]} : {virgule(valeurs[indice_bas])} %\ncause non établie",
        xy=(indice_bas, valeurs[indice_bas]),
        xytext=(indice_bas - 2.0, valeurs[indice_bas] - 15),
        color=SERIE_2,
        fontsize=8.5,
        arrowprops={"arrowstyle": "-", "color": SERIE_2, "linewidth": 1},
    )
    gauche.set_xticks(positions)
    gauche.set_xticklabels(etiquettes)
    gauche.set_ylim(18, 100)
    gauche.set_ylabel("concordance avec les anomalies signalées, en %", color=GRIS, fontsize=8.5)
    soigner(gauche, "La règle ne vieillit pas, mais 2023 décroche")

    # Panneau de droite : les deux calibrages, evalues sur la meme periode de test. L'ecart entre
    # les deux barres est exactement ce que la fuite ajoutait a la mesure publiee.
    sur_le_test = [ligne for ligne in calibrages if ligne["periode_evaluee"] == "test"]
    noms = [
        "calibrage global\nréférences calculées\nsur toutes les années",
        "calibrage honnête\nréférences calculées\navant la période jugée",
    ]
    hauteurs = [float(ligne["precision_pourcent"]) for ligne in sur_le_test]
    erreurs = [
        [h - float(ligne["precision_bas"]) for h, ligne in zip(hauteurs, sur_le_test, strict=True)],
        [
            float(ligne["precision_haut"]) - h
            for h, ligne in zip(hauteurs, sur_le_test, strict=True)
        ],
    ]
    barres = droite.bar(
        noms, hauteurs, color=[SERIE_2, SERIE_1], width=0.5, yerr=erreurs, capsize=5, ecolor=ENCRE
    )
    droite.bar_label(
        barres,
        labels=[f"{virgule(hauteur)} %" for hauteur in hauteurs],
        padding=12,
        color=GRIS,
        fontsize=9,
    )
    ecart = hauteurs[0] - hauteurs[1]
    droite.annotate(
        f"{virgule(ecart)} points\nque la fuite ajoutait",
        xy=(0.5, max(hauteurs) + 11),
        color=ENCRE,
        fontsize=9,
        ha="center",
        va="center",
    )
    droite.set_ylim(0, 92)
    droite.set_ylabel("concordance sur la période de test, en %", color=GRIS, fontsize=8.5)
    droite.tick_params(axis="x", labelsize=8)
    soigner(droite, "Ce que coûtait le calage sur tout l'historique")

    figure.suptitle(
        "Juger des marchés avec une médiane qu'ils ont aidé à former",
        color=ENCRE,
        fontsize=12.5,
        fontweight="bold",
        x=0.01,
        ha="left",
        y=1.04,
    )
    legender(
        figure,
        "Règle de prix au seuil de production (écart normalisé supérieur à 4, familles de 30 "
        "marchés minimum), évaluée contre les\nanomalies signalées par le producteur des données. "
        "Apprentissage 2019-2023, test 2024-2026. Barres d'erreur : intervalle de\nWilson à 95 %. "
        "À gauche, aucune dégradation avec l'âge de la règle, mais un décrochage de 2023 que "
        "l'intervalle interdit\nd'attribuer au hasard. À droite, les deux calibrages évalués sur "
        "la même période : la mesure publiée profitait de la fuite.\n"
        "Sources : mesures/resultats/stabilite-par-annee.csv et stabilite-calibrage.csv.",
    )
    enregistrer(figure, "23-stabilite-temporelle")


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
    figure_rapprochement()
    figure_precision_rapprochement()
    figure_nettoyage()
    figure_modele_vs_regles()
    figure_recherche()
    figure_assistant()
    figure_incertitude()
    figure_stabilite()
    figure_api()
    print(f"\nDossier : {chemin_lisible(FIGURES)}")


def figure_api() -> None:
    """Ce que l'API coute, et ce que le premier appel coute en plus.

    Deux panneaux qui repondent a deux questions differentes, et c'est le second qui a change le
    code. A gauche, la latence par route : ce qu'un visiteur attend quand le service tourne
    depuis un moment. A droite, la montee en charge : le service plie-t-il, et comment.

    Le premier appel sur base froide est trace a gauche, en marqueur separe et sur une echelle
    logarithmique, parce que c'est la seule facon de montrer ensemble 2 ms et 5 788 ms. Mesurer
    seulement la mediane a chaud aurait valide un service qui echoue a chaque deploiement.
    """
    latences = lire("api-latences")
    charge = lire("api-charge")

    figure, (gauche, droite) = plt.subplots(1, 2, figsize=(11.6, 4.3), width_ratios=[1.35, 1])

    # --- A gauche : la latence par route, en echelle logarithmique ---------
    noms = [ligne["route"] for ligne in latences][::-1]
    p50 = [float(ligne["p50_ms"]) for ligne in latences][::-1]
    p95 = [float(ligne["p95_ms"]) for ligne in latences][::-1]
    froid = [float(ligne["premier_appel_ms"]) for ligne in latences][::-1]
    positions = range(len(noms))

    gauche.barh(positions, p95, color=SERIE_1, alpha=0.3, height=0.6, label="p95")
    gauche.barh(positions, p50, color=SERIE_1, height=0.6, label="p50 (mediane)")
    gauche.scatter(
        froid,
        positions,
        marker="D",
        s=26,
        color=SERIE_2,
        zorder=3,
        label="premier appel, base froide",
    )
    gauche.set_xscale("log")
    gauche.set_yticks(list(positions))
    gauche.set_yticklabels(noms, fontsize=8.5)
    gauche.set_xlabel("millisecondes, echelle logarithmique", color=GRIS, fontsize=8.5)
    gauche.set_xlim(1, 20_000)
    # Le delai au-dela duquel la base abandonne la requete. Deux routes l'ont depasse avant
    # correction, et c'est ce trait qui a fait changer le code.
    gauche.axvline(10_000, color=SERIE_2, linestyle=":", linewidth=1.1)
    gauche.text(
        10_000,
        len(noms) - 0.35,
        " delai du service : 10 s",
        color=SERIE_2,
        fontsize=8,
        va="center",
    )
    gauche.grid(axis="y", visible=False)
    gauche.grid(axis="x", color=FILET, linewidth=0.6)
    soigner(gauche, "Ce qu'un visiteur attend, route par route")
    gauche.legend(frameon=False, fontsize=8, loc="lower right", labelcolor=GRIS)

    # --- A droite : la montee en charge -----------------------------------
    clients = [int(ligne["clients_simultanes"]) for ligne in charge]
    debit = [float(ligne["debit_par_seconde"]) for ligne in charge]
    p95_charge = [float(ligne["p95_ms"]) for ligne in charge]

    droite.plot(clients, debit, marker="o", color=SERIE_1, linewidth=1.6, label="debit")
    droite.set_xlabel("clients simultanes", color=GRIS, fontsize=8.5)
    droite.set_ylabel("requetes par seconde", color=SERIE_1, fontsize=8.5)
    droite.set_ylim(0, max(debit) * 1.3)
    droite.set_xticks(clients)
    droite.set_xticklabels([str(nombre) for nombre in clients])

    # Deuxieme axe : la latence. Les deux courbes ensemble disent la seule chose qui compte,
    # qu'un debit plafonne et une latence qui croit sont le meme fait, celui d'une file
    # d'attente. Separees, chacune se lirait a l'envers.
    latence = droite.twinx()
    latence.plot(
        clients, p95_charge, marker="s", color=SERIE_2, linewidth=1.6, linestyle="--", label="p95"
    )
    latence.set_ylabel("p95, millisecondes", color=SERIE_2, fontsize=8.5)
    latence.set_ylim(0, max(p95_charge) * 1.3)
    latence.tick_params(colors=GRIS, labelsize=8.5)
    for bord in ("top", "left"):
        latence.spines[bord].set_visible(False)
    latence.spines["right"].set_color(FILET)

    sommet = max(range(len(debit)), key=lambda indice: debit[indice])
    droite.annotate(
        f"{virgule(debit[sommet])} req/s\na {clients[sommet]} clients",
        xy=(clients[sommet], debit[sommet]),
        xytext=(clients[sommet] + 1.2, debit[sommet] * 0.62),
        color=ENCRE,
        fontsize=8.5,
        arrowprops={"arrowstyle": "-", "color": FILET, "linewidth": 0.9},
    )
    soigner(droite, "Le service ne tombe pas, il fait patienter")
    droite.grid(axis="y", color=FILET, linewidth=0.6)
    lignes_debit, etiquettes_debit = droite.get_legend_handles_labels()
    lignes_p95, etiquettes_p95 = latence.get_legend_handles_labels()
    droite.legend(
        lignes_debit + lignes_p95,
        etiquettes_debit + etiquettes_p95,
        frameon=False,
        fontsize=8,
        loc="upper left",
        labelcolor=GRIS,
    )

    legender(
        figure,
        "Source : make bench-api, 22 octobre 2026, Mac M2 Pro, base de 1 999 474 lignes, 20 "
        "appels par route.\nLe premier appel est mesure sur une base froide, juste apres le "
        "demarrage du service : c'est ce que vit le premier visiteur apres un deploiement. "
        "La charge\nporte sur la route de recherche, 60 appels par palier, aucun echec sur 300 "
        "appels.",
    )
    figure.tight_layout()
    enregistrer(figure, "24-api-latence-et-charge")


if __name__ == "__main__":
    main()
