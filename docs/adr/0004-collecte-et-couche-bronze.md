# ADR 0004. La collecte et la couche bronze

- Date : 2026-09-28
- Statut : accepte
- Phase : 3, collecte et stockage

## Contexte

Jusqu'ici, les donnees etaient telechargees a la main, par une commande `curl` dans un Makefile.
Cela suffisait pour explorer. Cela ne suffit plus, pour trois raisons mesurees pendant la phase 2 :

1. **Les sources changent tous les jours.** Le jeu DECP est republie chaque matin. Une mesure faite
   le 20 septembre ne peut pas etre refaite le 21 a l'identique, sauf a savoir precisement ce qui
   avait ete telecharge.
2. **Les sources tombent.** Trois interruptions reseau ont ete rencontrees pendant l'exploration.
   Sans reprise, une collecte de plusieurs minutes echoue entierement sur un incident d'une seconde.
3. **Les API publiques imposent des limites.** L'API Recherche d'entreprises annonce sept appels
   par seconde ; l'enrichissement complet demande onze heures d'appels.

## Decision

**Un service de collecte dedie, qui depose la donnee brute dans une couche bronze horodatee, et
ecrit un manifeste versionne.**

Quatre proprietes sont tenues, et chacune est testee :

| Propriete | Ce qu'elle garantit | Comment |
|---|---|---|
| **Tracabilite** | on sait exactement ce qui a ete mesure | manifeste avec adresse, date, taille et empreinte SHA-256 |
| **Idempotence** | relancer une collecte interrompue ne casse rien | fichier temporaire renomme a la fin, entree du manifeste remplacee et non ajoutee |
| **Rejouabilite** | corriger une regle ne demande pas de retelecharger | la donnee brute est conservee telle quelle, horodatee |
| **Menagement des sources** | on ne degrade pas un service public | six appels par seconde, reprise avec attente croissante |

**Ce qui est versionne, et ce qui ne l'est pas**

| Element | Taille | Versionne | Pourquoi |
|---|---|---|---|
| Donnee brute | 248,5 Mo par instantane | non | lourde, republiee quotidiennement, retelechargeable |
| Manifeste | quelques kilooctets | **oui** | c'est la preuve de ce qui a ete mesure |
| Agregats mesures | quelques kilooctets | **oui** | ce sont les chiffres du memoire |

Le manifeste est la piece qui rend une mesure verifiable par un tiers. Il repond a la question
« comment savez-vous que ce chiffre porte bien sur ce fichier-la », qui sera posee en soutenance.

## Alternatives examinees

### Faut-il un orchestrateur maintenant ?

| Option | Pour | Contre | Verdict |
|---|---|---|---|
| **Module Python avec sous-commandes** | aucune dependance, se lance partout, testable sans reseau | pas de planification ni de suivi d'execution | **retenu pour l'instant** |
| Dagster | interface de suivi, dependances entre etapes, reprise fine | un service a faire tourner, une dependance lourde, pour trois sources sans dependances entre elles | a reprendre en phase 4, quand dbt ajoutera des dependances |
| Airflow | la reference historique, tres repandu | encore plus lourd, concu pour des dizaines de flux | non |
| Simple planificateur systeme (cron) | present partout, zero dependance | aucune trace de ce qui a tourne, aucune reprise | retenu pour le declenchement sur le VPS |

**Le raisonnement** : un orchestrateur resout un probleme de dependances entre etapes. Aujourd'hui,
les trois sources sont independantes et se collectent en une commande chacune. Introduire Dagster
maintenant ajouterait un service a maintenir pour un besoin qui n'existe pas encore. La decision
sera reprise en phase 4, quand les transformations dbt creeront de vraies dependances, et elle sera
alors motivee par une mesure.

C'est le principe de l'escalier applique a l'outillage : on ne monte que quand la mesure le
justifie.

### Quelle bibliotheque pour les appels reseau

| Option | Pour | Contre | Verdict |
|---|---|---|---|
| **`urllib`, bibliotheque standard** | aucune dependance, presente meme sur un VPS minimal | code plus verbeux, ni reprise ni session incluses | **retenu** |
| `requests` | la plus connue, API agreable | synchrone uniquement, projet en maintenance douce | non |
| `httpx` | meme API, plus l'asynchrone et des delais fins | une dependance de plus pour un gain non mesure | a reconsiderer si la collecte devient parallele |

La reprise sur erreur et la limitation de debit tiennent en une trentaine de lignes, ecrites et
commentees. Les prendre d'une bibliotheque tierce economiserait ces lignes mais ajouterait une
dependance a surveiller, pour un comportement qu'il faut de toute facon comprendre et savoir
expliquer devant un jury.

### Quel format pour les avis du BOAMP

| Option | Pour | Contre | Verdict |
|---|---|---|---|
| **JSON Lines, un avis par ligne** | se lit en flux, se concatene sans retraitement, lu directement par DuckDB | un peu plus volumineux qu'un format binaire | **retenu** |
| JSON unique avec un tableau | un seul objet, familier | il faut tout charger en memoire pour lire le premier avis | non |
| Parquet | compact, types conserves | impose une conversion des la collecte, donc une transformation dans la couche bronze | non, la couche bronze ne transforme rien |

## Consequences

**Positives**

- Chaque chiffre du memoire peut etre rattache a un fichier precis, verifiable par son empreinte.
- Une collecte interrompue se relance sans precaution particuliere.
- La chaine peut etre rejouee apres correction d'une regle, sans dependre de ce que les sources
  publient aujourd'hui.
- Les tests de la collecte tournent sans reseau : ils verifient le comportement du code, pas la
  disponibilite d'une API publique.

**Negatives et limites**

- **Un instantane par collecte occupe 248,5 Mo.** Collecter tous les jours pendant un mois
  demanderait 7,5 Go. Une purge manuelle sera necessaire, et `make clean-all` la couvre.
- La collecte du BOAMP est bornee a deux mille avis par execution : l'API refuse de depasser dix
  mille enregistrements par requete. La collecte complete se fera par tranches de dates, ce qui
  reste a ecrire.
- Aucune planification automatique pour l'instant. Sur le VPS, ce sera un declenchement par cron,
  decide en phase 9.

## A mesurer ensuite

1. La duree d'une collecte complete des trois sources, et son empreinte reseau.
2. Le gain apporte par une collecte incrementale du BOAMP, quand elle sera ecrite.
3. Le moment ou les dependances entre etapes justifient un orchestrateur, avec le critere qui
   declenchera la decision.
