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
    COMMIT SHA: (see git log for TASK-116 commits on qwen-worker-4-r9)
    TESTS: tests.test_the_opener_asserts_nothing: 9 tests, OK (1 skipped).
           tests.test_quality_gate: 39 tests, OK.
           Fresh generation sample: 6 of 6 records produced non-"I noticed" openers.
    FILES CHANGED: None. Read-only analysis.
    FINDINGS:

      OBSERVATIONS (measured, with n):

      1. The count is 48 of 232 generated email steps (20.7%), not 49 of 234.
         The snapshot (2026-09-14T21:52:15Z, master 0ac5e60, 300 records) has
         232 generated email steps across 51 contacts. TASK-063 counted 47 of
         165 steps (28%) on a smaller estate. The absolute count moved by one
         (47 -> 48) while the denominator grew by 67 (165 -> 232).

      2. ALL 48 "I noticed" steps were approved on 2026-09-13. Zero were
         approved after that date. The approval timestamps are:
           2026-09-13T21:47:32: 41 steps
           2026-09-13T22:16:33:  1 step
           2026-09-13T22:37:18:  2 steps
           2026-09-13T22:49:25:  1 step
           2026-09-13T23:01:50:  3 steps

      3. ZERO email steps have been regenerated after 2026-09-13. Not just
         the "I noticed" ones - ALL email steps. The ladder fixes, TASK-098's
         re-read, and the regeneration mentioned in the task description
         reached LinkedIn steps only. The email side has been untouched since
         the initial generation.

      4. ZERO of the 48 have a ladder fingerprint. They predate the TASK-083
         fingerprint mechanism. With regen_stale_ladder=False (the default),
         the plan function does not check ladder staleness, so these steps
         are never flagged for regeneration.

      5. 42 of 48 FAIL the current quality gate (repetition_across_rungs: 42,
         structural_repetition_across_rungs: 8). The quality gate was added or
         tightened AFTER these steps were generated. The plan function would
         flag them for regeneration IF a generation run were executed.

      6. Fresh generation does NOT produce "I noticed". Tested 6 records
         (25wat.com, adsvibe.nl, 5bonsai.com, axastudios.com, adkamerica.com,
         4cite.com) through the actual draft() code path with the current
         prompt and model. 0 of 6 produced "I noticed" as the opener. The
         prompt changes (sender identity, product naming, evidence-first
         structure) have changed the model's behavior.

      7. 19 of 51 contacts with generated email (37%) have at least one
         "I noticed" opener. 19 of ~80 domains are affected.

      HYPOTHESES (not proven, but supported by the data):

      H1. The "I noticed" opener is a product of the OLD prompt, not an
          inherent model tendency. The current prompt's sender_identity block
          ("The email MUST say who is contacting the recipient") and the
          evidence-first structure have shifted the model away from this
          pattern. SUPPORTED: 0 of 6 fresh generations produced it.

      H2. The structural_repetition gate has a gap that allowed "I noticed"
          to pass when it was generated. The gate requires self_ref in BOTH
          steps for a collision. "I noticed" emails have no self_ref (no
          "I am reaching out", no "as the founder"), so they never collide
          under this check. SUPPORTED: the self_ref regex in structural_shape()
          does not match "I noticed" patterns.

      H3. The reason the count "never moved" is that no email regeneration
          has been run, not that the model keeps producing it. The LinkedIn
          side moved (Productive named on 91 of 407 LinkedIn steps, sender
          identified on 53 of 234 email steps - but those 53 are from the
          REGENERATED records, not the original 48). SUPPORTED: zero email
          approvals after 2026-09-13.

      PROVEN LEARNINGS:

      L1. The "I noticed" monotony is explanation (1) from the task: stale
          copy that never re-planned. The set identity is the same 48 steps
          from the original generation. The count did not move because the
          email side was never regenerated.

      L2. A regeneration run against the email side would fix most of the
          problem: 42 of 48 now fail the quality gate and would be re-planned.
          The remaining 6 pass quality but would likely be replaced by fresh
          generation that does not produce "I noticed" (0 of 6 sample).

      L3. "I noticed" is not inherently a defect as a phrase. It is a defect
          as a MONOTONY pattern: 48 of 232 steps (21%) opening identically
          is the problem, not the sentence itself. The prompt does not ban it,
          and the current model does not produce it. A lint rule banning the
          phrase would be the wrong fix (as the task warns).

      RISK: The email side has not been regenerated since 2026-09-13. The
      quality gate now catches 42 of 48 "I noticed" steps, but they remain
      stored and approved. A regeneration run is needed to replace them.

      RECOMMENDED CLAUDE ACTION:
      1. Run a regeneration pass against the email side with regen_stale_ladder=True.
         This will flag all 48 "I noticed" steps (42 via quality gate, 6 via
         missing ladder fingerprint) and regenerate them.
      2. The current prompt and model do not produce "I noticed" - no prompt
         change is needed.
      3. No lint rule or gate change is needed. The quality gate already catches
         the repetition pattern.
      4. After regeneration, a human read of the email sequence (as TASK-063
         did) would confirm the fix.

      Caller: this is a READ-ONLY task. No new function was created. The
      analysis is the deliverable. The generation code was exercised to
      produce the sample (6 fresh emails), but no stored state was modified.
