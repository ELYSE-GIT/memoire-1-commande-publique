#!/usr/bin/env python3
"""Verifie qu'un notebook a bien ete execute, en entier et sans erreur.

Pourquoi ce fichier existe : `jupyter execute --inplace` **sort en code 0 meme quand une cellule
leve une exception**. Constate le 28 septembre 2026, apres qu'une erreur SQL a interrompu le
notebook 08 sans que rien ne le signale. Une cible Makefile ou une etape de CI qui se fierait au
seul code de sortie laisserait donc passer un notebook casse, et le depot afficherait une trace
d'erreur au lieu d'un resultat.

    Option envisagee           Avantage                    Limite                      Verdict
    code de sortie de          rien a ecrire               ne voit pas les erreurs     insuffisant
    `jupyter execute`                                      de cellule
    `nbconvert --execute`      echoue correctement         dependance de plus, non     ecarte
                                                           installee ici
    nbval                      compare aux sorties         dependance, et fige des     ecarte
                               attendues                   sorties qui evoluent
    **ce script**              aucune dependance, lit le   a lancer apres l'execution  **retenu**
                               fichier reellement produit

Le script verifie trois choses, dans l'ordre du moins couteux au plus couteux a corriger :

    1. chaque cellule de code est du Python valide, ce qui se voit sans rien executer ;
    2. aucune cellule ne porte de sortie d'erreur ;
    3. toutes les cellules ont bien ete jouees.

Le point 1 a ete ajoute apres avoir attendu quatre minutes d'execution pour decouvrir une
apostrophe mal echappee a la derniere cellule.

Usage : `python analyses/verifier_notebooks.py analyses/*.ipynb`
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

# Les lignes magiques de Jupyter (`%matplotlib inline`, `!pip ...`) ne sont pas du Python et
# feraient echouer l'analyse syntaxique : on les retire avant de lire la cellule.
PREFIXES_MAGIQUES = ("%", "!", "?")


def code_python(source: str) -> str:
    """Le contenu d'une cellule, debarrasse des lignes magiques propres a Jupyter."""
    return "\n".join(
        ligne for ligne in source.splitlines() if not ligne.lstrip().startswith(PREFIXES_MAGIQUES)
    )


def verifier(chemin: Path) -> list[str]:
    """Renvoie la liste des problemes d'un notebook. Liste vide si tout va bien."""
    notebook = json.loads(chemin.read_text(encoding="utf-8"))
    cellules = [c for c in notebook["cells"] if c["cell_type"] == "code"]
    problemes = []

    for numero, cellule in enumerate(cellules, start=1):
        # 1. La syntaxe, qui se verifie sans executer quoi que ce soit.
        try:
            ast.parse(code_python("".join(cellule["source"])))
        except SyntaxError as erreur:
            problemes.append(f"cellule {numero} : syntaxe invalide : {erreur.msg}")

        # 2. Les erreurs enregistrees a l'execution.
        for sortie in cellule.get("outputs", []):
            if sortie.get("output_type") == "error":
                nom = sortie.get("ename", "erreur")
                message = str(sortie.get("evalue", ""))[:120]
                problemes.append(f"cellule {numero} : {nom} : {message}")

    # 3. Une cellule non executee porte un `execution_count` vide. Une seule suffit a dire que les
    # sorties enregistrees ne correspondent plus au code affiche a cote.
    non_executees = [n for n, c in enumerate(cellules, start=1) if c.get("execution_count") is None]
    if non_executees:
        liste = ", ".join(str(n) for n in non_executees[:10])
        suite = " ..." if len(non_executees) > 10 else ""
        problemes.append(f"{len(non_executees)} cellule(s) non executee(s) : {liste}{suite}")

    return problemes


def main(arguments: list[str]) -> int:
    if not arguments:
        print("usage : python analyses/verifier_notebooks.py <notebook.ipynb> ...")
        return 2

    en_defaut = 0
    for nom in arguments:
        problemes = verifier(Path(nom))
        if problemes:
            en_defaut += 1
            print(f"ECHEC  {nom}")
            for probleme in problemes:
                print(f"       {probleme}")
        else:
            print(f"ok     {nom}")

    if en_defaut:
        print(f"\n{en_defaut} notebook(s) a rejouer.")
    return 1 if en_defaut else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
