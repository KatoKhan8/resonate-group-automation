<#
  lane_treekill.ps1 - stop a task's WHOLE process tree, and prove it stopped.

  Dot-sourced by tools\lane_watcher.ps1. It is a separate file for one reason:
  a test has to call the real function. The watcher takes mandatory parameters
  and then enters an infinite loop, so a test cannot dot-source it; this file
  can be, and docs\ops\test_lane_watcher_treekill.ps1 does exactly that.

  ASCII ONLY, DELIBERATELY - the watcher's reason, unchanged. Windows
  PowerShell 5.1 reads a BOM-less .ps1 in the system ANSI codepage, and a UTF-8
  dash or curly quote arrives as a character PowerShell accepts as a string
  delimiter, which breaks the parse.

  NO Set-StrictMode HERE, DELIBERATELY. Set-StrictMode applies to the scope it
  runs in and to child scopes, and this file is DOT-SOURCED into the watcher's
  own scope - so setting it here would silently change the strictness of every
  statement in lane_watcher.ps1. A module must not reach back into its caller.

  WHY THIS EXISTS - measured by the qwen lane, 2026-10-15 (TASK 0070):

      Stop-Process -Id <cmd.exe wrapper> -Force   LEAVES THE CHILD RUNNING.

  The watcher launches `cmd.exe /c claude -p ... < brief > out`. Killing the
  wrapper takes the wrapper only. The `claude` child kept working for 23
  seconds (glm 0065) and 27 MINUTES (pilotcaps 0130) after their 90-minute
  "kills", and both finished their work and wrote their lane entries. Worse,
  the orphan still held the brief open as its inherited stdin, so the watcher's
  Move-Item of that brief into DONE was refused, $ErrorActionPreference =
  "Stop" made the refusal terminating, nothing caught it, and the watcher's
  script left the loop having logged neither DONE nor "watcher down." Two lanes
  lost their afternoon to a timeout that stopped nothing except the watcher.

  TWO RULES THIS FILE ENFORCES, both of them scar tissue:

  1. SELECTION IS BY PID ANCESTRY. NEVER BY A COMMANDLINE SUBSTRING.
     In that same TASK 0070 run a `CommandLine -like "*child.ps1*"` filter
     matched THE FILTERING PROCESS'S OWN command line - the filter was itself a
     `powershell` whose argv contained the pattern - and Stop-Process ended the
     measurement shell with exit 255. A CommandLine substring filter always
     matches itself. Nothing in this file reads CommandLine at all, and on top
     of that the caller's own pid and every ancestor of it are subtracted from
     every kill set, and a root inside that chain is REFUSED outright rather
     than returned as an empty set.

  2. A KILL IS NOT DONE BECAUSE taskkill PRINTED SUCCESS.
     `taskkill /T` walks LIVE parent links, so a grandchild whose parent has
     already exited is invisible to it. TASK 0070 left that as an honest limit:
     "treat the tree-kill as measured-better, not proven-complete." This file
     closes it by sampling the descendant set DURING the run, while the links
     are still intact, then sweeping the accumulated set afterwards by
     identity, then RE-READING the table and reporting the survivors. Verified
     means zero survivors measured after the sweep. It never means an exit code.

  PID REUSE is treated as a real hazard rather than a theoretical one: every
  pid is carried with its CreationDate, and a sweep only kills a pid whose
  creation time still matches the one recorded. A recycled pid is a DIFFERENT
  process and killing it would be killing a stranger.
#>

# A snapshot of the whole process table, keyed by pid. One CIM query: walking
# parent links inside a single snapshot is consistent, walking them with live
# per-pid queries is not.
function Get-LaneProcTable {
  $table = @{}
  foreach ($p in @(Get-CimInstance -ClassName Win32_Process -ErrorAction Stop)) {
    $thisPid = [int]$p.ProcessId
    $created = $null
    try { $created = $p.CreationDate } catch { }
    $table[$thisPid] = [pscustomobject]@{
      Pid     = $thisPid
      Ppid    = [int]$p.ParentProcessId
      Name    = [string]$p.Name
      Created = $created
      Key     = (Get-LaneProcKey -ProcPid $thisPid -Created $created)
    }
  }
  return $table
}

# The identity of a process is pid PLUS creation time. A pid on its own is a
# slot number that the OS reuses.
function Get-LaneProcKey {
  param([Parameter(Mandatory = $true)][int]$ProcPid, $Created)
  $ticks = 0
  if ($Created) { $ticks = $Created.Ticks }
  return ("" + $ProcPid + "|" + $ticks)
}

<#
  Get-LaneSelfChain - self plus every ancestor, upward.

  Returns a HASHTABLE of pid -> hop number (0 = $FromPid). A hashtable for two
  reasons: membership is a .ContainsKey() rather than a scan, and PowerShell
  UNROLLS an IEnumerable on return - a HashSet[int] came back from this
  function as an Object[], which happened to still answer .Contains() and so
  hid the fact that the type was not what the signature implied.

  THE WALK VALIDATES EVERY HOP AGAINST CREATION TIME, and that is the whole
  difficulty. ParentProcessId is a pid, and a pid is a SLOT the OS reuses. When
  a process's parent has exited, that field still holds the number, and if the
  number has been handed to a new process the naive walk climbs out of the real
  ancestry and into a stranger's subtree.

  MEASURED 2026-10-15 21:49, by this module's own test going red. The true
  ancestry of the test shell was six deep:

      89944 <- 94112 <- 65164 <- 80556 <- 66028 <- 79700

  and the unvalidated walk returned EIGHT, continuing 79700 <- 89976 <- 79652,
  because the lane launcher's parent slot had been reused. 79652 was a process
  inside the test's own fixture, so the fixture's cmd.exe was reported as an
  ANCESTOR of the test shell and the kill was refused. The failure direction
  was safe - a false refusal kills nothing - but a timeout that refuses to kill
  is the original defect back again, so this is a correctness bug either way.

  A parent is created at or before its child. If the candidate parent's
  creation time is LATER than the child's, that pid slot has been recycled and
  the real parent is gone: the walk stops there. A record with no creation time
  also stops it, because an unknown cannot be validated and UNKNOWN is never a
  pass.
#>
function Get-LaneSelfChain {
  param(
    [Parameter(Mandatory = $true)][hashtable]$Table,
    [Parameter(Mandatory = $true)][int]$FromPid
  )
  $chain = @{}
  $chain[$FromPid] = 0
  $cur = $FromPid
  for ($hop = 1; $hop -lt 64; $hop++) {
    if (-not $Table.ContainsKey($cur)) { break }
    $next = $Table[$cur].Ppid
    if ($next -le 0) { break }
    if ($chain.ContainsKey($next)) { break }          # cycle
    if (-not $Table.ContainsKey($next)) { break }     # parent is gone
    $childCreated  = $Table[$cur].Created
    $parentCreated = $Table[$next].Created
    if (-not $childCreated -or -not $parentCreated) { break }
    if ($parentCreated -gt $childCreated) { break }   # slot reused: not our parent
    $chain[$next] = $hop
    $cur = $next
  }
  return $chain
}

# Readable rendering of a chain, nearest first.
function Format-LaneChain {
  param([Parameter(Mandatory = $true)][hashtable]$Chain)
  return (($Chain.GetEnumerator() | Sort-Object Value | ForEach-Object { $_.Key }) -join " <- ")
}

<#
  Get-LaneDescendants - every descendant of $RootPid, inclusive, found by
  walking ParentProcessId links DOWNWARD inside a snapshot.

  Returns a HASHTABLE keyed by identity (pid|ticks), deliberately, so that an
  empty answer cannot be confused with a refusal: PowerShell unrolls an empty
  array to $null on return, which would make "nothing to kill" and "the kill
  was aimed at the killer" the same value. A hashtable does not unroll.

      $null       REFUSAL. $RootPid is the caller or an ancestor of it.
      .Count = 0  nothing below the root.

  The caller's own chain is excluded from the walk, so even a corrupted or
  reused parent link cannot aim the kill at the watcher.
#>
function Get-LaneDescendants {
  param(
    [Parameter(Mandatory = $true)][hashtable]$Table,
    [Parameter(Mandatory = $true)][int]$RootPid,
    [Parameter(Mandatory = $true)][int]$SelfPid
  )
  $self = Get-LaneSelfChain -Table $Table -FromPid $SelfPid
  if ($self.ContainsKey($RootPid)) { return $null }

  $kids = @{}
  foreach ($p in $Table.Values) {
    if (-not $kids.ContainsKey($p.Ppid)) {
      $kids[$p.Ppid] = New-Object System.Collections.ArrayList
    }
    $null = $kids[$p.Ppid].Add($p.Pid)
  }

  $out     = @{}
  $visited = New-Object 'System.Collections.Generic.HashSet[int]'
  $stack   = New-Object System.Collections.Stack
  $stack.Push($RootPid)
  while ($stack.Count -gt 0) {
    $cur = [int]$stack.Pop()
    if (-not $visited.Add($cur)) { continue }
    if ($self.ContainsKey($cur)) { continue }
    if ($Table.ContainsKey($cur)) { $out[$Table[$cur].Key] = $Table[$cur] }
    if ($kids.ContainsKey($cur)) {
      foreach ($k in $kids[$cur]) { if (-not $visited.Contains($k)) { $stack.Push($k) } }
    }
  }
  return $out
}

<#
  Stop-LaneProcessTree - kill the tree rooted at $RootPid and MEASURE the result.

    -RootPid      the cmd.exe wrapper the watcher started.
    -Accumulated  hashtable Key -> record, gathered by sampling the tree during
                  the run. This is what catches a grandchild whose parent
                  exited before the kill, which taskkill /T cannot see.
    -SelfPid      whose chain to protect. Defaults to this process. A parameter
                  only so the test can prove the subtraction.
    -Say          scriptblock log sink, so the watcher's own Log function keeps
                  the lane prefix on every line.

  Returns:
    Refused   $true when the root was the caller or an ancestor. NOTHING killed.
    Before    pids in the kill set, measured before the kill
    After     pids of the kill set still alive after the sweep, identity-matched
    Verified  $true only when After is empty AND the root is gone
    Taskkill  taskkill's own output lines
#>
function Stop-LaneProcessTree {
  param(
    [Parameter(Mandatory = $true)][int]$RootPid,
    [hashtable]$Accumulated,
    [int]$SelfPid = $PID,
    [int]$SweepRounds = 3,
    [int]$SweepPauseSeconds = 2,
    [scriptblock]$Say
  )
  if (-not $Say) { $Say = { param($m) Write-Host $m } }

  $table = Get-LaneProcTable
  $self  = Get-LaneSelfChain -Table $table -FromPid $SelfPid
  $live  = Get-LaneDescendants -Table $table -RootPid $RootPid -SelfPid $SelfPid

  if ($null -eq $live) {
    & $Say ("REFUSING TO KILL: pid " + $RootPid + " is this process (" + $SelfPid +
            ") or one of its ancestors. Nothing killed. This is the guard that " +
            "exists because a CommandLine substring filter killed its own " +
            "measurement shell on 2026-10-15: selection here is by pid " +
            "ancestry and the caller's own chain is always excluded.")
    return [pscustomobject]@{
      Refused = $true; Before = @(); After = @(); Verified = $false; Taskkill = @()
    }
  }

  # The kill set: what is below the root right now, UNION everything that was
  # ever seen below it and is still the same process.
  $set = @{}
  foreach ($k in $live.Keys) { $set[$k] = $live[$k] }
  if ($Accumulated) {
    foreach ($k in @($Accumulated.Keys)) {
      if ($set.ContainsKey($k)) { continue }
      $rec = $Accumulated[$k]
      $rp  = [int]$rec.Pid
      if ($self.ContainsKey($rp)) { continue }
      if ($table.ContainsKey($rp) -and $table[$rp].Key -eq $k) {
        $set[$k] = $table[$rp]
        & $Say ("ORPHAN still alive and added to the kill set: pid " + $rp + " (" +
                $table[$rp].Name + ") - it was seen below the root in an earlier " +
                "sample and taskkill /T cannot reach it, because its parent is gone")
      }
    }
  }

  $ordered = @($set.Values | Sort-Object Pid)
  $before  = @($ordered | ForEach-Object { $_.Pid })
  $shown   = (($ordered | ForEach-Object { "" + $_.Pid + ":" + $_.Name }) -join " ")
  if ($before.Count -eq 0) { $shown = "(empty)" }
  & $Say ("KILL SET before (" + $before.Count + "): " + $shown)

  # 1. The tree kill. taskkill /T /F is the only built-in that walks children.
  $tk = @()
  if ($table.ContainsKey($RootPid)) {
    $savedEap = $ErrorActionPreference
    try {
      # Native stderr merged into the pipeline raises NativeCommandError under
      # "Stop" in PowerShell 5.1, and taskkill writes its failures to stderr.
      $ErrorActionPreference = "Continue"
      $tk = @(& taskkill.exe /PID $RootPid /T /F 2>&1 | ForEach-Object { [string]$_ })
    } catch {
      $tk = @("taskkill threw: " + $_.Exception.Message)
    } finally {
      $ErrorActionPreference = $savedEap
    }
    foreach ($l in $tk) { if ($l.Trim()) { & $Say ("taskkill: " + $l.Trim()) } }
  } else {
    & $Say ("root pid " + $RootPid + " is already gone; skipping taskkill and " +
            "going straight to the sweep, because the accumulated set may " +
            "still hold live orphans")
  }

  # 2. Measure, then sweep whatever survived - including anything that appeared
  #    under a survivor between the snapshot and the kill.
  for ($round = 1; $round -le $SweepRounds; $round++) {
    Start-Sleep -Seconds $SweepPauseSeconds
    $now  = Get-LaneProcTable
    $self = Get-LaneSelfChain -Table $now -FromPid $SelfPid

    foreach ($rec in @($set.Values)) {
      $rp = [int]$rec.Pid
      if (-not $now.ContainsKey($rp)) { continue }
      if ($now[$rp].Key -ne $rec.Key) { continue }
      $extra = Get-LaneDescendants -Table $now -RootPid $rp -SelfPid $SelfPid
      if ($null -eq $extra) { continue }
      foreach ($ek in $extra.Keys) { if (-not $set.ContainsKey($ek)) { $set[$ek] = $extra[$ek] } }
    }

    $survivors = @()
    foreach ($rec in @($set.Values)) {
      $rp = [int]$rec.Pid
      if ($self.ContainsKey($rp)) { continue }
      if (-not $now.ContainsKey($rp)) { continue }
      if ($now[$rp].Key -ne $rec.Key) { continue }   # pid reused: a stranger. Leave it.
      $survivors += $rec
    }
    if ($survivors.Count -eq 0) { break }

    & $Say ("sweep round " + $round + ": " + $survivors.Count + " survivor(s): " +
            (($survivors | Sort-Object Pid | ForEach-Object { "" + $_.Pid + ":" + $_.Name }) -join " "))
    foreach ($rec in $survivors) {
      try { Stop-Process -Id ([int]$rec.Pid) -Force -ErrorAction Stop }
      catch { & $Say ("sweep could not stop pid " + $rec.Pid + ": " + $_.Exception.Message) }
    }
  }

  # 3. The verdict is a measurement, never an exit code.
  $final = Get-LaneProcTable
  $self  = Get-LaneSelfChain -Table $final -FromPid $SelfPid
  $after = @()
  foreach ($rec in @($set.Values)) {
    $rp = [int]$rec.Pid
    if ($self.ContainsKey($rp)) { continue }
    if (-not $final.ContainsKey($rp)) { continue }
    if ($final[$rp].Key -ne $rec.Key) { continue }
    $after += $rp
  }
  $after    = @($after | Sort-Object)
  $rootGone = -not $final.ContainsKey($RootPid)

  if ($after.Count -eq 0 -and $rootGone) {
    & $Say ("KILL VERIFIED: 0 of " + $before.Count + " still alive. after: (empty)")
  } else {
    $list = "(empty)"
    if ($after.Count -gt 0) { $list = ($after -join ",") }
    & $Say ("KILL INCOMPLETE: after: " + $list + "  rootGone=" + $rootGone +
            ". The brief may still be held open as an orphan's stdin; the " +
            "MOVE line below is what says whether it was.")
  }

  return [pscustomobject]@{
    Refused  = $false
    Before   = $before
    After    = $after
    Verified = ($after.Count -eq 0 -and $rootGone)
    Taskkill = $tk
  }
}
