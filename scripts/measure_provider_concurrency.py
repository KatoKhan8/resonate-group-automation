#!/usr/bin/env python3
"""What a provider actually does at K>1, measured on the call that costs nothing.

    py -3 scripts/measure_provider_concurrency.py
    py -3 scripts/measure_provider_concurrency.py --k 1,2,4 --requests 24

**SPENDS NO CREDITS.** It calls one route: ContactOut `people-count`, whose
cost is 0 by policy ("people-count is free, everything else burns credits" -
CLAUDE.md). The zero is checked against `enrich.COSTS` at runtime rather than
trusted from this docstring, and the script refuses to run if it has moved.

## Why this exists

`docs/PERF-LATENCY-MODEL-2026-09-18.md` models provider wait at 98-99% of a
real pass and says every latency value in it is ASSUMED.
`scripts/measure_provider_latency.py` removed the largest assumption by
measuring the dominant call - p50 0.425s, 112% slower than the model's MID
band - and was explicit about its own limit:

    THIS IS THE K=1 NUMBER AND NOTHING ELSE. A provider answering in
    200ms serially may answer in 900ms at K=8, or return 429.

That sentence is the open question, and it is the one a concurrency design
cannot be built without. This answers it for the call that dominates the
count, and only for that call.

## Why a number is needed before a limiter can have a default

A token bucket needs a rate. TASK-225's `ratelimit.py` sets the UNKNOWN-limit
floor at **5 per minute**, on the reasoning that no documented provider limit
is below it. That reasoning is sound and the number is still wrong for this
estate: 4,822 of the 8,760 provider calls in a 5,000-record pass are
`people-count`, and at 5/minute those alone take **16 hours** against the ~34
minutes the same pass takes serially today. A limiter that makes the system
28x slower is not a safety feature, it is an outage.

The honest fix is not to guess a larger number. It is to measure what the
provider sustains, and to classify the result as OBSERVED - which is neither
the vendor's CONFIRMED nor the marketing page's number, and is exactly what
this estate actually has evidence for.

## What it measures, and what it does not

Measured: wall-clock per request and total throughput at each K, plus every
non-200 status, separately, with 429 called out. Requests are identical in
shape and differ only in the query, so a cache cannot flatter one arm.

NOT measured: behaviour at K beyond what is run here, behaviour of the PAID
routes, behaviour under a full pass's mixed load, or behaviour tomorrow. A
rate limit that is not published can be changed without telling anybody, so
an OBSERVED ceiling is evidence about one moment and is labelled that way.

**A clean run at K is not permission to run at 2K.** The escalation rule in
the handoff stands: K=4 is the conservative start and K=8 only after a full
pass with zero 429s.
"""
import argparse
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import enrich                                          # noqa: E402
from src.providers import contactout, load_env                  # noqa: E402

FREE_ROUTE = "people-count"

# Distinct enough that no cache can serve one query from another's answer, and
# ordinary enough that none of them is an unusual load on the provider.
TITLES = ["chief executive officer", "chief financial officer",
          "chief operating officer", "vice president finance",
          "head of operations", "managing director", "founder",
          "operations director", "finance director", "general manager",
          "chief marketing officer", "head of finance"]


def refuse_if_it_costs():
    """The zero is checked, not trusted. A cost that moved stops the run."""
    cost = (enrich.COSTS or {}).get(FREE_ROUTE)
    if cost is None:
        raise SystemExit(
            f"REFUSED: {FREE_ROUTE!r} is not in enrich.COSTS, so this script "
            f"cannot prove it is free. It will not spend credits to find out.")
    if cost != 0:
        raise SystemExit(
            f"REFUSED: enrich.COSTS[{FREE_ROUTE!r}] is {cost}, not 0. This "
            f"script only ever calls routes that cost nothing, and that is "
            f"the whole reason it may run a few hundred requests.")
    return cost


def one_call(title):
    """One free people-count. Returns (seconds, status_word)."""
    started = time.perf_counter()
    try:
        contactout.people_count(job_title=[title])
        return time.perf_counter() - started, "ok"
    except Exception as exc:                        # noqa: BLE001
        text = f"{type(exc).__name__}: {exc}"
        if "429" in text:
            return time.perf_counter() - started, "429"
        if "5" == text[-3:-2]:
            return time.perf_counter() - started, "5xx"
        return time.perf_counter() - started, text[:60]


def run_arm(k, requests):
    titles = [TITLES[i % len(TITLES)] for i in range(requests)]
    started = time.perf_counter()
    if k == 1:
        results = [one_call(t) for t in titles]
    else:
        with ThreadPoolExecutor(max_workers=k) as pool:
            results = list(pool.map(one_call, titles))
    wall = time.perf_counter() - started
    times = [t for t, state in results if state == "ok"]
    states = {}
    for _t, state in results:
        states[state] = states.get(state, 0) + 1
    return {"k": k, "requests": requests, "wall": wall, "states": states,
            "ok": len(times),
            "p50": statistics.median(times) if times else None,
            "p95": (sorted(times)[max(0, int(len(times) * 0.95) - 1)]
                    if times else None),
            "max": max(times) if times else None,
            "rps": (len(times) / wall) if wall else 0.0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--k", default="1,2,4",
                        help="comma-separated concurrency levels")
    parser.add_argument("--requests", type=int, default=24,
                        help="requests per arm")
    parser.add_argument("--settle", type=float, default=5.0,
                        help="seconds between arms, so one does not bleed "
                             "its backlog into the next")
    args = parser.parse_args(argv)

    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))
    refuse_if_it_costs()

    levels = [int(x) for x in str(args.k).split(",") if x.strip()]
    print(f"ContactOut {FREE_ROUTE} (FREE, enrich.COSTS = 0). "
          f"{args.requests} requests per arm.\n")
    rows = []
    for i, k in enumerate(levels):
        if i:
            time.sleep(args.settle)
        row = run_arm(k, args.requests)
        rows.append(row)
        print(f"  K={row['k']:<3} wall {row['wall']:7.2f}s  "
              f"ok {row['ok']:>3}/{row['requests']:<3}  "
              f"p50 {row['p50'] or 0:.3f}s  p95 {row['p95'] or 0:.3f}s  "
              f"max {row['max'] or 0:.3f}s  "
              f"{row['rps']:6.2f} req/s  states={row['states']}")

    base = next((r for r in rows if r["k"] == 1), None)
    print()
    if base and base["rps"]:
        for row in rows:
            if row["k"] == 1:
                continue
            speedup = row["rps"] / base["rps"]
            print(f"  K={row['k']:<3} speedup {speedup:5.2f}x   "
                  f"p50 {(row['p50'] or 0) / (base['p50'] or 1):5.2f}x the "
                  f"serial p50")

    throttled = [r for r in rows if r["states"].get("429")]
    print()
    if throttled:
        print("  429 SEEN. That is the provider's answer and it outranks any "
              "speedup above:")
        for row in throttled:
            print(f"    K={row['k']}: {row['states']['429']} of "
                  f"{row['requests']}")
        print("  Set the limiter from the HIGHEST K that saw none, not from "
              "the fastest one.")
    else:
        best = max(rows, key=lambda r: r["rps"])
        print(f"  No 429 at any K tried. Highest sustained: "
              f"{best['rps']:.2f} req/s at K={best['k']} "
              f"({best['rps'] * 60:.0f}/minute).")
        print("  CLASSIFY THIS AS OBSERVED, NOT CONFIRMED. An unpublished "
              "limit can change without notice, so this is evidence about one "
              "moment, and a clean run at K is not permission to run at 2K.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
