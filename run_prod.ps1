# Windows PowerShell production deploy for MotoShop RMS
# Usage:
#   .\run_prod.ps1
#   .\run_prod.ps1 --skip-build
#   .\run_prod.ps1 --with-tunnel quick
#   .\run_prod.ps1 --stop-only
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python scripts/prod_deploy.py @args
    exit $LASTEXITCODE
}
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 scripts/prod_deploy.py @args
    exit $LASTEXITCODE
}

Write-Host "Python 3 not found. Install from https://www.python.org/downloads/"
exit 1
