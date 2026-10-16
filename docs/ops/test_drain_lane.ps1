<#
  test_drain_lane.ps1 - rotate a FIXTURE lane with DRAIN-LANE.ps1, in both
  states, and prove each one.

  ASCII ONLY, same reason as the files it tests.

  WHY A FIXTURE AND NOT A REAL LANE. qwen TASK 0180's boundaries: "Do not
  rotate, stop or restart any real lane in this task - build and prove, then
  hand over the command. Do not create STOP-ALL or any real STOP-<lane>
  outside your fixture." The entire estate travels with -Ops, so the fixture is
  a complete scratch estate in %TEMP% with its own queue, logs, LANE file,
  STOP files and tools directory. Real lane names are refused by name, the
  scratch root is asserted not to be the live one, and the STOP path is
  asserted to be outside the live estate before anything is written.

  THE ROTATION IS PROVED BY BYTE IDENTITY, NOT BY A BANNER. A rotation whose
  only evidence is "watcher up." proves a watcher started, not that the NEW
  bytes started. So the fixture deploys watcher v1 into the scratch tools
  directory, starts a lane on it, then OVERWRITES it with v2 - differing only
  in its -TaskTimeoutMinutes default, which the banner prints - and requires
  the post-rotation banner to carry v2's number and the pre-rotation banner to
  carry v1's. That is the same trick the real estate needs: on 2026-10-15 five
  of seven lanes ran the old 90-minute bytes for 38 minutes after the fix was
  deployed, and nothing said so.

  FOUR LEGS:
    1  DRY RUN on a working lane changes nothing at all
    2  rotate an IDLE lane
    3  rotate a WORKING lane - the task finishes, is recorded, is moved
    4  the fail-closed paths: a pre-existing STOP file, STOP-ALL, an
       unresolvable worktree, and an UNKNOWN state from a damaged pid lock
#>
param(
  [int]$WorkSeconds = 22,
  [switch]$KeepScratch
)

$ErrorActionPreference = "Stop"

$LiveOps   = "C:\Users\Zvonimir\Desktop\resonate-ops"
$Lane      = "rottest"
$RealLanes = @("glm", "glm-b", "glm-c", "pilotcaps", "qwen", "suppression", "webapp")
if ($RealLanes -contains $Lane) { Write-Host "REFUSING: real lane name."; exit 2 }

$RepoOps  = Split-Path -Parent $PSCommandPath
$Drain    = Join-Path $RepoOps "DRAIN-LANE.ps1"
$Watcher  = Join-Path $RepoOps "lane_watcher.ps1"
$TreeKill = Join-Path $RepoOps "lane_treekill.ps1"
$Refusal  = Join-Path $RepoOps "lane_refusal.ps1"
$FakeTask = Join-Path $RepoOps "fake_lane_task.ps1"
foreach ($f in @($Drain, $Watcher, $TreeKill, $Refusal, $FakeTask)) {
  if (-not (Test-Path -LiteralPath $f)) { Write-Host ("MISSING: " + $f); exit 2 }
}
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Write-Host "PRECONDITION UNMET: the watcher refuses to start without 'claude' on PATH."; exit 2
}

$Root       = Join-Path $env:TEMP ("lane-rot-" + [guid]::NewGuid().ToString("N").Substring(0, 12))
$ScratchOps = Join-Path $Root "ops"
$Wt         = Join-Path $Root "wt"
$Markers    = Join-Path $Root "markers"
$Queue      = Join-Path $ScratchOps ("queue\" + $Lane)
$Done       = Join-Path $Queue "DONE"
$Running    = Join-Path $Queue "RUNNING"
$LogDir     = Join-Path $ScratchOps "logs"
$WatchLog   = Join-Path $LogDir ("watcher-" + $Lane + ".log")
$LaneFile   = Join-Path $ScratchOps ("LANE-" + $Lane + ".md")
$StopMe     = Join-Path $ScratchOps ("STOP-" + $Lane)
$StopAll    = Join-Path $ScratchOps "STOP-ALL"
$LockFile   = Join-Path $LogDir ("watcher-" + $Lane + ".pid")
$ScratchTools = Join-Path $ScratchOps "tools"
$DeployedWatcher = Join-Path $ScratchTools "lane_watcher.ps1"

if ($ScratchOps.TrimEnd('\') -ieq $LiveOps.TrimEnd('\')) { Write-Host "REFUSING: scratch == live."; exit 2 }
if ($StopMe.ToLower().StartsWith($LiveOps.ToLower())) {
  Write-Host ("REFUSING: STOP path inside the live estate: " + $StopMe); exit 2
}
foreach ($d in @($Queue, $Done, $Running, $LogDir, $Markers, $ScratchTools, (Join-Path $Wt ".git"))) {
  New-Item -ItemType Directory -Path $d -Force | Out-Null
}
Set-Content -LiteralPath $LaneFile -Value ("# LANE-" + $Lane + " (scratch)") -Encoding UTF8
Copy-Item -LiteralPath $TreeKill -Destination (Join-Path $ScratchTools "lane_treekill.ps1") -Force
Copy-Item -LiteralPath $Refusal  -Destination (Join-Path $ScratchTools "lane_refusal.ps1") -Force

# The scratch START-ALL-LANES.ps1, so Resolve-LaneWorktree's AST read is
# exercised for real rather than bypassed with -Worktree.
Set-Content -LiteralPath (Join-Path $ScratchTools "START-ALL-LANES.ps1") -Encoding ASCII -Value @"
# SCRATCH copy, for test_drain_lane.ps1. Never started.
`$lanes = @(
  @{ Lane = "$Lane";  Worktree = "$Wt" }
)
"@

$fails  = New-Object System.Collections.ArrayList
$passes = 0
function Check($name, $ok, $detail) {
  if ($ok) { $script:passes++; Write-Host ("  PASS  " + $name + "   " + $detail) }
  else { [void]$script:fails.Add($name + " :: " + $detail); Write-Host ("  FAIL  " + $name + "   " + $detail) }
}
function LogText {
  if (-not (Test-Path -LiteralPath $WatchLog)) { return "" }
  for ($i = 1; $i -le 15; $i++) {
    try { return [System.IO.File]::ReadAllText($WatchLog) } catch { Start-Sleep -Milliseconds 150 }
  }
  return "<UNREADABLE>"
}
function WaitFor($pattern, $seconds, $what) {
  $end = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $end) {
    if ((LogText) -match $pattern) { return $true }
    Start-Sleep -Milliseconds 250
  }
  Write-Host ("  ... timed out after " + $seconds + "s waiting for " + $what); return $false
}
function WaitForFile($path, $seconds) {
  $end = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $end) { if (Test-Path -LiteralPath $path) { return $true }; Start-Sleep -Milliseconds 150 }
  return $false
}
function LivePids { @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like "*powershell*" } | ForEach-Object { $_.Id }) }

# THE TASK COMMAND AND THE TWO WATCHER VERSIONS -------------------------------
# v1 and v2 differ ONLY in the -TaskTimeoutMinutes DEFAULT, which the banner
# prints. That makes "which bytes are running" readable from the log, which is
# the thing the real estate could not answer.
$taskTemplate = '/c powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' +
                $FakeTask + '" -BriefPath "{BRIEF}" -MarkerDir "' + $Markers +
                '" -LaneFile "' + $LaneFile + '" -WorkSeconds ' + $WorkSeconds +
                ' < "{BRIEF}" > "{OUT}" 2>&1'

function DeployWatcher($timeoutDefault) {
  $src = [System.IO.File]::ReadAllText($Watcher)
  $old = '[double]$TaskTimeoutMinutes = 150,'
  $new = '[double]$TaskTimeoutMinutes = ' + $timeoutDefault + ','
  if ($src.IndexOf($old) -lt 0) { throw "could not find the timeout default to version the watcher" }
  $src = $src.Replace($old, $new)
  # Bake the scratch defaults in, so DRAIN-LANE.ps1 can start it with the same
  # argument list a real rotation uses (-Lane -Worktree -PermissionMode only).
  $src = $src.Replace('[string]$Ops = "C:\Users\Zvonimir\Desktop\resonate-ops",',
                      '[string]$Ops = "' + $ScratchOps + '",')
  $src = $src.Replace("'/c claude -p --permission-mode {MODE} < `"{BRIEF}`" > `"{OUT}`" 2>&1'",
                      "'" + $taskTemplate.Replace("'", "''") + "'")
  $src = $src.Replace('[int]$IdleSleepSeconds = 20,', '[int]$IdleSleepSeconds = 3,')
  [System.IO.File]::WriteAllText($DeployedWatcher, $src)
  $chk = [System.IO.File]::ReadAllText($DeployedWatcher)
  if ($chk.IndexOf($new) -lt 0) { throw "the versioned watcher did not read back" }
  if ($chk.IndexOf($ScratchOps) -lt 0) { throw "the scratch ops path did not read back" }
}

function Brief($name, $mode, $body) {
  $text = @(("# SCRATCH BRIEF - " + $name), ("MODE: " + $mode), "", $body) -join "`r`n"
  Set-Content -LiteralPath (Join-Path $Queue $name) -Encoding ASCII -Value $text
}

function RunDrain($extra) {
  $argv = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Drain,
            "-Lane", $Lane, "-Ops", $ScratchOps,
            "-WatcherPath", $DeployedWatcher,
            "-PermissionMode", "default",
            "-ProgressSeconds", "5",
            "-DrainTimeoutMinutes", "4",
            "-StartConfirmSeconds", "45")
  if ($extra) { $argv += $extra }
  $out = & powershell.exe @argv 2>&1
  return [pscustomobject]@{ Code = $LASTEXITCODE; Text = (($out | ForEach-Object { [string]$_ }) -join "`n") }
}

Write-Host ""
Write-Host "=== DRAIN-LANE.ps1 against a fixture lane =================================="
Write-Host ("scratch   " + $Root)
Write-Host ("work      " + $WorkSeconds + "s per task")
Write-Host ""

$w1 = $null
try {
  # =================================================================== LEG 0
  Write-Host "--- LEG 0  a lane that is DOWN --------------------------------------------"
  DeployWatcher 90
  Brief "0010-slow.md" "slowexit0" "Work, then complete cleanly."
  Brief "0020-slow.md" "slowexit0" "Work, then complete cleanly."
  Brief "0030-slow.md" "slowexit0" "Work, then complete cleanly."

  $d = RunDrain @()
  Check "DOWN is detected before anything exists" ($d.Text -match "STATE: DOWN") `
        "no lock, no log -> DOWN, and the dry run says so"
  Check "the dry run on a DOWN lane changes nothing" `
        ((-not (Test-Path -LiteralPath $LockFile)) -and (-not (Test-Path -LiteralPath $StopMe)) -and
         (@(Get-ChildItem -LiteralPath $Queue -Filter *.md).Count -eq 3)) `
        "no lock created, no STOP file, 3 briefs still queued"
  Check "the worktree was resolved from START-ALL-LANES.ps1 by AST" `
        ($d.Text -match "worktree resolved from START-ALL-LANES\.ps1: " + [regex]::Escape($Wt)) `
        "not copied into DRAIN-LANE, and not executed to get it"

  $d = RunDrain @("-Execute")
  Check "a DOWN lane starts, confirmed BY LOG CONTENT" ($d.Code -eq 0 -and $d.Text -match "CONFIRMED BY LOG CONTENT: watcher up\.") `
        "the launcher's own output is never the evidence"
  Check "and v1's bytes are identified in the banner" ($d.Text -match "timeout=90m") `
        "the banner names which bytes are running: v1 = 90 minutes"
  Check "it reports ROTATED" ($d.Text -match "ROTATED\.") ("exit " + $d.Code)

  # =================================================================== LEG 1
  Write-Host ""
  Write-Host "--- LEG 1  DRY RUN on a WORKING lane must change nothing ------------------"
  Check "a task is in flight" (WaitForFile (Join-Path $Markers "slowexit0.started") 40) "slowexit0.started exists"
  $lockBefore = (Get-Content -LiteralPath $LockFile -Raw).Trim()
  $logLenBefore = (LogText).Length
  $qBefore = (@(Get-ChildItem -LiteralPath $Queue -Filter *.md | ForEach-Object { $_.Name }) -join ",")

  $d = RunDrain @()
  Check "WORKING is detected" ($d.Text -match "STATE: WORKING") "pid live + a START with no closing verdict"
  Check "it names the open brief" ($d.Text -match "START 0010-slow\.md with no closing verdict") `
        "the authority is the log's control lines, not the RUNNING directory"
  Check "the dry run says DO NOT STOP ANYTHING" ($d.Text -match "PLAN: DO NOT STOP ANYTHING") "and explains why"
  Check "DRY RUN wrote no STOP file" (-not (Test-Path -LiteralPath $StopMe)) "nothing was created"
  Check "DRY RUN left the same watcher running" `
        ((Get-Content -LiteralPath $LockFile -Raw).Trim() -eq $lockBefore) ("pid still " + $lockBefore)
  Check "DRY RUN left the queue alone" `
        ((@(Get-ChildItem -LiteralPath $Queue -Filter *.md | ForEach-Object { $_.Name }) -join ",") -eq $qBefore) $qBefore
  Check "DRY RUN exits 0" ($d.Code -eq 0) ("exit " + $d.Code)

  # =================================================================== LEG 2
  Write-Host ""
  Write-Host "--- LEG 2  rotate a WORKING lane onto v2, mid-task ------------------------"
  # v2 is deployed WHILE v1 is working, which is exactly the real situation.
  DeployWatcher 150
  Check "v2 is on disk while v1 is still running" `
        (([System.IO.File]::ReadAllText($DeployedWatcher)).Contains('[double]$TaskTimeoutMinutes = 150,')) `
        "the deployed bytes are now v2; the RUNNING bytes are still v1"
  Check "still mid-task" (-not (Test-Path -LiteralPath (Join-Path $Markers "slowexit0.finished"))) `
        "slowexit0.finished absent"
  $startedAt = (Get-Item -LiteralPath (Join-Path $Markers "slowexit0.started")).LastWriteTime

  $d = RunDrain @("-Execute")
  Check "the rotation succeeded" ($d.Code -eq 0 -and $d.Text -match "ROTATED\.") ("exit " + $d.Code)
  Check "it drained rather than killed" ($d.Text -match "drained: the watcher has exited and the pid lock is gone") `
        "no process was stopped by this script"
  Check "THE IN-FLIGHT TASK FINISHED" (Test-Path -LiteralPath (Join-Path $Markers "slowexit0.finished")) `
        "slowexit0.finished exists - the task was not abandoned"
  $finAt = (Get-Item -LiteralPath (Join-Path $Markers "slowexit0.finished")).LastWriteTime
  Check "and it finished after it started, during the drain" ($finAt -gt $startedAt) `
        ($startedAt.ToString("HH:mm:ss.fff") + " -> " + $finAt.ToString("HH:mm:ss.fff"))
  Check "its DONE line was written" ((LogText) -match "DONE  0010-slow\.md -> exit0") `
        "somebody was still there to record it"
  Check "its brief was MOVED to DONE" ((LogText) -match "MOVED 0010-slow\.md ->") "recorded and filed"
  Check "exactly one DONE entry for it" `
        (@(Get-ChildItem -LiteralPath $Done -Filter "*exit0-0010-slow.md").Count -eq 1) `
        ((@(Get-ChildItem -LiteralPath $Done -Filter *.md) | ForEach-Object { $_.Name }) -join ", ")
  Check "the STOP file was cleaned up" (-not (Test-Path -LiteralPath $StopMe)) `
        "DRAIN-LANE removes only the STOP file it created, and it did"
  Check "V2's BYTES ARE NOW RUNNING, by banner content" ($d.Text -match "timeout=150m") `
        "90m -> 150m in the lane's own log. THIS is what 2026-10-15 could not answer."
  Check "the new watcher also names its modules" ($d.Text -match "refusalmod=" -and $d.Text -match "treekill=") `
        "so the record says which classifier and which kill module this lane now runs"
  Check "nothing was lost from the queue" `
        (@(Get-ChildItem -LiteralPath $Queue -Filter *.md).Count -ge 1) `
        ((@(Get-ChildItem -LiteralPath $Queue -Filter *.md) | ForEach-Object { $_.Name }) -join ", ")

  # =================================================================== LEG 3
  Write-Host ""
  Write-Host "--- LEG 3  rotate an IDLE lane --------------------------------------------"
  # Drain the queue so the lane goes genuinely idle, then rotate again.
  foreach ($f in @(Get-ChildItem -LiteralPath $Queue -Filter *.md)) { Remove-Item -LiteralPath $f.FullName -Force }
  Check "the lane reaches idle" (WaitFor "idle: queue empty" ($WorkSeconds * 3 + 90) "the idle line") `
        "queue emptied and the watcher said so"
  DeployWatcher 42
  $d = RunDrain @()
  Check "IDLE is detected" ($d.Text -match "STATE: IDLE") "pid live, no open task in the log"
  $d = RunDrain @("-Execute")
  Check "the idle rotation succeeded" ($d.Code -eq 0 -and $d.Text -match "ROTATED\.") ("exit " + $d.Code)
  Check "v3's bytes came up" ($d.Text -match "timeout=42m") "150m -> 42m, confirmed by log content"

  # =================================================================== LEG 4
  Write-Host ""
  Write-Host "--- LEG 4  the fail-closed paths ------------------------------------------"
  # (a) a STOP file that is somebody else's
  Set-Content -LiteralPath $StopMe -Value "the operator's" -Encoding ASCII
  $d = RunDrain @("-Execute")
  Check "a pre-existing STOP file ABORTS, and is not removed" `
        ($d.Code -eq 4 -and $d.Text -match "will not remove a STOP file it did not create" -and
         (Test-Path -LiteralPath $StopMe)) `
        ("exit " + $d.Code + "; the file is still there, which is the point")
  Remove-Item -LiteralPath $StopMe -Force

  # (b) STOP-ALL
  Set-Content -LiteralPath $StopAll -Value "all stop" -Encoding ASCII
  $d = RunDrain @("-Execute")
  Check "STOP-ALL ABORTS before anything is touched" `
        ($d.Code -eq 4 -and $d.Text -match "STOP-ALL exists" -and -not (Test-Path -LiteralPath $StopMe)) `
        ("exit " + $d.Code + " - a replacement watcher would have exited immediately")
  Remove-Item -LiteralPath $StopAll -Force

  # (c) AND (c2) TWO GUARDS, AND THE FIRST RUN OF THIS HARNESS CONFLATED THEM.
  # It asserted that `-Lane nosuchlane` would abort with "Not guessing a path",
  # got exit 4 - the right code - and FAILED on the text, because an EARLIER
  # guard fired first: a lane with no queue directory is rejected before its
  # worktree is ever looked up. The code was right and the assertion was wrong.
  # The standing rules name this exactly: when something goes red, confirm that
  # the intended guard failed and that a DIFFERENT guard did not fire first.
  # So both are now asserted, in the order they actually fire.
  function TryDrainLane($laneName) {
    $argv = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Drain,
              "-Lane", $laneName, "-Ops", $ScratchOps, "-WatcherPath", $DeployedWatcher)
    $o = & powershell.exe @argv 2>&1
    return [pscustomobject]@{ Code = $LASTEXITCODE; Text = (($o | ForEach-Object { [string]$_ }) -join "`n") }
  }

  $r = TryDrainLane "nosuchlane"
  Check "a lane with no queue directory ABORTS first" `
        ($r.Code -eq 4 -and $r.Text -match "no queue directory for this lane at") `
        ("exit " + $r.Code + " - this guard fires BEFORE the worktree lookup")

  # Now a lane that HAS a queue directory but is absent from START-ALL-LANES, so
  # the worktree lookup is genuinely reached and genuinely fails.
  $orphanLane = "rotorphan"
  New-Item -ItemType Directory -Path (Join-Path $ScratchOps ("queue\" + $orphanLane)) -Force | Out-Null
  $r = TryDrainLane $orphanLane
  Check "an unresolvable worktree ABORTS rather than guessing a path" `
        ($r.Code -eq 4 -and $r.Text -match "Not guessing a path") `
        ("exit " + $r.Code + " - the queue exists, so the lookup ran and found nothing")
  Check "and it says which authority it consulted" `
        ($r.Text -match "from tools\\START-ALL-LANES\.ps1") `
        "the abort names the file it could not find the lane in"

  # (d) a damaged pid lock -> UNKNOWN -> abort. Measured against a REAL live
  # watcher, so the abort is proven not to disturb it.
  $goodLock = (Get-Content -LiteralPath $LockFile -Raw).Trim()
  Set-Content -LiteralPath $LockFile -Value "not-a-pid" -Encoding ASCII
  $d = RunDrain @("-Execute")
  Check "a damaged pid lock is UNKNOWN and ABORTS" `
        ($d.Code -eq 4 -and $d.Text -match "STATE: UNKNOWN" -and $d.Text -match "which is not a pid") `
        ("exit " + $d.Code + " - UNKNOWN never becomes idle and never becomes a rotation")
  Check "the abort wrote no STOP file" (-not (Test-Path -LiteralPath $StopMe)) "nothing was touched"
  Set-Content -LiteralPath $LockFile -Value $goodLock -Encoding ASCII
  Check "the live watcher survived every abort" `
        ([bool](Get-Process -Id ([int]$goodLock) -ErrorAction SilentlyContinue)) `
        ("pid " + $goodLock + " still running after four fail-closed aborts")

  # ------------------------------------------------------------------ cleanup
  Write-Host ""
  Write-Host "--- stopping the fixture lane ----------------------------------------------"
  Set-Content -LiteralPath $StopMe -Value "fixture teardown" -Encoding ASCII
  Check "the fixture lane stops cleanly" (WaitFor "watcher down\." 90 "'watcher down.'") "via its own STOP file"
}
catch {
  [void]$fails.Add("HARNESS ABORTED :: " + $_.Exception.Message + " @line " + $_.InvocationInfo.ScriptLineNumber)
}
finally {
  if (Test-Path -LiteralPath $LockFile) {
    $p = (Get-Content -LiteralPath $LockFile -Raw).Trim()
    if ($p -match '^\d+$' -and (Get-Process -Id ([int]$p) -ErrorAction SilentlyContinue)) {
      Write-Host ("cleanup: fixture watcher pid " + $p + " still alive; stopping it")
      try { Stop-Process -Id ([int]$p) -Force -ErrorAction SilentlyContinue } catch { }
    }
  }
  foreach ($f in @(Get-ChildItem -LiteralPath $Markers -Filter "*.pid" -ErrorAction SilentlyContinue)) {
    $v = (Get-Content -LiteralPath $f.FullName -Raw).Trim()
    if ($v -match '^\d+$' -and (Get-Process -Id ([int]$v) -ErrorAction SilentlyContinue)) {
      try { Stop-Process -Id ([int]$v) -Force -ErrorAction SilentlyContinue } catch { }
    }
  }
  Write-Host ""
  Write-Host "=== RESULT ================================================================="
  Write-Host ("  passed " + $passes + "   failed " + $fails.Count)
  foreach ($f in $fails) { Write-Host ("  FAILED: " + $f) }
  $keep = Join-Path $env:TEMP ("lane-rot-last-" + $Lane + ".log")
  try { Copy-Item -LiteralPath $WatchLog -Destination $keep -Force; Write-Host ("  log copied to " + $keep) } catch { }
  if ($KeepScratch) { Write-Host ("  scratch kept: " + $Root) }
  else { try { Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue } catch { } }
}

if ($fails.Count -gt 0) { exit 1 }
exit 0
