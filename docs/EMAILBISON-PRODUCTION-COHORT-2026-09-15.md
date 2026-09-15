# EmailBison Production Cohort Design — 2026-09-15

TASK-145. What an EmailBison production cohort would have to look like, with
the provider evidence under each claim. Not a campaign — Claude creates
campaigns — a design somebody can build from without re-deriving it.

`EMAILBISON-COPY-REQUIREMENTS.md` is the standing contract and outranks
anything concluded here. It fixes: one conversation per sequence,
same-thread follow-ups via `thread_reply` not a new subject, no hardcoded
names, no greeting that may render empty. This document builds on those.

---

## 1. Who is the cohort?

**Snapshot stamp: `2026-09-14T21:52:15Z` from master `0ac5e60`, 300 records.**

### The four-way partition

| Cohort | Count | Definition |
|--------|-------|-----------|
| **Cold email** | **26** | Verified email AND no `bison_lead_id` |
| **Prior outreach, no reply** | **29** | Has `bison_lead_id`, no reply evidence in the log |
| **Unverified, neither** | **245** | No verified email, no `bison_lead_id` |
| **Total** | **300** | Partition sums exactly |

**All 29 records with `bison_lead_id` also have verified email** (overlap = 29).
The cold email cohort is therefore 55 verified − 29 with prior outreach = 26.

**No record in the snapshot carries reply evidence.** The log has no
`reply` step for any of the 29 `bison_lead_id` contacts. They are all
"no reply" by construction of the snapshot schema — there is no
reply-tracking field anywhere in the record.

### What each cohort means for a campaign

**Cold email cohort (n=26):** These contacts have a verified address and
have never been reached by EmailBison. They are the cold-first email
cohort — the equivalent of the LinkedIn canary's three contacts. Every
email step (em1–em5) is a first touch. The copy runs the full ladder:
relevance, angle, product, follow-up, easy out.

**Prior outreach, no reply (n=29):** These contacts were added to a
previous EmailBison campaign (campaign 481, which was paused at 23 leads
with 0 sends, or campaign 451, which completed with 1 send). They have a
`bison_lead_id` but no reply. The question for this cohort is whether the
previous campaign actually sent to them:

- Campaign 481 has `emails_sent = 0` and is PAUSED. If these 29 contacts
  were on 481, they were never emailed — the `bison_lead_id` was assigned
  at lead-creation time but no email went out. They are effectively cold.
- Campaign 451 has `emails_sent = 1` and is COMPLETED. One contact
  received one email. The other 28 were on 481.

**The honest read:** campaign 481 was paused before sending. Its 23 leads
(and possibly some from 451) carry `bison_lead_id` but were never
emailed. Until the provider's sent-email feed is checked per-lead, the
safe assumption is that these 29 contacts have a provider-side lead
record but may not have received any email. The copy should treat them as
cold until proven otherwise — a follow-up that says "following up on my
last email" to someone who never received one is a defect.

**Unverified (n=245):** Not eligible for either cohort. The standing rule
is that no email is generated for an unverified address. These records
have no contact with `verification.state == "verified"`, or no contact at
all (223 of 300 records have zero contacts in the snapshot).

### The cohort that matters

**26 cold-email contacts and possibly up to 29 more if campaign 481's
leads are confirmed unsent.** The total addressable email cohort is 26
(definite) to 55 (if all `bison_lead_id` contacts are confirmed never to
have been emailed). The upper bound requires a provider-side check of
campaign 481's scheduled-email feed — reads only, no writes.

---

## 2. What does the provider actually support for threading?

### The mechanism

**PROVIDER FACT.** `thread_reply` is a boolean field on a sequence step.
It is read from `GET /campaigns/{id}/sequence-steps` and written (at
sequence creation) via `POST /campaigns/{id}/sequence-steps`. The field
is on the step definition AND on each scheduled email row.

Source: `src/providers/bison.py`, `sequence_steps()` at line 1338, which
returns `thread_reply` among its trimmed fields. Confirmed by
`docs/BISON-PROVIDER-TRUTH-2026-09-14.md` section A (scheduled email row
has `thread_reply`, 61/61 populated).

### How a step is marked as a thread reply

The step carries `thread_reply: true` or `thread_reply: false`. The
pattern across a sequence is a tuple of booleans, one per step in
cadence order.

**In the codebase:** `cadencelibrary.THREAD_REPLY_PATTERNS` holds the
named patterns:

```python
THREAD_REPLY_PATTERNS = {
    "email_five": (False, True, False, True, False),
    "email_eight": (False, True, False, True, False, True, False, True),
}
```

A client config's `email_sequence.thread_reply_pattern` overrides the
ladder default. The override is a list of booleans, one per email step in
cadence order. Resolved in `bisonfactory._resolve_thread_pattern()` at
line 292.

The function `cadencelibrary.thread_reply_for(ladder_name, ordinal)`
returns the boolean for a given step position, or `None` when the ladder
has no declared pattern or the ordinal is past its end.

### What the subject field does on a thread reply

**PROVIDER FACT.** A step carries `email_subject` EVEN WHEN
`thread_reply` is True. Thread behaviour is governed by the flag, NOT by
omitting the subject. This is stated in three places:
`EMAILBISON-COPY-REQUIREMENTS.md` section 1, `cadencelibrary.py` line
251-252, and `bisonfactory.py` line 283.

**PROVIDER FACT.** The provider automatically prepends "Re:" to the
subject when `thread_reply=True`. Measured on 153 same-thread follow-ups:
all 153 carry "Re:", zero new-thread emails do. This is provider
behaviour, not a template choice. The generator must NOT write "Re:"
itself.

Source: `docs/BISON-THREAD-FINDINGS-2026-09-15.md`, section "Subject
Behaviour on Follow-Ups."

### Whether the provider exposes the variant structure on a step

**PROVIDER FACT.** EmailBison models variants as first-class sequence
steps. Each variant has:

| Field | Type | Meaning |
|-------|------|---------|
| `id` | int | The variant step's own unique identifier |
| `order` | null | Variants have no order — they are not sequence positions |
| `variant` | bool | True for variants, False for parent steps |
| `variant_from_step` | int | Points at the parent step's `id` |
| `email_subject` | str | The variant's own subject template |
| `email_body` | str | The variant's own body template |
| `thread_reply` | bool | The variant inherits or sets its own threading |
| `active` | bool | Whether the variant is enabled |

Source: `docs/BISON-PROVIDER-TRUTH-2026-09-14.md` section D, confirmed by
`src/configdiff.py` line 512 and `src/providers/bison.py` line 1380.

**The attribution chain is provider-supported:**

    reply -> scheduled_email_id -> scheduled_email.sequence_step_id
          -> variant step id -> variant template copy

70% of campaign 352's scheduled emails reference a variant step ID
directly (42 of 60 rows checked). The variant's `id` is the persistent
identifier for attribution.

**In the codebase:** `bisonfactory.py` resolves variants per contact at
line 615-686. `cadence.variant_for()` assigns one variant per contact
deterministically. Each variant is approved independently — five variants
means five approvals.

### What this means for the cohort design

1. **Threading is a flag, not a subject trick.** The step always carries a
   subject. The `thread_reply` boolean is the mechanism.
2. **Variants are first-class provider objects.** Each variant at a step
   position has its own `id`, its own copy, and its own attribution chain.
   Five variants per step is natively supported.
3. **The (F, T, F, T, F) pattern is configurable.** The ladder default can
   be overridden per client or per campaign. This is how an A/B test on
   thread_reply would work: two variants at step 2, one with
   `thread_reply=True`, one with `False`.

---

## 3. What does the cadence look like, and on what evidence?

### What the existing documents already settle

Two documents exist: `docs/BISON-CADENCE-FINDINGS-2026-09-14.md` (TASK-070)
and `docs/EMAILBISON-CADENCE-DESIGN-2026-09-15.md` (TASK-134). Plus
`docs/BISON-THREAD-FINDINGS-2026-09-15.md` (TASK-080). Here is what they
settle:

| Design choice | Settled? | Basis | What the evidence says |
|---------------|----------|-------|----------------------|
| **Five steps, not eight** | PARTIAL | TASK-103 measured campaign 330: steps 6-8 are strictly wasteful (0 replies from 95 sends). But n=1 at step 5 is too small to decide, and the 5-step vs 8-step comparison is confounded with campaign identity. | The honest answer: five is the current target, not a finding. |
| **3-day gaps between steps** | PARTIAL | Modal EmailBison gap (35.2% of 122 step instances). 92.3% of observed replies arrive before day 3 (n=65 pairs). | The 3-day gap is what was CONFIGURED, not what WORKED. It is consistent with the time-to-reply distribution but does not prove optimality. |
| **(F, T, F, T, F) thread pattern** | NOT SETTLED | No control group exists. Every campaign with sends uses `thread_reply=True` at step 2. Campaign 481 uses False at every step but has 0 sends. | The alternating pattern is a BET, labelled as such in TASK-134. |
| **No length instruction for follow-ups** | SETTLED | TASK-080: same-thread follow-ups that got replies average 857 chars vs 571 for new threads. Survivorship, supports neither direction. | "Be short" is removed. "Add one thought" carries the intent without asserting a length. |
| **The follow-up addendum** | SETTLED | Without it, the model writes another cold open and only the flag changes. | The addendum is appended when `thread_reply=True`. |
| **The pre-write guard** | SETTLED | Catches three greeting defect classes (empty, placeholder, planted name). | Fires before staging. |
| **The easy out at rung 5** | SETTLED | The fallback's `connected_4` is the best copy in the system for this. | The ladder asks for it; the prompt must produce it. |

### What is NOT settled

Every design choice that rests on a comparison between same-thread and
new-thread at the same position is NOT settled, because no such
comparison exists in the estate:

| Open question | What would settle it |
|---------------|---------------------|
| Does same-thread at step 2 outperform new-thread at step 2? | A campaign that runs both, holding everything else constant. |
| Does the alternating (F,T,F,T,F) pattern outperform step-2-only (F,T,F,F,F)? | Same: a controlled comparison. |
| Does a 3-day gap outperform a 5-day or 7-day gap? | No local evidence exists. General practice suggests 3-5 days; the estate configured 3. |
| Does a 5-step cadence outperform a 3-step? | No local evidence. TASK-103 shows steps 6-8 are wasteful but says nothing about 3 vs 5. |
| What is the estate's actual reply rate? | One send (campaign 451) is not a sample. The historical estate (238K sends) has reply data but is confounded with different audiences, copy, languages, and senders. |

### The honest statement

**With one send in the estate's history, the answer for most cadence
questions is "no local evidence exists yet."** The cadence design in
TASK-134 is a well-reasoned starting hypothesis with every bet labelled.
It is not a measurement. The first campaign's job is to produce the first
measurement.

---

## 4. What is the smallest first email campaign that would teach us something?

### The LinkedIn parallel

The LinkedIn side shipped a canary of three contacts. The email
equivalent is the smallest cohort whose result would change a decision.

### The cohort

**26 cold-email contacts** from the snapshot (verified email, no
`bison_lead_id`). These are the contacts for whom no EmailBison lead has
been created and no email has been sent.

Whether the 29 `bison_lead_id` contacts can be added depends on a
provider-side read of campaign 481's scheduled-email feed. If no email
was sent to them (likely, since `emails_sent = 0`), they are effectively
cold and the cohort is 55. If any were sent to, they are a different
cohort with different words (a follow-up, not a cold open).

**The design below is for the 26 cold contacts.** Expanding to 55 is
mechanically straightforward once the provider read confirms the 29 are
unsent.

### The cadence

Five steps on the `email_five` ladder. The THREAD pattern is (F, T, F, T, F)
— the current hypothesis, not a finding.

| Step | Day | Rung | thread_reply | Job |
|------|-----|------|-------------|-----|
| em1 | 1 | 1 | False (new thread) | Relevance, who is writing, one question |
| em2 | 4 | 2 | True (same thread) | A different angle, adds one thought |
| em3 | 7 | 3 | False (new thread) | Say what the product is and what it is worth |
| em4 | 10 | 4 | True (same thread) | A follow-up with a different argument |
| em5 | 14 | 5 | False (new thread) | Close the loop, easy no |

Inter-step delays: 3, 3, 3, 4 days. Total span: 14 days.

### The arms

**One arm, not two.** The cohort is too small (n=26) for a controlled
A/B test on thread_reply or cadence shape. A split into two arms of 13
would produce numbers too small to distinguish signal from noise at any
reasonable confidence level.

The single arm runs the (F, T, F, T, F) pattern. The question it answers
is not "which pattern is better" but "does email outreach from this
estate produce replies at all, and at what rate?"

### Variants

**One variant per step for the first campaign.** The provider supports
multiple variants per step (campaign 352 has 39 variants across 5
parents), but with 26 contacts and one variant per step, each variant
would be assigned to ~26 contacts. With two variants per step, each
variant reaches ~13 contacts — too few to distinguish.

The variant structure is ready to activate once the cohort grows. The
provider supports it natively; the codebase resolves it in
`bisonfactory._resolve_step_copy()`.

### What outcome would count as a signal

**Stated BEFORE the campaign exists, so the answer cannot be fitted to
the result afterwards.**

| Outcome | Threshold | What it changes |
|---------|-----------|-----------------|
| **Signal: email works** | ≥ 2 replies from 26 contacts (≥ 7.7%) | The email channel is viable. Proceed to a larger cohort and an A/B test on thread_reply. |
| **Signal: email does not work** | 0 replies from 26 contacts after all 5 steps complete | The email channel, as configured, is not producing. Investigate copy, sender reputation, or audience fit before spending more credits. |
| **Inconclusive** | 1 reply from 26 contacts (3.8%) | Too few to call. Expand the cohort to 55+ and re-run. |

**Why 2 of 26?** The historical estate's reply rates (from the reply
sample, TASK-070) range from 0.0% to 0.7% per campaign. But those are
large, multilingual marketing-agency campaigns with different audiences
and copy. The Resonate canary (campaign 451) sent 1 email and got 0
replies. A threshold of ≥ 2 from 26 (7.7%) is well above the estate's
historical range and would represent a qualitatively different outcome —
copy and audience that actually resonate.

**Do not call 1 reply a signal.** n=1 is an observation, not a rate. The
LinkedIn canary had 3 contacts and treated any outcome as informative
because the question was "does the mechanism work," not "what is the
reply rate." For email, the mechanism question is already answered (the
provider works, the code stages, the guard fires). The question for the
first campaign is whether the copy resonates, and that needs a numerator
of at least 2.

### What the campaign teaches, and what it cannot

**Teaches:**
- Whether the email copy, sender, and audience produce replies at a rate
  above the estate's historical baseline.
- Whether the (F, T, F, T, F) threading pattern works operationally
  (emails land in the right thread, "Re:" appears correctly).
- Whether the 14-day cadence span is practical (contacts respond within
  the window, or the breakup at em5 is too late/early).

**Cannot teach:**
- Whether same-thread outperforms new-thread (no control group).
- Whether 5 steps is better than 3 or 4 (no comparison arm).
- What the reply rate IS (26 contacts is too few for a rate estimate —
  the confidence interval on 2/26 is 1.0% to 24.2%).
- Whether the cadence generalises beyond this audience.

### The sequence of decisions after the first campaign

1. **If ≥ 2 replies:** expand to 55 contacts, add a second arm with
   (F, F, F, F, F) to test the threading hypothesis.
2. **If 1 reply:** expand to 55 contacts on the same arm, re-evaluate
   after the larger cohort completes.
3. **If 0 replies:** stop. Investigate copy quality (TASK-131's prompt
   fixes), sender reputation, and audience fit before spending more
   credits. The cadence design is not the problem if nobody replies to
   any of five emails.

---

## Summary

### The cohort

26 cold-email contacts (verified, no prior EmailBison outreach) from the
snapshot at `2026-09-14T21:52:15Z`. Possibly 55 if campaign 481's leads
are confirmed unsent. 245 records are unverified and not eligible.

### The threading mechanics

`thread_reply` is a boolean on the sequence step. The provider auto-
prepends "Re:" to the subject when True. The step always carries a
subject. The pattern is configurable per ladder and per client config.
Variants are first-class steps with their own `id` and
`variant_from_step` pointing at the parent.

### What the cadence documents settle and what they do not

Settled: five steps (not eight), 3-day gaps, no length instruction, the
follow-up addendum, the pre-write guard, the easy out at rung 5.

Not settled: the (F, T, F, T, F) pattern (no control group), same-thread
vs new-thread at any position, 5 vs 3 steps, the estate's actual reply
rate.

### The smallest first campaign

26 contacts, one arm, five steps, (F, T, F, T, F), 14-day span, one
variant per step. Success criterion stated in advance: ≥ 2 replies from
26 contacts (≥ 7.7%). Below that: 1 reply is inconclusive, 0 replies
means stop and investigate.

---

*Sources: queue snapshot (stamp: 2026-09-14T21:52:15Z, from master
0ac5e60, 300 records), `docs/BISON-CADENCE-FINDINGS-2026-09-14.md`
(TASK-070), `docs/EMAILBISON-CADENCE-DESIGN-2026-09-15.md` (TASK-134),
`docs/BISON-THREAD-FINDINGS-2026-09-15.md` (TASK-080),
`docs/BISON-PROVIDER-TRUTH-2026-09-14.md`,
`docs/EMAILBISON-COPY-REQUIREMENTS.md`, `src/cadencelibrary.py`,
`src/bisonfactory.py`, `src/providers/bison.py`. Analysis script:
`scripts/task145_cohort_analysis.py`. No unsanitised prospect PII. No
provider writes were made.*
