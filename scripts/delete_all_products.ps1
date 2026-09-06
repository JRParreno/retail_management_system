# Hard-delete ALL products (interactive yes/no).
# Usage (from repo root):
#   .\scripts\delete_all_products.ps1
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Backend = Join-Path $Root "backend"
$Py = Join-Path $Backend ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    throw "Backend venv not found at $Py. Run the Dev Launcher first-time setup."
}
Set-Location $Backend
& $Py -m app.scripts.delete_all_products @args
exit $LASTEXITCODE
