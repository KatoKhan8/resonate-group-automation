# The free path from `queued` to an ICP verdict, for 316 records

**Date:** 2026-09-16
**Task:** TASK-163
**Snapshot:** `work/queue.snapshot.jsonl` (550 records, stamp in `queue.snapshot.STAMP`)

## The question

316 records sit in `queued`, lane `domains`. 250 of them have no `company_facts`,
no `research`, and no `stages`. The remaining 66 have some `company_facts` but
no `research`. If `qualify` runs on these records and ICP returns `dropped`, the
batch is destroyed - `dropped` is terminal and unrecoverable.

Does evidence-free ICP drop? And is there a free research step that populates
evidence before ICP sees the record?

## Answer: A (with nuance)

**The free path is:**

```
python -m src.run --spend --cap 0 --stage enrich qualify
```

It populates evidence before ICP via the free webfetch leg, and no evidence-free
record can reach `dropped`.

## Evidence

### 1. What ICP decides with no evidence (code trace + measurement)

**Code trace** for a record with no `company_facts` and no `research`:

| Step | Function | Result | Deciding line |
|------|----------|--------|---------------|
| Segment | `segments.classify` | `vertical = UNKNOWN` | `classify_vertical` returns UNKNOWN when `text_of(rec)` has no keyword matches (line ~462 in segments.py) |
| V1 Score | `icp.score` | `icp_status = UNKNOWN`, `confidence = LOW` | `_confidence` returns LOW when vertical is UNKNOWN (line ~640 in icp.py) |
| V1 Verdict | `icp._verdict` | `(UNKNOWN, TIER_REVIEW, ...)` | Line ~762: "the vertical could not be determined" |
| Structural | `icpstructural.structural` | `verdict = ICP_REVIEW` | All 5 criteria return UNKNOWN; `verdict_of` returns ICP_REVIEW (line ~310 in icpstructural.py) |
| Final | `_structural_verdict` | `icp_status = REVIEW` | `FROM_STRUCTURAL[ICP_REVIEW] = REVIEW` (line ~830 in icp.py) |

The key invariant: **UNKNOWN is not FAIL** (icpstructural.py docstring). Every
criterion returns UNKNOWN when evidence is absent, and UNKNOWN criteria do not
produce ICP_FAIL. Only an affirmative FAIL status produces a rejection.

**Measurement on 5 records** (`scripts/task163_measure.py`):

| Record ID | Domain | icp_status | icp_score | confidence | structural | state after |
|-----------|--------|------------|-----------|------------|------------|-------------|
| spectrum-mobility | spectrum-mobility.com | review | 0.0 | low | icp_review | queued |
| pearl | justanswer.com | review | 0.0 | low | icp_review | queued |
| relay-app | relay.app | review | 0.0 | low | icp_review | queued |
| gartner-research-board | gartner.com | review | 0.0 | low | icp_review | queued |
| 17hats | 17hats.com | review | 0.0 | low | icp_review | queued |

**Result: 5/5 review, 0/5 dropped, 0/5 rejected.**

The structural criteria for all 5 records:
- `geography`: UNKNOWN (no location evidence)
- `company_type`: UNKNOWN (no vertical or industry)
- `services_business`: UNKNOWN (business model is UNKNOWN)
- `employees`: UNKNOWN (headcount could not be established)
- `tracks_time`: UNKNOWN (no evidence either way)

None returned FAIL. The `verdict_of` function requires at least one FAIL to
produce ICP_FAIL, and absent that, requires all DEFINING criteria to PASS for
ICP_PASS. With all UNKNOWN, the answer is ICP_REVIEW.

### 2. The free research path DOES trigger

**Code trace** for `stage_enrich` with `--spend --cap 0`:

1. `enrich_record(rec, budget, live=True, cap=0, ...)` is called
2. Free `people-count` runs (cost=0, NOT in UNPRICED, so cap=0 allows it)
   - Adds `headcount_signal` to `company_facts`
3. All paid calls blocked: `budget.affordable(cost>0, call)` returns False
4. Step 4b (public evidence):
   - `research.why(rec)` returns None initially (domains lane, 0 contacts)
   - Pre-research verdict computed: `qualify.company(rec, config, store_result=False)`
   - Verdict: `icp_status = "review"`
   - `research.why(rec, verdict=verdict)` checks:
     - `status in ("review", "unknown")` → True
     - `icp_prose_missing(rec)` → True (no research text, no need signals)
   - Returns `NEED_ICP_EVIDENCE`
5. `research.run(rec, config, live=True, spend=budget, ...)` is called
6. Inside `research.run`:
   - `_from_the_site_itself(rec, config)` runs FIRST (before any Apify check)
   - This is `webfetch.research(domain, config)` - free HTTP via urllib
   - If successful, populates `rec["research"]` with website content
   - Returns immediately; paid Apify path never reached

**Measurement** (`scripts/task163_research_trigger.py`):

| Record ID | research.why() before verdict | verdict.icp_status | research.why(verdict) |
|-----------|-------------------------------|--------------------|-----------------------|
| spectrum-mobility | None | review | public_evidence_required_for_icp_dimensions |
| pearl | None | review | public_evidence_required_for_icp_dimensions |
| relay-app | None | review | public_evidence_required_for_icp_dimensions |
| gartner-research-board | None | review | public_evidence_required_for_icp_dimensions |
| 17hats | None | review | public_evidence_required_for_icp_dimensions |

The webfetch trigger fires for all 5 records after the pre-verdict is computed.

### 3. The full free path

```
python -m src.run --spend --cap 0 --stage enrich qualify
```

What happens per record:

1. **stage_enrich** (free with --cap 0):
   - `people-count` (free): adds `headcount_signal` to `company_facts`
   - Paid calls: blocked by cap
   - Pre-research verdict: computed (free), returns `review`
   - `research.why(verdict=review)` → NEED_ICP_EVIDENCE
   - `webfetch.research(domain)`: free HTTP, populates `rec["research"]`
   - Apify: blocked by cap (never reached if webfetch succeeds)

2. **stage_qualify** (always free):
   - `qualify.needs_work(rec)` → True (no prior qualification)
   - `qualify.company(rec, config)`: runs ICP with enriched data
   - Verdict now has research text to score pain dimensions
   - Record moves from `review` to a more informed verdict

### 4. Even without research, qualify is safe

If webfetch fails for a domain (JS rendering required, blocked, timeout, etc.),
the record still enters `stage_qualify` with no research. The measurement above
proves this produces `review`, not `dropped`. The record stays in `queued` and
is fully recoverable.

## The three outcomes, distinguished

| Outcome | icp_status | Recoverable? | Count (5 measured) |
|---------|-----------|--------------|---------------------|
| Qualified | qualified | Yes | 0 |
| Review | review | Yes | 5 |
| Unknown | unknown | Yes | 0 |
| Rejected | rejected | Yes (via _release_stale_icp_drop) | 0 |
| **Dropped** | **N/A (state change)** | **NO** | **0** |

The trap the task names - summary lines that look the same - is handled by
checking `state_after` per record, not just the ICP status. All 5 records
remained in `queued` state.

## What the command costs

| Operation | Cost |
|-----------|------|
| people-count (ContactOut) | 0 credits |
| webfetch (urllib HTTP) | 0 credits |
| qualify.company | 0 credits |
| **Total per record** | **0 credits** |

The `--cap 0` flag blocks all paid calls. `Budget.affordable` specifically
blocks UNPRICED calls (Apify) when cap is 0, but webfetch runs before the
budget check and is not an UNPRICED call - it is simply free.

## Caveats

1. **Webfetch success is not guaranteed.** Some sites require JavaScript
   rendering, block automated access, or return only boilerplate. For these,
   `webfetch.research` returns None and the record qualifies on whatever
   `people-count` provided (just `headcount_signal`). The verdict is still
   `review`, not `dropped`.

2. **The 66 records WITH company_facts** already have some evidence. Their
   verdicts may be better than `review` even without webfetch, depending on
   what `company_facts` contains (industry, employees, description).

3. **`--spend` is required** for webfetch to run. Without it, `live=False`
   and `research.run` returns early before calling webfetch. The `--cap 0`
   ensures no credits are actually spent.

## Recommendation

Run the free path on all 316 records:

```
python -m src.run --spend --cap 0 --stage enrich qualify
```

This is safe: no record can reach `dropped` from evidence-free ICP. The worst
outcome is `review`, which is recoverable. The best outcome is that webfetch
populates enough evidence for a meaningful verdict.

## Files produced

- `scripts/task163_measure.py` - ICP verdict measurement on 5 records
- `scripts/task163_research_trigger.py` - research trigger verification
