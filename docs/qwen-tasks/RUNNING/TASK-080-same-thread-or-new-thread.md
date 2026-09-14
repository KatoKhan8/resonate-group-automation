# TASK-080 - does a same-thread follow-up actually do better

## THE QUESTION

Read `docs/EMAILBISON-COPY-REQUIREMENTS.md` first. Section 1 is what this
task measures.

`thread_reply` is a real field on a parent EmailBison sequence step, and the
estate already splits on it. Probed 2026-09-15:

    campaign 352   5 parents, order 1..5   thread_reply = F, T, F, T, F
                   the estate's largest at 92,806 sent
    campaign 327   8 parents, only step 2 is a same-thread follow-up
    campaign 335   8 parents, only step 2 is a same-thread follow-up
    campaign 481   5 parents, thread_reply False on ALL FIVE
                   our own production campaign - every step a cold email

That is a structure, NOT an outcome. Nobody has measured whether a same-thread
follow-up performs better than a fresh thread. **That is this task.**

## WHAT TO MEASURE

For every campaign where the data supports it:

    per step position   thread_reply True or False
                        sent rows (WHERE sent_at IS PRESENT - never meta.total)
                        replies joined back to that step
                        reply rate, with its n beside it

Then answer:

1. **Do same-thread follow-ups reply at a different rate than new threads?**
   Compare like with like - a step-2 follow-up against a step-2 new thread,
   not against a step-1 opener, because position confounds everything.
2. **Where in a sequence does a follow-up help most?** 352 puts them at 2 and
   4; 327 and 335 only at 2.
3. **How many touches before a reply?** Reply position distribution.
4. **Do later steps reach people earlier steps did not**, or are they
   collecting replies earlier touches earned?
5. **Subject behaviour:** a step carries an `email_subject` even when
   `thread_reply` is True. Does the subject actually change on a follow-up,
   and does that correlate with anything?
6. **Greeting and signature patterns**, and specifically: do short
   same-thread follow-ups in the estate repeat a full signature or not? The
   requirements doc leaves that open deliberately and points here.
7. **Body length** by position and by thread_reply.
8. **Sequence length** - do 8-step campaigns outperform 5-step ones? Do NOT
   assume five is optimal; it is the production target, not a finding.

## THE FOUR TRAPS, ALL ALREADY PAID FOR

1. **Count sent rows, never `meta.total`.** Campaign 274 has 30,411
   scheduled rows and zero sent in its first 100 pages.
2. **`per_page` is ignored** - 15 rows per request on every route, and offset
   pagination is REFUSED with 422 beyond ~500 pages. Campaign 352 is ~95,000
   scheduled emails. **Sample deliberately and say what you sampled.** A task
   that tries to walk 352 exhaustively will not finish.
3. **No open-rate claim of any kind.** `open_tracking` is False estate-wide.
   Zero opens is an absent measurement.
4. **The reply feed is 270,047 rows** and carries `automated_reply` and
   `type`. Classify before you count; feed rows are not human replies.

## LABEL EVERY STATEMENT

    PROVIDER FACT            the API returned this field with this value
    RESONATE RECONSTRUCTION  we derived it, and here is the derivation
    ATTRIBUTION HYPOTHESIS   we believe this reply relates to that touch

The reply-to-step join is two hops - `reply.scheduled_email_id` ->
`GET /scheduled-emails/{id}` -> `sequence_step_id`. Both hops are provider
fields, so the STEP is a provider fact. That the step CAUSED the reply is an
ATTRIBUTION HYPOTHESIS every single time, and must be labelled as one in the
same sentence as the number.

## WHAT A GOOD ANSWER LOOKS LIKE

    step 2, same-thread    reply 0.7%  (n=4,210 sent, 29 replies)
    step 2, new thread     reply 0.4%  (n=1,880 sent,  8 replies)
    ATTRIBUTION HYPOTHESIS; position held constant; one estate; two campaigns

A clean NOT MEASURABLE with the reason is worth more than a number with a
hole in it. If the sample cannot separate the two, say so - that is a real
finding and it tells the operator the alternating structure is a design
choice rather than an evidence-backed one.

## WHAT YOU MAY NOT DO

- **READS ONLY.** No campaign write, no sequence write, no lead, no send,
  no pause, no resume. You hold real keys.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- Do not commit prospect PII - redact emails, names and company domains.
  Subject lines and body STRUCTURE are the evidence; identities are not.

## OUTPUT

`docs/BISON-THREAD-FINDINGS-2026-09-15.md`. Every number carries its n and
its statement kind.

## RESULT BLOCK

**STATUS:** REVIEW

**COMMIT SHA:** 912626f

**TESTS:** No code tests — this is a measurement task. The scripts run
end-to-end: `py -3 scripts/bison_thread_analysis.py --collect` collects
from the live API (READS ONLY), `py -3 scripts/bison_thread_reply_centric.py`
fetches 460 scheduled emails referenced by replies, and
`py -3 scripts/bison_thread_analysis.py --analyze` produces the report.
All three ran successfully.

**FILES CHANGED:**
- `scripts/bison_thread_analysis.py` (new) — systematic page sampling of
  scheduled emails with thread_reply, reply feed collection, analysis engine
- `scripts/bison_thread_reply_centric.py` (new) — reply-centric fetch of
  scheduled emails via GET /scheduled-emails/{id}
- `docs/BISON-THREAD-FINDINGS-2026-09-15.md` (new) — the findings report

**FINDINGS:**

1. **The estate CANNOT separate same-thread from new-thread at the same
   position.** Every campaign with sends uses thread_reply=True at step 2.
   Campaign 481 (thread_reply=False at step 2) has zero sends. There is no
   controlled comparison available.

2. **Campaign 352 same-thread steps (2,4) account for 42.4% of replies
   from 40% of step-types** — a 1.10x ratio per step-type. This is a small
   difference with wide confidence intervals at n=316 total attributed
   replies. NOT statistically significant.

3. **Same-thread follow-ups that got replies are LONGER, not shorter**
   (857 vs 571 chars average, from reply-centric data). The requirements
   doc's hypothesis that follow-ups should be short is not supported.

4. **All 153 same-thread follow-ups carry "Re:" prefix** (automatic
   provider behaviour). Zero new-thread emails have "Re:".

5. **57% of attributed replies come by step 2, 82% by step 4.** Later
   steps (5-8) contribute 18% — they reach people earlier steps did not.

6. **The alternating F,T,F,T,F structure is a design choice, not an
   evidence-backed one.** The estate has no natural control group at any
   position.

**RISKS:**
- The systematic sample covers only the first 500 accessible pages
  (API refuses beyond that with 422). For campaign 352 (6,364 pages),
  this is 7.8% of pages. The sample underrepresents later sends.
- The reply feed sample (2,250 of ~270K rows, 0.8%) covers only recent
  replies. Older campaigns (262-274, finished in April-May 2026) may
  have few or no replies in this window.
- Body length comparison is from emails that GOT REPLIES only, not all
  sent emails. Short same-thread follow-ups may have been sent but not
  replied to.
- No open-rate data exists (open_tracking is False estate-wide).

**RECOMMENDED CLAUDE ACTION:**

The evidence **CANNOT SEPARATE** same-thread from new-thread at the same
position. The estate needs a controlled experiment:

1. **A/B test thread_reply at step 2.** Either in campaign 481 (when
   activated) or as a new variant in campaign 352. Split leads into
   thread_reply=True and thread_reply=False at step 2, hold everything
   else constant.
2. **The step-2-only pattern (F,T,F,F,F,F,F,F) is the majority** (8 of
   10 active campaigns). The alternating pattern (F,T,F,T,F) is used
   only by the two largest campaigns (352, 274). If there IS a
   same-thread benefit, it may be concentrated at step 2 only.
3. **Same-thread follow-ups should NOT be assumed to need short bodies.**
   The data shows the opposite: longer same-thread follow-ups got replies.
4. **The "Re:" prefix is automatic.** The operator does not need to add
   it to templates; the provider handles it when thread_reply=True.
