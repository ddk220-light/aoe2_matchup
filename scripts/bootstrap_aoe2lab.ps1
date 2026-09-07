[CmdletBinding()]
param(
    [string]$Python = "",
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvRoot = Join-Path $repoRoot "apps\video\.venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$configPath = Join-Path $repoRoot "aoe2lab.toml"

function Test-PythonLauncher([string]$Candidate) {
    if (-not $Candidate -or -not (Test-Path -LiteralPath $Candidate)) {
        return $false
    }
    try {
        & $Candidate -c "import sys; assert sys.version_info >= (3, 10)" 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Get-ConfiguredPythons {
    if (-not (Test-Path -LiteralPath $configPath)) {
        return $null
    }
    $section = ""
    $configured = @{}
    foreach ($line in Get-Content -LiteralPath $configPath) {
        if ($line -match '^\s*\[([^]]+)\]\s*$') {
            $section = $Matches[1].Trim().ToLowerInvariant()
            continue
        }
        if ($section -eq "paths" -and $line -match '^\s*(bootstrap_python|python)\s*=\s*["'']([^"'']+)["'']') {
            $key = $Matches[1].ToLowerInvariant()
            $candidate = [Environment]::ExpandEnvironmentVariables($Matches[2])
            if (-not [IO.Path]::IsPathRooted($candidate)) {
                $candidate = Join-Path $repoRoot $candidate
            }
            $configured[$key] = [IO.Path]::GetFullPath($candidate)
        }
    }
    return $configured
}

function Resolve-BasePython {
    $candidates = @()
    if ($Python) { $candidates += $Python }
    $configured = Get-ConfiguredPythons
    if ($configured.bootstrap_python) { $candidates += $configured.bootstrap_python }
    if ($configured.python -and $configured.python -ne $venvPython) {
        $candidates += $configured.python
    }
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) { $candidates += $pythonCommand.Source }
    foreach ($candidate in $candidates) {
        if (Test-PythonLauncher $candidate) { return $candidate }
    }
    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand) {
        try {
            $resolved = (& py -3.12 -c "import sys; print(sys.executable)").Trim()
            if (Test-PythonLauncher $resolved) { return $resolved }
        } catch {}
    }
    throw "Python 3.10 or newer was not found. Rerun with -Python <path-to-python.exe>."
}

function New-Aoe2LabVenv {
    $basePython = Resolve-BasePython
    $venvConfig = Join-Path $venvRoot "pyvenv.cfg"
    if (Test-Path -LiteralPath $venvConfig) {
        # --upgrade rewrites the Windows launcher and pyvenv.cfg without first
        # deleting already-installed packages. This repairs a venv whose base
        # interpreter moved or was uninstalled.
        & $basePython -m venv --upgrade $venvRoot
    } else {
        & $basePython -m venv $venvRoot
    }
    if ($LASTEXITCODE -ne 0) { throw "Failed to create or repair $venvRoot" }
}

function Test-Aoe2LabRuntime {
    if (-not (Test-PythonLauncher $venvPython)) { return $false }
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

$venvHealthy = Test-PythonLauncher $venvPython
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

if (-not (Test-Path -LiteralPath $configPath)) {
    Copy-Item -LiteralPath (Join-Path $repoRoot "aoe2lab.example.toml") -Destination $configPath
    Write-Host "Created $configPath. Set the AoE2 scenario directory if auto-detection is unsuitable."
}

if (-not (Test-Aoe2LabRuntime)) {
    if ($SkipDependencyInstall) {
        throw "AOE2 Lab dependencies are incomplete; rerun without -SkipDependencyInstall."
    }
    throw "AOE2 Lab runtime validation failed after dependency installation."
}

Push-Location $repoRoot
try {
    & $venvPython -m aoe2x.lab.cli doctor --live
} finally {
    Pop-Location
}
