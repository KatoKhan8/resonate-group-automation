PRIORITY: P1
DEPENDS: 

# TASK-120 - what is actually inside the 560 steps and 83 approvals

## THE DECISION THIS SERVES

`py -3 -m src.generate --regen-stale-ladder --client productive` reports:

    steps to re-plan:               560
    approvals that would be revoked:  83

**Revoking 83 human approvals is an operator decision** and it has not been
taken. Two numbers are not enough to make it on. This task makes the decision
informed without making it.

## WHAT TO PRODUCE - ALL DRY RUN

1. **What are the 560?** Break them down by channel, by step position, by
   record, and by WHY each is stale. A step stale because it predates the
   ladder fix is a different case from one stale because the ladder text moved
   since. Checkpoint D notes that today every stored step has NO fingerprint
   at all, so all of them are stale "regardless of what the ladder currently
   says" - confirm whether that is still true after any fingerprinted
   generation has run.
2. **What are the 83?** Which records, which steps, how old is each approval,
   and would the regenerated step plausibly need the same approval again?
3. **What would the estate look like AFTER?** Take a sample of stale steps,
   generate their replacements in dry run, and compare against the current
   copy on the measures that matter: Productive named, sender identified,
   ladder progression, "I noticed" openers, duplicate follow-ups.

That third item is the one that decides it. **If regenerated copy does not
measurably beat what is stored, the 83 approvals buy nothing.**

## WHAT NOT TO DO

- **Do not run the regeneration live.** Dry run only. The flag is opt-in and
  reports before it acts, and this task does not change that.
- Do not approve anything. Do not un-approve anything.
- Do not conclude "regenerate" or "do not regenerate". Produce the evidence;
  the decision is the operator's.

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
