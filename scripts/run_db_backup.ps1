# Windows PowerShell DB backup helper
# Usage:
#   .\scripts\run_db_backup.ps1 status
#   .\scripts\run_db_backup.ps1 backup
#   .\scripts\run_db_backup.ps1 install-cron
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
. "$PSScriptRoot\_python.ps1"
Invoke-RmsPython (@("scripts/db_backup.py") + $args)
