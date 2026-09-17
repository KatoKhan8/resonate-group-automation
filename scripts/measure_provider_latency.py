#!/usr/bin/env python3
"""Real provider latency, measured on the calls that cost nothing.

    py -3 scripts/measure_provider_latency.py
    py -3 scripts/measure_provider_latency.py --samples 40

**SPENDS NO CREDITS.** It calls only routes whose cost is zero:
`enrich.COSTS["people-count"]` is 0 by policy ("people-count is free,
everything else burns credits" - CLAUDE.md) and EmailBison reads are GETs.
It refuses to call anything with a non-zero cost, and the refusal is checked
against `enrich.COSTS` at runtime rather than trusted from this docstring.

## Why this exists

`docs/PERF-LATENCY-MODEL-2026-09-18.md` models a 5,000-record pass as 99% of
its wall time spent waiting on providers - and says plainly that **every
latency value in it is ASSUMED**, because no measured p50/p95/p99 exists
anywhere in this repository. The model's own "what it cannot answer" section
names this first.

It does not have to stay assumed for the call that dominates the count.
`people-count` is 4,822 of the 8,760 modelled calls at 5,000 records, and it
is free. So the largest single assumption in the model is measurable at zero
cost, which is what this does.

## What it measures, and what it does not

Measured: wall-clock round trip from just before the request to just after
the response is decoded, which is what a serial pipeline actually waits for.

NOT measured: latency under concurrency. A provider that answers in 200ms
serially may answer in 900ms at K=8, or return 429. **This produces the K=1
number and nothing else**, and a concurrency design must not read it as a
prediction of K=8.

Percentiles from a small sample are themselves uncertain. The sample size is
printed beside every figure for that reason, and p95 from 20 samples is
reported as what it is: the second-worst of twenty.
"""
import argparse
import json
import os
import statistics
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import enrich
from src.providers import bison, contactout, load_env, request

# Domains to ask about. Real, public, obviously-not-prospects, and used only
# as an argument - nothing is stored and no person is looked up.
NEUTRAL_DOMAINS = ("example.com", "wikipedia.org", "python.org", "gnu.org",
                   "mozilla.org", "apache.org", "debian.org", "kernel.org")


def _refuse_if_it_costs(call):
    """A call with a non-zero cost is not measurable for free. Refuse it."""
    cost = enrich.COSTS.get(call)
    if cost is None:
        raise SystemExit(f"{call!r} is not in enrich.COSTS; refusing to "
                         f"call a route whose price this script cannot read")
    if cost:
        raise SystemExit(f"{call!r} costs {cost} credit(s). This script "
                         f"measures only free routes.")
    return True


def _percentiles(times, label, samples):
    if not times:
        print(f"  {label:34} no successful samples")
        return None
    ordered = sorted(times)
    out = {
        "n": len(ordered),
        "min": ordered[0],
        "p50": statistics.median(ordered),
        "p95": ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))],
        "max": ordered[-1],
        "mean": statistics.fmean(ordered),
    }
    print(f"  {label:34} n={out['n']:<4} "
          f"min {out['min']:.3f}s  p50 {out['p50']:.3f}s  "
          f"p95 {out['p95']:.3f}s  max {out['max']:.3f}s")
    return out


def measure_people_count(samples):
    """ContactOut people-count. FREE, and 55% of the modelled call volume."""
    _refuse_if_it_costs("people-count")
    times, failures = [], 0
    for i in range(samples):
        domain = NEUTRAL_DOMAINS[i % len(NEUTRAL_DOMAINS)]
        start = time.perf_counter()
        try:
            contactout.people_count(domain=domain)
            times.append(time.perf_counter() - start)
        except Exception as exc:                   # noqa: BLE001 - classified
            failures += 1
            if failures == 1:
                print(f"    first failure: {type(exc).__name__}: "
                      f"{str(exc)[:110]}")
    return times, failures


def measure_bison_read(samples):
    """An EmailBison GET. Free, and the route the census walked 12,000 times."""
    times, failures = [], 0
    for _ in range(samples):
        start = time.perf_counter()
        try:
            status, _data = request(
                "GET", bison.query(f"{bison.base()}/campaigns",
                                   {"page": 1, "per_page": 1}),
                bison.headers())
            if status and 200 <= status < 300:
                times.append(time.perf_counter() - start)
            else:
                failures += 1
        except Exception:                          # noqa: BLE001 - classified
            failures += 1
    return times, failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=20)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    load_env()

    print(f"REAL provider latency, K=1 (serial). {args.samples} samples each.")
    print("Free routes only - no credits are spent.")
    print()

    results = {}
    for name, fn in (("contactout people-count (FREE)", measure_people_count),
                     ("emailbison GET /campaigns", measure_bison_read)):
        times, failures = fn(args.samples)
        stats = _percentiles(times, name, args.samples)
        if failures:
            print(f"  {'':34} {failures} call(s) failed and are excluded")
        if stats:
            results[name] = stats

    print()
    print("AGAINST THE MODEL'S ASSUMED VALUES "
          "(docs/PERF-LATENCY-MODEL-2026-09-18.md):")
    assumed = {"contactout people-count (FREE)": (0.10, 0.20, 0.50)}
    for name, (low, mid, high) in assumed.items():
        got = results.get(name)
        if not got:
            print(f"  {name}: not measured this run")
            continue
        p50 = got["p50"]
        where = ("BELOW the LOW band" if p50 < low else
                 "between LOW and MID" if p50 < mid else
                 "between MID and HIGH" if p50 < high else
                 "ABOVE the HIGH band")
        print(f"  {name}")
        print(f"    assumed low/mid/high {low}/{mid}/{high}s "
              f"-> measured p50 {p50:.3f}s  ({where})")
        print(f"    the MID band is {'optimistic' if p50 > mid else 'pessimistic'} "
              f"by {abs(p50 - mid) / max(mid, 1e-9) * 100:.0f}%")

    print()
    print("THIS IS THE K=1 NUMBER AND NOTHING ELSE. A provider answering in")
    print("200ms serially may answer in 900ms at K=8, or return 429. Do not")
    print("read it as a prediction of behaviour under concurrency.")

    if args.json:
        print()
        print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
