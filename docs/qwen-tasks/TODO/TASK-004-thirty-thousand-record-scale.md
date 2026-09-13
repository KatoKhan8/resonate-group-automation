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

STATUS: TODO
COMMIT SHA:
TESTS:
FILES CHANGED:
FINDINGS:
RISKS:
RECOMMENDED CLAUDE ACTION:
