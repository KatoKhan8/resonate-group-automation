# TASK 0210 — START-ALL-LANES counted a refusal as a start

Measured and built 2026-10-16 by the `qwen` lane in `C:\Users\Zvonimir\qwc` (an
LF tree), on branch `task-qwen-0090-watcher-treekill-2026-10-15`.
`origin/master` is `b1f290c84` and was not touched. **Nothing was deployed:
`resonate-ops\tools\START-ALL-LANES.ps1` is untouched at 5,933 bytes, mtime
2026-10-15 20:50:59.**

---

## 1. THE BRIEF'S PREMISE WAS TRUE AND TOO SMALL. IT WAS SEVEN LANES, NOT TWO.

The brief named two lanes refusing at 00:23:27 while the console reported them
started. The logs name **every lane in the estate**, all within two seconds:

    [2026-10-16 00:23:27] [glm]          REFUSING: the tree-kill module is missing: ...
    [2026-10-16 00:23:27] [glm-b]        REFUSING: the tree-kill module is missing: ...
    [2026-10-16 00:23:27] [glm-c]        REFUSING: the tree-kill module is missing: ...
    [2026-10-16 00:23:27] [suppression]  REFUSING: the tree-kill module is missing: ...
    [2026-10-16 00:23:28] [pilotcaps]    REFUSING: the tree-kill module is missing: ...
    [2026-10-16 00:23:28] [qwen]         REFUSING: the tree-kill module is missing: ...
    [2026-10-16 00:23:28] [webapp]       REFUSING: the tree-kill module is missing: ...

all naming the same absolute path, `resonate-ops\tools\lane_treekill.ps1`. The
whole estate was down and the launcher said seven watchers started. The next
successful start was **00:28:51 — 5 minutes 23 seconds later**, by hand.

Counted by the only authority that exists for it: anchored
`REFUSING: the tree-kill module is missing` lines across all seven
`logs\watcher-*.log` files, de-duplicated. Seven lanes, two seconds.

## 2. AND THE REFUSALS WERE RIGHT. THE "MYSTERY" IS A TIMESTAMP NOBODY READ.

The brief flagged, correctly and with the instruction not to guess a cause, that
`lane_treekill.ps1` sits on disk with mtime **2026-10-15 21:49:07** — 94 minutes
*before* it was reported missing — and that why `Test-Path` returned false was
not established.

It is established now, and it is not a mystery. It is the difference between two
timestamps:

    CreationTime    2026-10-16 00:28:44.529
    LastWriteTime   2026-10-15 21:49:07.799
    LastAccessTime  2026-10-16 12:47:14.049

**The file at that path was created at 00:28:44** — 76 seconds after the last
refusal, and **7 seconds before the successful restart at 00:28:51**. It was not
there at 00:23:27. It arrived carrying an older write time, which is exactly what
a move or a timestamp-preserving copy does.

So **`LastWriteTime` was never evidence of presence**, the apparent contradiction
dissolves, and all seven refusals were each telling the truth. This estate's own
rule applies to its own diagnosis: a derived number is only as good as what it
actually measures, and an mtime measures the last write, not the arrival.

**WHO moved it is NOT established and is not asserted.** The adjacent facts, as
hints and not measurements: `tools\lane_watcher.ps1.2026-10-15.bak` was created
at 22:22:40 and `lane_watcher.NEW.ps1` at 22:20:25, so somebody was working in
`tools\` that evening; and the file reappeared 7 seconds before the restart that
worked, which is what a hand fixing the problem looks like. The window in which
it was absent is bounded by measurement at **21:49:07 → 00:28:44**.

## 3. WHAT THE OLD LINE COULD AND COULD NOT SAY

    :103   Write-Host ("start " + $l.Lane + "  queued=" + $count)   before the process exists
    :105   Start-Process powershell -ArgumentList @(...)            no -Wait, no -PassThru
    :111   $started++                                               unconditional
    :115   Write-Host ([string]$started + " watcher(s) started ...") a count of calls

Nothing held the child's handle, so no exit code was ever readable, and the six
refusal paths in `lane_watcher.ps1` — a missing worktree, the main checkout, no
`.git`, no `claude` on PATH, a missing module (now four of them), and exit 3
against a live pid lock — were all invisible. **The defect was not that the
number was wrong. It was that the number could not be wrong.**

## 4. WHAT REPLACES IT

`docs\ops\START-ALL-LANES.ps1`. A lane counts as STARTED only on a `watcher up`
line in its own log, written after this launch began, by a process still alive.

**"After this launch began" is a BYTE OFFSET, not a parsed timestamp.** The log is
append-only, so its length before the launch is a mark and only the bytes past it
are new. A log timestamp has one-second resolution, and two launches inside one
second are precisely the case that broke the old script.

    STARTED               a `watcher up` line past the mark, process alive
    REFUSED               a `REFUSING:` line past the mark, or a non-zero exit
                          -> the reason is READ BACK OUT OF THE LOG and printed
    SKIPPED               decided before launching: no worktree, or a STOP file
    CAME UP THEN EXITED   `watcher up` past the mark but the child is gone
    UNKNOWN               log unreadable, log truncated under us, nothing within
                          the bound, or an exit 0 with nothing to say

and the totals line is

    started=1  refused=2  skipped=0  unknown=0   of 3 lane(s), mode acceptEdits

followed by a per-lane list of everything that is not STARTED, with its reason.
**UNKNOWN is never counted as started**, and the exit code is 0 only when nothing
refused and nothing is UNKNOWN — a launcher that returns success while three
lanes are down is the same defect wearing a different hat.

**The wait is bounded and the bound is printed before anything launches.** All
lanes are launched first, then ONE polling loop resolves them against a single
deadline (`-UpTimeoutSeconds`, default 25), so seven lanes cost 25 seconds in the
worst case rather than 175. Observed need: a refusal lands in well under a second
and a healthy `watcher up` in about one.

**Reuse rather than duplication**, as the brief required. `-PassThru` gives the
real process handle, so none of 0200's pid-liveness machinery is needed here and
none is called — the handle beats any pid test. The log read keeps 0180's
`Read-WatchLog` contract (retry, and an exhausted retry is UNKNOWN rather than
empty) as three inline lines rather than a call, because `DRAIN-LANE.ps1` is a
standalone tool with mandatory parameters and top-level behaviour: dot-sourcing
it to borrow one helper would run it. That is stated in the code at the point it
matters.

**`queued=` — the brief asked whether its staleness matters. It does not, and the
number is unchanged.** It is read before the watcher starts, so it can be lower
by the number of briefs consumed in between — at most one in the first seconds.
It is a display value; the authority for depth is the queue directory. **The one
thing changed is the LABEL, to `queued-at-launch=`**, so it says when it was
taken. If the operator counts a label as a change, revert that one token; the
reading and the number are untouched.

## 5. THE PROOF — 26 LEGS, 0 FAILS

`docs\ops\test_start_all_lanes.ps1`. Scratch ops under `%TEMP%`; the lanes are
called `cameup`, `nogit`, `locked`, `unreadable`, `missing`, `stopped`, `silent`,
`silentfail` and `silentzero`; the seven real lane names are refused by name
before anything is created; the only STOP file it can write is under the scratch
root, asserted; `claude` is never invoked.

    C1  a lane that comes up               STARTED, on its own watcher up line
    C2  a worktree with no .git            REFUSED, and the reason reads
                                           "no .git here: ..." - the watcher's
                                           own words, out of the log
    C3  a live pid lock                    REFUSED, reason "a watcher for this
                                           lane is already running as pid N"
    C4  an unreadable log                  UNKNOWN, never STARTED
    C5  a missing worktree path            SKIPPED
    C6  a STOP-<lane> file                 SKIPPED, not revived
    C7  a watcher that says nothing        UNKNOWN, reason names the bound, and
                                           the launcher did not hang
    C8  a silent NON-ZERO exit             REFUSED, "exited 2 with no REFUSING
                                           line in its log"
    C9  a silent exit 0                    UNKNOWN, "exited 0 having written
                                           nothing to its log"

and the totals and exit code are asserted for each group.

**The legs are known to be able to fail, because they did.** C1 through C7 all
went red on the first run (a lane table with an illegal trailing comma), and C8
went red twice for two different real causes. An assertion that has never failed
is a check nobody has tested.

**Mutation proof: `docs\ops\mutate_start_all_lanes.py`, baseline green, five
mutations and one pair.**

    N1   THE ORIGINAL DEFECT: started = the count of launch attempts
                                              KILLED by C1-C3, C8, C9
    N2   the child's handle is not captured    UNKILLABLE AS DECLARED
    N3   an unreadable log is read as empty    UNKILLABLE AS DECLARED
    N3b  that guard AND the truncation guard   KILLED by C4
    N4   the exit code is always 0             KILLED by C1-C3, C4-C6
    N5   a silent lane is counted as started   KILLED by C7

**N1 is the one that matters**: it restores exactly the defect this task is
about, and three leg groups go red. If N1 had survived, the rewrite would have
bought nothing.

## 6. FOUR DEFECTS FOUND IN THIS WORK'S OWN CODE, AND ONE WRONG ATTRIBUTION I HAD TO CORRECT

**(a) `Start-Process -Wait` waits for the whole PROCESS TREE.** The harness used
it to run the launcher, and a launcher that *succeeds* leaves a healthy watcher
running — so `-Wait` never returned and the harness ran past 420 seconds with the
launcher long finished. Measured: the launcher's own output file was complete and
correct (`started=1 refused=2`) while the harness was still blocked on pid 3568,
the `cameup` watcher it had just proved was up. Fixed by polling the launcher's
own handle against a bound.

**(b) A trailing comma is not legal inside `@( )` either.** The generated lane
table failed to parse, the launcher saw an empty table and exited 1 — and two
legs *passed* on that exit code, because `exit 1` is also what a broken table
produces. Those legs now require the totals line as well, so they can
discriminate.

**(c) PowerShell's comma precedence, for the FOURTH time in one day.** A stub
watcher was generated as

    @("param(...)", "# ... then exits " + $code, "exit " + $code)

which collapses into ONE line, putting `exit 2` **inside the comment**. The stub
exited 0. Leg C8 read "exited 0" for a stub meant to exit 2 — and leg C9
(exit 0 -> UNKNOWN) then **passed for the wrong reason**, because both stubs
exited 0. Today this same trap produced a one-line claim sidecar in
`lane_orphan.ps1` (TASK 0200), a one-line brief in that task's harness, and
`fake_lane_task.ps1`'s own comment records it costing an earlier author a whole
run. Four authors, one trap.

**(d) The wrong attribution, which is the one worth writing down.** When C8 first
went red I blamed a missing `$null = $proc.Handle`, on a real measurement that
under PowerShell 5.1 `ExitCode` is blank without it. I then changed TWO things at
once — the handle and the stub — and C8 went green. **The handle was not the
cause.** Mutation N2 removes it again and nothing goes red, because the blankness
only happens in the `-NoNewWindow` shape, which the launcher does not use:

    -NoNewWindow -PassThru, no handle   ->  ExitCode EMPTY
    -NoNewWindow -PassThru, handle      ->  ExitCode 7
    -PassThru (the launcher), no handle ->  ExitCode 2
    -PassThru (the launcher), handle    ->  ExitCode 2

That is CLAUDE.md's "confirm that the intended test failed for the intended
reason, and that a different guard did not fire first" — broken by me, and caught
by the mutation surviving rather than by the test going green. The line stays: it
costs nothing and it guards the day somebody adds `-NoNewWindow`. The comment at
that line now says exactly this instead of claiming it is load-bearing.

**N3 is the same shape as TASK 0200's M3** — an unreadable log read as empty is
caught by the *next* guard, the truncation check, because the empty string is
shorter than the mark. The UNKNOWN verdict is doubly protected, and N3b removes
both guards to prove the pair. Both unkillable mutations are declared and
explained rather than dropped from the list, which is how a guard with no red
state survives.

## 7. FOR THE OPERATOR

- **Nothing is deployed.** The live `tools\START-ALL-LANES.ps1` is the old one.
  Deploying this version is one file copy and it changes no watcher behaviour —
  it only tells the truth about it. **But see TASK 0200's report first: the
  watcher deploy is four files and a partial copy stops every lane you restart.**
- **The new launcher exits 1 when any lane is not STARTED.** If you have anything
  that treats a non-zero exit as a failure to act on, that is new behaviour.
- **What you will see when a lane refuses** is the watcher's own refusal line, on
  the launcher's console, next to the lane's name — not a count. And a lane whose
  state cannot be established reads UNKNOWN, with the reason, and is never
  counted as up.
- **The `queued=` label became `queued-at-launch=`.** The number is identical.
- **Still unestablished, and it is a read on that machine:** who removed
  `tools\lane_treekill.ps1` between 21:49:07 and 00:28:44 on the night of
  2026-10-15. The file is there now. If something in a deploy routine moves files
  out of `tools\` and back, the next deploy will take the estate down the same
  way, and the new launcher will at least say so in seven named lines instead of
  claiming success.
