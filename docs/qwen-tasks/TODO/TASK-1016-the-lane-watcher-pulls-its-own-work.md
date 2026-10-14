PRIORITY: P1
DEPENDS:
TIMEBOX: 180 minutes. The six refusals in THE QUESTION are the gate; they come
before the happy path. If you are not green on requirements 1-7 at 120 minutes,
stop building the loop, write what you measured under FINDINGS, commit, move
the file to REVIEW/ and stop. A watcher that runs tasks but cannot refuse is
worth less than no watcher at all.

# TASK-1016 - the lane watcher pulls its own work

## WHERE THIS SITS

Today the operator drives the lanes by hand. `docs/HANDOFF-2026-10-01-LIVE.md`
section 4 lists six lanes in flight, each one a terminal tab, and each tab is
fed by the operator pasting a line into it. Six tabs, one paste per task, and
the operator is the scheduler. He wants the lane to pull instead: a watcher
sits in the lane's own worktree, takes the next file out of `queue/<lane>/`,
runs it, records what happened, and takes the next.

**This task writes that watcher and its tests. It does not install it and it
does not run it.** No cron entry, no Scheduled Task, no `start`, no shortcut,
no edit to any existing launcher, and no invocation against a real lane
directory. The deliverable is a reviewed script plus a test module that proves
the refusals. Installation is a separate operator decision, and it is his.

### The reason this is a careful script and not a ten-line loop

A ten-line loop around `qwen.cmd` is twenty minutes of work, and this
repository has already paid for every one of the things it gets wrong:

- **Two workers on one task.** 2026-09-15: six of eight workers selected the
  same `TODO/` file, four produced the same answer, five were wasted. Reading
  a directory is not claiming anything - see `scripts/claim_task.py`'s module
  docstring, which is the written record of that day.
- **Six suites at once.** 2026-10-02: four launches, six concurrent runs, 3h42
  of waiting on a verdict that was only contending, and no result from any of
  them trustworthy. `src/suitelock.py` exists because of it.
- **A lock that serialised nothing.** The same day: the lock lived under
  `work/`, `work/` is gitignored, so every worktree had its own. Six runs in
  six trees took six different locks.
- **A live holder reported dead.** The same day again, twice: an empty lock
  file read as pid `None`, `None` read as dead, and a running suite's lock was
  unlinked. And `tasklist` typed into the Bash tool returns zero rows for every
  query, so a human reader called a live PID gone.

A puller touches all four of those at once. That is why this is a task with an
acceptance section and not a snippet.

## THE SHAPE, AND THE REASONS ARE THE SPECIFICATION

Write `scripts/lane_watcher.py`. Arguments, all of them explicit:

    --lane <name>          REQUIRED. The lane. Exact string, no globbing.
    --permission-mode <m>  REQUIRED. NO DEFAULT. See section 6.
    --queue-root <dir>     Optional override. Default resolves as in section 3.
    --max-tasks <n>        Optional. Stop cleanly after n tasks.
    --poll <seconds>       Optional. How long to sleep on an empty lane.
    --once                 Optional. Take at most one task and exit.

### 1. One task at a time per lane, and a RUNNING marker makes double-start impossible

Mutual exclusion is a **marker whose creation exactly one racer can win**, not
a directory listing. `os.open(path, O_CREAT | O_EXCL)` is the primitive that is
atomic on both Windows and POSIX, and it is already wrapped, hardened and
tested in this repository.

**Use `src/suitelock.py`. Do not write a second lock.** CLAUDE.md: *prefer
canonical state to a second representation of it*, and *no abstraction with one
caller*. `suitelock` already takes the path as a parameter and already carries
the three fixes a hand-rolled marker would have to rediscover:

    suitelock.acquire(file_path=<marker>, timeout=0, say=<your log sink>)
        -> returns the payload on success
        -> raises suitelock.SuiteBusy when a LIVE holder has it
        -> takes over a marker whose PID is gone, loudly, by itself
    suitelock.read(file_path=<marker>)
    suitelock.release(file_path=<marker>)      # only if THIS pid holds it

What you get for free, and what you would otherwise have to get wrong first:
the marker is published by staging and HARD-LINKING, because `O_CREAT|O_EXCL`
plus a separate write leaves the file briefly EMPTY (`_write_in_place`,
`DAMAGED_GRACE`); a marker whose content cannot be READ counts as ALIVE for 30
seconds rather than dead; `_alive` shells `tasklist` through `subprocess`,
which answers correctly, and treats an unknown answer as alive because waiting
costs time and stealing costs a corrupted run.

Three things you must handle yourself, and each is a requirement:

- **`timeout=0` is the whole point.** A lane watcher that WAITS for the other
  watcher has two watchers alive on one lane a few minutes later. It must
  refuse and exit with a distinct code. Do not pass a positive timeout.
- **Pass your own `say=`.** Every message in `suitelock` says `suite.lock:` and
  "one full suite runs on this machine at a time". An operator reading that in
  a lane log will go looking for a test suite. Route it into your log under the
  lane's own prefix.
- **`release` in a `finally`.** It already refuses to delete somebody else's
  marker, so a restarted watcher cannot unlink the marker of the watcher that
  took over from it. Rely on that; do not add your own pid check on top.

If, after reading the module, you find a measured reason `suitelock` cannot
serve - not a style preference, a measurement - write it under FINDINGS with
the file:line that forbids it, and only then write a marker of your own
carrying all three properties above. **You may not edit `src/suitelock.py`
either way.**

### 2. Refuse the main checkout, and refuse anything that is not a worktree

The watcher runs in a lane's own worktree. Running it in the main checkout puts
an unattended agent in the tree that holds `master`, and
`docs/qwen-tasks/README.md` is explicit that Claude's tree and a worker's tree
must never be the same physical worktree.

The discriminator, and it is exact:

    git rev-parse --path-format=absolute --git-dir
    git rev-parse --path-format=absolute --git-common-dir

In the **main checkout** these two are the SAME path. In a **linked worktree**
`--git-dir` is `<common>/worktrees/<name>` and the two differ. That is the
test. Also require `--is-inside-work-tree` to be `true`.

Three ways this check can pass without having checked anything, and all three
must fail closed:

- git is not on PATH, the command errors, or it times out -> **REFUSE**. An
  unreadable authority is UNKNOWN, and CLAUDE.md invariant 0 says UNKNOWN never
  becomes PASS, idle or safe. An `except Exception: return True` here is the
  silent fallback on a safety path that CLAUDE.md names by name.
- git answers a RELATIVE path -> **REFUSE** rather than resolve it. `abspath`
  would resolve it against the caller's cwd, which is exactly the bug
  `src/store.py:983` and `src/suitelock.py:91` both carry a comment about.
- the two paths differ only by separator or case. Compare through
  `os.path.normcase(os.path.realpath(p))`. On this machine `C:\Users\...` and
  `C:/Users/...` are the same directory and `==` says they are not, so a naive
  comparison calls the main checkout a worktree and lets the agent loose in it.
  **This is the single most likely way to ship this broken, and a test must
  cover it.**

The check reads the **process working directory**. Not `--queue-root`, not an
argument, and not `__file__` - `__file__` describes the tree the script was
read from, and the operator can run a script from anywhere.

### 3. Where the queue lives, and why a missing lane is not an empty lane

The operator writes tasks into ONE place; six lanes in six worktrees read them.
So the default queue root cannot be relative: `queue/` under the lane's own
worktree is six different directories, which is precisely how the suite lock
serialised nothing. Resolve it beside the MAIN checkout, from

    git rev-parse --path-format=absolute --git-common-dir

the one path that is identical from the main checkout and from every worktree.
`src/suitelock.py:91`, `src/store.py:1011` and `scripts/glm_verify_branch.py:119`
all do this; read one of them rather than inventing a fourth.

**A missing or unreadable `queue/<lane>/` is a REFUSAL, not an empty queue.**
This is invariant 0 applied to the thing that decides whether the watcher does
anything at all: a directory that does not exist and a directory with no work
in it are indistinguishable from `len(os.listdir(...)) == 0`, and the
difference is "the operator has not set this lane up" versus "the lane is
caught up". The first must exit non-zero and say so; the second sleeps.
**The watcher never creates the queue directory.** Creating it would convert a
typo in `--lane` into a lane that silently never receives work and reports
itself healthy forever.

Selection order: **ascending filename sort, never mtime.** A `git checkout`
stamps every file with the checkout time, so mtime ordering reshuffles the
whole queue the first time anyone switches branches. Same rule as
`DEFAULT-CHECKS.md`: lowest-numbered first.

Record the lifecycle you choose for a file that has been run - moved to a
sibling directory, or renamed in place - and make it **a move, never a copy**,
per `docs/qwen-tasks/README.md`. A failed task must not be picked up again on
the next iteration: if it stays in the queue, the three-failure rule below
counts one broken file three times and the lane dies on a single bad input,
which is the opposite of what that rule is for.

### 4. Two kill files, checked before EACH task

    <queue-root>/STOP-ALL        stops every lane
    <queue-root>/STOP-<lane>     stops this lane only

Both live at the queue root, in the main checkout, so one `STOP-ALL` reaches
six tabs without the operator having to find six directories.

- Checked **before each task, including the first**, and before the marker is
  acquired. A watcher that checks only between iterations cannot be stopped
  before it starts.
- **Exact name match on the lane.** `STOP-email` must not stop
  `email-research`, and `STOP-email-research` must not stop `email`. No
  prefixes, no globs, no case folding. Windows filesystems are
  case-insensitive, so a test that only proves `STOP-email` stops `email`
  proves nothing about the prefix bug.
- **An unreadable stop file STOPS.** `PermissionError`, `OSError`, anything -
  the stop is the safe side. Fail closed.
- A stop is **logged with the file that caused it** and exits with a code
  distinct from a failure exit. "Stopped" and "broke" are different facts and a
  supervisor must be able to tell them apart without parsing text.
- A stop does **not** kill a task already running. The marker is released, the
  current task finishes, and nothing new starts. Say this in the `--help` text:
  a kill file is a brake, not an abort, and an operator who believes otherwise
  will drop a `STOP-ALL` and expect six running agents to die.

### 5. Three consecutive failures and it exits

A watcher that loops on a broken task burns an agent's quota all night and
produces nothing. So: **three consecutive failures and the process exits**,
with its own distinct exit code and a log line naming all three tasks.

- **Consecutive.** A success resets the counter to zero. A counter that never
  resets stops a healthy lane on its third unrelated failure of the day.
- A failure is: the task process exited non-zero, OR it could not be started at
  all, OR it exceeded a timeout if you implement one. All three increment.
- The threshold is a module constant with the reason written beside it, not a
  bare `3` inline.

### 6. THE PERMISSION MODE - a parameter, with NO unsafe default

`--permission-mode` is **required and has no default.** Not "defaults to the
safe one", not `default=None` with a fallback filled in later: argparse must
refuse to start without it, and there must be no string anywhere in the module
that supplies one.

**State this in the `--help` text and in the module docstring, in these terms:**
a mode that auto-approves everything removes the last checkpoint before a push.
It is the point at which a human sees what an agent is about to do to the
repository, and with it gone an unreviewed change reaches a branch with nothing
in between. **It must not be used while `master` is unprotected.** The repo's
own dispatch line is `qwen.cmd --approval-mode yolo`, which is exactly that
mode, and `docs/qwen-tasks/README.md` records that workers are dispatched with
it today - so this is a live hazard in this repository, not a hypothetical.

The watcher does not interpret the mode. It validates that one was given, logs
it on every task start, and passes it through. **Prove it is passed through.**
A parameter that is required, validated, logged and then dropped before the
command is built is this repository's single most recurring defect - a thing
computed correctly that nothing downstream reads. Assert on the argv actually
handed to the spawned process.

### 7. Every start, exit code and stop is logged with a timestamp

One append-only log. UTC, ISO 8601, with the `Z`, so two lanes' logs can be
merged and read in order. At minimum:

    watcher start   lane, permission mode, worktree, queue root, pid
    task start      timestamp, task file, permission mode, the argv
    task end        timestamp, exit code, duration, consecutive-failure count
    stop            timestamp, which kill file, how many tasks ran
    refusal         timestamp, which refusal fired, and why

**Flush every line.** CLAUDE.md's rule for the suite - *without `-v` a killed
run leaves nothing analysable* - is the same rule here: a watcher that buffers
has no log at the only moment anyone wants one, which is after it was killed.

Write to the log **and** to stdout, so the tab the operator is watching shows
what the file shows. Log the path of the log at startup; a log nobody can find
is scrollback.

## THE QUESTION

`tests/test_lane_watcher.py`. Nine requirements, six of them refusals, each RED
under a stated mutation. Import the script the way `tests/test_claim_task.py`
does, through `sys.path`, and exercise the real entry points.

1. **The main checkout is refused.** Build a throwaway repo with `tempfile`,
   run the check with cwd inside it, assert refusal. Then `git worktree add` a
   second tree, run with cwd inside THAT, assert it is accepted. Both halves
   are required: the refusal alone would pass against a function that refuses
   everything.
2. **A non-worktree is refused**, and so is a cwd where git fails. Assert the
   refusal when `git` returns non-zero, when it raises, and when it answers a
   relative path. Three separate assertions; they are three separate bugs.
3. **Separator and case do not defeat the comparison.** Drive the check with
   the main checkout's path given back in the other separator and in a
   different case, and assert it still refuses.
4. **Two watchers on one lane cannot both run.** Acquire the marker, then call
   the watcher's own acquire path again in the same lane and assert it refuses
   with the distinct exit code - and assert the FIRST marker is still on disk
   and still names the first holder. A second watcher that refuses but unlinks
   the marker on its way out has broken the lane for the first one.
5. **A dead holder's marker is taken over, and a live one is not.** Write a
   marker naming a pid that cannot exist; assert takeover, and assert the
   takeover is logged with the dead pid. Then write one naming the live
   `os.getpid()`; assert refusal.
6. **Both kill files stop, and neither over-reaches.** `STOP-ALL` stops lane
   `email`. `STOP-email` stops `email`. `STOP-email` does **not** stop
   `email-research`. `STOP-email-research` does **not** stop `email`. An
   unreadable `STOP-ALL` stops. The stop exit code differs from the failure
   exit code. Six assertions.
7. **A missing lane directory refuses and an empty one sleeps.** Two cases, two
   different outcomes, and the watcher creates neither directory - assert the
   missing one is still missing afterwards.
8. **Three consecutive failures exit; two failures and a success do not.** Both
   halves. Feed it a fake task runner you control. Assert the exit code, and
   assert the log names all three failed tasks. Then feed
   fail/fail/succeed/fail/fail and assert it is still running - that is the
   assertion that proves the counter RESETS, and without it a watcher counting
   cumulative failures passes the first half.
9. **The permission mode is required and reaches the argv.** Assert that
   invoking with no `--permission-mode` exits non-zero without running
   anything. Assert there is no default: `parser.get_default("permission_mode")`
   is `None` and the option is `required`. Then capture the argv of the spawned
   process and assert the mode you passed is in it, positionally where the
   agent CLI expects it. *A mode that is validated and dropped is the defect
   this requirement exists to catch.*

## THE TRAP

**Nothing in this test module may spawn a real agent.** Inject the runner -
take the command builder or the spawn function as a parameter, or patch it. A
test that launches `qwen.cmd` spends real quota and reaches a real model.
Assume you have no credentials.

**Nothing may touch the real `queue/` or the real `work/`.** Every test builds
its own tree under `tempfile` and points `--queue-root` at it. If a test leaves
a `STOP-ALL` anywhere outside its own temp dir, that test has stopped six
lanes. Use `tests/base.py` and `tests/envisolation.py` isolation; a test that
writes into `work/` is a defect in the test, not a pass.

**`git worktree add` inside a test is slow and it is still required.** The
main-versus-worktree distinction cannot be faked by stubbing `rev-parse`,
because the thing being tested IS the interpretation of what `rev-parse`
returns. Stub it for requirements 2 and 3; build a real pair of trees for
requirement 1. If the real pair makes the module slower than the repository
tolerates, say so in FINDINGS with the measured seconds - do not quietly drop
to a stub and report green.

**`tests/test_claim_task.py` shells git and had to restore `os.environ` at
MODULE scope**, because the code under test sets `GIT_AUTHOR_DATE` and
`GIT_COMMITTER_DATE` itself and leaked them into every module that ran after
it. Read its `setUpModule`/`tearDownModule` before you write yours.

**`config/.env` is not in a worktree.** It is gitignored, so a tree made by
`git worktree add` has none. Nothing in this script may need it - if your
watcher dies with `MissingKey` in a worktree, the watcher is wrong.

**A green test module is not the acceptance.** Fixtures get invented and then
mock the buggy function. Each of the nine requirements has a mutation below,
and a mutation that leaves every test green means the test does not test the
control. The correct result block says so rather than reporting green.

**Do not assert on the text of `scripts/lane_watcher.py`.** Assert on exit
codes, raised classes, argv contents, files present on disk and log lines. A
source grep fails when somebody writes a comment, which has happened here
repeatedly.

## WHAT YOU MAY NOT DO

- **Do not install it.** No cron, no Scheduled Task, no autostart, no edit to
  any existing launcher, no `.cmd` or `.ps1` wrapper, no line added to any
  dispatch doc telling anyone to run it.
- **Do not run it against a real lane.** Not once, not with `--once`, not "just
  to see". The only executions are inside the test module, against temp
  directories, with the runner injected.
- No provider call of any kind. No send, no campaign mutation, no killswitch
  semantics, no approval semantics, no write to `work/`.
- Do not edit `src/suitelock.py`, `scripts/claim_task.py` or any existing test.
- Do not create `queue/` or any lane directory in this repository. The
  directory does not exist on master today; the operator creates it when he
  decides to install this. Note under FINDINGS that `queue/` is **not** in
  `.gitignore` as of today, so a committed queue file would be public - that is
  a finding for the operator, not a change for you to make.
- Never commit copy text, an email address, a contact name or a domain.

## FILES ALLOWED

    scripts/lane_watcher.py          (new)
    tests/test_lane_watcher.py       (new)

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/    work/*.jsonl
    src/suitelock.py         src/killswitch.py  src/store.py
    scripts/claim_task.py    scripts/run_suite.py
    docs/state/              queue/             .gitignore
    every existing file under tests/, including tests/base.py and
    tests/envisolation.py - read them, do not change them

## ACCEPTANCE

**The module itself** - run it, read the exit code off the process, never
through a pipe:

    py -3 -m unittest tests.test_lane_watcher -v

Green, with every test running. **A skip is not a pass**; if a test skips,
report it as a skip and say what it would have needed.

**The full offline suite, zero new failures, diffed BY TEST NAME in both
directions** against a reference measured on the master you branched from:

    py -3 scripts/run_suite.py --offline -v

Read `CLAUDE.md` on this before you start. It queues behind `src/suitelock.py`,
which means **one at a time on this machine** - a second run WAITS, it does not
start in parallel, and a wait is not a hang. Always `-v`: without it a killed
run leaves nothing analysable. While you wait, do the per-module name-set diff
on your own commit; do not launch a second suite.

**The comparison is a SET OF NAMES, never a count.** Three finished suites each
reported exactly 231 failing names on 2026-10-02 and one of them was a
different 231 - a fix landed, a flake appeared, and the scalar did not move.
Diff both directions and report:

    new failures      in yours, not in the reference    MUST BE EMPTY
    disappeared       in the reference, not in yours    each one verified
                                                        POSITIVELY by finding
                                                        it RUN and PASS in your
                                                        own log; absence proves
                                                        nothing

Record the reference's SHA, both exit codes read off the process, and both name
counts beside the two sets.

**The mutations that must go red.** Apply each to a scratch copy, run the
module, record which test names failed and why, then RESTORE and confirm
`git status` is clean:

    M1  Make the worktree check compare the two git paths with a bare `==`
        on the raw strings - no normcase, no realpath.
        -> requirement 3 must fail. Record whether 1 still passes; if it
           does, that is the measurement of how close this bug sits to a
           green suite.
    M2  Change the git-failure branch to `except Exception: return True`.
        -> requirement 2 must fail. This is the silent fallback on a safety
           path; if it stays green, your test asserts the wrong thing.
    M3  Pass a positive `timeout` to `suitelock.acquire`.
        -> requirement 4 must fail. A second watcher that WAITS instead of
           refusing is two watchers on one lane a few minutes later.
    M4  Make the kill-file check use `startswith` on the lane name.
        -> requirement 6's two over-reach assertions must fail while the two
           positive ones stay GREEN. That split is the proof the test
           distinguishes stopping from over-stopping.
    M5  Delete the `consecutive = 0` reset after a success.
        -> requirement 8's SECOND half must fail while the first half stays
           GREEN. If both halves stay green you have only tested the
           threshold and not the word "consecutive".
    M6  Give `--permission-mode` a default of the auto-approve-everything
        mode and drop `required`.
        -> requirement 9 must fail. ALSO RECORD what the watcher then does:
           an unattended agent running at full auto because an argument was
           omitted is the exact failure this parameter exists to prevent, and
           naming it in your result block is part of the deliverable.
    M7  Build the spawn argv without the permission mode, leaving every
        validation and the log line intact.
        -> requirement 9's argv assertion must fail. Everything else must stay
           green, which is what makes this the dangerous one: validated,
           logged, and never consumed.
    M8  Make a missing lane directory return an empty list instead of
        refusing.
        -> requirement 7 must fail. Record what the watcher reports; a typo in
           `--lane` answered with "caught up" is invariant 0 in one line.

A mutation that leaves every test green means the test does not test the
control, and the correct result block says so rather than reporting green.

## DELIVERABLE

One new script and one new test module; nine proven requirements; eight
mutations each recorded with the test names that went red and the reason each
failed; the M6 and M8 behaviours written down verbatim; the suite's two name
sets with the reference SHA beside them; both exit codes read off the process;
the source tree restored and `git status` clean. **The script is NOT installed
and has NEVER been run outside the tests - state that explicitly in the result
block.** Append the result block, `git mv` the file to REVIEW/, commit on
`qwen-worker`. Do not merge. Do not push to master.
