<#
  DRAIN-LANE.ps1 - rotate one lane onto new watcher bytes without abandoning
  the task it is running.

  ASCII ONLY, same reason as lane_watcher.ps1.

  ===========================================================================
  READ THIS FIRST: THE DRAIN MARKER THIS SCRIPT WAS ASKED TO INVENT ALREADY
  EXISTS, AND IT IS `STOP-<lane>`.
  ===========================================================================

  qwen TASK 0180 asked for "a drain marker the watcher honours AFTER its
  current task completes", on the premise that

      "the only ways to rotate a lane were: close its window by hand, or write
       STOP-<lane> and wait. Both are fine for an idle lane. NEITHER IS SAFE
       for a lane mid-task - the task is a `claude -p` child that survives its
       wrapper, so stopping the watcher abandons a running process with no one
       left to write its DONE line."

  THE SECOND HALF OF THAT IS TRUE OF CLOSING THE WINDOW AND FALSE OF THE STOP
  FILE. Both STOP checks in lane_watcher.ps1 sit at the TOP of the while loop;
  the task is launched, waited on, given its DONE line and moved to DONE
  strictly between them and the next iteration. Writing the file does not touch
  the running process at all.

  MEASURED, NOT READ - docs\ops\test_lane_drain_premise.ps1, 19/19 green,
  2026-10-16 10:38, scratch lane "draintest", `slowexit0` working 25s:

      task started            10:38:33.809
      STOP-draintest written  10:38:33.869   <- 60 ms later, strictly mid-task
      task FINISHED           10:38:58.823   <- 25s after the STOP file
      lane file               31 -> 89 bytes  (its work landed)
      DONE  0010-slow.md -> exit0             (its verdict was recorded)
      MOVED 0010-slow.md -> 20261016-103833-exit0-0010-slow.md
      STOP-draintest present. Exiting.        <- only now
      watcher down.
      watcher-draintest.pid removed

      log byte offsets: START 1587 < DONE 2146 < MOVED 2209 < STOP 2301 < DOWN 2369

  So this script does NOT add a marker. Adding one would have been a second
  representation of a truth the watcher already holds, and the two would drift.
  What was actually missing is everything AROUND the marker:

    1  no way to tell whether a lane is idle or working that is trustworthy,
    2  no bounded wait that reports progress instead of hanging,
    3  no confirmation that the NEW bytes actually came up. On 2026-10-15
       START-ALL-LANES printed "start" for seven lanes while all seven refused
       on their pid locks, and at 00:31 five of seven were still running the
       old 90-minute bytes thirty-eight minutes after the fix was deployed.

  This script is those three things. It is an orchestrator around a primitive
  that was already proven safe, which is why it is small.

  ===========================================================================
  DRY RUN IS THE DEFAULT. -Execute is always explicit.
  ===========================================================================
  Repository rule: "Dry run is the default for anything that sends. --live is
  always explicit." Stopping and restarting a lane is the local equivalent, so
  the default prints the plan and changes nothing.

  WHAT IT NEVER DOES: it never kills a watcher, never kills a task, never
  touches another lane, never creates STOP-ALL, and never removes a STOP file
  it did not itself create - a STOP file that was already there is the
  operator's and means that lane is being brought down on purpose.
#>
param(
  [Parameter(Mandatory = $true)][string]$Lane,

  # Empty = resolve from START-ALL-LANES.ps1, which is the single existing
  # authority for lane -> worktree. See Resolve-LaneWorktree.
  [string]$Worktree = "",

  [ValidateSet("acceptEdits", "bypassPermissions", "default", "plan")]
  [string]$PermissionMode = "bypassPermissions",

  # Nothing happens without this. See the header.
  [switch]$Execute,

  # How long to wait for a WORKING lane to finish its current task. The
  # watcher's own timeout is 150 minutes, so a drain can legitimately take that
  # long plus the task's own teardown. Default 160 minutes covers it; the wait
  # reports progress every 60s so it is never indistinguishable from a hang.
  [int]$DrainTimeoutMinutes = 160,
  [int]$ProgressSeconds = 60,

  # How long to wait for the pid lock to disappear after the watcher logs
  # "watcher down." They are not simultaneous: the lock is removed, then the
  # line is written.
  [int]$LockReleaseSeconds = 60,

  # How long to wait for the REPLACEMENT watcher to prove itself in the log.
  [int]$StartConfirmSeconds = 60,

  # Injection point, same convention as lane_watcher.ps1 (qwen TASK 0110), so a
  # fixture can point the whole script at a scratch estate. The live default
  # means a real run needs no arguments beyond -Lane.
  [string]$Ops = "C:\Users\Zvonimir\Desktop\resonate-ops",

  # Empty = "$Ops\tools\lane_watcher.ps1", which is what a real rotation uses.
  [string]$WatcherPath = "",

  # Passed through to the replacement watcher, for a fixture only.
  [string]$ExtraWatcherArgs = ""
)

$ErrorActionPreference = "Stop"

$Queue    = Join-Path $Ops ("queue\" + $Lane)
$Running  = Join-Path $Queue "RUNNING"
$LogDir   = Join-Path $Ops "logs"
$WatchLog = Join-Path $LogDir ("watcher-" + $Lane + ".log")
$LockFile = Join-Path $LogDir ("watcher-" + $Lane + ".pid")
$StopAll  = Join-Path $Ops "STOP-ALL"
$StopMe   = Join-Path $Ops ("STOP-" + $Lane)
if ($WatcherPath -eq "") { $WatcherPath = Join-Path $Ops "tools\lane_watcher.ps1" }

function Say($m) { Write-Host ("[drain " + $Lane + "] " + $m) }

# EVERY ABORT NAMES ITS REASON AND EXITS NON-ZERO. "Fail-closed everywhere" is
# the brief's requirement; an abort that looks like a no-op is not fail-closed,
# it is invisible.
function Abort($why) {
  Say ("ABORTING, NOTHING CHANGED: " + $why)
  exit 4
}

# ---------------------------------------------------------------------------
# READING THE LOG IS A MEASUREMENT AND CAN FAIL. An unreadable log must abort,
# never be treated as an empty one. This estate has already turned a swallowed
# read error into a false "the lock is free".
# ---------------------------------------------------------------------------
function Read-WatchLog {
  if (-not (Test-Path -LiteralPath $WatchLog)) { return $null }
  for ($i = 1; $i -le 15; $i++) {
    try { return [System.IO.File]::ReadAllText($WatchLog) } catch { Start-Sleep -Milliseconds 150 }
  }
  return $null
}

# ---------------------------------------------------------------------------
# lane -> worktree comes from START-ALL-LANES.ps1 BY PARSING, NOT BY COPYING.
#
# A second copy of that table here would be a parallel representation of the
# same truth, and the two would drift the first time a worktree moved - which
# has already happened once in this estate (webapp moved under
# Desktop\resonate-trees). The table is read out of the SCRIPT'S AST, so
# nothing is executed: dot-sourcing START-ALL-LANES would launch seven
# watchers, which is the opposite of what a rotation tool should do.
# ---------------------------------------------------------------------------
function Resolve-LaneWorktree($laneName) {
  $starter = Join-Path $Ops "tools\START-ALL-LANES.ps1"
  if (-not (Test-Path -LiteralPath $starter)) { return $null }
  $errs = $null
  $ast = [System.Management.Automation.Language.Parser]::ParseFile($starter, [ref]$null, [ref]$errs)
  if ($errs -and $errs.Count -gt 0) { return $null }
  if ($null -eq $ast) { return $null }
  $tables = $ast.FindAll({ $args[0] -is [System.Management.Automation.Language.HashtableAst] }, $true)
  foreach ($h in $tables) {
    $l = $null; $w = $null
    foreach ($kv in $h.KeyValuePairs) {
      $k = $kv.Item1.Extent.Text.Trim('"', "'", ' ')
      $v = $kv.Item2.Extent.Text.Trim('"', "'", ' ')
      if ($k -ieq "Lane")     { $l = $v }
      if ($k -ieq "Worktree") { $w = $v }
    }
    if ($l -and $w -and ($l -ieq $laneName)) { return $w }
  }
  return $null
}

# ---------------------------------------------------------------------------
# IS THIS LANE IDLE OR WORKING?
#
# THREE SIGNALS ARE REJECTED, EACH FOR A MEASURED REASON. The brief required
# this list and the reasons, because all three have already been believed and
# been wrong in this estate:
#
#   REJECTED: the .out file's SIZE. Measured 2026-10-16: the six tasks killed
#     at 09:16:45 left 559-byte .out files holding only the model warning, one
#     left 0 bytes, and the eight quota refusals left 713 bytes each. All of
#     those sizes belong to tasks that did NO work. Conversely a task can write
#     nothing for an hour while working hard. Size is not liveness and it is
#     not progress.
#
#   REJECTED: the RUNNING directory being empty or not. It is wrong in BOTH
#     directions. The brief is moved into RUNNING BEFORE "START" is logged, so
#     non-empty does not mean a task is running. And two paths deliberately
#     leave a brief in RUNNING while nothing at all is running: the
#     "MOVE STILL BLOCKED after 30s" path, and TASK 0175's
#     "RETURN STILL BLOCKED" / "RETURN REFUSED" paths. Both log that the lane
#     will idle on it. So empty does not mean idle either.
#
#   REJECTED: a filename in DONE. CONTINUITY SS3 already says a DONE filename
#     proves nothing, and 2026-10-16 made it prove something FALSE: fifteen
#     DONE entries today (nine from the quota refusals, six from the 09:16:45
#     mass kill) read exactly like completed work for tasks that never ran. A
#     DONE name records that a verdict was written. It says nothing about what
#     is running now.
#
# THE AUTHORITY IS TWO THINGS THAT MUST AGREE:
#   (a) the pid lock file, and whether that pid is a LIVE powershell process -
#       the same test lane_watcher.ps1 uses on itself to refuse a second copy,
#       so this script and the watcher cannot disagree about who holds a lane;
#   (b) the log's own CONTROL LINES, read forward from the last "watcher up.",
#       which is the only record of what the watcher believes it is doing.
#
# If they disagree, or either is unreadable, the answer is UNKNOWN and UNKNOWN
# ABORTS. It never becomes "idle" and never becomes "safe".
# ---------------------------------------------------------------------------
function Get-LaneState {
  $state = [pscustomobject]@{
    Verdict   = "UNKNOWN"   # DOWN | IDLE | WORKING | STALE_LOCK | UNKNOWN
    LockPid   = $null
    Alive     = $false
    LastLine  = ""
    Brief     = ""
    Why       = ""
  }

  # ---- (a) the lock
  $lockText = $null
  if (Test-Path -LiteralPath $LockFile) {
    for ($i = 1; $i -le 15 -and $null -eq $lockText; $i++) {
      try { $lockText = (Get-Content -LiteralPath $LockFile -Raw).Trim() } catch { Start-Sleep -Milliseconds 150 }
    }
    if ($null -eq $lockText) {
      $state.Why = "the pid lock " + $LockFile + " exists but could not be read in 15 attempts. UNKNOWN is not idle."
      return $state
    }
    if ($lockText -notmatch '^\d+$') {
      $state.Why = "the pid lock holds '" + $lockText + "', which is not a pid. UNKNOWN is not idle."
      return $state
    }
    $state.LockPid = [int]$lockText
    $proc = Get-Process -Id $state.LockPid -ErrorAction SilentlyContinue
    if ($proc) {
      # PID REUSE IS CHECKED, not assumed away. A recycled pid belonging to
      # something that is not a shell must not be read as a live watcher.
      if ($proc.ProcessName -like "*powershell*" -or $proc.ProcessName -like "*pwsh*") {
        $state.Alive = $true
      } else {
        $state.Why = ("the pid lock names " + $state.LockPid + " but that process is '" +
                      $proc.ProcessName + "', not a shell. Possible pid reuse. UNKNOWN is not idle.")
        return $state
      }
    }
  }

  # ---- (b) the log
  $t = Read-WatchLog
  if ($null -eq $t) {
    if (-not (Test-Path -LiteralPath $WatchLog)) {
      if (-not $state.Alive -and $null -eq $state.LockPid) {
        $state.Verdict = "DOWN"
        $state.Why = "no pid lock and no log at all: this lane has never run here."
        return $state
      }
      $state.Why = "a lock exists but there is no log at " + $WatchLog + ". UNKNOWN is not idle."
      return $state
    }
    $state.Why = "the log " + $WatchLog + " exists but could not be read in 15 attempts. UNKNOWN is not idle."
    return $state
  }

  # Only the CURRENT watcher's section matters. Lines from a previous run of
  # this lane describe a process that no longer exists.
  $cut = $t.LastIndexOf("watcher up.")
  $section = if ($cut -ge 0) { $t.Substring($cut) } else { $t }

  # The control vocabulary, in the order the watcher emits it. "START" is the
  # only one that opens a task; everything else closes one or is between tasks.
  $control = @()
  foreach ($line in ($section -split "`r?`n")) {
    if ($line -match '\]\s+(START|DONE  |REFUSED  |RETURNED |RETURN |MOVED |MOVE |NOWORK|TIMEOUT|idle: queue empty|a task is already in RUNNING|COOL-DOWN|watcher down\.|watcher up\.)') {
      $control += $line
    }
  }
  if ($control.Count -gt 0) { $state.LastLine = $control[$control.Count - 1] }

  # Is there a START with no closing verdict after it?
  $openBrief = ""
  foreach ($line in $control) {
    $m = [regex]::Match($line, '\]\s+START (.+?)\s*$')
    if ($m.Success) { $openBrief = $m.Groups[1].Value; continue }
    if ($line -match '\]\s+(DONE  |REFUSED  |watcher down\.)') { $openBrief = "" }
  }
  $state.Brief = $openBrief

  $logSaysDown = ($control.Count -gt 0 -and $control[$control.Count - 1] -match 'watcher down\.')

  # ---- (a) and (b) must agree
  if (-not $state.Alive) {
    if ($null -ne $state.LockPid -and -not $logSaysDown) {
      $state.Verdict = "STALE_LOCK"
      $state.Why = ("the lock names pid " + $state.LockPid + " but that process is gone, and the log's " +
                    "last control line is not 'watcher down.' - so a watcher died without saying so. " +
                    "lane_watcher.ps1 takes a stale lock over loudly, so starting is safe, but this is named.")
      return $state
    }
    $state.Verdict = "DOWN"
    $state.Why = "no live watcher process for this lane."
    return $state
  }

  if ($logSaysDown) {
    $state.Why = ("pid " + $state.LockPid + " is a live shell but the log's last control line says " +
                  "'watcher down.'. The two authorities DISAGREE. UNKNOWN is not idle.")
    return $state
  }

  if ($openBrief -ne "") {
    $state.Verdict = "WORKING"
    $state.Why = ("pid " + $state.LockPid + " is live and the log shows START " + $openBrief +
                  " with no closing verdict after it.")
  } else {
    $state.Verdict = "IDLE"
    $state.Why = ("pid " + $state.LockPid + " is live and no task is open in the log.")
  }
  return $state
}

# ===========================================================================
Say ("ops=" + $Ops)
Say ("watcher to start from: " + $WatcherPath)
if (-not $Execute) { Say "DRY RUN (default). Nothing will be changed. Add -Execute to act." }

if (-not (Test-Path -LiteralPath $WatcherPath)) { Abort ("no watcher script at " + $WatcherPath) }
if (-not (Test-Path -LiteralPath $Queue)) { Abort ("no queue directory for this lane at " + $Queue) }

# ---------------------------------------------------------------------------
# PRE-FLIGHT: CAN THE REPLACEMENT WATCHER EVEN START?
#
# The confirmation step at the bottom of this script DOES catch a replacement
# that refuses - but only AFTER the lane has been drained, which leaves the
# lane DOWN and the operator reading a log. That is the wrong end to find it.
#
# MEASURED 2026-10-16 14:21, and it was not hypothetical. TASK 0200 made
# tools\lane_orphan.ps1 a HARD dependency: the watcher logs "REFUSING: the
# orphan resolver is missing" and exits 2. The live tools\ holds only
# lane_treekill.ps1 - lane_orphan.ps1, lane_refusal.ps1 and lane_taskentry.ps1
# are all absent. So a rotation onto the current bytes would have drained a
# working lane and then been unable to restart it, once per lane, seven times.
#
# THE REQUIRED SET IS READ OUT OF THE WATCHER'S OWN SOURCE, never kept here. A
# list in this file would be a second representation of the watcher's
# dependencies, and TASK 0180's own deploy paragraph showed how fast that
# drifts: it named three files at 2026-10-16 10:55 and was already short one.
#
# EVERY referenced module is required, with no hard/soft split. Some make the
# watcher exit 2 and some make it degrade silently with "NO ALREADY-RECORDED
# CHECK"; distinguishing them would need exactly the fragile source analysis
# this check exists to avoid, and a silently degraded watcher is not a
# successful rotation. UNKNOWN is never a pass.
# ---------------------------------------------------------------------------
$injects = ($ExtraWatcherArgs -match '-(TreeKillPath|RefusalModulePath|OrphanModulePath|TaskEntryModulePath)\b')
if ($injects) {
  Say ("NOTE: -ExtraWatcherArgs injects a module path directly, so the tools\ pre-flight is skipped: " +
       $ExtraWatcherArgs)
} else {
  # The watcher resolves its modules from ITS OWN -Ops, which a fixture may
  # redirect. A real rotation passes no ExtraWatcherArgs, so this is $Ops.
  $wOps = $Ops
  $om = [regex]::Match($ExtraWatcherArgs, '-Ops\s+"?([^"\s]+)"?')
  if ($om.Success) { $wOps = $om.Groups[1].Value }
  $wTools = Join-Path $wOps "tools"

  $src = $null
  try { $src = [System.IO.File]::ReadAllText($WatcherPath) } catch { }
  if ($null -eq $src) {
    Abort ("could not read " + $WatcherPath + " to work out what it depends on. An unreadable " +
           "watcher is UNKNOWN, and UNKNOWN is not a rotation.")
  }
  $need = New-Object System.Collections.ArrayList
  foreach ($m in [regex]::Matches($src, 'Join-Path\s+\$Ops\s+"tools\\(lane_[A-Za-z0-9_]+\.ps1)"')) {
    $n = $m.Groups[1].Value
    if (-not $need.Contains($n)) { $null = $need.Add($n) }
  }
  if ($need.Count -eq 0) {
    Say ("pre-flight: " + (Split-Path -Leaf $WatcherPath) + " references no tools\lane_*.ps1 module")
  } else {
    $missing = @($need | Where-Object { -not (Test-Path -LiteralPath (Join-Path $wTools $_)) })
    if ($missing.Count -gt 0) {
      Abort ("the replacement watcher needs " + $need.Count + " module(s) from " + $wTools +
             " and " + $missing.Count + " of them are MISSING: " + ($missing -join ", ") +
             ". Deploy them beside lane_watcher.ps1 first. Draining the lane now would stop a " +
             "working watcher and then fail to start its replacement, leaving this lane DOWN. " +
             "Nothing has been changed.")
    }
    Say ("pre-flight: all " + $need.Count + " module(s) the watcher needs are present in " +
         $wTools + " (" + ($need -join ", ") + ")")
  }
}
if (Test-Path -LiteralPath $StopAll) {
  Abort ("STOP-ALL exists at " + $StopAll + ". A replacement watcher would exit immediately. " +
         "Remove it deliberately before rotating anything.")
}

# A STOP FILE THAT IS ALREADY THERE IS THE OPERATOR'S, AND IT IS NOT OURS TO
# REMOVE. START-ALL-LANES.ps1 learned this on 2026-10-15 02:31: clearing STOP
# files revived watchers that were mid-task and about to exit, leaving two per
# lane. This script therefore refuses rather than tidying up after somebody.
if (Test-Path -LiteralPath $StopMe) {
  Abort ("STOP-" + $Lane + " already exists at " + $StopMe + ". Somebody is bringing this lane down " +
         "on purpose. This script will not remove a STOP file it did not create. " +
         "Resolve that first, then rotate.")
}

if ($Worktree -eq "") {
  $Worktree = Resolve-LaneWorktree $Lane
  if ($null -eq $Worktree -or $Worktree -eq "") {
    Abort ("could not resolve a worktree for lane '" + $Lane + "' from tools\START-ALL-LANES.ps1, " +
           "and -Worktree was not given. Not guessing a path.")
  }
  Say ("worktree resolved from START-ALL-LANES.ps1: " + $Worktree)
} else {
  Say ("worktree given explicitly: " + $Worktree)
}
if (-not (Test-Path -LiteralPath $Worktree)) { Abort ("the worktree path does not exist: " + $Worktree) }

# ---------------------------------------------------------------- the state
$st = Get-LaneState
Say ("STATE: " + $st.Verdict)
Say ("  because: " + $st.Why)
if ($st.LastLine -ne "") { Say ("  last control line: " + $st.LastLine.Trim()) }

if ($st.Verdict -eq "UNKNOWN") {
  Abort ("the lane's state is UNKNOWN. " + $st.Why +
         " An ambiguous liveness answer never becomes a rotation.")
}

switch ($st.Verdict) {
  "DOWN"       { Say "PLAN: no watcher is running. Start one; nothing to drain." }
  "STALE_LOCK" { Say "PLAN: no live watcher, but a stale lock is present. Start one; the watcher takes the lock over loudly." }
  "IDLE"       { Say ("PLAN: write STOP-" + $Lane + ", wait for the lock to release, remove the STOP file, start the new bytes, confirm by log content.") }
  "WORKING"    {
    Say ("PLAN: DO NOT STOP ANYTHING. Write STOP-" + $Lane + " - which lane_watcher.ps1 only " +
         "reads at the top of its loop, so '" + $st.Brief + "' runs to completion, gets its DONE " +
         "line and is moved - then wait up to " + $DrainTimeoutMinutes +
         " min for the drain, remove the STOP file, start the new bytes, confirm by log content.")
    Say ("  (proven: docs\ops\test_lane_drain_premise.ps1, 19/19, 2026-10-16 10:38)")
  }
}

if (-not $Execute) {
  Say "DRY RUN COMPLETE. Nothing was changed. Re-run with -Execute to rotate."
  exit 0
}

# ======================================================================
# FROM HERE ON IT ACTS.
# ======================================================================
$needsDrain = ($st.Verdict -eq "IDLE" -or $st.Verdict -eq "WORKING")

if ($needsDrain) {
  $before = Read-WatchLog
  if ($null -eq $before) { Abort "the log became unreadable just before the STOP file was to be written." }

  Say ("writing " + $StopMe)
  Set-Content -LiteralPath $StopMe -Value ("DRAIN-LANE.ps1 " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -Encoding ASCII
  if (-not (Test-Path -LiteralPath $StopMe)) { Abort "the STOP file was written but is not on disk. Read back failed." }

  # THE STOP FILE IS REMOVED IN A finally, so an abort or a Ctrl-C below cannot
  # leave this lane stopped. A rotation that fails half way must leave the lane
  # restartable, not silently down.
  $drained = $false
  try {
    $deadline = (Get-Date).AddMinutes($DrainTimeoutMinutes)
    $lastSay  = Get-Date
    Say ("waiting for the watcher to finish its current work and release the lock (up to " +
         $DrainTimeoutMinutes + " min)")
    while ((Get-Date) -lt $deadline) {
      $alive = $false
      if ($null -ne $st.LockPid) { $alive = [bool](Get-Process -Id $st.LockPid -ErrorAction SilentlyContinue) }
      $lockThere = Test-Path -LiteralPath $LockFile
      if (-not $alive -and -not $lockThere) { $drained = $true; break }
      if (((Get-Date) - $lastSay).TotalSeconds -ge $ProgressSeconds) {
        # PROGRESS IS REPORTED, so a long drain is never indistinguishable from
        # a hang. A 150-minute task makes this legitimately slow.
        $now = Get-LaneState
        Say ("  still draining: state=" + $now.Verdict + " brief='" + $now.Brief +
             "' lock=" + $lockThere + " alive=" + $alive)
        $lastSay = Get-Date
      }
      Start-Sleep -Milliseconds 1000
    }

    if (-not $drained) {
      # The lock may linger a moment after the process exits; allow for that
      # explicitly rather than calling a race a failure.
      $end = (Get-Date).AddSeconds($LockReleaseSeconds)
      while ((Get-Date) -lt $end -and -not $drained) {
        if (-not (Test-Path -LiteralPath $LockFile)) { $drained = $true; break }
        Start-Sleep -Milliseconds 300
      }
    }
    if (-not $drained) {
      Abort ("the lane did not drain within " + $DrainTimeoutMinutes + " min + " + $LockReleaseSeconds +
             "s. The pid lock " + $LockFile + " is still present. NOTHING WAS RESTARTED and the STOP " +
             "file is being removed, so the existing watcher keeps working. Investigate before retrying.")
    }
    Say "drained: the watcher has exited and the pid lock is gone."
  }
  finally {
    if (Test-Path -LiteralPath $StopMe) {
      Say ("removing " + $StopMe + " (this script created it)")
      Remove-Item -LiteralPath $StopMe -Force -ErrorAction SilentlyContinue
    }
  }
  if (Test-Path -LiteralPath $StopMe) {
    Abort ("could not remove " + $StopMe + ". A replacement watcher would exit immediately, so nothing was started.")
  }
}

# ------------------------------------------------------------- the restart
# THE CONFIRMATION IS THE LOG'S CONTENT, NOT THE LAUNCHER'S OUTPUT. On
# 2026-10-15 START-ALL-LANES printed "start" for seven lanes and all seven
# refused on their pid locks, exit 3, with nothing on the console to say so.
# The only authority for "this lane came up" is a NEW "watcher up." line in the
# lane's own log, after the byte offset where we stopped looking.
$mark = 0
$pre = Read-WatchLog
if ($null -ne $pre) { $mark = $pre.Length }

Say ("starting " + $WatcherPath + " for lane " + $Lane + " in " + $Worktree)
$argv = @("-ExecutionPolicy", "Bypass", "-File", $WatcherPath,
          "-Lane", $Lane, "-Worktree", $Worktree, "-PermissionMode", $PermissionMode)
if ($ExtraWatcherArgs -ne "") { $argv += ($ExtraWatcherArgs -split '\s+') }
$newProc = Start-Process powershell -ArgumentList $argv -PassThru
$null = $newProc.Handle
Say ("launched pid " + $newProc.Id + " - that is the SHELL, not yet a confirmation")

$confirmed = $false
$banner    = ""
$end = (Get-Date).AddSeconds($StartConfirmSeconds)
while ((Get-Date) -lt $end) {
  $t = Read-WatchLog
  if ($null -ne $t -and $t.Length -gt $mark) {
    $tail = $t.Substring($mark)
    $m = [regex]::Match($tail, '\]\s+(watcher up\..*)')
    if ($m.Success) { $confirmed = $true; $banner = $m.Groups[1].Value.Trim(); break }
    if ($tail -match 'REFUSING: ') {
      $r = [regex]::Match($tail, 'REFUSING: .*')
      Abort ("the replacement watcher REFUSED to start: " + $r.Value.Trim())
    }
  }
  if (-not (Get-Process -Id $newProc.Id -ErrorAction SilentlyContinue)) {
    Start-Sleep -Milliseconds 500
    $t = Read-WatchLog
    if ($null -ne $t -and $t.Length -gt $mark -and $t.Substring($mark) -match '\]\s+(watcher up\..*)') {
      $confirmed = $true
      $banner = [regex]::Match($t.Substring($mark), '\]\s+(watcher up\..*)').Groups[1].Value.Trim()
      break
    }
    Abort ("the shell for the replacement watcher (pid " + $newProc.Id +
           ") exited without writing 'watcher up.' to " + $WatchLog +
           ". THIS LANE IS NOW DOWN. Read that log before retrying.")
  }
  Start-Sleep -Milliseconds 400
}

if (-not $confirmed) {
  Abort ("no new 'watcher up.' line appeared in " + $WatchLog + " within " + $StartConfirmSeconds +
         "s. The launcher's own output is NOT evidence - it printed 'start' for seven refusing lanes " +
         "on 2026-10-15. THIS LANE MAY BE DOWN: read that log.")
}

Say ("CONFIRMED BY LOG CONTENT: " + $banner)
# The banner carries the timeout, which is the whole point of a rotation: it is
# how the operator sees that the NEW bytes are the ones running.
$tm = [regex]::Match($banner, 'timeout=(\S+)')
if ($tm.Success) { Say ("  the running bytes report timeout=" + $tm.Groups[1].Value) }
else { Say "  NOTE: the banner carries no timeout= field. Confirmed up, but the bytes are not identified." }

# WHICH MODULES THE NEW WATCHER LOADED - AND THIS IS A WAIT, NOT ONE READ.
# lane_watcher.ps1 logs "watcher up." FIRST and its task=/treekill=/refusalmod=
# lines immediately after, so the confirm loop above breaks before they are
# written. A single read therefore loses a same-second race: measured
# 2026-10-16 14:30, the lines were in the log and this block printed nothing.
# Same defect class as the lost DONE line this run also found - one read of a
# file another process is still appending to - so it is fixed the same way.
$keys    = @("task=", "treekill=", "refusalmod=")
$found   = @{}
$keyEnd  = (Get-Date).AddSeconds(10)
while ((Get-Date) -lt $keyEnd -and $found.Count -lt $keys.Count) {
  $rm = Read-WatchLog
  if ($null -ne $rm -and $rm.Length -gt $mark) {
    $slice = $rm.Substring($mark)
    foreach ($k in $keys) {
      if ($found.ContainsKey($k)) { continue }
      $km = [regex]::Match($slice, [regex]::Escape($k) + '\S+')
      if ($km.Success) { $found[$k] = $km.Value }
    }
  }
  if ($found.Count -lt $keys.Count) { Start-Sleep -Milliseconds 200 }
}
foreach ($k in $keys) {
  if ($found.ContainsKey($k)) { Say ("  " + $found[$k]) }
  else { Say ("  NOTE: the new watcher never logged " + $k + " - it is up, but that module is unnamed in the record") }
}
Say "ROTATED."
exit 0
