# TASK 0110 — the lane watcher, exercised end to end

**qwen lane, 2026-10-15.** Measured on branch
`task-qwen-0090-watcher-treekill-2026-10-15`, in the `qwc` checkout
(`C:\Users\Zvonimir\qwc`, an **LF** tree — `requirements.txt` CR=0, like the
main checkout and unlike the five lane worktrees).

TASK 0090 closed with its own limit named:

> **The watcher's wiring is argued, not executed.** `$Ops` and the task command
> are hardcoded to the live queue and a real `claude -p`, so I could not run a
> timeout end-to-end without running it against production.

This task removes that limit and then uses it.

---

## 1. What the defect actually was, and why one test could not reach it

The kill module was already proven directly by
`docs/ops/test_lane_watcher_treekill.ps1`, and that proof stands. But what
stopped the `glm` and `pilotcaps` lanes on 2026-10-15 was not the kill. It was a
chain of five links:

| # | link |
|---|------|
| 1 | the timeout ran `Stop-Process -Force` on the `cmd.exe` wrapper |
| 2 | `claude` survived, still holding the brief open as its inherited stdin |
| 3 | `Move-Item` into DONE threw, because of that handle |
| 4 | `$ErrorActionPreference = "Stop"` made the throw terminating |
| 5 | nothing caught it, so the script left its own `while ($true)` loop |

**The live logs carry the signature of link 5 exactly.** Re-read at
2026-10-15 22:49 from `resonate-ops\logs`:

    watcher-glm.log:165        [15:12:37] START 0065-fix-the-halt-in-the-foreground.md
    watcher-glm.log:166        [16:42:37] TIMEOUT after 90 minutes, killing the process
    watcher-glm.log:174        [21:07:10] watcher up.          <- next line. 4h25 later.

    watcher-pilotcaps.log:415  [16:02:10] START 0130-certify-the-halt-fix.md
    watcher-pilotcaps.log:416  [17:32:10] TIMEOUT after 90 minutes, killing the process
                                          <- last line in that block.

No `DONE`, no `MOVED`, no `watcher down.`, no `UNHANDLED`. The `TIMEOUT` line is
the last thing each lane ever said.

---

## 2. The injection points

`docs/ops/lane_watcher.ps1`, +54 / -7. Every new parameter defaults to the value
that was hardcoded, so **nothing about a live run changes**.

| parameter | default | why |
|---|---|---|
| `-Ops` | `C:\Users\Zvonimir\Desktop\resonate-ops` | carries queue, RUNNING, DONE, logs, the LANE file, the STOP files and the tree-kill module with it — one parameter moves the whole blast radius |
| `-TaskExecutable` | `cmd.exe` | |
| `-TaskCommandTemplate` | `/c claude -p --permission-mode {MODE} < "{BRIEF}" > "{OUT}" 2>&1` | `{BRIEF}` appears as the **stdin redirect**, which is link 2 |
| `-TreeKillPath` | `""` → under `$Ops` | a test points it at the repository's own module, so the code under review is the code in the chain |
| `-TaskTimeoutMinutes` | `150`, now `[double]` not `[int]` | an integer floor of one minute put the timeout out of reach of any test that has to finish |

**The default command line is byte-identical to the one it replaces.** Proven,
not asserted:

    old: /c claude -p --permission-mode bypassPermissions < "C:\q\RUNNING\0110-x.md" > "C:\l\task-qwen-1.out" 2>&1
    new: /c claude -p --permission-mode bypassPermissions < "C:\q\RUNNING\0110-x.md" > "C:\l\task-qwen-1.out" 2>&1
    IDENTICAL (-ceq): True

`[double]` changes no existing call either: `150` is still `150` and
`-TaskTimeoutMinutes 90` still means 90.

Three lines were added to the banner, and they are not decoration. A watcher
pointed at a scratch queue and a fake task is **indistinguishable in the process
table** from one pointed at the live queue and `claude`. The log is the only
place that can tell them apart, so it now names `ops=`, `queue=`, `lanefile=`,
`task=` and `treekill=`. Without that, a test result and an estate measurement
leave the same record.

---

## 3. The fake task

`docs/ops/fake_lane_task.ps1`, new. It does the three things the chain depends
on, and **it takes its mode from the brief, not from a switch** — the watcher
takes one task command for its whole life, so a harness that needed three
behaviours would otherwise need three watchers, and *"the loop is still running
after the timeout"* cannot be proven by a watcher that only ever ran one task.

    exit0    grows the lane file, exits 0                     -> exit0
    nowork   exits 0 having written nothing to the lane file   -> NOWORK
    hang     sleeps past the deadline, no children             -> TIMEOUT
    orphan   hangs, and leaves a grandchild that OUTLIVES its  -> TIMEOUT
             parent and holds the brief open

`orphan` is the one that matters, and it reproduces both halves of what
`taskkill /T` cannot do:

- The grandchild's parent **exits first**, so the grandchild is invisible to a
  walk of live parent links.
- The grandchild **opens the brief** with `FileShare::Read` and no `::Delete`,
  which is what a reader that was never asked about renaming gets, and is why
  the rename threw. The real task held that handle by inheriting stdin; a
  `Start-Process` child cannot inherit one, so it is opened by name. The handle
  is the link under test, not the way it was acquired.

Every generation writes its pid to a marker file, so the harness asserts on
**identities**, never on a `CommandLine` substring — the filter that killed TASK
0070's own measurement shell.

---

## 4. The run

`docs/ops/test_lane_watcher_endtoend.ps1`, new. One watcher process, three
briefs, in filename order, **timeout first** so that everything after it is
evidence the loop survived it.

    > powershell -File docs\ops\test_lane_watcher_endtoend.ps1

Measured 2026-10-15 22:50-22:51 - **36 assertions, 0 failures, exit 0** - with
the pids and DONE filenames from that run. (The first run that carried the whole
chain was 22:47-22:48 and reported 31/1; the single failure was my own
assertion, corrected in section 5.)

    PASS  watcher started
    PASS  scratch is named in the log
    PASS  the fake task is the command, not claude

    --- LEG 1  TIMEOUT with a grandchild that outlived its parent ---
    PASS  leg1 dispatched
    PASS  three generations ran                     root=79936 parent=59652 child=72164
    PASS  the grandchild holds the brief open
    PASS  the child is a real orphan                parent exited, child still alive
    PASS  the orphan reached the kill set
    PASS  TIMEOUT logged
    PASS  kill verified, zero survivors             KILL VERIFIED: 0 of 3 still alive
    PASS  the fake task's own root is in the kill set     kill set = 72164,79936,88656
    PASS  the orphan is in the kill set             orphan=72164
    PASS  the already-dead parent is NOT in the kill set  parent=59652 had exited
    PASS  taskkill /T could not reach the orphan    2 terminations, neither was 72164
    PASS  the sweep is what killed the orphan
    PASS  every descendant is dead                  0 of 3 still alive, by pid
    PASS  DONE -> TIMEOUT written
    PASS  Move-Item succeeded
    PASS  no move was left blocked
    PASS  the brief is in DONE, suffixed TIMEOUT    20261015-225043-TIMEOUT-0010-orphan.md

    --- LEG 2  NOWORK, through the same Move-Item link ---
    PASS  the loop survived the timeout and took the next brief
    PASS  NOWORK detected
    PASS  DONE -> NOWORK written
    PASS  Move-Item succeeded (NOWORK)
    PASS  the brief is in DONE, suffixed NOWORK

    --- LEG 3  clean exit, through the same Move-Item link ---
    PASS  the loop is still running after two failures
    PASS  DONE -> exit0 written
    PASS  Move-Item succeeded (exit0)
    PASS  the lane file grew                        29 -> 72 bytes
    PASS  the brief is in DONE, suffixed exit0

    --- THE LOOP ---
    PASS  the watcher went idle on an empty queue
    PASS  the watcher process is still alive
    PASS  the watcher never logged an unhandled error
    PASS  three briefs consumed, three DONE files
    PASS  RUNNING is empty
    PASS  STOP-<lane> stops it cleanly

    passed 36   failed 0        EXITCODE=0

**The assertion that would have caught 2026-10-15 is `the loop survived the
timeout and took the next brief`,** and it is asserted by WORK rather than by
liveness. A process still in the table could be stuck anywhere; a watcher that
consumes two more briefs is running its loop.

### The kill, in the watcher's own words

Quoted from the 22:47 run, so the pids are that run's, not 22:50's:

    TIMEOUT after 0.2 minutes. Killing the whole process tree of pid 72584;
      4 process(es) were seen under it during the run.
    ORPHAN still alive and added to the kill set: pid 73392 (powershell.exe)
      - it was seen below the root in an earlier sample and taskkill /T cannot
      reach it, because its parent is gone
    KILL SET before (3): 72584:cmd.exe 73392:powershell.exe 79076:powershell.exe
    taskkill: SUCCESS: The process with PID 79076 ... has been terminated.
    taskkill: SUCCESS: The process with PID 72584 ... has been terminated.
    sweep round 1: 1 survivor(s): 73392:powershell.exe
    KILL VERIFIED: 0 of 3 still alive. after: (empty)

`taskkill` named **two** terminations and **neither was the orphan**. The sweep
found it on round 1. That is the module's central claim, and it is now a
measurement rather than an argument — the harness asserts both halves directly.

---

## 5. Three things this harness got wrong first, and what each one cost

A harness whose assertions have never been seen to fail is not evidence, so
these are recorded rather than quietly fixed.

**1. The task template did not survive `-ArgumentList`.** The first run produced
a watcher that logged **not one line** and three briefs that were never claimed.
`Start-Process` wraps an argument containing spaces in double quotes, and the
template contains its own quotes — around `{BRIEF}` and `{OUT}` — which
terminate that wrapper early. Fixed by launching through a generated launcher
script that puts the template in a single-quoted PowerShell literal. The harness
now also **fails fast**: if `watcher up.` never appears, or if the watcher pid
disappears while a line is being waited for, it aborts instead of grinding
through twenty 90-second waits. Eight minutes of the first attempt were spent
waiting on a process that had exited after nineteen seconds, which reads as slow
rather than as broken.

**2. The brief was one line, not four.** All three legs exited 9 twice in a row.
The cause was **not** `Set-Content` and **not** `-join`, which is what my first
comment on it said:

    @("# SCRATCH BRIEF - " + $name, "MODE: " + $mode, "", $body)

is not a four-element array. In PowerShell the comma binds **tighter** than
`+`, so this parses as one string concatenated with an array, which is then
flattened with `$OFS` — a space. 22 + 12 + 0 + 9 = 43 characters of content came
out as 46, three one-character separators rather than three CRLFs. Every element
is now parenthesised, and `Brief` throws if the result has fewer than four
lines. The fake task's refusal now also prints the bytes it read with `<CR>` and
`<LF>` marked, because a refusal that does not name what it refused cost a whole
run to diagnose.

**3. `N >= 4` was the wrong assertion, and the code was right.** It failed at
`N=3`. `orphan-parent` had already exited when the deadline fired, and the
module adds only processes still **alive** to a kill set — a dead process is not
a survivor and does not belong in one. This was my own version of the mistake
the standing rules name: a baseline compared by count instead of by name. The
assertion is now pid membership — root **in**, orphan **in**, already-dead
parent **out** — plus the two direct claims about `taskkill` and the sweep.

### The control, and what it proved on its own

`-SabotageKill` swaps the tree-kill module for a stub that reports
`Verified = $true` and kills nothing. Run at 2026-10-15 22:49-22:52 against the
same three briefs:

    [22:49:57] STUB KILL: pretending. Nothing was stopped.
    [22:50:27] MOVE BLOCKED (The process cannot access the file because it is
               being used by another process.) - retrying for 30s
    [22:50:57] MOVE STILL BLOCKED after 30s. 0010-orphan.md stays in RUNNING, so
               this lane will idle on it and say so every 3s. The DONE line
               above is the authority that the task ran. NOT exiting.
    [22:51:21] a task is already in RUNNING: 0010-orphan.md, not starting another
               ... (repeating every 3s)

    FAIL  the orphan reached the kill set
    FAIL  kill verified, zero survivors        no VERIFIED line; got STUB KILL
    FAIL  every descendant is dead             STILL ALIVE: root=1764, orphan=75828
    PASS  TIMEOUT logged
    PASS  DONE -> TIMEOUT written

This is better evidence than a control is usually asked to give, because it
reproduces **link 3 directly rather than by analogy**. The orphan's handle on
the brief really does make `Move-Item` fail, with the exact message the glm and
pilotcaps logs carried. And the two links 0090 fixed SEPARATELY from the kill
are visible holding on their own: `DONE -> TIMEOUT` was still written, and the
watcher **did not leave its loop** - it idled on the stranded brief and said so
every three seconds, which is what the pre-0090 script could not do.

The run ended **12 passed, 20 failed, exit 1**, against 36/0 for the real
module. So the PASS column means something: removing one module turns twenty
assertions red, and the ones that stay green - TIMEOUT logged, DONE written, the
loop alive - are exactly the ones 0090 fixed independently of the kill.

(That run predates the `N >= 4` correction above, so its output still shows the
old count-based assertion among the failures.)

---

## 6. Is 150 still the right number?

**Re-measured, not restated.** `measure_durations.py` parsed all seven
`watcher-*.log` files at 2026-10-15 22:49, pairing `START`/`DONE` strictly on
the watcher's own `[timestamp] [lane] ` prefix — each log also contains the
appended stdout of every task, and task prose quotes the words START and DONE
freely.

    paired START/DONE    77          (0090 measured 72; five more have closed since)
    median               16.9 min
    mean                 19.5 min
    longest              64.3 min    glm 0060, exit0
    over 60 min          1 of 77
    over 77 / 90 / 120 / 150 min     0 of 77

    by outcome           exit0 60    exit<n> 15    NOWORK 2    TIMEOUT 0

### That `TIMEOUT 0` is the finding

0090 reported that the cap bound on exactly two tasks, `glm 0065` and
`pilotcaps 0130`, both at exactly 90:00. Both are real — and **neither is a
paired record**. Each appears in its log as a `START` with no `DONE`, because
the watcher died at the `TIMEOUT` line before writing one (section 1).

So **every duration statistic built from paired records structurally excludes
every task the cap has ever bound.** 64.3 minutes is the longest task that
*survived*; it is not the longest task. The distribution that justified 150 is a
distribution of survivors, and that is a property of the defect, not of the
sample.

### Was 150 chosen against a floor that does not exist?

No — and if anything the floor was named too **low**. 0090 justified 150 against
the observed suite pair, 2267.7s + 2355.3s = 77.0 min. But CLAUDE.md's standing
figure for the suite is **2100-2720s alone**, and the upper end doubled is
5440s = **90.7 minutes of suite time alone**, before any reading, diffing or
writing. On top of that, `scripts/run_suite.py` takes a **machine-wide FIFO
lock** and a second full run WAITS: with seven lanes, a task needing a suite can
sit behind another lane's holder for up to a full suite before its own first leg
begins. One such wait on a worst-case pair is 90.7 + 45.3 = **136 minutes**,
which leaves 14 of the 150 for everything else the task does.

### Recommendation

**Keep 150. Do not lower it, and do not raise it.**

- Lowering it is not supported. The measured cost of the raise is zero: of 77
  records, zero genuine hangs, and the longest survivor is 64.3 min — no task
  that would have finished under 90 now runs longer. The only two tasks the cap
  ever bound were two-leg suite runs doing real work, not hangs.
- Raising it is not supported either. 150 already clears the documented worst
  case without lock contention, and the residual gap is **not closable by a
  number**: a lane waiting on another lane's suite lock is a scheduling fact,
  not a duration.
- **No single number serves both shapes of work.** A 17-minute median task and a
  lock-contended two-leg suite pair do not belong under the same cap. The clean
  next step is per-brief rather than per-watcher: a `TIMEOUT:` line in the brief,
  read exactly the way the fake task now reads `MODE:`, at the same place in the
  same loop. **I have not implemented that** — it changes how briefs are written,
  which is the operator's call, and the FOCUS RULE says it is filed, not started.
- **Re-ask this question in a week.** Once the fix is live, a timeout produces
  `DONE ... -> TIMEOUT` and a `*-TIMEOUT-*.md` file in DONE, so "how often does
  the cap bind" becomes answerable from the logs. Today it is not, and my 77
  records are survivors.

---

## 7. State, and what is NOT done

**The 0090 fix is on disk and NOT live.** Measured 2026-10-15 22:27:

    resonate-ops\tools\lane_watcher.ps1       mtime 22:20:25   sha256 8c9c9777...
    resonate-ops\tools\lane_watcher.NEW.ps1   mtime 22:20:25   sha256 identical
    qwc\docs\ops\lane_watcher.ps1 (at 566081c6e)               sha256 identical

The operator deployed the file. But all seven watcher processes started at
**21:07:08**, before it was replaced, and PowerShell 5.1 parses a script at
launch and never re-reads it — which 0090 measured directly. The authority is
each log's own banner, and the qwen one still says:

    [2026-10-15 21:07:10] [qwen] watcher up. ... timeout=90m

So the live watchers are still running the pre-0090 bytes, with a 90-minute
timeout that kills the wrapper only. **Taking the fix needs a per-lane restart,
which is the operator's, and `STOP-<lane>` never interrupts a running task.**
`lane_treekill.ps1` is **not** in `resonate-ops\tools\` yet, and the new watcher
REFUSES to start without it — so the restart must copy both files, not one.

Not done, deliberately: nothing deployed, no watcher started, stopped,
restarted or edited; no `STOP` file written anywhere outside the scratch root;
the live `resonate-ops\queue` never read as a queue and never written; no push,
no merge, no master commit; no provider, Apify, Slack or network call; no suite
run and `work/suite.lock` not taken; no campaign read or written; no other
lane's worktree touched.

Every process this task killed was one its own fixtures started, selected by a
pid recorded in a marker file. The harness's `finally` block kills the watcher
it launched and any marker pid still alive, and removes the scratch root.

### TASK 0100 — the record, not the work

Filed here because it is a lane fact and the lane file is the authority.
`8ff64efb9` carries 0100's 473-line report and the work is real, but
`LANE-qwen.md` has no 0100 entry, so the watcher logged at 22:22:56:

    NOWORK: exit 0 but LANE-qwen.md did not grow. Treating as a failure, not a completion.
    DONE  0100-apify-spend-is-invisible.md -> NOWORK

That is the guard working correctly on a task that did its work. **0100 is DONE
as work and lost as record**, and per the standing rules a brief moved to DONE
is gone — re-queueing the record is a file somebody has to write.
