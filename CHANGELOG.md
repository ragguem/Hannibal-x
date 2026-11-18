# Journal des versions

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Versions : [SemVer](https://semver.org/lang/fr/),
un lot livré = `0.N.0`, MVP de démonstration = `1.0.0` (ADR 0004).

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
