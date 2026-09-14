# TASK-039 - What the model actually gets, per message

Operator backlog: QWEN-20, personalisation evidence-pack quality.

## GOAL

An audit of the evidence pack reaching the model for each generated step, and
of how much of it is real.

## WHY IT MATTERS

Copy quality has been the bottleneck all week and every fix so far has been to
the GATES - lint, claims, quality, siblings. Nothing has audited the INPUT.
A model given a thin pack writes thin copy, and the gates then reject it,
which reads as a model problem and is not.

`claims.check` refuses a draft asserting anything the record does not support,
so a pack with little in it does not merely produce weak copy - it produces
copy that cannot pass.

## CURRENT FACTS

- `src/contextpack.py`, `src/evidence.py`, `src/dossier.py` and
  `src/observations.py` build and license what may be said.
- `ACCOUNT-INTELLIGENCE.md` is explicit that a signal is NOT a licence to say
  it: "a hiring signal is a reason to prioritise an account, not permission to
  write 'i saw you're hiring'".
- 43 stored steps assert something unsupported today, across 20 records.

## SCOPE

1. For a sample of records across the estate, dump what the pack CONTAINS -
   counts and kinds, not prose - and how many items are licensed to be said
   versus merely known.
2. Distribution: how many records have zero sayable evidence? Those are the
   records where good copy is impossible, and knowing how many there are is
   the deliverable.
3. Correlate pack size with whether that record's steps passed the gates. If
   thin packs predict gate failures, that is the finding and it redirects the
   whole copy effort.
4. Do NOT widen what may be said. If the conclusion is "most records cannot
   support a personalised sentence", that is the answer and it belongs in
   FINDINGS.

## PRODUCTION BOUNDARY

ZERO network. ZERO credentials - `config/.env` does not exist in this
worktree and a task that tries to obtain one has misunderstood its job. No
provider call. No write to `work/**`. Nothing is staged, activated or sent.

## HANDOFF FORMAT

Return ONLY this, concisely:

    STATUS / COMMIT SHA / FILES CHANGED / TESTS RUN / TEST RESULTS /
    BUGS FOUND / BUGS FIXED / RISKS / OPEN QUESTIONS /
    RECOMMENDED CLAUDE ACTION

Plus, required of every task since 2026-09-14: the output of
`grep -rn "<each new name you added>" src/` proving it is CONSUMED, and
confirmation that deleting the CALL to your new code makes a test fail.

## TESTS REQUIRED

- a record with no licensed evidence produces a pack that says so, rather than
  an empty one indistinguishable from an unbuilt one;
- an observation that is known but not licensed never appears as sayable;
- the audit script's counts are tested on an invented record with a known
  answer.

## DONE CONDITION

A report with the distribution, the zero-evidence count, and the correlation
between pack size and gate outcome.
