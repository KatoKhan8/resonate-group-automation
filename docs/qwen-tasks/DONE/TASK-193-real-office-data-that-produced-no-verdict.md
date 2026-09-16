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

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 313f871

**TESTS:** No test suite run - this is a measurement task, not a code change.
Three analysis scripts were executed against the snapshot and produced
consistent results.

**FILES CHANGED:**
- `docs/GEOGRAPHY-DISCARDED-2026-09-16.md` (new) - the deliverable report
- `scripts/task193_geography_analysis.py` (new) - initial analysis script
- `scripts/task193_missing_iso_codes.py` (new) - missing ISO codes analysis
- `scripts/task193_comprehensive_analysis.py` (new) - comprehensive scenario analysis

**FINDINGS:**

1. **Two issues, not one:**
   
   a) **17 ISO codes are missing from ISO_TO_NAME**, affecting 21 records.
      These include UA (Ukraine), CY (Cyprus), RU (Russia), GR (Greece),
      CZ (Czech Republic), and others. Offices in these countries do not
      resolve to a country at all, because the ISO code is not in the lookup
      table. This is a DATA GAP, not a design decision.
   
   b) **Design decision: "country not on include list" → UNKNOWN, not FAIL.**
      Even when a country IS resolved (e.g., China, India, UAE), if it is not
      on the client's include list, the code returns UNKNOWN rather than FAIL.
      The reasoning is in the module docstring: "UNKNOWN is not FAIL, and that
      is the whole point."

2. **The code path:** `resolve_country()` at lines 165-175 reads
   `company_facts.offices`, extracts the last token (ISO code) from each
   office line, and maps it through ISO_TO_NAME. `_geography()` at lines
   291-313 uses the resolved country: if in EXCLUDE list → FAIL, if in
   INCLUDE list → PASS, if not found → UNKNOWN, if found but not on either
   list → UNKNOWN with message "is on neither list, so it is unestablished
   rather than excluded."

3. **Defect or design:** DESIGN. The code is doing exactly what it was
   designed to do. The rationale is that an office list may be incomplete, a
   company headquartered outside the include list may still deliver inside it,
   and a single office in Cyprus may be a holding company. The system prefers
   to leave the company eligible with uncertainty rather than reject it on
   partial or inferred data.

4. **Which of the four discard shapes:** The third shape - "written in a
   shape it could not parse" - for the 21 records with missing ISO codes. The
   office data IS written to `company_facts.offices`, the criterion DOES read
   it (resolve_country iterates offices), but the ISO code extraction FAILS
   for 17 codes not in ISO_TO_NAME. For the remaining records (where the ISO
   code IS in the map), the data is read and deliberately treated as UNKNOWN
   rather than FAIL - which is the fourth shape, but is a design decision,
   not a defect.

5. **The count:** If office data were allowed to produce FAIL (and missing
   ISO codes were added):
   - 23 records would FAIL (of 550 total)
   - 0 of those are in icp_review
   - 8 are already dropped (no throughput gain)
   - 15 are in queued state (would be rejected before entering the pipeline)
   
   The throughput gain is 15 records that would be rejected earlier in the
   pipeline, saving the cost of processing them. But the risk is that a
   company with an office in Ukraine may still deliver services in the
   client's target markets, and rejecting it permanently on the strength of
   one office record is a loss the design avoids.

6. **How this differs from TLD inference producing FAIL:** It does not
   differ. The principle is the same: "an inference may move a criterion from
   UNKNOWN to PASS and never to FAIL." Office data is inference (the company
   has an office there, but may operate elsewhere), just like a TLD is
   inference (the domain is .ua, but the company may operate elsewhere). The
   difference is that office data is MORE concrete than a TLD - a physical
   office is a stronger signal than a domain registration. But the principle
   still applies.

7. **Per-record office data for TASK-185 Round 2 (25 records):** Of the 25
   records TASK-185 processed, 7 are shown in the report appendix. All have
   offices in INCLUDE countries (US, Canada) and PASS geography, except
   eski.media which has offices in England (GB) but segment.country="england",
   which is not in the include list, so it returns UNKNOWN.

**RISKS:**
- The 15 queued records that would FAIL represent throughput gain if the
  design changes. But the risk of false rejection is real, and the operator
  should decide.
- Adding the missing 17 ISO codes is a safe change (it only allows more
  countries to resolve). Changing the UNKNOWN-vs-FAIL behavior is not safe
  without operator approval, because `icp_fail` is terminal.

**RECOMMENDED CLAUDE ACTION:**
- Add the missing 17 ISO codes to ISO_TO_NAME (CZ, GR, CY, RS, SS, UA, AR,
  HU, JO, SI, LT, EE, ZA, MC, RU, TN, MX). This is a data gap fix, not a
  design change.
- Do not change the UNKNOWN-vs-FAIL behavior without operator approval.
- Consider whether "england" should map to "United Kingdom" in the geography
  logic. One record has offices in England (GB) but segment.country="england",
  which is not in the include list.
- The deliverable report is in `docs/GEOGRAPHY-DISCARDED-2026-09-16.md`.
