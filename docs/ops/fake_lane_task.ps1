<#
  fake_lane_task.ps1 - the task a lane watcher runs when it is under test.

  ASCII ONLY, same reason as lane_watcher.ps1: Windows PowerShell 5.1 reads a
  BOM-less .ps1 in the system ANSI codepage and a UTF-8 dash can become a
  string delimiter.

  WHY THIS EXISTS. qwen TASK 0090 fixed five linked failures in the watcher and
  could only prove the first of them, because $Ops and the task command were
  literals pointing at the live queue and a real `claude -p`. The thing that
  killed the glm and pilotcaps lanes on 2026-10-15 was not the kill, it was the
  CHAIN: the timeout killed the cmd.exe wrapper, `claude` survived holding the
  brief open as its inherited stdin, Move-Item threw, $ErrorActionPreference =
  "Stop" made that terminating, and the script left its own loop. No test could
  touch any of those five links. This file is the third one's other half.

  THE MODE COMES FROM THE BRIEF, NOT FROM A SWITCH. The watcher takes ONE task
  command for its whole life, so a harness that wanted three different task
  behaviours from one watcher would need three watchers - and "the loop is
  still running after the timeout" cannot be proven by a watcher that only ever
  ran one task. Reading the mode out of the brief makes the brief drive the
  behaviour, which is what a real task does too.

  WHAT IT CAN DO, and each one is a link in the chain:

    exit0    writes to the lane file and exits 0         -> exit0
    nowork   exits 0 having written nothing to the lane  -> NOWORK
    hang     sleeps past the deadline, no children       -> TIMEOUT
    orphan   hang, plus a grandchild that OUTLIVES its   -> TIMEOUT
             parent and holds the brief open

  `orphan` is the one that matters. taskkill /T walks LIVE parent links, so a
  grandchild whose parent has already exited is invisible to it; and the handle
  on the brief is what made Move-Item throw. Both are reproduced here, and the
  grandchild writes its pid to the marker directory so a test can assert on an
  identity rather than on a log line.

  STDIN. The brief arrives on stdin exactly as it does for `claude -p`, and
  this script reads it, so the inherited-handle shape of a real run is present
  and not simulated. -BriefPath is passed as well because the grandchild has to
  open that same file by name: `Start-Process` does not inherit handles.
#>
param(
  # Which link to play. Normally absent: it is read from the brief. The two
  # self-spawned roles pass it explicitly, because they have no stdin.
  [ValidateSet("", "exit0", "nowork", "hang", "orphan", "orphan-parent", "orphan-child")]
  [string]$Mode = "",
  [Parameter(Mandatory = $true)][string]$BriefPath,
  # Where pids and markers are written. A test asserts on these, never on a
  # CommandLine substring - TASK 0070 killed its own measurement shell with a
  # `-like "*child.ps1*"` filter that matched its own argv.
  [string]$MarkerDir = "",
  [string]$LaneFile = "",
  [int]$HangSeconds = 600,
  [int]$ParentLifeSeconds = 5,
  [int]$ChildLifeSeconds = 300
)

$ErrorActionPreference = "Stop"

function Say($m) {
  Write-Host ("[fake-task " + $PID + "] " + $m)
}

function Mark($name, $value) {
  if ($MarkerDir -eq "") { return }
  if (-not (Test-Path -LiteralPath $MarkerDir)) {
    New-Item -ItemType Directory -Path $MarkerDir -Force | Out-Null
  }
  Set-Content -LiteralPath (Join-Path $MarkerDir $name) -Value $value -Encoding ASCII
}

# ---------------------------------------------------------------- the mode
# Read stdin whether or not the mode is already known: the point of reading it
# is that the handle on the brief exists, which is the link under test.
$stdin = ""
if ($Mode -eq "" -or $Mode -eq "exit0" -or $Mode -eq "nowork" -or
    $Mode -eq "hang" -or $Mode -eq "orphan") {
  try { $stdin = [Console]::In.ReadToEnd() } catch { $stdin = "" }
}

if ($Mode -eq "") {
  $src = $stdin
  if ($src.Trim() -eq "") {
    # Falling back to the file is not the same measurement as reading stdin,
    # so it is logged rather than smoothed over.
    Say "stdin was empty; falling back to the brief on disk. THE STDIN LINK WAS NOT EXERCISED."
    $src = Get-Content -LiteralPath $BriefPath -Raw
  }
  $m = [regex]::Match($src, '(?m)^\s*MODE:\s*([a-z0-9-]+)\s*$')
  if (-not $m.Success) {
    # SHOW WHAT WAS READ. The first harness run got exit 9 three times with
    # nothing to say why, and the cause was a brief whose four lines had been
    # written as one. A refusal that does not name the bytes it refused costs a
    # whole run to diagnose.
    Say "REFUSING: the brief carries no 'MODE: <mode>' line. Not guessing one."
    $shown = $src
    if ($shown.Length -gt 400) { $shown = $shown.Substring(0, 400) + " ...[truncated]" }
    Say ("what I read (" + $src.Length + " bytes, " +
         ($src -split "`n").Count + " line(s)): " + $shown.Replace("`r", "<CR>").Replace("`n", "<LF>"))
    exit 9
  }
  $Mode = $m.Groups[1].Value
}

Say ("mode=" + $Mode + " brief=" + $BriefPath + " stdin=" + $stdin.Length + " bytes")

# WHAT THE CHILD CAN SEE OF ITS OWN DEADLINE. Added 2026-10-16, qwen TASK 0170.
# Recorded for every mode, before anything else happens, and recorded even when
# it is EMPTY - an empty marker is the evidence that the variable did not reach
# the child, which is a different fact from no marker at all. A test asserting
# on this file is asserting on the real inherited environment of a real child of
# the real watcher, not on the watcher's source text.
Mark "lane-deadline.env" ($env:LANE_DEADLINE + "")
Say ("LANE_DEADLINE as this child sees it: '" + $env:LANE_DEADLINE + "'")

$self = $PSCommandPath
if (-not $self) { $self = $MyInvocation.MyCommand.Definition }

function Spawn($childMode) {
  # NOT $args. That is an automatic variable, and shadowing it inside a
  # function is the kind of thing that works until the day it does not.
  $argv = @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $self,
    "-Mode", $childMode, "-BriefPath", $BriefPath,
    "-ParentLifeSeconds", [string]$ParentLifeSeconds,
    "-ChildLifeSeconds", [string]$ChildLifeSeconds
  )
  # An empty string in ArgumentList becomes an empty argv slot, which binds to
  # the next parameter as its value. Omit it instead of passing nothing.
  if ($MarkerDir -ne "") { $argv += @("-MarkerDir", $MarkerDir) }
  $p = Start-Process -FilePath "powershell.exe" -ArgumentList $argv `
                     -NoNewWindow -PassThru
  $null = $p.Handle
  return $p
}

switch ($Mode) {

  "exit0" {
    if ($LaneFile -ne "") {
      Add-Content -LiteralPath $LaneFile -Encoding UTF8 -Value (
        "fake task grew this lane file at " + (Get-Date -Format "HH:mm:ss"))
    }
    Mark "exit0.pid" $PID
    Say "grew the lane file; exiting 0"
    exit 0
  }

  "nowork" {
    # Deliberately does NOT touch the lane file. This is glm-b 0040 and 0050
    # reproduced: exit 0, nothing written, work not done.
    Mark "nowork.pid" $PID
    Say "wrote nothing to the lane file; exiting 0"
    exit 0
  }

  "hang" {
    Mark "hang.pid" $PID
    Say ("sleeping " + $HangSeconds + "s with no children; the watcher must time me out")
    Start-Sleep -Seconds $HangSeconds
    Say "NOT REACHED if the timeout worked"
    exit 0
  }

  "orphan" {
    Mark "orphan-root.pid" $PID
    $p = Spawn "orphan-parent"
    Mark "orphan-parent.pid.expected" $p.Id
    Say ("spawned orphan-parent pid " + $p.Id + "; sleeping " + $HangSeconds + "s")
    Start-Sleep -Seconds $HangSeconds
    Say "NOT REACHED if the timeout worked"
    exit 0
  }

  "orphan-parent" {
    Mark "orphan-parent.pid" $PID
    $p = Spawn "orphan-child"
    Mark "orphan-child.pid.expected" $p.Id
    Say ("spawned orphan-child pid " + $p.Id + "; living " + $ParentLifeSeconds +
         "s and then EXITING, which is what makes the child invisible to taskkill /T")
    Start-Sleep -Seconds $ParentLifeSeconds
    Mark "orphan-parent.exited" ((Get-Date -Format "HH:mm:ss.fff") + " pid " + $PID)
    exit 0
  }

  "orphan-child" {
    Mark "orphan-child.pid" $PID
    # HOLD THE BRIEF OPEN. FileShare::Read and not ::Delete, which is what a
    # reader that was never asked about renaming gets, and is why the rename
    # into DONE threw. The real task held this handle by inheriting stdin; a
    # Start-Process child cannot inherit it, so it is opened by name. The
    # handle is the link under test, not the way it was acquired.
    $fs = $null
    try {
      $fs = [System.IO.File]::Open(
        $BriefPath,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read)
      Mark "orphan-child.holds-brief" ("pid " + $PID + " holds " + $BriefPath)
    } catch {
      Mark "orphan-child.hold-failed" $_.Exception.Message
    }
    Start-Sleep -Seconds $ChildLifeSeconds
    if ($fs) { $fs.Close() }
    exit 0
  }

  default {
    Say ("REFUSING: unknown mode '" + $Mode + "'")
    exit 9
  }
}
