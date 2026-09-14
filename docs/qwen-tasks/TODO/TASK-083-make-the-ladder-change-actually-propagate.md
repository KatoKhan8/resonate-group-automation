# TASK-083 - make a ladder change actually reach the copy

## WHERE THIS STANDS

Read `docs/THE-LADDER-MOVED-AND-THE-COPY-DID-NOT-2026-09-15.md` in full,
including the two sections at the end.

TASK-079 measured the problem and its diagnostic is on master:

    records analysed                300
    records with affected steps      68
    TOTAL AFFECTED STEPS            581
      carrying a current approval   115

**It did not fix the propagation.** Its result block argued that
`src/approval.py` needs no change because a ladder change propagates through
"regeneration -> different text -> different fingerprint -> stale approval".
That chain never starts. Regeneration does not happen, because `plan` finds
no failing gate. This task starts it.

## WHAT TO BUILD

A step must be able to answer: **was I generated against the ladder and
prompt in force now?** And when the answer is no, `plan` must treat that as a
reason to re-plan, exactly as it treats a failing gate.

`scripts/ladder_impact.py` already computes which steps are affected. Read it
first - the hard part is done and the question is how `plan` consumes it.
Prefer reusing that logic over writing a second implementation of it;
`CLAUDE.md` is explicit that a parallel state machine for the same fact is
how two things drift.

Look at `src/approval.py`'s `fingerprint` before inventing a new mechanism.
It already hashes copy for a neighbouring purpose.

## THE THING THAT MAKES THIS DANGEROUS

Running it revokes 115 human approvals. An approval is bound to exact words,
so regenerated words mean a person must approve again. That is CORRECT and it
is expensive.

**Therefore it must be OPT-IN and it must report before it acts.**

    default            nothing changes. plan behaves exactly as today.
    explicit flag      re-plans ladder-stale steps
    before acting      prints how many steps and how many approvals

A run that silently un-approves 115 steps somebody reviewed is a worse defect
than the one being fixed. The operator decides when to spend that, not the
code.

## HOW YOU WILL KNOW IT WORKED

1. A test that a step generated against an OLD rung brief becomes
   re-plannable when the brief changes - asserting on what `plan` RETURNS,
   never on source text.
2. A test that an UNAFFECTED step is NOT re-planned. Precision is the point;
   a blanket invalidation is the thing we are avoiding.
3. A test that the default path is UNCHANGED - without the flag, `plan`
   returns exactly what it returns today. This is the test that keeps
   TASK-072's idempotence intact.
4. A test that the approval count is reported before anything is re-planned.
5. Break your own check deliberately: confirm the intended test fails, that
   it fails for the intended REASON, and that a different guard did not fire
   first.

## WHAT YOU MAY NOT DO

- **Do not run a live regeneration.** Not even a small one. The generation
  against real production state is Claude's, from Claude's worktree - and
  `work/queue.jsonl` in your worktree is NOT production state. Read
  `work/queue.snapshot.jsonl` and quote its STAMP.
- Do not delete stored copy.
- Do not add a force-all that rebuilds the estate.
- Do not change what `plan` does with a FAILING gate. That path is correct.
- Do not weaken a gate.
- **READS ONLY at every provider.** Approve nothing.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS (exact commands, exact counts, exit codes read off
the process and never through a pipe), FILES CHANGED, FINDINGS, RISKS,
RECOMMENDED CLAUDE ACTION. State plainly whether the default path is provably
unchanged, because that is what makes this safe to merge.
