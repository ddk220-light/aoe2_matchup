# Publish the golden data artifacts for a game build as a GitHub Release.
#
#   .\tools\publish_data_release.ps1 -Build 177723 [-BaselineDb D:\AI\matchup_baseline_177723.db]
#
# Creates/updates release tag data-v<build> on the current repo with:
#   - every committed golden artifact (data/golden/)
#   - the per-build civ_power_units JSON
#   - train_times.json (replay classifier sidecar)
#   - optionally the full matchup baseline DB, zipped (lives outside the repo)
param(
    [Parameter(Mandatory = $true)][string]$Build,
    [string]$BaselineDb = "",
    [string]$Repo = ""   # defaults to the current repo's origin
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$tag = "data-v$Build"
$assets = @(
    "data/golden/aoe2_reference.db",
    "data/golden/aoe2_units.db",
    "data/golden/derived_data.db",
    "data/golden/pool_scores.db",
    "data/golden/patches.db",
    "data/golden/civ_top_units.json",
    "data/golden/civ_power_units/$Build.json",
    "aoe2x/replay/train_times.json"
)
foreach ($a in $assets) {
    if (-not (Test-Path $a)) { throw "missing asset: $a" }
}

$tmpZip = $null
if ($BaselineDb -and (Test-Path $BaselineDb)) {
    $tmpZip = Join-Path $env:TEMP "matchup_baseline_$Build.zip"
    Write-Host "Zipping baseline $BaselineDb -> $tmpZip ..."
    Compress-Archive -Path $BaselineDb -DestinationPath $tmpZip -Force
    $assets += $tmpZip
}

$notes = @"
Golden data artifacts for AoE2:DE build $Build.

| Asset | What | Producer |
|---|---|---|
| aoe2_reference.db | fully-upgraded per-civ unit stats + audit trail | ``python -m aoe2x.dbgen.generate_reference`` |
| aoe2_units.db | flat unit_stats + unit_verifications | ``python -m aoe2x.dbgen.generate_main_db`` |
| derived_data.db | role/composite battle scores | ``python -m aoe2x.rank.derive_unit_rankings`` |
| pool_scores.db | multi-scale pool scores | ``python -m aoe2x.rank.derive_pool_scores`` |
| patches.db | per-build patch history | ``python -m aoe2x.batch.patch_pipeline`` |
| civ_power_units_$Build.json | advisor army rosters | ``best_units.save_civ_power_units`` |
| civ_top_units.json | per-civ top unit per line | ``python -m aoe2x.advisor.top_units`` |
| train_times.json | unit train times (replay classifier sidecar) | curated |
| matchup_baseline_$Build.zip (optional) | full multi-seed 1v1 matchup baseline (491k rows) | ``pypy3 -m aoe2x.batch.rebuild_matchup_baseline`` |

Regeneration runbooks: docs/architecture/runbooks.md. Schema/consumer map: data/golden/README.md.
"@

$repoArg = @()
if ($Repo) { $repoArg = @("--repo", $Repo) }

gh release view $tag @repoArg 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Release $tag exists - uploading assets (clobber)..."
    gh release upload $tag @assets --clobber @repoArg
} else {
    Write-Host "Creating release $tag ..."
    gh release create $tag @assets --title "Golden data - build $Build" --notes $notes @repoArg
}
if ($tmpZip) { Remove-Item $tmpZip -Confirm:$false }
Write-Host "Done: $tag"
