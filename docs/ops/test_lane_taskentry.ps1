<#
  test_lane_taskentry.ps1 - the already-recorded matcher, and the watcher that
  uses it, exercised end to end.

  ASCII ONLY. Same reason as the files it tests.

  WHAT IT TESTS AGAINST, AND WHAT IT CANNOT.

  qwen/0171 recorded that the PowerShell test proving LANE_DEADLINE reaches a
  child HAS NEVER BEEN OBSERVED TO RUN, because running it starts a watcher.
  The same constraint binds here and it is honoured the same way: the
  end-to-end leg runs a BYTE COPY of this repository's lane_watcher.ps1,
  inside a scratch $Ops under %TEMP%, on a lane called "tetest" which is not a
  lane, with the dispatch stubbed to a script that copies its brief and exits.
  No `claude` is invoked, no real queue is read, no real lane file is written,
  and the seven live watchers are neither read nor signalled.

  SO, PLAINLY: what is proven here is proven ON A COPY. What remains
  unobserved on the live watchers is everything about the live watchers - they
  are running lane_watcher.ps1 as deployed at
  C:\Users\Zvonimir\Desktop\resonate-ops\tools, which is the 2026-10-15 22:20
  version and does not contain this change at all. Adopting it is a restart,
  and a restart is the operator's.

  THE UNIT LEGS DO READ A REAL LANE FILE - LANE-glm-c.md - and only read it.
  That is deliberate: a matcher measured solely against fixtures written beside
  it is a matcher measured against its author's idea of the data.
#>
param(
  [string]$Module  = (Join-Path $PSScriptRoot "lane_taskentry.ps1"),
  [string]$Watcher = (Join-Path $PSScriptRoot "lane_watcher.ps1"),
  [string]$Ops     = "C:\Users\Zvonimir\Desktop\resonate-ops",
  [string]$Lane    = "tetest",
  [switch]$SkipEndToEnd,
  [switch]$KeepScratch
)
$ErrorActionPreference = "Stop"

$RealLanes = @("glm", "glm-b", "glm-c", "pilotcaps", "qwen", "suppression", "webapp")
if ($RealLanes -contains $Lane) { Write-Host ("REFUSING: '" + $Lane + "' is a real lane."); exit 2 }

$script:fails  = New-Object System.Collections.ArrayList
$script:passes = 0
function Check($name, $ok, $detail) {
  if ($ok) { $script:passes++; Write-Host ("  PASS  " + $name + "   " + $detail) }
  else { [void]$script:fails.Add($name); Write-Host ("  FAIL  " + $name + "   " + $detail) }
}

function SafeRead($path) {
  # THE LOG IS BEING WRITTEN WHILE THIS READS IT. Get-Content takes a share
  # mode that excludes the watcher's own Add-Content, so under
  # $ErrorActionPreference = "Stop" a poll that lands in the same instant as a
  # log line ENDS THE HARNESS. Measured on this harness's second run, 14:01:52.
  # Opened with FileShare.ReadWrite instead, and an unreadable moment is "" -
  # which is safe here because every caller is polling and will look again.
  if (-not (Test-Path -LiteralPath $path)) { return "" }
  try {
    $fs = [System.IO.File]::Open($path, 'Open', 'Read', 'ReadWrite')
    try {
      $sr = New-Object System.IO.StreamReader($fs)
      return $sr.ReadToEnd()
    } finally { $fs.Dispose() }
  } catch { return "" }
}

if (-not (Test-Path -LiteralPath $Module)) { Write-Host ("MISSING: " + $Module); exit 2 }
. $Module

Write-Host ""
Write-Host "=== lane_taskentry ========================================================="
Write-Host ("module    " + $Module)
Write-Host ("watcher   " + $Watcher)
Write-Host ""

# ------------------------------------------------------------- unit legs
$glmc = Join-Path $Ops "LANE-glm-c.md"
if (-not (Test-Path -LiteralPath $glmc)) { Write-Host ("PRECONDITION UNMET: " + $glmc); exit 2 }

# U1 / control C1a. The task brief names this location, so the assertion is on
# the LINE NUMBER and not merely on the state. A matcher that says MATCH and
# cannot say where is not auditable.
$u1 = Find-LaneTaskEntry -LaneFile $glmc -TaskId "0240"
Check "U1 known entry MATCH" (($u1.State -eq "MATCH") -and ($u1.Line -eq 2263)) `
      ("state=" + $u1.State + " line=" + $u1.Line + " n=" + $u1.Count)

# U2 / control C1b. An invented number.
$u2 = Find-LaneTaskEntry -LaneFile $glmc -TaskId "9987"
Check "U2 invented id NO_MATCH" ($u2.State -eq "NO_MATCH") ("state=" + $u2.State + " line=" + $u2.Line)

# U3. A missing authority is UNKNOWN, never NO_MATCH.
$u3 = Find-LaneTaskEntry -LaneFile (Join-Path $env:TEMP "no-such-LANE-file.md") -TaskId "0240"
Check "U3 missing lane file UNKNOWN" ($u3.State -eq "UNKNOWN") ("state=" + $u3.State + " why=" + $u3.Why)

# U4. An UNREADABLE authority is UNKNOWN. Held open with FileShare.None so the
# read genuinely throws; a permission change would not, on Windows, for this
# account.
$lockPath = Join-Path $env:TEMP ("lane-locked-" + [guid]::NewGuid().ToString("N").Substring(0,8) + ".md")
Set-Content -LiteralPath $lockPath -Value "## 2026-10-16 - TASK 0240 - done" -Encoding ASCII
$fs = [System.IO.File]::Open($lockPath, 'Open', 'Read', 'None')
try {
  $u4 = Find-LaneTaskEntry -LaneFile $lockPath -TaskId "0240"
  Check "U4 unreadable lane file UNKNOWN" ($u4.State -eq "UNKNOWN") ("state=" + $u4.State + " why=" + $u4.Why)
} finally { $fs.Close(); $fs.Dispose(); Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue }

# U5 / U6. The strict id extractor, including what it correctly REFUSES.
$ids = @{}
foreach ($n in @("0240-the-attach.md", "0162c-rescue.md", "notanid.md",
                 "20261016-091652-TIMEOUT-0220-x.md")) { $ids[$n] = Get-LaneBriefTaskId -BriefName $n }
Check "U5 id from a queue filename" ($ids["0240-the-attach.md"] -eq "0240") ("-> " + $ids["0240-the-attach.md"])
Check "U6 suffixed and archive names refused" `
      (($null -eq $ids["0162c-rescue.md"]) -and ($null -eq $ids["notanid.md"]) -and
       ($null -eq $ids["20261016-091652-TIMEOUT-0220-x.md"])) `
      "0162c / notanid / a DONE-stamped name all come back null -> UNKNOWN -> dispatch"

# U7. The save sweep exception.
Check "U7 save sweep recognised" `
      ((Test-LaneSaveSweep -BriefName "0161-save-sweep.md") -and
       -not (Test-LaneSaveSweep -BriefName "0240-the-attach.md")) "sweep=True / False"

# U8. THE FORWARD POINTER. LANE-glm-c.md:370 reads
#     NEXT: TASK 0040 (`queue/glm-c/0040-canary-approval-sheet.md`).
# which points at work NOT YET DONE. Any-line matching convicts on it.
$fx = Join-Path $env:TEMP ("lane-fx-" + [guid]::NewGuid().ToString("N").Substring(0,8) + ".md")
@(
  "# LANE - fixture",
  "",
  "NEXT: TASK 0040 (queue/glm-c/0040-canary-approval-sheet.md).",
  "",
  "Some prose that mentions TASK 0041 halfway through the sentence.",
  ""
) | Set-Content -LiteralPath $fx -Encoding ASCII
$u8  = Find-LaneTaskEntry -LaneFile $fx -TaskId "0040"
$u8b = Find-LaneTaskEntry -LaneFile $fx -TaskId "0041"
Check "U8 forward pointer is NOT an entry" `
      (($u8.State -eq "NO_MATCH") -and ($u8b.State -eq "NO_MATCH")) `
      ("NEXT: -> " + $u8.State + " ; mid-sentence -> " + $u8b.State)

# U9. THE SHAPE THE HEADING ANCHOR MISSED. glm-c records entries as plain
# dated paragraphs at column zero; eleven of its entries look like this.
@(
  "# LANE - fixture",
  "",
  "2026-10-15 - TASK 0040 - DEPENDENCY UNMET, STOPPED BEFORE GENERATING: the",
  "four approved trims are not in this worktree.",
  "",
  "## 2026-10-16 - TASK 0220 (GLM-C): the remaining bypasses, tiered",
  "",
  "- 2026-10-15 - TASK 0080 - GATE UNMET, STOPPED BEFORE GENERATING",
  ""
) | Set-Content -LiteralPath $fx -Encoding ASCII
$u9a = Find-LaneTaskEntry -LaneFile $fx -TaskId "0040"
$u9b = Find-LaneTaskEntry -LaneFile $fx -TaskId "0220"
$u9c = Find-LaneTaskEntry -LaneFile $fx -TaskId "0080"
Check "U9 dated paragraph, heading and bullet all match" `
      (($u9a.State -eq "MATCH") -and ($u9b.State -eq "MATCH") -and ($u9c.State -eq "MATCH")) `
      ("0040 L" + $u9a.Line + " / 0220 L" + $u9b.Line + " / 0080 L" + $u9c.Line)

# U10. The number boundary, in both directions.
@(
  "## 2026-10-16 - TASK 02200 - a five digit id",
  "## 2026-10-16 - TASK-0221 - hyphen separator",
  "## 2026-10-16 - TASK 222 - unpadded"
) | Set-Content -LiteralPath $fx -Encoding ASCII
$u10a = Find-LaneTaskEntry -LaneFile $fx -TaskId "0220"
$u10b = Find-LaneTaskEntry -LaneFile $fx -TaskId "0221"
$u10c = Find-LaneTaskEntry -LaneFile $fx -TaskId "0222"
Check "U10 digit boundary and separators" `
      (($u10a.State -eq "NO_MATCH") -and ($u10b.State -eq "MATCH") -and ($u10c.State -eq "MATCH")) `
      ("02200 vs 0220 -> " + $u10a.State + " ; TASK-0221 -> " + $u10b.State + " ; TASK 222 -> " + $u10c.State)
Remove-Item -LiteralPath $fx -Force -ErrorAction SilentlyContinue

# U11. The note writer: appends, reads back, and leaves what was there.
$brief = Join-Path $env:TEMP ("brief-" + [guid]::NewGuid().ToString("N").Substring(0,8) + ".md")
Set-Content -LiteralPath $brief -Value "# TASK 0240 brief body" -Encoding UTF8
$w = Write-LaneAlreadyRecordedNote -RunPath $brief -Lane "glm-c" -TaskId "0240" `
                                   -Hit @{ Line = 2263; Count = 1; Text = "## 2026-10-16 - TASK 0240" }
$after = [System.IO.File]::ReadAllText($brief)
Check "U11 note appended and read back" `
      ($w.Ok -and $after.Contains("WATCHER NOTE, APPENDED AT DISPATCH") -and
       $after.Contains("LANE-glm-c.md:2263") -and $after.Contains("# TASK 0240 brief body")) `
      ("ok=" + $w.Ok + " bytes=" + $after.Length)
Remove-Item -LiteralPath $brief -Force -ErrorAction SilentlyContinue

# U12. It never throws. A failed note must degrade to "no annotation".
$w2 = Write-LaneAlreadyRecordedNote -RunPath (Join-Path $env:TEMP "no-such-brief-xyz.md") `
        -Lane "glm-c" -TaskId "0240" -Hit @{ Line = 1; Count = 1; Text = "x" }
Check "U12 missing brief degrades, no throw" ((-not $w2.Ok) -and ($w2.Why -ne "")) ("why=" + $w2.Why)

# ------------------------------------------------------- end to end
if (-not $SkipEndToEnd) {
  if (-not (Test-Path -LiteralPath $Watcher)) { Write-Host ("MISSING: " + $Watcher); exit 2 }
  if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Host "PRECONDITION UNMET: the watcher refuses to start without claude on PATH."
    Write-Host "Unrelated to what this measures, but it blocks it."
    exit 2
  }

  $Root = Join-Path $env:TEMP ("lane-te-" + [guid]::NewGuid().ToString("N").Substring(0,12))
  $SOps = Join-Path $Root "ops"
  $Wt   = Join-Path $Root "wt"
  $Cap  = Join-Path $Root "captured"
  $Q    = Join-Path $SOps ("queue\" + $Lane)
  $LogD = Join-Path $SOps "logs"
  $WLog = Join-Path $LogD ("watcher-" + $Lane + ".log")
  $LF   = Join-Path $SOps ("LANE-" + $Lane + ".md")
  if ($SOps.TrimEnd('\') -ieq $Ops.TrimEnd('\')) { Write-Host "REFUSING: scratch resolved to the live ops."; exit 2 }
  foreach ($d in @($Q, (Join-Path $Q "DONE"), (Join-Path $Q "RUNNING"), $LogD, $Cap,
                   (Join-Path $SOps "tools"), (Join-Path $Wt ".git"))) {
    New-Item -ItemType Directory -Path $d -Force | Out-Null
  }

  # A BYTE COPY of the watcher, so that what ran is a file this harness owns
  # and the repository's copy cannot be disturbed by the run.
  $WCopy = Join-Path $SOps "tools\lane_watcher_COPY.ps1"
  Copy-Item -LiteralPath $Watcher -Destination $WCopy -Force
  foreach ($m in @("lane_treekill.ps1", "lane_refusal.ps1", "lane_orphan.ps1")) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $m) -Destination (Join-Path $SOps "tools") -Force
  }

  # The scratch lane file carries an entry for 0300 and nothing for 0310.
  @(
    ("# LANE - " + $Lane),
    "",
    "## 2026-10-16 - TASK 0300 - already done, commit deadbeef",
    "",
    "Body of the 0300 entry.",
    ""
  ) | Set-Content -LiteralPath $LF -Encoding UTF8

  # THE STUBBED DISPATCH. It copies the brief EXACTLY AS THE SESSION WOULD
  # RECEIVE IT - the annotated RUNNING copy - and grows the lane file so the
  # NOWORK guard does not count these as failures and stop the watcher at three.
  $stub = Join-Path $SOps "tools\stub_task.ps1"
  $stubBody = @(
    'param([string]$BriefPath, [string]$CaptureDir, [string]$LaneFile)',
    'Copy-Item -LiteralPath $BriefPath -Destination (Join-Path $CaptureDir (Split-Path -Leaf $BriefPath)) -Force',
    'Add-Content -LiteralPath $LaneFile -Value ("ran " + (Split-Path -Leaf $BriefPath)) -Encoding UTF8',
    'exit 0'
  ) -join "`r`n"
  Set-Content -LiteralPath $stub -Value $stubBody -Encoding ASCII

  function SBrief($name, $body) {
    $t = @(("# " + $name), "", $body) -join "`r`n"
    Set-Content -LiteralPath (Join-Path $Q $name) -Value $t -Encoding UTF8
  }
  SBrief "0300-already-done.md"  "This one has an entry in the scratch lane file."
  SBrief "0310-never-done.md"    "This one does not."
  SBrief "0320-save-sweep.md"    "A sweep. Never annotated, even with an entry."
  # The sweep's number DOES have an entry, so the only thing that can suppress
  # its note is the sweep rule itself.
  Add-Content -LiteralPath $LF -Value "## 2026-10-16 - TASK 0320 - swept before" -Encoding UTF8

  $tmpl = '/c powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + $stub +
          '" -BriefPath "{BRIEF}" -CaptureDir "' + $Cap + '" -LaneFile "' + $LF +
          '" < "{BRIEF}" > "{OUT}" 2>&1'

  # A LAUNCHER FILE, NOT -ArgumentList. test_lane_watcher_endtoend.ps1 measured
  # why on 2026-10-15: Start-Process wraps an array element containing spaces in
  # double quotes, and this template contains its own quotes around {BRIEF} and
  # {OUT}, which terminate that wrapper early. The first run of THIS harness hit
  # the same thing from the other end - the template split on spaces and
  # "powershell.exe" bound positionally to -PermissionMode, which refused it by
  # ValidateSet. A single-quoted PowerShell literal in a file is re-parsed by
  # nothing.
  $launcher = Join-Path $Root "run-watcher.ps1"
  # SPLATTED, so nothing in this file needs a line-continuation backtick and
  # nothing re-parses the template. Every value is a single-quoted PowerShell
  # literal with its own quotes doubled.
  $lt = @(
    '$p = @{',
    ("  Lane                = '" + $Lane + "'"),
    ("  Worktree            = '" + $Wt + "'"),
    ("  Ops                 = '" + $SOps + "'"),
    ("  TreeKillPath        = '" + (Join-Path $SOps "tools\lane_treekill.ps1") + "'"),
    ("  RefusalModulePath   = '" + (Join-Path $SOps "tools\lane_refusal.ps1") + "'"),
    ("  OrphanModulePath    = '" + (Join-Path $SOps "tools\lane_orphan.ps1") + "'"),
    ("  TaskEntryModulePath = '" + $Module + "'"),
    ("  TaskCommandTemplate = '" + $tmpl.Replace("'", "''") + "'"),
    '  TaskTimeoutMinutes  = 1',
    '  TreeSampleSeconds   = 5',
    '  IdleSleepSeconds    = 2',
    "  PermissionMode      = 'default'",
    '}',
    ('& "' + $WCopy + '" @p')
  ) -join "`r`n"
  Set-Content -LiteralPath $launcher -Value $lt -Encoding ASCII

  $wp = Start-Process -FilePath "powershell.exe" -NoNewWindow -PassThru -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $launcher)
  $null = $wp.Handle
  Write-Host ("  ... watcher copy running as pid " + $wp.Id + ", scratch " + $Root)

  # FAIL FAST, for the reason the sibling harness records: a watcher that died
  # at startup otherwise leaves this grinding through a three-minute wait and
  # the run reads as slow rather than as broken.
  $upEnd = (Get-Date).AddSeconds(30)
  $up = $false
  while ((Get-Date) -lt $upEnd) {
    if ((SafeRead $WLog) -match 'watcher up\.') { $up = $true; break }
    Start-Sleep -Milliseconds 300
  }
  Check "E0 the watcher copy started" $up "banner in the scratch log"
  if (-not $up) {
    Write-Host "ABORTING the end-to-end legs: the watcher never came up."
    (SafeRead $WLog) -split "`n" | Select-Object -Last 20 | ForEach-Object { Write-Host ("    " + $_) }
    if (-not $wp.HasExited) { Stop-Process -Id $wp.Id -Force -ErrorAction SilentlyContinue }
    Write-Host ""
    Write-Host ("PASS " + $script:passes + "   FAIL " + $script:fails.Count)
    exit 1
  }

  $end = (Get-Date).AddSeconds(180)
  while ((Get-Date) -lt $end) {
    if ((SafeRead $WLog) -match 'DONE\s+0320-save-sweep\.md') { break }
    if (-not (Get-Process -Id $wp.Id -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Milliseconds 500
  }
  Set-Content -LiteralPath (Join-Path $SOps ("STOP-" + $Lane)) -Value "stop" -Encoding ASCII
  $null = $wp.WaitForExit(30000)
  if (-not $wp.HasExited) { Stop-Process -Id $wp.Id -Force -ErrorAction SilentlyContinue }

  $log = SafeRead $WLog
  function CapText($n) {
    $p = Join-Path $Cap $n
    if (Test-Path -LiteralPath $p) { return [System.IO.File]::ReadAllText($p) }
    return ""
  }
  $c300 = CapText "0300-already-done.md"
  $c310 = CapText "0310-never-done.md"
  $c320 = CapText "0320-save-sweep.md"

  Check "E1 already-recorded logged and brief annotated" `
        (($log -match ('ALREADY RECORDED: TASK 0300 -> LANE-' + [regex]::Escape($Lane) + '\.md:3')) -and
         $c300.Contains("WATCHER NOTE, APPENDED AT DISPATCH")) `
        ("log=" + [bool]($log -match 'ALREADY RECORDED: TASK 0300') + " note-in-brief=" + $c300.Contains("WATCHER NOTE"))

  Check "E2 unrecorded brief dispatched clean" `
        (($log -match 'no entry for TASK 0310') -and ($c310 -ne "") -and
         -not $c310.Contains("WATCHER NOTE")) `
        ("log=" + [bool]($log -match 'no entry for TASK 0310') + " captured=" + $c310.Length +
         "B unannotated=" + (-not $c310.Contains("WATCHER NOTE")))

  Check "E3 save sweep never annotated despite an entry" `
        (($log -match 'is a save sweep') -and ($c320 -ne "") -and -not $c320.Contains("WATCHER NOTE")) `
        ("log=" + [bool]($log -match 'is a save sweep') + " unannotated=" + (-not $c320.Contains("WATCHER NOTE")))

  Check "E4 all three dispatched, none skipped" `
        (($c300 -ne "") -and ($c310 -ne "") -and ($c320 -ne "")) `
        "every brief reached the task; the mechanism annotates and never gates"

  $doneNote = ""
  $dn = @(Get-ChildItem -LiteralPath (Join-Path $Q "DONE") -Filter "*0300-already-done.md" -ErrorAction SilentlyContinue)
  if ($dn.Count -gt 0) { $doneNote = [System.IO.File]::ReadAllText($dn[0].FullName) }
  Check "E5 the DONE archive keeps the note" ($doneNote.Contains("WATCHER NOTE")) `
        "the archived brief records what the session actually read"

  if (-not $KeepScratch) { Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue }
  else { Write-Host ("  scratch kept: " + $Root) }
}

Write-Host ""
Write-Host ("PASS " + $script:passes + "   FAIL " + $script:fails.Count)
if ($script:fails.Count) {
  Write-Host ("FAILED: " + ($script:fails -join ", "))
  exit 1
}
exit 0
