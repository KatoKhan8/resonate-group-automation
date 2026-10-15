#!/usr/bin/env python3
"""Which campaigns are past a queue reader's cap, and which cross it next.

    py -3 scripts/queue_wall_check.py
    py -3 scripts/queue_wall_check.py --counts docs/state/QUEUE-COUNTS-2026-10-15.json
    py -3 scripts/queue_wall_check.py --json --max-age-days 7

READ-ONLY. Writes nothing. Makes NO provider call: it reads a dated counts
file and refuses one that is stale, because the thing it must never do is
report a current verdict off an old measurement.

TASK-0150. `bison.scheduled_emails` refuses a queue past `cap` pages rather
than returning a prefix, and TASK-0130 measured FIVE distinct effective caps
for that one endpoint across eighteen production call sites. So a campaign
can be readable by the watcher and invisible to the gate beside it, and
before this there was no run that said so: campaign 491 produced nothing,
once, silently, inside whichever caller asked.

## WHAT EXITS NON-ZERO, AND WHY THREE CODES

    0   every campaign fits every reader's cap AND survives one more step
    1   at least one campaign is OVER a cap, or AT-RISK on one more step
    2   cannot assess - the counts are stale, or a campaign's size is UNKNOWN

The margin is one more sequence step at today's lead count, because that is
the largest discrete jump a queue can take and it needs no lead added. It is
arithmetic about an event the operator can schedule this afternoon, not a
forecast. See `src/queuewall.py` for the derivation.

## THE COUNTS FILE IS NOT THE AUTHORITY

The authority for a queue row count is `bison.scheduled_emails` and for a
lead count `bison.campaign_lead_count`. The file exists so this check can run
and be tested without a provider call, and it carries `measured_at` so its
age is a fact rather than a hope. Past `--max-age-days` this script assesses
NOTHING and exits 2.
"""
import argparse
import datetime
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import queuewall                                       # noqa: E402

DEFAULT_COUNTS = os.path.join(ROOT, "docs", "state",
                              "QUEUE-COUNTS-2026-10-15.json")

EXIT_OK, EXIT_WALL, EXIT_CANNOT_ASSESS = 0, 1, 2


def exit_code(result):
    """Stale or UNKNOWN is 2; OVER or AT-RISK is 1; otherwise 0.

    Order matters: a run that could not assess must not report the same code
    as a run that assessed and found a wall, for the same reason the bounce
    stop's BLIND is not its STOP.
    """
    if result.get("stale"):
        return EXIT_CANNOT_ASSESS
    verdicts = [c["worst_verdict"] for c in result.get("campaigns") or []]
    if queuewall.UNKNOWN in verdicts:
        return EXIT_CANNOT_ASSESS
    if queuewall.OVER in verdicts or queuewall.AT_RISK in verdicts:
        return EXIT_WALL
    return EXIT_OK


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--counts", default=DEFAULT_COUNTS)
    ap.add_argument("--max-age-days", type=float, default=7.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    with open(args.counts, encoding="utf-8") as handle:
        counts = json.load(handle)
    result = queuewall.assess(counts, max_age_days=args.max_age_days)
    code = exit_code(result)

    if args.json:
        print(json.dumps(dict(result, exit_code=code), indent=1, default=str))
        return code

    print(f"\nQUEUE WALL CHECK  counts measured {result['measured_at']}  "
          f"age {result['age_days']} day(s)  limit {result['max_age_days']}")
    if result.get("stale"):
        # NOTHING IS ASSESSED AND NOTHING IS PRINTED AS THOUGH IT WERE. The
        # one failure mode worse than no check is a check reporting a clean
        # table off counts nobody has refreshed.
        print(f"\n  {result['why']}")
        print(f"  verdict CANNOT-ASSESS  exit {code}")
        return code

    caps = ", ".join(f"{name} {info['cap']}p/{info['wall_rows']}r"
                     for name, info in result["by_reader"].items())
    print(f"  readers: {caps}\n")
    header = (f"  {'camp':>5} {'status':<10} {'leads':>5} {'rows':>5} "
              f"{'pg':>3} {'st':>2} {'verdict':<8} {'+leads':>7}  "
              f"invisible to")
    print(header)
    for entry in result["campaigns"]:
        tightest = entry["by_reader"][result["readers"][0]]
        head = tightest["leads_of_headroom"]
        print(f"  {entry['campaign_id']:>5} {str(entry['status'] or '?'):<10} "
              f"{_n(entry['leads']):>5} {_n(entry['rows']):>5} "
              f"{_n(entry['pages']):>3} {_n(entry['steps']):>2} "
              f"{entry['worst_verdict']:<8} {_n(head):>7}  "
              f"{', '.join(entry['invisible_to']) or '-'}")
    for entry in result["campaigns"]:
        if entry["worst_verdict"] in queuewall.PASSING:
            continue
        # NAMED, WITH ITS NUMBERS AND THE CAP IT HIT. A campaign that
        # produces nothing has to be distinguishable from a campaign that has
        # nothing, and the difference is this line.
        for name in result["readers"]:
            one = entry["by_reader"][name]
            if one["verdict"] in queuewall.PASSING:
                continue
            print(f"\n  {one['verdict']} {entry['campaign_id']} for "
                  f"{name} (cap {one['cap']} pages = {one['wall_rows']} "
                  f"rows): {one['why']}")
    print(f"\n  totals: {result['total_rows']} rows, "
          f"{result['total_row_pages']} pages of rows, "
          f"{result['requests_per_pass']} requests a pass "
          f"(an empty queue still costs one)")
    print(f"\n  {result['why']}")
    print(f"  exit {code}")
    return code


def _n(value):
    return "?" if value is None else str(value)


if __name__ == "__main__":
    raise SystemExit(main())
