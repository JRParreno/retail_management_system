# Windows PowerShell launcher for MotoShop RMS local / dev menu
# Usage:
#   .\local_run.ps1
#   .\local_run.ps1 5
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python scripts/dev_menu.py @args
    exit $LASTEXITCODE
}
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 scripts/dev_menu.py @args
    exit $LASTEXITCODE
}

Write-Host "Python 3 not found. Install from https://www.python.org/downloads/"
Write-Host "  (check 'Add python.exe to PATH') or: winget install Python.Python.3.12"
exit 1
