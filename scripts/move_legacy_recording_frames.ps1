# Move only the audited legacy capture files; never replace external contents.
param([string]$PlanName='legacy-transfer-plan.json', [string]$ReceiptPrefix='legacy-transfer')
$ErrorActionPreference='Stop'
$repo='C:\dev\aoe2\aoe2_matchup'
$work=Join-Path $repo 'data\local\storage-audit'
$plan=Get-Content -LiteralPath (Join-Path $work $PlanName) -Raw | ConvertFrom-Json
$sourceRoot=[IO.Path]::GetFullPath($plan.sourceRoot)
$destinationRoot=[IO.Path]::GetFullPath($plan.destinationRoot)
$allowedPairs=@{
    'C:\dev\aoe2\aoe2record\lab'='D:\AoE2 Renders\legacy-aoe2record-frames'
    'C:\dev\aoe2\aoe2_matchup'='D:\AoE2 Renders\remaining-local-media'
}
if ($allowedPairs[$sourceRoot] -ne $destinationRoot -or $ReceiptPrefix -notmatch '^[a-z-]+$') { throw 'Unexpected plan roots' }
if ((Get-Partition -DriveLetter D | Get-Disk).SerialNumber.Trim() -ne '00000107000079B6') { throw 'Wrong external disk' }
$moved=0L
$completed=0
foreach ($entry in $plan.files) {
    $source=[IO.Path]::GetFullPath($entry.source)
    $target=[IO.Path]::GetFullPath((Join-Path $destinationRoot $entry.relative))
    if (-not $source.StartsWith($sourceRoot+'\',[StringComparison]::OrdinalIgnoreCase) -or -not $target.StartsWith($destinationRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Escaped transfer path' }
    $item=Get-Item -LiteralPath $source
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        if ($item.Target -ne $target) { throw 'Unexpected existing link' }
        continue
    }
    if ($item.Length -ne $entry.bytes) { throw 'Source changed' }
    $hash=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
    if (-not (Test-Path -LiteralPath $target)) {
        $partial=$target+'.partial'
        if (Test-Path -LiteralPath $partial) { throw 'Existing partial requires inspection' }
        Copy-Item -LiteralPath $source -Destination $partial
        if ((Get-Item -LiteralPath $partial).Length -ne $entry.bytes -or (Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash -ne $hash) { throw 'Copy verification failed' }
        Move-Item -LiteralPath $partial -Destination $target
    }
    if ((Get-Item -LiteralPath $target).Length -ne $entry.bytes -or (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $hash) { throw 'External conflict; source retained' }
    # Create the compatibility link before deleting anything; lack of symlink
    # privileges leaves the original capture intact.
    $pendingLink=$source+'.archive-link'
    New-Item -ItemType SymbolicLink -Path $pendingLink -Target $target | Out-Null
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $hash) { throw 'Source changed during copy; retained' }
    @{source=$source;target=$target;bytes=$entry.bytes;sha256=$hash;phase='verified'} | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $work ($ReceiptPrefix+'-receipts.jsonl'))
    Remove-Item -LiteralPath $source
    Move-Item -LiteralPath $pendingLink -Destination $source
    $moved+=$entry.bytes
    $completed++
    @{state='MOVING';completed=$completed;bytesMoved=$moved} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $work ($ReceiptPrefix+'-status.json'))
}
@{state='COMPLETE';completed=$completed;bytesMoved=$moved} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $work ($ReceiptPrefix+'-status.json'))
