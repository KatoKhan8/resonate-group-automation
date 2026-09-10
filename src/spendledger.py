#!/usr/bin/env python3
"""What this client has already spent, durably, across runs.

## The hole this fills

`enrich.Budget` is the only spend control there is, and it lives in memory for
the length of one invocation. So `--cap 260` means "260 credits in THIS run"
and nothing anywhere remembers the last one. On 2026-09-10 I ran three passes
over the same cohort at cap 260 each; every one was individually within
budget, and no part of the system could have told you the total.

`pilotcaps` bounds VOLUME - companies, contacts, sends per day - which is a
different question and does not bound money at all. A single company can cost
one credit or forty depending on how far down the waterfall it goes.

There is also no monetary budget anywhere in this repository. Searched for on
2026-09-10: no per-day cap, no per-provider cap, no total. The only "$5" in
the tree is a fixture string in BUILD-SPEC about a client's negotiating
position.

## What this does NOT do

**It does not choose a budget.** A ceiling nobody agreed to is not a safety
control, it is a number that will be raised the first time it is
inconvenient, and inventing one would make an operator's decision look like
an engineering default. `caps()` returns whatever the client config states
and `None` where it states nothing, and `None` means unlimited and SAYS so.

It also does not record observed cost. Expected and observed are different
claims - that is `costs.py`'s whole premise - and this ledger holds the
expected side only, at the moment of the call, which is the only moment the
system reliably knows anything.

## Fail-safe

An unreadable ledger REFUSES rather than allowing. A spend control that opens
when its own state is missing is a spend control that fails exactly when
something is already wrong.
"""
import argparse
import datetime
import json
import os

from . import store

# Where a client's declared ceilings live, if it declares any.
CONFIG_KEY = "budget"

# The ceilings this module understands. Each is credits, per the scope named,
# and each is None unless the client config says otherwise.
SCOPES = ("per_run", "per_day", "per_provider_per_day", "total")


class BudgetExceeded(RuntimeError):
    """A durable ceiling would be crossed. Refused, never trimmed."""


class LedgerUnreadable(RuntimeError):
    """The spend state could not be read, so no spend may be authorised."""


def path():
    """Beside the queue, so spend and the records it bought move together."""
    return os.path.abspath(os.environ.get("SPEND_LEDGER")
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           "spend-ledger.jsonl"))


def load():
    try:
        return store.read_jsonl(path())
    except FileNotFoundError:
        return []
    except Exception as e:                       # a corrupt ledger is not empty
        raise LedgerUnreadable(
            f"{path()} could not be read ({type(e).__name__}). Refusing to "
            f"authorise spend against unknown state.") from None


def today(now=None):
    return (now or datetime.datetime.now(datetime.timezone.utc)).date().isoformat()


def record(client, provider, call, expected_cost, run_id=None, at=None,
           rows=None):
    """Append one expected charge. Called at the moment of the call.

    Returns the row, so a caller can log it. Appending rather than updating a
    running total on purpose: a total is a derived number and a derived number
    that disagrees with its inputs is the thing nobody can debug.
    """
    row = {"at": at or store.now(), "day": today(),
           "client": client, "provider": provider, "call": call,
           "expected_cost": int(expected_cost or 0), "run_id": run_id}
    # A first run on a fresh deployment has no directory yet, and the spend
    # control refusing to record because of that would be the worst possible
    # failure: the call still happens, and nothing counts it.
    os.makedirs(os.path.dirname(path()), exist_ok=True)
    with open(path(), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def spent(client=None, day=None, provider=None, rows=None):
    """Expected credits already committed, filtered as asked.

    `client=None` counts every tenant together, which is almost never what a
    caller wants - `actionledger.count_on` had the same default and it was a
    real bug there. Named here rather than fixed, because a spend REPORT
    across all clients is legitimate and a spend CHECK across all clients is
    not; `check()` below requires a client.
    """
    rows = load() if rows is None else rows
    total = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if client is not None and row.get("client") != client:
            continue
        if day is not None and row.get("day") != day:
            continue
        if provider is not None and row.get("provider") != provider:
            continue
        total += int(row.get("expected_cost") or 0)
    return total


def caps(config):
    """The client's declared ceilings, and `None` where it declares none.

    `None` is UNLIMITED and is reported as such rather than defaulted to a
    number somebody would have to discover by hitting it.
    """
    declared = (config or {}).get(CONFIG_KEY) or {}
    return {scope: declared.get(scope) for scope in SCOPES}


def check(client, config, cost, provider=None, rows=None, day=None):
    """May this client spend `cost` more? Raises `BudgetExceeded` if not.

    Every ceiling is checked, and the FIRST one crossed is the one named, so
    the refusal says which limit applied rather than that some limit did.
    """
    if not client:
        raise BudgetExceeded(
            "a spend check needs a client; an unscoped budget is one client "
            "paying for another's run")
    rows = load() if rows is None else rows
    day = day or today()
    ceilings = caps(config)
    checks = (
        ("per_day", spent(client, day=day, rows=rows), f"today ({day})"),
        ("total", spent(client, rows=rows), "in total"),
    )
    for scope, already, where in checks:
        limit = ceilings.get(scope)
        if limit is not None and already + cost > limit:
            raise BudgetExceeded(
                f"{client} has committed {already} credit(s) {where} and this "
                f"call expects {cost}, which crosses the {scope} ceiling of "
                f"{limit}")
    limit = ceilings.get("per_provider_per_day")
    if limit is not None and provider:
        already = spent(client, day=day, provider=provider, rows=rows)
        if already + cost > limit:
            raise BudgetExceeded(
                f"{client} has committed {already} credit(s) to {provider} "
                f"today and this call expects {cost}, which crosses the "
                f"per_provider_per_day ceiling of {limit}")
    return True


def report(client=None, config=None, rows=None):
    """What has been committed, against what was declared."""
    rows = load() if rows is None else rows
    ceilings = caps(config) if config is not None else dict.fromkeys(SCOPES)
    by_provider, by_day = {}, {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if client is not None and row.get("client") != client:
            continue
        cost = int(row.get("expected_cost") or 0)
        by_provider[row.get("provider")] = by_provider.get(row.get("provider"), 0) + cost
        by_day[row.get("day")] = by_day.get(row.get("day"), 0) + cost
    return {
        "client": client,
        "expected_total": sum(by_day.values()),
        "expected_today": by_day.get(today(), 0),
        "by_provider": by_provider,
        "by_day": by_day,
        "ceilings": ceilings,
        "unlimited": [s for s, v in ceilings.items() if v is None],
        "note": "expected credits only. What the providers actually charged "
                "is a different question and belongs to src/costs.py",
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.spendledger")
    p.add_argument("--client")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    from . import clients
    config = None
    if a.client:
        try:
            config = clients.load(a.client)
        except Exception:
            config = {}
    out = report(a.client, config)
    if a.json:
        print(json.dumps(out, indent=1))
        return 0
    print(f"expected total   {out['expected_total']}")
    print(f"expected today   {out['expected_today']}")
    for provider, cost in sorted(out["by_provider"].items(),
                                 key=lambda kv: -kv[1]):
        print(f"  {str(provider):<14} {cost}")
    print("\nceilings")
    for scope, limit in out["ceilings"].items():
        print(f"  {scope:<24} {'UNLIMITED - none declared' if limit is None else limit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
