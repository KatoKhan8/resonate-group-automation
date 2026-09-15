# EmailBison provider readback, 2026-09-15

Read from the provider, read-only. Nothing was written. Every line below came
back from `GET /campaigns/{id}`, `GET /campaigns/{id}/sequence-steps` and
`GET /campaigns/{id}/leads`. The readback script is
`scripts/bison_readback.py` and it ran with `--expect`.

---

## THE TWO CAMPAIGNS

    canonical id                            provider id  status      leads
    productive-canary-email-2026-09-13      451          completed       1
    productive-email-liheavy-v1             481          paused         23

451 is the single-step canary. 481 is the five-step production campaign.

---

## CAMPAIGN 451 - READBACK

Exit code: **1** (FAIL). 5 passed, 3 failed.

| CHECK              | EXPECTED     | ACTUAL       | VERDICT |
|--------------------|--------------|--------------|---------|
| campaign_id        | 451          | 451          | PASS    |
| campaign_name      | (canary)     | (canary)     | PASS    |
| status             | completed    | completed    | PASS    |
| step_count         | 5            | 1            | FAIL    |
| step_1_subject     | {SUBJECT_1}  | {SUBJECT}    | FAIL    |
| step_1_body        | \<p\>{BODY_1}\</p\> | \<p\>{BODY}\</p\> | FAIL |
| step_1_wait        | 3            | 3            | PASS    |
| step_1_thread_reply| False        | False        | PASS    |

**Root cause:** The canary was created before the multi-step shape. The
canonical state was later updated to five steps but the provider still holds
the original single-step form using unnumbered `{SUBJECT}` and `{BODY}`
variables. This is a known shape mismatch, not a provider defect.

---

## CAMPAIGN 481 - READBACK

Exit code: **1** (FAIL). 22 passed, 2 failed.

| CHECK                | EXPECTED   | ACTUAL     | VERDICT  |
|----------------------|------------|------------|----------|
| campaign_id          | 481        | 481        | PASS     |
| campaign_name        | (full)     | (full)     | PASS     |
| status               | paused     | paused     | PASS     |
| step_count           | 5          | 5          | PASS     |
| step_1_subject       | {SUBJECT_1}| {SUBJECT_1}| PASS     |
| step_1_body          | \<p\>{BODY_1}\</p\> | \<p\>{BODY_1}\</p\> | PASS |
| step_1_wait          | 3          | 3          | PASS     |
| step_1_thread_reply  | False      | False      | PASS     |
| step_2_subject       | {SUBJECT_2}| {SUBJECT_2}| PASS     |
| step_2_body          | \<p\>{BODY_2}\</p\> | \<p\>{BODY_2}\</p\> | PASS |
| step_2_wait          | 4          | 4          | PASS     |
| **step_2_thread_reply** | **True** | **False** | **FAIL** |
| step_3_subject       | {SUBJECT_3}| {SUBJECT_3}| PASS     |
| step_3_body          | \<p\>{BODY_3}\</p\> | \<p\>{BODY_3}\</p\> | PASS |
| step_3_wait          | 4          | 4          | PASS     |
| step_3_thread_reply  | False      | False      | PASS     |
| step_4_subject       | {SUBJECT_4}| {SUBJECT_4}| PASS     |
| step_4_body          | \<p\>{BODY_4}\</p\> | \<p\>{BODY_4}\</p\> | PASS |
| step_4_wait          | 9          | 9          | PASS     |
| **step_4_thread_reply** | **True** | **False** | **FAIL** |
| step_5_subject       | {SUBJECT_5}| {SUBJECT_5}| PASS     |
| step_5_body          | \<p\>{BODY_5}\</p\> | \<p\>{BODY_5}\</p\> | PASS |
| step_5_wait          | 1          | 1          | PASS     |
| step_5_thread_reply  | False      | False      | PASS     |

---

## THE SIX CHECKS THE TASK ASKED FOR

### 1. Does the step the provider holds match the step we believe we wrote?

**Subject, body template and wait: YES for all five steps.** The merge-field
templates `{SUBJECT_N}` and `<p>{BODY_N}</p>` and the wait_in_days values
(3, 4, 4, 9, 1) all match.

**thread_reply: NO for steps 2 and 4.** The provider has `false` on all five
steps. The expected pattern is `(F, T, F, T, F)` from
`THREAD_REPLY_PATTERNS['email_five']`.

### 2. Do `variant`, `variant_from_step` and `thread_reply` come back?

**All three fields are present in the provider response.** The bison trimmer
in `sequence_steps()` reads them off the raw response. What came back:

    step   variant   variant_from_step   thread_reply
    1      false     null                false
    2      false     null                false  (expected: true)
    3      false     null                false
    4      false     null                false  (expected: true)
    5      false     null                false

`variant` and `variant_from_step` are populated by the provider (not discarded
by the trimmer) but both are empty/null - no A/B variant is configured on any
step. TASK-073's trimmer fix is confirmed working: the fields survive the
round-trip.

### 3. Does the thread_reply pattern match `THREAD_REPLY_PATTERNS['email_five']`?

**NO.** The expected pattern is `(False, True, False, True, False)`. The
provider holds `(False, False, False, False, False)`. Steps 2 and 4 should be
same-thread follow-ups and are instead new threads.

The chain is: ladder (`email_five`) -> `THREAD_REPLY_PATTERNS` ->
`bisonfactory._resolve_thread_pattern` -> `bisonfactory._sequence_steps` ->
`set_sequence` POST body -> provider storage. The expected value is computed
correctly (the readback confirms the local state), but the provider did not
store it. The write path either did not send `thread_reply: true` or the
provider discarded it.

### 4. Does the greeting render?

**There is no greeting.** None of the 14 populated leads carry a greeting in
any of the five body_N variables. The bodies start directly with the opening
sentence (e.g., "I noticed that Semcasting focuses on...").

No broken merge was found: no "Hey ,", "Hi undefined,", "Hi null," or bare
comma. This is because the body travels entirely as `{BODY_N}` - there is no
`first_name` or `company` merge variable at EmailBison, so there is nothing
to break. The greeting is absent by construction, not by defect.

The 9 unpopulated leads have no body_N variables at all (0 custom variables
or only `headline`/`location`). If the campaign were started, these leads
would receive emails with empty bodies.

### 5. Is there a signature?

**No.** None of the five steps carry a signature block on any of the 14
populated leads. The bodies end with a question (steps 1-4) or a closing
phrase (step 5: "Thank you for your time.") but no sender name, title or
sign-off line.

Sender identity was in ZERO of 165 email steps before the ladder fix. The
ladder's `purpose_with_thread` does not inject a signature. The body_N
approach carries the whole body as a single variable, so a signature would
have to be part of the generated copy - and it is not.

### 6. Are any two of the five steps the SAME message?

**No duplicate bodies.** All 14 populated leads have distinct body text on
every step.

**Duplicate subjects exist on three leads:**

    lead                                       steps  subject
    ray-kingman                                2 = 4  "Exploring Profitability Insights for Semcasting"
    jason-baker-advertising-marketing-leader   1 = 2 = 4  "Exploring Profitability for Roaring Media Agency"
    caleb-crail                                1 = 3  "Unlock Your Marketing Potential with C Squared Social"

Duplicate subjects are not duplicate messages (the bodies differ) but they
are a send-safety concern: a recipient seeing the same subject line three
times across five emails may read the sequence as automated rather than
personal.

---

## VERDICT SUMMARY

| Check                          | 481    | 451    |
|--------------------------------|--------|--------|
| Steps match (subject/body/wait)| PASS   | FAIL (shape mismatch) |
| variant/variant_from_step present | PASS (both empty) | n/a |
| thread_reply pattern           | **FAIL** | n/a  |
| Greeting renders               | PASS (no greeting exists) | n/a |
| Signature present              | FAIL (none) | n/a |
| Duplicate messages             | PASS (bodies unique) | n/a |
| Duplicate subjects             | FAIL (3 leads) | n/a |

**Overall exit code for 481: 1 (FAIL).**

The load-bearing failure is thread_reply. Steps 2 and 4 are meant to be
same-thread follow-ups and the provider has them as new threads. If campaign
481 is resumed, recipients will get five separate threads instead of three
threads with follow-ups nested - which is the exact defect the readback was
built to catch.
