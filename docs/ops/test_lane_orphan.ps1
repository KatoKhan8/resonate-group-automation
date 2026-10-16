<#
  test_lane_orphan.ps1 - prove that a RUNNING brief whose claiming watcher is
  dead gets moved aside and the lane keeps working, and that every other case
  leaves the brief exactly where it is.

  ASCII ONLY, same reason as the files it tests.

  WHY IT IS SAFE. Everything lives in %TEMP% via -Ops. The lane is called
  "orphantest", which is not a lane, and the real lane names are refused by
  name before anything is created. No real STOP file is ever written: the only
  STOP path this harness can produce is under the scratch ops root, asserted
  below. `claude` is never invoked - the watcher is pointed at
  fake_lane_task.ps1 through -TaskCommandTemplate. No real lane's RUNNING
  directory, log, pid lock or worktree is read or written.

  TWO PARTS, AND THEY ANSWER DIFFERENT QUESTIONS.

  PART A drives Resolve-LaneOrphanedRunning directly with an INJECTED process
  table. That is the only way to test a decision about a process that does not
  exist, a recycled pid, an unreadable table, and a table that comes back empty
  - none of which can be arranged on a real machine on demand. Every leg
  asserts the VERDICT and the ACTION separately, because "did not move the
  brief" is true of both ALIVE and UNKNOWN and they are not the same answer.

  PART B runs real watchers against a real scratch queue, because the thing
  that has to work is the watcher, not the function. It covers the four states
  the task brief names, including the one that needs two watchers at once.

  THE REGRESSION CONTROL THAT MATTERS MOST is A13. Before it existed, the
  sidecar's key came from Get-Process .StartTime and was compared against
  Get-LaneProcTable's key, which comes from CIM .CreationDate. Measured on this
  machine, for one live process, those differ by FOUR TICKS - CIM truncates to
  microseconds. The keys could therefore never match, so a LIVE claiming
  watcher would have been read as DEAD and its brief moved aside under it. A13
  is a real Write-LaneClaim followed by a real Test-LaneClaimOwner against a
  real table, and it goes red if anybody reintroduces a second source for that
  value.
#>
param(
  [string]$Lane = "orphantest",
  [int]$WorkSeconds = 45,
  [switch]$KeepScratch,
  [switch]$SkipPartB
)

$ErrorActionPreference = "Stop"

$LiveOps   = "C:\Users\Zvonimir\Desktop\resonate-ops"
$RealLanes = @("glm", "glm-b", "glm-c", "pilotcaps", "qwen", "suppression", "webapp")
if ($RealLanes -contains $Lane) {
  Write-Host ("REFUSING: '" + $Lane + "' is a real lane. This harness never names one."); exit 2
}

$RepoOps  = Split-Path -Parent $PSCommandPath
$Watcher  = Join-Path $RepoOps "lane_watcher.ps1"
$TreeKill = Join-Path $RepoOps "lane_treekill.ps1"
$Refusal  = Join-Path $RepoOps "lane_refusal.ps1"
$Orphan   = Join-Path $RepoOps "lane_orphan.ps1"
$FakeTask = Join-Path $RepoOps "fake_lane_task.ps1"
foreach ($f in @($Watcher, $TreeKill, $Refusal, $Orphan, $FakeTask)) {
  if (-not (Test-Path -LiteralPath $f)) { Write-Host ("MISSING: " + $f); exit 2 }
}

. $TreeKill
. $Orphan
foreach ($fn in @("Get-LaneProcTable", "Get-LaneProcKey", "Write-LaneClaim",
                  "Test-LaneClaimOwner", "Resolve-LaneOrphanedRunning", "Remove-LaneClaim")) {
  if (-not (Get-Command $fn -ErrorAction SilentlyContinue)) {
    Write-Host ("MISSING FUNCTION: " + $fn); exit 2
  }
}

$Root       = Join-Path $env:TEMP ("lane-orphan-" + [guid]::NewGuid().ToString("N").Substring(0, 12))
$ScratchOps = Join-Path $Root "ops"
if ($ScratchOps.TrimEnd('\') -ieq $LiveOps.TrimEnd('\')) {
  Write-Host "REFUSING: the scratch ops path resolved to the live one."; exit 2
}
if ($ScratchOps.ToLower().StartsWith($LiveOps.ToLower())) {
  Write-Host ("REFUSING: the scratch ops path is inside the live estate: " + $ScratchOps); exit 2
}

$fails  = New-Object System.Collections.ArrayList
$passes = 0
function Check($name, $ok, $detail) {
  if ($ok) { $script:passes++; Write-Host ("  PASS  " + $name + "   " + $detail) }
  else { [void]$script:fails.Add($name + " :: " + $detail); Write-Host ("  FAIL  " + $name + "   " + $detail) }
}

# ==========================================================================
# PART A - the resolver, with the process table injected
# ==========================================================================
Write-Host ""
Write-Host "PART A - Resolve-LaneOrphanedRunning against injected process tables"

$ACase = 0
function NewCase {
  param([string]$tag)
  $script:ACase++
  $dir = Join-Path $Root ("a" + $script:ACase + "-" + $tag)
  $run = Join-Path $dir "RUNNING"
  $don = Join-Path $dir "DONE"
  New-Item -ItemType Directory -Path $run -Force | Out-Null
  New-Item -ItemType Directory -Path $don -Force | Out-Null
  return [pscustomobject]@{ Dir = $dir; Running = $run; Done = $don }
}
function PutBrief {
  param($case, [string]$name = "0010-brief.md")
  $p = Join-Path $case.Running $name
  Set-Content -LiteralPath $p -Value "# scratch brief" -Encoding ASCII
  return $p
}
function PutSidecar {
  param([string]$runPath, [string]$body)
  Set-Content -LiteralPath ($runPath + ".claim") -Value $body -Encoding ASCII
}
# A table that is well-formed and contains this reader, so the resolver's own
# self-check passes and the leg under test is the only thing being measured.
function FakeTable {
  param([hashtable]$extra = @{})
  $t = @{}
  $me = Get-LaneProcTable
  $t[$PID] = $me[$PID]
  foreach ($k in $extra.Keys) { $t[[int]$k] = $extra[$k] }
  return $t
}
function Row {
  param([int]$rowPid, [string]$name, [string]$key)
  return [pscustomobject]@{ Pid = $rowPid; Ppid = 0; Name = $name; Created = $null; Key = $key }
}
$quiet = { param($m) }

# ---- A1 nothing in RUNNING
$c = NewCase "empty"
$r = Resolve-LaneOrphanedRunning -Running $c.Running -Done $c.Done -Lane $Lane -LogFn $quiet -ProcTable (FakeTable)
Check "A1 empty RUNNING is Action NONE" ($r.Action -eq "NONE") ("Action=" + $r.Action)

# ---- A2 no sidecar at all (the legacy case)
$c = NewCase "nosidecar"; $b = PutBrief $c
$r = Resolve-LaneOrphanedRunning -Running $c.Running -Done $c.Done -Lane $Lane -LogFn $quiet -ProcTable (FakeTable)
Check "A2 no sidecar is UNKNOWN" ($r.Verdict -eq "UNKNOWN") ("Verdict=" + $r.Verdict)
Check "A2 no sidecar LEAVES the brief" (($r.Action -eq "LEFT") -and (Test-Path -LiteralPath $b)) ("Action=" + $r.Action)
Check "A2 nothing was put in DONE" (@(Get-ChildItem $c.Done).Count -eq 0) "DONE is empty"

# ---- A3 owner absent from the table -> DEAD, moved aside
$c = NewCase "dead"; $b = PutBrief $c
PutSidecar $b ("schema=1`nlane=" + $Lane + "`npid=999999`nkey=999999|123`nname=powershell.exe`nclaimed_at=2026-10-16 01:00:00")
$r = Resolve-LaneOrphanedRunning -Running $c.Running -Done $c.Done -Lane $Lane -LogFn $quiet -ProcTable (FakeTable)
Check "A3 absent pid is DEAD" ($r.Verdict -eq "DEAD") ("Verdict=" + $r.Verdict)
Check "A3 the brief was MOVED" ($r.Action -eq "MOVED") ("Action=" + $r.Action)
Check "A3 RUNNING is now clear" (-not (Test-Path -LiteralPath $b)) "the brief is gone from RUNNING"
$moved = @(Get-ChildItem $c.Done -Filter *.md)
Check "A3 it is in DONE, named for a human" (
  ($moved.Count -eq 1) -and ($moved[0].Name -like "*-ORPHANED-NEEDS-REVIEW-0010-brief.md")
) ("DONE holds: " + (($moved | ForEach-Object { $_.Name }) -join ", "))
Check "A3 it was NOT returned to a queue" (
  -not (Test-Path -LiteralPath (Join-Path $c.Dir "0010-brief.md"))
) "no copy outside DONE"
Check "A3 the sidecar went with it" (-not (Test-Path -LiteralPath ($b + ".claim"))) "sidecar removed"

# ---- A4 pid present but the creation key differs -> pid reuse -> DEAD
$c = NewCase "reused"; $b = PutBrief $c
PutSidecar $b ("schema=1`npid=4242`nkey=4242|111111`nname=powershell.exe`nclaimed_at=x")
$t = FakeTable @{ 4242 = (Row 4242 "powershell.exe" "4242|999999") }
$r = Resolve-LaneOrphanedRunning -Running $c.Running -Done $c.Done -Lane $Lane -LogFn $quiet -ProcTable $t
Check "A4 recycled pid is DEAD, not alive" ($r.Verdict -eq "DEAD") ("Verdict=" + $r.Verdict + " :: " + $r.Why)
Check "A4 and it is moved aside" ($r.Action -eq "MOVED") ("Action=" + $r.Action)

# ---- A5 pid and key both match -> ALIVE, untouched
$c = NewCase "alive"; $b = PutBrief $c
PutSidecar $b ("schema=1`npid=4242`nkey=4242|111111`nname=powershell.exe`nclaimed_at=x")
$t = FakeTable @{ 4242 = (Row 4242 "powershell.exe" "4242|111111") }
$r = Resolve-LaneOrphanedRunning -Running $c.Running -Done $c.Done -Lane $Lane -LogFn $quiet -ProcTable $t
Check "A5 matching key is ALIVE" ($r.Verdict -eq "ALIVE") ("Verdict=" + $r.Verdict)
Check "A5 ALIVE leaves the brief" (($r.Action -eq "LEFT") -and (Test-Path -LiteralPath $b)) ("Action=" + $r.Action)
Check "A5 the sidecar is untouched" (Test-Path -LiteralPath ($b + ".claim")) "sidecar still there"

# ---- A6 garbage sidecar -> UNKNOWN
$c = NewCase "garbage"; $b = PutBrief $c
PutSidecar $b "this is not a sidecar, it is a sandwich"
$r = Resolve-LaneOrphanedRunning -Running $c.Running -Done $c.Done -Lane $Lane -LogFn $quiet -ProcTable (FakeTable)
Check "A6 garbage sidecar is UNKNOWN" ($r.Verdict -eq "UNKNOWN") ("Verdict=" + $r.Verdict)
Check "A6 garbage LEAVES the brief" (($r.Action -eq "LEFT") -and (Test-Path -LiteralPath $b)) ("Action=" + $r.Action)

# ---- A7 unreadable sidecar (held open with no sharing) -> UNKNOWN
$c = NewCase "unreadable"; $b = PutBrief $c
PutSidecar $b ("schema=1`npid=999999`nkey=999999|1`nname=powershell.exe")
$fs = [System.IO.File]::Open(($b + ".claim"), 'Open', 'Read', 'None')
try {
  $r = Resolve-LaneOrphanedRunning -Running $c.Running -Done $c.Done -Lane $Lane -LogFn $quiet -ProcTable (FakeTable)
} finally { $fs.Close(); $fs.Dispose() }
Check "A7 unreadable sidecar is UNKNOWN, not dead" ($r.Verdict -eq "UNKNOWN") ("Verdict=" + $r.Verdict + " :: " + $r.Why)
Check "A7 unreadable LEAVES the brief" (($r.Action -eq "LEFT") -and (Test-Path -LiteralPath $b)) ("Action=" + $r.Action)

# ---- A8 an empty process table -> UNKNOWN (catalogue entry 4)
$c = NewCase "emptytable"; $b = PutBrief $c
PutSidecar $b ("schema=1`npid=999999`nkey=999999|1`nname=powershell.exe")
$r = Resolve-LaneOrphanedRunning -Running $c.Running -Done $c.Done -Lane $Lane -LogFn $quiet -ProcTable @{}
Check "A8 empty table is UNKNOWN, not dead" ($r.Verdict -eq "UNKNOWN") ("Verdict=" + $r.Verdict)
Check "A8 empty table LEAVES the brief" (($r.Action -eq "LEFT") -and (Test-Path -LiteralPath $b)) ("Action=" + $r.Action)

# ---- A9 a table that does not contain the reader itself -> UNKNOWN
$c = NewCase "notself"; $b = PutBrief $c
PutSidecar $b ("schema=1`npid=999999`nkey=999999|1`nname=powershell.exe")
$t = @{ 4242 = (Row 4242 "notepad.exe" "4242|1") }
$r = Resolve-LaneOrphanedRunning -Running $c.Running -Done $c.Done -Lane $Lane -LogFn $quiet -ProcTable $t
Check "A9 a table without our own pid is UNKNOWN" ($r.Verdict -eq "UNKNOWN") ("Verdict=" + $r.Verdict + " :: " + $r.Why)
Check "A9 and it LEAVES the brief" (($r.Action -eq "LEFT") -and (Test-Path -LiteralPath $b)) ("Action=" + $r.Action)

# ---- A10 no key, pid now holds something that is not a shell -> DEAD
$c = NewCase "nokey-notshell"; $b = PutBrief $c
PutSidecar $b ("schema=1`npid=4242`nkey=`nname=powershell.exe")
$t = FakeTable @{ 4242 = (Row 4242 "notepad.exe" "4242|7") }
$r = Resolve-LaneOrphanedRunning -Running $c.Running -Done $c.Done -Lane $Lane -LogFn $quiet -ProcTable $t
Check "A10 no key + non-shell pid is DEAD" ($r.Verdict -eq "DEAD") ("Verdict=" + $r.Verdict)

# ---- A11 no key, pid now holds a shell -> UNKNOWN (a name cannot prove it)
$c = NewCase "nokey-shell"; $b = PutBrief $c
PutSidecar $b ("schema=1`npid=4242`nkey=`nname=powershell.exe")
$t = FakeTable @{ 4242 = (Row 4242 "powershell.exe" "4242|7") }
$r = Resolve-LaneOrphanedRunning -Running $c.Running -Done $c.Done -Lane $Lane -LogFn $quiet -ProcTable $t
Check "A11 no key + shell pid is UNKNOWN, not alive and not dead" ($r.Verdict -eq "UNKNOWN") ("Verdict=" + $r.Verdict)
Check "A11 and it LEAVES the brief" (($r.Action -eq "LEFT") -and (Test-Path -LiteralPath $b)) ("Action=" + $r.Action)

# ---- A12 two briefs in RUNNING: report it, resolve only the first
$c = NewCase "two"; $b1 = PutBrief $c "0010-brief.md"; $b2 = PutBrief $c "0020-brief.md"
PutSidecar $b1 ("schema=1`npid=999999`nkey=999999|1`nname=powershell.exe")
PutSidecar $b2 ("schema=1`npid=999999`nkey=999999|1`nname=powershell.exe")
$said = New-Object System.Collections.ArrayList
$rec  = { param($m) [void]$said.Add($m) }
$r = Resolve-LaneOrphanedRunning -Running $c.Running -Done $c.Done -Lane $Lane -LogFn $rec -ProcTable (FakeTable)
Check "A12 the second brief is reported" (($said -join " ") -match "2 briefs are in RUNNING") "the count is logged"
Check "A12 only the first is resolved" (
  ($r.Brief -eq "0010-brief.md") -and (-not (Test-Path -LiteralPath $b1)) -and (Test-Path -LiteralPath $b2)
) ("resolved " + $r.Brief + "; 0020 still in RUNNING")

# ---- A13 THE REGRESSION CONTROL: a real claim, a real table, must read ALIVE
$c = NewCase "roundtrip"; $b = PutBrief $c
$w = Write-LaneClaim -RunPath $b -Lane $Lane -WatchLog "none"
Check "A13 the sidecar was written" $w.Ok ("path=" + (Split-Path -Leaf $w.Path))
$claim = Read-LaneClaim -RunPath $b
Check "A13 it carries this process's pid" ($claim.ClaimPid -eq $PID) ("pid=" + $claim.ClaimPid + " expected " + $PID)
Check "A13 it carries a non-empty creation key" ($claim.Key -ne "") ("key=" + $claim.Key)
$own = Test-LaneClaimOwner -RunPath $b
Check "A13 a LIVE claimer reads ALIVE against a real table" ($own.Verdict -eq "ALIVE") ("Verdict=" + $own.Verdict + " :: " + $own.Why)
# and prove the key really is the table's own value, which is what the 4-tick
# measurement is about: a second source here is the bug.
$liveTable = Get-LaneProcTable
Check "A13 the key equals Get-LaneProcTable's key for this pid" (
  $claim.Key -eq $liveTable[$PID].Key
) ("sidecar=" + $claim.Key + " table=" + $liveTable[$PID].Key)
# NOT AN ASSERTION, AND THAT IS THE POINT. An earlier version of this leg
# asserted that the table key DIFFERS from the Get-Process key. It is flaky by
# construction: the gap is CIM's truncation to microseconds, so it is 0 to 9
# ticks depending on where the creation time happened to land, and a delta of 0
# is perfectly possible. It went red once in a mutation run and the mutation was
# blamed. The requirement is the leg above - the sidecar key IS the table's key -
# so the delta is now measured and printed rather than asserted.
$gpKey = Get-LaneProcKey -ProcPid $PID -Created (Get-Process -Id $PID).StartTime
$delta = [int64]($gpKey.Split("|")[1]) - [int64]($liveTable[$PID].Key.Split("|")[1])
Write-Host ("  INFO  A13 Get-Process is " + $delta + " ticks from CIM for this process; " +
            "the module uses the CIM value on both sides, so the gap cannot matter")
Remove-LaneClaim -RunPath $b
Check "A13 Remove-LaneClaim removes it" (-not (Test-Path -LiteralPath ($b + ".claim"))) "sidecar gone"

if ($SkipPartB) {
  Write-Host ""
  Write-Host ("PART B skipped. passes=" + $passes + " fails=" + $fails.Count)
  if ($fails.Count -gt 0) { $fails | ForEach-Object { Write-Host ("  " + $_) }; exit 1 }
  exit 0
}

# ==========================================================================
# PART B - real watchers, real scratch queue
# ==========================================================================
Write-Host ""
Write-Host "PART B - real watchers against a scratch lane"

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Write-Host "PRECONDITION UNMET: the watcher refuses to start without 'claude' on PATH."
  Write-Host "  (it is never invoked; -TaskCommandTemplate points at fake_lane_task.ps1)"
  exit 2
}

$Queue    = Join-Path $ScratchOps ("queue\" + $Lane)
$Running  = Join-Path $Queue "RUNNING"
$Done     = Join-Path $Queue "DONE"
$LogDir   = Join-Path $ScratchOps "logs"
$WatchLog = Join-Path $LogDir ("watcher-" + $Lane + ".log")
$LaneFile = Join-Path $ScratchOps ("LANE-" + $Lane + ".md")
$LockFile = Join-Path $LogDir ("watcher-" + $Lane + ".pid")
$StopMe   = Join-Path $ScratchOps ("STOP-" + $Lane)
$Wt       = Join-Path $Root "wt"
$Markers  = Join-Path $Root "markers"

if ($StopMe.ToLower().StartsWith($LiveOps.ToLower())) {
  Write-Host ("REFUSING: the STOP path is inside the live estate: " + $StopMe); exit 2
}
foreach ($d in @($Queue, $Running, $Done, $LogDir, $Markers,
                 (Join-Path $ScratchOps "tools"), (Join-Path $Wt ".git"))) {
  New-Item -ItemType Directory -Path $d -Force | Out-Null
}
Set-Content -LiteralPath $LaneFile -Value ("# LANE-" + $Lane + " (scratch)") -Encoding UTF8

function LogText {
  if (-not (Test-Path -LiteralPath $WatchLog)) { return "" }
  for ($i = 1; $i -le 12; $i++) {
    try { return [System.IO.File]::ReadAllText($WatchLog) } catch { Start-Sleep -Milliseconds 120 }
  }
  Write-Host "  ... WARNING: the watch log could not be read; this read is UNKNOWN, not empty"
  return "<UNREADABLE>"
}
function WaitForLog($pattern, $seconds) {
  $end = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $end) {
    if ((LogText) -match $pattern) { return $true }
    Start-Sleep -Milliseconds 250
  }
  return $false
}
$taskTemplate = '/c powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' +
                $FakeTask + '" -BriefPath "{BRIEF}" -MarkerDir "' + $Markers +
                '" -LaneFile "' + $LaneFile + '" -WorkSeconds ' + $WorkSeconds +
                ' < "{BRIEF}" > "{OUT}" 2>&1'
# A LAUNCHER FILE, NOT -ArgumentList, and this cost a measurement.
# Start-Process -ArgumentList joins its elements with spaces and does NOT quote
# them, so -TaskCommandTemplate (which contains spaces and quotes) was split
# into a dozen POSITIONAL arguments. They bound to the watcher's typed
# parameters and it refused with
#     Cannot convert value "powershell.exe" to type "System.Int32"
#     on parameter MaxConsecutiveFailures
# which reads exactly like the code under test failing, and is not. Writing the
# invocation to a .ps1 and running the file keeps the quoting intact, which is
# what test_lane_drain_premise.ps1 already does and why it does it.
$script:launchSeq = 0
function StartWatcher {
  param([switch]$Wait, [string]$OrphanPath = "")
  if ($OrphanPath -eq "") { $OrphanPath = $Orphan }
  $script:launchSeq++
  $launcher = Join-Path $Root ("run-watcher-" + $script:launchSeq + ".ps1")
  $q = [string][char]39
  $lines = @(
    ('& "' + $Watcher + '" `'),
    ('  -Lane ' + $q + $Lane + $q + ' `'),
    ('  -Worktree ' + $q + $Wt + $q + ' `'),
    ('  -Ops ' + $q + $ScratchOps + $q + ' `'),
    ('  -TreeKillPath ' + $q + $TreeKill + $q + ' `'),
    ('  -RefusalModulePath ' + $q + $Refusal + $q + ' `'),
    ('  -OrphanModulePath ' + $q + $OrphanPath + $q + ' `'),
    ('  -TaskCommandTemplate ' + $q + $taskTemplate.Replace($q, $q + $q) + $q + ' `'),
    ('  -TaskTimeoutMinutes 5 `'),
    ('  -TreeSampleSeconds 60 `'),
    ('  -IdleSleepSeconds 3 `'),
    ('  -PermissionMode acceptEdits'),
    ('exit $LASTEXITCODE')
  )
  Set-Content -LiteralPath $launcher -Encoding ASCII -Value $lines
  $pa = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $launcher)
  if ($Wait) {
    return (Start-Process -FilePath "powershell.exe" -ArgumentList $pa -NoNewWindow -PassThru -Wait)
  }
  return (Start-Process -FilePath "powershell.exe" -ArgumentList $pa -NoNewWindow -PassThru)
}
function StopWatcher($proc) {
  # A STOP file is only read at the top of the loop, so a watcher mid-task will
  # not see it until its task completes - which for the slow fixture task is a
  # whole WorkSeconds away. That is correct behaviour (TASK 0180 measured it) and
  # it is not what a harness wants between legs, so after a short grace the whole
  # tree is killed deliberately. Killing is safe HERE and only here: every pid in
  # it belongs to this fixture, and Stop-LaneProcessTree refuses to touch this
  # process or its ancestors.
  Set-Content -LiteralPath $StopMe -Value "stop" -Encoding ASCII
  if ($proc) {
    for ($i = 0; $i -lt 40 -and -not $proc.HasExited; $i++) { Start-Sleep -Milliseconds 200 }
    if (-not $proc.HasExited) {
      try { Stop-LaneProcessTree -RootPid $proc.Id -Say { param($m) } | Out-Null } catch { }
      try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch { }
    }
    for ($i = 0; $i -lt 50; $i++) {
      if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) { break }
      Start-Sleep -Milliseconds 200
    }
  }
  Remove-Item -LiteralPath $StopMe -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $LockFile -Force -ErrorAction SilentlyContinue
}
function ClearLog { Remove-Item -LiteralPath $WatchLog -Force -ErrorAction SilentlyContinue }
function ClearMarkers {
  Get-ChildItem $Markers -Force -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse
}
function ClearDirs {
  Get-ChildItem $Running -Force -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse
  Get-ChildItem $Done    -Force -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse
  Get-ChildItem $Queue -Filter *.md -ErrorAction SilentlyContinue | Remove-Item -Force
}
function Brief {
  param([string]$name, [string]$mode)
  # PARENTHESISED, and for the third recorded time in this estate. Without the
  # brackets PowerShell parses @("a" + $x, "b" + $y) as "a" + ($x, "b") + $y and
  # collapses the list into ONE space-joined line - so the brief had no MODE line
  # at the start of a line and fake_lane_task.ps1 refused it with exit 9. Its own
  # comment at line 114 records the same trap costing an earlier harness a whole
  # run, and lane_orphan.ps1 hit it today in Write-LaneClaim.
  $t = @(("# SCRATCH BRIEF - " + $name), ("MODE: " + $mode), "", "scratch") -join "`r`n"
  return $t
}

# ---- B1 dead owner end to end: moved aside, and the NEXT brief starts
Write-Host "  B1 a brief in RUNNING whose owner is dead"
ClearDirs; ClearLog
# a real pid that really exits, with its key read from the real table while it
# was alive - so the sidecar is honest and the owner is genuinely gone.
$victim = Start-Process -FilePath "powershell.exe" `
            -ArgumentList @("-NoProfile", "-Command", "Start-Sleep -Milliseconds 1200") `
            -NoNewWindow -PassThru
Start-Sleep -Milliseconds 350
$vTable = Get-LaneProcTable
$vKey = ""
if ($vTable.ContainsKey($victim.Id)) { $vKey = $vTable[$victim.Id].Key }
$victim.WaitForExit()
for ($i = 0; $i -lt 50; $i++) {
  if (-not (Get-Process -Id $victim.Id -ErrorAction SilentlyContinue)) { break }
  Start-Sleep -Milliseconds 100
}
Check "B1 the victim pid really is gone" (
  -not (Get-Process -Id $victim.Id -ErrorAction SilentlyContinue)
) ("pid " + $victim.Id + " exited")
Check "B1 and its key was captured while it lived" ($vKey -ne "") ("key=" + $vKey)

$orphanBrief = Join-Path $Running "0010-orphan.md"
Set-Content -LiteralPath $orphanBrief -Value (Brief "0010-orphan.md" "exit0") -Encoding ASCII
Set-Content -LiteralPath ($orphanBrief + ".claim") -Encoding ASCII -Value @(
  "schema=1", ("lane=" + $Lane), ("pid=" + $victim.Id), ("key=" + $vKey),
  "name=powershell.exe", "claimed_at=2026-10-16 01:00:00", "brief=0010-orphan.md")
Set-Content -LiteralPath (Join-Path $Queue "0020-next.md") -Value (Brief "0020-next.md" "exit0") -Encoding ASCII

$w1 = StartWatcher
$sawOrphan = WaitForLog "ORPHAN CHECK: 0010-orphan\.md was claimed by a watcher that is GONE" 40
$sawNext   = WaitForLog "START 0020-next\.md" 40
StopWatcher $w1
$log = LogText
Check "B1 the orphan is recognised as GONE" $sawOrphan "ORPHAN CHECK logged"
Check "B1 it is moved to DONE for review" (
  @(Get-ChildItem $Done -Filter "*-ORPHANED-NEEDS-REVIEW-0010-orphan.md").Count -eq 1
) ("DONE: " + ((Get-ChildItem $Done | ForEach-Object { $_.Name }) -join ", "))
Check "B1 RUNNING no longer holds it" (-not (Test-Path -LiteralPath $orphanBrief)) "cleared"
Check "B1 THE LANE KEPT WORKING: the next brief started" $sawNext "START 0020-next.md"
Check "B1 the orphan was NOT re-run" (
  ($log -split "`n" | Where-Object { $_ -match "START 0010-orphan\.md" }).Count -eq 0
) "no START line for the orphan"
Check "B1 the log says why a re-run is forbidden" (
  $log -match "THE ORPHAN IS NOT RE-RUN"
) "the 24/64 minute reason is in the log a human reads"

# ---- B2 live owner: the second watcher refuses on the pid lock
Write-Host "  B2 a brief in RUNNING whose owner is alive"
ClearDirs; ClearLog; ClearMarkers
Set-Content -LiteralPath (Join-Path $Queue "0010-slow.md") -Value (Brief "0010-slow.md" "slowexit0") -Encoding ASCII
$w2 = StartWatcher
$started = WaitForLog "START 0010-slow\.md" 40
Check "B2 watcher one claimed the slow brief" $started "START logged"
# THE WINDOW IS AN EXPLICIT CLAIM, not an assumption. B2 and B3 are about a LIVE
# owner, so every assertion below is void if the task has already completed and
# its brief has legitimately moved to DONE. The first run of this harness failed
# exactly there: WorkSeconds was 30, B2 and B3 took longer than that, and four
# legs read as defects when the code was right.
function TaskStillRunning {
  return ((Test-Path -LiteralPath (Join-Path $Markers "slowexit0.started")) -and
          (-not (Test-Path -LiteralPath (Join-Path $Markers "slowexit0.finished"))))
}
# The START line is logged before the child has run a statement, so wait for the
# task to SAY it is working rather than inferring it from the log.
$sawWorking = $false
$endw = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $endw -and -not $sawWorking) {
  if (Test-Path -LiteralPath (Join-Path $Markers "slowexit0.started")) { $sawWorking = $true }
  else { Start-Sleep -Milliseconds 200 }
}
Check "B2 the task is running, so the live-owner legs are testable" ((TaskStillRunning) -and $sawWorking) "started, not finished"
$live = Join-Path $Running "0010-slow.md"
Check "B2 it wrote a claim sidecar" (Test-Path -LiteralPath ($live + ".claim")) "sidecar present"
$claimBytes = $null
if (Test-Path -LiteralPath ($live + ".claim")) { $claimBytes = [System.IO.File]::ReadAllBytes($live + ".claim") }

$second = StartWatcher -Wait
Check "B2 the second watcher REFUSES" ($second.ExitCode -eq 3) ("exit code " + $second.ExitCode)
Check "B2 the brief is untouched" (Test-Path -LiteralPath $live) "still in RUNNING"
$afterBytes = $null
if (Test-Path -LiteralPath ($live + ".claim")) { $afterBytes = [System.IO.File]::ReadAllBytes($live + ".claim") }
Check "B2 the sidecar is byte-identical" (
  ($null -ne $claimBytes) -and ($null -ne $afterBytes) -and
  (([System.Convert]::ToBase64String($claimBytes)) -eq ([System.Convert]::ToBase64String($afterBytes)))
) "unchanged"
Check "B2 nothing was moved to DONE" (
  @(Get-ChildItem $Done -Filter "*ORPHANED*").Count -eq 0
) "no orphan move"

# ---- B3 live owner, lock removed by hand: the SIDECAR is what saves the brief
Write-Host "  B3 a live owner whose pid lock has been removed by hand"
ClearLog
Remove-Item -LiteralPath $LockFile -Force -ErrorAction SilentlyContinue
$third = StartWatcher
Check "B3 the task is STILL running as the third watcher starts" (TaskStillRunning) "window held"
$sawAlive = WaitForLog "ORPHAN CHECK: 0010-slow\.md is claimed by a LIVE watcher" 40
Check "B3 the orphan check reads it ALIVE from the sidecar alone" $sawAlive "ORPHAN CHECK ALIVE logged"
Check "B3 the brief is still in RUNNING" (Test-Path -LiteralPath $live) "untouched"
Check "B3 nothing was moved to DONE" (
  @(Get-ChildItem $Done -Filter "*ORPHANED*").Count -eq 0
) "no orphan move"
Check "B3 and the task was still running when all three legs were taken" (TaskStillRunning) "window held throughout"
StopWatcher $third
StopWatcher $w2

# ---- B4 the legacy case: no sidecar at all
Write-Host "  B4 a brief in RUNNING with no sidecar (every brief in flight today)"
ClearDirs; ClearLog
$legacy = Join-Path $Running "0010-legacy.md"
Set-Content -LiteralPath $legacy -Value (Brief "0010-legacy.md" "exit0") -Encoding ASCII
Set-Content -LiteralPath (Join-Path $Queue "0020-next.md") -Value (Brief "0020-next.md" "exit0") -Encoding ASCII
$w4 = StartWatcher
$sawUnknown = WaitForLog "ORPHAN CHECK: CANNOT DECIDE who owns 0010-legacy\.md" 40
$sawIdle    = WaitForLog "a task is already in RUNNING: 0010-legacy\.md" 40
StopWatcher $w4
$log4 = LogText
Check "B4 it says CANNOT DECIDE" $sawUnknown "logged"
Check "B4 the brief is LEFT in RUNNING" (Test-Path -LiteralPath $legacy) "untouched"
Check "B4 nothing was moved to DONE" (@(Get-ChildItem $Done -Filter "*ORPHANED*").Count -eq 0) "no move"
Check "B4 the lane idles on it, visibly" $sawIdle "the inflight branch behaves as before"
Check "B4 the next brief did NOT start" (
  ($log4 -split "`n" | Where-Object { $_ -match "START 0020-next\.md" }).Count -eq 0
) "the lane is honestly stalled, not silently skipping work"
Check "B4 the log names the one command a human runs" (
  $log4 -match "Move-Item"
) "the hand-clear is in the log"

# ---- B5 a garbage sidecar
Write-Host "  B5 a brief in RUNNING with a garbage sidecar"
ClearDirs; ClearLog
$g = Join-Path $Running "0010-garbage.md"
Set-Content -LiteralPath $g -Value (Brief "0010-garbage.md" "exit0") -Encoding ASCII
Set-Content -LiteralPath ($g + ".claim") -Value "nonsense" -Encoding ASCII
$w5 = StartWatcher
$sawG = WaitForLog "ORPHAN CHECK: CANNOT DECIDE who owns 0010-garbage\.md" 40
StopWatcher $w5
$log5 = LogText
Check "B5 a garbage sidecar is CANNOT DECIDE" $sawG "logged"
Check "B5 the reason names the missing pid" ($log5 -match "no usable pid") "reason is specific"
Check "B5 the brief is LEFT in RUNNING" (Test-Path -LiteralPath $g) "untouched"
Check "B5 nothing was moved to DONE" (@(Get-ChildItem $Done -Filter "*ORPHANED*").Count -eq 0) "no move"

# ---- B6 the module is mandatory: a missing one must REFUSE to start
Write-Host "  B6 the deploy contract: a missing module refuses to start"
ClearDirs; ClearLog
$missing = Join-Path $Root "no-such-orphan-module.ps1"
$b6 = StartWatcher -Wait -OrphanPath $missing
Check "B6 a missing orphan module is exit 2" ($b6.ExitCode -eq 2) ("exit code " + $b6.ExitCode)
Check "B6 and it says so in the log" ((LogText) -match "REFUSING: the orphan resolver is missing") "refusal logged"
Remove-Item -LiteralPath $LockFile -Force -ErrorAction SilentlyContinue

# ==========================================================================
Write-Host ""
Write-Host ("passes=" + $passes + "  fails=" + $fails.Count)
if ($fails.Count -gt 0) {
  Write-Host "FAILED:"
  $fails | ForEach-Object { Write-Host ("  " + $_) }
}
if ($KeepScratch) { Write-Host ("scratch kept at " + $Root) }
else {
  try { Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue } catch { }
}
if ($fails.Count -gt 0) { exit 1 }
exit 0
