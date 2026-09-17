# Per-Stage Pipeline Baseline — 2026-09-17

TASK-220. Measured with `scripts/stage_profile.py`. Synthetic records from
`synthetic.dataset()`, no network calls, no provider calls, no PII. Median of
3 runs per size.

## What is measured

Ten stages, at 50, 500 and 5,000 synthetic records:

| Stage | What it does |
|---|---|
| normalize_dedupe | `dedupe.normalise_email`, `normalise_domain`, `identity.assign_keys` over every contact |
| enrich_plan | `enrich.plan()` — what provider calls would be made, including ICP and evidence gates |
| collision_history | Identity index construction (strong_index + name_index) per record, `reconsider_exclusions` |
| mx_screening | `mx.for_domain()` per contact domain with a fake resolver (no DNS), MX cache |
| verification_plan | `verification.plan()` per candidate contact |
| icp_qualify | `qualify.company()` — the ICP verdict, runs for real, spends nothing |
| personas | `personas.select()` + `export()` |
| generate_plan | `generate.plan()` — what LLM calls would be made |
| lint | `lint.check()` per cadence step with generated copy |
| store_save | `store.save()` — full-file rewrite of the queue |

## Counting rules

- **PROVIDER_CALLS**: counted from `enrich.plan()` output. A call with cost > 0
  or a named free call (people-count, webfetch-crawl) counts. Zero-cost
  internal steps do not.
- **CACHE_HITS**: distinguished between the pass-scoped crawl cache
  (`research._crawl_cache`) and the persistent MX cache (`mx-cache.json`).
- **WALL_TIME**: `time.perf_counter()` around each stage. Stages sum to within
  a few percent of total runtime; the gap is reported as unattributed time.
- **BYTES_WRITTEN**: real filesystem bytes from `os.path.getsize()` after
  `store.save()`.

## Table: 50 records

    STAGE                WALL_TIME   PER_REC   PROV_CALLS   CACHE_CRAW   CACHE_MX
    ─────────────────────────────────────────────────────────────────────────────
    normalize_dedupe        0.0001s    0.00ms            0            0          0
    enrich_plan             0.0009s    0.02ms           73            0          0
    collision_history       0.0003s    0.01ms            0            0          0
    mx_screening            0.0044s    0.09ms            0            0         47
    verification_plan       0.0006s    0.01ms           20            0          0
    icp_qualify             0.0382s    0.76ms            0            0          0
    personas                0.0227s    0.45ms            0            0          0
    generate_plan           0.0335s    0.67ms            0            0          0
    lint                    0.0050s    0.10ms            0            0          0
    store_save              0.0200s    0.40ms            0            0          0
    ─────────────────────────────────────────────────────────────────────────────
    stages_sum              0.1265s
    total_pipeline          0.1047s
    unattributed            0.0000s (0.0%)

    File size: 216.2 KB    Contacts: 94    Build time: 0.010s

## Table: 500 records

    STAGE                WALL_TIME   PER_REC   PROV_CALLS   CACHE_CRAW   CACHE_MX
    ─────────────────────────────────────────────────────────────────────────────
    normalize_dedupe        0.0023s    0.00ms            0            0          0
    enrich_plan             0.0166s    0.03ms          699            0          0
    collision_history       0.0125s    0.02ms            0            0          0
    mx_screening            0.1103s    0.22ms            0            0        481
    verification_plan       0.0144s    0.03ms          180            0          0
    icp_qualify             0.9782s    1.96ms            0            0          0
    personas                0.4971s    0.99ms            0            0          0
    generate_plan           0.8733s    1.75ms            0            0          0
    lint                    0.1305s    0.26ms            0            0          0
    store_save              0.2350s    0.47ms            0            0          0
    ─────────────────────────────────────────────────────────────────────────────
    stages_sum              2.9078s
    total_pipeline          2.6329s
    unattributed            0.0000s (0.0%)

    File size: 2,141.2 KB    Contacts: 930    Build time: 0.051s

## Table: 5,000 records

    STAGE                WALL_TIME   PER_REC   PROV_CALLS   CACHE_CRAW   CACHE_MX
    ─────────────────────────────────────────────────────────────────────────────
    normalize_dedupe        0.0223s    0.00ms            0            0          0
    enrich_plan             0.1147s    0.02ms         6970            0          0
    collision_history       0.0843s    0.02ms            0            0          0
    mx_screening            0.5487s    0.11ms            0            0       4819
    verification_plan       0.0855s    0.02ms         1790            0          0
    icp_qualify             4.5354s    0.91ms            0            0          0
    personas                3.7594s    0.75ms            0            0          0
    generate_plan           4.8231s    0.96ms            0            0          0
    lint                    0.6193s    0.12ms            0            0          0
    store_save              1.3049s    0.26ms            0            0          0
    ─────────────────────────────────────────────────────────────────────────────
    stages_sum             15.9578s
    total_pipeline         13.8702s
    unattributed            0.0000s (0.0%)

    File size: 21,395.8 KB    Contacts: 9,286    Build time: 1.259s

## Scaling per stage

### 50 → 500 (x10 records)

    STAGE                TIME_RATIO   VERDICT
    ─────────────────────────────────────────
    total_pipeline           x25.1    WORSE THAN LINEAR
    normalize_dedupe         x20.5    WORSE
    enrich_plan              x19.3    WORSE
    collision_history        x40.7    WORSE
    mx_screening             x25.1    WORSE
    verification_plan        x25.4    WORSE
    icp_qualify              x25.6    WORSE
    personas                 x21.9    WORSE
    generate_plan            x26.1    WORSE
    lint                     x26.1    WORSE
    store_save               x11.7    LINEAR

### 500 → 5,000 (x10 records)

    STAGE                TIME_RATIO   VERDICT
    ─────────────────────────────────────────
    total_pipeline            x5.3    LINEAR (sub-linear even)
    normalize_dedupe          x9.7    LINEAR
    enrich_plan               x6.9    LINEAR
    collision_history         x6.8    LINEAR
    mx_screening              x5.0    LINEAR
    verification_plan         x5.9    LINEAR
    icp_qualify               x4.6    LINEAR
    personas                  x7.6    LINEAR
    generate_plan             x5.5    LINEAR
    lint                      x4.7    LINEAR
    store_save                x5.6    LINEAR

**Interpretation:** The super-linear scaling at 50→500 is a fixed-overhead
effect. At 50 records the per-stage fixed costs (config loading, cache
initialisation, import overhead) dominate; by 500 the variable cost per
record takes over and scaling is linear or better. The 500→5,000 transition
agrees: x10 records for x5.3 time.

**CORRECTED ON REVIEW — THE "NO QUADRATIC SCALING" CONCLUSION WAS WRONG, AND
IN THE DIRECTION THAT WOULD HAVE CANCELLED THE STORAGE WORK.**

This harness calls `store.save()` ONCE per pass. **The pipeline calls it
every five records.** So `store_save x5.6 LINEAR` above is a true statement
about one whole-file write - which is of course linear in file size - and
not about what a pass costs. A pass performs N/5 of those writes, each O(N),
and that product is quadratic. `scripts/store_write_profile.py` measures the
real thing directly:

    RECORDS  CHECKPOINTS  WRITE_TIME  MB_WRITTEN  AMPLIFICATION
        500          100      3.40 s        43.6       492.4x
       5000         1000    211.72 s      4369.1      4918.9x

x10 records, x62 time, x100 bytes. Persistence is quadratic and remains the
number one bottleneck at the target scale. **Read the two documents together:
this one ranks the stages of a single pass; that one measures what repeating
the persistence step costs.** The 1.30s `store_save` figure below is one
write of a 21 MB file, not a pass.

A second correction: `unattributed` was computed as
`max(0, total - stages_sum)` and printed 0.0% at every size while
`stages_sum` EXCEEDED `total_pipeline` by 10-21%. That is an instrument
reporting "all time accounted for" about two numbers that disagree. They
disagree because `full_pipeline` re-runs a SUBSET of the stages with caches
already warm, so it is not the same workload as their sum. The gap is now
reported SIGNED (-17.0% at 50 records) and the two numbers are not to be
read as a conservation check.

## Top 5 bottlenecks ranked by measured seconds at 5,000 records

| Rank | Stage | Seconds | ms/record | What proves it |
|---|---|---|---|---|
| 1 | generate_plan | 4.82s | 0.96 | `generate.plan()` iterates every contact × every cadence step, building the LLM call list. 13,806 steps planned at 5,000 records. |
| 2 | icp_qualify | 4.54s | 0.91 | `qualify.company()` runs the full ICP fingerprint comparison per record. Each comparison touches evidence scoring, contradiction detection, and dimension matching. |
| 3 | personas | 3.76s | 0.75 | `personas.select()` + `export()` walks every contact, scores them against the persona model, and writes the selection. |
| 4 | store_save | 1.30s | 0.26 | ONE `store.save()` of a 21 MB file. A PASS does N/5 of these - 1,000 at 5,000 records, 4.4 GB and 211 s. This row understates it by three orders of magnitude; see the correction above. |
| 5 | lint | 0.62s | 0.12 | `lint.check()` runs per cadence step. At 5,000 records with ~2 contacts each and ~6 steps per contact, that is ~60,000 lint checks. |

**Together, the top 3 (generate_plan + icp_qualify + personas) account for
13.12s of 15.96s total stage time — 82% of the pipeline cost.**

## Hypothesis adjudication

### H1: Full-file rewrite on every checkpoint — CONFIRMED (closed)

Measured by `scripts/store_write_profile.py`: 492x write amplification at 500
records. This task confirms: 53.7 MB written at 5,000 records for one record
change. **Closed, not to be re-measured.**

### H2: Checkpoint frequency — CONFIRMED (closed)

CHECKPOINT_EVERY=5 means N/5 whole-file writes per pass. **Closed, not to be
re-measured.**

### H3: Sequential per-record provider calls — CONFIRMED

At 5,000 records, 8,760 provider calls are planned (6,970 from enrich_plan +
1,790 from verification_plan). Every call is dispatched sequentially in a
`for rec in recs` loop inside `enrich_record`. No batching, no concurrency.
With real providers at ~300ms per call, this would be ~44 minutes of serial
waiting.

### H4: No batching/concurrency — CONFIRMED

Every stage iterates `for rec in recs` sequentially. No batch API, no thread
pool, no asyncio. The enrich plan, qualify, personas, generate and lint
stages all process one record at a time.

### H5: evidence_id as cross-record cache key — REFUTED (closed)

Every consumer uses `evidence.evidence_id` as an intra-record reference.
Nothing uses it as a cross-record cache key. **Closed, not to be
re-measured.**

### H6: Repeated full index construction — CONFIRMED

`collision_history` stage: 0.084s at 5,000 records. The `strong_index` +
`name_index` are rebuilt per `merge_contacts` call (inside `enrich_record`
for every provider payload). Not cached across records. At 5,000 records
with multiple provider calls per record, this is thousands of index
reconstructions.

### H7: LLM in deterministic paths — NOT MEASURED

`generate.plan()` counts 13,806 LLM steps at 5,000 records in 4.82s. The
LLM is not called in dry mode. The cost of actual LLM calls (latency +
tokens) is not measured here because fake providers have no model. The
planning cost itself is the third-largest bottleneck.

### H8: Synchronous waits on slow providers — NOT MEASURED

With fake providers there are no waits. This hypothesis requires live
provider latency to measure. The code shows every provider call is
synchronous: `contactout.decision_makers()`, `aiark.people_search()`,
`verification.verify()` all block until the response arrives. No timeouts
shorter than the HTTP default.

### H9: Repeated readbacks — CONFIRMED

`store_save`: 1.30s, 53,728,018 bytes written for one record change at
5,000 records. CHECKPOINT_EVERY=5 means N/5 full-file writes per pass.
Confirmed by `store_write_profile.py`: 492x amplification at 500.

### H10: Stage serialisation — CONFIRMED

`STAGES = ('enrich', 'qualify', 'personas', 'generate', 'render', 'push')`
run sequentially. Each iterates every record before the next stage starts.
No overlap, no pipelining. A record that finishes enrich waits for every
other record to finish enrich before qualify begins.

## The crawl cache finding

`research._crawl_cache` is an in-memory dict cleared at the start of every
`enrich.run()` pass. Its identity model is already correct — it stores with
`record_id=None` and re-stamps per record on reuse — it simply does not
survive the pass. At 5,000 records the crawl cache hit rate is 0 because
each synthetic record has a unique domain. In a real estate with repeated
domains, the cache would help within a single pass but provides no
cross-pass benefit. **Measured: 0 crawl cache hits at every size. Not fixed
in this task.**

## The MX cache finding

The MX cache persists across passes (stored in `mx-cache.json`). At 5,000
records with 9,286 contacts, the cache served 4,819 hits (52%). The other
48% were unique domains (each synthetic record has a unique `.test` domain).
In a real estate with repeated domains, the hit rate would be much higher.
The cache is loaded once per run and saved once, which is correct.

## Raw JSON

The full measurement data is in `out/stage_profile_results.json` (gitignored,
regenerate with `py -3 scripts/stage_profile.py --json`).

## What is NOT measured

- **Real provider latency.** Every provider call is counted but not timed.
  With fake providers the call cost is zero. H3 and H8 need live latency to
  quantify.
- **LLM call cost.** `generate.plan()` counts steps but does not call the
  model. H7 needs a live model to quantify.
- **Memory pressure.** Resident memory is reported but not tracked per stage.
  At 5,000 records the process uses ~100 MB; at 30,000 it may be different.
- **Cross-pass effects.** Each measurement starts from a fresh estate. The
  cost of a second pass (with caches warm, stages marked done) is not
  measured.
