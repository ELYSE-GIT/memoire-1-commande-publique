-- Migration 001 : le montant total sans le surcompte des groupements.
--
-- La premiere migration du projet, et la raison vaut d'etre notee : jusqu'ici, chaque
-- changement de schema se faisait en modifiant `base/schema/` puis en rechargeant une base
-- vide, ce qui est legitime pendant la construction. Ce changement-la arrive sur une base
-- deja chargee de 1 999 474 lignes, dont le rechargement complet prend plus d'une heure. Les
-- fichiers de `schema/` sont tous ecrits en `create table if not exists`, donc les relancer
-- n'ajoute aucune colonne a une table existante : sans ce fichier, la seule facon d'obtenir la
-- nouvelle colonne serait de taper un `alter table` dans la console, ce que la regle de
-- `base/README.md` interdit.
--
-- A lancer par `make migrer`. Idempotent : relancable sans effet.
--
-- Ce que la colonne contient, et pourquoi elle existe : voir
-- `base/schema/008-table-statistiques.sql`, a cote de sa declaration. En resume, additionner
-- les montants ligne par ligne surcompte de 36,7 pour cent, parce qu'un marche attribue a un
-- groupement d'entreprises repete le montant du marche entier sur chacune de ses lignes.

alter table statistiques
    add column if not exists montant_total_marches numeric(20, 2);

-- La colonne est vide jusqu'au prochain `make indexer`, qui lance
-- `009-remplir-statistiques.sql`. Elle accepte donc null, et l'API comme le site savent lire
-- cette absence : ils affichent alors le total brut en disant qu'il surcompte, plutot qu'un
-- tiret ou un zero.
select
    case
        when montant_total_marches is null
            then 'colonne ajoutee, vide : lancer `make indexer` pour la remplir'
        else 'colonne deja remplie'
    end as etat
from statistiques;
