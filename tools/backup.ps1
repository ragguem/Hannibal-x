# Sauvegarde du dépôt local (pas de remote) : un fichier bundle avec tout l'historique et les étiquettes.
#   .\tools\backup.ps1 -Destination E:\sauvegardes\hannibal
# Restauration : git clone <fichier>.bundle hannibal-x-dev
param([Parameter(Mandatory)][string]$Destination)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$head = (git rev-parse --short HEAD).Trim()
$file = Join-Path $Destination ("hannibal-x-{0}-{1}.bundle" -f (Get-Date -Format "yyyyMMdd-HHmm"), $head)
git bundle create $file --all
if ($LASTEXITCODE -ne 0) { exit 1 }
git bundle verify $file
if ($LASTEXITCODE -ne 0) { exit 1 }
Write-Host "Sauvegarde : $file"
