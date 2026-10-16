# TASK 0200 — a RUNNING brief whose owner is dead must not stop the lane

Measured and built 2026-10-16 by the `qwen` lane, in `C:\Users\Zvonimir\qwc`
(an LF tree), on branch `task-qwen-0090-watcher-treekill-2026-10-15`.
`origin/master` is `b1f290c84` and was not touched.

---

## FOR THE OPERATOR — what you will see, where the brief goes, what you decide

**The one-line summary: a lane that loses its watcher mid-task will now clear
itself and carry on, and the brief it was holding will be waiting for you in
`DONE\` with `ORPHANED-NEEDS-REVIEW` in its name.**

**What you will see in `logs\watcher-<lane>.log`**, once, at startup, when it
fires:

    ORPHAN CHECK: 0170-the-two-free-suite-lock-wins.md was claimed by a watcher
      that is GONE. pid 66028 is absent from a process table that does contain
      this reader, so the claiming watcher is gone.
    ORPHAN CHECK: moved it to 20261016-121314-ORPHANED-NEEDS-REVIEW-0170-the-two-
      free-suite-lock-wins.md and taking the next brief. THE ORPHAN IS NOT
      RE-RUN: on 2026-10-15 two killed tasks wrote complete lane entries 24 and
      64 minutes AFTER their kill, so a re-run would put a second task on a
      worktree the first may still be writing to. A human decides whether its
      work landed by reading LANE-<lane>.md.
    startup: RUNNING is clear and this lane can consume work again
      (was 0170-..., verdict DEAD)
    START 0175-the-refusal-that-eats-a-brief.md

**Where the brief goes.** To `queue\<lane>\DONE\`, under
`<stamp>-ORPHANED-NEEDS-REVIEW-<original name>`. It is **never put back in the
queue**, and the reason is in the log line above: the `claude -p` child outlives
the wrapper a timeout kills, so a re-run would start a second task in a worktree
the first may still be writing to. The two tasks killed on 2026-10-15 at 23:05
wrote complete lane entries at 23:29:50 and 00:09:10 — 24 and 64 minutes after
their kill.

**What you decide.** Only one thing, and only when you have a minute:
**did the orphan's work land?** Read `LANE-<lane>.md` for an entry naming that
task. If there is one, the work is done and the file in `DONE\` is just a
receipt. If there is none, the task needs re-queuing **as a fresh brief**, and
whoever writes it should check the lane's worktree and `git log` first — the
orphan may have left commits, as `qwen/0170` did. `qwen/0171` is the worked
example of exactly that read.

**The other line you may see, and what it means.** If the brief in `RUNNING\`
cannot be attributed, nothing is moved:

    ORPHAN CHECK: CANNOT DECIDE who owns 0170-....md, so it is LEFT ALONE and
      this lane will idle on it. no claim sidecar beside the brief, so its owner
      cannot be identified. This is the legacy case ... UNKNOWN is not dead.
    ORPHAN CHECK: a human resolves it with one command, and should read
      LANE-<lane>.md first in case the work already landed:
      Move-Item '...\RUNNING\0170-....md' '...\DONE\<stamp>-ORPHANED-NEEDS-REVIEW-0170-....md'

That is the behaviour this estate has today, with a log line that says so and
hands you the command. **It applies to every brief that is in flight when this
is deployed**, because those briefs were claimed before the sidecar existed. It
is self-limiting: every brief claimed after the deploy is decidable.

**AND THE ONE THING THAT CAN BITE YOU: THE DEPLOY IS FOUR FILES AND THEY GO
TOGETHER.** `tools\lane_watcher.ps1` now **refuses to start** — exit 2, with a
line saying which file is missing — unless `tools\lane_treekill.ps1`,
`tools\lane_refusal.ps1` and `tools\lane_orphan.ps1` are all beside it. That is
deliberate (a watcher that silently fell back to idling on an orphan forever
would be the defect), but it means **copying the watcher without the modules
stops every lane you restart.** Measured state of `resonate-ops\tools\` at
2026-10-16 12:3x:

    lane_treekill.ps1    present
    lane_refusal.ps1     ABSENT
    lane_orphan.ps1      ABSENT
    lane_watcher.ps1     md5 2e56e3b0a8b14571a6c205af5d01110d, 20,048 B,
                         mtime 2026-10-15 22:20 - and it requires NEITHER module,
                         so it is the pre-0175 bytes

So the live estate is running a watcher from 22:20 last night, and the work from
`qwen/0175` (the refusal that eats a brief) and this task is in the repository
and **not deployed**. Deploying is yours; nothing here deploys itself.

---

## What was built

Three files in the repository, none of them in `resonate-ops\tools\`:

    docs\ops\lane_orphan.ps1          the module      the resolver and the sidecar
    docs\ops\test_lane_orphan.ps1     the harness     67 legs, two parts
    docs\ops\mutate_lane_orphan.py    the proof       13 mutations

and four small changes in `docs\ops\lane_watcher.ps1`: an `-OrphanModulePath`
parameter, the dot-source with the refuse-on-missing contract, the startup
resolution before the main loop, and the sidecar write at claim time with its
removal on both paths where a brief leaves `RUNNING\`.

### The sidecar

At claim time, beside the brief and never inside it:
`queue\<lane>\RUNNING\<brief>.md.claim`, holding the claiming watcher's lane,
pid, **creation-time key**, process name and claim time. Beside, because the
brief is fed to the task on stdin and must stay byte-identical to what the queue
held; `.claim` rather than `.md` so the watcher's own `*.md` filters never see
it as a brief.

The write is **best-effort by design** and the watcher logs it if it fails. A
watcher that refused to start a task because a sidecar could not be written
would be a new way to stall a lane, which is the defect being fixed.

### Liveness is pid PLUS creation time, and that is not what the brief asked for

The brief says to use the watcher's own two-part test — pid and process name —
or to say why something else is better. Something else is better, for a reason
specific to this estate: **all seven watchers are `powershell`.** A recycled pid
that lands on another lane's watcher passes pid-plus-name and would be read as
"my claimer is still alive", which here is the fail-OPEN direction: the lane
stays stalled on a brief whose real owner is gone.

`lane_treekill.ps1` already has the right identity and said so first:

    # The identity of a process is pid PLUS creation time. A pid on its own is
    # a slot number that the OS reuses.
    function Get-LaneProcKey

So the sidecar records `Get-LaneProcKey`'s value and liveness is a key
comparison. A pid still present whose creation time differs is a **provably**
different process. Mutation M2 removes that comparison and leg A4 goes red.

### UNKNOWN is not dead

Every undecidable input returns UNKNOWN, and UNKNOWN leaves the brief exactly
where it is with a log line naming the one command a human runs:

    no sidecar (the legacy case)        UNKNOWN   leave alone
    an unreadable sidecar               UNKNOWN   leave alone
    a sidecar with no pid               UNKNOWN   leave alone
    a process table that will not read  UNKNOWN   leave alone
    a table that comes back empty       UNKNOWN   leave alone
    a table without this reader's pid   UNKNOWN   leave alone
    no key, and the pid is now a shell  UNKNOWN   leave alone

Catalogue entry 4 is `suitelock._alive` reading an unreadable process table as
dead. Mutation M1 makes UNKNOWN fall through to the move and five legs go red.

**The legacy case is UNKNOWN on purpose, and here is the defence.** A brief with
no sidecar is indistinguishable from two sides: a watcher on older bytes working
perfectly, or the orphan this exists to clear. The destructive error is a second
`claude -p` on a live worktree, and **"no live watcher" does not mean "no live
task"** — the 24 and 64 minute figures are exactly that. A human clearing one
file is cheap and reversible; a wrongly-moved brief plus a double-run is not.
The named falsifier, if the legacy stall ever becomes expensive enough to pay
for: walk the process table for a task process whose working directory is this
lane's worktree. That is a real measurement and it is **not built here**.

---

## Two defects this found in its own code, both before anything shipped

**1. Two sources for one number, four ticks apart.** The sidecar's key was first
written from `Get-Process .StartTime` and compared against
`Get-LaneProcTable`'s key, which is CIM `.CreationDate`. Measured on one live
process:

    Get-Process .StartTime     639277492085811234
    CIM         .CreationDate  639277492085811230     4 ticks earlier

because CIM truncates to microseconds while .NET keeps 100ns. **The keys could
therefore never match, so a LIVE claiming watcher would have read DEAD and its
brief would have been moved aside under it** — the fail-open direction. Fixed by
making the table the only source on both sides. Mutation M7 restores the bug and
leg A13 goes red. The delta is also *variable*: measured 1, 3 and 2 ticks on
three consecutive runs, which matters below.

**2. PowerShell's comma binds tighter than `+`, and this estate has now paid for
it three times.**

    @("a=" + $x, "b=" + $y)      parses as      "a=" + ($x, "b=") + $y

and collapses the whole list into ONE space-joined string. It wrote the sidecar
as a single line, so every field after the first was unparseable and the claim
read back with no pid — a live watcher's brief became undecidable instead of
ALIVE. It then did it again in this harness's own brief builder, which made
`fake_lane_task.ps1` refuse with exit 9. **And `fake_lane_task.ps1` carries a
comment at line 114 recording the same trap costing an earlier harness a whole
run**: *"the cause was a brief whose four lines had been written as one"*.

Three authors, same trap, one of them the file that documents it. Proposed, not
applied: one line in the failure-family catalogue. Mutation M9 removes the
parentheses again and leg A13 goes red.

---

## The harness: 67 legs, and why it is in two parts

    PART A   34 legs   the resolver with the process table INJECTED
    PART B   33 legs   real watchers against a real scratch queue
                       67 passes, 0 fails, exit 0

**Part A injects the table** because that is the only way to test a decision
about a process that does not exist, a recycled pid, a table that will not read
and a table that comes back empty. Every leg asserts the **verdict** and the
**action** separately, because "did not move the brief" is true of both ALIVE
and UNKNOWN and they are not the same answer.

**Part B runs real watchers**, because the thing that has to work is the
watcher, not the function. It covers the four states the brief names:

    B1  dead owner      -> moved aside, and THE NEXT BRIEF STARTED
    B2  live owner      -> untouched, and the second watcher refused (exit 3)
    B3  live owner with the pid lock deleted by hand
                        -> the sidecar alone reads ALIVE and the brief is left
    B4  no sidecar      -> CANNOT DECIDE, left in RUNNING, lane idles visibly
    B5  garbage sidecar -> CANNOT DECIDE, left in RUNNING
    B6  module missing  -> the watcher refuses to start, exit 2

**B3 is the leg that justifies the sidecar's existence.** The pid lock already
tells a starting watcher whether another is alive — but the lock can be deleted
or overwritten, and then it says nothing. With the lock gone, the sidecar still
proves the claimer is alive and the brief survives.

**B2 and B3 assert their own window.** They are about a LIVE owner, so every
assertion in them is void if the task has already finished and its brief has
legitimately moved on. The harness waits for the task to say it is working and
re-asserts, before and after, that it has not finished. The first run of this
harness failed exactly there — four legs read as defects when the code was
right.

**Two harness-construction defects worth recording**, because both read like the
code under test failing:

- `Start-Process -ArgumentList` **does not quote**, so
  `-TaskCommandTemplate` (which contains spaces) was split into a dozen
  positional arguments, bound to the watcher's typed parameters, and the watcher
  refused with *"Cannot convert value "powershell.exe" to type "System.Int32" on
  parameter MaxConsecutiveFailures"*. `test_lane_drain_premise.ps1` already
  avoided this by writing a launcher `.ps1`; this one now does the same.
- `$args` is an automatic variable. Binding it inside a function was the first
  thing suspected and was **not** the cause — recorded so the next reader does
  not re-suspect it.

---

## The mutation proof: 13 mutations, every named leg red

    py -3 docs/ops/mutate_lane_orphan.py --baseline

    M1   UNKNOWN treated as dead                      KILLED by A2,A6,A7,A9,A11
    M2   the creation-time key is not compared         KILLED by A4
    M3   the empty-table guard removed                 UNKILLABLE AS DECLARED
    M3b  the empty-table AND self-pid guards removed   KILLED by A8,A9
    M4   the self-pid sanity check removed             KILLED by A9
    M5   the orphan is RE-QUEUED instead of moved      KILLED by A3
    M6   the moved file is not named for review        KILLED by A3
    M7   the key taken from Get-Process again          KILLED by A13
    M8   the sidecar is left behind                    KILLED by A3
    M9   the parentheses come off the sidecar lines    KILLED by A13
    M10  the move is skipped, MOVED still reported     KILLED by A3
    M11  the startup resolver is never called          KILLED by B1
    M12  the claim sidecar is never written            KILLED by B2,B3

**M3 is declared unkillable and that is a result, not a pass.** Removing the
empty-process-table guard leaves every leg green, because the very next guard —
*this table does not contain my own pid* — catches the same input. The
empty-table check is therefore **subsumed: it cannot be the guard that fires.**
It is kept because its message names the actual condition, and M3b proves that
removing both guards does go red. An unkillable mutation that is explained is
information; one quietly dropped from the list is how a guard with no red state
survives, which is catalogue family 1.

**M11 and M12 mutate the WATCHER, not the module**, so the proof covers the
wiring and not only the function. M11 also reddens B3, B4 and B5 and M1 also
reddens A8 — a mutation taking down more than its own requirement is reported
rather than hidden.

**One flaky assertion was found and removed, not retried.** An earlier A13 leg
asserted that the `Get-Process` key *differs* from the CIM key. The gap is CIM's
truncation, so it is 0 to 9 ticks depending on where the creation time landed —
measured 1, 3 and 2 on three consecutive runs — and a delta of 0 is perfectly
possible. It went red once inside a mutation run and the mutation was briefly
blamed. The requirement is the leg beside it (*the sidecar key IS the table's
key*), so the delta is now **printed as INFO and not asserted**. Part A then ran
green three times in a row.

---

## What is NOT built, and the interaction worth knowing

- **Nothing was deployed.** See the operator section.
- **No real lane was restarted, stopped, rotated or read for write.** No real
  `STOP-<lane>` or `STOP-ALL` was created: the harness asserts its STOP path is
  outside the live estate before writing it, and refuses if it is not.
- **The resolver cannot tell "ran, but the move failed" from "never ran, and the
  return was refused".** Both leave a brief in `RUNNING\` on purpose
  (`MOVE STILL BLOCKED`, `RETURN REFUSED`, `RETURN STILL BLOCKED`), and after
  that watcher exits the next one will see a dead owner and move the brief aside
  as `ORPHANED-NEEDS-REVIEW`. The **log** is the authority for which happened —
  a `DONE` line means it ran — and the filename says a human must look. Writing
  the outcome into the sidecar would make the distinction cheaper and was
  **deliberately not built**: the log already holds that truth, and a second
  representation of it is how two states drift.
- **One `claude -p` per worktree is still not enforced anywhere.** This task
  stops the watcher from *causing* a double-run; nothing prevents one.
