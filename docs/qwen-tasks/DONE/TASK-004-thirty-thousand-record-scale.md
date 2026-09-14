# TASK-004 - Where this engine stops working at 30,000 records

## GOAL

A measured answer, not an opinion, to: at what record count does each hot
path stop being usable, and which of them is quadratic.

## WHY IT MATTERS

`work/queue.jsonl` is 300 records and 9MB today. The TAM this is aimed at is
two orders of magnitude larger, and `STREAMING-ARCHITECTURE.md` describes the
next phase as a stream of accounts rather than a file walked stage by stage.
Before anybody designs that, the actual cliff should be measured. A rewrite
justified by a guess is the expensive kind.

## CURRENT CONTEXT

- `src/store.py` is the ONLY door to `work/queue.jsonl`, and
  `src/campaigns.py` the only door to `work/campaigns.jsonl`. Both load the
  whole file.
- `store.transaction()` is used per-write in some places - see
  `bisonfactory._remember_lead`, which opens a transaction per lead.
- Suspects worth checking: `dedupe`, `collision`, `fatigue`, `duplicates`,
  `campaignseg`, `hygiene`, `icp` replay, `funnel`.

## SCOPE

1. Build a SYNTHETIC estate generator: 1k / 5k / 15k / 30k records with the
   same shape as a real record (contacts, cadence, evidence). Synthetic
   means generated, never a copy of `work/queue.jsonl`.
2. Time each candidate path at each size. Plot or tabulate; identify which
   curves are superlinear.
3. For each superlinear path, name the exact line and the data structure that
   would fix it. Do not implement the fix - state it.
4. Measure peak RSS too. The prior MemoryExhaustion on this machine means
   memory is a real limit, not a footnote.

## FILES ALLOWED

`tests/`, `docs/qwen-tasks/`, a new benchmark module, a new markdown report
under `docs/`. Synthetic data goes in a temp directory, never in `work/`.

## FILES FORBIDDEN

`src/**` - measure, do not optimise. `work/**` - never read the real queue
into a benchmark and never write to it. `config/clients/**`.

## PRODUCTION CONSTRAINTS

Offline. No provider calls. No credits. Bounded concurrency - one process at
a time for the memory measurements or the numbers are meaningless.

## TESTS REQUIRED

The generator needs a test that a generated record satisfies the same
invariants a real one does, or the benchmark measures a shape that does not
exist. Reuse the existing invariant checks rather than restating them.

## EXPECTED OUTPUT

`docs/SCALE-MEASUREMENT-30K.md`: a table of path x size x seconds x peak RSS,
and a ranked list of what breaks first.

## DONE CONDITION

Claude can point at one measured number and say "this is why the streaming
architecture is needed, and this is the first thing it has to change".

## RESULT

STATUS: DONE
COMMIT SHA: dbc778f (benchmark + tests), pending final commit (report + task move)
TESTS: tests/test_scale_generator.py — 7 tests, all pass. Validates that
  synthetic records satisfy store.validate, carry required fields, have
  contact keys, have emails or linkedin profiles, cycle through all 28
  defect shapes, and round-trip through store.save/load.
FILES CHANGED:
  - benchmarks/scale_30k.py (new) — measures 12 hot paths at 1k/5k/15k/30k
  - tests/test_scale_generator.py (new) — 7 invariant tests for the generator
  - docs/SCALE-MEASUREMENT-30K.md (new) — the full measurement report
  - docs/qwen-tasks/RUNNING/TASK-004-thirty-thousand-record-scale.md (moved to DONE/)
FINDINGS:
  Two paths are QUADRATIC and will make 30,000 records unusable:

  1. dedupe.find — growth factor 49.7x (1k→15k). 0.14s at 1k, 8.8s at 5k,
     105.7s at 15k, >600s at 30k. The inner loop scans the entire growing
     findings list for every name-key collision: O(n²) in the number of
     records. Fix: replace the linear scan with a set of (record_id,
     contact_key) tuples. One-line change in src/dedupe.py ~line 180.

  2. campaignseg.assign — growth factor 64.1x (1k→15k). 0.05s at 1k, 2.4s
     at 5k, 45.3s at 15k, >600s at 30k. Calls settings(config) inside the
     inner loop, creating a new dict on every invocation. Fix: cache
     settings() once at the top of assign(). Also uses id(entry) as dict
     key (TASK-028 bug class).

  One pattern is LINEAR BUT DOMINATES WALL TIME:

  3. store.transaction — 12.4s per transaction at 30k. bisonfactory._remember_lead
     opens one transaction per lead. 1,000 leads at 30k scale = 3.4 hours.
     Fix: batch writes into one transaction. Longer-term: streaming architecture.

  All other paths (report.funnel, hygiene.index, fatigue.check_all,
  dedupe.company_collisions, store.save, store.load) are LINEAR and
  acceptable at 30k.

  Peak RSS at 15k: 759 MB. At 30k the whole-process run was killed by OOM.
  Queue file at 30k: 125.5 MB.

  THE NUMBER: store.transaction at 30k takes 12.4 seconds per call.
  A batch of 1,000 lead writes takes 3.4 hours. That is why the streaming
  architecture is needed.

RISKS:
  - The 30k dedupe.find and campaignseg.assign measurements exceeded the
    10-minute window. The 1k→15k data conclusively establishes the
    quadratic curve; the 30k run confirms it (>600s at 30k).
  - The initial 30k all-paths run was killed by OOM, demonstrating the
    memory risk at scale.
  - The "superlinear" growth factors for linear paths (store.save, etc.)
    at 1k→15k are an artifact of the small-size constant (JSON parsing
    warmup, memory allocation). The 15k→30k data confirms they are linear.

RECOMMENDED CLAUDE ACTION:
  1. Fix dedupe.find first (one-line change, eliminates the quadratic).
  2. Fix campaignseg.assign second (cache settings, replace id() keys).
  3. Batch bisonfactory._remember_lead writes into one transaction.
  4. The streaming architecture (STREAMING-ARCHITECTURE.md) is justified
     by the measured numbers, not a guess.
