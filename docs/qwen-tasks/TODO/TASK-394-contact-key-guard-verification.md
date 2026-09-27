PRIORITY: P2
SIZE: S
DEPENDS:
STATUS: BLOCKED
ABSORBED_BY: TASK-389

# TASK-394 — contact-key guard: verify TASK-389's finding

**BLOCKED AS REDUNDANT by Claude, 2026-09-27.** GLM TASK-405 verified this and
found it duplicates TASK-389's scope: both cover the same contact-key guard, and
the handoff had already flagged the risk of double-verifying duplicate work.
Dispatching both spends two workers on one question.

`STATUS: BLOCKED` stops it being dispatched now. `ABSORBED_BY: TASK-389` closes it
automatically once 389 reaches DONE, because `claim_task.py` excludes a task whose
`ABSORBED_BY` target is in the done set. 389 is NOT done yet, which is exactly why
both fields are needed: `ABSORBED_BY` alone would leave this dispatchable until
389 landed.

Note on 405's own verdict: it is VOID on provenance (it recorded "COMMIT SHA: N/A"
and cited `facad830`, which is TASK-389's commit rather than a reviewed head). The
redundancy finding is accepted because it is independently checkable from the two
task files' scope, not because 405 asserted it. If 389 is ever cancelled rather
than completed, unblock this task instead of letting it close silently.

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
