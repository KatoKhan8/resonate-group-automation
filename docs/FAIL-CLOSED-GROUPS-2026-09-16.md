# FAIL-CLOSED GROUPS - 2026-09-16

TASK-213 deliverable. Read-only analysis of the 550-record live queue.

## Source

- File: `work/queue.jsonl` in Claude's worktree (`resonate-group-automation`)
- Records: 550
- Generated: 2026-09-16 from live state

## Summary

**TASK-211's "42 fail-closed" grouping was wrong on both counts.**

The 42 records do not exist as a single misfiled population. The two groups
TASK-211 identified were based on `icp_flags` text matching, not on the actual
criterion verdict. The flags are informational; the criterion is the verdict.

| TASK-211 claim | Actual count | Actual status |
|----------------|--------------|---------------|
| 32 too_small, fail-closed | 106 employees FAIL | All already `rejected`, 90 dropped |
| 10 geo_excluded, fail-closed | 2 geo FAIL (exclude list) | Both already `rejected` and dropped |
| - | 296 geo UNKNOWN (not on include list) | NOT fail-closed; TASK-193 design |

## 1. Where the records sit

### too_small (employees criterion FAIL): 106 records

| State | Count | icp_status | structural_verdict |
|-------|-------|------------|-------------------|
| dropped | 90 | rejected | icp_fail |
| queued | 16 | rejected | icp_fail |

**All 106 are already terminal.** Zero are in review. The verdict is recorded
on the criterion: `employees.status = "fail"` with a measured headcount below
the tolerated floor of 14 (20 less 30% tolerance).

The 16 in state `queued` with `icp_status=rejected` will not advance - the
pipeline gates on `icp_status` and `routing.plan` zeroes the contact cap for
anything not `qualified`.

### geo_excluded (geography criterion FAIL): 2 records

| State | Count | icp_status | structural_verdict |
|-------|-------|------------|-------------------|
| dropped | 2 | rejected | icp_fail |

Both are already terminal. One was China, one was India - both on the client's
explicit exclude list.

### geo_not_on_include_list (geography UNKNOWN): 296 records

| State | Count | icp_status | structural_verdict |
|-------|-------|------------|-------------------|
| queued | 292 | review: 208, rejected: 88 | icp_review: 208, icp_fail: 88 |
| dropped | 4 | review/rejected | varies |

These 296 are **NOT fail-closed**. The geography criterion returns UNKNOWN when
a country resolves but is not on the include list. This is the TASK-193
design finding: "a company headquartered outside the target geography may
still deliver inside it."

## 2. Is the verdict recorded or only derivable?

**Recorded.** For all 106 employees-FAIL records:

- `qualification.verdict.structural.criteria.employees.status = "fail"`
- `qualification.verdict.structural.verdict = "icp_fail"`
- `qualification.verdict.icp_status = "rejected"`

The verdict is stored at every level of the chain. It is not inferred from
`icp_flags` or any other derivative field.

**The `icp_flags` field is a separate, earlier signal.** 78 records carry an
`icp_flags` entry like "11 employees, under the client minimum of 20" but
their employees criterion is NOT fail. These are records where:

- The headcount is a band (11-50) that straddles the floor → UNKNOWN
- The headcount is within tolerance (14-19) → PASS_WITH_TOLERANCE
- A second provider raised the headcount above the floor → PASS

The flag notes the raw data; the criterion evaluates all evidence. This is the
system working correctly, not a discrepancy.

## 3. TASK-193 check on geo_excluded

**Confirmed: the 10 "geo_excluded" TASK-211 named are NOT fail-closed.**

TASK-193 established that `_geography()` returns UNKNOWN (not FAIL) when a
country resolves but is not on the include list. The code at
`src/icpstructural.py` lines 375-398:

```python
# After checking exclude list (FAIL) and include list (PASS):
if not country and not _norm(region):
    return _answer(UNKNOWN, "no usable location evidence...")
return _answer(UNKNOWN,
               "%r is on neither list, so it is unestablished rather than "
               "excluded" % (country or region),
               source=source or "segment.region")
```

The 296 records with geography UNKNOWN are correctly held. They are not
fail-closed and should not be moved.

Only 2 records have geography FAIL (on the exclude list). Both are already
dropped and rejected.

## 4. What should happen per group

| Group | Count | Action |
|-------|-------|--------|
| too_small, employees FAIL, already rejected | 106 | Nothing. Already terminal. |
| geo FAIL, exclude list, already rejected | 2 | Nothing. Already terminal. |
| geo UNKNOWN, not on include list | 296 | Nothing. Correctly held per TASK-193 design. |
| too_small flag but criterion not FAIL | 78 | Nothing. System working correctly. |

**No record should be moved.** The 42 records TASK-211 identified as
"fail-closed, sitting in review" do not exist. The too_small records are
already rejected; the geo_excluded records are correctly UNKNOWN.

## 5. Corrected review count

**215 records have `icp_status = "review"`.** This is the correct number.

Breakdown of the 215 review records by unknown criteria:

| Unknown criteria | Count |
|-----------------|-------|
| company_type, geography, services_business, tracks_time | 104 |
| geography, tracks_time | 35 |
| company_type, employees, geography, services_business, tracks_time | 33 |
| employees, geography, tracks_time | 13 |
| geography, services_business, tracks_time | 13 |
| employees, geography, services_business, tracks_time | 10 |
| company_type, services_business, tracks_time | 4 |
| company_type, employees, services_business, tracks_time | 3 |

**208 of 215 review records have geography as UNKNOWN.** This is the dominant
reason records are in review. It is not a misfiling - it is the honest answer
when a company's location cannot be established against the client's lists.

**7 of 215 review records do NOT have geography unknown.** These have other
combinations of unknown criteria (company_type, services_business,
tracks_time, employees). They are in review because the evidence is
genuinely insufficient, not because something is misfiled.

**Zero review records have any FAIL criterion.** The system is not holding
failed records in review. Every record in review is there because at least
one criterion is UNKNOWN.

## The throughput implication

The review queue of 215 is not inflated by 42 misfiled records. It is the
correct size for an estate where:

- 208 records have unknown geography (country not on either list)
- 7 records have other unknown criteria
- All 106 employees-FAIL records are already rejected
- All 2 geo-FAIL records are already rejected

The throughput question is not "how do we shrink review by moving records
out" but "how do we resolve the 208 unknown-geography records" - and the
answer to that is more evidence (free crawl, then ContactOut), not a status
change.
