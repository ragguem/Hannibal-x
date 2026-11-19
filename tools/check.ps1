# Contrôle complet du dépôt, équivalent local de la CI. Obligatoire avant chaque étiquette vX.Y.Z.
#   .\tools\check.ps1            contrôles Python, schémas, composition
#   .\tools\check.ps1 -Image     construit aussi l'image API (démon Docker requis)
param([switch]$Image)

# Windows PowerShell 5 transforme toute sortie stderr d'un outil en erreur : seul $LASTEXITCODE fait foi.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)
$failed = @()

function Step([string]$Name, [scriptblock]$Command) {
    Write-Host "`n== $Name" -ForegroundColor Cyan
    & $Command 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { $script:failed += $Name; Write-Host "ÉCHEC : $Name" -ForegroundColor Red }
}

Step "verrou uv à jour" { uv lock --check }
Step "dépendances figées" { uv sync --frozen --all-packages --quiet }
Step "ruff check" { uv run --frozen ruff check . }
Step "ruff format" { uv run --frozen ruff format --check . }
Step "mypy" { uv run --frozen mypy }
Step "import-linter" { uv run --frozen lint-imports }
Step "pytest + couverture" {
    uv run --frozen pytest -q --cov=hannibal_platform --cov=hannibal_contracts --cov=hannibal_api --cov-report=term --cov-fail-under=85
}
Step "back-office : restauration figée" { dotnet restore apps/backoffice/Hannibal.Backoffice.slnx --locked-mode }
Step "back-office : format" { dotnet format apps/backoffice/Hannibal.Backoffice.slnx --verify-no-changes --no-restore }
Step "back-office : tests" { dotnet test --solution apps/backoffice/Hannibal.Backoffice.slnx --no-restore }
Step "crochets pre-commit (tous les fichiers)" { uv run --frozen pre-commit run --all-files }
if (Test-Path pnpm-lock.yaml) { Step "pnpm (verrou figé)" { pnpm install --frozen-lockfile --silent } }
Step "web : client OpenAPI à jour" {
    pnpm --dir apps/web run openapi --silent
    git diff --exit-code -- apps/web/src/services/openapi.d.ts
}
Step "web : tsc" { pnpm --dir apps/web run typecheck }
Step "web : eslint" { pnpm --dir apps/web run lint }
Step "web : vitest + couverture" { pnpm --dir apps/web run coverage }
Step "web : build" { pnpm --dir apps/web run build }
Step "composition dev valide" {
    docker compose -f infra/compose/compose.dev.yml --env-file infra/compose/dev.env.example config --quiet
}
if ($Image) {
    $version = (Get-Content VERSION).Trim()
    Step "image api" { docker build -f apps/api/Dockerfile --build-arg VERSION=$version -t "hannibal/api:$version" . }
    Step "image back-office" { docker build -f apps/backoffice/Dockerfile --build-arg VERSION=$version -t "hannibal/backoffice:$version" . }
}

if ($failed.Count) {
    Write-Host "`n$($failed.Count) contrôle(s) en échec : $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "`nTous les contrôles sont verts." -ForegroundColor Green
