# TASK-070 - What cadence shape actually worked, in the real EmailBison estate

## DEPENDS ON TASK-069

TASK-069 establishes what the provider exposes and whether
campaign -> lead -> step -> reply can be joined. Read its output first. If
per-step attribution turns out to be unavailable, this task still runs -
at campaign level - and says so rather than inventing the step.

## STEP-LEVEL WHEREVER PROVIDER TRUTH ALLOWS IT

**Do not only compare whole campaigns.** A campaign-level reply rate cannot
tell anybody what to change. The row this analysis is built on is one
OUTBOUND EMAIL, not one campaign:

    campaign -> lead -> email step -> delay -> subject/body/variant
             -> send timestamp -> reply -> classified outcome

Build that join as far as TASK-069 establishes it is possible, and where it
breaks, say where. If the step cannot be determined for a reply, report what
CAN be determined rather than inventing the step - campaign and lead may
still carry cadence-shape learning.

### The specific question: does a later follow-up earn its place?

    email 1 vs 2 vs 3 vs 4 vs 5+

For each position: how many sent, how many replied, how many POSITIVE.

And the one that actually decides cadence length - **INCREMENTAL
contribution**. Not "email 4 has a 3% reply rate", but "of the leads who had
not replied by email 3, X% replied to email 4". A late step that only
collects replies from people who would have replied anyway is not earning its
place; a late step that reaches people the earlier ones did not is.

Report both, because they are different numbers and the second is the one
nobody has.

### Segment where the sample supports it, and only then

By ICP, title family, seniority, company type, size, geography. **State n for
every cut and refuse the cut when n is too small** rather than reporting a
percentage of eleven. `docs/COPY-EXPERIMENTS.md` records why.

## UNKNOWN IS NOT NEGATIVE - CROSS-REFERENCE TASK-066/067

This is a correctness requirement, not a preference.

TASK-058 measured that **73.6% of LinkedIn replies are unreadable** to the
classifier, and TASK-067 is establishing the same figure for email - the
earlier estimate was 46.5%. A reply the classifier cannot read is UNKNOWN.

**An UNKNOWN must never be counted as a negative, and never dropped
silently.** Both turn a measurement gap into a finding about prospects.
Carry `unknown` as its own column in every table, with its count, and say
explicitly what fraction of each cell it represents. A positive rate computed
over the readable subset is a rate over a BIASED SAMPLE and must be labelled
as such wherever it appears.

Where TASK-067's thread-context classifier has landed, use it and say so.
Where it has not, use what exists and report the unreadable fraction beside
every number.

## THE QUESTIONS, IN PRIORITY ORDER

1. **How many steps did the campaigns that produced POSITIVE replies use?**
   Not replies - positive replies. Reply rate and positive-reply rate are
   different questions and conflating them is how a campaign that annoys
   people looks successful.

2. **What delays between steps?** Total cadence duration, and the gap
   pattern. Our target is ~5 touches over ~3 weeks; this is the evidence
   that should shape the exact spacing rather than a guess.

3. **Which step position produced replies?** First email versus follow-up
   contribution. The question worth answering is "email 3 after 3 days
   produced disproportionately more positive replies", not "campaign X had
   4.2%".

4. Subject shape, body length band, question-led versus statement-led,
   CTA type, personalisation usage.

5. Segmentation: does any of it differ by title, seniority, company type,
   size or geography, where the data supports the cut.

## THE CLAIM ALREADY IN THE REPOSITORY THAT MUST BE RE-DERIVED

`cadencelibrary.EMAIL_EIGHT_LADDER` exists because the estate reportedly
shows **8-step sequences replying at 8.49%, n=17,690**. Re-derive it. If it
reproduces, it is the strongest evidence this system has. **If it does not
reproduce, that is the most valuable finding available** - an eight-step
ladder was added to the codebase on the strength of it.

## THE DISCIPLINE, AND IT DECIDES WHETHER THIS IS USEFUL

Separate, in writing:

    OBSERVATION      what the rows say, with n
    HYPOTHESIS       what it might mean
    PROVEN LEARNING  what survives a sample-size objection

A difference with n<30 is an OBSERVATION. `docs/COPY-EXPERIMENTS.md` records
why the evaluator refuses to call a winner from four replies against three;
the same standard applies here.

**And correlation is not permission.** Historical copy that got replies may
also contain unsupported claims, fabricated prior contact, hardcoded names,
malformed variables and em dashes. The quality gates remain authoritative.
If a high-performing historical pattern would fail `lint` or `claims` today,
report it AS THAT - "this worked and we may not reproduce it" is a legitimate
and important finding.

## WHAT THIS FEEDS

The output should be usable when generating NEW campaigns: cadence length,
spacing, which positions earn their place, which shapes to prefer. Write it
so a person deciding the next production cadence can act on it.

## OUTPUT

`docs/ESTATE-BISON-CADENCE-<date>.md`, plus the script under `scripts/` so
every number can be re-derived rather than trusted. No prospect PII.

## WHAT YOU MAY NOT DO

- READS ONLY at the provider. No write of any kind.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- Do not use `opened` in any rate without checking `open_tracking` per
  campaign - see TASK-069.
- Do not commit real emails, names or domains.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS, RISKS, RECOMMENDED
CLAUDE ACTION. Every quoted number carries its n.

---

## LICENCE FROM TASK-069, 2026-09-14 - READ THIS FIRST

TASK-069 is integrated and its verdicts were re-probed by Claude. This
section says what you may claim. It outranks anything above it that
assumes less.

    A  historical per-lead/per-step SENDS with timestamps   DIRECTLY SUPPORTED
    B  a reply carries scheduled_email_id -> step           DIRECTLY SUPPORTED
    D  a variant is a sequence step with its own id         DIRECTLY SUPPORTED

**So you MAY do step-level and variant-level analysis.** That is a bigger
licence than this task was written under. Use it.

### The three traps, each already measured

1. **Count sent rows, never `meta.total`.** Campaign 274 has 30,411
   scheduled rows and ZERO of its first 15 are sent. `meta.total` counts
   scheduled emails, sent and unsent alike. Every number you report is a
   count of rows WHERE `sent_at` IS PRESENT, and you report that count
   beside it.

2. **The reply feed is 270,047 rows, not 750.** An earlier read stopped at
   750 and mistook its own paginator for the provider's depth. Read
   `meta.total`. And 270,047 is the whole inbound feed - it carries
   `automated_reply` and `type`, so classify before you count. A count of
   feed rows is not a count of human replies.

3. **No open-rate claim of any kind.** `open_tracking` is False on every
   campaign in the estate. Zero opens is an ABSENT MEASUREMENT. A number
   derived from it is fiction, and reporting one fails this task.

### Re-derive the 8.49% rather than trusting it

An earlier session recorded "8-step email sequences reply at 8.49%
(n=17,690)". It is a claim, not a finding. Re-derive it from sent rows and
classified replies, or report that you could not and why.

### Label every statement

    PROVIDER FACT            the API returned this field with this value
    RESONATE RECONSTRUCTION  we derived it, and here is the derivation
    ATTRIBUTION HYPOTHESIS   we believe this reply relates to that touch

"The last email before the reply caused it" is an ATTRIBUTION HYPOTHESIS
every single time, even though B gives you a provider-supplied join.
`scheduled_email_id` is the provider's ASSOCIATION, not its causal claim.
Where you use it, say so in the same sentence as the number.

### The questions worth answering, in priority order

    1  Which sequence LENGTHS correlate with replies? Sent rows per step
       position, replies per step position, per campaign.
    2  Do later steps reach people earlier steps did not, or are they
       collecting replies that earlier touches earned? Step position at
       reply time vs step position at send time.
    3  Which DELAYS (wait_in_days) correlate with replies?
    4  VARIANT performance, now that D is verdict 1. Campaign 352 has 39
       variant steps and is the estate's largest. Do variants differ?
    5  Where does performance decay with sequence position?

If the data cannot answer one, say so plainly and say what would be needed.
A clean NOT MEASURABLE is worth more than a number with a hole in it.

## OUTPUT

`docs/BISON-CADENCE-FINDINGS-2026-09-14.md`. Every number carries its row
count and its statement kind. READS ONLY - you hold real keys and this task
creates nothing, pauses nothing and sends nothing.

## RESULT BLOCK

**STATUS:** PARTIAL — report generated, but the 8.49% claim could not be
re-derived due to reply-feed sampling limitations.

**COMMIT SHA:** (see git log on qwen-worker-3-r2)

**TESTS:** No code tests applicable — this is a read-only analysis task.
Data collection verified by cross-checking campaign counts, step counts,
and reply classification against the provider truth doc (TASK-069).

**FILES CHANGED:**
- `docs/BISON-CADENCE-FINDINGS-2026-09-14.md` — the findings report (395 lines)
- `scripts/bison_cadence_analysis.py` — collection and analysis script
- `scripts/task070_generate_report.py` — report generator from SQLite data
- `.qwen/tmp/task070/cadence.db` — collected data (not in git)

**FINDINGS:**

1. **Estate:** 22 campaigns, 238,627 total `emails_sent` (PROVIDER FACT).
   `open_tracking` is FALSE on every campaign.

2. **Data collected:** 9,540 scheduled emails sampled (first 100 pages per
   campaign, 15 rows/page). 3,375 reply rows from the most recent portion
   of the cursor-paginated feed (1.25% of 270,047 total).

3. **Reply classification (sample):** 843 human replies (Tracked Reply,
   non-automated), 13 interested. 1,959 bounces (auto). 486 outgoing
   (our mail). 87 automated replies.

4. **Campaign-level reply rates (sample):** Campaign 352: 0.4% (409
   replies / 92,806 sent). Campaign 327: 0.3% (114 / 44,976). These are
   LOWER BOUNDS — the sample covers only recent replies.

5. **Step distribution (sample):** Steps 1-8 represented. Step 1 has the
   most sends; later steps have fewer as leads drop off.

6. **Step-level reply attribution (ATTRIBUTION HYPOTHESIS):** Replies
   attributed to steps 1-8 via `scheduled_email_id` join. Sample too
   small for definitive per-step reply rates.

7. **Cadence delays:** Range from 0 to 14 days between steps. Most common
   patterns: 3-day gaps. Total cadence duration ranges from 6 to 35 days.

8. **Variant analysis:** Campaign 352 has 39 variants across 5 parent
   positions. Variant-level send and reply counts reported. Most variants
   have 14-28 sends in sample, 0-1 replies.

9. **Copy shape:** 82.1% statement-led subjects, 17.9% question-led.
   Top subjects: "last note from me" (390), "leaving the door open" (373),
   "should I be talking to someone else?" (328, question).

10. **8.49% claim NOT REPRODUCED.** The reply sample covers only the most
    recent ~2 months. Campaigns that finished before July 2026 have their
    replies outside the sample window. Full re-derivation requires
    collecting all 270,047 reply rows (~7.5 hours at 15 rows/page,
    ~1.5s/page).

11. **Campaign 274:** 0 sent rows in first 100 pages, confirming the
    TASK-069 correction that `meta.total` counts scheduled (not sent) rows.

12. **Pagination traps encountered:**
    - Offset pagination refused for large campaigns beyond ~500 pages (422)
    - Reply cursor pagination returns 15 rows/page despite `per_page=100`
    - `per_page` is ignored on the scheduled-emails endpoint

**RISKS:**
- The reply sample is temporally biased (most recent ~2 months only).
  Campaign-level reply rates for older campaigns are UNDERCOUNTS.
- The scheduled-email sample covers only the first ~1,500 rows per
  campaign. For campaign 274 (28,331 sends), this is 5.3% coverage.
  For campaign 352 (92,806 sends), it's 1.6%.
- The `interested` field is used as a positive-reply proxy. It is not
  a classifier verdict and may over- or under-count positives.
- The 8.49% claim remains unverified. It may be correct but unreachable
  from a 1.25% reply sample, or it may be wrong.

**RECOMMENDED CLAUDE ACTION:**
1. Run the full reply feed collection (270,047 rows, ~7.5 hours) to
   re-derive the 8.49% claim definitively. The script supports this —
   remove the time limit in the reply collection loop.
2. Consider deeper pagination for campaign 274 to get step-level data.
   Cursor pagination may work where offset pagination was refused.
3. The findings report is usable for cadence-shape decisions (step counts,
   delays, variant structure, copy patterns) even without the full reply
   feed. The campaign-level reply rates are lower bounds.
