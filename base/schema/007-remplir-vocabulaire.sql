-- Remplir le vocabulaire. A lancer APRES le chargement, en meme temps que les index : c'est une
-- donnee derivee de la colonne `recherche`, donc fausse des que les marches changent.
--
-- `tablesample system (5)` tire environ 5 % des **pages** de la table, pas 5 % des lignes. C'est
-- ce qui le rend rapide : PostgreSQL saute des pages entieres au lieu de les lire toutes. Le
-- biais correspondant est reel et documente : des lignes voisines dans une page se ressemblent
-- souvent, parce qu'elles ont ete chargees ensemble. Pour ce que cette table sert a decider
-- (comparer une frequence a 0,05 % et a 12 %), ce biais est sans effet, et l'alternative
-- `bernoulli` lit toute la table pour un gain nul ici.
--
-- Mesure du 21 octobre 2026 : 8,0 s, 73 722 lexemes.

truncate table vocabulaire;

insert into vocabulaire (lexeme, marches, echantillon)
select mots.word,
       mots.ndoc,
       -- La taille reelle de l'echantillon, comptee et non supposee : `tablesample` ne rend pas
       -- exactement 5 %, et une frequence calculee sur un denominateur suppose serait fausse.
       (select count(*) from marches tablesample system (5))
from ts_stat('select recherche from marches tablesample system (5)') as mots;

analyze vocabulaire;

-- Preuve que la table sert a quelque chose : les deux parasites et deux vrais mots du domaine.
select lexeme,
       marches,
       round(100.0 * marches / echantillon, 2) as part_en_pourcent
from vocabulaire
where lexeme in ('a', 'le', 'voir', 'scolair', 'quel')
order by marches desc;
