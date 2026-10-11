-- La configuration plein texte francaise du projet.
--
-- PostgreSQL fournit une configuration `french` qui racinise les mots (« marches » et
-- « marche » deviennent la meme racine) et ecarte les mots vides (« de », « la », « pour »).
-- Elle ne retire pas les accents.
--
-- Pourquoi c'est un probleme ici : les objets de marche sont ecrits par des milliers d'agents
-- differents, avec ou sans accents, et un utilisateur tape rarement « rénovation » avec son
-- accent dans une barre de recherche. Sans traitement, « renovation » et « rénovation » sont
-- deux mots sans rapport.
--
--     Option envisagee           Avantage                    Limite                      Verdict
--     configuration `french`     fournie, rien a ecrire      les accents separent des    insuffisant
--     telle quelle                                           mots identiques
--     retirer les accents en     simple a comprendre         deux colonnes a maintenir,  ecarte
--     amont, dans une colonne                                et le texte affiche perd
--     separee                                                ses accents
--     **configuration derivee,   un seul endroit a declarer, il faut la creer avant les   **retenu**
--     avec unaccent dans la      le texte stocke garde ses   colonnes qui s'en servent
--     chaine de dictionnaires**  accents
--     moteur de recherche        gere tout cela seul         un service de plus, non      ecarte
--     dedie                                                  mesure comme necessaire
--
-- La configuration est creee dans le schema `public` et toujours nommee en entier dans les
-- colonnes qui l'utilisent : une colonne generee doit designer sa configuration sans ambiguite,
-- sinon sa valeur dependrait du `search_path` de celui qui ecrit.

do $$
begin
    if not exists (
        select 1 from pg_ts_config where cfgname = 'francais'
    ) then
        create text search configuration public.francais (copy = french);

        -- L'ordre compte : unaccent d'abord, qui retire les accents, puis french_stem, qui
        -- ramene le mot a sa racine. Inverser les deux donnerait des racines accentuees que la
        -- recherche sans accent ne retrouverait pas.
        alter text search configuration public.francais
            alter mapping for hword, hword_part, word
            with unaccent, french_stem;
    end if;
end
$$;

-- Preuve que la configuration fait ce qu'on attend. Les deux appels doivent donner le meme
-- resultat, sans quoi la recherche serait sensible aux accents.
select
    to_tsvector('public.francais', 'Rénovation de la toiture de l''école') as avec_accents,
    to_tsvector('public.francais', 'renovation de la toiture de l''ecole') as sans_accents;
