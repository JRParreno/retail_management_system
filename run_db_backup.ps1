# Windows PowerShell DB backup helper
# Usage:
#   .\run_db_backup.ps1 status
#   .\run_db_backup.ps1 backup
#   .\run_db_backup.ps1 install-cron
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python scripts/db_backup.py @args
    exit $LASTEXITCODE
}
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 scripts/db_backup.py @args
    exit $LASTEXITCODE
}

Write-Host "Python 3 not found."
exit 1
