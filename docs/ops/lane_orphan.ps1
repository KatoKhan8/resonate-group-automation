<#
  lane_orphan.ps1 - a RUNNING brief whose claiming watcher is dead must not
  stop the lane.

  ASCII ONLY, same reason as the files it sits beside: this estate cites sha256
  of these files and compares name-sets across trees with different line
  endings, so nothing here may depend on a non-ASCII byte.

  WHY THIS FILE EXISTS, MEASURED 2026-10-15 into 2026-10-16.

  A watcher that dies mid-task leaves its brief in queue\<lane>\RUNNING\.
  Nothing clears it. The next watcher reaches the "inflight" branch of the main
  loop, finds a file there, logs

      a task is already in RUNNING: <brief>, not starting another

  sleeps, and does it again - with no deadline and no escalation. The log keeps
  moving, so the lane reads as ALIVE in every instrument the estate has, while
  consuming no work at all. Three events in 23 hours, every one cleared by a
  human:

      glm    0065   16:42:37 TIMEOUT -> 21:07:10 restart      4 h 25 min dead
      glm    0067   23:05:10 TIMEOUT -> 00:42:31 hand-clear   1 h 37 min dead
      glm-c  0160   23:05:14 TIMEOUT -> 00:42:32 hand-clear   1 h 37 min dead
                                                            = 7.66 lane-hours

  The 00:28:51 restart onto newer watcher bytes did NOT help: the new watcher
  inherited the stale RUNNING file and refused for 14 further minutes, until the
  files were removed by hand at 00:42:31.

  ===========================================================================
  AN ORPHANED BRIEF IS NEVER RE-RUN. NOT OPTIONALLY, NOT BEHIND A SWITCH.
  ===========================================================================

  The obvious recovery - put the brief back in the queue - is the destructive
  one, and the measurement says so plainly. The two tasks killed at 23:05 WERE
  NOT DEAD:

      LANE-glm.md    was written at 23:29:50   24 minutes AFTER its kill
      LANE-glm-c.md  was written at 00:09:10   64 minutes AFTER its kill

  both with complete entries. The `claude -p` child outlives the wrapper that
  the timeout kills, keeps working in the lane's worktree, and finishes. So
  re-dispatching an orphaned brief puts a SECOND `claude -p` on a worktree a
  first one is still writing to, and the work is not even lost: it lands 24 to
  64 minutes later with no DONE line.

  Therefore the recovery is: move the brief aside under a name that says a human
  must look at it, and take the NEXT brief. The lane keeps working. A person
  decides later whether the orphan's work landed - which is a cheap read of the
  LANE file, and 0171 did exactly that for qwen 0170.

  DO NOT REMOVE THAT RESTRICTION WITHOUT MEETING THE 24 AND 64 MINUTE FIGURES.

  ---------------------------------------------------------------------------
  LIVENESS: PID PLUS CREATION TIME, NOT PID PLUS NAME, AND HERE IS WHY.
  ---------------------------------------------------------------------------

  lane_watcher.ps1's own pid lock tests pid AND process name together, because
  Windows recycles pids and a bare Get-Process -Id is not an answer. That is
  right as far as it goes, and in THIS estate it does not go far enough: all
  seven watchers are `powershell`. A recycled pid that lands on another lane's
  watcher passes the pid-plus-name test and would be read as "my claimer is
  still alive" - which here is the FAIL-OPEN direction, because it leaves the
  lane stalled on a brief whose real owner is gone.

  lane_treekill.ps1 already has the right identity and the reasoning for it:

      # The identity of a process is pid PLUS creation time. A pid on its own
      # is a slot number that the OS reuses.
      function Get-LaneProcKey

  So the sidecar records the claiming watcher's Get-LaneProcKey, and liveness
  is a KEY COMPARISON. A pid still present whose creation time differs is a
  provably different process, which pid-plus-name cannot establish. The process
  name is recorded too, and is used only to describe what the pid now holds in
  the log line a human reads.

  ---------------------------------------------------------------------------
  UNKNOWN IS NOT DEAD, AND THE FAIL-CLOSED ANSWER IS TO LEAVE THE BRIEF ALONE.
  ---------------------------------------------------------------------------

  Catalogue entry 4 is suitelock._alive reading an UNREADABLE PROCESS TABLE as
  dead. This file must not repeat it. Every undecidable input returns UNKNOWN
  and UNKNOWN leaves the brief exactly where it is, with a log line saying the
  decision could not be made and naming the one command a human runs:

      an unreadable sidecar               -> UNKNOWN
      a sidecar with no pid or no key     -> UNKNOWN
      a process table that will not read  -> UNKNOWN
      no sidecar at all (legacy brief)    -> UNKNOWN   (see the next paragraph)

  THE LEGACY CASE IS DELIBERATELY UNKNOWN. Every brief in flight when this file
  is first deployed has no sidecar, because the sidecar did not exist when it
  was claimed. Such a brief is indistinguishable from two sides: it may be held
  by a watcher running older bytes and working perfectly, or it may be the
  orphan this file exists to clear. The destructive error is a second
  `claude -p` on a live worktree, and "no live WATCHER" does not mean "no live
  TASK" - the 24 and 64 minute figures above are exactly that. So the legacy
  brief is left alone and reported, and a human clears it with one Move-Item,
  which is cheap and reversible. The case is also SELF-LIMITING: it exists only
  for briefs claimed before the deploy, and every brief claimed after it is
  decidable. The named falsifier, if the legacy stall ever becomes expensive
  enough to pay for: walk the process table for a task process whose working
  directory is this lane's worktree. That is a real measurement and it is not
  built here.
#>

$script:LaneOrphanSchema = 1

# ---------------------------------------------------------------- the sidecar
# Beside the brief, not inside it: the brief is fed to the task on stdin and
# must stay byte-identical to what the queue held. ".claim" rather than ".md"
# so the watcher's own *.md filters never see it as a brief.
function Get-LaneClaimPath {
  param([Parameter(Mandatory = $true)][string]$RunPath)
  return ($RunPath + ".claim")
}

<#
  Write-LaneClaim - record the claiming watcher's identity beside the brief.

  It must survive the watcher's death, since that is the only case it exists
  for, so it is a plain file written at claim time and removed when the brief
  leaves RUNNING.

  The write is best-effort BY DESIGN and the caller is told so by the return
  value. A watcher that refused to start a task because it could not write a
  sidecar would be a new way to stall a lane, which is the defect being fixed.
  A missing sidecar degrades to the legacy case above - UNKNOWN, leave alone -
  which is safe.
#>
function Write-LaneClaim {
  param(
    [Parameter(Mandatory = $true)][string]$RunPath,
    [Parameter(Mandatory = $true)][string]$Lane,
    [string]$WatchLog = ""
  )
  $claim = Get-LaneClaimPath -RunPath $RunPath
  $procKey  = ""
  $procName = ""
  # ONE AUTHORITY FOR THE KEY, AND THIS COST A MEASUREMENT RATHER THAN A GUESS.
  # The key written here is compared against Get-LaneProcTable's key later, so it
  # must come from the SAME source. It does not do to take it from Get-Process:
  # measured 2026-10-16 on this machine, for one live process,
  #
  #     Get-Process .StartTime      639277492085811234
  #     CIM         .CreationDate   639277492085811230     <- 4 ticks earlier
  #
  # because CIM truncates to microseconds while .NET keeps 100ns. Two sources
  # for one number, four ticks apart, and the keys would NEVER have matched - so
  # a live claiming watcher would have read DEAD and its brief would have been
  # moved aside under it. That is the fail-OPEN direction and it is the exact
  # shape CLAUDE.md names: a second representation of a truth that then drifts.
  # So the table is the only source, on both sides.
  try {
    if (Get-Command Get-LaneProcTable -ErrorAction SilentlyContinue) {
      $table = Get-LaneProcTable
      if ($table -and $table.ContainsKey($PID)) {
        $procKey  = $table[$PID].Key
        $procName = $table[$PID].Name
      }
    }
  } catch { }
  if ($procName -eq "") {
    try { $procName = (Get-Process -Id $PID -ErrorAction Stop).ProcessName } catch { }
  }
  # EVERY ELEMENT IS PARENTHESISED, and that is not style. Without the brackets
  # PowerShell's comma binds TIGHTER than +, so
  #     @("a=" + $x, "b=" + $y)
  # parses as "a=" + ($x, "b=") + $y and collapses the whole list into ONE
  # space-joined string. Measured 2026-10-16 by this module's own test leg A13:
  # the sidecar was written as a single line, every field after the first was
  # unparseable, and the claim read back with no pid - so a live watcher's brief
  # was undecidable instead of ALIVE. The test caught it; the code did not say it.
  $lines = @(
    ("schema=" + $script:LaneOrphanSchema),
    ("lane=" + $Lane),
    ("pid=" + $PID),
    ("key=" + $procKey),
    ("name=" + $procName),
    ("claimed_at=" + (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")),
    ("brief=" + (Split-Path -Leaf $RunPath)),
    ("watchlog=" + $WatchLog)
  )
  try {
    Set-Content -LiteralPath $claim -Value $lines -Encoding ASCII -ErrorAction Stop
    return [pscustomobject]@{ Ok = $true; Path = $claim; Why = "" }
  } catch {
    return [pscustomobject]@{ Ok = $false; Path = $claim; Why = $_.Exception.Message }
  }
}

function Remove-LaneClaim {
  param([Parameter(Mandatory = $true)][string]$RunPath)
  $claim = Get-LaneClaimPath -RunPath $RunPath
  try { Remove-Item -LiteralPath $claim -Force -ErrorAction SilentlyContinue } catch { }
}

# ------------------------------------------------------------------- the read
# Retried, because a file being written by another process can fail to open and
# that is not the same as absent. An exhausted retry is UNKNOWN, never empty.
function Read-LaneClaim {
  param(
    [Parameter(Mandatory = $true)][string]$RunPath,
    [int]$Attempts = 12
  )
  $claim = Get-LaneClaimPath -RunPath $RunPath
  $out = [pscustomobject]@{
    Present = $false; Readable = $false; ClaimPid = $null
    Key = ""; Name = ""; ClaimedAt = ""; Path = $claim; Why = ""
  }
  if (-not (Test-Path -LiteralPath $claim)) {
    $out.Why = "no sidecar at " + $claim
    return $out
  }
  $out.Present = $true
  $text = $null
  for ($i = 1; $i -le $Attempts -and $null -eq $text; $i++) {
    try { $text = [System.IO.File]::ReadAllText($claim) } catch { Start-Sleep -Milliseconds 120 }
  }
  if ($null -eq $text) {
    $out.Why = "the sidecar exists but could not be read in " + $Attempts + " attempts"
    return $out
  }
  $out.Readable = $true
  foreach ($line in ($text -split "`r?`n")) {
    $kv = $line.Split("=", 2)
    if ($kv.Count -ne 2) { continue }
    switch ($kv[0].Trim()) {
      "pid"        { if ($kv[1].Trim() -match '^\d+$') { $out.ClaimPid = [int]$kv[1].Trim() } }
      "key"        { $out.Key = $kv[1].Trim() }
      "name"       { $out.Name = $kv[1].Trim() }
      "claimed_at" { $out.ClaimedAt = $kv[1].Trim() }
    }
  }
  if ($null -eq $out.ClaimPid) { $out.Why = "the sidecar carries no usable pid" }
  return $out
}

<#
  Test-LaneClaimOwner - is the watcher that claimed this brief still running?

  Returns ALIVE | DEAD | UNKNOWN with a Why that is fit to put in a log a human
  reads. UNKNOWN is a real answer and the caller must treat it as "do not act".

  -ProcTable lets a test inject a table. $null means "query it", and a query
  that THROWS is UNKNOWN - never dead.
#>
function Test-LaneClaimOwner {
  param(
    [Parameter(Mandatory = $true)][string]$RunPath,
    $ProcTable = $null,
    [int]$Attempts = 12
  )
  $claim = Read-LaneClaim -RunPath $RunPath -Attempts $Attempts
  $res = [pscustomobject]@{
    Verdict = "UNKNOWN"; ClaimPid = $claim.ClaimPid; Key = $claim.Key
    Name = $claim.Name; ClaimedAt = $claim.ClaimedAt
    SidecarPresent = $claim.Present; Why = ""
  }
  if (-not $claim.Present) {
    $res.Why = ("no claim sidecar beside the brief, so its owner cannot be " +
                "identified. This is the legacy case: a brief claimed before " +
                "the sidecar existed. UNKNOWN is not dead.")
    return $res
  }
  if (-not $claim.Readable) {
    $res.Why = $claim.Why + ". UNKNOWN is not dead."
    return $res
  }
  if ($null -eq $claim.ClaimPid) {
    $res.Why = $claim.Why + ". UNKNOWN is not dead."
    return $res
  }

  $table = $ProcTable
  if ($null -eq $table) {
    if (-not (Get-Command Get-LaneProcTable -ErrorAction SilentlyContinue)) {
      $res.Why = ("the process table helper Get-LaneProcTable is not loaded, so " +
                  "liveness cannot be decided. UNKNOWN is not dead.")
      return $res
    }
    try { $table = Get-LaneProcTable } catch {
      $res.Why = ("the process table could not be read (" + $_.Exception.Message +
                  "). UNKNOWN is not dead.")
      return $res
    }
  }
  if ($null -eq $table -or $table.Count -eq 0) {
    # A table with no rows is not a machine with no processes. This reader is
    # itself a process, so its own absence proves the read failed. That is
    # catalogue entry 4 in one line.
    $res.Why = "the process table came back empty, which cannot be true. UNKNOWN is not dead."
    return $res
  }
  if (-not $table.ContainsKey($PID)) {
    $res.Why = ("the process table does not contain this reader's own pid " + $PID +
                ", so the read is not trustworthy. UNKNOWN is not dead.")
    return $res
  }

  if (-not $table.ContainsKey($claim.ClaimPid)) {
    $res.Verdict = "DEAD"
    $res.Why = ("pid " + $claim.ClaimPid + " is absent from a process table that " +
                "does contain this reader, so the claiming watcher is gone.")
    return $res
  }

  $now = $table[$claim.ClaimPid]
  if ($claim.Key -eq "") {
    # No key to compare: fall back to the watcher's own pid-plus-name test, and
    # say in the verdict that the weaker test was used. Name agreement cannot
    # prove ALIVE here - every watcher on this machine is powershell - so the
    # only safe answers are DEAD on disagreement and UNKNOWN on agreement.
    if ($now.Name -notlike "*powershell*" -and $now.Name -notlike "*pwsh*") {
      $res.Verdict = "DEAD"
      $res.Why = ("the sidecar carries no creation-time key; pid " + $claim.ClaimPid +
                  " now holds '" + $now.Name + "', which is not a shell, so the pid " +
                  "was recycled and the claiming watcher is gone.")
      return $res
    }
    $res.Why = ("the sidecar carries no creation-time key and pid " + $claim.ClaimPid +
                " now holds '" + $now.Name + "'. A matching name cannot prove identity " +
                "here because every watcher on this machine is powershell. UNKNOWN is not dead.")
    return $res
  }
  if ($now.Key -eq $claim.Key) {
    $res.Verdict = "ALIVE"
    $res.Why = ("pid " + $claim.ClaimPid + " is present and its creation-time key matches " +
                "the sidecar, so the claiming watcher is the same process and is running.")
    return $res
  }
  $res.Verdict = "DEAD"
  $res.Why = ("pid " + $claim.ClaimPid + " is present but its creation-time key differs " +
              "from the sidecar (" + $now.Key + " now, " + $claim.Key + " then), so that " +
              "pid was recycled and the claiming watcher is gone.")
  return $res
}

<#
  Resolve-LaneOrphanedRunning - run this ONCE at startup, before the main loop.

  Returns a result object; it does not decide what the caller does next beyond
  moving an orphan aside. -LogFn is the watcher's own Log, so every line lands
  in watcher-<lane>.log where the estate's instruments already read.

  Action = NONE | MOVED | LEFT
     NONE   nothing in RUNNING.
     MOVED  the owner is provably dead; the brief is in DONE under
            <stamp>-ORPHANED-NEEDS-REVIEW-<brief> and the lane may proceed.
     LEFT   the owner is alive, or undecidable, or the move failed. The brief
            stays in RUNNING and the inflight branch will do what it does now.
#>
function Resolve-LaneOrphanedRunning {
  param(
    [Parameter(Mandatory = $true)][string]$Running,
    [Parameter(Mandatory = $true)][string]$Done,
    [Parameter(Mandatory = $true)][string]$Lane,
    $LogFn = $null,
    $ProcTable = $null
  )
  $say = { param($m) if ($LogFn) { & $LogFn $m } else { Write-Host $m } }

  $res = [pscustomobject]@{
    Action = "NONE"; Verdict = ""; Brief = ""; MovedTo = ""; Why = ""
  }
  $inflight = @(Get-ChildItem -LiteralPath $Running -Filter *.md -ErrorAction SilentlyContinue |
                Sort-Object Name)
  if ($inflight.Count -eq 0) { return $res }

  if ($inflight.Count -gt 1) {
    # Two briefs in RUNNING is not a state this watcher creates. Report it and
    # resolve only the first; a human should see the rest.
    & $say ("ORPHAN CHECK: " + $inflight.Count + " briefs are in RUNNING, which this " +
            "watcher never produces. Resolving only " + $inflight[0].Name +
            "; the others need a human.")
  }

  $brief   = $inflight[0]
  $runPath = $brief.FullName
  $res.Brief = $brief.Name

  $owner = Test-LaneClaimOwner -RunPath $runPath -ProcTable $ProcTable
  $res.Verdict = $owner.Verdict

  if ($owner.Verdict -eq "ALIVE") {
    $res.Action = "LEFT"
    $res.Why = $owner.Why
    & $say ("ORPHAN CHECK: " + $brief.Name + " is claimed by a LIVE watcher (pid " +
            $owner.ClaimPid + ", claimed " + $owner.ClaimedAt + "). Leaving it exactly " +
            "as it is. " + $owner.Why)
    return $res
  }

  if ($owner.Verdict -eq "UNKNOWN") {
    $res.Action = "LEFT"
    $res.Why = $owner.Why
    & $say ("ORPHAN CHECK: CANNOT DECIDE who owns " + $brief.Name + ", so it is LEFT " +
            "ALONE and this lane will idle on it. " + $owner.Why)
    & $say ("ORPHAN CHECK: a human resolves it with one command, and should read " +
            "LANE-" + $Lane + ".md first in case the work already landed:  " +
            "Move-Item '" + $runPath + "' '" + (Join-Path $Done ((Get-Date -Format "yyyyMMdd-HHmmss") +
            "-ORPHANED-NEEDS-REVIEW-" + $brief.Name)) + "'")
    return $res
  }

  # DEAD. Move it aside under a name that says a human must look, and never
  # back into the queue - see the 24 and 64 minute figures at the top of this
  # file.
  $stamp    = Get-Date -Format "yyyyMMdd-HHmmss"
  $doneName = $stamp + "-ORPHANED-NEEDS-REVIEW-" + $brief.Name
  $donePath = Join-Path $Done $doneName
  & $say ("ORPHAN CHECK: " + $brief.Name + " was claimed by a watcher that is GONE. " +
          $owner.Why)
  try {
    Move-Item -LiteralPath $runPath -Destination $donePath -Force -ErrorAction Stop
  } catch {
    $res.Action = "LEFT"
    $res.Why = "the move aside failed: " + $_.Exception.Message
    & $say ("ORPHAN CHECK: the move aside FAILED (" + $_.Exception.Message +
            "). " + $brief.Name + " stays in RUNNING and this lane will idle on it. " +
            "Nothing is lost and nothing is duplicated.")
    return $res
  }
  Remove-LaneClaim -RunPath $runPath
  $res.Action  = "MOVED"
  $res.MovedTo = $donePath
  $res.Why     = $owner.Why
  & $say ("ORPHAN CHECK: moved it to " + $doneName + " and taking the next brief. " +
          "THE ORPHAN IS NOT RE-RUN: on 2026-10-15 two killed tasks wrote complete " +
          "lane entries 24 and 64 minutes AFTER their kill, so a re-run would put a " +
          "second task on a worktree the first may still be writing to. A human " +
          "decides whether its work landed by reading LANE-" + $Lane + ".md.")
  return $res
}
