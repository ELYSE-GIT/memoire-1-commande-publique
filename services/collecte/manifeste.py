"""Tracabilite de la collecte : qui a telecharge quoi, quand, et quel etait le contenu exact.

Le probleme que ce module resout : les sources du projet sont republiees tous les jours. Une
mesure faite aujourd'hui ne peut donc pas etre refaite demain a l'identique, sauf a savoir
precisement ce qui a ete telecharge. Sans cette trace, un chiffre du memoire devient
invoerifiable des le lendemain.

La donnee brute, elle, n'est pas versionnee : 236 Mo par instantane, republies quotidiennement,
n'ont rien a faire dans un depot git. Le manifeste, qui pese quelques kilooctets, l'est.

    Ce qu'on garde           Taille        Versionne   Pourquoi
    la donnee brute          236 Mo/jour   non         lourde, remplacable, retelechargeable
    le manifeste             quelques Ko   oui         c'est la preuve de ce qui a ete mesure
    les agregats mesures     quelques Ko   oui         ce sont les chiffres du memoire

L'empreinte SHA-256 repond a une question precise : le fichier analyse est-il exactement celui que
la source a publie ce jour-la. Deux fichiers differents donnent deux empreintes differentes, et la
verification ne demande pas de conserver l'original.

Pourquoi SHA-256 plutot qu'autre chose :

    Option      Avantage                        Limite                      Verdict
    SHA-256     standard, disponible partout,   quelques secondes sur       retenu
                aucune collision connue         236 Mo
    MD5         plus rapide                     collisions demontrees,      ecarte
                                                a eviter meme hors securite
    Taille      instantane                      deux fichiers differents    insuffisant seul
    du fichier                                  peuvent faire la meme taille
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
BRONZE = RACINE / "donnees" / "bronze"
MANIFESTES = RACINE / "donnees" / "manifestes"

# Lecture par blocs : un fichier de 236 Mo charge d'un coup tiendrait en memoire sur ce Mac, mais
# pas sur le VPS, et la collecte doit tourner sur les deux.
TAILLE_BLOC = 1024 * 1024


@dataclass(frozen=True)
class Entree:
    """Une collecte : ce qui a ete recupere, d'ou, quand, et sous quelle forme."""

    source: str
    adresse: str
    fichier: str
    date_collecte: str
    taille_octets: int
    empreinte_sha256: str
    lignes: int | None = None
    commentaire: str = ""

    @property
    def taille_mo(self) -> float:
        """Taille en megaoctets, arrondie, pour l'affichage et le memoire."""
        return round(self.taille_octets / 1e6, 1)


def empreinte(chemin: Path) -> str:
    """Calcule l'empreinte SHA-256 d'un fichier, par blocs."""
    calcul = hashlib.sha256()
    with chemin.open("rb") as fichier:
        while bloc := fichier.read(TAILLE_BLOC):
            calcul.update(bloc)
    return calcul.hexdigest()


def decrire(
    source: str, adresse: str, chemin: Path, lignes: int | None = None, commentaire: str = ""
) -> Entree:
    """Constitue l'entree de manifeste d'un fichier deja telecharge."""
    return Entree(
        source=source,
        adresse=adresse,
        fichier=str(chemin.relative_to(RACINE)),
        date_collecte=datetime.now(UTC).isoformat(timespec="seconds"),
        taille_octets=chemin.stat().st_size,
        empreinte_sha256=empreinte(chemin),
        lignes=lignes,
        commentaire=commentaire,
    )


def enregistrer(entree: Entree) -> Path:
    """Ecrit l'entree dans le manifeste du jour, et renvoie son chemin.

    Un manifeste par jour plutot qu'un fichier unique qui grossit : les differences restent
    lisibles dans git, et deux collectes du meme jour se retrouvent cote a cote.
    """
    MANIFESTES.mkdir(parents=True, exist_ok=True)
    jour = entree.date_collecte[:10]
    chemin = MANIFESTES / f"{jour}.json"

    entrees: list[dict[str, object]] = []
    if chemin.exists():
        entrees = json.loads(chemin.read_text(encoding="utf-8"))

    # Une nouvelle collecte de la meme source le meme jour remplace la precedente : c'est ce qui
    # rend l'operation idempotente. Relancer une collecte interrompue ne laisse pas deux traces
    # contradictoires du meme evenement.
    entrees = [e for e in entrees if e.get("source") != entree.source]
    entrees.append(asdict(entree))
    entrees.sort(key=lambda e: str(e["source"]))

    chemin.write_text(json.dumps(entrees, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return chemin


def verifier(entree: Entree) -> bool:
    """Le fichier decrit par cette entree est-il toujours celui qui a ete collecte ?

    Sert a repondre en soutenance a la question « comment savez-vous que ce chiffre porte bien
    sur ce fichier-la ».
    """
    chemin = RACINE / entree.fichier
    if not chemin.exists():
        return False
    return empreinte(chemin) == entree.empreinte_sha256


def dernier_manifeste() -> list[Entree]:
    """Les entrees du manifeste le plus recent, ou une liste vide s'il n'y en a aucun."""
    if not MANIFESTES.exists():
        return []
    fichiers = sorted(MANIFESTES.glob("*.json"))
    if not fichiers:
        return []
    return [Entree(**e) for e in json.loads(fichiers[-1].read_text(encoding="utf-8"))]
