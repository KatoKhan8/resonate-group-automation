<#
  test_lane_watcher_endtoend.ps1 - run the real lane watcher, end to end,
  against a scratch queue and a fake task, and assert the whole chain.

  ASCII ONLY. Same reason as the files it tests.

  WHAT THIS CLOSES. qwen TASK 0090 fixed the watcher and flagged its own
  limit: "the watcher's wiring is argued, not executed. $Ops and the task
  command are hardcoded to the live queue and a real `claude -p`, so I could
  not run a timeout end-to-end without running it against production."
  The kill module was proven directly by test_lane_watcher_treekill.ps1, and
  that proof stands. But what killed the glm and pilotcaps lanes on 2026-10-15
  was not the kill, it was the CHAIN of five links:

    1  the timeout killed the cmd.exe wrapper
    2  `claude` survived, holding the brief open as its inherited stdin
    3  Move-Item into DONE threw, because of that handle
    4  $ErrorActionPreference = "Stop" made the throw terminating
    5  nothing caught it, so the script left its own loop

  No test could touch any of them. This one runs all five, in order, in one
  watcher process, against three briefs.

  THE FIFTH LINK IS THE ONE THAT WOULD HAVE CAUGHT THAT AFTERNOON, and it
  cannot be proven by a watcher that only ever ran one task. So the loop's
  survival is asserted by WORK, not by liveness: the watcher consumes two more
  briefs after the timeout. A process that is merely still in the table could
  be stuck anywhere.

  WHY IT IS SAFE. The watcher's entire blast radius travels with -Ops, so one
  parameter moves the queue, RUNNING, DONE, the logs, the LANE file and the
  STOP files into %TEMP%. The live paths are refused by name below, the lane is
  called "e2etest" which is not a lane, and nothing outside the scratch root is
  written. Every process this harness kills is one its own fake task started,
  selected by a pid the harness recorded in a marker file - never by a
  CommandLine substring, which is how TASK 0070 killed its own measurement
  shell.

  THE CONTROL. -SabotageKill swaps the tree-kill module for a stub that reports
  success and kills nothing. The orphan then survives, the handle is still on
  the brief, and the run SHOULD fail its kill and move assertions - while the
  DONE line and the loop survive anyway, because 0090 fixed that separately.
  A harness whose assertions have never been seen to fail is not evidence.
#>
param(
  [string]$Lane = "e2etest",
  # 0.2 min = 12s. The timeout parameter became [double] in TASK 0110 for
  # exactly this: an integer floor of one minute put it out of reach of a test.
  [double]$TimeoutMinutes = 0.2,
  [int]$SampleSeconds = 2,
  [switch]$SabotageKill,
  [switch]$KeepScratch
)

$ErrorActionPreference = "Stop"

$LiveOps  = "C:\Users\Zvonimir\Desktop\resonate-ops"
$RealLanes = @("glm", "glm-b", "glm-c", "pilotcaps", "qwen", "suppression", "webapp")

if ($RealLanes -contains $Lane) {
  Write-Host ("REFUSING: '" + $Lane + "' is a real lane. This harness never names one.")
  exit 2
}

$RepoOps  = Split-Path -Parent $PSCommandPath
$Watcher  = Join-Path $RepoOps "lane_watcher.ps1"
$TreeKill = Join-Path $RepoOps "lane_treekill.ps1"
$FakeTask = Join-Path $RepoOps "fake_lane_task.ps1"
foreach ($f in @($Watcher, $TreeKill, $FakeTask)) {
  if (-not (Test-Path -LiteralPath $f)) { Write-Host ("MISSING: " + $f); exit 2 }
}

# ------------------------------------------------------------- the scratch
$Root     = Join-Path $env:TEMP ("lane-e2e-" + [guid]::NewGuid().ToString("N").Substring(0, 12))
$ScratchOps = Join-Path $Root "ops"
$Wt       = Join-Path $Root "wt"
$Markers  = Join-Path $Root "markers"
$Queue    = Join-Path $ScratchOps ("queue\" + $Lane)
$Done     = Join-Path $Queue "DONE"
$Running  = Join-Path $Queue "RUNNING"
$LogDir   = Join-Path $ScratchOps "logs"
$WatchLog = Join-Path $LogDir ("watcher-" + $Lane + ".log")
$LaneFile = Join-Path $ScratchOps ("LANE-" + $Lane + ".md")
$StopMe   = Join-Path $ScratchOps ("STOP-" + $Lane)

if ($ScratchOps.TrimEnd('\') -ieq $LiveOps.TrimEnd('\')) {
  Write-Host "REFUSING: the scratch ops path resolved to the live one."; exit 2
}

foreach ($d in @($Queue, $Done, $Running, $LogDir, $Markers,
                 (Join-Path $ScratchOps "tools"), (Join-Path $Wt ".git"))) {
  New-Item -ItemType Directory -Path $d -Force | Out-Null
}
Set-Content -LiteralPath $LaneFile -Value "# LANE-$Lane (scratch)" -Encoding UTF8

# The module in the chain is the repository's own, not a copy of it - unless
# the control is asked for, in which case it is a stub that lies.
$useTreeKill = $TreeKill
if ($SabotageKill) {
  $useTreeKill = Join-Path $ScratchOps "tools\lane_treekill_STUB.ps1"
  @'
# CONTROL STUB. Reports a verified kill and kills nothing. Used only by
# test_lane_watcher_endtoend.ps1 -SabotageKill, to show the assertions can fail.
function Get-LaneProcTable { return @{} }
function Get-LaneDescendants { param($Table, $RootPid, $SelfPid) return @{} }
function Stop-LaneProcessTree {
  param($RootPid, $Accumulated, [scriptblock]$Say)
  if ($Say) { & $Say "STUB KILL: pretending. Nothing was stopped." }
  return [pscustomobject]@{ Refused = $false; Before = @(); After = @(); Verified = $true; Taskkill = @() }
}
'@ | Set-Content -LiteralPath $useTreeKill -Encoding ASCII
}

# ------------------------------------------------------------- the briefs
# Filename order is dispatch order, and the order is the argument: the timeout
# comes FIRST so that everything after it is evidence the loop survived it.
function Brief($name, $mode, $body) {
  # EVERY ELEMENT IS PARENTHESISED, and that is the whole point of this
  # function having a comment. Measured 2026-10-15 22:50, after two harness
  # runs in which all three legs exited 9:
  #
  #     @("# SCRATCH BRIEF - " + $name, "MODE: " + $mode, "", $body)
  #
  # is NOT a four-element array. In PowerShell the comma binds TIGHTER than
  # +, so this parses as
  #
  #     @("# SCRATCH BRIEF - " + ($name, "MODE: " + ($mode, "", $body)))
  #
  # - one string concatenated with an array, which PowerShell flattens using
  # $OFS, a space. The result was a single 119-byte line, the fake task's
  # line-anchored MODE regex could not match it, and the brief never had four
  # lines to begin with. -join was innocent and so was Set-Content: an earlier
  # version of this comment blamed Set-Content for joining an array that had
  # never existed.
  #
  # Checked by length: 22 + 12 + 0 + 9 = 43 characters of content, and the
  # result was 46 - three one-character separators, not three CRLFs.
  $text = @(
    ("# SCRATCH BRIEF - " + $name),
    ("MODE: " + $mode),
    "",
    $body) -join "`r`n"
  if (($text -split "`n").Count -lt 4) {
    throw ("the brief for " + $name + " came out as " + ($text -split "`n").Count +
           " line(s). It must be four. This is the comma-binds-tighter-than-plus bug.")
  }
  Set-Content -LiteralPath (Join-Path $Queue $name) -Encoding ASCII -Value $text
}
Brief "0010-orphan.md" "orphan" "Hang past the deadline and leave a grandchild whose parent has exited."
Brief "0020-nowork.md" "nowork" "Exit 0 without touching the lane file."
Brief "0030-exit0.md"  "exit0"  "Grow the lane file and exit 0."

# ------------------------------------------------------------- the command
# The injection point used exactly as designed: {BRIEF} appears twice, once as
# the stdin redirect (the handle that is link 2) and once as an argument, so
# the grandchild can open the same file by name.
$taskTemplate = '/c powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' +
                $FakeTask + '" -BriefPath "{BRIEF}" -MarkerDir "' + $Markers +
                '" -LaneFile "' + $LaneFile + '" -ParentLifeSeconds 5 ' +
                '-ChildLifeSeconds 300 -HangSeconds 600 < "{BRIEF}" > "{OUT}" 2>&1'

$fails = New-Object System.Collections.ArrayList
$passes = 0
function Check($name, $ok, $detail) {
  if ($ok) { $script:passes++; Write-Host ("  PASS  " + $name + "   " + $detail) }
  else { [void]$script:fails.Add($name + " :: " + $detail); Write-Host ("  FAIL  " + $name + "   " + $detail) }
}

function LogText { if (Test-Path -LiteralPath $WatchLog) { return (Get-Content -LiteralPath $WatchLog -Raw) } return "" }

# $script:watchPid is set once the watcher is launched. WaitFor stops early if
# that process is gone AND the line has still not appeared: the first run of
# this harness spent eight minutes waiting on a watcher that had exited after
# nineteen seconds, which reads as slow rather than as broken.
$script:watchPid = $null
function WaitFor($pattern, $seconds, $what) {
  $end = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $end) {
    if ((LogText) -match $pattern) { return $true }
    if ($script:watchPid -and -not (Get-Process -Id $script:watchPid -ErrorAction SilentlyContinue)) {
      # One last read: the line may have landed in the same instant it exited.
      if ((LogText) -match $pattern) { return $true }
      Write-Host ("  ... the watcher (pid " + $script:watchPid + ") is GONE and " + $what + " never appeared")
      return $false
    }
    Start-Sleep -Milliseconds 400
  }
  Write-Host ("  ... timed out after " + $seconds + "s waiting for " + $what)
  return $false
}

function WaitForFile($path, $seconds) {
  $end = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $end) {
    if (Test-Path -LiteralPath $path) { return $true }
    Start-Sleep -Milliseconds 200
  }
  return $false
}

function MarkerPid($name) {
  $p = Join-Path $Markers $name
  if (-not (Test-Path -LiteralPath $p)) { return $null }
  $v = (Get-Content -LiteralPath $p -Raw).Trim()
  if ($v -match '^\d+$') { return [int]$v }
  return $null
}

function IsAlive($thePid) {
  if ($null -eq $thePid) { return $false }
  return [bool](Get-Process -Id $thePid -ErrorAction SilentlyContinue)
}

Write-Host ""
Write-Host "=== lane watcher, end to end ==============================================="
Write-Host ("scratch   " + $Root)
Write-Host ("watcher   " + $Watcher)
Write-Host ("treekill  " + $useTreeKill + $(if ($SabotageKill) { "   (CONTROL: this one lies)" } else { "" }))
Write-Host ("timeout   " + $TimeoutMinutes + " min   sample " + $SampleSeconds + "s")
Write-Host ""

# `claude` on PATH is a precondition of the watcher, not of this test - the
# task command is overridden and claude is never invoked. Named because a
# REFUSING line would otherwise look like a test failure.
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Write-Host "PRECONDITION UNMET: the watcher refuses to start without `claude` on PATH."
  Write-Host "That guard is unrelated to what this test measures, but it does block it."
  exit 2
}

# THE WATCHER IS LAUNCHED THROUGH A GENERATED LAUNCHER, and the reason is a
# measurement: passing $taskTemplate as an element of -ArgumentList silently
# destroyed it. Start-Process wraps an element containing spaces in double
# quotes, and the template contains its own double quotes - around {BRIEF} and
# {OUT} - which terminate that wrapper early. The first run of this harness
# produced a watcher that never logged a single line and three briefs that were
# never claimed. A launcher file puts the template in a single-quoted
# PowerShell literal, where nothing re-parses it.
$launcher = Join-Path $Root "run-watcher.ps1"
$launcherText =
  '& "' + $Watcher + '" `' + "`n" +
  '  -Lane ''' + $Lane + ''' `' + "`n" +
  '  -Worktree ''' + $Wt + ''' `' + "`n" +
  '  -Ops ''' + $ScratchOps + ''' `' + "`n" +
  '  -TreeKillPath ''' + $useTreeKill + ''' `' + "`n" +
  '  -TaskCommandTemplate ''' + $taskTemplate.Replace("'", "''") + ''' `' + "`n" +
  '  -TaskTimeoutMinutes ' + $TimeoutMinutes + ' `' + "`n" +
  '  -TreeSampleSeconds ' + $SampleSeconds + ' `' + "`n" +
  '  -IdleSleepSeconds 3 `' + "`n" +
  '  -PermissionMode default' + "`n"
Set-Content -LiteralPath $launcher -Value $launcherText -Encoding ASCII

$watcherProc = $null
try {
  $watcherProc = Start-Process -FilePath "powershell.exe" -PassThru -NoNewWindow -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $launcher
  )
  $null = $watcherProc.Handle
  $script:watchPid = $watcherProc.Id
  Write-Host ("watcher pid " + $watcherProc.Id)

  $up = WaitFor "watcher up\." 30 "'watcher up.'"
  Check "watcher started" $up "the scratch watcher logged its banner"
  if (-not $up) {
    # FAIL FAST. Without this, a watcher that died at startup left the harness
    # grinding through twenty 90-second waits for lines that could never come,
    # and the run looked slow rather than broken.
    Write-Host ""
    Write-Host "ABORTING: the watcher never came up, so nothing below could be measured."
    Write-Host ("  launcher: " + $launcher)
    Write-Host ("  alive:    " + (IsAlive $watcherProc.Id))
    Write-Host "  log so far:"
    Write-Host (LogText)
    throw "watcher did not start"
  }
  Check "scratch is named in the log" ((LogText) -match [regex]::Escape("ops=" + $ScratchOps)) `
        "a test run and a live run are distinguishable in the log"
  Check "the fake task is the command, not claude" ((LogText) -match "fake_lane_task\.ps1") `
        "the injected template reached the watcher intact"

  # ---------------------------------------------------------------- LEG 1
  Write-Host ""
  Write-Host "--- LEG 1  TIMEOUT with a grandchild that outlived its parent -------------"
  Check "leg1 dispatched" (WaitFor "START 0010-orphan\.md" 25 "START 0010") "the watcher claimed the brief"

  $okRoot   = WaitForFile (Join-Path $Markers "orphan-root.pid") 25
  $okParent = WaitForFile (Join-Path $Markers "orphan-parent.pid") 25
  $okChild  = WaitForFile (Join-Path $Markers "orphan-child.pid") 25
  $rootPid   = MarkerPid "orphan-root.pid"
  $parentPid = MarkerPid "orphan-parent.pid"
  $childPid  = MarkerPid "orphan-child.pid"
  Check "three generations ran" ($okRoot -and $okParent -and $okChild) `
        ("root=" + $rootPid + " parent=" + $parentPid + " child=" + $childPid)
  Check "the grandchild holds the brief open" (WaitForFile (Join-Path $Markers "orphan-child.holds-brief") 25) `
        "link 2 of the chain: a handle on the brief, FileShare::Read, no ::Delete"

  # THE ORPHAN IS PROVEN TO BE AN ORPHAN, not assumed to be one: the parent's
  # exit marker is waited for, and the child is measured alive at that moment.
  $okExit = WaitForFile (Join-Path $Markers "orphan-parent.exited") 30
  $childAliveWhenOrphaned = IsAlive $childPid
  $parentGone = -not (IsAlive $parentPid)
  Check "the child is a real orphan" ($okExit -and $parentGone -and $childAliveWhenOrphaned) `
        ("parent " + $parentPid + " exited and child " + $childPid +
         " was still alive - taskkill /T walks LIVE links and cannot see it")

  $sawOrphanInKillSet = WaitFor ("ORPHAN still alive and added to the kill set: pid " + $childPid) 90 "the orphan being added to the kill set"
  Check "the orphan reached the kill set" $sawOrphanInKillSet `
        "the accumulated samples, not taskkill /T, are what found it"

  Check "TIMEOUT logged" (WaitFor "TIMEOUT after " 90 "the TIMEOUT line") ("deadline was " + $TimeoutMinutes + " min")

  $gotVerdict = WaitFor "(KILL VERIFIED: 0 of \d+ still alive|KILL INCOMPLETE|THE KILL WAS REFUSED|STUB KILL)" 90 "a kill verdict"
  $txt = LogText
  $m = [regex]::Match($txt, 'KILL VERIFIED: 0 of (\d+) still alive')
  Check "kill verified, zero survivors" ($m.Success) `
        ($(if ($m.Success) { "KILL VERIFIED: 0 of " + $m.Groups[1].Value + " still alive" } else { "no VERIFIED line; got: " + (($txt -split "`n" | Where-Object { $_ -match "KILL |STUB " }) -join " | ") }))
  # BY MEMBERSHIP, NOT BY COUNT. The first full run of this harness asserted
  # N >= 4 - wrapper, fake-task root, orphan-parent, orphan - and FAILED at
  # N=3. The code was right and the assertion was wrong: orphan-parent had
  # already exited by the time the deadline fired, and the module adds only
  # processes still ALIVE to the kill set. A dead process is not a survivor and
  # does not belong in one. Counting it was this harness's own version of the
  # mistake the standing rules name: a baseline compared by count, not by name.
  $killSet = [regex]::Match($txt, 'KILL SET before \((\d+)\): (.+)')
  $setPids = @()
  if ($killSet.Success) {
    foreach ($tok in ($killSet.Groups[2].Value -split '\s+')) {
      $mm = [regex]::Match($tok, '^(\d+):')
      if ($mm.Success) { $setPids += [int]$mm.Groups[1].Value }
    }
  }
  Check "the fake task's own root is in the kill set" ($setPids -contains $rootPid) `
        ("kill set = " + ($setPids -join ",") + "; root=" + $rootPid)
  Check "the orphan is in the kill set" ($setPids -contains $childPid) `
        ("orphan=" + $childPid + ", reached only through the accumulated samples")
  Check "the already-dead parent is NOT in the kill set" (-not ($setPids -contains $parentPid)) `
        ("parent=" + $parentPid + " had exited; a dead process is not a survivor")

  # THE POINT OF THE WHOLE MODULE, asserted directly: taskkill /T walks LIVE
  # parent links, so it cannot name the orphan, and the SWEEP is what kills it.
  $tkLines = @($txt -split "`n" | Where-Object { $_ -match "taskkill: " })
  $tkNamedOrphan = [bool](@($tkLines | Where-Object { $_ -match ("PID " + $childPid + " ") }).Count)
  Check "taskkill /T could not reach the orphan" (-not $tkNamedOrphan) `
        ("taskkill named " + $tkLines.Count + " termination(s), none of them pid " + $childPid)
  Check "the sweep is what killed the orphan" ($txt -match ("sweep round \d+: \d+ survivor\(s\): .*" + $childPid + ":")) `
        "re-reading the table after the kill is the only thing that found it"

  # Dead by identity, measured, not inferred from an exit code.
  Start-Sleep -Seconds 2
  $stillAlive = @()
  foreach ($pr in @(@("root", $rootPid), @("parent", $parentPid), @("orphan", $childPid))) {
    if (IsAlive $pr[1]) { $stillAlive += ($pr[0] + "=" + $pr[1]) }
  }
  Check "every descendant is dead" ($stillAlive.Count -eq 0) `
        ($(if ($stillAlive.Count -eq 0) { "0 of 3 still alive, by pid" } else { "STILL ALIVE: " + ($stillAlive -join ",") }))

  Check "DONE -> TIMEOUT written" (WaitFor "DONE  0010-orphan\.md -> TIMEOUT" 60 "the DONE line") `
        "link 5: the record is written before the filesystem is asked for anything"
  Check "Move-Item succeeded" (WaitFor "MOVED 0010-orphan\.md ->" 60 "the MOVED line") `
        "link 3: the handle was gone, so the rename into DONE did not throw"
  Check "no move was left blocked" (-not ((LogText) -match "MOVE STILL BLOCKED after 30s\. 0010-orphan")) `
        "nothing stayed stranded in RUNNING"
  $doneFile = @(Get-ChildItem -LiteralPath $Done -Filter "*TIMEOUT-0010-orphan.md" -ErrorAction SilentlyContinue)
  Check "the brief is in DONE, suffixed TIMEOUT" ($doneFile.Count -eq 1) `
        ($(if ($doneFile.Count -eq 1) { $doneFile[0].Name } else { "found " + $doneFile.Count + " matching files" }))

  # ---------------------------------------------------------------- LEG 2
  Write-Host ""
  Write-Host "--- LEG 2  NOWORK, through the same Move-Item link ------------------------"
  Check "the loop survived the timeout and took the next brief" (WaitFor "START 0020-nowork\.md" 90 "START 0020") `
        "THIS is the assertion that would have caught 2026-10-15: the loop did not exit"
  Check "NOWORK detected" (WaitFor ("NOWORK: exit 0 but LANE-" + $Lane + "\.md did not grow") 60 "the NOWORK line") `
        "exit 0 with no lane growth is a failure, not a completion"
  Check "DONE -> NOWORK written" (WaitFor "DONE  0020-nowork\.md -> NOWORK" 60 "the DONE line") "record first"
  Check "Move-Item succeeded (NOWORK)" (WaitFor "MOVED 0020-nowork\.md ->" 60 "the MOVED line") "the shared link again"
  $doneNw = @(Get-ChildItem -LiteralPath $Done -Filter "*NOWORK-0020-nowork.md" -ErrorAction SilentlyContinue)
  Check "the brief is in DONE, suffixed NOWORK" ($doneNw.Count -eq 1) `
        ($(if ($doneNw.Count -eq 1) { $doneNw[0].Name } else { "found " + $doneNw.Count }))

  # ---------------------------------------------------------------- LEG 3
  Write-Host ""
  Write-Host "--- LEG 3  clean exit, through the same Move-Item link --------------------"
  $laneBefore = (Get-Item -LiteralPath $LaneFile).Length
  Check "the loop is still running after two failures" (WaitFor "START 0030-exit0\.md" 90 "START 0030") `
        "two consecutive failures did not reach MaxConsecutiveFailures=3"
  Check "DONE -> exit0 written" (WaitFor "DONE  0030-exit0\.md -> exit0" 60 "the DONE line") "clean exit recorded as exit0"
  Check "Move-Item succeeded (exit0)" (WaitFor "MOVED 0030-exit0\.md ->" 60 "the MOVED line") "the shared link a third time"
  $laneAfter = (Get-Item -LiteralPath $LaneFile).Length
  Check "the lane file grew" ($laneAfter -gt $laneBefore) ($laneBefore.ToString() + " -> " + $laneAfter + " bytes")
  $doneOk = @(Get-ChildItem -LiteralPath $Done -Filter "*exit0-0030-exit0.md" -ErrorAction SilentlyContinue)
  Check "the brief is in DONE, suffixed exit0" ($doneOk.Count -eq 1) `
        ($(if ($doneOk.Count -eq 1) { $doneOk[0].Name } else { "found " + $doneOk.Count }))

  # --------------------------------------------------------- THE LOOP LIVES
  Write-Host ""
  Write-Host "--- THE LOOP ---------------------------------------------------------------"
  Check "the watcher went idle on an empty queue" (WaitFor "idle: queue empty" 90 "the idle line") `
        "it is polling, not stuck and not gone"
  Check "the watcher process is still alive" (IsAlive $watcherProc.Id) ("pid " + $watcherProc.Id)
  Check "the watcher never logged an unhandled error" (-not ((LogText) -match "UNHANDLED |watcher down \(unhandled error\)")) `
        "link 4: no throw was allowed to become terminating"
  Check "three briefs consumed, three DONE files" (@(Get-ChildItem -LiteralPath $Done -Filter *.md).Count -eq 3) `
        ("DONE holds " + @(Get-ChildItem -LiteralPath $Done -Filter *.md).Count + " files")
  Check "RUNNING is empty" (@(Get-ChildItem -LiteralPath $Running -Filter *.md -ErrorAction SilentlyContinue).Count -eq 0) `
        "nothing stranded"

  # Exit the way the operator does, so that path is exercised too.
  Set-Content -LiteralPath $StopMe -Value "e2e test" -Encoding ASCII
  Check "STOP-<lane> stops it cleanly" (WaitFor "watcher down\." 60 "'watcher down.'") "and the pid lock is released"
}
catch {
  [void]$fails.Add("HARNESS ABORTED :: " + $_.Exception.Message)
}
finally {
  # Kill ONLY what this harness started, by pid, never by a name filter.
  if ($watcherProc -and (IsAlive $watcherProc.Id)) {
    Write-Host ("cleanup: watcher pid " + $watcherProc.Id + " is still alive; stopping it")
    try { Stop-Process -Id $watcherProc.Id -Force -ErrorAction SilentlyContinue } catch { }
  }
  foreach ($f in @(Get-ChildItem -LiteralPath $Markers -Filter "*.pid" -ErrorAction SilentlyContinue)) {
    $p = MarkerPid $f.Name
    if (IsAlive $p) {
      Write-Host ("cleanup: fake-task pid " + $p + " (" + $f.Name + ") still alive; stopping it")
      try { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } catch { }
    }
  }
  Write-Host ""
  Write-Host "=== RESULT ================================================================="
  Write-Host ("  passed " + $passes + "   failed " + $fails.Count)
  foreach ($f in $fails) { Write-Host ("  FAILED: " + $f) }
  if ($KeepScratch) {
    Write-Host ("  scratch kept: " + $Root)
  } else {
    Write-Host ("  log copied to " + (Join-Path $env:TEMP ("lane-e2e-last-" + $Lane + ".log")))
    try { Copy-Item -LiteralPath $WatchLog -Destination (Join-Path $env:TEMP ("lane-e2e-last-" + $Lane + ".log")) -Force } catch { }
    try { Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue } catch { }
  }
}

if ($fails.Count -gt 0) { exit 1 }
exit 0
