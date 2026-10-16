<#
  test_lane_drain_premise.ps1 - measure what STOP-<lane> ACTUALLY does when it
  is written while a task is running.

  ASCII ONLY, same reason as the files it tests.

  WHY THIS EXISTS, AND IT IS A PREMISE CHECK BEFORE A BUILD. The brief for qwen
  TASK 0180 says:

      "the only ways to rotate a lane were: close its window by hand, or write
       STOP-<lane> and wait. Both are fine for an idle lane. NEITHER IS SAFE
       for a lane mid-task - the task is a `claude -p` child that survives its
       wrapper, so stopping the watcher abandons a running process with no one
       left to write its DONE line."

  That is true of CLOSING THE WINDOW. Reading lane_watcher.ps1 says it should
  NOT be true of the STOP FILE: both STOP checks sit at the TOP of the while
  loop, and the task runs, is recorded and is moved between them and the next
  iteration. So a STOP file written mid-task should be invisible until the
  current task has completed, been given its DONE line and been moved.

  READING IS NOT MEASURING, so this file measures it. The standing rules say a
  premise in a task file may be wrong and that "the premise did not survive" is
  a better result than work built on it.

  THE MEASUREMENT HAS TO PIN THE ORDER, not just the outcome. A STOP file
  written after a task happened to finish would show the same end state and
  prove nothing. So `slowexit0` writes two markers, `slowexit0.started` and
  `slowexit0.finished`, and this harness asserts that the STOP file was created
  strictly BETWEEN them - and that the finished marker appeared AFTER the STOP
  file - using file timestamps, which is an order claim rather than an outcome
  claim.

  WHY IT IS SAFE. Everything is in %TEMP% via -Ops. The lane is called
  "draintest", which is not a lane, and real lane names are refused by name. The
  STOP file is created under the SCRATCH ops root, never under the live one -
  asserted explicitly below, because TASK 0180's boundaries forbid creating a
  real STOP-<lane>. `claude` is never invoked.
#>
param(
  [string]$Lane = "draintest",
  [int]$WorkSeconds = 25,
  [switch]$KeepScratch
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
$FakeTask = Join-Path $RepoOps "fake_lane_task.ps1"
foreach ($f in @($Watcher, $TreeKill, $Refusal, $FakeTask)) {
  if (-not (Test-Path -LiteralPath $f)) { Write-Host ("MISSING: " + $f); exit 2 }
}
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Write-Host "PRECONDITION UNMET: the watcher refuses to start without 'claude' on PATH."; exit 2
}

$Root       = Join-Path $env:TEMP ("lane-drain-" + [guid]::NewGuid().ToString("N").Substring(0, 12))
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
$LockFile   = Join-Path $LogDir ("watcher-" + $Lane + ".pid")

if ($ScratchOps.TrimEnd('\') -ieq $LiveOps.TrimEnd('\')) {
  Write-Host "REFUSING: the scratch ops path resolved to the live one."; exit 2
}
# TASK 0180's boundary, asserted rather than trusted: the STOP file this harness
# writes must not be anywhere under the live ops root.
if ($StopMe.ToLower().StartsWith($LiveOps.ToLower())) {
  Write-Host ("REFUSING: the STOP path is inside the live estate: " + $StopMe); exit 2
}
foreach ($d in @($Queue, $Done, $Running, $LogDir, $Markers,
                 (Join-Path $ScratchOps "tools"), (Join-Path $Wt ".git"))) {
  New-Item -ItemType Directory -Path $d -Force | Out-Null
}
Set-Content -LiteralPath $LaneFile -Value ("# LANE-" + $Lane + " (scratch)") -Encoding UTF8

# EVERY lane_*.ps1 BESIDE THIS HARNESS IS DEPLOYED INTO THE SCRATCH tools\,
# DERIVED AND NOT LISTED. A hardcoded list is exactly what broke this harness:
# it was written on 2026-10-16 10:38 against a watcher that needed two modules,
# and TASK 0200 then made tools\lane_orphan.ps1 a HARD dependency - the watcher
# exits 2 with "REFUSING: the orphan resolver is missing" - so on 2026-10-16
# 14:21 every leg that needs a live watcher failed, 4 of 5, for a reason that
# had nothing to do with the premise under test. Deriving the set means the next
# module added to the watcher cannot repeat it.
#
# Deployed into $ScratchOps\tools rather than injected by -XxxModulePath,
# because that is how the LIVE estate resolves them: a fixture that injects
# every path by hand cannot notice a dependency nobody injected.
$deployedMods = @()
foreach ($m in @(Get-ChildItem -LiteralPath $RepoOps -Filter "lane_*.ps1" -File)) {
  if ($m.Name -ieq "lane_watcher.ps1") { continue }
  Copy-Item -LiteralPath $m.FullName -Destination (Join-Path $ScratchOps ("tools\" + $m.Name)) -Force
  $deployedMods += $m.Name
}

$fails  = New-Object System.Collections.ArrayList
$passes = 0
function Check($name, $ok, $detail) {
  if ($ok) { $script:passes++; Write-Host ("  PASS  " + $name + "   " + $detail) }
  else { [void]$script:fails.Add($name + " :: " + $detail); Write-Host ("  FAIL  " + $name + "   " + $detail) }
}
function LogText {
  if (-not (Test-Path -LiteralPath $WatchLog)) { return "" }
  for ($i = 1; $i -le 12; $i++) {
    try { return [System.IO.File]::ReadAllText($WatchLog) } catch { Start-Sleep -Milliseconds 120 }
  }
  Write-Host "  ... WARNING: the watch log could not be read; this read is UNKNOWN, not empty"
  return "<UNREADABLE>"
}
$script:watchPid = $null
function WaitFor($pattern, $seconds, $what) {
  $end = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $end) {
    if ((LogText) -match $pattern) { return $true }
    if ($script:watchPid -and -not (Get-Process -Id $script:watchPid -ErrorAction SilentlyContinue)) {
      if ((LogText) -match $pattern) { return $true }
      Write-Host ("  ... the watcher is GONE and " + $what + " never appeared"); return $false
    }
    Start-Sleep -Milliseconds 250
  }
  Write-Host ("  ... timed out after " + $seconds + "s waiting for " + $what); return $false
}
function WaitForFile($path, $seconds) {
  $end = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $end) {
    if (Test-Path -LiteralPath $path) { return $true }
    Start-Sleep -Milliseconds 150
  }
  return $false
}
function IsAlive($thePid) {
  if ($null -eq $thePid) { return $false }
  return [bool](Get-Process -Id $thePid -ErrorAction SilentlyContinue)
}
function Stamp($path) {
  if (-not (Test-Path -LiteralPath $path)) { return $null }
  return (Get-Item -LiteralPath $path).LastWriteTime
}

$text = @(
  "# SCRATCH BRIEF - 0010-slow.md",
  "MODE: slowexit0",
  "",
  ("Work for " + $WorkSeconds + "s and then complete cleanly.")) -join "`r`n"
Set-Content -LiteralPath (Join-Path $Queue "0010-slow.md") -Encoding ASCII -Value $text

$taskTemplate = '/c powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' +
                $FakeTask + '" -BriefPath "{BRIEF}" -MarkerDir "' + $Markers +
                '" -LaneFile "' + $LaneFile + '" -WorkSeconds ' + $WorkSeconds +
                ' < "{BRIEF}" > "{OUT}" 2>&1'

$launcher = Join-Path $Root "run-watcher.ps1"
Set-Content -LiteralPath $launcher -Encoding ASCII -Value (
  '& "' + $Watcher + '" `' + "`n" +
  '  -Lane ''' + $Lane + ''' `' + "`n" +
  '  -Worktree ''' + $Wt + ''' `' + "`n" +
  '  -Ops ''' + $ScratchOps + ''' `' + "`n" +
  '  -TreeKillPath ''' + $TreeKill + ''' `' + "`n" +
  '  -RefusalModulePath ''' + $Refusal + ''' `' + "`n" +
  '  -TaskCommandTemplate ''' + $taskTemplate.Replace("'", "''") + ''' `' + "`n" +
  '  -TaskTimeoutMinutes 5 `' + "`n" +
  '  -TreeSampleSeconds 60 `' + "`n" +
  '  -IdleSleepSeconds 3 `' + "`n" +
  '  -PermissionMode default' + "`n")

Write-Host ""
Write-Host "=== does STOP-<lane> written MID-TASK drain, or abandon? ==================="
Write-Host ("scratch     " + $Root)
Write-Host ("work        " + $WorkSeconds + "s")
Write-Host ("STOP path   " + $StopMe)
Write-Host ""

$wp = $null
try {
  $wp = Start-Process -FilePath "powershell.exe" -PassThru -NoNewWindow -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $launcher)
  $null = $wp.Handle
  $script:watchPid = $wp.Id
  Write-Host ("watcher pid " + $wp.Id)
  Check "watcher up" (WaitFor "watcher up\." 30 "'watcher up.'") "banner logged"
  Check "task dispatched" (WaitFor "START 0010-slow\.md" 30 "START") "the brief was claimed"

  # THE TASK IS PROVEN TO BE RUNNING BEFORE THE STOP FILE IS WRITTEN. Without
  # this the whole measurement would be "a STOP file was written at some point",
  # which is the thing it is supposed to distinguish.
  Check "the task really started" (WaitForFile (Join-Path $Markers "slowexit0.started") 30) `
        "slowexit0.started exists, so a task is genuinely in flight"
  $tStarted = Stamp (Join-Path $Markers "slowexit0.started")
  Check "the task has NOT finished yet" (-not (Test-Path -LiteralPath (Join-Path $Markers "slowexit0.finished"))) `
        "slowexit0.finished absent - we are strictly mid-task"
  $laneBefore = (Get-Item -LiteralPath $LaneFile).Length

  Write-Host ""
  Write-Host "--- writing STOP-<lane> NOW, with the task still running -------------------"
  Set-Content -LiteralPath $StopMe -Value "drain premise check" -Encoding ASCII
  $tStop = Stamp $StopMe
  Write-Host ("    STOP written at " + $tStop.ToString("HH:mm:ss.fff") +
              "   task started at " + $tStarted.ToString("HH:mm:ss.fff"))
  Check "STOP was written AFTER the task started" ($tStop -gt $tStarted) `
        "so the STOP file is genuinely mid-task, not before it"
  Check "the watcher did not die on the spot" (IsAlive $wp.Id) `
        ("pid " + $wp.Id + " still alive immediately after the STOP file appeared")

  # ---------------------------------------------------- the question itself
  Write-Host ""
  Write-Host "--- what happens to the task that was already running? ---------------------"
  $finished = WaitForFile (Join-Path $Markers "slowexit0.finished") ($WorkSeconds + 90)
  Check "THE RUNNING TASK WAS ALLOWED TO FINISH" $finished `
        "slowexit0.finished exists: the STOP file did not abandon it"
  if ($finished) {
    $tFin = Stamp (Join-Path $Markers "slowexit0.finished")
    Write-Host ("    task finished at " + $tFin.ToString("HH:mm:ss.fff"))
    Check "it finished AFTER the STOP file was written" ($tFin -gt $tStop) `
          ("STOP " + $tStop.ToString("HH:mm:ss.fff") + " -> finished " + $tFin.ToString("HH:mm:ss.fff") +
           ". THIS is the order that decides the premise.")
  }
  Check "the task's work reached the lane file" ((Get-Item -LiteralPath $LaneFile).Length -gt $laneBefore) `
        ($laneBefore.ToString() + " -> " + (Get-Item -LiteralPath $LaneFile).Length + " bytes")
  Check "ITS DONE LINE WAS WRITTEN" (WaitFor "DONE  0010-slow\.md -> exit0" 60 "the DONE line") `
        "somebody was still there to record it - this is what the brief feared would be lost"
  Check "and the brief was MOVED to DONE" (WaitFor "MOVED 0010-slow\.md ->" 60 "the MOVED line") "recorded and filed"
  $d = @(Get-ChildItem -LiteralPath $Done -Filter "*exit0-0010-slow.md" -ErrorAction SilentlyContinue)
  Check "DONE holds exactly one entry for it, suffixed exit0" ($d.Count -eq 1) `
        ($(if ($d.Count -eq 1) { $d[0].Name } else { "found " + $d.Count }))

  # ------------------------------------------------- and only THEN does it stop
  Write-Host ""
  Write-Host "--- and only then does the watcher stop ------------------------------------"
  Check "the STOP file was honoured" (WaitFor ("STOP-" + $Lane + " present\. Exiting\.") 60 "the STOP line") `
        "noticed at the TOP of the next iteration, not during the task"
  Check "watcher down" (WaitFor "watcher down\." 60 "'watcher down.'") "cleanly"
  Check "no unhandled error" (-not ((LogText) -match "UNHANDLED |watcher down \(unhandled error\)")) "clean exit path"
  Check "nothing stranded in RUNNING" `
        (@(Get-ChildItem -LiteralPath $Running -Filter *.md -ErrorAction SilentlyContinue).Count -eq 0) `
        "RUNNING is empty"

  # THE PID LOCK IS RELEASED, which is what a rotation has to wait for.
  $lockGone = $false
  $end = (Get-Date).AddSeconds(30)
  while ((Get-Date) -lt $end) {
    if (-not (Test-Path -LiteralPath $LockFile)) { $lockGone = $true; break }
    Start-Sleep -Milliseconds 200
  }
  Check "THE PID LOCK IS GONE" $lockGone `
        ("watcher-" + $Lane + ".pid removed, so a replacement watcher can take the lane. " +
         "This is the signal a rotation must wait on.")
  Check "the watcher process has exited" (-not (IsAlive $wp.Id)) ("pid " + $wp.Id + " gone")

  # ----------------------------------------------------- the ORDER, in the log
  Write-Host ""
  Write-Host "--- the order, straight out of the log -------------------------------------"
  $t = LogText
  $iStart = $t.IndexOf("START 0010-slow.md")
  $iDone  = $t.IndexOf("DONE  0010-slow.md ->")
  $iMoved = $t.IndexOf("MOVED 0010-slow.md ->")
  $iStop  = $t.IndexOf("STOP-" + $Lane + " present")
  $iDown  = $t.IndexOf("watcher down.")
  Write-Host ("    offsets  START=" + $iStart + "  DONE=" + $iDone + "  MOVED=" + $iMoved +
              "  STOP=" + $iStop + "  DOWN=" + $iDown)
  Check "log order is START < DONE < MOVED < STOP-honoured < down" `
        ($iStart -ge 0 -and $iDone -gt $iStart -and $iMoved -gt $iDone -and
         $iStop -gt $iMoved -and $iDown -gt $iStop) `
        "the STOP file is acted on strictly after the task is recorded and filed"
}
catch {
  [void]$fails.Add("HARNESS ABORTED :: " + $_.Exception.Message + " @line " + $_.InvocationInfo.ScriptLineNumber)
}
finally {
  if ($wp -and (IsAlive $wp.Id)) {
    Write-Host ("cleanup: watcher pid " + $wp.Id + " still alive; stopping it")
    try { Stop-Process -Id $wp.Id -Force -ErrorAction SilentlyContinue } catch { }
  }
  Write-Host ""
  Write-Host "=== RESULT ================================================================="
  Write-Host ("  passed " + $passes + "   failed " + $fails.Count)
  foreach ($f in $fails) { Write-Host ("  FAILED: " + $f) }
  if ($KeepScratch) { Write-Host ("  scratch kept: " + $Root) }
  else { try { Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue } catch { } }
}

if ($fails.Count -gt 0) { exit 1 }
exit 0
