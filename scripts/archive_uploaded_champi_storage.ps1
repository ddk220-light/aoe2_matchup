# Archive only the reviewed uploaded-package plan. Keep original logical paths
# as junctions after copy/hash verification; never remove an unverified source.
$ErrorActionPreference = 'Stop'
$repo = 'C:\dev\aoe2\aoe2_matchup'
$work = Join-Path $repo 'data\local\champi-standard-comparison'
$plan = Get-Content -LiteralPath (Join-Path $work 'archive-plan.json') -Raw | ConvertFrom-Json
# Require capacity for the entire outstanding plan before any copy or removal.
# A per-package check alone can leave a large archive partially transferred.
$remainingBytes = [long]0
foreach ($entry in $plan.directories) {
    $item = Get-Item -LiteralPath $entry.source
    if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        $remainingBytes += [long]$entry.bytes
    }
}
if ((Get-PSDrive D).Free -lt ($remainingBytes + 2GB)) {
    throw 'Insufficient capacity for the complete archive; originals retained. Resolve capacity and review the plan before starting.'
}
$sourceRoot = [IO.Path]::GetFullPath($plan.sourceRoot).TrimEnd('\') + '\'
$destinationRoot = [IO.Path]::GetFullPath($plan.destinationRoot).TrimEnd('\') + '\'
if ($sourceRoot -ne "$repo\aoe2x\js_simulation\calibration\lab\" -or -not $destinationRoot.StartsWith('D:\AoE2 Archive\')) { throw 'Unexpected archive roots' }
$completed = 0
$movedBytes = [long]0
$receiptDir = Join-Path $work 'archive-receipts'
New-Item -ItemType Directory -Path $receiptDir -Force | Out-Null
function Save-Status($state, $current, $reason) {
    @{state=$state;pid=$PID;completed=$completed;total=$plan.directories.Count;movedBytes=$movedBytes;current=$current;reason=$reason;updatedAt=(Get-Date).ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $work 'archive-status.json')
}
foreach ($row in $plan.directories) {
    $src = [IO.Path]::GetFullPath($row.source)
    $dst = [IO.Path]::GetFullPath($row.destination)
    if (-not $src.StartsWith($sourceRoot,[StringComparison]::OrdinalIgnoreCase) -or -not $dst.StartsWith($destinationRoot,[StringComparison]::OrdinalIgnoreCase)) { throw 'Archive target escaped approved roots' }
    $sourceItem = Get-Item -LiteralPath $src
    if ($sourceItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        if ($sourceItem.LinkType -eq 'Junction' -and [IO.Path]::GetFullPath($sourceItem.Target) -eq $dst) { $completed++; $movedBytes += [long]$row.bytes; continue }
        throw "Unexpected source link: $src"
    }
    if ((Get-PSDrive D).Free -lt ([long]$row.bytes + 2GB)) { Save-Status 'WAITING_FOR_SPACE' $src 'External drive needs more free space; source retained'; exit 2 }
    Save-Status 'COPYING_AND_VERIFYING' $src $null
    $files = @(Get-ChildItem -LiteralPath $src -Recurse -File -Force)
    if (@(Get-ChildItem -LiteralPath $src -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { throw "Nested link in $src" }
    New-Item -ItemType Directory -Path $dst -Force | Out-Null
    $verified = @()
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($src.Length).TrimStart('\')
        $target = [IO.Path]::GetFullPath((Join-Path $dst $relative))
        if (-not $target.StartsWith($dst+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'File target escaped package' }
        New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($target)) -Force | Out-Null
        $sourceHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        if (-not (Test-Path -LiteralPath $target)) { Copy-Item -LiteralPath $file.FullName -Destination $target }
        $copy = Get-Item -LiteralPath $target
        if ($copy.Length -ne $file.Length -or (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $sourceHash) { throw "Archive mismatch; original kept: $target" }
        if ((Get-Item -LiteralPath $file.FullName).LastWriteTimeUtc -ne $file.LastWriteTimeUtc) { throw 'Source changed during copy' }
        $verified += @{relative=$relative;bytes=$file.Length;sha256=$sourceHash}
    }
    if (@(Get-ChildItem -LiteralPath $src -Recurse -File -Force).Count -ne $files.Count) { throw 'Source file set changed during copy' }
    $receipt = Join-Path $receiptDir (($src.Substring($sourceRoot.Length) -replace '[\\/:]','_')+'.json')
    @{source=$src;destination=$dst;files=$verified;evidence=$row.evidence;verifiedAt=(Get-Date).ToUniversalTime().ToString('o')} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $receipt
    # Both absolute boundaries were checked above. No computed shell commands.
    Remove-Item -LiteralPath $src -Recurse -Force
    New-Item -ItemType Junction -Path $src -Target $dst | Out-Null
    $completed++; $movedBytes += [long]$row.bytes
    Save-Status 'RUNNING' $null $null
}
Save-Status 'COMPLETE' $null $null
