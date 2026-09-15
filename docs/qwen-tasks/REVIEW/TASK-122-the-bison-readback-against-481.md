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

## RESULT

**STATUS:** DONE
**COMMIT SHA:** 862c425
**TESTS:** `py -3 scripts/bison_readback.py productive-email-liheavy-v1 --expect` → exit code 1 (22 PASS, 2 FAIL)
**FILES CHANGED:**
- `docs/BISON-READBACK-481-2026-09-15.md` (new - deliverable)

**FINDINGS:**

1. **thread_reply FAIL on steps 2 and 4.** Expected (F,T,F,T,F), observed
   (F,F,F,F,F). The ladder, factory, and readback script all compute the
   correct pattern. The campaign was staged on 2026-09-13T20:11, before
   TASK-081 added `thread_reply` to the sequence writer (integrated
   2026-09-14T23:58). The provider defaulted all steps to `false`.

2. **variant and variant_from_step come back.** Both fields are present in
   the provider response (false and null respectively). The TASK-073 trimmer
   fix is confirmed working end-to-end.

3. **No broken greetings.** 0 of 115 bodies (23 leads × 5 steps) contain
   "Hey ,", "Hi undefined,", "Hi null,", or a bare comma greeting.

4. **No signatures.** 0 of 115 bodies contain a sign-off. EmailBison has no
   sender merge variable, so the signature must be in the body text. The
   copy was generated before the ladder instructed the generator to include
   one.

5. **No duplicate bodies.** All five body_N values are distinct for every
   lead. 3 of 23 leads have duplicate subjects (steps 2 and 4 share a
   subject line), but the bodies are always different.

6. **Campaign state confirmed:** paused, 23 leads, 0 emails sent, 0
   contacted.

**OBSERVATIONS:**
- (n=115) Zero bodies start with a greeting. The generated copy begins
  directly with the message content. This is a property of the generated
  copy, not a provider or trimmer defect.
- (n=3 of 23) Subject line duplication across steps. The generator produced
  the same subject for different steps on 3 leads. Bodies remain distinct.

**HYPOTHESES:**
- Re-staging campaign 481's sequence would fix the thread_reply defect,
  since the current code writes the field correctly. The campaign would need
  to be rebuilt (sequence route appends, no replace).

**PROVEN LEARNINGS:**
- The bison_readback script catches the exact defect it was built to catch:
  a step meant as a follow-up that landed as a new thread. The readback is
  now proven against a live campaign for the first time.

**RISKS:**
- Campaign 481 cannot be fixed in place. The sequence route appends and has
  no replace or delete. Fixing thread_reply requires rebuilding the campaign
  (new provider id, re-attach leads).

**RECOMMENDED CLAUDE ACTION:**
- Review the deliverable at `docs/BISON-READBACK-481-2026-09-15.md`.
- Decide whether to re-stage campaign 481 (requires a new provider campaign
  since the sequence route appends) or leave it as-is for the experiment.
- TASK-091 is in REVIEW with the same finding; consolidate or close.
