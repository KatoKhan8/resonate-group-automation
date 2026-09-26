PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-393 — batch pipeline on the client file: verify TASK-347's progress

TASK-347 (client file through qualification/MX/CheapVerifier/research/facts,
in batches of 1,000, stop before copy) is already queued/possibly in flight.
This task's job: read TASK-347's CURRENT state (TODO/RUNNING/REVIEW/DONE,
across all worker branches, not just master) and report exactly how far it
has gotten — batches completed, qualification rate measured so far, any
blocker it hit — rather than waiting for a final result that may not land
before this session's handoff.

## Acceptance

1. Name TASK-347's real current state with evidence (branch, last commit,
   batches processed if any).
2. If it is stalled or blocked: name the blocker plainly, do not guess.
3. If genuinely not started: this task becomes "start it," following
   TASK-347's own spec exactly — do not restate or fork it.
4. No new code unless TASK-347 is confirmed not started and this task picks
   it up directly.

## What this task may NOT do

- Do not commit anything from work/ (client PII).
- No provider write, nothing sent.
