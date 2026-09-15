# Qwen task queue

Claude (this repository, branch `master`) is the engineering lead and the only
agent permitted to touch production provider state. Qwen is a parallel worker
in an isolated worktree.

    Claude worktree   C:\Users\Zvonimir\Desktop\resonate-group-automation   master
    Qwen worktree     C:\Users\Zvonimir\Desktop\resonate-qwen-worker        qwen-worker

Never let both edit the same physical worktree.

## Lifecycle

    TODO/     written by Claude, not yet started
    RUNNING/  Qwen has picked it up
    DONE/     Qwen has finished and recorded a result

Move the file between directories; do not copy it. One task, one file.

## What Qwen may never own

Live sends. Campaign activation. Real provider mutations at EmailBison or
HeyReach. Production ledgers (`work/*.jsonl`). Killswitch semantics.
Approval semantics. Secrets. Unsanitised prospect PII.

If a task reaches one of those boundaries: write the boundary into the task
file under FINDINGS, commit the safe engineering work, and take the next task.

## Git policy

Qwen commits only on `qwen-worker` and pushes only `qwen-worker`. It never
merges into `master`. Claude fetches, reads the diff, and cherry-picks.

## Result block

Every finished task file ends with:

    STATUS
    COMMIT SHA
    TESTS
    FILES CHANGED
    FINDINGS
    RISKS
    RECOMMENDED CLAUDE ACTION

## Tooling note - CORRECTED 2026-09-15

An earlier version of this file said the `qwen` CLI was "NOT installed on
this machine and is not on PATH" and that these tasks were "queued and
durable rather than dispatched. Nothing here assumes an agent has read them."

**That is false and was false for two days.** Qwen Pro runs eight parallel
workers against this queue. The CLI is not on PATH - the grain of truth the
stale paragraph was built on - but it is installed, and it is dispatched by
absolute path:

    C:\Users\Zvonimir\AppData\Local\qwen-code\bin\qwen.cmd
        --approval-mode yolo  "<prompt>"

Run each from inside its own worktree. Do NOT pass `--max-tool-calls`.
Credentials are present in all eight worktrees.

This is the third environment document in this repository found asserting the
opposite of the truth - `QWEN.md` told a worker it had no credentials while it
held all three, and `src/providerwrites.py` said `SUPPORTED` was empty while
six routes were live, one of which had written a production sequence.
**Check a claim about the environment before you act on it.** Each of those
cost real work.

## Dispatch, 2026-09-15: one task per worker, named explicitly

A worker told to "take the next task" will scan `TODO/` and collide with
another worker. That happened on the first round-6 dispatch: two workers both
ran TASK-095. Name the single task file in the prompt, tell the worker the
others are being run right now by somebody else, and have it `git mv` that
file to `RUNNING/` as its first action so the claim is visible.

A worker that replies "Ready. What's the task?" has done nothing. Lead the
prompt with the literal first command rather than with context, and check
that each worker's branch actually moved before believing the pool is busy.
