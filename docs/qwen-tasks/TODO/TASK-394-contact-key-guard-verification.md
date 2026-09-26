PRIORITY: P2
SIZE: S
DEPENDS:

# TASK-394 — contact-key guard: verify TASK-389's finding

TASK-389 (contact-key guard clean-up) is already queued/possibly in flight
with the same scope. Read its current state first; if complete, verify its
finding independently (re-run its own acceptance) rather than duplicating
the trace. If TASK-389 has not started, this task is redundant — pick
whichever of the two a worker reaches first and let the other close as
superseded citing the one that did the work.

## Acceptance

1. State TASK-389's status plainly.
2. If done: independently re-run its guard-failure test (or its "nothing
   inconsistent" conclusion) and confirm or refute.
3. If not started: do TASK-389's own work, not a rewritten version of it.

## What this task may NOT do

- Do not fork a second contact-key validation function - one guard, one
  location, matching TASK-389's own goal.
- Nothing sent, nothing activated.
