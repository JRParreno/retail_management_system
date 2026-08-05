# Windows PowerShell production deploy / restart
Set-Location $PSScriptRoot
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
  & py -3 scripts\prod_deploy.py @args
  exit $LASTEXITCODE
}
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
  & python scripts\prod_deploy.py @args
  exit $LASTEXITCODE
}
Write-Error "Python 3 not found. Install Python 3 and try again."
exit 1
