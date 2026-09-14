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
