# TASK-070 - What cadence shape actually worked, in the real EmailBison estate

## DEPENDS ON TASK-069

TASK-069 establishes what the provider exposes and whether
campaign -> lead -> step -> reply can be joined. Read its output first. If
per-step attribution turns out to be unavailable, this task still runs -
at campaign level - and says so rather than inventing the step.

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
