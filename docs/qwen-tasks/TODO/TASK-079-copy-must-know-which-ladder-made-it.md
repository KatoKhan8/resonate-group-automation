# TASK-079 - a step must know which ladder made it

## THE DEFECT

Read `docs/THE-LADDER-MOVED-AND-THE-COPY-DID-NOT-2026-09-15.md` first. It is
the measurement and it is short.

Summary: the LinkedIn ladder was rewritten, the email prompt was fixed, a full
regeneration ran and exited 0, and the copy did not change. Per-sequence
product naming came back at 68%, which is exactly the baseline measured
BEFORE any of the work. Email sender identity is 0%.

The cause is not the ladder. `plan` re-plans a step when that step FAILS A
GATE, which is correct and is what makes regeneration idempotent. But a
stored step records nothing about what produced it:

    approval, body, channel, generated, note, subject, template

No ladder version. No prompt fingerprint. So when the ladder changes, the old
copy still passes every gate - it always did - and `plan` says "nothing to
generate". The improvement never reaches the copy it was written for.

## WHAT TO BUILD

A step must carry enough to answer: **was this generated against the ladder
and prompt that are in force now?**

The obvious shape is a fingerprint stored on the step - a hash over the rung
brief that produced it plus the prompt template - and a planner check that
treats a mismatch as a reason to re-plan, exactly like a failing gate.

**Do not take that design as given.** `CLAUDE.md` says to prefer canonical
state to a second representation of it and to make new state earn its place.
Look at what already exists first: `approval` carries a fingerprint bound to
exact words (`src/approval.py` - `fingerprint`, `is_approved`), and that
machinery may already answer a neighbouring question. Read it before adding
a parallel one.

## THE CONSEQUENCE THAT MUST BE DELIBERATE, NOT DISCOVERED

An approval is bound to the exact words and is revoked when a word changes.
So invalidating copy invalidates approval.

That is CORRECT - a person approved words, not an intention - but it means a
ladder edit silently un-approves human-reviewed work. **That must be visible
and counted, never a side effect somebody finds later.** Whatever you build:

    report how many steps a ladder change would invalidate, BEFORE it does it
    report how many approvals that would revoke
    make the invalidation an explicit action, not a surprise

A dry run that says "this ladder change invalidates 412 steps and revokes 88
approvals" is the deliverable that makes this safe to use.

## WHAT NOT TO DO

- **Do not delete stored copy.** It discards approvals and spends credits on
  steps that are already good.
- **Do not add a `--force-all` that regenerates the estate.** The point is
  precision: re-plan what the ladder change actually affects.
- **Do not widen a gate.** This is not a gate problem.
- Do not change what `plan` does with a FAILING gate. That path is correct
  and TASK-072 depends on it.

## HOW YOU WILL KNOW IT WORKED

1. A test that changes a rung brief and proves the affected steps become
   re-plannable, asserting on what `plan` RETURNS - not on source text.
2. A test that an UNAFFECTED step is NOT re-planned, so the change is
   precise rather than a blanket invalidation.
3. A test that the approval consequence is reported.
4. Then run it for real against the current estate and report: how many steps
   does the TASK-075 ladder change invalidate, and how many approvals would
   that revoke? That number is the answer the operator needs before anyone
   re-runs generation.

Break your own check deliberately and confirm the intended test fails for the
intended reason, and that a different guard did not fire first.

## WHAT YOU MAY NOT DO

- **READS ONLY at every provider.** No campaign write, no lead add, no send.
- Do not approve anything.
- Do not run a live regeneration of the estate as part of this task. Report
  the counts; the regeneration is Claude's call.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS (exact commands, exact counts, exit codes read off
the process and never through a pipe), FILES CHANGED, FINDINGS (the two
counts above), RISKS, RECOMMENDED CLAUDE ACTION.
