# TASK-041 - Two quadratics and a transaction

TASK-004 measured these and deliberately did not fix them. This fixes them.

## GOAL

Make the three operations TASK-004 named survive 30,000 records.

## THE MEASUREMENTS, from `docs/SCALE-MEASUREMENT-30K.md`

    dedupe.find          0.14s @1k   8.8s @5k   105.7s @15k   >600s @30k
    campaignseg.assign   0.05s @1k   2.4s @5k    45.3s @15k   >600s @30k
    store.transaction                            12.4s per transaction @30k

The first two are QUADRATIC - growth factors of 49.7x and 64.1x from 1k to
15k. The third is linear and still fatal in aggregate:
`bisonfactory._remember_lead` opens ONE TRANSACTION PER LEAD, so a thousand
leads at 30k scale is about 3.4 hours of writing.

## WHAT TASK-004 FOUND, and it is specific

1. **`dedupe.find`** - the inner loop scans the entire growing findings list
   for every name-key collision. Replace the linear scan with a set of
   `(record_id, contact_key)` tuples.
2. **`campaignseg.assign`** - calls `settings(config)` inside the inner loop,
   building a new dict every time. Cache it once at the top. **It also uses
   `id(entry)` as a dict key**, which is the same bug class TASK-028 was
   rejected for: `id()` is a memory address, reused after collection and
   meaningless across processes. Fix that too, and key on something canonical.
3. **`store.transaction`** - batch the lead writes into one transaction rather
   than one per lead.

## THE RULE FOR THIS TASK

**Measure before and after, with the benchmark that already exists.**
`benchmarks/scale_30k.py` is in the repository and produced the numbers above.
A fix that is not measured is a guess, and a fix measured with a different
harness cannot be compared to the table above.

Do not rewrite anything for elegance. Three specific changes, three
measurements.

## FILES ALLOWED

`src/dedupe.py`, `src/campaignseg.py`, `src/bisonfactory.py` (only
`_remember_lead` and its immediate callers), `benchmarks/`, `tests/`,
`docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/store.py` - `transaction` itself is correct and is load-bearing for
`refuse_history_loss`; the fix is in how often it is CALLED, not in what it
does. `src/providerwrites.py`, `src/executionguard.py`, `src/killswitch.py`,
`src/providers/**`, `work/**`.

## PRODUCTION BOUNDARY

ZERO network, ZERO credentials, synthetic estates only - never copy the real
estate into a benchmark. Nothing staged, activated or sent.

## TESTS REQUIRED

- `dedupe.find` returns the SAME findings before and after, on a fixture with
  known duplicates. A faster function that finds different duplicates is not a
  speedup, and dedupe decides who gets contacted twice.
- `campaignseg.assign` returns the same assignment, and is keyed on something
  that survives a new object - prove it by passing a rebuilt entry.
- The batched lead write produces the same canonical state as the per-lead
  one, and still refuses a history-losing write.
- Before/after timings at 1k, 5k and 15k from `benchmarks/scale_30k.py`.

## DONE CONDITION

Both quadratics are linear or near it, the transaction count for N leads is
O(1) rather than O(N), and the before/after table is in the result block.

## HANDOFF FORMAT

STATUS / COMMIT SHA / FILES CHANGED / TESTS RUN / TEST RESULTS / BUGS FOUND /
BUGS FIXED / RISKS / OPEN QUESTIONS / RECOMMENDED CLAUDE ACTION - plus the
before/after timing table and the grep proving each new name is consumed.
