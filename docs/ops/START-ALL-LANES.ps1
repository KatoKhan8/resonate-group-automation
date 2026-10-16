<#
  START-ALL-LANES.ps1 - run this ONCE. It opens one watcher window per lane,
  and then it CHECKS WHETHER THEY CAME UP before it tells you they did.

  ASCII ONLY, deliberately. Windows PowerShell 5.1 reads a .ps1 without a BOM
  in the system ANSI codepage, and a UTF-8 dash or curly quote breaks the parse.

  Stop everything:   create the file  resonate-ops\STOP-ALL
  Stop one lane:     create the file  resonate-ops\STOP-<lane>
  Resume later:      delete the STOP file, run this script again.

  ===========================================================================
  WHY THIS VERSION EXISTS: THE OLD TOTALS LINE COUNTED Start-Process CALLS.
  ===========================================================================

  The version this replaces printed "start <lane>" BEFORE the process existed,
  called Start-Process with neither -Wait nor -PassThru so nothing ever held the
  child's handle or read its exit code, incremented its counter
  unconditionally, and finished with

      7 watcher(s) started in mode bypassPermissions.

  That number was a count of launch attempts. `lane_watcher.ps1` has six refusal
  paths that all fire inside the first second - a missing worktree, the main
  checkout, no .git, no `claude` on PATH, a missing module (now four of them),
  and exit 3 against a live pid lock - and every one of them was invisible here.

  MEASURED 2026-10-16 00:23:27, AND IT WAS WORSE THAN THE TASK BRIEF SAID.
  The brief for this work named two lanes. The logs name SEVEN - every lane in
  the estate refused within two seconds, all with the same line:

      [00:23:27] [glm]          REFUSING: the tree-kill module is missing: ...
      [00:23:27] [glm-b]        REFUSING: the tree-kill module is missing: ...
      [00:23:27] [glm-c]        REFUSING: the tree-kill module is missing: ...
      [00:23:27] [suppression]  REFUSING: the tree-kill module is missing: ...
      [00:23:28] [pilotcaps]    REFUSING: the tree-kill module is missing: ...
      [00:23:28] [qwen]         REFUSING: the tree-kill module is missing: ...
      [00:23:28] [webapp]       REFUSING: the tree-kill module is missing: ...

  The console said seven started. The whole estate was down, and the next
  successful start was 00:28:51 - 5 minutes 23 seconds later, by hand.

  AND THE REFUSALS WERE RIGHT. The task brief flagged, correctly, that
  tools\lane_treekill.ps1 has an mtime of 2026-10-15 21:49:07, which is 94
  minutes BEFORE it was reported missing, and said not to assert a cause. The
  cause is now measured and it is not a mystery - it is the difference between
  two timestamps nobody had looked at:

      CreationTime   2026-10-16 00:28:44.529
      LastWriteTime  2026-10-15 21:49:07.799

  The file at that path was CREATED at 00:28:44 - 76 seconds after the last
  refusal and 7 seconds before the successful restart at 00:28:51. It was not
  there at 00:23:27. It arrived carrying an older write time, which is what a
  move or a timestamp-preserving copy does. So LastWriteTime was never evidence
  of presence, and the seven refusals were each telling the truth.

  WHO moved it is NOT established and is not asserted here. The one adjacent
  fact: tools\lane_watcher.ps1.2026-10-15.bak was created at 22:22:40 and
  lane_watcher.NEW.ps1 at 22:20:25, so somebody was working in tools\ that
  evening. That is a hint and not a measurement.

  ===========================================================================
  WHAT THIS VERSION DOES INSTEAD
  ===========================================================================

  A lane counts as STARTED only on the evidence the estate already trusts: a
  `watcher up` line in that lane's own log, written AFTER this launch began, by
  a process that is still alive. Not the console, not Start-Process returning,
  not a window appearing.

  "After this launch began" is measured by BYTE OFFSET, not by parsing the
  timestamp in the line. The log is append-only, so the length before the launch
  is a mark and only the bytes past it are new. A timestamp has one-second
  resolution and two launches inside one second are exactly the case that broke
  the old script.

  Every launch holds its child's handle (-PassThru), so an exit code is
  readable. The classification, per lane:

      STARTED    a `watcher up` line past the mark, and the process is alive
      REFUSED    a `REFUSING:` line past the mark, or the child exited non-zero
                 -> the reason is READ BACK OUT OF THE LOG and printed here
      SKIPPED    decided before launching: no worktree path, or a STOP file
      CAME UP THEN EXITED   `watcher up` past the mark but the child is gone
      UNKNOWN    the log cannot be read, or nothing appeared within the bound,
                 or the child exited 0 with nothing to say

  UNKNOWN IS NEVER COUNTED AS STARTED. That is the whole point of the rewrite:
  the old line's defect was not that it was wrong, it was that it could not be
  wrong.

  THE WAIT IS BOUNDED AND THE BOUND IS PRINTED. All lanes are launched first,
  then one polling loop resolves them against a SINGLE deadline
  (-UpTimeoutSeconds, default 25), so seven lanes cost 25 seconds in the worst
  case rather than 175. A refusal lands in well under a second and a healthy
  `watcher up` in about one, so the bound is around twenty times the observed
  need.

  EXIT CODE: 0 only when nothing refused and nothing is UNKNOWN. A launcher that
  returns success while three lanes are down is the defect in another form.

  NO -NoExit, SINCE 2026-10-15 21:00. Earlier versions launched each watcher
  with -NoExit, so when a watcher's script ended the SHELL stayed open at a
  prompt: 17 dead shells accumulated, indistinguishable by command line from the
  live ones, and the per-lane pid lock tests whether the PROCESS exists - so a
  crashed script inside a surviving shell kept its lock forever and this script
  refused that lane on the next start with exit 3, silently. That is how glm and
  pilotcaps failed to come back. Without -NoExit the window closes when the
  script ends and the lock goes with it.

  PermissionMode acceptEdits (default) is safe but a lane can stall waiting for
  a shell approval. bypassPermissions runs non-stop with no human checkpoint.
  The watcher empties the SYSTEM git config for every child process, which
  removes the configured credential helper and so stops the DEFAULT git push
  path. It is NOT a boundary: the GCM, wincred and helper-selector binaries stay
  on PATH and the per-user credential store is reachable directly. The boundary
  is the server-side ruleset on master, measured refusing a push with GH013.
#>
param(
  [ValidateSet("acceptEdits", "bypassPermissions", "default", "plan")]
  [string]$PermissionMode = "acceptEdits",

  # The bound on waiting for evidence, for ALL lanes together.
  [int]$UpTimeoutSeconds = 25,

  # Everything below exists so a fixture can drive this script without naming a
  # real lane or touching the live estate. Defaults are the live values.
  [string]$Ops = "C:\Users\Zvonimir\Desktop\resonate-ops",
  [string]$WatcherPath = "",

  # A .ps1 that returns the lane table: @( @{ Lane = "x"; Worktree = "..." } ).
  # Empty means the built-in table below.
  [string]$LaneTablePath = "",

  # Extra arguments appended to every watcher launch, for a fixture that needs
  # -Ops, -TreeKillPath and friends on the child.
  [string[]]$ExtraWatcherArgs = @()
)

$ErrorActionPreference = "Stop"

if ($WatcherPath -eq "") { $WatcherPath = Join-Path $Ops "tools\lane_watcher.ps1" }
$LogDir = Join-Path $Ops "logs"

if (Test-Path -LiteralPath (Join-Path $Ops "STOP-ALL")) {
  Write-Host "STOP-ALL exists. Delete it first or every watcher exits immediately."
  exit 1
}
if (-not (Test-Path -LiteralPath $WatcherPath)) {
  Write-Host ("watcher script not found: " + $WatcherPath)
  exit 1
}

# Paths verified on 2026-10-15. The first five are git worktrees on the Desktop;
# qwen is a standalone remote-less clone in the home folder. webapp is the first
# tree created under Desktop\resonate-trees. A path that does not exist is
# SKIPPED and said so, which is the intended behaviour.
$lanes = @(
  @{ Lane = "glm";         Worktree = "C:\Users\Zvonimir\Desktop\wt-glm-review-2026-10-14" },
  @{ Lane = "glm-b";       Worktree = "C:\Users\Zvonimir\Desktop\wt-glm-b-2026-10-14" },
  @{ Lane = "glm-c";       Worktree = "C:\Users\Zvonimir\Desktop\wt-glm-c-2026-10-14" },
  @{ Lane = "suppression"; Worktree = "C:\Users\Zvonimir\Desktop\wt-suppression-2026-10-14" },
  @{ Lane = "pilotcaps";   Worktree = "C:\Users\Zvonimir\Desktop\wt-pilotcaps-2026-10-14" },
  @{ Lane = "qwen";        Worktree = "C:\Users\Zvonimir\qwc" },
  @{ Lane = "webapp";      Worktree = "C:\Users\Zvonimir\Desktop\resonate-trees\wt-webapp-2026-10-15" }
)
if ($LaneTablePath -ne "") {
  if (-not (Test-Path -LiteralPath $LaneTablePath)) {
    Write-Host ("lane table not found: " + $LaneTablePath); exit 1
  }
  $lanes = @(& $LaneTablePath)
  if ($lanes.Count -eq 0) {
    Write-Host ("the lane table at " + $LaneTablePath + " returned nothing"); exit 1
  }
}

# ---------------------------------------------------------------- the log read
# Retried, and an exhausted retry is UNKNOWN rather than empty. A log being
# appended to by another process can fail to open, and "could not read" is not
# "nothing there" - the distinction DRAIN-LANE.ps1's Read-WatchLog makes for the
# same reason. It is three lines rather than a call into that script, because
# DRAIN-LANE.ps1 is a standalone tool with mandatory parameters and top-level
# behaviour: dot-sourcing it to borrow one helper would run it.
function Read-LaneLog {
  param([string]$Path, [int]$Attempts = 10)
  if (-not (Test-Path -LiteralPath $Path)) { return "" }
  for ($i = 1; $i -le $Attempts; $i++) {
    try { return [System.IO.File]::ReadAllText($Path) } catch { Start-Sleep -Milliseconds 120 }
  }
  return $null            # UNREADABLE, and the caller must not read it as empty
}
function Get-LaneLogLength {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) { return 0 }
  for ($i = 1; $i -le 10; $i++) {
    try { return (Get-Item -LiteralPath $Path).Length } catch { Start-Sleep -Milliseconds 120 }
  }
  return $null            # UNKNOWN mark: cannot tell new lines from old ones
}
function Get-NewTail {
  param([string]$Path, $Mark)
  $text = Read-LaneLog -Path $Path
  if ($null -eq $text) { return $null }
  if ($null -eq $Mark)  { return $null }
  if ($text.Length -lt $Mark) {
    # The log got SHORTER. It was truncated or replaced under us, so the mark no
    # longer separates new from old. Refuse to guess.
    return $null
  }
  return $text.Substring($Mark)
}

# ----------------------------------------------------------------- the launch
$results = New-Object System.Collections.ArrayList
function Record($lane, $state, $why) {
  [void]$results.Add([pscustomobject]@{ Lane = $lane; State = $state; Why = $why })
}

$pending = New-Object System.Collections.ArrayList
Write-Host ("launching " + $lanes.Count + " lane(s) in mode " + $PermissionMode +
            "; evidence bound " + $UpTimeoutSeconds + "s")
Write-Host ""

foreach ($l in $lanes) {
  $lane = [string]$l.Lane
  $wt   = [string]$l.Worktree

  if (-not (Test-Path -LiteralPath $wt)) {
    Write-Host ("  SKIP     " + $lane + " : path not found: " + $wt)
    Record $lane "SKIPPED" ("path not found: " + $wt)
    continue
  }
  $stopMe = Join-Path $Ops ("STOP-" + $lane)
  if (Test-Path -LiteralPath $stopMe) {
    # Do NOT clear it here. Clearing STOP files on 2026-10-15 02:31 revived
    # watchers that were mid-task and about to exit, leaving two per lane.
    Write-Host ("  SKIP     " + $lane + " : STOP-" + $lane + " exists. Delete it when that lane is fully down, then run this again.")
    Record $lane "SKIPPED" ("STOP-" + $lane + " exists")
    continue
  }

  $logPath = Join-Path $LogDir ("watcher-" + $lane + ".log")
  $mark    = Get-LaneLogLength -Path $logPath
  $queue   = Join-Path $Ops ("queue\" + $lane)
  # queued= is the count AT LAUNCH and is relabelled to say so. It is a display
  # number: the watcher consumes a brief within seconds, so by the time anyone
  # reads the console it can already be one lower. That cannot mislead a
  # decision - the authority for depth is the queue directory itself - so the
  # number is unchanged and only its label is honest about when it was taken.
  $count   = @(Get-ChildItem -LiteralPath $queue -Filter *.md -ErrorAction SilentlyContinue).Count

  $wargs = @("-ExecutionPolicy", "Bypass", "-File", $WatcherPath,
             "-Lane", $lane, "-Worktree", $wt, "-PermissionMode", $PermissionMode)
  if ($ExtraWatcherArgs.Count -gt 0) { $wargs += $ExtraWatcherArgs }

  # -PassThru, so the handle is held and the exit code is readable. Its absence
  # is the defect this script was rewritten for.
  $proc = $null
  try {
    $proc = Start-Process powershell -ArgumentList $wargs -PassThru
    # Capture the handle. DEFENSIVE, NOT LOAD-BEARING HERE, and the difference
    # was measured rather than assumed - after getting it wrong once. Under
    # Windows PowerShell 5.1, which is what the estate runs:
    #     -NoNewWindow -PassThru, no handle   ->  ExitCode EMPTY after exit
    #     -NoNewWindow -PassThru, handle      ->  ExitCode 7
    #     -PassThru (this shape), no handle   ->  ExitCode 2
    #     -PassThru (this shape), handle      ->  ExitCode 2
    # So in THIS call shape the code is readable either way and mutation N2
    # (remove this line) is unkillable - which is how the measurement came to be
    # taken. It stays because it costs nothing and because the day somebody adds
    # -NoNewWindow the exit-code branch below would start reading blanks in
    # silence. lane_watcher.ps1 does the same at its own Start-Process.
    $null = $proc.Handle
  } catch {
    Write-Host ("  REFUSED  " + $lane + " : Start-Process failed: " + $_.Exception.Message)
    Record $lane "REFUSED" ("Start-Process failed: " + $_.Exception.Message)
    continue
  }
  Write-Host ("  launched " + $lane + "  pid=" + $proc.Id + "  queued-at-launch=" + $count)
  [void]$pending.Add([pscustomobject]@{
    Lane = $lane; Proc = $proc; Log = $logPath; Mark = $mark
  })
}

# ------------------------------------------------------- resolve, once, bounded
Write-Host ""
if ($pending.Count -gt 0) {
  Write-Host ("waiting up to " + $UpTimeoutSeconds + "s for evidence from " +
              $pending.Count + " launched lane(s)")
}
$deadline = (Get-Date).AddSeconds($UpTimeoutSeconds)
$left = New-Object System.Collections.ArrayList
foreach ($p in $pending) { [void]$left.Add($p) }

while ($left.Count -gt 0 -and (Get-Date) -lt $deadline) {
  $stillLeft = New-Object System.Collections.ArrayList
  foreach ($p in $left) {
    $tail = Get-NewTail -Path $p.Log -Mark $p.Mark
    if ($null -eq $tail) {
      # Unreadable, or an unusable mark. Keep trying until the deadline: a
      # transient lock is common and a permanent one is UNKNOWN below.
      [void]$stillLeft.Add($p); continue
    }
    $exited = $false
    try { $exited = $p.Proc.HasExited } catch { }

    if ($tail -match "(?m)^\[.*\]\s+\[" + [regex]::Escape($p.Lane) + "\]\s+watcher up\.") {
      if ($exited) {
        $code = "unknown"
        try { $code = [string]$p.Proc.ExitCode } catch { }
        Write-Host ("  CAME UP THEN EXITED  " + $p.Lane + " : exit " + $code +
                    ". It logged `watcher up` and is gone; read its log.")
        Record $p.Lane "UNKNOWN" ("came up then exited, code " + $code)
      } else {
        Write-Host ("  STARTED  " + $p.Lane + " : `watcher up` in its own log, pid " +
                    $p.Proc.Id + " alive")
        Record $p.Lane "STARTED" "watcher up, process alive"
      }
      continue
    }

    $refusal = $null
    foreach ($line in ($tail -split "`r?`n")) {
      if ($line -match "REFUSING:") { $refusal = $line.Trim() }
    }
    if ($null -ne $refusal) {
      Write-Host ("  REFUSED  " + $p.Lane + " : " + $refusal)
      Record $p.Lane "REFUSED" $refusal
      continue
    }
    if ($exited) {
      $code = "unknown"
      try { $code = [string]$p.Proc.ExitCode } catch { }
      if ($code -eq "0") {
        Write-Host ("  UNKNOWN  " + $p.Lane + " : the process exited 0 having written " +
                    "nothing to its log. Not counted as started.")
        Record $p.Lane "UNKNOWN" "exited 0 with no log line"
      } else {
        Write-Host ("  REFUSED  " + $p.Lane + " : exited " + $code +
                    " with no REFUSING line in its log. Read " + $p.Log)
        Record $p.Lane "REFUSED" ("exited " + $code + ", no reason in the log")
      }
      continue
    }
    [void]$stillLeft.Add($p)
  }
  $left = $stillLeft
  if ($left.Count -gt 0) { Start-Sleep -Milliseconds 300 }
}

foreach ($p in $left) {
  $tail = Get-NewTail -Path $p.Log -Mark $p.Mark
  if ($null -eq $tail) {
    Write-Host ("  UNKNOWN  " + $p.Lane + " : its log could not be read, or was " +
                "replaced while this ran (" + $p.Log + "). NOT counted as started.")
    Record $p.Lane "UNKNOWN" "log unreadable or truncated under us"
  } else {
    Write-Host ("  UNKNOWN  " + $p.Lane + " : nothing in its log within " +
                $UpTimeoutSeconds + "s. The process may still be starting. " +
                "NOT counted as started.")
    Record $p.Lane "UNKNOWN" ("silent for " + $UpTimeoutSeconds + "s")
  }
}

# ------------------------------------------------------------------- the totals
$started = @($results | Where-Object { $_.State -eq "STARTED" }).Count
$refused = @($results | Where-Object { $_.State -eq "REFUSED" }).Count
$skipped = @($results | Where-Object { $_.State -eq "SKIPPED" }).Count
$unknown = @($results | Where-Object { $_.State -eq "UNKNOWN" }).Count

Write-Host ""
Write-Host ("started=" + $started + "  refused=" + $refused + "  skipped=" + $skipped +
            "  unknown=" + $unknown + "   of " + $lanes.Count + " lane(s), mode " +
            $PermissionMode)
if ($refused -gt 0 -or $unknown -gt 0) {
  Write-Host "NOT EVERY LANE IS UP. The lanes that are not STARTED:"
  foreach ($r in $results) {
    if ($r.State -ne "STARTED") {
      Write-Host ("  " + $r.State.PadRight(8) + " " + $r.Lane.PadRight(12) + " " + $r.Why)
    }
  }
}
Write-Host ("logs: " + $LogDir)

if ($refused -gt 0 -or $unknown -gt 0) { exit 1 }
exit 0
