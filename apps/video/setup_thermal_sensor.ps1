# One-time administrator setup, then a read-only background sensor broker.
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$out = Join-Path $root 'data/local/thermal'
New-Item -ItemType Directory -Force -Path $out | Out-Null
try {
    if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Administrator approval is required for CPU hardware sensors.' }
    if (-not (Get-Service -Name PawnIO -ErrorAction SilentlyContinue)) {
        $installer = Join-Path $root '.tools/thermal/PawnIO_setup.exe'
        $sig = Get-AuthenticodeSignature -LiteralPath $installer
        if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'CN=namazso.eu') { throw 'Unexpected PawnIO installer signature; installation blocked.' }
        $install = Start-Process -FilePath $installer -ArgumentList '-install' -WindowStyle Hidden -Wait -PassThru
        if ($install.ExitCode -ne 0) { throw "PawnIO setup exited $($install.ExitCode)" }
    }
    $shell = Join-Path $env:WINDIR 'System32/WindowsPowerShell/v1.0/powershell.exe'
    $sensor = Join-Path $root 'apps/video/thermal_sensor.ps1'
    Start-Process -FilePath $shell -ArgumentList '-NoProfile','-File',("`"{0}`"" -f $sensor) -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $out 'sensor.stdout.log') -RedirectStandardError (Join-Path $out 'sensor.stderr.log') | Out-Null
    'CPU sensor broker launched' | Set-Content -LiteralPath (Join-Path $out 'setup.log')
} catch {
    $_.Exception.ToString() | Set-Content -LiteralPath (Join-Path $out 'setup.log')
    throw
}
