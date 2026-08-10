# Windows PowerShell production deploy for MotoShop RMS
# Usage:
#   .\scripts\run_prod.ps1
#   .\scripts\run_prod.ps1 --skip-build
#   .\scripts\run_prod.ps1 --with-tunnel quick
#   .\scripts\run_prod.ps1 --stop-only
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
. "$PSScriptRoot\_python.ps1"
Invoke-RmsPython (@("scripts/prod_deploy.py") + $args)
