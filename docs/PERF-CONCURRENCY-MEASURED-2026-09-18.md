# Provider concurrency, MEASURED: 8x at K=8, no 429 anywhere, knee at K=12

2026-09-18. Every figure below is **MEASURED** against the live ContactOut
API on the route whose cost is zero. Nothing here is modelled. The one thing
that is modelled is labelled where it appears.

    py -3 scripts/measure_provider_concurrency.py --k 1,4,8,12 --requests 24

## The open question this closes

`docs/PERF-LATENCY-MODEL-2026-09-18.md` put provider wait at 98.2-99.7% of a
real 5,000-record pass and was explicit that every latency value in it was
ASSUMED. `scripts/measure_provider_latency.py` then measured the dominant
call - `people-count`, 4,822 of the modelled 8,760 calls - and closed half the
gap, while naming the other half as plainly as it could:

> **THIS IS THE K=1 NUMBER AND NOTHING ELSE.** A provider answering in 200ms
> serially may answer in 900ms at K=8, or return 429.

That was the whole risk in the concurrency plan: the speedup might not exist,
or might exist and be paid for in throttling. It does exist, and it is not.

## The measurement

24 requests per arm, identical in shape, differing only in the query so no
cache can flatter one arm. Arms separated by a settle gap.

    K     wall     ok      p50      p95      max     req/s   speedup   429
    1    11.42s   24/24   0.461s   0.568s   0.595s    2.10        -     0
    4     2.93s   24/24   0.477s   0.542s   0.581s    8.19    3.89x     0
    8     1.43s   24/24   0.454s   0.499s   0.516s   16.78    7.98x     0
    12    1.39s   24/24   0.432s   0.454s   0.945s   17.29    8.23x     0

A second run at `--k 1,2,4 --requests 16` agreed: K=2 2.44x, K=4 4.01x, no 429.

## What it says

**1. The speedup is real and very nearly linear to K=8.** 7.98x at K=8 is
within 0.3% of perfect scaling. This is what a workload that is 99% waiting
looks like when you stop waiting one at a time.

**2. Latency does not degrade under concurrency. It improves slightly.** p50
went 0.461 -> 0.477 -> 0.454 -> 0.432 across K=1,4,8,12, and p95 fell from
0.568s to 0.499s at K=8. The pessimistic reading in the model - "may answer in
900ms at K=8" - is refuted for this route.

**3. There were no 429s at any level tried, including K=12.** ContactOut
sustained ~1,038 requests/minute here without throttling.

**4. The knee is at K=12 and it is OURS, not the provider's.** K=12 buys 3%
over K=8 (8.23x against 7.98x) while its `max` jumps from 0.516s to 0.945s.
Throughput flattening at ~17 req/s while the provider is still answering every
request and never throttling is the signature of a local ceiling - client,
socket pool or network - not a server-side limit. **So going past K=8 on this
route buys nothing and adds tail latency.**

## What this does to the pass

The model's MID band assumed 0.2s for this call. Measured p50 is ~0.46s, so
the serial cost of the 4,822 `people-count` calls in a 5,000-record pass is
about **2,218 seconds - roughly 37 minutes - for that one call alone**, worse
than the whole-pass MID figure the model published.

At K=8, the same calls take about **278 seconds**. (MODELLED: 4,822 x measured
p50 / measured speedup. The 5,000-record pass itself has not been run.)

**The ranking is unchanged and the case is stronger.** Provider wait still
dominates; it is simply both larger than assumed and more tractable than
assumed.

## What this does NOT say, and the limits matter

- **One route only.** `people-count` is free, which is the entire reason it
  could be hammered 88 times. The PAID routes that make up the other ~45% of
  the call count have NOT been measured at any K, and their limits remain
  **UNKNOWN**. This measurement must not be generalised to them.
- **One moment only.** An unpublished limit can be changed without telling
  anybody. This is OBSERVED, not CONFIRMED, and it is evidence about a Friday
  morning.
- **A clean run at K is not permission to run at 2K** in production. The
  escalation rule stands: K=4 is the conservative start and K=8 only after a
  full pass with zero 429s. What changed is that K=8 now has a measured
  ceiling behind it rather than a hope.
- **It says nothing about what may be parallelised.** The shared `Budget` cap,
  the waterfall ledger's append ORDER, the `new_accounts_per_day` reservation
  lock and checkpoint ordering are all still serial by requirement. `gather`'s
  decide-serially / fetch-concurrently / apply-serially-IN-INPUT-ORDER shape
  exists for exactly that reason and this changes none of it.

## The consequence for the rate limiter

TASK-225 landed `src/ratelimit.py` with an UNKNOWN-limit floor of **5 per
minute**, reasoning that no documented provider limit is below it. The
reasoning is sound and the number is wrong for this estate, by a factor this
measurement can now state: the provider sustains **1,038/minute observed**,
and at 5/minute the `people-count` calls in one pass would take **16 hours**
instead of 37 minutes. A limiter that makes the system 28x slower than it
already is would be an outage wearing a safety feature's clothes.

The fix is not a bigger guess. It is a third classification.
`LimitClassification` currently offers CONFIRMED, MARKETING_PAGE and UNKNOWN,
and this estate now holds evidence that is none of those: **OBSERVED** - not
the vendor's word, not a marketing page, but a rate this system has actually
sustained and recorded, with the date it was sustained on.

    people-count   OBSERVED   1,038/min at K=12, no 429, 2026-09-18
                              operate at K=8; K=12 buys 3% and costs tail
    everything else UNKNOWN   the conservative floor, unchanged

`ratelimit.py` is NOT yet integrated. That is the next piece of work and it
should land with the OBSERVED classification, not without it.

## Reproducing

    py -3 scripts/measure_provider_latency.py --samples 30      # K=1
    py -3 scripts/measure_provider_concurrency.py --k 1,4,8,12  # K>1

Both refuse to call anything whose `enrich.COSTS` entry is not 0, checked at
runtime rather than trusted from a docstring. Neither spends a credit.
