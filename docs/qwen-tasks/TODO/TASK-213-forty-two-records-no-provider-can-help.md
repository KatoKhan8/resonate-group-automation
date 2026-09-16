PRIORITY: P1
DEPENDS:

# TASK-213 - forty-two records no provider can help, sitting where?

## WHERE THIS SITS

TASK-211 grouped the unresolved queued records by the REASON they are
unresolved, which is the grouping that decides what to buy. Two groups need
nothing bought, ever:

    32   too_small       FAIL-CLOSED. No provider can fix a headcount that is
                         genuinely below the threshold.
    10   geo_excluded    FAIL-CLOSED. A client constraint, not missing data.
    33   missing_all_three (industry/offices/employees) - these DO need
                         evidence: free crawl first, then ContactOut.

Forty-two records are therefore finished. The question nobody has asked is
where they are SITTING. If they are in `review`, they are in a queue that
implies a human should look at them, and no human ever needs to: the answer is
already known and no purchase changes it.

That matters twice over. It inflates the review count that every throughput
measurement today has been reasoning about - 314 of 316 in review - and it puts
42 records in front of a person who will read them and conclude nothing.

## THE QUESTION

1. **Where are the 42 now?** Per record, hashed: `state`, `icp_status`, and
   which criterion produced the fail-closed verdict. Read live state and name
   the file and its record count.
2. **Is the verdict actually recorded, or only derivable?** A record whose
   headcount is known to be below threshold should carry a FAIL on the
   employees criterion and therefore `icp_fail`. If instead it carries UNKNOWN
   and TASK-211 inferred "too_small" from the raw field, then the pipeline does
   not know what the analysis knows, and that is the finding.
3. **For `geo_excluded`: check this against TASK-193 before concluding
   anything.** TASK-193 established a DELIBERATE design choice - a country that
   resolves but is off the include list returns UNKNOWN rather than FAIL,
   because a company headquartered outside the target geography may still
   deliver inside it. So `geo_excluded` may be exactly the population that is
   correctly held as UNKNOWN rather than failed. If so, these 10 are NOT
   fail-closed and TASK-211's grouping was wrong. Say which.
4. **Then say what should happen**, for each group, without doing it:
     - already terminal and correctly so -> nothing, and report the count
     - terminal in substance but sitting in review -> what transition, and
       what evidence justifies it
     - not terminal at all -> which group they actually belong to
5. **Report the corrected review count.** If 42 records are misfiled, then the
   number that every throughput conclusion today rests on is wrong by 42, and
   the corrected figure is the most useful line in your deliverable.

## THE TRAP

**Do not move a single record.** `icp_fail` and `dropped` are both terminal,
and a record moved there on an inferred verdict is a prospect rejected forever
on an analysis rather than on a measured criterion. TASK-193 was given the same
prohibition for the same reason and kept it.

Second trap, and it is why item 3 exists: "the country is not on the include
list" and "this company cannot be a customer" are different statements. The
first is a fact about a list. Treating it as the second is how a fail-closed
group gets manufactured out of a deliberate UNKNOWN.

## WHAT YOU MAY NOT DO

- No paid provider calls, no provider writes.
- Do not move any record between states. Do not set `icp_status`.
- Do not change a criterion, a threshold, the include list, or the
  UNKNOWN-versus-FAIL rule.
- Read live state, name the file, quote its record count. The snapshot is
  stale and has already produced one wrong number today.
- Never commit PII. Hash record ids and domains; report countries in
  aggregate.

## FILES ALLOWED

    docs/FAIL-CLOSED-GROUPS-2026-09-16.md   (new)
    scripts/task213_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The 42 located with state, icp_status and the criterion behind each; whether
the verdict is recorded or merely derivable; the TASK-193 check on
`geo_excluded` with a verdict on whether those 10 are fail-closed at all; what
should happen per group; and the corrected review count.
