PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-463 — `untraceable_company_claim` refuses 592 of 1,323 real leads

**Filed as a finding, off the critical path, 2026-09-28.** Found incidentally
while verifying an unrelated claim about `empty_sentence`, and it is larger than
the thing being verified — which is why it is a task rather than a footnote.

## THE MEASUREMENT

In the as-stored shape, across the real store (`work/queue.jsonl`):

    untraceable_company_claim   592 of 1,323 rendered leads   44.7%

**That makes it the single largest refusal cause in the store today** — bigger
than every other copylint rule, and bigger than the `empty_sentence` defect that
`TASK-400` was built around.

Measured, not estimated. Re-derive before acting on it: the number came from
putting stored copy through today's copylint, so it is a statement about the copy
that exists now, not about a past run.

## WHY THIS IS NOT AUTOMATICALLY A BUG — READ THIS BEFORE "FIXING" ANYTHING

`untraceable_company_claim` is a **claim-licensing** rule: it fires when copy
asserts something about the prospect's company that no admitted evidence
supports. A high firing rate has at least four very different causes, and they
call for opposite responses:

1. **The copy really is making unsupported claims.** Then 44.7% is the gate doing
   its job and the fix is upstream, in generation.
2. **The evidence exists but is not admitted** — identity-bound to the wrong
   account, or refused by `identity_of`. Then the fix is in research/admission.
3. **The evidence was narrowed underneath the copy.** Two changes landed on
   2026-09-27: `TASK-330` made grounding bind a claim to the pack SENTENCE rather
   than a token anywhere in the pack, and `TASK-378` widened `SPECIFIC_RES` to
   single digits. Both tighten deliberately. **Copy written before them is being
   judged by rules that did not exist when it was written**, so some of the 592
   may be stale copy rather than bad copy.
4. **`CLIENT_SUPPLIED` facts stopped licensing claims** the same evening
   (decision B). Any claim that leaned on one of the six client-CSV fields now
   has no support by design.

**Causes 3 and 4 are known, recent and intentional.** So the first deliverable is
not a fix — it is an attribution.

## SCOPE

1. **Attribute the 592.** How many fire because of cause 1, 2, 3 or 4? Report the
   split with the method. A single number with no attribution is what this task
   exists to replace.
2. Name the most common shapes of unsupported claim, with the offending sentence
   pattern — **never a real prospect's name, company, email or domain in the
   committed report.** `work/` is gitignored because it is real companies and real
   contacts; report patterns and counts.
3. Say what would have to change upstream for the rate to fall **without
   touching the rule**, and what the rate would then be.

## WHAT THIS TASK MAY NOT DO

- **Never widen or weaken `untraceable_company_claim`, or any lint rule, to lower
  the number.** CLAUDE.md: "Never widen a lint rule to make a draft pass.
  Regenerate the draft." A high refusal rate on a claim-licensing gate is
  evidence, and this gate is one of the things standing between the product and
  a false statement about a real company.
- Do not change generation behaviour in this task. Measure and attribute; the
  fix is a separate task once the cause is known.
- Do not touch `docs/state/SUITE-BASELINE-2026-09-26.txt`.

## ACCEPTANCE

1. The 592 are attributed across the four causes (or others you find and name),
   each with its count and how it was determined.
2. Every number is re-derivable from a named source, and the report says which
   shape the copy was measured in — as-stored, or through a generation path.
3. No prospect PII in the committed report.
4. The rule is unchanged. `git diff` on `src/copylint.py` is empty.
5. A recommendation for the upstream fix, with the predicted rate after it, and
   a statement of what you did NOT verify.

Provider writes 0. Never call a real provider or model. The freeze is in force.
Do not touch campaigns 487/489/493. Reserved files tonight — do not edit:
`src/bisonfactory.py`, `src/generate.py`, `src/generate_campaign.py`,
`tests/test_generate.py`, `src/claims.py`, `src/executionguard.py`,
`src/copylint.py`.
