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
