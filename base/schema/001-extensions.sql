-- Les extensions PostgreSQL utilisees par le projet.
--
-- Une extension est du code ajoute au moteur. On n'en active que ce qui sert, et chacune est
-- justifiee ici : une extension inutile est une surface d'attaque et une dependance de plus a
-- maintenir lors d'une montee de version.

-- unaccent retire les accents d'un texte. Indispensable pour la recherche en francais : sans
-- elle, chercher « marche » ne trouve pas « marché », et « cote d or » ne trouve pas
-- « Côte-d'Or ». Un utilisateur ne tape pas les accents dans une barre de recherche.
create extension if not exists unaccent;

-- pg_trgm decoupe un texte en groupes de trois caracteres. Deux usages prevus :
--   la tolerance aux fautes de frappe, qu'un index plein texte ne couvre pas ;
--   la recherche sur un nom d'acheteur partiel, ou la racinisation ne sert a rien.
-- Mesure a faire en phase 6 : combien de questions du jeu de test elle rattrape.
create extension if not exists pg_trgm;

-- pgvector ajoute un type de donnee pour les plongements lexicaux et les index de recherche par
-- similarite. Activee des maintenant pour que le schema soit complet, mais **aucune colonne
-- vectorielle n'est creee tant que la mesure n'a pas montre que la recherche par mots-cles ne
-- suffit pas**. C'est le principe de l'escalier : la marche la plus basse d'abord.
create extension if not exists vector;

-- Verification lisible a l'ecran, pour que `make base-init` montre ce qu'il a fait.
select extname as extension, extversion as version
from pg_extension
where extname in ('unaccent', 'pg_trgm', 'vector')
order by extname;
