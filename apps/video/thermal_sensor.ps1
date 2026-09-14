# Read-only CPU sensor broker. Run with Windows PowerShell 5.1 as administrator.
param([switch]$Once)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$out = Join-Path $root 'data/local/thermal'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$mutex = New-Object Threading.Mutex($false, 'Local\AoE2LabThermalSensor')
if (-not $mutex.WaitOne(0)) { exit 0 }
$computer = $null
try {
    [Reflection.Assembly]::LoadFrom((Join-Path $root '.tools/thermal/lhm-0.9.6/LibreHardwareMonitorLib.dll')) | Out-Null
    $computer = New-Object LibreHardwareMonitor.Hardware.Computer
    $computer.IsCpuEnabled = $true
    $computer.Open()
    do {
        $sensors = @()
        foreach ($hw in $computer.Hardware) {
            $hw.Update()
            if ($hw.HardwareType.ToString() -eq 'Cpu') {
                foreach ($sensor in $hw.Sensors) {
                    if ($sensor.SensorType.ToString() -eq 'Temperature' -and $sensor.Name -notmatch 'Distance to TjMax' -and $null -ne $sensor.Value) {
                        $sensors += @{ name=$sensor.Name; id=$sensor.Identifier.ToString(); celsius=[double]$sensor.Value }
                    }
                }
            }
        }
        $sample = @{timestamp=[DateTimeOffset]::UtcNow.ToString('o'); pid=$PID; sensors=$sensors; source='LibreHardwareMonitor 0.9.6 CPU core/package sensors'}
        $sample | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $out 'cpu.tmp.json')
        Move-Item -LiteralPath (Join-Path $out 'cpu.tmp.json') -Destination (Join-Path $out 'cpu.json') -Force
        if (-not $Once) { Start-Sleep -Seconds 5 }
    } while (-not $Once)
} catch {
    @{timestamp=[DateTimeOffset]::UtcNow.ToString('o'); error=$_.Exception.Message; sensors=@()} | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $out 'cpu.json')
    throw
} finally {
    if ($computer) { $computer.Close() }
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
