<#
  test_lane_deadline_in_child_env.ps1 - does a lane task actually SEE its own
  deadline?

  ASCII ONLY. Same reason as the files it tests: Windows PowerShell 5.1 reads a
  BOM-less .ps1 in the system ANSI codepage and a UTF-8 dash can become a string
  delimiter.

  WHAT IT PROVES. qwen TASK 0150 D2: the watcher computes the kill time and
  tells the child nothing, so a task cannot tell a 15-minute remainder from a
  90-minute one. `glm 0065` and `pilotcaps 0130` were both killed at exactly
  90:00 while doing real work and their real processes carried on for 25 and 64
  minutes with no watcher left to record a DONE line.

  The assertion is on the INHERITED ENVIRONMENT OF A REAL CHILD of the real
  watcher - a marker file the fake task writes from `$env:LANE_DEADLINE` - and
  never on the watcher's source text. Three independent properties, because
  each one has its own way of being wrong:

    1  it ARRIVES            a missing export leaves the marker empty
    2  it is an INSTANT      exporting the duration (150) parses as nothing,
                             and that is exactly what D2 warned against
    3  it is THIS task's     a stale or sign-flipped instant lands outside the
                             window [launch + timeout, launch + timeout + 60s]

  Property 3 is what makes the test more than a presence check. The window's
  lower bound is strictly after the harness's own t0 plus the timeout, so a
  deadline computed from any other moment fails it.

  WHY IT IS SAFE. The watcher's whole blast radius travels with -Ops, so one
  parameter moves the queue, RUNNING, DONE, the logs, the LANE file and the STOP
  files into %TEMP%. The live ops path is refused by name, the lane is called
  "deadlinetest" which is not a lane, `claude` is never invoked, and the only
  process this harness stops is the watcher it started itself, by the pid it
  recorded. No lock is taken. Nothing outside the scratch root is written.
#>
param(
  [string]$Lane = "deadlinetest",
  # 0.5 min = 30s. Long enough that the window below is not a coin toss, short
  # enough that the whole run is under a minute. The task under test exits at
  # once; the timeout is never reached and nothing is killed.
  [double]$TimeoutMinutes = 0.5,
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
$FakeTask = Join-Path $RepoOps "fake_lane_task.ps1"
foreach ($f in @($Watcher, $TreeKill, $FakeTask)) {
  if (-not (Test-Path -LiteralPath $f)) { Write-Host ("MISSING: " + $f); exit 2 }
}

$Root       = Join-Path $env:TEMP ("lane-deadline-" + [guid]::NewGuid().ToString("N").Substring(0, 12))
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
$Marker     = Join-Path $Markers "lane-deadline.env"

if ($ScratchOps.TrimEnd('\') -ieq $LiveOps.TrimEnd('\')) {
  Write-Host "REFUSING: the scratch ops path resolved to the live one."; exit 2
}

foreach ($d in @($Queue, $Done, $Running, $LogDir, $Markers,
                 (Join-Path $ScratchOps "tools"), (Join-Path $Wt ".git"))) {
  New-Item -ItemType Directory -Path $d -Force | Out-Null
}
Set-Content -LiteralPath $LaneFile -Value "# LANE-$Lane (scratch)" -Encoding UTF8

# EVERY ELEMENT PARENTHESISED. In PowerShell the comma binds tighter than +, so
# @("a" + $x, "b" + $y) is one string concatenated with an array and comes out
# as a single line joined by $OFS. That cost the e2e harness two whole runs.
$briefText = @(
  "# SCRATCH BRIEF - deadline",
  "MODE: exit0",
  "",
  "Grow the lane file, record LANE_DEADLINE as the child sees it, exit 0.") -join "`r`n"
Set-Content -LiteralPath (Join-Path $Queue "0010-deadline.md") -Encoding ASCII -Value $briefText

$taskTemplate = '/c powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' +
                $FakeTask + '" -BriefPath "{BRIEF}" -MarkerDir "' + $Markers +
                '" -LaneFile "' + $LaneFile + '" < "{BRIEF}" > "{OUT}" 2>&1'

$fails = New-Object System.Collections.ArrayList
$passes = 0
function Check($name, $ok, $detail) {
  if ($ok) { $script:passes++; Write-Host ("  PASS  " + $name + "   " + $detail) }
  else { [void]$script:fails.Add($name + " :: " + $detail); Write-Host ("  FAIL  " + $name + "   " + $detail) }
}
function LogText { if (Test-Path -LiteralPath $WatchLog) { return (Get-Content -LiteralPath $WatchLog -Raw) } return "" }

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
function WaitForFile($path, $seconds) {
  $end = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $end) {
    if (Test-Path -LiteralPath $path) { return $true }
    Start-Sleep -Milliseconds 200
  }
  return $false
}

Write-Host ""
Write-Host "=== LANE_DEADLINE reaches the child ========================================"
Write-Host ("scratch   " + $Root)
Write-Host ("watcher   " + $Watcher)
Write-Host ("timeout   " + $TimeoutMinutes + " min")
Write-Host ""

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Write-Host "PRECONDITION UNMET: the watcher refuses to start without claude on PATH."
  Write-Host "That guard is unrelated to what this test measures, but it does block it."
  exit 2
}

# A LAUNCHER FILE, not -ArgumentList. Start-Process wraps an element containing
# spaces in double quotes and the task template carries its own, which
# terminates that wrapper early and silently destroys it.
$launcher = Join-Path $Root "run-watcher.ps1"
Set-Content -LiteralPath $launcher -Encoding ASCII -Value (
  '& "' + $Watcher + '" `' + "`n" +
  '  -Lane ''' + $Lane + ''' `' + "`n" +
  '  -Worktree ''' + $Wt + ''' `' + "`n" +
  '  -Ops ''' + $ScratchOps + ''' `' + "`n" +
  '  -TreeKillPath ''' + $TreeKill + ''' `' + "`n" +
  '  -TaskCommandTemplate ''' + $taskTemplate.Replace("'", "''") + ''' `' + "`n" +
  '  -TaskTimeoutMinutes ' + $TimeoutMinutes + ' `' + "`n" +
  '  -TreeSampleSeconds 2 `' + "`n" +
  '  -IdleSleepSeconds 3 `' + "`n" +
  '  -PermissionMode default' + "`n")

# t0 IS TAKEN BEFORE THE WATCHER EXISTS, so every later instant is strictly
# after it. This is what makes the window assertion a real bound rather than a
# restatement of whatever the watcher happened to write.
$t0 = Get-Date
$watcherProc = $null
try {
  $watcherProc = Start-Process -FilePath "powershell.exe" -PassThru -NoNewWindow -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $launcher)
  $null = $watcherProc.Handle
  $script:watchPid = $watcherProc.Id
  Write-Host ("watcher pid " + $watcherProc.Id)

  $up = WaitFor "watcher up\." 30 "'watcher up.'"
  Check "watcher started" $up "the scratch watcher logged its banner"
  if (-not $up) {
    Write-Host ""
    Write-Host "ABORTING: the watcher never came up, so nothing below could be measured."
    Write-Host (LogText)
    throw "watcher did not start"
  }

  Check "leg dispatched" (WaitFor "START 0010-deadline\.md" 25 "START 0010") "the watcher claimed the brief"

  # The watcher's own line. Secondary: it proves the watcher knows the value,
  # not that the child received it, which is what the marker below is for.
  Check "the watcher logs the deadline it exported" ((LogText) -match "LANE_DEADLINE=\S") `
        "the figure is in the lane log, so a reader can reconstruct a kill"

  Check "the child wrote its marker" (WaitForFile $Marker 30) `
        "a real child of the real watcher recorded what it could see"

  $seen = ""
  if (Test-Path -LiteralPath $Marker) { $seen = (Get-Content -LiteralPath $Marker -Raw).Trim() }

  # --- 1  IT ARRIVES
  Check "LANE_DEADLINE is set in the child environment" ($seen -ne "") `
        ($(if ($seen -ne "") { "'" + $seen + "'" } else { "the marker is EMPTY: the variable did not reach the child" }))

  # --- 2  IT IS AN INSTANT, NOT A DURATION
  $parsed = [datetimeoffset]::MinValue
  $ok = [datetimeoffset]::TryParse($seen, [ref]$parsed)
  Check "it is an ISO-8601 instant, not a duration" $ok `
        ($(if ($ok) { "parsed as " + $parsed.ToString("o") } else { "'" + $seen + "' does not parse as an instant - this is the D2 failure: exporting the DURATION" }))
  Check "it carries an offset, so it is not ambiguous" ($seen -match '[+\-]\d{2}:\d{2}$') `
        ("tail of '" + $seen + "'")

  # --- 3  IT IS THIS TASK'S DEADLINE
  # [$t0 + timeout, $t0 + timeout + 60s]. The watcher starts, reads its
  # parameters, claims the brief and only then computes the deadline, so the
  # true value is always a little after the lower bound and well inside the
  # upper one. A stale instant, a sign flip or a deadline taken from any other
  # moment lands outside.
  $low  = $t0.AddMinutes($TimeoutMinutes)
  $high = $t0.AddMinutes($TimeoutMinutes).AddSeconds(60)
  $inWindow = $false
  if ($ok) {
    $local = $parsed.LocalDateTime
    $inWindow = ($local -ge $low -and $local -le $high)
  }
  Check "it is THIS task's deadline, in the expected window" $inWindow `
        ("t0=" + $t0.ToString("HH:mm:ss") + " window=[" + $low.ToString("HH:mm:ss") +
         ".." + $high.ToString("HH:mm:ss") + "] got=" +
         $(if ($ok) { $parsed.LocalDateTime.ToString("HH:mm:ss") } else { "UNPARSEABLE" }))

  # --- the reader on the other side agrees
  # The Python module that every lane will actually call, run against the exact
  # bytes this child saw. A format the watcher can write and the reader cannot
  # parse would be a feature that works only in this harness.
  if ($seen -ne "") {
    $py = Join-Path $Root "readback.py"
    Set-Content -LiteralPath $py -Encoding ASCII -Value @(
      "import sys",
      "sys.path.insert(0, sys.argv[2])",
      "from src import lanedeadline",
      "v = lanedeadline.decide(legs=1, env={'LANE_DEADLINE': sys.argv[1]})",
      "print(v['decision'], v['source'], round(v['minutes_left'] or -999, 1))")
    $repoRoot = Split-Path -Parent (Split-Path -Parent $RepoOps)
    $out = & py -3 $py $seen $repoRoot 2>&1
    Check "src/lanedeadline.py parses what the watcher wrote" (("" + $out) -match "LANE_DEADLINE") `
          ("readback: " + ("" + $out).Trim())
  }

  Check "DONE -> exit0 written" (WaitFor "DONE  0010-deadline\.md -> exit0" 60 "the DONE line") "the task completed normally"
  Check "no unhandled error" (-not ((LogText) -match "UNHANDLED |watcher down \(unhandled error\)")) `
        "the extra export did not disturb the loop"

  Set-Content -LiteralPath $StopMe -Value "deadline test" -Encoding ASCII
  Check "STOP-<lane> stops it cleanly" (WaitFor "watcher down\." 60 "'watcher down.'") "and the pid lock is released"
}
catch {
  [void]$fails.Add("HARNESS ABORTED :: " + $_.Exception.Message)
}
finally {
  if ($watcherProc -and (Get-Process -Id $watcherProc.Id -ErrorAction SilentlyContinue)) {
    Write-Host ("cleanup: watcher pid " + $watcherProc.Id + " is still alive; stopping it")
    try { Stop-Process -Id $watcherProc.Id -Force -ErrorAction SilentlyContinue } catch { }
  }
  Write-Host ""
  Write-Host "=== RESULT ================================================================="
  Write-Host ("  passed " + $passes + "   failed " + $fails.Count)
  foreach ($f in $fails) { Write-Host ("  FAILED: " + $f) }
  if ($KeepScratch) {
    Write-Host ("  scratch kept: " + $Root)
  } else {
    try { Copy-Item -LiteralPath $WatchLog -Destination (Join-Path $env:TEMP ("lane-deadline-last-" + $Lane + ".log")) -Force } catch { }
    try { Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue } catch { }
  }
}

if ($fails.Count -gt 0) { exit 1 }
exit 0
