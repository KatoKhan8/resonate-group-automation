PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-372 — the suite baseline is 73 failures short, so it cannot gate a merge

`docs/state/SUITE-BASELINE-2026-09-26.txt` lists **128 named failures** and
OPERATING-MODE §19 makes it the merge gate: a known baseline failure is visible
debt, a **new failure BLOCKS**, and the count may never silently increase.

**Two workers independently measured a different number today**, neither of
them looking for it:

- TASK-366 (`qwen-worker-3-r76`): "Full suite completed (12405 tests, 201
  failures). Diff against baseline shows 73 new failures, but verification
  confirms these are PRE-EXISTING failures not captured in the baseline. Tests
  fail identically with and without my changes (verified by checking out
  49d6ff97)."
- TASK-354 (`qwen-worker-5-r77`): "Full suite: 203 failing names (128 baseline
  + 75 new). The 75 new are pre-existing staging/provider pipeline errors …
  that error on setup."

Two measurements, ~73 and ~75 unrecorded failures, from different branches.
**A gate that reports 73 false positives on every merge is a gate nobody can
use**, and tonight every integration has had to reason around it by hand.

**A count is not the deliverable. A NAMED SET is.** The baseline's whole
purpose is set difference: which test names fail now that did not fail before.
Two runs that both say "201" can be different failures.

## Build

    docs/state/SUITE-BASELINE-2026-09-26.txt   REGENERATE, on clean master
    docs/state/SUITE-BASELINE-DELTA-2026-09-26.md   NEW, the explanation

`scripts/suite_baseline.py` and `scripts/run_suite.py` already exist. Read them
before writing anything; TASK-366 reports that `run_suite.py`'s 30-minute
timeout is too short for this machine and the suite takes 35-100 minutes. Fix
the timeout if that is what is in the way, and say you did.

## Acceptance — RUN each, paste real output

1. **Regenerate on clean master, with nothing else in the tree.** `git status
   --porcelain` empty before you start, and paste it. A baseline measured over
   somebody's uncommitted change is not a baseline.

2. **Wait for `work/suite_verdict.txt`.** Do **not** grep a running log for a
   FAIL prefix — mid-run that always returns nothing and reads as success.

3. **The set diff, both directions.** Against the old 128:
   - names failing now that are not in the old file — list every one;
   - names in the old file that now pass — list every one.
   Report both lists in full. `sort -u` both sides; a duplicate name inflates a
   count and hides a set.

4. **Each newly recorded failure gets one line in the delta document:** the
   test name, and whether it is (a) genuinely pre-existing and simply never
   recorded, (b) a failure introduced between the baseline's run and now, or
   (c) environment-dependent — a missing credential, a network call, a
   timeout. Category (c) must be named as such, because a test that fails only
   on a machine without credentials is not debt, it is a test that should skip.

5. **Prove it is pre-existing where you claim it.** For at least the ten
   largest groups, check out the commit the baseline was taken at, re-run those
   named tests, and show the same failure. Do not assert it from the shape of
   the name.

6. **The regenerated baseline is verified to be usable:** run the suite a
   second time and diff the two named sets. A stable baseline gives an empty
   diff. If it does not, you have found flaky tests — name them, and say so in
   the delta document rather than averaging them away.

## What this task may NOT do

- **Do not delete, skip, xfail or weaken a single test to shrink the number.**
  §19: never delete a legitimate test for green CI. A safety test failing
  because production violates the contract is evidence, and it stays.
- Do not fix any of the failures. This task measures; fixing is separate tasks.
- Do not touch `src/`. If the only way to get a clean measurement is a change
  under `src/`, stop and report it.
- Nothing sent, activated, resumed, enrolled or attached. Production freeze.

---

## DIAGNOSIS BY CLAUDE, 2026-09-27 — read this before retrying

This task failed four times overnight and was stuck in RUNNING for 675+ minutes.
The operator's instruction is explicit: diagnose, then resume or requeue safely,
**never restart blindly**. Here is what was actually measured.

**1. It was DOUBLE DISPATCHED.** The task file sits in `RUNNING/` on TWO
branches at once:

    qwen-worker-2-r9        RUNNING/TASK-372-...
    qwen-worker-6-r80       RUNNING/TASK-372-...

Two workers on one task is the condition `pool.sh` has a lock to prevent. Before
doing anything else, confirm which branch is yours and do not fight the other.

**2. Nothing was running.** A full process listing at 12:40 showed no `qwen`
process and no `node` process anywhere on the machine: only the watchdog, four
`pool.sh sweep` shells, and long-lived watch loops from 09-24/09-25. The claim
was held with zero commits for over eleven hours because the worker process was
gone, not because the suite was slow.

**3. THE LIKELY ROOT CAUSE: the wrong verdict path.** An orphaned poll loop
(PID 26052, started 2026-09-26 23:08, killed 2026-09-27) was waiting on

    /c/Users/Zvonimir/Desktop/resonate-qwen-9/scripts/suite_verdict.txt

That path is wrong. This repository's convention is **`work/suite_verdict.txt`**.
A loop waiting on `scripts/suite_verdict.txt` can never exit, which matches the
"identical poll loop" pattern that killed this task four times. Confirmed absent
in both `resonate-qwen-2` and `resonate-qwen-9`: no `suite_verdict.txt` exists at
`work/`, at `scripts/`, or at the repository root.

**So: check your own wait path first.** Wait on `work/suite_verdict.txt`, detach
the long-running step, and poll with increasing backoff, never an identical check
repeated back to back.

**4. The watchdog will not rescue you.** It fired CRITICAL for this task
repeatedly and then stopped: "stuck in RUNNING a SECOND time, not auto-requeuing
again, needs a human look". It is working as designed; it just cannot help.
Separately, until 2026-09-27 those CRITICAL alerts reached nobody, because
`slack.live()` read the environment without loading `config/.env`. That is fixed,
so a repeat failure will now actually be visible.

**Reminder on what the baseline is for.** The baseline is a SET OF NAMED
FAILURES, not a count. Regenerate it as names and diff sets. A count that matches
while the names differ is two regressions cancelling out, and the count may never
silently increase.
