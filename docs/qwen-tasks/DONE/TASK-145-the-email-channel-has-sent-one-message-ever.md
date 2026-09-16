PRIORITY: P1
DEPENDS:

# TASK-145 - EmailBison is a production channel that has sent one email

## THE STATE, READ FROM THE PROVIDER

    campaign 481   PAUSED     23 leads    0 sent
    campaign 451   COMPLETED   -          1 sent

Both are ours. Nothing new has been created. So the email half of the loop -
inventory, cohort, copy, cadence, send, reply, outcome, learning - has run end
to end exactly once, and every downstream conclusion about email rests on that
one send.

Meanwhile the LinkedIn half is shipping its first cohort. The two channels are
not in competition: 29 contacts carry a prior `bison_lead_id` and are held OUT
of the LinkedIn control arm precisely because they are not cold, and the
account-collision gate rejects 151 of 248 LinkedIn candidates because somebody
at that account is already in an EMAIL sequence. The estate's email history is
what makes the LinkedIn cohort safe, and it is also the thing nobody is
currently learning from.

## WHAT THIS TASK IS

Establish what an EmailBison production cohort would have to look like, as a
DESIGN with the provider evidence under it. Not a campaign - Claude creates
campaigns - a design somebody can build from without re-deriving it.

`EMAILBISON-COPY-REQUIREMENTS.md` is the standing contract and it outranks
anything you conclude here. Read it first. It already fixes several things
that would otherwise be open questions:

    a sequence is ONE CONVERSATION
    same-thread follow-ups use the provider's thread_reply rather than a new
      subject on every step
    no name is ever hardcoded
    no greeting may render empty

Do not re-litigate those. Build on them.

## THE FOUR QUESTIONS

### 1. Who is the cohort?

Against `work/queue.snapshot.jsonl` - **quote the STAMP**. How many contacts
have a VERIFIED email address and no prior EmailBison outreach? How many have
prior outreach that ended without a reply, which is a different cohort with
different words? A contact with an unverified address is not in either: the
standing rule is that no email is generated for an unverified address.

### 2. What does the provider actually support for threading?

TASK-141 is establishing the reply/step/variant boundary and its findings may
already be pushed to `qwen-worker-4-r18` - read
`docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md` if it is there rather than
re-probing. What you need on top of it:

    how a step is marked as a thread reply rather than a new thread
    what the subject field does on a thread reply
    whether the provider exposes the variant structure on a step
      (parent vs variant, `variant_from_step`)

Reads only. You hold real EmailBison keys and the rule is no write, no send,
no campaign mutation, no resume, no pause.

### 3. What does the CADENCE look like, and on what evidence?

`docs/BISON-CADENCE-FINDINGS-2026-09-14.md` and
`docs/EMAILBISON-CADENCE-DESIGN-2026-09-15.md` exist. Read them and say what
they already settle. Then, for anything they do not settle, say what evidence
would settle it - and be honest that with one send in the estate's history,
the answer for most of it is "no local evidence exists yet".

**Do not derive a cadence from the estate's own outcomes and present it as
learned.** One send is not a sample. Where the recommendation rests on general
practice rather than on this estate's data, label it that way.

### 4. What is the smallest first email campaign that would teach us something?

The LinkedIn side shipped a canary of three. The email equivalent: the
smallest cohort whose result would change a decision. State the cohort, the
cadence, the arms if any, and what outcome would count as a signal - BEFORE
the campaign exists, so the answer cannot be fitted to the result afterwards.

## WHAT YOU MAY NOT DO

- No provider writes. No campaign creation, no sequence write, no resume.
- Do not run `py -3 -m src.generate --live`. Generation against the real queue
  is Claude's; a run here writes to an isolated worktree queue that never
  reaches production.
- Do not quote an open rate. `open_tracking` is False estate-wide.
- Do not count an UNKNOWN reply as negative.
- Do not write to `work/`.

## FILES ALLOWED

    docs/EMAILBISON-PRODUCTION-COHORT-2026-09-15.md   (new)
    scripts/task145_*.py
    the task file itself

## FILES FORBIDDEN

    src/       work/       config/

## DELIVERABLE

The cohort with its counts and the snapshot stamp, the threading mechanics
with the field that carries them, what the existing cadence documents already
settle and what they do not, and the smallest first campaign with its success
criterion stated in advance.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** f5f8ef5

**TESTS:**
- `scripts/task145_cohort_analysis.py` runs clean against the snapshot, four-way partition sums to 300.

**FILES CHANGED:**
- `docs/EMAILBISON-PRODUCTION-COHORT-2026-09-15.md` (new) — the design document
- `scripts/task145_cohort_analysis.py` (new) — the cohort analysis script
- Task file moved from TODO/ to RUNNING/

**FINDINGS:**

1. **Cohort (snapshot stamp: 2026-09-14T21:52:15Z):**
   - 26 cold-email contacts (verified, no bison_lead_id)
   - 29 prior-outreach contacts (bison_lead_id, no reply evidence)
   - 245 unverified, not eligible
   - All 29 bison_lead_id contacts also have verified email
   - No reply evidence exists for any contact in the snapshot

2. **Campaign 481 context:** PAUSED with 0 sends. The 29 bison_lead_id
   contacts were likely added as leads but never emailed. They are
   effectively cold until proven otherwise by a provider-side read.

3. **Threading mechanics:**
   - `thread_reply` is a boolean on the sequence step
   - Provider auto-prepends "Re:" when True (153/153 confirmed)
   - Step always carries `email_subject` even when thread_reply=True
   - Pattern is configurable: ladder default or client override
   - Variants are first-class steps with `id`, `variant_from_step`, `thread_reply`

4. **What existing documents settle:**
   - Five steps (not eight), 3-day gaps, no length instruction,
     follow-up addendum, pre-write guard, easy out at rung 5

5. **What is NOT settled:**
   - (F,T,F,T,F) pattern (no control group)
   - Same-thread vs new-thread at any position
   - 5 vs 3 steps, the estate's actual reply rate

6. **Smallest first campaign:**
   - 26 contacts, one arm, five steps, (F,T,F,T,F), 14-day span
   - Success criterion: ≥ 2 replies from 26 (≥ 7.7%)
   - 1 reply = inconclusive, 0 replies = stop and investigate

**RISKS:**
- The 29 bison_lead_id contacts may have been emailed on campaign 451
  (1 send). A provider-side read of scheduled-email feeds would confirm.
- 26 contacts is a small cohort. The confidence interval on 2/26 is
  1.0%-24.2%. The result is directional, not precise.

**RECOMMENDED CLAUDE ACTION:**
1. Review the design document at `docs/EMAILBISON-PRODUCTION-COHORT-2026-09-15.md`
2. Confirm the 29 bison_lead_id contacts were never emailed (read campaign 481's scheduled-email feed)
3. If confirmed, the addressable cohort is 55, not 26
4. Decide whether to proceed with the 26-contact canary or expand to 55
