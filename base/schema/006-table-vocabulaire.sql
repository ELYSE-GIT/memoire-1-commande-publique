-- Le vocabulaire de l'index, avec le nombre de marches ou chaque mot apparait.
--
-- A quoi il sert : filtrer les mots d'une question qui ne peuvent pas y aider.
--
-- Mesure du 21 octobre 2026, qui a rendu cette table necessaire. Les sept questions d'essai de
-- l'assistant renvoyaient **zero resultat**, toutes. Cause : `websearch_to_tsquery` combine les
-- mots par ET, et il suffit d'un mot absent de l'index pour annuler la requete entiere.
--
--     mot de la question    marches qui le contiennent    effet en mode ET
--     combien                                        0    annule tout
--     remporte                                       1    annule presque tout
--     quel                                         513    annule 99,97 %
--     voirie                                    42 061    utile
--
-- Deux parasites existent, a chaque bout du spectre :
--
--     trop rare       « combien », « remporte » : le mot vient de la question, pas du domaine
--     trop frequent   « a » (23,5 % des marches), « le » (13,5 %) : ne discrimine rien
--
-- Le second cas a une cause mesuree et inattendue, decrite dans `002-configuration-plein-texte.sql` :
-- la configuration `public.francais` retire les accents **avant** le dictionnaire. La preposition
-- « à » arrive donc au dictionnaire sous la forme « a », et la liste des mots vides francaise
-- contient « à » mais pas « a ». Resultat mesure : « à » a cesse d'etre un mot vide le jour ou la
-- recherche est devenue insensible aux accents.
--
-- Le meme mecanisme, a l'envers, laisse passer « les » : la liste contient « le » et « la », pas
-- « les ». Le dictionnaire verifie la liste sur le mot d'origine, puis racinise, et « les » sort
-- sous le lexeme « le ». Un mot vide entre donc dans l'index par la porte de son pluriel.
--
-- Aucun des deux ne se corrige dans la configuration sans perdre l'insensibilite aux accents,
-- qui est le service rendu a l'utilisateur. Ils se corrigent ici, par la frequence.
--
-- === Pourquoi une table et non un calcul a la volee ==========================
--
--     Option envisagee           Avantage                    Limite                      Verdict
--     une liste de mots ecrite   immediate, zero calcul      a maintenir a la main ;     ecarte
--     a la main                                              muette sur les fautes de
--                                                            frappe et sur « a »
--     compter a chaque           toujours juste              une lecture d'index par     ecarte
--     question                                               mot : mesure a 40 ms par
--                                                            mot, soit 300 ms pour une
--                                                            question de huit mots
--     **table de frequences     une seule lecture indexee    a reconstruire quand les    **retenu**
--     construite avec l'index** par question (0,3 ms) ;      donnees changent, donc au
--                                construite des donnees,     meme moment que l'index
--                                donc jamais inventee
--
-- A quelle echelle la reponse changerait : sous quelques milliers de marches, aucun filtre n'est
-- utile, la cascade ET puis OU de la recherche suffit. Au-dela d'une dizaine de millions, il
-- faudrait echantillonner plus finement ou tenir la table a jour par declencheur.
--
-- === Pourquoi un echantillon de 5 pour cent ==================================
--
-- `ts_stat` lit tous les vecteurs demandes. Mesure sur cette base :
--
--     sur 100 % des marches     non mesure, interrompu apres deux minutes
--     sur 5 % des marches       8,0 s, 73 722 lexemes distincts
--
-- Ce qu'on demande a cette table, c'est un ordre de grandeur pour comparer a un seuil, pas un
-- compte exact. Un echantillon systematique de 5 % donne cet ordre de grandeur a mieux que le
-- pour-cent pres sur les mots qui comptent, et les mots trop rares pour y figurer sont
-- precisement ceux qu'on veut ecarter.

create table if not exists vocabulaire (
    -- Le lexeme, c'est-a-dire le mot apres racinisation : « voirie » est stocke « voir ».
    -- C'est la forme presente dans l'index, donc la seule sur laquelle on peut compter.
    lexeme      text primary key,
    -- Nombre de marches de l'echantillon qui contiennent ce lexeme.
    marches     integer not null,
    -- Taille de l'echantillon, repetee sur chaque ligne. Redondant, et c'est voulu : la
    -- frequence doit pouvoir se calculer sans connaitre le contexte de construction.
    echantillon integer not null
);

comment on table vocabulaire is
    'Frequences des mots de l''index, sur un echantillon de 5 %. Reconstruite avec les index.';
comment on column vocabulaire.lexeme is
    'Mot apres racinisation francaise, tel qu''il figure dans la colonne recherche.';
