# EmailBison Readback: Campaign 481

**Date:** 2026-09-15
**Campaign:** productive-email-liheavy-v1 (provider id 481)
**Name:** RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - BUYER - LIHEAVY-V1
**Status:** paused
**Leads:** 23
**Emails sent:** 0
**Script:** `scripts/bison_readback.py productive-email-liheavy-v1 --expect`
**Exit code:** 1 (FAIL)

---

## PASS/FAIL Table

| # | Check | Expected | Actual | Verdict |
|---|-------|----------|--------|---------|
| 1 | campaign_id | 481 | 481 | PASS |
| 2 | campaign_name | RESONATE - PRODUCTIVE - EMAI... | RESONATE - PRODUCTIVE - EMAIL... | PASS |
| 3 | status | paused | paused | PASS |
| 4 | step_count | 5 | 5 | PASS |
| 5 | step_1_subject | {SUBJECT_1} | {SUBJECT_1} | PASS |
| 6 | step_1_body | \<p\>{BODY_1}\</p\> | \<p\>{BODY_1}\</p\> | PASS |
| 7 | step_1_wait | 3 | 3 | PASS |
| 8 | step_1_thread_reply | False | False | PASS |
| 9 | step_2_subject | {SUBJECT_2} | {SUBJECT_2} | PASS |
| 10 | step_2_body | \<p\>{BODY_2}\</p\> | \<p\>{BODY_2}\</p\> | PASS |
| 11 | step_2_wait | 4 | 4 | PASS |
| 12 | **step_2_thread_reply** | **True** | **False** | **FAIL** |
| 13 | step_3_subject | {SUBJECT_3} | {SUBJECT_3} | PASS |
| 14 | step_3_body | \<p\>{BODY_3}\</p\> | \<p\>{BODY_3}\</p\> | PASS |
| 15 | step_3_wait | 4 | 4 | PASS |
| 16 | step_3_thread_reply | False | False | PASS |
| 17 | step_4_subject | {SUBJECT_4} | {SUBJECT_4} | PASS |
| 18 | step_4_body | \<p\>{BODY_4}\</p\> | \<p\>{BODY_4}\</p\> | PASS |
| 19 | step_4_wait | 9 | 9 | PASS |
| 20 | **step_4_thread_reply** | **True** | **False** | **FAIL** |
| 21 | step_5_subject | {SUBJECT_5} | {SUBJECT_5} | PASS |
| 22 | step_5_body | \<p\>{BODY_5}\</p\> | \<p\>{BODY_5}\</p\> | PASS |
| 23 | step_5_wait | 1 | 1 | PASS |
| 24 | step_5_thread_reply | False | False | PASS |

**Result: 22 passed, 2 failed**

---

## Per-Step Analysis

### 1. Does the provider's step match what we believe we wrote?

**Subject, body, and wait: YES for all five steps.** Every subject template
(`{SUBJECT_1}` through `{SUBJECT_5}`), every body template (`<p>{BODY_1}</p>`
through `<p>{BODY_5}</p>`), and every wait (3, 4, 4, 9, 1) match exactly.

**thread_reply: NO for steps 2 and 4.** Expected True (follow-up in the same
thread), got False (new thread). The pattern at the provider is (F, F, F, F, F)
instead of (F, T, F, T, F).

### 2. Do `variant`, `variant_from_step` and `thread_reply` come back?

**Yes, all three fields are present in the provider response.** The TASK-073
trimmer fix preserves them through the read path:

| Field | Step 1 | Step 2 | Step 3 | Step 4 | Step 5 |
|-------|--------|--------|--------|--------|--------|
| variant | false | false | false | false | false |
| variant_from_step | null | null | null | null | null |
| thread_reply | false | false | false | false | false |

`variant` = false and `variant_from_step` = null are correct: this campaign
does not use A/B variants. `thread_reply` = false for ALL five steps is the
defect.

### 3. Does the thread pattern match `THREAD_REPLY_PATTERNS['email_five']`?

**No.** The ladder defines `(False, True, False, True, False)`. The factory
computes this correctly - `bisonfactory._sequence_steps` produces the expected
pattern. The readback script confirms the expected values. But the provider
holds `false` for every step.

**Root cause:** Campaign 481 was staged on 2026-09-13T20:11. TASK-081, which
added `thread_reply` to the sequence payload, was integrated on
2026-09-14T23:58. The campaign was staged **before** the code could write
`thread_reply` to the provider. The sequence was written without the field,
and the provider defaulted every step to `false` (new thread).

The chain ladder → factory → payload is proven correct in the code. The last
hop (payload → provider storage) was never made for this campaign because it
predates the feature.

### 4. Does the greeting render?

**No broken greetings found.** Scanned all 115 bodies (23 leads × 5 steps)
for:
- "Hey ,", "Hi ,", "Hello ," (empty name)
- "Hi undefined,", "Hi null,", "Hi None," (literal placeholder)
- Bare comma after greeting word: `(Hi|Hey|Hello)\s+,`

**Zero matches.** No greeting defect reached the provider.

**Observation:** Zero of 115 bodies start with a greeting at all. The
generated copy begins directly with the message body (e.g., "I noticed that
Semcasting focuses on..."). This is not a defect in the provider or the
trimmer - it is a property of the generated copy itself. Whether a greeting
should be present is a copy-design question, not a readback question.

### 5. Is the sender identified in a signature?

**No signature found in any of the 115 bodies.** Scanned the last 200
characters of every body for "Best,", "Regards,", "Thanks,", "Cheers,",
"Sincerely," followed by a name.

**Zero matches.** EmailBison has no `{first_name}` or `{sender_name}` merge
variable - the body travels as `{BODY_N}` - so a signature must be part of
the generated body text. The current copy does not include one.

This is consistent with TASK-080's finding: sender identity was in zero of
165 email steps before the ladder fix. The ladder now instructs the generator
to include a signature, but campaign 481's copy was generated before that
fix. Like the thread_reply defect, this is a staging-timestamp issue, not a
code defect.

### 6. Are any two of the five steps the same message?

**No duplicate bodies.** For every lead, all five `body_N` values are
distinct.

**Duplicate subjects:** 3 of 23 leads have at least one pair of identical
subjects:
- Lead 1 (hash `ee5cd91b094a`): subject_4 = subject_2
- Lead 3 (hash `062eb4bd3473`): subject_4 = subject_2, subject_2 duplicate
- Lead 19 (hash `836de1843ccc`): subject_3 = subject_2

The body text is always distinct even when subjects repeat, so this is not a
send-safety defect (no duplicate message). It is a copy-variety observation:
the generator produced the same subject line for different steps on 3 of 23
leads.

---

## Campaign State

| Field | Value |
|-------|-------|
| Provider ID | 481 |
| Canonical ID | productive-email-liheavy-v1 |
| Status | paused |
| Total leads | 23 |
| Emails sent | 0 |
| Total contacted | 0 |
| Completion | 0% |
| Created | 2026-09-13T20:11:34Z |
| Updated | 2026-09-13T22:17:13Z |

---

## Summary

The readback caught the exact defect it was built to catch: steps 2 and 4
were meant to be same-thread follow-ups (`thread_reply: true`) but landed as
new threads (`thread_reply: false`) at the provider. The root cause is that
campaign 481 was staged before `thread_reply` support was added to the
sequence writer. The fix is to re-stage the campaign's sequence, which will
write the correct thread_reply values.

Everything else matches: subjects, bodies, waits, lead count, sent count.
No broken greetings, no duplicate bodies. The `variant` and `variant_from_step`
fields survive the round-trip (both correctly false/null for a non-A/B
campaign).
