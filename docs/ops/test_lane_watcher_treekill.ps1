<#
  test_lane_watcher_treekill.ps1 - the proof for docs\ops\lane_treekill.ps1.

  It dot-sources the REAL module and calls the REAL functions. It does not
  search the source for words: CLAUDE.md, "test behaviour, not the text of the
  source" - a grep-the-source test goes red when somebody writes a comment,
  which has happened repeatedly in this repository.

  SAFE BY CONSTRUCTION. Everything it kills, it started itself, inside its own
  throwaway directory under $env:TEMP. It never selects a process by name,
  window title or command-line substring; every selection is a pid this script
  recorded when it launched the process, matched on pid PLUS creation time. It
  touches no lane, no queue, no worktree, no network and no lock.

  RUN IT:
      powershell -NoProfile -ExecutionPolicy Bypass -File <this file>
  Exit 0 = every leg passed. Exit 1 = at least one leg failed.

  ASCII ONLY, deliberately, same reason as the watcher.

  EIGHT LEGS. Each one is a requirement, and each requirement names the
  mutation that must turn it red:

    A   Stop-Process -Force on the cmd.exe wrapper LEAVES THE CHILD RUNNING.
        This is the behaviour being replaced, and the leg PASSES when the
        child survives - it is the control, not an aspiration.
        Mutation: none. If this leg ever goes red, the premise of the whole
        fix has changed and the fix should be re-argued, not adjusted.

    B   Stop-LaneProcessTree on the same shape leaves NOTHING behind, AND the
        single taskkill call reached more than one process.
        Mutation: drop /T from the taskkill call -> B red. The second clause is
        why: without it the leg stayed GREEN under that mutation, because the
        sweep kills the leftovers anyway. The sweep is the guarantee; /T is the
        prompt path. A leg that cannot tell them apart tests only one of them.

    C1  Bare `taskkill /PID <root> /T /F` MISSES an orphaned grandchild,
        because /T walks live parent links only. The honest limit TASK 0070
        recorded, now measured. Control leg; passes when the orphan survives.

    C2  Stop-LaneProcessTree with the accumulated sample CATCHES that orphan.
        Mutation: remove the -Accumulated union block -> C2 red.

    D1  A root that is the caller or an ancestor of the caller is REFUSED,
        and nothing is killed. The caller is still alive afterwards.
        Mutation: remove the self-chain refusal in Get-LaneDescendants -> D1
        red, and it goes red by this script killing its own shell, which is
        exactly what happened on 2026-10-15.

    D2  A COMMANDLINE SUBSTRING FILTER ALWAYS MATCHES ITSELF - measured here,
        in this process, against this process - and the module's pid-ancestry
        selection does not. Two measurements, one hazard, one guard.
        Mutation: none available; the hazard is a property of CIM, not of the
        module. The leg exists so that a future session cannot reintroduce a
        substring filter and claim it is equivalent.

    E   A RECYCLED PID IS A STRANGER. An accumulated entry whose pid is alive
        but whose creation time does not match is NOT killed.
        Mutation: remove the Key comparison from the -Accumulated union -> E
        red, and a process this script never started dies.

    F   THE UPWARD WALK STOPS AT A REUSED PARENT SLOT. A pure-function leg on
        a synthetic table, because the live version of this is not
        reproducible on demand: it depends on whether a recycled pid happens
        to land inside the fixture. It did, at 21:49 on 2026-10-15, and it
        refused Leg B. This leg is the deterministic guard for that.
        Mutation: remove the creation-time comparison in Get-LaneSelfChain ->
        F red.
#>
param(
  [string]$WorkRoot = (Join-Path $env:TEMP "qwen0090-treekill"),
  [switch]$KeepFixtures
)

$ErrorActionPreference = "Stop"

# The module under test. Same directory as this file.
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$module = Join-Path $here "lane_treekill.ps1"
if (-not (Test-Path -LiteralPath $module)) {
  Write-Host ("FATAL: module not found next to this test: " + $module); exit 2
}
. $module

if (Test-Path -LiteralPath $WorkRoot) { Remove-Item -LiteralPath $WorkRoot -Recurse -Force }
$null = New-Item -ItemType Directory -Path $WorkRoot -Force

$script:results = New-Object System.Collections.ArrayList
$script:started = @{}     # key -> record, everything this script launched

function Say($m) {
  Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss.fff"), $m)
}
function Leg($name, $ok, $detail) {
  $null = $script:results.Add([pscustomobject]@{ Leg = $name; Ok = [bool]$ok; Detail = $detail })
  $tag = "FAIL"
  if ($ok) { $tag = "PASS" }
  Say ("  " + $tag + "  " + $name + " : " + $detail)
}

# ---------------------------------------------------------------- fixtures
#
# The shape mimics the watcher exactly: cmd.exe /c <long-lived child>, and the
# child spawns its own child, because `claude` spawns node and the watcher's
# kill has to reach through both.
#
#   NORMAL  cmd.exe -> child.ps1 -> grandchild.ps1      (all three long-lived)
#   ORPHAN  cmd.exe -> child.ps1 -> mid.ps1 -> grandchild.ps1
#           where mid.ps1 EXITS after a few seconds, so the grandchild's live
#           parent link is broken and taskkill /T cannot reach it.

$childPs1 = Join-Path $WorkRoot "child.ps1"
Set-Content -LiteralPath $childPs1 -Encoding ASCII -Value @'
param([string]$Root, [string]$Mode)
$me = Join-Path $Root ("alive-child-" + $PID + ".txt")
if ($Mode -eq "orphan") {
  Start-Process -FilePath "powershell" -ArgumentList @(
    "-NoProfile","-ExecutionPolicy","Bypass","-File",(Join-Path $Root "mid.ps1"),
    "-Root",$Root) -WindowStyle Hidden | Out-Null
} else {
  Start-Process -FilePath "powershell" -ArgumentList @(
    "-NoProfile","-ExecutionPolicy","Bypass","-File",(Join-Path $Root "grandchild.ps1"),
    "-Root",$Root) -WindowStyle Hidden | Out-Null
}
while ($true) {
  Set-Content -LiteralPath $me -Value ((Get-Date).ToString("o")) -Encoding ASCII
  Start-Sleep -Milliseconds 400
}
'@

$midPs1 = Join-Path $WorkRoot "mid.ps1"
Set-Content -LiteralPath $midPs1 -Encoding ASCII -Value @'
param([string]$Root)
Start-Process -FilePath "powershell" -ArgumentList @(
  "-NoProfile","-ExecutionPolicy","Bypass","-File",(Join-Path $Root "grandchild.ps1"),
  "-Root",$Root) -WindowStyle Hidden | Out-Null
Set-Content -LiteralPath (Join-Path $Root ("alive-mid-" + $PID + ".txt")) -Value "up" -Encoding ASCII
# Alive long enough for the test to sample the tree while the links are intact,
# then gone - which is what orphans the grandchild.
Start-Sleep -Seconds 6
exit 0
'@

$grandPs1 = Join-Path $WorkRoot "grandchild.ps1"
Set-Content -LiteralPath $grandPs1 -Encoding ASCII -Value @'
param([string]$Root)
$me = Join-Path $Root ("alive-grandchild-" + $PID + ".txt")
while ($true) {
  Set-Content -LiteralPath $me -Value ((Get-Date).ToString("o")) -Encoding ASCII
  Start-Sleep -Milliseconds 400
}
'@

# Start a fixture and return the cmd.exe wrapper's process object.
function Start-Fixture([string]$Mode) {
  $args_ = '/c powershell -NoProfile -ExecutionPolicy Bypass -File "' + $childPs1 +
           '" -Root "' + $WorkRoot + '" -Mode ' + $Mode
  $p = Start-Process -FilePath "cmd.exe" -ArgumentList $args_ -WindowStyle Hidden -PassThru
  $null = $p.Handle
  return $p
}

# Wait until the fixture tree has at least $n members, or give up.
function Wait-Tree([int]$RootPid, [int]$n, [int]$timeoutSeconds = 25) {
  $deadline = (Get-Date).AddSeconds($timeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    $t = Get-LaneProcTable
    $d = Get-LaneDescendants -Table $t -RootPid $RootPid -SelfPid $PID
    if ($null -ne $d -and $d.Count -ge $n) {
      foreach ($k in $d.Keys) { $script:started[$k] = $d[$k] }
      return $d
    }
    Start-Sleep -Milliseconds 400
  }
  return $null
}

# Identity-matched liveness: a pid whose creation time no longer matches is a
# different process and counts as GONE.
function Get-StillAlive($records) {
  $now  = Get-LaneProcTable
  $out  = @()
  foreach ($r in @($records)) {
    $p = [int]$r.Pid
    if ($now.ContainsKey($p) -and $now[$p].Key -eq $r.Key) { $out += $r }
  }
  return ,@($out)
}

function Show($records) {
  $a = @($records)
  if ($a.Count -eq 0) { return "(none)" }
  return (($a | Sort-Object Pid | ForEach-Object { "" + $_.Pid + ":" + $_.Name }) -join " ")
}

# Last-resort cleanup for anything this script started. Identity-matched, never
# by name or command line.
function Remove-Fixtures {
  $now = Get-LaneProcTable
  $self = Get-LaneSelfChain -Table $now -FromPid $PID
  foreach ($k in @($script:started.Keys)) {
    $r = $script:started[$k]
    $p = [int]$r.Pid
    if ($self.ContainsKey($p)) { continue }
    if (-not $now.ContainsKey($p)) { continue }
    if ($now[$p].Key -ne $r.Key) { continue }
    try { Stop-Process -Id $p -Force -ErrorAction Stop; Say ("cleanup: stopped leftover fixture pid " + $p) } catch { }
  }
}

Say ("module : " + $module)
Say ("sha256 : " + (Get-FileHash -LiteralPath $module -Algorithm SHA256).Hash)
Say ("work   : " + $WorkRoot)
Say ("self   : pid " + $PID + "  chain " + (Format-LaneChain -Chain (Get-LaneSelfChain -Table (Get-LaneProcTable) -FromPid $PID)))
Say ""

try {

# =========================================================== LEG A (control)
Say "LEG A - Stop-Process -Force on the cmd.exe wrapper (the behaviour being replaced)"
$pA   = Start-Fixture "normal"
$treeA = Wait-Tree $pA.Id 3
if ($null -eq $treeA) {
  Leg "A" $false "fixture never reached 3 processes; cannot run the control"
} else {
  $recA = @($treeA.Values)
  Say ("  before: " + (Show $recA))
  Stop-Process -Id $pA.Id -Force
  Start-Sleep -Seconds 4
  $aliveA = Get-StillAlive $recA
  Say ("  after : " + (Show $aliveA))
  $rootGoneA = -not (Get-LaneProcTable).ContainsKey($pA.Id)
  Leg "A" (($aliveA.Count -gt 0) -and $rootGoneA) (
    "wrapper " + $pA.Id + " gone=" + $rootGoneA + ", but " + $aliveA.Count +
    " of " + $recA.Count + " survived: " + (Show $aliveA) +
    " -- Stop-Process -Force orphans the task")
  foreach ($r in @($aliveA)) { try { Stop-Process -Id ([int]$r.Pid) -Force } catch { } }
  Start-Sleep -Seconds 1
}
Say ""

# =========================================================== LEG B
Say "LEG B - Stop-LaneProcessTree on the same shape"
$pB    = Start-Fixture "normal"
$treeB = Wait-Tree $pB.Id 3
if ($null -eq $treeB) {
  Leg "B" $false "fixture never reached 3 processes"
} else {
  $recB = @($treeB.Values)
  Say ("  before: " + (Show $recB))
  $rB = Stop-LaneProcessTree -RootPid $pB.Id -Say { param($m) Say ("    " + $m) }
  Start-Sleep -Seconds 1
  $aliveB = Get-StillAlive $recB
  Say ("  after : " + (Show $aliveB))
  # THE SECOND HALF OF THIS LEG EXISTS BECAUSE MUTATION M1 DID NOT GO RED.
  # Measured 2026-10-15 21:58: with /T dropped from the taskkill call, "nothing
  # survived" was STILL true, because the sweep kills the leftovers one by one.
  # That is a true and reassuring fact about the sweep, and it meant the leg was
  # not testing /T at all. So the leg now also asserts that the single taskkill
  # call reported more than one pid - which only /T can do - and the mutation
  # turns it red for the intended reason.
  $tkPids = @($rB.Taskkill | Where-Object { $_ -notmatch 'ERROR' -and $_ -match '[0-9][0-9]' })
  Leg "B" (($rB.Verified) -and ($aliveB.Count -eq 0) -and ($rB.After.Count -eq 0) -and
           (-not $rB.Refused) -and ($tkPids.Count -ge 2)) (
    "before=[" + ($rB.Before -join ",") + "] after=[" + ($rB.After -join ",") +
    "] Verified=" + $rB.Verified + "; independent re-measure says " +
    $aliveB.Count + " alive; one taskkill call reported " + $tkPids.Count +
    " pid(s), which needs /T (>=2 required)")
}
Say ""

# =========================================================== LEG C1 (control)
Say "LEG C1 - bare taskkill /T /F against an ORPHANED grandchild"
$pC1 = Start-Fixture "orphan"
$treeC1 = Wait-Tree $pC1.Id 4
if ($null -eq $treeC1) {
  Leg "C1" $false "orphan fixture never reached 4 processes (cmd/child/mid/grandchild)"
} else {
  $recC1 = @($treeC1.Values)
  Say ("  sampled while links intact: " + (Show $recC1))
  Say "  waiting for mid.ps1 to exit, which orphans the grandchild..."
  Start-Sleep -Seconds 8
  $t = Get-LaneProcTable
  $visible = Get-LaneDescendants -Table $t -RootPid $pC1.Id -SelfPid $PID
  Say ("  visible below the root NOW: " + (Show @($visible.Values)) + "  (the orphan is not in it)")
  $eap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
  $null = & taskkill.exe /PID $pC1.Id /T /F 2>&1
  $ErrorActionPreference = $eap
  Start-Sleep -Seconds 4
  $aliveC1 = Get-StillAlive $recC1
  Say ("  after bare taskkill /T /F: " + (Show $aliveC1))
  Leg "C1" ($aliveC1.Count -gt 0) (
    "" + $aliveC1.Count + " of " + $recC1.Count + " survived a /T kill: " + (Show $aliveC1) +
    " -- /T walks LIVE parent links, so an orphan is invisible to it")
  foreach ($r in @($aliveC1)) { try { Stop-Process -Id ([int]$r.Pid) -Force } catch { } }
  Start-Sleep -Seconds 1
}
Say ""

# =========================================================== LEG C2
Say "LEG C2 - Stop-LaneProcessTree WITH the accumulated sample, same orphan shape"
$pC2 = Start-Fixture "orphan"
$treeC2 = Wait-Tree $pC2.Id 4
if ($null -eq $treeC2) {
  Leg "C2" $false "orphan fixture never reached 4 processes"
} else {
  $accC2 = @{}
  foreach ($k in $treeC2.Keys) { $accC2[$k] = $treeC2[$k] }
  $recC2 = @($treeC2.Values)
  Say ("  accumulated while links intact: " + (Show $recC2))
  Say "  waiting for mid.ps1 to exit..."
  Start-Sleep -Seconds 8
  $rC2 = Stop-LaneProcessTree -RootPid $pC2.Id -Accumulated $accC2 -Say { param($m) Say ("    " + $m) }
  Start-Sleep -Seconds 1
  $aliveC2 = Get-StillAlive $recC2
  Say ("  after : " + (Show $aliveC2))
  Leg "C2" (($rC2.Verified) -and ($aliveC2.Count -eq 0)) (
    "before=[" + ($rC2.Before -join ",") + "] after=[" + ($rC2.After -join ",") +
    "] Verified=" + $rC2.Verified + "; independent re-measure says " +
    $aliveC2.Count + " alive")
}
Say ""

# =========================================================== LEG D1
Say "LEG D1 - a root that is the caller, or an ancestor of the caller, is REFUSED"
$tD   = Get-LaneProcTable
$myPpid = 0
if ($tD.ContainsKey($PID)) { $myPpid = $tD[$PID].Ppid }

$dSelf = Get-LaneDescendants -Table $tD -RootPid $PID -SelfPid $PID
$dAnc  = $null
$ancTested = $false
if ($myPpid -gt 0 -and $tD.ContainsKey($myPpid)) {
  $dAnc = Get-LaneDescendants -Table $tD -RootPid $myPpid -SelfPid $PID
  $ancTested = $true
}
$rD = Stop-LaneProcessTree -RootPid $PID -Say { param($m) Say ("    " + $m) }
$iAmStillHere = (Get-LaneProcTable).ContainsKey($PID)

$okD1 = ($null -eq $dSelf) -and $rD.Refused -and ($rD.Before.Count -eq 0) -and
        (-not $rD.Verified) -and $iAmStillHere
if ($ancTested) { $okD1 = $okD1 -and ($null -eq $dAnc) }
Leg "D1" $okD1 (
  "Get-LaneDescendants(root=self " + $PID + ")=" + $(if ($null -eq $dSelf) { "REFUSED(null)" } else { "RETURNED " + $dSelf.Count }) +
  "; (root=parent " + $myPpid + ")=" + $(if (-not $ancTested) { "n/a" } elseif ($null -eq $dAnc) { "REFUSED(null)" } else { "RETURNED " + $dAnc.Count }) +
  "; Stop-LaneProcessTree.Refused=" + $rD.Refused + " Before=[" + ($rD.Before -join ",") +
  "]; this shell alive after=" + $iAmStillHere)
Say ""

# =========================================================== LEG D2
Say "LEG D2 - a CommandLine substring filter matches itself; pid ancestry does not"
# This script's own command line contains the path of this script, so any
# substring filter built from that path matches THIS process. That is the
# 2026-10-15 defect, reproduced here against this very shell.
$needle = Split-Path -Leaf $MyInvocation.MyCommand.Path
$substringHits = @(Get-CimInstance -ClassName Win32_Process |
                   Where-Object { $_.CommandLine -and $_.CommandLine -like ("*" + $needle + "*") } |
                   ForEach-Object { [int]$_.ProcessId })
$filterMatchedItself = ($substringHits -contains $PID)

# Now the guard: a fixture root, selected by ancestry, never yields this shell.
$pD = Start-Fixture "normal"
$treeD = Wait-Tree $pD.Id 2
$ancestryHits = @()
if ($null -ne $treeD) { $ancestryHits = @($treeD.Values | ForEach-Object { [int]$_.Pid }) }
$ancestryIncludedSelf = ($ancestryHits -contains $PID)
$rD2 = Stop-LaneProcessTree -RootPid $pD.Id -Say { param($m) Say ("    " + $m) }
$selfKilled = -not (Get-LaneProcTable).ContainsKey($PID)

Leg "D2" ($filterMatchedItself -and (-not $ancestryIncludedSelf) -and (-not $selfKilled) -and $rD2.Verified) (
  "substring filter on '" + $needle + "' matched " + $substringHits.Count +
  " process(es) INCLUDING THIS ONE (" + $PID + ")=" + $filterMatchedItself +
  "; pid-ancestry set for root " + $pD.Id + " was [" + ($ancestryHits -join ",") +
  "], contains self=" + $ancestryIncludedSelf + "; after the kill this shell is alive=" + (-not $selfKilled))
Say ""

# =========================================================== LEG E
Say "LEG E - an accumulated entry whose pid is alive but whose identity does not match is NOT killed"
$pE = Start-Fixture "normal"
$treeE = Wait-Tree $pE.Id 3
$pBystander = Start-Fixture "normal"
$treeBy = Wait-Tree $pBystander.Id 2
if ($null -eq $treeE -or $null -eq $treeBy) {
  Leg "E" $false "fixtures did not come up"
} else {
  $recE = @($treeE.Values)
  # Forge a recycled-pid record: the BYSTANDER's live pid carrying a creation
  # time that is not its own. A correct sweep must leave it alone.
  $byRec   = @($treeBy.Values)[0]
  $forged  = [pscustomobject]@{
    Pid     = $byRec.Pid
    Ppid    = $byRec.Ppid
    Name    = $byRec.Name
    Created = $byRec.Created
    Key     = (Get-LaneProcKey -ProcPid $byRec.Pid -Created ($byRec.Created).AddSeconds(-999))
  }
  $accE = @{}
  foreach ($k in $treeE.Keys) { $accE[$k] = $treeE[$k] }
  $accE[$forged.Key] = $forged
  Say ("  bystander pid " + $byRec.Pid + " (" + $byRec.Name + ") injected with a WRONG creation time")
  $rE = Stop-LaneProcessTree -RootPid $pE.Id -Accumulated $accE -Say { param($m) Say ("    " + $m) }
  Start-Sleep -Seconds 1
  $byStillAlive = @(Get-StillAlive @($byRec)).Count -eq 1
  $aliveE = Get-StillAlive $recE
  Leg "E" ($byStillAlive -and ($aliveE.Count -eq 0) -and ($rE.Before -notcontains $byRec.Pid)) (
    "bystander " + $byRec.Pid + " alive after=" + $byStillAlive +
    "; it was " + $(if ($rE.Before -contains $byRec.Pid) { "WRONGLY IN" } else { "correctly absent from" }) +
    " the kill set [" + ($rE.Before -join ",") + "]; target tree survivors=" + $aliveE.Count)
}
Say ""

# =========================================================== LEG F
Say "LEG F - the upward walk stops at a reused parent slot (synthetic table)"
$t0 = Get-Date "2026-01-01T00:00:00"
function New-FakeRow([int]$ProcPid, [int]$Ppid, $Created) {
  return [pscustomobject]@{
    Pid = $ProcPid; Ppid = $Ppid; Name = ("fake-" + $ProcPid); Created = $Created
    Key = (Get-LaneProcKey -ProcPid $ProcPid -Created $Created)
  }
}
# 100's recorded parent is 200, but 200 was created AFTER 100, so that pid slot
# was recycled and 100's real parent is gone. The walk must stop at 100.
$reused = @{
  100 = (New-FakeRow 100 200 $t0.AddSeconds(30))
  200 = (New-FakeRow 200 300 $t0.AddSeconds(60))
  300 = (New-FakeRow 300 0   $t0)
}
# Same shape with a credible ancestry: every parent older than its child.
$sane = @{
  100 = (New-FakeRow 100 200 $t0.AddSeconds(60))
  200 = (New-FakeRow 200 300 $t0.AddSeconds(30))
  300 = (New-FakeRow 300 0   $t0)
}
$chainReused = Get-LaneSelfChain -Table $reused -FromPid 100
$chainSane   = Get-LaneSelfChain -Table $sane   -FromPid 100
$okF = ($chainReused.Count -eq 1) -and $chainReused.ContainsKey(100) -and
       ($chainSane.Count -eq 3) -and $chainSane.ContainsKey(200) -and $chainSane.ContainsKey(300)
Leg "F" $okF (
  "reused-slot table -> chain [" + (Format-LaneChain -Chain $chainReused) +
  "] (must be 100 alone); credible table -> chain [" +
  (Format-LaneChain -Chain $chainSane) + "] (must be 100 <- 200 <- 300)")
Say ""

} finally {
  Remove-Fixtures
  if (-not $KeepFixtures) {
    try { Remove-Item -LiteralPath $WorkRoot -Recurse -Force -ErrorAction SilentlyContinue } catch { }
  }
}

# ------------------------------------------------------------------ verdict
Say "================================================================"
$fail = @($script:results | Where-Object { -not $_.Ok })
foreach ($r in $script:results) {
  $tag = "FAIL"
  if ($r.Ok) { $tag = "PASS" }
  Say ($tag + "  " + $r.Leg)
}
Say ("legs: " + $script:results.Count + "  passed: " + ($script:results.Count - $fail.Count) + "  failed: " + $fail.Count)
if ($fail.Count -gt 0) { Say "RESULT: FAIL"; exit 1 }
Say "RESULT: PASS"
exit 0
