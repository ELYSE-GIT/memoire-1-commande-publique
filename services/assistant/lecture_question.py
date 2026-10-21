"""Lire une question en francais et en extraire ce qu'une requete SQL peut utiliser.

Ce fichier ne parle jamais a la base. Il recoit des lexiques et rend une question analysee, ce
qui le rend testable sans conteneur : `tests/test_assistant.py` lui donne trois regions et
quatre mots de vocabulaire.

=== Le principe de l'escalier, applique a la comprehension ===================

Le projet ne monte d'une marche que si la mesure le justifie. Pour comprendre une question, les
marches sont :

    1. motifs et lexiques      ce fichier
    2. classifieur entraine    un modele qui apprend l'intention sur des questions etiquetees
    3. modele de langue        on lui donne le schema et il ecrit le SQL

On reste sur la premiere tant qu'elle repond. Ce qui la ferait quitter est enonce dans l'ADR
0009 : une intention sur cinq mal reconnue sur un jeu de questions reelles.

=== Pourquoi l'intention consomme ses mots ==================================

C'est la lecon de la premiere tentative, du 21 octobre 2026. Les sept questions d'essai
renvoyaient zero resultat parce que les mots de la question partaient dans la requete plein
texte : « combien de marches de voirie » cherchait des marches contenant le mot « combien ».

Premiere correction essayee : filtrer par frequence dans l'index. Elle rattrape deux questions
sur sept. Les cinq autres echouent sur « quel », « meilleur », « signales », « achete », qui
sont des mots assez rares dans les marches pour passer le filtre, et assez courants dans une
question pour la detruire.

La vraie correction est structurelle : **le motif qui reconnait une intention retire du texte
les mots qui l'ont declenchee**. « qui a remporte » ne designe pas un contenu, il designe une
operation sur les donnees. Le filtre par frequence reste, mais a sa vraie place : un garde-fou
pour les fautes de frappe et pour les mots vides que la configuration laisse passer.

    Option envisagee            Avantage                   Limite                      Verdict
    liste de mots de question   simple a lire              une liste de plus a tenir ;  ecarte
    ecrite a la main                                       muette sur les tournures
    tout confier au filtre      une seule mecanique        mesure : 2 questions sur 7   ecarte
    par frequence                                          seulement
    **motifs qui consomment**   le mot sert deux fois :    il faut ecrire les motifs ;   **retenu**
    **+ filtre en garde-fou**   il donne l'intention et    une tournure non prevue
                                quitte le texte            retombe sur la recherche

A quelle echelle la reponse changerait : au-dela d'une vingtaine d'intentions, ou si les
questions reelles s'eloignent beaucoup de ces tournures, un classifieur entraine sur les
questions reellement posees devient le bon outil. C'est mesurable : voir `mesures/assistant.py`.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field

# Profondeur des listes rendues : dix titulaires, dix acheteurs, dix extraits. C'est ce qu'une
# page affiche, et ce qu'un humain relit sans se perdre.
PROFONDEUR = 10


def plier(texte: str) -> str:
    """Minuscules, accents retires, ponctuation remplacee par des espaces.

    Le meme pliage que celui de la configuration `public.francais`, pour que les motifs
    s'ecrivent une seule fois, sans accents, et reconnaissent les deux orthographes.
    """
    sans_accent = unicodedata.normalize("NFKD", texte.lower())
    sans_accent = "".join(c for c in sans_accent if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sans_accent).split())


# === Les intentions ==========================================================
#
# Une intention, c'est une operation sur les donnees, pas un sujet. Six suffisent a couvrir les
# questions que le projet sait traiter ; la septieme ligne est le refus, et elle vient en premier.
#
# L'ordre compte. « combien coute la restauration scolaire » contient « combien » et « coute » :
# c'est une somme, pas un comptage. Les motifs les plus specifiques sont donc testes d'abord.
#
# Chaque motif est ecrit sur le texte plie : sans accents, sans ponctuation, en minuscules.

JUGEMENT = re.compile(
    r"\b(?:"
    r"meilleur\w*|pire\w*|bon marche|"
    r"recommand\w+|conseill\w+|devrai\w+|faut il|dois je|"
    r"fiable\w*|honnete\w*|serieu\w+|competent\w*|"
    r"corromp\w+|fraud\w+|coupable\w*|malhonnete\w*|triche\w*|vole\w*"
    r")\b"
)
"""Ce que les donnees ne portent pas : un jugement de valeur ou une accusation.

Deux refus differents sont confondus ici volontairement, parce que la reponse est la meme.

« quel est le meilleur fournisseur » demande une appreciation. Les donnees disent qui a obtenu
combien de marches, pas qui travaille bien : aucune mesure de la qualite d'execution n'existe
dans les donnees essentielles de la commande publique.

« qui a fraude » demande une qualification penale. Le projet signale des marches **atypiques**,
c'est-a-dire eloignes de leurs pairs, et l'ADR 0006 pose que 48 % des marches signales par la
regle de prix sont des faux positifs. Repondre a cette question serait diffamatoire. Le refus
n'est pas une limite technique, c'est le comportement correct.
"""

INTENTIONS: list[tuple[str, re.Pattern[str]]] = [
    # Qui a obtenu les marches. Les tournures sont nombreuses parce que c'est la question la
    # plus posee a un moteur de marches publics.
    (
        "titulaires",
        re.compile(
            r"\b(?:"
            r"qui (?:a |ont )?(?:remport\w+|obten\w+|gagn\w+|eu|decroch\w+)|"
            r"qui (?:fournit|fournissent|realise|realisent|livre|livrent|travaille)|"
            r"quel\w* (?:entrepris\w+|societ\w+|titulair\w+|fournisseur\w*|prestatair\w+|"
            r"attributair\w+)|"
            r"attribu\w+ a qui|titulair\w+"
            r")\b"
        ),
    ),
    # Qui achete. Utile pour l'autre moitie du marche : un fournisseur cherche ses clients.
    (
        "acheteurs",
        re.compile(
            r"\b(?:"
            r"qui achet\w+|quel\w* achet\w+|"
            r"quel\w* (?:collectivit\w+|commun\w+|mairi\w+|administrat\w+|departement\w*|"
            r"region\w*|etablissement\w*)"
            r")\b"
        ),
    ),
    # Les marches signales par les regles de detection de la phase 5.
    (
        "signales",
        re.compile(
            r"\b(?:signal\w+|atypiqu\w+|suspect\w*|anormal\w*|anormau\w*|alert\w+|"
            r"inhabituel\w*|etrange\w*)\b"
        ),
    ),
    # Une somme d'argent. Teste avant le comptage : « combien coute » est une somme.
    (
        "montant",
        re.compile(
            r"\b(?:montant\w*|total\w*|somme\w*|cout\w*|cout|budget\w*|depens\w+|"
            r"combien (?:coute|coutent|a coute|ca coute))\b"
        ),
    ),
    # Un comptage.
    ("comptage", re.compile(r"\b(?:combien|nombre d[eu]|quantite)\b")),
]

# Le superlatif. Toute intention de ce fichier rend deja un classement decroissant : « qui achete
# le plus de logiciels » et « qui achete des logiciels » appellent la meme requete. Les mots du
# superlatif ne decrivent donc aucun contenu, et partiraient sinon dans la requete plein texte,
# ou « plus » existe (« travaux plus-value ») et change le resultat.
SUPERLATIF = re.compile(r"\b(?:le plus|les plus|la plus|le moins|les moins|davantage|surtout)\b")

# Mots qui nomment le schema plutot qu'un contenu. Ils ne declenchent aucune intention mais ne
# doivent pas partir dans la requete plein texte.
#
# Pourquoi cette liste est courte et explicite, alors que le reste est mesure : ces mots ont une
# frequence parfaitement ordinaire dans les objets de marche. « marche » apparait dans 8,7 % des
# marches, souvent a bon droit (« amenagement du marche couvert »). Aucune statistique ne peut
# distinguer le mot qui nomme la table du mot qui decrit un hall de marche : seule la place dans
# la phrase le dirait, et ce serait monter une marche de l'escalier pour six mots.
MOTS_DE_SCHEMA = frozenset(
    {
        "marche",
        "marches",
        "contrat",
        "contrats",
        "lot",
        "lots",
        "appel",
        "appels",
        "offre",
        "offres",
        "donnee",
        "donnees",
        "liste",
        "lister",
        "montre",
        "montrer",
        "donne",
        "donner",
        "cherche",
        "chercher",
        "trouve",
        "trouver",
        "affiche",
        "afficher",
    }
)


@dataclass(frozen=True)
class Lexiques:
    """Ce que la base apprend a l'analyseur. Fourni par l'appelant, jamais lu ici.

    `frequence` rend la part des marches qui contiennent un mot, entre 0 et 1. Elle vient de la
    table `vocabulaire`, ou d'un dictionnaire dans les tests.
    """

    regions: dict[str, str]
    departements: dict[str, str]
    frequence: Callable[[str], float]
    annees: tuple[int, int]


@dataclass
class Question:
    """Une question analysee, prete a devenir du SQL."""

    posee: str
    intention: str
    texte: str = ""
    annee: int | None = None
    region: str | None = None
    departement: str | None = None
    refus: str | None = None
    # Chaque mot ecarte, avec la raison. Affiche a l'utilisateur et relu pendant les mesures :
    # un assistant qui jette un mot doit pouvoir dire lequel et pourquoi.
    ecartes: list[tuple[str, str]] = field(default_factory=list)
    # Les mots ecartes **dont le retrait change la question**, isoles des autres.
    #
    # Retirer « de » ou « marches » ne change pas ce qui est demande. Retirer un mot que
    # l'utilisateur a choisi pour decrire ce qu'il cherche, parce qu'il est absent de l'index ou
    # trop rare, change la question posee.
    #
    # Le defaut que cette distinction corrige a ete trouve le 21 octobre 2026 en relisant les
    # resultats du banc, sur la question A40 du jeu : « combien de marches de dsfgdsfg en 2023 ».
    # Le mot inconnu partait en silence, l'annee restait, et l'assistant repondait « 272 057
    # marches notifies en 2023 ». Une reponse juste a une autre question est une reponse fausse,
    # et c'est la forme d'erreur la plus dangereuse pour cet outil : elle est credible.
    perdus: list[str] = field(default_factory=list)


# Valeur rendue par `Lexiques.frequence` pour un mot que PostgreSQL considere comme vide.
#
# Pourquoi une valeur sentinelle plutot que zero : un mot vide et un mot absent de l'index
# meritent deux messages differents. « de » n'est pas une faute de frappe, et dire a
# l'utilisateur que « de » a ete ecarte parce qu'il est « trop frequent (100 %) » est faux : il a
# ete ecarte parce que PostgreSQL ne l'indexe pas. Premiere version du 21 octobre, corrigee en
# lisant les raisons affichees, qui etaient toutes justes sauf celle-la.
MOT_VIDE = -1.0

# Bornes du filtre par frequence. Reglees par la mesure, pas choisies : voir le notebook
# `analyses/09-assistant-reponses-sourcees.ipynb`, section 5, qui trace la precision du filtre
# en fonction des deux seuils sur le jeu de questions.
#
# Le plancher ecarte ce qui est trop rare pour etre du vocabulaire du domaine : une faute de
# frappe, ou un mot de question non prevu par les motifs.
PLANCHER = 0.0005
# Le plafond ecarte ce qui est trop frequent pour discriminer. Il rattrape « à » et « les », que
# la configuration insensible aux accents laisse passer (mesure dans `006-vocabulaire.sql`).
PLAFOND = 0.12


def lire(question: str, lexiques: Lexiques) -> Question:
    """Analyser une question. Ne touche pas la base.

    L'ordre des etapes est le fond du sujet : chaque etape retire du texte ce qu'elle a compris,
    et ne laisse a la suivante que ce qu'elle n'a pas su interpreter. Ce qui reste a la fin est,
    par construction, du vocabulaire de marche.
    """
    plie = plier(question)

    # 1. Le refus d'abord. Une question qui demande un jugement n'est pas une question mal
    #    posee : c'est une question a laquelle ces donnees ne repondent pas.
    if JUGEMENT.search(plie):
        return Question(
            posee=question,
            intention="refus",
            refus=(
                "Cette question demande une appreciation ou une accusation. Les donnees "
                "essentielles de la commande publique disent qui a obtenu quel marche pour quel "
                "montant ; elles ne disent pas qui travaille bien, ni qui a mal agi. Un marche "
                "signale est un marche eloigne de ses pairs, et 48 % des signalements de prix "
                "sont des faux positifs : ce n'est pas une preuve."
            ),
        )

    # 2. L'intention, qui retire **toutes** les occurrences de ses mots declencheurs.
    #
    #    `re.sub` et non `search` : c'est la correction du 21 octobre, apres mesure. Avec
    #    `search`, « quel montant total pour la restauration scolaire » retirait « montant » et
    #    laissait « total » partir dans la requete plein texte, qui cherchait alors des marches
    #    contenant le mot « total » : zero resultat. Un motif qui reconnait une intention doit
    #    emporter tout ce qui l'exprime.
    intention = "extraits"
    for nom, motif in INTENTIONS:
        if motif.search(plie):
            intention = nom
            plie = " ".join(motif.sub(" ", plie).split())
            break

    plie = " ".join(SUPERLATIF.sub(" ", plie).split())

    analysee = Question(posee=question, intention=intention)

    # 3. L'annee.
    #
    #    Le motif a d'abord ete `20\d{2}`, ce qui semblait suffire sur un domaine dont les
    #    donnees commencent en 2015. Un test l'a contredit : « combien de marches de voirie en
    #    1998 » n'etait alors pas lu comme une annee du tout. Le nombre partait dans le texte, en
    #    etait ecarte parce qu'absent de l'index, et l'assistant repondait sur la voirie en
    #    taisant qu'il avait ignore la date. Le refus prevu pour 2030 ne se declenchait pas pour
    #    1998, alors que les deux sont hors periode.
    #
    #    Le motif accepte donc quatre chiffres, et la **plage** decide. Les bornes 1990 et 2100
    #    ne sont pas decoratives : « fourniture de 1500 repas » contient quatre chiffres qui ne
    #    sont pas une annee, et doivent rester dans le texte cherche.
    annee_trouvee = re.search(r"\b(\d{4})\b", plie)
    if annee_trouvee and 1990 <= int(annee_trouvee.group(1)) <= 2100:
        annee = int(annee_trouvee.group(1))
        plie = plie.replace(annee_trouvee.group(1), " ")
        premiere, derniere = lexiques.annees
        if not premiere <= annee <= derniere:
            analysee.intention = "refus"
            analysee.refus = (
                f"L'annee {annee} n'est pas couverte. Les donnees chargees vont de {premiere} "
                f"a {derniere}."
            )
            return analysee
        analysee.annee = annee

    # 4. Le lieu. Les noms viennent de la base, donc ils ne peuvent pas etre inventes ni
    #    vieillir. Les plus longs d'abord : « Loire-Atlantique » avant « Loire », sinon le
    #    departement mangerait la moitie du nom de l'autre.
    for lexique, champ in ((lexiques.regions, "region"), (lexiques.departements, "departement")):
        for cle in sorted(lexique, key=len, reverse=True):
            if re.search(rf"\b{re.escape(cle)}\b", plie):
                setattr(analysee, champ, lexique[cle])
                plie = re.sub(rf"\b{re.escape(cle)}\b", " ", plie)
                break

    # 5. Le garde-fou par frequence, sur ce qui reste.
    gardes: list[str] = []
    for mot in plie.split():
        if mot in MOTS_DE_SCHEMA:
            analysee.ecartes.append((mot, "nomme les donnees, pas leur contenu"))
            continue
        if len(mot) < 2:
            analysee.ecartes.append((mot, "trop court"))
            continue
        part = lexiques.frequence(mot)
        if part == MOT_VIDE:
            analysee.ecartes.append((mot, "mot vide : PostgreSQL ne l'indexe pas"))
        elif part <= 0.0:
            analysee.ecartes.append((mot, "absent de l'index"))
            analysee.perdus.append(mot)
        elif part < PLANCHER:
            analysee.ecartes.append((mot, f"trop rare ({part:.3%} des marches)"))
            analysee.perdus.append(mot)
        elif part > PLAFOND:
            analysee.ecartes.append((mot, f"trop frequent ({part:.1%} des marches)"))
        else:
            gardes.append(mot)
    analysee.texte = " ".join(gardes)

    # 6. Deux refus, pour deux situations qu'il serait tentant de confondre.
    #
    #    « combien de marches en 2023 » ne laisse aucun texte, et c'est une question valable :
    #    tous les mots retires etaient des mots vides ou des mots de schema, et l'annee suffit a
    #    poser la question.
    #
    #    « combien de marches de dsfgdsfg en 2023 » ne laisse aucun texte non plus, mais pour une
    #    autre raison : le seul mot de contenu a ete perdu. Repondre serait repondre a une autre
    #    question. Le critere n'est donc pas « reste-t-il un filtre » mais « a-t-on perdu ce que
    #    l'utilisateur cherchait ».
    if not analysee.texte and analysee.perdus:
        analysee.intention = "refus"
        analysee.refus = (
            "Je ne sais pas repondre : "
            + ", ".join(f"« {mot} »" for mot in analysee.perdus)
            + (" n'apparait" if len(analysee.perdus) == 1 else " n'apparaissent")
            + " dans aucun marche charge, et c'est le seul terme de recherche de la question. "
            "Repondre sur les autres criteres seuls repondrait a une question differente."
        )
        return analysee

    if not analysee.texte and not (analysee.annee or analysee.region or analysee.departement):
        analysee.intention = "refus"
        analysee.refus = "Aucun critere exploitable dans cette question. " + (
            "Mots ecartes : " + ", ".join(f"{mot} ({raison})" for mot, raison in analysee.ecartes)
            if analysee.ecartes
            else "La question est vide."
        )

    return analysee
