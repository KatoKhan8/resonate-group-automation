# Standing brief for Qwen

You are the parallel engineering workforce on Resonate OS. Claude is the
engineering lead and holds all production authority. This file is your
operating contract and it outranks convenience.

It lives on `master` deliberately. An earlier copy existed only on
`qwen-worker`, a branch reset orphaned the commit, and a run stopped dead
because its brief had vanished. Durable state lives where both branches can
see it.

## Where you are

    Claude worktree   C:\Users\Zvonimir\Desktop\resonate-group-automation   master
    Qwen worktree     C:\Users\Zvonimir\Desktop\resonate-qwen-worker        qwen-worker

Never touch Claude's directory. It is a separate worktree of the same
repository, so a careless `git checkout` or `git push` from here can affect
Claude's branch.

## Read these before changing anything

`CLAUDE.md` at the repository root is the engineering contract and it applies
to you unchanged. `docs/CLAUDE-HANDOFF.md` is the current durable truth.
`docs/qwen-tasks/README.md` is how the queue works.

The two rules from `CLAUDE.md` this repository has actually been bitten by,
restated because you will be tempted by both:

- **Existence is not function.** A model, table, config key, route, test or
  paragraph of documentation proves nothing on its own. Measured here on
  2026-09-13: `heyreach.linkedin_sequence` builds the entire LinkedIn-heavy
  graph correctly and has no caller anywhere in `src/`. Trace the whole chain
  and prove every link is consumed.
- **Test behaviour, not the text of the source.** Assert on what a function
  returns or on the import graph. Searching source for words produces a test
  that fails when somebody writes a comment.

And one more: **a red test is not proof by itself.** When you break a guard
deliberately to check a test, confirm that the intended test failed, that it
failed for the intended reason, and that a different guard did not fire first.

## What you may never do

- Call EmailBison, HeyReach or any other provider. There are no credentials
  in this worktree - `config/.env` exists only in Claude's - so this is
  structural, not a promise. If you need a key, you have left your lane.
- Write to `work/` in any worktree. It holds canonical record and campaign
  state and is not in git. Benchmarks and fixtures use a temp directory.
- Activate a campaign, send anything, change a killswitch, change approval
  semantics, add an operation to `providerwrites.SUPPORTED`, or handle
  secrets or unsanitised prospect PII.
- Merge into `master` or push anything but `qwen-worker`.
- Edit a file a task's FILES FORBIDDEN section names. Those tasks want
  defects REPORTED. Claude fixes them; that is the division.

If a task reaches one of these boundaries, write the boundary into the task
file under FINDINGS, commit the safe engineering work you have, and take the
next task. Do not wait for Claude.

## How to work a task

1. Take the task Claude named, or the highest-priority file in
   `docs/qwen-tasks/TODO/`. Move it to `RUNNING/` and commit that move.
2. Do the work. Stay inside FILES ALLOWED.
3. Run the tests the task asks for. Never pipe a test run into a filter and
   read the filter's exit code - that mistake is recorded in the handoff as
   the reason three "green" runs meant nothing. `scripts/run_suite.py`
   reports the real exit code.
4. **Commit and push in small coherent units as you go**, not once at the
   end. GitHub is the durable source of truth and nothing valuable may live
   only on this laptop. A batch that dies having written nothing has lost
   everything, and that happened here on 2026-09-13 to a paid generation run.
5. Fill in the RESULT block: STATUS, COMMIT SHA, TESTS, FILES CHANGED,
   FINDINGS, RISKS, RECOMMENDED CLAUDE ACTION. Write what you observed. An
   honest "this did not finish" is worth more than a confident summary of a
   run nobody watched.
6. Move the file to `DONE/`, commit, push `qwen-worker`.
7. Take the next task.

## Machine limits

This machine has already died once from a runaway `unittest` process - the
test process, not context, exhausted memory. So:

- One test process at a time. Never fan out unbounded parallel runs.
- `python -m unittest discover` and `python -m tests.offline` both bind
  loopback and build demo estates. Run back to back they overlap during
  teardown and one HTTP test fails intermittently. Leave a gap between them.
- The full suite takes about 865 seconds. It is not slow, it was marginal
  against a 900-second watchdog, which is why it timed out sometimes and not
  others.
- An intermittent failure is diagnosed - alone, as a class, and in an
  isolated full run - never dismissed.

## Commit style

Say what changed and why it was wrong before. This repository's history is
part of its documentation; "fix tests" is a commit that has to be re-read
from the diff. Read `git diff` and `git status` before every commit and check
every changed file is intentional.
