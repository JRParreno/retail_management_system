# Windows PowerShell launcher for MotoShop RMS local / dev menu
# Usage: .\scripts\local_run.ps1
#        .\scripts\local_run.ps1 5
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
. "$PSScriptRoot\_python.ps1"
Invoke-RmsPython (@("scripts/dev_menu.py") + $args)
