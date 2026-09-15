PRIORITY: P2
DEPENDS: 

# TASK-122 - run the EmailBison readback against the paused campaign

## WHY THIS IS STILL OPEN

`scripts/bison_readback.py` was BUILT and has never been run against a live
campaign. TASK-091 was dispatched for this; check its result first - if it
ran, this task verifies and extends rather than repeats.

The HeyReach side has 27/27 PASS on campaign 599020, re-verified after every
change. EmailBison has no equivalent proof.

## THE TARGET

    481   RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOUSTON
          paused, 23 leads, 5 provider steps, 0 sent

Paused with real steps and real leads and nothing sent - the safest possible
subject. **It stays paused.**

## WHAT TO ESTABLISH, PER STEP

1. Does the provider's step match what we believe we wrote?
2. Do `variant`, `variant_from_step` and `thread_reply` come back? The trimmer
   discarded all three until TASK-073; this is the first chance to see whether
   the provider populates them on OUR campaign.
3. Does the thread pattern match `THREAD_REPLY_PATTERNS['email_five']` =
   (F, T, F, T, F)? That pattern is carried ladder -> factory -> payload ->
   readback. Prove the last hop.
4. **Does the greeting render?** There is no `first_name` and no `company`
   merge variable at EmailBison - the body travels as `body_N` - so a broken
   greeting is not caught by the provider and reaches a person. Check for
   "Hey ,", "Hi undefined,", "Hi null," and a bare comma.
5. Is the sender identified in a signature?
6. Are any two of the five steps the same message?

## WHAT NOT TO DO

- **No writes.** No PATCH, POST, PUT or DELETE. Do not unpause 481, do not add
  a lead, do not activate anything.
- Do not use `meta.total` as a sent count - count rows WHERE `sent_at` IS
  PRESENT.
- Do not set `per_page` and believe it; it is accepted and ignored.
- Hash prospect addresses in the report.

## DELIVERABLE

A PASS/FAIL table in the shape of the HeyReach one with the exit code read off
the process. **If it FAILS, the failure is the deliverable** - do not repair
the copy to make the readback pass.

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
