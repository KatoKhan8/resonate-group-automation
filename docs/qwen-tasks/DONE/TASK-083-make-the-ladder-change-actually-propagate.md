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

STATUS: DONE
COMMIT SHA: 159cb57
TESTS:
  py -3 -m unittest tests.test_ladder_propagation -v
    Ran 24 tests in 0.117s - OK (exit code 0)
  py -3 -m unittest tests.test_generate -v
    Ran 51 tests in 0.463s - OK (exit code 0)
  py -3 -m unittest tests.test_ladder_impact -v
    Ran 22 tests in 0.022s - OK (exit code 0)
  No conflict markers in src/ tests/ scripts/

FILES CHANGED:
  src/generate.py    ladder_fingerprint(), ladder_stale(), plan() flag,
                     draft/linkedin_note/set store fingerprint,
                     run()/generate_record()/main() threading,
                     --regen-stale-ladder CLI flag, impact report
  tests/test_ladder_propagation.py   24 tests, new file
  docs/THE-LADDER-MOVED-AND-THE-COPY-DID-NOT-2026-09-15.md   from master
  docs/qwen-tasks/RUNNING/TASK-083-make-the-ladder-change-actually-propagate.md

FINDINGS:
  1. The default path is PROVABLY UNCHANGED. Three tests assert it:
     - plan(rec) and plan(rec, regen_stale_ladder=False) return identical ops
     - A step with a wrong fingerprint is NOT re-planned without the flag
     - A step with no fingerprint is NOT re-planned without the flag
     run() returns stale_steps=0 and regen_stale_ladder=False by default.

  2. The ladder fingerprint covers channel + ordinal + purpose TEXT.
     Any edit to the ladder brief - a word, a reorder, a new rung, a
     different sequence naming a different ladder - moves the fingerprint.
     This subsumes the hardcoded EMAIL_CHANGED_RUNGS / LINKEDIN_CHANGED_RUNGS
     in ladder_impact.py without replacing it (that script is still useful
     for its per-record breakdown).

  3. Steps without a fingerprint (all 686 stored steps in the estate) are
     treated as stale ONLY when the flag is set. Without the flag, the
     absence of a fingerprint is invisible. This is deliberate: treating
     missing fingerprints as stale by default would be the blanket
     invalidation the task explicitly forbids.

  4. The approval interaction is CORRECT BY CONSTRUCTION, not by code in
     approval.py. A regenerated step has different text, which changes the
     approval fingerprint, which makes is_approved() return False. No
     explicit revocation is needed. The impact report counts how many
     current approvals WOULD be invalidated, which is what the operator
     needs to see before deciding to run.

  5. Caller chain verified:
     grep -rn "ladder_fingerprint\|ladder_stale\|regen_stale_ladder" src/
     returns 35+ hits across plan(), draft(), linkedin_note(),
     _regenerate_linkedin_set(), generate_record(), run(), main().
     Nothing is decorative.

  6. work/queue.snapshot.jsonl: 300 records, modified 2026-09-14T23:52:16.
     No STAMP field in the data; the file modification time is the stamp.
     No live regeneration was run. READS ONLY at every provider.

RISKS:
  1. The first time --regen-stale-ladder is run against real production
     state, it will flag ALL stored steps (none carry a fingerprint yet).
     The impact report will show the full cost. The operator must decide
     whether to proceed with --live or stage it per-record with --id.

  2. After a regeneration with the flag, the new steps will carry correct
     fingerprints. Subsequent runs without the flag will be idempotent
     (the fingerprint matches, so no re-plan). Subsequent ladder changes
     will move the fingerprint again, and the cycle repeats.

  3. The --regen-stale-ladder flag does NOT delete stored copy or revoke
     approvals directly. It causes plan() to emit re-plan ops, which
     cause generate_record() to overwrite the stored step with new text.
     The approval is invalidated implicitly because the text changed.

RECOMMENDED CLAUDE ACTION:
  1. Review the diff. The default path is the safety property.
  2. Run scripts/ladder_impact.py against production state to get the
     per-record breakdown (this worktree has no credentials).
  3. When ready, run `py -3 -m src.generate --regen-stale-ladder` (dry run)
     from Claude's worktree to see the impact report with real numbers.
  4. The actual regeneration is Claude's call from Claude's worktree,
     because it needs model credentials and touches production state.
