PRIORITY: P1
DEPENDS:

# TASK-202 - nobody has run the whole suite today

## WHERE THIS SITS

Twenty-six tasks landed on master on 2026-09-16, touching `src/generate.py`,
`src/liststaging.py`, `src/holdreasons.py`, `src/providers/xai.py`,
`src/run.py`, `scripts/claim_task.py`, the cadence step list, three test
allowlists and the PII guard. Every one of them was tested, and each was tested
against a SUBSET Claude chose - the modules that task touched, plus invariants
and audit. The largest single run was 455 tests.

The full suite has not run green end to end since before this morning. That is
the gap: a subset cannot see a break between two modules that no single task
owned, and today's changes crossed generate, the cadence graph, the runner's
flags, the write contracts and the claim logic.

Known conditions to respect, from CLAUDE.md:

    `unittest discover` and `tests.offline` both bind loopback and build demo
    estates; run back to back they still overlap during teardown, and one HTTP
    test fails intermittently. Leave a gap between them.

    This machine has already died once from a runaway `unittest` process.

Eight workers are also running against this repository right now, and several
write to `work/`.

## THE QUESTION

1. **Run the whole suite.** Read the exit code OFF THE PROCESS, never through a
   pipe. Report the totals: run, failures, errors, skips.
2. **Leave the gap.** Run `unittest discover` and `tests.offline` separately
   with a pause between them, and say what you ran and in what order. If one
   HTTP test fails intermittently, run it alone to find out whether it is the
   known intermittent or something new - CLAUDE.md requires an intermittent be
   diagnosed alone, as a class, and in an isolated full run, never dismissed.
3. **For every red test, classify it** as one of: a real break from today's
   changes, a pre-existing failure older than today, a stale allowlist, a
   fixture problem, or an ordering or concurrency artefact of the eight live
   workers. Name which task's change is implicated where you can.
4. **Fix only the ones that are stale allowlists or plainly broken fixtures.**
   Anything that looks like a real behaviour break: report it with the task
   that caused it and the smallest reproduction. Do not fix a behaviour break
   in a module you have not read.
5. **Report the runtime**, so the next person knows what a full run costs.

## THE TRAP

Never weaken, skip, `expectedFailure` or delete an assertion to reach green.
That prohibition is in CLAUDE.md and it is the one most likely to be violated
by a task whose deliverable is "the suite is green" - so the deliverable here is
**an honest account of what is red**, and green is not required for this task to
succeed. A suite reported green by a run that skipped what it could not pass is
worse than a red one.

Second trap: do not run a live stage, a generation pass or anything that writes
to `work/` as a side effect of testing. Eight workers are using it. If a test
requires a writable estate, it should already build its own temp one; if one
does not, that is a finding.

## WHAT YOU MAY NOT DO

- No provider writes, no paid provider calls, no model calls.
- Do not write to `work/queue.jsonl` or `work/campaigns.jsonl`.
- Do not weaken, skip or delete an assertion.
- Do not fix a behaviour break in a module you have not read - report it.
- Do not run the suite twice concurrently, and do not leave a runaway process.
  Bound it and say what you bounded it to.

## FILES ALLOWED

    tests/   (stale allowlists and broken fixtures only)
    docs/SUITE-2026-09-16.md   (new)
    scripts/task202_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The totals with the exit code read off the process, the order you ran things
in, every red test classified with the implicated change, what you fixed and
why it was safe to fix, what you left red and its reproduction, and the
runtime.
