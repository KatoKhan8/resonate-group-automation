<#
  lane_watcher.ps1 - one watcher per lane. The operator starts it ONCE.

  It takes the first file in queue\<lane>\ (filename order), runs it as a
  `claude -p` prompt inside that lane's worktree, appends everything to
  logs\watcher-<lane>.log, then moves the task to DONE and takes the next one.
  One task at a time. No pasting into tabs.

  ASCII ONLY, DELIBERATELY. Windows PowerShell 5.1 reads a .ps1 without a BOM
  in the system ANSI codepage; a UTF-8 em dash arrives as a curly quote that
  PowerShell accepts as a string delimiter and the parse breaks.

  EXIT CODE: Start-Process -PassThru returns a Process whose ExitCode reads
  back as $null unless the handle was cached while the process was alive. v1
  did not do that, so every task was recorded as "exit" with no number AND
  counted as a failure, stopping each lane after three SUCCESSFUL tasks.
  Reading $proc.Handle once fixes it. Do not remove that line.

  CREDENTIALS: v1-v4 set GIT_CONFIG_COUNT=1, GIT_CONFIG_KEY_0=credential.helper
  and GIT_CONFIG_VALUE_0="" to clear the helper list. In PowerShell, assigning
  "" to an environment variable DELETES it, so KEY_0 existed with no VALUE_0
  and EVERY git command in every lane died with
      fatal: missing config value GIT_CONFIG_VALUE_0   (exit 128)
  which reads like a catastrophic repository fault. Measured by the qwen lane
  2026-10-15 02:10. The replacement points GIT_CONFIG_SYSTEM at an empty file,
  which drops the SYSTEM-level config wholesale - including
  credential.helper=manager, the Git Credential Manager entry that let a lane
  push to master on 2026-10-15 from a clone with no remotes.

  WHAT THIS IS AND IS NOT - corrected 2026-10-15 03:20 after the qwen lane
  measured it. It removes the system-level helper entry for child processes,
  which stops the DEFAULT `git push` path. It is NOT a boundary: the GCM and
  wincred binaries stay on PATH and the per-user credential store is reachable
  directly, so a lane that wanted to could still authenticate. There is no
  global credential.helper to remove - an earlier version of this comment
  implied otherwise and that was wrong. Treat this as a speed bump.

  THE BOUNDARY IS THE SERVER-SIDE RULESET on master, measured refusing a push
  with GH013 at 02:05. A real boundary inside a lane would need the lanes to
  run as an OS user whose credential store holds nothing, or no reusable PAT in
  Windows Credential Manager at all. Both are the operator's calls.

  A control documented as stronger than it is, is worse than a known speed
  bump. That is why this paragraph says what it says.

  THE TIMEOUT STOPS THE TASK, SINCE 2026-10-15 (qwen TASK 0070 measured it,
  TASK 0090 fixed it). It used to stop only the `cmd.exe` wrapper, so the
  `claude` child kept working - 23 seconds in one case and 27 MINUTES in
  another - still holding the brief open as its inherited stdin, which made the
  Move-Item into DONE throw, which under $ErrorActionPreference = "Stop" ended
  the script. Two lanes stopped consuming work that afternoon and neither said
  so in its own log. See tools\lane_treekill.ps1 for the kill, and note what it
  does NOT claim: `taskkill /T` alone is not enough, because it walks LIVE
  parent links and an orphaned grandchild is invisible to it. The tree is
  therefore sampled DURING the run and the accumulated set is swept and
  re-measured afterwards.
#>
param(
  [Parameter(Mandatory = $true)][string]$Lane,
  [Parameter(Mandatory = $true)][string]$Worktree,
  [ValidateSet("acceptEdits", "bypassPermissions", "default", "plan")]
  [string]$PermissionMode = "acceptEdits",
  [int]$IdleSleepSeconds = 20,
  [int]$MaxConsecutiveFailures = 3,
  # 90 UNTIL 2026-10-15. Raised to 150 only AFTER the kill above was fixed, and
  # in that order deliberately: at 90 on the old code the timeout killed the
  # cmd.exe wrapper and left the task running, so raising it first would only
  # have postponed the same silent death.
  #
  # MEASURED, 72 paired START/DONE records across all seven lane logs:
  #
  #     longest task that ever COMPLETED      64.3 min  (glm 0060)
  #     median                                16.9 min
  #     over 77 min                           0 of 72
  #     over 90 min                           0 of 72
  #
  # So the cap binds on exactly two tasks in the estate's history, glm 0065 and
  # pilotcaps 0130, and neither was hung: both were two-leg suite runs whose
  # SUITE TIME ALONE was 2267.7s + 2355.3s = 77 minutes, before any reading,
  # diffing or writing. They were killed at exactly 90:00 and both went on to
  # finish their work and write their lane entries. 150 leaves 73 minutes
  # around a 77-minute suite pair.
  #
  # What the raise costs: a genuinely hung task now wastes 150 minutes of a
  # lane instead of 90. Observed frequency of a genuine hang in those 72
  # records: zero. Both 90-minute hits were productive work, not hangs. That is
  # the trade, and it is a measurement rather than a preference.
  [int]$TaskTimeoutMinutes = 150,
  # How often the running task's process tree is sampled. The samples are what
  # catch a grandchild whose parent exits before the timeout: taskkill /T walks
  # LIVE parent links and cannot see an orphan, so the only moment that orphan
  # is attributable to this task is while its parent still exists.
  [int]$TreeSampleSeconds = 60,
  [switch]$KeepSystemGitConfig
)

$ErrorActionPreference = "Stop"

$Ops      = "C:\Users\Zvonimir\Desktop\resonate-ops"
$MainCo   = "C:\Users\Zvonimir\Desktop\resonate-group-automation"
$Queue    = Join-Path $Ops ("queue\" + $Lane)
$Running  = Join-Path $Queue "RUNNING"
$Done     = Join-Path $Queue "DONE"
$LogDir   = Join-Path $Ops "logs"
$WatchLog = Join-Path $LogDir ("watcher-" + $Lane + ".log")
$StopAll  = Join-Path $Ops "STOP-ALL"
$StopMe   = Join-Path $Ops ("STOP-" + $Lane)
$EmptyCfg = Join-Path $Ops "tools\empty-system.gitconfig"
$LockFile = Join-Path $LogDir ("watcher-" + $Lane + ".pid")
$LaneFile = Join-Path $Ops ("LANE-" + $Lane + ".md")

# The tree kill lives in its own file so that a test can call it: this script
# takes mandatory parameters and then loops forever, so a test cannot
# dot-source it. Proof: docs\ops\test_lane_watcher_treekill.ps1 (eight legs)
# and docs\ops\mutate_lane_treekill.py (five mutations) in the repository.
$TreeKill = Join-Path $Ops "tools\lane_treekill.ps1"

function Log($msg) {
  $line = "[{0}] [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Lane, $msg
  Write-Host $line
  try { Add-Content -LiteralPath $WatchLog -Value $line -Encoding UTF8 } catch { }
}

foreach ($d in @($Queue, $Running, $Done, $LogDir)) {
  if (-not (Test-Path -LiteralPath $d)) {
    New-Item -ItemType Directory -Path $d -Force | Out-Null
  }
}

if (-not (Test-Path -LiteralPath $Worktree)) {
  Log ("REFUSING: path does not exist: " + $Worktree); exit 2
}
$wt = (Resolve-Path -LiteralPath $Worktree).Path.TrimEnd('\')
if ($wt -ieq $MainCo.TrimEnd('\')) {
  Log "REFUSING: that is the main checkout. A lane never runs there."; exit 2
}
if (-not (Test-Path -LiteralPath (Join-Path $wt ".git"))) {
  Log ("REFUSING: no .git here: " + $wt); exit 2
}
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Log "REFUSING: 'claude' is not on PATH."; exit 2
}
# REFUSE rather than run without it. A watcher whose timeout cannot stop a task
# is the defect this file was changed to remove, and a missing dependency is not
# allowed to restore it quietly.
if (-not (Test-Path -LiteralPath $TreeKill)) {
  Log ("REFUSING: the tree-kill module is missing: " + $TreeKill +
       ". Without it a timeout would kill the cmd.exe wrapper only and orphan the task.")
  exit 2
}
. $TreeKill
if (-not (Get-Command Stop-LaneProcessTree -ErrorAction SilentlyContinue)) {
  Log ("REFUSING: " + $TreeKill + " did not define Stop-LaneProcessTree."); exit 2
}

# ------------------------------------------------- one watcher per lane
# Running START-ALL-LANES while watchers are already up produced two watchers
# on four lanes on 2026-10-15 02:23. Two watchers poll the same queue folder,
# and the RUNNING check is read-then-move, not atomic, so both can take the
# same task. This lock makes the second copy refuse instead.
if (Test-Path -LiteralPath $LockFile) {
  $other = ""
  try { $other = (Get-Content -LiteralPath $LockFile -Raw).Trim() } catch { }
  $alive = $null
  if ($other -match '^\d+$') {
    $alive = Get-Process -Id ([int]$other) -ErrorAction SilentlyContinue
  }
  if ($alive -and $alive.ProcessName -like "*powershell*") {
    Log ("REFUSING: a watcher for this lane is already running as pid " + $other + ". Close that window first, or create STOP-" + $Lane + ".")
    exit 3
  }
  if ($other -ne "") { Log ("stale lock from pid " + $other + "; that process is gone, taking over") }
}
Set-Content -LiteralPath $LockFile -Value $PID -Encoding ASCII

# ----------------------------------------------- credential containment
# Clear any leftovers from earlier versions of this script, which broke git.
Remove-Item Env:GIT_CONFIG_COUNT   -ErrorAction SilentlyContinue
Remove-Item Env:GIT_CONFIG_KEY_0   -ErrorAction SilentlyContinue
Remove-Item Env:GIT_CONFIG_VALUE_0 -ErrorAction SilentlyContinue

if ($KeepSystemGitConfig) {
  Log "WARNING: -KeepSystemGitConfig set; the system credential helper stays available to this lane"
} else {
  if (-not (Test-Path -LiteralPath $EmptyCfg)) {
    New-Item -ItemType File -Path $EmptyCfg -Force | Out-Null
  }
  $env:GIT_CONFIG_SYSTEM = $EmptyCfg
  Log ("system git config replaced with an empty file for child processes: " + $EmptyCfg)
  Log "this stops the default git push path only; it is NOT a boundary, the credential store stays reachable. The boundary is the ruleset on master."
  Log "user.name and user.email still resolve, so lanes can still commit"
}
$env:GIT_TERMINAL_PROMPT = "0"

Log ("watcher up. tree=" + $wt + " mode=" + $PermissionMode + " timeout=" + $TaskTimeoutMinutes + "m")
if ($PermissionMode -eq "bypassPermissions") {
  Log "NOTE: bypassPermissions, no human checkpoint remains before any action this lane takes"
}

$fails = 0

# EVERY EXIT PATH LEAVES A LINE BEHIND. Under $ErrorActionPreference = "Stop"
# any unguarded statement in the loop below is a way to leave it silently, and
# on 2026-10-15 two lanes did exactly that: Move-Item threw, nothing caught it,
# and neither "DONE" nor "watcher down." was ever logged. The two moves are
# guarded individually further down; this trap is the backstop for the CLASS,
# so that the next unguarded statement somebody adds cannot repeat it. `break`
# rather than `continue`, deliberately: resuming after an unknown failure is
# how a lane does half a task.
#
# The window no longer survives the script - START-ALL-LANES.ps1 dropped
# -NoExit on 2026-10-15 21:00 - so an exit here really does release this lane's
# pid lock and the lane can simply be started again. Before that change the
# process stayed alive at an interactive prompt: the process table said the
# lane was up, the queue said it was not, and the pid lock refused the restart.
trap {
  Log ("UNHANDLED " + $_.Exception.GetType().Name + " at line " +
       $_.InvocationInfo.ScriptLineNumber + ": " + $_.Exception.Message)
  Log ("the failing statement was: " + $_.InvocationInfo.Line.Trim())
  Log "watcher down (unhandled error). The lock is released; start this lane again."
  try { Remove-Item -LiteralPath $LockFile -Force -ErrorAction SilentlyContinue } catch { }
  break
}

while ($true) {

  if (Test-Path -LiteralPath $StopAll) { Log "STOP-ALL present. Exiting."; break }
  if (Test-Path -LiteralPath $StopMe)  { Log ("STOP-" + $Lane + " present. Exiting."); break }

  $inflight = @(Get-ChildItem -LiteralPath $Running -Filter *.md -ErrorAction SilentlyContinue)
  if ($inflight.Count -gt 0) {
    Log ("a task is already in RUNNING: " + $inflight[0].Name + ", not starting another")
    Start-Sleep -Seconds $IdleSleepSeconds
    continue
  }

  $next = @(Get-ChildItem -LiteralPath $Queue -Filter *.md -ErrorAction SilentlyContinue |
            Sort-Object Name) | Select-Object -First 1
  if (-not $next) {
    # An idle watcher used to log NOTHING, so a log that had stopped moving was
    # indistinguishable from a script that had died. One line every five
    # minutes makes the log the single authority for "is this lane consuming
    # work" - the question that had no authority at all on 2026-10-15, when the
    # process table said six lanes were up and the queue said four.
    if (-not $script:lastIdle -or ((Get-Date) - $script:lastIdle).TotalMinutes -ge 5) {
      Log "idle: queue empty, RUNNING empty, still polling"
      $script:lastIdle = Get-Date
    }
    Start-Sleep -Seconds $IdleSleepSeconds
    continue
  }

  $runPath = Join-Path $Running $next.Name
  # The same unguarded rename as the one into DONE, with the same consequence:
  # a brief held open by an editor, a backup agent or a virus scanner would end
  # the script here, before "START" had ever been logged.
  try {
    Move-Item -LiteralPath $next.FullName -Destination $runPath -Force
  } catch {
    Log ("CANNOT CLAIM " + $next.Name + " (" + $_.Exception.Message +
         "). Leaving it in the queue and retrying after the idle sleep.")
    Start-Sleep -Seconds $IdleSleepSeconds
    continue
  }
  Log ("START " + $next.Name)

  $stamp   = Get-Date -Format "yyyyMMdd-HHmmss"
  $outFile = Join-Path $LogDir ("task-" + $Lane + "-" + $stamp + ".out")

  # A task that exits 0 having written nothing to its LANE file did not do the
  # work. glm-b task 0040 (2026-10-15 02:23) exited 0 with a 709-byte output -
  # the model-name warning and nothing else - and the four approved copy trims
  # were never applied. The first version of this guard also required the
  # output to be under 1000 bytes, and glm-b 0050 slipped through it: 2112
  # bytes of PLAN PROSE, no lane growth, no commit, exit 0. A model that writes
  # a plan instead of doing the work is exactly the failure this guard exists
  # for, so output length is no longer part of the test. Lane-file growth alone
  # decides. Diagnosed by the glm-b lane itself, 2026-10-15 03:33.
  $laneBefore = $null
  if (Test-Path -LiteralPath $LaneFile) {
    $laneBefore = (Get-Item -LiteralPath $LaneFile).Length
  }

  $code     = $null
  $timedOut = $false
  try {
    $cmdLine = '/c claude -p --permission-mode ' + $PermissionMode +
               ' < "' + $runPath + '" > "' + $outFile + '" 2>&1'
    $proc = Start-Process -FilePath "cmd.exe" -ArgumentList $cmdLine `
                          -WorkingDirectory $wt -NoNewWindow -PassThru
    $null = $proc.Handle

    # WAIT IN SLICES AND SAMPLE THE TREE. The single blocking WaitForExit this
    # replaces was right about the timeout and blind about the task: by the time
    # it returned, any process the task had started was already unattributable
    # if its own parent had exited. Sampling while the links are intact is the
    # only moment an orphan can be tied to this task, and it is what makes
    # "nothing left behind" provable rather than hoped for.
    $deadline = (Get-Date).AddMinutes($TaskTimeoutMinutes)
    $seen     = @{}
    $exited   = $false
    while (-not $exited) {
      $remainMs = [int][Math]::Max(1000, ($deadline - (Get-Date)).TotalMilliseconds)
      $sliceMs  = [int][Math]::Min(($TreeSampleSeconds * 1000), $remainMs)
      if ($proc.WaitForExit($sliceMs)) { $exited = $true; break }
      try {
        $snap = Get-LaneProcTable
        $desc = Get-LaneDescendants -Table $snap -RootPid $proc.Id -SelfPid $PID
        if ($null -ne $desc) {
          foreach ($k in $desc.Keys) { $seen[$k] = $desc[$k] }
        }
      } catch {
        # A sample is a diagnostic, never a gate. Losing one must not end the
        # task and must not end the watcher.
        Log ("tree sample failed (continuing): " + $_.Exception.Message)
      }
      if ((Get-Date) -ge $deadline) { break }
    }

    if (-not $exited) {
      $timedOut = $true
      Log ("TIMEOUT after " + $TaskTimeoutMinutes + " minutes. Killing the whole " +
           "process tree of pid " + $proc.Id + "; " + $seen.Count +
           " process(es) were seen under it during the run.")
      $killed = Stop-LaneProcessTree -RootPid $proc.Id -Accumulated $seen -Say ${function:Log}
      if ($killed.Refused) {
        Log "THE KILL WAS REFUSED and nothing was stopped. That root was this watcher or one of its own ancestors, which should be impossible for a process this script started: investigate before trusting this lane."
      } elseif (-not $killed.Verified) {
        Log ("THE KILL IS NOT VERIFIED. Still alive: " + ($killed.After -join ",") +
             ". The task may still be writing, and it may still hold the brief open.")
      }
    }

    # BOUNDED. The unbounded WaitForExit() this replaces was a second way to
    # stop consuming work with nothing in the log, if a kill ever failed to take.
    if (-not $proc.WaitForExit(30000)) {
      Log ("WARNING: the wrapper pid " + $proc.Id + " is still alive 30s after the kill; continuing anyway")
    }

    if ($timedOut) {
      $code = 124
    } else {
      $code = $proc.ExitCode
      if ($null -eq $code) {
        Log "WARNING: exit code unavailable; treating as success because the process exited on its own"
        $code = 0
      }
    }
  } catch {
    Log ("EXCEPTION: " + $_.Exception.Message)
    $code = 1
  }

  if (Test-Path -LiteralPath $outFile) {
    try {
      Add-Content -LiteralPath $WatchLog -Value (Get-Content -LiteralPath $outFile -Raw) -Encoding UTF8
    } catch { }
  }

  $noWork = $false
  if (-not $timedOut -and $code -eq 0) {
    $laneAfter = $null
    if (Test-Path -LiteralPath $LaneFile) {
      $laneAfter = (Get-Item -LiteralPath $LaneFile).Length
    }
    if ($laneAfter -eq $laneBefore) {
      $noWork = $true
      Log ("NOWORK: exit 0 but LANE-" + $Lane + ".md did not grow. Treating as a failure, not a completion.")
    }
  }

  if ($timedOut) { $suffix = "TIMEOUT" } elseif ($noWork) { $suffix = "NOWORK" } else { $suffix = "exit" + $code }
  $donePath = Join-Path $Done ($stamp + "-" + $suffix + "-" + $next.Name)

  # THE RECORD IS WRITTEN BEFORE THE FILESYSTEM IS ASKED FOR ANYTHING.
  # 2026-10-15: this order cost the glm and pilotcaps lanes their afternoon. The
  # rename threw "being used by another process" - the orphaned task still held
  # the brief open as its stdin - "Stop" made that terminating, and the script
  # left the loop having logged neither DONE nor "watcher down."
  # The DONE line now comes first, so the record exists even when the rename is
  # refused, and the MOVED / MOVE BLOCKED line immediately after it says
  # whether the brief actually moved. The pair is never ambiguous; a DONE on its
  # own would be. The retry is here because the hold is TRANSIENT - the holder
  # of the glm brief was gone 18 seconds after the kill - and the tree kill
  # above should have released it before this line is reached at all.
  Log ("DONE  " + $next.Name + " -> " + $suffix)
  $moved = $false
  for ($try = 1; $try -le 10 -and -not $moved; $try++) {
    try {
      Move-Item -LiteralPath $runPath -Destination $donePath -Force
      $moved = $true
    } catch {
      if ($try -eq 1) { Log ("MOVE BLOCKED (" + $_.Exception.Message + ") - retrying for 30s") }
      Start-Sleep -Seconds 3
    }
  }
  if ($moved) {
    Log ("MOVED " + $next.Name + " -> " + (Split-Path -Leaf $donePath))
  } else {
    Log ("MOVE STILL BLOCKED after 30s. " + $next.Name + " stays in RUNNING, so " +
         "this lane will idle on it and say so every " + $IdleSleepSeconds +
         "s. The DONE line above is the authority that the task ran. NOT exiting.")
  }

  if ($code -ne 0 -or $noWork) { $fails++ } else { $fails = 0 }
  if ($fails -ge $MaxConsecutiveFailures) {
    Log ([string]$fails + " consecutive failures. Exiting rather than looping on a broken task.")
    break
  }
  Start-Sleep -Seconds 5
}
try { Remove-Item -LiteralPath $LockFile -Force -ErrorAction SilentlyContinue } catch { }
Log "watcher down."
