# Windows PowerShell production deploy / restart
Set-Location $PSScriptRoot

function Invoke-ProdDeploy {
  param([string]$Exe, [string[]]$PrefixArgs = @())
  & $Exe @PrefixArgs scripts\prod_deploy.py @args
  exit $LASTEXITCODE
}

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { Invoke-ProdDeploy $py.Source @("-3") }

$python3 = Get-Command python3 -ErrorAction SilentlyContinue
if ($python3) { Invoke-ProdDeploy $python3.Source }

$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) { Invoke-ProdDeploy $python.Source }

Write-Error "Python 3 not found. Install Python 3 (python3 / py / python) and try again."
exit 1
