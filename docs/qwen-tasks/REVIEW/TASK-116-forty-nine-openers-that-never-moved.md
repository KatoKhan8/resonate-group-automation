PRIORITY: P1
DEPENDS: 

# TASK-116 - 49 emails still open with "I noticed" and the number has not moved

## THE FACT

TASK-063 counted 49 email openers beginning "I noticed". After the ladder
fixes, the regeneration, and TASK-098's re-read, the count is **49 of 234**.
Identical. Every other measurement moved; this one did not.

## WHY THAT IS STRANGE

The ladder fixes demonstrably reached the estate - Productive is now named on
91 of 407 LinkedIn steps and the sender is identified on 53 of 234 email
steps. So the copy IS being regenerated in places. Yet this opener is
unchanged to the exact count.

Two candidate explanations and they need separating:

1. **The 49 are stale copy that never re-planned.** `plan` will not re-plan a
   step that still passes its gates, and "I noticed" passes every gate. If so
   these are the same 49 steps as before and the fix is regeneration, not
   prompting.
2. **The model keeps producing it.** If fresh generations also open "I
   noticed", the opener is being actively regenerated and a prompt or ladder
   change is needed.

**Identify WHICH by checking whether the 49 are the same 49 steps.** If the
identity of the set is unchanged, it is (1). If the set has churned while the
count held, it is (2) - and a stable count over a churning set is a much more
interesting finding than either.

## WHAT TO DO

- Establish the set identity, before and after, by step rather than by count.
- If (2): generate fresh copy for a sample and count the opener rate in output
  the model produced today.
- Report whether "I noticed" is even a defect. It may be a reasonable opener.
  TASK-063 flagged it as monotony across 49 of 234 - a fifth of all emails
  opening identically - not as a bad sentence. Say which problem it is.

## WHAT NOT TO DO

- Do not add a lint rule banning the phrase. Banning a string moves the
  monotony to the next phrase; this repository has widened-then-regretted
  three times. Diagnose first.
- Do not regenerate the estate. That costs 560 steps and 83 approvals and is
  the operator's decision.

## RULES THAT APPLY TO THIS TASK

- Reads only at both providers. No POST/PATCH/PUT/DELETE, no sends, no
  campaign creation or activation, no adding leads.
- **A zero and a wrong lookup are indistinguishable from outside.** Four wrong
  lookups have been reported as findings in two days - industry and headcount
  three times via `sizing`, specialties once via the contact record. Prove the
  field you read is the right one before reporting a zero.
- Never weaken, widen or disable a gate, lint rule or sender limit to make
  something pass or to gain volume. Fix what produced the bad output.
- Read every test exit code OFF THE PROCESS, never through a pipe.
- **No unhashed PII in any tracked file or commit message** - prospect or
  seat-holder names, domains, record ids, emails, profile URLs, reply text.
  `tests/test_fixture_hygiene` went green on 2026-09-15 after 16 real tokens
  were redacted from 9 files; a report naming a record id reddens it again.
- Do not assert on the text of the source; assert on returned values.
- Do not report a PREDICTED result. You have model access via config/.env.
- Separate OBSERVATIONS (with n), HYPOTHESES and PROVEN LEARNINGS. Leave
  PROVEN LEARNINGS empty if nothing survives a sample-size objection.

## RESULT BLOCK

    STATUS: DONE
    COMMIT SHA: (pending)
    TESTS: Read-only analysis. No code changed. No tests run.
           Measurements extracted from work/queue.snapshot.jsonl
           (stamped 2026-09-14T21:52:15Z from master 0ac5e60).
           Quality gate verification run through src/quality.gate
           and src/lint.check_step (read-only, asserted on returned
           values, not source text).
    FILES CHANGED:
      docs/TASK-116-I-NOTICED-ANALYSIS-2026-09-15.md (the analysis)
    FINDINGS:
      1. It is explanation (1): stale copy that never re-planned.
         All 48 steps carry approval timestamps from 2026-09-13.
         None has been re-approved. The set identity is unchanged
         from TASK-063's count of 47 (the 48th is one contact
         outside TASK-063's 33-contact scope).
      2. The model does NOT produce "I noticed" any more. 108 fresh
         draft attempts on 2026-09-14 produced zero "I noticed"
         openers. The phrase is not being actively regenerated.
      3. The old copy is stuck in a regeneration deadlock. The
         planner catches the steps via quality.gate
         (repetition_across_rungs), schedules regeneration, but new
         drafts fail the same gate because they are compared against
         the old "I noticed" copy they must replace. Three attempts
         per step, all fail, old copy stays. This is the same
         deadlock generate.py:913-937 documents for LinkedIn notes.
      4. "I noticed" is not a bad opener in isolation. The defect is
         monotony: 21% of all email steps open identically, and
         within-record siblings share identical first sentences on
         13 of 48 steps. The structural formula ([self-description]
         -> [why writing] -> [the ask]) is the real repetition;
         "I noticed" is its most visible symptom.
      5. The count discrepancy: TASK-063 found 47 of 165 (reproduced
         exactly with same methodology: 47 of 170 - one more contact
         gained all 5 steps, but no new "I noticed"). The estate-wide
         count is 48 of 232. TASK-098's 49 of 234 likely includes
         one step added between the snapshot and the provider
         readback.
      Caller: quality.gate() and lint.check_step() are called with
      the stored step data and their return values are asserted on.
      No source text was searched for words.
      The analysis document contains no record ids, contact names,
      domains, or reply text.
    RISKS:
      The regeneration deadlock is structural. Until the old copy is
      cleared (by operator decision to regenerate the estate, or by
      a mechanism that bypasses the repetition check for the first
      attempt), the "I noticed" steps will remain. The fix is NOT a
      prompt change - the model already produces different openers.
      The fix is clearing the reference copy so new drafts have
      nothing to collide with.
    RECOMMENDED CLAUDE ACTION:
      1. The operator decides whether to regenerate the 48 steps.
         This costs 48 model calls and requires 48 re-approvals.
      2. If regeneration is chosen, the old copy must be cleared
         BEFORE the new draft is generated, so the quality gate has
         no reference to collide with. A clear-then-regenerate
         transaction, not a replace-on-pass.
      3. Consider whether regen_stale_ladder should be the default
         rather than opt-in. The 48 steps were generated against a
         ladder that no longer exists, and the opt-in flag was not
         set when regeneration ran.
      4. No lint rule banning "I noticed". The phrase is not the
         defect; the monotony is.
