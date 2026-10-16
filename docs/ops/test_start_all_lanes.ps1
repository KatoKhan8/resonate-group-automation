<#
  test_start_all_lanes.ps1 - prove that the launcher's output is true.

  ASCII ONLY, same reason as the files it tests.

  WHY IT IS SAFE. Everything lives in %TEMP%. The lanes are called cameup,
  nogit, locked, unreadable, missing, stopped and silent - none of them is a
  lane, and the seven real names are refused by name before anything is created.
  The only STOP file this harness can write is under the scratch ops root,
  asserted below. No real lane is started, stopped or read for write. `claude`
  is never invoked: the watcher is reached through a wrapper that supplies
  -TaskCommandTemplate pointing at fake_lane_task.ps1.

  WHY A WRAPPER RATHER THAN -ExtraWatcherArgs. Start-Process -ArgumentList does
  not quote its elements, so a -TaskCommandTemplate (which is full of spaces)
  would be split into positional arguments and bind to the watcher's typed
  parameters - the failure that cost this estate a diagnosis earlier today,
  recorded in TASK-0200's report. So the fixture points the launcher at a small
  wrapper .ps1 per case; the wrapper receives -Lane/-Worktree/-PermissionMode
  from the launcher and forwards them to the real watcher with everything else
  quoted properly. -ExtraWatcherArgs stays unused here and is therefore NOT
  claimed to be tested.

  THE BAR, FROM THE TASK BRIEF:
    - a lane counts as started only on evidence it came up;
    - a lane that refuses is named with its reason, read back out of its log;
    - the totals distinguish started / refused / skipped / unknown;
    - ambiguity is UNKNOWN, never started;
    - the wait is bounded and the bound is stated.
#>
param(
  [int]$UpTimeoutSeconds = 12,
  [switch]$KeepScratch
)

$ErrorActionPreference = "Stop"

$LiveOps   = "C:\Users\Zvonimir\Desktop\resonate-ops"
$RealLanes = @("glm", "glm-b", "glm-c", "pilotcaps", "qwen", "suppression", "webapp")

$RepoOps  = Split-Path -Parent $PSCommandPath
$Launcher = Join-Path $RepoOps "START-ALL-LANES.ps1"
$Watcher  = Join-Path $RepoOps "lane_watcher.ps1"
$TreeKill = Join-Path $RepoOps "lane_treekill.ps1"
$Refusal  = Join-Path $RepoOps "lane_refusal.ps1"
$Orphan   = Join-Path $RepoOps "lane_orphan.ps1"
$FakeTask = Join-Path $RepoOps "fake_lane_task.ps1"
foreach ($f in @($Launcher, $Watcher, $TreeKill, $Refusal, $Orphan, $FakeTask)) {
  if (-not (Test-Path -LiteralPath $f)) { Write-Host ("MISSING: " + $f); exit 2 }
}
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Write-Host "PRECONDITION UNMET: the watcher refuses to start without 'claude' on PATH."
  exit 2
}

$Root       = Join-Path $env:TEMP ("lane-launch-" + [guid]::NewGuid().ToString("N").Substring(0, 12))
$ScratchOps = Join-Path $Root "ops"
if ($ScratchOps.ToLower().StartsWith($LiveOps.ToLower()) -or
    $ScratchOps.TrimEnd('\') -ieq $LiveOps.TrimEnd('\')) {
  Write-Host ("REFUSING: the scratch ops path is inside the live estate: " + $ScratchOps); exit 2
}
$LogDir  = Join-Path $ScratchOps "logs"
$Markers = Join-Path $Root "markers"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
New-Item -ItemType Directory -Path $Markers -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $ScratchOps "tools") -Force | Out-Null

$fails  = New-Object System.Collections.ArrayList
$passes = 0
function Check($name, $ok, $detail) {
  if ($ok) { $script:passes++; Write-Host ("  PASS  " + $name + "   " + $detail) }
  else { [void]$script:fails.Add($name + " :: " + $detail); Write-Host ("  FAIL  " + $name + "   " + $detail) }
}

function NewLane {
  param([string]$name, [switch]$NoGit, [switch]$NoPath)
  if ($RealLanes -contains $name) {
    Write-Host ("REFUSING: '" + $name + "' is a real lane name."); exit 2
  }
  $wt = Join-Path $Root ("wt-" + $name)
  if (-not $NoPath) {
    New-Item -ItemType Directory -Path $wt -Force | Out-Null
    if (-not $NoGit) { New-Item -ItemType Directory -Path (Join-Path $wt ".git") -Force | Out-Null }
  }
  $q = Join-Path $ScratchOps ("queue\" + $name)
  New-Item -ItemType Directory -Path (Join-Path $q "RUNNING") -Force | Out-Null
  New-Item -ItemType Directory -Path (Join-Path $q "DONE") -Force | Out-Null
  Set-Content -LiteralPath (Join-Path $ScratchOps ("LANE-" + $name + ".md")) `
              -Value ("# LANE-" + $name + " (scratch)") -Encoding UTF8
  return $wt
}

# A lane table file, which is how the launcher is pointed away from the estate.
function WriteLaneTable {
  param([string]$path, [hashtable[]]$rows)
  $q = [string][char]39
  $lines = New-Object System.Collections.ArrayList
  [void]$lines.Add("@(")
  for ($i = 0; $i -lt $rows.Count; $i++) {
    $r = $rows[$i]
    # NO TRAILING COMMA ON THE LAST ROW. It is not legal inside @( ) either -
    # "Missing expression after ','" - and the first run of this harness spent
    # all three cases on it, with the lane table failing to parse so the
    # launcher saw an empty table and exited 1 for the wrong reason.
    $tail = ","
    if ($i -eq $rows.Count - 1) { $tail = "" }
    [void]$lines.Add(("  @{ Lane = " + $q + $r.Lane + $q + "; Worktree = " +
                      $q + $r.Worktree + $q + " }" + $tail))
  }
  [void]$lines.Add(")")
  Set-Content -LiteralPath $path -Value $lines -Encoding ASCII
}

# The wrapper: receives the launcher's three arguments, forwards them with the
# scratch plumbing quoted properly.
function WriteWrapper {
  param([string]$path, [string]$mode = "forward")
  $q = [string][char]39
  $taskTemplate = '/c powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' +
                  $FakeTask + '" -BriefPath "{BRIEF}" -MarkerDir "' + $Markers +
                  '" -LaneFile "' + (Join-Path $ScratchOps "LANE-{LANE}.md") +
                  '" -WorkSeconds 5 < "{BRIEF}" > "{OUT}" 2>&1'
  if ($mode -eq "silent") {
    $lines = @(
      "param([string]`$Lane, [string]`$Worktree, [string]`$PermissionMode)",
      "# A watcher that starts and says NOTHING. The launcher must call this",
      "# UNKNOWN, never started.",
      "Start-Sleep -Seconds 600")
  } else {
    $lines = @(
      "param([string]`$Lane, [string]`$Worktree, [string]`$PermissionMode)",
      ("`$tpl = " + $q + $taskTemplate.Replace($q, $q + $q) + $q),
      ("`$tpl = `$tpl.Replace(" + $q + "{LANE}" + $q + ", `$Lane)"),
      ("& " + $q + $Watcher + $q + " -Lane `$Lane -Worktree `$Worktree " +
       "-PermissionMode `$PermissionMode -Ops " + $q + $ScratchOps + $q +
       " -TreeKillPath " + $q + $TreeKill + $q +
       " -RefusalModulePath " + $q + $Refusal + $q +
       " -OrphanModulePath " + $q + $Orphan + $q +
       " -TaskCommandTemplate `$tpl -TaskTimeoutMinutes 5 -IdleSleepSeconds 3"),
      "exit `$LASTEXITCODE")
  }
  Set-Content -LiteralPath $path -Value $lines -Encoding ASCII
}

# Stub watchers that write NOTHING and exit with a chosen code. These exercise
# the launcher's exit-code branch, which the REFUSING-line cases never reach -
# and which was measurably broken until the handle was captured.
function WriteExitStub {
  param([string]$path, [int]$code)
  # PARENTHESISED. FOURTH TIME TODAY. Without the brackets the comma binds
  # tighter than + and the three elements collapse into ONE line:
  #     param(...)
  #     # writes nothing anywhere, then exits 2 exit 2
  # - the `exit 2` ends up inside the comment, the stub exits 0, and leg C8 reads
  # "exited 0" for a stub that was supposed to exit 2. Worse, C9 (exit 0 ->
  # UNKNOWN) then PASSED for the wrong reason, because both stubs exited 0.
  Set-Content -LiteralPath $path -Encoding ASCII -Value @(
    ("param([string]`$Lane, [string]`$Worktree, [string]`$PermissionMode)"),
    ("# writes nothing anywhere, then exits " + $code),
    ("exit " + $code))
}

function RunLauncher {
  param([string]$tablePath, [string]$watcherPath, [int]$bound = $UpTimeoutSeconds)
  $outFile = Join-Path $Root ("launch-" + [guid]::NewGuid().ToString("N").Substring(0, 6) + ".txt")
  $wargs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Launcher,
             "-Ops", $ScratchOps, "-WatcherPath", $watcherPath,
             "-LaneTablePath", $tablePath, "-UpTimeoutSeconds", [string]$bound,
             "-PermissionMode", "acceptEdits")
  # NO -Wait, AND THIS IS NOT A STYLE CHOICE. Start-Process -Wait waits for the
  # whole PROCESS TREE, and a launcher that succeeds leaves a healthy watcher
  # running - so -Wait never returned and this harness ran past 420 seconds with
  # the launcher long finished. Measured 2026-10-16: the launcher's own output
  # file was complete and correct while the harness was still blocked on pid
  # 3568, the `cameup` watcher it had just proved was up. Poll the launcher's own
  # handle against a bound instead.
  $p = Start-Process -FilePath "powershell.exe" -ArgumentList $wargs `
         -NoNewWindow -PassThru -RedirectStandardOutput $outFile
  # Same handle capture, same reason: under 5.1 ExitCode is empty without it, and
  # the first run of this harness passed its exit-code legs on `null -ne 0`.
  $null = $p.Handle
  $end = (Get-Date).AddSeconds($bound + 60)
  while (-not $p.HasExited -and (Get-Date) -lt $end) { Start-Sleep -Milliseconds 200 }
  if (-not $p.HasExited) {
    Write-Host ("  ... the LAUNCHER itself did not exit within " + ($bound + 60) +
                "s; killing it. That is a harness timeout, not a verdict.")
    try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch { }
    Start-Sleep -Milliseconds 500
  }
  $code = 999
  try { $code = $p.ExitCode } catch { }
  $text = ""
  if (Test-Path -LiteralPath $outFile) {
    for ($i = 1; $i -le 10 -and $text -eq ""; $i++) {
      try { $text = Get-Content -LiteralPath $outFile -Raw } catch { Start-Sleep -Milliseconds 150 }
    }
  }
  if ($null -eq $text) { $text = "" }
  return [pscustomobject]@{ Code = $code; Out = $text }
}

function KillLaneWatchers {
  # Everything this harness started is a powershell whose command line names the
  # scratch root. Selection is by that string and nothing else is touched.
  foreach ($proc in @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                      Where-Object { $_.CommandLine -and $_.CommandLine -like ("*" + $Root + "*") })) {
    if ([int]$proc.ProcessId -eq $PID) { continue }
    try { Stop-Process -Id ([int]$proc.ProcessId) -Force -ErrorAction SilentlyContinue } catch { }
  }
}

$wrapper = Join-Path $Root "wrap.ps1"
$silent  = Join-Path $Root "wrap-silent.ps1"
WriteWrapper $wrapper "forward"
WriteWrapper $silent  "silent"

# ==========================================================================
Write-Host ""
Write-Host "C1-C3  a lane that comes up, one with no .git, one behind a live pid lock"

$wtUp     = NewLane "cameup"
$wtNoGit  = NewLane "nogit" -NoGit
$wtLocked = NewLane "locked"

# a live pid lock for the "locked" lane: a real, live powershell
$holder = Start-Process -FilePath "powershell.exe" `
            -ArgumentList @("-NoProfile", "-Command", "Start-Sleep -Seconds 300") `
            -NoNewWindow -PassThru
Start-Sleep -Milliseconds 400
Set-Content -LiteralPath (Join-Path $LogDir "watcher-locked.pid") -Value $holder.Id -Encoding ASCII
Check "C3 setup: the lock holder is alive" (
  [bool](Get-Process -Id $holder.Id -ErrorAction SilentlyContinue)
) ("pid " + $holder.Id)

$table1 = Join-Path $Root "lanes1.ps1"
WriteLaneTable $table1 @(
  @{ Lane = "cameup"; Worktree = $wtUp },
  @{ Lane = "nogit";  Worktree = $wtNoGit },
  @{ Lane = "locked"; Worktree = $wtLocked })
$r1 = RunLauncher $table1 $wrapper

Write-Host "  ---- launcher output ----"
foreach ($line in ($r1.Out -split "`r?`n")) { if ($line.Trim() -ne "") { Write-Host ("  | " + $line) } }
Write-Host "  -------------------------"

Check "C1 the healthy lane is STARTED" (
  $r1.Out -match "STARTED\s+cameup"
) "classified on its own watcher up line"
Check "C2 the lane with no .git is REFUSED" (
  $r1.Out -match "REFUSED\s+nogit"
) "classified as refused"
Check "C2 and its REASON is read back out of the log" (
  $r1.Out -match "no \.git here"
) "the watcher's own words are on the launcher's output"
Check "C3 the lane behind a live pid lock is REFUSED" (
  $r1.Out -match "REFUSED\s+locked"
) "classified as refused"
Check "C3 and its reason names the lock" (
  $r1.Out -match "a watcher for this lane is already running as pid"
) "the exit-3 reason is reported"
Check "C1-C3 the totals distinguish the classes" (
  $r1.Out -match "started=1\s+refused=2\s+skipped=0\s+unknown=0"
) "started=1 refused=2 skipped=0 unknown=0"
Check "C1-C3 the exit code is non-zero because two lanes are down" (
  ($r1.Code -eq 1) -and ($r1.Out -match "started=1\s+refused=2")
) ("exit " + $r1.Code + " WITH the totals line present - the first run of this " +
   "harness passed this leg while everything else failed, because exit 1 is also " +
   "what a broken lane table produces")
Check "C1-C3 it does NOT claim N watchers started" (
  -not ($r1.Out -match "watcher\(s\) started")
) "the old totals sentence is gone"
Check "C1-C3 queued= is labelled as a launch-time reading" (
  $r1.Out -match "queued-at-launch="
) "the label says when the number was taken"

KillLaneWatchers
try { Stop-Process -Id $holder.Id -Force -ErrorAction SilentlyContinue } catch { }

# ==========================================================================
Write-Host ""
Write-Host "C4-C6  an unreadable log, a missing path, a STOP file"

$wtUnread = NewLane "unreadable"
$wtMiss   = NewLane "missing" -NoPath
$wtStop   = NewLane "stopped"
$stopPath = Join-Path $ScratchOps "STOP-stopped"
if ($stopPath.ToLower().StartsWith($LiveOps.ToLower())) {
  Write-Host ("REFUSING: the STOP path is inside the live estate: " + $stopPath); exit 2
}
Set-Content -LiteralPath $stopPath -Value "scratch" -Encoding ASCII

# the unreadable log: created, then held open with no sharing at all
$unreadLog = Join-Path $LogDir "watcher-unreadable.log"
Set-Content -LiteralPath $unreadLog -Value "[pre-existing line]" -Encoding UTF8
$hold = [System.IO.File]::Open($unreadLog, 'Open', 'ReadWrite', 'None')

$table2 = Join-Path $Root "lanes2.ps1"
WriteLaneTable $table2 @(
  @{ Lane = "unreadable"; Worktree = $wtUnread },
  @{ Lane = "missing";    Worktree = $wtMiss },
  @{ Lane = "stopped";    Worktree = $wtStop })
$r2 = RunLauncher $table2 $wrapper
$hold.Close(); $hold.Dispose()

Write-Host "  ---- launcher output ----"
foreach ($line in ($r2.Out -split "`r?`n")) { if ($line.Trim() -ne "") { Write-Host ("  | " + $line) } }
Write-Host "  -------------------------"

Check "C4 an unreadable log is UNKNOWN, never STARTED" (
  ($r2.Out -match "UNKNOWN\s+unreadable") -and (-not ($r2.Out -match "STARTED\s+unreadable"))
) "classified UNKNOWN"
Check "C4 and it says the log could not be read" (
  $r2.Out -match "could not be read"
) "the reason is specific"
Check "C5 a missing worktree path is SKIPPED" (
  $r2.Out -match "SKIP\s+missing" -or $r2.Out -match "SKIPPED\s+missing"
) "classified skipped"
Check "C6 a STOP file is SKIPPED, not revived" (
  $r2.Out -match "SKIP\s+stopped" -or $r2.Out -match "SKIPPED\s+stopped"
) "classified skipped"
Check "C4-C6 the totals count skipped separately from unknown" (
  $r2.Out -match "started=0\s+refused=0\s+skipped=2\s+unknown=1"
) "started=0 refused=0 skipped=2 unknown=1"
Check "C4-C6 the exit code is non-zero because one lane is UNKNOWN" (
  ($r2.Code -eq 1) -and ($r2.Out -match "unknown=1")
) ("exit " + $r2.Code + " with unknown=1 on the totals line")

KillLaneWatchers

# ==========================================================================
Write-Host ""
Write-Host "C7  a watcher that starts and says nothing within the bound"

$wtSilent = NewLane "silent"
$table3 = Join-Path $Root "lanes3.ps1"
WriteLaneTable $table3 @(@{ Lane = "silent"; Worktree = $wtSilent })
$t0 = Get-Date
$r3 = RunLauncher $table3 $silent 6
$elapsed = ((Get-Date) - $t0).TotalSeconds

Write-Host "  ---- launcher output ----"
foreach ($line in ($r3.Out -split "`r?`n")) { if ($line.Trim() -ne "") { Write-Host ("  | " + $line) } }
Write-Host "  -------------------------"

Check "C7 a silent watcher is UNKNOWN, never STARTED" (
  ($r3.Out -match "UNKNOWN\s+silent") -and (-not ($r3.Out -match "STARTED\s+silent"))
) "classified UNKNOWN"
Check "C7 and the reason names the bound" (
  $r3.Out -match "nothing in its log within 6s"
) "the bound is in the reason"
Check "C7 THE LAUNCHER DID NOT HANG" (
  ($elapsed -lt 45) -and ($r3.Out -match "started=0")
) ([string][math]::Round($elapsed, 1) + "s wall clock against a 6s bound, and it " +
   "got far enough to print its totals - a launcher that died instantly would " +
   "also be fast")
Check "C7 the stated bound is on the output" (
  $r3.Out -match "evidence bound 6s"
) "the bound is printed before anything is launched"

KillLaneWatchers

# ==========================================================================
Write-Host ""
Write-Host "C8-C9  the exit-code branch: a silent non-zero exit, and a silent exit 0"

$stub2 = Join-Path $Root "wrap-exit2.ps1"
$stub0 = Join-Path $Root "wrap-exit0.ps1"
WriteExitStub $stub2 2
WriteExitStub $stub0 0

$wtE2 = NewLane "silentfail"
$table4 = Join-Path $Root "lanes4.ps1"
WriteLaneTable $table4 @(@{ Lane = "silentfail"; Worktree = $wtE2 })
$r4 = RunLauncher $table4 $stub2 8
Write-Host "  ---- launcher output ----"
foreach ($line in ($r4.Out -split "`r?`n")) { if ($line.Trim() -ne "") { Write-Host ("  | " + $line) } }
Write-Host "  -------------------------"
Check "C8 a watcher that exits non-zero with NO log line is REFUSED" (
  $r4.Out -match "REFUSED\s+silentfail"
) "classified refused"
Check "C8 AND THE CODE IS READ, not blank" (
  $r4.Out -match "exited 2 with no REFUSING line"
) "the exit code reached the output - this is the leg the missing handle broke"
Check "C8 the totals count it as refused" (
  $r4.Out -match "started=0\s+refused=1\s+skipped=0\s+unknown=0"
) "started=0 refused=1"

$wtE0 = NewLane "silentzero"
$table5 = Join-Path $Root "lanes5.ps1"
WriteLaneTable $table5 @(@{ Lane = "silentzero"; Worktree = $wtE0 })
$r5 = RunLauncher $table5 $stub0 8
Write-Host "  ---- launcher output ----"
foreach ($line in ($r5.Out -split "`r?`n")) { if ($line.Trim() -ne "") { Write-Host ("  | " + $line) } }
Write-Host "  -------------------------"
Check "C9 a watcher that exits 0 saying nothing is UNKNOWN, not started" (
  ($r5.Out -match "UNKNOWN\s+silentzero") -and (-not ($r5.Out -match "STARTED\s+silentzero"))
) "classified UNKNOWN"
Check "C9 and the reason says it exited 0 with nothing to say" (
  $r5.Out -match "exited 0 having written nothing"
) "the reason is specific - and it is only reachable when the code is readable"
Check "C9 the totals count it as unknown" (
  $r5.Out -match "started=0\s+refused=0\s+skipped=0\s+unknown=1"
) "unknown=1"

KillLaneWatchers

# ==========================================================================
Write-Host ""
Write-Host ("passes=" + $passes + "  fails=" + $fails.Count)
if ($fails.Count -gt 0) {
  Write-Host "FAILED:"
  $fails | ForEach-Object { Write-Host ("  " + $_) }
}
if ($KeepScratch) { Write-Host ("scratch kept at " + $Root) }
else { try { Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue } catch { } }
if ($fails.Count -gt 0) { exit 1 }
exit 0
