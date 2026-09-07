[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$LabArguments
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $repoRoot "apps\video\.venv\Scripts\python.exe"

function Test-LabRuntime {
    if (-not (Test-Path -LiteralPath $venvPython)) { return $false }
    try {
        Push-Location $repoRoot
        & $venvPython -c "import aoe2x, AoE2ScenarioParser, grpc, cv2, numpy, PIL, pydirectinput, pygetwindow" | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    } finally {
        Pop-Location
    }
}

if (-not (Test-LabRuntime)) {
    Write-Host "AOE2 Lab runtime is missing or stale; repairing it now..."
    & (Join-Path $PSScriptRoot "bootstrap_aoe2lab.ps1")
    if ($LASTEXITCODE -ne 0 -or -not (Test-LabRuntime)) {
        throw "AOE2 Lab runtime repair did not produce a usable environment."
    }
}

Push-Location $repoRoot
try {
    # AoE2ScenarioParser writes Unicode progress glyphs. Force a stable stream
    # encoding so Windows legacy console code pages cannot abort a live run.
    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONUTF8 = "1"
    & $venvPython -m aoe2x.lab.cli @LabArguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
