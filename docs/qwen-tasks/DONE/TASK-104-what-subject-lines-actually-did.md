PRIORITY: P2
DEPENDS: 

# TASK-104 - subject lines: what the estate actually shows

## WHAT IS KNOWN

    82.1% statement-led, 17.9% question-led   (shape distribution)

That is a distribution of what was SENT, not of what WORKED. Nobody has
related subject shape to outcome with a denominator.

TASK-059's recovered report gives reply counts by subject shape - empty 8792,
statement 551, reply-prefix 286, question 97 - but 8,792 of those are rows
with no subject at all, which are the historical rows with no scheduled email
attached. **Those 8,792 are the same rows that made its other numbers wrong.**
Treat them as unmeasurable, not as "empty subject".

## WHAT TO ESTABLISH

For a deliberately sampled set where the subject IS known and the send IS
confirmed:

1. Reply rate by subject shape - statement, question, reply-prefix (`Re:`).
2. Does a `Re:` prefix correlate with same-thread follow-ups, and can the two
   be told apart? A same-thread follow-up may carry the original subject; if
   so, "reply-prefix" is a proxy for threading rather than an independent
   choice, and treating them as separate shapes double-counts.
3. Subject LENGTH against outcome.
4. Whether any of it survives a sample-size objection.

## WHAT NOT TO DO

- **Do not widen `SUBJECT_VOCABULARY`.** It has been measured and rejected
  twice. A finding that some word correlates with replies is not permission.
- Do not quote an open rate. `open_tracking` is False estate-wide.
- Do not count a row with no subject as a short subject.

## DELIVERABLE

`docs/SUBJECT-ANALYSIS-2026-09-15.md`, with the sample stated, and PROVEN
LEARNINGS empty unless something genuinely survives.

## RULES THAT APPLY TO THIS TASK

- Reads only at both providers. No POST/PATCH/PUT/DELETE, no sends, no
  campaign creation or activation, no adding leads.
- **A zero and a wrong lookup are indistinguishable from the outside.** If you
  measure zero of something, prove you read the right field first. Industry
  and headcount were reported at 0% three separate times by a reader looking
  at `sizing`, which is null everywhere, instead of `company_facts`.
- Say what you SAMPLED. `per_page` is accepted and IGNORED on every EmailBison
  route - you get 15 rows whatever you ask for - and offset pagination is
  refused past ~500 pages. A number without its page budget is not
  reproducible.
- Never use `meta.total` as a sent count. Campaign 274 reports 30,411
  scheduled rows and zero of its first 100 pages are sent. Count rows WHERE
  `sent_at` IS PRESENT.
- **Do not quote 8.49%** - unreproduced. **Do not quote any open rate** -
  `open_tracking` is False estate-wide, which is an ABSENT MEASUREMENT and not
  a zero. **Do not count an UNKNOWN as negative** - 53.4% of unknowns are
  correctly unknown.
- INTERESTED may NOT carry a learning claim: 0.44 precision on the old pattern
  set, and the new set is UNMEASURED, which is not the same as good.
  MEETING_INTENT (1.00) and OBJECTION (1.00) may, with recall stated.
- Never weaken, widen or disable a gate, a lint rule or a sender limit to make
  something pass or to gain volume. Fix what produced the bad output.
- Read every test exit code OFF THE PROCESS, never through a pipe.
- No unhashed PII in any tracked file or commit message - no real names,
  domains, emails, profile URLs or reply text. A seat holder is a real person
  too; Claude leaked one yesterday and the guard caught it.
- Separate OBSERVATIONS (with n), HYPOTHESES, and PROVEN LEARNINGS. Leave
  PROVEN LEARNINGS empty if nothing survives a sample-size objection. TASK-059
  left it empty and was right to.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 42e3434

**TESTS:** Read-only analysis script. No code changes to src/. Script at
`scripts/subject_analysis.py` is reproducible.

**FILES CHANGED:**
- `docs/SUBJECT-ANALYSIS-2026-09-15.md` — the deliverable
- `scripts/subject_analysis.py` — the analysis script (read-only at providers)
- `docs/qwen-tasks/RUNNING/TASK-104-what-subject-lines-actually-did.md` — this file

**FINDINGS:**

1,037 sent rows sampled across 9 campaigns (of ~236k total estate sends).
332 inbound replies collected from the reply feed (80 pages, cursor paginated).
Only 4 of 1,037 sampled sent rows appear in the reply feed — the feed covers
a different slice of the estate.

**Shape distribution (n=1,037 sent rows with a subject):**
- statement: 838 (80.8%)
- question: 142 (13.7%)
- reply_prefix: 57 (5.5%)

**Reply rates by shape (provider counter, 2 total replies in sample):**
- statement: 2/838 = 0.24%
- question: 0/142 = 0.00%
- reply_prefix: 0/57 = 0.00%

**Re: and threading:** 57/57 (100%) of reply_prefix subjects have
`thread_reply=True`. PROVIDER FACT. Re: is a threading mechanism, not an
independent subject choice.

**Subject length:** mean 29.8 chars, median 26. The 2 emails that got
replies (provider counter) were 24.5 chars average — no meaningful difference
from the 1,035 that did not (n=2, not a finding).

**Merge-field rendering:** 37/1,037 subjects show broken merge fields
(leading spaces, orphaned possessives from empty {COMPANY} renders).

**Generated vs sent:** The queue snapshot (300 records) generated 58%
statement / 42% question. The sent population is 81% statement / 14%
question / 5% reply_prefix — the sent estate is dominated by older
campaigns (274, 327-335) whose templates were statement-heavy.

**PROVEN LEARNINGS: Empty.** 2 replies across 1,037 rows cannot distinguish
shape effects from noise. The Re:/threading observation is structural
(100% agreement) but based on n=57 and stated as an observation, not a
learning.

**RISKS:**
- Sample is 0.4% of estate sends. Reply counts are too sparse for
  shape-level comparison.
- Campaigns 328 and 274 required deep-page sampling (pages 100-500) because
  their first pages are all unsent scheduled rows. This introduces a
  positional bias — later pages may have different subject distributions
  than earlier ones.
- The reply feed (332 replies, 80 pages) covers a different time slice than
  the scheduled email sample. Cross-reference match rate is 4/1037.

**RECOMMENDED CLAUDE ACTION:**
- Accept `docs/SUBJECT-ANALYSIS-2026-09-15.md` as the deliverable.
- The PROVEN LEARNINGS section is correctly empty. Nothing here changes
  copy generation or subject line strategy.
- The Re:/threading observation is worth noting for cadence design: a
  `Re:` prefix is not a subject choice but a threading setting on the
  sequence step.
