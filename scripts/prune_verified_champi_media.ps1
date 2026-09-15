# Remove only exact media files from the reviewed compact-copy manifest.
# No recursive deletes, no removal of metadata or unrelated campaigns.
$ErrorActionPreference='Stop'
$repo='C:\dev\aoe2\aoe2_matchup'
$work=Join-Path $repo 'data\local\compact-storage'
$plan=Get-Content -LiteralPath (Join-Path $work 'champi-media-cleanup-plan.json') -Raw | ConvertFrom-Json
$state=Get-Content -LiteralPath (Join-Path $repo 'data\local\champi-standard-comparison\capture\status.json') -Raw | ConvertFrom-Json
if($state.state -ne 'COMPLETE' -or $state.completed -ne 296 -or $state.failed -ne 0){throw 'Captures must be complete'}
if($plan.files.Count -ne 888 -or $plan.recursiveDelete){throw 'Unexpected cleanup manifest'}
$verified=@{}
$deleted=0
$bytes=[long]0
foreach($row in $plan.files){
 $source=[IO.Path]::GetFullPath($row.source)
 if($row.jobId -notmatch '^champi_standard_(incas|mapuche|muisca|tupi)_'){throw 'Unexpected job'}
 $civ=$Matches[1]
 $run="$repo\aoe2x\js_simulation\calibration\lab\runs\$($row.jobId)\live\run_001"
 if(-not $source.StartsWith($run+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Source escaped run'}
 if($source -notmatch '(\.mov|\.mp4|\.frames\.bin)$'){throw 'Unexpected media extension'}
 foreach($proof in $row.replacements){
  $target=[IO.Path]::GetFullPath($proof.path)
  if(-not $target.StartsWith("D:\AoE2 Renders\champi-standard-$civ\",[StringComparison]::OrdinalIgnoreCase)){throw 'Unexpected archive target'}
  if(-not $verified.ContainsKey($target)){
   if((Get-Item -LiteralPath $target).Length -ne $proof.bytes -or (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $proof.sha256){throw 'Archive verification failed; originals retained'}
   $verified[$target]=$true
  }
 }
 if(Test-Path -LiteralPath $source){
  $item=Get-Item -LiteralPath $source
  if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Refusing linked source'}
  if($item.Length -ne $row.bytes -or (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $row.sha256){throw 'Source changed; retained'}
  @{index="D:/AoE2 Renders/champi-standard-$civ/run.json";jobId=$row.jobId;restoreTool='apps/video/materialize_compact_recording.py'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $run 'archived.json')
  Remove-Item -LiteralPath $source
  $bytes += [long]$row.bytes
  $deleted++
 }
 @{state='RUNNING';deleted=$deleted;freedBytes=$bytes;total=$plan.files.Count;current=$source;pid=$PID} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $work 'champi-cleanup-status.json')
}
@{state='COMPLETE';deleted=$deleted;freedBytes=$bytes;total=$plan.files.Count;pid=$PID} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $work 'champi-cleanup-status.json')
