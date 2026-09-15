PRIORITY: P1
DEPENDS:

# TASK-153 - the historical estate, and the two findings that already moved production

## WHY THIS IS NOT A REPEAT OF TASK-139

TASK-139 measured relationship state and found the machinery wired but unfed.
Two things have happened since that change the question:

1. **13 of 29 contacts carrying a `bison_lead_id` were NEVER EMAILED.**
   Campaign 481 was paused before it sent anything; a lead id is assigned at
   lead creation. Proving field: `overall_stats.emails_sent` on
   `GET /leads/{id}`. Those 13 are cold and are currently held out of BOTH
   channels on a false assumption.
2. **A contact was refused at the provider gate for 4 prior LinkedIn messages**
   from the client's own seat, last 2026-07-18, never replied to.
   `collision.check_linkedin_profile` sees that; nothing in cohort selection
   did until it was moved there.

So the estate knows more than the pipeline reads. This task finds the rest.

## WHAT TO MEASURE

Against the snapshot - **quote the STAMP** - plus READ-ONLY provider reads:

1. Re-run the never-emailed check across every contact carrying a
   `bison_lead_id` and confirm the 13/16 split holds at 550 records.
2. For every contact in the eligible pool, how many have LinkedIn conversation
   history on one of the client's 33 seats? This is the check that caught one
   at the gate. Count them BEFORE they reach a gate.
3. Which accounts carry a prior REPLY, positive or negative, and where is that
   recorded? A positive reply is not a reason to exclude somebody - it is a
   reason to treat them as warm - and the two are currently conflated.
4. What is the honest total: of the eligible pool, how many are genuinely cold,
   how many are warm, how many must never be contacted?

## WHAT YOU MAY NOT DO

- READS ONLY at every provider. No write, no send, no campaign mutation.
- Do not write to `work/`. Do not change `eligibility.must_not_contact`.
- Hash prospect identifiers in the document.

## FILES ALLOWED

    docs/HISTORICAL-ESTATE-2026-09-15.md   (new)
    scripts/task153_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The 13/16 split re-confirmed at 550, the LinkedIn-history count across the
eligible pool, the prior-reply inventory with the field that proves each, and
the cold/warm/never split with its evidence.
