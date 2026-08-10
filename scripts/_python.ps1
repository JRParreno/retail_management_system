# Shared: resolve a real Python 3 (skip Microsoft Store stub).
# Dot-source from other scripts: . "$PSScriptRoot\_python.ps1"
function Test-RealPython([string]$Exe, [string[]]$PrefixArgs) {
    try {
        $out = & $Exe @PrefixArgs --version 2>&1 | Out-String
        return ($LASTEXITCODE -eq 0) -and ($out -match "Python 3\.")
    } catch {
        return $false
    }
}

function Find-RmsPython {
    $candidates = @(
        @{ Exe = "py"; Args = @("-3") },
        @{ Exe = "python"; Args = @() },
        @{ Exe = "python3"; Args = @() }
    )
    foreach ($c in $candidates) {
        $cmd = Get-Command $c.Exe -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        if ($cmd.Source -match "WindowsApps\\python") { continue }
        if (Test-RealPython $c.Exe $c.Args) {
            return @{ Exe = $c.Exe; Args = $c.Args }
        }
    }
    $paths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:ProgramFiles\Python313\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python311\python.exe"
    )
    foreach ($p in $paths) {
        if ((Test-Path $p) -and (Test-RealPython $p @())) {
            return @{ Exe = $p; Args = @() }
        }
    }
    return $null
}

function Invoke-RmsPython([string[]]$ScriptAndArgs) {
    $py = Find-RmsPython
    if (-not $py) {
        Write-Host "Python 3 not installed (or not on PATH - Microsoft Store stub only)."
        Write-Host "Install: winget install --id Python.Python.3.12 -e --source winget"
        Write-Host "  or https://www.python.org/downloads/  (check 'Add python.exe to PATH')"
        Write-Host "Then open a NEW terminal. Disable App execution aliases for python.exe if needed:"
        Write-Host "  Settings -> Apps -> Advanced app settings -> App execution aliases"
        exit 1
    }
    & $py.Exe @($py.Args + $ScriptAndArgs)
    exit $LASTEXITCODE
}
