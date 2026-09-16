PRIORITY: P0
DEPENDS:

# TASK-193 - the provider said Ukraine and the criterion still said UNKNOWN

## WHERE THIS SITS

TASK-185 bought company-info for 50 records and moved zero verdicts. One line
of its result explains why, and it is not the line anybody expected:

    geography: 0 resolved. Offices returned are in countries not on the
    client's include list (UA, CY, RU, etc.)

Read that again. The provider **did** return office locations. Real structured
data, for records whose geography criterion was UNKNOWN. And the criterion
stayed UNKNOWN.

If a record's offices are in countries outside the client's include list, the
honest geography verdict is **FAIL**, not UNKNOWN. And a FAIL is not a
disappointment here - it is the cheapest possible outcome. `icp_fail` is
terminal, it consumes zero person credits, and it takes the record out of a
review queue that a human would otherwise have to look at.

So the possibility is that we are holding records in `review` that the data we
already have says should be cleanly rejected. That is throughput in the
direction nobody was looking.

## THE QUESTION

1. **Confirm or refute it.** Take the 25 Round 2 records from TASK-185. For
   each, what did company-info return for offices, what did the geography
   criterion do with it, and why. Quote the code path in `icpstructural.py`
   that turns an office list into PASS, FAIL or UNKNOWN.
2. **Is it a defect or a design?** There are honest reasons a criterion refuses
   to FAIL on this data: an office list may be incomplete, a company
   headquartered outside the include list may still deliver inside it, and a
   single office in Cyprus may be a holding company. If one of those is the
   reason, find it in the code or the comments and say so - then this is not a
   defect and the finding is that geography cannot be resolved by office data
   at all, which is just as valuable.
3. **If it IS a defect**, establish exactly what was discarded: was the office
   data never written to `company_facts`, written under a key the criterion
   does not read, written in a shape it could not parse, or read and
   deliberately ignored? These are four different bugs.
4. **Count what it is worth.** If office data were allowed to produce a FAIL,
   how many of the 66 review records would be cleanly rejected, and how many of
   the 550? That number is the value of fixing it.
5. **Do not fix it in this task.** Report it with the count. A change that
   lets a criterion produce FAIL from inferred or partial data can reject a
   good company permanently, and `icp_fail` is terminal. That is Claude's call
   and possibly the operator's.

## THE TRAP

This task can destroy accounts if it goes one step further than asked. A FAIL
is terminal. Getting this wrong in the permissive direction rejects real
prospects forever on the strength of one office record from one provider.
**So: measure, count, report. Change nothing.**

Second trap: TASK-190 is separately wiring free evidence and is under a hard
rule that an inference may move a criterion from UNKNOWN to PASS and never to
FAIL. That rule and this task's question are in tension on purpose. If your
answer is that office data should produce FAIL, say explicitly how that differs
from a TLD inference producing FAIL, because the operator will ask.

## WHAT YOU MAY NOT DO

- No paid provider calls. TASK-185's results are already recorded - read them.
  Do not re-buy the data.
- No provider writes.
- Do not change `icp.py`, `icpstructural.py`, a criterion or a threshold.
- Do not move any record to `icp_fail`, `dropped`, or any other state.
- Never commit PII. Hash record ids and domains, and note that country names
  are not PII but a domain plus its country is close to it.

## FILES ALLOWED

    docs/GEOGRAPHY-DISCARDED-2026-09-16.md   (new)
    scripts/task193_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The per-record office data and what geography did with it, the code path
quoted, a defect-or-design verdict with the reason, which of the four discard
shapes it is if a defect, and the count of records that would be cleanly
rejected if office data could produce a FAIL.
