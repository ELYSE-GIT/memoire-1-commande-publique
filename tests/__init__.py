"""Fait du dossier des tests un paquet, pour qu'un test puisse en importer un autre.

`tests/test_site.py` reutilise le faux curseur et les lignes d'exemple de `tests/test_api.py` :
le site appelle les memes routes, donc les memes formes de donnees, et les recopier aurait cree
deux verites a tenir a jour. Sans ce fichier, mypy voit le meme fichier sous deux noms de module
(`test_api` et `tests.test_api`) et s'arrete.
"""
