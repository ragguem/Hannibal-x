# Journal des versions

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Versions : [SemVer](https://semver.org/lang/fr/),
un lot livré = `0.N.0`, MVP de démonstration = `1.0.0` (ADR 0004).

## [Non publié]

### Ajouté

- ADR 0006 : dépôt git local, sans remote ni CI hébergée.
- `tools/check.ps1` et `tools/check.sh` : contrôle complet local (équivalent de la CI), seuil de couverture 85 %.
- `tools/backup.ps1` : sauvegarde du dépôt par `git bundle`.
- Lot 1 (en cours) : `packages/core` (`hannibal-core`), avec `signals` (interpréteur) et `orders` (`grammar`, `kinematics`, `recommendations`, `mtp_mapping`), copiés de l’ancien code sans entrée-sortie ; contrat import-linter « Core : aucune entrée-sortie ».
- Goldens de caractérisation exécutés sur `legacy` et sur `core` ; écarts voulus du cœur dans `golden/core/`.
- Limite de vitesse unique `SpeedLimits` (3 à 28 nœuds par défaut) pour le clavier et les signaux : un ordre hors
  bornes est ramené à la borne avec une note (le clavier refusait au-delà de 18 nœuds).
- ADR 0007 : back-office métier en .NET 10 (`apps/backoffice`), cœur tactique et IA en Python.
- Socle `apps/backoffice` (.NET 10) : couches Domain / Application / Infrastructure / Api, `/v1/health`, `/v1/ready`
  (sondes PostgreSQL et API, adaptateurs faux ou réels), `/metrics` protégé, `request_id`, `ErrorBody`, jeton interne,
  journal JSON ; 16 tests (contrats JSON Schema partagés, règles de couches) ; image Docker chiseled non root ;
  service dans la composition ; `dotnet format` et `dotnet test` dans pre-commit et `tools/check`.

### Supprimé

- Fichiers obsolètes de `legacy/` (liste dans `legacy/README.md`).

### Modifié

- Crochets pre-commit entièrement hors ligne (`pre-commit-hooks` verrouillé dans `uv.lock`), avec mypy et pytest.
- `.github/workflows/ci.yml` conservé mais inactif.

## [0.1.0] — 2026-11-18 — Lot 0 : fondations

### Ajouté

- Monodépôt : espace de travail uv (Python 3.12) et pnpm, `uv.lock` et `pnpm-lock.yaml` figés.
- `packages/platform` 0.1.0 : configuration typée, journal JSON (structlog), `X-Request-Id`, UUIDv7, erreurs
  `{ code, message, request_id }`, jeton interne, client HTTP interne, `/health`, métriques Prometheus protégées.
- `packages/contracts` 0.1.0 : `ContractModel`, `ErrorBody`, `Health`, `Readiness`, export des schémas JSON
  et test de dérive.
- `apps/api` 0.1.0 : squelette hexagonal, `GET /v1/health`, `GET /v1/ready` (PostgreSQL, Ollama), mode `fake`,
  image Docker non root.
- `infra/compose/compose.dev.yml` : PostgreSQL 17 + pgvector 0.8.7, API, Ollama 0.35.1 (profil `gpu`).
- `eval/characterization` : goldens de l'ancien code (interpréteur, grammaire, cinématique, recommandations,
  pont signaux → ordres), KB synthétique, test sur le jeu réel (marqué `data`), scripts d'enregistrement serveur.
- CI : ruff, mypy strict, import-linter, pytest avec couverture, image API, composition, job Node.
- ADR 0001 à 0005, `docs/developpement.md`, `docs/donnees-hors-depot.md`.

### Modifié

- L'ancien code est déplacé dans `legacy/` ; ses scripts lisent `HANNIBAL_HOME` (défaut `~/hannibal`).
- `.gitignore` adapté à la nouvelle arborescence.
