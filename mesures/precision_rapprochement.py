"""Justesse du rapprochement, par seuil de similarite.

Le balayage de `rapprochement_boamp_decp.py` mesure **combien** d'avis sont rapproches selon le
seuil. Il ne dit rien de leur justesse. Or un seuil bas rapproche davantage, et rapproche davantage
a tort : sans cette seconde mesure, on choisirait le seuil qui maximise un chiffre sans valeur.

Ce script croise deux fichiers :

  - `mesures/verification/*-verdicts-rapprochement.csv` : soixante paires relues une par une, avec
    un verdict pose a la main. C'est la seule partie du projet qui ne soit pas automatisable, et
    elle est versionnee pour pouvoir etre recontrolee.
  - `mesures/resultats/*-rapprochement-balayage.csv` : le nombre d'avis rapproches par seuil.

Il en sort une table de decision : pour chaque seuil, la couverture, la justesse estimee, et le
nombre de rapprochements justes attendus.

**Precaution de calcul.** L'echantillon relu est stratifie : douze paires par tranche de
similarite, quelle que soit la frequence reelle de la tranche. Faire la moyenne des verdicts
donnerait donc un chiffre faux, puisque les tranches rares y pesreraient autant que les frequentes.
La justesse est donc ponderee par le nombre reel de rapprochements de chaque tranche, lu dans le
balayage. C'est exactement le redressement d'un echantillon stratifie.

Pourquoi un echantillon stratifie plutot qu'un tirage uniforme :

    Option              Avantage                        Limite                   Verdict
    Stratifie par       autant d'exemples la ou la      demande un redressement  retenu
    tranche             methode doute que la ou         pour revenir au reel
                        elle est sure
    Tirage uniforme     moyenne directement juste       presque que des cas      ecarte
                                                        faciles, on n'apprend
                                                        rien sur la frontiere
    Tout relire         verite complete                 des milliers de paires,  impossible
                                                        hors de portee

Lancement : `make bench-precision`.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

RACINE = Path(__file__).resolve().parent.parent
VERIFICATION = RACINE / "mesures" / "verification"
RESULTATS = RACINE / "mesures" / "resultats"

# La fenetre de reference pour la table de decision. Le balayage a montre qu'elle change peu le
# resultat : de 6 a 36 mois, le nombre d'avis avec candidats passe seulement de 137 a 147.
FENETRE_REFERENCE = 18

# Bornes des tranches relues, dans l'ordre. La derniere borne haute depasse 1 pour inclure les
# similarites egales a 1, qui existent : deux libelles strictement identiques.
TRANCHES = [(0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01)]


def dernier(dossier: Path, motif: str) -> Path:
    """Le fichier le plus recent correspondant au motif."""
    fichiers = sorted(dossier.glob(motif))
    if not fichiers:
        message = f"aucun fichier {motif} dans {dossier}"
        raise FileNotFoundError(message)
    return fichiers[-1]


def justesse_par_tranche() -> dict[str, dict[str, int | float]]:
    """Compte les verdicts poses a la main, tranche par tranche.

    Les paires marquees « doute » sont comptees a part et exclues du calcul de justesse : les
    inclure comme justes gonflerait le resultat, les inclure comme fausses le sous-estimerait.
    Leur nombre est publie pour que le lecteur juge.
    """
    lignes = list(
        csv.DictReader(dernier(VERIFICATION, "*-verdicts-rapprochement.csv").open(encoding="utf-8"))
    )
    par_tranche: dict[str, dict[str, int | float]] = {}
    for bas, haut in TRANCHES:
        nom = f"{bas} a {haut}"
        verdicts = [ligne["verdict_humain"] for ligne in lignes if ligne["tranche"] == nom]
        oui = verdicts.count("oui")
        non = verdicts.count("non")
        doute = verdicts.count("doute")
        tranches_sures = oui + non
        par_tranche[nom] = {
            "relues": len(verdicts),
            "justes": oui,
            "fausses": non,
            "doutes": doute,
            "justesse": round(oui / tranches_sures, 3) if tranches_sures else 0.0,
        }
    return par_tranche


def rapprochements_par_seuil() -> dict[float, int]:
    """Nombre d'avis rapproches par l'objet, pour chaque seuil, a la fenetre de reference."""
    lignes = list(
        csv.DictReader(dernier(RESULTATS, "*-rapprochement-balayage.csv").open(encoding="utf-8"))
    )
    return {
        float(ligne["seuil_objet"]): int(ligne["confiance_moyenne"])
        for ligne in lignes
        if int(ligne["fenetre_mois"]) == FENETRE_REFERENCE
    }


def table_de_decision() -> list[dict[str, Any]]:
    """Pour chaque seuil : couverture, justesse ponderee, et rapprochements justes attendus."""
    justesse = justesse_par_tranche()
    par_seuil = rapprochements_par_seuil()
    seuils = sorted(par_seuil)
    total_avis = 300  # taille de l'echantillon mesure, rappelee pour le calcul de couverture

    # Nombre de rapprochements dans chaque tranche : la difference entre deux seuils consecutifs.
    effectifs: dict[str, int] = {}
    for indice, (bas, haut) in enumerate(TRANCHES):
        au_dessus_de_bas = par_seuil.get(bas, 0)
        au_dessus_de_haut = par_seuil.get(haut, 0) if indice + 1 < len(TRANCHES) else 0
        effectifs[f"{bas} a {haut}"] = au_dessus_de_bas - au_dessus_de_haut

    table: list[dict[str, Any]] = []
    for seuil in seuils:
        tranches_retenues = [
            nom for (bas, haut), nom in zip(TRANCHES, effectifs, strict=True) if bas >= seuil
        ]
        total = sum(effectifs[nom] for nom in tranches_retenues)
        if total == 0:
            continue
        # Justesse ponderee : chaque tranche pese son effectif reel, pas son poids dans
        # l'echantillon relu.
        ponderee = (
            sum(effectifs[nom] * float(justesse[nom]["justesse"]) for nom in tranches_retenues)
            / total
        )
        table.append(
            {
                "seuil_objet": seuil,
                "rapproches_par_objet": total,
                "couverture_pourcent": round(100 * total / total_avis, 1),
                "justesse_estimee_pourcent": round(100 * ponderee, 1),
                "rapprochements_justes_attendus": round(total * ponderee, 1),
            }
        )
    return table


def main() -> None:
    justesse = justesse_par_tranche()
    print("Justesse relue a la main, par tranche de similarite :")
    for nom, valeurs in justesse.items():
        print(
            f"  {nom:<12} {valeurs['relues']:>2} paires relues, "
            f"{valeurs['justes']:>2} justes, {valeurs['fausses']:>2} fausses, "
            f"{valeurs['doutes']:>2} doutes   justesse {100 * float(valeurs['justesse']):>5.1f} %"
        )

    table = table_de_decision()
    print("\nTable de decision, fenetre de 18 mois :")
    print("  seuil   rapproches   couverture   justesse   justes attendus")
    for ligne in table:
        print(
            f"  {ligne['seuil_objet']:>5}   {ligne['rapproches_par_objet']:>10}   "
            f"{ligne['couverture_pourcent']:>9} %   {ligne['justesse_estimee_pourcent']:>7} %   "
            f"{ligne['rapprochements_justes_attendus']:>15}"
        )

    RESULTATS.mkdir(parents=True, exist_ok=True)
    chemin = RESULTATS / "rapprochement-precision.csv"
    with chemin.open("w", newline="", encoding="utf-8") as sortie:
        auteur = csv.DictWriter(sortie, fieldnames=list(table[0].keys()), lineterminator="\n")
        auteur.writeheader()
        auteur.writerows(table)
    print(f"\nEcrit : {chemin.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
