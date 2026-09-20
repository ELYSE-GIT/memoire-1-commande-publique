# 01. Installation de zero sur le Mac

Objectif : partir d'un Mac vierge et arriver a un projet qui tourne. Duree totale : environ 30 min,
dont 10 min d'attente pendant les telechargements.

Machine de reference : MacBook M2 Pro, 10 coeurs, 16 Go de RAM, processeur uniquement (pas de GPU).

## 1. Homebrew, le gestionnaire de paquets

Ou : terminal du Mac. Duree : 5 min. A faire une seule fois sur la machine.

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Verifier :

```bash
brew --version
```

Resultat attendu : un numero de version, par exemple `Homebrew 7.0.4`.

## 2. Les outils du projet

Ou : terminal du Mac. Duree : 5 a 10 min.

```bash
brew install uv colima docker docker-compose pre-commit gitleaks
```

| Outil | Role |
|---|---|
| `uv` | cree le `.venv`, installe et verrouille les dependances Python |
| `colima` | la machine virtuelle Linux qui heberge les conteneurs |
| `docker` | la commande qui pilote les conteneurs |
| `docker-compose` | lance plusieurs conteneurs ensemble |
| `pre-commit` | lance les verifications avant chaque commit |
| `gitleaks` | refuse un commit qui contient une cle ou un mot de passe |

Verifier :

```bash
uv --version && colima version && docker --version && gitleaks version
```

Note : Colima remplace Docker Desktop. Meme commande `docker`, mais rien ne tourne quand la VM est
arretee, et pas de licence d'entreprise a surveiller.

## 3. Recuperer le projet

Ou : terminal du Mac. Duree : 1 min.

```bash
git clone https://github.com/ELYSE-GIT/memoire-1-commande-publique.git
cd memoire-1-commande-publique
```

## 4. L'environnement Python

Ou : a la racine du projet. Duree : 2 min.

```bash
make install
```

Ce que ca fait : `uv` lit `.python-version` et `pyproject.toml`, installe Python 3.12 s'il manque,
cree le dossier `.venv`, puis installe exactement les versions listees dans `uv.lock`.

Resultat attendu : un dossier `.venv/` et la ligne `Installed N packages`.

## 5. Les verifications avant commit

Ou : a la racine du projet. Duree : 1 min. A faire une seule fois apres le clone.

```bash
pre-commit install
```

Resultat attendu : `pre-commit installed at .git/hooks/pre-commit`.

A partir de la, chaque `git commit` lance le style, le format et la recherche de secrets. Si une
verification echoue, le commit est refuse et le probleme est affiche.

## 6. La configuration locale

Ou : a la racine du projet. Duree : 2 min.

```bash
cp .env.example .env
```

Puis ouvrir `.env` et remplacer les valeurs `a_changer`. Le fichier `.env` n'est jamais versionne :
il est dans `.gitignore`, et gitleaks bloque tout secret qui tenterait de passer.

## 7. Verifier que tout fonctionne

Ou : a la racine du projet. Duree : 1 min.

```bash
make verif
```

Ce que ca fait : style (Ruff), types (mypy), tests (pytest) et recherche de secrets (gitleaks).

Resultat attendu : les tests passent et aucune erreur n'est signalee. C'est exactement ce que la
chaine d'integration continue rejoue a chaque push.

## 8. Les conteneurs

Ou : a la racine du projet. Duree : 2 min au premier demarrage.

```bash
make vm-up      # demarre la VM, 4 CPU, 6 Go de RAM, 40 Go de disque
docker run --rm hello-world
make vm-down    # arrete la VM
```

Resultat attendu : le message `Hello from Docker!`, puis la VM s'arrete et ne consomme plus rien.

## En cas de probleme

Voir [08-depannage.md](08-depannage.md).
