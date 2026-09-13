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

## Tooling note, 2026-09-13

The `qwen` CLI is NOT installed on this machine and is not on PATH. Checked
from both bash and PowerShell. These tasks are therefore queued and durable
rather than dispatched. Nothing here assumes an agent has read them.
