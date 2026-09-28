# Toutes les commandes du projet passent par ce fichier.
# `make help` affiche la liste. Chaque cible porte un commentaire apres ##.

.DEFAULT_GOAL := help
SHELL := /bin/bash

## help : affiche toutes les commandes disponibles
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/^## /  /'

# --- Environnement Python -------------------------------------------------

## install : cree le .venv et installe les dependances verrouillees
install:
	uv sync

## hooks : installe les verifications automatiques avant chaque commit
hooks:
	pre-commit install

## lint : verifie le style et les pieges courants (Ruff)
lint:
	uv run ruff check .

## format : reformate le code (Ruff)
format:
	uv run ruff format .

## types : verifie les types (mypy)
types:
	uv run mypy .

## test : lance les tests avec la couverture
test:
	uv run pytest

## secrets : cherche des mots de passe ou des cles, dans les fichiers et dans l'historique
secrets:
	@echo "--- fichiers presents ---"
	gitleaks dir . --no-banner --redact
	@echo "--- historique des commits ---"
	gitleaks git . --no-banner --redact

## verif : tout ce que la CI verifie, en une commande
verif: lint types test secrets

# --- Conteneurs -----------------------------------------------------------

## vm-up : demarre la VM des conteneurs (4 CPU, 6 Go, 40 Go de disque)
vm-up:
	colima start --cpu 4 --memory 6 --disk 40

## vm-down : arrete la VM des conteneurs (a faire en fin de session)
vm-down:
	colima stop

## up : demarre les services du projet
up:
	docker compose up -d

## down : arrete les services du projet
down:
	docker compose down

## etat : affiche les conteneurs en cours et la VM
etat:
	@colima status || true
	@docker compose ps || true

# --- Donnees et mesures -----------------------------------------------------

# Adresse du jeu consolide publie sur data.gouv.fr. Le nom du dossier contient la date de
# publication : il change a chaque mise a jour quotidienne, d'ou la resolution par l'API.
URL_JEU_DECP = https://www.data.gouv.fr/api/1/datasets/donnees-essentielles-de-la-commande-publique-consolidees-format-tabulaire/

## collecte-decp : collecte le jeu DECP vers la couche bronze, avec manifeste
collecte-decp:
	uv run python -m services.collecte decp

## collecte-boamp : collecte les avis du BOAMP sur une periode, vers la couche bronze
collecte-boamp:
	uv run python -m services.collecte boamp --debut 2025-01-01 --fin 2025-07-01

## collecte : les deux sources, puis l'etat du manifeste
collecte: collecte-decp collecte-boamp collecte-etat

## collecte-etat : affiche le dernier manifeste et verifie que les fichiers sont intacts
collecte-etat:
	uv run python -m services.collecte etat

## donnees-decp : telecharge le jeu DECP consolide en Parquet (environ 240 Mo)
donnees-decp:
	@mkdir -p donnees/brut
	@echo "Resolution de l'adresse du fichier courant..."
	@url=$$(curl -s "$(URL_JEU_DECP)" | uv run python -c "import json,sys; d=json.load(sys.stdin); print(next(r['url'] for r in d['resources'] if r['title']=='decp.parquet'))"); \
		echo "$$url"; \
		curl -L --progress-bar -o donnees/brut/decp.parquet "$$url"
	@ls -lh donnees/brut/decp.parquet

# --- Transformation -------------------------------------------------------

# Le chemin de la donnee brute est passe en absolu. Une vue dbt qui porterait un chemin relatif
# ne fonctionnerait que si on l'interroge depuis le dossier de dbt : un notebook ou un script
# lance depuis la racine echouerait. Le defaut a ete rencontre, puis corrige ici.
CHEMIN_DECP = $(CURDIR)/donnees/bronze/decp/*/decp.parquet
DBT = cd services/transformation && uv run dbt

## transformer : construit les trois couches, bronze, argent et or
transformer:
	$(DBT) build --vars '{"chemin_decp": "$(CHEMIN_DECP)"}'

## transformer-tester : lance uniquement les tests de donnees
transformer-tester:
	$(DBT) test --vars '{"chemin_decp": "$(CHEMIN_DECP)"}'

## transformer-doc : genere la documentation et le graphe des dependances
transformer-doc:
	$(DBT) docs generate --vars '{"chemin_decp": "$(CHEMIN_DECP)"}'
	@echo "Ouvrir : cd services/transformation && uv run dbt docs serve"

## bench-decp : mesure la qualite et les performances sur le jeu DECP
bench-decp:
	uv run python mesures/decp_qualite.py

## bench-decp-distributions : calcule les agregats descriptifs (CSV dans mesures/resultats)
bench-decp-distributions:
	uv run python mesures/decp_distributions.py

## bench-rapprochement : mesure si les avis du BOAMP peuvent etre relies aux marches des DECP
bench-rapprochement:
	uv run python mesures/rapprochement_boamp_decp.py

## bench-nettoyage : mesure l'effet de chaque regle de nettoyage, couche par couche
bench-nettoyage:
	uv run python mesures/nettoyage.py

## bench-detection : evalue la regle de prix contre les anomalies signalees par le producteur
bench-detection:
	uv run python mesures/detection.py

## bench-precision : croise les verdicts relus a la main avec le balayage des seuils
bench-precision:
	uv run python mesures/precision_rapprochement.py

## figures : trace les figures du memoire a partir des agregats mesures
figures:
	uv run python mesures/figures.py

## notebooks : rejoue tous les notebooks d'exploration et enregistre leurs resultats
notebooks:
	cd analyses && uv run jupyter execute --inplace 01-exploration-decp.ipynb
	cd analyses && uv run jupyter execute --inplace 02-statistiques-descriptives.ipynb

# --- Documentation --------------------------------------------------------

## docs-txt : genere la version .txt des commandes a partir des .md
docs-txt:
	@mkdir -p docs/commandes/txt
	@for f in docs/commandes/*.md; do \
		cp "$$f" "docs/commandes/txt/$$(basename $${f%.md}).txt"; \
	done
	@echo "Version txt generee dans docs/commandes/txt/"

# --- Nettoyage ------------------------------------------------------------

## clean : supprime les caches Python et les rapports de tests
clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

## clean-all : supprime tout ce que le projet a cree sur le Mac
clean-all: clean
	-docker compose down -v --rmi local
	rm -rf .venv donnees
	@echo "Pour liberer la VM entierement : colima delete"

.PHONY: help install hooks transformer transformer-tester transformer-doc collecte collecte-decp collecte-boamp collecte-etat donnees-decp bench-decp bench-decp-distributions bench-rapprochement bench-precision bench-nettoyage bench-detection figures notebooks lint format types test secrets verif vm-up vm-down up down etat docs-txt clean clean-all
