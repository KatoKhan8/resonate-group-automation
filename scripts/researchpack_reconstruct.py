#!/usr/bin/env python3
"""What a killed research walk actually did: from the run records and the cache.

    py -3 scripts/researchpack_reconstruct.py --work <dir> \
        --since 2026-09-24T21:50:00.000Z --env <path to config/.env>

## WHY THIS EXISTS, TWICE NOW

`scripts/researchpack_pilot.py` was killed by the harness at account 24 of
25 before it printed its own summary, and its block-buffered stdout went
with it. `scripts/researchpack_cohort.py` was killed at account 65 of 92 the
same way. In both cases nothing MEASURED was lost, and that is the point
worth keeping: the facts are in the pack cache, the committed credits are in
`work/spend-ledger.jsonl`, and the charges are on Apify's own run records.
A summary a script prints at the end is the most fragile copy of all three.

So this reconstructs the report from the three durable sources instead of
from the process that died:

  ledger   `spendledger` rows in the window - what we COMMITTED, in credits
  apify    `GET /v2/actor-runs` in the window - what we were BILLED, in USD
  cache    `work/researchpack-cohort-*-cache.json` - what we CAME AWAY WITH

Observed and planned are kept apart everywhere, for the reason
`src/costs.py` exists: the ledger's integer cent is rounded up and every
LinkedIn run costs a fraction of one.

Reads only. It starts nothing and writes no ledger row.
"""
import argparse
import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

KINDS = ("open_role", "company_post", "person_post", "site_page")


def runs_in_window(since, until=None, limit=1000):
    """This account's actor runs, newest first, filtered on `startedAt`.

    The run ids the walk collected died with it, so they are asked of the
    provider instead. `GET /v2/actor-runs` carries `usageTotalUsd` and the
    actor id on every row, which is the same field
    `scripts/researchpack_pilot.py` read per run.
    """
    from src.providers import apify, key, query, request
    token = key(apify.KEY_VAR)
    status, data = request("GET", query(apify.BASE + "/actor-runs",
                                        {"token": token, "limit": limit,
                                         "desc": "1"}))
    items = ((data or {}).get("data") or {}).get("items") or []
    out = []
    for row in items:
        started = str(row.get("startedAt") or "")
        if started < since:
            continue
        if until and started > until:
            continue
        out.append(row)
    return out


def actor_names(runs):
    """`actId` is an id, not a name. Resolve each one once."""
    from src.providers import apify, key, query, request
    token = key(apify.KEY_VAR)
    names = {}
    for act_id in sorted({r.get("actId") for r in runs if r.get("actId")}):
        status, data = request("GET", query(
            apify.BASE + "/acts/" + str(act_id), {"token": token}))
        body = (data or {}).get("data") or {}
        owner = body.get("username") or "?"
        names[act_id] = "%s/%s" % (owner, body.get("name") or act_id)
    return names


def cache_rows(work_dir, pattern):
    out = {}
    for path in sorted(glob.glob(os.path.join(work_dir, pattern))):
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        for k, v in (data or {}).items():
            if isinstance(v, dict):
                out[k] = v
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", default=os.path.join(ROOT, "work"))
    parser.add_argument("--since", required=True)
    parser.add_argument("--until", default=None)
    parser.add_argument("--client", default="productive")
    parser.add_argument("--env", default=None)
    parser.add_argument("--cache-glob",
                        default="researchpack-cohort-*-cache.json")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    work_dir = os.path.abspath(args.work)
    os.environ["QUEUE"] = os.path.join(work_dir, "queue.jsonl")
    os.environ["SPEND_LEDGER"] = os.path.join(work_dir, "spend-ledger.jsonl")
    from src import spendledger
    from src.providers import load_env
    load_env(args.env) if args.env else load_env()

    # ---------------------------------------------------------- the ledger
    ledger = [r for r in spendledger.load()
              if isinstance(r, dict) and r.get("client") == args.client
              and str(r.get("at") or "") >= args.since
              and (not args.until or str(r.get("at") or "") <= args.until)]
    by_call = collections.Counter()
    for row in ledger:
        by_call[row.get("call")] += int(row.get("expected_cost") or 0)

    # ------------------------------------------------- apify's own records
    runs = runs_in_window(args.since, args.until)
    names = actor_names(runs)
    per_actor_usd = collections.Counter()
    per_actor_runs = collections.Counter()
    per_actor_status = collections.defaultdict(collections.Counter)
    for row in runs:
        name = names.get(row.get("actId"), str(row.get("actId")))
        per_actor_usd[name] += float(row.get("usageTotalUsd") or 0.0)
        per_actor_runs[name] += 1
        per_actor_status[name][row.get("status")] += 1
    total_usd = sum(per_actor_usd.values())

    # ------------------------------------------------------- what we kept
    entries = cache_rows(work_dir, args.cache_glob)
    domains = {e.get("domain") for e in entries.values() if e.get("domain")}
    covered = collections.defaultdict(set)
    facts_by_kind = collections.Counter()
    for entry in entries.values():
        domain = entry.get("domain")
        for fact in entry.get("facts") or []:
            if not isinstance(fact, dict):
                continue
            facts_by_kind[fact.get("kind")] += 1
            covered[fact.get("kind")].add(domain)
    site_outcomes = collections.Counter(
        (e.get("site") or {}).get("outcome") for e in entries.values()
        if e.get("profile") == "site_content")

    n = len(domains) or 1
    print("RECONSTRUCTED from the ledger, Apify's run records and the cache")
    print("window  %s .. %s" % (args.since, args.until or "now"))
    print("cache   %s" % os.path.join(work_dir, args.cache_glob))

    print("\nWHAT WAS COMMITTED  (spend ledger, expected credits, rounded up)")
    print("  %d row(s), %d credit(s)"
          % (len(ledger), sum(by_call.values())))
    for call, credits in sorted(by_call.items(), key=lambda kv: -kv[1]):
        count = len([r for r in ledger if r.get("call") == call])
        print("    %-16s %3d row(s)  %4d credit(s)" % (call, count, credits))

    print("\nWHAT WAS BILLED  (Apify run records, usageTotalUsd)")
    for name in sorted(per_actor_usd):
        print("    %-40s %3d run(s)  $%.5f  %s"
              % (name, per_actor_runs[name], per_actor_usd[name],
                 dict(per_actor_status[name])))
    print("    %-40s %3d run(s)  $%.5f" % ("TOTAL", len(runs), total_usd))
    print("    %-40s            $%.5f  over %d account(s)"
          % ("per account", total_usd / n, len(domains)))

    print("\nWHAT WE CAME AWAY WITH  (the cache, %d account(s))" % len(domains))
    for kind in KINDS:
        print("    %-14s %3d account(s) covered  %5.1f%%   %4d fact(s)"
              % (kind, len(covered[kind]), 100.0 * len(covered[kind]) / n,
                 facts_by_kind[kind]))
    any_fact = {d for kind in KINDS for d in covered[kind]}
    print("    %-14s %3d account(s)            %5.1f%%"
          % ("ANY", len(any_fact), 100.0 * len(any_fact) / n))
    print("\n    our crawler's outcomes: %s" % dict(site_outcomes))

    summary = {
        "window": [args.since, args.until],
        "ledger_rows": len(ledger),
        "ledger_credits": sum(by_call.values()),
        "ledger_by_call": dict(by_call),
        "apify_runs": len(runs),
        "apify_usd_total": round(total_usd, 6),
        "apify_usd_per_account": round(total_usd / n, 6),
        "apify_by_actor_usd": {k: round(v, 6)
                               for k, v in per_actor_usd.items()},
        "apify_runs_by_actor": dict(per_actor_runs),
        "accounts_in_cache": len(domains),
        "covered": {k: len(v) for k, v in covered.items()},
        "facts_by_kind": dict(facts_by_kind),
        "site_outcomes": dict(site_outcomes),
    }
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=1, default=str)
        print("\nwrote %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
