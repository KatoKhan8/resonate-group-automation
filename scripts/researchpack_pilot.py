#!/usr/bin/env python3
"""A BOUNDED research-pack pilot: what each source costs, and what it covers.

    py -3 scripts/researchpack_pilot.py                      # plan only
    py -3 scripts/researchpack_pilot.py --accounts 25 --live

## WHY IT IS A SCRIPT AND NOT A TEST

It spends real money on the operator's Apify account. Everything about it is
therefore explicit: `--live` or nothing is started, `--accounts` is capped at
`MAX_ACCOUNTS`, `--budget-usd` stops the walk the moment observed spend
crosses it, and `pack.MAX_CHARGE_PER_RUN_USD` stops any single actor run
that would bill more than a run of this shape ever should.

## WHAT IT MEASURES, AND WHY OBSERVED IS NOT PLANNED

`spendledger` holds the EXPECTED cost at the moment of the call, in whole
cents, rounded up. That is the right thing for a budget control and the
wrong thing for a per-account cost report: every LinkedIn run here costs a
fraction of a cent, so the ledger's honest integer is several times the real
figure. This reads what Apify actually billed - `usageTotalUsd` on each run,
plus the account's own monthly-usage total before and after, which is the
number Apify will invoice - and reports both, because a projection built on
a planned figure nobody checked is how a budget is missed.

## COVERAGE IS PER SOURCE AND IT IS ABOUT FACTS, NOT RUNS

A run that SUCCEEDED and returned nothing is not coverage. A source covers
an account when the pack came away with at least one fact of that source's
kind - one thing that can be quoted with a url and a date behind it.

## IT WRITES TO `work/`, WHICH IS GITIGNORED

The per-account rows name real prospects. The summary this prints is safe to
paste; the file is not, and `docs/` would be a data incident.
"""
import argparse
import collections
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import linkedin, researchpack, store                   # noqa: E402
from src.providers import apify, key, load_env, query, request  # noqa: E402
from src.researchpack import actors, pack                       # noqa: E402
from src.researchpack import cache as rpcache                   # noqa: E402

#: The operator said 20 to 30. A pilot that can be pointed at hundreds by a
#: flag is not a bounded pilot, so the flag cannot express it.
MAX_ACCOUNTS = 30

#: `economic_buyer` is this estate's word for the exec. `champion` is its own.
PERSONAS = {"champion": "champion", "exec": "economic_buyer"}

SOURCES = ("open_roles", "company_posts", "person_posts:champion",
           "person_posts:exec", "site_content")

KIND_OF = {"open_roles": "open_role", "company_posts": "company_post",
           "person_posts:champion": "person_post",
           "person_posts:exec": "person_post",
           "site_content": "site_page"}


def monthly_usage_usd():
    """What Apify says this billing cycle has cost. The invoice's own number."""
    status, data = request("GET", query(apify.BASE + "/users/me/usage/monthly",
                                        {"token": key(apify.KEY_VAR)}))
    body = (data or {}).get("data") or {}
    return float(body.get("totalUsageCreditsUsdAfterVolumeDiscount") or 0.0)


def contact_url(record, persona):
    """That persona's LinkedIn profile, preferring the primary contact.

    THROUGH `linkedin.canonical`, which is where this repository already
    holds the one form of a profile URL. Seven of the estate's stored values
    are a bare vanity name and the rest carry locale hosts and tracking
    parameters, so the raw field is refused by `apify.check_url` for having
    no scheme - correctly. The fix is to canonicalise the input, never to
    teach the guard to accept a schemeless string. `canonical` returns None
    for anything that is not a member profile, and the pack then reports the
    person source as unaddressable, which is the honest reading.
    """
    wanted = PERSONAS[persona]
    rows = [c for c in (record.get("contacts") or [])
            if c.get("linkedin") and (c.get("persona") or "") == wanted]
    rows.sort(key=lambda c: (not c.get("primary"), str(c.get("name") or "")))
    for row in rows:
        url = linkedin.canonical(row["linkedin"])
        if url:
            return url
    return None


def selectable(record):
    """An account worth spending research on.

    A dropped or do-not-contact record is money spent on somebody nobody may
    write to, and a record with no company name cannot reach the jobs actor
    at all - so it would measure the pilot's selection rather than the
    source's coverage.
    """
    if record.get("do_not_contact") or record.get("drop_reason"):
        return False
    return bool(record.get("domain")) and bool(record.get("company"))


def choose(limit):
    """Deterministic by domain, so a re-run measures the same accounts."""
    rows = [r for r in store.load() if selectable(r)]
    rows.sort(key=lambda r: str(r.get("domain") or "").lower())
    return rows[:limit]


def measure(observed):
    """A runner that is the production lifecycle plus the run id.

    `pack._live_runner` deliberately returns rows and nothing else -
    production has no use for a run id. A cost measurement does: the billed
    figure lives on the run, and reconstructing it from item counts would be
    the planned number again wearing a different hat. The polling, the
    timeout and the dataset read are still `providers.apify`'s.
    """
    def runner(actor, payload, limit):
        started = pack._start(actor, payload)
        finished = apify.wait_for(started["id"]) or {}
        dataset = finished.get("dataset_id") or started.get("dataset_id")
        rows = apify.dataset_items(dataset, limit) if dataset else []
        observed.append({"actor": actor, "run_id": started["id"],
                         "status": finished.get("status"),
                         "rows": len(rows)})
        return rows
    return runner


def billed(run_ids):
    """What each run actually cost, read back after the events settle."""
    out = {}
    token = key(apify.KEY_VAR)
    for run_id in run_ids:
        status, data = request("GET", query(
            apify.BASE + "/actor-runs/" + run_id, {"token": token}))
        row = (data or {}).get("data") or {}
        out[run_id] = {"usd": float(row.get("usageTotalUsd") or 0.0),
                       "status": row.get("status"),
                       "events": row.get("chargedEventCounts") or {}}
    return out


def one(record, client, observed, resolve_slug=False):
    """One account's pack, with the runs it started attributed to it."""
    mark = len(observed)
    built = researchpack.build(
        str(record.get("domain")), live=True, client=client,
        company=record.get("company"),
        champion=contact_url(record, "champion"),
        exec_profile=contact_url(record, "exec"),
        resolve_slug=resolve_slug,
        runner=measure(observed))
    built["runs"] = [r["run_id"] for r in observed[mark:]]
    built["company"] = record.get("company")
    return built


def summarise(packs, charges):
    """Coverage per source, and observed cost per account per source."""
    n = len(packs) or 1
    by_source = collections.OrderedDict()
    for source in SOURCES:
        kind = KIND_OF[source]
        subject = source.split(":")[1] if ":" in source else None
        covered = 0
        attempted = 0
        for built in packs:
            if source in built["unaddressable"]:
                continue
            attempted += 1
            hits = [f for f in built["facts"]
                    if f["kind"] == kind
                    and (subject is None or f.get("subject") == subject)]
            covered += 1 if hits else 0
        by_source[source] = {"attempted": attempted, "covered": covered,
                             "coverage": covered / float(n)}
    total = sum(c["usd"] for c in charges.values())
    by_actor = collections.Counter()
    for c in charges.values():
        by_actor[c.get("actor", "?")] += c["usd"]
    return {"accounts": len(packs), "by_source": by_source,
            "observed_usd_total": round(total, 6),
            "observed_usd_per_account": round(total / float(n), 6)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--accounts", type=int, default=25)
    parser.add_argument("--budget-usd", type=float, default=3.0)
    parser.add_argument("--client", default="productive")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--resolve-slug", action="store_true",
                        help="after the jobs run fails to yield a slug, ask "
                             "harvestapi/linkedin-company for it. Off by "
                             "default: the operator asked for the slug to "
                             "come out of the jobs run, and this measures "
                             "what the rest would cost")
    parser.add_argument("--cold", action="store_true",
                        help="a pilot-only research cache, so the measurement "
                             "is a COLD one. A warm cache reports a cost per "
                             "account of nearly zero and proves only that the "
                             "cache works")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    load_env()
    if args.cold:
        os.environ[rpcache.CACHE_VAR] = os.path.join(
            os.path.dirname(store.queue_path()),
            "researchpack-pilot-cache.json")
    count = max(1, min(int(args.accounts), MAX_ACCOUNTS))
    chosen = choose(count)

    print("research pack pilot")
    print("  accounts        %d (cap %d)" % (len(chosen), MAX_ACCOUNTS))
    print("  budget          $%.2f, and the walk stops on it" % args.budget_usd)
    print("  per-run ceiling $%.2f" % pack.MAX_CHARGE_PER_RUN_USD)
    print("  planned cost    $%.4f per account, all four sources"
          % sum(actors.usd_per_account(n) for n in
                ("open_roles", "company_posts", "person_posts", "site_content")))
    for name in ("open_roles", "company_posts", "person_posts", "site_content"):
        spec = actors.ACTORS[name]
        print("    %-14s %-38s $%.5f"
              % (name, spec["actor"], actors.usd_per_account(name)))
    if not args.live:
        print("\nnot live: nothing was started and nothing was charged.")
        return 0

    before = monthly_usage_usd()
    print("\napify monthly usage before: $%.4f" % before)

    observed, packs = [], []
    started = time.time()
    for i, record in enumerate(chosen, 1):
        charged = sum(c["usd"] for c in
                      billed([r["run_id"] for r in observed]).values()) \
            if observed else 0.0
        if charged >= args.budget_usd:
            print("STOPPING at account %d: observed $%.4f has reached the "
                  "budget" % (i, charged))
            break
        built = one(record, args.client, observed, args.resolve_slug)
        packs.append(built)
        print("  %3d/%d %-34s facts=%-3d bought=%s unaddressable=%s"
              % (i, len(chosen), str(record.get("domain"))[:34],
                 built["fact_count"], ",".join(built["bought"]) or "-",
                 ",".join(sorted(built["unaddressable"])) or "-"))

    # Events settle a moment after a run ends, so the charge is read once at
    # the end rather than per account - a figure read too early reads as the
    # actor-start alone, which is how a per-event actor looks free.
    time.sleep(10)
    charges = billed([r["run_id"] for r in observed])
    for row in observed:
        charges[row["run_id"]]["actor"] = row["actor"]
        charges[row["run_id"]]["rows"] = row["rows"]
    after = monthly_usage_usd()

    summary = summarise(packs, charges)
    summary["slug_source"] = dict(collections.Counter(
        b.get("slug_source") or "none" for b in packs))
    summary["monthly_usage_before"] = before
    summary["monthly_usage_after"] = after
    summary["monthly_usage_delta"] = round(after - before, 6)
    summary["seconds"] = round(time.time() - started, 1)
    summary["per_actor_usd"] = dict(collections.Counter(
        {a: round(sum(c["usd"] for c in charges.values()
                      if c.get("actor") == a), 6)
         for a in {c.get("actor") for c in charges.values()}}))

    out = args.out or os.path.join(os.path.dirname(store.queue_path()),
                                   "researchpack-pilot-%s.json"
                                   % time.strftime("%Y%m%dT%H%M%SZ",
                                                   time.gmtime()))
    with open(out, "w", encoding="utf-8") as handle:
        json.dump({"summary": summary, "packs": packs, "charges": charges},
                  handle, indent=1, default=str, ensure_ascii=False)

    print("\nwhere the company LinkedIn slug came from")
    for where, count in sorted(summary["slug_source"].items(),
                               key=lambda kv: -kv[1]):
        print("  %-24s %2d/%-2d  %5.1f%%"
              % (where, count, summary["accounts"],
                 100.0 * count / float(summary["accounts"] or 1)))

    print("\ncoverage per source, over %d account(s)" % summary["accounts"])
    for source, row in summary["by_source"].items():
        print("  %-24s %2d/%-2d addressable, %2d covered  %5.1f%%"
              % (source, row["attempted"], summary["accounts"],
                 row["covered"], 100.0 * row["coverage"]))
    print("\nobserved spend")
    for actor, usd in sorted(summary["per_actor_usd"].items()):
        print("  %-44s $%.5f" % (actor, usd))
    print("  %-44s $%.5f" % ("TOTAL", summary["observed_usd_total"]))
    print("  %-44s $%.5f" % ("per account", summary["observed_usd_per_account"]))
    print("  %-44s $%.5f" % ("apify monthly-usage delta",
                             summary["monthly_usage_delta"]))
    print("\nwrote %s  (work/ is gitignored and these rows name real "
          "prospects)" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
