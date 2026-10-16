# TASK 0171 — did an orphan already finish 0170, and can it be proven?

qwen lane, 2026-10-16. Measured at
`119d545965cf689757c5242495f123a2df0188c1`, branch
`task-qwen-0090-watcher-treekill-2026-10-15`, reachable from `4bdb3a213`.
`origin/master` is `b1f290c84` and was not touched.

## The answer

**Neither of the two worlds the brief named. `ORPHAN_WORK`.**

0170's **build** ran to completion — both features, wired end to end, 53 tests
green. Nothing of it was committed, and its **record did not exist in any form**:
no commit, no report, no lane entry, no `DONE` line, a 0-byte stdout. Two clauses
of its own brief — the mutation proof and the closing paragraph — had never been
done.

So it was world B for the code and world A for the proof and the record. The
brief's rule for A applies ("finish from where it stopped, do not start over from
nothing if a usable partial exists"), and that is what happened: the orphan's
bytes were committed unchanged first, then the missing proof, paragraph, report
and record were added on top, in separate commits so the two authors are
tellable apart.

## 1. The evidence, in the order the brief asked for it

| question | answer | how |
|---|---|---|
| HEAD vs 0160's `4bdb3a213` | **identical** — no commit followed it | `git log --oneline -5`, `git rev-parse HEAD` |
| dirty tree? | **yes** — 4 modified, 5 untracked, all 0170's | `git status --porcelain` |
| lane entry for 0170? | **absent.** 196 headings, none names 0170; `LANE-qwen.md` mtime **00:57:45**, *before 0170 started* | heading scan |
| prior entry intact? | **yes** — 0160's entry is complete and ends with its `QUEUE` section saying it is starting 0170 | read the seam |
| `task-qwen-20261016-005853.out` | **0 bytes**, mtime unchanged at 00:58:53 | `stat`, read by content |
| brief still in `RUNNING\`? | **no** — the operator hand-moved it to `DONE\` at 09:16:50 as `NEPOZNATO-JE-LI-ODRADJEN` ("unknown whether it was done"). Weighed at nothing, as instructed | directory listing |
| any 0170 commit anywhere? | **no** | reflog + `git branch -a` + `git log --all` |

Two things settled it, and neither is a filename.

**The mtimes bracket the orphan's whole life.** 0160 reported "tree clean" at
00:58:48 and the watcher logged `START 0170` five seconds later. All nine files
have mtimes between **01:04:20 and 01:13:01**, and `__pycache__` holds compiled
bytecode for both new test modules dated **01:11:58 and 01:13:04**. So the
orphan worked for ~14 minutes, wrote everything, and *ran its own tests*. Nothing
on this disk was touched by it after 01:13:04.

**The work runs.** 53 tests, 0 failures, 23 seconds — and 72 more in the three
other modules that touch the changed code, also green. 125 tests, 0 failures.

### One correction to the diff, because the raw number is misleading

`git diff --stat` reports 1,208 insertions / 822 deletions, which for "two
changes with zero correctness cost" looks like a rewrite. It is not. These files
were mixed-ending and the orphan's editor wrote them uniformly CRLF, which is
what this tree is. `--ignore-cr-at-eol` gives the real delta: **+389 / −3** across
the four tracked files, plus 1,298 lines of new files. Worth stating because the
standing rules warn about exactly this and a reviewer reading the headline number
would reasonably refuse the diff.

## 2. The control — the test was blind, and the control caught it

Run against 0160, which demonstrably finished, the first version of the probe
returned **INCOMPLETE**. That is the §4 control doing its job on its author, and
it exposed two real defects:

- **It judged test results by exit code.** `tests.test_fixture_hygiene` carries 5
  of this repo's standing 231 failing names, so a module that has been red all
  week read as a regression. Fixed: failures are compared as a **name set** —
  `failing - baseline` — never by count or exit status, which is the operator
  rule of 2026-10-02 (three finished suites each reported 231 failures and one of
  them was a different 231).
- **It demanded tests of a task that was never asked for any.** 0160 was a
  measurement task; its deliverable is a report. Fixed with an explicit
  `--deliverable measurement`.

With both fixed, 0160 reads **COMPLETE**.

A third false pass appeared on first real use and is the most instructive. The
probe's commit check searched `--all --reflog` for the token `0170` and **passed**
— on the strength of `cc112ae60 "TASK 0170: the nine measured on ONE tree"`,
which is *pilotcaps'* task 0170 on `integ/canary-nine-2026-10-15`. **A bare task
number is not a lane-unique identifier**: seven lanes draw briefs from the same
number sequence, and eight different `0170`s exist across this estate's queues.
The one check that decides "was this work committed" was being answered by
another lane's commit. It is now scoped to a named ref, with same-token hits
elsewhere reported as a warning and never as the pass.

### The negative control: a fabricated-complete record over half-applied code

`docs/ops/probe_control_half_applied.sh` builds the hardest case rather than an
easy one, in a throwaway local clone: **every RECORD check is made to pass** — a
real commit naming the task, a report file, a lane-file heading, a watcher log
carrying both `START` and `DONE ... -> exit0`, a non-empty stdout — over a change
that is only half applied. Two shapes, neither COMPLETE:

    A  test references a helper the source half never got   -> INCOMPLETE
    B  module imports, runs, and the guard is absent        -> INCOMPLETE

Both held. A completeness check that calls everything complete is this estate's
sixth failure family and B7 shipped exactly that; this one can be shown to say
no, against a record built specifically to fool it.

**It also corrected a prediction of mine.** I expected variant A to come out
`UNKNOWN`, reasoning that an unimportable module measures nothing. It comes out
`INCOMPLETE`: unittest wraps the failure in `unittest.loader._FailedTest` and
reports it as a failing *name*, so there is a `Ran 1 test` line. The stricter
verdict is right, but the probe's `UNKNOWN` branch is therefore **unexercised by
this control** — named here as a gap rather than papered over.

## 3. For the operator — the watcher did NOT die at its 90-minute timeout

This contradicts both the brief's hypothesis and
`resonate-ops\CONTINUITY.md` §4 trap 1, which currently reads:

> **Second instance, measured 2026-10-16 02:28.** The `qwen` watcher died the
> same way, on the same old bytes, and wrote nothing at all — the log's last line
> is a `START` from 00:58:53.

**The mechanism and the time are both wrong, and there is an exact control for
it.** The old bytes *do* log a `TIMEOUT` line before killing anything. Four
surviving instances prove it, two of them from the very same launch as qwen's:

    [2026-10-15 21:07:10] [glm]    watcher up ... timeout=90m
    [2026-10-15 21:07:10] [glm-c]  watcher up ... timeout=90m
    [2026-10-15 21:07:10] [qwen]   watcher up ... timeout=90m     <- same second

    [2026-10-15 23:05:10] [glm]    TIMEOUT after 90 minutes, killing the process
    [2026-10-15 23:05:14] [glm-c]  TIMEOUT after 90 minutes, killing the process
    [qwen]                         no TIMEOUT line anywhere in the file

All three watchers were started **in the same second, from the same bytes, with
the same 90-minute cap**. Two of them timed out and said so. The third is the one
whose timeout is alleged, and its log contains no `TIMEOUT` line at all — so this
is not an argument about what the old code might have logged; it is the same code,
observed doing it, twice, minutes apart.

**So qwen's watcher never reached 02:28:53.** And it did not take any of the
other three documented exits either. The script logs a distinct line for every
one of them:

    STOP-ALL / STOP-<lane> present   -> "STOP-ALL present. Exiting."
    queue drained, loop ends         -> "watcher down."
    unhandled error                  -> "watcher down (unhandled error)."
    timeout                          -> "TIMEOUT after N minutes..."

**None of the four appears.** The log simply stops mid-task and resumes 8h15m
later with a new watcher at 09:14:03 reporting a stale lock from pid 66028, by
then gone. A process that takes any coded exit path writes a line; one that is
killed outright writes nothing. **The signature here is abrupt external
termination, not an error path** — which is also why the `.out` is 0 bytes: it
was never flushed.

For completeness, the 01:48 shutdowns in the other lanes are **not** related:
`glm`, `glm-b` and `glm-c` each logged a clean `watcher down.` at 01:46:23–01:48:09
immediately after a `DONE`, with no STOP line — their queues had drained, burnt
through by the run of `exit1` briefs that never ran. No STOP file exists.

**The timing points at ~01:13, not 02:28.** A live watcher polls its child and
logs `DONE` the moment it exits. The task's last act on disk was 01:13:04. Had
the watcher been alive and the child exited then, there would be a `DONE` line;
had the child still been running, the watcher would have gone on to log a
`TIMEOUT` at 02:28:53. Neither exists, which puts the watcher's death at or
before ~01:13:04 — about 14 minutes into the task and **75 minutes before its
timeout could fire.**

### What this means for the orphan theory

**0170 was most likely not a trap-1 orphan at all.** Trap 1's signature, measured
at 23:05 on both `glm` and `glm-c`, is that the task *survives* its supervisor
and runs to completion — "both orphaned tasks ran to completion anyway, through
their whole queues, with no DONE line written." 0170 did not: it stopped writing
at 01:13:04, mid-brief, with its build done and its proof, report, entry and
commit all still to do. Watcher and task appear to have stopped **together**,
which is what a killed process tree looks like and not what trap 1 looks like.

**What killed them is UNKNOWN and I will not guess.** No `claude.exe` from that
window survives — a process census with a self-check (the reader saw 569
processes and found itself) shows nothing started between 00:55 and 02:35 but two
interactive consoles and a Chrome. What would settle it: the Windows event log
for process exits around 01:13 on 2026-10-16, or the operator's own
recollection. Two circumstantial facts, offered as timeline and not as cause: an
interactive PowerShell console was opened at **01:11:13** and is still running
eight hours later, and `tools\OFFSITE-BACKUP.ps1` was edited at **01:21:28** — so
somebody was working on this machine inside that window.

**Recommendation for CONTINUITY.md:** trap 1's second instance should be
withdrawn or re-characterised. Counting qwen as a fourth trap-1 watcher makes the
trap's cost ("four watchers in 29 hours") overstate trap 1 and, more importantly,
hides a *second and different* way a lane can be lost — one that the trap-1 fix
already shipped in `0090` does nothing about. I have not edited that file; it is
not mine and the correction is the operator's to make.

**Not restarted, as instructed.** No watcher or process was started, stopped or
killed by this task.

### Why this matters more than the two features 0170 built

0170's own loss is not in the failure family any of 0150's seven proposals
address. The lane had time, knew what to do, and produced good work; the
**supervisor stopped recording while the task was still healthy**, and the task
had no way to notice. `LANE_DEADLINE` lets a task ask "can I finish?" — 0170's
answer would have been a confident and correct yes. Nothing lets it ask "is
anyone still listening?"

That is the gap, and it is cheap to close in the direction that already works:
the brief for 0171 existed because a **human** read a log tail and noticed a
`START` with no ending. A `START` older than the lane's own timeout with no
ending is a two-line check against a log the watcher already writes. Filed, not
built — it is outside this brief.

## 4. What this task changed

| | |
|---|---|
| `119d54596` | 0170's work, committed exactly as found, not one line mine |
| `docs/ops/mutation_proof_0170.py` | the proof 0170 never ran. 6/6 killed by the named test |
| `docs/ops/task_completeness_probe.py` | the A/B test, with its three fixed blindnesses |
| `docs/ops/probe_control_half_applied.sh` | the negative control, both shapes |
| `TASK-0170-...md` | 0170's missing report, including its §4 paragraph |

Nothing was started that is still running. No watcher touched, no process killed,
no `RUNNING\`/`DONE\` file moved, nothing written to `logs\watcher-qwen.log` — the
watcher owns those and the gap is recorded in `LANE-qwen.md` instead. No push or
merge to master; `origin/master` verified at `b1f290c84`. No provider, Apify,
Slack or network call beyond `git fetch` and a push to this lane's own branch. No
suite lock taken — every test run was a direct `unittest` invocation, never
`run_suite.py`. `config\.env`, production `work\` state and `src/providers/*` were
not read or changed. No key printed.

## 5. Two artefacts a brief named that do not exist

Reported by path rather than worked around, per the standing rule:

- **`provenance()`** — 0171's brief says to state the verified SHA "the way this
  lane's `provenance()` pattern requires rather than by typing a SHA". No such
  function exists anywhere in the repository (`grep -rn "def provenance"` is
  empty). The intent is clear and was honoured: every SHA in this report was
  derived by `git rev-parse` in a script that also verifies the committed blobs
  carry the features, rather than typed.
`CONTINUITY.md` is **not** one of them, and I nearly filed it as one. It is
absent from this worktree and from `git log --all`, and I had written it up as a
missing artefact on that basis. It exists — `C:\Users\Zvonimir\Desktop\resonate-ops\CONTINUITY.md`,
130 KB, last written 09:04 today — in the ops folder, which is exactly the trap
the standing rules added on 2026-10-15 23:40: **a brief's paths are not relative
to the lane's worktree.** Checking before asserting the absence is what turned
that from a false finding into section 3's correction, which could only be
written by reading the file.
