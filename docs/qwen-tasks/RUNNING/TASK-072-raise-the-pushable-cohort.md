# TASK-072 - raise the pushable cohort above three of fifteen

## THE PRODUCTION BLOCKER, STATED PLAINLY

    pushable   3 of 15 contacts

HeyReach campaign 599020 is written, read back and correct - 27/27 PASS. The
sequence does not depend on the cohort because the graph carries merge
fields. **A lead add does.** Three contacts is too thin a cohort to promote,
and the other twelve are blocked by copy that still fails a gate.

Raising that number is REGENERATION work. It is not a permission change and
it is not a gate change.

## WHAT TO DO

    py -3 -m src.generate --live --client productive
    py -3 scripts/write_heyreach_sequence.py productive-linkedin-production-v1

Repeat until the dry run stops raising `FactoryRefused`, capped at FIVE
passes. It is idempotent: the planner only re-plans steps that fail a gate,
and `store.transaction()` commits per record, so a killed run loses nothing
finished.

TASK-068 landed set-at-a-time regeneration, so a contact whose notes are
mutually repetitive can now escape - each candidate is no longer judged
against five stale siblings saying the same thing. That was the wall the
previous three attempts hit.

## REPORT THE NUMBER THAT MATTERS

After each pass, report `pushable` as N of 15, and which contacts moved.
A pass that does not move it is a finding, not a failure - say WHICH contact
is blocking and WHICH gate refused it, quoting the refusal.

## THE RULE THAT OUTRANKS FINISHING THIS TASK

**Do not widen a gate to raise the number.** Not `SUBJECT_VOCABULARY`, not
the repetition checks, not the unsupported-claim gate, not the lint rules.
This was measured and rejected on 2026-09-14: discounting the client's own
angle vocabulary clears every collision on the blocking contact AND passes
four askings of the same question. The reasoning is in
`docs/WHY-REGENERATION-CANNOT-CONVERGE-2026-09-14.md`. Read it before you
are tempted.

A gate that refuses your copy is telling you the copy is bad. Regenerate it.

If after five passes the number has not moved, STOP and report. Do not start
editing gates to make progress.

## WHAT YOU MAY NOT DO

- **READS ONLY at every provider.** No HeyReach write, no lead add, no
  campaign mutation, no EmailBison write. You hold real keys. Generation
  calls the MODEL, which is allowed and is the point of this task.
- Do not edit `work/queue.jsonl` or `work/campaigns.jsonl` directly. Only
  `src/store.py` touches them.
- If `work/queue.jsonl.lock` names a dead pid, removing it is allowed and
  expected - a run was killed mid-write. Say in your result that you did.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS (pushable before and
after, per pass), RISKS, RECOMMENDED CLAUDE ACTION.
