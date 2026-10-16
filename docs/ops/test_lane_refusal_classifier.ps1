<#
  test_lane_refusal_classifier.ps1 - prove Test-LaneProviderRefusal against the
  REAL BYTES the provider produced on 2026-10-16, not against an imitation of
  them.

  ASCII ONLY, same reason as the files it tests.

  WHY THE REAL BYTES MATTER HERE MORE THAN USUALLY. The provider's line is not
  ASCII - it carries U+00B7 between the status and the body - and this
  repository has been wrong before about what a file on disk actually contains.
  A classifier proven only against a string typed in a test file is a
  classifier proven against the test author's memory of the provider. So the
  eight captured .out files are read as bytes and fed in verbatim.

  THEY ARE READ FROM THE LIVE LOG DIRECTORY, WHICH IS A READ AND ONLY A READ.
  Nothing here writes to, moves or deletes anything under resonate-ops. If the
  artifacts are gone - log rotation, a cleanup - this script says UNKNOWN and
  exits 2 rather than passing on the synthetic cases alone. An artifact-based
  proof whose artifacts are missing is not a weaker proof, it is no proof.

  THE NEGATIVE THAT COST THE MOST THOUGHT is case E:
  logs\task-qwen-20261015-230405.out is a task that RAN, did its work, grew the
  lane file and exited 0, and its own report contains the line

      Assistant model='<synthetic>'  'API Error: Connection refused
      (ECONNREFUSED)'  cost_usd=0

  A task quoting an API error inside its own output. An unanchored 'API Error'
  match would have fired on it. This file is in the suite as a permanent
  reminder that the haystack contains the needle's cousin.

  CASE F is the other family found the same day and deliberately NOT caught:
  at 09:16:45 all six running lane tasks died at once with exit code -1 and an
  .out holding only the model warning - no API Error line at all. Six briefs
  consumed, none run. That is the same damage from a different cause, it has no
  provider signature to match on, and guessing at it would be exactly the
  "unclear case takes the new path" failure the brief forbids. It is asserted
  here to FALL THROUGH to today's behaviour, so the boundary of this patch is
  recorded rather than assumed.
#>
param(
  [string]$Ops = "C:\Users\Zvonimir\Desktop\resonate-ops",
  # Named so a mutation run can point at a mutated copy of the module.
  [string]$ModulePath = ""
)

$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $PSCommandPath
if ($ModulePath -eq "") { $ModulePath = Join-Path $here "lane_refusal.ps1" }
if (-not (Test-Path -LiteralPath $ModulePath)) {
  Write-Host ("MISSING: " + $ModulePath); exit 2
}
. $ModulePath
foreach ($fn in @("Test-LaneProviderRefusal", "Get-LaneRefusalSignatures", "Get-LaneRefusalResetTime")) {
  if (-not (Get-Command $fn -ErrorAction SilentlyContinue)) {
    Write-Host ("MISSING FUNCTION: " + $fn + " (did " + $ModulePath + " parse?)"); exit 2
  }
}

$LogDir = Join-Path $Ops "logs"

# The eight captured refusals. Named individually and NOT globbed, because a
# glob would silently shrink to seven, or to zero, and still report PASS.
$REFUSAL_OUTS = @(
  "task-glm-20261016-004231.out",
  "task-glm-20261016-014141.out",
  "task-glm-20261016-014455.out",
  "task-glm-b-20261016-011843.out",
  "task-glm-b-20261016-014312.out",
  "task-glm-c-20261016-004232.out",
  "task-glm-c-20261016-014156.out",
  "task-glm-c-20261016-014506.out"
)
# The 09:16:45 mass-kill family: exit -1, no API Error line.
$EXITMINUS1_OUTS = @(
  "task-glm-20261016-091403.out",
  "task-glm-b-20261016-091403.out",
  "task-glm-c-20261016-091403.out"
)
# A task that RAN and quoted an API error in its own report.
$QUOTING_OUT = "task-qwen-20261015-230405.out"

$fails  = New-Object System.Collections.ArrayList
$passes = 0
function Check($name, $ok, $detail) {
  if ($ok) { $script:passes++; Write-Host ("  PASS  " + $name + "   " + $detail) }
  else { [void]$script:fails.Add($name + " :: " + $detail); Write-Host ("  FAIL  " + $name + "   " + $detail) }
}

# READ AS BYTES AND DECODE UTF-8 EXPLICITLY. Get-Content -Raw would decode in
# the console's codepage, which is not what the provider wrote, and the whole
# point of this file is that the bytes are the provider's.
function ReadOut($name) {
  $p = Join-Path $LogDir $name
  if (-not (Test-Path -LiteralPath $p)) { return $null }
  $bytes = [System.IO.File]::ReadAllBytes($p)
  return [pscustomobject]@{
    Name  = $name
    Path  = $p
    Bytes = $bytes.Length
    Text  = [System.Text.Encoding]::UTF8.GetString($bytes)
    HasMiddot = ($bytes -contains 0xC2)
  }
}

Write-Host ""
Write-Host "=== the refusal classifier, against real provider bytes ===================="
Write-Host ("module    " + $ModulePath)
Write-Host ("artifacts " + $LogDir)
Write-Host ""

# ---------------------------------------------------------- the artifacts exist
$missing = @()
foreach ($n in ($REFUSAL_OUTS + $EXITMINUS1_OUTS + @($QUOTING_OUT))) {
  if (-not (Test-Path -LiteralPath (Join-Path $LogDir $n))) { $missing += $n }
}
if ($missing.Count -gt 0) {
  Write-Host "UNKNOWN: the captured artifacts this proof rests on are not on disk."
  foreach ($n in $missing) { Write-Host ("  missing: " + (Join-Path $LogDir $n)) }
  Write-Host "Not reporting PASS on the synthetic cases alone. Re-capture or name a new authority."
  exit 2
}

# ============================================================== CASE A
# The real thing, under the real gates: exit 1, no lane growth, no timeout.
Write-Host "--- CASE A  the eight real refusals -> REFUSAL -----------------------------"
foreach ($n in $REFUSAL_OUTS) {
  $o = ReadOut $n
  $r = Test-LaneProviderRefusal -OutText $o.Text -ExitCode 1 -TimedOut $false -LaneGrew $false
  Check ("A " + $n) ($r.IsRefusal -and $r.Signature -eq "api-error-429" -and $r.Status -eq "429") `
        ($o.Bytes.ToString() + " bytes, non-ascii=" + $o.HasMiddot + " -> IsRefusal=" + $r.IsRefusal +
         " sig=" + $r.Signature + " reset='" + $r.ResetAtRaw + "'")
}
$o1 = ReadOut $REFUSAL_OUTS[0]
$r1 = Test-LaneProviderRefusal -OutText $o1.Text -ExitCode 1 -TimedOut $false -LaneGrew $false
Check "A reset time is extracted verbatim" ($r1.ResetAtRaw -eq "2026-10-16 08:07:16") `
      ("got '" + $r1.ResetAtRaw + "'; it is the PROVIDER's clock (+6h from here) and is never scheduled against")
Check "A verdict string is the new one" ($r1.Verdict -eq "PROVIDER_REFUSED") `
      ("Verdict=" + $r1.Verdict + " - not exit0, not exit1, not NOWORK")

# ============================================================== CASES B/C/D
# Each gate, broken one at a time, with the same real bytes. These are what make
# the string the LAST gate rather than the only one.
Write-Host ""
Write-Host "--- CASES B,C,D  one gate broken at a time, same real bytes ----------------"
foreach ($n in $REFUSAL_OUTS) {
  $o = ReadOut $n
  $b = Test-LaneProviderRefusal -OutText $o.Text -ExitCode 0 -TimedOut $false -LaneGrew $false
  Check ("B exit 0 is never a refusal: " + $n) (-not $b.IsRefusal) ("gate=" + $b.FailedGate)
  $c = Test-LaneProviderRefusal -OutText $o.Text -ExitCode 1 -TimedOut $false -LaneGrew $true
  Check ("C lane grew, so work happened: " + $n) (-not $c.IsRefusal) ("gate=" + $c.FailedGate)
  $d = Test-LaneProviderRefusal -OutText $o.Text -ExitCode 1 -TimedOut $true -LaneGrew $false
  Check ("D a timeout stays a timeout: " + $n) (-not $d.IsRefusal) ("gate=" + $d.FailedGate)
}
# The exit code that this watcher's own history has produced as $null.
$e = Test-LaneProviderRefusal -OutText $o1.Text -ExitCode $null -TimedOut $false -LaneGrew $false
Check "B2 an unreadable exit code is not a refusal" (-not $e.IsRefusal -and $e.FailedGate -eq "2-exit-code-unusable") `
      ("gate=" + $e.FailedGate + " - the watcher has read \$null back from ExitCode before")
$dflt = Test-LaneProviderRefusal -OutText $o1.Text -ExitCode 1
Check "B3 the DEFAULTS fail closed" (-not $dflt.IsRefusal) `
      ("a caller that passes neither -LaneGrew nor -TimedOut gets gate=" + $dflt.FailedGate)

# ============================================================== CASE E
Write-Host ""
Write-Host "--- CASE E  a task that RAN and quoted 'API Error' in its own report -------"
$oq = ReadOut $QUOTING_OUT
Check "E the needle's cousin is present in the haystack" ($oq.Text -match "API Error: Connection refused") `
      ($QUOTING_OUT + " really does contain the words 'API Error'")
$rq = Test-LaneProviderRefusal -OutText $oq.Text -ExitCode 1 -TimedOut $false -LaneGrew $false
Check "E not a refusal even under the other three gates" (-not $rq.IsRefusal) ("gate=" + $rq.FailedGate)
Check "E not even a near miss" (-not $rq.NearMiss) `
      ("NearMiss=" + $rq.NearMiss + " - the line is mid-line inside the task's own prose, so the anchor excludes it")

# ============================================================== CASE F
Write-Host ""
Write-Host "--- CASE F  the 09:16:45 exit -1 family, deliberately NOT caught -----------"
foreach ($n in $EXITMINUS1_OUTS) {
  $o = ReadOut $n
  Check ("F " + $n + " carries no API Error line") (-not ($o.Text -match "API Error")) `
        ($o.Bytes.ToString() + " bytes, model warning only")
  $r = Test-LaneProviderRefusal -OutText $o.Text -ExitCode -1 -TimedOut $false -LaneGrew $false
  Check ("F " + $n + " falls through to today's behaviour") (-not $r.IsRefusal -and -not $r.NearMiss) `
        ("gate=" + $r.FailedGate + " - no signature to match, so no guess is made. This is the patch's boundary.")
}

# ============================================================== CASE G
Write-Host ""
Write-Host "--- CASE G  synthetic wordings: resilience and the near-miss alarm ---------"
$trace = "Traceback (most recent call last):`r`n  File `"x.py`", line 1`r`nKeyError: 'provider_truth'`r`n"
$g = Test-LaneProviderRefusal -OutText $trace -ExitCode 1 -TimedOut $false -LaneGrew $false
Check "G an ordinary traceback is an ordinary failure" (-not $g.IsRefusal -and -not $g.NearMiss) ("gate=" + $g.FailedGate)

# The CLI prefix reworded, the provider's own sentence intact -> the second
# signature carries it. This is why there are two and not one.
$h = Test-LaneProviderRefusal -OutText "Provider said no: Usage limit reached for 5 hour. Your limit will reset at 2026-10-16 08:07:16`r`n" `
                              -ExitCode 1 -TimedOut $false -LaneGrew $false
Check "G prefix reworded, quota sentence intact -> still caught" ($h.IsRefusal -and $h.Signature -eq "usage-limit-reached") `
      ("sig=" + $h.Signature + " - one rewording cannot silence both signatures")

# BOTH wordings gone. This is failure family 1 arriving, and the required
# behaviour is: fall back to today, and SAY SO.
$i = Test-LaneProviderRefusal -OutText "API Failure: rejected, status 429, retry later`r`n" `
                              -ExitCode 1 -TimedOut $false -LaneGrew $false
Check "G both wordings gone -> NOT a refusal (fail closed)" (-not $i.IsRefusal) ("gate=" + $i.FailedGate)
Check "G both wordings gone -> NEAR MISS is raised" ($i.NearMiss) `
      ("NearMissBy=" + $i.NearMissBy + " - the day the provider rewords, the lane log says so instead of quietly eating briefs")

# Reset-time extraction is a string operation and nothing more.
Check "G no reset time in the text -> empty, not a guess" ((Get-LaneRefusalResetTime -OutText "nothing here") -eq "") `
      "an absent timestamp is '' - never a default, never now()"
Check "G two signatures are registered" ((Get-LaneRefusalSignatures).Count -eq 2) `
      ((((Get-LaneRefusalSignatures) | ForEach-Object { $_.Name }) -join ", "))

Write-Host ""
Write-Host "=== RESULT ================================================================="
Write-Host ("  passed " + $passes + "   failed " + $fails.Count)
foreach ($f in $fails) { Write-Host ("  FAILED: " + $f) }
if ($fails.Count -gt 0) { exit 1 }
exit 0
