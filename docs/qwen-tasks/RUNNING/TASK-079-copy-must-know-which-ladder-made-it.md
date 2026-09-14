# TASK-079 - copy must know which ladder made it

## THE PROBLEM

TASK-075 rewrote the LinkedIn ladder (all 6 rungs) and the email five-ladder
(rungs 1, 3, 4). Stored copy was generated against the OLD ladder. The
approval fingerprint binds to exact words, so regenerated copy with the new
ladder will produce different words and invalidate the approval.

The operator needs a DRY-RUN COUNT: how many stored steps does the ladder
change affect, and how many approvals would regeneration revoke?

## WHAT THIS TASK DELIVERS

A diagnostic script (`scripts/ladder_impact.py`) that reads the queue and
reports:

1. How many stored steps use changed ladder rungs
2. How many of those carry a current approval
3. Per-record breakdown

## CONSTRAINTS

- READS ONLY at every provider
- Do not delete stored copy
- Do not add a force-all flag
- Do not change what plan does with a failing gate
- Do not run a live regeneration
- Report the counts and leave regeneration to Claude

## FILES ALLOWED

- scripts/ladder_impact.py (new)
- tests/test_ladder_impact.py (new)
- This task file

## FILES FORBIDDEN

- src/approval.py
- src/cadencelibrary.py
- src/generate.py
- src/approve.py
- src/store.py
- work/ (no direct access)

## RESULT BLOCK

STATUS:

COMMIT SHA:

TESTS:

FILES CHANGED:

FINDINGS:

RISKS:

RECOMMENDED CLAUDE ACTION:
