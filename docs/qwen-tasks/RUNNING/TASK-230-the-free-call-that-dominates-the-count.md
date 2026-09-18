# TASK-230 - give the bounded gather its first caller: the free call

## The numbers this rests on, all measured

`docs/PERF-CONCURRENCY-MEASURED-2026-09-18.md`, against live ContactOut:

    K=1   2.10 req/s   p50 0.461s
    K=4   8.19 req/s   p50 0.477s   3.89x
    K=8  16.78 req/s   p50 0.454s   7.98x     <- operate here
    K=12 17.29 req/s   p50 0.432s   8.23x     <- the knee, and it is OURS

Zero 429s at every level. Latency did not degrade under concurrency; p95 fell.

`people-count` is **4,822 of the 8,760 provider calls** in a modelled
5,000-record pass and its measured serial cost is about **37 minutes**. At
K=8 that is about 5.

## Why THIS call and not a more important one

Because it costs nothing. `enrich.COSTS["people-count"]` is 0.

`src/gather.py`'s own docstring names the trap that makes concurrency
dangerous here: **a timed-out call STILL REACHED THE PROVIDER AND STILL COST A
CREDIT.** `timeout` abandons the wait, it does not cancel the request. On a
paid route, fifty timeouts under-count the ledger by fifty credits and
`costs.reconcile()` then reports clean against a wrong number.

On a route that costs zero, that entire failure mode has no value to be wrong
about. So the call that dominates the count is also the only one where the
first wiring cannot corrupt the spend audit. That is the whole argument for
starting here, and it is why this task does NOT touch `decision-makers`,
`email-verifier` or any other paid route.

## The objective

`src/gather.py` currently has no caller. Give it one: a prefetch of
`company_facts.headcount_signal` across many records, concurrently, before
`enrich.run` walks them one at a time.

Falsifiable requirements:

1. **The shape is gather's and must not be reinvented**: decide SERIALLY,
   fetch CONCURRENTLY, apply SERIALLY IN INPUT ORDER. Input order is what
   keeps the waterfall ledger byte-identical to a serial run, and that is the
   acceptance test below.

2. **EVERY CALL STILL GOES THROUGH `spend()`.** CLAUDE.md: "Every paid call
   goes through enrich's `spend()`, which writes the waterfall ledger. A
   provider call that skips it is invisible to the spend audit, and an audit
   that reports clean because it watched nothing is worse than none." A
   prefetch that populates `headcount_signal` behind `spend()`'s back would
   ALSO silently suppress the `spend()` call inside `enrich` - which is
   guarded by `"headcount_signal" not in facts` - and the ledger would lose
   the step entirely. `spend()` is the DECIDE phase. It runs serially.

3. **THE ACCEPTANCE TEST IS LEDGER EQUALITY.** Run the same fixture cohort
   twice, once serial and once at K=8, and assert the waterfall ledger is
   byte-identical: same steps, same order, same reasons. Not "same count" -
   the ORDER is what `costs.reconcile()` reads. If they differ, the wiring is
   wrong however fast it is.

4. Concurrency is BOUNDED and configurable, defaulting to **K=8**, with the
   measurement named in the comment. Do not default higher: K=12 buys 3% and
   raises `max` from 0.516s to 0.945s.

5. A failure on one record must not fail the pass. `people-count` already
   appends to `failures` and continues; that behaviour is preserved per
   record, and one slow or failing request must not block unrelated records.

6. **The shared `Budget` cap is NOT made concurrent.** Two concurrent charges
   read the same `spent` and both pass, so a 260-credit cap silently spends
   262. Section 7 of `docs/PRODUCTION-HANDOFF-2026-09-18.md` names the four
   things that cannot be parallelised - the Budget cap, the ledger append
   order, the `new_accounts_per_day` reservation lock, and checkpoint
   ordering. Keeping `spend()` in the serial DECIDE phase is what respects
   all four; do not move it.

## Tests required

- Ledger equality, serial vs K=8, on a fixture cohort. This is the one that
  matters.
- Results land on the right records: a prefetch that puts company A's count on
  company B is the worst possible outcome and input-order apply is what
  prevents it. Assert it explicitly with distinguishable fake answers.
- One record's failure leaves the others intact and appends its own failure.
- `spend()` is called once per record that needs the call, and NOT called for
  a record that already has `headcount_signal`.
- Break-proof it: shuffle the apply order deliberately and confirm the ledger
  equality test fails, and fails for that reason.

## Boundaries

Use FAKE providers in tests. Do not call ContactOut in a test.

Do not touch any PAID route. Do not change `enrich.COSTS`. Do not change
`waterfall`'s vocabulary. Do not add a second code path that reaches a
provider without `spend()`.

The timeout stays where `gather` puts it and its docstring keeps saying what
it does NOT do. Enforcing a timeout at the HTTP layer so it aborts the request
is a separate piece of work and is a prerequisite for wiring any PAID route -
say so in your report rather than attempting it here.
