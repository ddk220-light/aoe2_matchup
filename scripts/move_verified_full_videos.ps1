# Bounded, verified file moves for the explicitly inventoried published masters.
# No recursive deletion. Requires capacity for the entire plan before starting.
$ErrorActionPreference = 'Stop'
$repo = 'C:\dev\aoe2\aoe2_matchup'
$work = Join-Path $repo 'data\local\compact-storage'
New-Item -ItemType Directory -Path $work -Force | Out-Null
$rows = Get-Content -LiteralPath (Join-Path $repo 'data\local\champi-standard-comparison\archive-uploaded-fulls.json') -Raw | ConvertFrom-Json
$root = "$repo\aoe2x\js_simulation\calibration\lab\compilations\"
$destinationRoot = 'D:\AoE2 Renders\'
$disk = Get-Partition -DriveLetter D | Get-Disk
if ($disk.FriendlyName -ne 'WD My Passport 0730' -or $disk.BusType -ne 'USB') { throw 'Expected external disk is not mounted' }
$total = [long]0
foreach ($row in $rows) { if(Test-Path -LiteralPath $row.path) { $total += (Get-Item -LiteralPath $row.path).Length } }
if ((Get-PSDrive D).Free -lt $total + 5GB) { throw 'Insufficient capacity for all masters plus reserve' }
$done = @()
foreach ($row in $rows) {
    $source = [IO.Path]::GetFullPath($row.path)
    if (-not $source.StartsWith($root,[StringComparison]::OrdinalIgnoreCase)) { throw 'Source outside reviewed compilations' }
    $parts = $source.Substring($root.Length).Split('\')
    if ($parts.Count -ne 3 -or $parts[1] -notlike 'final*') { throw 'Unexpected final-video layout' }
    $folder = Join-Path $destinationRoot ($parts[0] + '--' + $parts[1])
    $target = [IO.Path]::GetFullPath((Join-Path $folder $parts[2]))
    if (-not $target.StartsWith($destinationRoot,[StringComparison]::OrdinalIgnoreCase)) { throw 'Destination outside archive' }
    $receiptPath = Join-Path $work ($parts[0] + '--' + $parts[1] + '.json')
    if (-not (Test-Path -LiteralPath $source)) {
        if (Test-Path -LiteralPath $receiptPath) { $done += Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json; continue }
        throw "Missing source without verified receipt: $source"
    }
    $item = Get-Item -LiteralPath $source
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Source must be a regular file' }
    $bytes = $item.Length
    $hash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    @{state='COPYING';source=$source;destination=$target;completed=$done.Count;total=$rows.Count} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $work 'status.json')
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
    if (-not (Test-Path -LiteralPath $target)) {
        Copy-Item -LiteralPath $source -Destination ($target+'.partial')
        if ((Get-Item -LiteralPath ($target+'.partial')).Length -ne $bytes -or (Get-FileHash -LiteralPath ($target+'.partial') -Algorithm SHA256).Hash -ne $hash) { throw 'Copy verification failed; source retained' }
        Move-Item -LiteralPath ($target+'.partial') -Destination $target
    }
    if ((Get-Item -LiteralPath $target).Length -ne $bytes -or (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $hash) { throw 'Destination mismatch; source retained' }
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $hash) { throw 'Source changed during copy; retained' }
    $receipt = @{source=$source;destination=$target;bytes=$bytes;sha256=$hash;videoIds=$row.videoIds;verifiedAt=(Get-Date).ToUniversalTime().ToString('o');sourceRemoved=$false}
    $receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $receiptPath
    # Delete only this exact verified regular file; never remove a folder tree.
    Remove-Item -LiteralPath $source
    $receipt.sourceRemoved=$true
    $receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $receiptPath
    $done += $receipt
}
@{state='COMPLETE';completed=$done.Count;total=$rows.Count;files=$done} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $work 'status.json')
