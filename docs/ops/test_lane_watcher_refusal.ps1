<#
  test_lane_watcher_refusal.ps1 - run the REAL lane watcher, end to end, against
  a scratch queue, and prove that a provider refusal returns the brief while an
  ordinary task failure still consumes it.

  ASCII ONLY, same reason as the files it tests.

  WHAT IT CLOSES. On 2026-10-16 01:41-01:48 the GLM plan hit its rolling 5-hour
  limit, nine briefs were consumed in seven minutes across three lanes and none
  of them ran. The watcher had two verdicts, finished and failed, and chose the
  failed one, which is the verdict that moves the brief into DONE.

  WHY IT IS SAFE. The watcher's whole blast radius travels with -Ops (qwen TASK
  0110), so one parameter moves the queue, RUNNING, DONE, the logs, the LANE
  file and the STOP files into %TEMP%. The live ops path is refused by name
  below, the lane is called "reftest" which is not a lane, `claude` is never
  invoked - the task command is injected and points at fake_lane_task.ps1 - and
  no real lane, log or worktree is read or written. Every process this harness
  stops is one it started, selected by a pid it recorded.

  THE FOUR CASES, IN FILENAME ORDER, WHICH IS DISPATCH ORDER:

    0010-taskfail   THE CONTROL. exit 1, a traceback, no 429, no lane growth.
                    Must be CONSUMED to DONE as exit1, exactly as today.
    0020-nowork     exit 0, no lane growth.  Must be NOWORK, consumed.
    0030-exit0      exit 0, lane grows.      Must be exit0, consumed.
    0040-refused    exit 1, the provider's real 429 text, no lane growth.
                    Must be RETURNED to queue\reftest\ under its original name.

  THE CONTROL COMES FIRST ON PURPOSE. If the patch is wrong in the dangerous
  direction - returning every failure to the queue - then 0010 goes back to the
  queue, 0010 sorts before everything else, and the watcher never reaches a
  single other case. The run cannot accidentally look fine.

  THE REFUSAL COMES LAST ON PURPOSE TOO, and the reason is a real consequence
  worth naming rather than designing around: the queue is FIFO by filename, so a
  returned brief is picked up again before anything behind it. That is correct -
  a refused brief has not been tried and keeps its place - but it means a
  refusing lane is HEAD-OF-LINE BLOCKED and does not quietly work through the
  rest of its queue. If 0040 were first, 0020 and 0030 would never run. Stated
  in the lane entry as a consequence for the operator, not hidden here.

  THE FIFTH LEG is the one the brief asked for by name: four refusals in a row.
  With MaxConsecutiveFailures = 3 and refusals NOT counted as failures (the
  default), the watcher must still be alive and still returning on the fourth.
  That is the direct proof that the three-failure guard no longer fires on a
  provider refusal.

  THE SIXTH LEG runs a second watcher with -MaxConsecutiveRefusals 2 and proves
  the OTHER bound: a lane that only ever refuses stops, cleanly, with the brief
  still in its queue. Unbounded refusal would be a lane that looks alive and
  consumes nothing.

  BYTE-IDENTICAL IS CHECKED AS BYTES. Every snapshot is name + length + SHA256
  for every file in the queue directory, compared as a string. "The file is
  still there" is not the claim; "the queue after a refusal is byte-identical to
  the queue before it" is.
#>
param(
  [string]$Lane = "reftest",
  [int]$Backoff = 5,
  # THE SABOTAGE CONTROL. Swaps lane_refusal.ps1 for a stub that classifies
  # EVERY non-zero exit with no lane growth as a provider refusal - the patch
  # wrong in the dangerous direction. Leg 2's assertions MUST then go red, and
  # the run must report NOT MET. A harness whose control has never been seen to
  # fail is not evidence; the brief for TASK 0175 says so in as many words.
  [switch]$SabotageSignature,
  [switch]$KeepScratch
)

$ErrorActionPreference = "Stop"

$LiveOps   = "C:\Users\Zvonimir\Desktop\resonate-ops"
$RealLanes = @("glm", "glm-b", "glm-c", "pilotcaps", "qwen", "suppression", "webapp")

if ($RealLanes -contains $Lane) {
  Write-Host ("REFUSING: '" + $Lane + "' is a real lane. This harness never names one.")
  exit 2
}

$RepoOps  = Split-Path -Parent $PSCommandPath
$Watcher  = Join-Path $RepoOps "lane_watcher.ps1"
$TreeKill = Join-Path $RepoOps "lane_treekill.ps1"
$Refusal  = Join-Path $RepoOps "lane_refusal.ps1"
$FakeTask = Join-Path $RepoOps "fake_lane_task.ps1"
foreach ($f in @($Watcher, $TreeKill, $Refusal, $FakeTask)) {
  if (-not (Test-Path -LiteralPath $f)) { Write-Host ("MISSING: " + $f); exit 2 }
}
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Write-Host "PRECONDITION UNMET: the watcher refuses to start without 'claude' on PATH."
  Write-Host "That guard is unrelated to what this test measures, but it does block it."
  exit 2
}

$Root       = Join-Path $env:TEMP ("lane-ref-" + [guid]::NewGuid().ToString("N").Substring(0, 12))
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

if ($ScratchOps.TrimEnd('\') -ieq $LiveOps.TrimEnd('\')) {
  Write-Host "REFUSING: the scratch ops path resolved to the live one."; exit 2
}
foreach ($d in @($Queue, $Done, $Running, $LogDir, $Markers,
                 (Join-Path $ScratchOps "tools"), (Join-Path $Wt ".git"))) {
  New-Item -ItemType Directory -Path $d -Force | Out-Null
}
Set-Content -LiteralPath $LaneFile -Value ("# LANE-" + $Lane + " (scratch)") -Encoding UTF8

# The module in the chain is the repository's own, not a copy of it - unless the
# sabotage control is asked for, in which case it is a stub that drops gate 4.
$useRefusal = $Refusal
if ($SabotageSignature) {
  $useRefusal = Join-Path $ScratchOps "tools\lane_refusal_SABOTAGE.ps1"
  @'
# SABOTAGE CONTROL. Drops gate 4 - the signature - so EVERY non-zero exit with
# no lane growth is called a provider refusal. This is the patch wrong in the
# dangerous direction: a watcher that returns every failure to its queue and
# loops forever on a genuinely broken brief. Used only by
# test_lane_watcher_refusal.ps1 -SabotageSignature, to show the control can fail.
function Get-LaneRefusalSignatures { return @([pscustomobject]@{ Name = "SABOTAGE-matches-anything"; Pattern = '(?s).*'; Status = "429"; Note = "stub" }) }
function Get-LaneRefusalNearMissPatterns { return @() }
function Get-LaneRefusalResetTime { param([string]$OutText = "") return "" }
function Test-LaneProviderRefusal {
  param([string]$OutText = "", $ExitCode = $null, [bool]$TimedOut = $false, [bool]$LaneGrew = $true)
  $r = [pscustomobject]@{ IsRefusal = $false; Verdict = ""; Signature = ""; Status = "";
                          ResetAtRaw = ""; NearMiss = $false; NearMissBy = ""; Reason = ""; FailedGate = "" }
  if ($TimedOut) { $r.FailedGate = "1-timed-out"; return $r }
  $t = ""
  if ($null -ne $ExitCode) { $t = ([string]$ExitCode).Trim() }
  if ($t -notmatch '^-?\d+$' -or [int]$t -eq 0) { $r.FailedGate = "2"; return $r }
  if ($LaneGrew) { $r.FailedGate = "3"; return $r }
  $r.IsRefusal = $true; $r.Verdict = "PROVIDER_REFUSED"
  $r.Signature = "SABOTAGE-matches-anything"; $r.Status = "429"
  $r.Reason = "SABOTAGE: gate 4 removed"
  return $r
}
'@ | Set-Content -LiteralPath $useRefusal -Encoding ASCII
}

$fails  = New-Object System.Collections.ArrayList
$passes = 0
function Check($name, $ok, $detail) {
  if ($ok) { $script:passes++; Write-Host ("  PASS  " + $name + "   " + $detail) }
  else { [void]$script:fails.Add($name + " :: " + $detail); Write-Host ("  FAIL  " + $name + "   " + $detail) }
}
# TOLERANT BY MEASUREMENT, NOT BY HABIT. Under -SabotageSignature the watcher
# keeps running and keeps appending, and a plain Get-Content raced it: the
# sabotage run on 2026-10-16 10:12 aborted with "being used by another process"
# AFTER its assertions had already been recorded. A read that fails must not end
# the harness, and - because a swallowed read error became a false "the lock is
# free" in this estate once already - a read that NEVER succeeds is reported
# rather than returned as "".
function LogText {
  if (-not (Test-Path -LiteralPath $WatchLog)) { return "" }
  for ($i = 1; $i -le 12; $i++) {
    try { return [System.IO.File]::ReadAllText($WatchLog) } catch { Start-Sleep -Milliseconds 120 }
  }
  Write-Host "  ... WARNING: the watch log could not be read in 12 attempts; this read is UNKNOWN, not empty"
  return "<UNREADABLE>"
}

$script:watchPid = $null
function WaitFor($pattern, $seconds, $what) {
  $end = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $end) {
    if ((LogText) -match $pattern) { return $true }
    if ($script:watchPid -and -not (Get-Process -Id $script:watchPid -ErrorAction SilentlyContinue)) {
      if ((LogText) -match $pattern) { return $true }
      Write-Host ("  ... the watcher (pid " + $script:watchPid + ") is GONE and " + $what + " never appeared")
      return $false
    }
    Start-Sleep -Milliseconds 300
  }
  Write-Host ("  ... timed out after " + $seconds + "s waiting for " + $what)
  return $false
}
function WaitForCount($pattern, $n, $seconds, $what) {
  $end = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $end) {
    if (([regex]::Matches((LogText), $pattern)).Count -ge $n) { return $true }
    if ($script:watchPid -and -not (Get-Process -Id $script:watchPid -ErrorAction SilentlyContinue)) {
      if (([regex]::Matches((LogText), $pattern)).Count -ge $n) { return $true }
      Write-Host ("  ... the watcher is GONE at " + ([regex]::Matches((LogText), $pattern)).Count +
                  " of " + $n + " " + $what)
      return $false
    }
    Start-Sleep -Milliseconds 300
  }
  Write-Host ("  ... timed out waiting for " + $n + "x " + $what +
              " (saw " + ([regex]::Matches((LogText), $pattern)).Count + ")")
  return $false
}
function IsAlive($thePid) {
  if ($null -eq $thePid) { return $false }
  return [bool](Get-Process -Id $thePid -ErrorAction SilentlyContinue)
}

# name|length|sha256 for every .md in the queue DIRECTORY ITSELF (not DONE, not
# RUNNING), sorted. This is the authority for "byte-identical".
function QueueSnapshot {
  $sha = [System.Security.Cryptography.SHA256]::Create()
  $rows = @()
  foreach ($f in @(Get-ChildItem -LiteralPath $Queue -Filter *.md -ErrorAction SilentlyContinue | Sort-Object Name)) {
    $b = [System.IO.File]::ReadAllBytes($f.FullName)
    $h = [BitConverter]::ToString($sha.ComputeHash($b)).Replace("-", "").Substring(0, 16)
    $rows += ($f.Name + "|" + $b.Length + "|" + $h)
  }
  $sha.Dispose()
  if ($rows.Count -eq 0) { return "<empty>" }
  return ($rows -join "  ;  ")
}
function ShowQueue($label) {
  Write-Host ("    QUEUE " + $label.PadRight(26) + " " + (QueueSnapshot))
}

function Brief($name, $mode, $body) {
  # Every element parenthesised: in PowerShell the comma binds tighter than +,
  # so an unparenthesised list is one flattened string. Diagnosed by the
  # endtoend harness on 2026-10-15 after three legs exited 9.
  $text = @(
    ("# SCRATCH BRIEF - " + $name),
    ("MODE: " + $mode),
    "",
    $body) -join "`r`n"
  if (($text -split "`n").Count -lt 4) {
    throw ("the brief for " + $name + " came out as " + ($text -split "`n").Count + " line(s).")
  }
  Set-Content -LiteralPath (Join-Path $Queue $name) -Encoding ASCII -Value $text
}

$taskTemplate = '/c powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' +
                $FakeTask + '" -BriefPath "{BRIEF}" -MarkerDir "' + $Markers +
                '" -LaneFile "' + $LaneFile + '" < "{BRIEF}" > "{OUT}" 2>&1'

function LaunchWatcher($extraArgs) {
  $launcher = Join-Path $Root ("run-watcher-" + [guid]::NewGuid().ToString("N").Substring(0, 6) + ".ps1")
  # THE TEMPLATE GOES THROUGH A FILE, NOT -ArgumentList. Start-Process wraps an
  # element containing spaces in double quotes and the template has its own
  # quotes around {BRIEF} and {OUT}, which terminate that wrapper early. The
  # endtoend harness lost a whole run to this.
  $t =
    '& "' + $Watcher + '" `' + "`n" +
    '  -Lane ''' + $Lane + ''' `' + "`n" +
    '  -Worktree ''' + $Wt + ''' `' + "`n" +
    '  -Ops ''' + $ScratchOps + ''' `' + "`n" +
    '  -TreeKillPath ''' + $TreeKill + ''' `' + "`n" +
    '  -RefusalModulePath ''' + $useRefusal + ''' `' + "`n" +
    '  -TaskCommandTemplate ''' + $taskTemplate.Replace("'", "''") + ''' `' + "`n" +
    '  -TaskTimeoutMinutes 2 `' + "`n" +
    '  -TreeSampleSeconds 30 `' + "`n" +
    '  -IdleSleepSeconds 3 `' + "`n" +
    '  -RefusalBackoffSeconds ' + $Backoff + ' `' + "`n" +
    '  -MaxRefusalBackoffSeconds ' + $Backoff + ' `' + "`n" +
    '  ' + $extraArgs + ' `' + "`n" +
    '  -PermissionMode default' + "`n"
  Set-Content -LiteralPath $launcher -Value $t -Encoding ASCII
  $p = Start-Process -FilePath "powershell.exe" -PassThru -NoNewWindow -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $launcher)
  $null = $p.Handle
  return $p
}

Write-Host ""
Write-Host "=== the lane watcher, a provider refusal, and its control =================="
Write-Host ("scratch   " + $Root)
Write-Host ("watcher   " + $Watcher)
Write-Host ("refusal   " + $useRefusal + $(if ($SabotageSignature) { "   (SABOTAGE CONTROL: this one calls every failure a refusal)" } else { "" }))
Write-Host ("backoff   " + $Backoff + "s (flat, so the harness finishes)")
Write-Host ""

$wp = $null
$wp2 = $null
try {
  Brief "0010-taskfail.md" "taskfail" "THE CONTROL. Fail like an ordinary task. Must be consumed to DONE as exit1."
  Brief "0020-nowork.md"   "nowork"   "Exit 0 without touching the lane file. Must be NOWORK."
  Brief "0030-exit0.md"    "exit0"    "Grow the lane file and exit 0. Must be exit0."
  Brief "0040-refused.md"  "refused"  "Print the provider's real 429 refusal and exit 1. Must be RETURNED to the queue."

  $snapStart = QueueSnapshot
  Write-Host "--- the queue before the watcher starts ------------------------------------"
  ShowQueue "at start"
  Write-Host ""

  $wp = LaunchWatcher "-MaxConsecutiveRefusals 0"
  $script:watchPid = $wp.Id
  Write-Host ("watcher pid " + $wp.Id)
  $up = WaitFor "watcher up\." 30 "'watcher up.'"
  Check "watcher started" $up "the scratch watcher logged its banner"
  if (-not $up) { Write-Host (LogText); throw "watcher did not start" }
  Check "the refusal module is named in the log" ((LogText) -match [regex]::Escape("refusalmod=" + $useRefusal)) `
        "a reader of this log can tell which classifier took the decisions below"
  Check "scratch, not live, is named in the log" ((LogText) -match [regex]::Escape("ops=" + $ScratchOps)) `
        "a test run and a live run are distinguishable in the log"

  # ------------------------------------------------------------------- CASE 2
  # THE CONTROL, AND IT RUNS FIRST. It is case 2 in the brief's numbering; it is
  # leg 1 here because if the patch returns ordinary failures to the queue, this
  # brief comes back, sorts first, and nothing else in this harness ever runs.
  Write-Host ""
  Write-Host "--- CASE 2 (THE CONTROL)  an ordinary task failure must still be eaten ----"
  Check "control dispatched" (WaitFor "START 0010-taskfail\.md" 30 "START 0010") "the watcher claimed it"
  Check "control recorded as exit1" (WaitFor "DONE  0010-taskfail\.md -> exit1" 90 "the DONE line") `
        "exit 1, no lane growth, a traceback and no 429 - the behaviour that exists today"
  Check "control moved to DONE" (WaitFor "MOVED 0010-taskfail\.md ->" 60 "the MOVED line") "consumed"
  Check "control was NOT classified a refusal" (-not ((LogText) -match "REFUSED  0010-taskfail")) `
        "no REFUSED line for it: the string gate held, so the patch is not returning every failure"
  # NOT A BARE Test-Path, AND THE SABOTAGE RUN IS WHY. On 2026-10-16 10:12 the
  # -SabotageSignature run made this assertion PASS while the patch was wrong:
  # the brief had been returned to the queue and then immediately claimed back
  # into RUNNING, so at the instant the directory was read it was in neither
  # place. A control that can pass for a timing reason is not a control. The
  # log-based half cannot race: a RETURNED line, once written, stays written.
  $ctlReturned = ([regex]::Matches((LogText), "RETURNED 0010-taskfail\.md ->")).Count
  Check "control was never RETURNED to the queue" `
        ($ctlReturned -eq 0 -and -not (Test-Path -LiteralPath (Join-Path $Queue "0010-taskfail.md"))) `
        ($ctlReturned.ToString() + " RETURNED lines for the control. THIS is the assertion that fails if the patch is wrong")
  $dTf = @(Get-ChildItem -LiteralPath $Done -Filter "*exit1-0010-taskfail.md" -ErrorAction SilentlyContinue)
  Check "control has exactly one DONE entry, suffixed exit1" ($dTf.Count -eq 1) `
        ($(if ($dTf.Count -eq 1) { $dTf[0].Name } else { "found " + $dTf.Count }))
  # WHAT THE CONTROL ACTUALLY PRINTED, echoed verbatim. The brief for TASK 0175
  # requires the entry to state that this case was run and what it printed: a
  # report that does not show the control's own bytes is asking to be believed
  # rather than read.
  Write-Host ""
  Write-Host "    the control's own output (" -NoNewline
  $ctlOut = @(Get-ChildItem -LiteralPath $LogDir -Filter "task-*.out" -ErrorAction SilentlyContinue |
              Sort-Object Name | Select-Object -First 1)
  if ($ctlOut.Count -eq 1) {
    Write-Host ($ctlOut[0].Name + ", " + $ctlOut[0].Length + " bytes):")
    foreach ($ln in @(Get-Content -LiteralPath $ctlOut[0].FullName)) { Write-Host ("      | " + $ln) }
    $ctlText = (Get-Content -LiteralPath $ctlOut[0].FullName -Raw)
    Check "the control printed a traceback" ($ctlText -match "Traceback \(most recent call last\)") "an ordinary task failure"
    Check "the control printed NO usage-limit text" (-not ($ctlText -match "Usage limit reached")) `
          "so the only thing separating it from the refusal case is the text"
    Check "the control printed NO 429" (-not ($ctlText -match "\b429\b")) "same exit code, same lane growth, different words"
  } else {
    Write-Host "NOT FOUND)"
    Check "the control's .out was captured" $false ("found " + $ctlOut.Count + " .out files")
  }
  Write-Host ""
  ShowQueue "after the control"

  # ------------------------------------------------------------------- CASE 3
  Write-Host ""
  Write-Host "--- CASE 3  exit 0 with no lane growth -> NOWORK, unchanged ---------------"
  Check "NOWORK detected" (WaitFor ("NOWORK: exit 0 but LANE-" + $Lane + "\.md did not grow") 90 "the NOWORK line") `
        "unchanged from today"
  Check "NOWORK recorded and consumed" (WaitFor "DONE  0020-nowork\.md -> NOWORK" 60 "the DONE line") "consumed"
  Check "NOWORK brief is not back in the queue" (-not (Test-Path -LiteralPath (Join-Path $Queue "0020-nowork.md"))) `
        "the new path did not reach it"

  # ------------------------------------------------------------------- CASE 4
  Write-Host ""
  Write-Host "--- CASE 4  exit 0 with lane growth -> exit0, unchanged -------------------"
  Check "exit0 recorded and consumed" (WaitFor "DONE  0030-exit0\.md -> exit0" 120 "the DONE line") "unchanged from today"
  Check "exit0 brief is not back in the queue" (-not (Test-Path -LiteralPath (Join-Path $Queue "0030-exit0.md"))) `
        "the new path did not reach it"

  # ------------------------------------------------------------------- CASE 1
  Write-Host ""
  Write-Host "--- CASE 1  the provider refusal -> returned, not consumed ----------------"
  $snapBefore = QueueSnapshot
  ShowQueue "BEFORE the refusal"
  Check "refusal dispatched" (WaitFor "START 0040-refused\.md" 60 "START 0040") "the watcher claimed it"
  Check "REFUSED verdict written" (WaitFor "REFUSED  0040-refused\.md -> PROVIDER_REFUSED" 120 "the REFUSED line") `
        "a verdict that is not exit0, not exit1 and not NOWORK"
  Check "the matched signature is named in the log" ((LogText) -match "signature=api-error-429 status=429") `
        "the record says WHICH wording fired, not merely that something did"
  Check "the provider's reset time is logged, not scheduled against" `
        ((LogText) -match [regex]::Escape("the provider states a reset at '2026-10-16 08:07:16'")) `
        "and the line says it is the provider's clock, +6h from this machine"
  Check "RETURNED, under the original name" (WaitFor "RETURNED 0040-refused\.md ->" 60 "the RETURNED line") `
        "back into queue\\<lane>\\, not into DONE"

  $okReturned = WaitForCount "RETURNED 0040-refused\.md ->" 1 60 "RETURNED"
  Start-Sleep -Milliseconds 400
  $snapAfter = QueueSnapshot
  ShowQueue "AFTER the refusal"
  Check "the queue is BYTE-IDENTICAL across the refusal" ($snapAfter -eq $snapBefore) `
        ($(if ($snapAfter -eq $snapBefore) { "same names, same lengths, same SHA256" }
           else { "BEFORE " + $snapBefore + "   AFTER " + $snapAfter }))
  Check "nothing for the refusal is in DONE" `
        (@(Get-ChildItem -LiteralPath $Done -Filter "*0040-refused.md" -ErrorAction SilentlyContinue).Count -eq 0) `
        "DONE\\ holds no entry for a task that did not run"
  Check "no DONE verdict line was written for it" (-not ((LogText) -match "DONE  0040-refused\.md ->")) `
        "the DONE line is reserved for a task that ran"
  Check "DONE still holds exactly the three that ran" `
        (@(Get-ChildItem -LiteralPath $Done -Filter *.md).Count -eq 3) `
        ("DONE holds " + @(Get-ChildItem -LiteralPath $Done -Filter *.md).Count + ": " +
         ((@(Get-ChildItem -LiteralPath $Done -Filter *.md) | ForEach-Object { $_.Name }) -join ", "))
  Check "a cool-down was logged" ((LogText) -match "COOL-DOWN \d+s before this lane looks at the queue again") `
        "the lane does not take the same brief back in five seconds"

  # --------------------------------------------------------------- FOUR IN A ROW
  Write-Host ""
  Write-Host "--- LEG 5  four refusals in a row, and the three-failure guard ------------"
  $ok4 = WaitForCount "RETURNED 0040-refused\.md ->" 4 ((($Backoff + 12) * 4) + 60) "RETURNED"
  $nReturned = ([regex]::Matches((LogText), "RETURNED 0040-refused\.md ->")).Count
  $nRefused  = ([regex]::Matches((LogText), "REFUSED  0040-refused\.md -> PROVIDER_REFUSED")).Count
  Check "four refusals, four returns" ($ok4 -and $nReturned -ge 4) `
        ($nRefused.ToString() + " REFUSED lines, " + $nReturned + " RETURNED lines")
  Check "the watcher did NOT exit on the third" `
        (-not ((LogText) -match "consecutive failures\. Exiting")) `
        "MaxConsecutiveFailures=3 and refusals are not counted as failures, so the guard never fired"
  Check "the watcher process is still alive after four" (IsAlive $wp.Id) ("pid " + $wp.Id)
  Check "the queue is still byte-identical after four" ((QueueSnapshot) -eq $snapBefore) `
        ((QueueSnapshot))
  Check "still nothing in DONE for it" `
        (@(Get-ChildItem -LiteralPath $Done -Filter "*0040-refused.md" -ErrorAction SilentlyContinue).Count -eq 0) `
        "four refusals cost zero briefs"
  Check "no unhandled error anywhere in the run" (-not ((LogText) -match "UNHANDLED |watcher down \(unhandled error\)")) `
        "no throw was allowed to become terminating"
  ShowQueue "after four refusals"

  Set-Content -LiteralPath $StopMe -Value "refusal test" -Encoding ASCII
  Check "STOP-<lane> stops it during a cool-down" (WaitFor "watcher down\." 60 "'watcher down.'") `
        "the cool-down is sliced, so the operator's brake is not up to 30 minutes slow"
  Remove-Item -LiteralPath $StopMe -Force -ErrorAction SilentlyContinue

  # ------------------------------------------------------------- THE OTHER BOUND
  Write-Host ""
  Write-Host "--- LEG 6  -MaxConsecutiveRefusals 2: the lane stops, the brief stays -----"
  $logBefore = (LogText).Length
  $wp2 = LaunchWatcher "-MaxConsecutiveRefusals 2"
  $script:watchPid = $wp2.Id
  Write-Host ("second watcher pid " + $wp2.Id)
  Check "second watcher started" (WaitFor "maxrefusals=2" 30 "the banner with maxrefusals=2") "bound set to 2"
  Check "it stops on the second refusal" (WaitFor "2 consecutive provider refusals\. Exiting" 180 "the refusal-bound line") `
        "a lane that only ever refuses does not idle forever looking alive"
  Check "it says nothing was lost" ((LogText) -match "NOTHING WAS LOST: every refused brief is back in queue") `
        "the exit line names the consequence rather than leaving it to be inferred"
  Check "it exited" (WaitFor "watcher down\." 60 "'watcher down.'") "cleanly"
  Start-Sleep -Milliseconds 500
  Check "the brief is STILL in the queue after the bound fired" `
        ((QueueSnapshot) -eq $snapBefore) ((QueueSnapshot))
  Check "and still nothing in DONE for it" `
        (@(Get-ChildItem -LiteralPath $Done -Filter "*0040-refused.md" -ErrorAction SilentlyContinue).Count -eq 0) `
        "the bound bounds the lane, not the brief"
  ShowQueue "at the very end"

  # -------------------------------------------------- the whole-run accounting
  Write-Host ""
  Write-Host "--- the accounting ---------------------------------------------------------"
  $finalQ = @(Get-ChildItem -LiteralPath $Queue -Filter *.md | ForEach-Object { $_.Name })
  Check "exactly one brief is left queued, and it is the refused one" `
        ($finalQ.Count -eq 1 -and $finalQ[0] -eq "0040-refused.md") (($finalQ -join ", "))
  Check "RUNNING is empty" `
        (@(Get-ChildItem -LiteralPath $Running -Filter *.md -ErrorAction SilentlyContinue).Count -eq 0) `
        "nothing stranded"
  Check "three briefs ran, three DONE entries, no fourth" `
        (@(Get-ChildItem -LiteralPath $Done -Filter *.md).Count -eq 3) `
        ((@(Get-ChildItem -LiteralPath $Done -Filter *.md) | ForEach-Object { $_.Name }) -join ", ")
}
catch {
  [void]$fails.Add("HARNESS ABORTED :: " + $_.Exception.Message + " @line " + $_.InvocationInfo.ScriptLineNumber)
}
finally {
  foreach ($p in @($wp, $wp2)) {
    if ($p -and (IsAlive $p.Id)) {
      Write-Host ("cleanup: watcher pid " + $p.Id + " still alive; stopping it")
      try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch { }
    }
  }
  foreach ($f in @(Get-ChildItem -LiteralPath $Markers -Filter "*.pid" -ErrorAction SilentlyContinue)) {
    $v = (Get-Content -LiteralPath $f.FullName -Raw).Trim()
    if ($v -match '^\d+$' -and (IsAlive ([int]$v))) {
      Write-Host ("cleanup: fake-task pid " + $v + " still alive; stopping it")
      try { Stop-Process -Id ([int]$v) -Force -ErrorAction SilentlyContinue } catch { }
    }
  }
  Write-Host ""
  Write-Host "=== RESULT ================================================================="
  Write-Host ("  passed " + $passes + "   failed " + $fails.Count)
  foreach ($f in $fails) { Write-Host ("  FAILED: " + $f) }
  $keep = Join-Path $env:TEMP ("lane-ref-last-" + $Lane + ".log")
  try { Copy-Item -LiteralPath $WatchLog -Destination $keep -Force; Write-Host ("  log copied to " + $keep) } catch { }
  if ($KeepScratch) { Write-Host ("  scratch kept: " + $Root) }
  else { try { Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue } catch { } }
}

if ($fails.Count -gt 0) { exit 1 }
exit 0
