[CmdletBinding()]
param(
    [string]$Python = "",
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvRoot = Join-Path $repoRoot "apps\video\.venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"

function New-Aoe2LabVenv {
    if ($Python) {
        & $Python -m venv --clear $venvRoot
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -m venv --clear $venvRoot
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv --clear $venvRoot
    } else {
        throw "Python 3.10 or newer was not found. Install Python, then rerun with -Python <path>."
    }
}

$venvHealthy = $false
if (Test-Path -LiteralPath $venvPython) {
    try {
        & $venvPython --version | Out-Null
        $venvHealthy = $LASTEXITCODE -eq 0
    } catch {
        $venvHealthy = $false
    }
}
if (-not $venvHealthy) {
    Write-Host "Creating or repairing the repository-local AOE2 Lab environment..."
    New-Aoe2LabVenv
}

& $venvPython -c "import sys; assert sys.version_info >= (3, 10), sys.version"
if (-not $SkipDependencyInstall) {
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -e $repoRoot
    & $venvPython -m pip install -r (Join-Path $repoRoot "aoe2x\lab\requirements-windows.txt")
}

$configPath = Join-Path $repoRoot "aoe2lab.toml"
if (-not (Test-Path -LiteralPath $configPath)) {
    Copy-Item -LiteralPath (Join-Path $repoRoot "aoe2lab.example.toml") -Destination $configPath
    Write-Host "Created $configPath. Set the AoE2 scenario directory if auto-detection is unsuitable."
}

Push-Location $repoRoot
try {
    & $venvPython -m aoe2x.lab.cli doctor --live
} finally {
    Pop-Location
}
