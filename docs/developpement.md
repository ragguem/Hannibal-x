# Développer sur Hannibal X

## Prérequis

| Outil | Version | Remarque |
|---|---|---|
| Git | 2.4x et plus | `core.autocrlf=false` conseillé ; `.gitattributes` impose LF |
| uv | 0.13 | installe et fige Python et les dépendances |
| Python | 3.12 | imposé par ROS 2 Jazzy (`rclpy`) |
| Node.js | 24 LTS (22.12 et plus accepté) | front à partir du Lot 1 |
| pnpm | 10 | `corepack enable` ou installation directe |
| Docker Engine / Compose | 29 / v2 | composition de développement |

## Premiers pas

```bash
uv sync --all-packages
uv run pre-commit install
pnpm install
uv run pytest
```

Contrôles lancés par la CI (à lancer avant de pousser) :

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run lint-imports
uv run pytest
```

## Lancer l'API

Sans aucune dépendance (sondes factices) :

```bash
HX_API_ADAPTERS=fake uv run uvicorn --factory hannibal_api.socle.main:create_app --reload
# http://127.0.0.1:8000/v1/health, /v1/ready, /v1/docs
```

Avec PostgreSQL (et Ollama en option) par Docker :

```bash
cp infra/compose/dev.env.example infra/compose/dev.env      # puis changer le mot de passe
docker compose -f infra/compose/compose.dev.yml --env-file infra/compose/dev.env up -d --build
docker compose -f infra/compose/compose.dev.yml --env-file infra/compose/dev.env --profile gpu up -d
```

Variables de l'API : préfixe `HX_API_` (`ADAPTERS`, `DATABASE_URL`, `OLLAMA_URL`, `LOG_LEVEL`, `ENVIRONMENT`,
`INTERNAL_TOKEN`, `METRICS_TOKEN`, `READINESS_TIMEOUT_S`). Hors `dev`/`test`, `/metrics` et les routes internes
exigent leur jeton.

## Règles du code

- Architecture hexagonale par processus : `domain` (pur) ← `application` (cas d'usage, ports) ← `infrastructure`
  et `presentation` ← `socle` (configuration et assemblage). Vérifié par import-linter.
- Le domaine n'importe ni FastAPI, ni SQLAlchemy, ni httpx, ni `hannibal_platform`.
- Toute erreur sortante passe par `hannibal_platform.errors` : `{ code, message, request_id }`, jamais de détail interne.
- Journal : une ligne JSON par événement, jamais de texte de publication, d'audio, de jeton ou de prompt complet.
- Un contrat modifié : `uv run hx-export-schemas`, et le diff de `packages/contracts/schemas/` va dans le commit.
- Une fonction de l'ancien code réécrite : brancher le nouveau code sur `eval/characterization/` (voir son README).

## Git

- Développement sur `main` (trunk-based), branches courtes si besoin, CI verte avant fusion.
- Conventional Commits : `feat(api): …`, `fix(signals): …`, `chore: …`, `docs: …`, `test: …`, `refactor: …`.
- Fin de lot : `CHANGELOG.md`, `VERSION` et versions des paquets à `0.N.0`, étiquette `v0.N.0`.

## Poste Windows derrière un proxy ou un bac à sable

Constaté sur le poste de développement initial :

- `uv python install` échoue si les binaires Python hébergés sur GitHub sont bloqués. Contournement : installer
  le paquet NuGet `python` 3.12 (nuget.org), puis `UV_PYTHON=<chemin>\tools\python.exe` et `UV_PYTHON_DOWNLOADS=never`.
- uv lit le proxy système ; si ce proxy ne résout pas les noms (erreur « tunnel error … dns error »), définir
  `NO_PROXY=*` pour la session.
- `uv` s'installe dans `%USERPROFILE%\.local\bin`, à ajouter au `PATH`.

```powershell
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
$env:UV_PYTHON = "$env:LOCALAPPDATA\Programs\cpython-3.12-nuget\tools\python.exe"
$env:UV_PYTHON_DOWNLOADS = "never"
$env:NO_PROXY = "*"
uv sync --all-packages
```
