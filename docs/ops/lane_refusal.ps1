<#
  lane_refusal.ps1 - decide whether a lane task was REFUSED BY THE PROVIDER
  BEFORE IT EVER RAN, as opposed to having run and failed.

  ASCII ONLY, DELIBERATELY. Same reason as lane_watcher.ps1: Windows PowerShell
  5.1 reads a BOM-less .ps1 in the system ANSI codepage, and a UTF-8 punctuation
  character arrives as something PowerShell may accept as a string delimiter.
  NOTE THAT THE PROVIDER'S OWN LINE IS NOT ASCII - it carries a U+00B7 middot
  between the status and the body - which is precisely why no pattern below ever
  looks at that character.

  IT LIVES IN ITS OWN FILE SO A TEST CAN DOT-SOURCE IT, exactly as
  lane_treekill.ps1 does and for the same reason: lane_watcher.ps1 takes
  mandatory parameters and then loops forever, so nothing can dot-source it, and
  a classifier that can only be exercised by refusing a real lane is a
  classifier nobody can test. Proof:
  docs\ops\test_lane_refusal_classifier.ps1 (real provider bytes),
  docs\ops\mutate_lane_refusal.py (gate-by-gate mutation),
  docs\ops\test_lane_watcher_refusal.ps1 (the whole chain, end to end).

  ------------------------------------------------------------------ WHY

  2026-10-16 01:41-01:48, measured in logs\watcher-{glm,glm-b,glm-c}.log: the
  GLM Coding Max plan hit its rolling 5-hour limit, every `claude -p` started
  afterwards was refused by the provider in about three minutes, and the watcher
  had no verdict for *never started*. It wrote exit1, moved the brief to DONE
  and took the next one. Nine briefs in seven minutes, none executed. Two of the
  nine were on the canary critical path.

  Failure family 6, named in
  FINDING-the-quota-that-ate-nine-briefs-2026-10-16.md: a result the instrument
  has no name for is reported as the nearest name it does have - and here the
  nearest name was the destructive one, because a failure consumes the brief.

  ------------------------------------------------- WHAT IS AND IS NOT A GATE

  FOUR GATES, ALL REQUIRED, AND THE STRING IS THE LAST OF THEM. The string is
  the weakest link - the provider can reword its message any day, which is
  failure family 1 - so it is never asked to carry the decision alone:

    1  the task did not TIME OUT          a timeout is a timeout, and the
                                          watcher already has a verdict for it
    2  the exit code is a non-zero INT    a zero exit is a completion or NOWORK
    3  the LANE FILE DID NOT GROW         this is the one gate that does not
                                          depend on any provider wording. If the
                                          task recorded work, returning the
                                          brief would re-run work already done,
                                          so a refusal that arrives after real
                                          work is deliberately NOT a refusal
    4  a named signature matched          see Get-LaneRefusalSignatures

  WHAT HAPPENS WHEN THE STRING STOPS MATCHING, which it eventually will: gate 4
  fails, Test-LaneProviderRefusal returns IsRefusal = $false, and the watcher
  takes the path that exists today - exit<N>, brief consumed into DONE. That is
  the fail-closed direction the brief required: an unclassifiable exit must
  NEVER take the return-to-queue path, because a watcher that returns every
  failure to its queue loops forever on a genuinely broken brief, which is the
  same bug facing the other way.

  It is fail-closed, not free. So the NEAR MISS flag exists: when gates 1-3 pass
  and gate 4 does not, while the output still looks like a transport-level
  complaint, the caller is told to SAY SO LOUDLY in the lane log. The day the
  wording changes, the log says "a refusal signature nearly matched" instead of
  silently going back to eating briefs. A fallback nobody can see is this
  repository's own signature defect.

  WHY THERE ARE TWO SIGNATURES AND NOT ONE: so that a single wording change does
  not lose the behaviour. The prefix and the quota sentence are independent
  wordings from independent layers (the CLI prints the first, the provider's API
  body carries the second), and either alone is sufficient under gates 1-3.

  -------------------------------- THE RESET TIME IS NOT A WALL-CLOCK INSTANT

  The message states one:

      [1308][Usage limit reached for 5 hour.
             Your limit will reset at 2026-10-16 08:07:16]

  IT IS IN THE PROVIDER'S OWN CLOCK AND THE STRING CARRIES NO OFFSET. Measured
  2026-10-16 across all eight captured refusals, by comparing the 14-digit stamp
  that opens each message's request id against the local mtime of the .out file
  the watcher had just finished writing:

      task-glm-20261016-004231.out      provider 07:41:36   local 01:41:36
      task-glm-20261016-014141.out      provider 07:44:49   local 01:44:49
      task-glm-20261016-014455.out      provider 07:48:08   local 01:48:09
      task-glm-b-20261016-011843.out    provider 07:43:07   local 01:43:07
      task-glm-b-20261016-014312.out    provider 07:46:22   local 01:46:22
      task-glm-c-20261016-004232.out    provider 07:41:50   local 01:41:50
      task-glm-c-20261016-014156.out    provider 07:45:00   local 01:45:00
      task-glm-c-20261016-014506.out    provider 07:48:08   local 01:48:08

      offset  +6:00:00 on seven of eight, +5:59:59 on the eighth (one second of
              rounding between the provider stamping the id and the watcher
              closing the file). This machine is Europe/Zagreb, CEST = UTC+2,
              so the provider clock is UTC+8.

  So "reset at 2026-10-16 08:07:16" meant 02:07:16 on THIS machine. A watcher
  that had slept until 08:07:16 local would have idled SIX HOURS past the
  reset - and the operator in fact restarted the three GLM lanes at 09:16 and
  they ran normally, which is consistent with the reset having passed at 02:07
  and not at 08:07.

  Get-LaneRefusalResetTime therefore returns THE STRING EXACTLY AS PRINTED and
  refuses to convert it to an instant. It is for the log, so a human reading the
  lane file sees what the provider claimed. Nothing schedules against it. A
  guessed timezone is worse than a missing one.
#>

# -------------------------------------------------------------- SIGNATURES
# One place, one table, each entry named. Adding a wording is a one-line change
# an operator can review, and the matched name is written into the lane log so
# the record says WHICH wording fired rather than merely that something did.
function Get-LaneRefusalSignatures {
  return @(
    [pscustomobject]@{
      Name    = "api-error-429"
      # LINE-ANCHORED, and that anchor is doing real work. Measured against a
      # real negative: logs\task-qwen-20261015-230405.out, a task that ran, did
      # its work, grew the lane file and exited 0, contains
      #
      #   Assistant model='<synthetic>'  'API Error: Connection refused
      #   (ECONNREFUSED)'  cost_usd=0
      #
      # - a task QUOTING an API error inside its own report. An unanchored
      # 'API Error' would match that. The anchor excludes it structurally, which
      # is a second independent reason on top of gates 2 and 3.
      #
      # The status is matched both parenthesised and bare so a formatting change
      # around it does not cost the match. The U+00B7 that follows it in the real
      # message is never looked at.
      Pattern = '(?m)^[ \t]*API Error\b[^\r\n]*(\(429\)|\b429\b)'
      Status  = "429"
      Note    = "the CLI's own transport-level prefix, carrying HTTP 429. The status is far more stable than the sentence after it."
    },
    [pscustomobject]@{
      Name    = "usage-limit-reached"
      # The provider's API body rather than the CLI's prefix, so this one
      # survives a change to the prefix. Both the quota phrase AND the reset
      # promise are required on one line: that pair is what a quota refusal
      # says and what a task discussing quotas in prose does not.
      Pattern = '(?m)^[^\r\n]*\bUsage limit reached\b[^\r\n]*\breset\b'
      Status  = "429"
      Note    = "the provider's own quota sentence. Independent of the CLI prefix, so one rewording cannot silence both."
    }
  )
}

# ------------------------------------------------------- NEAR-MISS PATTERNS
# NOT gates. These answer "did this look like a transport refusal that we failed
# to name", so that the day the wording moves, the lane log says so.
function Get-LaneRefusalNearMissPatterns {
  return @(
    [pscustomobject]@{ Name = "api-error-line";  Pattern = '(?m)^[ \t]*API Error\b' },
    [pscustomobject]@{ Name = "bare-429";        Pattern = '(?m)^[^\r\n]*\b429\b' },
    [pscustomobject]@{ Name = "rate-limit-word"; Pattern = '(?im)^[^\r\n]*\b(rate limit|quota exceeded|too many requests)\b' }
  )
}

# ------------------------------------------------------------- THE RESET TIME
# Returns the reset timestamp EXACTLY AS THE PROVIDER PRINTED IT, or "".
# It is NOT parsed, NOT localised and NOT converted to an instant. See the
# header: it is in the provider's clock, measured +6h from this machine, and the
# string carries no offset to correct it with.
function Get-LaneRefusalResetTime {
  param([string]$OutText = "")
  if ($null -eq $OutText -or $OutText -eq "") { return "" }
  $m = [regex]::Match($OutText, 'reset at\s+(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})')
  if ($m.Success) { return $m.Groups[1].Value }
  return ""
}

# ----------------------------------------------------------- THE CLASSIFIER
# FAIL-CLOSED BY CONSTRUCTION, INCLUDING ITS DEFAULTS. $LaneGrew defaults to
# $true and $ExitCode to $null, so a caller that forgets to pass either one gets
# "not a refusal" and today's behaviour, never the new path. A default that
# opens a destructive-free path for a caller who said nothing is not a safe
# default, it is an unsafe one with a friendly name.
function Test-LaneProviderRefusal {
  param(
    [string]$OutText = "",
    $ExitCode = $null,
    [bool]$TimedOut = $false,
    [bool]$LaneGrew = $true
  )

  $result = [pscustomobject]@{
    IsRefusal  = $false
    Verdict    = ""
    Signature  = ""
    Status     = ""
    ResetAtRaw = ""
    NearMiss   = $false
    NearMissBy = ""
    Reason     = ""
    FailedGate = ""
  }

  if ($null -eq $OutText) { $OutText = "" }

  # ---- GATE 1  a timeout is a timeout
  if ($TimedOut) {
    $result.FailedGate = "1-timed-out"
    $result.Reason = "the task timed out; TIMEOUT is already a verdict and the task did run"
    return $result
  }

  # ---- GATE 2  a non-zero integer exit
  # Checked on the STRING FORM so that $null, "", an unexpected type or an
  # unreadable exit code all land on "not a refusal" rather than on a type
  # error inside a guard. The watcher's own history has a case where the exit
  # code read back as $null; that must never be read as a refusal.
  $codeText = ""
  if ($null -ne $ExitCode) { $codeText = ([string]$ExitCode).Trim() }
  if ($codeText -notmatch '^-?\d+$') {
    $result.FailedGate = "2-exit-code-unusable"
    $result.Reason = "the exit code is not an integer (got '" + $codeText + "'), so nothing about this run is classifiable"
    return $result
  }
  if ([int]$codeText -eq 0) {
    $result.FailedGate = "2-exit-zero"
    $result.Reason = "the task exited 0; that is a completion or NOWORK, never a refusal"
    return $result
  }

  # ---- GATE 3  no work was recorded
  # The only gate that depends on nothing the provider writes.
  if ($LaneGrew) {
    $result.FailedGate = "3-lane-file-grew"
    $result.Reason = "the lane file grew, so work was recorded; returning the brief would re-run work already done"
    return $result
  }

  # ---- GATE 4  a named signature
  foreach ($sig in (Get-LaneRefusalSignatures)) {
    if ($OutText -match $sig.Pattern) {
      $result.IsRefusal  = $true
      $result.Verdict    = "PROVIDER_REFUSED"
      $result.Signature  = $sig.Name
      $result.Status     = $sig.Status
      $result.ResetAtRaw = Get-LaneRefusalResetTime -OutText $OutText
      $result.Reason     = "exit " + $codeText + ", no lane growth, and the output matched signature '" + $sig.Name + "'"
      return $result
    }
  }

  # Gates 1-3 passed and gate 4 did not. Say whether it LOOKED like one, so a
  # reworded message is visible in the log instead of silently costing briefs.
  $hits = @()
  foreach ($nm in (Get-LaneRefusalNearMissPatterns)) {
    if ($OutText -match $nm.Pattern) { $hits += $nm.Name }
  }
  $result.FailedGate = "4-no-signature"
  if ($hits.Count -gt 0) {
    $result.NearMiss   = $true
    $result.NearMissBy = ($hits -join ",")
    $result.ResetAtRaw = Get-LaneRefusalResetTime -OutText $OutText
    $result.Reason = "no refusal signature matched, but the output looks transport-level (" +
                     ($hits -join ",") + "). TREATED AS AN ORDINARY FAILURE - fail closed - " +
                     "and the wording may have changed."
  } else {
    $result.Reason = "no refusal signature and nothing transport-level in the output; an ordinary task failure"
  }
  return $result
}
