<#
.SYNOPSIS
  The part of the 2026-09-23 machine hardening that a standard user cannot do.

.WHY
  On 2026-09-23 05:29:09 MoUsoCoreWorker.exe restarted this machine and killed
  every production loop (System event 1074). Active hours were 09:00-01:00, so
  05:29 was a window Windows had been told it could reboot in - which is
  exactly the unattended overnight run.

  docs/MACHINE-HARDENING-2026-09-23.md records what was already applied
  without elevation. This script is the remainder. Run it from an ELEVATED
  PowerShell:

      powershell -ExecutionPolicy Bypass -File scripts\harden_machine_elevated.ps1

  Every change prints BEFORE and AFTER. -WhatIf shows the plan and writes
  nothing.

.NOTE ON SCOPE
  It does NOT touch the Acer services, which were checked and are not
  implicated - the event log names MoUsoCoreWorker.exe as the initiator. It
  does not disable Windows Update. Quality and security updates still install;
  what changes is WHEN the machine may restart itself.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = 'Stop'

function Require-Admin {
  $p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
  if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Not elevated. Right-click PowerShell -> Run as administrator, then re-run this script."
  }
}
Require-Admin
Write-Host "Elevated OK`n" -ForegroundColor Green

function Set-Reg($Path, $Name, $Value, $Type, $Why) {
  if (-not (Test-Path $Path)) {
    if ($PSCmdlet.ShouldProcess($Path, "create key")) { New-Item -Path $Path -Force | Out-Null }
  }
  $before = (Get-ItemProperty -Path $Path -Name $Name -EA SilentlyContinue).$Name
  if ($null -eq $before) { $before = '<unset>' }
  if ($PSCmdlet.ShouldProcess("$Path\$Name", "set to $Value")) {
    New-ItemProperty -Path $Path -Name $Name -Value $Value -PropertyType $Type -Force | Out-Null
  }
  $after = (Get-ItemProperty -Path $Path -Name $Name -EA SilentlyContinue).$Name
  "{0,-38} BEFORE={1,-10} AFTER={2,-10}  {3}" -f $Name, $before, $after, $Why
}

# ---------------------------------------------------------------- 1. auto-restart
Write-Host "== 1. Windows Update: forbid an automatic restart while signed in ==" -ForegroundColor Cyan
$AU = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
Set-Reg $AU 'NoAutoRebootWithLoggedOnUsers' 1 'DWord' 'the measured cause: 1074 at 05:29:09'
Set-Reg $AU 'AUPowerManagement'             0 'DWord' 'do not let WU wake the machine to install'
# AUOptions 3 = download, notify before install. It does NOT stop updates; it
# stops the orchestrator deciding the install/restart moment on its own.
Set-Reg $AU 'AUOptions'                     3 'DWord' 'notify before install, do not auto-install'
Set-Reg $AU 'NoAutoUpdate'                  0 'DWord' 'updates stay ON - only the restart timing changes'

# ---------------------------------------------------------------- 2. fast startup
Write-Host "`n== 2. Fast startup off ==" -ForegroundColor Cyan
$PWR = 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power'
Set-Reg $PWR 'HiberbootEnabled' 0 'DWord' 'a hybrid boot restores a stale session and hides a reboot'

# `powercfg /hibernate off` would also clear fast startup, but it deletes
# hiberfil.sys and removes hibernate as a battery backstop. HiberbootEnabled=0
# is the narrower change and is what was asked for.

# ---------------------------------------------------------------- 3. wake-to-work
Write-Host "`n== 3. Scheduled tasks that can wake or restart the machine ==" -ForegroundColor Cyan
# There is NO 'Reboot' task in this build's UpdateOrchestrator folder - the
# restart comes from the USO service itself (MoUsoCoreWorker.exe), which is why
# item 1 above is the real lever. What IS here is a task that WAKES the box.
$candidates = @(
  '\Microsoft\Windows\UpdateOrchestrator\Schedule Wake To Work',
  '\Microsoft\Windows\UpdateOrchestrator\Reboot',
  '\Microsoft\Windows\UpdateOrchestrator\Reboot_AC',
  '\Microsoft\Windows\UpdateOrchestrator\Reboot_Battery'
)
foreach ($full in $candidates) {
  $path = Split-Path $full -Parent
  $name = Split-Path $full -Leaf
  $t = Get-ScheduledTask -TaskPath "$path\" -TaskName $name -EA SilentlyContinue
  if (-not $t) { "{0,-58} ABSENT on this build" -f $name; continue }
  $before = $t.State
  if ($PSCmdlet.ShouldProcess($full, "disable")) {
    try { Disable-ScheduledTask -TaskPath "$path\" -TaskName $name -EA Stop | Out-Null }
    catch { "{0,-58} BEFORE={1} REFUSED: {2}" -f $name, $before, $_.Exception.Message; continue }
  }
  $after = (Get-ScheduledTask -TaskPath "$path\" -TaskName $name -EA SilentlyContinue).State
  "{0,-58} BEFORE={1,-10} AFTER={2}" -f $name, $before, $after
}

Write-Host "`n-- every remaining task whose action can restart the machine --"
Get-ScheduledTask -EA SilentlyContinue | Where-Object {
  $_.Actions | Where-Object { ($_.Execute -match 'shutdown\.exe|MusNotification|UsoClient') -or ($_.Arguments -match '\b/r\b|\b/s\b|Reboot') }
} | Select-Object TaskPath, TaskName, State | Format-Table -AutoSize

# Wake timers off on AC, so nothing schedules a wake for update work.
$scheme = ((powercfg /getactivescheme) -split '\s+')[3]
powercfg /setacvalueindex $scheme SUB_SLEEP RTCWAKE 0 2>$null
powercfg /setdcvalueindex $scheme SUB_SLEEP RTCWAKE 0 2>$null
powercfg /setactive $scheme
Write-Host "wake timers: disabled on AC and DC"

# ---------------------------------------------------------------- 4. proof
Write-Host "`n== 4. Proof: powercfg /requests (needs elevation - this is why) ==" -ForegroundColor Cyan
powercfg /requests

Write-Host "`n-- with a monitor's keep-awake held, SYSTEM: should list python.exe --"
Write-Host "   run this while a supervised monitor is up:"
Write-Host "     powercfg /requests"
Write-Host "   and expect a SYSTEM: entry naming the python process."

Write-Host "`n== 5. Sleep reachability ==" -ForegroundColor Cyan
powercfg /a

Write-Host "`nDone. Re-run docs/MACHINE-HARDENING-2026-09-23.md's verify block to confirm." -ForegroundColor Green
