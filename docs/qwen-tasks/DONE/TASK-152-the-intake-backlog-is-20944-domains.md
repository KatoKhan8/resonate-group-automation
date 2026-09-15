PRIORITY: P1
DEPENDS:

# TASK-152 - 550 of 20,944 domains are in the queue

## THE NUMBER

`batches/productive-*.csv` adapts a 51,741-row people file into 20,944 unique
COMPANY domains. 550 records are in the live queue. That is 2.6%.

The estate was never the constraint - throughput was, and nobody has measured
where it actually stops.

## WHAT THIS TASK IS

Measure the intake pipeline's real cost and rate per stage, so Claude can size
the next batches instead of guessing.

Against `work/queue.snapshot.jsonl` - **quote the STAMP** - and the batch
builder:

1. Per stage, how many of the 550 records are in it, and what does the stage
   cost per record: provider calls, model calls, wall time. `scripts/
   build_intake_batch.py` and `src/ingest.py` are the entry; `src/qualify.py`
   is the first expensive gate.
2. Where do records STOP? Count the terminal states and the reason on each.
   119+ are dropped by ICP - that is the gate working. What else halts, and is
   it a gate or a gap?
3. What does one batch of 250 actually cost end to end, in provider credits
   and model calls, derived from the 550 already processed rather than
   estimated from the code?
4. Which stages are deterministic and which call a model? Cross-reference
   TASK-149 if it has landed.

## WHAT YOU MAY NOT DO

- Do not run `src.ingest` against the real queue. Production state is Claude's.
- No provider writes. No model calls to measure model calls.
- Do not write to `work/`.

## FILES ALLOWED

    docs/INTAKE-THROUGHPUT-2026-09-15.md   (new)
    scripts/task152_*.py

## FILES FORBIDDEN

    src/   work/   config/   batches/

## DELIVERABLE

Per-stage counts and per-record costs from the 550 real records, the terminal
states with reasons, the measured cost of a 250 batch, and the recommended
next batch size with the arithmetic.

---

## RESULT

- **STATUS:** DONE
- **COMMIT:** 43b9176
- **TESTS:** Analysis scripts run against snapshot; no production code changed
- **FILES CHANGED:**
  - `docs/INTAKE-THROUGHPUT-2026-09-15.md` (new) — the deliverable
  - `scripts/task152_analyze_intake.py` (new) — per-stage counts and costs
  - `scripts/task152_deep_dive.py` (new) — held records, ICP detail, batch origins
- **FINDINGS:**
  - Snapshot: `2026-09-15T17:52:12+00:00 from master cf23154 550 records`
  - 250 of 550 are raw intake (not yet qualified) from `productive-intake-00000-00250.csv`
  - 116 dropped by ICP gate (101 for size <20 employees, 17 for geo)
  - 66 queued for human review (ICP verdict: review/unknown)
  - 36 held: unresolved email verification (gap, not gate)
  - Total provider credits: 1,725 (3.14/record amortised, 25.7/sendable)
  - Total model calls: 5,407 (9.83/record amortised, 80.7/sendable)
  - 250-batch projection: 784 provider credits, 2,458 model calls, ~30 sendable
  - To get 50 sendable: 410 records needed; to get 100: 821 records
  - All pre-qualify stages are deterministic; model is called only at draft
  - TASK-149 has not landed (still in TODO)
- **RISKS:**
  - The 40% ICP rejection rate is driven by the purchased list's skew toward micro-agencies (median 5 employees). This rate may not hold on later batches if they have different size distributions.
  - 36 held records represent a gap: no resolution path for accept_all/unresolvable domains.
- **RECOMMENDED CLAUDE ACTION:**
  1. Run qualify on the 250 already queued (free, no credits)
  2. Enrich whatever passes ICP (~74 expected)
  3. Decide on next batch size based on actual yield from the 250
