# Windows PowerShell launcher for MotoShop RMS menu
Set-Location $PSScriptRoot
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
  & py -3 scripts\dev_menu.py @args
  exit $LASTEXITCODE
}
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
  & python scripts\dev_menu.py @args
  exit $LASTEXITCODE
}
Write-Error "Python 3 not found. Install Python 3 and try again."
exit 1
