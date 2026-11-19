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
| SDK .NET | 11.0.100 (`global.json`), runtime ASP.NET Core 10 | back-office `apps/backoffice` (ADR 0007) ; `nuget.config` local limité à nuget.org |

## Premiers pas

```bash
uv sync --all-packages
uv run pre-commit install
pnpm install
uv run pytest
```

Le dépôt est local, sans CI distante (ADR 0006) :

- chaque commit passe par les crochets pre-commit (ruff, mypy, import-linter, pytest, fichiers de données refusés) ;
- le contrôle complet, obligatoire avant chaque étiquette de lot :

```powershell
.\tools\check.ps1            # poste Windows ; -Image pour construire aussi l'image API
```

```bash
tools/check.sh               # serveur ; --image pour construire aussi l'image API
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

## Voix (service asr)

En mode `fake`, l'API « entend » toujours `HX_API_SCRIPTED_TRANSCRIPT`. Pour le service seul :

```bash
HX_ASR_ENGINE=scripted uv run uvicorn --factory hannibal_asr.main:create_app --port 8200
uv sync --extra whisper    # vraie reconnaissance : faster-whisper, modèle téléchargé au premier appel
HX_ASR_ENGINE=whisper HX_ASR_DEVICE=cpu HX_ASR_WHISPER_MODEL=small uv run uvicorn --factory hannibal_asr.main:create_app --port 8200
```

Variables : préfixe `HX_ASR_` (`ENGINE`, `WHISPER_MODEL`, `WHISPER_FALLBACK_MODEL`, `DEVICE`, `GPU_COMPUTE_TYPE`,
`CPU_COMPUTE_TYPE`, `LANGUAGE`, `BEAM_SIZE`, `MAX_AUDIO_BYTES`). Côté API : `HX_API_ASR_URL`,
`HX_API_RECORDINGS_DIR` (audio des ordres, hors dépôt, à sauvegarder avec le registre). Sur le serveur :
`docker build -f services/asr/Dockerfile --target gpu`. Le micro du navigateur exige HTTPS ou `localhost` ;
sinon, importer un WAV.

## Doctrine (services doctrine et rerank)

En mode `fake`, l'API répond avec un assistant d'exemple (texte inventé). Pour les services seuls, sans GPU ni base :

```bash
HX_RERANK_SCORER=lexical uv run uvicorn --factory hannibal_rerank.main:create_app --port 8300
HX_DOCTRINE_ADAPTERS=sample HX_DOCTRINE_RERANK_URL=http://127.0.0.1:8300 \
  uv run uvicorn --factory hannibal_doctrine.main:create_app --port 8400
```

Mode `real` : index `v2` chargé (la réindexation n'est pas encore dans le dépôt), rôle `hannibal_doctrine` créé
par `services/doctrine/sql/roles.sql`, `HX_DOCTRINE_DATABASE_URL`, `HX_DOCTRINE_OLLAMA_URL` (modèles
`gemma3:12b` et `bge-m3`). Réglages : préfixe `HX_DOCTRINE_` (`MIN_SIMILARITY`, `EXTRACTS`, `RETRY_EXTRACTS`,
`FALLBACK_MODEL`, `ANSWER_STYLE`, `USE_TABLE_ROWS`, `USE_GENERATED_QUESTIONS`, `CLASSIFIED_PUBLICATIONS`…) ; côté
API : `HX_API_DOCTRINE_URL` et la file GPU (`DOCTRINE_ACTIVE`, `DOCTRINE_WAITING`, `DOCTRINE_WAIT_S`). Recette sur
le serveur : `python eval/doctrine/doctrine_eval.py <jeu hors dépôt>` ou le workflow `eval`.

## Lancer le back-office (.NET)

```bash
dotnet test --solution apps/backoffice/Hannibal.Backoffice.slnx
HX_BACKOFFICE_ADAPTERS=fake dotnet run --project apps/backoffice/src/Hannibal.Backoffice.Api
# http://127.0.0.1:5000/v1/health, /v1/ready ; port 8080 dans la composition
```

Variables : préfixe `HX_BACKOFFICE_` (`ADAPTERS`, `DATABASE_URL` au format Npgsql, `API_URL`, `ENVIRONMENT`,
`INTERNAL_TOKEN`, `METRICS_TOKEN`), mêmes règles que l'API. Les réponses sont validées contre les schémas
de `packages/contracts/schemas` : un changement de contrat côté Python casse les tests .NET.

## Lancer la console web (React)

```bash
pnpm install --frozen-lockfile
pnpm --dir apps/web dev:mock      # faux back-office MSW : instructeur / demo (tous droits), eleve / demo
pnpm --dir apps/web dev           # vrai back-office : proxy /v1 vers HX_BACKOFFICE_URL (http://127.0.0.1:8080)
pnpm --dir apps/web test          # Vitest ; coverage pour la couverture
HX_E2E_CHANNEL=msedge pnpm --dir apps/web e2e   # Playwright sur les faux, avec Edge ou Chrome déjà installé
pnpm --dir apps/web openapi       # régénère le client après un changement de apps/api/openapi.json
```

Couches (architecture 1.1.0 § 14, vérifiées par ESLint) : seul `src/socle/composition.tsx` construit les
adaptateurs `services/http-api` et `services/sse-stream` ; `features/` et `pages/` passent par `useApi()` et
`useStream()` ; `components/` ne reçoit que des props. La Vue 3D (`view3d.html`, `src/features/vue3d`) garde son
moteur three.js hors React : `/vue3d/:id` l'encadre, `/view3d.html?demo` la joue sans mission. La page
`/registre` (permission `audit:read`) remplace `registre.html` ; dans le faux back-office, chaque enregistrement
est « entendu » comme `ALL SHIPS CORPEN 045 SPEED 12`.

## Règles du code

- Architecture hexagonale par processus : `domain` (pur) ← `application` (cas d'usage, ports) ← `infrastructure`
  et `presentation` ← `socle` (configuration et assemblage). Vérifié par import-linter.
- Le domaine n'importe ni FastAPI, ni SQLAlchemy, ni httpx, ni `hannibal_platform`.
- Toute erreur sortante passe par `hannibal_platform.errors` : `{ code, message, request_id }`, jamais de détail interne.
- Journal : une ligne JSON par événement, jamais de texte de publication, d'audio, de jeton ou de prompt complet.
- Un contrat modifié : `uv run hx-export-schemas`, et le diff de `packages/contracts/schemas/` va dans le commit.
- Une fonction de l'ancien code réécrite : brancher le nouveau code sur `eval/characterization/` (voir son README).

## Git

- Tous les commits restent en local. Développement sur `main`, branche locale courte pour un essai risqué.
- Pas de `--no-verify`, sauf commit de travail repris avant l'étiquette.
- Conventional Commits : `feat(api): …`, `fix(signals): …`, `chore: …`, `docs: …`, `test: …`, `refactor: …`.
- Fin de lot :
  1. `CHANGELOG.md`, `VERSION` et versions des paquets à `0.N.0` ;
  2. `.\tools\check.ps1` vert (avec `-Image` si Docker tourne) ;
  3. `git tag -a v0.N.0 -m "Lot N : …"` ;
  4. `.\tools\backup.ps1 -Destination <support externe>` : le dépôt n'existe nulle part ailleurs.

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
