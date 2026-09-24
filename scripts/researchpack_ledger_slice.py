#!/usr/bin/env python3
"""The spend-ledger rows one research run wrote, by time window.

    py -3 scripts/researchpack_ledger_slice.py --work <dir> \
        --since 2026-09-24T21:55:00+00:00 --client productive

## WHY NOT JUST READ `spent(client, day=today)` TWICE

Because the day rolls over. `spendledger.record` stamps `day` from UTC at
the moment of the call, and a walk that starts at 21:55Z and runs for an
hour and a quarter writes rows into TWO days. A before/after pair taken
against the day the walk started reports the second half as zero, which
reads as a run that stopped spending rather than one that crossed midnight.

So the proof of what a run cost is the ROWS, selected on `at`, and this
prints them: the count, the credits, the split per call, and the exact
first and last row so the window can be checked against the run's own log.

Reads only. It never writes to the ledger and has no verb that could.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", default=os.path.join(ROOT, "work"))
    parser.add_argument("--since", required=True,
                        help="ISO timestamp; rows with `at` >= this")
    parser.add_argument("--until", default=None)
    parser.add_argument("--client", default="productive")
    parser.add_argument("--provider", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    os.environ["QUEUE"] = os.path.join(os.path.abspath(args.work),
                                       "queue.jsonl")
    os.environ["SPEND_LEDGER"] = os.path.join(os.path.abspath(args.work),
                                              "spend-ledger.jsonl")
    from src import spendledger

    rows = []
    for row in spendledger.load():
        if not isinstance(row, dict):
            continue
        if row.get("client") != args.client:
            continue
        at = str(row.get("at") or "")
        if at < args.since:
            continue
        if args.until and at > args.until:
            continue
        if args.provider and row.get("provider") != args.provider:
            continue
        rows.append(row)

    by_call = collections.Counter()
    by_day = collections.Counter()
    for row in rows:
        by_call[(row.get("provider"), row.get("call"))] += int(
            row.get("expected_cost") or 0)
        by_day[row.get("day")] += int(row.get("expected_cost") or 0)
    total = sum(by_day.values())

    if args.json:
        print(json.dumps({"rows": len(rows), "credits": total,
                          "by_call": {"%s/%s" % k: v
                                      for k, v in by_call.items()},
                          "by_day": dict(by_day),
                          "first": rows[0] if rows else None,
                          "last": rows[-1] if rows else None}, indent=1))
        return 0

    print("ledger %s" % spendledger.path())
    print("client %s, window %s .. %s"
          % (args.client, args.since, args.until or "now"))
    print("\n%d row(s), %d credit(s)" % (len(rows), total))
    for (provider, call), credits in sorted(by_call.items(),
                                            key=lambda kv: -kv[1]):
        count = len([r for r in rows if r.get("provider") == provider
                     and r.get("call") == call])
        print("  %-10s %-16s %3d row(s)  %4d credit(s)"
              % (provider, call, count, credits))
    print("\nper ledger day, because a long walk crosses UTC midnight")
    for day, credits in sorted(by_day.items()):
        print("  %-12s %4d credit(s)" % (day, credits))
    if rows:
        print("\nfirst %s" % json.dumps(rows[0]))
        print("last  %s" % json.dumps(rows[-1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
