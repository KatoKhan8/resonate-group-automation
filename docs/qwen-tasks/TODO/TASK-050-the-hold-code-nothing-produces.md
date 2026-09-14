# TASK-050 - A hold code that exists and that nothing ever produces

## THE FINDING

Four tests fail in `tests/test_the_cadence_reacts_to_what_the_prospect_did.py`
and have done for some time. They are behavioural, not fixture rot.

The state machine answers a generic `linkedin:step_requirement_unmet` in a
situation where `linkedinstate.HELD_REQUEST_OUTSTANDING` exists and is the
specific, correct answer. Nothing in `src/` produces that constant.

This is the defect class `CLAUDE.md` names first and this repository keeps
re-finding: a thing computed correctly that nothing downstream reads, or in
this case a named answer nothing upstream writes. The constant exists. The
tests expect it. The producer is missing.

## WHY IT MATTERS BEYOND THE TEST COUNT

A generic hold code and a specific one are not the same information. "This
step's requirement is unmet" tells an operator nothing they can act on. "A
connection request is outstanding" tells them to wait rather than to
investigate, and it is the difference between a queue somebody can triage
and a queue somebody ignores.

It also matters for the LinkedIn-heavy cadence specifically, where six of
eleven touches are LinkedIn and several of them carry
`requires: connection_accepted`. Whatever a held LinkedIn step reports is
what an operator will be reading a great deal of.

## GOAL

`HELD_REQUEST_OUTSTANDING` is produced by the code path that should produce
it, the four tests pass, and no other hold code changes meaning.

## HOW TO WORK IT

1. Reproduce first. Run the four tests, read what each one asserts and what
   it actually got. Write down the four situations in one line each.
2. Find where the generic code is returned. Establish whether the specific
   case is REACHED and mislabelled, or never reached at all. Those are
   different bugs and only one of them is a labelling fix.
3. Read `src/linkedinstate.py` for the full set of hold codes and what each
   one means. The answer must be one of the existing meanings - do not
   invent a new code, and do not repurpose one.
4. Fix the smallest root cause. Then attack it: break the producer
   deliberately and confirm the intended test fails, that it fails for the
   intended reason, and that a different guard did not fire first.

## ONE RELATED FACT, SO YOU DO NOT TRIP OVER IT

`tests/test_linkedinstate_redteam.py` carries an expected failure: an
already-connected person's `li1` returns WAIT instead of SKIP, because the
Open Profile alternative names a capability this system has not proven. That
is a DIFFERENT open defect, deliberately recorded, and it is not yours to
close. If your change alters its behaviour, stop and report it rather than
updating the expectation.

## WHAT YOU MAY NOT DO

- Do not weaken a check or loosen an assertion to make a test pass.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- No provider call, no live send, no campaign mutation.

## RESULT BLOCK

End this file with STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS,
RISKS, RECOMMENDED CLAUDE ACTION.
