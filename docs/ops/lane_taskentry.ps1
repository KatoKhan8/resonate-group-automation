<#
  lane_taskentry.ps1 - "has this lane already recorded TASK NNNN?"

  WHY THIS EXISTS. The dispatcher has no memory. A brief that is re-queued by
  hand is indistinguishable, to the watcher, from one that has never run, and
  the estate paid for that on 2026-10-16: glm-c's 0220 was dispatched 09:16:52
  and died on the 150-minute timeout at 11:47:00 on a brief whose report was
  already at LANE-glm-c.md:1948 and whose re-measurement was already at :2091.
  Its .out is 559 bytes - the model banner and nothing else. Measured from
  logs\watcher-glm-c.log lines 445 and 457.

  WHAT IT DELIBERATELY DOES NOT DO: SKIP.

  Skipping and dispatching are not symmetric failures.

    Skipping a brief that is NOT done loses work silently, and there is a
    measured case: glm-c/0161 looked done, ran in 3m44s, and found that
    task-glm-c-0164-brake-ship (0355fe7b7) had no remote ref at all and held
    the only copy of TASK 0225's work. A skip there would have left it on one
    disk and nobody would have been told.

    Dispatching a brief that IS done costs a dispatch. glm/0073's third
    dispatch found a new defect; glm-c/0220's timeout found nothing.

  So the answer is an ANNOTATION, not a gate. The watcher still dispatches;
  the session is told, in the brief it reads, that an entry already exists and
  where. The estate's own precedent is that a lane handed a finished brief
  AUDITS the deliverable - glm-b/0010 and glm-c/0220 both did - and the cost
  this removes is the hours spent discovering that, not the audit itself.

  A rule that cannot be wrong in a direction that loses work can be wrong
  cheaply. This one is only ever wrong cheaply.

  THE THREE STATES ARE NOT TWO. MATCH, NO_MATCH and UNKNOWN. UNKNOWN is what
  an unreadable lane file, a missing lane file or a brief whose filename does
  not declare a task id produces, and UNKNOWN annotates NOTHING and dispatches
  normally. Absence of a readable answer is never evidence of absence of an
  entry, and it is never evidence of one either.

  ASCII ONLY, like every other script in this folder, for the PowerShell 5.1
  ANSI-codepage reason documented at the top of lane_watcher.ps1.
#>

function Get-LaneBriefTaskId {
  <#
    The task id a QUEUE brief filename declares, or $null.

    STRICT ON PURPOSE. The queue convention is NNNN-slug.md. Anything else
    returns $null, which the caller turns into UNKNOWN and dispatches. A looser
    extractor would ask the lane file a question about the wrong task and
    answer it confidently, which is worse than not asking.

    Note what this correctly REFUSES: glm-c has 0162c-rescue-the-28-minute-run
    and 0162d-three-of-your-four-are-already-recorded in its queue right now.
    Those are different briefs from 0162 and must not inherit 0162's entry. The
    trailing letter breaks the pattern, so they come back $null -> UNKNOWN ->
    dispatched, which is the safe direction.
  #>
  param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$BriefName)
  if ($BriefName -match '^(\d{4})-') { return $Matches[1] }
  return $null
}

function Test-LaneSaveSweep {
  <#
    A save sweep re-measures state. It is never waste and is never annotated as
    already-done, however many times its number appears in the lane file.
    Named as an exception by the task brief, and by the evidence: glm-c ran
    0161-save-sweep twice on 2026-10-16 (09:14 exit-1, 11:47 exit0) and the
    second run is the one that found the branch with no remote ref.
  #>
  param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$BriefName)
  return ($BriefName -match '(?i)save[-_ ]?sweep')
}

function Find-LaneTaskEntry {
  <#
    Does $LaneFile carry an entry claiming TASK $TaskId?

    THE RULE, stated so it can be refuted. A line counts iff BOTH hold:

      1. ENTRY-OPENER SHAPE. The line starts, within three spaces and through
         an optional bullet, optional bold and optional markdown heading
         marker, with either the word TASK or an ISO date.

      2. TASK-ADJACENT NUMBER. Somewhere in the first 120 characters of that
         line, the word TASK is followed - across at most three characters of
         space, dash, underscore, colon or hash - by one to four digits whose
         NUMERIC value equals $TaskId, with a word boundary after them.

    WHY NOT HEADINGS ALONE, which is what this function did in its first
    version and what webapp/0200 measured. Because glm-c does not use them.
    LANE-glm-c.md records TASK 0040, 0050, 0080, 0090, 0100 and 0110 as plain
    dated paragraphs at column zero:

        2026-10-15 - TASK 0040 - DEPENDENCY UNMET, STOPPED BEFORE GENERATING:

    A heading-anchored rule calls every one of those NO ENTRY. Measured: the
    heading-only rule missed 14 real entries across the seven lane files, and
    eleven of them are in that one lane. The anchor had to move from "is a
    heading" to "opens an entry", and an ISO date at the start of a line is how
    this estate opens one.

    WHY NOT ANY LINE CONTAINING "TASK NNNN", which is the obvious relaxation.
    Because LANE-glm-c.md:370 reads

        NEXT: TASK 0040 (`queue/glm-c/0040-canary-approval-sheet.md`).

    which is a forward pointer to work NOT YET DONE - the exact claim this
    function must never make. It does not open with TASK and it does not open
    with a date, so the shape test refuses it. That line is the single most
    instructive false positive in the estate and it is why rule 1 exists.

    NUMERIC comparison, so TASK 0220, TASK 220 and TASK-0220 are one answer.
    The word boundary after the digits is what stops TASK 02200 matching 0220.

    Returns a hashtable:
      State  MATCH | NO_MATCH | UNKNOWN
      Count  number of lines that matched
      Line   1-based line number of the FIRST match, or 0
      Text   that line, trimmed, or ''
      Why    for UNKNOWN, the reason; otherwise ''
  #>
  param(
    [Parameter(Mandatory = $true)][AllowEmptyString()][string]$LaneFile,
    [Parameter(Mandatory = $true)][AllowEmptyString()][string]$TaskId
  )

  $res = @{ State = "UNKNOWN"; Count = 0; Line = 0; Text = ""; Why = "" }

  if ([string]::IsNullOrWhiteSpace($TaskId) -or ($TaskId -notmatch '^\d{1,4}$')) {
    $res.Why = "no task id could be derived from the brief filename"
    return $res
  }
  if ([string]::IsNullOrWhiteSpace($LaneFile) -or -not (Test-Path -LiteralPath $LaneFile)) {
    $res.Why = "lane file not found: " + $LaneFile
    return $res
  }

  $lines = $null
  try {
    $lines = @(Get-Content -LiteralPath $LaneFile -ErrorAction Stop)
  } catch {
    # FAIL CLOSED, loudly. An unreadable authority is UNKNOWN. It is never
    # "no entry", which would be a silent licence to dispatch as if asked,
    # and it is never "entry exists", which would annotate a lie.
    $res.Why = "lane file unreadable (" + $_.Exception.GetType().Name + "): " + $_.Exception.Message
    return $res
  }

  $want   = [int]$TaskId
  $opener = [regex]'(?i)^[ \t]{0,3}(?:[-*+][ \t]+)?\**(?:#{1,6}[ \t]+\**)?(?:TASK\b|\d{4}-\d{2}-\d{2}\b)'
  # Applied per line, so the reported line NUMBER is a measurement rather than
  # a byte offset reconstructed afterwards. These files run to 18,528 lines; a
  # location that is approximately right is a location nobody can check.
  $pair   = [regex]'(?i)\bTASK\b[ \t\-_:#]{0,3}(\d{1,4})\b'

  for ($i = 0; $i -lt $lines.Count; $i++) {
    $ln = $lines[$i]
    if (-not $opener.IsMatch($ln)) { continue }
    $head = if ($ln.Length -gt 120) { $ln.Substring(0, 120) } else { $ln }
    # A line may cite more than one task - '## TASK 0140 - 0100'S WORK IS NOW
    # DURABLE' is real - so every TASK-number pair on it is walked, not the
    # first only.
    foreach ($m in $pair.Matches($head)) {
      if ([int]$m.Groups[1].Value -eq $want) {
        $res.Count++
        if ($res.Line -eq 0) { $res.Line = $i + 1; $res.Text = $ln.Trim() }
        break
      }
    }
  }

  if ($res.Count -gt 0) { $res.State = "MATCH" } else { $res.State = "NO_MATCH" }
  return $res
}

function Write-LaneAlreadyRecordedNote {
  <#
    Append the note to the brief IN RUNNING, which is the only channel into
    the session there is.

    WHY THE BRIEF AND NOT AN ENVIRONMENT VARIABLE OR A SIDECAR. The watcher
    launches the task as

        cmd /c claude -p --permission-mode {MODE} < "{BRIEF}" > "{OUT}" 2>&1

    so the brief on STDIN is the whole of what the session is handed. A
    sidecar file or an env var is a thing the session would have to already
    know to look for, which is the same reference-that-resolves-to-nothing
    failure the standing rules' own path bug was.

    IT IS THE RUNNING COPY, NEVER THE QUEUE FILE. The queue original was
    already moved out by the caller, so nothing in queue\<lane>\ is touched.
    The annotated copy is the one that lands in DONE, which is a second reason
    to do it this way: the archive then records what the session actually read
    rather than what was written for it.

    Returns @{ Ok = $true|$false; Why = '' }. Never throws - the caller treats
    a failure as "no annotation" and dispatches anyway.
  #>
  param(
    [Parameter(Mandatory = $true)][string]$RunPath,
    [Parameter(Mandatory = $true)][string]$Lane,
    [Parameter(Mandatory = $true)][string]$TaskId,
    [Parameter(Mandatory = $true)]$Hit
  )
  $out = @{ Ok = $false; Why = "" }
  try {
    if (-not (Test-Path -LiteralPath $RunPath)) { $out.Why = "brief not found: " + $RunPath; return $out }

    $nl = [Environment]::NewLine
    $sb = New-Object System.Text.StringBuilder
    foreach ($l in @(
      "",
      "---",
      "",
      "## WATCHER NOTE, APPENDED AT DISPATCH - NOT PART OF THE BRIEF",
      "",
      ('`LANE-' + $Lane + '.md` ALREADY CARRIES AN ENTRY CLAIMING TASK ' + $TaskId + '.'),
      "",
      ("    LANE-" + $Lane + ".md:" + $Hit.Line),
      ("    " + $Hit.Text),
      "",
      ([string]$Hit.Count + " line(s) in that file match. THIS IS AN ANNOTATION, NOT A SKIP: the"),
      "watcher dispatched this brief normally and what to do about it is yours.",
      "The watcher does not skip because the two errors are not symmetric - a",
      "wrong skip loses work silently, and glm-c/0161 is the case: it looked",
      "done, ran in 3m44s, and found a branch with no remote ref at all holding",
      "the only copy of TASK 0225's work.",
      "",
      "So READ THE ENTRY FIRST, then do ONE of these and say in your own entry",
      "which one you chose and why:",
      "",
      "  AUDIT     the entry is right and the deliverable exists. Re-measure its",
      "            gate yourself at the moment you look, confirm the artifact on",
      "            the branch it names, and record AUDITED with what you",
      "            re-measured. This is the estate's precedent and usually the",
      "            right answer.",
      "  COMPLETE  the entry is partial. Finish the named gap only.",
      "  REDO      the entry is wrong, or the artifact it names does not exist.",
      "            Say how you measured that BEFORE redoing anything.",
      "",
      "A MATCH IS A MATCH ON A LINE. It is not proof the work was done: a",
      "handoff saying DONE, ARTIFACT VERIFIED is not proof, and this estate has",
      "measured three such artifacts missing from master. Check it yourself.",
      ""
    )) { [void]$sb.Append($l); [void]$sb.Append($nl) }

    # UTF-8 WITHOUT A BOM, explicitly. Add-Content -Encoding UTF8 under
    # PowerShell 5.1 is BOM-writing, and a BOM dropped into the middle of a
    # brief would arrive on the session's stdin as a stray character.
    $enc = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::AppendAllText($RunPath, $sb.ToString(), $enc)

    # READ IT BACK. "Measure before you claim; a tool reporting success is not
    # evidence the write landed" - the standing rules, and this is the cheapest
    # possible instance of it.
    $after = [System.IO.File]::ReadAllText($RunPath)
    if ($after.Contains("WATCHER NOTE, APPENDED AT DISPATCH")) {
      $out.Ok = $true
    } else {
      $out.Why = "appended, but the marker was not in the file on read-back"
    }
  } catch {
    $out.Why = $_.Exception.GetType().Name + ": " + $_.Exception.Message
  }
  return $out
}
