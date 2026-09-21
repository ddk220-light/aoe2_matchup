# Execute only the explicit storage plan. Native PowerShell handles copying,
# verification, deletion, and junction creation end to end.
param([string]$PlanFile='plan.json',[string]$StatusFile='status.json')
$ErrorActionPreference = 'Stop'
$repo = 'C:\dev\aoe2\aoe2_matchup'
$archive = 'D:\AoE2 Renders'
$work = Join-Path $repo 'data\local\storage-consolidation-20260916'
$plan = Get-Content -LiteralPath (Join-Path $work $PlanFile) -Raw | ConvertFrom-Json
if ($plan.sourceRoot -ne $repo -or $plan.destinationRoot -ne $archive) { throw 'Unexpected plan roots' }
$log = Join-Path $work 'receipts.jsonl'
$verified = @{}
$archiveChecks = @{}
$pruned = [long]0; $moved = [long]0; $done = 0; $issues = [System.Collections.Generic.List[object]]::new()
function Boundary($path, $root) {
    $absolute = [IO.Path]::GetFullPath($path)
    if (-not $absolute.StartsWith($root.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)) { throw "Outside approved root: $absolute" }
    return $absolute
}
function Event($row) {
    $row.at = (Get-Date).ToUniversalTime().ToString('o')
    $row | ConvertTo-Json -Depth 12 -Compress | Add-Content -LiteralPath $log
}
function Status($state,$current) {
    @{state=$state;current=$current;pid=$PID;prunedBytes=$pruned;movedBytes=$moved;completedPackages=$done;totalPackages=$plan.moves.Count;issues=$issues;updatedAt=(Get-Date).ToUniversalTime().ToString('o')} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work $StatusFile)
}
function CheckFile($entry) {
    $path = [IO.Path]::GetFullPath($entry.path)
    if (-not ($path.StartsWith($repo+'\',[StringComparison]::OrdinalIgnoreCase) -or $path.StartsWith($archive+'\',[StringComparison]::OrdinalIgnoreCase))) { throw 'Guard outside storage roots' }
    $f=Get-Item -LiteralPath $path
    $key=$path+'|'+$f.Length+'|'+$f.LastWriteTimeUtc.Ticks
    if ($f.Length -ne [long]$entry.bytes) { throw "Guard size mismatch: $path" }
    if (-not $verified.ContainsKey($key)) {
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $entry.sha256) { throw "Guard checksum mismatch: $path" }
        $verified[$key]=$true
    }
}
function CheckArchive($index) {
    if ($archiveChecks.ContainsKey($index)) { return }
    $index=Boundary $index $archive
    $o=Get-Content -LiteralPath $index -Raw | ConvertFrom-Json
    foreach ($matchup in $o.matchups) {
        foreach ($prop in $matchup.files.PSObject.Properties) {
            $e=$prop.Value
            $p=Boundary (Join-Path (Split-Path $index) $e.path) $archive
            if ((Get-Item -LiteralPath $p).Length -ne [long]$e.bytes) { throw "Archived render input absent: $p" }
        }
    }
    # Existing archive has its original checksum receipt. This size/presence
    # check only authorizes removal of derived renders, never the archived raw.
    $archiveChecks[$index]=$true
}
function PhysicalFiles($root) {
    $queue=[System.Collections.Generic.Queue[string]]::new(); $queue.Enqueue($root)
    while($queue.Count) {
        $dir=$queue.Dequeue()
        foreach($item in Get-ChildItem -LiteralPath $dir -Force) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
            if ($item.PSIsContainer) { $queue.Enqueue($item.FullName) } else { $item }
        }
    }
}
foreach($row in $plan.prunes) {
    try {
        $root=if($row.path.StartsWith('D:')){$archive}else{$repo}
        $path=Boundary $row.path $root
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        $item=Get-Item -LiteralPath $path
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Prune path is a link' }
        if ($item.Length -ne [long]$row.bytes) { throw 'Prune file changed after planning' }
        Status 'VERIFYING_RETAINED_SOURCES' $path
        foreach($guard in $row.guards) { CheckFile $guard }
        foreach($index in $row.archiveGuards) { CheckArchive $index }
        if (-not $row.guards.Count -and -not $row.archiveGuards.Count) { throw 'Unguarded removal prohibited' }
        Event @{action='prune-authorized';path=$path;bytes=$row.bytes;reason=$row.reason;guards=$row.guards;archiveGuards=$row.archiveGuards}
        Remove-Item -LiteralPath $path -Force
        $pruned += [long]$row.bytes
        Event @{action='pruned';path=$path;bytes=$row.bytes}
    } catch {
        $issues.Add(@{action='prune';path=$row.path;error=$_.Exception.Message})
        Event @{action='prune-skipped';path=$row.path;error=$_.Exception.Message}
    }
}
foreach($row in $plan.moves) {
    try {
        $src=Boundary $row.source $repo; $dst=Boundary $row.destination $archive
        $item=Get-Item -LiteralPath $src
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
        $files=@(PhysicalFiles $src)
        $needed=[long]0
        foreach($f in $files) {
            $relative=$f.FullName.Substring($src.Length).TrimStart('\')
            if(-not (Test-Path -LiteralPath (Join-Path $dst $relative))) {$needed+=$f.Length}
        }
        if((Get-PSDrive D).Free -lt ($needed+[long]$plan.reserveBytes)) { throw 'External disk reserve reached; original retained' }
        New-Item -ItemType Directory -Path $dst -Force | Out-Null
        Status 'COPYING_AND_HASH_VERIFYING' $src
        $checks=[System.Collections.Generic.List[object]]::new()
        foreach($f in $files) {
            $relative=$f.FullName.Substring($src.Length).TrimStart('\')
            $target=Boundary (Join-Path $dst $relative) $dst
            New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($target)) -Force | Out-Null
            $hash=(Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
            if(-not (Test-Path -LiteralPath $target)) {
                $partial=$target+'.consolidating'
                Copy-Item -LiteralPath $f.FullName -Destination $partial -Force
                if((Get-Item -LiteralPath $partial).Length -ne $f.Length -or (Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash -ne $hash) {throw "Copy verification failed: $target"}
                Move-Item -LiteralPath $partial -Destination $target
            } elseif ((Get-Item -LiteralPath $target).Length -ne $f.Length -or (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $hash) {throw "Destination conflict: $target"}
            $now=Get-Item -LiteralPath $f.FullName
            if($now.Length -ne $f.Length -or $now.LastWriteTimeUtc -ne $f.LastWriteTimeUtc) {throw 'Source changed during transfer'}
            $checks.Add(@{relative=$relative;bytes=$f.Length;sha256=$hash})
        }
        $after=@(PhysicalFiles $src)
        if($after.Count -ne $files.Count) {throw 'Source file set changed during transfer'}
        $receiptName=($src.Substring($repo.Length).TrimStart('\') -replace '[\\/:]','_')+'.json'
        @{source=$src;destination=$dst;verifiedAt=(Get-Date).ToUniversalTime().ToString('o');files=$checks} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work $receiptName)
        # Explicit absolute boundaries verified above. PowerShell removes the
        # source directory itself; archive is a distinct, already verified tree.
        $src=Boundary $src $repo; $dst=Boundary $dst $archive
        Remove-Item -LiteralPath $src -Recurse -Force
        New-Item -ItemType Junction -Path $src -Target $dst | Out-Null
        # Windows PowerShell 5.1 does not expose hashtable keys as properties
        # to Measure-Object. Sum explicitly after the durable receipt is saved.
        $bytes=[long]0
        foreach($check in $checks) { $bytes += [long]$check.bytes }
        $moved += [long]$bytes; $done++
        Event @{action='transferred';source=$src;destination=$dst;bytes=$bytes;files=$checks.Count;receipt=$receiptName}
    } catch {
        $issues.Add(@{action='move';source=$row.source;error=$_.Exception.Message})
        Event @{action='move-skipped';source=$row.source;error=$_.Exception.Message}
    }
}
Status $(if($issues.Count){'COMPLETE_WITH_EXCEPTIONS'}else{'COMPLETE'}) $null
