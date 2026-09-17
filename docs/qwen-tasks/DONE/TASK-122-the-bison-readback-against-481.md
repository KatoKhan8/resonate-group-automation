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

---

## RESULT

**STATUS: FAIL**

**COMMIT SHA:** fb47811

**TESTS:** `py -3 scripts/bison_readback.py productive-email-liheavy-v1 --expect`
exit code 1 (read off the process). 22 passed, 2 failed.

**FILES CHANGED:** none (read-only task)

---

### PASS/FAIL TABLE

Script exit code: **1** (FAIL)

```
CHECK                        EXPECTED     ACTUAL       VERDICT
campaign_id                  481          481          PASS
campaign_name                (matches)    (matches)    PASS
status                       paused       paused       PASS
step_count                   5            5            PASS
step_1_subject               {SUBJECT_1}  {SUBJECT_1}  PASS
step_1_body                  <p>{BODY_1}</p>  (same)   PASS
step_1_wait                  3            3            PASS
step_1_thread_reply          False        False        PASS
step_2_subject               {SUBJECT_2}  {SUBJECT_2}  PASS
step_2_body                  <p>{BODY_2}</p>  (same)   PASS
step_2_wait                  4            4            PASS
step_2_thread_reply          True         False        ** FAIL **
step_3_subject               {SUBJECT_3}  {SUBJECT_3}  PASS
step_3_body                  <p>{BODY_3}</p>  (same)   PASS
step_3_wait                  4            4            PASS
step_3_thread_reply          False        False        PASS
step_4_subject               {SUBJECT_4}  {SUBJECT_4}  PASS
step_4_body                  <p>{BODY_4}</p>  (same)   PASS
step_4_wait                  9            9            PASS
step_4_thread_reply          True         False        ** FAIL **
step_5_subject               {SUBJECT_5}  {SUBJECT_5}  PASS
step_5_body                  <p>{BODY_5}</p>  (same)   PASS
step_5_wait                  1            1            PASS
step_5_thread_reply          False        False        PASS
```

---

### PER-QUESTION FINDINGS

**1. Does the provider's step match what we believe we wrote?**

PASS for subject, body template, and wait on all 5 steps. The template
structure (`{SUBJECT_N}`, `<p>{BODY_N}</p>`) is intact. Wait days
(3, 4, 4, 9, 1) match exactly.

**2. Do `variant`, `variant_from_step` and `thread_reply` come back?**

Yes. All three fields are returned by `GET /campaigns/481/sequence-steps`:

| Step | variant | variant_from_step | thread_reply |
|------|---------|-------------------|--------------|
| 1    | false   | null              | false        |
| 2    | false   | null              | false        |
| 3    | false   | null              | false        |
| 4    | false   | null              | false        |
| 5    | false   | null              | false        |

`variant` and `variant_from_step` are populated by the provider (not
discarded by the trimmer). Both are `false`/`null` because no variants
are configured. `thread_reply` is the load-bearing field and it is
**wrong on steps 2 and 4**.

**3. Does the thread pattern match (F, T, F, T, F)?**

**FAIL.** Expected: `(False, True, False, True, False)`.
Actual at provider: `(False, False, False, False, False)`.

The pattern is carried ladder -> factory -> payload -> readback. The
last hop fails: the factory computed `thread_reply=True` for steps 2
and 4 (from `THREAD_REPLY_PATTERNS['email_five']`), but the provider
stores `false` for all five. The pattern was never written, or was
written and discarded.

This is the exact defect `bison_readback.py` was built to catch: a
follow-up step meant to be same-thread that landed as a new thread.

**4. Does the greeting render?**

PASS (no broken greetings found). Checked all 14 leads with email copy
(70 bodies total, 5 steps x 14 leads). No instance of:
- "Hey ," / "Hi ," / "Hello ," (empty name)
- "Hi undefined," / "Hi null," / "Hi None," (literal placeholder)
- Bare comma greeting

Bodies do not use personal greetings at all. They open with company
observations: "I noticed that X focuses on...", "X states that they
help...", "X highlights expertise in...". Five of 14 open with
"I noticed/I see/I wanted"; the remaining 9 open with the company
name directly. No greeting-line defect is possible because no
greeting line exists.

**5. Is the sender identified in a signature?**

**FAIL.** 0 of 70 bodies contain a sender name (either of the two humans
whose inboxes 481 was attached to), email domain (dont<client-e1c53a>.com),
or closing
formula ("Regards", "Best,", "Sincerely", "Thanks,"). Bodies end with
a question or a generic closing ("Thank you for your time.", "I
appreciate your time and consideration. Thank you.") but never
identify who is sending.

EmailBison has no sender-signature merge variable; the signature must
be in the body text itself. It is not.

**6. Are any two of the five steps the same message?**

At the template level: PASS. All 5 steps have distinct templates
(`{SUBJECT_1}` through `{SUBJECT_5}`, `{BODY_1}` through `{BODY_5}`).

At the copy level (per-lead custom variables):
- **Bodies**: No lead has two steps with identical body text. All 70
  bodies are unique.
- **Subjects**: 2 of 14 leads have `subject_2 == subject_4` (both
  "Exploring Profitability Insights for {company}"). 1 lead has
  `subject_1 == subject_2`, `subject_1 == subject_3`, and
  `subject_1 == subject_4`. These are generated copy, not template
  defects - the generator produced the same subject for different
  steps.

---

### ADDITIONAL FINDINGS

**Lead copy completeness (n=23 leads at provider):**
- 14 leads have complete email copy (5 bodies + 5 subjects + metadata)
- 6 leads have only `headline` and `location` custom variables
  (LinkedIn-oriented, no email copy)
- 3 leads have no custom variables at all

The 9 leads without email copy were attached to the campaign but
never had email drafts generated. The campaign is "LIHEAVY-V1"
(LinkedIn-heavy), which explains LinkedIn-only leads. But the
sequence is 5 email steps, and those 9 leads will receive nothing if
the campaign is activated for email.

**Campaign state confirmed:**
- Provider status: `paused`
- `emails_sent`: 0
- `total_leads_contacted`: 0
- `total_leads`: 23
- Campaign is safe to inspect; nothing has been sent.

**Pagination note:** The leads endpoint IS paginated (15 per page,
2 pages for 23 leads). The `sequence_steps` endpoint is NOT paginated
(confirmed: all 5 steps in one response, `?page=2` returns the same
5). The readback script uses `sequence_steps` which is correct.

---

### OBSERVATIONS

1. The thread_reply pattern (F,T,F,T,F) was computed correctly by the
   factory but is not stored at the provider (n=5 steps, 2 mismatches).
2. No sender signature exists in any of the 70 generated bodies
   (n=70, 0 with signature).
3. Subject duplication across steps occurs for 3 of 14 leads (n=14,
   3 with at least one duplicate subject pair).
4. 9 of 23 leads at the provider have no email copy (n=23, 9 without).

### HYPOTHESES

1. The `thread_reply` flag was never sent to the provider during
   `set_sequence`. The factory's `_sequence_steps` computes it, but
   `_ensure_sequence` may not pass it in the POST payload. This is
   the most likely cause - the field is computed but not transmitted.
2. The missing signatures are a generator issue: the copy prompt does
   not instruct the model to include a sender sign-off, and EmailBison
   has no signature merge variable to fall back on.
3. The subject duplication is a generator issue: different steps with
   similar themes (profitability, identity resolution) produce the
   same subject line for the same company.

### PROVEN LEARNINGS

1. `bison_readback.py` works. It caught the thread_reply defect it was
   built to catch. Exit code 1 on FAIL, read off the process.
2. The provider returns `variant`, `variant_from_step`, and
   `thread_reply` on `sequence_steps`. The trimmer (TASK-073) now
   carries all three.
3. The thread_reply pattern does NOT survive the write to the
   provider. The factory computes it; the provider does not store it.
   The gap is in the write path, not the read path.

### RISKS

- If campaign 481 is activated without fixing thread_reply, steps 2
  and 4 will send as new threads instead of follow-ups. This is the
  defect the readback caught.
- If activated without fixing signatures, all emails will go out
  without identifying the sender.
- The 9 leads without email copy will be skipped by the sequence
  (their `{BODY_N}` variables are empty/absent).

### RECOMMENDED CLAUDE ACTION

1. **Fix the thread_reply write path.** The factory computes
   `thread_reply` per step but the POST to
   `/campaigns/{id}/sequence-steps` may not include it. Trace from
   `_ensure_sequence` through `set_sequence` to the JSON payload and
   prove the flag is in it. Then re-stage campaign 481 (dry run
   first) and re-run this readback.
2. **Fix the signature gap.** Add a sender sign-off instruction to
   the copy generation prompt, or add a signature block to the body
   template.
3. **Do not activate campaign 481** until both fixes are in place and
   the readback passes.
