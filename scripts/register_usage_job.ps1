<#
.SYNOPSIS
    Register the daily usage report as a Windows scheduled task.

.DESCRIPTION
    Creates a scheduled task that runs scripts/usage_report.py at 00:00
    Europe/Zagreb every day. The script writes docs/usage/YYYY-MM-DD.md.

    Runs as a Python script on the Windows scheduler now; moves to the
    Hetzner host after Monday's cutover. No n8n.

.PARAMETER DryRun
    Show what would be registered without creating the task.

.EXAMPLE
    .\scripts\register_usage_job.ps1
    .\scripts\register_usage_job.ps1 -DryRun
#>
param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$taskName = "ResonateOS-DailyUsageReport"
$scriptDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$reportScript = Join-Path $scriptDir "scripts\usage_report.py"

# 00:00 Europe/Zagreb. Windows Task Scheduler runs in local time, so we
# set the trigger to 00:00 and rely on the machine's timezone being set
# to Europe/Zagreb. If the machine is in a different timezone, the task
# will fire at the wrong wall-clock time and the operator must adjust.
$triggerTime = New-ScheduledTaskTrigger -Daily -At "00:00"

# The action: py -3 scripts/usage_report.py
# We use `py -3` because that is the documented Python launcher on this
# Windows machine. The working directory is the repository root.
$action = New-ScheduledTaskAction -Execute "py" `
    -Argument "-3 scripts/usage_report.py" `
    -WorkingDirectory $scriptDir

# Settings: start on demand, run whether or not the user is logged on,
# stop if running longer than 1 hour (a report that takes an hour is
# stuck), and start immediately if the scheduled time was missed.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

# The principal: run as the current user. We do not request elevated
# privileges - git commit and push need only the user's own credentials.
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive

if ($DryRun) {
    Write-Host "DRY RUN - would register:"
    Write-Host "  Task name:    $taskName"
    Write-Host "  Script:       $reportScript"
    Write-Host "  Trigger:      Daily at 00:00 (Europe/Zagreb local time)"
    Write-Host "  Action:       py -3 scripts/usage_report.py"
    Write-Host "  Working dir:  $scriptDir"
    Write-Host "  Time limit:   1 hour"
    Write-Host ""
    Write-Host "To register for real, run without -DryRun."
    exit 0
}

# Remove any existing task with the same name
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing task: $taskName"
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Register the new task
Register-ScheduledTask -TaskName $taskName `
    -Trigger $triggerTime `
    -Action $action `
    -Settings $settings `
    -Principal $principal `
    -Description "Daily provider usage and balance report. Writes docs/usage/YYYY-MM-DD.md."

Write-Host ""
Write-Host "Registered: $taskName"
Write-Host "  Next run:  $((Get-ScheduledTask -TaskName $taskName).Triggers | Select-Object -ExpandProperty StartBoundary)"
Write-Host "  Script:    $reportScript"
Write-Host ""
Write-Host "Verify with:  Get-ScheduledTask -TaskName '$taskName' | Format-List"
Write-Host "Run now with: Start-ScheduledTask -TaskName '$taskName'"
