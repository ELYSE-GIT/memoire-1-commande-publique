# mesures/reference

Les donnees de reference dont les mesures ont besoin et qui ne viennent pas du projet : des
tarifs publics, des taux de change, des nomenclatures. Elles sont versionnees, datees et
sourcees, parce qu'une mesure qui s'appuie sur un chiffre inverifiable ne vaut rien.

| Fichier | Contenu | Relevé le |
|---|---|---|
| `prix-cloud.csv` | les tarifs publics d'OVHcloud, AWS, Azure et Google Cloud utilises par `make bench-couts`, et le taux de change de la BCE | 2026-10-22 |

## `prix-cloud.csv`

Neuf colonnes : `fournisseur`, `service`, `reference`, `region`, `unite`, `prix`, `devise`,
`source`, `consulte_le`. Chaque ligne est reverifiable : l'adresse de la source y figure, et
c'est toujours celle du fournisseur lui-meme.

### Ce qui a le droit d'y entrer

**Uniquement des listes de prix officielles et lisibles par une machine.** Pas un comparateur,
pas un article de blog, pas une capture d'ecran. Un test le verifie en controlant le domaine de
chaque source.

| Fournisseur | Source utilisee | Nature |
|---|---|---|
| AWS | `pricing.us-east-1.amazonaws.com/offers/v1.0/aws/...` | liste de prix publique, CSV, par service et par region |
| Azure | `prices.azure.com/api/retail/prices` | interface de tarification au detail, JSON, sans compte |
| OVHcloud | `api.ovh.com/v1/order/catalog/public/vps` | catalogue public, JSON, en euros |
| Google Cloud | `cloud.google.com/sql/pricing` | page de tarification, tableaux lisibles dans la source |
| BCE | `api.frankfurter.dev` | taux de reference de la Banque centrale europeenne |

### Les trois precautions qui comptent

**La region.** Les tarifs varient fortement d'une region a l'autre chez le meme fournisseur. Les
relevés portent sur l'Europe : `eu-west-3` (Paris) pour AWS, `francecentral` pour Azure, la
France pour OVHcloud.

**La date.** Les tarifs du nuage changent plusieurs fois par an. Un test verifie que toutes les
lignes sont relevees le meme jour : melanger deux releves comparerait des prix qui n'ont jamais
coexiste.

**La devise.** AWS et Google Cloud publient en dollars, Azure et OVHcloud en euros. La
conversion se fait au taux de la BCE du jour du releve, qui figure dans le fichier comme une
ligne a part entiere, et non comme une constante cachee dans le code.

### Ce que ce fichier ne contient pas, et pourquoi

**Databricks, Snowflake et OpenAI.** Aucune des trois ne publie de tarif sous une forme
verifiable sans ouvrir un compte : leurs pages de tarification construisent leurs tableaux dans
le navigateur, et aucune n'expose de liste de prix publique comparable a celle d'AWS ou d'Azure.
Verifie le 22 octobre 2026. Le projet prefere ne publier aucun chiffre plutot qu'un chiffre
repris d'un tiers. Cette asymetrie est commentee dans la section 8.3.5 du memoire.

**Les remises.** Aucun engagement, aucune reservation, aucune remise de volume, aucun credit de
depart. Ce sont les tarifs qu'une petite structure paie reellement, et c'est le cas qui
interesse ce memoire. Les tarifs reserves sur un ou trois ans reduiraient la facture geree de
30 a 50 pour cent selon les fournisseurs, sans changer l'ordre de grandeur de la conclusion.

**La TVA.** Tous les montants sont hors taxes, des deux cotes de la comparaison.

## Mettre a jour les tarifs

Relancer les quatre relevés le meme jour, mettre a jour `consulte_le`, puis `make bench-couts` et
`make figures`. Les tests signaleront tout chiffre du memoire devenu faux. Les commandes exactes
sont dans l'en-tete de `mesures/couts.py`.
