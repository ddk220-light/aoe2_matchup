# Complete the already-authorized background transfer with read-only verification
# and restoration of previously working nested archive links. No file deletion.
$ErrorActionPreference='Stop'
$repo='C:\dev\aoe2\aoe2_matchup'
$archive='D:\AoE2 Renders'
$work=Join-Path $repo 'data\local\storage-consolidation-20260916'
Set-Location -LiteralPath $repo
while($true) {
    try { $state=Get-Content -LiteralPath (Join-Path $work 'status.json') -Raw | ConvertFrom-Json } catch { Start-Sleep -Seconds 10; continue }
    if($state.state -like 'COMPLETE*') {break}
    if(-not(Get-Process -Id $state.pid -ErrorAction SilentlyContinue)) {throw 'Transfer worker exited without a completion state; originals and receipts retained'}
    Start-Sleep -Seconds 15
}
& "$repo\apps\video\.venv\Scripts\python.exe" "$repo\scripts\prepare_storage_conflict_retry.py" | Set-Content -LiteralPath (Join-Path $work 'conflict-retry-preparation.json')
if($LASTEXITCODE -ne 0){throw 'Conflict retry preparation failed'}
& "$repo\scripts\consolidate_recording_storage.ps1" -PlanFile 'conflict-retry-plan.json' -StatusFile 'conflict-retry-status.json'
$links=Get-Content -LiteralPath (Join-Path $work 'nested-links-before.json') -Raw | ConvertFrom-Json
$results=@()
foreach($link in $links) {
    if(-not $link.exists){continue}
    try {
        $destination=[IO.Path]::GetFullPath($link.destination)
        $target=$link.target
        if($target.StartsWith('\\?\')){$target=$target.Substring(4)}
        $target=[IO.Path]::GetFullPath($target)
        if(-not $destination.StartsWith($archive+'\',[StringComparison]::OrdinalIgnoreCase) -or -not $target.StartsWith($archive+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Nested link outside approved archive'}
        $package=Get-Item -LiteralPath $link.package
        if(-not ($package.Attributes -band [IO.FileAttributes]::ReparsePoint)){continue}
        $relative=$link.source.Substring($link.package.Length).TrimStart('\')
        $destination=[IO.Path]::GetFullPath((Join-Path ([string]$package.Target) $relative))
        if(-not $destination.StartsWith($archive+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Restored link outside archive'}
        if(-not(Test-Path -LiteralPath $target)){throw 'Previously available nested-link target is missing'}
        if(-not(Test-Path -LiteralPath $destination)) {
            New-Item -ItemType Directory -Path (Split-Path $destination) -Force | Out-Null
            if($link.directory){New-Item -ItemType Junction -Path $destination -Target $target | Out-Null}
            else {New-Item -ItemType SymbolicLink -Path $destination -Target $target | Out-Null}
        }
        $results+=@{destination=$destination;target=$target;state='AVAILABLE'}
    } catch {$results+=@{destination=$link.destination;state='NEEDS_REVIEW';error=$_.Exception.Message}}
}
$results | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work 'nested-links-after.json')
& "$repo\apps\video\.venv\Scripts\python.exe" "$repo\scripts\verify_storage_consolidation.py" | Set-Content -LiteralPath (Join-Path $work 'verification-output.txt')
if($LASTEXITCODE -ne 0){throw 'Final transfer verification failed to run'}
& "$repo\apps\video\.venv\Scripts\python.exe" "$repo\scripts\audit_retained_capture_media.py" | Set-Content -LiteralPath (Join-Path $work 'inventory-output.json')
if($LASTEXITCODE -ne 0){throw 'Final recording inventory failed to run'}
& "$repo\apps\video\.venv\Scripts\python.exe" "$repo\scripts\report_storage_consolidation.py"
if($LASTEXITCODE -ne 0){throw 'Completion report failed'}
