<#
  measure_lane_taskentry.ps1 - the false-positive and false-negative rates of
  the already-recorded matcher, over the seven REAL lane files.

  It runs the shipped function. Not a reimplementation of it, not a
  reconstruction of what it probably does - lane_taskentry.ps1 is dot-sourced
  and Find-LaneTaskEntry is the thing measured, because a rate measured against
  a copy of the rule is a rate about the copy.

  Two baselines are measured beside it, both named in webapp/0200, so the
  numbers are comparable rather than merely small:

    A  NUMBER-ONLY   the 4-digit id appears anywhere in the lane file
    B  HEADING-NUM   the id appears in a markdown heading, TASK or not
    C  SHIPPED       Find-LaneTaskEntry: heading AND TASK-adjacent

  Population: every brief filename the queue holds for that lane - pending,
  RUNNING and DONE - reduced to distinct (lane, task id) pairs. That is the
  exact question the watcher asks, asked once per thing it could ask about.

  Output is a TSV on stdout so the hand validation reads the same rows the
  rates are computed from.
#>
param(
  [string]$Ops = "C:\Users\Zvonimir\Desktop\resonate-ops",
  [string]$Module = (Join-Path $PSScriptRoot "lane_taskentry.ps1"),
  [string[]]$Lanes = @("glm", "glm-b", "glm-c", "pilotcaps", "qwen", "suppression", "webapp")
)
$ErrorActionPreference = "Stop"
. $Module

function Get-AnyBriefTaskId {
  # HARNESS ONLY, and deliberately looser than Get-LaneBriefTaskId, because the
  # population includes DONE filenames the watcher never parses:
  #     20261016-105037-exit0-0176-the-revert-that-...md
  #     20261016-091403-exit-1-0161-save-sweep.md
  #     20261016-0920-NEPOZNATO-JE-LI-ODRADJEN-0170-the-two-...md
  # The shipped extractor must stay strict; this one must cover the archive.
  param([string]$Name)
  $s = $Name
  if ($s -match '^\d{8}-\d{4,6}-(.*)$') { $s = $Matches[1] }
  if ($s -match '(?<!\d)(\d{4})-') { return $Matches[1] }
  return $null
}

$rows = @()
foreach ($lane in $Lanes) {
  $laneFile = Join-Path $Ops ("LANE-" + $lane + ".md")
  $raw      = Get-Content -LiteralPath $laneFile -Raw
  $lines    = @(Get-Content -LiteralPath $laneFile)

  $seen = @{}
  foreach ($sub in @("", "RUNNING", "DONE")) {
    $dir = Join-Path $Ops ("queue\" + $lane)
    if ($sub -ne "") { $dir = Join-Path $dir $sub }
    foreach ($f in @(Get-ChildItem -LiteralPath $dir -Filter *.md -File -ErrorAction SilentlyContinue)) {
      $id = Get-AnyBriefTaskId -Name $f.Name
      if ($null -eq $id) {
        $rows += [pscustomobject]@{ Lane=$lane; Id="NOID"; Where=$(if($sub -eq ""){"queue"}else{$sub}); File=$f.Name; A=""; B=""; H=""; D=""; C=""; CLine=0; CCount=0; CText="" }
        continue
      }
      if ($seen.ContainsKey($id)) { continue }
      $seen[$id] = $f.Name

      # A - NUMBER-ONLY: the id appears anywhere in the lane file.
      $a = if ($raw -match ("(?<!\d)" + [regex]::Escape($id) + "(?!\d)")) { "MATCH" } else { "NO_MATCH" }

      # B - HEADING-NUM: the id appears in a markdown heading, TASK or not.
      $b = "NO_MATCH"
      foreach ($ln in $lines) {
        if ($ln -match ('^[ \t]{0,3}#{1,6}[ \t].*(?<!\d)' + [regex]::Escape($id) + '(?!\d)')) { $b = "MATCH"; break }
      }

      # H - HEADING + TASK-ADJACENT: the rule this harness REFUTED. Kept as a
      # measured baseline rather than deleted, because "the anchor moved from
      # heading to entry-opener" is a claim with a number behind it only while
      # the old rule is still being scored on the same population.
      $h = "NO_MATCH"
      foreach ($ln in $lines) {
        foreach ($m in ([regex]'(?i)^[ \t]{0,3}#{1,6}[ \t].*?\bTASK\b[ \t\-_:#]{0,3}(\d{1,4})\b').Matches($ln)) {
          if ([int]$m.Groups[1].Value -eq [int]$id) { $h = "MATCH"; break }
        }
        if ($h -eq "MATCH") { break }
      }

      # D - ANY LINE + TASK-ADJACENT: no position anchor at all. The loosest
      # TASK-keyed rule, measured so the entry-opener anchor's cost is visible.
      $d = "NO_MATCH"
      foreach ($ln in $lines) {
        foreach ($m in ([regex]'(?i)\bTASK\b[ \t\-_:#]{0,3}(\d{1,4})\b').Matches($ln)) {
          if ([int]$m.Groups[1].Value -eq [int]$id) { $d = "MATCH"; break }
        }
        if ($d -eq "MATCH") { break }
      }

      # C - THE SHIPPED RULE.
      $c = Find-LaneTaskEntry -LaneFile $laneFile -TaskId $id

      $rows += [pscustomobject]@{
        Lane=$lane; Id=$id; Where=$(if($sub -eq ""){"queue"}else{$sub}); File=$f.Name
        A=$a; B=$b; H=$h; D=$d; C=$c.State; CLine=$c.Line; CCount=$c.Count; CText=$c.Text
      }
    }
  }
}

"LANE`tID`tWHERE`tA_numonly`tB_headnum`tH_headtask`tD_anyline`tC_shipped`tC_LINE`tC_N`tC_LINETEXT`tBRIEF"
foreach ($r in ($rows | Sort-Object Lane, Id)) {
  "{0}`t{1}`t{2}`t{3}`t{4}`t{5}`t{6}`t{7}`t{8}`t{9}`t{10}`t{11}" -f `
    $r.Lane, $r.Id, $r.Where, $r.A, $r.B, $r.H, $r.D, $r.C, $r.CLine, $r.CCount, $r.CText, $r.File
}

$pairs = @($rows | Where-Object { $_.Id -ne "NOID" })
""
("POPULATION  distinct (lane,task) pairs: " + $pairs.Count + "   unparseable filenames: " + @($rows | Where-Object { $_.Id -eq "NOID" }).Count)
foreach ($k in @("A","B","H","D","C")) {
  $m = @($pairs | Where-Object { $_.$k -eq "MATCH" }).Count
  ("  rule {0}: MATCH {1}  NO_MATCH {2}" -f $k, $m, ($pairs.Count - $m))
}
