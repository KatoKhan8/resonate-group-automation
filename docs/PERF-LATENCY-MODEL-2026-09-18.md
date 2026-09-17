# Provider Latency Model — 2026-09-18

TASK-222. Measured with `scripts/stage_profile.py --latency {low,mid,high}`.
Synthetic records from `synthetic.dataset()`, no network calls, no provider
calls, no PII. **Every latency value below is ASSUMED.** No live provider
latency has been measured in this repository.

## What this is and is not

This document models what a real pass would cost in wall time if provider
calls carried latency. It does NOT measure real provider latency. The model
is a sleep-based approximation labelled everywhere as ASSUMED. A number
presented as a measurement when it is a model is the failure mode this task
exists to prevent.

## Sources consulted

| Source | What it says | Classification |
|---|---|---|
| `docs/PERF-STAGE-BASELINE-2026-09-17.md` | "~300ms per call" | ASSUMED — stated as a rough reference, not measured |
| `src/providers/__init__.py` | `TIMEOUT = 25` seconds | Upper bound on HTTP timeout, not typical latency |
| `src/providers/xai.py` | `XAI_TIMEOUT = 300` seconds | LLM timeout, confirms LLM calls are very slow |
| `docs/GROK-PROVIDER-RESEARCH-2026-09-17.md` | Rate limits, not latency | No latency data |
| `docs/SCALE-MEASUREMENT-30K.md` | "12.4 seconds per call" for bison batch | Batch operation, not per-API-call latency |
| `docs/AI-CALL-SITE-INVENTORY-2026-09-15.md` | Token counts per LLM call | Used to estimate LLM latency from token volume |

**No measured provider p50/p95/p99 exists in this repository.** The LOW/MID/HIGH
bands below are constructed around the ~300ms reference with wider spreads for
providers whose response contracts are unknown.

## Latency model

All values in seconds per call. All ASSUMED.

| Call name | LOW | MID | HIGH | Source / rationale |
|---|---|---|---|---|
| `people-count` | 0.10 | 0.20 | 0.50 | ContactOut free call, lightweight. ~300ms reference. |
| `decision-makers` | 0.20 | 0.40 | 1.00 | ContactOut, heavier payload (multiple profiles). |
| `company-information-from-domain` | 0.10 | 0.30 | 0.80 | ContactOut, single-company lookup. |
| `email-verifier` (ContactOut) | 0.10 | 0.30 | 0.80 | ContactOut verification, single address. |
| `deliverable-verify` | 0.15 | 0.40 | 1.00 | Deliverable API, simple verification. |
| `reoon-verify` | 0.15 | 0.40 | 1.00 | Reoon power mode, catch-all clearing. |
| `aiark-people-search` | 0.50 | 1.00 | 3.00 | AI Ark, slower index, fallback path. |
| `blitz-company` | 0.15 | 0.40 | 1.00 | Blitz, company lookup. |
| `blitz-domain-to-linkedin` | 0.15 | 0.40 | 1.00 | Blitz, domain → LinkedIn. |
| `blitz-linkedin-to-domain` | 0.15 | 0.40 | 1.00 | Blitz, LinkedIn → domain. |
| `blitz-employee-finder` | 0.20 | 0.50 | 1.50 | Blitz, employee search. |
| `blitz-email` | 0.15 | 0.40 | 1.00 | Blitz, email lookup. |
| `apify-research` | 1.00 | 3.00 | 8.00 | Apify actor run, compute-billed, highly variable. |
| `xai-research` | 2.00 | 5.00 | 10.00 | xAI LLM call. `XAI_TIMEOUT=300` in code confirms very slow. |
| `webfetch-crawl` | 0.20 | 0.50 | 2.00 | HTTP crawl, variable by target. |

LLM calls (generate stage) are NOT included in the provider wait model because
they are a separate concern (token cost + model latency) and the task scope is
provider calls. The model covers enrichment and verification only.

## The table

### MID band (reference)

```
RECORDS  PROV_CALLS  BAND  SERIAL_WAIT  CPU_TIME   TOTAL    WAIT%    K=1      K=4      K=8      K=16
   50          93    mid      21.0s       0.1s     21.1s    99.5%    21.0s     5.2s     2.6s     1.3s
  500         879    mid     197.4s       1.3s    198.7s    99.3%   197.4s    49.4s    24.7s    12.3s
5,000       8,760    mid   1,966.8s      15.1s  1,981.9s    99.2% 1,966.8s   491.7s   245.8s   122.9s
```

### LOW band (optimistic)

```
RECORDS  PROV_CALLS  BAND  SERIAL_WAIT  CPU_TIME   TOTAL    WAIT%    K=1      K=4      K=8      K=16
   50          93    low       8.9s       0.1s      9.0s    98.9%     8.9s     2.2s     1.1s     0.6s
  500         879    low      84.3s       1.3s     85.6s    98.5%    84.3s    21.1s    10.5s     5.3s
5,000       8,760    low     840.2s      15.2s    855.4s    98.2%   840.2s   210.1s   105.0s    52.5s
```

### HIGH band (pessimistic)

```
RECORDS  PROV_CALLS  BAND  SERIAL_WAIT  CPU_TIME    TOTAL    WAIT%    K=1       K=4       K=8       K=16
   50          93   high      53.3s       0.1s      53.4s    99.8%    53.3s     13.3s      6.7s      3.3s
  500         879   high     500.7s       1.3s     502.0s    99.7%   500.7s    125.2s     62.6s     31.3s
5,000       8,760   high   4,988.6s      14.6s   5,003.2s    99.7% 4,988.6s  1,247.2s    623.6s    311.8s
```

### Per-provider breakdown at 5,000 records (MID band)

```
CALL                                  COUNT   LAT_s     WAIT_s
--------------------------------------------------------------
people-count                          4,822    0.20      964.4s
email-verifier                        1,074    0.30      322.2s
reoon-verify                            358    0.40      143.2s
deliverable-verify                      358    0.40      143.2s
company-information-from-domain         358    0.30      107.4s
```

**`people-count` dominates:** 4,822 of 6,970 enrich calls (69%) and 964s of
1,967s serial wait (49%). It runs on every domain as the free "is this domain
real?" gate, which is correct — it is the call that stops paid searches on
dead domains. The cost is that it is also the call that creates the most
serial wait.

## Answers to the four questions

### 1. At 500 and 5,000 records, what fraction of a real pass is provider WAIT versus CPU?

| Size | CPU time | Serial wait (MID) | Total | Wait fraction |
|---|---|---|---|---|
| 500 records | 1.3s | 197.4s | 198.7s | **99.3%** |
| 5,000 records | 15.1s | 1,966.8s | 1,981.9s | **99.2%** |

**Provider WAIT dominates at every size.** The local CPU work (normalize,
plan, qualify, personas, generate plan, lint, store save) is 15 seconds at
5,000 records. The provider wait is 33 minutes (MID), 14 minutes (LOW), or
83 minutes (HIGH). The 14-second baseline measurement from
`PERF-STAGE-BASELINE-2026-09-17.md` is 99% CPU because it has zero provider
latency. A real run inverts that completely.

### 2. What does bounded concurrency at K=4/8/16 give, and where does it stop helping?

At 5,000 records (MID band):

| K | Wall time | Speedup | Diminishing returns |
|---|---|---|---|
| 1 (serial) | 1,966.8s (33 min) | 1.0× | — |
| 4 | 491.7s (8.2 min) | 4.0× | — |
| 8 | 245.8s (4.1 min) | 8.0× | 2× over K=4 |
| 16 | 122.9s (2.0 min) | 16.0× | 2× over K=8 |

**The ideal model shows linear speedup with no diminishing returns** because
it assumes every call is independent and the pool is never idle. In practice,
diminishing returns start where the critical path (sequential dependencies)
becomes the floor. See Question 3 for what cannot be parallelised.

**Where it stops helping:** The model breaks down when the critical path
exceeds `serial/K`. At K=16 with MID latency, the ideal wall time is 123s.
If the sequential floor is, say, 60s (from checkpoint ordering), then K=32
would give `max(1967/32, 60) = 61.5s` — only 2s better than K=16 for 2× the
complexity. The practical ceiling is where `serial/K ≈ critical_path`.

### 3. What is NOT parallelisable, and what would break if it were?

This is the most important answer. A concurrency design that ignores these
buys speed and loses the spend audit.

#### 3a. `enrich.spend()` — the waterfall ledger

**Location:** `src/enrich.py:865` (the `spend()` closure inside
`enrich_record`).

**What it does:** Every provider call passes through `spend()`, which:
1. Checks the in-memory `Budget` cap (`budget.charge()`).
2. Checks the durable `spendledger` (`spendledger.check()`).
3. Records the call in the waterfall ledger (`waterfall.record_step()`).

**Why it must be sequential:** The budget is shared across the batch. Two
concurrent calls checking `budget.spent + cost <= budget.cap` can both see
the same `spent` value and both pass, exceeding the cap by one call. The
waterfall ledger is a list appended to the record dict; concurrent appends
from threads would need a lock, and the order of entries would be
non-deterministic, breaking the audit trail that `costs.reconcile()` reads.

**What breaks:** The credit cap becomes a suggestion rather than a bound.
The spend audit reads a ledger with non-deterministic ordering and cannot
reproduce the expected-vs-actual comparison. A cap of 260 credits could
silently spend 262.

#### 3b. The per-record credit cap

**Location:** `src/enrich.py:865-950`, the `Budget` class.

**What it does:** `Budget.charge(cost, what)` checks `self.spent + cost <=
self.cap` and increments `self.spent`. This is a read-modify-write on shared
state.

**Why it must be sequential:** Without a lock, two threads reading
`self.spent = 258` with `cap = 260` and `cost = 5` both pass the check and
both charge, reaching 268. The cap is the single most important spend
control in the system.

**What breaks:** The cap is exceeded. The operator's budget is violated.
`costs.reconcile()` reports `COST_UNRECONCILED` because expected and actual
disagree.

#### 3c. `new_accounts_per_day` reservation lock

**Location:** `src/executionguard.py:694-755`, `src/pilotcaps.py:68`.

**What it does:** Limits how many new accounts (companies) may be opened in
a single day. The ceiling is 5 (`pilotcaps.CEILING["new_accounts_per_day"]`).
The guard reads the current count, checks the limit, and reserves a slot.

**Why it must be sequential:** Read-check-write on a shared counter. Two
concurrent records reading `opened = 4` with limit 5 both pass and both
reserve, making the count 6 against a ceiling of 5.

**What breaks:** The daily account-opening limit is exceeded. This is a
client-visible constraint — opening too many accounts triggers review and
potential account suspension at the provider.

#### 3d. `store.save()` checkpointing

**Location:** `src/run.py:114` (`CHECKPOINT_EVERY = 5`), `src/store.py:815`.

**What it does:** Every 5 records, `store.save()` rewrites the entire queue
file. This is a full-file serialize-and-rename operation.

**Why it must be sequential:** The file is the canonical state. Two
concurrent `store.save()` calls would serialize different versions of the
record list and race on the rename. The loser's writes are lost. The
checkpoint is designed around the invariant that at most one writer exists.

**What breaks:** Lost records. A concurrent save that reads the file while
another is writing sees a partial file. The rename-is-atomic guarantee only
holds when there is one writer.

#### 3e. Per-record enrichment ordering

**Location:** `src/enrich.py:955-1109`, the waterfall sequence inside
`enrich_record`.

**What it does:** Each record's enrichment follows a strict sequence:
1. `people-count` (free, is domain staffed?)
2. `decision-makers` (only if no contacts)
3. `company-information-from-domain` (only if 1 or 2 found nobody)
4. `aiark-people-search` (only if ContactOut found nobody)
5. Verification per contact

Each step's predicate depends on the previous step's result. `decision-makers`
only runs if `people-count` found nobody usable. `company-info` only runs if
`decision-makers` found nobody. The waterfall is a chain of conditionals.

**Why it must be sequential per record:** The predicate for step N reads the
result of step N-1. Parallelising within a record would require either
speculative execution (wasting credits on calls whose predicates will fail)
or a dependency graph (which is just serial execution with extra steps).

**What breaks:** Credits spent on calls that the waterfall would have
skipped. A `decision-makers` call on a domain that `people-count` would have
found staffed wastes 10 credits. At 5,000 records with 70% ContactOut
success rate, that is ~3,500 wasted calls × 10 credits = 35,000 credits.

#### 3f. Cross-record parallelism is safe ONLY for the network I/O

The above constraints are all per-record or shared-state. The one thing that
CAN be parallelised is the HTTP request itself: while record A waits for
ContactOut to respond, record B's ContactOut call can be in flight. This is
the standard thread-pool model and it is what K=4/8/16 gives. But the
`spend()` gate, the budget check, and the waterfall append must happen
BEFORE the HTTP request is dispatched, and the result must be recorded
AFTER it returns. The parallelisable region is the HTTP round-trip alone.

### 4. Given documented provider rate limits, what K is even permitted?

From `docs/GROK-PROVIDER-RESEARCH-2026-09-17.md`:

| Provider | Limit | Value | Classification | Source |
|---|---|---|---|---|
| EmailBison `POST /api/leads/multiple` | 500 leads per request | 500 | **DOCUMENTED** | OpenAPI spec |
| EmailBison "requests per minute" | 3,000 | 3,000 | **MARKETING** | Features page, NOT in API reference |
| EmailBison CSV upload | 50,000 leads per CSV | 50,000 | **DOCUMENTED** | Docs guide |
| HeyReach `AddLeadsToCampaignV2` | 100 account-lead pairs | 100 | **DOCUMENTED** | Postman collection |
| HeyReach rate limit | NOT DOCUMENTED | — | **UNKNOWN** | No rate-limit schema in API docs |
| ContactOut rate limit | NOT DOCUMENTED | — | **UNKNOWN** | No published rate-limit docs found |
| Deliverable rate limit | NOT DOCUMENTED | — | **UNKNOWN** | No published rate-limit docs found |
| Reoon rate limit | NOT DOCUMENTED | — | **UNKNOWN** | No published rate-limit docs found |
| AI Ark rate limit | NOT DOCUMENTED | — | **UNKNOWN** | No published rate-limit docs found |
| Blitz rate limit | NOT DOCUMENTED | — | **UNKNOWN** | No published rate-limit docs found |

**What K is permitted:** For the providers that dominate the call count
(ContactOut at 4,822 people-count + 1,074 email-verifier = 5,896 calls),
the rate limit is **UNKNOWN**. The only documented limits are on EmailBison
and HeyReach, which are write-side providers (lead creation, campaign
attachment) and not part of the enrichment path this model covers.

**Conservative recommendation:** Without documented rate limits for the
enrichment providers, K=4 is the safe starting point. It gives 4× speedup
(33 min → 8 min at MID) without risking rate-limit responses from providers
whose limits are unknown. K=8 doubles that (4 min) but is a guess about
what the providers tolerate. K=16 (2 min) is only justified after observing
zero 429 responses at K=8 for a full pass.

**The 3,000 requests/minute EmailBison figure is MARKETING, not a limit this
system can rely on.** It appears on a features page, not in the API
reference. The API reference documents per-request array sizes (500 leads)
but no rate. A system that designs around 3,000 rpm and gets rate-limited at
500 rpm has built on a number that was never a promise.

## What the model CANNOT answer

1. **Real provider latency.** Every value is ASSUMED. The model cannot
   replace a live measurement. Running `--live` with timing instrumentation
   would produce real numbers; this document deliberately does not.

2. **Rate-limit behaviour under load.** The model assumes every call
   succeeds. A provider that returns 429 at K=8 would invalidate the K=8
   column. The model cannot predict this without documented rate limits.

3. **LLM call latency.** The generate stage plans 13,806 LLM steps at 5,000
   records. Each step is a model call at 2-8 seconds (ASSUMED). The total
   LLM wait is not included in the provider wait model because it is a
   separate resource (tokens + model capacity) with different concurrency
   constraints (prompt caching, rate limits per model).

4. **Cross-pass effects.** The model covers one pass. A second pass with
   caches warm, stages marked done, and records already enriched has a
   different call profile. The model cannot predict it.

5. **The critical path floor.** The model reports ideal concurrency
   speedups. The actual floor depends on the sequential dependencies listed
   in Question 3, which the model does not measure — it states them from
   code reading. A real implementation would need to measure the
   non-parallelisable fraction.

## How to reproduce

```bash
# Without latency model (existing baseline, unchanged):
py -3 scripts/stage_profile.py --sizes 50,500,5000

# With latency model:
py -3 scripts/stage_profile.py --sizes 50,500,5000 --latency mid
py -3 scripts/stage_profile.py --sizes 50,500,5000 --latency low
py -3 scripts/stage_profile.py --sizes 50,500,5000 --latency high

# Custom concurrency levels:
py -3 scripts/stage_profile.py --sizes 5000 --latency mid --concurrency 1,2,4,8,16,32
```

## Tests

```
tests/test_stage_profile.py::TestLatencyModel
  test_latency_model_off_by_default       — model exists, bands ordered
  test_serial_wait_matches_count_times_latency — sum(count × lat) within 1%
  test_k1_equals_serial                   — K=1 == serial
  test_concurrency_reduces_wall_time      — K=4 < K=8 < K=16 < serial
  test_critical_path_floor                — floor applies when serial/K < floor
  test_count_calls_by_provider            — per-call-name breakdown
  test_empty_counts_produce_zero_wait     — no calls → zero wait
```

All 17 tests in `tests/test_stage_profile.py` pass.

---

## MEASURED 2026-09-18: the biggest assumption, replaced. No credits spent.

This document's "what it cannot answer" section put real provider latency
first. For the call that dominates the volume, it did not have to stay
unanswered: `people-count` is 4,822 of the 8,760 modelled calls at 5,000
records and `enrich.COSTS["people-count"]` is **0**. So the largest single
assumption here was measurable for free.

`scripts/measure_provider_latency.py`, 16 serial samples against neutral
public domains, nothing stored:

    ROUTE                              n    min      p50      p95      max
    contactout people-count (FREE)    16  0.402s   0.425s   0.998s   1.177s
    emailbison GET /campaigns         16  0.134s   0.149s   0.166s   0.183s

### The MID band was optimistic by 113% for the dominant call

    assumed   low 0.10   MID 0.20   high 0.50
    measured  p50 0.425  -> between MID and HIGH

And the consequence is larger than it sounds, because this call is 55% of
the volume:

    people-count alone, at the measured p50:   4,822 x 0.425s = 2,049s
    the ENTIRE MID-band estimate for all
    8,760 calls was:                                            1,967s

**One call type, measured, already exceeds the whole MID-band estimate by 83
seconds - and the other 3,938 calls are on top of that.** So a real
5,000-record pass sits at or beyond the MID band rather than comfortably
inside it, and the HIGH band is not a pessimistic outlier.

**This strengthens the conclusion rather than changing it.** Provider wait was
98-99% of a pass under every assumed band; measuring the dominant call moved
the estimate up, not down. Concurrency remains the first performance item.

### What is still ASSUMED

Everything except the two rows above. `decision-makers`, the verification
providers, Blitz, AI Ark, Apify and xAI are all still estimates, and they are
the ones that cost credits to measure - which is why they have not been.
Their bands stand.

### What this number is NOT

**It is the K=1 number and nothing else.** A provider answering in 425ms
serially may answer in 900ms at K=8, or return 429. Nothing here predicts
behaviour under concurrency, and the K=4/8/16 columns above remain an IDEAL
model. The first thing a concurrency implementation should do is re-run this
script under load and find out.

Sample-size honesty: p50 from 16 samples is reasonable; the p95 above is the
second-worst of sixteen and should be read as that rather than as a
distribution tail.
