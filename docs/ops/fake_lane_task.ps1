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
    refused  prints the provider's real 429 refusal and  -> REFUSED, and the
             exits 1, having run nothing                    brief goes BACK to
                                                            the queue
    taskfail prints a traceback and exits 1 - no 429, no -> exit1, brief
             usage-limit text, no lane growth               consumed, as before

  THE LAST TWO ARE A PAIR AND MUST STAY ONE. Added by qwen TASK 0175 after a
  provider quota refusal ate nine briefs on 2026-10-16. They are identical in
  exit code (1), in lane growth (none) and in timing; the ONLY thing that
  differs is the text. `taskfail` is therefore the control that can fail the
  refusal patch, and a run that does not show it having been able to fail is
  not evidence.

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
  [ValidateSet("", "exit0", "nowork", "refused", "taskfail", "hang", "orphan", "orphan-parent", "orphan-child")]
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
    $Mode -eq "refused" -or $Mode -eq "taskfail" -or
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

  # ------------------------------------------------- qwen TASK 0175, 2026-10-16
  # THE PROVIDER REFUSAL. Prints what the provider actually printed on
  # 2026-10-16 01:41-01:48 and exits NON-ZERO, which is the whole difficulty:
  # on the exit code alone it is indistinguishable from a task that ran and
  # failed, and the watcher used to call it exit1 and consume the brief.
  #
  # THE THREE LINES ARE THE REAL ONES, taken from
  # logs\task-glm-c-20261016-014156.out (713 bytes). The model-recognition
  # warning is included because it is what every real GLM lane .out opens with,
  # so a signature that accidentally depended on the output being EMPTY would
  # not pass here - and the original defect's own .out files were 713 bytes, not
  # zero.
  "refused" {
    Mark "refused.pid" $PID
    Write-Host ('"glm-5.3" is not a model this version of Claude Code recognizes, so auto-compact will keep this session within 200k tokens (the context window it assumes). If the model accepts more, append [1m] to the model name for 1M, or set CLAUDE_CODE_MAX_CONTEXT_TOKENS to its real window; to make it recognized, map it in the modelOverrides setting or update Claude Code; CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT=1 restores the previous wait-for-the-API behavior.')
    Write-Host ('[claude-code:unrecognized_model] {"model":"glm-5.3","query_source":"generate_session_title"}')
    # THE MIDDOT IS BUILT, NOT TYPED. The provider's line carries U+00B7 between
    # the status and the body; this file is ASCII only (PowerShell 5.1 reads a
    # BOM-less .ps1 in the system codepage), so the character is constructed.
    # Nothing in lane_refusal.ps1 looks at it - it is here for fidelity, and
    # because a classifier that silently depended on it would fail this leg.
    $mid = [string][char]0xB7
    Write-Host ("API Error: Request rejected (429) " + $mid +
                " [1308][Usage limit reached for 5 hour. Your limit will reset at 2026-10-16 08:07:16][20261016074500b101012cec9142b4]")
    # The lane file is deliberately NOT touched: nothing ran, so nothing was
    # recorded, which is gate 3 of the classifier.
    exit 1
  }

  # THE CONTROL, AND IT MUST BE ABLE TO FAIL THE PATCH. An ordinary task
  # failure: a traceback, no usage-limit text, no 429, no lane growth - and
  # EXIT 1, the same code as the refusal above. The exit code, the absence of
  # lane growth and the non-zero status are all identical to "refused"; the ONLY
  # difference is the text. So if the new path returns this brief to the queue,
  # the string gate is not doing its job and the patch is wrong: a watcher that
  # returns every failure to its queue loops forever on a broken brief, which is
  # the same bug facing the other way.
  "taskfail" {
    Mark "taskfail.pid" $PID
    Write-Host ('"glm-5.3" is not a model this version of Claude Code recognizes, so auto-compact will keep this session within 200k tokens (the context window it assumes).')
    Write-Host "Traceback (most recent call last):"
    Write-Host '  File "C:\Users\Zvonimir\Desktop\wt-glm-c-2026-10-14\scripts\measure.py", line 212, in <module>'
    Write-Host "    main()"
    Write-Host '  File "C:\Users\Zvonimir\Desktop\wt-glm-c-2026-10-14\scripts\measure.py", line 188, in main'
    Write-Host "    rows = store.load_queue()"
    Write-Host "KeyError: 'provider_truth'"
    exit 1
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
