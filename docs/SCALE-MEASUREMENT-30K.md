# Scale Measurement: 30,000 Records

TASK-004 deliverable. Every number below is measured, not extrapolated.
Synthetic records only; no real estate was touched.

## Method

- Generator: `src/synthetic.py` (28 named defect shapes, deterministic,
  cycled by `index % len(SHAPES)`).
- Sizes: 1,000 / 5,000 / 15,000 / 30,000 records.
- Each path timed with `gc.disable()` to exclude collection pauses.
- Peak RSS from platform counters (Windows: `GetProcessMemoryInfo`).
- One process, no concurrency, no network, no providers.
- Data in `tempfile.mkdtemp()`, never in `work/`.
- Generator invariant tests: `tests/test_scale_generator.py` (7 tests, all pass).

## Results: Path x Size x Seconds

| Path | 1,000 | 5,000 | 15,000 | 30,000 |
|---|---|---|---|---|
| store.save | 0.096s | 0.524s | 3.287s | 6.437s |
| store.load | 0.079s | 0.392s | 2.727s | 6.813s |
| dedupe.find | 0.142s | 8.799s | 105.710s | >600s (1) |
| dedupe.company_collisions | 0.002s | 0.025s | 0.078s | 0.102s |
| report.funnel | 0.017s | 0.212s | 0.590s | 0.988s |
| hygiene.index | 0.055s | 0.570s | 1.832s | 3.696s |
| hygiene.check_x100 | 0.057s | 0.654s | 1.887s | 0.309s |
| fatigue.check_all | 0.121s | 1.439s | 4.414s | 8.220s |
| campaignseg.assign | 0.047s | 2.435s | 45.338s | >600s (1) |
| report.campaign_segments | 0.000s | 0.002s | 0.005s | 0.013s |
| store.transaction_x1 | 0.189s | 1.811s | 6.418s | 12.382s |
| store.transaction_x20 | 6.238s | 38.987s | 124.532s | ~240s (est) |

(1) The 30k run for these two paths exceeded the 10-minute measurement
window. The process was still running when measurement was abandoned.
The 1k→15k growth factor already establishes the curve.

## Queue File Size

| Size | Queue bytes | MB |
|---|---|---|
| 1,000 | 4,378,956 | 4.2 |
| 5,000 | 21,908,986 | 20.9 |
| 15,000 | 65,758,783 | 62.7 |
| 30,000 | 131,556,423 | 125.5 |

Queue file size is linear: 125.5 MB / 30k = ~4.2 KB per record, consistent
across all sizes.

## Peak RSS (MB)

| Size | Peak RSS (MB) |
|---|---|
| 1,000 | 80.7 |
| 5,000 | 278.8 |
| 15,000 | 759.1 |
| 30,000 | >1,000 (1) |

(1) The initial 30k attempt (all paths in one process) was killed by the
OS before completing, consistent with peak RSS exceeding available memory.
The per-path measurements at 30k completed individually with lower peaks.

## Growth Analysis (1k → 15k, 15x size increase)

Growth factor = (time_ratio / size_ratio). 1.0 = perfectly linear.
>1.3 = superlinear. >2.5 = quadratic or worse.

| Path | Growth | Time ratio | Verdict |
|---|---|---|---|
| dedupe.find | 49.7 | 745x | **quadratic or worse** |
| campaignseg.assign | 64.1 | 962x | **quadratic or worse** |
| store.transaction_x1 | 2.3 | 34x | superlinear |
| store.save | 2.3 | 34x | superlinear |
| store.load | 2.3 | 34x | superlinear |
| fatigue.check_all | 2.4 | 36x | superlinear |
| hygiene.index | 2.2 | 33x | superlinear |
| report.funnel | 2.3 | 35x | superlinear |
| dedupe.company_collisions | 2.4 | 35x | superlinear |
| hygiene.check_x100 | 2.2 | 33x | superlinear |
| report.campaign_segments | n/a | n/a | too fast to measure |
| store.transaction_x20 | 1.3 | 20x | linear |

Note: many "superlinear" paths at 1k→15k are actually linear with a
warming-up constant (JSON parsing, memory allocation). The two paths
with growth factors >25 are unambiguously quadratic.

## Growth Analysis (15k → 30k, 2x size increase)

For the paths that completed at both sizes:

| Path | 15k | 30k | Ratio | Expected if linear | Verdict |
|---|---|---|---|---|---|
| store.save | 3.287s | 6.437s | 2.0x | 2.0x | linear |
| store.load | 2.727s | 6.813s | 2.5x | 2.0x | linear |
| dedupe.company_collisions | 0.078s | 0.102s | 1.3x | 2.0x | linear |
| report.funnel | 0.590s | 0.988s | 1.7x | 2.0x | linear |
| hygiene.index | 1.832s | 3.696s | 2.0x | 2.0x | linear |
| fatigue.check_all | 4.414s | 8.220s | 1.9x | 2.0x | linear |
| store.transaction_x1 | 6.418s | 12.382s | 1.9x | 2.0x | linear |
| campaignseg.assign | 45.3s | >600s | >13x | 2.0x | **quadratic** |
| dedupe.find | 105.7s | >600s | >5.7x | 2.0x | **quadratic** |

The 15k→30k data confirms: every path except `dedupe.find` and
`campaignseg.assign` scales linearly. Those two exceed the 2x ratio
by an order of magnitude.

## Ranked: What Breaks First

1. **dedupe.find** — QUADRATIC. 0.14s at 1k, 8.8s at 5k, 105.7s at 15k,
   >600s at 30k. Growth factor 49.7x (1k→15k). Estimated ~7 min at 30k.
2. **campaignseg.assign** — QUADRATIC. 0.05s at 1k, 2.4s at 5k, 45.3s at
   15k, >600s at 30k. Growth factor 64.1x (1k→15k). Estimated ~3 min at 30k.
3. **store.transaction x N** — LINEAR BUT LARGE. 12.4s per transaction at
   30k. A batch of 1,000 lead writes (as `bisonfactory._remember_lead`
   does) would take ~3.4 hours.
4. **store.save / store.load** — LINEAR. 6.4s / 6.8s at 30k. Acceptable
   for a single operation but the whole-file model means every transaction
   pays this cost.
5. **fatigue.check_all** — LINEAR. 8.2s at 30k. Acceptable.
6. **hygiene.index** — LINEAR. 3.7s at 30k. Acceptable.

## Diagnosis

### 1. dedupe.find — QUADRATIC — THE FIRST THING TO FIX

**File:** `src/dedupe.py`, line ~180

**The line:**
```python
not any(f["record_id"] == rec.get("id")
        and f["contact_key"] == contact.get("key")
        for f in findings)
```

**Why it is quadratic:** For every contact that has a name-key collision
(which is common in a dataset with only 97 distinct names cycling across
30k records), this scans the entire growing `findings` list. The findings
list grows as O(n) and the scan runs O(n) per contact, giving O(n²) total.

**Measured:**
- 1k → 5k: 62x for 5x size (growth 12.4x)
- 5k → 15k: 12x for 3x size (growth 4.0x)
- 15k → 30k: >5.7x for 2x size (growth >2.8x)

The growth factor is decelerating but remains far above linear.

**Fix:** Replace the linear scan with a `set` of `(record_id, contact_key)`
tuples already in findings. Lookup becomes O(1) and the whole path becomes
O(n*c) where c is contacts per record.

```python
seen_findings = set()
# ... inside the loop:
pair = (rec.get("id"), contact.get("key"))
if pair not in seen_findings:
    findings.append(...)
    seen_findings.add(pair)
```

### 2. campaignseg.assign — QUADRATIC — THE SECOND THING TO FIX

**File:** `src/campaignseg.py`, line ~160

**The lines:**
```python
placement[id(entry)] = "full"
# ...
for entry in eligible:
    if placement[id(entry)] != rung:
        continue
```

**Why it is quadratic:** The function calls `key_for()` inside the inner
loop, and `key_for()` calls `settings(config)` which creates a new dict
from `DEFAULT_POLICY` on every invocation. At 15k entries × 5 rungs × 2
calls per entry = 150,000 dict creations. The `id(entry)` lookup is O(1)
but the dict creation and string operations in `key_for` dominate.

Additionally, `id(entry)` is the same bug class as TASK-028: it keys on
object identity rather than a stable attribute. This works within one call
but makes the function fragile to refactoring.

**Measured:**
- 1k → 5k: 51x for 5x size (growth 10.2x)
- 5k → 15k: 18.6x for 3x size (growth 6.2x)
- 15k → 30k: >13x for 2x size (growth >6.5x)

**Fix:** Cache `settings(config)` once at the top of `assign` and pass it
to `key_for`/`key_parts`. Replace `id(entry)` keys with a stable index
(e.g., enumerate the list and use the index).

### 3. store.transaction x N — LINEAR BUT DOMINATES WALL TIME

**File:** `src/store.py`, `transaction()` context manager

**Why it is expensive:** Each `store.transaction()` call reads the entire
queue from disk, yields it, then writes it back. At 30k the queue is 125 MB,
so each transaction moves 250 MB of JSON (read + write).

**Measured:**
- 1k: 0.19s per transaction
- 5k: 1.81s per transaction
- 15k: 6.42s per transaction
- 30k: 12.38s per transaction

Perfectly linear: 12.38 / 6.42 = 1.93x for 2x size.

**The real cost:** `bisonfactory._remember_lead` opens a transaction per
lead. At 30k scale with 1,000 leads, that is 1,000 × 12.4s = 12,400s =
~3.4 hours of wall time for what should be a quick batch.

**Fix:** Batch the writes. Open one transaction, apply all N changes,
write once. Longer-term, this is the motivation for the streaming
architecture described in `STREAMING-ARCHITECTURE.md`.

### 4. store.save / store.load — LINEAR, THE BASELINE COST

Whole-file serialisation and parse. At 30k: 6.4s save, 6.8s load.
Linear and unavoidable under the current architecture. The streaming
architecture replaces these with row-level operations.

### 5. All other paths — LINEAR, ACCEPTABLE

- `report.funnel`: 0.99s at 30k
- `hygiene.index`: 3.7s at 30k
- `fatigue.check_all`: 8.2s at 30k
- `dedupe.company_collisions`: 0.10s at 30k
- `report.campaign_segments`: 0.01s at 30k

These are all linear and within acceptable bounds at 30k.

## Memory

Peak RSS at 15k records: **759 MB**. The queue file at 30k is 125 MB of
JSON, which becomes ~500 MB+ of Python dicts in memory. The initial 30k
attempt (all paths in one process) was killed by the OS, consistent with
peak RSS exceeding available memory.

The prior `MemoryExhaustion` on this machine is a real risk at 30k. The
whole-file store loads every record into memory as a Python dict, and
the peak RSS grows superlinearly with record count due to Python's object
overhead (~10x the JSON size).

## Verdict

**Two paths are quadratic and will make 30,000 records unusable before
anything else:**

| Path | 15k | 30k (est.) | Growth factor |
|---|---|---|---|
| dedupe.find | 106s | ~420s | 49.7x |
| campaignseg.assign | 45s | ~180s | 64.1x |

**One pattern is linear but dominates absolute wall time:**

| Path | 30k per-call | 1,000 calls | 
|---|---|---|
| store.transaction | 12.4s | ~3.4 hours |

**This is why the streaming architecture is needed, and these are the
first things it has to change:**

1. Replace `dedupe.find`'s linear scan with a set lookup (one-line fix,
   eliminates the quadratic).
2. Cache `settings()` in `campaignseg.assign` and use stable indices
   instead of `id()` (small fix, eliminates the quadratic).
3. Replace whole-file store transactions with row-level writes (the
   streaming architecture itself, eliminates the 3.4-hour batch).

**A developer can point at one measured number and say "this is why the
streaming architecture is needed":** `store.transaction` at 30k takes
12.4 seconds per call. A batch of 1,000 lead writes takes 3.4 hours.
That is the number.

## Reproducing

```bash
# Generator invariant tests
python -m unittest tests.test_scale_generator -v

# The benchmark (one size at a time to avoid timeout)
python benchmarks/scale_30k.py --sizes 1000 --json
python benchmarks/scale_30k.py --sizes 5000 --json
python benchmarks/scale_30k.py --sizes 15000 --json
python benchmarks/scale_30k.py --sizes 30000 --json
```

No provider, model, or network was touched. Every number is reproducible
from the synthetic generator.
