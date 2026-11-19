#!/usr/bin/env bash
# Contrôle complet du dépôt, équivalent local de la CI. Obligatoire avant chaque étiquette vX.Y.Z.
#   tools/check.sh            contrôles Python, schémas, composition
#   tools/check.sh --image    construit aussi l'image API
set -uo pipefail
cd "$(dirname "$0")/.."
failed=()

step() {
  local name="$1"; shift
  printf '\n== %s\n' "$name"
  "$@" || { failed+=("$name"); printf 'ÉCHEC : %s\n' "$name"; }
}

step "verrou uv à jour" uv lock --check
step "dépendances figées" uv sync --frozen --all-packages --quiet
step "ruff check" uv run --frozen ruff check .
step "ruff format" uv run --frozen ruff format --check .
step "mypy" uv run --frozen mypy
step "import-linter" uv run --frozen lint-imports
step "pytest + couverture" uv run --frozen pytest -q --cov=hannibal_platform --cov=hannibal_contracts \
  --cov=hannibal_api --cov-report=term --cov-fail-under=85
if command -v dotnet >/dev/null; then
  step "back-office : restauration figée" dotnet restore apps/backoffice/Hannibal.Backoffice.slnx --locked-mode
  step "back-office : format" dotnet format apps/backoffice/Hannibal.Backoffice.slnx --verify-no-changes --no-restore
  step "back-office : tests" dotnet test --solution apps/backoffice/Hannibal.Backoffice.slnx --no-restore
fi
step "crochets pre-commit (tous les fichiers)" uv run --frozen pre-commit run --all-files
[[ -f pnpm-lock.yaml ]] && step "pnpm (verrou figé)" pnpm install --frozen-lockfile --silent
step "web : client OpenAPI à jour" bash -c \
  "pnpm --dir apps/web run openapi --silent && git diff --exit-code -- apps/web/src/services/openapi.d.ts"
step "web : tsc" pnpm --dir apps/web run typecheck
step "web : eslint" pnpm --dir apps/web run lint
step "web : vitest + couverture" pnpm --dir apps/web run coverage
step "web : build" pnpm --dir apps/web run build
step "composition dev valide" docker compose -f infra/compose/compose.dev.yml \
  --env-file infra/compose/dev.env.example config --quiet
if [[ "${1:-}" == "--image" ]]; then
  version="$(tr -d '[:space:]' < VERSION)"
  step "image api" docker build -f apps/api/Dockerfile --build-arg "VERSION=$version" -t "hannibal/api:$version" .
  step "image back-office" docker build -f apps/backoffice/Dockerfile --build-arg "VERSION=$version" -t "hannibal/backoffice:$version" .
fi

if ((${#failed[@]})); then
  printf '\n%d contrôle(s) en échec : %s\n' "${#failed[@]}" "${failed[*]}"
  exit 1
fi
printf '\nTous les contrôles sont verts.\n'
